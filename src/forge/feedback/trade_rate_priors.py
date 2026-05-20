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
    """
    if not gated_runs:
        return {}

    trades_by_hash = {gr.run.config_hash: int(gr.run.trade_count) for gr in gated_runs}
    family_by_indicator = {ind.id: ind.family for ind in registry.indicators}

    rows = db.execute(
        "SELECT config_hash, config_json FROM submissions WHERE config_hash IN (SELECT UNNEST(?))",
        [list(trades_by_hash.keys())],
    ).fetchall()

    buckets: dict[BucketKey, list[int]] = {}
    for config_hash, config_json in rows:
        extracted = _extract_bucket_inputs(config_json)
        if extracted is None:
            continue
        hypothesis, dte_bucket, directional_indicator = extracted
        family = family_by_indicator.get(directional_indicator)
        if family is None:
            continue
        key: BucketKey = (hypothesis, dte_bucket, family)
        buckets.setdefault(key, []).append(trades_by_hash[config_hash])

    out: dict[BucketKey, BucketStats] = {}
    for key, trade_counts in buckets.items():
        n_total = len(trade_counts)
        n_pass = sum(1 for n in trade_counts if n >= min_trades)
        n_zero_trade = sum(1 for n in trade_counts if n == 0)
        posterior = (alpha + n_pass) / (alpha + beta + n_total)
        out[key] = BucketStats(
            n_total=n_total,
            n_pass=n_pass,
            n_zero_trade=n_zero_trade,
            posterior_p_pass=posterior,
        )
    return out


__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_BETA",
    "DEFAULT_MIN_TRADES",
    "BucketKey",
    "BucketStats",
    "compute_trade_rate_priors",
]
