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
    from collections.abc import Set as AbstractSet

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import PreFilterReport
    from forge.ranking.arm_floor import Arm
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
    """
    scored: list[RankedCandidate] = []
    for report in reports:
        if not report.passed:
            continue
        prior = (
            verdict_scorer(report.config)
            if verdict_scorer is not None
            else compute_prior_promotion_proximity(report.config, promoted_strategies)
        )
        composite = ranker.score(report, prior)
        scored.append(
            RankedCandidate(
                report=report,
                prior_promotion_score=prior,
                composite_score=composite,
            ),
        )
    return select_top_n(
        scored,
        n,
        similarity_fn=similarity_fn,
        min_per_hypothesis=min_per_hypothesis,
        floor_exempt_hypotheses=floor_exempt_hypotheses,
        mature_arms=mature_arms,
    )


__all__ = ["rank_batch"]
