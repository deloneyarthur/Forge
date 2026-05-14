"""Filter 6: regime exposure. DESIGN.md §5.3.6.

Counts the directional signal's activations by macro regime; rejects
configs whose largest single-regime share exceeds
`calibration.regime_exposure.max_single_regime_concentration` (default
0.80). The strategy is too narrowly specialized to one market.

Score is normalized Shannon entropy across the six §5.3.6 regimes:
uniform -> 1.0, all-in-one-regime -> 0.0. Empty activation set passes
with score 0.0 (earlier filters would reject for density anyway).

O(N) activations; cost_tier=6 in the §5.2 battery.
"""

from __future__ import annotations

import math
from collections import Counter
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.feature_cache import REGIMES
from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


# log(6) — max possible entropy across the canonical six regimes. Used to
# normalize the score to [0, 1] regardless of how many regimes the
# activations actually span.
_LOG_K = math.log(len(REGIMES))


class RegimeExposureFilter:
    """§5.3.6 — reject configs concentrated in a single macro regime."""

    name = "regime_exposure"
    cost_tier = 6

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        activations = ctx.feature_cache.activation_dates(directional.id)

        if not activations:
            return FilterResult(
                passed=True,
                score=0.0,
                details=MappingProxyType(
                    {
                        "regime_counts": {},
                        "max_regime": None,
                        "max_share": 0.0,
                        "n_activations": 0,
                    }
                ),
            )

        counts: Counter[str] = Counter(ctx.feature_cache.regime_label(d) for d in activations)
        n = sum(counts.values())
        max_regime, max_count = counts.most_common(1)[0]
        max_share = max_count / n

        threshold = ctx.calibration.regime_exposure.max_single_regime_concentration
        passed = max_share <= threshold

        if n > 0 and _LOG_K > 0:
            entropy = -sum((c / n) * math.log(c / n) for c in counts.values())
            score = entropy / _LOG_K
        else:
            score = 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "regime_counts": dict(counts),
                    "max_regime": max_regime,
                    "max_share": max_share,
                    "n_activations": n,
                    "max_single_regime_concentration_threshold": threshold,
                }
            ),
        )


__all__ = ["RegimeExposureFilter"]
