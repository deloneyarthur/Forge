"""Unit tests for `forge.prefilters.resource_feasibility` (§5.3.2).

Filter 2 of the §5.2 battery (O(1), cost_tier=2). Rejects configs whose
maximum indicator lookback exceeds `registry.data_history_days` — those
configs would have NaN for most of any backtest.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from crucible_contracts import (
    IndicatorMetadata,
    RegistrySnapshot,
    SignalSpec,
)

from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import SyntheticFeatureCache
from forge.prefilters.resource_feasibility import ResourceFeasibilityFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


def _ctx(registry: RegistrySnapshot) -> FilterContext:
    return FilterContext(
        registry=registry,
        feature_cache=SyntheticFeatureCache(root_seed=0),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def _short_history_registry(*, history_days: int, lookback: int) -> RegistrySnapshot:
    """Build a registry where the one indicator (matching minimal_strategy_config)
    has the given lookback and the snapshot has the given history depth."""
    return RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="rsi_2",
                version=1,
                family="mean_reversion",
                lookback=lookback,
                params_schema={},
            ),
            IndicatorMetadata(
                id="iv_rank",
                version=1,
                family="iv_structure",
                lookback=1,
                params_schema={},
            ),
        ),
        signal_types=("threshold",),
        exit_ids=("expiry_exit", "theta_cliff_exit", "earnings_exit", "liquidity_exit"),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=history_days,
        data_start_date=date(2022, 1, 1),
    )


def test_satisfies_filter_protocol() -> None:
    f: Filter = ResourceFeasibilityFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = ResourceFeasibilityFilter()
    assert f.name == "resource_feasibility"
    assert f.cost_tier == 2


def test_passes_with_minimal_fixture() -> None:
    """Default fixture (lookback=30 via iv_rank) vs 1008 days passes
    comfortably."""
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(minimal_registry_snapshot()))
    assert result.passed
    # Score should be high — minimal config uses very little of the window.
    assert result.score > 0.9


def test_rejects_when_max_lookback_exceeds_history() -> None:
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    # rsi_2 lookback set to 200, history only 100 days.
    registry = _short_history_registry(history_days=100, lookback=200)
    result = f.apply(cfg, _ctx(registry))
    assert not result.passed
    assert result.score == 0.0


def test_passes_when_max_lookback_equals_history() -> None:
    """Edge: ``<=`` not ``<``. A config that uses exactly the available
    history is still feasible (one observation per indicator)."""
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    registry = _short_history_registry(history_days=100, lookback=100)
    result = f.apply(cfg, _ctx(registry))
    assert result.passed


def test_details_record_max_lookback_and_history_days() -> None:
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    registry = _short_history_registry(history_days=100, lookback=150)
    result = f.apply(cfg, _ctx(registry))
    assert result.details["max_lookback"] == 150
    assert result.details["data_history_days"] == 100


def test_score_decreases_as_max_lookback_approaches_history() -> None:
    """Higher lookback / history ratio -> lower score (less headroom)."""
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    high_room = f.apply(cfg, _ctx(_short_history_registry(history_days=1000, lookback=10)))
    low_room = f.apply(cfg, _ctx(_short_history_registry(history_days=1000, lookback=900)))
    assert high_room.score > low_room.score


def test_score_is_zero_on_rejection() -> None:
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(_short_history_registry(history_days=100, lookback=500)))
    assert result.score == 0.0


def test_multi_indicator_signal_uses_max_lookback() -> None:
    """D010: when a signal references multiple indicators, take the max.
    Here the directional signal references both rsi_2 (lb=2) and a fake
    long indicator (lb=300); the strategy should be measured against
    300, not 2."""
    f = ResourceFeasibilityFilter()
    registry = RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="rsi_2", version=1, family="mean_reversion", lookback=2, params_schema={}
            ),
            IndicatorMetadata(
                id="long_thing", version=1, family="trend", lookback=300, params_schema={}
            ),
            IndicatorMetadata(
                id="iv_rank", version=1, family="iv_structure", lookback=1, params_schema={}
            ),
        ),
        signal_types=("threshold",),
        exit_ids=("expiry_exit", "theta_cliff_exit", "earnings_exit", "liquidity_exit"),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=200,
        data_start_date=date(2022, 1, 1),
    )
    cfg = minimal_strategy_config(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2", "long_thing"),
                params={"threshold": 30.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = f.apply(cfg, _ctx(registry))
    # max_lookback = 300, history = 200 -> reject
    assert not result.passed
    assert result.details["max_lookback"] == 300


@pytest.mark.parametrize("history", [10, 100, 1008, 5000])
def test_passes_with_minimal_fixture_at_various_history_depths(history: int) -> None:
    """As long as history >= max lookback (=30 for iv_rank in fixture),
    the filter passes."""
    f = ResourceFeasibilityFilter()
    cfg = minimal_strategy_config()
    registry = _short_history_registry(history_days=history, lookback=2)
    if history < 30:  # iv_rank lookback is 30 in the minimal fixture variant
        # The _short_history_registry sets iv_rank lookback=1, so max is the
        # rsi_2 lookback we pass. Always passes here.
        pass
    result = f.apply(cfg, _ctx(registry))
    assert result.passed
