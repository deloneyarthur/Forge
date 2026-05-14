"""Filter 1: structural redundancy. DESIGN.md §5.3.1.

Rejects configs whose `config_hash` has already appeared in a prior batch.
O(1) frozenset lookup; first filter in the §5.2 cost-ordered battery
(`cost_tier=1`).

The hash is computed by `crucible_contracts.StrategyConfig.config_hash`
which canonicalizes signals (sorted), parameters, exits (sorted), and
sizer per §5.3.1's checklist.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


class StructuralRedundancyFilter:
    """§5.3.1 — reject configs whose hash has already been submitted."""

    name = "structural_redundancy"
    cost_tier = 1

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        if config.config_hash in ctx.prior_config_hashes:
            return FilterResult(
                passed=False,
                score=0.0,
                details=MappingProxyType({"config_hash": config.config_hash}),
            )
        return FilterResult(passed=True, score=1.0)


__all__ = ["StructuralRedundancyFilter"]
