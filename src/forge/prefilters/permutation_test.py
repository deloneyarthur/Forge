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
from bisect import bisect_right
from datetime import date, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

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


def _forward_cumulative_pool(
    ordered_days: list[date],
    returns_map: Mapping[date, float],
    horizon: int,
) -> dict[date, float]:
    """P1-1: cumulative forward return over the next ``horizon`` TRADING days for every
    trading day that has ``horizon`` successors — the null pool for ``cumulative_trading``.

    ``ordered_days`` ARE the trading days (the returns-index keys, sorted), so walking them
    is a trading-day shift by construction — no CALENDAR arithmetic, no weekend loss. The
    map value at day ``ordered_days[i]`` is ``sum(returns[i+1 .. i+horizon])`` (T+1..T+k).
    (The P1-2a ``absolute`` |move| variant lived here until D301 — dropped at D235.)"""
    out: dict[date, float] = {}
    n = len(ordered_days)
    for i in range(n - horizon):
        cumulative = sum(returns_map[ordered_days[j]] for j in range(i + 1, i + 1 + horizon))
        out[ordered_days[i]] = cumulative
    return out


def _real_forward_cumulative(
    activations: Iterable[date],
    ordered_days: list[date],
    returns_map: Mapping[date, float],
    horizon: int,
) -> tuple[float, int]:
    """Real notional under ``cumulative_trading``: for each activation, the cumulative return
    over the first ``horizon`` TRADING days STRICTLY after it (via the returns index, so a
    Friday activation reads Mon.. not the dropped weekend). Activations without ``horizon``
    trading days left in the window are dropped, mirroring the legacy out-of-window drop; the
    returned count is the effective sample size the null must match."""
    total = 0.0
    effective_n = 0
    n = len(ordered_days)
    for d in activations:
        pos = bisect_right(ordered_days, d)  # first trading day strictly after d
        if pos + horizon <= n:
            cumulative = sum(returns_map[ordered_days[j]] for j in range(pos, pos + horizon))
            total += cumulative
            effective_n += 1
    return total, effective_n


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
        mode = ctx.calibration.permutation_test.forward_return_mode

        # Permuted-null pool: returns over the full data window. Anchored at
        # `registry.data_start_date` (contracts v1.6.0) so the calendar axis stays
        # consistent with whatever cache implementation answers `returns(dates)`.
        # Computed up front (no RNG here) so both modes share the trading-day index;
        # RNG is only drawn in the permutation loop below → the legacy branch stays
        # byte-identical to pre-P1-1.
        history = ctx.feature_cache.data_history_days
        window = _full_window(ctx.registry.data_start_date, history)
        all_returns_map = ctx.feature_cache.returns(window)

        if mode == "cumulative_trading" and horizon > 0:
            # P1-1: cumulative return over the next `horizon` TRADING days (T+1..T+k), null
            # built on the SAME statistic (else a k-day real sum vs 1-day null sums is a
            # scale mismatch). ordered_days == the trading-day index (returns-map keys).
            ordered_days = sorted(all_returns_map)
            pool = list(_forward_cumulative_pool(ordered_days, all_returns_map, horizon).values())
            real_notional, effective_n = _real_forward_cumulative(
                activations, ordered_days, all_returns_map, horizon
            )
        else:
            # Legacy single_day: the return on the single CALENDAR day at T+horizon (buggy —
            # kept as the default so an un-flipped tree is byte-identical). Dates past the
            # window end are dropped by `returns()`; `effective_n` reflects the in-window count.
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
            pool = list(all_returns_map.values())

        rng = ctx.rng_factory("permutation_test")
        ge_real = 0
        if effective_n > 0 and len(pool) >= effective_n:
            for _ in range(n_permutations):
                sampled = rng.sample(pool, effective_n)
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
                    "forward_return_mode": mode,
                    "p_value_threshold": p_threshold,
                }
            ),
        )


__all__ = ["PermutationTestFilter"]
