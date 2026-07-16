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
from typing import TYPE_CHECKING

from forge.ranking.diversifier import jaccard_signal_ids, select_top_n
from forge.ranking.prior_promotion import compute_prior_promotion_proximity
from forge.ranking.types import RankedCandidate

if TYPE_CHECKING:
    import random
    from collections.abc import Set as AbstractSet

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import PreFilterReport
    from forge.ranking.arm_floor import Arm
    from forge.ranking.experiment_cells import ExperimentCell
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
    experiment_cells: AbstractSet[ExperimentCell] | None = None,
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
        experiment_cells=experiment_cells,
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
    experiment_cells: AbstractSet[ExperimentCell] | None = None,
) -> tuple[list[RankedCandidate], list[RankedCandidate]]:
    """P3.3 (B7) exploration holdout: rank-select the top ``n - holdout_n`` as usual, then draw
    ``holdout_n`` at RANDOM from the survivors ranking did NOT pick — configs that bypass the
    learned ranking, giving F3 / the wf_p25 lane / the estimand UNBIASED labels (they train on
    Forge-selected submissions otherwise — a direct feedback loop). Returns
    ``(selected, holdout)``. Total submitted is still ``<= n`` (holdout REPLACES rank slots, it
    doesn't add). `holdout_n == 0` reduces to a plain `rank_batch` selection with an empty
    holdout, so the caller's flag-OFF path stays byte-identical."""
    scored = _score_reports(
        ranker,
        reports,
        promoted_strategies,
        verdict_scorer=verdict_scorer,
        gate_tail_ordering=gate_tail_ordering,
    )
    selected = select_top_n(
        scored,
        max(0, n - holdout_n),
        similarity_fn=similarity_fn,
        min_per_hypothesis=min_per_hypothesis,
        floor_exempt_hypotheses=floor_exempt_hypotheses,
        mature_arms=mature_arms,
        experiment_cells=experiment_cells,
    )
    selected_hashes = {c.report.config.config_hash for c in selected}
    pool = [c for c in scored if c.report.config.config_hash not in selected_hashes]
    holdout = sample_exploration_holdout(pool, holdout_n, rng)
    return selected, holdout


__all__ = ["rank_batch", "rank_batch_with_holdout", "sample_exploration_holdout"]
