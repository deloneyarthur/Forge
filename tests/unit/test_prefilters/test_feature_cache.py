"""Unit tests for ``forge.prefilters.feature_cache``.

Covers:
- `FeatureCache` Protocol shape is satisfied by `SyntheticFeatureCache`.
- Determinism: same `root_seed` -> identical activations / returns /
  regime labels (CLAUDE.md hard rule #6 / hard rule #8).
- Constructor exposes `data_history_days`; window respects `start_date`.
- `activation_dates(signal_id)` returns dates strictly inside the window.
- Two different signal_ids produce different sets.
- `returns(dates)` returns one finite float per requested date.
- `regime_label(d)` returns one of the six §5.3.6 regimes.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from forge.prefilters.feature_cache import (
    REGIMES,
    FeatureCache,
    SyntheticFeatureCache,
)


def test_synthetic_satisfies_feature_cache_protocol() -> None:
    cache = SyntheticFeatureCache(root_seed=1)
    assert isinstance(cache, FeatureCache)


def test_data_history_days_reflects_constructor_arg() -> None:
    cache = SyntheticFeatureCache(root_seed=1, data_history_days=512)
    assert cache.data_history_days == 512


def test_default_data_history_days_is_1008() -> None:
    """1008 = 4 x 252 trading days, matching §5.3.3/4 framing."""
    cache = SyntheticFeatureCache(root_seed=1)
    assert cache.data_history_days == 1008


def test_activation_dates_are_inside_window() -> None:
    start = date(2022, 1, 1)
    cache = SyntheticFeatureCache(root_seed=1, data_history_days=200, start_date=start)
    dates = cache.activation_dates("rsi_2")
    end = start + timedelta(days=199)
    for d in dates:
        assert start <= d <= end


def test_activation_dates_are_deterministic_for_same_seed_and_signal() -> None:
    """§13.1 / hard rule #6: same (seed, signal) -> same activations."""
    a = SyntheticFeatureCache(root_seed=42).activation_dates("rsi_2")
    b = SyntheticFeatureCache(root_seed=42).activation_dates("rsi_2")
    assert a == b


def test_activation_dates_differ_across_signal_ids() -> None:
    """Different signals must produce different activation patterns —
    otherwise novelty / signal-density filters can't distinguish them."""
    cache = SyntheticFeatureCache(root_seed=42)
    a = cache.activation_dates("rsi_2")
    b = cache.activation_dates("ema_50")
    assert a != b


def test_activation_dates_differ_across_seeds() -> None:
    a = SyntheticFeatureCache(root_seed=1).activation_dates("rsi_2")
    b = SyntheticFeatureCache(root_seed=2).activation_dates("rsi_2")
    assert a != b


def test_activation_dates_non_trivial_count() -> None:
    """The synthetic cache should produce enough activations to exercise
    the signal_density filter (>= 30 minimum) for typical signals."""
    cache = SyntheticFeatureCache(root_seed=7)
    dates = cache.activation_dates("rsi_2")
    assert len(dates) > 30


def test_returns_one_finite_float_per_date() -> None:
    cache = SyntheticFeatureCache(root_seed=1)
    dates = [date(2022, 1, 1), date(2022, 1, 2), date(2022, 1, 3)]
    rets = cache.returns(dates)
    assert set(rets.keys()) == set(dates)
    for r in rets.values():
        assert math.isfinite(r)


def test_returns_are_deterministic_for_same_seed_and_dates() -> None:
    cache_a = SyntheticFeatureCache(root_seed=99)
    cache_b = SyntheticFeatureCache(root_seed=99)
    dates = [date(2022, 1, 1), date(2022, 6, 30)]
    assert cache_a.returns(dates) == cache_b.returns(dates)


def test_returns_differ_across_seeds() -> None:
    dates = [date(2022, 1, 1)]
    a = SyntheticFeatureCache(root_seed=1).returns(dates)
    b = SyntheticFeatureCache(root_seed=2).returns(dates)
    assert a != b


def test_regime_label_returns_known_regime() -> None:
    cache = SyntheticFeatureCache(root_seed=1)
    label = cache.regime_label(date(2022, 1, 1))
    assert label in REGIMES


def test_regime_label_is_deterministic_per_date() -> None:
    cache_a = SyntheticFeatureCache(root_seed=5)
    cache_b = SyntheticFeatureCache(root_seed=5)
    d = date(2023, 7, 4)
    assert cache_a.regime_label(d) == cache_b.regime_label(d)


def test_regime_distribution_is_not_degenerate() -> None:
    """Synthetic regime labels should span > 1 regime across the window,
    otherwise the regime_exposure filter (§5.3.6) would never fire."""
    cache = SyntheticFeatureCache(root_seed=1, data_history_days=500)
    labels = {cache.regime_label(date(2022, 1, 1) + timedelta(days=i)) for i in range(500)}
    assert len(labels) >= 2


def test_six_canonical_regimes_present_in_module() -> None:
    """REGIMES tuple matches §5.3.6's six labels exactly."""
    assert set(REGIMES) == {"bull", "bear", "low_vol", "high_vol", "trending", "ranging"}


def test_rejects_zero_history() -> None:
    with pytest.raises(ValueError, match="data_history_days"):
        SyntheticFeatureCache(root_seed=1, data_history_days=0)


def test_rejects_negative_history() -> None:
    with pytest.raises(ValueError, match="data_history_days"):
        SyntheticFeatureCache(root_seed=1, data_history_days=-1)
