"""Tests for the ``requires`` and ``forbids`` predicates.

Per D015 these predicate types are not used by any v1 grammar rule
directly — S5 is encoded as a single ``custom_python`` to preserve the
21-rule count (D001). The §12 deliverable still requires both predicates
to be implemented and tested; these tests exercise them via synthetic
rule shapes drawn from §3.4's example forms.

Semantics:
  - ``requires``: if `if` matches → `then` MUST also match. If `if` does
    not match, the predicate vacuously passes.
  - ``forbids``: if `if` matches → `then` must NOT match. If `if` does
    not match, the predicate vacuously passes.

"Includes" matches both direct list membership and id-attribute matching
on Pydantic-model items (an `ExitSpec(id="time_stop")` is "included" by
the literal `"time_stop"`).
"""

from __future__ import annotations

from crucible_contracts import ExitSpec

from forge.grammar import evaluate
from forge.grammar.models import ForbidsPredicate, RequiresPredicate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)


def _registry() -> object:
    return minimal_registry_snapshot()


# ---------------------------------------------------------------------------
# requires
# ---------------------------------------------------------------------------


def test_requires_if_matches_and_then_holds() -> None:
    """mean_reversion → exits include time_stop. Fixture has time_stop
    when we attach it; baseline doesn't, so add it."""
    cfg = minimal_strategy_config(
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="time_stop"),
        ),
    )
    p = RequiresPredicate.model_validate(
        {
            "type": "requires",
            "if": {"field": "hypothesis", "value": "mean_reversion"},
            "then": {"field": "exits", "includes": "time_stop"},
        },
    )
    result = evaluate(p, cfg, _registry())
    assert result.passed


def test_requires_if_matches_but_then_missing_fails() -> None:
    """Default fixture is mean_reversion without time_stop — rule fails."""
    p = RequiresPredicate.model_validate(
        {
            "type": "requires",
            "if": {"field": "hypothesis", "value": "mean_reversion"},
            "then": {"field": "exits", "includes": "time_stop"},
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "time_stop" in result.detail


def test_requires_if_no_match_passes_vacuously() -> None:
    """trend_continuation → time_stop required; fixture is mean_reversion
    so the `if` clause doesn't fire, and the rule passes."""
    p = RequiresPredicate.model_validate(
        {
            "type": "requires",
            "if": {"field": "hypothesis", "value": "trend_continuation"},
            "then": {"field": "exits", "includes": "trailing_atr"},
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_requires_unknown_if_field_reported() -> None:
    p = RequiresPredicate.model_validate(
        {
            "type": "requires",
            "if": {"field": "nonexistent", "value": "x"},
            "then": {"field": "exits", "includes": "y"},
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "could not be resolved" in result.detail


def test_requires_includes_matches_plain_list_value() -> None:
    """`indicators` is a tuple of strings — direct membership works
    without id-attribute coercion."""
    p = RequiresPredicate.model_validate(
        {
            "type": "requires",
            "if": {"field": "hypothesis", "value": "mean_reversion"},
            "then": {"field": "signals.id", "includes": "sig_directional"},
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


# ---------------------------------------------------------------------------
# forbids
# ---------------------------------------------------------------------------


def test_forbids_if_matches_and_then_present_fails() -> None:
    """trend_continuation forbids hard_profit_target. Construct a
    trend_continuation config with hard_profit_target to fail the rule."""
    cfg = minimal_strategy_config(
        hypothesis="trend_continuation",
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
            ExitSpec(id="hard_profit_target"),
        ),
    )
    p = ForbidsPredicate.model_validate(
        {
            "type": "forbids",
            "if": {"field": "hypothesis", "value": "trend_continuation"},
            "then": {"field": "exits", "includes": "hard_profit_target"},
        },
    )
    result = evaluate(p, cfg, _registry())
    assert not result.passed
    assert "hard_profit_target" in result.detail


def test_forbids_if_matches_but_then_absent_passes() -> None:
    cfg = minimal_strategy_config(hypothesis="trend_continuation")
    p = ForbidsPredicate.model_validate(
        {
            "type": "forbids",
            "if": {"field": "hypothesis", "value": "trend_continuation"},
            "then": {"field": "exits", "includes": "hard_profit_target"},
        },
    )
    result = evaluate(p, cfg, _registry())
    assert result.passed


def test_forbids_if_no_match_passes_vacuously() -> None:
    """Fixture is mean_reversion; trend-specific forbids don't fire."""
    p = ForbidsPredicate.model_validate(
        {
            "type": "forbids",
            "if": {"field": "hypothesis", "value": "trend_continuation"},
            "then": {"field": "exits", "includes": "hard_profit_target"},
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_forbids_passing_detail_is_empty() -> None:
    p = ForbidsPredicate.model_validate(
        {
            "type": "forbids",
            "if": {"field": "hypothesis", "value": "trend_continuation"},
            "then": {"field": "exits", "includes": "hard_profit_target"},
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.detail == ""
