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

from forge.enumeration.underlying_class import underlying_class

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

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
# D081 semantics at the reward layer; one current-version run ≈ 4 prior ones.
COMPONENT_PRIOR_VERSION_WEIGHT: float = 0.25
# The gated-runs window every feedback weight loader requests. Shared here (not
# in the CLI) so the tiebreak-vs-window invariant is checkable next to ε.
FEEDBACK_GATED_RUNS_LIMIT: int = 10_000

_COMPONENT_DECISIONS: frozenset[str] = frozenset({"component", "promote"})


def component_prior_mean(*, alpha: float = COMPONENT_ALPHA, beta: float = COMPONENT_BETA) -> float:
    """Beta(alpha, beta) prior mean — the weight given to unseen keys."""
    return alpha / (alpha + beta)


def _component_run_reward(gated_run: GatedRun, *, tiebreak_weight: float) -> float:
    """1.0 for a component/promote decision, else an epsilon-scale tiebreak.

    Promote counts as a component event — a promoted run cleared component-level
    screening on the way (contracts: 'component' = passed component screening
    but not the full portfolio gate). The tiebreak reuses the D094/D101 quality
    signals (gate-progress + Sharpe-proximity) at a scale that can order
    zero-component keys but can never outrank a real component (see the section
    comment's sizing invariant).
    """
    if gated_run.decision.decision in _COMPONENT_DECISIONS:
        return 1.0
    gates = gated_run.decision.gate_results
    gate_fraction = sum(1 for g in gates.values() if g.passed) / len(gates) if gates else 0.0
    traded = gated_run.run.trade_count >= DEFAULT_TRADE_FLOOR
    return tiebreak_weight * (gate_fraction + _sharpe_reward(gated_run, traded=traded)) / 2.0


def _component_rate_posteriors[K](
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    key_of: Callable[[Mapping[str, object]], K | None],
    *,
    alpha: float,
    beta: float,
    tiebreak_weight: float,
    current_grammar_version: str | None,
    prior_version_weight: float,
    cold_start_hypotheses: frozenset[str],
) -> dict[K, float]:
    """Beta-smoothed component-rate posterior per ``key_of(config)`` key.

    The shared engine behind the hypothesis / regime / bucket / underlying-class
    weighters: one join (submissions → batch_summaries for the D081 version
    resolution, restricted to the gated hashes), one estimand, one smoothing
    rule — so every granularity stays on a single coherent scale. Rows whose
    ``key_of`` returns None are skipped (wrong hypothesis for a scoped key,
    corrupt config_json, missing fields). Same determinism property as the rest
    of the module (hard rule #6): a pure function of the snapshot inputs.
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
        key = key_of(cfg)
        if key is None:
            continue
        is_current = current_grammar_version is None or grammar_version == current_grammar_version
        if not is_current and cfg.get("hypothesis") in cold_start_hypotheses:
            continue
        weight = 1.0 if is_current else prior_version_weight
        bucket = acc.setdefault(key, [0.0, 0.0])
        bucket[0] += weight
        bucket[1] += weight * _component_run_reward(gr, tiebreak_weight=tiebreak_weight)
    return {
        key: (alpha + reward_sum) / (alpha + beta + total)
        for key, (total, reward_sum) in acc.items()
    }


def compute_hypothesis_component_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    hypotheses: Iterable[str],
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
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
        current_grammar_version=current_grammar_version,
        prior_version_weight=prior_version_weight,
        cold_start_hypotheses=cold_start_hypotheses,
    )


# ---------------------------------------------------------------------------
# Dynamic relative_value regime-gate curation (D103 / v9; estimand re-aimed by
# D105).
#
# relative_value has no §3.5 R-rule, so the sampler draws its mandatory regime
# gate near-uniformly from the WHOLE registry (search_space._build_regime_pool),
# unlike R1/R2/R3-constrained mean_reversion / trend_continuation /
# volatility_event. In the live gated cohort the two most-sampled relative_value
# gates (rsi_2, rv_rank) are among the WORST performers — an incoherent gate
# just subsets a pairs-convergence signal's entry dates with noise, yielding the
# negative-Sharpe runs that fail walk_forward_sharpe_median / cpcv_sharpe_p25.
# Rather than a static hand-curated subset (overfit to a thin n~49 sample), this
# LEARNS which gates yield accepted components, scoped to relative_value, so the
# sampler tilts toward them. D105 note: the original D103 estimand (the D094
# trade-biased reward) collapsed once the rv fix made every gate trade — the
# live journal showed all 34 gates compressed into 0.33-0.40 — so it now uses
# the component-rate engine above. The regime POOL is unchanged (hard rule #1 —
# no rule edit); only the SELECTION weight changes, floored by the sampler
# (D067 analogue) so no regime is starved out of exploration.
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


def compute_relative_value_regime_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = COMPONENT_ALPHA,
    beta: float = COMPONENT_BETA,
    tiebreak_weight: float = COMPONENT_TIEBREAK_WEIGHT,
    current_grammar_version: str | None = None,
    prior_version_weight: float = COMPONENT_PRIOR_VERSION_WEIGHT,
    cold_start_hypotheses: frozenset[str] = frozenset(),
) -> dict[str, float]:
    """Per-regime-indicator component-rate posterior, WITHIN ``relative_value``
    (D103, estimand re-aimed by D105).

    Each gated ``relative_value`` run contributes the component-rate reward
    (component/promote = 1.0, epsilon tiebreak otherwise), bucketed by its
    regime-gate indicator. Returns RAW posteriors — the regime key set is open
    (registry-dependent), so the sampler compares against its own prior/floor
    constants rather than a normalized scale (see the D105 section comment).
    Same empty -> ``{}`` cold-start contract (the sampler falls back to
    uniform) and the same determinism property (hard rule #6: a pure function
    of the ``submissions`` table + the ``gated_runs`` snapshot).
    """

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


__all__ = [
    "COMPONENT_ALPHA",
    "COMPONENT_BETA",
    "COMPONENT_PRIOR_VERSION_WEIGHT",
    "COMPONENT_TIEBREAK_WEIGHT",
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
    "FEEDBACK_GATED_RUNS_LIMIT",
    "apply_exploration_floor",
    "component_prior_mean",
    "compute_hypothesis_bucket_weights",
    "compute_hypothesis_component_weights",
    "compute_hypothesis_reward_weights",
    "compute_hypothesis_weights",
    "compute_relative_value_regime_weights",
    "compute_underlying_class_weights",
    "prior_mean",
]
