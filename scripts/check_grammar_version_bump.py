#!/usr/bin/env python3
"""Pre-commit hook: enforce CLAUDE.md hard rule #10.

If ``config/grammar.yaml`` is staged AND its content differs from the
last committed version, then either:

  (a) the file is byte-identical to its HEAD revision (no change — exit 0), OR
  (b) ``grammar_version`` has been bumped AND the prior version is staged
      under ``config/grammar_archive/{prior_version}.yaml``.

Otherwise refuse the commit with a non-zero exit code and a clear
message explaining what to do.

This script is intentionally dependency-free (stdlib only). Pre-commit
runs it as a `local` hook; staged file contents come from the git index.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAMMAR_PATH = Path("config/grammar.yaml")
ARCHIVE_DIR = Path("config/grammar_archive")

_VERSION_RE = re.compile(r"^grammar_version:\s*(\S+)\s*$", re.MULTILINE)


def _staged_changes() -> set[str]:
    """Paths with changes staged for the upcoming commit (vs HEAD)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _head_content(path: Path | str) -> bytes | None:
    """Content of `path` at HEAD; None if not tracked."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _index_content(path: Path | str) -> bytes | None:
    """Post-commit content of `path` — the index version (whether or not
    it differs from HEAD). None if the file isn't in the index."""
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _extract_grammar_version(content: bytes) -> str | None:
    """Pull the ``grammar_version`` field from YAML text without importing
    pyyaml (keeps the hook stdlib-only)."""
    text = content.decode("utf-8", errors="replace")
    match = _VERSION_RE.search(text)
    if match is None:
        return None
    return match.group(1).strip("\"'")


def main() -> int:
    staged = _staged_changes()
    grammar_str = str(GRAMMAR_PATH)
    if grammar_str not in staged:
        return 0

    new_content = _index_content(GRAMMAR_PATH)
    old_content = _head_content(GRAMMAR_PATH)

    if new_content is None:
        # Staged but no index content — likely a deletion. We don't
        # police grammar.yaml deletion at the hook level.
        return 0

    if old_content is None:
        # First-commit case: grammar.yaml didn't exist at HEAD. Require
        # that the archive entry for the new version is also in the index
        # (this triggers the staged-change set since it's a brand-new file).
        new_version = _extract_grammar_version(new_content)
        if new_version is None:
            print(
                "pre-commit: grammar.yaml is missing or has unparseable `grammar_version:` field",
                file=sys.stderr,
            )
            return 1
        archive_path = str(ARCHIVE_DIR / f"{new_version}.yaml")
        if _index_content(archive_path) is None:
            print(
                f"pre-commit: grammar.yaml v{new_version} is being introduced "
                f"but its archive entry {archive_path} is not staged. "
                f"Stage both files together.",
                file=sys.stderr,
            )
            return 1
        return 0

    if new_content == old_content:
        # Staged for some reason but byte-identical to HEAD — no enforcement.
        return 0

    new_version = _extract_grammar_version(new_content)
    old_version = _extract_grammar_version(old_content)
    if new_version is None:
        print(
            "pre-commit: staged grammar.yaml has unparseable `grammar_version:` field",
            file=sys.stderr,
        )
        return 1
    if old_version is None:
        # Should not happen for an established file, but treat conservatively.
        print(
            "pre-commit: HEAD grammar.yaml has unparseable `grammar_version:`; "
            "manual review required before changes can land.",
            file=sys.stderr,
        )
        return 1

    if new_version == old_version:
        print(
            f"pre-commit: config/grammar.yaml content changed but "
            f"`grammar_version` is still {old_version!r}. Bump the version "
            f"and stage the prior content into "
            f"config/grammar_archive/{old_version}.yaml. "
            f"See CLAUDE.md hard rule #10.",
            file=sys.stderr,
        )
        return 1

    prior_archive_path = str(ARCHIVE_DIR / f"{old_version}.yaml")
    archive_content = _index_content(prior_archive_path)
    if archive_content is None:
        print(
            f"pre-commit: grammar_version bumped {old_version!r} → "
            f"{new_version!r}, but {prior_archive_path} is not in the index. "
            f"Run: cp <prior grammar.yaml> {prior_archive_path}; git add "
            f"{prior_archive_path}.",
            file=sys.stderr,
        )
        return 1

    # The archive's post-commit content must match HEAD's prior grammar.yaml.
    if archive_content != old_content:
        print(
            f"pre-commit: archive {prior_archive_path} does NOT match "
            f"HEAD's grammar.yaml. The archive must be a byte-exact copy of "
            f"the prior version.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
