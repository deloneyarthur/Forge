#!/usr/bin/env python3
"""Pre-commit hook: keep `config/grammar.yaml` and `docs/GRAMMAR.md` in sync.

If either file is staged, every rule id in `grammar.yaml` must have a
matching ``## {id}:`` or ``### {id}:`` heading in `GRAMMAR.md`, and vice
versa. Otherwise the rule and its narrative drift apart.

Stdlib-only — same dependency profile as `check_grammar_version_bump.py`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAMMAR_PATH = "config/grammar.yaml"
DOC_PATH = "docs/GRAMMAR.md"

_RULE_ID_RE = re.compile(r"^\s*-\s*id:\s*([A-Za-z][A-Za-z0-9_]*)\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{2,4}\s+([A-Za-z]\d+):\s", re.MULTILINE)


def _staged_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _staged_content(path: str) -> str | None:
    """Index content of `path` as text, or None if not tracked."""
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def _extract_grammar_rule_ids(content: str) -> set[str]:
    return set(_RULE_ID_RE.findall(content))


def _extract_doc_heading_ids(content: str) -> set[str]:
    return set(_HEADING_RE.findall(content))


def main() -> int:
    staged = _staged_files()
    if GRAMMAR_PATH not in staged and DOC_PATH not in staged:
        return 0

    grammar_text = _staged_content(GRAMMAR_PATH)
    doc_text = _staged_content(DOC_PATH)

    if grammar_text is None:
        print(
            f"pre-commit: {GRAMMAR_PATH} not tracked but the doc-sync hook "
            f"fired — investigate the staged files.",
            file=sys.stderr,
        )
        return 1
    if doc_text is None:
        print(f"pre-commit: {DOC_PATH} not tracked", file=sys.stderr)
        return 1

    rule_ids = _extract_grammar_rule_ids(grammar_text)
    heading_ids = _extract_doc_heading_ids(doc_text)

    missing_headings = sorted(rule_ids - heading_ids)
    orphan_headings = sorted(heading_ids - rule_ids)

    if missing_headings or orphan_headings:
        if missing_headings:
            print(
                f"pre-commit: {DOC_PATH} is missing sections for rule ids: "
                f"{missing_headings}. Add a '## {{id}}: …' or '### {{id}}: …' "
                f"heading for each.",
                file=sys.stderr,
            )
        if orphan_headings:
            print(
                f"pre-commit: {DOC_PATH} has sections for rule ids not present "
                f"in {GRAMMAR_PATH}: {orphan_headings}. Either remove the "
                f"section or add the rule.",
                file=sys.stderr,
            )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
