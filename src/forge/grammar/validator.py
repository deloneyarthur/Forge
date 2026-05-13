"""Grammar validator: ``validate(config, grammar, registry)``.

Iterates the grammar's rules in declaration order, evaluates each
predicate against ``config`` + ``registry``, and accumulates error
strings for every rule that fails. Returns a
``crucible_contracts.ValidationResult`` — the same shape Crucible uses
on its side, so a contract-level callback can compare verdicts later.

Design:
  - **No short-circuit.** Phase 1's property tests need to know *which*
    rules a generated config violates; bailing on the first failure
    would hide overlapping violations.
  - **Inactive rules are skipped silently.** An ``active: false`` rule
    represents an operator's deliberate suspension; not a passing rule.
  - **GrammarLoadError propagates.** If a ``custom_python`` predicate
    references an unknown function at evaluation time (the loader
    *should* have caught it earlier), we re-raise rather than silently
    fail the config. The bug is in the grammar, not the config.

Architecture: D017.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crucible_contracts import ValidationResult

from forge.grammar.predicates import evaluate

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar.models import Grammar


def validate(
    config: StrategyConfig,
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> ValidationResult:
    """Check ``config`` against every active rule in ``grammar``.

    Returns ``ValidationResult(valid=True, errors=())`` when every active
    rule passes; otherwise ``valid=False`` and ``errors`` is a tuple of
    ``"rule_id: detail"`` strings in rule-declaration order.
    """
    errors: list[str] = []
    for rule in grammar.rules:
        if not rule.active:
            continue
        result = evaluate(rule.predicate, config, registry)
        if not result.passed:
            errors.append(f"{rule.id}: {result.detail}")
    return ValidationResult(valid=not errors, errors=tuple(errors))


__all__ = ["validate"]
