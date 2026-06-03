"""Failure-bias weights for the enumerator (long-term #1).

Forge's prior-promotion-proximity term in the ranker (§6.2) is the only
memory of past outcomes today, and it's dead until something promotes.
This module gives the enumerator its OWN memory: per-hypothesis posterior
mean of promotion rate, Bayesian-smoothed so untested hypotheses get
near-prior weight and well-tested-but-failing hypotheses get
down-weighted as their sample size grows.

Wiring (separate from this module):
  - cli/main.py computes weights once per iteration via
    `compute_hypothesis_weights(db, gated_runs)`
  - sampler.py accepts an optional `hypothesis_weights` map and
    `rng.choices(weights=...)` instead of `rng.choice(...)`
  - Empty/missing weights → uniform sampling (no behavior change)

Determinism note (hard rule #6 nuance): given the same
`(grammar_version, registry_version, root_seed, iteration,
gated_runs_snapshot)`, enumeration is deterministic. Weights are an
additional input. They change over time as Crucible gates more runs;
that's the *point* — Forge learns. The reproducibility property holds
when the gated_runs snapshot is held constant.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    import duckdb
    from crucible_contracts import GatedRun


# Beta prior over per-hypothesis promotion rate. Mild prior favoring
# exploration: alpha=1, beta=10 → prior mean ~0.09. A hypothesis with
# zero observations gets that weight; a hypothesis with 100 observed
# trials and 0 promotions gets posterior mean = 1/111 ≈ 0.009 — strongly
# down-weighted. A hypothesis with 100 trials and 5 promotions gets
# 6/111 ≈ 0.054 — moderately up-weighted. The (1, 10) choice keeps the
# prior weak enough that data dominates after ~30 trials but strong
# enough that one unlucky batch doesn't zero out a class.
DEFAULT_ALPHA: float = 1.0
DEFAULT_BETA: float = 10.0


def _iter_hypothesis_outcomes(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
) -> Iterator[tuple[str, GatedRun]]:
    """Yield ``(hypothesis, gated_run)`` per submission with a matching gated run.

    The shared join behind both the promotion-only and the multi-class reward
    weighters. Submissions whose ``config_json`` is not a dict, or that lack a
    string ``hypothesis``, are skipped. config_hash is unique-indexed in
    ``submissions`` (§13.4), so each hash maps to at most one row.
    """
    run_by_hash: dict[str, GatedRun] = {gr.run.config_hash: gr for gr in gated_runs}
    rows = db.execute("SELECT config_hash, config_json FROM submissions").fetchall()
    for config_hash, config_json_raw in rows:
        gr = run_by_hash.get(config_hash)
        if gr is None:
            continue
        cfg = json.loads(config_json_raw) if isinstance(config_json_raw, str) else config_json_raw
        hyp = cfg.get("hypothesis") if isinstance(cfg, dict) else None
        if not isinstance(hyp, str):
            continue
        yield hyp, gr


def compute_hypothesis_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
) -> dict[str, float]:
    """Posterior mean of promotion rate per hypothesis, Beta-smoothed.

    Joins Forge's `submissions` table (which has `config_json` containing
    the hypothesis) with the supplied `gated_runs` (which carry the
    promotion decision per `config_hash`). Returns a dict mapping
    hypothesis name → posterior mean in (0, 1).

    A hypothesis seen in `submissions` but not yet present in
    `gated_runs` (still being backtested) contributes nothing. Empty
    `gated_runs` → returns an empty dict; the caller treats that as
    "fall back to uniform sampling."
    """
    if not gated_runs:
        return {}
    counts: dict[str, list[int]] = {}  # hypothesis → [total, promoted]
    for hyp, gr in _iter_hypothesis_outcomes(db, gated_runs):
        bucket = counts.setdefault(hyp, [0, 0])
        bucket[0] += 1
        if gr.decision.decision == "promote":
            bucket[1] += 1
    return {
        hyp: (alpha + promoted) / (alpha + beta + total)
        for hyp, (total, promoted) in counts.items()
    }


def prior_mean(*, alpha: float = DEFAULT_ALPHA, beta: float = DEFAULT_BETA) -> float:
    """Beta(alpha, beta) prior mean — the weight given to unseen hypotheses."""
    return alpha / (alpha + beta)


# ---------------------------------------------------------------------------
# Multi-class reward weighting (improvement-plan Phase 2; D094).
#
# `compute_hypothesis_weights` learns only from promotions. With Forge in a
# sustained zero-promotion regime (§1.2), every hypothesis collapses to the
# same trial-count decay and the enumerator loses its gradient. This weighter
# generalizes the Beta-posterior mean to a graded per-run reward built from the
# two signals that DO vary across hypotheses pre-promotion:
#
#   - trade production — `run.trade_count >= TRADE_FLOOR`. The dominant gate
#     failure is `min_oos_trade_count` (~99.9% of decisions per the generator
#     plan), so "does this hypothesis fire at all" is the highest-information
#     signal available before anything promotes.
#   - gate progress — fraction of `gate_results` passed: a continuous "how far
#     down the gauntlet" measure that → 1.0 for a promoted run (the contracts
#     validator guarantees promote => no failed gate), layering an edge
#     gradient on top of bare trade production.
#   - sharpe proximity (D101) — `walk_forward_sharpe_median` (the gate's FAILING
#     axis) linearly ramped to [0, 1] against the 2.0 gate threshold, credited
#     only for runs that traded. gate_progress is a GENERIC pass-fraction
#     (dominated by the easy Calmar/DD gates) and so Sharpe-blind — without this
#     term the gradient hill-climbs the axis that passes and ignores the one
#     that fails (Crucible's 2026-06-03 v5 Sharpe diagnosis).
#
# reward = TRADE_PRODUCTION_WEIGHT*traded + GATE_PROGRESS_WEIGHT*gate_fraction
# + SHARPE_WEIGHT*sharpe_proximity, with a promotion short-circuit to the
# ceiling (1.0). The three weights sum to 1.0 so reward in [0, 1] and the
# smoothed weight stays in (0, 1), leaving `apply_exploration_floor`'s semantics
# unchanged. The D067 floor is the diversity guard for the Sharpe tilt: a
# hypothesis with no Sharpe data yet (e.g. just-cold-started mean_reversion)
# keeps its floored / Beta-prior budget and cannot be starved.
#
# Scope (deliberate): the prefilter-killed / runner-failed outcomes the plan
# also names are NOT consumed here — they never produce a GatedRun, and
# down-weighting a structurally-scarce-but-valid hypothesis (e.g. relative_value
# with its single pairs indicator) for being prefilter-deduped would worsen the
# monoculture this is meant to relieve. The D067 exploration floor still
# guarantees every hypothesis a minimum sampling budget regardless of reward.
# ---------------------------------------------------------------------------

DEFAULT_TRADE_FLOOR: int = 1
# D101 — the three reward weights sum to 1.0 so reward stays in [0, 1]
# (apply_exploration_floor's semantics unchanged). Split was 0.6/0.4 (D094,
# trade/gate only); D101 reseats it to seat the Sharpe term — gate_progress is a
# generic, Sharpe-blind pass-fraction, the exact axis the gate fails on.
DEFAULT_TRADE_PRODUCTION_WEIGHT: float = 0.5
DEFAULT_GATE_PROGRESS_WEIGHT: float = 0.2
DEFAULT_SHARPE_WEIGHT: float = 0.3
# Sharpe normalization (D101): linear ramp from FLOOR (0 reward) to CEILING
# (full reward) of `walk_forward_sharpe_median` — CEILING = the §8.7
# WF-Sharpe-median gate threshold (2.0), so the term rewards proximity to
# passing. Credited only for runs that traded.
DEFAULT_SHARPE_METRIC: str = "walk_forward_sharpe_median"
DEFAULT_SHARPE_FLOOR: float = 0.0
DEFAULT_SHARPE_CEILING: float = 2.0


def _sharpe_reward(gated_run: GatedRun, *, traded: bool) -> float:
    """Proximity of a run's walk-forward Sharpe to the gate, in [0, 1] (D101).

    Linear ramp from `DEFAULT_SHARPE_FLOOR` (0.0 reward) to
    `DEFAULT_SHARPE_CEILING` (1.0 reward = the WF-Sharpe-median gate threshold),
    clamped. Credited only for runs that traded — a non-trading strategy's
    Sharpe is meaningless — and 0.0 when the metric is absent (no crash, no
    credit), so missing data never inflates the reward.
    """
    if not traded:
        return 0.0
    raw = gated_run.run.metrics.get(DEFAULT_SHARPE_METRIC)
    if raw is None:
        return 0.0
    span = DEFAULT_SHARPE_CEILING - DEFAULT_SHARPE_FLOOR
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (float(raw) - DEFAULT_SHARPE_FLOOR) / span))


def _run_reward(
    gated_run: GatedRun,
    *,
    trade_floor: int,
    trade_production_weight: float,
    gate_progress_weight: float,
    sharpe_weight: float,
) -> float:
    """Graded reward in [0, 1] for one gated run (see the module section above)."""
    if gated_run.decision.decision == "promote":
        return 1.0
    traded = gated_run.run.trade_count >= trade_floor
    gates = gated_run.decision.gate_results
    gate_fraction = sum(1 for g in gates.values() if g.passed) / len(gates) if gates else 0.0
    return (
        trade_production_weight * (1.0 if traded else 0.0)
        + gate_progress_weight * gate_fraction
        + sharpe_weight * _sharpe_reward(gated_run, traded=traded)
    )


def compute_hypothesis_reward_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    trade_floor: int = DEFAULT_TRADE_FLOOR,
    trade_production_weight: float = DEFAULT_TRADE_PRODUCTION_WEIGHT,
    gate_progress_weight: float = DEFAULT_GATE_PROGRESS_WEIGHT,
    sharpe_weight: float = DEFAULT_SHARPE_WEIGHT,
) -> dict[str, float]:
    """Per-hypothesis Beta-smoothed mean of a graded multi-class reward.

    Generalizes `compute_hypothesis_weights`: each gated run contributes a
    reward in [0, 1] (trade-production + gate-progress + Sharpe-proximity,
    promotion = 1.0)
    rather than a binary promoted flag, so the enumerator keeps a gradient
    even when nothing has promoted. Same join semantics, same empty -> `{}`
    cold-start contract, and the same determinism property (hard rule #6:
    a pure function of the `submissions` table + the `gated_runs` snapshot).
    """
    if not gated_runs:
        return {}
    acc: dict[str, list[float]] = {}  # hypothesis → [total, reward_sum]
    for hyp, gr in _iter_hypothesis_outcomes(db, gated_runs):
        bucket = acc.setdefault(hyp, [0.0, 0.0])
        bucket[0] += 1.0
        bucket[1] += _run_reward(
            gr,
            trade_floor=trade_floor,
            trade_production_weight=trade_production_weight,
            gate_progress_weight=gate_progress_weight,
            sharpe_weight=sharpe_weight,
        )
    return {
        hyp: (alpha + reward_sum) / (alpha + beta + total)
        for hyp, (total, reward_sum) in acc.items()
    }


# D067 — minimum exploration weight applied across all canonical
# hypotheses to prevent the cold-start death spiral: a hypothesis with
# zero gated history gets prior weight (~0.091), but once a single
# unlucky batch lands it gets posterior ~0.005, then never gets sampled
# again to accumulate corrective evidence. The floor breaks this. Sized
# so that 5 active hypotheses all at floor would each receive ~20% of
# the budget — enough exploration for each to accumulate ~50 gated
# trials per ~250-candidate iteration before the floor releases them
# back to natural posterior dominance. See IMPLEMENTATION_DECISIONS.md
# D067 for full rationale (4039 submissions, 1 mean_reversion / 0
# trend_continuation pre-floor).
DEFAULT_EXPLORATION_FLOOR: float = 0.05


def apply_exploration_floor(
    weights: Mapping[str, float],
    *,
    hypotheses: Iterable[str],
    floor: float = DEFAULT_EXPLORATION_FLOOR,
    fallback: float | None = None,
) -> dict[str, float]:
    """Apply a minimum exploration floor across a canonical hypothesis set.

    For each ``h`` in ``hypotheses``:
      - Present in ``weights``: returns ``max(weights[h], floor)``.
      - Absent from ``weights`` with ``fallback`` set:
        ``max(fallback, floor)`` — used to keep unobserved hypotheses on
        the Beta prior (typically higher than the floor anyway, so the
        prior dominates for true cold-starts while the floor protects
        observed-but-failing hypotheses).
      - Absent with ``fallback=None``: returns ``floor`` directly.

    The returned dict ALWAYS contains every name in ``hypotheses``, so
    the sampler's `weights.get(h, prior_mean)` fallback no longer fires
    for canonical hypotheses — every one is explicitly floored before
    leaving this function. Callers that need the raw posterior should
    call ``compute_hypothesis_weights`` directly.
    """
    result: dict[str, float] = {}
    for h in hypotheses:
        if h in weights:
            result[h] = max(weights[h], floor)
        elif fallback is not None:
            result[h] = max(fallback, floor)
        else:
            result[h] = floor
    return result


__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_BETA",
    "DEFAULT_EXPLORATION_FLOOR",
    "DEFAULT_GATE_PROGRESS_WEIGHT",
    "DEFAULT_SHARPE_CEILING",
    "DEFAULT_SHARPE_FLOOR",
    "DEFAULT_SHARPE_METRIC",
    "DEFAULT_SHARPE_WEIGHT",
    "DEFAULT_TRADE_FLOOR",
    "DEFAULT_TRADE_PRODUCTION_WEIGHT",
    "apply_exploration_floor",
    "compute_hypothesis_reward_weights",
    "compute_hypothesis_weights",
    "prior_mean",
]
