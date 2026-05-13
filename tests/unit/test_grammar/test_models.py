"""Pydantic schema tests for ``forge.grammar.models``.

Covers: each predicate variant's construction + frozenness + extra-forbid;
mutual-exclusion validators on cardinality and numerical_range; Rule shape;
Grammar id-uniqueness validator; discriminated-union parsing of `type` key.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from forge.grammar.models import (
    CardinalityPredicate,
    CompatibilityPredicate,
    CustomPythonPredicate,
    ForbidsPredicate,
    Grammar,
    NumericalRangePredicate,
    Predicate,
    PredicateResult,
    RequiresPredicate,
    Rule,
)

_PREDICATE_TA: TypeAdapter[Predicate] = TypeAdapter(Predicate)


# ---------------------------------------------------------------------------
# PredicateResult
# ---------------------------------------------------------------------------


def test_predicate_result_defaults_detail_empty() -> None:
    r = PredicateResult(passed=True)
    assert r.passed
    assert r.detail == ""


def test_predicate_result_is_frozen() -> None:
    r = PredicateResult(passed=False, detail="x")
    with pytest.raises(AttributeError):
        r.passed = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CardinalityPredicate
# ---------------------------------------------------------------------------


def test_cardinality_count_only() -> None:
    p = CardinalityPredicate(type="cardinality", field="hypothesis", count=1)
    assert p.count == 1
    assert p.min is None
    assert p.max is None


def test_cardinality_range_only() -> None:
    p = CardinalityPredicate(type="cardinality", field="signals", min=1, max=4)
    assert p.min == 1
    assert p.max == 4
    assert p.count is None


def test_cardinality_count_and_range_rejected() -> None:
    with pytest.raises(ValidationError):
        CardinalityPredicate(type="cardinality", field="signals", count=1, min=1)


def test_cardinality_neither_count_nor_range_rejected() -> None:
    with pytest.raises(ValidationError):
        CardinalityPredicate(type="cardinality", field="signals")


def test_cardinality_min_above_max_rejected() -> None:
    with pytest.raises(ValidationError):
        CardinalityPredicate(type="cardinality", field="signals", min=5, max=2)


def test_cardinality_empty_field_rejected() -> None:
    with pytest.raises(ValidationError):
        CardinalityPredicate(type="cardinality", field="", count=1)


def test_cardinality_frozen() -> None:
    p = CardinalityPredicate(type="cardinality", field="hypothesis", count=1)
    with pytest.raises(ValidationError):
        p.field = "other"  # type: ignore[misc]


def test_cardinality_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        CardinalityPredicate(
            type="cardinality",
            field="hypothesis",
            count=1,
            sneaky=True,  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Requires + Forbids
# ---------------------------------------------------------------------------


def test_requires_construction() -> None:
    p = RequiresPredicate.model_validate(
        {
            "type": "requires",
            "if": {"field": "hypothesis", "value": "mean_reversion"},
            "then": {"field": "exits", "includes": "time_stop"},
        },
    )
    assert p.if_.field == "hypothesis"
    assert p.if_.value == "mean_reversion"
    assert p.then.includes == "time_stop"


def test_forbids_construction() -> None:
    p = ForbidsPredicate.model_validate(
        {
            "type": "forbids",
            "if": {"field": "hypothesis", "value": "trend_continuation"},
            "then": {"field": "exits", "includes": "hard_profit_target"},
        },
    )
    assert p.if_.value == "trend_continuation"
    assert p.then.includes == "hard_profit_target"


def test_requires_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        RequiresPredicate.model_validate(
            {
                "type": "requires",
                "if": {"field": "hypothesis", "value": "x", "extra": 1},
                "then": {"field": "exits", "includes": "y"},
            },
        )


# ---------------------------------------------------------------------------
# CompatibilityPredicate
# ---------------------------------------------------------------------------


def test_compatibility_construction() -> None:
    p = CompatibilityPredicate(
        type="compatibility",
        field1="lookback_class",
        field2="dte_bucket",
        table={
            "short_lookback": ("swing_short",),
            "medium_lookback": ("swing_short", "swing_mid"),
            "long_lookback": ("swing_mid", "swing_long"),
        },
    )
    assert p.table["short_lookback"] == ("swing_short",)


# ---------------------------------------------------------------------------
# NumericalRangePredicate
# ---------------------------------------------------------------------------


def test_numerical_range_min_only() -> None:
    p = NumericalRangePredicate(type="numerical_range", field="sizer.x", min=0.005)
    assert p.min == 0.005
    assert p.max is None


def test_numerical_range_max_only() -> None:
    p = NumericalRangePredicate(type="numerical_range", field="sizer.x", max=0.02)
    assert p.max == 0.02
    assert p.min is None


def test_numerical_range_neither_bound_rejected() -> None:
    with pytest.raises(ValidationError):
        NumericalRangePredicate(type="numerical_range", field="sizer.x")


def test_numerical_range_min_above_max_rejected() -> None:
    with pytest.raises(ValidationError):
        NumericalRangePredicate(
            type="numerical_range",
            field="sizer.x",
            min=0.10,
            max=0.05,
        )


# ---------------------------------------------------------------------------
# CustomPythonPredicate
# ---------------------------------------------------------------------------


def test_custom_python_construction() -> None:
    p = CustomPythonPredicate(type="custom_python", function="exits_match_hypothesis")
    assert p.function == "exits_match_hypothesis"


def test_custom_python_empty_function_rejected() -> None:
    with pytest.raises(ValidationError):
        CustomPythonPredicate(type="custom_python", function="")


# ---------------------------------------------------------------------------
# Discriminated-union dispatch
# ---------------------------------------------------------------------------


def test_predicate_union_parses_cardinality() -> None:
    p = _PREDICATE_TA.validate_python(
        {"type": "cardinality", "field": "hypothesis", "count": 1},
    )
    assert isinstance(p, CardinalityPredicate)


def test_predicate_union_parses_requires() -> None:
    p = _PREDICATE_TA.validate_python(
        {
            "type": "requires",
            "if": {"field": "hypothesis", "value": "x"},
            "then": {"field": "exits", "includes": "y"},
        },
    )
    assert isinstance(p, RequiresPredicate)


def test_predicate_union_unknown_type_rejected() -> None:
    with pytest.raises(ValidationError):
        _PREDICATE_TA.validate_python({"type": "bogus", "field": "x"})


def test_predicate_union_missing_discriminator_rejected() -> None:
    with pytest.raises(ValidationError):
        _PREDICATE_TA.validate_python({"field": "x", "count": 1})


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


def _rule(
    rule_id: str = "S1",
    category: str = "structural",
) -> dict[str, object]:
    return {
        "id": rule_id,
        "category": category,
        "version": 1,
        "active": True,
        "rationale_ref": f"GRAMMAR.md#{rule_id}",
        "predicate": {"type": "cardinality", "field": "hypothesis", "count": 1},
        "cost_estimate": "low",
        "evidence_to_relax": (),
    }


def test_rule_construction() -> None:
    r = Rule.model_validate(_rule())
    assert r.id == "S1"
    assert r.category == "structural"
    assert isinstance(r.predicate, CardinalityPredicate)


def test_rule_invalid_category_rejected() -> None:
    with pytest.raises(ValidationError):
        Rule.model_validate(_rule(category="bogus"))


def test_rule_version_must_be_positive() -> None:
    bad = _rule()
    bad["version"] = 0
    with pytest.raises(ValidationError):
        Rule.model_validate(bad)


def test_rule_extra_field_rejected() -> None:
    bad = _rule()
    bad["sneaky_extra"] = "x"
    with pytest.raises(ValidationError):
        Rule.model_validate(bad)


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------


def test_grammar_construction() -> None:
    g = Grammar.model_validate(
        {
            "grammar_version": "v1",
            "rules": (_rule("S1"), _rule("S2")),
        },
    )
    assert g.grammar_version == "v1"
    assert len(g.rules) == 2


def test_grammar_duplicate_rule_ids_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Grammar.model_validate(
            {
                "grammar_version": "v1",
                "rules": (_rule("S1"), _rule("S1")),
            },
        )
    assert "duplicate rule ids" in str(exc.value)


def test_grammar_empty_rules_accepted() -> None:
    """An empty grammar is valid (Phase 1 boot path); Phase 1 deliverable
    fills it with 21 rules. Empty-load test guards the loader's smoke path."""
    g = Grammar.model_validate({"grammar_version": "v0", "rules": ()})
    assert len(g.rules) == 0
