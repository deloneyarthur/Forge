"""Tests for ``forge.grammar.loader.load_grammar``.

Exercises: YAML parse failures, schema-level validation failures, unknown
``custom_python`` function names, archive-consistency check (matching
version with differing content → ``GrammarVersionError``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.grammar.loader import load_grammar
from forge.grammar.models import GrammarLoadError, GrammarVersionError


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _valid_grammar_yaml(grammar_version: str = "v1") -> str:
    return f"""\
grammar_version: {grammar_version}
rules:
  - id: S1
    category: structural
    version: 1
    active: true
    rationale_ref: GRAMMAR.md#S1
    predicate:
      type: cardinality
      field: hypothesis
      count: 1
    cost_estimate: low
    evidence_to_relax: []
  - id: S2
    category: structural
    version: 1
    active: true
    rationale_ref: GRAMMAR.md#S2
    predicate:
      type: cardinality
      field: signals.role.directional
      count: 1
    cost_estimate: low
    evidence_to_relax: []
"""


def test_load_valid_grammar(tmp_path: Path) -> None:
    path = _write(tmp_path / "grammar.yaml", _valid_grammar_yaml())
    grammar = load_grammar(path, check_archive=False)
    assert grammar.grammar_version == "v1"
    assert len(grammar.rules) == 2
    assert grammar.rules[0].id == "S1"


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(GrammarLoadError, match="not found"):
        load_grammar(tmp_path / "nope.yaml", check_archive=False)


def test_load_yaml_parse_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "grammar.yaml", "grammar_version: v1\nrules: [\n  - id: S1")
    with pytest.raises(GrammarLoadError, match="YAML parse error"):
        load_grammar(path, check_archive=False)


def test_load_non_mapping_root(tmp_path: Path) -> None:
    path = _write(tmp_path / "grammar.yaml", "- not a mapping\n")
    with pytest.raises(GrammarLoadError, match="must be a mapping"):
        load_grammar(path, check_archive=False)


def test_load_schema_failure_unknown_predicate_type(tmp_path: Path) -> None:
    body = """\
grammar_version: v1
rules:
  - id: S1
    category: structural
    version: 1
    active: true
    rationale_ref: GRAMMAR.md#S1
    predicate:
      type: not_a_real_type
      field: hypothesis
    cost_estimate: low
    evidence_to_relax: []
"""
    path = _write(tmp_path / "grammar.yaml", body)
    with pytest.raises(GrammarLoadError, match="schema validation failed"):
        load_grammar(path, check_archive=False)


def test_load_rejects_unknown_custom_python_name(tmp_path: Path) -> None:
    body = """\
grammar_version: v1
rules:
  - id: S5
    category: structural
    version: 1
    active: true
    rationale_ref: GRAMMAR.md#S5
    predicate:
      type: custom_python
      function: not_yet_implemented
    cost_estimate: medium
    evidence_to_relax: []
"""
    path = _write(tmp_path / "grammar.yaml", body)
    with pytest.raises(GrammarLoadError, match="unregistered custom_python"):
        load_grammar(path, check_archive=False)


def test_load_accepts_registered_custom_python_name(tmp_path: Path) -> None:
    body = """\
grammar_version: v1
rules:
  - id: STUB
    category: structural
    version: 1
    active: true
    rationale_ref: GRAMMAR.md#STUB
    predicate:
      type: custom_python
      function: always_pass
    cost_estimate: low
    evidence_to_relax: []
"""
    path = _write(tmp_path / "grammar.yaml", body)
    grammar = load_grammar(path, check_archive=False)
    assert grammar.rules[0].predicate.function == "always_pass"  # type: ignore[union-attr]


def test_load_no_archive_dir_passes(tmp_path: Path) -> None:
    """First-commit case: no archive directory yet. Loader must not error."""
    path = _write(tmp_path / "grammar.yaml", _valid_grammar_yaml())
    archive = tmp_path / "grammar_archive"  # does not exist
    grammar = load_grammar(path, archive_dir=archive)
    assert grammar.grammar_version == "v1"


def test_load_archive_consistent_version_passes(tmp_path: Path) -> None:
    """Archive contains v1.yaml matching the on-disk file → no error."""
    archive = tmp_path / "grammar_archive"
    archive.mkdir()
    body = _valid_grammar_yaml("v1")
    path = _write(tmp_path / "grammar.yaml", body)
    _write(archive / "v1.yaml", body)
    grammar = load_grammar(path, archive_dir=archive)
    assert grammar.grammar_version == "v1"


def test_load_archive_silent_drift_rejected(tmp_path: Path) -> None:
    """grammar.yaml content has changed but the version didn't bump and
    the archive entry for that version still has the OLD content. The
    operator violated the version-bump rule."""
    archive = tmp_path / "grammar_archive"
    archive.mkdir()
    # archive entry locked at the old content
    _write(archive / "v1.yaml", _valid_grammar_yaml("v1"))
    # current grammar.yaml claims v1 but its rules differ
    drifted = _valid_grammar_yaml("v1").replace("count: 1", "count: 2")
    path = _write(tmp_path / "grammar.yaml", drifted)
    with pytest.raises(GrammarVersionError, match="differs from archived"):
        load_grammar(path, archive_dir=archive)


def test_load_archive_new_version_no_match_passes(tmp_path: Path) -> None:
    """grammar.yaml bumped to v2; v1 is archived; v2 isn't yet (will be
    after the pre-commit hook runs). Loader must accept this."""
    archive = tmp_path / "grammar_archive"
    archive.mkdir()
    _write(archive / "v1.yaml", _valid_grammar_yaml("v1"))
    path = _write(tmp_path / "grammar.yaml", _valid_grammar_yaml("v2"))
    grammar = load_grammar(path, archive_dir=archive)
    assert grammar.grammar_version == "v2"
