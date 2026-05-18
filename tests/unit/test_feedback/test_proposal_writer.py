"""Tests for feedback.proposal_writer (Phase 5 module 6, D024/D5).

``append_proposal(proposal, *, open_proposals_path, db)`` writes BOTH:

  - A v1 YAML mapping document to ``OPEN_PROPOSALS.md`` (audit trail)
  - A row to ``grammar_proposals`` table with status='pending'

OPEN_PROPOSALS.md follows the cross-repo ``forge-proposals/v1`` contract
(QuantIQ D297). The first append to a fresh file writes the contract
header; subsequent appends preserve it. Writes are atomic (tmp + rename).

Structurally, this module exposes NO ``apply_loosening`` function — hard
rule #4 analogue. Tightening application happens in dedicated paths
(auto_tune.py for calibration; cli/grammar.py for grammar.yaml).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from forge.feedback import proposal_writer
from forge.feedback.proposal_writer import CONTRACT_HEADER, append_proposal
from forge.feedback.types import GrammarProposal
from forge.persistence.db import db_connection


def _proposal(
    *,
    proposal_type: str = "loosen",
    target: str = "prefilter_calibration",
    rationale: str = "test rationale",
    evidence_json: dict[str, str] | None = None,
) -> GrammarProposal:
    return GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=datetime(2026, 5, 13, 12, tzinfo=UTC),
        proposal_type=proposal_type,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        proposal_yaml="# yaml snippet\nkey: value\n",
        rationale=rationale,
        evidence_json=evidence_json if evidence_json is not None else {"trigger": "test"},
    )


# ---------------------------------------------------------------------------
# v1 contract: file shape + header
# ---------------------------------------------------------------------------


def test_append_creates_file_with_contract_header_when_missing(
    tmp_path: Path,
) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    assert open_proposals.exists()
    content = open_proposals.read_text(encoding="utf-8")
    # First line MUST be the contract header per v1 spec.
    assert content.splitlines()[0] == CONTRACT_HEADER
    assert str(p.proposal_id) in content


def test_append_writes_v1_yaml_mapping_fields(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal(proposal_type="loosen", rationale="loosen me")
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    # v1 uses YAML mappings (no leading ``- ``) inside ``---`` blocks.
    assert "proposal_id: " in content
    assert "proposal_type: loosen" in content
    assert "target: prefilter_calibration" in content
    assert "rationale: loosen me" in content
    assert "status: PENDING" in content


def test_append_emits_evidence_as_native_mapping(tmp_path: Path) -> None:
    """v1 contract renames legacy ``evidence_json`` (stringified) →
    ``evidence`` (native YAML mapping)."""
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    # The trigger key surfaces; the value is *not* wrapped in quotes
    # as a stringified-JSON would be.
    assert "evidence:" in content
    assert "  trigger: test" in content
    # Legacy evidence_json field is gone.
    assert "evidence_json:" not in content


def test_append_two_proposals_creates_multi_doc_yaml(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    # D034: dedup is by structural intent (trigger + target/hypothesis/family),
    # not rationale string. Use distinct trigger values so both write.
    p1 = _proposal(rationale="first", evidence_json={"trigger": "alpha"})
    p2 = _proposal(rationale="second", evidence_json={"trigger": "beta"})
    with db_connection(forge_db) as conn:
        append_proposal(p1, open_proposals_path=open_proposals, db=conn)
        append_proposal(p2, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    # Parse with yaml.safe_load_all to confirm valid multi-doc YAML.
    docs = [d for d in yaml.safe_load_all(content) if d is not None]
    assert len(docs) == 2
    assert docs[0]["rationale"] == "first"
    assert docs[1]["rationale"] == "second"


def test_contract_header_written_only_once(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    with db_connection(forge_db) as conn:
        append_proposal(
            _proposal(rationale="first"),
            open_proposals_path=open_proposals,
            db=conn,
        )
        append_proposal(
            _proposal(rationale="second"),
            open_proposals_path=open_proposals,
            db=conn,
        )
        append_proposal(
            _proposal(rationale="third"),
            open_proposals_path=open_proposals,
            db=conn,
        )
    content = open_proposals.read_text(encoding="utf-8")
    # The contract header line appears exactly once (at line 1).
    assert content.splitlines()[0] == CONTRACT_HEADER
    assert content.count(CONTRACT_HEADER) == 1


def test_append_refuses_to_write_to_non_v1_file(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    # Simulate a pre-migration legacy file.
    open_proposals.write_text(
        "\n---\n- proposal_id: legacy\n- STATUS: PENDING\n",
        encoding="utf-8",
    )
    p = _proposal()
    with db_connection(forge_db) as conn, pytest.raises(RuntimeError, match="forge-proposals/v1"):
        append_proposal(p, open_proposals_path=open_proposals, db=conn)


def test_append_overwrites_empty_legacy_file(tmp_path: Path) -> None:
    """An empty pre-existing file (size 0) is treated as 'fresh' —
    we write the header rather than refusing."""
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    open_proposals.write_text("", encoding="utf-8")
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    content = open_proposals.read_text(encoding="utf-8")
    assert content.splitlines()[0] == CONTRACT_HEADER


def test_atomic_write_leaves_no_tmp_file(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p = _proposal()
    with db_connection(forge_db) as conn:
        append_proposal(p, open_proposals_path=open_proposals, db=conn)
    tmp = open_proposals.with_suffix(open_proposals.suffix + ".tmp")
    assert not tmp.exists()


# ---------------------------------------------------------------------------
# DB row insertion (unchanged from legacy — DB schema is per-row, not file)
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


def test_append_evidence_json_roundtrips_in_db(tmp_path: Path) -> None:
    """The DB column is still named ``evidence_json`` and stores
    stringified JSON — the v1 rename applies to the file shape only."""
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


# ---------------------------------------------------------------------------
# Dedup of identical pending proposals (§8.4 trigger fires every batch)
# ---------------------------------------------------------------------------


def test_append_skips_identical_pending_proposal(tmp_path: Path) -> None:
    """Two proposals with same (type, rationale) collapse to one pending row.

    Auto-tune fires on every batch where the trigger condition holds.
    Without dedup, OPEN_PROPOSALS.md floods with thousands of identical
    entries. Dedup matches by (proposal_type, rationale, status='pending'):
    the *intent* of a pending proposal is captured by those fields.
    """
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p1 = _proposal(rationale="rolling promotion rate below threshold")
    p2 = _proposal(rationale="rolling promotion rate below threshold")
    with db_connection(forge_db) as conn:
        wrote_p1 = append_proposal(p1, open_proposals_path=open_proposals, db=conn)
        wrote_p2 = append_proposal(p2, open_proposals_path=open_proposals, db=conn)
    assert wrote_p1 is True
    assert wrote_p2 is False
    # DB has exactly one pending row.
    with db_connection(forge_db) as conn:
        count_row = conn.execute(
            "SELECT COUNT(*) FROM grammar_proposals WHERE status = 'pending'",
        ).fetchone()
    assert count_row is not None
    assert count_row[0] == 1


def test_append_writes_again_after_pending_resolves(tmp_path: Path) -> None:
    """After the operator decides a pending proposal (approve/reject), a
    fresh proposal with the same intent is allowed to be written.

    The dedup match is `status='pending'` only; resolved proposals don't
    block future writes — the auto-tune condition may legitimately fire
    again after a calibration cycle.
    """
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p1 = _proposal(rationale="recurring trigger")
    p2 = _proposal(rationale="recurring trigger")
    with db_connection(forge_db) as conn:
        append_proposal(p1, open_proposals_path=open_proposals, db=conn)
        # Operator decides p1.
        conn.execute(
            "UPDATE grammar_proposals SET status = 'rejected' WHERE proposal_id = ?",
            [str(p1.proposal_id)],
        )
        # New proposal should now write.
        wrote_p2 = append_proposal(p2, open_proposals_path=open_proposals, db=conn)
    assert wrote_p2 is True


def test_append_different_intents_both_written(tmp_path: Path) -> None:
    """Distinct intents aren't deduped — they convey different operator
    decisions even if rationales coincidentally look similar.

    D034: intent = (proposal_type, evidence.trigger, evidence.target /
    hypothesis / family). Two proposals with the same trigger but
    different per-trigger detail keys are independent.
    """
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p1 = _proposal(
        rationale="rationale A",
        evidence_json={"trigger": "gate_failure_concentration", "target": "sharpe_gate"},
    )
    p2 = _proposal(
        rationale="rationale B",
        evidence_json={"trigger": "gate_failure_concentration", "target": "profit_factor"},
    )
    with db_connection(forge_db) as conn:
        a = append_proposal(p1, open_proposals_path=open_proposals, db=conn)
        b = append_proposal(p2, open_proposals_path=open_proposals, db=conn)
    assert a is True
    assert b is True


def test_append_same_intent_different_count_fields_deduped(tmp_path: Path) -> None:
    """D034 invariant: same intent (trigger + target) deduped even when
    count fields in evidence vary across batches.

    Pre-D034 the dedup key was rationale text, which embeds mutable count
    fields. So `failure_count=308` and `failure_count=412` proposals about
    the same gate would write distinct rows every batch. Post-D034 they
    share intent ("gate_failure_concentration", "sharpe_gate") and dedup.
    """
    forge_db = tmp_path / "forge.db"
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    p1 = _proposal(
        rationale="308 of rejected failed `sharpe_gate`",
        evidence_json={
            "trigger": "gate_failure_concentration",
            "target": "sharpe_gate",
            "failure_count": "308",
        },
    )
    p2 = _proposal(
        rationale="412 of rejected failed `sharpe_gate`",
        evidence_json={
            "trigger": "gate_failure_concentration",
            "target": "sharpe_gate",
            "failure_count": "412",
        },
    )
    with db_connection(forge_db) as conn:
        a = append_proposal(p1, open_proposals_path=open_proposals, db=conn)
        b = append_proposal(p2, open_proposals_path=open_proposals, db=conn)
    assert a is True
    # b should dedup — same intent, just different count field
    assert b is False
