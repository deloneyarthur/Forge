"""Filter 4: expected trade count. DESIGN.md §5.3.4.

Combines the directional signal's activation count with the DTE bucket's
typical hold time to estimate trades over the cached window. Rejects
configs whose estimate falls below
`calibration.expected_trade_count.min_trades` (default 50).

§5.3.4 motivation: Crucible requires 100 OOS trades for promotion, so
Forge wants 50+ trades of headroom in the cached window before paying the
cost of a full backtest.

The hold-day table is a coarse estimate; refinement belongs to Phase 5
when feedback data shows actual trade-rate distributions per bucket.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext

# Approximate hold time per DTE bucket — midpoint of §3.5 P2 entry-DTE
# windows. Used to convert activation count to expected trade count
# under a concurrency cap.
_HOLD_DAYS_BY_BUCKET: dict[str, int] = {
    "swing_short": 15,  # P2 entry window (14, 21) ~ 17.5 midpoint, rounded down
    "swing_mid": 35,  # P2 entry window (30, 45)
    "swing_long": 75,  # P2 entry window (60, 90)
}

# How many concurrent positions a single strategy can hold. The grammar
# doesn't model this directly; 5 is a sensible Phase 3 default that lets
# swing_long strategies clear the trade-count floor without forcing
# every strategy into the same shape. Phase 5 may revisit.
_MAX_CONCURRENT_POSITIONS = 5


class ExpectedTradesFilter:
    """§5.3.4 — reject configs whose estimated trade count is too low."""

    name = "expected_trades"
    cost_tier = 4

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        n_activations = len(ctx.feature_cache.activation_dates(directional.id))

        hold = _HOLD_DAYS_BY_BUCKET[config.dte_bucket]
        capacity = _MAX_CONCURRENT_POSITIONS * (ctx.registry.data_history_days / hold)
        estimated = min(n_activations, int(capacity))

        min_required = ctx.calibration.expected_trade_count.min_trades
        passed = estimated >= min_required
        if passed:
            denominator = math.log1p(10 * min_required)
            score = min(1.0, math.log1p(estimated) / denominator) if denominator > 0 else 0.0
        else:
            score = 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "n_activations": n_activations,
                    "estimated_trades": estimated,
                    "min_trades": min_required,
                    "dte_bucket": config.dte_bucket,
                    "hold_days": hold,
                }
            ),
        )


__all__ = ["ExpectedTradesFilter"]
