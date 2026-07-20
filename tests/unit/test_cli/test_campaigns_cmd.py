"""Tests for `forge campaigns` (D299) — registry listing + carriage audit CLI.

Thin wrappers over ``forge.ranking.campaigns`` / ``campaign_audit`` (the pure
logic is tested there); these pin the CLI contract: list shows every registry
record with its decision read, audit exits 1 when any campaign is starved
(usable as a scripted tripwire) and 0 otherwise.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import open_db

runner = CliRunner()


def test_campaigns_list_shows_registry() -> None:
    result = runner.invoke(app, ["campaigns", "list"])
    assert result.exit_code == 0
    for name in ("resid-vix-two-arm", "mr-timer-duration", "ve-exit-repair"):
        assert name in result.output
    assert "farming" in result.output
    # The conversion note is the whole point of the lifecycle — show it.
    assert "65316ca4" in result.output


def _seed_db(path: Path, *, starve_ve: bool) -> None:
    now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
    conn = open_db(path)
    rows: list[tuple[str, str | None]] = []
    if starve_ve:
        # ve members: 1 of 100 ranked (1%), 3 of 10 holdout (30%) -> starved.
        rows += [("volatility_event", "ranked")]
        rows += [("trend_continuation", "ranked")] * 99
        rows += [("volatility_event", "holdout")] * 3
        rows += [("trend_continuation", "holdout")] * 7
    else:
        rows += [("trend_continuation", "ranked")] * 10
    for hypothesis, mode in rows:
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status, crucible_run_id, selection_mode)
            VALUES (?, ?, ?, ?, ?, 'submitted', NULL, ?)
            """,
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                uuid.uuid4().hex[:16],
                json.dumps({"hypothesis": hypothesis}),
                (now - timedelta(days=1)).replace(tzinfo=None),
                mode,
            ],
        )
    conn.close()


def test_campaigns_audit_exit_1_on_starvation(tmp_path: Path) -> None:
    db = tmp_path / "forge.db"
    _seed_db(db, starve_ve=True)
    result = runner.invoke(app, ["campaigns", "audit", "--forge-db", str(db)])
    assert result.exit_code == 1
    assert "STARVED" in result.output
    assert "ve-exit-repair" in result.output


def test_campaigns_audit_exit_0_when_healthy(tmp_path: Path) -> None:
    db = tmp_path / "forge.db"
    _seed_db(db, starve_ve=False)
    result = runner.invoke(app, ["campaigns", "audit", "--forge-db", str(db)])
    assert result.exit_code == 0
    assert "STARVED" not in result.output
