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
from dataclasses import replace as dc_replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from forge.core.seed import SeedHierarchy
from forge.prefilters.calibration import _validate_forward_return_mode, load_calibration
from forge.prefilters.feature_cache import REGIMES, Regime
from forge.prefilters.permutation_test import PermutationTestFilter, _significance_score
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
        # Mirror CrucibleFeatureCache contract: silently drop missing
        # dates (D075's forward-horizon shift can push some past the
        # window boundary).
        return {d: self._returns[d] for d in dates if d in self._returns}

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


def _ctx_mode(
    cache: _ReturnsCache,
    mode: str,
    *,
    seed_root: int = 0,
    horizon: int | None = None,
) -> FilterContext:
    """A FilterContext whose permutation_test calibration overrides the forward-return mode
    (and optionally the horizon) — exercises the fixes without a temp YAML."""
    base = load_calibration(_PREFILTER_YAML)
    pt = base.permutation_test
    if horizon is not None:
        pt = dc_replace(pt, forward_horizon_days=horizon)
    pt = dc_replace(pt, forward_return_mode=mode)
    hierarchy = SeedHierarchy(seed_root)
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=dc_replace(base, permutation_test=pt),
        rng_factory=hierarchy.rng,
    )


# ---------------------------------------------------------------------------
# P1-1 (strategy-audit) — cumulative_trading forward-return mode
# ---------------------------------------------------------------------------


def test_shipped_calibration_mode_is_cumulative_trading() -> None:
    # FLIPPED 2026-07-04 (D237, prereg 848a1f67, after D220 confirmed): the live
    # prefilter.yaml now ships cumulative_trading. (An OLD config without the key still
    # defaults to single_day — see the back-compat test below.)
    cal = load_calibration(_PREFILTER_YAML)
    assert cal.permutation_test.forward_return_mode == "cumulative_trading"


def test_absent_forward_return_mode_defaults_single_day(tmp_path: Path) -> None:
    # Back-compat: a prefilter.yaml WITHOUT the key parses to the legacy single_day default
    # (the loader's `.get(..., "single_day")`). Derived from the real config to stay valid.
    import yaml

    raw = yaml.safe_load(_PREFILTER_YAML.read_text(encoding="utf-8"))
    raw["prefilter"]["permutation_test"].pop("forward_return_mode", None)
    keyless = tmp_path / "pf.yaml"
    keyless.write_text(yaml.safe_dump(raw), encoding="utf-8")
    assert load_calibration(keyless).permutation_test.forward_return_mode == "single_day"


def test_validate_forward_return_mode_rejects_unknown() -> None:
    assert _validate_forward_return_mode("cumulative_trading") == "cumulative_trading"
    with pytest.raises(ValueError, match="forward_return_mode"):
        _validate_forward_return_mode("bogus")


def test_cumulative_trading_sums_forward_trading_days() -> None:
    # 10 consecutive trading days, returns 0..9. Activate on day 2, horizon 2 → cumulative over
    # the next TWO trading days (T+1, T+2) = returns[3] + returns[4] = 7.0, NOT a single day.
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(10)
    returns_map = {d: float(i) for i, d in enumerate(window)}
    cache = _ReturnsCache(frozenset({window[2]}), returns_map)
    result = f.apply(cfg, _ctx_mode(cache, "cumulative_trading", horizon=2))
    assert result.details["forward_return_mode"] == "cumulative_trading"
    assert result.details["effective_n"] == 1
    assert result.details["real_notional"] == pytest.approx(7.0)


def test_cumulative_trading_reads_next_trading_day_not_weekend() -> None:
    # BUG (b): a Friday activation with the CALENDAR shift lands on Saturday (dropped). The
    # trading-day shift reads the next TRADING day (Monday) instead — no weekend sample loss.
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    trading: list[date] = []
    d = date(2022, 1, 3)  # a Monday
    while len(trading) < 15:
        if d.weekday() < 5:  # Mon-Fri only; weekends are non-trading (absent from the map)
            trading.append(d)
        d += timedelta(days=1)
    returns_map = {dd: 1.0 for dd in trading}
    friday = trading[4]
    assert friday.weekday() == 4
    cache = _ReturnsCache(frozenset({friday}), returns_map)

    legacy = f.apply(cfg, _ctx_mode(cache, "single_day", horizon=1))
    assert legacy.details["effective_n"] == 0  # Friday+1cal = Saturday, dropped

    cumulative = f.apply(cfg, _ctx_mode(cache, "cumulative_trading", horizon=1))
    assert cumulative.details["effective_n"] == 1  # Friday → next trading day (Monday)
    assert cumulative.details["real_notional"] == pytest.approx(1.0)


def test_cumulative_informative_signal_passes() -> None:
    # Signal fires the trading day BEFORE each high-return day; T+1 cumulative lands on the
    # +1.0 days → real notional tops the null → passes.
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    returns_map = {d: (1.0 if 1 <= i <= 50 else 0.0) for i, d in enumerate(window)}
    cache = _ReturnsCache(frozenset(window[:49]), returns_map)
    result = f.apply(cfg, _ctx_mode(cache, "cumulative_trading", horizon=1))
    assert result.passed


def test_cumulative_determinism_same_seed() -> None:
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    returns_map = {d: 0.5 if i % 2 == 0 else -0.4 for i, d in enumerate(window)}
    cache = _ReturnsCache(frozenset(window[::3]), returns_map)
    a = f.apply(cfg, _ctx_mode(cache, "cumulative_trading", seed_root=7, horizon=3))
    b = f.apply(cfg, _ctx_mode(cache, "cumulative_trading", seed_root=7, horizon=3))
    assert a.details["p_value"] == b.details["p_value"]


# ---------------------------------------------------------------------------
# P1-2a — vol-appropriate (|move|) null for volatility_event
# ---------------------------------------------------------------------------


def _ve_config() -> object:
    # model_copy doesn't re-validate (R3 event-proximity isn't needed — the filter only reads
    # config.hypothesis + the directional signal).
    return minimal_strategy_config().model_copy(update={"hypothesis": "volatility_event"})


def test_ve_cumulative_is_signed() -> None:
    # D301: the P1-2a |move| variant is removed (dropped at D235) — ve configs use the
    # same signed cumulative statistic as every family.
    f = PermutationTestFilter()
    ve_cfg = _ve_config()
    window = _trading_window(10)
    returns_map = {d: float(i) for i, d in enumerate(window)}
    cache = _ReturnsCache(frozenset({window[2]}), returns_map)
    result = f.apply(ve_cfg, _ctx_mode(cache, "cumulative_trading", horizon=2))
    assert "volatility_event_absolute_move" not in result.details
    assert result.details["real_notional"] == pytest.approx(7.0)  # signed 3+4, not |3+4|


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


def test_score_is_threshold_relative() -> None:
    """D095: the ranker score maps the passing p-value range onto full [0, 1]
    (`1 - p/threshold`), not the legacy `1 - p` that squashed passers into
    [0.90, 1.0]. Integration check: the filter's score matches the helper."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(50)
    returns_map = {d: 1.0 if i < 10 else 0.0 for i, d in enumerate(window)}
    activations = frozenset(window[:10])
    cache = _ReturnsCache(activations, returns_map)
    result = f.apply(cfg, _ctx(cache))
    p = result.details["p_value"]
    thr = result.details["p_value_threshold"]
    assert result.score == pytest.approx(_significance_score(p, thr))


def test_significance_score_uses_full_passing_range() -> None:
    """D095: the re-grade gives statistical significance real resolution among
    survivors. A barely-passing p (≈threshold) → ~0; a strongly-significant p
    (≈0) → ~1; the legacy `1 - p` would have rated both ~0.9-1.0."""
    assert _significance_score(0.0, 0.10) == pytest.approx(1.0)  # most significant
    assert _significance_score(0.10, 0.10) == pytest.approx(0.0)  # barely passing
    assert _significance_score(0.05, 0.10) == pytest.approx(0.5)  # mid-range resolution
    assert _significance_score(0.5, 0.10) == pytest.approx(0.0)  # failing → clamped
    assert _significance_score(0.0, 0.0) == 0.0  # degenerate threshold → 0


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


# ---------------------------------------------------------------------------
# D075 — forward-horizon return comparison
# ---------------------------------------------------------------------------


def test_d075_details_record_horizon_and_effective_n() -> None:
    """D075 added two new detail keys: `forward_horizon_days` (which value
    was used) and `effective_n` (how many activation->target dates landed
    in-window)."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    returns_map = {d: 0.01 for d in window}
    activations = frozenset(window[:50])
    cache = _ReturnsCache(activations, returns_map)
    result = f.apply(cfg, _ctx(cache))
    assert "forward_horizon_days" in result.details
    assert "effective_n" in result.details
    assert result.details["forward_horizon_days"] == 5  # production default
    # 50 activations, all near window start, all in-window after T+5 shift.
    assert result.details["effective_n"] == 50


def test_d075_leading_indicator_passes_only_with_horizon() -> None:
    """A signal whose activations predict T+5 returns (but not T+0 returns)
    is the canonical case D075 is designed to fix. Same data, two
    calibrations: horizon=0 rejects, horizon=5 passes."""
    from forge.prefilters.calibration import (
        AutoTuneCalibration,
        Calibration,
        ExpectedTradeCountCalibration,
        NoveltyCalibration,
        PermutationTestCalibration,
        PredictedActivationsCalibration,
        RegimeExposureCalibration,
        SignalCorrelationCalibration,
        SignalDensityCalibration,
    )

    def _calib(horizon: int) -> Calibration:
        return Calibration(
            signal_density=SignalDensityCalibration(min_activations=30),
            expected_trade_count=ExpectedTradeCountCalibration(min_trades=50),
            predicted_activations=PredictedActivationsCalibration(min_entries=10),
            novelty=NoveltyCalibration(max_jaccard_overlap=0.80),
            signal_correlation=SignalCorrelationCalibration(max_jaccard_overlap=0.85),
            regime_exposure=RegimeExposureCalibration(max_single_regime_concentration=0.80),
            permutation_test=PermutationTestCalibration(
                n_permutations=100,
                p_value_threshold=0.10,
                forward_horizon_days=horizon,
            ),
            auto_tune=AutoTuneCalibration(
                enabled=True,
                min_promotion_rate=0.005,
                max_promotion_rate=0.05,
                adjustment_pct_per_step=0.10,
                max_cumulative_adjustment=0.30,
            ),
        )

    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(200)
    # Activations on a 6-day grid (0, 6, 12, ..., 192) so the T+5 dates
    # land on (5, 11, 17, ..., 197) — disjoint from the activation set.
    # At horizon=0 the filter sees zero returns; at horizon=5 it sees the
    # full +1.0 boost.
    from datetime import timedelta as _td

    returns_map: dict[date, float] = dict.fromkeys(window, 0.0)
    activations_list = [window[i] for i in range(0, 200, 6)]  # 34 dates
    for d in activations_list:
        forward = d + _td(days=5)
        if forward in returns_map:
            returns_map[forward] = 1.0
    activations = frozenset(activations_list)
    cache = _ReturnsCache(activations, returns_map)

    hierarchy0 = SeedHierarchy(0)
    ctx_h0 = FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=_calib(horizon=0),
        rng_factory=hierarchy0.rng,
    )
    hierarchy5 = SeedHierarchy(0)
    ctx_h5 = FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=_calib(horizon=5),
        rng_factory=hierarchy5.rng,
    )

    result_h0 = f.apply(cfg, ctx_h0)
    result_h5 = f.apply(cfg, ctx_h5)

    # horizon=0: signal sees only T+0 (zero) returns -> notional 0 vs
    # permuted draws from a window with 40 isolated +1.0 days; p_value
    # should be HIGH -> fail.
    assert not result_h0.passed
    # horizon=5: signal sees T+5 returns (40 of which are +1.0) -> notional
    # = 40 vs permuted random subsets -> p_value should be near 0 -> pass.
    assert result_h5.passed


def test_d075_dates_past_window_drop_from_effective_n() -> None:
    """Activations near the end of the window shift T+5 past the data
    boundary; those drops are silent (matches CrucibleFeatureCache
    contract) and effective_n reflects the in-window count."""
    f = PermutationTestFilter()
    cfg = minimal_strategy_config()
    window = _trading_window(50)
    returns_map = {d: 0.0 for d in window}
    # 30 activations across the LAST 30 days of the window. After shifting
    # +5, dates 46..49 stay in-window (4) but dates 50..78 (which would
    # require window slots that don't exist) drop.
    activations = frozenset(window[-30:])  # days 20..49
    cache = _ReturnsCache(activations, returns_map)
    result = f.apply(cfg, _ctx(cache))
    # Original 30 activations; horizon=5 shifts to days 25..54; only
    # days 25..49 are in the 50-day window. effective_n == 25.
    assert result.details["n_activations"] == 30
    assert result.details["effective_n"] == 25


# ---------------------------------------------------------------------------
# Q21 — `data_history_days` is a TRADING-day count; the null-pool window must
# span the equivalent CALENDAR range or it silently truncates.
# ---------------------------------------------------------------------------


def test_q21_full_window_spans_calendar_extent_of_trading_days() -> None:
    """`data_history_days` counts trading days (~252/yr). Treating it as
    calendar days (pre-fix) truncated the permutation null pool: a 2118-
    trading-day / ~8.4-year window reached only 2023-10, dropping ~2.5y of
    recent returns and biasing every p-value. The window must cover the
    equivalent calendar span. Over-coverage is harmless — `returns()` drops
    dates with no data."""
    from forge.prefilters.permutation_test import _full_window

    start = date(2018, 1, 2)
    n_trading = 2118  # ~8.4 trading years
    window = _full_window(start, n_trading)
    # Must reach into ~2026 to cover 2118 trading days of calendar time
    # (pre-fix it stopped at 2023-10-20, i.e. start + 2118 calendar days).
    assert window[-1] >= date(2026, 1, 1), f"null-pool window truncated at {window[-1]}"
    # Sanity: doesn't wildly overshoot the real calendar extent.
    assert (window[-1] - start).days < n_trading * 2


def test_q21_window_unchanged_for_pure_calendar_caller_dates() -> None:
    """Regression guard: the existing `_ReturnsCache` tests size returns over
    N consecutive calendar days and set data_history_days=N. The longer window
    still covers those N dates (the rest are dropped by `returns()`), so the
    matched return pool — and every existing test's verdict — is unchanged."""
    from forge.prefilters.permutation_test import _full_window

    start = date(2022, 1, 1)
    window = set(_full_window(start, 200))
    original_200 = {start + timedelta(days=i) for i in range(200)}
    assert original_200 <= window  # the longer window is a superset
