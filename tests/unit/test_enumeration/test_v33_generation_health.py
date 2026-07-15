"""v33 generation-health change set — Crucible's 2026-07-15 addendum + the
late-published 07-13/07-14 relays (D276; `docs/proposals/v33-generation-health.md`).

Enumeration-policy bump (`docs/tasks/grammar-change.md` classification #2/#3;
`rules:` text untouched — every retirement is EMISSION-side, so previously
submitted lineages stay grammar-valid under the unchanged predicates). Items:

  1. resid_vix CONFIRMED-region concentration (their 07-13 followup: three
     pipeline-native residual_momentum configs pass the WF gate in-book):
     window [70,160] / skip [7,21] / percentile threshold (0.65,0.85); regime
     pool PINNED to {vix_term_slope, hurst}; vix gate threshold [0.1,0.7],
     hurst gate percentile [0.40,0.50]; combiner PINNED cross_sectional_rank
     (monthly, rank_k {5,10}, long_only-biased 0.75).
  2. days_to_nfp / days_to_cpi regime_range (7,60) → (7,30): ceilings are
     35/34 (monthly countdowns), so ~42% of the old draws were provably inert.
  4. pre_earnings_setup retired from vol_event's EMISSION pool (~450/wk at
     91-100%% dead); R3 still ACCEPTS it (validity unchanged).
  5. the trend days_since_jump veto never stacks on a gamma_flip_distance_pct
     primary gate (~300/wk at 93-98%% dead); other pairings keep the veto —
     the resid x vix x dsj dual-gate arm is explicitly requested supply.
  6. option_momentum retired from DIRECTIONAL emission (100%% dead, a month
     post-fix).
  7. gamma_flip_distance_pct retired as a MEAN_REVERSION directional (~100/wk
     dead); it remains an R1 REGIME gate.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import IndicatorMetadata, RegistrySnapshot

from forge.enumeration.indicator_thresholds import sample_threshold_params
from forge.enumeration.sampler import _directional_signal_params, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(
        _REPO_ROOT / "config" / "grammar.yaml",
        archive_dir=_REPO_ROOT / "config" / "grammar_archive",
    )


@pytest.fixture
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


def _meta(
    ind_id: str,
    family: str,
    *,
    version: int = 1,
    lookback: int = 0,
    rank_coherent: bool = False,
    market_wide: bool = False,
) -> IndicatorMetadata:
    return IndicatorMetadata(
        id=ind_id,
        version=version,
        family=family,
        lookback=lookback,
        params_schema={},
        rank_per_name_coherent=rank_coherent,
        market_wide_by_design=market_wide,
    )


def _v33_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + every id the v33 items touch, families/flags exactly
    as the live registry publishes them (mirrors the _v18/_v25/_v27 helpers)."""
    extra = (
        _meta("residual_momentum", "trend", lookback=504, rank_coherent=True),
        _meta("vix_term_slope", "macro", market_wide=True),
        _meta("days_since_jump", "volatility", version=3, lookback=252, rank_coherent=True),
        _meta("gamma_flip_distance_pct", "dealer_positioning", lookback=1),
        _meta("option_momentum", "smart_money", lookback=147),
        _meta("pre_earnings_setup", "calendar", version=2, lookback=252),
        _meta("days_to_nfp", "calendar"),
        _meta("days_to_cpi", "calendar"),
    )
    return base.model_copy(update={"indicators": (*base.indicators, *extra)})


# --- item 2: days_to_nfp / days_to_cpi threshold prior inside the ceiling -----


@pytest.mark.parametrize("indicator_id", ["days_to_nfp", "days_to_cpi"])
def test_v33_macro_countdown_regime_thresholds_inside_ceiling(indicator_id: str) -> None:
    """Monthly-event countdowns ceiling at 35/34 (max inter-event gap over
    2018-2026); the old (7,60) prior put ~42%% of `op="<"` gates above the
    ceiling = always-true no-ops. (7,30) mirrors the already-safe days_to_opex."""
    for seed in range(200):
        params = sample_threshold_params(indicator_id, "regime_filter", random.Random(seed))
        assert params["op"] == "<"
        assert 7.0 <= params["threshold"] <= 30.0, (indicator_id, params)


# --- item 6: option_momentum retired from directional emission ----------------


def test_v33_option_momentum_not_in_any_directional_pool(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """100%% structurally dead (47/wk, median 5 OOS trades, ~0 conversions in a
    month at the v19 min_months fix) — retired from EVERY hypothesis's
    directional emission. smart_money stays a C2 trend family (the X2 kelly
    chain feature `expected_value_estimator` is untouched)."""
    space = build_search_space(grammar, _v33_registry(registry))
    for hyp, pool in space.directional_indicators_by_hypothesis.items():
        assert "option_momentum" not in pool, hyp


# --- item 7: gamma_flip retired as a MEAN_REVERSION directional ---------------


def test_v33_gamma_flip_not_a_mean_reversion_directional(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """gamma_flip-as-directional inside mean_reversion is dead in every gate
    combination Crucible sees (~100/wk, 94-97%% WF=0). Retired from MR's
    directional pool ONLY — other dealer directionals (walls, gex) stay."""
    space = build_search_space(grammar, _v33_registry(registry))
    assert (
        "gamma_flip_distance_pct"
        not in space.directional_indicators_by_hypothesis["mean_reversion"]
    )
    assert "call_wall_distance_pct" in space.directional_indicators_by_hypothesis["mean_reversion"]


def test_v33_gamma_flip_r1_gate_superseded_by_v34(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """v33 kept the D107 R1 gate on the addendum's evidence ("single-gated MR
    cells are not in the dead table"); the census #2 (D278/v34) then measured
    the gate dead at scale in EVERY pairing (12,088 uses, 0.1% component) and
    retired it from emission globally — the v34 pool tests own the pin; this
    records the supersession so the v33 assumption isn't re-derived."""
    space = build_search_space(grammar, _v33_registry(registry))
    assert "gamma_flip_distance_pct" not in space.regime_indicators_by_hypothesis["mean_reversion"]


# --- item 4: pre_earnings_setup retired from vol_event EMISSION ---------------


def test_v33_vol_event_regime_pool_excludes_pre_earnings_setup(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """~450 configs/wk at 91-100%% dead across every ve directional (the gate
    opens a few quiet-RV days per name-quarter; ANDed with any directional
    threshold it starves below the trade floor; ve conversion 0.1%%). Retired
    from the SAMPLER pool; the other R3 event-proximity gates remain."""
    space = build_search_space(grammar, _v33_registry(registry))
    ve_pool = space.regime_indicators_by_hypothesis["volatility_event"]
    assert "pre_earnings_setup" not in ve_pool
    assert "days_to_earnings" in ve_pool  # the rest of R3 unchanged


def test_v33_r3_predicate_still_accepts_pre_earnings_setup() -> None:
    """EMISSION-side retirement only (hard rule #1): the §3.5 R3 predicate's
    accepted-indicator set is untouched, so the existing submitted lineage
    stays grammar-valid."""
    from forge.grammar.custom_predicates import _R3_EVENT_PROXIMITY_INDICATORS

    assert "pre_earnings_setup" in _R3_EVENT_PROXIMITY_INDICATORS


# --- item 5: dsj veto never stacks on a gamma_flip primary gate ---------------


# test_v33_trend_dsj_veto_never_on_gamma_flip_gate was superseded by v34/D278:
# gamma_flip is no longer emittable as a PRIMARY gate at all, so the emission
# path can't exercise the pairing filter. The filter itself is kept as
# defense-in-depth against re-admission and is unit-pinned in
# test_v34_census_retirements.py::test_v34_dsj_gamma_flip_veto_filter_kept_as_defense_in_depth.


def test_v33_trend_dsj_veto_survives_on_other_gates(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Only the gamma_flip pairing dies: the dsj veto still stacks on the other
    (non-volatility-family, C1-eligible) trend gates — the resid x vix x dsj
    dual-gate arm is explicitly requested supply (their 07-13 followup)."""
    reg = _v33_registry(registry)
    space = build_search_space(grammar, reg)
    seen_dsj_veto = 0
    for seed in range(600):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        gates = [s for s in cfg.signals if s.role == "regime_filter"]
        if any("days_since_jump" in g.indicators for g in gates):
            seen_dsj_veto += 1
            assert gates[0].indicators[0] != "gamma_flip_distance_pct", cfg.name
    assert seen_dsj_veto > 0


# --- item 1: resid_vix confirmed-region concentration -------------------------


def test_v33_resid_momentum_window_skip_confirmed_region() -> None:
    """Formation knobs narrowed from the exploration bounds (63-252 / 0-21) to
    the confirmed-converter region: window [70,160] (converters 73/126/147),
    skip [7,21] (7/15/21; skip<7 never converted)."""
    for seed in range(200):
        params = _directional_signal_params("residual_momentum", random.Random(seed))
        assert 70 <= params["window"] <= 160, params
        assert 7 <= params["skip"] <= 21, params


def test_v33_resid_momentum_percentile_threshold_narrowed() -> None:
    """Directional percentile (0.60,0.90) → (0.65,0.85): converters carried
    0.71-0.82; the region's edges never converted. Window stays 252."""
    for seed in range(200):
        params = sample_threshold_params("residual_momentum", "directional", random.Random(seed))
        assert params.get("use_percentile") is True
        assert params.get("percentile_window") == 252
        assert 0.65 <= params["threshold"] <= 0.85, params


def test_v33_resid_regime_pool_pinned_to_confirmed_arms(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Density lever: every resid draw spends its gate on one of the two
    CONFIRMED arms (vix_term_slope — the WF carriers; hurst — the cpcv
    carrier). Other R2 gates keep their full pools on other directionals."""
    reg = _v33_registry(registry)
    space = build_search_space(grammar, reg)
    seen = {"vix_term_slope": 0, "hurst": 0}
    for seed in range(800):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators[0] != "residual_momentum":
            continue
        gates = [s for s in cfg.signals if s.role == "regime_filter"]
        primary = gates[0].indicators[0]
        assert primary in seen, cfg.name
        seen[primary] += 1
    assert seen["vix_term_slope"] > 0
    assert seen["hurst"] > 0


def test_v33_resid_gate_thresholds_in_confirmed_ranges(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """vix_term_slope gate [0.1,0.7] (converters 0.22/0.66; the old (0.0,2.0)
    wasted mass above the region), hurst gate percentile [0.40,0.50]
    (the cpcv carrier's p41-p46 neighborhood). Both scoped to the resid
    directional — every other pairing keeps the table's ranges."""
    reg = _v33_registry(registry)
    space = build_search_space(grammar, reg)
    for seed in range(800):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators[0] != "residual_momentum":
            continue
        g = next(s for s in cfg.signals if s.role == "regime_filter")
        if g.indicators[0] == "vix_term_slope":
            assert g.params["op"] == ">"
            assert 0.1 <= g.params["threshold"] <= 0.7, cfg.name
        else:
            assert g.params["op"] == ">"
            assert g.params.get("use_percentile") is True
            assert 0.40 <= g.params["threshold"] <= 0.50, cfg.name


def test_v33_resid_structure_pinned_to_rank_monthly(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every converter is monthly cross_sectional_rank (the confluence config
    nearest the probe trades 3 times in 8.5y — the combiner is load-bearing).
    Pinned: combiner xsect-rank, monthly rebalance, rank_k {5,10};
    direction_mode long_only-BIASED (2 of 3 WF passes; long_short explorable)."""
    reg = _v33_registry(registry)
    space = build_search_space(grammar, reg)
    modes = {"long_only": 0, "long_short": 0}
    for seed in range(800):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators[0] != "residual_momentum":
            continue
        assert cfg.combiner.type == "cross_sectional_rank", cfg.name
        assert cfg.combiner.rebalance_frequency == "monthly", cfg.name
        assert cfg.combiner.rank_k in (5, 10), cfg.name
        assert cfg.underlying is None, cfg.name
        modes[cfg.combiner.direction_mode] += 1
    assert modes["long_only"] > modes["long_short"] > 0
