"""Tests for `forge yield-audit` (D302) — CLI contract only (logic lives in
``forge.feedback.yield_audit`` and is tested there). Pins: exit 0 always
(detection, not a tripwire), dead names render a staged rider draft, and the
command never writes anything."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import open_db

runner = CliRunner()

_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)


def _seed_db(path: Path, *, dead_count: int) -> None:
    conn = open_db(path)
    for _ in range(dead_count):
        config_hash = uuid.uuid4().hex[:16]
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status, crucible_run_id, selection_mode)
            VALUES (?, ?, ?, ?, ?, 'submitted', NULL, 'ranked')
            """,
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                config_hash,
                json.dumps(
                    {
                        "underlying": "XYZ",
                        "hypothesis": "trend_continuation",
                        "dte_bucket": "swing_mid",
                    }
                ),
                _NOW.replace(tzinfo=None),
            ],
        )
        conn.execute(
            """
            INSERT INTO verdicts
                (crucible_run_id, config_hash, decision, decided_at, trade_count,
                 grammar_version, gate_results, recorded_at)
            VALUES (?, ?, 'reject', ?, NULL, 'v42', '{}', ?)
            """,
            [
                str(uuid.uuid4()),
                config_hash,
                _NOW.replace(tzinfo=None),
                _NOW.replace(tzinfo=None),
            ],
        )
    conn.close()


def test_yield_audit_prints_rider_draft_on_dead_name(tmp_path: Path) -> None:
    db = tmp_path / "forge.db"
    _seed_db(db, dead_count=12)
    before = sorted(tmp_path.iterdir())
    result = runner.invoke(
        app,
        ["yield-audit", "--forge-db", str(db), "--min-name-n", "10"],
    )
    assert result.exit_code == 0
    assert "DEAD NAMES (1): XYZ" in result.output
    assert "STAGED RIDER DRAFT" in result.output
    assert "prereg" in result.output  # the D207 discipline is part of the draft
    assert sorted(tmp_path.iterdir()) == before  # writes nothing


def test_yield_audit_clean_run(tmp_path: Path) -> None:
    db = tmp_path / "forge.db"
    _seed_db(db, dead_count=3)  # below the floor
    result = runner.invoke(
        app,
        ["yield-audit", "--forge-db", str(db), "--min-name-n", "10"],
    )
    assert result.exit_code == 0
    assert "no dead-name flags" in result.output
