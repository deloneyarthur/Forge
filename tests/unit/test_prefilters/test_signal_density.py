"""Unit tests for `forge.prefilters.signal_density` (§5.3.3).

Filter 3 of the §5.2 battery (cost_tier=3, O(N) feature rows). Counts the
directional signal's historical activations and rejects below the
`calibration.signal_density.min_activations` threshold (default 30).
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest

from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import REGIMES, SyntheticFeatureCache
from forge.prefilters.signal_density import SignalDensityFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


class _FixedActivationsCache:
    """Test stub: returns the same frozenset for every signal_id."""

    data_history_days = 1008

    def __init__(self, activations: frozenset[date]) -> None:
        self._activations = activations

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return self._activations

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.0 for d in dates}

    def regime_label(self, d: date) -> str:
        del d
        return REGIMES[0]


def _ctx(cache: object = None) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache or SyntheticFeatureCache(root_seed=0),  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def _activations_simple(n: int) -> frozenset[date]:
    return frozenset(date.fromordinal(date(2022, 1, 1).toordinal() + i) for i in range(n))


def test_satisfies_filter_protocol() -> None:
    f: Filter = SignalDensityFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = SignalDensityFilter()
    assert f.name == "signal_density"
    assert f.cost_tier == 3


def test_passes_when_activations_at_threshold() -> None:
    """Exactly `min_activations` (30) passes — threshold is inclusive."""
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(30))
    result = f.apply(cfg, _ctx(cache))
    assert result.passed


def test_rejects_below_threshold() -> None:
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(29))
    result = f.apply(cfg, _ctx(cache))
    assert not result.passed


def test_passes_well_above_threshold() -> None:
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(500))
    result = f.apply(cfg, _ctx(cache))
    assert result.passed
    assert result.score > 0.5


def test_score_monotone_in_activation_count() -> None:
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    a = f.apply(cfg, _ctx(_FixedActivationsCache(_activations_simple(40)))).score
    b = f.apply(cfg, _ctx(_FixedActivationsCache(_activations_simple(100)))).score
    c = f.apply(cfg, _ctx(_FixedActivationsCache(_activations_simple(500)))).score
    assert a < b < c


def test_score_is_zero_when_no_activations() -> None:
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(_FixedActivationsCache(frozenset())))
    assert not result.passed
    assert result.score == 0.0


def test_score_is_in_unit_interval() -> None:
    """The score must stay clamped to [0, 1] for very large activation
    counts (e.g., a signal that fires every day)."""
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(10_000))
    result = f.apply(cfg, _ctx(cache))
    assert 0.0 <= result.score <= 1.0


def test_details_record_counts() -> None:
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(25))
    result = f.apply(cfg, _ctx(cache))
    assert result.details["n_activations"] == 25
    assert result.details["min_activations"] == 30


def test_uses_directional_signal_not_regime_filter() -> None:
    """The §5.3.3 description names the directional signal specifically;
    the regime_filter has different semantics and shouldn't be measured."""

    class _RoleAwareCache:
        data_history_days = 1008

        def __init__(self) -> None:
            self.calls: list[str] = []

        def activation_dates(self, signal_id: str) -> frozenset[date]:
            self.calls.append(signal_id)
            return _activations_simple(100)

        def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
            return {d: 0.0 for d in dates}

        def regime_label(self, d: date) -> str:
            del d
            return REGIMES[0]

    cache = _RoleAwareCache()
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    f.apply(cfg, _ctx(cache))  # type: ignore[arg-type]
    # Should look up exactly the directional signal id, not the regime one.
    assert "sig_directional" in cache.calls
    assert "sig_regime" not in cache.calls


def test_pure_does_not_mutate_context() -> None:
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    ctx = _ctx()
    prior = ctx.prior_config_hashes
    f.apply(cfg, ctx)
    assert ctx.prior_config_hashes is prior


@pytest.mark.parametrize("n", [0, 1, 5, 29])
def test_score_is_zero_for_subthreshold_counts(n: int) -> None:
    """Below threshold -> passed=False AND score=0; the ranker uses
    these as zeroes regardless of how close they came."""
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(n))
    result = f.apply(cfg, _ctx(cache))
    assert not result.passed
    assert result.score == 0.0


def test_score_formula_is_log_normalized() -> None:
    """The score uses a log-normalized formula (more graceful than linear
    saturation): log1p(n) / log1p(10 * min_activations), clamped."""
    f = SignalDensityFilter()
    cfg = minimal_strategy_config()
    cache = _FixedActivationsCache(_activations_simple(60))
    result = f.apply(cfg, _ctx(cache))
    expected = math.log1p(60) / math.log1p(10 * 30)
    assert math.isclose(result.score, expected, rel_tol=1e-9)
