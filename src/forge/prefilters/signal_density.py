"""Filter 3: signal density. DESIGN.md §5.3.3.

Counts the directional signal's historical activations and rejects below
`calibration.signal_density.min_activations` (default 30). O(N) feature
rows; cost_tier=3 in the §5.2 battery.

Score is `log1p(n) / log1p(10 * min_activations)`, clamped to [0, 1].
This is graceful at low counts (passes barely produce a low score; the
ranker can still weight them) and saturates near 10x the threshold.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import SignalSpec, StrategyConfig

    from forge.prefilters.types import FilterContext


def _directional_signal(config: StrategyConfig) -> SignalSpec:
    """Return the one directional signal. §3.5 S2 guarantees exactly one
    exists in any grammar-valid config; this is a defensive lookup."""
    directionals = [s for s in config.signals if s.role == "directional"]
    if len(directionals) != 1:
        msg = (
            "signal_density: expected exactly one directional signal "
            f"(grammar S2); got {len(directionals)}"
        )
        raise ValueError(msg)
    return directionals[0]


class SignalDensityFilter:
    """§5.3.3 — reject configs whose directional signal fires too rarely."""

    name = "signal_density"
    cost_tier = 3

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        activations = ctx.feature_cache.activation_dates(directional.id)
        n = len(activations)
        min_required = ctx.calibration.signal_density.min_activations

        passed = n >= min_required
        if passed:
            denominator = math.log1p(10 * min_required)
            score = min(1.0, math.log1p(n) / denominator) if denominator > 0 else 0.0
        else:
            score = 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType({"n_activations": n, "min_activations": min_required}),
        )


__all__ = ["SignalDensityFilter"]
