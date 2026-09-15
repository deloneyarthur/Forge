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

from forge.grammar.custom_predicates import (
    _R1_GATE_EXEMPT_DIRECTIONALS,
)
from forge.grammar.custom_predicates import REGISTRY as _CUSTOM_REGISTRY
from forge.grammar.models import (
    CardinalityPredicate,
    CustomPythonPredicate,
    GrammarLoadError,
    NumericalRangePredicate,
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


def evaluate_cardinality(  # noqa: PLR0911 — one return per (count/min/max/exempt) branch; the D280 S3 carve-out is the seventh
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

    # D280 (v35): §3.5 S3's regime_filter min-1 shares the gate REQUIREMENT
    # with R1, so the operator-approved bare-drop carve-out (OPEN_PROPOSALS
    # `4d35a046`) exempts the capitulation directional from BOTH surfaces —
    # discovered at build time: the R1 predicate exemption alone left S3
    # rejecting every gate-less config. Scoped to exactly the S3 shape (this
    # field, a min bound, count 0) and the R1-exempt directional tuples; the
    # yaml rule text is untouched (the D270/D280 carve-out convention).
    if (
        predicate.field == "signals.role.regime_filter"
        and predicate.min is not None
        and count == 0
        and any(
            sig.role == "directional" and sig.indicators in _R1_GATE_EXEMPT_DIRECTIONALS
            for sig in config.signals
        )
    ):
        return PredicateResult(passed=True)

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
# Numerical range
# ---------------------------------------------------------------------------


def evaluate_numerical_range(
    predicate: NumericalRangePredicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Resolve ``predicate.field`` to a single numeric value and assert
    ``min ≤ value ≤ max`` (whichever bounds are set; model load guarantees
    at least one).

    Booleans are explicitly rejected even though ``isinstance(True, int)``
    is True — a typo'd boolean field would otherwise satisfy a `min: 0,
    max: 1` bound silently.
    """
    del registry
    try:
        matches = resolve(config, predicate.field)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return PredicateResult(
            passed=False,
            detail=(f"numerical_range field {predicate.field!r} could not be resolved: {exc}"),
        )

    if len(matches) != 1:
        return PredicateResult(
            passed=False,
            detail=(
                f"numerical_range {predicate.field!r}: expected exactly 1 value, got {len(matches)}"
            ),
        )

    value = matches[0]
    if isinstance(value, bool) or not isinstance(value, int | float):
        return PredicateResult(
            passed=False,
            detail=(f"numerical_range {predicate.field!r}: value {value!r} is not numeric"),
        )

    if predicate.min is not None and value < predicate.min:
        return PredicateResult(
            passed=False,
            detail=(
                f"numerical_range {predicate.field!r}: value {value} below min {predicate.min}"
            ),
        )
    if predicate.max is not None and value > predicate.max:
        return PredicateResult(
            passed=False,
            detail=(
                f"numerical_range {predicate.field!r}: value {value} above max {predicate.max}"
            ),
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# Requires / forbids — share if/then clause semantics
# ---------------------------------------------------------------------------


def evaluate_custom_python(
    predicate: CustomPythonPredicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Dispatch to the registered function named by ``predicate.function``.

    The loader is expected to have verified that the name exists in
    ``custom_predicates.REGISTRY`` at load time (raising
    ``GrammarLoadError`` on unknown names). If a name slips through and
    reaches evaluation, we raise ``GrammarLoadError`` here — preferable to
    silently failing the rule because the failure mode is a load-time bug,
    not a config issue.
    """
    fn = _CUSTOM_REGISTRY.get(predicate.function)
    if fn is None:
        msg = (
            f"custom_python predicate references unknown function "
            f"{predicate.function!r}; not in registry (known: "
            f"{sorted(_CUSTOM_REGISTRY)})"
        )
        raise GrammarLoadError(msg)
    return fn(config, registry)


# ---------------------------------------------------------------------------
# Dispatch registry
# ---------------------------------------------------------------------------


_PredicateImpl = Callable[[Any, "StrategyConfig", "RegistrySnapshot"], PredicateResult]


_IMPL: dict[type, _PredicateImpl] = {
    CardinalityPredicate: cast("_PredicateImpl", evaluate_cardinality),
    CustomPythonPredicate: cast("_PredicateImpl", evaluate_custom_python),
    NumericalRangePredicate: cast("_PredicateImpl", evaluate_numerical_range),
}


__all__ = [
    "evaluate",
    "evaluate_cardinality",
    "evaluate_custom_python",
    "evaluate_numerical_range",
]
