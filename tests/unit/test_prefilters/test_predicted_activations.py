"""Unit tests for `forge.prefilters.predicted_activations` (T1.3).

Filter 5 of the §5.2 battery (cost_tier=5). Intersects the directional
signal's activations with each regime_filter gate's activations and
rejects below `calibration.predicted_activations.min_entries` (default 10).
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

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
from forge.prefilters.predicted_activations import PredictedActivationsFilter
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
    """Test cache: returns configurable per-signal_id activation sets."""

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


def _config_with_regime() -> StrategyConfig:
    """Minimal grammar-valid config with one directional + one regime gate.

    Both signals share `id` patterns matching the production sampler so
    the filter's signal-id lookups hit the cache correctly.
    """
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
                indicators=("rsi_2",),
                params={"threshold": 30.0, "op": "<"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0, "op": "<"},
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
    f: Filter = PredictedActivationsFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = PredictedActivationsFilter()
    assert f.name == "predicted_activations"
    assert f.cost_tier == 5


# ---------------------------------------------------------------------------
# Intersection mechanics
# ---------------------------------------------------------------------------


def test_passes_when_intersection_above_threshold() -> None:
    """When directional AND regime co-fire on 20+ dates, passes (floor=10)."""
    dates = _date_range(date(2024, 1, 1), 20)
    cache = _StubCache({
        "sig_directional": dates,
        "sig_regime": dates,  # full overlap
    })
    f = PredictedActivationsFilter()
    result = f.apply(_config_with_regime(), _ctx(cache))
    assert result.passed is True
    assert result.details["predicted_n_entries"] == 20
    assert result.score > 0.0


def test_rejects_when_intersection_below_threshold() -> None:
    """5 co-fires < 10 floor → reject."""
    dates = _date_range(date(2024, 1, 1), 5)
    cache = _StubCache({
        "sig_directional": dates,
        "sig_regime": dates,
    })
    f = PredictedActivationsFilter()
    result = f.apply(_config_with_regime(), _ctx(cache))
    assert result.passed is False
    assert result.details["predicted_n_entries"] == 5
    assert result.score == 0.0


def test_rejects_when_intersection_empty_silent_failure_case() -> None:
    """T1.3's headline case: directional fires often, regime never co-fires.

    Concretely: directional fires 1000 dates; regime fires 0 dates (e.g.,
    days_to_earnings on SPY returns sentinel 999 — never <=3). The
    intersection is empty and the filter rejects pre-submission.
    """
    directional_dates = _date_range(date(2020, 1, 1), 1000)
    regime_dates: frozenset[date] = frozenset()  # silent-failure case
    cache = _StubCache({
        "sig_directional": directional_dates,
        "sig_regime": regime_dates,
    })
    f = PredictedActivationsFilter()
    result = f.apply(_config_with_regime(), _ctx(cache))
    assert result.passed is False
    assert result.details["predicted_n_entries"] == 0
    assert result.details["n_directional_firings"] == 1000


def test_intersection_disjoint_dates_yields_zero() -> None:
    """Directional fires on month 1; regime fires on month 2. No overlap."""
    directional = _date_range(date(2024, 1, 1), 30)
    regime = _date_range(date(2024, 2, 15), 30)  # entirely disjoint
    cache = _StubCache({
        "sig_directional": directional,
        "sig_regime": regime,
    })
    f = PredictedActivationsFilter()
    result = f.apply(_config_with_regime(), _ctx(cache))
    assert result.passed is False
    assert result.details["predicted_n_entries"] == 0


def test_intersection_partial_overlap_counted_correctly() -> None:
    """Directional: days 1..50; regime: days 30..80. Overlap = 21 days (30..50)."""
    directional = _date_range(date(2024, 1, 1), 50)  # ordinals 0..49
    regime = frozenset(
        date.fromordinal(date(2024, 1, 1).toordinal() + i) for i in range(29, 80)
    )  # ordinals 29..79
    cache = _StubCache({
        "sig_directional": directional,
        "sig_regime": regime,
    })
    f = PredictedActivationsFilter()
    result = f.apply(_config_with_regime(), _ctx(cache))
    assert result.passed is True
    assert result.details["predicted_n_entries"] == 21  # ordinals 29..49 inclusive


# ---------------------------------------------------------------------------
# Defensive guards
# ---------------------------------------------------------------------------


def test_rejects_when_no_directional_signal_present() -> None:
    """Defensive: §3.5 S2 mandates exactly one directional. Filter raises
    ValueError if not (mirrors SignalDensityFilter's pattern)."""
    cfg = _config_with_regime()
    # Remove the directional signal
    no_directional = cfg.model_copy(update={
        "signals": tuple(s for s in cfg.signals if s.role != "directional"),
    })
    cache = _StubCache({})
    f = PredictedActivationsFilter()
    import pytest
    with pytest.raises(ValueError, match="expected exactly one directional"):
        f.apply(no_directional, _ctx(cache))


def test_handles_multiple_regime_gates() -> None:
    """If a config has multiple regime_filter signals, intersect with all."""
    directional = _date_range(date(2024, 1, 1), 50)
    regime_a = _date_range(date(2024, 1, 1), 30)  # first 30 days
    regime_b = _date_range(date(2024, 1, 11), 25)  # days 11..35
    # Intersection = days 11..29 = 19 days
    cfg = _config_with_regime()
    # Add a second regime gate to the config
    extra_regime = SignalSpec(
        id="sig_regime_b",
        type="threshold",
        role="regime_filter",
        indicators=("adx",),
        params={"threshold": 25.0, "op": ">"},
    )
    cfg = cfg.model_copy(update={"signals": (*cfg.signals, extra_regime)})
    cache = _StubCache({
        "sig_directional": directional,
        "sig_regime": regime_a,
        "sig_regime_b": regime_b,
    })
    f = PredictedActivationsFilter()
    result = f.apply(cfg, _ctx(cache))
    # dir (ord 0..49) ∩ regime_a (ord 0..29) ∩ regime_b (ord 10..34) = ord 10..29 = 20 days
    assert result.details["predicted_n_entries"] == 20
    assert result.details["n_regime_gates"] == 2
    assert result.passed is True  # 20 >= 10 floor
