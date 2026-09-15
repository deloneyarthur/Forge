"""The v55 emission policy: every Python-side property of the frozen grammar, in one module.

WHY one file: seventeen per-version modules each pinned an emission property under a page of
narrative. The properties are silent-re-admission tripwires the freeze hook cannot see (it
guards `grammar.yaml` text, not the sampler), so EVERY assertion is kept and grouped by the
hypothesis it protects; the narratives live in the D-entries each test names. Folded 2026-09-15
(Batch 6 part C) from: trend_grammar_v23 (D236), trend_grammar_v23_exits (D236), resid_vix_v27
(D264), v33_generation_health (D276), v34_census_retirements (D278), v36_exit_duration_priors
(D270), v38_exit_mix (D282), v39_ve_program (D289), v40_mr_timer_cell (D291), v41_tier3_xsect
(D292/D294), v47_single_name_retirement (D328), v52_capitulation_retirement (D328/D340),
v55_vix_conditioner_retired (D366), mr_grammar_v24 (D254), mr_grammar_v28 (D265),
mr_grammar_v29 (D266), event_momentum (D109/D268).

Populations are module fixtures drawn with `sample_configs` (seed k of a small population is
seed k of a larger one on the same inputs, so slices are the original populations).
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from typing import ClassVar

import pytest
from crucible_contracts import RegistrySnapshot, SignalSpec, StrategyConfig

import forge.enumeration.sampler as sampler_mod
from forge.enumeration import enumerate_candidates
from forge.enumeration.indicator_thresholds import (
    _INDICATOR_THRESHOLD_TABLE,
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.sampler import (
    _K_MULTIPLIERS,
    _MR_RANGING_GATES,
    _NO_EARNINGS_UNDERLYINGS,
    _STRUCTURALLY_UNTRADEABLE_UNDERLYINGS,
    _TIER_1_ETF_UNDERLYINGS,
    _VIX_CONDITIONER_ID,
    _VIX_CONDITIONER_SHARE,
    SamplerError,
    _directional_signal_params,
    _dte_target,
    _eligible_regime_vetoes,
    _exit_params,
    _pick_underlying,
)
from forge.enumeration.search_space import SearchSpace, _build_regime_pool, build_search_space
from forge.grammar import Grammar, load_grammar, validate
from forge.grammar.custom_predicates import (
    _C2_HYPOTHESIS_EXTRA_IDS,
    _MR_REGIME_VETO_INDICATORS,
    _R1_GAMMA_REGIME_INDICATOR,
    _R1_GATE_EXEMPT_DIRECTIONALS,
    _R1_MARKET_REALIZED_VOL_REGIME_INDICATOR,
    _R1_REALIZED_VOL_REGIME_INDICATOR,
    _R1_VOL_REGIME_INDICATOR,
    _R2_TREND_CONTINUATION_REGIME_INDICATORS,
    _R3_EVENT_PROXIMITY_INDICATORS,
    _S5_HYPOTHESIS_EXITS,
)
from forge.grammar.signal_horizon import (
    _DEFAULT_HORIZON_DAYS,
    buckets_for_horizon_class,
    horizon_class,
    nearest_bucket,
    signal_horizon_days,
)
from tests.fixtures.contexts import REPO_ROOT
from tests.fixtures.registries import its_registry, rtr_registry, v33_registry, v44_registry
from tests.fixtures.registries import v31_registry as _v31_registry
from tests.fixtures.sampling import sample_configs
from tests.fixtures.strategy_configs import minimal_registry_snapshot
from tests.fixtures.universe_snapshot import UNIVERSE_TIER3_SNAPSHOT_2026_07_20

_XSECT_SHARE = {"trend_continuation": 0.6, "mean_reversion": 0.6}


# ------------------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(
        REPO_ROOT / "config" / "grammar.yaml", archive_dir=REPO_ROOT / "config" / "grammar_archive"
    )


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


@pytest.fixture(scope="module")
def v31_registry(registry: RegistrySnapshot) -> RegistrySnapshot:
    """Serves the parameterized `momentum` (the D270 setup): a retirement whose content is
    "momentum stops being emitted" is vacuous on a registry that never served it (D340)."""
    return _v31_registry(registry)


@pytest.fixture(scope="module")
def v33_reg(registry: RegistrySnapshot) -> RegistrySnapshot:
    return v33_registry(registry)


@pytest.fixture(scope="module")
def v33_space(grammar: Grammar, v33_reg: RegistrySnapshot) -> SearchSpace:
    return build_search_space(grammar, v33_reg)


@pytest.fixture(scope="module")
def trend_draws(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, registry, n=3000, hypothesis="trend_continuation")


@pytest.fixture(scope="module")
def mr_draws(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, registry, n=4000, hypothesis="mean_reversion")


@pytest.fixture(scope="module")
def ve_draws(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, registry, n=400, hypothesis="volatility_event")


@pytest.fixture(scope="module")
def any_draws(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, registry, n=2000)


@pytest.fixture(scope="module")
def xsect_draws(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, registry, n=3000, rank_share=1.0)


@pytest.fixture(scope="module")
def v31_trend_draws(grammar: Grammar, v31_registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, v31_registry, n=600, hypothesis="trend_continuation")


@pytest.fixture(scope="module")
def v31_mr_draws(grammar: Grammar, v31_registry: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, v31_registry, n=600, hypothesis="mean_reversion")


@pytest.fixture(scope="module")
def v33_trend_draws(grammar: Grammar, v33_reg: RegistrySnapshot) -> list[StrategyConfig]:
    return sample_configs(grammar, v33_reg, n=800, hypothesis="trend_continuation")


def _enumerate(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return list(
        enumerate_candidates(
            grammar, registry, seed=0, max_candidates=6000, rank_combiner_share=_XSECT_SHARE
        )
    )


@pytest.fixture(scope="module")
def v47_configs(grammar: Grammar, registry: RegistrySnapshot) -> list[StrategyConfig]:
    return _enumerate(grammar, registry)


@pytest.fixture(scope="module")
def v52_configs(grammar: Grammar, v31_registry: RegistrySnapshot) -> list[StrategyConfig]:
    return _enumerate(grammar, v31_registry)


@pytest.fixture(scope="module")
def serving_registry(registry: RegistrySnapshot) -> RegistrySnapshot:
    """Serves vix_term_slope as a trend gate; under the minimal registry the conditioner is
    dormant anyway and a test there would have passed before the retirement (D366)."""
    return v44_registry(registry)


@pytest.fixture(scope="module")
def v55_configs(grammar: Grammar, serving_registry: RegistrySnapshot) -> list[StrategyConfig]:
    return list(enumerate_candidates(grammar, serving_registry, seed=11, max_candidates=20000))


# ------------------------------------------------------------------------------- helpers


def _exit_ids(cfg: StrategyConfig) -> frozenset[str]:
    return frozenset(e.id for e in cfg.exits)


def _time_stop_params(cfg: StrategyConfig) -> dict[str, object] | None:
    return next((dict(e.params) for e in cfg.exits if e.id == "time_stop"), None)


def _directional(cfg: StrategyConfig) -> SignalSpec:
    return next(s for s in cfg.signals if s.role == "directional")


def _is_capitulation(cfg: StrategyConfig) -> bool:
    return _directional(cfg).indicators == ("momentum",)


def _gates(cfg: StrategyConfig) -> list[str]:
    return [s.indicators[0] for s in cfg.signals if s.role == "regime_filter"]


def _share(cfgs: list[StrategyConfig], exit_id: str) -> float:
    return sum(1 for c in cfgs if exit_id in _exit_ids(c)) / len(cfgs)


def _bucket(cfgs: list[StrategyConfig], dte_bucket: str) -> list[StrategyConfig]:
    return [c for c in cfgs if c.dte_bucket == dte_bucket]


def _resid_draws(cfgs: list[StrategyConfig]) -> list[StrategyConfig]:
    return [c for c in cfgs if _directional(c).indicators[0] == "residual_momentum"]


# ==============================================================================================
# TREND CONTINUATION
# ==============================================================================================


@pytest.mark.parametrize(
    ("indicator", "role", "skippable"),
    [
        ("sma_slope", "directional", False),
        ("ad_slope", "directional", False),
        ("momentum_252", "directional", False),
        ("returns_12m_skip1", "directional", True),
        ("macd", "directional", True),
        ("ema_cross", "directional", True),
        ("supertrend", "directional", True),
        ("residual_momentum", "directional", False),
        ("residual_momentum", "regime_filter", True),
        ("vix_term_slope", "regime_filter", False),
        ("vix_term_slope", "directional", True),
    ],
)
def test_trend_threshold_roles(indicator: str, role: str, skippable: bool) -> None:
    """v23 (D236) keeps one 12-1 momentum and prunes macd/ema_cross/supertrend; v27 (D264)
    admits residual_momentum as a directional only and vix_term_slope as a gate only."""
    assert bool(is_threshold_skippable(indicator, role)) is skippable


@pytest.mark.parametrize(
    ("indicator", "days", "cls"),
    [
        ("sma_slope", 200, "long_lookback"),
        ("ad_slope", 60, "medium_lookback"),
        ("residual_momentum", 63, "medium_lookback"),
        ("vix_term_slope", 1, None),
    ],
)
def test_trend_signal_horizons(indicator: str, days: int, cls: str | None) -> None:
    """Explicit S4 horizons: slopes at their lookback, resid at 63 td, the gate at 1 (D236/D264)."""
    assert signal_horizon_days(indicator) == days
    if cls is not None:
        assert horizon_class(indicator) == cls


@pytest.mark.parametrize("indicator", ["sma_slope", "ad_slope", "residual_momentum"])
def test_trend_directionals_do_not_ride_the_default_horizon(indicator: str) -> None:
    assert signal_horizon_days(indicator) != _DEFAULT_HORIZON_DAYS


@pytest.mark.parametrize("indicator", ["sma_slope", "ad_slope"])
def test_slope_directionals_are_percentile_only(indicator: str) -> None:
    """Distribution-free: no absolute range ships without a value distribution (D236)."""
    params = sample_threshold_params(indicator, "directional", random.Random(0))
    assert params.get("use_percentile") is True
    assert "threshold" in params
    assert isinstance(params["threshold"], float)
    assert 0.0 <= params["threshold"] <= 1.0


@pytest.mark.parametrize(("n_seeds", "lo", "hi"), [(50, 0.60, 0.90), (200, 0.65, 0.85)])
def test_residual_momentum_percentile_emission(n_seeds: int, lo: float, hi: float) -> None:
    """v27 (D264) shipped [0.60, 0.90]; v33 (D276) narrowed to the converters' [0.65, 0.85]."""
    for seed in range(n_seeds):
        params = sample_threshold_params("residual_momentum", "directional", random.Random(seed))
        assert params.get("use_percentile") is True
        assert params.get("op") == ">"
        assert params.get("percentile_window") == 252
        assert isinstance(params["threshold"], float)
        assert lo <= params["threshold"] <= hi, params


@pytest.mark.parametrize(
    ("n_seeds", "window", "skip"), [(50, (63, 252), (0, 21)), (200, (70, 160), (7, 21))]
)
def test_residual_momentum_formation_knobs(
    n_seeds: int, window: tuple[int, int], skip: tuple[int, int]
) -> None:
    """window/skip ride the directional params (D264); v33 (D276) narrowed them to the confirmed
    region."""
    for seed in range(n_seeds):
        params = _directional_signal_params("residual_momentum", random.Random(seed))
        assert isinstance(params["window"], int)
        assert window[0] <= params["window"] <= window[1], params
        assert isinstance(params["skip"], int)
        assert skip[0] <= params["skip"] <= skip[1], params
        assert params.get("use_percentile") is True
        assert "threshold" in params


def test_residual_momentum_params_deterministic() -> None:
    """Hard rule #6: same seed, same params, draw for draw."""
    assert _directional_signal_params("residual_momentum", random.Random(1234)) == (
        _directional_signal_params("residual_momentum", random.Random(1234))
    )


def test_residual_momentum_horizon_snaps_to_swing_mid() -> None:
    """63 td is medium_lookback, so S4 permits swing_short/swing_mid and k in 2..4 lands on
    swing_mid (D102/D264)."""
    assert horizon_class("residual_momentum") == "medium_lookback"
    allowed = buckets_for_horizon_class("medium_lookback")
    assert allowed == ("swing_short", "swing_mid")
    for k in (2, 3, 4):
        assert nearest_bucket(allowed, float(k * 63)) == "swing_mid"


def test_vix_term_slope_regime_params_absolute_contango() -> None:
    """Native-unit threshold in [0.0, 2.0], op ">": fire in contango (D264)."""
    for seed in range(50):
        params = sample_threshold_params("vix_term_slope", "regime_filter", random.Random(seed))
        assert params.get("op") == ">"
        assert "use_percentile" not in params
        assert isinstance(params["threshold"], float)
        assert 0.0 <= params["threshold"] <= 2.0


def test_vix_term_slope_in_r2_pool() -> None:
    """The R2 python-side pool accepts vix_term_slope (D264)."""
    assert "vix_term_slope" in _R2_TREND_CONTINUATION_REGIME_INDICATORS


# --- exits (v23 D236) ---


def test_parabolic_sar_dropped_from_trend_exit_pool() -> None:
    """Refuted incumbent: chandelier beat parabolic_sar by +0.29 CPCV-p25 and WF (D236)."""
    pool = _S5_HYPOTHESIS_EXITS["trend_continuation"]["required_from_set"]
    assert "parabolic_sar_exit" not in pool
    assert "chandelier_exit" in pool


def test_trend_exit_pool_is_trailing_atr_and_chandelier() -> None:
    """The 3-way trend exit pick loses parabolic_sar; trailing_atr stays (D236)."""
    assert _S5_HYPOTHESIS_EXITS["trend_continuation"]["required_from_set"] == (
        "trailing_atr",
        "chandelier_exit",
    )


def test_chandelier_exit_emits_atr_multiplier_sweep() -> None:
    """Crucible's chandelier template reads atr_multiplier from the exit params (D236)."""
    rng = random.Random(0)
    seen: set[float] = set()
    for _ in range(200):
        params = _exit_params("chandelier_exit", rng)
        assert "atr_multiplier" in params, "chandelier leaked empty params"
        assert isinstance(params["atr_multiplier"], float)
        assert 2.0 <= params["atr_multiplier"] <= 3.0
        seen.add(params["atr_multiplier"])
    assert len(seen) > 1, "atr_multiplier must be swept, not constant"


def test_chandelier_atr_multiplier_deterministic() -> None:
    assert _exit_params("chandelier_exit", random.Random(42)) == _exit_params(
        "chandelier_exit", random.Random(42)
    )


def test_parabolic_sar_exit_params_unchanged() -> None:
    """Dropping parabolic_sar from the trend pool does not give it params (D236)."""
    assert _exit_params("parabolic_sar_exit", random.Random(0)) == {}


def test_days_to_fomc_event_window_tightened() -> None:
    """Event-proximity window 60d to 14d, low end at least 5d (D236)."""
    spec = _INDICATOR_THRESHOLD_TABLE["days_to_fomc"]
    assert spec.regime_range is not None
    low, high = spec.regime_range
    assert (low, high) == (7.0, 14.0)
    assert high <= 14.0
    assert low >= 5.0


def test_days_to_fomc_regime_fires_when_event_imminent() -> None:
    params = sample_threshold_params("days_to_fomc", "regime_filter", random.Random(0))
    assert params["op"] == "<"


def test_days_to_fomc_regime_samples_near_ten_day_sweetspot() -> None:
    """Median sampled window about 10d, was about 33.5d under (7, 60) (D236)."""
    rng = random.Random(0)
    vals = [
        float(sample_threshold_params("days_to_fomc", "regime_filter", rng)["threshold"])  # type: ignore[arg-type]
        for _ in range(500)
    ]
    assert all(7.0 <= v <= 14.0 for v in vals)
    assert 9.0 <= statistics.median(vals) <= 12.0


# --- exit mix on the sampled population (v38 D282, v40 D291) ---


def test_v38_trend_swing_long_timer_share_reduced(trend_draws: list[StrategyConfig]) -> None:
    """The scoped cell draws time_stop at p=0.15, was 0.5 (D282)."""
    swing_long = _bucket(trend_draws, "swing_long")
    assert len(swing_long) >= 300, f"too few swing_long draws: {len(swing_long)}"
    assert 0.10 < _share(swing_long, "time_stop") < 0.21


def test_v38_trend_swing_long_chandelier_only_share_rises(
    trend_draws: list[StrategyConfig],
) -> None:
    """Chandelier-only discretionary sets rise well above the 0.22 baseline (D282)."""
    swing_long = _bucket(trend_draws, "swing_long")
    assert len(swing_long) >= 300
    mandatory = frozenset.intersection(*(_exit_ids(c) for c in swing_long))
    chan_only = sum(
        1 for c in swing_long if (_exit_ids(c) - mandatory) == {"chandelier_exit"}
    ) / len(swing_long)
    assert chan_only > 0.30, f"chandelier-only share {chan_only:.3f} not well above 0.22"


def test_v38_trend_swing_mid_timer_share_unchanged(trend_draws: list[StrategyConfig]) -> None:
    """ "Do not touch other buckets": swing_mid keeps the p=0.5 optional draw (D282)."""
    swing_mid = _bucket(trend_draws, "swing_mid")
    assert len(swing_mid) >= 300, f"too few swing_mid draws: {len(swing_mid)}"
    assert 0.42 < _share(swing_mid, "time_stop") < 0.58


def test_v38_remaining_swing_long_timers_keep_u810(trend_draws: list[StrategyConfig]) -> None:
    """The v36 U[8,10] n_bars prior composes with the reduced draw (D270/D282)."""
    carriers = [c for c in _bucket(trend_draws, "swing_long") if "time_stop" in _exit_ids(c)]
    assert carriers, "no surviving timer draws to check"
    for cfg in carriers:
        params = next(e.params for e in cfg.exits if e.id == "time_stop")
        assert params.get("n_bars") in (8, 9, 10), (cfg.name, params)


def test_v40_trend_required_pick_stays_uniform(trend_draws: list[StrategyConfig]) -> None:
    """Control for the MR timer bias: trend's required_from_set pick stays 50/50 (D291)."""
    assert 0.42 < _share(trend_draws, "chandelier_exit") < 0.58


def test_v36_trend_swing_long_time_stop_in_8_10(v31_trend_draws: list[StrategyConfig]) -> None:
    """Every trend swing_long time_stop samples n_bars in U[8,10] and covers it (D270)."""
    seen: set[object] = set()
    for cfg in _bucket(v31_trend_draws, "swing_long"):
        ts = _time_stop_params(cfg)
        if ts is None:
            continue
        assert isinstance(ts.get("n_bars"), int), ts
        assert 8 <= ts["n_bars"] <= 10, ts  # type: ignore[operator]
        seen.add(ts["n_bars"])
    assert seen == {8, 9, 10}, seen


def test_v36_trend_other_buckets_keep_the_bare_time_stop(
    v31_trend_draws: list[StrategyConfig],
) -> None:
    """ "Do not touch other buckets on this evidence": param-less time_stop elsewhere (D270)."""
    checked = 0
    for cfg in v31_trend_draws:
        ts = _time_stop_params(cfg)
        if cfg.dte_bucket == "swing_long" or ts is None:
            continue
        checked += 1
        assert ts == {}, (cfg.dte_bucket, ts)
    assert checked > 0, "no non-swing_long trend time_stop draws sampled"


# --- the resid_vix concentrated sweep (v33 D276) ---


def test_v33_resid_regime_pool_pinned_to_confirmed_arms(
    v33_trend_draws: list[StrategyConfig],
) -> None:
    """Density lever: every resid draw spends its gate on vix_term_slope or hurst (D276)."""
    seen = {"vix_term_slope": 0, "hurst": 0}
    for cfg in _resid_draws(v33_trend_draws):
        primary = _gates(cfg)[0]
        assert primary in seen, cfg.name
        seen[primary] += 1
    assert seen["vix_term_slope"] > 0
    assert seen["hurst"] > 0


def test_v33_resid_gate_thresholds_in_confirmed_ranges(
    v33_trend_draws: list[StrategyConfig],
) -> None:
    """vix gate [0.1, 0.7] (converters 0.22/0.66), hurst percentile [0.40, 0.50] (D276)."""
    for cfg in _resid_draws(v33_trend_draws):
        g = next(s for s in cfg.signals if s.role == "regime_filter")
        assert g.params["op"] == ">"
        if g.indicators[0] == "vix_term_slope":
            assert 0.1 <= g.params["threshold"] <= 0.7, cfg.name
        else:
            assert g.params.get("use_percentile") is True
            assert 0.40 <= g.params["threshold"] <= 0.50, cfg.name


def test_v33_resid_structure_pinned_to_rank_monthly(
    v33_trend_draws: list[StrategyConfig],
) -> None:
    """Every converter was monthly cross_sectional_rank, k in {5, 10}, mostly long_only (D276)."""
    modes = {"long_only": 0, "long_short": 0}
    for cfg in _resid_draws(v33_trend_draws):
        assert cfg.combiner.type == "cross_sectional_rank", cfg.name
        assert cfg.combiner.rebalance_frequency == "monthly", cfg.name
        assert cfg.combiner.rank_k in (5, 10), cfg.name
        assert cfg.underlying is None, cfg.name
        modes[cfg.combiner.direction_mode] += 1
    assert modes["long_only"] > modes["long_short"] > 0


def test_v33_trend_dsj_veto_survives_on_other_gates(
    v33_trend_draws: list[StrategyConfig],
) -> None:
    """Only the gamma_flip pairing dies: the days_since_jump veto still stacks elsewhere (D276)."""
    seen_dsj_veto = 0
    for cfg in v33_trend_draws[:600]:
        gates = [s for s in cfg.signals if s.role == "regime_filter"]
        if any("days_since_jump" in g.indicators for g in gates):
            seen_dsj_veto += 1
            assert gates[0].indicators[0] != "gamma_flip_distance_pct", cfg.name
    assert seen_dsj_veto > 0


# ==============================================================================================
# MEAN REVERSION
# ==============================================================================================

_ALL_MR_GATE_IDS = {
    "iv_rank",
    "gamma_flip_distance_pct",
    "hurst",
    "rv_rank",
    "vol_regime",
    "realized_vol",
    "market_realized_vol",
    "rsi_2",
}


@pytest.mark.parametrize(
    ("constant", "indicator"),
    [
        (_R1_VOL_REGIME_INDICATOR, "vol_regime"),
        (_R1_REALIZED_VOL_REGIME_INDICATOR, "realized_vol"),
        (_R1_MARKET_REALIZED_VOL_REGIME_INDICATOR, "market_realized_vol"),
    ],
)
def test_mr_r1_gate_constants(constant: str, indicator: str) -> None:
    """The R1 predicate names each calm-vol gate explicitly (D254, D265, D266)."""
    assert constant == indicator


@pytest.mark.parametrize(
    ("registered", "indicator"),
    [
        (_ALL_MR_GATE_IDS - {"realized_vol", "market_realized_vol"}, "vol_regime"),
        (_ALL_MR_GATE_IDS - {"market_realized_vol"}, "realized_vol"),
        (_ALL_MR_GATE_IDS, "market_realized_vol"),
    ],
)
def test_mr_calm_vol_gates_enumerable_in_mr_regime_pool(
    registered: set[str], indicator: str
) -> None:
    """Registered is not enumerable: each gate must reach the MR pool (D254, D265, D266)."""
    pool = _build_regime_pool(registered, single_name_only_ids=frozenset())
    assert indicator in pool["mean_reversion"]


@pytest.mark.parametrize(
    "indicator",
    ["vol_regime", "realized_vol", "market_realized_vol", "rv_rank", "gamma_flip_distance_pct"],
)
def test_mr_ranging_gate_boost_set(indicator: str) -> None:
    """The 3x ranging-gate boost covers every calm-vol gate; adds never replaced (D254-D266)."""
    assert indicator in _MR_RANGING_GATES


def test_hurst_dropped_from_mr_ranging_gate_boost() -> None:
    """hurst is null-to-negative as an MR gate (-0.27 vs rv_rank, 0/6), so no boost (D254)."""
    assert "hurst" not in _MR_RANGING_GATES


def test_mr_veto_pool_is_two_member() -> None:
    """The MR veto pool widened to (ivol, market_realized_vol) (D266)."""
    assert _MR_REGIME_VETO_INDICATORS == ("ivol", "market_realized_vol")


@pytest.mark.parametrize(
    ("indicator", "regime_range", "op_regime", "gate_only"),
    [
        ("vol_regime", (2.0, 2.0), None, False),
        ("realized_vol", (0.15, 0.30), "<", False),
        ("market_realized_vol", (0.15, 0.30), "<", True),
    ],
)
def test_mr_gate_threshold_specs(
    indicator: str, regime_range: tuple[float, float], op_regime: str | None, gate_only: bool
) -> None:
    """vol_regime pinned raw at 2 (exclude the high tercile); the absolute-RV gates carry the
    asked [0.15, 0.30] sweep, market_realized_vol gate-only (D254, D265, D266)."""
    spec = _INDICATOR_THRESHOLD_TABLE[indicator]
    assert spec.regime_range == regime_range
    assert spec.regime_percentile_range is None
    if op_regime is not None:
        assert spec.op_regime == op_regime
    if gate_only:
        assert spec.directional_range is None
        assert spec.directional_percentile_range is None


def test_vol_regime_emits_raw_exclude_high_tercile() -> None:
    params = sample_threshold_params("vol_regime", "regime_filter", random.Random(0))
    assert params.get("use_percentile") is not True
    assert params["threshold"] == 2.0
    assert params["op"] == "<"


@pytest.mark.parametrize("indicator", ["realized_vol", "market_realized_vol"])
def test_absolute_rv_gates_emit_threshold_in_sweep(indicator: str) -> None:
    params = sample_threshold_params(indicator, "regime_filter", random.Random(0))
    assert "use_percentile" not in params
    assert params["op"] == "<"
    assert 0.15 <= float(params["threshold"]) <= 0.30  # type: ignore[arg-type]


def test_market_realized_vol_horizon_gate_only() -> None:
    """Horizon 1: gate-only, S4 never consults it (D266)."""
    assert signal_horizon_days("market_realized_vol") == 1


def test_zscore_returns_kept_as_mr_directional() -> None:
    """Ranked #2 by the xsect backtest (0.442); never drop it (D254)."""
    assert not is_threshold_skippable("zscore_returns", "directional")


# --- the MR timer cell (v36 D270, v38 D282, v40 D291) ---


def test_v40_mr_required_pick_biased_to_time_stop(mr_draws: list[StrategyConfig]) -> None:
    """Non-capitulation MR draws time_stop from the required set at p=0.65 (D291)."""
    cfgs = [c for c in mr_draws if not _is_capitulation(c)]
    assert len(cfgs) >= 1000, f"too few non-capitulation MR draws: {len(cfgs)}"
    assert 0.60 < _share(cfgs, "time_stop") < 0.70


def test_v38_mr_time_stop_share(mr_draws: list[StrategyConfig]) -> None:
    """MR's timer is a required_from_set pick, so the share holds at ~0.65 (D282)."""
    assert 0.60 < _share(mr_draws[:1500], "time_stop") < 0.70


def test_v40_mr_time_stop_nbars_in_8_12_all_buckets(mr_draws: list[StrategyConfig]) -> None:
    """Every non-capitulation MR time_stop emits n_bars in [8, 12]; none is param-less (D291)."""
    checked = 0
    for cfg in mr_draws:
        if _is_capitulation(cfg):
            continue
        ts = _time_stop_params(cfg)
        if ts is None:
            continue
        assert ts.get("n_bars") is not None, f"param-less time_stop survived at {cfg.dte_bucket}"
        assert 8 <= ts["n_bars"] <= 12, (cfg.dte_bucket, ts)  # type: ignore[operator]
        checked += 1
    assert checked >= 500, f"too few MR time_stop draws checked: {checked}"


def test_mr_swing_mid_time_stop_in_8_12_since_v40(v31_mr_draws: list[StrategyConfig]) -> None:
    """Non-capitulation MR swing_mid time_stop samples n_bars in [8, 12] and reaches both
    ends (D270, widened by D291)."""
    seen: set[object] = set()
    for cfg in _bucket(v31_mr_draws, "swing_mid"):
        ts = _time_stop_params(cfg)
        if _is_capitulation(cfg) or ts is None:
            continue
        assert isinstance(ts.get("n_bars"), int), ts
        assert 8 <= ts["n_bars"] <= 12, ts  # type: ignore[operator]
        seen.add(ts["n_bars"])
    assert seen, "no MR swing_mid time_stop draws sampled"
    assert {8, 12} <= seen, seen


def test_mr_swing_short_time_stop_in_family_box_since_v40(
    v31_mr_draws: list[StrategyConfig],
) -> None:
    """v36 kept swing_short param-less; v40 (D291) retired that: the box is bucket-wide."""
    checked = 0
    for cfg in v31_mr_draws:
        ts = _time_stop_params(cfg)
        if _is_capitulation(cfg) or cfg.dte_bucket == "swing_mid" or ts is None:
            continue
        checked += 1
        assert isinstance(ts.get("n_bars"), int), (cfg.dte_bucket, ts)
        assert 8 <= ts["n_bars"] <= 12, (cfg.dte_bucket, ts)  # type: ignore[operator]
    assert checked > 0, "no non-capitulation MR swing_short time_stop draws sampled"


# ==============================================================================================
# VOLATILITY EVENT (v39 D289)
# ==============================================================================================


def test_v39_ve_never_emits_event_passed(ve_draws: list[StrategyConfig]) -> None:
    """The fallback-mode truncation is gone: no ve config carries event_passed_exit (D289)."""
    for cfg in ve_draws:
        assert "event_passed_exit" not in _exit_ids(cfg), cfg.name


def test_v39_ve_time_stop_required_with_u47(ve_draws: list[StrategyConfig]) -> None:
    """time_stop is the required ve hold with n_bars in U[4,7], beside iv_crush_exit (D289)."""
    for cfg in ve_draws:
        ids = _exit_ids(cfg)
        assert "time_stop" in ids, cfg.name
        assert "iv_crush_exit" in ids, cfg.name
        params = next(e.params for e in cfg.exits if e.id == "time_stop")
        assert params.get("n_bars") in (4, 5, 6, 7), (cfg.name, params)


def test_v39_ve_emission_stays_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot, ve_draws: list[StrategyConfig]
) -> None:
    for cfg in ve_draws[:150]:
        result = validate(cfg, grammar, registry)
        assert result.valid, (cfg.name, result.errors)


def test_v39_ve_veto_sampled_when_registry_serves_rtr(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """ref_trailing_return rides the generic ~0.5 veto draw in ve cells: op ">", threshold in
    [-0.03, -0.02], reference SPY/QQQ, window 3..10, every axis sampled (D289)."""
    reg = rtr_registry(registry)
    cfgs = sample_configs(grammar, reg, n=600, hypothesis="volatility_event")
    refs: set[str] = set()
    windows: set[int] = set()
    thresholds: list[float] = []
    for cfg in cfgs:
        veto = next(
            (
                s
                for s in cfg.signals
                if s.role == "regime_filter" and s.indicators == ("ref_trailing_return",)
            ),
            None,
        )
        if veto is None:
            continue
        assert veto.params.get("op") == ">", veto.params
        thr = veto.params.get("threshold")
        assert isinstance(thr, float), veto.params
        assert -0.03 <= thr <= -0.02, veto.params
        ref = veto.params.get("reference")
        assert ref in ("SPY", "QQQ"), veto.params
        win = veto.params.get("window")
        assert isinstance(win, int), veto.params
        assert 3 <= win <= 10, veto.params
        refs.add(str(ref))
        windows.add(win)
        thresholds.append(thr)
        assert validate(cfg, grammar, reg).valid, cfg.name
    share = len(thresholds) / len(cfgs)
    assert 0.20 < share < 0.60, f"ve veto share {share:.2f} (C1 guard eats some draws)"
    assert refs == {"SPY", "QQQ"}, refs
    assert len(windows) >= 4, windows
    assert len(set(thresholds)) > 10


def test_v39_ve_veto_absent_without_registry_support(ve_draws: list[StrategyConfig]) -> None:
    """Registry not serving ref_trailing_return means an empty ve veto pool (D289)."""
    for cfg in ve_draws[:200]:
        assert all(s.indicators != ("ref_trailing_return",) for s in cfg.signals), cfg.name


def test_v39_iv_term_slope_range_loosened(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The directional threshold axis reaches the x1.3-loosened floor 0.0077 (D289)."""
    lows: list[float] = []
    for cfg in sample_configs(
        grammar, its_registry(registry), n=800, hypothesis="volatility_event"
    ):
        d = _directional(cfg)
        if d.indicators[0] != "iv_term_slope":
            continue
        thr = d.params.get("threshold")
        if isinstance(thr, float):
            lows.append(thr)
    assert lows, "no iv_term_slope directional draws"
    assert min(lows) < 0.0095, f"loosened region unsampled: min={min(lows):.4f}"
    assert max(lows) <= 0.04 + 1e-9
    assert min(lows) >= 0.0077 - 1e-9


def test_v39_other_hypotheses_exits_untouched(mr_draws: list[StrategyConfig]) -> None:
    """The ve schema edit must not leak: MR keeps its ~0.65 timer share (D289)."""
    assert 0.60 < _share(mr_draws[:600], "time_stop") < 0.70


# ==============================================================================================
# EVENT MOMENTUM (H2 D109; retired D328; the D268 no-earnings exclusion)
# ==============================================================================================


@pytest.mark.parametrize(
    ("indicator", "role", "skippable"),
    [
        ("sue", "directional", False),
        ("sue", "regime_filter", True),
        ("days_since_earnings", "regime_filter", False),
        ("days_since_earnings", "directional", True),
    ],
)
def test_event_momentum_threshold_roles(indicator: str, role: str, skippable: bool) -> None:
    """sue drives direction only; days_since_earnings is the post-event timing gate only (D109)."""
    assert bool(is_threshold_skippable(indicator, role)) is skippable


def test_sue_directional_fires_on_a_strong_positive_surprise() -> None:
    params = sample_threshold_params("sue", "directional", random.Random(0))
    assert params["op"] == ">"
    assert isinstance(params["threshold"], float)
    assert params["threshold"] > 0.0


def test_days_since_earnings_regime_is_a_post_event_window() -> None:
    """Fire WITHIN N trading days after the print, the PEAD edge (D109)."""
    params = sample_threshold_params("days_since_earnings", "regime_filter", random.Random(0))
    assert params["op"] == "<"
    assert 3.0 <= float(params["threshold"]) <= 10.0  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("indicator", "days", "cls"), [("sue", 10, "medium_lookback"), ("days_since_earnings", 5, None)]
)
def test_event_momentum_horizons(indicator: str, days: int, cls: str | None) -> None:
    """~10 td post-earnings drift is medium_lookback; the timing gate is near-instant (D109)."""
    assert signal_horizon_days(indicator) == days
    if cls is not None:
        assert horizon_class(indicator) == cls


def test_event_momentum_dte_target_is_k_times_drift_window() -> None:
    horizon = signal_horizon_days("sue")
    targets = {_dte_target("event_momentum", "sue", random.Random(s)) for s in range(60)}
    assert targets == {float(k * horizon) for k in _K_MULTIPLIERS}


def test_event_momentum_retired_not_samplable(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """v47 (D328) retired event_momentum into DISABLED_HYPOTHESES: forcing it is an error."""
    space = build_search_space(grammar, registry)
    with pytest.raises(SamplerError):
        sampler_mod.sample_config(
            space, registry, random.Random(0), forced_hypothesis="event_momentum"
        )


def test_no_earnings_set_covers_the_flagged_etfs_but_not_real_companies() -> None:
    """D268: the stopgap exclusion is a superset of the tier-1 ETFs and spares companies."""
    assert _TIER_1_ETF_UNDERLYINGS <= _NO_EARNINGS_UNDERLYINGS
    for etf in ("SOXL", "SOXX", "TQQQ", "SQQQ", "GLD", "TLT", "UVXY", "VIX", "SMH", "XLK", "XLE"):
        assert etf in _NO_EARNINGS_UNDERLYINGS, etf
    for company in ("RTX", "AAPL", "NVDA", "JPM", "COIN", "MSTR"):
        assert company not in _NO_EARNINGS_UNDERLYINGS, company


def test_pick_underlying_excludes_no_earnings_for_earnings_gated_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hermetic: an earnings-gated draw never lands on a no-earnings name, and the dormant
    (no-manifest) path is pinned explicitly so the live box's coverage cannot mask it (D268)."""
    pool = ("AAPL", "RTX", "SOXL", "XLK", "SPY", "TQQQ")
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    monkeypatch.setattr(sampler_mod, "_load_earnings_covered_symbols", lambda: ())
    drawn = {
        _pick_underlying(random.Random(s), "event_momentum", ("days_since_earnings",))
        for s in range(300)
    }
    assert drawn <= {"AAPL", "RTX"}, drawn
    assert "RTX" in drawn
    unfiltered = {_pick_underlying(random.Random(s), "mean_reversion", ()) for s in range(300)}
    assert unfiltered & {"SOXL", "XLK", "SPY", "TQQQ"}, unfiltered


# ==============================================================================================
# CROSS-CUTTING: census retirements (v33 D276, v34 D278)
# ==============================================================================================


@pytest.mark.parametrize("indicator", ["days_to_nfp", "days_to_cpi"])
def test_v33_macro_countdown_regime_thresholds_inside_ceiling(indicator: str) -> None:
    """Monthly-event countdowns stay inside the [7, 30] window, op "<" (D276)."""
    for seed in range(200):
        params = sample_threshold_params(indicator, "regime_filter", random.Random(seed))
        assert params["op"] == "<"
        assert 7.0 <= params["threshold"] <= 30.0, (indicator, params)  # type: ignore[operator]


def test_v33_option_momentum_not_in_any_directional_pool(v33_space: SearchSpace) -> None:
    """Structurally dead (47/wk, median 5 OOS trades, ~0 conversions) (D276)."""
    for hyp, pool in v33_space.directional_indicators_by_hypothesis.items():
        assert "option_momentum" not in pool, hyp


def test_v33_gamma_flip_not_a_mean_reversion_directional(v33_space: SearchSpace) -> None:
    """gamma_flip-as-directional inside MR is dead in every gate; call_wall stays (D276)."""
    mr = v33_space.directional_indicators_by_hypothesis["mean_reversion"]
    assert "gamma_flip_distance_pct" not in mr
    assert "call_wall_distance_pct" in mr


def test_v33_gamma_flip_r1_gate_superseded_by_v34(v33_space: SearchSpace) -> None:
    """v33 kept the D107 R1 gate on the addendum's evidence; v34 retired it (D276, D278)."""
    assert (
        "gamma_flip_distance_pct" not in v33_space.regime_indicators_by_hypothesis["mean_reversion"]
    )


def test_v34_gamma_flip_not_in_any_regime_pool(v33_space: SearchSpace) -> None:
    """12,088 uses at 0.1% component / 79% WF=0.0 across EVERY pairing (D278)."""
    for hyp, pool in v33_space.regime_indicators_by_hypothesis.items():
        assert "gamma_flip_distance_pct" not in pool, hyp


def test_v34_gamma_flip_survives_as_a_vol_event_directional(v33_space: SearchSpace) -> None:
    """The retirement is gate-scoped: the C2 dealer-family DIRECTIONAL use in ve stays (D278)."""
    assert (
        "gamma_flip_distance_pct"
        in v33_space.directional_indicators_by_hypothesis["volatility_event"]
    )


def test_v33_vol_event_regime_pool_excludes_pre_earnings_setup(v33_space: SearchSpace) -> None:
    """~450 configs/wk at 91-100% dead across every ve directional; the rest of R3 stays (D276)."""
    ve_pool = v33_space.regime_indicators_by_hypothesis["volatility_event"]
    assert "pre_earnings_setup" not in ve_pool
    assert "days_to_earnings" in ve_pool


def test_v33_r3_predicate_still_accepts_pre_earnings_setup() -> None:
    """Hard rule #1: emission-side retirement only; the §3.5 R3 predicate still accepts it."""
    assert "pre_earnings_setup" in _R3_EVENT_PROXIMITY_INDICATORS


def test_v34_r1_r2_predicates_still_accept_gamma_flip_gates() -> None:
    """Hard rule #1: both rule predicates keep accepting what the sampler no longer draws."""
    assert _R1_GAMMA_REGIME_INDICATOR == "gamma_flip_distance_pct"
    assert "gamma_flip_distance_pct" in _R2_TREND_CONTINUATION_REGIME_INDICATORS


def test_v34_dsj_gamma_flip_veto_filter_kept_as_defense_in_depth() -> None:
    """The v33 pairing filter stays live although gamma_flip gates are no longer drawn (D278)."""

    class _FakeSpace:
        regime_veto_indicators_by_hypothesis: ClassVar[dict[str, tuple[str, ...]]] = {
            "trend_continuation": ("days_since_jump",)
        }
        regime_veto_family_by_id: ClassVar[dict[str, str]] = {"days_since_jump": "volatility"}
        indicators_by_family: ClassVar[dict[str, tuple[str, ...]]] = {"volatility": ()}

    def gated(indicator: str, threshold: float) -> list[SignalSpec]:
        return [
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=(indicator,),
                params={"threshold": threshold, "op": ">"},
            )
        ]

    space = _FakeSpace()
    gamma = gated("gamma_flip_distance_pct", 0.0)
    hurst = gated("hurst", 0.5)
    assert _eligible_regime_vetoes(gamma, space, "trend_continuation") == ()  # type: ignore[arg-type]
    assert _eligible_regime_vetoes(hurst, space, "trend_continuation") == (  # type: ignore[arg-type]
        "days_since_jump",
    )


# ==============================================================================================
# CROSS-CUTTING: universe and tier stamps (v34 D278, v41/v42 D292/D294)
# ==============================================================================================

_UNTRADEABLE_NAMES = (
    "IWM SLB BKNG BRK.B SOXX LLY GS MSTR ASML COST AAL ADBE AMZN ARKK BSX DIA DVN EEM EFA "
    "GE INTC KO LRCX LUV MS MSFT NEM NKE PEP TXN UNG UPS VZ WFC XBI XLF XLI XLP XLV XOM"
)
_UNTRADEABLE = frozenset(_UNTRADEABLE_NAMES.split())


def test_v34_untradeable_names_never_drawn(grammar: Grammar, v33_reg: RegistrySnapshot) -> None:
    """BKNG/BRK.B are live tier-2 names whose contracts never clear the spread gate (D278)."""
    drawn = {c.underlying for c in sample_configs(grammar, v33_reg, n=500) if c.underlying}
    assert drawn
    assert not drawn & {"BKNG", "BRK.B"}, sorted(drawn & {"BKNG", "BRK.B"})


def test_v34_untradeable_exclusion_applies_to_the_pool_itself() -> None:
    """Pool-level pin: BKNG/BRK.B (D278) + SOXX/LLY/GS/MSTR (D286) + ASML/COST (D292) + the
    30-name yield-audit cohort (D309) + IWM/SLB (v50, prereg 8eaa7e4aca93)."""
    assert _UNTRADEABLE == _STRUCTURALLY_UNTRADEABLE_UNDERLYINGS


def test_v41_single_name_stamps_true_tier(any_draws: list[StrategyConfig]) -> None:
    """A single-name config's tier is the underlying's TRUE tier from the tiered export (D292)."""
    seen_t3 = seen_t2 = 0
    for cfg in any_draws[:1500]:
        if cfg.underlying is None:
            continue
        if cfg.underlying in UNIVERSE_TIER3_SNAPSHOT_2026_07_20:
            assert cfg.tier == 3, (cfg.underlying, cfg.tier)
            seen_t3 += 1
        else:
            assert cfg.tier == 2, (cfg.underlying, cfg.tier)
            seen_t2 += 1
    assert seen_t3 >= 100, f"too few tier-3 single-name draws: {seen_t3}"
    assert seen_t2 >= 50, f"too few tier-2 single-name draws: {seen_t2}"


def test_xsect_stamps_tier2_since_v42(xsect_draws: list[StrategyConfig]) -> None:
    """Every rank-combiner config stamps tier=2; the v41 tier=3 share bought duplicate books at
    1.5x costs (D294)."""
    xsect = [c for c in xsect_draws if c.combiner.type == "cross_sectional_rank"]
    assert len(xsect) >= 300, f"too few xsect draws: {len(xsect)}"
    assert all(c.tier == 2 for c in xsect), Counter(c.tier for c in xsect)


def test_v41_tier_dormant_without_tiered_export(
    grammar: Grammar, registry: RegistrySnapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty tier-3 set (old-shape export, D033 fallback) stamps everything tier=2 (D292)."""
    monkeypatch.setattr(sampler_mod, "_tier3_symbols", frozenset)
    for cfg in sample_configs(grammar, registry, n=600, rank_share=1.0):
        assert cfg.tier == 2, (cfg.name, cfg.underlying, cfg.tier)


def test_v41_asml_cost_never_drawn(any_draws: list[StrategyConfig]) -> None:
    """The D292 rider: ASML/COST join the structural exclusion, the pool stays wide."""
    drawn = {c.underlying for c in any_draws if c.underlying}
    assert "ASML" not in drawn
    assert "COST" not in drawn
    assert len(drawn) > 60, f"pool unexpectedly small: {len(drawn)}"


def test_v41_universe_fingerprint_carries_tier_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fingerprint must move when the tier SPLIT moves on the same union (D292 H-3)."""
    with_t3 = sampler_mod.universe_fingerprint()
    monkeypatch.setattr(sampler_mod, "_tier3_symbols", frozenset)
    assert with_t3 != sampler_mod.universe_fingerprint()


# ==============================================================================================
# CROSS-CUTTING: freeze-programme retirements (v47 D328, v52 D328/D340, v55 D366)
# ==============================================================================================


def test_relative_value_and_event_momentum_disabled(v47_configs: list[StrategyConfig]) -> None:
    hyps = {cfg.hypothesis for cfg in v47_configs}
    assert "relative_value" not in hyps
    assert "event_momentum" not in hyps


@pytest.mark.parametrize("population", ["v47_configs", "v52_configs"])
def test_no_single_name_trend_or_mr_remains(
    population: str, request: pytest.FixtureRequest
) -> None:
    """v47 retired single-name trend/MR with capitulation as the sole exemption; v52 withdrew it
    (0 components in 603 decided), so the axis is empty on the serving registry too (D328)."""
    for cfg in request.getfixturevalue(population):
        if cfg.hypothesis not in ("trend_continuation", "mean_reversion"):
            continue
        assert cfg.combiner.type == "cross_sectional_rank", cfg.name


@pytest.mark.parametrize("population", ["v47_configs", "v52_configs"])
def test_xsect_trend_and_mr_preserved(population: str, request: pytest.FixtureRequest) -> None:
    """The prune must not cost xsect supply: the prereg's falsifier is a conversion drop (D328)."""
    axes = Counter(
        (cfg.hypothesis, "xsect" if cfg.combiner.type == "cross_sectional_rank" else "named")
        for cfg in request.getfixturevalue(population)
    )
    assert axes[("trend_continuation", "xsect")] > 0
    assert axes[("mean_reversion", "xsect")] > 0


def test_retired_single_name_is_counted_as_a_rejection(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    counter: Counter[str] = Counter()
    list(
        enumerate_candidates(
            grammar,
            registry,
            seed=0,
            max_candidates=500,
            rank_combiner_share=_XSECT_SHARE,
            rejection_counter=counter,
        )
    )
    assert counter["retired_single_name"] > 0


def test_momentum_is_no_longer_an_mr_directional(v52_configs: list[StrategyConfig]) -> None:
    """The emission proof the v52 prereg predicts: zero momentum MR configs on a registry that
    serves momentum (D328/D340)."""
    offenders = [
        cfg.name
        for cfg in v52_configs
        if cfg.hypothesis == "mean_reversion" and _directional(cfg).indicators[0] == "momentum"
    ]
    assert offenders == []


def test_the_two_carve_out_tables_are_empty() -> None:
    """Both loosenings are withdrawn, not bypassed: a bypassed carve-out is a re-admission
    waiting for a one-line edit (D328)."""
    assert _C2_HYPOTHESIS_EXTRA_IDS == {}
    assert frozenset() == _R1_GATE_EXEMPT_DIRECTIONALS


def test_every_mr_config_carries_a_regime_gate(v52_configs: list[StrategyConfig]) -> None:
    """R1 is whole again: the capitulation bare-drop was the only gate-less MR arm (D328)."""
    for cfg in v52_configs:
        if cfg.hypothesis != "mean_reversion":
            continue
        assert any(s.role == "regime_filter" for s in cfg.signals), cfg.name


def test_the_share_constant_is_zero() -> None:
    """The v55 retirement itself, pinned so restoring it cannot be a silent edit (D366)."""
    assert _VIX_CONDITIONER_SHARE == 0.0


def test_no_config_carries_the_conditioner_on_a_serving_registry(
    v55_configs: list[StrategyConfig],
) -> None:
    """The emission proof, keyed on the conditioner's SIGNAL ID (D366)."""
    carriers = [c for c in v55_configs if any(s.id == "sig_vix_conditioner" for s in c.signals)]
    assert not carriers, f"{len(carriers)} configs still carry a sig_vix_conditioner signal"


def test_no_hurst_vix_double_gate_survives(v55_configs: list[StrategyConfig]) -> None:
    """The specific pair Crucible refuted, asserted directly rather than via the id (D366)."""
    doubles = [c for c in v55_configs if "hurst" in _gates(c) and _VIX_CONDITIONER_ID in _gates(c)]
    assert not doubles, f"{len(doubles)} hurst x vix double-gates survived the v55 retirement"


def test_vix_is_still_reachable_as_a_primary_regime_gate(
    v55_configs: list[StrategyConfig],
) -> None:
    """The retirement is scoped to the CONDITIONER, not to the indicator (D366)."""
    primaries = [
        c
        for c in v55_configs
        if any(s.id == "sig_regime" and s.indicators[0] == _VIX_CONDITIONER_ID for s in c.signals)
    ]
    assert primaries, "vix_term_slope disappeared as a PRIMARY gate; the retirement over-reached"
