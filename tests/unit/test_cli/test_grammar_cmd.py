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
    target: str = "prefilter_calibration",
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
            json.dumps({"trigger": "test", "target_field": target}),
            status,
        ],
    )


_PREFILTER_YAML = """\
prefilter:
  signal_density:
    min_activations: 30
  expected_trade_count:
    min_trades: 50
  predicted_activations:
    min_entries: 10
  novelty:
    max_jaccard_overlap: 0.80
  signal_correlation:
    max_jaccard_overlap: 0.85
  regime_exposure:
    max_single_regime_concentration: 0.80
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
    forward_horizon_days: 0
  auto_tune:
    enabled: true
    min_promotion_rate: 0.005
    max_promotion_rate: 0.05
    adjustment_pct_per_step: 0.10
    max_cumulative_adjustment: 0.30
"""


def _insert_gate_failure_tighten(
    db: duckdb.DuckDBPyConnection,
    *,
    proposal_id: uuid.UUID,
    status: str = "pending",
) -> None:
    """Insert a proposer-shape tighten (the only shape apply-proposal handles)."""
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
            "tighten",
            "# proposed prefilter tightening",
            "100% of rejected candidates failed `sharpe_baseline`",
            json.dumps(
                {
                    "trigger": "gate_failure_concentration",
                    "target": "sharpe_baseline",
                    "failure_count": 110,
                    "failure_rate": 1.0,
                }
            ),
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


# ---------------------------------------------------------------------------
# apply-proposal (long-term #2)
# ---------------------------------------------------------------------------


def test_apply_proposal_tightens_yaml_and_marks_applied(tmp_path: Path) -> None:
    """Happy path: pending tighten → status='applied' + yaml threshold lowered."""
    forge_db = tmp_path / "forge.db"
    prefilter_yaml = tmp_path / "prefilter.yaml"
    prefilter_yaml.write_text(_PREFILTER_YAML)
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_gate_failure_tighten(conn, proposal_id=pid)
    result = runner.invoke(
        app,
        [
            "grammar",
            "apply-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "applied" in result.stdout
    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT status, decided_by FROM grammar_proposals WHERE proposal_id = ?",
            [str(pid)],
        ).fetchone()
    assert row == ("applied", "AJ")
    # The yaml content should have changed (some threshold tightened).
    new_text = prefilter_yaml.read_text()
    assert new_text != _PREFILTER_YAML


def test_apply_proposal_records_grammar_versions_row(tmp_path: Path) -> None:
    """The §13.2 audit trail row lands in grammar_versions."""
    forge_db = tmp_path / "forge.db"
    prefilter_yaml = tmp_path / "prefilter.yaml"
    prefilter_yaml.write_text(_PREFILTER_YAML)
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_gate_failure_tighten(conn, proposal_id=pid)
    runner.invoke(
        app,
        [
            "grammar",
            "apply-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    with db_connection(forge_db) as conn:
        rows = conn.execute(
            "SELECT change_type, change_description FROM grammar_versions"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "manual_tighten_calibration"
    assert str(pid) in rows[0][1]


def test_apply_proposal_rejects_loosen(tmp_path: Path) -> None:
    """Loosens stay on the manual path — hard rule #4 + §13.2."""
    forge_db = tmp_path / "forge.db"
    prefilter_yaml = tmp_path / "prefilter.yaml"
    prefilter_yaml.write_text(_PREFILTER_YAML)
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_proposal(conn, proposal_id=pid, proposal_type="loosen")
    result = runner.invoke(
        app,
        [
            "grammar",
            "apply-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    assert result.exit_code != 0
    assert "loosen" in result.output.lower() or "tighten" in result.output.lower()


def test_apply_proposal_rejects_unsupported_trigger(tmp_path: Path) -> None:
    """A hypothesis_dominance tighten targets grammar.yaml — manual only."""
    forge_db = tmp_path / "forge.db"
    prefilter_yaml = tmp_path / "prefilter.yaml"
    prefilter_yaml.write_text(_PREFILTER_YAML)
    pid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        conn.execute(
            """
            INSERT INTO grammar_proposals
                (proposal_id, proposed_at, proposal_type, proposal_yaml,
                 rationale, evidence_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(pid),
                datetime(2026, 5, 13, 12, tzinfo=UTC),
                "tighten",
                "# grammar tighten snippet",
                "hypothesis dominance",
                json.dumps({"trigger": "hypothesis_dominance"}),
                "pending",
            ],
        )
    result = runner.invoke(
        app,
        [
            "grammar",
            "apply-proposal",
            "--id",
            str(pid),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    assert result.exit_code != 0
    assert "trigger" in result.output.lower()


def test_apply_proposal_missing_id_errors(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    prefilter_yaml = tmp_path / "prefilter.yaml"
    prefilter_yaml.write_text(_PREFILTER_YAML)
    with db_connection(forge_db):
        pass
    result = runner.invoke(
        app,
        [
            "grammar",
            "apply-proposal",
            "--id",
            str(uuid.uuid4()),
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# T2.2 / D040 — `forge grammar revert` CLI
# ---------------------------------------------------------------------------


def _write_grammar_yaml(path: Path, version: str, rule_count: int = 1) -> None:
    """Minimal valid grammar.yaml for revert tests."""
    path.write_text(
        f"grammar_version: {version}\n"
        f"rules:\n"
        + "".join(
            f"  - id: S{i}\n    category: structural\n    version: 1\n"
            f"    active: true\n    rationale_ref: GRAMMAR.md#S{i}\n"
            f"    predicate:\n      type: cardinality\n      field: hypothesis\n      count: 1\n"
            f"    cost_estimate: low\n"
            for i in range(1, rule_count + 1)
        ),
        encoding="utf-8",
    )


def test_revert_promotes_prior_version_forward(tmp_path: Path) -> None:
    """T2.2 / D040 — revert to v1 produces a new v3 with v1's content.

    v1.yaml in archive (original) stays untouched. Current grammar.yaml
    becomes "v3 grammar_version + v1 rule content". v2 (the bad version
    we're reverting from) stays in archive for forensics.
    """
    forge_db = tmp_path / "forge.db"
    grammar_yaml = tmp_path / "grammar.yaml"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    # Build a v1 + v2 + current grammar.yaml(=v2)
    v1_archive = archive_dir / "v1.yaml"
    _write_grammar_yaml(v1_archive, "v1", rule_count=1)
    v2_archive = archive_dir / "v2.yaml"
    _write_grammar_yaml(v2_archive, "v2", rule_count=2)
    _write_grammar_yaml(grammar_yaml, "v2", rule_count=2)

    result = runner.invoke(
        app,
        [
            "grammar",
            "revert",
            "--to-version",
            "v1",
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--grammar-yaml",
            str(grammar_yaml),
            "--archive-dir",
            str(archive_dir),
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Current grammar.yaml now carries v3 label + v1's rule content
    text = grammar_yaml.read_text(encoding="utf-8")
    assert "grammar_version: v3" in text
    assert "id: S1" in text
    assert "id: S2" not in text  # v1 only had 1 rule; S2 was v2-only
    # v3 archive entry exists with same content (sans the REVERT header)
    v3_archive = archive_dir / "v3.yaml"
    assert v3_archive.exists()
    # v1 + v2 archives untouched
    assert v1_archive.read_text(encoding="utf-8").startswith("grammar_version: v1")
    assert v2_archive.read_text(encoding="utf-8").startswith("grammar_version: v2")
    # forge_db has a 'revert' audit row
    with db_connection(forge_db) as conn:
        rows = conn.execute(
            "SELECT change_type, change_description, operator_initials FROM grammar_versions "
            "WHERE change_type = 'revert'",
        ).fetchall()
    assert len(rows) == 1
    assert "reverted to v1" in rows[0][1]


def test_revert_rejects_missing_version(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    grammar_yaml = tmp_path / "grammar.yaml"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    _write_grammar_yaml(grammar_yaml, "v2")
    _write_grammar_yaml(archive_dir / "v2.yaml", "v2")
    result = runner.invoke(
        app,
        [
            "grammar",
            "revert",
            "--to-version",
            "v99",
            "--initials",
            "AJ",
            "--forge-db",
            str(forge_db),
            "--grammar-yaml",
            str(grammar_yaml),
            "--archive-dir",
            str(archive_dir),
        ],
    )
    assert result.exit_code != 0
    assert "no archive entry" in result.output


def test_revert_rejects_empty_initials(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    grammar_yaml = tmp_path / "grammar.yaml"
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    _write_grammar_yaml(grammar_yaml, "v2")
    _write_grammar_yaml(archive_dir / "v1.yaml", "v1")
    _write_grammar_yaml(archive_dir / "v2.yaml", "v2")
    result = runner.invoke(
        app,
        [
            "grammar",
            "revert",
            "--to-version",
            "v1",
            "--initials",
            "   ",
            "--forge-db",
            str(forge_db),
            "--grammar-yaml",
            str(grammar_yaml),
            "--archive-dir",
            str(archive_dir),
        ],
    )
    assert result.exit_code == 2  # typer-style "bad input" exit
