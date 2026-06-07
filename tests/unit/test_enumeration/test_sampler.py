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

from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar, validate
from forge.grammar.custom_predicates import (
    _C2_HYPOTHESIS_FAMILIES,
    _P2_ENTRY_DTE,
    _P3_DELTA_BAND,
    _R1_IV_RANK_INDICATOR,
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
            assert regime_id == _R1_IV_RANK_INDICATOR, (
                f"R1 violated at seed={seed}: regime={regime_id}"
            )
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


def test_p2_selector_dte_in_entry_window(grammar: Grammar, registry: RegistrySnapshot) -> None:
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        window_low, window_high = _P2_ENTRY_DTE[cfg.dte_bucket]
        assert window_low <= cfg.selector.dte_min, f"P2 dte_min below window at seed={seed}"
        assert cfg.selector.dte_max <= window_high, f"P2 dte_max above window at seed={seed}"


def test_p3_delta_target_in_band(grammar: Grammar, registry: RegistrySnapshot) -> None:
    for seed in range(30):
        cfg = _sample(grammar, registry, seed=seed)
        band_low, band_high = _P3_DELTA_BAND[cfg.dte_bucket]
        assert band_low <= cfg.selector.delta_target <= band_high, (
            f"P3 delta_target out of band at seed={seed}: "
            f"{cfg.selector.delta_target} not in [{band_low}, {band_high}]"
        )


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
    """An observed-but-zero-reward regime is floored (~0.05), so it keeps a
    minimum sampling budget rather than collapsing to never-sampled."""
    regimes = ("a", "b")
    weights = {"a": 1.0, "b": 0.0}
    counts = _count_picks("relative_value", regimes, weights, seed=1, n=3000)
    # b floored to 0.05 vs a's 1.0 -> ~0.05/1.05 ≈ 4.8% of 3000 ≈ 140
    assert counts.get("b", 0) > 50


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


def test_sampler_reaches_every_hypothesis(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Across 300 seeds, every samplable hypothesis should appear at least
    once. Catches biased sampling that locks onto one hypothesis.

    D066: ``tail_hedge`` is excluded — it's overlay-only.
    D098 (v5): ``regime_arbitrage`` is excluded — dropped from enumeration as
    a low-yield-by-construction grammar-iteration decision. Both are in
    ``NON_ENUMERABLE_HYPOTHESES``; see the D098 invariants for the leak guard."""
    seen: set[str] = set()
    for seed in range(300):
        cfg = _sample(grammar, registry, seed=seed)
        seen.add(cfg.hypothesis)
    assert seen == {
        "trend_continuation",
        "mean_reversion",
        "relative_value",
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


def test_d098_relative_value_underlying_is_none(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """D098 (v5): relative_value is a pairs strategy — its underlying is the
    pair itself (resolved Crucible-side), so the config must carry
    ``underlying=None``. Reverts D079's single-ticker anchor (no longer needed
    after Crucible 4f5271f loads all pair legs regardless of tier)."""
    space = build_search_space(grammar, registry)
    rv = sample_config(space, registry, random.Random(3), forced_hypothesis="relative_value")
    assert rv.hypothesis == "relative_value"
    assert rv.underlying is None


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


def test_load_underlyings_returns_fallback_when_no_export(tmp_path: Path) -> None:
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


def test_load_underlyings_reads_export(tmp_path: Path) -> None:
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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
