"""Tests for ``forge.grammar.validator.validate``.

Covers: empty grammar, single-rule pass, multi-rule with failures,
inactive-rule skipping, error-message format (rule-id prefix +
predicate detail), error ordering matches rule-declaration order, the
GrammarLoadError propagation path.
"""

from __future__ import annotations

import pytest

from forge.grammar.models import (
    CardinalityPredicate,
    CustomPythonPredicate,
    Grammar,
    GrammarLoadError,
    NumericalRangePredicate,
    Rule,
)
from forge.grammar.validator import validate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)


def _rule(
    rule_id: str,
    predicate: object,
    *,
    active: bool = True,
    category: str = "structural",
) -> Rule:
    return Rule.model_validate(
        {
            "id": rule_id,
            "category": category,
            "version": 1,
            "active": active,
            "rationale_ref": f"GRAMMAR.md#{rule_id}",
            "predicate": predicate,
            "cost_estimate": "low",
        },
    )


def test_validate_empty_grammar_is_valid() -> None:
    grammar = Grammar(grammar_version="v1", rules=())
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert result.valid
    assert result.errors == ()


def test_validate_all_rules_pass() -> None:
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "S1",
                CardinalityPredicate(type="cardinality", field="hypothesis", count=1),
            ),
            _rule(
                "S2",
                CardinalityPredicate(
                    type="cardinality",
                    field="signals.role.directional",
                    count=1,
                ),
            ),
            _rule(
                "S3",
                CardinalityPredicate(
                    type="cardinality",
                    field="signals.role.regime_filter",
                    min=1,
                ),
            ),
        ),
    )
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert result.valid
    assert result.errors == ()


def test_validate_failures_are_named_and_ordered() -> None:
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "S1",
                CardinalityPredicate(type="cardinality", field="hypothesis", count=1),
            ),
            _rule(
                "FAIL_A",
                CardinalityPredicate(
                    type="cardinality",
                    field="signals.role.directional",
                    count=99,
                ),
            ),
            _rule(
                "FAIL_B",
                NumericalRangePredicate(
                    type="numerical_range",
                    field="sizer.per_trade_risk_pct",
                    min=0.99,
                    max=1.00,
                ),
            ),
        ),
    )
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert not result.valid
    assert len(result.errors) == 2
    assert result.errors[0].startswith("FAIL_A:")
    assert result.errors[1].startswith("FAIL_B:")
    assert "expected count=99" in result.errors[0]
    assert "below min 0.99" in result.errors[1]


def test_validate_skips_inactive_rules() -> None:
    """An inactive rule must NOT contribute to errors even if it would
    fail. This is how the operator suspends a rule mid-investigation."""
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "WOULD_FAIL",
                CardinalityPredicate(type="cardinality", field="hypothesis", count=99),
                active=False,
            ),
        ),
    )
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert result.valid
    assert result.errors == ()


def test_validate_full_error_list_no_short_circuit() -> None:
    """Property tests rely on the validator reporting every failing
    rule, not bailing on the first one."""
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "F1",
                CardinalityPredicate(type="cardinality", field="hypothesis", count=99),
            ),
            _rule(
                "F2",
                CardinalityPredicate(type="cardinality", field="signals", count=99),
            ),
            _rule(
                "F3",
                CardinalityPredicate(type="cardinality", field="exits", count=99),
            ),
        ),
    )
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert not result.valid
    assert len(result.errors) == 3
    assert {e.split(":", 1)[0] for e in result.errors} == {"F1", "F2", "F3"}


def test_validate_unknown_custom_python_function_propagates() -> None:
    """A custom_python predicate naming an unregistered function is a
    grammar-load bug; the validator surfaces it rather than reporting a
    misleading rule failure."""
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "BAD",
                CustomPythonPredicate(type="custom_python", function="not_registered"),
            ),
        ),
    )
    with pytest.raises(GrammarLoadError):
        validate(
            minimal_strategy_config(),
            grammar,
            minimal_registry_snapshot(),
        )


def test_validate_passing_custom_python_dispatches() -> None:
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "STUB",
                CustomPythonPredicate(type="custom_python", function="always_pass"),
            ),
        ),
    )
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert result.valid


def test_validate_failing_custom_python_appears_in_errors() -> None:
    grammar = Grammar(
        grammar_version="v1",
        rules=(
            _rule(
                "STUB_FAIL",
                CustomPythonPredicate(type="custom_python", function="always_fail"),
            ),
        ),
    )
    result = validate(
        minimal_strategy_config(),
        grammar,
        minimal_registry_snapshot(),
    )
    assert not result.valid
    assert len(result.errors) == 1
    assert result.errors[0].startswith("STUB_FAIL:")
    assert "always_fail" in result.errors[0]
