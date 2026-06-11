"""Tests for `forge ranker-model dataset` (D132 / F1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

runner = CliRunner()


def _seed_forge_db(db_path: Path, *, decided_at: datetime) -> None:
    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

    rid = str(uuid.uuid4())
    run = GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash="aaaa000011112222",
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v17",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision="component",
            gate_results={
                "regime_coverage": GateResult(
                    gate_name="regime_coverage",
                    passed=True,
                    value=None,
                    threshold=None,
                    detail="",
                ),
            },
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "aaaa000011112222",
                minimal_strategy_config().model_dump_json(),
                datetime(2026, 6, 10, 11, 0),  # noqa: DTZ001 — naive-UTC convention
                "gated",
            ],
        )
        record_verdicts(conn, [run])


def _write_registry_export(exports_dir: Path) -> None:
    exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = minimal_registry_snapshot()
    (exports_dir / "registry_snapshot_2026-06-10T180000Z.json").write_text(
        snapshot.model_dump_json(), encoding="utf-8"
    )


def test_dataset_command_writes_parquet(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_forge_db(db_path, decided_at=datetime(2026, 6, 10, 18, 0))  # noqa: DTZ001
    _write_registry_export(tmp_path / "exports")
    out = tmp_path / "dataset.parquet"

    result = runner.invoke(
        app,
        [
            "ranker-model",
            "dataset",
            "--forge-db",
            str(db_path),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    frame = pl.read_parquet(out)
    assert frame.height == 1
    assert frame["label"].to_list() == [1]
    assert "dataset: 1 rows (1 positive)" in result.output


def test_dataset_command_era_cut_override(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    # Post-default-cut but pre-override: excluded under the override.
    _seed_forge_db(db_path, decided_at=datetime(2026, 6, 10, 18, 0))  # noqa: DTZ001
    _write_registry_export(tmp_path / "exports")
    out = tmp_path / "dataset.parquet"

    result = runner.invoke(
        app,
        [
            "ranker-model",
            "dataset",
            "--forge-db",
            str(db_path),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--era-cut",
            "2026-06-10T19:00:00+00:00",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert pl.read_parquet(out).height == 0
