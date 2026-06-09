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
    assert space.directional_indicators_by_hypothesis["trend_continuation"] == (
        "ema_50",
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


def test_regime_pool_trend_continuation_includes_gamma_flip() -> None:
    """D107 (v11 / H3): when the registry carries `gamma_flip_distance_pct` (it
    does live — enumerated 3.4k+ times), it joins the trend_continuation regime
    pool via R2, sorted second. Tested directly on `_build_regime_pool` so the
    shared minimal fixture (and its golden sampler-sequence tests) stays stable."""
    # D112: gamma_flip stays in the trend (single-name) pool even though it is
    # a dealer indicator — the exclusion targets universe templates only.
    pool = _build_regime_pool(
        {"adx", "hurst", "rv_rank", "gamma_flip_distance_pct"},
        dealer_ids=frozenset({"gamma_flip_distance_pct"}),
    )
    assert pool["trend_continuation"] == (
        "adx",
        "gamma_flip_distance_pct",
        "hurst",
        "rv_rank",
    )


def test_regime_pool_mean_reversion_is_iv_rank(space: SearchSpace) -> None:
    """R1: mean_reversion regime gate is iv_rank. (The minimal fixture omits
    gamma_flip_distance_pct; the D107 gamma-gate pool membership is covered in
    `test_regime_pool_mean_reversion_includes_gamma_flip`.)"""
    assert space.regime_indicators_by_hypothesis["mean_reversion"] == ("iv_rank",)


def test_regime_pool_mean_reversion_includes_gamma_flip() -> None:
    """D107 (v11 / H3, MR side): when the registry carries
    `gamma_flip_distance_pct`, it joins mean_reversion's R1 regime pool as an
    alternative to `iv_rank` (the long-gamma / ranging regime). Pool is sorted →
    gamma_flip first. Tested directly on `_build_regime_pool` so the shared
    minimal fixture (and its golden sampler-sequence tests) stays stable."""
    # D112: gamma_flip stays in the MR (single-name) pool even though it is a
    # dealer indicator — the exclusion targets universe templates only.
    pool = _build_regime_pool(
        {"iv_rank", "gamma_flip_distance_pct"},
        dealer_ids=frozenset({"gamma_flip_distance_pct"}),
    )
    assert pool["mean_reversion"] == ("gamma_flip_distance_pct", "iv_rank")


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
    assert pool == {ind.id for ind in registry.indicators} - dealer


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


def test_s5_required_volatility_event_has_both_iv_crush_and_event_passed(
    space: SearchSpace,
) -> None:
    required = space.s5_required_by_hypothesis["volatility_event"]
    assert "iv_crush_exit" in required
    assert "event_passed_exit" in required


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
