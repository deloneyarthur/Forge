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
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from forge.enumeration.underlying_class import underlying_class

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

    import duckdb
    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult


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
        # D290: ghost-era ve labels are fiction — never learn from them.
        if is_ve_ghost_label(hyp, gr.decision.decided_at):
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
    Sharpe is meaningless — and 0.0 when the value is absent (no crash, no
    credit), so missing data never inflates the reward.

    D106 source fix: the live gated export carries walk_forward_sharpe_median
    in ``gate_results[...].value`` — NOT in ``run.metrics``, whose keys are the
    base backtest stats only — so the D101 metrics-only read silently scored 0
    for every run. The gate row's measured value is authoritative; the metrics
    key is retained as a fallback for export shapes that do carry it.
    """
    if not traded:
        return 0.0
    gate_row = gated_run.decision.gate_results.get(DEFAULT_SHARPE_METRIC)
    raw = gate_row.value if gate_row is not None and gate_row.value is not None else None
    if raw is None:
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


# ---------------------------------------------------------------------------
# Component-rate reward family (D105; Crucible yield-map handoff 2026-06-07).
#
# The D094/D101 graded reward made TRADE PRODUCTION the dominant term because,
# in the zero-trade cold-start era it was designed in, "does this class fire at
# all" was the highest-information signal available. That rationale expired the
# moment Crucible's rv lookback fix (5fd485a, 2026-06-07) flipped
# relative_value to ~100% trading: the trade term became a Goodhart proxy —
# the live loop weighted relative_value 0.567 at 0.7-1.0% component yield while
# volatility_event sat at 0.169 yielding 3.9-9.7%. With 41 v9 components in the
# pool, the scarce-but-real signal is now WHICH CLASSES CRUCIBLE ACCEPTS.
#
# Estimand: Beta-smoothed posterior of P(decision ∈ {component, promote}) per
# key, with an epsilon-scale tiebreak from gate-progress + Sharpe-proximity so
# zero-component classes still order (the D094 gradient survives, demoted to
# tiebreak). A blend cannot do this job: any material weight on gate_fraction
# or traded re-instates the Goodhart, because both are themselves
# trade-correlated (e.g. 0.7·component + 0.2·gate still ranks the heavy trader
# above the component minter on live numbers).
#
# Scale design (why these constants differ from DEFAULT_ALPHA/BETA):
#   - COMPONENT_BETA = 50: prior mean 1/51 ≈ 2.0% sits AT the observed marginal
#     component rate (17/1,000 and 84/5,000 in the live export windows), so an
#     unobserved key samples like an average one and ~50 observations halve the
#     prior's pull. The old Beta(1,10) prior mean (~9%) was calibrated for
#     rewards in the 0.1-0.6 range and would let any unobserved key dominate.
#   - COMPONENT_TIEBREAK_WEIGHT: sized so the maximum tiebreak mass across the
#     whole feedback window (FEEDBACK_GATED_RUNS_LIMIT x ε ≤ 0.5) stays below
#     one component event's reward — trading volume can never outrank a single
#     real component. Invariant pinned in tests.
#   - Version scoping mirrors trade_rate_priors (D081/D098): the gated export
#     carries no grammar_version field and its tail reaches weeks back
#     (pre-v5 re-gate pollution, D103), so rows resolve their version through
#     Forge's own submissions → batch_summaries join; prior-version rows weigh
#     0.25 and cold-start hypotheses drop them entirely.
#
# Consumers and scale: `compute_hypothesis_component_weights` NORMALIZES by the
# max over the (closed, always-filled) enumerable-hypothesis set so the result
# flows through the untouched D067 `apply_exploration_floor(floor=0.05)`
# pipeline — raw component-rate posteriors (~0.005-0.05) would otherwise all
# sit at/below the floor and flatten. The per-regime / finer-grained maps stay
# RAW posteriors instead: their key sets are open (registry-dependent), so
# normalizing would inflate a sparsely-observed key against the prior fallback
# at the draw site; the sampler's prior/floor constants are rescaled to this
# family's scale instead (same floor-to-prior ratio as D067).
# ---------------------------------------------------------------------------

COMPONENT_ALPHA: float = 1.0
COMPONENT_BETA: float = 50.0
COMPONENT_TIEBREAK_WEIGHT: float = 5e-5
# D114 — joint-quality term. A rejected run earns
# COMPONENT_QUALITY_WEIGHT * clamp(min(wf/thr_wf, cpcv/thr_cpcv), 0, 1),
# eligible only when it passed its OWN min_oos_trade_count gate (per-bucket
# thresholds ride in the gate row). Why a MATERIAL weight where D105 demoted
# continuous signals to epsilon: the D105 Goodhart was TRADE-correlated signals
# (gate_fraction / traded) — quality here is the two promotion-quality gate
# VALUES themselves, which trading volume cannot farm (corr(trade_count,
# cpcv_p25) ~ -0.14 on the live verdicts cohort) and which admission-rule
# changes cannot move (Q32: regime_coverage enforcement zeroed single-name
# component minting 2026-06-08 while the recorded WF/CPCV values were
# untouched — the binary event signal mislearns "the cell died", the value
# signal does not). Sizing: 1/0.25 = 4 frontier-grade rejects (quality 1.0)
# ≈ one component event; the live frontier is sparse (4 joint near-misses in
# 10,089 decisions), so typical cells move by quality only when they
# consistently score — a DELIBERATE departure from the D105 "no volume can
# outrank one component" bound, which now holds only for zero-quality volume.
# Emission-proofed against the live verdicts cohort (D114).
COMPONENT_QUALITY_WEIGHT: float = 0.25
# The two promotion-quality gates whose VALUES form the joint score, and the
# per-run trade-floor gate that makes those values meaningful at scale.
_QUALITY_GATES: tuple[str, str] = ("walk_forward_sharpe_median", "cpcv_sharpe_p25")
_QUALITY_TRADE_FLOOR_GATE: str = "min_oos_trade_count"
# D081 semantics at the reward layer; one current-version run ≈ 4 prior ones.
COMPONENT_PRIOR_VERSION_WEIGHT: float = 0.25
# D106 — empirical-Bayes anchor strength for the hierarchical weighters
# (underlying name ← class; (hypothesis, directional, bucket) ← (hypothesis,
# bucket)). Matches the COMPONENT_ALPHA+BETA scale: ~50 observations halve the
# coarse anchor's pull, so AAPL-grade evidence (37/101) escapes its class while
# a 1-run name stays pinned to it.
COMPONENT_HIER_PRIOR_STRENGTH: float = 50.0
# The gated-runs window every feedback weight loader requests. Shared here (not
# in the CLI) so the tiebreak-vs-window invariant is checkable next to ε.
FEEDBACK_GATED_RUNS_LIMIT: int = 10_000

# H4 (orthogonal-yield, NEW_HYPOTHESES_V11_PLAN). The marginal-value discount
# applied to a (hypothesis, directional, underlying-class) FACTOR CELL's
# underlying draw weight: discount = (1 + m) ** -strength, m = the cell's
# version-weighted component count. strength=0.5 is the pure Grinold/pod-shop
# 1/sqrt form (the m-th correlated sleeve ≈ 1/sqrt(m) of the first); we ship
# gentler. STATUS.md emission read (2026-06-08): pure sqrt is a ~46% first-order
# raw-yield cut on the live name cells — too aggressive for "same yield, more
# orthogonal". DEFAULT_ORTHOGONAL_YIELD_STRENGTH = 0.15 is the operator-calibrated
# curve (D108, emission-proofed against the live export ⋈ forge.db: top name cell
# AAPL m≈20 → 0.64 discount, steady-state name-concentration -13% at raw-yield
# -17%, honouring "yield roughly flat"). MIN_DISCOUNT is a hard cap so a hugely
# over-mined cell still can't be starved — the sampler's underlying exploration
# floor is a second, independent guard. Anti-Goodhart: with the component-count
# estimand (tiebreak_weight=0.0 below) a cell's discount is a pure function of
# components, never trades, so discount = 1.0 (cell absent) at m = 0.
DEFAULT_ORTHOGONAL_YIELD_STRENGTH: float = 0.15
DEFAULT_ORTHOGONAL_YIELD_MIN_DISCOUNT: float = 0.25

_COMPONENT_DECISIONS: frozenset[str] = frozenset({"component", "promote"})

# D128 (enforcing D124's read standard in the reward path).
#
# Key 1 — cost-floor value era. Crucible's slippage cost floor deployed at
# exactly 2026-06-09T22:52:57Z (their restart boundary, D124): every
# WF/CPCV/Sharpe VALUE decided before it is zero-slippage-optimistic. Such
# values must never earn reward — the D114 quality term and the
# Sharpe-proximity half of the D094/D101 tiebreak are zeroed for pre-cut
# rows. The gate_fraction half survives: pass/fail booleans are not values.
# This is a literal constant, not a clock read (hard rule #8 untouched).
_COST_FLOOR_VALUE_CUT: datetime = datetime(2026, 6, 9, 22, 52, 57, tzinfo=UTC)

# Key 2 — coverage honesty is a row marker, not a time cut. Byte-for-byte
# Crucible's `honest_regime_coverage` predicate (pool filter ≡ refit trigger
# ≡ this read — cannot drift): the regime_coverage row passed AND its detail
# does not carry the unverified-pass marker. Absent row (pre-Q32 legacy) =
# cannot verify = not honest, fail-closed. 94% of legacy "components" fail
# this marker (D124) — their binary event was unverified-admission noise;
# honest re-evaluations flow in via the fullhist-refit children (same
# config_hash), replacing the evidence organically.
_COVERAGE_GATE: str = "regime_coverage"
_COVERAGE_UNVERIFIED_MARK: str = "coverage_unverified"

# Label-era key for the learned verdict model (D132 / F1). Stricter than the
# value-cut above on purpose: training LABELS must come from the engine that
# enforces earnings exits and reads correct single-name chains — the composite
# clean-era boundary (Crucible's exit-era runner restart, D130/D131; the v2
# registry and v17 followed within 19 minutes of the same boot). Literal
# constant, not a clock read (hard rule #8 untouched). Any era boundary
# declared after a model's training cutoff obsoletes that model (the F3 era
# guard refuses it).
CLEAN_ERA_LABEL_CUT: datetime = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)

# D290 (the v39 companion) — the ve ghost-label cut. Crucible's 2026-07-19 ve
# close-out: 23/25 stored-cpcv ve components were GHOSTS (their
# put_wall/gex/vex/cex staleness blind spot, fixed their-side 2026-07-18), and
# 34,273 ve verdicts / 657 fictional components sit inside OUR clean-era
# training window — ~10% of all positive labels. Their §6 ask: treat pre-07-18
# ve stored scores as unrankable. `volatility_event` rows decided before this
# cut are excluded from EVERY learned trainer (hypothesis weights, the
# D105/D106 component-rate weighters, trade-rate priors, the ranker dataset,
# arm-floor maturity) — the CLEAN_ERA precedent scoped to one hypothesis.
# Non-ve rows and post-cut ve rows are untouched.
VE_GHOST_LABEL_CUT: datetime = datetime(2026, 7, 18, 0, 0, 0, tzinfo=UTC)

_VE_GHOST_HYPOTHESIS = "volatility_event"


def is_ve_ghost_label(hypothesis: str | None, decided_at: datetime) -> bool:
    """True iff this (hypothesis, decided_at) label falls under the ve ghost cut.

    Naive timestamps are UTC by repo convention (the verdicts/export era is
    uniform post-D117)."""
    if hypothesis != _VE_GHOST_HYPOTHESIS:
        return False
    decided = decided_at
    if decided.tzinfo is None:
        decided = decided.replace(tzinfo=UTC)
    return decided < VE_GHOST_LABEL_CUT


def _values_readable(gated_run: GatedRun) -> bool:
    """D124 key 1: False when the run was decided before the cost-floor cut.

    Naive timestamps are UTC (the verdicts/export era is uniform post-D117).
    """
    decided = gated_run.decision.decided_at
    if decided.tzinfo is None:
        decided = decided.replace(tzinfo=UTC)
    return decided >= _COST_FLOOR_VALUE_CUT


def honest_regime_coverage_row(gate_results: Mapping[str, GateResult]) -> bool:
    """D124 key 2 on a bare gate-results mapping — the single source of truth.

    Shared by the reward path (via `_honest_regime_coverage`) and the learned
    verdict model's label builder (D132), so the two reads cannot drift.
    """
    row = gate_results.get(_COVERAGE_GATE)
    return row is not None and row.passed and _COVERAGE_UNVERIFIED_MARK not in (row.detail or "")


def _honest_regime_coverage(gated_run: GatedRun) -> bool:
    """D124 key 2: True only when the coverage gate REALLY evaluated and passed."""
    return honest_regime_coverage_row(gated_run.decision.gate_results)


def component_prior_mean(*, alpha: float = COMPONENT_ALPHA, beta: float = COMPONENT_BETA) -> float:
    """Beta(alpha, beta) prior mean — the weight given to unseen keys."""
    return alpha / (alpha + beta)


def _joint_quality(gated_run: GatedRun) -> float:
    """Joint promotion-quality proximity of a run, in [0, 1] (D114).

    ``clamp(min(value/threshold over _QUALITY_GATES), 0, 1)`` — the MIN because
    promotion requires BOTH axes, so the binding gate scores. Thresholds come
    from the run's own gate rows (robust to Crucible recalibration and
    per-bucket variation), and the run must have PASSED its own
    ``min_oos_trade_count`` gate — quality below the breadth floor is noise.
    Any absent row/value/threshold (or a non-positive threshold) → 0.0: missing
    data never inflates (the ``_sharpe_reward`` stance). ``regime_coverage``
    and every other gate's pass/fail are deliberately NOT consulted — that is
    the Q32 robustness property pinned in tests.
    """
    gates = gated_run.decision.gate_results
    floor_row = gates.get(_QUALITY_TRADE_FLOOR_GATE)
    if floor_row is None or not floor_row.passed:
        return 0.0
    score = 1.0
    for gate_name in _QUALITY_GATES:
        row = gates.get(gate_name)
        if row is None or row.value is None or row.threshold is None or row.threshold <= 0.0:
            return 0.0
        score = min(score, float(row.value) / float(row.threshold))
    return max(0.0, score)


def _component_run_reward(
    gated_run: GatedRun,
    *,
    tiebreak_weight: float,
    quality_weight: float,
) -> float:
    """1.0 for a component/promote decision, else quality + epsilon tiebreak.

    Promote counts as a component event — a promoted run cleared component-level
    screening on the way (contracts: 'component' = passed component screening
    but not the full portfolio gate). Rejects earn ``quality_weight *
    _joint_quality`` (D114 — material, see the section comment's sizing
    rationale) plus the D094/D101 epsilon tiebreak (gate-progress +
    Sharpe-proximity) that orders zero-quality keys but can never outrank a
    real component.
    """
    if gated_run.decision.decision in _COMPONENT_DECISIONS and _honest_regime_coverage(gated_run):
        return 1.0
    # D128: a dishonest-coverage "component" (unverified-pass admission) is
    # not the binary event — it falls through and earns what its READABLE
    # values earn, like any reject.
    gates = gated_run.decision.gate_results
    gate_fraction = sum(1 for g in gates.values() if g.passed) / len(gates) if gates else 0.0
    traded = gated_run.run.trade_count >= DEFAULT_TRADE_FLOOR
    readable = _values_readable(gated_run)
    quality = (
        quality_weight * _joint_quality(gated_run) if quality_weight > 0.0 and readable else 0.0
    )
    sharpe_term = _sharpe_reward(gated_run, traded=traded) if readable else 0.0
    tiebreak = tiebreak_weight * (gate_fraction + sharpe_term) / 2.0
    return quality + tiebreak


def _component_rate_sums[K](
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    key_of: Callable[[Mapping[str, object]], K | None],
    *,
    tiebreak_weight: float,
    quality_weight: float,
    current_grammar_version: str | None,
    prior_version_weight: float,
    cold_start_hypotheses: frozenset[str],
) -> dict[K, list[float]]:
    """Version-weighted ``[total, reward_sum]`` per key — the engine's raw
    evidence, pre-smoothing (D106 split: the hierarchical weighters aggregate
    fine-key sums into coarse priors before smoothing, so they need the sums,
    not the posteriors).
    """
    if not gated_runs:
        return {}
    run_by_hash: dict[str, GatedRun] = {gr.run.config_hash: gr for gr in gated_runs}
    # LEFT JOIN so legacy/orphan submissions still contribute; their NULL
    # grammar_version counts as a prior version when scoping is active
    # (trade_rate_priors precedent). Restricting to the gated hashes avoids the
    # full-table scan the D094-era iterator performs.
    rows = db.execute(
        """
        SELECT s.config_hash, s.config_json, b.grammar_version
        FROM submissions s
        LEFT JOIN batch_summaries b ON s.forge_batch_id = b.forge_batch_id
        WHERE s.config_hash IN (SELECT UNNEST(?))
        """,
        [list(run_by_hash.keys())],
    ).fetchall()

    acc: dict[K, list[float]] = {}  # key → [weighted_total, weighted_reward_sum]
    for config_hash, config_json_raw, grammar_version in rows:
        gr = run_by_hash.get(config_hash)
        if gr is None:
            continue
        cfg = json.loads(config_json_raw) if isinstance(config_json_raw, str) else config_json_raw
        if not isinstance(cfg, dict):
            continue
        # D290: ghost-era ve labels are fiction — never learn from them.
        if is_ve_ghost_label(cfg.get("hypothesis"), gr.decision.decided_at):
            continue
        key = key_of(cfg)
        if key is None:
            continue
        is_current = current_grammar_version is None or grammar_version == current_grammar_version
        if not is_current and cfg.get("hypothesis") in cold_start_hypotheses:
            continue
        weight = 1.0 if is_current else prior_version_weight
        bucket = acc.setdefault(key, [0.0, 0.0])
        bucket[0] += weight
        bucket[1] += weight * _component_run_reward(
            gr, tiebreak_weight=tiebreak_weight, quality_weight=quality_weight
        )
    return acc


def _component_rate_posteriors[K](
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    key_of: Callable[[Mapping[str, object]], K | None],
    *,
    alpha: float,
    beta: float,
    tiebreak_weight: float,
    quality_weight: float,
    current_grammar_version: str | None,
    prior_version_weight: float,
    cold_start_hypotheses: frozenset[str],
) -> dict[K, float]:
    """Beta-smoothed component-rate posterior per ``key_of(config)`` key.

    The shared engine behind the hypothesis / regime / bucket / underlying
    weighters: one join (submissions → batch_summaries for the D081 version
    resolution, restricted to the gated hashes), one estimand, one smoothing
    rule — so every granularity stays on a single coherent scale. Rows whose
    ``key_of`` returns None are skipped (wrong hypothesis for a scoped key,
    corrupt config_json, missing fields). Same determinism property as the rest
    of the module (hard rule #6): a pure function of the snapshot inputs.
    """
    sums = _component_rate_sums(
        db,
        gated_runs,
        key_of,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    return {
        key: (alpha + reward_sum) / (alpha + beta + total)
        for key, (total, reward_sum) in sums.items()
    }


def _hierarchical_posteriors[F, C](
    fine_sums: Mapping[F, Sequence[float]],
    coarse_of: Callable[[F], C],
    *,
    alpha: float,
    beta: float,
    prior_strength: float,
) -> dict[F, float]:
    """Empirical-Bayes shrinkage: fine-key posteriors anchored on their coarse
    cell (D106).

    Coarse posteriors come from the AGGREGATED fine sums (Beta(alpha, beta)
    against the global prior — identical to the flat weighter's output for the
    same key, by construction). Each fine key then gets
    ``(S * coarse + fine_reward_sum) / (S + fine_n)``: zero fine evidence →
    exactly the coarse posterior; ~S observations halve the coarse anchor's
    pull. This is what stops a thin fine cell from riding its own noise while
    letting an AAPL-grade outlier escape its class.
    """
    coarse_sums: dict[C, list[float]] = {}
    for fine_key, (total, reward_sum) in fine_sums.items():
        bucket = coarse_sums.setdefault(coarse_of(fine_key), [0.0, 0.0])
        bucket[0] += total
        bucket[1] += reward_sum
    coarse_post = {
        c: (alpha + reward_sum) / (alpha + beta + total)
        for c, (total, reward_sum) in coarse_sums.items()
    }
    return {
        fine_key: (prior_strength * coarse_post[coarse_of(fine_key)] + reward_sum)
        / (prior_strength + total)
        for fine_key, (total, reward_sum) in fine_sums.items()
    }


def compute_hypothesis_component_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    hypotheses: Iterable[str],
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
) -> dict[str, float]:
    """Per-hypothesis component-rate weights, normalized to max = 1.0.

    Every requested hypothesis is present in the result: observed ones carry
    their posterior, unobserved ones the prior mean (an average-class weight —
    neither dominant nor starved). Normalization restores the D067 floor's
    intended bite ("the worst class still gets ~5% of the best class's share")
    without touching the floor constant; `rng.choices` only consumes ratios, so
    the sampling distribution is unchanged by the rescale. Empty ``gated_runs``
    → ``{}`` (the caller's cold-start contract, same as every weighter here).
    """
    if not gated_runs:
        return {}

    def _hypothesis_of(cfg: Mapping[str, object]) -> str | None:
        hyp = cfg.get("hypothesis")
        return hyp if isinstance(hyp, str) else None

    posteriors = _component_rate_posteriors(
        db,
        gated_runs,
        _hypothesis_of,
        alpha=alpha,
        beta=beta,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    pm = component_prior_mean(alpha=alpha, beta=beta)
    filled = {h: posteriors.get(h, pm) for h in hypotheses}
    if not filled:
        return {}
    mx = max(filled.values())
    if mx <= 0.0:  # unreachable with alpha > 0; defensive against knob abuse
        return dict.fromkeys(filled, 1.0)
    return {h: v / mx for h, v in filled.items()}


def compute_hypothesis_bucket_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
) -> dict[tuple[str, str], float]:
    """Component-rate posterior per ``(hypothesis, dte_bucket)`` cell (D105).

    The yield structure Crucible reported (2026-06-07) lives BELOW hypothesis
    granularity — volatility_event x swing_mid yielded 9.7% on 31 decided while
    mean_reversion x swing_mid sat at 0/628 — and per-hypothesis weights cannot
    express that. These cells feed the sampler's joint (directional, bucket)
    draw: the DTE bucket is derived from the directional's horizon (D102), and
    for most indicators every k lands in ONE bucket, so steering the bucket mix
    necessarily steers the directional pick too. Returns RAW posteriors (the
    sampler compares against its own prior/floor on this scale — see the
    section comment). Empty gated_runs → ``{}`` (cold start, uniform draw).
    """

    def _hyp_bucket_of(cfg: Mapping[str, object]) -> tuple[str, str] | None:
        hyp = cfg.get("hypothesis")
        bucket = cfg.get("dte_bucket")
        if isinstance(hyp, str) and isinstance(bucket, str):
            return (hyp, bucket)
        return None

    return _component_rate_posteriors(
        db,
        gated_runs,
        _hyp_bucket_of,
        alpha=alpha,
        beta=beta,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )


def compute_underlying_class_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
) -> dict[str, float]:
    """Component-rate posterior per underlying CLASS (D105).

    The yield map's strongest structure: high-idio-vol single names minted
    12.8-27.9% (AAPL 17/61, NVDA 8/36, TSLA 6/47) while every diversified
    ETF/index underlying with >=30 decided sat at 0 components. Two learned
    classes (the curated `forge.enumeration.underlying_class` table) capture
    most of that signal; per-name smoothing can come later. relative_value
    rows are naturally excluded — their ``underlying`` is None (pairs legs are
    Crucible-resolved, D098). Returns RAW posteriors for the sampler's
    class-weighted underlying draw. Empty gated_runs → ``{}`` (cold start).
    """

    def _class_of(cfg: Mapping[str, object]) -> str | None:
        underlying = cfg.get("underlying")
        return underlying_class(underlying) if isinstance(underlying, str) else None

    return _component_rate_posteriors(
        db,
        gated_runs,
        _class_of,
        alpha=alpha,
        beta=beta,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )


def compute_underlying_name_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
    prior_strength: float = COMPONENT_HIER_PRIOR_STRENGTH,
) -> dict[str, float]:
    """Per-NAME component-rate posterior, shrunk toward the name's class (D106).

    The two-class prior (D105) is leaky in both directions — inside the
    high-idio class, AAPL minted 36.6% (37/101) while SHOP sat at 0/85 — and
    pre-D105 sampling drew underlyings uniformly, so those per-name reads are
    quasi-randomized. Each observed name's posterior anchors on its class
    posterior (identical to `compute_underlying_class_weights` for the same
    inputs, by construction) and moves with its own evidence. Unobserved names
    are ABSENT: the sampler falls through to the class weight, then the prior.
    Empty gated_runs → ``{}``.
    """

    def _name_of(cfg: Mapping[str, object]) -> str | None:
        underlying = cfg.get("underlying")
        return underlying if isinstance(underlying, str) else None

    name_sums = _component_rate_sums(
        db,
        gated_runs,
        _name_of,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    return _hierarchical_posteriors(
        name_sums,
        underlying_class,
        alpha=alpha,
        beta=beta,
        prior_strength=prior_strength,
    )


def _directional_indicator_of(cfg: Mapping[str, object]) -> str | None:
    """The directional signal's first indicator id of a serialized config, or
    ``None``.

    The §3.5 directional signal carries the hypothesis's entry concept; its
    first indicator id is the directional family the D106 triple cell and the
    H4 factor cell both key on. Returns ``None`` when the directional signal or
    its indicator list is absent/malformed (mirrors ``_regime_indicator_of``)."""
    signals = cfg.get("signals")
    if not isinstance(signals, list):
        return None
    for sig in signals:
        if isinstance(sig, dict) and sig.get("role") == "directional":
            inds = sig.get("indicators")
            if isinstance(inds, (list, tuple)) and inds and isinstance(inds[0], str):
                return inds[0]
            return None
    return None


def compute_hypothesis_directional_bucket_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
    prior_strength: float = COMPONENT_HIER_PRIOR_STRENGTH,
) -> dict[tuple[str, str, str], float]:
    """``(hypothesis, directional, dte_bucket)`` component-rate posterior,
    shrunk toward its ``(hypothesis, dte_bucket)`` pair (D106).

    The directional structure is real — vol_event x iv_rank 17.9% vs
    gamma_flip 0/147; mean_reversion x put_wall 7.7% vs every classic
    oscillator at 0/~1,100 — but a FLAT directional weight multiplied into the
    D105 bucket cell would double-count correlated effects (iv_rank's edge is
    partly its swing_mid reach, which the bucket cell already prices). Keying
    the full triple and anchoring on the pair separates "this directional
    mints" from "this bucket mints": zero triple evidence reproduces the pair
    cell exactly, so the joint draw's fallback chain (triple → pair → prior)
    is scale-coherent. Empty gated_runs → ``{}``.
    """

    def _hyp_dir_bucket_of(cfg: Mapping[str, object]) -> tuple[str, str, str] | None:
        hyp = cfg.get("hypothesis")
        bucket = cfg.get("dte_bucket")
        directional = _directional_indicator_of(cfg)
        if isinstance(hyp, str) and isinstance(bucket, str) and directional is not None:
            return (hyp, directional, bucket)
        return None

    triple_sums = _component_rate_sums(
        db,
        gated_runs,
        _hyp_dir_bucket_of,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    return _hierarchical_posteriors(
        triple_sums,
        lambda key: (key[0], key[2]),
        alpha=alpha,
        beta=beta,
        prior_strength=prior_strength,
    )


def _cohort_of(cfg: Mapping[str, object]) -> str | None:
    """The cohort of a serialized config: ``"xsect"`` for a ``cross_sectional_rank``
    combiner (the H1 breadth lever — underlying=None, the runner ranks the
    universe), ``"single"`` for ``confluence`` (a pinned single name). ``None``
    when the combiner is absent/malformed or carries an unrecognized type.

    Cohort is NOT a first-class StrategyConfig field — it is exactly
    ``combiner.type``, the same value the sampler sets at its final draw
    (sampler.py H1 block). It is the §3 axis of Crucible's 2026-06-17 yield-map
    refresh: the largest within-stratum component-rate spread (cross-sectional
    momentum 40.4% vs single-name 0.96% on the identical recipe)."""
    combiner = cfg.get("combiner")
    if not isinstance(combiner, dict):
        return None
    ctype = combiner.get("type")
    if ctype == "cross_sectional_rank":
        return "xsect"
    if ctype == "confluence":
        return "single"
    return None


def compute_cohort_yield_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
    prior_strength: float = COMPONENT_HIER_PRIOR_STRENGTH,
) -> dict[tuple[str, str, str, str], float]:
    """``(hypothesis, directional, dte_bucket, cohort)`` component-rate posterior,
    shrunk toward its ``(hypothesis, directional, dte_bucket)`` D106 triple.

    Crucible's 2026-06-17 yield-map refresh found COHORT (cross-sectional vs
    single-name) is the largest within-stratum yield axis: the identical
    ``momentum_252 | hurst | swing_long`` trend recipe mints 40.4%
    cross-sectional vs 0.96% single-name. The D105 pair and D106 triple cannot
    express it, and the sampler draws the cohort from a FIXED
    ``rank_combiner_share`` coin-flip, blind to yield. This weighter learns the
    cohort component-rate so the sampler can tilt its (last) cohort draw toward
    the higher-minting cohort of the already-chosen recipe.

    The quad is anchored on the D106 triple (``key[:3]``) exactly as the triple
    is anchored on the D105 pair: zero cohort-specific evidence reproduces the
    triple posterior, so the sampler's fallback chain (cohort -> triple -> share)
    stays scale-coherent. This is a WITHIN-hypothesis reallocation
    (single<->xsect for a fixed ``(hypothesis, directional)``) — it never shifts
    the cross-hypothesis mix, which lives in the hypothesis weights (so it cannot
    by itself deepen the trend monoculture). Same engine, estimand and version
    scoping (D081) as the D105/D106 weighters; empty gated_runs -> ``{}``
    (cold-start: the sampler keeps the fixed share, byte-identical — hard rule #6).
    """

    def _hyp_dir_bucket_cohort_of(cfg: Mapping[str, object]) -> tuple[str, str, str, str] | None:
        hyp = cfg.get("hypothesis")
        bucket = cfg.get("dte_bucket")
        directional = _directional_indicator_of(cfg)
        cohort = _cohort_of(cfg)
        if (
            isinstance(hyp, str)
            and isinstance(bucket, str)
            and directional is not None
            and cohort is not None
        ):
            return (hyp, directional, bucket, cohort)
        return None

    quad_sums = _component_rate_sums(
        db,
        gated_runs,
        _hyp_dir_bucket_cohort_of,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    return _hierarchical_posteriors(
        quad_sums,
        lambda key: (key[0], key[1], key[2]),
        alpha=alpha,
        beta=beta,
        prior_strength=prior_strength,
    )


def compute_regime_gate_yield_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
    prior_strength: float = COMPONENT_HIER_PRIOR_STRENGTH,
) -> dict[tuple[str, str, str, str], float]:
    """``(hypothesis, directional, dte_bucket, regime_gate)`` component-rate
    posterior, shrunk toward its ``(hypothesis, directional, dte_bucket)`` D106
    triple — increment 2 of Crucible's 2026-06-17 yield-map refresh (§2/§4).

    Within a fixed triple the regime GATE moves the component rate (live Forge
    data: trend|momentum_252|swing_long mints hurst 8.1% vs gamma_flip 0.0% —
    the §4 "gamma_flip regime gate is a near-universal yield sink" replicates).
    This learns that lift so the sampler's regime draw avoids the sink gates and
    favours the minting ones, on top of the §3.5 R-rule pool (hard rule #1: the
    pool is unchanged; only the draw WITHIN it is re-weighted).

    **D119 GUARD — relative_value is EXCLUDED.** Its ``pairs_convergence`` runner
    evaluates NO regime filter (`pairs_convergence.py`, D118/D119), so an rv
    regime label is a dead tag: weighting it would repeat the D119 sampling-
    artifact mistake (gate-id↔outcome correlation with no causal path). Every
    other hypothesis's runner (composable_long_options / cross_sectional_rank)
    DOES evaluate the gate, so the lift is causal. Cohort is deliberately NOT in
    the key: the regime is drawn BEFORE the cohort in `sample_config`, so it
    cannot be conditioned on it (a cohort-conditioned regime is the cohort-
    reorder increment); the quad is cohort-blended.

    Same engine, estimand and version scoping (D081) as the D105/D106/cohort
    weighters; empty gated_runs -> ``{}`` (cold-start: the sampler keeps its
    D150/uniform regime draw, byte-identical — hard rule #6).
    """

    def _hyp_dir_bucket_regime_of(cfg: Mapping[str, object]) -> tuple[str, str, str, str] | None:
        hyp = cfg.get("hypothesis")
        # D119: relative_value's pairs runner never evaluates the gate — the label
        # is dead, so it must not contribute a learned cell (excluded here AND
        # guarded again at the draw site in `_pick_regime`).
        if hyp == "relative_value":
            return None
        bucket = cfg.get("dte_bucket")
        directional = _directional_indicator_of(cfg)
        regime = _regime_indicator_of(cfg)
        if (
            isinstance(hyp, str)
            and isinstance(bucket, str)
            and directional is not None
            and regime is not None
        ):
            return (hyp, directional, bucket, regime)
        return None

    quad_sums = _component_rate_sums(
        db,
        gated_runs,
        _hyp_dir_bucket_regime_of,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    return _hierarchical_posteriors(
        quad_sums,
        lambda key: (key[0], key[1], key[2]),
        alpha=alpha,
        beta=beta,
        prior_strength=prior_strength,
    )


# ---------------------------------------------------------------------------
# Orthogonal-yield marginal-value discount (H4; NEW_HYPOTHESES_V11_PLAN).
#
# D105 re-aimed the reward to raw component-rate. That maximises components, but
# the live pool (2026-06-08 yield map) shows it over-concentrates into CORRELATED
# sleeves: 122 volatility_event components share one variance-risk-premium factor
# and one macro calendar, 36 on AAPL alone. The pod-shop uncorrelated-sleeve
# model (Millennium: 330+ *uncorrelated* sleeves, partitioned to prevent alpha
# cannibalisation) says the marginal portfolio value of the 37th AAPL long-vol
# clone ≈ 0 — so a generator that keeps minting them is spending breadth it can't
# bank. H4 discounts each (hypothesis x directional x underlying-class) FACTOR
# CELL's underlying-draw weight by the Grinold marginal-value factor
# (1 + m) ** -strength, m = the cell's component count: the over-mined cell yields
# draw probability to orthogonal candidates without lowering any gate (hard rule
# #3) and without a grammar change (versionless, like D101/D103/D105 components).
#
# Why this is NOT the §6.3 diversifier: the diversifier is selection-side and
# Jaccard-keyed — two AAPL long-vol configs with different thresholds have low
# structural Jaccard yet sit in the IDENTICAL factor cell, so it cannot see the
# correlation H4 targets. H4 lives on the generation/feedback side, keyed on the
# factor cell, where the concentration actually accumulates.
#
# Anti-Goodhart by construction: the discount is computed off the COMPONENT count
# only (tiebreak_weight=0.0 — the ordering tiebreak the other weighters carry is
# irrelevant to a marginal-value count), so it is a pure function of components,
# never trades. A cell with 0 components is ABSENT from the map (discount 1.0 at
# the draw site): dead-but-busy cells are neither inflated nor penalised for
# trading — only over-represented cells bite. The cell is keyed on underlying
# NAME (D108, from the emission proof): at class granularity the underlying draw
# can only shift high-idio→diversified within a (hyp, directional), and
# diversified vol_event mints far less, so a class discount dilutes yield rather
# than orthogonalising; the name cell spreads the over-mined name (AAPL) across
# its minting peers (NVDA/AMD/…). Note H4 cannot reach the FACTOR (variance-risk-
# premium) concentration all high-idio vol_event components share — that needs
# hypothesis/directional diversification, not the underlying draw — so its
# ceiling is modest by construction (a quality lever, not a breadth lever).
#
# Consumer: the sampler slices the triple map by the chosen (hypothesis,
# directional) and multiplies each candidate ticker's existing D105/D106 weight
# by its class's discount BEFORE the underlying exploration floor — so the floor
# is preserved and a crowded cell stays explorable (evidence keeps flowing to
# revise the discount). None/empty → no-op (byte-identical; hard rule #6).
# ---------------------------------------------------------------------------


def _factor_cell_of(cfg: Mapping[str, object]) -> tuple[str, str, str] | None:
    """The ``(hypothesis, directional, underlying-name)`` factor cell of a
    serialized config, or ``None``.

    Keyed on the NAME (not the two-class label) per the 2026-06-08 emission proof
    (D108): H4 attaches at the underlying draw, which only redistributes WITHIN a
    fixed (hypothesis, directional); at class granularity the only move is
    high-idio→diversified, and diversified vol_event mints ~0.7% vs high-idio's
    6.1%, so a class discount dilutes yield instead of orthogonalising. The real
    concentration ("36 on AAPL") is per-name inside high-idio, so the name cell
    is what lets the discount spread AAPL→NVDA/AMD (all minting names). Natural
    D105(class)→D106(name) progression.

    ``None`` for relative_value (its ``underlying`` is None — pairs legs are
    Crucible-resolved, D098 — so it has no single-name draw for H4 to tilt) and
    for any config missing a parseable hypothesis / directional / underlying."""
    hyp = cfg.get("hypothesis")
    underlying = cfg.get("underlying")
    if not isinstance(hyp, str) or not isinstance(underlying, str):
        return None
    directional = _directional_indicator_of(cfg)
    if directional is None:
        return None
    return (hyp, directional, underlying)


def compute_orthogonal_yield_discounts(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
    strength: float = DEFAULT_ORTHOGONAL_YIELD_STRENGTH,
    min_discount: float = DEFAULT_ORTHOGONAL_YIELD_MIN_DISCOUNT,
) -> dict[tuple[str, str, str], float]:
    """Marginal-value discount per ``(hypothesis, directional, underlying-name)``
    factor cell (H4).

    Each cell's discount is ``max(min_discount, (1 + m) ** -strength)`` where
    ``m`` is the cell's version-weighted component count (D081 scoping: a
    prior-version component contributes ``prior_version_weight``; a cold-start
    hypothesis drops its prior-version rows entirely). Only cells with at least
    one component appear — a cell with zero components has discount 1.0 and is
    omitted, so the sampler (which defaults absent cells to 1.0) leaves it
    untouched. This is the anti-Goodhart property: the discount keys on
    components, never on trades.

    Same determinism property as the rest of the module (hard rule #6: a pure
    function of the ``submissions`` table + the ``gated_runs`` snapshot) and the
    same empty → ``{}`` cold-start contract (the sampler then applies no
    discount, byte-identical to the pre-H4 underlying draw).
    """
    if not gated_runs:
        return {}
    # tiebreak_weight=0.0 AND quality_weight=0.0: H4 wants the pure component
    # COUNT for the marginal-value factor — neither the gate/Sharpe ordering
    # tiebreak nor the D114 joint-quality term may contribute, or componentless
    # cells would gain non-zero mass and break "discount = 1.0 at m = 0".
    sums = _component_rate_sums(
        db,
        gated_runs,
        _factor_cell_of,
        tiebreak_weight=0.0,
        quality_weight=0.0,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )
    return {
        cell: max(min_discount, (1.0 + count) ** (-strength))
        for cell, (_total, count) in sums.items()
        if count > 0.0
    }


# ---------------------------------------------------------------------------
# Dynamic relative_value regime-gate curation (D103 / v9; estimand re-aimed by
# D105) — FROZEN by D119 (2026-06-09).
#
# relative_value has no §3.5 R-rule, so the sampler draws its mandatory regime
# gate near-uniformly from the WHOLE registry (search_space._build_regime_pool),
# unlike R1/R2/R3-constrained mean_reversion / trend_continuation /
# volatility_event. In the live gated cohort the two most-sampled relative_value
# gates (rsi_2, rv_rank) were among the WORST performers — so D103 LEARNED which
# gates yield accepted components, scoped to relative_value, and the sampler
# tilted toward them. D105 note: the original D103 estimand (the D094
# trade-biased reward) collapsed once the rv fix made every gate trade — the
# live journal showed all 34 gates compressed into 0.33-0.40 — so it was
# re-aimed at the component-rate engine above.
#
# D119 FREEZE: Crucible's class-map response (2026-06-09,
# `../Crucible/docs/handoffs/FORGE_rank_gate_class_map.md` §3) proved from code
# that the `pairs_convergence` runner evaluates NO regime filters —
# `propose_actions` gates purely on cointegration pvalue/zscore/halflife and
# never calls `signal.evaluate(...)` (`pairs_convergence.py:89-168`). Every
# relative_value regime gate ever submitted (15,960/15,960 confluence → all
# routed to that path) was a dead label, so the D103 premise ("rsi_2/rv_rank
# are the worst-performing gates") was a sampling artifact: gate-id vs outcome
# correlations with no causal path. The learned posterior is noise; APPLYING it
# tilts rv emission toward accidental winners. The compute function therefore
# returns `{}` unconditionally — the sampler's documented cold-start contract
# (empty → uniform regime draw, identical to pre-D103). The learning machinery
# below the early return is kept dormant for reversibility: if Crucible threads
# regime gates into the pairs path, drop the early return and restore the D103
# learning tests from git history at the D119 commit. The regime POOL is
# unchanged throughout (hard rule #1 — no rule edit).
# ---------------------------------------------------------------------------

_REGIME_CURATED_HYPOTHESIS: str = "relative_value"


def _regime_indicator_of(cfg: Mapping[str, object]) -> str | None:
    """The regime-gate indicator id of a serialized config, or ``None``.

    The §3.5 S3 ``regime_filter`` signal carries the gate; its first indicator
    id is the regime concept D103 curates. Returns ``None`` when the signal or
    indicator list is absent/malformed (the caller then skips that run).
    """
    signals = cfg.get("signals")
    if not isinstance(signals, list):
        return None
    for sig in signals:
        if isinstance(sig, dict) and sig.get("role") == "regime_filter":
            inds = sig.get("indicators")
            if isinstance(inds, (list, tuple)) and inds and isinstance(inds[0], str):
                return inds[0]
    return None


# D119 — the freeze switch. True → `compute_relative_value_regime_weights`
# returns `{}` unconditionally (sampler falls back to the uniform regime draw,
# identical to pre-D103). Flip to False ONLY when Crucible's pairs path
# actually evaluates regime filters (see the section comment above) — and
# restore the D103 learning tests from git history at the D119 commit.
_RV_REGIME_WEIGHTS_FROZEN: bool = True


def compute_relative_value_regime_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    quality_weight: float = COMPONENT_QUALITY_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
) -> dict[str, float]:
    """FROZEN (D119): returns ``{}`` unconditionally — see the section comment.

    Crucible's ``pairs_convergence`` runner never evaluates regime filters
    (class-map response §3, 2026-06-09), so the D103/D105 posterior this
    computed was fit to noise. ``{}`` engages the sampler's documented
    cold-start contract (uniform regime draw, identical to pre-D103) and the
    CLI's truthiness-gated journal line simply disappears. The signature and
    the dormant learning body are kept for reversibility — flip
    ``_RV_REGIME_WEIGHTS_FROZEN`` only when the pairs path evaluates gates.
    """
    if _RV_REGIME_WEIGHTS_FROZEN:
        return {}

    def _rv_regime_of(cfg: Mapping[str, object]) -> str | None:
        if cfg.get("hypothesis") != _REGIME_CURATED_HYPOTHESIS:
            return None
        return _regime_indicator_of(cfg)

    return _component_rate_posteriors(
        db,
        gated_runs,
        _rv_regime_of,
        alpha=alpha,
        beta=beta,
        tiebreak_weight=tiebreak_weight,
        quality_weight=quality_weight,
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )


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


def apply_orthogonal_family_floor(
    weights: Mapping[str, float],
    family_floors: Mapping[str, float],
) -> dict[str, float]:
    """Lift designated orthogonal families to a per-family floor over the
    learned hypothesis weights (Layer-2 decorrelated-supply lever; see
    docs/proposals/orthogonal-family-supply-for-pbo.md §3 Layer 2).

    The learned component-rate estimand (``compute_hypothesis_component_weights``)
    rewards "more of what already clears as a component" — the homogeneity PBO
    penalizes — so it starves the one PBO-orthogonal in-v1 family (single-name
    ``volatility_event``, Crucible-validated 2026-06-29 as the second factor:
    PC1 load 0.10, the book clearing real CSCV PBO 0.107) down to the D067 5%
    exploration floor while the 0.78-correlated trend~mr core oscillates at the
    top. This applies a bounded, EXPLICIT floor for the named families so
    assembly has orthogonal material to build a low-PBO book from — WITHOUT
    touching Crucible's gate (hard rule 3) or the grammar (rule 1).

    Contract:
      - Empty ``family_floors`` → ``dict(weights)`` with identical numeric
        values (the flag-OFF cold path). The sampler's family draw is a pure
        function of these values (``rng.choices(..., weights=…)``), so an
        identical-valued map preserves the byte-identical emitted sequence
        (hard rule 6). Always a COPY — never mutate the caller's learned map.
      - ``max(weights[f], floor)``: a family is only ever RAISED, never
        lowered (a family already above its floor passes through; the D067
        floor and every other family's learned budget are preserved — the lift
        only redistributes SAMPLING SHARE via normalization, starving nothing).
      - UNIT (read carefully when interpreting the A/B): ``floor`` is a
        max-NORMALIZED weight — the top learned family sits at 1.0 — NOT a target
        sampling share. The realized share of a floored family is
        ``floor / sum(weights)`` and therefore FLOATS with the other (oscillating)
        families' weights: ``volatility_event=0.20`` delivered ~10.7% share with
        trend saturated at 1.0 (D216 activation), and RISES if the top family's
        weight falls. Judge the lever on the journal's delivered share, not on the
        floor number.
      - A name in ``family_floors`` but ABSENT from ``weights`` is ignored — an
        orthogonal floor never introduces a non-samplable hypothesis.
    """
    result = dict(weights)
    for fam, floor in family_floors.items():
        if fam in result:
            result[fam] = max(result[fam], floor)
    return result


__all__ = [
    "COMPONENT_ALPHA",
    "COMPONENT_BETA",
    "COMPONENT_HIER_PRIOR_STRENGTH",
    "COMPONENT_PRIOR_VERSION_WEIGHT",
    "COMPONENT_QUALITY_WEIGHT",
    "COMPONENT_TIEBREAK_WEIGHT",
    "DEFAULT_ALPHA",
    "DEFAULT_BETA",
    "DEFAULT_EXPLORATION_FLOOR",
    "DEFAULT_GATE_PROGRESS_WEIGHT",
    "DEFAULT_ORTHOGONAL_YIELD_MIN_DISCOUNT",
    "DEFAULT_ORTHOGONAL_YIELD_STRENGTH",
    "DEFAULT_SHARPE_CEILING",
    "DEFAULT_SHARPE_FLOOR",
    "DEFAULT_SHARPE_METRIC",
    "DEFAULT_SHARPE_WEIGHT",
    "DEFAULT_TRADE_FLOOR",
    "DEFAULT_TRADE_PRODUCTION_WEIGHT",
    "FEEDBACK_GATED_RUNS_LIMIT",
    "apply_exploration_floor",
    "apply_orthogonal_family_floor",
    "component_prior_mean",
    "compute_hypothesis_bucket_weights",
    "compute_hypothesis_component_weights",
    "compute_hypothesis_directional_bucket_weights",
    "compute_hypothesis_reward_weights",
    "compute_hypothesis_weights",
    "compute_orthogonal_yield_discounts",
    "compute_relative_value_regime_weights",
    "compute_underlying_class_weights",
    "compute_underlying_name_weights",
    "prior_mean",
]
