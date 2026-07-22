"""H2 (v12 / D109) — event_momentum grammar wiring.

event_momentum is a directional post-earnings-drift (PEAD) hypothesis. It
enters AFTER the print to ride the drift (structurally orthogonal to
volatility_event, which rides the pre-print IV crush). Its grammar shape:

  - directional = ``sue`` (standardized unexpected earnings, family
    ``post_event_drift``) — the surprise drives the drift direction.
  - regime/timing gate = ``days_since_earnings`` (family ``calendar`` after
    Crucible's §2.1 reclassification) — "fire within N days after the print".
  - exits = drift-decay ``time_stop`` (required) + momentum trailing
    (optional); no ``hard_profit_target`` (convex payoff, like the winners).

These tests pin the §3.5 predicate behaviour (C1/C2/S5) and the per-hypothesis
pools for event_momentum. End-to-end sampling lives in
``tests/unit/test_enumeration/test_event_momentum.py``.
"""

from __future__ import annotations

from pathlib import Path

from crucible_contracts import ExitSpec, SignalSpec

from forge.enumeration.search_space import (
    NON_ENUMERABLE_HYPOTHESES,
    build_search_space,
)
from forge.grammar import evaluate, load_grammar
from forge.grammar.models import CustomPythonPredicate
from tests.fixtures.strategy_configs import (
    grammar_valid_baseline,
    minimal_registry_snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


def _grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


def _registry() -> object:
    return minimal_registry_snapshot()


def _predicate(name: str) -> CustomPythonPredicate:
    return CustomPythonPredicate(type="custom_python", function=name)


def _event_momentum_config(**overrides: object):
    """A grammar-valid event_momentum baseline: sue directional (post_event_drift,
    strong-surprise threshold) + days_since_earnings timing gate (calendar,
    post-event window) + a drift-decay time_stop. swing_short matches sue's
    medium-lookback horizon and the baseline selector's 14-21 DTE window."""
    base: dict[str, object] = {
        "hypothesis": "event_momentum",
        "dte_bucket": "swing_short",
        "signals": (
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("sue",),
                params={"threshold": 1.5, "op": ">"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("days_since_earnings",),
                params={"threshold": 5.0, "op": "<"},
            ),
        ),
        "exits": (
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
        ),
    }
    base.update(overrides)
    return grammar_valid_baseline(**base)


# ---------------------------------------------------------------------------
# C2 — directional family matches hypothesis
# ---------------------------------------------------------------------------


def test_c2_event_momentum_accepts_post_event_drift() -> None:
    """sue (post_event_drift) is event_momentum's only allowed directional family."""
    result = evaluate(
        _predicate("directional_family_matches_hypothesis"),
        _event_momentum_config(),
        _registry(),
    )
    assert result.passed


def test_c2_event_momentum_rejects_other_family() -> None:
    """A mean_reversion-family directional (rsi_2) is not post_event_drift → C2 fails."""
    cfg = _event_momentum_config(
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
                indicators=("days_since_earnings",),
                params={"threshold": 5.0, "op": "<"},
            ),
        ),
    )
    result = evaluate(_predicate("directional_family_matches_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "post_event_drift" in result.detail
    assert "mean_reversion" in result.detail


# ---------------------------------------------------------------------------
# C1 — the §2.1 resolution: sue + days_since_earnings are DIFFERENT families
# ---------------------------------------------------------------------------


def test_c1_sue_and_days_since_earnings_coexist() -> None:
    """The load-bearing §2.1 fact: sue=post_event_drift, days_since_earnings=calendar,
    so the PEAD structure (surprise directional + post-event timing gate) is
    C1-legal in one config. If Crucible had left days_since_earnings under
    post_event_drift this would fail."""
    result = evaluate(
        _predicate("no_duplicate_indicator_families"),
        _event_momentum_config(),
        _registry(),
    )
    assert result.passed


# ---------------------------------------------------------------------------
# S5 — exit framework consistent with the drift thesis
# ---------------------------------------------------------------------------


def test_s5_event_momentum_baseline_passes() -> None:
    """time_stop from required_from_set + mandatory exits → S5 satisfied."""
    result = evaluate(
        _predicate("exits_match_hypothesis"),
        _event_momentum_config(),
        _registry(),
    )
    assert result.passed


def test_s5_event_momentum_requires_a_drift_decay_stop() -> None:
    """Drop the time_stop (the only required_from_set member) → S5 fails."""
    cfg = _event_momentum_config(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "required_from_set" in result.detail


def test_s5_event_momentum_allows_momentum_trailing() -> None:
    """trailing_atr is an optional momentum-trailing addition (E3 activation set)."""
    cfg = _event_momentum_config(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.35}),
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert result.passed


def test_s5_event_momentum_forbids_hard_profit_target() -> None:
    """Convex payoff (like the vol_event winners): no hard profit target."""
    cfg = _event_momentum_config(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
            ExitSpec(id="hard_profit_target", params={"target_pct": 0.5}),
        ),
    )
    result = evaluate(_predicate("exits_match_hypothesis"), cfg, _registry())
    assert not result.passed
    assert "forbidden" in result.detail


# ---------------------------------------------------------------------------
# Search-space pools — the post-event regime requirement is sampler-side
# policy (no new grammar.yaml rule), mirroring the R-rule regime pools.
# ---------------------------------------------------------------------------


def test_event_momentum_is_disabled() -> None:
    # D328 (v47): event_momentum retired into DISABLED_HYPOTHESES — single-name-
    # only (rank-excluded `sue`), dead (3 components, 0 conversion), its only book
    # use the D268 SOXL degenerate. It stays in space.hypotheses (grammar.yaml S1
    # lists it, hard rule #1) but is never enumerated, like regime_arbitrage.
    grammar = _grammar()
    space = build_search_space(grammar, minimal_registry_snapshot())
    assert "event_momentum" in space.hypotheses
    assert "event_momentum" in NON_ENUMERABLE_HYPOTHESES


def test_event_momentum_directional_pool_is_sue() -> None:
    grammar = _grammar()
    space = build_search_space(grammar, minimal_registry_snapshot())
    assert space.directional_indicators_by_hypothesis["event_momentum"] == ("sue",)


def test_event_momentum_regime_pool_is_days_since_earnings() -> None:
    """The post-event timing gate is constrained to days_since_earnings via the
    regime-pool builder (sampler-side policy, like R1/R2/R3's pools) — no 22nd
    grammar.yaml rule (hard rule #1)."""
    grammar = _grammar()
    space = build_search_space(grammar, minimal_registry_snapshot())
    assert space.regime_indicators_by_hypothesis["event_momentum"] == ("days_since_earnings",)
