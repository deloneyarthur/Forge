"""Built-in predicate evaluators for the v1 grammar engine.

Each ``evaluate_*`` function is pure: ``(predicate, config, registry) ->
PredicateResult``. The top-level ``evaluate`` dispatches on the predicate's
concrete type via an internal registry — adding a new predicate variant
means adding one model class in ``models.py`` and one evaluator here, no
``isinstance`` chains in the rule engine.

The ``custom_python`` evaluator looks the function name up in
``forge.grammar.custom_predicates.REGISTRY``; unknown names raise
``GrammarLoadError`` at load time, so callers can assume the function exists
by the time evaluation runs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from forge.grammar.models import (
    CardinalityPredicate,
    Predicate,
    PredicateResult,
)
from forge.grammar.path_resolver import resolve

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------


def evaluate(
    predicate: Predicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Evaluate ``predicate`` against ``config`` using ``registry`` for any
    lookups the predicate needs. Returns a ``PredicateResult``."""
    impl = _IMPL.get(type(predicate))
    if impl is None:
        msg = (
            f"no evaluator registered for predicate type "
            f"{type(predicate).__name__}; phase 1 work in progress"
        )
        raise NotImplementedError(msg)
    return impl(predicate, config, registry)


# ---------------------------------------------------------------------------
# Cardinality
# ---------------------------------------------------------------------------


def evaluate_cardinality(
    predicate: CardinalityPredicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Count matches at ``predicate.field`` and assert it satisfies
    ``count`` or ``[min, max]`` (whichever is set; validated mutually
    exclusive at model load).
    """
    del registry  # unused; kept for uniform predicate-evaluator signature
    try:
        matches = resolve(config, predicate.field)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return PredicateResult(
            passed=False,
            detail=f"cardinality field {predicate.field!r} could not be resolved: {exc}",
        )

    count = len(matches)

    if predicate.count is not None:
        if count == predicate.count:
            return PredicateResult(passed=True)
        return PredicateResult(
            passed=False,
            detail=(
                f"cardinality {predicate.field!r}: expected count={predicate.count}, got {count}"
            ),
        )

    if predicate.min is not None and count < predicate.min:
        return PredicateResult(
            passed=False,
            detail=(f"cardinality {predicate.field!r}: count {count} below min {predicate.min}"),
        )
    if predicate.max is not None and count > predicate.max:
        return PredicateResult(
            passed=False,
            detail=(f"cardinality {predicate.field!r}: count {count} above max {predicate.max}"),
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# Dispatch registry
# ---------------------------------------------------------------------------


_PredicateImpl = Callable[[Any, "StrategyConfig", "RegistrySnapshot"], PredicateResult]


_IMPL: dict[type, _PredicateImpl] = {
    CardinalityPredicate: cast("_PredicateImpl", evaluate_cardinality),
}


__all__ = [
    "evaluate",
    "evaluate_cardinality",
]
