"""Filter 7: permutation test. DESIGN.md §5.3.7.

For K=100 shuffles of the date->return mapping, compare the strategy's
real notional return against the permuted distribution. Reject when the
empirical p-value (fraction of permutations with notional >= real)
exceeds `calibration.permutation_test.p_value_threshold` (default 0.10).

A signal that does no better than chance ends up in the middle of the
permuted distribution (p-value ~ 0.5) and gets rejected. A genuine
signal lands above most permutations and survives.

D075 (2026-05-19): the comparison is now grounded on T+k forward returns
rather than T+0 same-day returns. Trend / leading-indicator signals
predict the *future* drift after activation, not the activation-day
return — the legacy T+0 test systematically wiped trend_continuation
(0 of 9,308 historical configs ever passed). The `forward_horizon_days`
calibration field controls k; 0 preserves legacy behavior.

All randomness flows through `ctx.rng_factory("permutation_test")`
(hard rule #8). Cost_tier=9, the most expensive filter in the §5.2
battery (post-T1.3 + T2.6 insertions) — runs last for short-circuit
efficiency.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


# `data_history_days` counts TRADING sessions (~252/yr); the permutation null
# pool must span the equivalent CALENDAR range. 366/252 over-covers (holidays +
# leap years) and `feature_cache.returns()` silently drops the surplus dateless
# days — so over-coverage is free, whereas under-coverage (the pre-Q21
# calendar-as-trading-days bug) truncated the pool by ~40% on the 2018 window
# (2118 sessions reached only 2023-10 instead of ~2026), biasing every p-value.
_CALENDAR_DAYS_PER_TRADING_DAY = 366 / 252


def _full_window(start: date, n_trading_days: int) -> list[date]:
    """Calendar dates spanning `n_trading_days` trading sessions from `start`."""
    n_calendar = math.ceil(n_trading_days * _CALENDAR_DAYS_PER_TRADING_DAY)
    return [start + timedelta(days=i) for i in range(n_calendar)]


def _significance_score(p_value: float, p_threshold: float) -> float:
    """Ranker (§6.2) sub-score: map the *passing* p-value range [0, threshold]
    onto the full [0, 1] so statistical significance has real resolution among
    survivors.

    D095: the legacy `1 - p_value` squashed every passer into
    `[1 - threshold, 1]` (e.g. [0.90, 1.0] at threshold 0.10), so the §6.2
    permutation weight (0.15) carried almost no variance among submitted
    candidates — the ranker-flatness finding. Here a highly-significant passer
    (p≈0) scores ~1.0 and a barely-significant one (p≈threshold) scores ~0.0,
    while pass/fail (`p_value <= p_threshold`) is unchanged. Failing candidates
    clamp to 0.0 (they never reach the ranker per the `Ranker.score`
    precondition). A non-positive threshold (degenerate) yields 0.0.
    """
    if p_threshold <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - p_value / p_threshold))


class PermutationTestFilter:
    """§5.3.7 — reject configs whose real notional sits within the
    permuted bulk."""

    name = "permutation_test"
    cost_tier = 9

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        activations = ctx.feature_cache.activation_dates(directional.id)

        n_permutations = ctx.calibration.permutation_test.n_permutations
        p_threshold = ctx.calibration.permutation_test.p_value_threshold
        horizon = ctx.calibration.permutation_test.forward_horizon_days

        # D075: shift activation dates by `horizon` days before reading
        # returns. Dates that land past the data window's end are silently
        # dropped by `feature_cache.returns()`; `effective_n` reflects the
        # in-window count so the permutation sample size matches.
        if horizon == 0:
            target_dates: list[date] = list(activations)
        else:
            target_dates = [d + timedelta(days=horizon) for d in activations]

        if target_dates:
            real_returns = ctx.feature_cache.returns(target_dates)
            real_notional = sum(real_returns.values())
            effective_n = len(real_returns)
        else:
            real_notional = 0.0
            effective_n = 0

        # Permuted distribution: random subsets of size `effective_n`
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
        if effective_n > 0 and len(all_returns) >= effective_n:
            for _ in range(n_permutations):
                sampled = rng.sample(all_returns, effective_n)
                if sum(sampled) >= real_notional:
                    ge_real += 1
            p_value = ge_real / n_permutations
        else:
            # Empty (or all-out-of-window) activations: nothing to compare.
            # Earlier filters would have rejected the legitimately empty case.
            p_value = 1.0

        passed = p_value <= p_threshold
        score = _significance_score(p_value, p_threshold)

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "p_value": p_value,
                    "n_permutations": n_permutations,
                    "real_notional": real_notional,
                    "n_activations": len(activations),
                    "effective_n": effective_n,
                    "forward_horizon_days": horizon,
                    "p_value_threshold": p_threshold,
                }
            ),
        )


__all__ = ["PermutationTestFilter"]
