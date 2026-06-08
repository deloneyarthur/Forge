"""Tests for `forge feedback` CLI (Phase 5 module 10, D024/D6).

`forge feedback [--batch-id ID | --since T] [--crucible-db PATH]
[--forge-db PATH] [--config PATH]`: reads Crucible's gated runs for the
batch, runs analyzer + proposer, persists proposals to OPEN_PROPOSALS.md
and grammar_proposals.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

runner = CliRunner()


def _insert_forge_submission(
    db: duckdb.DuckDBPyConnection,
    *,
    batch_id: uuid.UUID,
    status: str = "submitted",
    cfg_override: object = None,
) -> uuid.UUID:
    candidate_id = uuid.uuid4()
    config = cfg_override or minimal_strategy_config()
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(candidate_id),
            str(batch_id),
            config.config_hash,
            config.model_dump_json(),
            datetime(2026, 5, 13, 12, tzinfo=UTC),
            status,
        ],
    )
    return candidate_id


def _insert_batch_summary(
    db: duckdb.DuckDBPyConnection,
    *,
    batch_id: uuid.UUID,
    batch_size: int = 1,
) -> None:
    db.execute(
        "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
        "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
        [str(batch_id), batch_size, datetime(2026, 5, 13, 12, tzinfo=UTC), "v1", "abc"],
    )


def _insert_crucible_gated(
    crucible_db: Path, *, config_hash: str, decision: str = "promote"
) -> None:
    conn = duckdb.connect(str(crucible_db))
    try:
        run_id = str(uuid.uuid4())
        gates = (
            {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": True, "value": 1.2}}
            if decision == "promote"
            else {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": False, "value": 0.4}}
        )
        conn.execute(
            "INSERT INTO runs (run_id, config_hash, source, status, period_start, "
            "period_end, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                config_hash,
                "forge",
                "gated",
                date(2022, 1, 1),
                date(2024, 12, 31),
                date(2026, 5, 13),
                date(2026, 5, 13),
            ],
        )
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [
                run_id,
                decision,
                json.dumps(gates),
                datetime(2026, 5, 13, 14, tzinfo=UTC),
                "gate_v1",
            ],
        )
        conn.execute(
            "INSERT INTO metrics (run_id, metric_name, value) VALUES (?, ?, ?)",
            [run_id, "walk_forward_sharpe_median", 1.2],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def test_feedback_help() -> None:
    result = runner.invoke(app, ["feedback", "--help"])
    assert result.exit_code == 0
    assert "feedback" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Missing required args
# ---------------------------------------------------------------------------


def test_feedback_no_crucible_db_errors(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db):
        pass
    result = runner.invoke(
        app,
        ["feedback", "--forge-db", str(forge_db), "--no-config"],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_feedback_happy_path(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash, decision="promote")
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, batch_id=batch_id, cfg_override=cfg)
    result = runner.invoke(
        app,
        [
            "feedback",
            "--no-config",
            "--forge-db",
            str(forge_db),
            "--crucible-db",
            str(crucible_db),
            "--batch-id",
            str(batch_id),
            "--open-proposals",
            str(tmp_path / "OPEN_PROPOSALS.md"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "gated_count=1" in result.stdout
    assert "promoted_count=1" in result.stdout
    # Verify the submission status was updated
    with db_connection(forge_db) as conn:
        row = conn.execute("SELECT status FROM submissions").fetchone()
    assert row is not None
    assert row[0] == "gated"


def test_feedback_writes_proposal_when_trigger_fires(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    # 4 promoted candidates of same hypothesis → trigger (b) hypothesis_dominance fires
    cfgs = [minimal_strategy_config().model_copy(update={"name": f"c{i}"}) for i in range(4)]
    for cfg in cfgs:
        _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash, decision="promote")
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=4)
        for cfg in cfgs:
            _insert_forge_submission(conn, batch_id=batch_id, cfg_override=cfg)
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    result = runner.invoke(
        app,
        [
            "feedback",
            "--no-config",
            "--forge-db",
            str(forge_db),
            "--crucible-db",
            str(crucible_db),
            "--batch-id",
            str(batch_id),
            "--open-proposals",
            str(open_proposals),
        ],
    )
    assert result.exit_code == 0
    assert open_proposals.exists()
    content = open_proposals.read_text(encoding="utf-8")
    assert "hypothesis_dominance" in content


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_feedback_idempotent_for_same_batch(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, batch_id=batch_id, cfg_override=cfg)
    args = [
        "feedback",
        "--no-config",
        "--forge-db",
        str(forge_db),
        "--crucible-db",
        str(crucible_db),
        "--batch-id",
        str(batch_id),
        "--open-proposals",
        str(tmp_path / "OPEN_PROPOSALS.md"),
    ]
    first = runner.invoke(app, args)
    second = runner.invoke(app, args)
    assert first.exit_code == 0
    assert second.exit_code == 0
    # Both runs see the same gated outcome
    assert "gated_count=1" in first.stdout
    assert "gated_count=1" in second.stdout


# ---------------------------------------------------------------------------
# D054 / P1-2 — `forge feedback` produces the same enrichment as the loop
# ---------------------------------------------------------------------------


def test_d054_feedback_cmd_stamps_counterfactual_phase_into_proposals(
    tmp_path: Path,
) -> None:
    """D054: manual `forge feedback` must apply the same T2.3 counterfactual
    enrichment as the autonomous loop's `_consume_feedback_after_submit`.
    Both call sites should produce identical OPEN_PROPOSALS.md output for
    the same input batch, so the operator's manual diagnostic path is not
    second-class. Pre-D054 the manual command bypassed enrichment entirely,
    silently producing different evidence_json than the loop."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    cfgs = [minimal_strategy_config().model_copy(update={"name": f"d54_{i}"}) for i in range(4)]
    for cfg in cfgs:
        _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash, decision="promote")
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=4)
        for cfg in cfgs:
            _insert_forge_submission(conn, batch_id=batch_id, cfg_override=cfg)
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    result = runner.invoke(
        app,
        [
            "feedback",
            "--no-config",
            "--forge-db",
            str(forge_db),
            "--crucible-db",
            str(crucible_db),
            "--batch-id",
            str(batch_id),
            "--open-proposals",
            str(open_proposals),
        ],
    )
    assert result.exit_code == 0
    assert open_proposals.exists()
    content = open_proposals.read_text(encoding="utf-8")
    # T2.3 counterfactual fields must appear in every proposal's evidence.
    assert "counterfactual_phase" in content, (
        "manual `forge feedback` did not stamp counterfactual_phase into "
        "evidence_json — diverges from the autonomous loop output."
    )
    assert "counterfactual_rejection_rate" in content
    assert "counterfactual_promoted_count" in content
    # And the static disclaimer note.
    assert "phase-1 binary safety floor" in content


# ---------------------------------------------------------------------------
# M-12 (audit 2026-05-29) — `forge feedback` must run the §13.5 startup
# contracts-version check before any Crucible I/O (every other Crucible-touching
# command does; feedback was the gap).
# ---------------------------------------------------------------------------


def test_m12_feedback_checks_contracts_version_before_io(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from crucible_contracts import SchemaVersionMismatch

    import forge.core.contracts_check as cc

    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"

    def _raise() -> str:
        raise SchemaVersionMismatch("forge expects 1.x, contracts is 2.x")

    monkeypatch.setattr(cc, "check_contracts_version", _raise)
    result = runner.invoke(
        app,
        ["feedback", "--no-config", "--forge-db", str(forge_db), "--crucible-db", str(crucible_db)],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, SchemaVersionMismatch)
