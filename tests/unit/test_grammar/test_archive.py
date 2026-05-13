"""Tests for ``forge.grammar.archive`` — hash + version-bump enforcement.

Covers: hashing, archive lookup, archive write (including idempotency on
identical content), refusal to overwrite a version with new content, the
``list_archived_versions`` helper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.grammar.archive import (
    archive_grammar,
    compute_grammar_hash,
    find_archived_grammar,
    list_archived_versions,
)


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_compute_grammar_hash_stable(tmp_path: Path) -> None:
    body = "grammar_version: v1\nrules: []\n"
    a = _write(tmp_path / "a.yaml", body)
    b = _write(tmp_path / "b.yaml", body)
    assert compute_grammar_hash(a) == compute_grammar_hash(b)


def test_compute_grammar_hash_changes_with_content(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.yaml", "grammar_version: v1\n")
    b = _write(tmp_path / "b.yaml", "grammar_version: v2\n")
    assert compute_grammar_hash(a) != compute_grammar_hash(b)


def test_find_archived_grammar_present(tmp_path: Path) -> None:
    archive = tmp_path / "grammar_archive"
    archive.mkdir()
    _write(archive / "v3.yaml", "x")
    found = find_archived_grammar("v3", archive)
    assert found == archive / "v3.yaml"


def test_find_archived_grammar_missing(tmp_path: Path) -> None:
    archive = tmp_path / "grammar_archive"
    archive.mkdir()
    assert find_archived_grammar("v3", archive) is None


def test_find_archived_grammar_missing_archive_dir(tmp_path: Path) -> None:
    # archive_dir doesn't even exist
    nonexistent = tmp_path / "nope"
    assert find_archived_grammar("v3", nonexistent) is None


def test_archive_grammar_writes_new_entry(tmp_path: Path) -> None:
    grammar = _write(tmp_path / "grammar.yaml", "grammar_version: v1\n")
    archive = tmp_path / "grammar_archive"
    written = archive_grammar(grammar, archive, "v1")
    assert written == archive / "v1.yaml"
    assert written.read_text() == "grammar_version: v1\n"


def test_archive_grammar_creates_archive_dir(tmp_path: Path) -> None:
    """The archive helper creates the archive dir if it doesn't exist."""
    grammar = _write(tmp_path / "grammar.yaml", "x")
    archive = tmp_path / "deep" / "grammar_archive"
    assert not archive.exists()
    archive_grammar(grammar, archive, "v1")
    assert archive.exists()


def test_archive_grammar_idempotent_on_identical_content(tmp_path: Path) -> None:
    grammar = _write(tmp_path / "grammar.yaml", "grammar_version: v1\n")
    archive = tmp_path / "grammar_archive"
    archive_grammar(grammar, archive, "v1")
    # Second call with same content is a no-op
    archive_grammar(grammar, archive, "v1")


def test_archive_grammar_refuses_content_collision(tmp_path: Path) -> None:
    """Two different contents at the same version is the bug the
    archive prevents — the pre-commit hook should have bumped the
    version first."""
    grammar = _write(tmp_path / "grammar.yaml", "grammar_version: v1\nfoo: 1\n")
    archive = tmp_path / "grammar_archive"
    archive_grammar(grammar, archive, "v1")
    _write(tmp_path / "grammar.yaml", "grammar_version: v1\nfoo: 2\n")
    with pytest.raises(FileExistsError, match="already exists"):
        archive_grammar(tmp_path / "grammar.yaml", archive, "v1")


def test_list_archived_versions_empty_when_no_dir(tmp_path: Path) -> None:
    assert list_archived_versions(tmp_path / "nope") == []


def test_list_archived_versions_returns_sorted_stems(tmp_path: Path) -> None:
    archive = tmp_path / "grammar_archive"
    archive.mkdir()
    _write(archive / "v3.yaml", "x")
    _write(archive / "v1.yaml", "x")
    _write(archive / "v2.yaml", "x")
    assert list_archived_versions(archive) == ["v1", "v2", "v3"]
