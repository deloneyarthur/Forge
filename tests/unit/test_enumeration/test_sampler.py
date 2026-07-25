"""Unit tests for ``forge.enumeration.sampler``.

The sampler's job is path (a) from the Phase 2 closure plan: produce
grammar-valid ``StrategyConfig``s by construction. These tests pin down
the per-rule conformance + the determinism contract + the
empty-pool / unsamplable-mode edges.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from crucible_contracts import (
    MANDATORY_EXIT_IDS,
    IndicatorMetadata,
    RegistrySnapshot,
    StrategyConfig,
)

from forge.enumeration.iterator import enumerate_candidates
from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar, validate
from forge.grammar.custom_predicates import (
    _C2_HYPOTHESIS_FAMILIES,
    _P2_ENTRY_DTE,
    _P3_DELTA_BAND,
    _P3_DELTA_BAND_OVERRIDES,
    _R1_GAMMA_REGIME_INDICATOR,
    _R1_HURST_REGIME_INDICATOR,
    _R1_IV_RANK_INDICATOR,
    _R1_REALIZED_VOL_REGIME_INDICATOR,
    _R1_RV_RANK_REGIME_INDICATOR,
    _R2_TREND_CONTINUATION_REGIME_INDICATORS,
    _R3_EVENT_PROXIMITY_INDICATORS,
    _S5_HYPOTHESIS_EXITS,
)
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


@pytest.fixture
def rng() -> random.Random:
    return random.Random(0xF09E)


def _sample(grammar: Grammar, registry: RegistrySnapshot, seed: int) -> StrategyConfig:
    space = build_search_space(grammar, registry)
    rng = random.Random(seed)
    return sample_config(space, registry, rng)


# ---------------------------------------------------------------------------
# Smoke + determinism
# ---------------------------------------------------------------------------


def test_sample_returns_strategy_config(
    grammar: Grammar, registry: RegistrySnapshot, rng: random.Random
) -> None:
    space = build_search_space(grammar, registry)
    cfg = sample_config(space, registry, rng)
    assert isinstance(cfg, StrategyConfig)


def test_same_seed_same_config(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """§13.1 prerequisite: identical (space, registry, rng-state) → identical
    config. The sampler is the inner loop that this property depends on."""
    a = _sample(grammar, registry, seed=42)
    b = _sample(grammar, registry, seed=42)
    assert a.config_hash == b.config_hash


def test_different_seeds_usually_differ(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Sanity check: two different seeds shouldn't produce identical configs.
    The space is large enough that collision is statistically negligible."""
    a = _sample(grammar, registry, seed=1)
    b = _sample(grammar, registry, seed=2)
    assert a.config_hash != b.config_hash


def test_equity_hedge_metadata_is_none(
    grammar: Grammar, registry: RegistrySnapshot, rng: random.Random
) -> None:
    """D5: Forge submits pure options; equity_hedge_metadata is set by
    QuantIQ post-promotion, never by Forge."""
    space = build_search_space(grammar, registry)
    cfg = sample_config(space, registry, rng)
    assert cfg.equity_hedge_metadata is None


# ---------------------------------------------------------------------------
# Grammar validity — sample then validate (the path (a) contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", list(range(100)))
def test_sample_is_grammar_valid(grammar: Grammar, registry: RegistrySnapshot, seed: int) -> None:
    """100 deterministic seeds; every sample must pass the Phase 1 validator
    with no rule errors. If this fails, the sampler is leaking invalid
    configs into the iterator and path (a) is broken."""
    space = build_search_space(grammar, registry)
    cfg = sample_config(space, registry, random.Random(seed))
    result = validate(cfg, grammar, registry)
    assert result.valid, f"seed={seed} produced invalid config; errors={result.errors}"


# ---------------------------------------------------------------------------
# §3.5 conformance — spot checks on individual rules
# ---------------------------------------------------------------------------


def test_c2_directional_family_matches_hypothesis(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    by_id = {ind.id: ind for ind in registry.indicators}
    for seed in range(50):
        cfg = _sample(grammar, registry, seed=seed)
        directional = next(s for s in cfg.signals if s.role == "directional")
        directional_family = by_id[directional.indicators[0]].family
        allowed = _C2_HYPOTHESIS_FAMILIES.get(cfg.hypothesis)
        if allowed is None:  # regime_arbitrage allows any family
            continue
        assert directional_family in allowed, (
            f"C2 violated at seed={seed}: hypothesis={cfg.hypothesis} "
            f"directional family={directional_family!r}, allowed={allowed}"
        )


def test_c1_no_duplicate_indicator_families_across_signals(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """C1 holds across ALL signals — directional, regime, chain."""
    by_id = {ind.id: ind for ind in registry.indicators}
    for seed in range(50):
        cfg = _sample(grammar, registry, seed=seed)
        families = [by_id[ind_id].family for sig in cfg.signals for ind_id in sig.indicators]
        assert len(families) == len(set(families)), (
            f"C1 violated at seed={seed}: families={families}"
        )


def test_c4_regime_disjoint_from_directional_in_id(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    for seed in range(50):
        cfg = _sample(grammar, registry, seed=seed)
        directional = next(s for s in cfg.signals if s.role == "directional")
        regime_signals = [s for s in cfg.signals if s.role == "regime_filter"]
        for regime in regime_signals:
            assert directional.indicators[0] != regime.indicators[0], f"C4 violated at seed={seed}"


def test_r1_r2_r3_regime_indicator_when_applicable(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """R1/R2/R3: when the hypothesis pins a regime gate, the sampled regime
    indicator must be from the pinned list."""
    for seed in range(50):
        cfg = _sample(grammar, registry, seed=seed)
        regime = next(s for s in cfg.signals if s.role == "regime_filter")
        regime_id = regime.indicators[0]
        if cfg.hypothesis == "trend_continuation":
            assert regime_id in _R2_TREND_CONTINUATION_REGIME_INDICATORS, (
                f"R2 violated at seed={seed}: regime={regime_id}"
            )
        elif cfg.hypothesis == "mean_reversion":
            # D107 + D150 + D167 + D265: R1 accepts iv_rank, gamma_flip
            # (long-gamma), hurst (mean-reverting H<0.5), rv_rank (cheap realized
            # vol percentile), or realized_vol (D265 absolute calm) — all
            # ranging/calm-admitting gates.
            assert regime_id in {
                _R1_IV_RANK_INDICATOR,
                _R1_GAMMA_REGIME_INDICATOR,
                _R1_HURST_REGIME_INDICATOR,
                _R1_RV_RANK_REGIME_INDICATOR,
                _R1_REALIZED_VOL_REGIME_INDICATOR,
            }, f"R1 violated at seed={seed}: regime={regime_id}"
        elif cfg.hypothesis == "volatility_event":
            assert regime_id in _R3_EVENT_PROXIMITY_INDICATORS, (
                f"R3 violated at seed={seed}: regime={regime_id}"
            )


def test_e1_mandatory_exits_present(grammar: Grammar, registry: RegistrySnapshot) -> None:
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        exit_ids = {e.id for e in cfg.exits}
        missing = MANDATORY_EXIT_IDS - exit_ids
        assert not missing, f"E1 violated at seed={seed}: missing {missing}"


def test_s5_required_exits_present_and_forbidden_absent(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D071 (v3 schema): every config has all required_always exits;
    exactly one from required_from_set (when non-empty); no forbidden."""
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        exit_ids = {e.id for e in cfg.exits}
        rules = _S5_HYPOTHESIS_EXITS[cfg.hypothesis]
        for required_exit in rules["required_always"]:
            assert required_exit in exit_ids, (
                f"S5 required_always {required_exit!r} missing at "
                f"seed={seed} hypothesis={cfg.hypothesis}"
            )
        required_set = set(rules["required_from_set"])
        if required_set:
            chosen = exit_ids & required_set
            assert len(chosen) == 1, (
                f"S5 required_from_set: expected exactly 1 of "
                f"{sorted(required_set)} at seed={seed} "
                f"hypothesis={cfg.hypothesis}, got {sorted(chosen)}"
            )
        for forbidden_exit in rules["forbidden"]:
            assert forbidden_exit not in exit_ids, (
                f"S5 forbidden {forbidden_exit!r} present at seed={seed} "
                f"hypothesis={cfg.hypothesis}"
            )


# ---------------------------------------------------------------------------
# D257 — pair-context exits are inert on non-pairs configs (Crucible handoff
# FORGE_inert_pair_exits_2026-07-08). zscore_reversion_exit / convergence_exit
# read ctx.pair_spread_zscore, populated ONLY by the pairs backtester
# (relative_value). On any other hypothesis they can never fire — dead weight.
# ---------------------------------------------------------------------------
_PAIR_CONTEXT_EXIT_IDS = frozenset({"zscore_reversion_exit", "convergence_exit"})


def test_d257_pair_context_exits_only_on_relative_value(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D257: the two pair-spread exits must be emitted ONLY under relative_value
    (the pairs template). On single-name / xsect hypotheses they are structurally
    inert (0 firings), so the grammar must not declare them there."""
    seen_non_pairs = 0
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.hypothesis != "relative_value":
            seen_non_pairs += 1
            inert = {e.id for e in cfg.exits} & _PAIR_CONTEXT_EXIT_IDS
            assert not inert, (
                f"inert pair-context exit(s) {sorted(inert)} declared on "
                f"hypothesis={cfg.hypothesis} at seed={seed}"
            )
    assert seen_non_pairs > 0, "no non-pairs configs sampled — test is vacuous"


def test_p2_selector_dte_in_entry_window(grammar: Grammar, registry: RegistrySnapshot) -> None:
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        window_low, window_high = _P2_ENTRY_DTE[cfg.dte_bucket]
        assert window_low <= cfg.selector.dte_min, f"P2 dte_min below window at seed={seed}"
        assert cfg.selector.dte_max <= window_high, f"P2 dte_max above window at seed={seed}"


def test_p3_delta_target_in_band(grammar: Grammar, registry: RegistrySnapshot) -> None:
    # D125 (v16) re-pin: the band lookup is hypothesis-aware — trend's
    # swing_long/mid upper edges widened to 0.55, everything else on the base
    # bands. The sampler must respect the per-hypothesis effective band.
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        band_low, band_high = _P3_DELTA_BAND_OVERRIDES.get(cfg.hypothesis, {}).get(
            cfg.dte_bucket, _P3_DELTA_BAND[cfg.dte_bucket]
        )
        assert band_low <= cfg.selector.delta_target <= band_high, (
            f"P3 delta_target out of band at seed={seed}: "
            f"{cfg.selector.delta_target} not in [{band_low}, {band_high}]"
        )


def test_p3_trend_sampler_explores_widened_band(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D125 (v16): forced-trend draws must actually reach the widened region
    (delta > 0.36 in swing_long / > 0.46 in swing_mid) and never exceed 0.55;
    non-trend draws stay inside the base bands. RED-born on v15 (trend
    swing_long capped at 0.35)."""
    space = build_search_space(grammar, registry)
    seen_widened = {"swing_long": False, "swing_mid": False}
    for seed in range(400):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="trend_continuation"
        )
        delta = cfg.selector.delta_target
        assert delta <= 0.55, cfg.name
        if cfg.dte_bucket == "swing_long":
            assert delta >= 0.20, cfg.name
            if delta > 0.36:
                seen_widened["swing_long"] = True
        elif cfg.dte_bucket == "swing_mid":
            assert delta >= 0.30, cfg.name
            if delta > 0.46:
                seen_widened["swing_mid"] = True
    assert all(seen_widened.values()), seen_widened
    # Non-trend control: mean_reversion stays on the base bands everywhere.
    for seed in range(200):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="mean_reversion"
        )
        lo, hi = _P3_DELTA_BAND[cfg.dte_bucket]
        assert lo <= cfg.selector.delta_target <= hi, cfg.name


def test_p4_risk_pct_in_range(grammar: Grammar, registry: RegistrySnapshot) -> None:
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        assert 0.005 <= cfg.sizer.per_trade_risk_pct <= 0.02, (
            f"P4 risk_pct out of range at seed={seed}: {cfg.sizer.per_trade_risk_pct}"
        )


# ---------------------------------------------------------------------------
# D074 (Phase 5) — sizer-mode-specific knob sampling + DTE-within-bucket
# ---------------------------------------------------------------------------


def test_d074_dte_min_strictly_less_than_dte_max(
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> None:
    """D074: dte_min sampled from the low half, dte_max from the high
    half — disjoint, so dte_min < dte_max by construction across seeds."""
    for seed in range(100):
        cfg = _sample(grammar, registry, seed=seed)
        assert cfg.selector.dte_min < cfg.selector.dte_max, (
            f"seed={seed}: dte_min={cfg.selector.dte_min} >= dte_max={cfg.selector.dte_max}"
        )


def test_d074_dte_window_uses_both_halves(
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> None:
    """D074: across 100 seeds for swing_short configs, the sampler should
    produce dte_min values that span the low half of the window and
    dte_max values that span the high half. Catches a regression where
    sampling collapses to the window's extremes only."""
    dte_min_seen: set[int] = set()
    dte_max_seen: set[int] = set()
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.dte_bucket != "swing_short":
            continue
        dte_min_seen.add(cfg.selector.dte_min)
        dte_max_seen.add(cfg.selector.dte_max)
    # swing_short (14, 21) → mid=17 → dte_min ∈ {14..17}, dte_max ∈ {18..21}
    assert dte_min_seen.issubset({14, 15, 16, 17}), f"dte_min outside low half: {dte_min_seen}"
    assert dte_max_seen.issubset({18, 19, 20, 21}), f"dte_max outside high half: {dte_max_seen}"
    # At least 3 distinct values seen across the 300 seeds.
    assert len(dte_min_seen) >= 3, f"dte_min collapsed to {dte_min_seen}"
    assert len(dte_max_seen) >= 3, f"dte_max collapsed to {dte_max_seen}"


def test_d074_kelly_fraction_sampled_for_fractional_kelly_mode(
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> None:
    """fractional_kelly configs sample kelly_fraction in [0.10, 0.50]."""
    seen: set[float] = set()
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.sizer.mode != "fractional_kelly":
            continue
        assert 0.10 <= cfg.sizer.kelly_fraction <= 0.50, (
            f"seed={seed}: kelly_fraction={cfg.sizer.kelly_fraction} out of range"
        )
        seen.add(cfg.sizer.kelly_fraction)
    # Across enough seeds we should see >= 5 distinct kelly values.
    if seen:
        assert len(seen) >= 5, f"kelly_fraction collapsed to {sorted(seen)}"


def test_d074_vol_target_sampled_for_vol_target_mode(
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> None:
    """vol_target configs sample vol_target_annual in [0.10, 0.30]."""
    seen: set[float] = set()
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.sizer.mode != "vol_target":
            continue
        assert 0.10 <= cfg.sizer.vol_target_annual <= 0.30, (
            f"seed={seed}: vol_target_annual={cfg.sizer.vol_target_annual} out of range"
        )
        seen.add(cfg.sizer.vol_target_annual)
    if seen:
        assert len(seen) >= 5, f"vol_target_annual collapsed to {sorted(seen)}"


def test_d074_fixed_risk_pct_keeps_default_kelly_and_vol_target(
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> None:
    """fixed_risk_pct mode doesn't read kelly_fraction or vol_target_annual;
    they stay at defaults (0.25 / 0.20) for those configs."""
    from forge.enumeration import defaults

    for seed in range(150):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.sizer.mode != "fixed_risk_pct":
            continue
        assert cfg.sizer.kelly_fraction == defaults.KELLY_FRACTION
        assert cfg.sizer.vol_target_annual == defaults.VOL_TARGET_ANNUAL


# ---------------------------------------------------------------------------
# §3.5 X1 / X2 — sizer-mode → required chain indicator
# ---------------------------------------------------------------------------


def test_vol_target_chains_realized_vol(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Find a seed where the sampler picks vol_target; assert realized_vol
    is on the strategy."""
    found = False
    for seed in range(200):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.sizer.mode != "vol_target":
            continue
        found = True
        all_indicators = {ind for sig in cfg.signals for ind in sig.indicators}
        assert "realized_vol" in all_indicators, (
            f"X1 violated at seed={seed}: realized_vol missing from {all_indicators}"
        )
    assert found, "no vol_target sample in 200 seeds — sampler may be biased"


def test_fractional_kelly_chains_ev_estimator(grammar: Grammar, registry: RegistrySnapshot) -> None:
    found = False
    for seed in range(200):
        cfg = _sample(grammar, registry, seed=seed)
        if cfg.sizer.mode != "fractional_kelly":
            continue
        found = True
        all_indicators = {ind for sig in cfg.signals for ind in sig.indicators}
        assert "expected_value_estimator" in all_indicators, (
            f"X2 violated at seed={seed}: expected_value_estimator missing"
        )
    assert found, "no fractional_kelly sample in 200 seeds — sampler may be biased"


# ---------------------------------------------------------------------------
# Coverage — sampler reaches every hypothesis given enough seeds
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# D068 — pairs_convergence template params (relative_value zero-trades fix)
# ---------------------------------------------------------------------------


def test_d068_pairs_zscore_directional_emits_template_params() -> None:
    """When the directional indicator is `pairs_zscore`, the sampler must
    populate the template-expected keys (`lookback`, `pvalue_max`,
    `zscore_entry`, `halflife_min`, `halflife_max`) in addition to the
    generic threshold/op. Crucible's pairs_convergence template reads
    these via `signals[0].params.get(...)`."""
    from forge.enumeration.sampler import _directional_signal_params

    params = _directional_signal_params("pairs_zscore", random.Random(0))
    for key in (
        "threshold",
        "op",  # generic threshold predicate (activation date)
        "lookback",
        "pvalue_max",
        "zscore_entry",
        "halflife_min",
        "halflife_max",
    ):
        assert key in params, f"missing pairs template key {key!r} in {params}"


def test_d068_pairs_template_params_ranges() -> None:
    """Sampled values must fall in the documented sampling ranges across
    a sweep of seeds. Catches accidental range tightening regressions."""
    from forge.enumeration.sampler import _directional_signal_params

    for seed in range(50):
        params = _directional_signal_params("pairs_zscore", random.Random(seed))
        # D072 shifted ranges toward the permissive end of D068's sweep to
        # solve zero-trade firing; D103 (v9) tightens pvalue_max + zscore_entry
        # back toward the quality region now that firing is solved (see
        # _sample_pairs_template_params).
        assert params["lookback"] in (126, 189, 252, 378)
        assert 0.02 <= float(params["pvalue_max"]) <= 0.12
        assert 1.0 <= float(params["zscore_entry"]) <= 2.0
        assert params["halflife_min"] in (1, 2, 3, 5)
        assert params["halflife_max"] in (20, 45, 60, 90)
        # The disjoint-range design must hold by construction.
        assert int(params["halflife_min"]) < int(params["halflife_max"])  # type: ignore[arg-type]


def test_d068_pairs_template_params_deterministic_under_same_rng() -> None:
    """Same seed → same params. Required by hard rule #6."""
    from forge.enumeration.sampler import _directional_signal_params

    a = _directional_signal_params("pairs_zscore", random.Random(2026))
    b = _directional_signal_params("pairs_zscore", random.Random(2026))
    assert a == b


def test_d068_non_pairs_indicator_does_not_get_template_params() -> None:
    """Only `pairs_zscore` gets the template-specific keys; other
    directional indicators keep the generic threshold/op shape so
    the dispatch doesn't accidentally pollute unrelated signals."""
    from forge.enumeration.sampler import _directional_signal_params

    for indicator_id in ("rsi_2", "ema_50", "momentum_252", "vix_level"):
        params = _directional_signal_params(indicator_id, random.Random(42))
        for forbidden_key in ("lookback", "pvalue_max", "zscore_entry"):
            assert forbidden_key not in params, (
                f"unexpected pairs key {forbidden_key!r} on {indicator_id!r}"
            )


# ---------------------------------------------------------------------------
# D103 (v9) — pairs quality-bias: tighten cointegration + divergence entry
# ---------------------------------------------------------------------------


def test_d103_pairs_quality_bias_tightens_pvalue_and_zscore_entry() -> None:
    """v9/D103 biases relative_value enumeration toward the higher-Sharpe
    region of its config space, now that v5-v8 solved firing (current-grammar
    relative_value fires ~77%, but median traded Sharpe was ~-0.085, failing
    walk_forward_sharpe_median / cpcv_sharpe_p25).

    Evidence (current-grammar gated relative_value, 2026-06-04):
      - zscore_entry >= 1.0 -> median Sharpe +0.072 vs -0.177 below 1.0;
      - pvalue_max <= 0.14 -> +0.023 vs -0.086 above.

    So every sampled pairs config must enter on a larger divergence
    (zscore_entry >= 1.0) and require stronger cointegration
    (pvalue_max <= 0.12) than D072's fire-chasing ranges. This is a
    TIGHTENING of enumeration scope (hard rule #3/#4: never loosens
    Crucible's gate)."""
    from forge.enumeration.sampler import _sample_pairs_template_params

    for seed in range(200):
        params = _sample_pairs_template_params(random.Random(seed))
        assert float(params["zscore_entry"]) >= 1.0, params
        assert float(params["pvalue_max"]) <= 0.12, params


def test_d105_pairs_lookback_capped_at_280() -> None:
    """v10/D105: the rv lookback > 280 band is confirmed dead — post-rv-fix
    those configs run and trade properly and went 0-for-155 with best WF 0.19,
    while all 7 rv components sit at lookback <= 252. The 378 option (25% of
    rv enumeration) is dropped; the surviving choices stay un-renormalized
    otherwise."""
    from forge.enumeration.sampler import _sample_pairs_template_params

    seen: set[int] = set()
    for seed in range(300):
        params = _sample_pairs_template_params(random.Random(seed))
        lookback = int(params["lookback"])  # type: ignore[call-overload]
        assert lookback <= 280, params
        seen.add(lookback)
    assert seen == {126, 189, 252}


def _count_picks(hypothesis: str, regimes: tuple[str, ...], weights, *, seed: int, n: int) -> dict:
    from forge.enumeration.sampler import _pick_regime

    rng = random.Random(seed)
    counts: dict[str, int] = {}
    for _ in range(n):
        r = _pick_regime(hypothesis, regimes, rng, weights)
        counts[r] = counts.get(r, 0) + 1
    return counts


def test_d103_pick_regime_favors_high_weight_for_relative_value() -> None:
    """The curated hypothesis tilts toward the high-weight regime gate but the
    D067 floor keeps the low-weight gates explorable (never starved to zero)."""
    regimes = ("rsi_2", "put_call_flow", "amihud")
    weights = {"put_call_flow": 0.9, "rsi_2": 0.01, "amihud": 0.01}
    counts = _count_picks("relative_value", regimes, weights, seed=0, n=2000)
    assert counts["put_call_flow"] > counts["rsi_2"]
    assert counts["put_call_flow"] > counts["amihud"]
    assert counts.get("rsi_2", 0) > 0  # exploration floor keeps it sampled
    assert counts.get("amihud", 0) > 0


def test_d103_pick_regime_floor_keeps_zeroed_regime_explorable() -> None:
    """An observed-but-zero-reward regime is floored, so it keeps a minimum
    sampling budget rather than collapsing to never-sampled. Weights here are
    on the D105 component-rate scale (a learned-good gate posterior ~0.04)."""
    regimes = ("a", "b")
    weights = {"a": 0.04, "b": 0.0}
    counts = _count_picks("relative_value", regimes, weights, seed=1, n=3000)
    # b floored to 0.01 vs a's 0.04 -> 0.01/0.05 = 20% of 3000 ≈ 600
    assert counts.get("b", 0) > 300


def test_d103_pick_regime_uniform_and_byte_identical_for_non_curated() -> None:
    """regime_weights present but hypothesis != relative_value -> uniform pick,
    byte-identical to the pre-D103 `rng.choice` draw (other hypotheses' R-rule
    pools are already coherent; D103 must not touch them or their determinism)."""
    from forge.enumeration.sampler import _pick_regime

    regimes = ("adx", "hurst", "rv_rank")
    weights = {"adx": 0.99, "hurst": 0.005, "rv_rank": 0.005}
    r1, r2 = random.Random(7), random.Random(7)
    seq_pick = [_pick_regime("trend_continuation", regimes, r1, weights) for _ in range(40)]
    seq_choice = [r2.choice(regimes) for _ in range(40)]
    assert seq_pick == seq_choice  # weights ignored -> identical rng consumption


def test_d103_pick_regime_cold_start_byte_identical_for_relative_value() -> None:
    """relative_value with NO weights (cold start) -> uniform, byte-identical to
    the pre-D103 `rng.choice` path (hard rule #6: weights are an added input)."""
    from forge.enumeration.sampler import _pick_regime

    regimes = ("a", "b", "c", "d")
    r1, r2 = random.Random(123), random.Random(123)
    seq_pick = [_pick_regime("relative_value", regimes, r1, None) for _ in range(40)]
    seq_choice = [r2.choice(regimes) for _ in range(40)]
    assert seq_pick == seq_choice


# ---------------------------------------------------------------------------
# D105 — hypothesis x dte_bucket weights drive a JOINT (directional, bucket)
# draw. The DTE bucket is derived from the directional's horizon (D102), and
# for most indicators every k lands in ONE bucket (macd → all swing_mid,
# momentum_252 → all swing_long), so a k-only reweight could never move the
# mix; the joint draw steers the directional pick too.
# ---------------------------------------------------------------------------


def _bucket_distribution(
    grammar: Grammar,
    registry: RegistrySnapshot,
    hypothesis: str,
    bucket_weights: dict[tuple[str, str], float] | None,
    *,
    n: int = 300,
) -> dict[str, int]:
    space = build_search_space(grammar, registry)
    counts: dict[str, int] = {}
    for seed in range(n):
        cfg = sample_config(
            space,
            registry,
            random.Random(seed),
            forced_hypothesis=hypothesis,
            bucket_weights=bucket_weights,
        )
        counts[cfg.dte_bucket] = counts.get(cfg.dte_bucket, 0) + 1
    return counts


def test_d105_bucket_weights_cold_start_byte_identical(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Hard rule #6: bucket_weights is an ADDED input — absent (None) or empty
    ({}) must reproduce the pre-D105 sequence exactly."""
    space = build_search_space(grammar, registry)
    for seed in range(60):
        base = sample_config(space, registry, random.Random(seed))
        none_w = sample_config(space, registry, random.Random(seed), bucket_weights=None)
        empty_w = sample_config(space, registry, random.Random(seed), bucket_weights={})
        assert base.config_hash == none_w.config_hash == empty_w.config_hash, f"seed={seed}"


def test_d105_bucket_options_are_locked_per_directional() -> None:
    """WHY the draw is joint: most directionals are bucket-locked across k —
    momentum_252's k·252 targets all snap to swing_long, rsi_14's k·14 all to
    swing_mid — so a k-only reweight could never move a hypothesis's bucket
    mix. relative_value (no k) lists its S4-permitted buckets directly."""
    from forge.enumeration.sampler import _directional_bucket_options

    all_buckets = {"swing_short", "swing_mid", "swing_long"}
    assert _directional_bucket_options("trend_continuation", "momentum_252", all_buckets) == (
        "swing_long",
        "swing_long",
        "swing_long",
    )
    assert _directional_bucket_options("mean_reversion", "rsi_14", all_buckets) == (
        "swing_mid",
        "swing_mid",
        "swing_mid",
    )
    # vol_event's knob is the event lead: {5, 10} -> swing_short, 20 -> swing_mid.
    assert _directional_bucket_options("volatility_event", "iv_rank", all_buckets) == (
        "swing_short",
        "swing_short",
        "swing_mid",
    )
    # relative_value: S4-permitted buckets for pairs_zscore (horizon 60, medium).
    assert _directional_bucket_options("relative_value", "pairs_zscore", all_buckets) == (
        "swing_short",
        "swing_mid",
    )


def test_d105_bucket_weights_steer_directional_choice(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The load-bearing joint-draw property: weighting (mean_reversion,
    swing_mid) must steer the DIRECTIONAL pick toward the mid-locked indicator
    (rsi_14) and away from the short-locked ones (rsi_2 / call_wall), because
    the bucket is derived from the directional — there is no other path to the
    cell."""
    space = build_search_space(grammar, registry)

    def _directional_counts(weights: dict[tuple[str, str], float] | None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for seed in range(300):
            cfg = sample_config(
                space,
                registry,
                random.Random(seed),
                forced_hypothesis="mean_reversion",
                bucket_weights=weights,
            )
            directional = next(s for s in cfg.signals if s.role == "directional")
            counts[directional.indicators[0]] = counts.get(directional.indicators[0], 0) + 1
        return counts

    cold = _directional_counts(None)
    weighted = _directional_counts({("mean_reversion", "swing_mid"): 0.05})
    assert weighted.get("rsi_14", 0) > cold.get("rsi_14", 0) * 1.5
    assert weighted.get("rsi_14", 0) > 150  # dominant share of 300
    # The short-locked directionals stay explorable (floor), just rarer.
    assert weighted.get("rsi_2", 0) + weighted.get("call_wall_distance_pct", 0) > 0


def test_d105_bucket_weights_tilt_volatility_event_toward_mid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """vol_event x swing_mid (9.7% yield, starved ~20:1) — weighting the cell
    must raise the mid share (the lead-20 event bracket)."""
    cold = _bucket_distribution(grammar, registry, "volatility_event", None)
    hot = {("volatility_event", "swing_mid"): 0.05}
    weighted = _bucket_distribution(grammar, registry, "volatility_event", hot)
    cold_mid = cold.get("swing_mid", 0)
    assert weighted.get("swing_mid", 0) > cold_mid * 1.5
    assert weighted.get("swing_short", 0) > 0  # floor keeps short explorable


def test_d105_bucket_weights_starve_low_yield_cell_but_not_to_zero(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The converse: weighting one cell hot starves the others toward the floor
    but never to zero (D067 analogue at the bucket level)."""
    hot = {("mean_reversion", "swing_short"): 0.05}
    weighted = _bucket_distribution(grammar, registry, "mean_reversion", hot)
    assert weighted.get("swing_short", 0) > weighted.get("swing_mid", 0)
    assert weighted.get("swing_mid", 0) > 0


# ---------------------------------------------------------------------------
# D105 — underlying-class weighted pick. High-idio-vol single names minted
# 12.8-27.9% in the yield map; diversified ETF/index sat at 0/~390. The class
# weight tilts `_pick_underlying`'s draw; cold start stays byte-identical.
# ---------------------------------------------------------------------------


def _pick_underlyings_against_fallback(
    weights: dict[str, float] | None, *, n: int = 2000, with_earnings_gate: bool = False
) -> dict[str, int]:
    """Run `_pick_underlying` n times against the offline fallback pool."""
    import forge.enumeration.sampler as sampler_mod
    from forge.enumeration.sampler import _load_underlyings, _pick_underlying

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = Path("/nonexistent_d105_test_dir")
    try:
        _load_underlyings.cache_clear()
        rng = random.Random(0xD105)
        counts: dict[str, int] = {}
        regimes = ("days_to_earnings",) if with_earnings_gate else ()
        for _ in range(n):
            u = _pick_underlying(rng, "volatility_event", regimes, underlying_class_weights=weights)
            assert u is not None
            counts[u] = counts.get(u, 0) + 1
        return counts
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


def test_d105_underlying_cold_start_byte_identical(real_universe_loader: object) -> None:
    """Hard rule #6: class weights are an ADDED input — absent (None) and empty
    ({}) must reproduce the pre-D105 `rng.choice` sequence exactly."""
    import forge.enumeration.sampler as sampler_mod
    from forge.enumeration.sampler import _load_underlyings, _pick_underlying

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = Path("/nonexistent_d105_test_dir")
    try:
        _load_underlyings.cache_clear()
        # D286 (v37): the baseline draws from the POST-exclusion pool — the
        # fallback list carries GS/MSTR, which the untradeable filter now eats
        # (pre-D286 the fallback and filtered pools happened to coincide).
        pool = tuple(
            u
            for u in _load_underlyings()
            if u not in sampler_mod._STRUCTURALLY_UNTRADEABLE_UNDERLYINGS
        )
        r1, r2, r3 = random.Random(9), random.Random(9), random.Random(9)
        seq_none = [
            _pick_underlying(r1, "mean_reversion", (), underlying_class_weights=None)
            for _ in range(40)
        ]
        seq_empty = [
            _pick_underlying(r2, "mean_reversion", (), underlying_class_weights={})
            for _ in range(40)
        ]
        seq_choice = [r3.choice(pool) for _ in range(40)]
        assert seq_none == seq_empty == seq_choice
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


def test_d105_underlying_class_weights_tilt_toward_high_idio_vol(
    real_universe_loader: object,
) -> None:
    """A learned high_idio_vol class (component-rate scale ~0.04) must pull the
    draw strongly toward single names while the floor keeps the diversified
    ETFs explorable (evidence keeps flowing to revise the wall-of-zeros)."""
    from forge.enumeration.underlying_class import DIVERSIFIED, HIGH_IDIO_VOL, underlying_class

    weights = {HIGH_IDIO_VOL: 0.04, DIVERSIFIED: 0.002}
    counts = _pick_underlyings_against_fallback(weights)
    div = sum(n for t, n in counts.items() if underlying_class(t) == DIVERSIFIED)
    high = sum(n for t, n in counts.items() if underlying_class(t) == HIGH_IDIO_VOL)
    # Fallback pool was 4 diversified / 20 high; D309 (v43) excludes
    # DIA/MSFT/AMZN from the draw -> 3 div / 18 high, and the floored
    # diversified share lands EXACTLY on the 5% bound (uniform would be ~14%).
    # The claim is unchanged — crushed to the floor but NOT zero — so the
    # bound becomes inclusive.
    assert div > 0
    assert div / (div + high) <= 0.05


def test_d105_underlying_weights_respect_earnings_etf_exclusion(
    real_universe_loader: object,
) -> None:
    """T1.4 invariant survives the weighted path: with days_to_earnings in the
    regime, Tier-1 ETFs stay out of the pool regardless of class weights."""
    from forge.enumeration.sampler import _TIER_1_ETF_UNDERLYINGS
    from forge.enumeration.underlying_class import DIVERSIFIED, HIGH_IDIO_VOL

    weights = {HIGH_IDIO_VOL: 0.002, DIVERSIFIED: 0.04}  # even tilted TOWARD ETFs
    counts = _pick_underlyings_against_fallback(weights, with_earnings_gate=True)
    assert not set(counts) & _TIER_1_ETF_UNDERLYINGS


def test_sampler_reaches_every_hypothesis(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Across 300 seeds, every samplable hypothesis should appear at least
    once. Catches biased sampling that locks onto one hypothesis.

    D066: ``tail_hedge`` is excluded — it's overlay-only.
    D098 (v5): ``regime_arbitrage`` is excluded — dropped from enumeration as
    a low-yield-by-construction grammar-iteration decision. Both are in
    ``NON_ENUMERABLE_HYPOTHESES``; see the D098 invariants for the leak guard.
    D109 (v12): ``event_momentum`` joins the enumerable set (PEAD directional;
    the minimal fixture registers sue + days_since_earnings)."""
    seen: set[str] = set()
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        seen.add(cfg.hypothesis)
    # D328 (v47): relative_value + event_momentum joined DISABLED_HYPOTHESES
    # (no productive form) → no longer enumerable, like regime_arbitrage.
    assert seen == {
        "trend_continuation",
        "mean_reversion",
        "volatility_event",
    }


def test_d098_regime_arbitrage_not_sampled(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """D098 (v5): regime_arbitrage is in ``DISABLED_HYPOTHESES`` and must never
    be emitted by the weighted/uniform sampler across a seed sweep."""
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        assert cfg.hypothesis != "regime_arbitrage", f"seed={seed} leaked regime_arbitrage"


def test_d098_regime_arbitrage_blocked_when_forced(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D098 (v5): a direct sampler call must reject ``forced_hypothesis=
    'regime_arbitrage'`` exactly as it does for the overlay-only set — it's no
    longer in the samplable pool."""
    space = build_search_space(grammar, registry)
    with pytest.raises(SamplerError, match=r"forced_hypothesis='regime_arbitrage'"):
        sample_config(space, registry, random.Random(0), forced_hypothesis="regime_arbitrage")


def test_d328_relative_value_retired_not_samplable(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D328 (v47): relative_value is retired into DISABLED_HYPOTHESES — refuted
    (D215/D276: xsect rank-IC negative, corr-to-MR 0.88) + dormant. It stays in
    grammar.yaml S1 (hard rule #1) but is never enumerated, so forcing it raises
    (supersedes the D098 underlying=None enumeration assertion)."""
    space = build_search_space(grammar, registry)
    with pytest.raises(SamplerError):
        sample_config(space, registry, random.Random(3), forced_hypothesis="relative_value")


def test_d098_non_pairs_hypothesis_still_gets_underlying(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D098 guard: the underlying=None branch is relative_value-only — other
    hypotheses still draw a concrete ticker from the universe pool."""
    space = build_search_space(grammar, registry)
    cfg = sample_config(space, registry, random.Random(5), forced_hypothesis="trend_continuation")
    assert cfg.underlying is not None


# ---------------------------------------------------------------------------
# Failure modes — empty pools
# ---------------------------------------------------------------------------


def test_sampler_raises_when_no_hypothesis_has_pools(grammar: Grammar) -> None:
    """An empty-indicators registry produces no samplable hypothesis."""
    empty_registry = RegistrySnapshot(
        indicators=(),
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
        data_start_date=date(2022, 1, 1),
    )
    space = build_search_space(grammar, empty_registry)
    with pytest.raises(SamplerError, match="no hypothesis"):
        sample_config(space, empty_registry, random.Random(1))


def test_sampler_raises_when_no_sizer_mode_is_samplable(grammar: Grammar) -> None:
    """A registry with only vol_target and no realized_vol indicator leaves
    no samplable sizer mode."""
    registry = RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="rsi_2",
                version=1,
                family="mean_reversion",
                lookback=2,
                params_schema={},
            ),
            IndicatorMetadata(
                id="iv_rank",
                version=1,
                family="iv_structure",
                lookback=30,
                params_schema={},
            ),
        ),
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("vol_target",),  # X1 unsatisfiable: no realized_vol
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
        data_start_date=date(2022, 1, 1),
    )
    space = build_search_space(grammar, registry)
    with pytest.raises(SamplerError, match="no sizer mode"):
        sample_config(space, registry, random.Random(1))


# ---------------------------------------------------------------------------
# D078 — universe loader
# ---------------------------------------------------------------------------


def test_load_underlyings_returns_fallback_when_no_export(
    tmp_path: Path, real_universe_loader: object
) -> None:
    """D078: when universe export is absent, fallback list is used."""
    from forge.enumeration.sampler import (
        _FALLBACK_TIER_1_2_UNDERLYINGS,
        _load_underlyings,
    )

    _load_underlyings.cache_clear()
    import forge.enumeration.sampler as sampler_mod

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = tmp_path / "nonexistent_dir"
    try:
        _load_underlyings.cache_clear()
        result = _load_underlyings()
        assert result == _FALLBACK_TIER_1_2_UNDERLYINGS
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


def test_load_underlyings_reads_export(tmp_path: Path, real_universe_loader: object) -> None:
    """D078 / Q23 (contracts 1.13.0): tickers load from `universe_tickers.json`
    in the export dir via the blessed contracts helper."""
    import json as json_mod

    from forge.enumeration.sampler import _load_underlyings

    (tmp_path / "universe_tickers.json").write_text(
        json_mod.dumps(
            {
                "schema_version": "1.0",
                "tier_1": ["SPY", "QQQ"],
                "tier_2": ["AAPL", "MSFT"],
            }
        )
    )
    import forge.enumeration.sampler as sampler_mod

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = tmp_path
    try:
        _load_underlyings.cache_clear()
        result = _load_underlyings()
        assert result == ("AAPL", "MSFT", "QQQ", "SPY")
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


def test_m13_unreadable_export_logs_drift_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], real_universe_loader: object
) -> None:
    """M-13: a present-but-unparseable universe export logs a distinct drift
    WARNING (not silent) before falling back — separate from the expected
    'file absent' offline case. Post-contracts-1.13.0 the helper raises
    QueryError on the malformed file and `_load_underlyings` logs + falls back.

    Asserts via capsys rather than structlog.testing.capture_logs(): the
    module-level logger caches its bound logger once another test configures
    structlog, so capture_logs() can't intercept it (order-dependent). The
    rendered output is stable regardless.
    """
    import forge.enumeration.sampler as sampler_mod
    from forge.enumeration.sampler import (
        _FALLBACK_TIER_1_2_UNDERLYINGS,
        _load_underlyings,
    )

    (tmp_path / "universe_tickers.json").write_text("{ this is not valid json ")

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = tmp_path
    try:
        _load_underlyings.cache_clear()
        result = _load_underlyings()
        assert result == _FALLBACK_TIER_1_2_UNDERLYINGS
        captured = capsys.readouterr()
        # Drift WARNING emitted (distinct from the silent pre-fix `pass`).
        assert "universe_export_unreadable" in (captured.out + captured.err)
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


# ---------------------------------------------------------------------------
# D106 — hierarchical draw chains: underlying name -> class -> prior, and
# (hypothesis, directional, bucket) triple -> (hypothesis, bucket) pair ->
# prior. Cold start (all maps empty) stays byte-identical to pre-D105.
# ---------------------------------------------------------------------------


def test_d106_name_weights_override_class_within_pool(real_universe_loader: object) -> None:
    """A learned-hot name (AAPL-like) must outdraw its class peers; names
    without a name-level weight keep the class weight (the fallback chain)."""
    import forge.enumeration.sampler as sampler_mod
    from forge.enumeration.sampler import _load_underlyings, _pick_underlying
    from forge.enumeration.underlying_class import DIVERSIFIED, HIGH_IDIO_VOL

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = Path("/nonexistent_d106_test_dir")
    try:
        _load_underlyings.cache_clear()
        class_w = {HIGH_IDIO_VOL: 0.02, DIVERSIFIED: 0.002}
        name_w = {"AAPL": 0.25}  # ~12x its class
        rng = random.Random(0xD106)
        counts: dict[str, int] = {}
        for _ in range(3000):
            u = _pick_underlying(
                rng,
                "volatility_event",
                (),
                underlying_class_weights=class_w,
                underlying_name_weights=name_w,
            )
            assert u is not None
            counts[u] = counts.get(u, 0) + 1
        # AAPL weight 0.25 vs 19 high-class names at 0.02 + 4 diversified at
        # floor(0.01): AAPL share ~ 0.25/(0.25 + 19*0.02 + 4*0.01) ~ 37%.
        assert counts["AAPL"] > 800
        # the chain still samples un-named peers via the class weight
        assert counts.get("NVDA", 0) > 0
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


def test_d106_name_weights_cold_start_byte_identical(real_universe_loader: object) -> None:
    """Both underlying maps empty -> the pre-D105 uniform rng.choice sequence."""
    import forge.enumeration.sampler as sampler_mod
    from forge.enumeration.sampler import _load_underlyings, _pick_underlying

    original_dir = sampler_mod._UNIVERSE_EXPORT_DIR
    sampler_mod._UNIVERSE_EXPORT_DIR = Path("/nonexistent_d106_test_dir")
    try:
        _load_underlyings.cache_clear()
        # D286 (v37): baseline = the post-exclusion pool (see the D105 test).
        pool = tuple(
            u
            for u in _load_underlyings()
            if u not in sampler_mod._STRUCTURALLY_UNTRADEABLE_UNDERLYINGS
        )
        r1, r2 = random.Random(11), random.Random(11)
        seq = [
            _pick_underlying(
                r1,
                "mean_reversion",
                (),
                underlying_class_weights={},
                underlying_name_weights={},
            )
            for _ in range(30)
        ]
        ref = [r2.choice(pool) for _ in range(30)]
        assert seq == ref
    finally:
        sampler_mod._UNIVERSE_EXPORT_DIR = original_dir
        _load_underlyings.cache_clear()


def test_d106_triple_cell_overrides_pair_cell_in_joint_draw(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The (hypothesis, directional, bucket) triple outranks the pair fallback:
    with the PAIR (mean_reversion, swing_mid) hot but the rsi_14 triple cell
    learned-DEAD, the draw must avoid rsi_14 (the only mid-locked mr
    directional in the fixture) relative to the pair-only baseline."""
    space = build_search_space(grammar, registry)

    def _mid_share(triples: dict[tuple[str, str, str], float] | None) -> int:
        mid = 0
        for seed in range(300):
            cfg = sample_config(
                space,
                registry,
                random.Random(seed),
                forced_hypothesis="mean_reversion",
                bucket_weights={("mean_reversion", "swing_mid"): 0.05},
                directional_bucket_weights=triples,
            )
            if cfg.dte_bucket == "swing_mid":
                mid += 1
        return mid

    pair_only = _mid_share(None)
    dead_triple = _mid_share({("mean_reversion", "rsi_14", "swing_mid"): 0.001})
    assert pair_only > 150  # hot pair pulls toward rsi_14/swing_mid
    assert dead_triple < pair_only * 0.5  # triple evidence overrides the pair


def test_d106_triple_cold_start_byte_identical(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """All weight maps empty/None -> byte-identical configs to the bare call."""
    space = build_search_space(grammar, registry)
    for seed in range(40):
        base = sample_config(space, registry, random.Random(seed))
        full_none = sample_config(
            space,
            registry,
            random.Random(seed),
            bucket_weights={},
            directional_bucket_weights={},
            underlying_class_weights={},
            underlying_name_weights={},
        )
        assert base.config_hash == full_none.config_hash, f"seed={seed}"


def test_regime_signal_params_gamma_flip_op_is_hypothesis_aware() -> None:
    """D107 (v11 / H3): the dealer-gamma regime gate fires on opposite sides of
    the flip per hypothesis. mean_reversion uses the LONG-gamma / dampening side
    (op '<', flip below spot); trend_continuation uses the SHORT-gamma /
    amplifying side (op '>', the indicator_thresholds default). Same indicator,
    opposite regime selection — the 'switch'."""
    from forge.enumeration.sampler import _regime_signal_params

    rng = random.Random(20260608)
    mr = _regime_signal_params("mean_reversion", "gamma_flip_distance_pct", rng)
    trend = _regime_signal_params("trend_continuation", "gamma_flip_distance_pct", rng)
    assert mr["op"] == "<"
    assert trend["op"] == ">"


def test_regime_signal_params_gamma_op_flip_scoped_to_gamma_only() -> None:
    """The MR op-flip is scoped to gamma_flip_distance_pct — iv_rank (MR's other
    R1 gate) is byte-identical to the raw threshold sampler, no override leaked."""
    from forge.enumeration.indicator_thresholds import sample_threshold_params
    from forge.enumeration.sampler import _regime_signal_params

    via_regime = _regime_signal_params("mean_reversion", "iv_rank", random.Random(7))
    via_raw = sample_threshold_params("iv_rank", "regime_filter", random.Random(7))
    assert via_regime == via_raw


def test_regime_signal_params_hurst_op_is_mean_reverting_side() -> None:
    """D150 (v20): mean_reversion's hurst regime gate fires on the mean-reverting
    H<0.5 side (op '<'); the indicator_thresholds default '>' is R2's trend side."""
    from forge.enumeration.sampler import _regime_signal_params

    mr = _regime_signal_params("mean_reversion", "hurst", random.Random(20260614))
    assert mr["op"] == "<"


def test_pick_regime_biases_mean_reversion_toward_ranging_gates() -> None:
    """D150 (v20): mean_reversion's R1 regime-gate pick is biased ~3:1 toward the
    ranging gates (gamma_flip, hurst) vs the sparse iv_rank — iv_rank stays present
    (weight 1.0, not zeroed) but heavily down-weighted. Uniform would split ~1/3 each."""
    from collections import Counter

    from forge.enumeration.sampler import _pick_regime

    rng = random.Random(20260614)
    regimes = ("gamma_flip_distance_pct", "hurst", "iv_rank")
    counts = Counter(_pick_regime("mean_reversion", regimes, rng, None) for _ in range(3000))
    iv = counts["iv_rank"]
    ranging = counts["gamma_flip_distance_pct"] + counts["hurst"]
    assert iv > 0  # never starved out of exploration
    assert ranging > 2 * iv  # heavily biased toward ranging (uniform would give ~2x only)


def test_mr_ranging_gates_includes_rv_rank() -> None:
    """D167 (v22): rv_rank joins the MR ranging-gate bias set so the sampler
    prefers it (the densest, rank-coherent cheap-realized-vol gate) over the
    prefilter-sparse iv_rank, alongside gamma_flip + hurst (D150). Crucible
    (FORGE_mr_rv_hurst_overlap_response): rv_rank ⟂ and DOMINATES hurst."""
    from forge.enumeration.sampler import _MR_RANGING_GATES

    assert "rv_rank" in _MR_RANGING_GATES


def test_pick_regime_biases_mean_reversion_toward_rv_rank() -> None:
    """D167 (v22): with rv_rank in MR's pool, the pick is biased toward the
    ranging gates {gamma_flip, hurst, rv_rank} and away from the sparse iv_rank
    (which stays present at weight 1.0, never zeroed)."""
    from collections import Counter

    from forge.enumeration.sampler import _pick_regime

    rng = random.Random(20260615)
    regimes = ("gamma_flip_distance_pct", "hurst", "iv_rank", "rv_rank")
    counts = Counter(_pick_regime("mean_reversion", regimes, rng, None) for _ in range(4000))
    iv = counts["iv_rank"]
    rv = counts["rv_rank"]
    assert iv > 0  # never starved out of exploration
    assert rv > 2 * iv  # rv_rank ranging-weighted (3.0) vs iv_rank (1.0) → ~3x; uniform would tie


def test_exit_params_event_passed_retired() -> None:
    """D290 (v39): the D169 ladder is RETIRED — event_passed_exit left the ve
    schema (its only carrier; it always ran Crucible's fallback mode, a hard
    cut at entry+n_bars — the wound behind the v21->v22 ve conversion
    collapse, D289). _exit_params emits nothing for it."""
    from forge.enumeration.sampler import _exit_params

    for s in range(50):
        assert _exit_params("event_passed_exit", random.Random(s)) == {}


def test_exit_params_other_exits_unchanged() -> None:
    """D169: only event_passed_exit (+ the E3 trailing_atr activation) carry sampler
    params; every other exit stays empty so Crucible reads its runtime default."""
    from forge.enumeration.sampler import _exit_params

    assert _exit_params("premium_stop_loss", random.Random(0)) == {}
    assert _exit_params("time_stop", random.Random(0)) == {}  # cross-hypothesis; deferred
    atr = _exit_params("trailing_atr", random.Random(0))
    assert set(atr) == {"activate_after_gain_pct"}
    assert 0.30 <= atr["activate_after_gain_pct"] <= 0.50  # type: ignore[operator]


# ---------------------------------------------------------------------------
# D131 (v17) — iv_minus_rv activated as a ve directional; market_state in R2
# ---------------------------------------------------------------------------


def _v17_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + the two v17-activated live-registry ids."""
    extra = (
        IndicatorMetadata(
            id="iv_minus_rv",
            version=1,
            family="iv_structure",
            lookback=21,
            params_schema={},
            rank_per_name_coherent=False,
            market_wide_by_design=False,
        ),
        IndicatorMetadata(
            id="market_state",
            version=1,
            family="macro",
            lookback=0,
            params_schema={},
            rank_per_name_coherent=False,
            market_wide_by_design=True,
        ),
    )
    return base.model_copy(update={"indicators": (*base.indicators, *extra)})


def test_v17_ve_draws_iv_minus_rv_directional(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """D131 (v17): with threshold + horizon entries live, iv_minus_rv
    auto-enters volatility_event's DIRECTIONAL pool via C2 (iv_structure).
    Gate direction `<` — enter when IV is cheap vs realized (Goyal-Saretto,
    net-debit book per Crucible's Q34 answer). Its 21d horizon is
    medium_lookback → ve x swing_mid becomes reachable (the partial Q28
    lift) — assert at least one such draw appears."""
    reg = _v17_registry(registry)
    space = build_search_space(grammar, reg)
    seen = seen_swing_mid = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="volatility_event")
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators[0] != "iv_minus_rv":
            continue
        seen += 1
        assert d.params["op"] == "<", cfg.name
        assert -0.05 <= d.params["threshold"] <= 0.01, cfg.name
        if cfg.dte_bucket == "swing_mid":
            seen_swing_mid += 1
        else:
            assert cfg.dte_bucket == "swing_short", cfg.name  # S4 medium class
    assert seen > 0
    assert seen_swing_mid > 0


def test_v17_trend_draws_market_state_regime_gate(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D131 (v17): market_state joins R2's pool (operator-approved rule edit —
    R2's own evidence_to_relax clause fired). The threshold is the degenerate
    by-design cut: exactly 0.0 with op '>' (up-market admits)."""
    reg = _v17_registry(registry)
    space = build_search_space(grammar, reg)
    seen = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        g = next(s for s in cfg.signals if s.role == "regime_filter")
        if g.indicators[0] != "market_state":
            continue
        seen += 1
        assert g.params == {"threshold": 0.0, "op": ">"}, cfg.name
    assert seen > 0


def test_v17_market_state_gate_allowed_on_rank_arm(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """market_state is market_wide_by_design — uniform-across-names is CORRECT
    for a market gate, so trend rank draws gated on it stay rank-eligible
    (the v16 flag key: excluded only when NOT coherent AND NOT market-wide)."""
    reg = _v17_registry(registry)
    space = build_search_space(grammar, reg)
    assert "market_state" not in space.rank_excluded_ids
    share = {"trend_continuation": 1.0}
    seen_ms_rank = 0
    for seed in range(400):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="trend_continuation",
            rank_combiner_share=share,
        )
        uses_ms = any("market_state" in s.indicators for s in cfg.signals)
        if uses_ms and cfg.combiner.type == "cross_sectional_rank":
            seen_ms_rank += 1
    assert seen_ms_rank > 0


# ---------------------------------------------------------------------------
# D135 (v18) — adoption cut: iv_term_slope ve directional (A2), pre_earnings
# setup in R3; option_momentum deliberately NOT activated (data-starved, Q39)
# ---------------------------------------------------------------------------


def _v18_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + the live-registry ids relevant to the v18 cut
    (flags/families exactly as the 52-id snapshot
    `registry_snapshot_2026-06-10T172339Z.json` publishes them)."""
    extra = (
        IndicatorMetadata(
            id="iv_term_slope",
            version=1,
            family="iv_structure",
            lookback=0,
            params_schema={},
            rank_per_name_coherent=False,
            market_wide_by_design=False,
        ),
        IndicatorMetadata(
            id="option_momentum",
            version=1,
            family="smart_money",
            lookback=147,
            params_schema={},
            rank_per_name_coherent=False,
            market_wide_by_design=False,
        ),
        IndicatorMetadata(
            id="pre_earnings_setup",
            version=2,
            family="calendar",
            lookback=252,
            params_schema={},
            rank_per_name_coherent=False,
            market_wide_by_design=False,
        ),
    )
    return base.model_copy(update={"indicators": (*base.indicators, *extra)})


def test_v18_ve_draws_iv_term_slope_directional(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D135 (v18): with threshold + horizon entries live, iv_term_slope
    auto-enters volatility_event's DIRECTIONAL pool via C2 (iv_structure).
    Gate direction `>` — upward slope predicts option returns (Vasquez
    JFQA 2017; long-only book buys the steep-contango names). Its 21d
    horizon is medium_lookback, making it the second medium-horizon ve
    anchor (the A2 condition; full Q28 lift) — assert swing_mid draws."""
    reg = _v18_registry(registry)
    space = build_search_space(grammar, reg)
    seen = seen_swing_mid = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="volatility_event")
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators[0] != "iv_term_slope":
            continue
        seen += 1
        assert d.params["op"] == ">", cfg.name
        # D290 (v39): the floor is the x1.3-loosened 0.0077 (was 0.01).
        assert 0.0077 <= d.params["threshold"] <= 0.04, cfg.name
        if cfg.dte_bucket == "swing_mid":
            seen_swing_mid += 1
        else:
            assert cfg.dte_bucket == "swing_short", cfg.name  # S4 medium class
    assert seen > 0
    assert seen_swing_mid > 0


def test_v33_ve_never_draws_pre_earnings_setup(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D276 (v33) retires the D135/v18 admission from EMISSION: ~450 configs/wk
    at 91-100% structurally dead (the composed quiet-RV pre-earnings window
    ANDed with any directional threshold starves below the OOS trade floor;
    ve conversion 0.1% — Crucible addendum 2026-07-15 §B). Even with the
    registry serving the id, volatility_event never draws it; the R3 predicate
    still ACCEPTS it (emission-side retirement, hard rule #1 — the v18
    param-shape history lives in git). The T1.4 ETF-underlying constraint it
    exercised keeps its own coverage via days_to_earnings."""
    reg = _v18_registry(registry)
    space = build_search_space(grammar, reg)
    assert "pre_earnings_setup" not in space.regime_indicators_by_hypothesis["volatility_event"]
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="volatility_event")
        assert not any("pre_earnings_setup" in s.indicators for s in cfg.signals), cfg.name


def test_v33_option_momentum_retired_from_directional_emission(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D276 (v33) retires the D138/v19 activation from EMISSION: 100%
    structurally dead (47/wk, median 5 OOS trades, ~0 component conversions in
    the month since the min_months=3 fix — Crucible addendum 2026-07-15 §B).
    The threshold-table entry stays (is_threshold_skippable unchanged — the
    submitted lineage's params remain interpretable); the pool exclusion does
    the retirement, and the smart_money sibling expected_value_estimator stays
    pinned out of the directional path exactly as before (the X2 kelly sizer
    feature — the C2 smart_money family admission itself is untouched)."""
    from forge.enumeration.indicator_thresholds import is_threshold_skippable

    assert not is_threshold_skippable("option_momentum", "directional")  # entry kept
    assert is_threshold_skippable("expected_value_estimator", "directional")  # EV pinned out
    reg = _v18_registry(registry)
    space = build_search_space(grammar, reg)
    for hyp, pool in space.directional_indicators_by_hypothesis.items():
        assert "option_momentum" not in pool, hyp
    for seed in range(300):
        cfg = sample_config(space, reg, random.Random(seed))
        for s in cfg.signals:
            if s.role != "directional":
                continue
            assert "option_momentum" not in s.indicators, cfg.name
            assert "expected_value_estimator" not in s.indicators, cfg.name


def test_v18_new_ids_rank_excluded(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """All three v18 ids publish rank_per_name_coherent=False AND
    market_wide_by_design=False — the v16 flag-derived exclusion must
    pick them up with no Forge-side id list (fail-closed by design)."""
    reg = _v18_registry(registry)
    space = build_search_space(grammar, reg)
    for ind in ("iv_term_slope", "option_momentum", "pre_earnings_setup"):
        assert ind in space.rank_excluded_ids, ind


# ---------------------------------------------------------------------------
# Cohort-yield axis (§3 of Crucible's 2026-06-17 yield-map refresh,
# FORGE_structural_yield_map_refresh.md): the cohort draw (cross_sectional_rank
# vs confluence) becomes YIELD-DRIVEN instead of the fixed rank_combiner_share
# coin-flip. Default OFF (no map / empty map) == byte-identical to the H1 draw.
# ---------------------------------------------------------------------------

_COHORT_TREND = "trend_continuation"

# Golden hashes captured from the PRE-refactor sampler (the inline
# `if rank_combiner_share and ...` block) at seed 4242, rank_combiner_share
# {trend/mr/em: 0.5}. The refactor to `_cohort_xsect_probability` MUST reproduce
# this exact rng sequence when cohort_yield_weights is None (hard rule #6).
# D265 (v28): re-pinned — realized_vol in the MR regime pool moved position 4
# (an MR config's regime draw). none_run == empty_run re-verified under v28.
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — TWO composed shifts. (a) The scoped time_stop n_bars
# draw consumes an extra word on the SHARED enumeration stream (rejected
# attempts included) from the first scoped attempt — licensing verified
# mechanically per variant (old-behavior monkeypatch vs new code under the
# SAME universe: first divergence == first scoped attempt, index 5 here;
# intermediate positions may heal via _randbelow rejection variance).
# (b) Crucible's 2026-07-16T08:27:54Z July tier export (-FCX/WBD/WDC/VIX/
# BKNG/XLY/XLB, +APH/MDT) landed mid-deploy and moved underlying draws —
# the Q50 live-export coupling, second environment hit in two days.
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
# v51 (2026-07-25): re-pinned AGAIN — the v50 rank_k=5 trend bias was REVERTED the same
# night (collider-biased evidence, k=5 is the worse value; see the tombstone in sampler.py).
# So this state is "v49 draws + the IWM/SLB pool exclusion": the (b) contribution below is
# gone and only the (a) pool-shift signature remains. Environment-matched per D286/D290/D309.
# v50 (2026-07-24): re-pinned — TWO changes contribute, and their signatures are
# separable. (a) The IWM+SLB yield-audit round-2 exclusion shrinks the single-name
# drawable pool again (38 -> 40 excluded), which is the v37/v41/v43 pool-shift
# signature: verified that EVERY first divergence here is a `volatility_event`
# single-name confluence config (the only single-name hypothesis left after v47),
# @0 for the seed-7777 goldens whose first config taps the pool and @2-@3 otherwise.
# (b) The rank_k=5 trend bias replaces one `rng.choice(_RANK_K_CHOICES)` with one
# `rng.random()` on trend-xsect draws, so trend rank positions diverge downstream.
# Environment-matched per the D286/D290/D309 discipline: at the pre-edit preflight
# the OLD code reproduced every constant below EXACTLY (the full suite was green
# except the contracts pin), so this re-pin carries no unrelated drift. 7-11 of 15
# positions survive byte-identical in each golden — the per-index seeding signature,
# configs whose draws miss both the shrunken pool and the trend rank path.
# D309 (v43): re-pinned — the 30-name yield-audit exclusion shifts the
# single-name underlying draw (drawable pool 38 names smaller). Licensing
# harness environment-matched: OLD code reproduced every constant exactly at
# HEAD (2037-green suite pre-window). First divergences: every 7777-seed
# regime golden @0 (its first config taps the shrunken pool — the v37/v41
# pool-shift signature); cohort @2 with 5/15 positions surviving byte-
# identical (per-index seeding: configs whose draws miss the excluded pool
# region reproduce exactly). The relational structure across variants is
# re-asserted by the tests below; the first-capitulation landmark moved
# 30 → 71 (scan window widened to 80).
_COHORT_GOLDEN_PRE_REFACTOR = [
    "1feb1dc81f4427f4",
    "dde5703b72f300a1",
    "c8e89ddaae894a65",
    "acd95b51437b132e",
    "69f050e79be4e717",
    "9773f97a5028e439",
    "c4b9a3f54e771c9f",
    "219cedfd0ce11930",
    "ed16b154735434b9",
    "05e71b18c2056b11",
    "13ac6ad099175be2",
    "d1dd5478e6beb9f0",
    "906af3289a51e4e6",
    "3e3fc290110bab4c",
    "d5a3956a56e6206f",
]


def test_cohort_xsect_probability_yield_driven_and_clamped() -> None:
    """Yield-driven cohort probability: p = w_xsect / (w_xsect + w_single),
    clamped to the exploration band so neither cohort is starved to 0.

    D328 (v48): asserted on event_momentum — trend/MR are pinned to 1.0 (their
    single-name form is retired), so the yield-driven branch no longer governs them."""
    from forge.enumeration.sampler import _COHORT_EXPLORATION_FLOOR, _cohort_xsect_probability

    key = ("event_momentum", "sue", "swing_short")
    fav_xsect = {(*key, "xsect"): 0.40, (*key, "single"): 0.01}
    p = _cohort_xsect_probability(
        *key, cohort_yield_weights=fav_xsect, rank_combiner_share={"event_momentum": 0.33}
    )
    assert p == pytest.approx(1.0 - _COHORT_EXPLORATION_FLOOR)  # 0.976 -> ceiling
    fav_single = {(*key, "xsect"): 0.01, (*key, "single"): 0.40}
    p_rev = _cohort_xsect_probability(
        *key, cohort_yield_weights=fav_single, rank_combiner_share={"event_momentum": 0.33}
    )
    assert p_rev == pytest.approx(_COHORT_EXPLORATION_FLOOR)  # 0.024 -> floor


def test_cohort_xsect_probability_falls_back_to_fixed_share() -> None:
    """No cohort map, or a map with no evidence for THIS recipe -> the fixed
    rank_combiner_share (byte-identical to the pre-cohort H1 draw).

    D328 (v48): trend + MR are now PINNED to 1.0 (their single-name form is retired,
    so the cohort split is meaningless), so the fallback is exercised on the one
    remaining RANK_COMBINER member, event_momentum."""
    from forge.enumeration.sampler import _cohort_xsect_probability

    # the pin wins for the xsect-only hypotheses
    assert _cohort_xsect_probability(
        _COHORT_TREND,
        "momentum_252",
        "swing_long",
        cohort_yield_weights=None,
        rank_combiner_share={_COHORT_TREND: 0.33},
    ) == pytest.approx(1.0)
    # the share fallback still governs a non-pinned rank hypothesis
    assert _cohort_xsect_probability(
        "event_momentum",
        "sue",
        "swing_short",
        cohort_yield_weights=None,
        rank_combiner_share={"event_momentum": 0.33},
    ) == pytest.approx(0.33)
    assert _cohort_xsect_probability(
        "event_momentum",
        "sue",
        "swing_short",
        cohort_yield_weights={("mean_reversion", "rsi_2", "swing_short", "xsect"): 0.5},
        rank_combiner_share={"event_momentum": 0.33},
    ) == pytest.approx(0.33)


def test_cohort_xsect_probability_zero_for_non_rank_hypothesis() -> None:
    """Hypotheses outside RANK_COMBINER_HYPOTHESES are never rank-eligible -> 0.0
    (the sampler then draws NO rng for the cohort, confluence stays). Also 0.0
    when neither a cohort map nor a share is supplied (the cold path)."""
    from forge.enumeration.sampler import _cohort_xsect_probability

    assert (
        _cohort_xsect_probability(
            "relative_value",
            "pairs_zscore",
            "swing_mid",
            cohort_yield_weights={
                ("relative_value", "pairs_zscore", "swing_mid", "xsect"): 0.9,
                ("relative_value", "pairs_zscore", "swing_mid", "single"): 0.01,
            },
            rank_combiner_share={"relative_value": 0.5},
        )
        == 0.0
    )
    # D328 (v48): the cold path (no map, no share) still yields 0.0 — asserted on
    # event_momentum, since trend/MR are now pinned to 1.0 by the xsect-only rule.
    assert (
        _cohort_xsect_probability(
            "event_momentum",
            "sue",
            "swing_short",
            cohort_yield_weights=None,
            rank_combiner_share=None,
        )
        == 0.0
    )


def test_cohort_yield_cold_start_byte_identical(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Hard rule #6: cohort_yield_weights is an ADDED input behind the flag. When
    None/empty the sampler must reproduce the H1 fixed-share rng sequence
    EXACTLY — pinned against a golden captured from the pre-refactor code, so a
    restart with the flag unset can never silently change submissions (D104)."""
    share = {"trend_continuation": 0.5, "mean_reversion": 0.5, "event_momentum": 0.5}
    none_run = [
        c.config_hash
        for c in enumerate_candidates(
            grammar,
            registry,
            4242,
            max_candidates=15,
            rank_combiner_share=share,
            cohort_yield_weights=None,
        )
    ]
    empty_run = [
        c.config_hash
        for c in enumerate_candidates(
            grammar,
            registry,
            4242,
            max_candidates=15,
            rank_combiner_share=share,
            cohort_yield_weights={},
        )
    ]
    assert none_run == _COHORT_GOLDEN_PRE_REFACTOR
    assert empty_run == _COHORT_GOLDEN_PRE_REFACTOR


def test_cohort_yield_tilts_cohort_draw_by_yield(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D328 (v48): trend + MR are PINNED xsect-only, so the cohort tilt is INERT for
    them — a map screaming "single" produces the same xsect share as no map at all.
    (The tilt mechanism itself is unit-tested on event_momentum in
    test_cohort_xsect_probability_yield_driven_and_clamped.) The residual non-xsect
    configs are the rank-INELIGIBLE draws that the call-site guard keeps confluence;
    the v47 iterator filter drops those downstream."""
    space = build_search_space(grammar, registry)
    fav_single: dict[tuple[str, str, str, str], float] = {}
    for bucket in ("swing_long", "swing_mid"):
        fav_single[(_COHORT_TREND, "momentum_252", bucket, "xsect")] = 0.01
        fav_single[(_COHORT_TREND, "momentum_252", bucket, "single")] = 0.40

    def _xsect_share(cohort_weights: dict | None) -> tuple[int, int]:
        xs = total = 0
        for seed in range(400):
            cfg = sample_config(
                space,
                registry,
                random.Random(seed),
                forced_hypothesis=_COHORT_TREND,
                rank_combiner_share={_COHORT_TREND: 0.5},
                cohort_yield_weights=cohort_weights,
            )
            directional = next(s for s in cfg.signals if s.role == "directional").indicators[0]
            if directional != "momentum_252":
                continue
            total += 1
            if cfg.combiner.type == "cross_sectional_rank":
                xs += 1
        return xs, total

    xs_none, total_none = _xsect_share(None)
    xs_single, total_single = _xsect_share(fav_single)
    assert total_none > 0
    # the pin overrides the map entirely: identical outcome either way
    assert (xs_none, total_none) == (xs_single, total_single)
    # and the pinned share is high — every rank-ELIGIBLE draw went xsect
    assert xs_none / total_none > 0.6


# ---------------------------------------------------------------------------
# Regime-gate-yield axis (§2/§4 of Crucible's 2026-06-17 yield-map refresh):
# the regime draw composes the learned (hyp, directional, bucket, regime)
# component-rate onto the D150/uniform base — down-weighting sink gates
# (gamma_flip) and up-weighting minting ones. relative_value never composed
# (D119). Default OFF (no map) == byte-identical.
# ---------------------------------------------------------------------------

# Golden hashes from the PRE-refactor sampler (plain enumerate, seed 7777) — the
# regime draw fires for every config, so this pins that adding the learned param
# preserves the D150/uniform rng sequence when the map is absent (hard rule #6).
# D257 (v25): re-pinned. Dropping zscore_reversion_exit from mean_reversion's
# exit set (an inert pair exit) changes the post-exit rng draw for MR configs, so
# the config_hash moved at seq positions 11 & 14 (both MR). The flag-inertness
# invariant (none_run == empty_run) was re-verified under v25 before re-pinning —
# only the absolute sequence moved, hard rule #6 intact (version bump licenses it).
# D265 (v28): re-pinned again — realized_vol joins the MR regime pool (the base
# fixture already serves it for X1), moving position 14 (the slice's
# realized_vol-gated MR config). none_run == empty_run re-verified under v28.
# D268 (v30): re-pinned — the earnings-gated underlying exclusion widened from the
# 4 tier-1 ETFs to the full no-earnings set (_NO_EARNINGS_UNDERLYINGS), so every
# earnings-gated config (event_momentum / vol_event drawing an earnings gate) draws
# from a smaller pool; `rng.choice` on that pool consumes rng differently, cascading
# the sequence from the first earnings-gated config (position 0 here is a
# volatility_event) onward. Non-earnings configs are individually unchanged; the
# cascade is the rng-stream reshuffle, licensed by the v30 bump. All six cold-start
# goldens re-pinned; none_run == empty_run + all inter-golden prefix relations
# re-verified before pinning. NB these slices read the LIVE universe export via
# `_load_underlyings` (pre-existing — earnings configs draw from it).
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — TWO composed shifts (see the cohort golden's D282
# note): the scoped n_bars attempts here are 2 & 5 (licensing: old-vs-new code
# under the SAME universe first diverges at attempt 2), and the 07-16 universe
# export shrink independently moved underlying draws (Q50). none_run ==
# empty_run re-verified under v36.
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D288 (v38): re-pinned — the trend swing_long time_stop optional draw drops
# to p=0.15 (exit-mix relay), so scoped configs flip their timer pick and the
# skipped n_bars randint shifts downstream draws. Licensing harness
# environment-matched: OLD code reproduced every constant exactly; each first
# divergence verified as a trend swing_long exit draw (PRE@2, V27@11). The
# cohort golden (seed 4242) is untouched — its slice hosts no scoped flip.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
# D328 (v47): re-pinned — single-name trend/MR retirement (the iterator's
# emission-policy filter) + relative_value/event_momentum disable. `sample_config`
# is byte-identical (this is an enumerate-side filter, not a sampler change), but
# the enumerate_candidates sequence legitimately shifts: disabling em/relval drops
# them from `samplable_hypotheses` (the unforced hypothesis pick moves), and the
# filter drops confluence trend/MR (retry advances the rng). The flag-off
# invariants (none_run == empty_run) were re-verified BEFORE re-pinning. The
# active-golden relational splits moved to position 0 (a served-registry veto's
# eligibility rng draw on a now-FILTERED trend/MR config diverges the retry
# sequence earlier) — documented per test. All 7 goldens re-pinned off the pinned
# universe fixture. See D328.
_REGIME_GOLDEN_PRE = [
    "73932a3bb6897934",
    "fd067aa010c15678",
    "7248bfffdcbd22c8",
    "b192ee728dc459fb",
    "fb703dadd797e327",
    "4dcaf88253b6f4ce",
    "9e80f8335b574b15",
    "5b77ae8008072ca3",
    "08b0c86e4e079f9c",
    "c05d0f78b549c1a3",
    "e1fffb3db6f1cbdd",
    "2803381a7ff3fc20",
    "4be47b590a2a43cc",
    "4ca710af62108eda",
    "8b5bbc192c9a25a3",
]


def test_pick_regime_learned_downweights_sink_gate() -> None:
    """Composition: a sink regime gate (gamma_flip, ~0 posterior) is drawn far
    less than a minting one (hurst) — the §4 gamma_flip-sink avoidance."""
    from collections import Counter

    from forge.enumeration.sampler import _pick_regime

    regimes = ("hurst", "adx", "gamma_flip_distance_pct")
    learned = {"hurst": 0.08, "adx": 0.05, "gamma_flip_distance_pct": 0.001}
    rng = random.Random(1)
    counts = Counter(
        _pick_regime("trend_continuation", regimes, rng, None, learned) for _ in range(3000)
    )
    assert counts["hurst"] > counts["adx"] > counts["gamma_flip_distance_pct"]
    assert counts["gamma_flip_distance_pct"] < counts["hurst"] * 0.2  # sink crushed


def test_pick_regime_learned_preserves_d150_on_dead_triple() -> None:
    """A DEAD triple (all regimes ~equal posterior) must leave the D150 mr
    ranging-bias intact — base * posterior stays proportional to base, so the
    deliberate diversity lever is refined by evidence, never silently discarded.
    D254 (v24): the boosted gate here is `vol_regime` (hurst was dropped from the
    boost set — bias away — but stays R1-accepted at weight 1.0)."""
    from collections import Counter

    from forge.enumeration.sampler import _pick_regime

    regimes = ("vol_regime", "iv_rank")  # vol_regime is a D254 ranging gate (x3), iv_rank x1
    flat = {"vol_regime": 0.002, "iv_rank": 0.002}  # dead triple, equal posteriors
    rng_l = random.Random(7)
    with_learned = Counter(
        _pick_regime("mean_reversion", regimes, rng_l, None, flat) for _ in range(4000)
    )
    rng_b = random.Random(7)
    base_only = Counter(
        _pick_regime("mean_reversion", regimes, rng_b, None, None) for _ in range(4000)
    )
    # D150 favours the ranging gate ~3:1 in BOTH (flat learned doesn't disturb it)
    assert with_learned["vol_regime"] > 2.5 * with_learned["iv_rank"]
    assert base_only["vol_regime"] > 2.5 * base_only["iv_rank"]


def test_pick_regime_relative_value_never_composed_d119() -> None:
    """D119: relative_value's runner ignores the gate, so learned weights must
    NEVER bias its regime draw — it stays uniform even with a lopsided map."""
    from collections import Counter

    from forge.enumeration.sampler import _pick_regime

    regimes = ("rv_rank", "rsi_2")
    lopsided = {"rv_rank": 0.9, "rsi_2": 0.001}  # would crush rsi_2 if applied
    rng = random.Random(3)
    counts = Counter(
        _pick_regime("relative_value", regimes, rng, None, lopsided) for _ in range(3000)
    )
    # uniform: neither gate dominates (rv never composes the learned map)
    assert 0.4 < counts["rv_rank"] / 3000 < 0.6


def test_regime_gate_yield_cold_start_byte_identical(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Hard rule #6: regime_gate_yield_weights is an ADDED input behind the flag.
    None/empty must reproduce the D150/uniform regime rng sequence EXACTLY —
    pinned against a golden captured from the pre-refactor code."""
    none_run = [
        c.config_hash
        for c in enumerate_candidates(
            grammar, registry, 7777, max_candidates=15, regime_gate_yield_weights=None
        )
    ]
    empty_run = [
        c.config_hash
        for c in enumerate_candidates(
            grammar, registry, 7777, max_candidates=15, regime_gate_yield_weights={}
        )
    ]
    assert none_run == _REGIME_GOLDEN_PRE
    assert empty_run == _REGIME_GOLDEN_PRE


def test_regime_gate_yield_tilts_regime_draw(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """End-to-end through sample_config: regime weights favouring hurst and
    crushing adx shift the trend regime-gate distribution accordingly — the draw
    is now driven by learned component-yield, not a flat draw."""
    space = build_search_space(grammar, registry)
    weights: dict[tuple[str, str, str, str], float] = {}
    for d in space.directional_indicators_by_hypothesis["trend_continuation"]:
        for b in space.dte_buckets:
            weights[("trend_continuation", d, b, "hurst")] = 0.50
            weights[("trend_continuation", d, b, "adx")] = 0.001
            weights[("trend_continuation", d, b, "rv_rank")] = 0.05

    def _regime_dist(rw: dict | None) -> dict[str, float]:
        from collections import Counter

        c: Counter[str] = Counter()
        for seed in range(500):
            cfg = sample_config(
                space,
                registry,
                random.Random(seed),
                forced_hypothesis="trend_continuation",
                regime_gate_yield_weights=rw,
            )
            c[next(s for s in cfg.signals if s.role == "regime_filter").indicators[0]] += 1
        total = sum(c.values())
        return {k: v / total for k, v in c.items()}

    base = _regime_dist(None)
    tilted = _regime_dist(weights)
    assert tilted.get("adx", 0.0) < base.get("adx", 1.0) - 0.15  # adx crushed
    assert tilted.get("hurst", 0.0) > base.get("hurst", 0.0) + 0.1  # hurst favoured


# ---------------------------------------------------------------------------
# D258 (v25) — days_since_jump event-frequency VETO (Crucible
# FORGE_days_since_jump_indicator_2026-07-08). An OPTIONAL SECOND regime gate
# that ANDs on top of the mandatory trend-strength gate; trend_continuation only;
# DORMANT until the registry serves the indicator.
# ---------------------------------------------------------------------------
def _v25_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + the v25 days_since_jump veto indicator (family
    volatility, version 3, rank-per-name coherent) — the object Forge reads once
    Crucible publishes the snapshot serving dsj."""
    dsj = IndicatorMetadata(
        id="days_since_jump",
        version=3,
        family="volatility",
        lookback=252,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    return base.model_copy(update={"indicators": (*base.indicators, dsj)})


def test_d258_dsj_veto_dormant_without_registry_indicator(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Byte-identity's precondition: on a registry WITHOUT days_since_jump the veto
    pool is empty, so no config carries the second gate and `days_since_jump` is
    never emitted (complements the cold-start goldens)."""
    for seed in range(200):
        cfg = _sample(grammar, registry, seed=seed)
        ids = {ind for s in cfg.signals for ind in s.indicators}
        assert "days_since_jump" not in ids, f"dsj emitted while dormant at seed={seed}"
        assert not any(s.id == "sig_regime_veto" for s in cfg.signals)


def test_d258_dsj_veto_active_on_trend_and_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """With the registry serving dsj, some trend_continuation configs carry a
    SECOND regime gate = days_since_jump (op '<', threshold on the 30-65 plateau)
    ANDed on top of the trend-strength gate. Every such config is grammar-valid:
    R2 is still satisfied by the primary gate, and C1 holds — dsj (volatility)
    never co-occurs with rv_rank/vol_regime (also volatility)."""
    reg = _v25_registry(registry)
    space = build_search_space(grammar, reg)
    veto_seen = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        regime_sigs = [s for s in cfg.signals if s.role == "regime_filter"]
        veto_sigs = [s for s in regime_sigs if s.indicators == ("days_since_jump",)]
        if not veto_sigs:
            continue
        veto_seen += 1
        assert validate(cfg, grammar, reg).valid, f"dsj-veto config invalid at seed={seed}"
        # the veto is ADDITIONAL — a trend-strength primary gate is still present
        assert len(regime_sigs) == 2, f"expected 2 regime gates at seed={seed}"
        primary = next(s for s in regime_sigs if s.indicators != ("days_since_jump",))
        assert primary.indicators[0] in _R2_TREND_CONTINUATION_REGIME_INDICATORS
        # C1: dsj never stacks on another volatility-family gate
        assert primary.indicators[0] not in {"rv_rank", "vol_regime"}, cfg.name
        veto_params = veto_sigs[0].params
        assert veto_params["op"] == "<", cfg.name
        assert 30.0 <= veto_params["threshold"] <= 65.0, veto_params
    assert veto_seen > 0, "no dsj-veto config produced under the active registry"


def test_d258_dsj_veto_absent_on_non_trend_hypotheses(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Scope: the veto pool is trend_continuation-only, so mean_reversion (and
    every other hypothesis) never carries days_since_jump even when the registry
    serves it."""
    reg = _v25_registry(registry)
    space = build_search_space(grammar, reg)
    for seed in range(200):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        ids = {ind for s in cfg.signals for ind in s.indicators}
        assert "days_since_jump" not in ids, f"dsj leaked onto mean_reversion at seed={seed}"


# D258 dsj-ACTIVE cold-start golden (seed 7777, max 15) — the registry-hash-free
# analog of _REGIME_GOLDEN_PRE for the dsj-SERVING path. Crucible's snapshot has
# served days_since_jump since 2026-07-09T00:06:43Z (verified family volatility /
# version 3 / lookback 252, matching _v25_registry), so the daemon left the
# dormant path at deploy. On the served registry the veto's eligibility check
# `rng.random() < _DSJ_VETO_SHARE` is EVALUATED — consuming one draw — on every
# veto-eligible trend_continuation config even when it does not fire, so the
# sequence legitimately diverges from the dormant golden (indices 0-2 still match;
# it splits once the first eligible trend config consumes the veto draw). That is
# the D258 "registry_hash rolls = legitimate sequence change" the v25 bump
# licenses; the DORMANT path stays byte-identical
# (test_regime_gate_yield_cold_start_byte_identical). Crucible does NOT publish a
# registry_hash (Forge computes it from snapshot content), so this pins the
# deterministic _v25_registry fixture, not a live hash. The v26 ivol_lo MR gate
# touches the same veto block and WILL move this — re-pin there with the D-entry.
# D265 (v28): re-pinned — realized_vol in the MR regime pool moved position 14
# (the slice's realized_vol-gated MR config; same single-position shift as
# _REGIME_GOLDEN_PRE, so the dsj-vs-PRE split structure is untouched).
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — scoped n_bars attempts at 2 & 13 (licensing: old-vs-
# new code under the SAME universe first diverges at attempt 2) + the 07-16
# universe export shrink (Q50). Under these pins the PRE-vs-DSJ split sits at
# position 3 (the first eligible trend config), as pre-v36.
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D288 (v38): re-pinned — the trend swing_long time_stop optional draw drops
# to p=0.15 (exit-mix relay), so scoped configs flip their timer pick and the
# skipped n_bars randint shifts downstream draws. Licensing harness
# environment-matched: OLD code reproduced every constant exactly; each first
# divergence verified as a trend swing_long exit draw (PRE@2, V27@11). The
# cohort golden (seed 4242) is untouched — its slice hosts no scoped flip.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
_REGIME_GOLDEN_DSJ_ACTIVE = [
    "4ef13271b509bd9b",
    "79ef7900584be424",
    "1525c6460c2e6baf",
    "4dcaf88253b6f4ce",
    "9e80f8335b574b15",
    "a385d495a6f9850c",
    "f559b676b5125f19",
    "b094fbdbedff6798",
    "3700e79ebd3683e3",
    "2803381a7ff3fc20",
    "4be47b590a2a43cc",
    "d0506c7863226f5e",
    "d68ae89893f62345",
    "978680d3f23fb4f1",
    "a3c9580554a6b8e1",
]


def test_d258_dsj_active_cold_start_golden(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Byte-pin the dsj-ACTIVE enumeration sequence (registry serving
    days_since_jump) so the veto path is determinism-covered independent of the
    live, per-publish-rolling registry_hash. It DIFFERS from the dormant
    _REGIME_GOLDEN_PRE (the veto eligibility draw is consumed on eligible
    trend_continuation configs) — the D258 legitimate sequence change the v25 bump
    licenses — while the dormant path stays byte-identical elsewhere."""
    reg = _v25_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_DSJ_ACTIVE
    # the served registry legitimately shifts the sequence vs dormant (D258)
    assert active != _REGIME_GOLDEN_PRE
    # v47 (D328): single-name trend is retired (the iterator filter), but a
    # dsj-served trend config still consumes its veto-eligibility rng draw before
    # being filtered — so the dormant-vs-served RETRY sequences diverge from
    # position 0. UNCHANGED by v48: this slice is the cold path (no share), which
    # v48 leaves byte-identical. Core invariant stays `active != PRE`.
    assert active[0] != _REGIME_GOLDEN_PRE[0]


# ---------------------------------------------------------------------------
# D263 (v26) — ivol name-selection VETO on mean_reversion (Crucible
# FORGE_ivol_lo_mr_entry_gate_2026-07-09). An OPTIONAL SECOND regime gate that
# ANDs on top of the mandatory MR regime gate; mean_reversion only; percentile
# plateau [0.2,0.4] (op '<'), window 63. UNLIKE dsj: ivol is family
# idiosyncratic_vol (contracts 1.28.0), so C1 lets it STACK on the volatility
# gate (rv_rank/vol_regime) — the validated form.
# ---------------------------------------------------------------------------
def _v26_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + the v25 dsj veto AND the v26 ivol veto indicator (family
    idiosyncratic_vol, version 1, lookback 63) — the object Forge reads once the
    registry serves both (the live v26 state: dsj served since 2026-07-09, ivol
    since the 1.28.0 reclassification)."""
    dsj = IndicatorMetadata(
        id="days_since_jump",
        version=3,
        family="volatility",
        lookback=252,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    ivol = IndicatorMetadata(
        id="ivol",
        version=1,
        family="idiosyncratic_vol",
        lookback=63,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    return base.model_copy(update={"indicators": (*base.indicators, dsj, ivol)})


def test_d263_ivol_veto_dormant_without_registry_indicator(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Byte-identity's precondition: on the base registry (no ivol) the MR veto
    pool is empty, so no mean_reversion config carries an ivol second gate and
    `ivol` is never emitted (complements the cold-start goldens)."""
    space = build_search_space(grammar, registry)
    for seed in range(200):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="mean_reversion"
        )
        ids = {ind for s in cfg.signals for ind in s.indicators}
        assert "ivol" not in ids, f"ivol emitted while dormant at seed={seed}"
        assert not any(s.id == "sig_regime_veto" for s in cfg.signals)


def test_d263_ivol_veto_active_on_mr_and_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """With the registry serving ivol, some mean_reversion configs carry a SECOND
    regime gate = ivol (op '<', percentile plateau [0.2,0.4], window 63) ANDed on
    top of the mandatory MR regime gate. Every such config is grammar-valid: R1 is
    satisfied by the primary gate, and C1 holds. KEY (the OPPOSITE of dsj): ivol
    (idiosyncratic_vol) STACKS on rv_rank/vol_regime (volatility) — the C1-legal
    co-occurrence the 1.28.0 family split enabled."""
    reg = _v26_registry(registry)
    space = build_search_space(grammar, reg)
    mr_primary_gates = {
        "iv_rank",
        "gamma_flip_distance_pct",
        "hurst",
        "rv_rank",
        "vol_regime",
        "realized_vol",  # D265 (v28): the absolute-RV sixth gate
    }
    veto_seen = 0
    stacked_on_volatility = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        regime_sigs = [s for s in cfg.signals if s.role == "regime_filter"]
        veto_sigs = [s for s in regime_sigs if s.indicators == ("ivol",)]
        if not veto_sigs:
            continue
        veto_seen += 1
        assert validate(cfg, grammar, reg).valid, f"ivol-veto config invalid at seed={seed}"
        # the veto is ADDITIONAL — the mandatory MR primary gate is still present
        assert len(regime_sigs) == 2, f"expected 2 regime gates at seed={seed}"
        primary = next(s for s in regime_sigs if s.indicators != ("ivol",))
        assert primary.indicators[0] in mr_primary_gates, cfg.name
        if primary.indicators[0] in {"rv_rank", "vol_regime"}:
            stacked_on_volatility += 1  # ivol(idiosyncratic_vol) + a volatility gate: C1-legal
        p = veto_sigs[0].params
        assert p["op"] == "<", p
        assert p["use_percentile"] is True, p
        assert 0.2 <= float(p["threshold"]) <= 0.4, p
        assert p["percentile_window"] == 63, p
    assert veto_seen > 0, "no ivol-veto config produced under the active registry"
    assert stacked_on_volatility > 0, "ivol never stacked on a volatility gate (the validated form)"


def test_d263_ivol_veto_absent_on_non_mr_hypotheses(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Scope: the ivol veto pool is mean_reversion-only, so trend_continuation (and
    every other hypothesis) never carries ivol even when the registry serves it.
    (dsj may still appear on trend — that's the v25 veto, a different pool.)"""
    reg = _v26_registry(registry)
    space = build_search_space(grammar, reg)
    # D328 (v47): event_momentum dropped — it's DISABLED_HYPOTHESES now, so
    # forcing it raises (not samplable). trend + ve still exercise the scope guard.
    for hypothesis in ("trend_continuation", "volatility_event"):
        for seed in range(150):
            cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis=hypothesis)
            ids = {ind for s in cfg.signals for ind in s.indicators}
            assert "ivol" not in ids, f"ivol leaked onto {hypothesis} at seed={seed}"


# D263 v26 cold-start golden (seed 7777, max 15) on a registry serving BOTH dsj
# and ivol — the live v26 state. Differs from _REGIME_GOLDEN_DSJ_ACTIVE (dsj-only)
# because veto-eligible mean_reversion configs now draw the ivol veto (3 of these
# 15 actually carry it: positions 3, 6, 11). The dsj-only and fully-dormant
# goldens above shifted only where the D265 realized_vol pool add moved MR draws.
# D265 (v28): re-pinned — realized_vol joins the MR regime pool; the slice's MR
# configs from position 6 re-drew their gates, cascading the ivol-veto positions
# (were 3, 7, 12).
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — scoped n_bars attempts at 2, 9 & 12 (licensing:
# first old-vs-new divergence == attempt 2 under the SAME universe) + the
# 07-16 universe export shrink (Q50).
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D288 (v38): re-pinned — the trend swing_long time_stop optional draw drops
# to p=0.15 (exit-mix relay), so scoped configs flip their timer pick and the
# skipped n_bars randint shifts downstream draws. Licensing harness
# environment-matched: OLD code reproduced every constant exactly; each first
# divergence verified as a trend swing_long exit draw (PRE@2, V27@11). The
# cohort golden (seed 4242) is untouched — its slice hosts no scoped flip.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
_REGIME_GOLDEN_V26_ACTIVE = [
    "a44cd8f2c4edb745",
    "f9695f0ff64a0775",
    "3b43fd7342013488",
    "7a1151e3f8353573",
    "465fd6a56a91528f",
    "f559b676b5125f19",
    "5e3d288ae9134cda",
    "d7acbf9c2e787039",
    "270c5da463424bff",
    "d68ae89893f62345",
    "dd69c9ce38deb87d",
    "53163b623425f893",
    "6e6e0bc6ba2776ea",
    "37fad70c7af734a3",
    "b42d8da37f55d162",
]


def test_d263_ivol_active_cold_start_golden(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Byte-pin the v26 enumeration sequence (registry serving dsj + ivol). It
    diverges from the dsj-only _REGIME_GOLDEN_DSJ_ACTIVE once the first veto-
    eligible mean_reversion config draws the ivol veto — the D263 licensed change;
    the dormant + dsj-only goldens stay byte-identical (asserted by their own
    tests)."""
    reg = _v26_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_V26_ACTIVE
    assert active != _REGIME_GOLDEN_DSJ_ACTIVE  # ivol on MR shifts the sequence
    # v47 (D328): ivol is an MR second gate, and single-name MR is retired — so it
    # only manifests on xsect MR, which needs a rank_combiner_share. The no-share
    # byte-pin slice above no longer carries it; verify reachability on the xsect
    # (production) path. Dedicated coverage: test_d263_ivol_veto_active_on_mr.
    assert any(
        any("ivol" in s.indicators for s in c.signals)
        for c in enumerate_candidates(
            grammar, reg, 7777, max_candidates=25, rank_combiner_share={"mean_reversion": 0.6}
        )
    )


# ---------------------------------------------------------------------------
# D264 (v27): resid_vix activation — residual_momentum trend directional x
# vix_term_slope R2 calm gate (Crucible FORGE_resid_vix_generation_request_
# 2026-07-11: their probe on this pair = the FIRST walk-forward-gate pass in
# program history). Reachability lives here; the table/horizon/R2-pool unit
# assertions live in test_resid_vix_v27.py. The dormant goldens above stay
# byte-identical (their fixtures serve neither id → pools unchanged).
# ---------------------------------------------------------------------------
def _v27_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + dsj + ivol (the v26 state) + the two v27 activations
    (residual_momentum family=trend rank-coherent; vix_term_slope family=macro
    market-wide) — the object Forge reads on the live v27 registry (both ids
    long-registered; verified in registry_snapshot_2026-07-11T010003Z.json)."""
    resid = IndicatorMetadata(
        id="residual_momentum",
        version=1,
        family="trend",
        lookback=504,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    vix_slope = IndicatorMetadata(
        id="vix_term_slope",
        version=1,
        family="macro",
        lookback=0,
        params_schema={},
        rank_per_name_coherent=False,
        market_wide_by_design=True,
    )
    v26 = _v26_registry(base)
    return v26.model_copy(update={"indicators": (*v26.indicators, resid, vix_slope)})


def test_d264_resid_vix_pools_reachable(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Both ids enter their pools once the registry serves them: residual_momentum
    the trend_continuation directional pool (C2 family=trend + threshold entry),
    vix_term_slope the trend regime pool (R2 python-side accept + threshold entry)."""
    space = build_search_space(grammar, _v27_registry(registry))
    assert "residual_momentum" in space.directional_indicators_by_hypothesis["trend_continuation"]
    assert "vix_term_slope" in space.regime_indicators_by_hypothesis["trend_continuation"]


def test_d264_resid_vix_pair_emitted_and_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The exact handoff pair (residual_momentum directional + vix_term_slope
    gate) is actually SAMPLED — with the probe's param shape: percentile
    threshold in [0.60, 0.90] + window/skip knobs on the directional, absolute
    contango threshold in [0.0, 2.0] op '>' on the gate — and the emitted
    config passes full grammar validation (C1: trend x macro never collides)."""
    reg = _v27_registry(registry)
    space = build_search_space(grammar, reg)
    found = False
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        directional = next(s for s in cfg.signals if s.role == "directional")
        if directional.indicators != ("residual_momentum",):
            continue
        gates = [s for s in cfg.signals if s.role == "regime_filter"]
        vix_gates = [g for g in gates if g.indicators == ("vix_term_slope",)]
        if not vix_gates:
            continue
        found = True
        assert directional.params.get("use_percentile") is True
        threshold = directional.params["threshold"]
        assert isinstance(threshold, float)
        assert 0.60 <= threshold <= 0.90
        window = directional.params.get("window")
        skip = directional.params.get("skip")
        assert isinstance(window, int)
        assert 63 <= window <= 252
        assert isinstance(skip, int)
        assert 0 <= skip <= 21
        gate = vix_gates[0]
        assert gate.params.get("op") == ">"
        gate_threshold = gate.params["threshold"]
        assert isinstance(gate_threshold, float)
        assert 0.0 <= gate_threshold <= 2.0
        result = validate(cfg, grammar, reg)
        assert result.valid, f"seed={seed}: {result.errors}"
        break
    assert found, "resid_momentum x vix_term_slope never emitted in 400 seeds"


def test_d264_new_ids_dormant_without_registry(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Byte-identity's precondition (the dsj/ivol pattern): on a registry that
    serves neither id, neither is ever emitted — the base-fixture pools are
    unchanged, so every pre-v27 golden above holds."""
    space = build_search_space(grammar, registry)
    assert (
        "residual_momentum" not in space.directional_indicators_by_hypothesis["trend_continuation"]
    )
    assert "vix_term_slope" not in space.regime_indicators_by_hypothesis["trend_continuation"]


# D264 v27 cold-start golden (seed 7777, max 15) on a registry serving dsj, ivol
# AND the two v27 activations — the live v27 state. Diverges from
# _REGIME_GOLDEN_V26_ACTIVE at position 2, the first trend_continuation config
# that draws from the widened pools (positions 2 and 4 carry residual_momentum /
# vix_term_slope in this slice). The dormant/dsj/v26 goldens above are UNCHANGED
# (their fixtures serve neither new id), proving the activation didn't perturb
# the existing paths.
# D265 (v28): re-pinned — realized_vol in the MR regime pool moved position 12
# (the slice's realized_vol-gated MR config).
# D276 (v33): re-pinned — the resid_vix confirmed-region concentration (regime
# pool pin to {vix_term_slope, hurst}, narrowed knobs/gates, forced monthly
# rank combiner) reshuffles exactly the trend positions that can draw
# residual_momentum (2-8, 12-14); the non-trend positions 0-1 and 9-11 are
# byte-identical, and the pre-v27 goldens above are untouched (their fixtures
# never serve the id) — the licensed-where-changed shape.
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — this slice's first scoped n_bars attempt is position
# 9 (the resid concentration reshapes the earlier trend positions' buckets;
# licensing: first old-vs-new divergence == attempt 9 under the SAME universe)
# + the 07-16 universe export shrink (Q50), which moved earlier positions too.
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D288 (v38): re-pinned — the trend swing_long time_stop optional draw drops
# to p=0.15 (exit-mix relay), so scoped configs flip their timer pick and the
# skipped n_bars randint shifts downstream draws. Licensing harness
# environment-matched: OLD code reproduced every constant exactly; each first
# divergence verified as a trend swing_long exit draw (PRE@2, V27@11). The
# cohort golden (seed 4242) is untouched — its slice hosts no scoped flip.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
_REGIME_GOLDEN_V27_ACTIVE = [
    "d7f9a3f7c58dea33",
    "26d318b70b6157ef",
    "a045c8ed725b63c0",
    "8286541b66527cac",
    "9af608af3f9311f4",
    "b9344d0800f2a3b4",
    "1a67e9c676c269a9",
    "7a2b04389ddf6985",
    "92a3816d0baf6053",
    "f559b676b5125f19",
    "5e3d288ae9134cda",
    "d7acbf9c2e787039",
    "270c5da463424bff",
    "55a43515d605d317",
    "4754afa717d583fd",
]


def test_d264_resid_vix_active_cold_start_golden(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Byte-pin the v27 enumeration sequence (registry serving both new ids). It
    diverges from _REGIME_GOLDEN_V26_ACTIVE once the first trend_continuation
    config draws from the widened directional/R2 pools — the D264 licensed
    change; every pre-v27 golden stays byte-identical (asserted by their own
    tests)."""
    reg = _v27_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_V27_ACTIVE
    assert active != _REGIME_GOLDEN_V26_ACTIVE  # widened trend pools shift the sequence
    # v47 (D328): residual_momentum is xsect-pinned (single-name trend retired), so
    # the resid xsect config leads at position 0 — the v27 slice now diverges from
    # v26 from position 0 (was position 1). Core invariant: active != V26.
    assert active[0] != _REGIME_GOLDEN_V26_ACTIVE[0]
    # at least one config in this slice actually carries a v27 id
    assert any(
        any(
            ind in ("residual_momentum", "vix_term_slope")
            for s in c.signals
            for ind in s.indicators
        )
        for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)
    )


# ---------------------------------------------------------------------------
# D265 (v28): realized_vol ABSOLUTE mean_reversion regime gate — Crucible
# FORGE_mr_absolute_vol_gate_request_2026-07-12. The base fixture already
# serves realized_vol (the X1 vol_target chain), so reachability needs no
# registry wrapper; the ivol-stack test rides _v26_registry. Constants/table
# unit tests: test_mr_grammar_v28.py.
# ---------------------------------------------------------------------------


def test_d265_realized_vol_mr_primary_reachable_and_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Some mean_reversion configs draw realized_vol as the PRIMARY regime gate:
    ABSOLUTE threshold in the asked 0.15-0.30 sweep, op '<', never percentile
    (a percentile IS rv_rank — the diagnosed defect). Every such config is fully
    grammar-valid (the widened R1 accepts it; C1/C4 hold by construction), and
    the vol_target chain guard keeps realized_vol single-role (a vol_target
    sizer's chain would put a second volatility-family signal in the config)."""
    space = build_search_space(grammar, registry)
    seen = 0
    for seed in range(400):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="mean_reversion"
        )
        primary = next(s for s in cfg.signals if s.id == "sig_regime")
        if primary.indicators != ("realized_vol",):
            continue
        seen += 1
        p = primary.params
        assert p["op"] == "<", p
        assert "use_percentile" not in p, p
        assert 0.15 <= float(p["threshold"]) <= 0.30, p
        res = validate(cfg, grammar, registry)
        assert res.valid, f"seed={seed}: {res.errors}"
        assert cfg.sizer.mode != "vol_target", f"chain-guard breach at seed={seed}"
    assert seen > 0, "realized_vol never drawn as the MR primary gate"


def test_d265_ivol_veto_stacks_on_realized_vol_primary(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The asked both-gates shape: absolute realized_vol (volatility — SYSTEMATIC
    protection) + the D263 ivol percentile veto (idiosyncratic_vol — the
    ablation-proven falling-knife veto) AND-stacked in one config, C1-legal
    because the 1.28.0 family split keeps the families distinct."""
    reg = _v26_registry(registry)
    space = build_search_space(grammar, reg)
    stacked = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        regime_sigs = [s for s in cfg.signals if s.role == "regime_filter"]
        primary = next(s for s in regime_sigs if s.id == "sig_regime")
        if primary.indicators != ("realized_vol",):
            continue
        if any(s.id == "sig_regime_veto" and s.indicators == ("ivol",) for s in regime_sigs):
            stacked += 1
            res = validate(cfg, grammar, reg)
            assert res.valid, f"seed={seed}: {res.errors}"
    assert stacked > 0, "ivol veto never stacked on a realized_vol primary"


# ---------------------------------------------------------------------------
# D266 (v29): market_realized_vol — the MARKET-level absolute-RV MR gate
# (Crucible CRUCIBLE_market_realized_vol_registered_2026-07-12; family macro
# BY DESIGN so C1 stacks it with the vol/idio families). Primary (R1 seventh
# gate) AND second MR veto-pool member — "pair it with EITHER existing gate".
# Constants/table unit tests: test_mr_grammar_v29.py.
# ---------------------------------------------------------------------------


def _v29_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """_v26_registry + market_realized_vol (family macro, version 1, lookback 0,
    market-wide) — the live v29 state (their registry serves it since
    registry_snapshot_2026-07-12T053611Z)."""
    market_rv = IndicatorMetadata(
        id="market_realized_vol",
        version=1,
        family="macro",
        lookback=0,
        params_schema={},
        rank_per_name_coherent=False,
        market_wide_by_design=True,
    )
    v26 = _v26_registry(base)
    return v26.model_copy(update={"indicators": (*v26.indicators, market_rv)})


def test_d266_market_rv_mr_primary_reachable_and_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """market_realized_vol draws as the MR PRIMARY gate: ABSOLUTE threshold in
    the 0.15-0.30 sweep, op '<', never percentile; fully grammar-valid. Being
    family macro it does NOT hit the vol_target chain guard (volatility), so
    market-gated configs MAY carry vol_target sizers — validity asserted when
    the pairing occurs."""
    reg = _v29_registry(registry)
    space = build_search_space(grammar, reg)
    seen = 0
    vol_target_paired = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        primary = next(s for s in cfg.signals if s.id == "sig_regime")
        if primary.indicators != ("market_realized_vol",):
            continue
        seen += 1
        p = primary.params
        assert p["op"] == "<", p
        assert "use_percentile" not in p, p
        assert 0.15 <= float(p["threshold"]) <= 0.30, p
        res = validate(cfg, grammar, reg)
        assert res.valid, f"seed={seed}: {res.errors}"
        if cfg.sizer.mode == "vol_target":
            vol_target_paired += 1
            assert res.valid  # macro + the volatility chain: C1-legal
    assert seen > 0, "market_realized_vol never drawn as the MR primary gate"


def test_d266_market_rv_vetoes_on_volatility_primary(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The asked pairing: a VOLATILITY primary (rv_rank / realized_vol) with
    market_realized_vol as the ANDed second gate — C1-legal (macro ≠
    volatility). One veto slot: never ivol AND market_rv in the same config;
    a market_rv PRIMARY never also carries a market_rv veto (per-id family
    guard: macro already present)."""
    reg = _v29_registry(registry)
    space = build_search_space(grammar, reg)
    market_veto_seen = 0
    on_volatility = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        regime_sigs = [s for s in cfg.signals if s.role == "regime_filter"]
        vetoes = [s for s in regime_sigs if s.id == "sig_regime_veto"]
        assert len(vetoes) <= 1, f"two vetoes at seed={seed}"
        primary = next(s for s in regime_sigs if s.id == "sig_regime")
        if vetoes and vetoes[0].indicators == ("market_realized_vol",):
            market_veto_seen += 1
            assert primary.indicators != ("market_realized_vol",), cfg.name
            res = validate(cfg, grammar, reg)
            assert res.valid, f"seed={seed}: {res.errors}"
            p = vetoes[0].params
            assert p["op"] == "<", p
            assert "use_percentile" not in p, p
            if primary.indicators[0] in {"rv_rank", "realized_vol", "vol_regime"}:
                on_volatility += 1
    assert market_veto_seen > 0, "market_realized_vol never drawn as the MR veto"
    assert on_volatility > 0, "market_rv veto never paired with a volatility primary"


def test_d266_veto_generalization_leaves_single_id_pools_byte_identical(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The per-id C1 guard refactor must not perturb single-id veto pools: on the
    v26 fixture (ivol-only MR veto, dsj-only trend veto) the enumeration sequence
    equals the pinned _REGIME_GOLDEN_V26_ACTIVE exactly (also asserted by the
    d263 golden test — duplicated here so a refactor failure names the cause)."""
    reg = _v26_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_V26_ACTIVE


# D266 v29 cold-start golden (seed 7777, max 15) on a registry serving dsj, ivol,
# AND market_realized_vol — the live v29 state. Diverges from
# _REGIME_GOLDEN_V26_ACTIVE at position 3 (the first MR config whose widened
# primary pool / two-member veto draw lands differently; market_rv carriers at
# positions 3 and 11). Every pre-v29 golden stays byte-identical — the fixtures
# don't serve market_realized_vol, and the per-id guard refactor preserves
# single-id-pool rng consumption exactly (asserted by their own tests plus
# test_d266_veto_generalization_leaves_single_id_pools_byte_identical).
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — scoped n_bars attempts at 2, 9 & 12 (same shape as
# _REGIME_GOLDEN_V26_ACTIVE) + the 07-16 universe export shrink (Q50); the
# mutual V26/V29 split sits at position 7 under these pins, prefix relation
# [:3] preserved and asserted.
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D288 (v38): re-pinned — the trend swing_long time_stop optional draw drops
# to p=0.15 (exit-mix relay), so scoped configs flip their timer pick and the
# skipped n_bars randint shifts downstream draws. Licensing harness
# environment-matched: OLD code reproduced every constant exactly; each first
# divergence verified as a trend swing_long exit draw (PRE@2, V27@11). The
# cohort golden (seed 4242) is untouched — its slice hosts no scoped flip.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
_REGIME_GOLDEN_V29_ACTIVE = [
    "a44cd8f2c4edb745",
    "f9695f0ff64a0775",
    "3b43fd7342013488",
    "7a1151e3f8353573",
    "465fd6a56a91528f",
    "f559b676b5125f19",
    "5c836b9f7cd9ce90",
    "bc623b1e6b67996c",
    "e1fffb3db6f1cbdd",
    "d51562fab64f945d",
    "4bacb2bec16db27d",
    "d68ae89893f62345",
    "dd69c9ce38deb87d",
    "53163b623425f893",
    "6e6e0bc6ba2776ea",
]


def test_d266_market_rv_active_cold_start_golden(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Byte-pin the v29 enumeration sequence (registry serving dsj + ivol +
    market_realized_vol). Diverges from _REGIME_GOLDEN_V26_ACTIVE at the first
    MR config touched by the widened pools — the D266 licensed change."""
    reg = _v29_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_V29_ACTIVE
    assert active != _REGIME_GOLDEN_V26_ACTIVE
    assert active[:3] == _REGIME_GOLDEN_V26_ACTIVE[:3]  # split at the first eligible MR config
    # v47 (D328): market_realized_vol is an MR primary gate; single-name MR is
    # retired, so it manifests only on xsect MR (needs a share). Verify on the
    # xsect (production) path. Dedicated coverage: the reachable test above.
    assert any(
        any("market_realized_vol" in s.indicators for s in c.signals)
        for c in enumerate_candidates(
            grammar, reg, 7777, max_candidates=15, rank_combiner_share={"mean_reversion": 0.6}
        )
    )


# ---------------------------------------------------------------------------
# D270 (v31): capitulation-bounce — `momentum` drop-trigger as a mean_reversion
# directional (Crucible FORGE_capitulation_bounce_generation_request_2026-07-12).
# §3.5 C2 per-id carve-out (operator-approved loosening, OPEN_PROPOSALS
# e9d74318); gate PINNED to rv_rank op ">" [50, 80] (elevated vol — the
# intended-strength condition the probe's coding bug left inert); veto slot
# skipped (calm-side vetoes contradict the thesis); time_stop n_bars [5, 15]
# (probe hold 10 td; the engine default is 5 and Forge never sampled it).
# Constants/table/C2 unit tests: test_capitulation_bounce_v31.py.
# ---------------------------------------------------------------------------


def _v31_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """_v29_registry + the parameterized `momentum` (family trend, version 1,
    rank-coherent) — the live v31 state (their registry has served it all
    along; it was Forge-side dark)."""
    momentum = IndicatorMetadata(
        id="momentum",
        version=1,
        family="trend",
        lookback=504,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    v29 = _v29_registry(base)
    return v29.model_copy(update={"indicators": (*v29.indicators, momentum)})


def test_d270_momentum_pools_scoped_to_mean_reversion(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The C2 carve-out admits momentum to MR's directional pool ONLY when the
    registry serves it; the trend pool PIN-EXCLUDES it (contrarian op +
    time-stop chassis are wrong for continuation — and trend draws must stay
    byte-identical)."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    assert "momentum" in space.directional_indicators_by_hypothesis["mean_reversion"]
    assert "momentum" not in space.directional_indicators_by_hypothesis["trend_continuation"]
    base_space = build_search_space(grammar, registry)
    assert "momentum" not in base_space.directional_indicators_by_hypothesis["mean_reversion"]


def test_d270_capitulation_reachable_and_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The full capitulation genome, v35/D280 BARE-DROP shape: momentum
    directional (absolute drop threshold, lookback/skip knobs) x NO regime
    gate (the v31 rv_rank pin dropped on Crucible's adjudication; R1-exempt)
    x {swing_short, swing_mid} (the k=1 rider) x CALL-default x no veto x
    confluence-only x never vol_target — every emitted instance fully
    grammar-valid."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    seen = 0
    time_stop_seen = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        directional = next(s for s in cfg.signals if s.role == "directional")
        if directional.indicators != ("momentum",):
            continue
        seen += 1
        p = directional.params
        assert p["op"] == "<", p
        assert "use_percentile" not in p, p
        assert -0.083 <= float(p["threshold"]) <= -0.041, p
        assert isinstance(p["lookback"], int), p
        assert 3 <= p["lookback"] <= 10, p
        assert p["skip"] == 0, p
        # D280 (v35): BARE-DROP — no regime gate of any kind.
        assert not [s for s in cfg.signals if s.role == "regime_filter"], cfg.signals
        # chassis: probe bucket + the k=1 swing_short rider, no calm-side
        # veto, single-name-only, no vol chain
        assert cfg.dte_bucket in ("swing_short", "swing_mid"), cfg.dte_bucket
        assert not any(s.id == "sig_regime_veto" for s in cfg.signals), cfg.signals
        assert cfg.combiner.type == "confluence", cfg.combiner
        assert cfg.sizer.mode != "vol_target", cfg.sizer
        for ex in cfg.exits:
            if ex.id == "time_stop":
                time_stop_seen += 1
                n_bars = ex.params.get("n_bars")
                assert isinstance(n_bars, int), ex.params
                assert 5 <= n_bars <= 15, ex.params
        res = validate(cfg, grammar, reg)
        assert res.valid, f"seed={seed}: {res.errors}"
    assert seen > 0, "momentum never drawn as the MR directional"
    assert time_stop_seen > 0, "no capitulation config ever drew the time_stop exit"


def test_d270_momentum_never_anchors_trend(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The pool pin holds end-to-end: no trend_continuation draw ever anchors
    on momentum (its threshold entry would otherwise auto-admit it — family
    trend — with contrarian '<' semantics under a continuation thesis)."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        directional = next(s for s in cfg.signals if s.role == "directional")
        assert directional.indicators != ("momentum",), f"seed={seed}"


def test_d270_non_momentum_time_stop_params_unchanged(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The n_bars emission is scoped to exactly the evidenced cells — D270's
    premise ("capitulation ONLY") widened by v36/D282 to the range table:
    capitulation U[5,15] (both buckets, veto-frozen), MR U[8,12] (D291/v40:
    bucket-wide, narrowed from swing_mid [8,15]), trend swing_long U[8,10].
    Every OTHER hypothesis/bucket keeps the bare time_stop (engine default 5),
    so the untouched slices stay untouched (the D169 concern, cell-scoped)."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    checked_bare = 0
    checked_scoped = 0
    for seed in range(400):
        cfg = sample_config(space, reg, random.Random(seed))
        directional = next(s for s in cfg.signals if s.role == "directional")
        if directional.indicators == ("momentum",):
            continue
        scoped_range = None
        if cfg.hypothesis == "mean_reversion":
            scoped_range = (8, 12)  # D291 (v40): the family box, all buckets
        elif cfg.hypothesis == "trend_continuation" and cfg.dte_bucket == "swing_long":
            scoped_range = (8, 10)
        elif cfg.hypothesis == "volatility_event":
            scoped_range = (4, 7)  # D290 (v39): the required ve hold, both buckets
        for ex in cfg.exits:
            if ex.id != "time_stop":
                continue
            if scoped_range is None:
                checked_bare += 1
                assert ex.params == {}, (cfg.hypothesis, cfg.dte_bucket, ex.params)
            else:
                checked_scoped += 1
                n_bars = ex.params.get("n_bars")
                assert isinstance(n_bars, int), (cfg.hypothesis, cfg.dte_bucket, ex.params)
                low, high = scoped_range
                assert low <= n_bars <= high, (cfg.hypothesis, cfg.dte_bucket, ex.params)
    assert checked_bare > 0, "no bare time_stop draws sampled"
    assert checked_scoped > 0, "no scoped time_stop draws sampled"


def test_d270_v29_golden_byte_identical_without_momentum(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Hard rule #6 guard on the plumbing refactor (directional_id threaded
    into _regime_signal_params/_build_exits + the veto short-circuit): on a
    registry NOT serving momentum the sequence equals the pinned v29 golden
    exactly (also asserted by the d266 golden test — duplicated so a failure
    names this cause)."""
    reg = _v29_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_V29_ACTIVE


# D270 v31 cold-start golden (seed 7777, max 15) on a registry serving dsj, ivol,
# market_realized_vol AND the parameterized momentum — the live v31 state.
# Diverges from _REGIME_GOLDEN_V29_ACTIVE at position 3 (the first MR config:
# the C2-carved momentum widens MR's directional pool, reshuffling its draw).
# No carrier lands in this 15-slice at this seed (the first is at position 24 —
# asserted below over a 30-slice); every pre-v31 golden stays byte-identical:
# their fixtures never serve momentum, the trend pool pin-excludes it where
# served, and the directional_id plumbing defaults keep all other paths'
# rng consumption exact (asserted by their own tests plus
# test_d270_v29_golden_byte_identical_without_momentum).
# D278 (v34): re-pinned — the BKNG/BRK.B untradeable-name exclusion shifts the
# underlying draw on (nearly) every position, and gamma_flip left the MR/trend
# regime pools; relational splits between the goldens are preserved (asserted).
# D282 (v36): re-pinned — scoped n_bars attempts at 2 & 12 (the capitulation
# path itself is byte-identical: same U[5,15] range, same draw count — the
# veto-frozen D270 box) + the 07-16 universe export shrink (Q50); the mutual
# V29/V31 split sits at position 13 under these pins, prefix relation [:3]
# preserved and asserted.
# D286 (v37): re-pinned — the SOXX/LLY/GS/MSTR untradeable-name exclusion
# shifts the single-name underlying draw (pool 118->114; licensing harness
# environment-matched: OLD code reproduced every constant exactly, and each
# first divergence is a single-name draw — position 0's BMY maps identically
# by index). The resid 50/50 coin touches only fixtures serving resid (v27+).
# Relational splits re-asserted by the tests below.
# D288 (v38): re-pinned — the trend swing_long time_stop optional draw drops
# to p=0.15 (exit-mix relay), so scoped configs flip their timer pick and the
# skipped n_bars randint shifts downstream draws. Licensing harness
# environment-matched: OLD code reproduced every constant exactly; each first
# divergence verified as a trend swing_long exit draw (PRE@2, V27@11). The
# cohort golden (seed 4242) is untouched — its slice hosts no scoped flip.
# D290 (v39): re-pinned — the ve exit-schema fix (event_passed_exit OUT,
# time_stop REQUIRED with n_bars U[4,7]) changes every ve config's exit draws.
# Licensing harness environment-matched: OLD code reproduced every constant
# exactly; every first divergence is a volatility_event config carrying the
# new stack (seed-7777 goldens @0 — their first config is ve; cohort @8).
_REGIME_GOLDEN_V31_ACTIVE = [
    "a44cd8f2c4edb745",
    "f9695f0ff64a0775",
    "3b43fd7342013488",
    "7a1151e3f8353573",
    "465fd6a56a91528f",
    "f559b676b5125f19",
    "5c836b9f7cd9ce90",
    "bc623b1e6b67996c",
    "e1fffb3db6f1cbdd",
    "d27ed0d03bd5c5d1",
    "d51562fab64f945d",
    "4bacb2bec16db27d",
    "d68ae89893f62345",
    "a887f0edab4f3842",
    "cde55c964da3d4ae",
]


def test_d270_capitulation_active_cold_start_golden(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Byte-pin the v31 enumeration sequence (registry serving momentum on top
    of the v29 set). Diverges from _REGIME_GOLDEN_V29_ACTIVE at the first MR
    config touched by the widened directional pool — the D270 licensed change —
    and a full capitulation genome appears within the scan window (position 71
    since the D309/v43 pool shift; see the comment below)."""
    reg = _v31_registry(registry)
    active = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=15)]
    assert active == _REGIME_GOLDEN_V31_ACTIVE
    # The D291/v40 stream re-pin moved the first capitulation genome (and with
    # it the v29-vs-v31 split) to position 30 — the 15-length goldens now
    # coincide, so the divergence claim is asserted on a live 40-window pair.
    # D309 (v43): the 30-name exclusion's pool shift moved the first
    # capitulation genome again, 30 → 71 — the carriers scan widens to 80
    # (same landmark, same claim; the v29-vs-v31 divergence stays in-40).
    reg29 = _v29_registry(registry)
    s29 = [c.config_hash for c in enumerate_candidates(grammar, reg29, 7777, max_candidates=40)]
    s31 = [c.config_hash for c in enumerate_candidates(grammar, reg, 7777, max_candidates=40)]
    assert s31 != s29  # widened MR pool shifts the sequence
    carriers = [
        c
        for c in enumerate_candidates(grammar, reg, 7777, max_candidates=80)
        if any(s.role == "directional" and s.indicators == ("momentum",) for s in c.signals)
    ]
    assert carriers, "no capitulation genome in the first 80 draws"


# ---------------------------------------------------------------------------
# D286 (v37) — cohort-read follow-ups: 4 outcome-starved names out of
# single-name sampling; the resid two-arm gate draw un-starved (uniform coin,
# the D119 "learned weights must not bias an experimental draw" precedent);
# the conftest universe pin (Q50 durable fix) asserted active.
# ---------------------------------------------------------------------------


def test_v37_untradeable_names_never_drawn() -> None:
    """D286 (v37): SOXX/LLY/GS/MSTR join the structurally-untradeable exclusion
    (Crucible row-45 trailing-window guard: 96.1-99.8% WF-zero on ~1,000-run
    samples each) — the single-name draw must never emit them. Same terms as the
    D278 frozen list: re-admission on Crucible's relay only."""
    from forge.enumeration.sampler import _pick_underlying

    rng = random.Random(0xD286)
    drawn = {_pick_underlying(rng, "volatility_event", ()) for _ in range(4000)}
    assert drawn.isdisjoint({"SOXX", "LLY", "GS", "MSTR"})
    # Sanity: the draw still covers most of the pinned 118-name July universe.
    assert len(drawn) > 80


def test_v37_resid_gate_mix_ignores_learned_weights(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D286 (v37): the resid two-arm sweep is an EXPERIMENT — adversarial learned
    regime-gate weights (hurst minting, vix_term_slope crushed) must NOT starve
    the vix arm. The pinned pair draws a uniform coin (D119 precedent), so the
    emitted resid gate mix stays ~50/50 regardless of the posteriors that starved
    it to ~94% hurst in production (Crucible's 07-16 cohort read)."""
    from collections import Counter

    reg = _v27_registry(registry)  # serves residual_momentum + vix_term_slope
    space = build_search_space(grammar, reg)
    weights: dict[tuple[str, str, str, str], float] = {}
    for d in space.directional_indicators_by_hypothesis["trend_continuation"]:
        for b in space.dte_buckets:
            weights[("trend_continuation", d, b, "hurst")] = 0.50
            weights[("trend_continuation", d, b, "vix_term_slope")] = 0.001

    gates: Counter[str] = Counter()
    for seed in range(3000):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="trend_continuation",
            regime_gate_yield_weights=weights,
        )
        directional = next(s for s in cfg.signals if s.role == "directional")
        if directional.indicators[0] != "residual_momentum":
            continue
        regime = next((s for s in cfg.signals if s.role == "regime_filter"), None)
        if regime is None:
            continue
        gates[regime.indicators[0]] += 1

    total = gates.get("hurst", 0) + gates.get("vix_term_slope", 0)
    assert total >= 100, f"too few resid draws to judge the mix: {gates}"
    vix_share = gates.get("vix_term_slope", 0) / total
    assert 0.35 < vix_share < 0.65, f"vix arm starved/flooded despite the pin: {gates}"


def test_v37_universe_pin_active_by_default() -> None:
    """Q50 durable fix (D286/v37): the conftest autouse pin freezes the sampler
    universe to the 2026-07-16 export snapshot — a live tier export can no longer
    move test draws (the class that broke 9 goldens at position 0 in both the v34
    and v36 deploys ends here)."""
    import forge.enumeration.sampler as sampler_mod
    from tests.fixtures.universe_snapshot import UNIVERSE_SNAPSHOT_2026_07_16

    assert sampler_mod._load_underlyings() == UNIVERSE_SNAPSHOT_2026_07_16
    assert len(UNIVERSE_SNAPSHOT_2026_07_16) == 118
