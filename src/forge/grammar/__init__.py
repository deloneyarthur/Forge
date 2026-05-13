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

from forge.grammar.archive import (
    archive_grammar,
    compute_grammar_hash,
    find_archived_grammar,
    list_archived_versions,
)
from forge.grammar.loader import load_grammar
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
from forge.grammar.validator import validate

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
    "archive_grammar",
    "compute_grammar_hash",
    "evaluate",
    "find_archived_grammar",
    "list_archived_versions",
    "load_grammar",
    "resolve",
    "validate",
]
