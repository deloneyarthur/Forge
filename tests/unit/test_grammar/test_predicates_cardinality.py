"""Tests for the ``cardinality`` predicate (the S1/S2/S3/C3 workhorse).

A cardinality predicate counts matches at a path and asserts the count is
exactly ``count`` (or within ``[min, max]``). The path uses the resolver
covered in ``test_path_resolver.py``, so these tests focus on the count
arithmetic + error reporting.
"""

from __future__ import annotations

from forge.grammar import evaluate
from forge.grammar.models import CardinalityPredicate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)


def _registry() -> object:  # narrowing not needed in tests
    return minimal_registry_snapshot()


def test_s1_exactly_one_hypothesis() -> None:
    """S1 encoding: every config has exactly one hypothesis (Pydantic Literal
    enforces this at contracts level; grammar reports it as a passing rule)."""
    p = CardinalityPredicate(type="cardinality", field="hypothesis", count=1)
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_s2_exactly_one_directional_signal() -> None:
    p = CardinalityPredicate(
        type="cardinality",
        field="signals.role.directional",
        count=1,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_s3_at_least_one_regime_filter() -> None:
    p = CardinalityPredicate(
        type="cardinality",
        field="signals.role.regime_filter",
        min=1,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_c3_max_four_signals_under_limit() -> None:
    p = CardinalityPredicate(type="cardinality", field="signals", max=4)
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_cardinality_fails_when_count_mismatched() -> None:
    p = CardinalityPredicate(
        type="cardinality",
        field="signals.role.directional",
        count=2,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "expected count=2" in result.detail
    assert "got 1" in result.detail


def test_cardinality_fails_below_min() -> None:
    p = CardinalityPredicate(
        type="cardinality",
        field="signals.role.confluence",
        min=1,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "below min 1" in result.detail


def test_cardinality_fails_above_max() -> None:
    """Construct a config with 4 signals to overshoot a max=3 cap."""
    from crucible_contracts import SignalSpec

    extra_signals = (
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
            indicators=("iv_rank_30",),
        ),
        SignalSpec(
            id="sig_filter_a",
            type="threshold",
            role="filter",
            indicators=("rsi_2",),
        ),
        SignalSpec(
            id="sig_filter_b",
            type="threshold",
            role="confluence",
            indicators=("iv_rank_30",),
        ),
    )
    cfg = minimal_strategy_config(signals=extra_signals)
    p = CardinalityPredicate(type="cardinality", field="signals", max=3)
    result = evaluate(p, cfg, _registry())
    assert not result.passed
    assert "above max 3" in result.detail


def test_cardinality_invalid_field_reported() -> None:
    p = CardinalityPredicate(
        type="cardinality",
        field="not_a_real_field",
        count=1,
    )
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "could not be resolved" in result.detail
    assert "not_a_real_field" in result.detail


def test_cardinality_min_and_max_both_satisfied() -> None:
    p = CardinalityPredicate(type="cardinality", field="signals", min=1, max=4)
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed


def test_cardinality_passing_detail_is_empty() -> None:
    p = CardinalityPredicate(type="cardinality", field="hypothesis", count=1)
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.detail == ""
