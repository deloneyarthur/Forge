"""Tests for the ``compatibility`` predicate.

Per D018 the predicate is a generic key→target table lookup; no v1 rule
uses it directly (S4 is encoded as ``custom_python``). These tests
exercise the table-lookup semantics via synthetic rule shapes.

Semantics:
  - resolve ``field1`` → expect a single value, treat as a key into ``table``.
  - resolve ``field2`` → expect a single value, treat as the target.
  - pass if ``field2_value in table[field1_value]``; fail otherwise.
"""

from __future__ import annotations

from forge.grammar import evaluate
from forge.grammar.models import CompatibilityPredicate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)


def _registry() -> object:
    return minimal_registry_snapshot()


def test_compatibility_key_target_in_table_passes() -> None:
    """hypothesis=mean_reversion, dte_bucket=swing_short; table allows
    swing_short under mean_reversion."""
    p = CompatibilityPredicate(
        type="compatibility",
        field1="hypothesis",
        field2="dte_bucket",
        table={
            "mean_reversion": ("swing_short", "swing_mid"),
            "trend_continuation": ("swing_short",),
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_compatibility_target_not_in_table_fails() -> None:
    """hypothesis=mean_reversion, dte_bucket=swing_short; restrict the
    table to swing_mid only — fixture's swing_short is rejected."""
    p = CompatibilityPredicate(
        type="compatibility",
        field1="hypothesis",
        field2="dte_bucket",
        table={
            "mean_reversion": ("swing_mid",),
            "trend_continuation": ("swing_short",),
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "swing_short" in result.detail
    assert "mean_reversion" in result.detail


def test_compatibility_key_missing_from_table_fails() -> None:
    p = CompatibilityPredicate(
        type="compatibility",
        field1="hypothesis",
        field2="dte_bucket",
        table={
            "trend_continuation": ("swing_short",),
        },
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "mean_reversion" in result.detail
    assert "not present" in result.detail or "no entry" in result.detail


def test_compatibility_field1_resolution_error_reported() -> None:
    p = CompatibilityPredicate(
        type="compatibility",
        field1="nonexistent",
        field2="dte_bucket",
        table={"x": ("y",)},
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "could not be resolved" in result.detail


def test_compatibility_field2_resolution_error_reported() -> None:
    p = CompatibilityPredicate(
        type="compatibility",
        field1="hypothesis",
        field2="nonexistent",
        table={"mean_reversion": ("swing_short",)},
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "could not be resolved" in result.detail


def test_compatibility_field1_multi_value_rejected() -> None:
    """field1 must resolve to a single value — `signals.id` resolves to
    multiple, so the predicate reports the structural error."""
    p = CompatibilityPredicate(
        type="compatibility",
        field1="signals.id",
        field2="dte_bucket",
        table={"sig_directional": ("swing_short",)},
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "expected exactly 1 value" in result.detail


def test_compatibility_passing_detail_is_empty() -> None:
    p = CompatibilityPredicate(
        type="compatibility",
        field1="hypothesis",
        field2="dte_bucket",
        table={"mean_reversion": ("swing_short",)},
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.detail == ""
