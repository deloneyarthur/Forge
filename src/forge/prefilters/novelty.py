"""Filter 5: novelty. DESIGN.md §5.3.5.

For each prior tested config in `ctx.prior_firing_dates`, compute the
Jaccard overlap of historical directional-signal firing dates. Reject
when max overlap exceeds `calibration.novelty.max_jaccard_overlap`
(default 0.80). Prevents Forge from flooding Crucible with minor
variations of already-tested ideas.

O(M) priors with constant work per prior (frozenset intersection +
union). `cost_tier=5` in the §5.2 battery.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from datetime import date

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


def _jaccard(a: frozenset[date], b: frozenset[date]) -> float:
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


class NoveltyFilter:
    """§5.3.5 — reject configs with > threshold Jaccard overlap to a prior."""

    name = "novelty"
    cost_tier = 5

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        candidate = ctx.feature_cache.activation_dates(directional.id)

        max_overlap = 0.0
        max_overlap_with: str | None = None
        for prior_hash, prior_dates in ctx.prior_firing_dates.items():
            overlap = _jaccard(candidate, prior_dates)
            if overlap > max_overlap:
                max_overlap = overlap
                max_overlap_with = prior_hash

        threshold = ctx.calibration.novelty.max_jaccard_overlap
        passed = max_overlap <= threshold
        # Score: 1.0 = fully novel; 0.0 = identical to a prior.
        score = 1.0 - max_overlap if passed else 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "max_overlap": max_overlap,
                    "max_overlap_with": max_overlap_with,
                    "n_priors_checked": len(ctx.prior_firing_dates),
                    "max_jaccard_overlap_threshold": threshold,
                }
            ),
        )


__all__ = ["NoveltyFilter"]
