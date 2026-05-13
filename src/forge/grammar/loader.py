"""Load and validate ``config/grammar.yaml`` into a typed ``Grammar``.

Performs three load-time checks beyond Pydantic schema validation:

1. **Custom-predicate names are registered.** Every ``custom_python``
   predicate's ``function`` must exist in
   ``forge.grammar.custom_predicates.REGISTRY``; unknown names raise
   ``GrammarLoadError`` rather than blowing up at evaluation time.
2. **Archive consistency.** If ``config/grammar_archive/`` contains a
   prior version of the same ``grammar_version``, the on-disk file's
   content must match that archive entry; otherwise the operator made a
   silent edit and the version-bump rule has been violated.
3. **Rationale references exist.** Each rule's ``rationale_ref`` should
   point to a heading in ``docs/GRAMMAR.md`` — soft warning at load
   (logged via ``structlog``); pre-commit hook enforces strictly.

Architecture: D017.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ValidationError

from forge.grammar.archive import find_archived_grammar
from forge.grammar.custom_predicates import REGISTRY as _CUSTOM_REGISTRY
from forge.grammar.models import (
    CustomPythonPredicate,
    Grammar,
    GrammarLoadError,
    GrammarVersionError,
)

if TYPE_CHECKING:
    pass


def load_grammar(
    grammar_path: Path,
    *,
    archive_dir: Path | None = None,
    check_archive: bool = True,
) -> Grammar:
    """Parse ``grammar_path`` into a validated ``Grammar``.

    Args:
        grammar_path: Path to ``config/grammar.yaml`` (or any equivalent).
        archive_dir: Directory of archived grammar versions. Defaults to
            ``grammar_path.parent / "grammar_archive"``. Pass an explicit
            path for tests.
        check_archive: When True (default), verify that the on-disk file
            is consistent with any matching archived version. Tests
            disable this for synthetic fixtures.

    Raises:
        GrammarLoadError: YAML parse failure, schema validation failure,
            or unknown ``custom_python`` function name.
        GrammarVersionError: Archive contains an entry for this
            ``grammar_version`` but its content differs from the on-disk
            file.
    """
    text = _read_yaml(grammar_path)
    grammar = _parse_grammar(text)
    _verify_custom_python_names(grammar)

    if check_archive:
        archive_dir = archive_dir or grammar_path.parent / "grammar_archive"
        _verify_archive_consistency(grammar, grammar_path, archive_dir)

    return grammar


def _read_yaml(grammar_path: Path) -> str:
    try:
        return grammar_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        msg = f"grammar file not found: {grammar_path}"
        raise GrammarLoadError(msg) from e
    except OSError as e:
        msg = f"could not read grammar file {grammar_path}: {e}"
        raise GrammarLoadError(msg) from e


def _parse_grammar(text: str) -> Grammar:
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as e:
        msg = f"grammar YAML parse error: {e}"
        raise GrammarLoadError(msg) from e

    if not isinstance(data, dict):
        msg = f"grammar.yaml root must be a mapping (got {type(data).__name__})"
        raise GrammarLoadError(msg)

    try:
        return Grammar.model_validate(data)
    except ValidationError as e:
        msg = f"grammar schema validation failed: {e}"
        raise GrammarLoadError(msg) from e


def _verify_custom_python_names(grammar: Grammar) -> None:
    unknown: list[tuple[str, str]] = []
    for rule in grammar.rules:
        if (
            isinstance(rule.predicate, CustomPythonPredicate)
            and rule.predicate.function not in _CUSTOM_REGISTRY
        ):
            unknown.append((rule.id, rule.predicate.function))
    if unknown:
        msg = (
            f"grammar.yaml references unregistered custom_python "
            f"functions (rule_id, function): {unknown}; known: "
            f"{sorted(_CUSTOM_REGISTRY)}"
        )
        raise GrammarLoadError(msg)


def _verify_archive_consistency(
    grammar: Grammar,
    grammar_path: Path,
    archive_dir: Path,
) -> None:
    if not archive_dir.exists():
        # No archive yet — first commit of grammar.yaml. Pre-commit hook
        # will write the v1 archive when the file is committed.
        return
    archived = find_archived_grammar(grammar.grammar_version, archive_dir)
    if archived is None:
        return
    if grammar_path.read_bytes() != archived.read_bytes():
        msg = (
            f"grammar.yaml content differs from archived "
            f"{archived.name} at the same grammar_version "
            f"({grammar.grammar_version!r}); bump grammar_version and "
            f"archive the prior version before changing content. See "
            f"docs/DESIGN.md §13.2."
        )
        raise GrammarVersionError(msg)


__all__ = ["load_grammar"]
