"""Filter 2: resource feasibility. DESIGN.md §5.3.2.

Rejects configs whose maximum indicator lookback exceeds the available
historical depth (`registry.data_history_days`, added in contracts v1.5.0).
Lookback per signal is `max` across the signal's indicators (D010).

O(1) per config (linear in signals x indicators, both small constants).
Runs second in the §5.2 battery, after structural redundancy.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


class ResourceFeasibilityFilter:
    """§5.3.2 — reject configs whose max lookback exceeds history depth."""

    name = "resource_feasibility"
    cost_tier = 2

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        by_id = {ind.id: ind for ind in ctx.registry.indicators}
        max_lookback = 0
        for sig in config.signals:
            for ind_id in sig.indicators:
                max_lookback = max(max_lookback, by_id[ind_id].lookback)

        history = ctx.registry.data_history_days
        passed = max_lookback <= history
        # Headroom fraction in [0, 1] when feasible; 0.0 on rejection.
        score = 1.0 - (max_lookback / history) if passed else 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType({"max_lookback": max_lookback, "data_history_days": history}),
        )


__all__ = ["ResourceFeasibilityFilter"]
