"""D076 / Q16 — per-bucket gated-cohort trade-rate posteriors.

Q16 surfaced that `expected_trades` measured indicator activations rather
than trades — the 77% zero-trade survival rate proved the activations
heuristic could not discriminate. This module replaces it with a learned
posterior over real outcomes.

For each `(hypothesis, dte_bucket, directional_family)` bucket observed in
the gated_runs cohort, compute the Bayesian-smoothed posterior probability
that a config in that bucket clears `min_trades` actual trades. The
filter rejects configs whose bucket posterior falls below
`min_pass_probability`; buckets with fewer than `min_bucket_samples`
gated runs fall back to the activations heuristic (cold-start).

Bucket key shape matches the operator's diagnostic frame (Q16/Q17): the
relative_value x swing_short x pairs bucket — 370/375 zero-trade in the
2026-05-15 → 2026-05-20 cohort — flips to ~100% rejection under this
prior, while mean_reversion x swing_short x mean_reversion (the
healthy buckets) is unaffected.

Mirrors `forge.feedback.rejection_weights` in design: join Forge's
submissions to Crucible's gated_runs by config_hash, bucket, and
Beta(alpha, beta)-smooth so a single unlucky bucket can't lock itself
out. Cold-start (empty cohort) returns `{}` — caller treats as "no
prior", filter falls through to the legacy heuristic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb
    from crucible_contracts import GatedRun, RegistrySnapshot


# Beta prior over per-bucket P(n_trades >= min_trades). Same shape as
# `rejection_weights.DEFAULT_ALPHA/BETA` so cold-start buckets get prior
# mean ~0.09 — well above the proposed default `min_pass_probability` of
# 0.10's complement, so a bucket needs real evidence to be rejected even
# at the floor. A bucket with 100 observed trials and 0 passes gets
# posterior (1+0) / (1+10+100) = 1/111 ≈ 0.009 — strongly rejected.
DEFAULT_ALPHA: float = 1.0
DEFAULT_BETA: float = 10.0

# Default `min_trades` matches `ExpectedTradeCountCalibration.min_trades`.
# Kept here as a module constant so callers that compute priors without a
# `Calibration` (CLI helpers, tests) don't need to plumb one in.
DEFAULT_MIN_TRADES: int = 50

# D081 — grammar-version weighting. Gated runs submitted under a grammar
# version other than the caller's `current_grammar_version` contribute to a
# bucket's posterior at this weight instead of 1.0. Down-weighting (rather than
# discarding) keeps legacy signal alive for buckets that have no current-version
# data yet — e.g. relative_value with 0 v4 gated runs — so the filter doesn't go
# inert and re-flood Crucible, while current-version evidence comes to dominate
# as it accumulates. 0.25 ⇒ one current-version run is worth ~4 prior-version runs.
DEFAULT_PRIOR_VERSION_WEIGHT: float = 0.25

# D098 — hypotheses whose pre-current-grammar-version gated cohort is
# structurally invalid (a now-fixed defect, not a real edge signal) and so must
# be re-learned from current-version evidence only. The production CLI passes
# this set to `compute_trade_rate_priors` as `cold_start_hypotheses`.
#
# relative_value: its ~100% zero-trade history (e.g. 370/375 in the 2026-05-15
# cohort) was Crucible's pre-4f5271f pairs-loading bug — each run reached only
# 1-5 of 37 pairs. Commit 4f5271f loads all pair legs regardless of tier, so v5
# is relative_value's first fair test; down-weighting (D081) alone would leave
# its high-n poisoned bucket in empirical-prior mode and block it at pre-filter.
# Remove an entry once the hypothesis has a representative current-version
# cohort — the D081 down-weighting path then suffices.
COLD_START_HYPOTHESES: frozenset[str] = frozenset({"relative_value"})


BucketKey = tuple[str, str, str]  # (hypothesis, dte_bucket, directional_family)


@dataclass(frozen=True, slots=True)
class BucketStats:
    """Gated-cohort outcomes for one `(hypothesis, dte_bucket, family)` bucket.

    `posterior_p_pass` is the Beta-smoothed P(n_trades >= min_trades),
    which the filter compares against `min_pass_probability`. Lower
    posterior → more likely to reject. `n_total` lets the filter apply
    the `min_bucket_samples` cold-start threshold.
    """

    n_total: int
    n_pass: int
    n_zero_trade: int
    posterior_p_pass: float


def _extract_bucket_inputs(
    config_json: object,
) -> tuple[str, str, str] | None:
    """Pull `(hypothesis, dte_bucket, directional_indicator_id)` from a config_json.

    Returns None when the row's shape is wrong (corrupt rows, legacy
    rows missing the discriminator fields). Caller skips the row.
    """
    if isinstance(config_json, str):
        try:
            cfg = json.loads(config_json)
        except (json.JSONDecodeError, ValueError):
            return None
    elif isinstance(config_json, dict):
        cfg = config_json
    else:
        return None

    if not isinstance(cfg, dict):
        return None
    hypothesis = cfg.get("hypothesis")
    dte_bucket = cfg.get("dte_bucket")
    if not isinstance(hypothesis, str) or not isinstance(dte_bucket, str):
        return None

    directional_indicator: str | None = None
    for sig in cfg.get("signals", []):
        if not isinstance(sig, dict):
            continue
        if sig.get("role") != "directional":
            continue
        indicators = sig.get("indicators") or ()
        if not indicators:
            continue
        candidate = indicators[0]
        if isinstance(candidate, str):
            directional_indicator = candidate
            break
    if directional_indicator is None:
        return None
    return hypothesis, dte_bucket, directional_indicator


def compute_trade_rate_priors(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    registry: RegistrySnapshot,
    *,
    min_trades: int = DEFAULT_MIN_TRADES,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    current_grammar_version: str | None = None,
    prior_version_weight: float = DEFAULT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
) -> dict[BucketKey, BucketStats]:
    """Per-bucket P(n_trades >= min_trades) posteriors from the gated cohort.

    Joins `gated_runs` (config_hash + trade_count) to Forge's
    `submissions` table (config_hash + config_json) to extract the
    `(hypothesis, dte_bucket, directional_indicator)` per row, then maps
    the indicator to its family via `registry.indicators`. Configs whose
    directional indicator isn't in the registry are skipped (the bucket
    can't be keyed without a family). Empty cohort → empty dict.

    `alpha` / `beta` are the Beta-prior parameters; defaults match
    `rejection_weights`'s mild prior favouring exploration. `min_trades`
    is the threshold that defines a "pass" in the underlying cohort —
    set it equal to `ExpectedTradeCountCalibration.min_trades` so the
    posterior measures what the filter actually wants.

    D081 — `current_grammar_version`: when set, gated runs submitted under a
    different grammar version (resolved via `submissions -> batch_summaries`)
    are down-weighted to `prior_version_weight` in the posterior, so a config
    built under grammar vN is judged mostly by vN trade behaviour (grammar
    changes are exactly what shift trade rates — e.g. D077-D079). Raw counts
    (`n_total`/`n_pass`/`n_zero_trade`) stay unweighted: they feed the
    cold-start sample floor and telemetry. `None` (default) weights every run
    1.0 — identical to pre-D081 behaviour.

    D098 — `cold_start_hypotheses`: for these hypotheses, prior-version gated
    runs are DROPPED ENTIRELY (not merely down-weighted as in D081). Use when a
    hypothesis's pre-current-version cohort is structurally invalid rather than
    merely stale — e.g. relative_value's ~100% zero-trade history was a now-fixed
    Crucible pairs-loading defect (commit 4f5271f), not a real edge signal.
    Dropping that evidence lets the bucket fall below `min_bucket_samples`, so
    the `expected_trades` filter cold-starts to the permissive activations
    heuristic and the hypothesis gets a genuine current-version retest instead
    of being killed at pre-filter on poisoned priors. No-op when
    `current_grammar_version is None` (prior/current is indistinguishable) or a
    hypothesis isn't listed; the default empty set reproduces pure D081.
    """
    if not gated_runs:
        return {}

    trades_by_hash = {gr.run.config_hash: int(gr.run.trade_count) for gr in gated_runs}
    family_by_indicator = {ind.id: ind.family for ind in registry.indicators}

    # LEFT JOIN so submissions without a batch_summaries row (legacy / orphan)
    # still bucket; their NULL grammar_version is treated as a prior version
    # when scoping is active. `forge_batch_id` is the batch_summaries PK and
    # `config_hash` is unique in submissions, so neither join multiplies rows.
    rows = db.execute(
        """
        SELECT s.config_hash, s.config_json, b.grammar_version
        FROM submissions s
        LEFT JOIN batch_summaries b ON s.forge_batch_id = b.forge_batch_id
        WHERE s.config_hash IN (SELECT UNNEST(?))
        """,
        [list(trades_by_hash.keys())],
    ).fetchall()

    # bucket -> list of (trade_count, version_weight)
    buckets: dict[BucketKey, list[tuple[int, float]]] = {}
    for config_hash, config_json, grammar_version in rows:
        extracted = _extract_bucket_inputs(config_json)
        if extracted is None:
            continue
        hypothesis, dte_bucket, directional_indicator = extracted
        family = family_by_indicator.get(directional_indicator)
        if family is None:
            continue
        is_current = current_grammar_version is None or grammar_version == current_grammar_version
        # D098: drop prior-version evidence entirely for cold-start hypotheses
        # (see docstring) so their poisoned legacy cohort can't keep the bucket
        # in empirical-prior mode and block the current-version retest.
        if not is_current and hypothesis in cold_start_hypotheses:
            continue
        weight = 1.0 if is_current else prior_version_weight
        key: BucketKey = (hypothesis, dte_bucket, family)
        buckets.setdefault(key, []).append((trades_by_hash[config_hash], weight))

    out: dict[BucketKey, BucketStats] = {}
    for key, observations in buckets.items():
        # Raw counts feed the cold-start floor + telemetry; the posterior uses
        # version-weighted evidence (D081).
        n_total = len(observations)
        n_pass = sum(1 for trades, _w in observations if trades >= min_trades)
        n_zero_trade = sum(1 for trades, _w in observations if trades == 0)
        weighted_total = sum(w for _t, w in observations)
        weighted_pass = sum(w for trades, w in observations if trades >= min_trades)
        posterior = (alpha + weighted_pass) / (alpha + beta + weighted_total)
        out[key] = BucketStats(
            n_total=n_total,
            n_pass=n_pass,
            n_zero_trade=n_zero_trade,
            posterior_p_pass=posterior,
        )
    return out


__all__ = [
    "COLD_START_HYPOTHESES",
    "DEFAULT_ALPHA",
    "DEFAULT_BETA",
    "DEFAULT_MIN_TRADES",
    "DEFAULT_PRIOR_VERSION_WEIGHT",
    "BucketKey",
    "BucketStats",
    "compute_trade_rate_priors",
]
