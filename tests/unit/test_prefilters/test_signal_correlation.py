"""Unit tests for `forge.prefilters.signal_correlation` (T2.6).

Filter 7 of the §5.2 battery (cost_tier=7). Rejects configs whose
pairwise signal-activation Jaccard overlap exceeds
`calibration.signal_correlation.max_jaccard_overlap` (default 0.85).
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest
from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
)

from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import REGIMES
from forge.prefilters.signal_correlation import SignalCorrelationFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"
_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


class _StubCache:
    """Test cache: per-signal-id activation date sets."""

    data_history_days = 1008

    def __init__(self, activations_by_id: dict[str, frozenset[date]]) -> None:
        self._data = activations_by_id

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        return self._data.get(signal_id, frozenset())

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.0 for d in dates}

    def regime_label(self, d: date) -> str:
        del d
        return REGIMES[0]


def _ctx(cache: object) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def _date_range(start: date, n: int) -> frozenset[date]:
    return frozenset(date.fromordinal(start.toordinal() + i) for i in range(n))


def _config_two_signals(
    sig_a_indicator: str = "rsi_2",
    sig_b_indicator: str = "iv_rank",
) -> StrategyConfig:
    """Minimal config with two signals — one directional, one regime_filter."""
    return StrategyConfig(
        name="test_cfg",
        hypothesis="mean_reversion",
        dte_bucket="swing_short",
        underlying="SPY",
        tier=1,
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=(sig_a_indicator,),
                params={"threshold": 30.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=(sig_b_indicator,),
                params={"threshold": 50.0},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )


# ---------------------------------------------------------------------------
# Protocol / metadata
# ---------------------------------------------------------------------------


def test_satisfies_filter_protocol() -> None:
    f: Filter = SignalCorrelationFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = SignalCorrelationFilter()
    assert f.name == "signal_correlation"
    assert f.cost_tier == 7


# ---------------------------------------------------------------------------
# Correlation mechanics
# ---------------------------------------------------------------------------


def test_passes_when_signals_uncorrelated() -> None:
    """Signals firing on disjoint date sets → Jaccard = 0 → passes."""
    cfg = _config_two_signals()
    cache = _StubCache(
        {
            "sig_directional": _date_range(date(2024, 1, 1), 30),
            "sig_regime": _date_range(date(2024, 6, 1), 30),  # disjoint
        }
    )
    f = SignalCorrelationFilter()
    result = f.apply(cfg, _ctx(cache))
    assert result.passed is True
    assert result.details["max_jaccard"] == 0.0
    assert result.score == 1.0


def test_rejects_when_signals_identical() -> None:
    """Two signals firing on identical dates → Jaccard = 1.0 → rejects."""
    cfg = _config_two_signals()
    dates = _date_range(date(2024, 1, 1), 30)
    cache = _StubCache({"sig_directional": dates, "sig_regime": dates})
    f = SignalCorrelationFilter()
    result = f.apply(cfg, _ctx(cache))
    assert result.passed is False
    assert result.details["max_jaccard"] == pytest.approx(1.0)


def test_rejects_at_just_above_threshold() -> None:
    """28 of 30 overlap → Jaccard = 28/32 = 0.875 > 0.85 → rejects."""
    cfg = _config_two_signals()
    a = _date_range(date(2024, 1, 1), 30)
    # Build b: 28 dates from a + 2 distinct
    base_ordinal = date(2024, 1, 1).toordinal()
    b_dates = [
        *sorted(a)[:28],
        date.fromordinal(base_ordinal + 50),
        date.fromordinal(base_ordinal + 51),
    ]
    b = frozenset(b_dates)
    cache = _StubCache({"sig_directional": a, "sig_regime": b})
    f = SignalCorrelationFilter()
    result = f.apply(cfg, _ctx(cache))
    expected_jaccard = 28 / (30 + 2)  # |A|=30, |B|=30, intersect=28, union=32
    assert result.details["max_jaccard"] == pytest.approx(expected_jaccard, abs=1e-6)
    assert result.passed is False  # 0.875 > 0.85


def test_passes_just_below_threshold() -> None:
    """20 of 30 overlap → Jaccard = 20/40 = 0.5 < 0.85 → passes."""
    cfg = _config_two_signals()
    a = _date_range(date(2024, 1, 1), 30)
    base_ordinal = date(2024, 1, 1).toordinal()
    b_dates = [
        *sorted(a)[:20],
        *[date.fromordinal(base_ordinal + 100 + i) for i in range(10)],
    ]
    b = frozenset(b_dates)
    cache = _StubCache({"sig_directional": a, "sig_regime": b})
    f = SignalCorrelationFilter()
    result = f.apply(cfg, _ctx(cache))
    assert result.passed is True
    assert result.details["max_jaccard"] == pytest.approx(20 / 40, abs=1e-6)


def test_single_signal_trivially_passes() -> None:
    """A config with only one signal has nothing to correlate; passes."""
    cfg = StrategyConfig(
        name="solo",
        hypothesis="mean_reversion",
        dte_bucket="swing_short",
        underlying="SPY",
        tier=1,
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
                params={"threshold": 30.0},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )
    cache = _StubCache({"sig_directional": _date_range(date(2024, 1, 1), 30)})
    f = SignalCorrelationFilter()
    result = f.apply(cfg, _ctx(cache))
    assert result.passed is True
    assert result.details["n_signals"] == 1


def test_empty_activation_sets_are_treated_as_uncorrelated() -> None:
    """Defensive: a signal with zero activations doesn't divide-by-zero."""
    cfg = _config_two_signals()
    cache = _StubCache(
        {
            "sig_directional": frozenset(),
            "sig_regime": _date_range(date(2024, 1, 1), 30),
        }
    )
    f = SignalCorrelationFilter()
    result = f.apply(cfg, _ctx(cache))
    assert result.passed is True
    assert result.details["max_jaccard"] == 0.0
