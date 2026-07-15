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
    CompatibilityPredicate,
    CustomPythonPredicate,
    ForbidsPredicate,
    GrammarLoadError,
    NumericalRangePredicate,
    Predicate,
    PredicateResult,
    RequiresPredicate,
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


def _resolve_field_or_empty(config: StrategyConfig, field: str) -> list[Any] | None:
    """Resolve `field` against `config`; return None on resolution failure
    so the predicate can report the underlying issue rather than swallow."""
    try:
        return resolve(config, field)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _value_in(items: list[Any], target: Any) -> bool:
    """Treat ``items`` as a collection; return True if ``target`` matches
    any element. A Pydantic-model element with an ``id`` attribute is
    matched by id equality — so ``ExitSpec(id="time_stop")`` is "included"
    by the literal ``"time_stop"`` (the §3.4 example reading)."""
    for item in items:
        if item == target:
            return True
        item_id = getattr(item, "id", None)
        if item_id is not None and item_id == target:
            return True
    return False


def _if_clause_matches(config: StrategyConfig, field: str, value: Any) -> bool | None:
    """Return True if `field` on `config` resolves to a value equal to
    `value`; False if it resolves but doesn't match; None if resolution
    failed (caller reports the error)."""
    resolved = _resolve_field_or_empty(config, field)
    if resolved is None:
        return None
    return any(item == value for item in resolved)


def evaluate_requires(
    predicate: RequiresPredicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """§3.4 ``requires``: if-clause match → then-clause must also match.

    Vacuously passes when the if-clause does not match — the rule's
    domain doesn't apply.
    """
    del registry

    if_match = _if_clause_matches(config, predicate.if_.field, predicate.if_.value)
    if if_match is None:
        return PredicateResult(
            passed=False,
            detail=(f"requires.if field {predicate.if_.field!r} could not be resolved"),
        )
    if not if_match:
        return PredicateResult(passed=True)

    then_items = _resolve_field_or_empty(config, predicate.then.field)
    if then_items is None:
        return PredicateResult(
            passed=False,
            detail=(f"requires.then field {predicate.then.field!r} could not be resolved"),
        )
    if _value_in(then_items, predicate.then.includes):
        return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"requires: when {predicate.if_.field}={predicate.if_.value!r}, "
            f"{predicate.then.field} must include {predicate.then.includes!r}"
        ),
    )


def evaluate_forbids(
    predicate: ForbidsPredicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """§3.4 ``forbids``: if-clause match → then-clause must NOT match.

    Vacuously passes when the if-clause does not match.
    """
    del registry

    if_match = _if_clause_matches(config, predicate.if_.field, predicate.if_.value)
    if if_match is None:
        return PredicateResult(
            passed=False,
            detail=(f"forbids.if field {predicate.if_.field!r} could not be resolved"),
        )
    if not if_match:
        return PredicateResult(passed=True)

    then_items = _resolve_field_or_empty(config, predicate.then.field)
    if then_items is None:
        return PredicateResult(
            passed=False,
            detail=(f"forbids.then field {predicate.then.field!r} could not be resolved"),
        )
    if not _value_in(then_items, predicate.then.includes):
        return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"forbids: when {predicate.if_.field}={predicate.if_.value!r}, "
            f"{predicate.then.field} must NOT include "
            f"{predicate.then.includes!r}"
        ),
    )


# ---------------------------------------------------------------------------
# Compatibility — generic key → target table lookup (D018)
# ---------------------------------------------------------------------------


def _resolve_single(
    config: StrategyConfig,
    field: str,
    predicate_name: str,
) -> tuple[Any, PredicateResult | None]:
    """Resolve `field` and assert exactly one match. Returns
    ``(value, None)`` on success, ``(None, error_result)`` on failure."""
    try:
        matches = resolve(config, field)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return None, PredicateResult(
            passed=False,
            detail=f"{predicate_name} field {field!r} could not be resolved: {exc}",
        )
    if len(matches) != 1:
        return None, PredicateResult(
            passed=False,
            detail=(f"{predicate_name} {field!r}: expected exactly 1 value, got {len(matches)}"),
        )
    return matches[0], None


def evaluate_compatibility(
    predicate: CompatibilityPredicate,
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """§3.4 ``compatibility``: ``field2``'s value must appear in
    ``table[field1's value]``. Pure table lookup; domain-aware
    transformations live in ``custom_python`` predicates per D018.
    """
    del registry

    key, err = _resolve_single(config, predicate.field1, "compatibility")
    if err is not None:
        return err
    target, err = _resolve_single(config, predicate.field2, "compatibility")
    if err is not None:
        return err

    key_str = str(key)
    if key_str not in predicate.table:
        return PredicateResult(
            passed=False,
            detail=(
                f"compatibility: {predicate.field1}={key_str!r} has no entry "
                f"in table (known keys: {sorted(predicate.table)})"
            ),
        )

    allowed = predicate.table[key_str]
    if target in allowed or str(target) in allowed:
        return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"compatibility: under {predicate.field1}={key_str!r}, "
            f"{predicate.field2}={target!r} is not in allowed set "
            f"{list(allowed)}"
        ),
    )


# ---------------------------------------------------------------------------
# Custom Python — escape hatch via function-name registry
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
    CompatibilityPredicate: cast("_PredicateImpl", evaluate_compatibility),
    CustomPythonPredicate: cast("_PredicateImpl", evaluate_custom_python),
    ForbidsPredicate: cast("_PredicateImpl", evaluate_forbids),
    NumericalRangePredicate: cast("_PredicateImpl", evaluate_numerical_range),
    RequiresPredicate: cast("_PredicateImpl", evaluate_requires),
}


__all__ = [
    "evaluate",
    "evaluate_cardinality",
    "evaluate_compatibility",
    "evaluate_custom_python",
    "evaluate_forbids",
    "evaluate_numerical_range",
    "evaluate_requires",
]
