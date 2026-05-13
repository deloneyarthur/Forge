"""forge.grammar — hypothesis grammar parser, predicates, validator, archive (Phase 1).

Public surface:

- Pydantic schemas: ``Rule``, ``Grammar``, the six ``*Predicate`` variants,
  and the ``Predicate`` discriminated-union alias.
- Evaluation value type: ``PredicateResult``.
- Exceptions: ``GrammarError``, ``GrammarLoadError``, ``GrammarVersionError``.
- Path resolution: ``resolve(root, path)``.
- Predicate evaluation: ``evaluate(predicate, config, registry)``.

Architecture rationale: see ``IMPLEMENTATION_DECISIONS.md`` D017.
"""

from __future__ import annotations

from forge.grammar.models import (
    CardinalityPredicate,
    CompatibilityPredicate,
    CustomPythonPredicate,
    ForbidsPredicate,
    Grammar,
    GrammarError,
    GrammarLoadError,
    GrammarVersionError,
    NumericalRangePredicate,
    Predicate,
    PredicateResult,
    RequiresPredicate,
    Rule,
)
from forge.grammar.path_resolver import resolve
from forge.grammar.predicates import evaluate

__all__ = [
    "CardinalityPredicate",
    "CompatibilityPredicate",
    "CustomPythonPredicate",
    "ForbidsPredicate",
    "Grammar",
    "GrammarError",
    "GrammarLoadError",
    "GrammarVersionError",
    "NumericalRangePredicate",
    "Predicate",
    "PredicateResult",
    "RequiresPredicate",
    "Rule",
    "evaluate",
    "resolve",
]
