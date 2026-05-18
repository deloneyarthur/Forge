"""Filter 7: permutation test. DESIGN.md §5.3.7.

For K=100 shuffles of the date->return mapping, compare the strategy's
real notional return against the permuted distribution. Reject when the
empirical p-value (fraction of permutations with notional >= real)
exceeds `calibration.permutation_test.p_value_threshold` (default 0.10).

A signal that does no better than chance ends up in the middle of the
permuted distribution (p-value ~ 0.5) and gets rejected. A genuine
signal lands above most permutations and survives.

All randomness flows through `ctx.rng_factory("permutation_test")`
(hard rule #8). Cost_tier=9, the most expensive filter in the §5.2
battery (post-T1.3 + T2.6 insertions) — runs last for short-circuit
efficiency.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


def _full_window(start: date, n_days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n_days)]


class PermutationTestFilter:
    """§5.3.7 — reject configs whose real notional sits within the
    permuted bulk."""

    name = "permutation_test"
    cost_tier = 9

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        activations = ctx.feature_cache.activation_dates(directional.id)
        n_activations = len(activations)

        n_permutations = ctx.calibration.permutation_test.n_permutations
        p_threshold = ctx.calibration.permutation_test.p_value_threshold

        # Real notional: sum of returns on the activation dates.
        if activations:
            real_returns = ctx.feature_cache.returns(activations)
            real_notional = sum(real_returns.values())
        else:
            real_notional = 0.0

        # Permuted distribution: random subsets of size n_activations
        # drawn from the full window's returns. The window is anchored at
        # `registry.data_start_date` (contracts v1.6.0) so the calendar
        # axis stays consistent with whatever cache implementation answers
        # `returns(dates)`.
        history = ctx.feature_cache.data_history_days
        window = _full_window(ctx.registry.data_start_date, history)
        all_returns_map = ctx.feature_cache.returns(window)
        all_returns = list(all_returns_map.values())

        rng = ctx.rng_factory("permutation_test")
        ge_real = 0
        if n_activations > 0 and len(all_returns) >= n_activations:
            for _ in range(n_permutations):
                sampled = rng.sample(all_returns, n_activations)
                if sum(sampled) >= real_notional:
                    ge_real += 1
            p_value = ge_real / n_permutations
        else:
            # Empty activations: nothing to compare. Treat as null result;
            # earlier filters would have rejected.
            p_value = 1.0

        passed = p_value <= p_threshold
        score = max(0.0, min(1.0, 1.0 - p_value))

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "p_value": p_value,
                    "n_permutations": n_permutations,
                    "real_notional": real_notional,
                    "n_activations": n_activations,
                    "p_value_threshold": p_threshold,
                }
            ),
        )


__all__ = ["PermutationTestFilter"]
