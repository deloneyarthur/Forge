"""Unit tests for `forge.prefilters.expected_trades` (§5.3.4).

Filter 4 of the §5.2 battery (cost_tier=4, O(N) feature rows). Combines
the directional signal's activation count with the DTE bucket's typical
hold time to estimate trades over the cached window; rejects below
`calibration.expected_trade_count.min_trades` (default 50).
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest

from forge.prefilters.calibration import load_calibration
from forge.prefilters.expected_trades import (
    _HOLD_DAYS_BY_BUCKET,
    _MAX_CONCURRENT_POSITIONS,
    ExpectedTradesFilter,
)
from forge.prefilters.feature_cache import REGIMES
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


class _FixedActivationsCache:
    data_history_days = 1008

    def __init__(self, n: int) -> None:
        self._activations = frozenset(
            date.fromordinal(date(2022, 1, 1).toordinal() + i) for i in range(n)
        )

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return self._activations

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.0 for d in dates}

    def regime_label(self, d: date) -> str:
        del d
        return REGIMES[0]


def _ctx(n_activations: int) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=_FixedActivationsCache(n_activations),  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def test_satisfies_filter_protocol() -> None:
    f: Filter = ExpectedTradesFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = ExpectedTradesFilter()
    assert f.name == "expected_trades"
    assert f.cost_tier == 4


def test_passes_with_dense_short_bucket() -> None:
    """swing_short, 100 activations -> easily clears the 50-trade floor."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=100))
    assert result.passed


def test_rejects_when_activations_below_min_trades() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=40))
    assert not result.passed


def test_swing_long_high_density_capped_by_concurrency() -> None:
    """A swing_long config (hold ~75d) can hold at most ~MAX_SLOTS *
    (history/hold) concurrent positions; an extremely dense signal is
    capped by that ceiling even if activations are far above min_trades."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_long")
    # 1000 activations would naively imply 1000 trades; concurrency caps it.
    result = f.apply(cfg, _ctx(n_activations=1000))
    capacity = _MAX_CONCURRENT_POSITIONS * (1008 / _HOLD_DAYS_BY_BUCKET["swing_long"])
    assert result.details["estimated_trades"] <= int(capacity) + 1


def test_swing_short_high_density_not_capped() -> None:
    """swing_short hold ~15d allows many concurrent / sequential trades;
    typical activation counts are well under capacity."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=200))
    # min(200, 5 * 1008/15) = 200
    assert result.details["estimated_trades"] == 200


def test_score_monotone_in_estimated_trades() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    a = f.apply(cfg, _ctx(60)).score
    b = f.apply(cfg, _ctx(150)).score
    assert a < b


def test_score_clamped_to_unit_interval() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(10_000))
    assert 0.0 <= result.score <= 1.0


def test_subthreshold_score_is_zero() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(20))
    assert result.score == 0.0


def test_details_record_all_relevant_numbers() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_mid")
    result = f.apply(cfg, _ctx(80))
    assert result.details["n_activations"] == 80
    assert result.details["min_trades"] == 50
    assert result.details["dte_bucket"] == "swing_mid"
    assert "hold_days" in result.details
    assert "estimated_trades" in result.details


def test_pure() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config()
    ctx = _ctx(100)
    prior = ctx.prior_config_hashes
    f.apply(cfg, ctx)
    assert ctx.prior_config_hashes is prior


@pytest.mark.parametrize("bucket", ["swing_short", "swing_mid", "swing_long"])
def test_each_bucket_has_a_hold_days_entry(bucket: str) -> None:
    assert bucket in _HOLD_DAYS_BY_BUCKET
    assert _HOLD_DAYS_BY_BUCKET[bucket] > 0


def test_hold_days_are_increasing_across_buckets() -> None:
    """swing_short < swing_mid < swing_long; sanity-check the table."""
    s = _HOLD_DAYS_BY_BUCKET["swing_short"]
    m = _HOLD_DAYS_BY_BUCKET["swing_mid"]
    long_h = _HOLD_DAYS_BY_BUCKET["swing_long"]
    assert s < m < long_h
