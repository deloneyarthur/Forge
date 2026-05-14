"""Tests for feedback.proposal_writer (Phase 5 module 6, D024/D5).

`append_proposal(proposal, *, open_proposals_path, db)` writes BOTH:
  - A markdown ---delimited block to `OPEN_PROPOSALS.md` (audit trail)
  - A row to `grammar_proposals` table with status='pending'

Structurally, this module exposes NO `apply_loosening` function — hard
rule #4 analogue. Tightening application happens in dedicated paths
(auto_tune.py for calibration; cli/grammar.py for grammar.yaml).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from pathlib import Path

from forge.feedback import proposal_writer
from forge.feedback.proposal_writer import append_proposal
from forge.feedback.types import GrammarProposal
from forge.persistence.db import db_connection


def _proposal(
    *,
    proposal_type: str = "loosen",
    target: str = "prefilter_calibration",
    rationale: str = "test rationale",
) -> GrammarProposal:
    return GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=datetime(2026, 5, 13, 12, tzinfo=UTC),
        proposal_type=proposal_type,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        proposal_yaml="# yaml snippet\nkey: value\n",
        rationale=rationale,
        evidence_json={"trigger": "test"},
    )


# ---------------------------------------------------------------------------
# Markdown audit
# ---------------------------------------------------------------------------


def test_append_creates_open_proposals_md_when_missing(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    assert open_proposals.exists()
    content = open_proposals.read_text(encoding="utf-8")
    assert "---" in content
    assert str(p.proposal_id) in content


def test_append_uses_dash_delimited_block_format(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal(proposal_type="loosen", rationale="loosen me")
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    assert "proposal_id:" in content
    assert "proposal_type: loosen" in content
    assert "target: prefilter_calibration" in content
    assert "loosen me" in content


def test_append_includes_evidence_json(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    assert "trigger" in content


def test_append_two_proposals_separates_with_delimiters(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p1 = _proposal(rationale="first")
    p2 = _proposal(rationale="second")
    with db_connection(forge_db) as conn:
        append_proposal(p1, open_proposals_path=open_proposals, db=conn)
        append_proposal(p2, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    assert content.count("---") >= 2
    assert "first" in content
    assert "second" in content


# ---------------------------------------------------------------------------
# DB row insertion
# ---------------------------------------------------------------------------


def test_append_inserts_grammar_proposals_row(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
        row = conn.execute(
            """
            SELECT proposal_type, status, rationale
            FROM grammar_proposals
            WHERE proposal_id = ?
            """,
            [str(p.proposal_id)],
        ).fetchone()
    assert row is not None
    assert row[0] == "loosen"
    assert row[1] == "pending"
    assert row[2] == "test rationale"


def test_append_evidence_json_roundtrips(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
        row = conn.execute(
            "SELECT evidence_json FROM grammar_proposals WHERE proposal_id = ?",
            [str(p.proposal_id)],
        ).fetchone()
    import json

    assert row is not None
    parsed = json.loads(row[0])
    assert parsed["trigger"] == "test"


def test_append_tighten_also_writes_to_md(tmp_path: Path) -> None:
    """Both tighten and loosen go through the audit path. Difference is
    in downstream application (tighten can auto-apply via dedicated paths;
    loosen cannot)."""
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal(proposal_type="tighten")
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    assert open_proposals.exists()


# ---------------------------------------------------------------------------
# Structural hard-rule-#4 analogue: no apply_loosening function exists
# ---------------------------------------------------------------------------


def test_no_apply_loosening_function_in_module() -> None:
    """proposal_writer must NOT expose any apply_loosening / apply_loosen
    function. Loosenings flow only through OPEN_PROPOSALS.md."""
    members = inspect.getmembers(proposal_writer, inspect.isfunction)
    names = {n for n, _ in members}
    assert "apply_loosening" not in names
    assert "apply_loosen" not in names
