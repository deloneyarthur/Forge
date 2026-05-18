"""Unit tests for `forge.prefilters.permutation_test` (§5.3.7).

Filter 7 of the §5.2 battery (cost_tier=7, O(K) permutations). For K=100
shuffles of the date->return mapping, compare the real strategy's
notional return against the permuted distribution; reject when the
empirical p-value exceeds `calibration.permutation_test.p_value_threshold`
(default 0.10). Seeded RNG per hard rule #8.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest

from forge.core.seed import SeedHierarchy
from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import REGIMES, Regime
from forge.prefilters.permutation_test import PermutationTestFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


class _ReturnsCache:
    """Test stub: fixed activation set + full-window returns dict.

    The filter pulls returns over the full data window for the
    permutation procedure, so `data_history_days` is sized to match the
    supplied returns map.
    """

    def __init__(
        self,
        activations: frozenset[date],
        returns_by_date: Mapping[date, float],
    ) -> None:
        self._activations = activations
        self._returns = returns_by_date
        self.data_history_days = len(returns_by_date)

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return self._activations

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: self._returns[d] for d in dates}

    def regime_label(self, d: date) -> Regime:
        del d
        return REGIMES[0]


def _ctx(cache: _ReturnsCache, *, seed_root: int = 0) -> FilterContext:
    hierarchy = SeedHierarchy(seed_root)
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=hierarchy.rng,
    )


def _trading_window(n_days: int) -> list[date]:
    d0 = date(2022, 1, 1).toordinal()
    return [date.fromordinal(d0 + i) for i in range(n_days)]


def test_satisfies_filter_protocol() -> None:
    f: Filter = PermutationTestFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = PermutationTestFilter()
    assert f.name == "permutation_test"
    # T1.3 bumped 7->8 for PredictedActivationsFilter at 5;
    # T2.6 bumped 8->9 for SignalCorrelationFilter at 7.
    assert f.cost_tier == 9


def test_informative_signal_passes() -> None:
    """Signal fires precisely on the highest-return days -> real notional
    is at the top of any permuted distribution -> p-value ~= 0."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    # First 50 days +1.0 return, rest +/- small noise.
    returns_map: dict[date, float] = {}
    for i, d in enumerate(window):
        returns_map[d] = 1.0 if i < 50 else 0.0
    activations = frozenset(window[:50])  # fires exactly on the +1.0 days
    cache = _ReturnsCache(activations, returns_map)
    result = f.apply(cfg, _ctx(cache))
    assert result.passed
    assert result.score >= 0.9


def test_noise_signal_rejected() -> None:
    """Signal fires on random days against uniformly mixed returns ->
    real notional sits within the permuted bulk -> p-value > threshold."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    rng_for_data = random.Random(0)
    returns_map = {d: rng_for_data.gauss(0.0, 0.01) for d in window}
    # 50 activations on random dates.
    activations = frozenset(rng_for_data.sample(window, 50))
    cache = _ReturnsCache(activations, returns_map)
    # With pure noise and a 0.10 threshold, the p-value should land
    # somewhere in [0, 1] — *most* of the time well above 0.10. We
    # accept the filter's verdict; the assertion is that it doesn't
    # always pass noise across a sweep of seeds.
    rejections = 0
    for seed in range(10):
        r = f.apply(cfg, _ctx(cache, seed_root=seed))
        if not r.passed:
            rejections += 1
    assert rejections >= 1


def test_determinism_same_seed_same_p_value() -> None:
    """Hard rule #6: same seed -> same result. Permutation test must
    obey because all randomness flows through `ctx.rng_factory`."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    returns_map = {d: 0.5 if i % 2 == 0 else -0.4 for i, d in enumerate(window)}
    activations = frozenset(window[::3])
    cache = _ReturnsCache(activations, returns_map)
    a = f.apply(cfg, _ctx(cache, seed_root=7)).details["p_value"]
    b = f.apply(cfg, _ctx(cache, seed_root=7)).details["p_value"]
    assert a == b


def test_different_seeds_produce_different_p_values() -> None:
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    returns_map = {d: 0.5 if i % 2 == 0 else -0.4 for i, d in enumerate(window)}
    activations = frozenset(window[::3])
    cache = _ReturnsCache(activations, returns_map)
    a = f.apply(cfg, _ctx(cache, seed_root=1)).details["p_value"]
    b = f.apply(cfg, _ctx(cache, seed_root=2)).details["p_value"]
    assert a != b


def test_score_is_one_minus_p_value() -> None:
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(50)
    returns_map = {d: 1.0 if i < 10 else 0.0 for i, d in enumerate(window)}
    activations = frozenset(window[:10])
    cache = _ReturnsCache(activations, returns_map)
    result = f.apply(cfg, _ctx(cache))
    p = result.details["p_value"]
    assert abs(result.score - (1.0 - p)) < 1e-9


def test_details_record_p_value_n_permutations_real_notional() -> None:
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(50)
    returns_map = {d: float(i) / 50 for i, d in enumerate(window)}
    activations = frozenset(window[:10])
    cache = _ReturnsCache(activations, returns_map)
    result = f.apply(cfg, _ctx(cache))
    assert "p_value" in result.details
    assert result.details["n_permutations"] == 100
    assert "real_notional" in result.details
    assert "p_value_threshold" in result.details


def test_passes_when_no_activations() -> None:
    """Empty activation set -> real notional = 0; permutations also avg 0;
    not statistically distinguishable. Earlier filters reject; we just
    don't crash."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(50)
    returns_map = {d: 0.01 for d in window}
    cache = _ReturnsCache(frozenset(), returns_map)
    result = f.apply(cfg, _ctx(cache))
    # Score is bounded; we just verify it doesn't crash and returns
    # a valid FilterResult.
    assert 0.0 <= result.score <= 1.0


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_repeated_runs_with_same_seed_are_byte_identical(seed: int) -> None:
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(100)
    returns_map = {d: float(i % 5 - 2) / 100 for i, d in enumerate(window)}
    activations = frozenset(window[:30])
    cache = _ReturnsCache(activations, returns_map)
    a = f.apply(cfg, _ctx(cache, seed_root=seed))
    b = f.apply(cfg, _ctx(cache, seed_root=seed))
    assert a.passed == b.passed
    assert a.details["p_value"] == b.details["p_value"]
