"""Unit tests for ``forge.enumeration.search_space``.

Covers:
- Determinism (§13.1 / hard rule #6) of `build_search_space`.
- C2 / R1 / R2 / R3 / X1 / X2 / P4 resolution against the test registry.
- Sorted/canonical ordering across every collection.
- Empty-pool handling when a registry lacks a required indicator.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from crucible_contracts import (
    MANDATORY_EXIT_IDS,
    IndicatorMetadata,
    RegistrySnapshot,
)

from forge.enumeration.search_space import (
    SearchSpace,
    _build_regime_pool,
    build_search_space,
    rank_excluded_indicator_ids,
)
from forge.grammar import load_grammar
from forge.grammar.custom_predicates import (
    _P2_ENTRY_DTE,
    _P3_DELTA_BAND,
)
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


@pytest.fixture(scope="module")
def v1_grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


@pytest.fixture(scope="module")
def space(v1_grammar: object, registry: RegistrySnapshot) -> SearchSpace:
    return build_search_space(v1_grammar, registry)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Determinism — §13.1 / CLAUDE.md hard rule #6
# ---------------------------------------------------------------------------


def test_build_search_space_is_deterministic(
    v1_grammar: object,
    registry: RegistrySnapshot,
) -> None:
    """Two builds from the same (grammar, registry) must compare equal —
    this is the prerequisite for the §13.1 enumeration-determinism test."""
    a = build_search_space(v1_grammar, registry)  # type: ignore[arg-type]
    b = build_search_space(v1_grammar, registry)  # type: ignore[arg-type]
    assert a == b


def test_search_space_is_frozen(space: SearchSpace) -> None:
    """Catches accidental mutation: dataclass(frozen=True) must hold."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        space.hypotheses = ("only_one",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Top-level categorical axes
# ---------------------------------------------------------------------------


def test_hypotheses_in_canonical_order(space: SearchSpace) -> None:
    assert space.hypotheses == (
        "trend_continuation",
        "mean_reversion",
        "regime_arbitrage",
        "relative_value",
        "volatility_event",
        "tail_hedge",
        "event_momentum",  # v12 / D109 — appended, matches contracts Literal order
    )


def test_dte_buckets_in_canonical_order(space: SearchSpace) -> None:
    assert space.dte_buckets == ("swing_short", "swing_mid", "swing_long")


def test_sizer_modes_sorted_from_registry(space: SearchSpace) -> None:
    assert space.sizer_modes == ("fixed_risk_pct", "fractional_kelly", "vol_target")


def test_samplable_sizer_modes_when_all_x_rules_met(space: SearchSpace) -> None:
    """The test registry has realized_vol + expected_value_estimator, so
    every sizer mode is samplable."""
    assert space.samplable_sizer_modes == (
        "fixed_risk_pct",
        "fractional_kelly",
        "vol_target",
    )


# ---------------------------------------------------------------------------
# Indicators by family — sorted within each family, sorted families
# ---------------------------------------------------------------------------


def test_indicators_by_family_contains_trend_strength(space: SearchSpace) -> None:
    """Phase 2 prerequisite: post-contracts-v1.4.0, adx + hurst live in the
    `trend_strength` family rather than `volatility` (D019)."""
    assert space.indicators_by_family["trend_strength"] == ("adx", "hurst")


def test_indicators_by_family_lists_are_sorted(space: SearchSpace) -> None:
    for family, ids in space.indicators_by_family.items():
        assert list(ids) == sorted(ids), f"family {family} indicators not sorted"


def test_indicators_by_family_keys_are_sorted(space: SearchSpace) -> None:
    keys = list(space.indicators_by_family.keys())
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# §3.5 C2 — directional family pool per hypothesis
# ---------------------------------------------------------------------------


def test_directional_pool_trend_continuation(space: SearchSpace) -> None:
    """D138 (v19): `smart_money` joins trend_continuation's C2 families (for
    option_momentum). The C2 build-pool is family-level, so the minimal
    registry's only smart_money member, `expected_value_estimator`, appears here
    too — but it is pinned OUT at sample time (directional range nulled →
    is_threshold_skippable), so it is never an actual directional. The live
    registry adds option_momentum, the real activation target."""
    assert space.directional_indicators_by_hypothesis["trend_continuation"] == (
        "ema_50",
        "expected_value_estimator",
        "momentum_252",
    )


def test_directional_pool_mean_reversion(space: SearchSpace) -> None:
    """D062 widened mean_reversion's C2 allowlist to include
    `dealer_positioning` (call/put walls and gamma-flip are MR magnets)."""
    assert space.directional_indicators_by_hypothesis["mean_reversion"] == (
        "call_wall_distance_pct",
        "gex",
        "rsi_14",
        "rsi_2",
    )


def test_directional_pool_relative_value_is_pairs_only(space: SearchSpace) -> None:
    assert space.directional_indicators_by_hypothesis["relative_value"] == ("pairs_zscore",)


def test_directional_pool_volatility_event_is_iv_plus_flow(
    space: SearchSpace,
) -> None:
    """C2 allows iv_structure + flow + dealer_positioning for volatility_event
    (D062 added dealer_positioning alongside Crucible's 6 dealer indicators)."""
    assert space.directional_indicators_by_hypothesis["volatility_event"] == (
        "call_wall_distance_pct",
        "gex",
        "iv_rank",
        "put_call_flow",
    )


def test_directional_pool_tail_hedge_is_macro(space: SearchSpace) -> None:
    assert space.directional_indicators_by_hypothesis["tail_hedge"] == ("vix_level",)


def test_directional_pool_regime_arbitrage_is_any_family(
    space: SearchSpace,
    registry: RegistrySnapshot,
) -> None:
    """C2 maps regime_arbitrage to None (any family allowed) — pool should
    equal every registered indicator id, sorted."""
    expected = tuple(sorted(ind.id for ind in registry.indicators))
    assert space.directional_indicators_by_hypothesis["regime_arbitrage"] == expected


# ---------------------------------------------------------------------------
# §3.5 R1 / R2 / R3 — regime gate pool per hypothesis
# ---------------------------------------------------------------------------


def test_regime_pool_trend_continuation_is_r2(space: SearchSpace) -> None:
    """R2: trend_continuation regime gate is adx, hurst, or rv_rank (D077).
    (The minimal fixture registry omits gamma_flip_distance_pct; D107's
    gamma-gate pool membership is covered directly in
    `test_regime_pool_trend_continuation_includes_gamma_flip`.)"""
    assert space.regime_indicators_by_hypothesis["trend_continuation"] == (
        "adx",
        "hurst",
        "rv_rank",
    )


def test_regime_pool_trend_continuation_excludes_gamma_flip() -> None:
    """D278 (v34) retires the D107 R2 admission from EMISSION: the census read
    the gate at 0.1% component rate / 79% WF=0.0 across 12,088 uses — dead in
    every pairing, not just the v33-flagged dsj one. Even when the registry
    serves it, the trend pool omits it; the R2 predicate still accepts it
    (lineage validity)."""
    pool = _build_regime_pool(
        {"adx", "hurst", "rv_rank", "gamma_flip_distance_pct"},
        single_name_only_ids=frozenset({"gamma_flip_distance_pct"}),
    )
    assert pool["trend_continuation"] == (
        "adx",
        "hurst",
        "rv_rank",
    )


def test_regime_pool_mean_reversion_iv_rank_and_hurst(space: SearchSpace) -> None:
    """R1: mean_reversion regime gates. The minimal fixture carries iv_rank, hurst,
    rv_rank, and realized_vol (omits gamma_flip_distance_pct / vol_regime), so the
    D150 + D167 + D265 widenings make the pool ('hurst', 'iv_rank', 'realized_vol',
    'rv_rank'), sorted. The gamma-gate RETIREMENT (v34/D278) is covered in
    `test_regime_pool_mean_reversion_excludes_gamma_flip`."""
    assert space.regime_indicators_by_hypothesis["mean_reversion"] == (
        "hurst",
        "iv_rank",
        "realized_vol",
        "rv_rank",
    )


def test_regime_pool_mean_reversion_excludes_gamma_flip() -> None:
    """D278 (v34) retires the D107 R1 admission from EMISSION (census: dead in
    every MR pairing too — 94-97% WF=0 as a directional died in v33, the gate
    side dies here). Even when the registry serves it, MR's pool omits it;
    the R1 predicate still accepts it (lineage validity)."""
    pool = _build_regime_pool(
        {"iv_rank", "gamma_flip_distance_pct"},
        single_name_only_ids=frozenset({"gamma_flip_distance_pct", "iv_rank"}),
    )
    assert pool["mean_reversion"] == ("iv_rank",)


def test_regime_pool_mean_reversion_includes_hurst() -> None:
    """D150 (v20, MR side): when the registry carries `hurst`, it joins
    mean_reversion's R1 regime pool as a third ranging gate (the mean-reverting
    H<0.5 side). Pool is sorted. Tested on `_build_regime_pool` directly so the
    shared minimal fixture (and golden sampler-sequence tests) stays stable."""
    pool = _build_regime_pool(
        {"iv_rank", "gamma_flip_distance_pct", "hurst"},
        single_name_only_ids=frozenset({"gamma_flip_distance_pct", "iv_rank"}),
    )
    # gamma_flip absent since v34/D278 (emission retirement).
    assert pool["mean_reversion"] == ("hurst", "iv_rank")


def test_regime_pool_mean_reversion_includes_rv_rank() -> None:
    """D167 (v22, MR side): when the registry carries `rv_rank`, it joins
    mean_reversion's R1 regime pool as a fourth gate (cheap realized vol, the
    calm/reversion-friendly regime — Crucible: rv_rank ⟂ and DOMINATES hurst).
    rv_rank is rank-coherent (NOT single-name-only), so the universe-template
    exclusion doesn't touch the single-name MR pool. Pool is sorted. Tested on
    `_build_regime_pool` directly so the shared minimal fixture stays stable."""
    pool = _build_regime_pool(
        {"iv_rank", "gamma_flip_distance_pct", "hurst", "rv_rank"},
        single_name_only_ids=frozenset({"gamma_flip_distance_pct", "iv_rank"}),
    )
    # gamma_flip absent since v34/D278 (emission retirement).
    assert pool["mean_reversion"] == (
        "hurst",
        "iv_rank",
        "rv_rank",
    )


def test_regime_pool_volatility_event_is_event_proximity(
    space: SearchSpace,
) -> None:
    """R3: volatility_event regime gate is days_to_earnings or days_to_fomc."""
    assert space.regime_indicators_by_hypothesis["volatility_event"] == (
        "days_to_earnings",
        "days_to_fomc",
    )


def test_regime_pool_unconstrained_hypothesis_uses_full_registry(
    space: SearchSpace,
    registry: RegistrySnapshot,
) -> None:
    """No R-rule for regime_arbitrage/tail_hedge → any registry indicator may
    serve. C4 is enforced at sample time. (relative_value lost its unconstrained
    pool to the D112 dealer exclusion — next test.)"""
    expected = tuple(sorted(ind.id for ind in registry.indicators))
    for hyp in ("regime_arbitrage", "tail_hedge"):
        assert space.regime_indicators_by_hypothesis[hyp] == expected, hyp


def test_regime_pool_relative_value_excludes_dealer_positioning(
    space: SearchSpace,
    registry: RegistrySnapshot,
) -> None:
    """D112 (v13): relative_value is the universe template (underlying=None —
    Crucible scans the universe for legs), so a dealer regime gate multiplies
    the per-bar greek grid by every name: the 5-14 min headline tail. The
    decided universe x dealer cohort (n=199) cleared no §8.7 gate (mean WF
    -0.129). Dealer indicators are single-name only."""
    dealer = {ind.id for ind in registry.indicators if ind.family == "dealer_positioning"}
    assert dealer, "fixture registry must carry dealer indicators for this test"
    pool = set(space.regime_indicators_by_hypothesis["relative_value"])
    assert not pool & dealer


def test_regime_pool_relative_value_excludes_chain_reading(
    space: SearchSpace,
    registry: RegistrySnapshot,
) -> None:
    """D116 (v14): relative_value's universe scan also drops the chain-reading
    ids (iv_rank, put_call_flow) — the same per-name chain-source decoupling as
    D112's dealer cut, confirmed class-wide by Crucible's fail-open sweep (Q33:
    iv_rank = garbage_mismatch, put_call_flow = hidden uniform SPY reference).
    Together with the dealer exclusion the rv pool is registry minus the
    single-name-only set; single-name hypotheses keep the full pool."""
    dealer = {ind.id for ind in registry.indicators if ind.family == "dealer_positioning"}
    chain = {"iv_rank", "put_call_flow"} & {ind.id for ind in registry.indicators}
    assert chain, "fixture registry must carry chain-reading indicators for this test"
    pool = set(space.regime_indicators_by_hypothesis["relative_value"])
    assert not pool & chain
    # D118 (v15) → D125 (v16) re-pin: the exclusion is flag-derived now —
    # rv pool = registry minus `rank_excluded_indicator_ids` (dealer family +
    # every NOT-coherent/NOT-market-wide id). vs v15 this also drops
    # pairs_zscore from the GATE pool (it is flag-excluded in Crucible's 13;
    # it remains rv's pairs-path DIRECTIONAL, which this pool never governed).
    assert pool == {ind.id for ind in registry.indicators} - rank_excluded_indicator_ids(registry)
    # The flag key subsumes the old explicit sets — dealer/chain stay out.
    assert not pool & dealer


def test_regime_pool_relative_value_excludes_rank_decoupled(
    space: SearchSpace,
    registry: RegistrySnapshot,
) -> None:
    """D118 (v15): re-keys the universe-template gate exclusion on Crucible's
    indicator→mode map (`rank_gate_class_map.json`, 2026-06-09): the broken
    class is per-name DECOUPLING from the evaluated sym, not chain reads.
    Beyond D112's dealer family and D116's chain-reading ids, the map adds the
    per-name event/DB indicators — `sue`, `days_since_earnings`,
    `days_to_earnings` (keyed on ``params["symbol"]``, never threaded on
    universe paths → inert fail-open) and `expected_value_estimator` (reads the
    runs DB keyed on ``params["underlying"]`` → the reference's EV for every
    name; rv's top historical gate, structurally ignored on the pairs path) —
    none may gate a universe scan. Keep-side: the R-rule-free single-name
    hypotheses keep the full pool (pinned by
    test_regime_pool_unconstrained_hypothesis_uses_full_registry above —
    the composable path pins the symbol, where all four are coherent)."""
    decoupled = {"sue", "days_since_earnings", "days_to_earnings", "expected_value_estimator"}
    present = decoupled & {ind.id for ind in registry.indicators}
    assert present == decoupled, "fixture registry must carry all four decoupled ids"
    pool = set(space.regime_indicators_by_hypothesis["relative_value"])
    assert not pool & decoupled


# ---------------------------------------------------------------------------
# §3.5 X1 / X2 — sizer mode → required indicator
# ---------------------------------------------------------------------------


def test_sizer_required_vol_target_is_realized_vol(space: SearchSpace) -> None:
    assert space.sizer_required_indicator["vol_target"] == "realized_vol"


def test_sizer_required_fractional_kelly_is_ev_estimator(
    space: SearchSpace,
) -> None:
    assert space.sizer_required_indicator["fractional_kelly"] == "expected_value_estimator"


def test_sizer_required_fixed_risk_pct_has_no_entry(space: SearchSpace) -> None:
    """``fixed_risk_pct`` has no §3.5 X-rule, so the sparse map omits it.
    The sampler reads via ``.get()``; ``None`` means "no chaining needed."""
    assert "fixed_risk_pct" not in space.sizer_required_indicator
    assert space.sizer_required_indicator.get("fixed_risk_pct") is None


def test_unsamplable_mode_drops_when_indicator_missing(
    v1_grammar: object,
) -> None:
    """If realized_vol is absent from the registry, ``vol_target`` falls out
    of ``samplable_sizer_modes`` AND out of ``sizer_required_indicator``.
    The sampler never picks an X-rule-unsatisfiable mode."""
    empty_realized_vol_registry = RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="adx",
                version=1,
                family="trend_strength",
                lookback=14,
                params_schema={},
            ),
        ),
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("vol_target",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
        data_start_date=date(2022, 1, 1),
    )
    space = build_search_space(v1_grammar, empty_realized_vol_registry)  # type: ignore[arg-type]
    assert "vol_target" not in space.samplable_sizer_modes
    assert "vol_target" not in space.sizer_required_indicator
    assert space.samplable_sizer_modes == ()


# ---------------------------------------------------------------------------
# §3.5 P2 / P3 — entry-DTE window + delta-band by bucket
# ---------------------------------------------------------------------------


def test_dte_entry_window_by_bucket_matches_phase1_table(
    space: SearchSpace,
) -> None:
    """P2 entry-side windows propagate verbatim from Phase 1's _P2_ENTRY_DTE."""
    assert dict(space.dte_entry_window_by_bucket) == dict(_P2_ENTRY_DTE)


def test_delta_band_by_bucket_matches_phase1_table(space: SearchSpace) -> None:
    """P3 delta bands propagate verbatim from Phase 1's _P3_DELTA_BAND."""
    assert dict(space.delta_band_by_bucket) == dict(_P3_DELTA_BAND)


# ---------------------------------------------------------------------------
# §3.5 P4 — risk_pct range resolved from grammar
# ---------------------------------------------------------------------------


def test_p4_risk_pct_range_from_grammar(space: SearchSpace) -> None:
    """v1 grammar.yaml's P4 numerical_range rule provides (0.005, 0.02)."""
    assert space.risk_pct_range == (0.005, 0.02)


# ---------------------------------------------------------------------------
# §3.5 S5 / E1 — exits
# ---------------------------------------------------------------------------


def test_e1_mandatory_matches_contracts(space: SearchSpace) -> None:
    """The mandatory-exit tuple is sorted MANDATORY_EXIT_IDS from contracts."""
    assert space.e1_mandatory == tuple(sorted(MANDATORY_EXIT_IDS))


def test_s5_required_includes_trend_trailing_atr(space: SearchSpace) -> None:
    assert "trailing_atr" in space.s5_required_by_hypothesis["trend_continuation"]


def test_s5_forbidden_for_trend_includes_hard_profit_target(
    space: SearchSpace,
) -> None:
    assert "hard_profit_target" in space.s5_forbidden_by_hypothesis["trend_continuation"]


def test_s5_required_volatility_event_has_iv_crush_and_time_stop(
    space: SearchSpace,
) -> None:
    """D290 (v39): time_stop replaced event_passed_exit as the required ve hold
    (the fallback-mode truncation; Crucible's 07-19 close-out)."""
    required = space.s5_required_by_hypothesis["volatility_event"]
    assert "iv_crush_exit" in required
    assert "time_stop" in required
    assert "event_passed_exit" not in required


# ---------------------------------------------------------------------------
# Empty-pool handling (registry-driven)
# ---------------------------------------------------------------------------


def test_empty_directional_pool_when_family_absent(v1_grammar: object) -> None:
    """If the registry has no trend-family indicator, trend_continuation's
    directional pool is empty. The sampler will decline to emit configs for
    that hypothesis."""
    no_trend_registry = RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="rsi_14",
                version=1,
                family="mean_reversion",
                lookback=14,
                params_schema={},
            ),
        ),
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
        data_start_date=date(2022, 1, 1),
    )
    space = build_search_space(v1_grammar, no_trend_registry)  # type: ignore[arg-type]
    assert space.directional_indicators_by_hypothesis["trend_continuation"] == ()
