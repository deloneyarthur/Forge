"""Phase 4 batch-ranking orchestrator.

`rank_batch` composes the §6 components: skip short-circuited reports,
compute `prior_promotion_proximity` per candidate, apply the §6.2
weighted scorer, then run §6.3 greedy diversification to pick `n`.

The function returns up to `n` `RankedCandidate`s in selection order —
that order is the submission queue's per-batch ordering. Caller hands
the list to the submitter, which writes one per inbox slot.

D023/D8 — module 6 of the Phase 4 build.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from forge.ranking.campaigns import config_cell
from forge.ranking.diversifier import jaccard_signal_ids, select_top_n
from forge.ranking.prior_promotion import compute_prior_promotion_proximity
from forge.ranking.types import RankedCandidate

if TYPE_CHECKING:
    import random
    from collections.abc import Set as AbstractSet

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import PreFilterReport
    from forge.ranking.arm_floor import Arm
    from forge.ranking.campaigns import ExperimentCell
    from forge.ranking.scorer import Ranker


# D103 — production per-hypothesis submission floor. Guarantees each enumerable
# hypothesis at least this many of the batch's submitted slots so the orthogonal
# (relative_value) sleeve can't be starved to ~0 by a feedback oscillation (the
# midday mean_reversion flood). ~7.5% of a 200-config batch; binds only during a
# crowding event — a safety net, not a target. Tunable.
_PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS: int = 15

# D145 — hypotheses exempt from the D103 floor above. The floor was built to
# PROTECT the orthogonal relative_value sleeve; Q40 (2026-06-13) established that
# rv is structurally 0-yielding under options-only (long-premium, no spreads,
# 0/3639 honest-era), so guaranteeing it ~7.5% of every batch is pure waste.
# Exempting it reclaims those slots for the merit-ranked pool; rv still competes
# on its (heavily down-weighted) composite. Enumeration is untouched (ranking-
# stage only). Re-evaluate if Crucible ships OverlaySpec / a bear-paying path
# that makes rv viable (PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md).
_PRODUCTION_FLOOR_EXEMPT_HYPOTHESES: frozenset[str] = frozenset({"relative_value"})


@dataclass(frozen=True, slots=True)
class ObjectiveLane:
    """One concurrent submission arm ordered by its own objective (prereg `8cfe95f4a6e9`).

    ``candidate_filter`` is NOT optional decoration — it is what makes a lane reproduce the
    result it was validated on. The trend target (`P(top-200 by wf_p10)`, +34% strong
    components) was measured by RESTRICTING the population to trend rows and selecting
    within it. Without the filter the same model scores every candidate, and since `wf_p10`
    scores MR configs highly too it would select MR — competing with the MR lane for the
    same configs instead of supplying trend, and quietly failing to reproduce its own
    offline number. A lane must select from the population it was fitted and judged on.

    ``None`` means the whole survivor pool, which is correct for a globally-fitted target
    like the MR lane's `sharpe_baseline`.
    """

    tag: str
    slots: int
    scorer: Callable[[StrategyConfig], float]
    candidate_filter: Callable[[StrategyConfig], bool] | None = None


def rank_batch(
    ranker: Ranker,
    reports: Iterable[PreFilterReport],
    promoted_strategies: Sequence[StrategyConfig],
    n: int,
    *,
    similarity_fn: Callable[[StrategyConfig, StrategyConfig], float] = jaccard_signal_ids,
    min_per_hypothesis: int = 0,
    floor_exempt_hypotheses: AbstractSet[str] = frozenset(),
    mature_arms: AbstractSet[Arm] | None = None,
    verdict_scorer: Callable[[StrategyConfig], float] | None = None,
    gate_tail_ordering: bool = False,
    mature_cells: AbstractSet[ExperimentCell] | None = None,
) -> list[RankedCandidate]:
    """Score, diversify, and return up to `n` candidates.

    Only `reports` with `passed=True` reach the scorer — short-circuited
    reports (a filter rejected, later filters skipped) lack the full
    §6.2 inputs and would be biased.

    `promoted_strategies` is the per-batch list returned by
    `crucible_contracts.get_promoted_strategies(...)`. Empty list is
    correct for week-1 operation (no promotions yet); the
    `prior_promotion_proximity` score is `0.0` for every candidate in
    that case, and the §6.2 weighted sum's other 0.90 of weight does
    the work.

    `mature_arms` (D136) activates the diversifier's per-arm exploration
    floor — young `(role, indicator_id)` arms get reserved slots so a new
    grammar arm can't be starved at ranking by the learned weights (the
    v17 cold-start lesson). `None` keeps the legacy selection exactly.

    `floor_exempt_hypotheses` (D145) drops named hypotheses from the D103
    `min_per_hypothesis` reservation while leaving them eligible on merit —
    for a structurally 0-yielding sleeve whose floor is pure waste (Q40).
    Empty (default) keeps the floor universal.

    `verdict_scorer` (D149 — F3 wiring) sets `prior_promotion_proximity :=
    P(component)`: when provided, the per-candidate prior term is this learned
    score INSTEAD of the Jaccard `compute_prior_promotion_proximity`. `None`
    (default) is the **Jaccard kill-switch** — the legacy prior, byte-identical.
    The caller (the production loop) builds the scorer from the latest verdict
    model under an env kill-switch and shadow-compares before trusting it; the
    §6.2 weights and every other term are untouched (it only fills the prior slot).

    `gate_tail_ordering` (P1.1) closes the gate-then-tail shadow↔production fidelity
    gap. In `gate-tail` mode the `verdict_scorer` returns `gate_tail_prior` — `tail_norm`
    for configs clearing the P(component) floor, **0.0 for ineligibles**. When this flag is
    True the composite IS that value (the §6.2 hygiene blend is BYPASSED), so the gate is
    HARD: ineligibles pin to 0.0 (a fixed point of the diversifier's `score·(1-penalty)`
    multiply → they can never outrank an eligible config), and eligibles order by `tail_norm`
    — the same order the shadow's `gate_tail_rank_score` produces. False (default) keeps the
    blend `ranker.score(report, prior)` — byte-identical. Only meaningful with a `verdict_scorer`
    returning a gate-tail value; a no-op on the Jaccard/blend paths.
    """
    scored = _score_reports(
        ranker,
        reports,
        promoted_strategies,
        verdict_scorer=verdict_scorer,
        gate_tail_ordering=gate_tail_ordering,
    )
    return select_top_n(
        scored,
        n,
        similarity_fn=similarity_fn,
        min_per_hypothesis=min_per_hypothesis,
        floor_exempt_hypotheses=floor_exempt_hypotheses,
        mature_arms=mature_arms,
        mature_cells=mature_cells,
    )


def _score_reports(
    ranker: Ranker,
    reports: Iterable[PreFilterReport],
    promoted_strategies: Sequence[StrategyConfig],
    *,
    verdict_scorer: Callable[[StrategyConfig], float] | None,
    gate_tail_ordering: bool,
) -> list[RankedCandidate]:
    """§6.2 score every passed report into a `RankedCandidate` (pre-diversification).
    Shared by `rank_batch` and `rank_batch_with_holdout` so their scoring is identical."""
    scored: list[RankedCandidate] = []
    for report in reports:
        if not report.passed:
            continue
        prior = (
            verdict_scorer(report.config)
            if verdict_scorer is not None
            else compute_prior_promotion_proximity(report.config, promoted_strategies)
        )
        # gate-tail (P1.1): the prior IS the ranking key — a HARD gate matching the shadow.
        # Otherwise the §6.2 weighted blend (default; byte-identical).
        composite = prior if gate_tail_ordering else ranker.score(report, prior)
        scored.append(
            RankedCandidate(
                report=report,
                prior_promotion_score=prior,
                composite_score=composite,
            ),
        )
    return scored


def sample_exploration_holdout(
    pool: Sequence[RankedCandidate], holdout_n: int, rng: random.Random
) -> list[RankedCandidate]:
    """P3.3 (B7): deterministically draw up to `holdout_n` candidates at RANDOM from `pool`
    (the rank-NON-selected survivors). Sorted by config_hash first so the draw is reproducible
    for a given `rng` seed (hard rule #6); the RNG must come from `SeedHierarchy` (rule #8)."""
    if holdout_n <= 0 or not pool:
        return []
    ordered = sorted(pool, key=lambda c: c.report.config.config_hash)
    return rng.sample(ordered, min(holdout_n, len(ordered)))


def sample_young_cell_explore(
    pool: Sequence[RankedCandidate],
    quota: int,
    rng: random.Random,
    *,
    mature_cells: AbstractSet[ExperimentCell] | None,
) -> list[RankedCandidate]:
    """D316 (Theme 2d): seeded random draw of up to ``quota`` YOUNG-cell members
    from the rank-non-selected survivors.

    The floor (D307) guarantees young cells get submitted; this quota makes them
    accrue UNBIASED labels faster than the flat 5% holdout provides. It is a
    SEPARATE lane (tagged ``young_explore`` by the submitter) precisely so the
    uniform holdout stays a clean estimand — the ranker-vs-random A/B (prereg
    61837dd2) and the campaign-audit carriage denominator (D299) both depend on
    the holdout being an unweighted draw. Eligibility mirrors diversifier phase
    0c: cell present, not mature. ``mature_cells is None``
    (floor flag off) or ``quota <= 0`` → inert, byte-identical. Same
    determinism contract as the holdout draw (sorted, seeded, rule #6/#8)."""
    if quota <= 0 or not pool or mature_cells is None:
        return []
    young = [
        c
        for c in pool
        if (cell := config_cell(c.report.config)) is not None and cell not in mature_cells
    ]
    if not young:
        return []
    ordered = sorted(young, key=lambda c: c.report.config.config_hash)
    return rng.sample(ordered, min(quota, len(ordered)))


def rank_batch_with_holdout(
    ranker: Ranker,
    reports: Iterable[PreFilterReport],
    promoted_strategies: Sequence[StrategyConfig],
    n: int,
    *,
    holdout_n: int,
    rng: random.Random,
    similarity_fn: Callable[[StrategyConfig, StrategyConfig], float] = jaccard_signal_ids,
    min_per_hypothesis: int = 0,
    floor_exempt_hypotheses: AbstractSet[str] = frozenset(),
    mature_arms: AbstractSet[Arm] | None = None,
    verdict_scorer: Callable[[StrategyConfig], float] | None = None,
    gate_tail_ordering: bool = False,
    mature_cells: AbstractSet[ExperimentCell] | None = None,
) -> tuple[list[RankedCandidate], list[RankedCandidate]]:
    """P3.3 (B7) exploration holdout: rank-select the top ``n - holdout_n`` as usual, then draw
    ``holdout_n`` at RANDOM from the survivors ranking did NOT pick — configs that bypass the
    learned ranking, giving F3 / the wf_p25 lane / the estimand UNBIASED labels (they train on
    Forge-selected submissions otherwise — a direct feedback loop). Returns
    ``(selected, holdout)``. Total submitted is still ``<= n`` (holdout REPLACES rank slots, it
    doesn't add). `holdout_n == 0` reduces to a plain `rank_batch` selection with an empty
    holdout, so the caller's flag-OFF path stays byte-identical."""
    selected, holdout, _young, _extra = rank_batch_with_exploration(
        ranker,
        reports,
        promoted_strategies,
        n,
        holdout_n=holdout_n,
        rng=rng,
        young_explore_n=0,
        young_rng=None,
        similarity_fn=similarity_fn,
        min_per_hypothesis=min_per_hypothesis,
        floor_exempt_hypotheses=floor_exempt_hypotheses,
        mature_arms=mature_arms,
        verdict_scorer=verdict_scorer,
        gate_tail_ordering=gate_tail_ordering,
        mature_cells=mature_cells,
    )
    return selected, holdout


def rank_batch_with_exploration(
    ranker: Ranker,
    reports: Iterable[PreFilterReport],
    promoted_strategies: Sequence[StrategyConfig],
    n: int,
    *,
    holdout_n: int,
    rng: random.Random,
    young_explore_n: int = 0,
    young_rng: random.Random | None = None,
    similarity_fn: Callable[[StrategyConfig, StrategyConfig], float] = jaccard_signal_ids,
    min_per_hypothesis: int = 0,
    floor_exempt_hypotheses: AbstractSet[str] = frozenset(),
    mature_arms: AbstractSet[Arm] | None = None,
    verdict_scorer: Callable[[StrategyConfig], float] | None = None,
    gate_tail_ordering: bool = False,
    mature_cells: AbstractSet[ExperimentCell] | None = None,
    extra_lanes: Sequence[ObjectiveLane] = (),
) -> tuple[
    list[RankedCandidate],
    list[RankedCandidate],
    list[RankedCandidate],
    dict[str, list[RankedCandidate]],
]:
    """The exploration engine (P3.3 holdout + D316 young-cell quota + the tail lane).

    Returns ``(selected, holdout, young_explore, extra)`` where ``extra`` maps each
    objective lane's tag to its picks — the submission lanes
    the submitter tags. Rank slots = ``n - holdout_n - effective_young`` where
    ``effective_young`` counts only what the young draw can actually fill (a
    short young pool never under-fills the merit lane). Draw order: merit →
    holdout (uniform, from ALL non-selected survivors — the estimand lane must
    never be conditioned on cell age) → young quota (from the remainder, young
    cells only). Both explore lanes REPLACE rank slots; total
    stays ``<= n``. ``young_explore_n == 0`` or ``mature_cells is None`` (the
    D307 floor flag off) keeps the young lane empty and the holdout path
    byte-identical to the pre-D316 form.

    ``extra_lanes`` (prereg `8cfe95f4a6e9`) is a sequence of `ObjectiveLane` CONCURRENT
    arms, each ordered by its own objective rather than the merit lane's
    `E[cpcv]`. Measured 2026-07-27, the objective is REGIONAL not global: on the MR slice
    `P(top-800 by sharpe_baseline)` delivers 4.23x the merit arm's strong-component rate
    live, while on TREND that same target is WORSE than the incumbent (41 vs 44) and
    `P(top-200 by wf_p10)` wins instead (59 vs 44, +34%). One lane per region, each with
    its own target.

    Lanes draw in the order given, before the merit lane, from the same survivor pool; each
    lane's picks leave the pool so no config lands in two arms and the arm split stays a
    query rather than an inference. Their slots come OUT of the merit lane, so batch size is
    unchanged and every arm is like-for-like.

    Why concurrent rather than a switch: Crucible's `k5_share` fix read at +5.09 sigma *because*
    it was an arm split, and their instrument has a drift floor where bootstrap SEs
    understate across-window variation by 1.3-2.1x and do not shrink with n — so a
    before/after comparison across time is unreadable at any sample size, while two arms in
    the same batches cancel the drift. ``tail_n == 0`` or no scorer → empty lane, and every
    other lane is byte-identical."""
    scored = _score_reports(
        ranker,
        reports,
        promoted_strategies,
        verdict_scorer=verdict_scorer,
        gate_tail_ordering=gate_tail_ordering,
    )
    # Objective arms draw first, each on its own scorer, and never share a config with the
    # merit arm or each other — disjoint lanes are what make the arm split readable.
    extra: dict[str, list[RankedCandidate]] = {}
    for lane in extra_lanes:
        tag, slots = lane.tag, lane.slots
        if slots <= 0 or not scored:
            extra[tag] = []
            continue
        # Restrict to the population this lane was fitted and judged on, BEFORE scoring.
        eligible = (
            scored
            if lane.candidate_filter is None
            else [c for c in scored if lane.candidate_filter(c.report.config)]
        )
        if not eligible:
            extra[tag] = []
            continue
        rescored = [
            RankedCandidate(
                report=c.report,
                prior_promotion_score=c.prior_promotion_score,
                composite_score=lane.scorer(c.report.config),
            )
            for c in eligible
        ]
        picks = select_top_n(
            rescored,
            min(slots, len(rescored)),
            similarity_fn=similarity_fn,
            min_per_hypothesis=0,
            floor_exempt_hypotheses=floor_exempt_hypotheses,
        )
        extra[tag] = picks
        taken = {c.report.config.config_hash for c in picks}
        scored = [c for c in scored if c.report.config.config_hash not in taken]
    # Pre-draw the young quota's FEASIBLE size against the whole scored pool so
    # merit slots are only surrendered for draws that can actually happen. The
    # actual draw runs after selection/holdout over the true remainder.
    if young_explore_n > 0 and mature_cells is not None:
        young_capacity = sum(
            1
            for c in scored
            if (cell := config_cell(c.report.config)) is not None and cell not in mature_cells
        )
        effective_young = min(young_explore_n, young_capacity)
    else:
        effective_young = 0
    selected = select_top_n(
        scored,
        max(0, n - holdout_n - effective_young - sum(len(v) for v in extra.values())),
        similarity_fn=similarity_fn,
        min_per_hypothesis=min_per_hypothesis,
        floor_exempt_hypotheses=floor_exempt_hypotheses,
        mature_arms=mature_arms,
        mature_cells=mature_cells,
    )
    selected_hashes = {c.report.config.config_hash for c in selected}
    pool = [c for c in scored if c.report.config.config_hash not in selected_hashes]
    holdout = sample_exploration_holdout(pool, holdout_n, rng)
    holdout_hashes = {c.report.config.config_hash for c in holdout}
    remainder = [c for c in pool if c.report.config.config_hash not in holdout_hashes]
    young = (
        sample_young_cell_explore(
            remainder,
            effective_young,
            young_rng,
            mature_cells=mature_cells,
        )
        if effective_young > 0 and young_rng is not None
        else []
    )
    return selected, holdout, young, extra


__all__ = [
    "ObjectiveLane",
    "rank_batch",
    "rank_batch_with_exploration",
    "rank_batch_with_holdout",
    "sample_exploration_holdout",
    "sample_young_cell_explore",
]
