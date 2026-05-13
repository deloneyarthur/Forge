"""Grammar archive helpers — hash + version-bump enforcement.

Phase 1 deliverable item 6 + hard rule #10: any change to
``config/grammar.yaml`` must be accompanied by a ``grammar_version``
bump and an archive entry for the prior version under
``config/grammar_archive/v{N}.yaml``. The loader uses
``find_archived_grammar`` to detect silent edits at load time; the
pre-commit hook (module 9) uses ``archive_grammar`` to write the
prior-version copy when a bump is staged.

Archive filenames are ``{grammar_version}.yaml`` verbatim — no path
parsing, no version-string surgery. The ``grammar_version`` field in
``grammar.yaml`` *is* the filename root.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def compute_grammar_hash(grammar_path: Path) -> str:
    """SHA-256 hex digest of ``grammar_path``'s bytes. Used by the
    pre-commit hook to detect silent edits."""
    return hashlib.sha256(grammar_path.read_bytes()).hexdigest()


def find_archived_grammar(grammar_version: str, archive_dir: Path) -> Path | None:
    """Return the path of the archive entry for ``grammar_version`` if
    present, else ``None``. Lookup is by filename: a single archive file
    named ``{grammar_version}.yaml``.
    """
    candidate = archive_dir / f"{grammar_version}.yaml"
    if candidate.exists():
        return candidate
    return None


def archive_grammar(
    grammar_path: Path,
    archive_dir: Path,
    grammar_version: str,
) -> Path:
    """Copy ``grammar_path`` to ``archive_dir / {grammar_version}.yaml``.

    Idempotent on content but fails loud on version collision: if an
    archive entry for this version already exists with different content,
    ``FileExistsError`` is raised. Same-content overwrites are no-ops.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{grammar_version}.yaml"
    new_content = grammar_path.read_bytes()
    if target.exists():
        existing = target.read_bytes()
        if existing == new_content:
            return target
        msg = (
            f"archive entry {target} already exists with different "
            f"content; bump grammar_version instead of overwriting."
        )
        raise FileExistsError(msg)
    shutil.copyfile(grammar_path, target)
    return target


def list_archived_versions(archive_dir: Path) -> list[str]:
    """Return archived version strings in lexical-sorted order. Useful
    for the pre-commit hook to display history; not a load-time concern.
    """
    if not archive_dir.exists():
        return []
    return sorted(p.stem for p in archive_dir.glob("*.yaml"))


__all__ = [
    "archive_grammar",
    "compute_grammar_hash",
    "find_archived_grammar",
    "list_archived_versions",
]
