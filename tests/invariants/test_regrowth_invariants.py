"""Regrowth rules, checked instead of remembered (Batch 7 of the 2026-09 simplification, D428).

WHY: the repo had all the right conventions in August 2026 and still regrew — a 559 KB STATUS.md,
a 702 KB ledger, 21 relay files at the root, 38 days without a sweep (D371, D407). Every rule below
attaches to a moment where it is checked by the suite, so drift fails a commit rather than a memory.
The ceilings are deliberately loose (rotation happens at 400 KB; the test trips at 450) so that the
person doing the rotation is never racing the test.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

STATUS_MAX_BYTES = 150_000
STATUS_BLOCK_MAX_CHARS = 1_200
STATUS_BLOCKS_CHECKED = 5
LEDGER_MAX_BYTES = 450_000
# The one relay allowed at the root: the operator-parked Path-C dossier (D152; architecture.md
# root-file taxonomy). Every other relay lives in ~/proj/freeze/relays/ (D362).
ALLOWED_ROOT_RELAYS = frozenset({"PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md"})


def _status_blocks() -> list[str]:
    lines = (_ROOT / "STATUS.md").read_text(encoding="utf-8").split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    return ["\n".join(lines[a:b]) for a, b in zip(starts, [*starts[1:], len(lines)], strict=False)]


def test_status_stays_a_session_read_path_not_a_ledger() -> None:
    size = (_ROOT / "STATUS.md").stat().st_size
    assert size <= STATUS_MAX_BYTES, (
        f"STATUS.md is {size:,} bytes; rotate older blocks to _archive/STATUS_<era>.md (D242/D407)"
    )


def test_recent_status_blocks_are_short_and_cite_their_d_entry() -> None:
    """The narrative lives in the D-entry; a STATUS block is the what/why/state."""
    for block in _status_blocks()[:STATUS_BLOCKS_CHECKED]:
        heading = block.split("\n", 1)[0]
        assert len(block) <= STATUS_BLOCK_MAX_CHARS, (
            f"STATUS block {len(block)} chars > {STATUS_BLOCK_MAX_CHARS}: {heading[:80]}"
        )
        assert re.search(r"\(D\d{3}\)", block), f"STATUS block cites no D-entry: {heading[:80]}"


def test_ledger_rotates_before_it_becomes_unreadable() -> None:
    size = (_ROOT / "IMPLEMENTATION_DECISIONS.md").stat().st_size
    assert size <= LEDGER_MAX_BYTES, (
        f"IMPLEMENTATION_DECISIONS.md is {size:,} bytes; rotate a slice to "
        "_archive/IMPLEMENTATION_DECISIONS_D<a>-D<b>.md (rule: rotate at 400 KB)"
    )


def test_open_questions_holds_open_questions_only() -> None:
    """Sweep-on-land: a resolved Q moves to _archive/OPEN_QUESTIONS_RESOLVED.md in the
    resolving commit."""
    text = (_ROOT / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
    # "PARTIALLY RESOLVED" is a legitimately open, bannered question (e.g. Q29); a heading
    # that says RESOLVED outright belongs in the archive.
    resolved = [
        line
        for line in text.split("\n")
        if line.startswith("## ") and re.search(r"(?<!PARTIALLY )\bRESOLVED\b", line)
    ]
    assert not resolved, f"resolved entries still in OPEN_QUESTIONS.md: {resolved}"


def test_no_new_relay_files_at_the_repo_root() -> None:
    relays = {p.name for p in _ROOT.glob("PROMPT_*.md")}
    assert relays <= ALLOWED_ROOT_RELAYS, (
        f"relays at root {sorted(relays - ALLOWED_ROOT_RELAYS)}; "
        "the channel is ~/proj/freeze/relays/"
    )


def test_every_script_is_in_the_manpage_inventory() -> None:
    """A one-off script dies with its D-entry; whatever is left in scripts/ is documented."""
    manpage = (_ROOT / "docs" / "MANPAGE.md").read_text(encoding="utf-8")
    scripts = sorted(p.name for p in (_ROOT / "scripts").iterdir() if p.is_file())
    missing = [name for name in scripts if name not in manpage]
    assert not missing, f"scripts not in docs/MANPAGE.md SCRIPTS inventory: {missing}"
