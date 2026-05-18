"""Unit tests for `forge.prefilters.regime_exposure` (§5.3.6).

Filter 6 of the §5.2 battery (cost_tier=6, O(N) activations). Counts the
directional signal's activations by macro regime; rejects when any one
regime holds more than
`calibration.regime_exposure.max_single_regime_concentration` (default
0.80) — the strategy is too narrowly specialized to one market.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest

from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import REGIMES, Regime
from forge.prefilters.regime_exposure import RegimeExposureFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


class _LabeledCache:
    """Test stub: returns the candidate activations and a fixed per-date
    regime label mapping."""

    data_history_days = 1008

    def __init__(self, activations: frozenset[date], labels: dict[date, Regime]) -> None:
        self._activations = activations
        self._labels = labels

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return self._activations

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.0 for d in dates}

    def regime_label(self, d: date) -> Regime:
        return self._labels[d]


def _ctx(cache: _LabeledCache) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def _balanced_labels(n_per_regime: int = 20) -> tuple[frozenset[date], dict[date, Regime]]:
    """n_per_regime activations in each of the six regimes."""
    activations: list[date] = []
    labels: dict[date, Regime] = {}
    d0 = date(2022, 1, 1).toordinal()
    cursor = 0
    for regime in REGIMES:
        for _ in range(n_per_regime):
            d = date.fromordinal(d0 + cursor)
            activations.append(d)
            labels[d] = regime
            cursor += 1
    return frozenset(activations), labels


def _skewed_labels(
    dominant: Regime, dominant_count: int, other_count: int
) -> tuple[frozenset[date], dict[date, Regime]]:
    """Mostly-`dominant` distribution with a tail of other regimes."""
    activations: list[date] = []
    labels: dict[date, Regime] = {}
    d0 = date(2022, 1, 1).toordinal()
    cursor = 0
    for _ in range(dominant_count):
        d = date.fromordinal(d0 + cursor)
        activations.append(d)
        labels[d] = dominant
        cursor += 1
    others = [r for r in REGIMES if r != dominant]
    for r in others:
        for _ in range(other_count):
            d = date.fromordinal(d0 + cursor)
            activations.append(d)
            labels[d] = r
            cursor += 1
    return frozenset(activations), labels


def test_satisfies_filter_protocol() -> None:
    f: Filter = RegimeExposureFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = RegimeExposureFilter()
    assert f.name == "regime_exposure"
    # T1.3 bumped 6->7 for PredictedActivationsFilter at 5; T2.6 bumped
    # 7->8 for SignalCorrelationFilter at 7.
    assert f.cost_tier == 8


def test_passes_with_balanced_distribution() -> None:
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    activations, labels = _balanced_labels(20)
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    assert result.passed


def test_rejects_when_one_regime_dominates() -> None:
    """90% in 'bull' should fail the 0.80 threshold."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    activations, labels = _skewed_labels("bull", dominant_count=90, other_count=2)
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    assert not result.passed
    assert result.details["max_regime"] == "bull"


def test_passes_at_exactly_eighty_percent() -> None:
    """80% in one regime is the boundary; <= passes (inclusive)."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    # 80 in 'bull', 4 in each of the other 5 regimes -> 100 total, 80% bull.
    activations, labels = _skewed_labels("bull", dominant_count=80, other_count=4)
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    assert result.passed


def test_score_higher_for_balanced_distribution() -> None:
    """Entropy-based score: uniform across regimes -> high, concentrated -> low."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    balanced = _LabeledCache(*_balanced_labels(20))
    skewed = _LabeledCache(*_skewed_labels("bull", 60, 8))
    s_balanced = f.apply(cfg, _ctx(balanced)).score
    s_skewed = f.apply(cfg, _ctx(skewed)).score
    assert s_balanced > s_skewed


def test_score_uniform_six_regimes_is_one() -> None:
    """Perfectly uniform across all six -> entropy/log(6) = 1.0."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    activations, labels = _balanced_labels(50)
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    assert math.isclose(result.score, 1.0, abs_tol=1e-9)


def test_score_single_regime_is_zero() -> None:
    """All activations in one regime -> entropy 0 -> score 0."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    d0 = date(2022, 1, 1).toordinal()
    activations = frozenset(date.fromordinal(d0 + i) for i in range(50))
    labels: dict[date, Regime] = {d: "bull" for d in activations}
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    assert not result.passed
    assert result.score == 0.0


def test_passes_with_no_activations() -> None:
    """An empty activation set has no concentration risk. Earlier filters
    would reject for density; here we treat as score=0 + pass=True."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(_LabeledCache(frozenset(), {})))
    assert result.passed
    assert result.score == 0.0


def test_details_record_per_regime_counts_and_max() -> None:
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    activations, labels = _skewed_labels("bear", 30, 5)
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    counts = result.details["regime_counts"]
    assert counts["bear"] == 30
    assert result.details["max_regime"] == "bear"
    assert 0.0 <= result.details["max_share"] <= 1.0


def test_pure() -> None:
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    activations, labels = _balanced_labels(10)
    ctx = _ctx(_LabeledCache(activations, labels))
    prior = ctx.prior_config_hashes
    f.apply(cfg, ctx)
    assert ctx.prior_config_hashes is prior


@pytest.mark.parametrize("dominant_count", [50, 75, 80, 81, 90])
def test_threshold_is_inclusive_at_calibration_value(dominant_count: int) -> None:
    """At calibration default 0.80, max_share <= 0.80 passes, > 0.80 fails."""
    f = RegimeExposureFilter()
    cfg = minimal_strategy_config()
    # other_count chosen so that total is dominant_count / 0.80 (when 80%)
    # but the key property: max_share = dominant_count / total. We rig:
    other_total = 100 - dominant_count  # 5 other regimes share this
    other_per = max(1, other_total // 5)
    activations, labels = _skewed_labels("bull", dominant_count, other_per)
    result = f.apply(cfg, _ctx(_LabeledCache(activations, labels)))
    if result.details["max_share"] <= 0.80:
        assert result.passed
    else:
        assert not result.passed
