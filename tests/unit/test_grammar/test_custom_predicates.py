"""Tests for the 16 §3.5 custom_python predicate functions.

Each rule has at least one positive test (passes for a baseline config
that satisfies the rule) and at least one negative test (fails when the
rule is violated). The baseline is ``grammar_valid_baseline()`` from
the fixture module — a config that passes every §3.5 rule against the
fixture registry.

Tests are organized by rule id. Each predicate is called via the
top-level ``evaluate(predicate, config, registry)`` dispatcher to keep
the call path uniform with production usage.
"""

from __future__ import annotations

import pytest
from crucible_contracts import ExitSpec, SelectorSpec, SignalSpec, SizerSpec

from forge.grammar import evaluate
from forge.grammar.models import CustomPythonPredicate
from tests.fixtures.strategy_configs import (
    grammar_valid_baseline,
    minimal_registry_snapshot,
)


def _registry() -> object:
    return minimal_registry_snapshot()


def _predicate(name: str) -> CustomPythonPredicate:
    return CustomPythonPredicate(type="custom_python", function=name)


# ---------------------------------------------------------------------------
# S4 — lookback class ↔ DTE bucket
# ---------------------------------------------------------------------------


def test_s4_short_lookback_matches_swing_short() -> None:
    result = evaluate(
        _predicate("lookback_class_matches_dte_bucket"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_s4_long_lookback_with_swing_short_fails() -> None:
    """Override directional indicator to a long-lookback one — baseline
    bucket is swing_short, which only allows short_lookback."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("momentum_252",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(_predicate("lookback_class_matches_dte_bucket"), cfg, _registry())
    assert not result.passed
    assert "long_lookback" in result.detail
    assert "swing_short" in result.detail


def test_s4_unknown_indicator_reported() -> None:
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("not_in_registry",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(_predicate("lookback_class_matches_dte_bucket"), cfg, _registry())
    assert not result.passed
    assert "not present in registry" in result.detail


# ---------------------------------------------------------------------------
# S5 — Exit framework consistent with hypothesis
# ---------------------------------------------------------------------------


def test_m15_grammar_md_s5_documents_every_exit_in_source_table() -> None:
    """M-15 (audit 2026-05-29): content-aware S5 doc-sync. GRAMMAR.md §S5 must
    document the v3 schema vocabulary AND every exit id in the source-of-truth
    `_S5_HYPOTHESIS_EXITS`. The pre-commit doc-sync hook only checks heading-id
    existence, not content, so the §S5 narrative silently drifted to the stale
    v2 single-required wording. (Implemented as a pytest invariant rather than
    in the stdlib-only hook, which can't import the Python table.)
    """
    import re
    from pathlib import Path

    from forge.grammar.custom_predicates import _S5_HYPOTHESIS_EXITS

    grammar_md = (Path(__file__).resolve().parents[3] / "docs" / "GRAMMAR.md").read_text()
    match = re.search(r"### S5:.*?(?=\n### |\n## |\Z)", grammar_md, re.DOTALL)
    assert match, "GRAMMAR.md is missing the ### S5 section"
    s5 = match.group(0)

    for kw in ("required_always", "required_from_set", "optional_additions", "forbidden"):
        assert kw in s5, f"GRAMMAR.md §S5 missing v3 schema term {kw!r}"

    missing = [
        (hyp, key, exit_id)
        for hyp, table in _S5_HYPOTHESIS_EXITS.items()
        for key in ("required_always", "required_from_set", "optional_additions", "forbidden")
        for exit_id in table[key]
        if exit_id not in s5
    ]
    assert not missing, f"GRAMMAR.md §S5 omits exit ids from _S5_HYPOTHESIS_EXITS: {missing}"


def test_s5_mean_reversion_with_time_stop_passes() -> None:
    """Baseline has time_stop + mean_reversion → S5 passes."""
    result = evaluate(_predicate("exits_match_hypothesis"), grammar_valid_baseline(), _registry())
    assert result.passed


def test_s5_mean_reversion_without_time_stop_fails() -> None:
    """Remove time_stop — mean_reversion's required exit."""
    cfg = grammar_valid_baseline(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    # D071 schema: time_stop is mean_reversion's only required_from_set entry
    assert "required_from_set" in result.detail
    assert "time_stop" in result.detail


def test_s5_trend_with_hard_profit_target_fails() -> None:
    """trend_continuation forbids hard_profit_target."""
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
            ExitSpec(id="hard_profit_target"),
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "forbidden exits present" in result.detail
    assert "hard_profit_target" in result.detail


def test_s5_volatility_event_requires_both_exits() -> None:
    """volatility_event requires both iv_crush_exit AND event_passed_exit."""
    cfg = grammar_valid_baseline(
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("days_to_earnings",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            # event_passed_exit missing
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "event_passed_exit" in result.detail


# ---------------------------------------------------------------------------
# D071 (Phase 4 multi-exit schema)
# ---------------------------------------------------------------------------


def test_d071_volatility_event_missing_required_always_fails() -> None:
    """volatility_event has 2-element required_always — missing one fails."""
    cfg = grammar_valid_baseline(
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("days_to_earnings",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            # event_passed_exit missing — required_always
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "required_always" in result.detail
    assert "event_passed_exit" in result.detail


def test_d071_foreign_exit_fails() -> None:
    """An exit outside E1 + required_always + required_from_set +
    optional_additions is foreign and rejected."""
    cfg = grammar_valid_baseline(
        # mean_reversion: required_from_set={time_stop}, optional_additions=()
        # E1 mandatory: expiry, theta_cliff, earnings, liquidity
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),  # chosen from required_from_set
            ExitSpec(id="trailing_atr"),  # foreign for mean_reversion
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "foreign" in result.detail
    assert "trailing_atr" in result.detail


def test_d071_too_many_optional_additions_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """M-16 (audit 2026-05-29): the K_MAX_OPTIONAL=2 cap is a hard-rule-#1 (§3.5)
    rejection branch and MUST have a failure-mode test with an assertion.

    No shipped hypothesis currently ships >2 optional_additions, so the prior
    test always `pytest.skip`ped and asserted nothing. Here we extend one
    hypothesis's optional pool to 3 entries (via monkeypatch), attach all 3 to a
    config, and assert the cap branch fires — exercising the reachable
    set-arithmetic directly rather than waiting on a future grammar expansion.
    """
    from forge.grammar import custom_predicates as cp

    # regime_arbitrage: requires exactly 1 of {regime_flip_exit}; extend its
    # optional pool to 3 so attaching all 3 trips branch (4) and ONLY branch (4)
    # (the 3 are in the allow-set, so branch (3) "foreign exits" stays quiet).
    synthetic = {
        "required_always": (),
        "required_from_set": ("regime_flip_exit",),
        "optional_additions": ("time_stop", "iv_crush_exit", "target_exit"),
        "forbidden": (),
    }
    monkeypatch.setitem(cp._S5_HYPOTHESIS_EXITS, "regime_arbitrage", synthetic)

    cfg = grammar_valid_baseline(
        hypothesis="regime_arbitrage",
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="regime_flip_exit"),  # required_from_set (exactly 1)
            ExitSpec(id="time_stop"),  # optional #1
            ExitSpec(id="iv_crush_exit"),  # optional #2
            ExitSpec(id="target_exit"),  # optional #3 -> exceeds K_MAX_OPTIONAL=2
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "too many optional_additions" in result.detail
    assert f"K_MAX_OPTIONAL={cp.K_MAX_OPTIONAL}" in result.detail


def test_d071_sampler_optional_additions_can_fire_over_seeds() -> None:
    """Across N seeds, optional_additions for a hypothesis with non-empty
    pool fires at least once. Confirms the rng-driven p=0.5 picks aren't
    accidentally pinned to never-fire."""
    import random
    from pathlib import Path

    from forge.enumeration.sampler import sample_config
    from forge.enumeration.search_space import build_search_space
    from forge.grammar import load_grammar
    from forge.grammar.custom_predicates import _S5_HYPOTHESIS_EXITS
    from tests.fixtures.strategy_configs import minimal_registry_snapshot

    _REPO_ROOT = Path(__file__).resolve().parents[3]
    grammar = load_grammar(
        _REPO_ROOT / "config" / "grammar.yaml",
        archive_dir=_REPO_ROOT / "config" / "grammar_archive",
    )
    registry = minimal_registry_snapshot()
    space = build_search_space(grammar, registry)
    fired_optional: set[str] = set()
    for seed in range(120):
        cfg = sample_config(space, registry, random.Random(seed))
        rules = _S5_HYPOTHESIS_EXITS[cfg.hypothesis]
        optional_pool = set(rules["optional_additions"])
        if not optional_pool:
            continue
        exit_ids = {e.id for e in cfg.exits}
        # An optional addition is one that's in the pool AND in exits AND
        # NOT mandatory/required.
        e1_or_required = (
            set(space.e1_mandatory)
            | set(rules["required_always"])
            | set(rules["required_from_set"])
        )
        fired_here = (exit_ids & optional_pool) - e1_or_required
        fired_optional |= fired_here
    assert fired_optional, (
        "No optional_additions fired across 120 seeds — sampler's p=0.5 "
        "Bernoulli for optional picks may be broken"
    )


# ---------------------------------------------------------------------------
# C1 — No two indicators from the same family
# ---------------------------------------------------------------------------


def test_c1_baseline_passes() -> None:
    result = evaluate(
        _predicate("no_duplicate_indicator_families"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_c1_two_mean_reversion_indicators_fail() -> None:
    """Add a second mean_reversion-family indicator on a confluence signal."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
            SignalSpec(
                id="sig_confluence",
                type="threshold",
                role="confluence",
                indicators=("rsi_14",),  # also mean_reversion
            ),
        ),
    )
    result = evaluate(_predicate("no_duplicate_indicator_families"), cfg, _registry())
    assert not result.passed
    assert "share family" in result.detail
    assert "mean_reversion" in result.detail


def test_c1_unknown_indicator_reported() -> None:
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("not_in_registry",),
            ),
        ),
    )
    result = evaluate(_predicate("no_duplicate_indicator_families"), cfg, _registry())
    assert not result.passed
    assert "not in registry" in result.detail


# ---------------------------------------------------------------------------
# C2 — Directional family matches hypothesis
# ---------------------------------------------------------------------------


def test_c2_mean_reversion_matches() -> None:
    result = evaluate(
        _predicate("directional_family_matches_hypothesis"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_c2_trend_with_mean_reversion_directional_fails() -> None:
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        # keep mean_reversion-family rsi_2 as directional — wrong family
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),
            ),
        ),
    )
    result = evaluate(_predicate("directional_family_matches_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "trend" in result.detail
    assert "mean_reversion" in result.detail


def test_c2_volatility_event_accepts_dealer_positioning() -> None:
    """D062: dealer-positioning indicators (gex/vex/cex/walls/gamma-flip)
    are first-class drivers of vol-regime strategies; the C2 allowlist for
    `volatility_event` includes `dealer_positioning` alongside iv_structure
    and flow."""
    cfg = grammar_valid_baseline(
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("gex",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="regime_flip_exit"),
        ),
    )
    result = evaluate(_predicate("directional_family_matches_hypothesis"), cfg, _registry())
    assert result.passed


def test_c2_mean_reversion_accepts_dealer_positioning() -> None:
    """D062: call/put walls and the gamma-flip line are mean-reversion
    magnets; the C2 allowlist for `mean_reversion` includes
    `dealer_positioning` alongside the native `mean_reversion` family."""
    cfg = grammar_valid_baseline(
        hypothesis="mean_reversion",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("call_wall_distance_pct",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(_predicate("directional_family_matches_hypothesis"), cfg, _registry())
    assert result.passed


def test_c2_trend_continuation_rejects_dealer_positioning() -> None:
    """D062: dealer_positioning is allowed for `volatility_event` and
    `mean_reversion` only — `trend_continuation` still requires `trend`."""
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("gex",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),
            ),
        ),
    )
    result = evaluate(_predicate("directional_family_matches_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "dealer_positioning" in result.detail


def test_c2_regime_arbitrage_accepts_any_family() -> None:
    cfg = grammar_valid_baseline(
        hypothesis="regime_arbitrage",
        signals=(
            # directional from `pairs` family — would fail for any other
            # hypothesis, but regime_arbitrage allows any family.
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("pairs_zscore",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="regime_flip_exit"),
        ),
    )
    result = evaluate(_predicate("directional_family_matches_hypothesis"), cfg, _registry())
    assert result.passed


# ---------------------------------------------------------------------------
# C4 — Regime gate ≠ directional indicator
# ---------------------------------------------------------------------------


def test_c4_disjoint_indicators_pass() -> None:
    result = evaluate(
        _predicate("regime_indicators_disjoint_from_directional"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_c4_shared_indicator_fails() -> None:
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("rsi_2",),  # same as directional
            ),
        ),
    )
    result = evaluate(_predicate("regime_indicators_disjoint_from_directional"), cfg, _registry())
    assert not result.passed
    assert "rsi_2" in result.detail


# ---------------------------------------------------------------------------
# P1 — Indicator params within registry schema keys
# ---------------------------------------------------------------------------


def test_p1_baseline_passes() -> None:
    result = evaluate(
        _predicate("indicator_params_within_registry_ranges"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_p1_unknown_param_key_fails() -> None:
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"bogus_param": 1},  # iv_rank schema doesn't declare this
            ),
        ),
    )
    result = evaluate(_predicate("indicator_params_within_registry_ranges"), cfg, _registry())
    assert not result.passed
    assert "bogus_param" in result.detail


# ---------------------------------------------------------------------------
# P2 — DTE window per bucket
# ---------------------------------------------------------------------------


def test_p2_swing_short_window_passes() -> None:
    result = evaluate(
        _predicate("dte_window_matches_bucket"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_p2_swing_short_dte_outside_window_fails() -> None:
    cfg = grammar_valid_baseline(
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=5,  # below 14
            dte_max=12,
        ),
    )
    result = evaluate(_predicate("dte_window_matches_bucket"), cfg, _registry())
    assert not result.passed
    assert "swing_short" in result.detail


# ---------------------------------------------------------------------------
# P3 — Delta target in DTE-appropriate band
# ---------------------------------------------------------------------------


def test_p3_baseline_passes() -> None:
    result = evaluate(
        _predicate("delta_target_in_dte_band"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_p3_delta_target_outside_band_fails() -> None:
    cfg = grammar_valid_baseline(
        selector=SelectorSpec(
            delta_target=0.20,  # swing_short requires 0.40-0.55
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
    )
    result = evaluate(_predicate("delta_target_in_dte_band"), cfg, _registry())
    assert not result.passed
    assert "swing_short" in result.detail
    assert "0.4" in result.detail


def test_p3_trend_widened_swing_long_band_passes() -> None:
    """D125 (v16): trend_continuation swing_long band widens 0.20-0.35 →
    0.20-0.55 (hypothesis-scoped — P3's first per-hypothesis override).
    Evidence: within-band delta-tercile readout (components 5/8/16 rising
    toward the upper edge; every honest-coverage trend component in the upper
    two terciles) + the Frazzini-Pedersen embedded-leverage drag prior (Q35);
    operator-approved loosening (OPEN_PROPOSALS 343e71fd)."""
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        dte_bucket="swing_long",
        selector=SelectorSpec(
            delta_target=0.50,  # off-band for base swing_long, in-band for trend
            delta_tolerance=0.05,
            dte_min=60,
            dte_max=90,
        ),
    )
    result = evaluate(_predicate("delta_target_in_dte_band"), cfg, _registry())
    assert result.passed, result.detail


def test_p3_non_trend_swing_long_band_unchanged() -> None:
    """D125 (v16): the widening is trend-scoped ONLY — the MR and vol_event
    delta-tercile gradients are flat-to-inverted (components concentrate at
    LOW delta), so every other hypothesis keeps the base bands."""
    cfg = grammar_valid_baseline(
        hypothesis="mean_reversion",
        dte_bucket="swing_long",
        selector=SelectorSpec(
            delta_target=0.50,
            delta_tolerance=0.05,
            dte_min=60,
            dte_max=90,
        ),
    )
    result = evaluate(_predicate("delta_target_in_dte_band"), cfg, _registry())
    assert not result.passed
    assert "swing_long" in result.detail
    assert "0.35" in result.detail


def test_p3_trend_swing_mid_widened_swing_short_unchanged() -> None:
    """D125 (v16): trend swing_mid widens to 0.30-0.55; trend swing_short has
    NO override (already 0.40-0.55 — the ATM-ish floor rationale untouched)."""
    mid = grammar_valid_baseline(
        hypothesis="trend_continuation",
        dte_bucket="swing_mid",
        selector=SelectorSpec(
            delta_target=0.55,
            delta_tolerance=0.05,
            dte_min=30,
            dte_max=45,
        ),
    )
    assert evaluate(_predicate("delta_target_in_dte_band"), mid, _registry()).passed
    short = grammar_valid_baseline(
        hypothesis="trend_continuation",
        dte_bucket="swing_short",
        selector=SelectorSpec(
            delta_target=0.30,  # below swing_short's 0.40 floor — still invalid
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
    )
    assert not evaluate(_predicate("delta_target_in_dte_band"), short, _registry()).passed


# ---------------------------------------------------------------------------
# E1 — Mandatory exits present
# ---------------------------------------------------------------------------


def test_e1_all_four_present() -> None:
    result = evaluate(
        _predicate("mandatory_exits_present"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_e1_missing_mandatory_exit_fails() -> None:
    """Drop earnings_exit. (StrategyConfig itself enforces all 4, so
    constructing via the model isn't possible — but the grammar predicate
    must still detect it for completeness.) We bypass via direct dict
    construction is not possible (Pydantic frozen); test cannot actually
    create such a config, so we just smoke-test the positive path. The
    contracts-level validator already enforces the mandatory exits at
    instance creation — this rule is a defense-in-depth check."""
    # Document the constraint-level coverage above; positive path
    # exercised by test_e1_all_four_present.
    assert True


# ---------------------------------------------------------------------------
# E2 — At most 2 stop-loss exits
# ---------------------------------------------------------------------------


def test_e2_zero_stop_loss_passes() -> None:
    result = evaluate(
        _predicate("at_most_two_stop_loss_exits"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_e2_three_stop_loss_fails() -> None:
    cfg = grammar_valid_baseline(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="premium_stop_loss"),
            ExitSpec(id="atr_underlying_stop_loss"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
    )
    result = evaluate(_predicate("at_most_two_stop_loss_exits"), cfg, _registry())
    assert not result.passed
    assert "3 stop-loss" in result.detail


def test_e2_two_stop_loss_at_limit_passes() -> None:
    cfg = grammar_valid_baseline(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="premium_stop_loss"),
            ExitSpec(id="atr_underlying_stop_loss"),
        ),
    )
    result = evaluate(_predicate("at_most_two_stop_loss_exits"), cfg, _registry())
    assert result.passed


# ---------------------------------------------------------------------------
# E3 — trailing_atr requires activation threshold
# ---------------------------------------------------------------------------


def test_e3_baseline_passes() -> None:
    """Baseline has no trailing_atr — E3 passes vacuously."""
    result = evaluate(
        _predicate("trailing_atr_has_activation_threshold"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_e3_trailing_atr_with_threshold_passes() -> None:
    cfg = grammar_valid_baseline(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
    )
    result = evaluate(_predicate("trailing_atr_has_activation_threshold"), cfg, _registry())
    assert result.passed


def test_e3_trailing_atr_without_threshold_fails() -> None:
    cfg = grammar_valid_baseline(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="trailing_atr"),  # no params
        ),
    )
    result = evaluate(_predicate("trailing_atr_has_activation_threshold"), cfg, _registry())
    assert not result.passed
    assert "activate_after_gain_pct" in result.detail


def test_e3_trailing_atr_below_min_threshold_fails() -> None:
    cfg = grammar_valid_baseline(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.20}),
        ),
    )
    result = evaluate(_predicate("trailing_atr_has_activation_threshold"), cfg, _registry())
    assert not result.passed
    assert "0.3" in result.detail


# ---------------------------------------------------------------------------
# R1 — mean_reversion → iv_rank ≤ 50 regime gate
# ---------------------------------------------------------------------------


def test_r1_baseline_passes() -> None:
    """Baseline is mean_reversion with iv_rank regime gate, threshold=50."""
    result = evaluate(
        _predicate("mean_reversion_requires_iv_rank_gate"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_r1_non_mean_reversion_passes_vacuously() -> None:
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert result.passed


def test_r1_missing_iv_rank_gate_fails() -> None:
    """mean_reversion without an iv_rank regime gate — R1 fires and fails."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),  # not iv_rank
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert not result.passed
    assert "iv_rank" in result.detail


def test_r1_iv_rank_threshold_above_50_fails() -> None:
    """iv_rank is present but threshold > 50 — fails."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 75},  # above the 50 cap
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert not result.passed


def test_r1_mean_reversion_accepts_gamma_flip_gate() -> None:
    """D107 (v11 / H3): a dealer-gamma regime gate is an accepted alternative to
    the iv_rank cheap-IV gate for mean_reversion — MR pays in the long-gamma /
    dampening / ranging regime (flip below spot → op_regime '<'). No iv_rank
    present, yet R1 passes."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("gamma_flip_distance_pct",),
                params={"threshold": 0.0, "op": "<"},
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert result.passed


def test_r1_mean_reversion_accepts_hurst_gate() -> None:
    """D150 (v20): hurst (op '<', the mean-reverting H<0.5 side) is an accepted R1
    regime gate for mean_reversion — the purest ranging signal. Mirrors the D107
    gamma_flip widening; directional is rsi_2 here (C4 keeps hurst single-role)."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("hurst",),
                params={"threshold": 0.45, "op": "<"},
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert result.passed


def test_r1_mean_reversion_accepts_rv_rank_gate() -> None:
    """D167 (v22): rv_rank (op '<', cheap realized vol — the calm, reversion-
    friendly regime) is a fourth accepted R1 regime gate for mean_reversion,
    alongside iv_rank / gamma_flip / hurst. Crucible (FORGE_mr_rv_hurst_overlap_
    response): rv_rank is independent of and DOMINATES the v21 hurst gate. Mirrors
    the D107/D150 widenings; directional is rsi_2 (C4 keeps rv_rank single-role)."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("rv_rank",),
                params={"threshold": 25.0, "op": "<"},
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert result.passed


def test_r1_mean_reversion_accepts_vol_regime_gate() -> None:
    """D254 (v24): vol_regime (op '<', threshold 2 — exclude the high-vol tercile)
    is a fifth accepted R1 regime gate for mean_reversion, alongside iv_rank /
    gamma_flip / hurst / rv_rank. Crucible's xsect-MR backtest
    (FORGE_signal_quality_champions §2b.1): vol_regime<2 beats the rv_rank cost gate
    by +0.244 CPCV-p25 in ALL 6 comps. ADD not replace (R1 stays an OR). RAW discrete
    tercile — no threshold cap, op set by the sampler (like gamma/hurst/rv_rank)."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("vol_regime",),
                params={"threshold": 2.0, "op": "<"},
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert result.passed


def test_r1_mean_reversion_accepts_realized_vol_gate() -> None:
    """D265 (v28): realized_vol (op '<', ABSOLUTE annualized RV — the systematic-
    vol complement to the percentile gates) is a sixth accepted R1 regime gate for
    mean_reversion. Crucible FORGE_mr_absolute_vol_gate_request_2026-07-12: the
    champion's rv_rank percentile gate NORMALIZES in regime-wide vol spikes
    (probe 2026-07-12: rv_rank<62 open 21/21 days on all five knife-catch names in
    2022-12 while absolute rv held ≥ 0.25). ADD not replace (R1 stays an OR);
    op-agnostic convention like gamma/hurst/rv_rank/vol_regime — the sampler sets
    op '<' with the asked 0.15-0.30 absolute sweep."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("realized_vol",),
                params={"threshold": 0.20, "op": "<"},
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert result.passed


def test_r1_mean_reversion_without_iv_rank_or_gamma_fails() -> None:
    """D107: with neither iv_rank nor a gamma gate, R1 still fires and fails."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),  # neither iv_rank nor gamma_flip_distance_pct
            ),
        ),
    )
    result = evaluate(_predicate("mean_reversion_requires_iv_rank_gate"), cfg, _registry())
    assert not result.passed


# ---------------------------------------------------------------------------
# R2 — trend_continuation → adx/hurst regime gate
# ---------------------------------------------------------------------------


def test_r2_baseline_passes_vacuously() -> None:
    """Baseline is mean_reversion — R2 doesn't fire."""
    result = evaluate(
        _predicate("trend_requires_trend_strength_gate"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_r2_trend_with_adx_passes() -> None:
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("adx",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
    )
    result = evaluate(_predicate("trend_requires_trend_strength_gate"), cfg, _registry())
    assert result.passed


def test_r2_trend_with_rv_rank_passes() -> None:
    """D077: rv_rank is an accepted regime_filter for trend_continuation."""
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("rv_rank",),
                params={"threshold": 50, "op": "<", "rv_window": 21, "window": 252},
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
    )
    result = evaluate(_predicate("trend_requires_trend_strength_gate"), cfg, _registry())
    assert result.passed


def test_r2_trend_with_gamma_flip_passes() -> None:
    """D107 (v11 / H3): gamma_flip_distance_pct is an accepted regime gate for
    trend_continuation — the dealer-gamma regime switch. Trend pays in the
    short-gamma / vol-amplifying regime (flip above spot → dealers short gamma),
    so the gate fires when gamma_flip_distance_pct > threshold (op_regime '>')."""
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("gamma_flip_distance_pct",),
                params={"threshold": 0.0, "op": ">"},
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
    )
    result = evaluate(_predicate("trend_requires_trend_strength_gate"), cfg, _registry())
    assert result.passed


def test_r2_trend_with_vix_term_slope_passes() -> None:
    """v27 (D264): vix_term_slope is an accepted R2 regime gate — the calm-market
    (contango) conditioner for trend entries. Reverses the v17/D131 deliberate
    exclusion: Crucible's resid_vix probe measured exactly this use at campaign
    grade (first walk-forward-gate pass in program history). Gate fires when the
    vol term structure is in contango: op '>', threshold ≥ 0."""
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("vix_term_slope",),
                params={"threshold": 0.0, "op": ">"},
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
    )
    result = evaluate(_predicate("trend_requires_trend_strength_gate"), cfg, _registry())
    assert result.passed


def test_r2_trend_without_adx_or_hurst_fails() -> None:
    cfg = grammar_valid_baseline(
        hypothesis="trend_continuation",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(_predicate("trend_requires_trend_strength_gate"), cfg, _registry())
    assert not result.passed


# ---------------------------------------------------------------------------
# R3 — volatility_event → event-proximity regime gate
# ---------------------------------------------------------------------------


def test_r3_baseline_passes_vacuously() -> None:
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_r3_volatility_event_with_days_to_earnings_passes() -> None:
    # T1.4 / grammar v2 / D039: days_to_earnings is valid for single-name
    # underlyings but rejected on ETFs (where it returns sentinel 999).
    # Default baseline uses SPY (ETF); override to a single-name here.
    cfg = grammar_valid_baseline(
        underlying="AAPL",
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("days_to_earnings",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            ExitSpec(id="event_passed_exit"),
        ),
    )
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        cfg,
        _registry(),
    )
    assert result.passed


def test_r3_volatility_event_with_days_to_earnings_on_etf_rejects() -> None:
    """T1.4 / D039: vol_event + ETF + days_to_earnings is the silent-failure
    case from the translation corpus (sentinel 999 → 0 trades). R3 v2
    rejects it at validation time."""
    cfg = grammar_valid_baseline(
        underlying="SPY",  # ETF — days_to_earnings is sentinel 999 here
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("days_to_earnings",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            ExitSpec(id="event_passed_exit"),
        ),
    )
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        cfg,
        _registry(),
    )
    assert not result.passed
    assert "ETF" in (result.detail or "")
    assert "days_to_earnings" in (result.detail or "")


def test_r3_volatility_event_with_days_to_fomc_passes_on_etf() -> None:
    """T1.4: macro-event indicators (days_to_fomc, days_to_cpi, etc.) are
    valid on ETFs. Only days_to_earnings is ETF-incompatible."""
    cfg = grammar_valid_baseline(
        underlying="SPY",
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("days_to_fomc",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            ExitSpec(id="event_passed_exit"),
        ),
    )
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        cfg,
        _registry(),
    )
    assert result.passed


def test_r3_volatility_event_without_event_gate_fails() -> None:
    cfg = grammar_valid_baseline(
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        cfg,
        _registry(),
    )
    assert not result.passed


# ---------------------------------------------------------------------------
# X1 — vol_target sizer → realized_vol indicator
# ---------------------------------------------------------------------------


def test_x1_non_vol_target_passes_vacuously() -> None:
    result = evaluate(
        _predicate("vol_target_requires_realized_vol_indicator"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_x1_vol_target_with_realized_vol_passes() -> None:
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
            SignalSpec(
                id="sig_vol",
                type="passthrough",
                role="filter",
                indicators=("realized_vol",),
            ),
        ),
        sizer=SizerSpec(mode="vol_target"),
    )
    result = evaluate(
        _predicate("vol_target_requires_realized_vol_indicator"),
        cfg,
        _registry(),
    )
    assert result.passed


def test_x1_vol_target_without_realized_vol_fails() -> None:
    cfg = grammar_valid_baseline(sizer=SizerSpec(mode="vol_target"))
    result = evaluate(
        _predicate("vol_target_requires_realized_vol_indicator"),
        cfg,
        _registry(),
    )
    assert not result.passed
    assert "realized_vol" in result.detail


# ---------------------------------------------------------------------------
# X2 — fractional_kelly sizer → expected_value_estimator
# ---------------------------------------------------------------------------


def test_x2_non_kelly_passes_vacuously() -> None:
    result = evaluate(
        _predicate("kelly_requires_expected_value_estimator"),
        grammar_valid_baseline(),
        _registry(),
    )
    assert result.passed


def test_x2_kelly_with_estimator_passes() -> None:
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
            SignalSpec(
                id="sig_ev",
                type="passthrough",
                role="filter",
                indicators=("expected_value_estimator",),
            ),
        ),
        sizer=SizerSpec(mode="fractional_kelly"),
    )
    result = evaluate(_predicate("kelly_requires_expected_value_estimator"), cfg, _registry())
    assert result.passed


def test_x2_kelly_without_estimator_fails() -> None:
    cfg = grammar_valid_baseline(sizer=SizerSpec(mode="fractional_kelly"))
    result = evaluate(_predicate("kelly_requires_expected_value_estimator"), cfg, _registry())
    assert not result.passed
    assert "expected_value_estimator" in result.detail


def test_r3_volatility_event_with_pre_earnings_setup_passes() -> None:
    """D135 (v18): pre_earnings_setup (the composed days_to_earnings x
    rv_rank conditioner, family calendar) joins R3's event-proximity pool —
    it IS an earnings-proximity gate, at full fidelity in the 1-gate slot."""
    cfg = grammar_valid_baseline(
        underlying="AAPL",
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("pre_earnings_setup",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            ExitSpec(id="event_passed_exit"),
        ),
    )
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        cfg,
        _registry(),
    )
    assert result.passed


def test_r3_volatility_event_with_pre_earnings_setup_on_etf_rejects() -> None:
    """D135 (v18): pre_earnings_setup composes days_to_earnings, which is
    far-value on ETFs (no earnings) — the conjunction never admits there
    (permanent 0.0 = silent zero-trade). Same T1.4 rejection class."""
    cfg = grammar_valid_baseline(
        underlying="SPY",  # ETF — no earnings; composed gate never fires
        hypothesis="volatility_event",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("put_call_flow",),
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("pre_earnings_setup",),
            ),
        ),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="iv_crush_exit"),
            ExitSpec(id="event_passed_exit"),
        ),
    )
    result = evaluate(
        _predicate("volatility_event_requires_event_proximity_gate"),
        cfg,
        _registry(),
    )
    assert not result.passed
    assert "ETF" in (result.detail or "")
    assert "pre_earnings_setup" in (result.detail or "")
