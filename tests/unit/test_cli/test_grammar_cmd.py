"""Tests for `forge grammar list-proposals / approve-proposal / reject-proposal`
(Phase 5 module 12, D024/D11; §8.5 operator workflow).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection

runner = CliRunner()


def _insert_proposal(
    db: duckdb.DuckDBPyConnection,
    *,
    proposal_id: uuid.UUID,
    proposal_type: str = "loosen",
    status: str = "pending",
    rationale: str = "test rationale",
) -> None:
    db.execute(
        """
        INSERT INTO grammar_proposals
            (proposal_id, proposed_at, proposal_type, proposal_yaml,
             rationale, evidence_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(proposal_id),
            datetime(2026, 5, 13, 12, tzinfo=UTC),
            proposal_type,
            "# yaml snippet",
            rationale,
            json.dumps({"trigger": "test"}),
            status,
        ],
    )


# ---------------------------------------------------------------------------
# list-proposals
# ---------------------------------------------------------------------------


def test_list_proposals_empty_prints_no_pending(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db):
        pass
    result = runner.invoke(
        app,
        ["grammar", "list-proposals", "--forge-db", str(forge_db)],
    )
    assert result.exit_code == 0, result.stdout
    assert "no pending" in result.stdout.lower() or "0 pending" in result.stdout.lower()


def test_list_proposals_shows_pending(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_proposal(conn, proposal_id=pid, rationale="unique rationale here")
    result = runner.invoke(
        app,
        ["grammar", "list-proposals", "--forge-db", str(forge_db)],
    )
    assert result.exit_code == 0
    assert str(pid) in result.stdout
    assert "unique rationale here" in result.stdout


def test_list_proposals_skips_approved(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    pid_p = uuid.uuid4()
    pid_a = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_proposal(conn, proposal_id=pid_p, rationale="pending one")
        _insert_proposal(conn, proposal_id=pid_a, status="approved", rationale="approved one")
    result = runner.invoke(
        app,
        ["grammar", "list-proposals", "--forge-db", str(forge_db)],
    )
    assert result.exit_code == 0
    assert "pending one" in result.stdout
    assert "approved one" not in result.stdout


# ---------------------------------------------------------------------------
# approve-proposal
# ---------------------------------------------------------------------------


def test_approve_proposal_updates_row(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_proposal(conn, proposal_id=pid)
    result = runner.invoke(
        app,
        [
            "grammar",
            "approve-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
        ],
    )
    assert result.exit_code == 0
    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT status, decided_by, decided_at FROM grammar_proposals WHERE proposal_id = ?",
            [str(pid)],
        ).fetchone()
    assert row is not None
    assert row[0] == "approved"
    assert row[1] == "AJ"
    assert row[2] is not None


def test_approve_unknown_id_errors(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db):
        pass
    result = runner.invoke(
        app,
        [
            "grammar",
            "approve-proposal",
            "--id",
            str(uuid.uuid4()),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
        ],
    )
    assert result.exit_code != 0


def test_approve_already_approved_is_idempotent(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_proposal(conn, proposal_id=pid, status="approved")
    result = runner.invoke(
        app,
        [
            "grammar",
            "approve-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
        ],
    )
    # Re-approve is OK (status already 'approved')
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# reject-proposal
# ---------------------------------------------------------------------------


def test_reject_proposal_updates_status(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_proposal(conn, proposal_id=pid)
    result = runner.invoke(
        app,
        [
            "grammar",
            "reject-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
        ],
    )
    assert result.exit_code == 0
    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT status FROM grammar_proposals WHERE proposal_id = ?",
            [str(pid)],
        ).fetchone()
    assert row is not None
    assert row[0] == "rejected"
