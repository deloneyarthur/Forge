"""Tests for the ``numerical_range`` predicate (the P4 workhorse).

`numerical_range` resolves a path to a single scalar, asserts it's numeric,
and checks ``min ≤ value ≤ max`` (whichever bounds are set). Used by P4
(`sizer.per_trade_risk_pct ∈ [0.005, 0.02]`) and by future v1.x rules.
"""

from __future__ import annotations

from forge.grammar import evaluate
from forge.grammar.models import NumericalRangePredicate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)


def _registry() -> object:
    return minimal_registry_snapshot()


def test_p4_per_trade_risk_pct_within_band() -> None:
    """P4 encoding: sizer.per_trade_risk_pct ∈ [0.005, 0.02]. Fixture's
    default of 0.02 sits at the upper edge — accepted."""
    p = NumericalRangePredicate(
        type="numerical_range",
        field="sizer.per_trade_risk_pct",
        min=0.005,
        max=0.02,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_numerical_range_min_only_pass() -> None:
    p = NumericalRangePredicate(
        type="numerical_range",
        field="sizer.per_trade_risk_pct",
        min=0.005,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_numerical_range_max_only_pass() -> None:
    p = NumericalRangePredicate(
        type="numerical_range",
        field="sizer.per_trade_risk_pct",
        max=0.02,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_numerical_range_below_min_fails() -> None:
    from crucible_contracts import SizerSpec

    cfg = minimal_strategy_config(
        sizer=SizerSpec(mode="fixed_risk_pct", per_trade_risk_pct=0.001),
    )
    p = NumericalRangePredicate(
        type="numerical_range",
        field="sizer.per_trade_risk_pct",
        min=0.005,
        max=0.02,
    )
    result = evaluate(p, cfg, _registry())
    assert not result.passed
    assert "below min 0.005" in result.detail


def test_numerical_range_above_max_fails() -> None:
    """SizerSpec already caps per_trade_risk_pct at 0.02 (contracts). Use
    `selector.delta_target` for an out-of-range fail without violating
    the contracts cap."""
    p = NumericalRangePredicate(
        type="numerical_range",
        field="selector.delta_target",
        min=0.0,
        max=0.30,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "above max 0.3" in result.detail


def test_numerical_range_integer_value_accepted() -> None:
    """`tier` is an int; numerical_range accepts int values, not just float."""
    p = NumericalRangePredicate(type="numerical_range", field="tier", min=1, max=3)
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_numerical_range_bool_rejected() -> None:
    """`bool` is a subclass of `int` in Python; the evaluator must reject
    it explicitly so a typo'd `active: true` path can't satisfy a numeric
    bound by accident."""
    from crucible_contracts import SelectorSpec

    cfg = minimal_strategy_config(
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
            prefer_monthly_expiry=True,
        ),
    )
    p = NumericalRangePredicate(
        type="numerical_range",
        field="selector.prefer_monthly_expiry",
        min=0,
        max=10,
    )
    result = evaluate(p, cfg, _registry())
    assert not result.passed
    assert "not numeric" in result.detail


def test_numerical_range_string_value_rejected() -> None:
    p = NumericalRangePredicate(
        type="numerical_range",
        field="hypothesis",
        min=0.0,
        max=1.0,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "not numeric" in result.detail


def test_numerical_range_unknown_field_reported() -> None:
    p = NumericalRangePredicate(
        type="numerical_range",
        field="not_a_real_field",
        min=0.0,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "could not be resolved" in result.detail


def test_numerical_range_multi_value_rejected() -> None:
    """A path that resolves to multiple values (e.g., `signals.id`) is a
    grammar-author error for `numerical_range`; the evaluator reports it."""
    p = NumericalRangePredicate(
        type="numerical_range",
        field="signals.id",
        min=0.0,
        max=1.0,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "expected exactly 1 value" in result.detail


def test_numerical_range_passing_detail_is_empty() -> None:
    p = NumericalRangePredicate(type="numerical_range", field="tier", min=1, max=3)
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.detail == ""
