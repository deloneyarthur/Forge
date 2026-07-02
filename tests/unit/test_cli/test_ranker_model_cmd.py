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


def _seed_training_db(db_path: Path, *, n: int = 60) -> None:
    """n submissions with varying delta_target; every 6th verdict an honest component."""
    from crucible_contracts import GatedRun, SelectorSpec
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

    with db_connection(db_path) as conn:
        runs = []
        for i in range(n):
            config_hash = f"cafe{i:012d}"
            config = minimal_strategy_config(
                selector=SelectorSpec(
                    delta_target=0.40 + (i % 15) * 0.01,
                    delta_tolerance=0.05,
                    dte_min=14,
                    dte_max=21,
                ),
            )
            conn.execute(
                "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
                "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                    config_hash,
                    config.model_dump_json(),
                    datetime(2026, 6, 10, 17, 30),  # noqa: DTZ001
                    "gated",
                ],
            )
            rid = str(uuid.uuid4())
            runs.append(
                GatedRun(
                    run=RunResult(
                        run_id=rid,
                        config_hash=config_hash,
                        metrics={"total_return": 0.1},
                        trade_count=120,
                        period_start=date(2021, 6, 2),
                        period_end=date(2026, 6, 1),
                        grammar_version="v17",
                    ),
                    decision=PromotionDecision(
                        run_id=rid,
                        decision="component" if i % 6 == 0 else "reject",
                        gate_results={
                            "regime_coverage": GateResult(
                                gate_name="regime_coverage",
                                passed=True,
                                value=None,
                                threshold=None,
                                detail="",
                            ),
                            "cpcv_sharpe_p25": GateResult(
                                gate_name="cpcv_sharpe_p25",
                                passed=False,
                                value=0.3 + (0.5 if i % 6 == 0 else 0.0) + (i % 5) * 0.02,
                                threshold=1.5,
                            ),
                        },
                        decided_at=datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                        decided_by="runner.forge_minimal",
                    ),
                )
            )
        record_verdicts(conn, runs)


def test_train_command_writes_artifact(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path)
    _write_registry_export(tmp_path / "exports")
    models_dir = tmp_path / "models"

    result = runner.invoke(
        app,
        [
            "ranker-model",
            "train",
            "--forge-db",
            str(db_path),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--models-dir",
            str(models_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    artifacts = list(models_dir.glob("verdict_model_*.json"))
    assert len(artifacts) == 1
    assert "model_id=" in result.output
    assert "rows=60 (10 positive)" in result.output


def test_train_command_refuses_tiny_dataset(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path, n=12)
    _write_registry_export(tmp_path / "exports")

    result = runner.invoke(
        app,
        [
            "ranker-model",
            "train",
            "--forge-db",
            str(db_path),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--models-dir",
            str(tmp_path / "models"),
        ],
    )

    assert result.exit_code == 1
    assert "refusing to train" in result.output


def test_eval_command_reports_model_vs_incumbent(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path, n=24)
    # Attach shadow scores for the existing candidates: model tracks the label,
    # incumbent is anti-correlated.
    with db_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT s.forge_candidate_id, v.decision FROM submissions s "
            "JOIN verdicts v ON v.config_hash = s.config_hash",
        ).fetchall()
        for candidate_id, decision in rows:
            positive = decision == "component"
            conn.execute(
                "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
                "composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
                [
                    str(candidate_id),
                    "feedbeeffeedbeef",
                    0.9 if positive else 0.1,
                    0.1 if positive else 0.9,
                    datetime(2026, 6, 10, 17, 30),  # noqa: DTZ001
                ],
            )

    result = runner.invoke(
        app,
        ["ranker-model", "eval", "--forge-db", str(db_path)],
    )

    assert result.exit_code == 0, result.output
    assert "model=feedbeeffeedbeef" in result.output
    assert "auc_margin=+1.000" in result.output
    assert "criterion(+0.05)=PASS" in result.output


def test_train_robustness_command_writes_artifact(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path)
    _write_registry_export(tmp_path / "exports")
    models_dir = tmp_path / "models"

    result = runner.invoke(
        app,
        [
            "ranker-model",
            "train-robustness",
            "--forge-db",
            str(db_path),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--models-dir",
            str(models_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    artifacts = list(models_dir.glob("robustness_model_*.json"))
    assert len(artifacts) == 1
    assert "trained robustness[target_cpcv_p25]" in result.output
    assert "train_r2=" in result.output


def test_train_robustness_refuses_when_target_all_null(tmp_path: Path) -> None:
    # The seeder carries cpcv but not WF — train-robustness on WF must refuse.
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path)
    _write_registry_export(tmp_path / "exports")

    result = runner.invoke(
        app,
        [
            "ranker-model",
            "train-robustness",
            "--forge-db",
            str(db_path),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--models-dir",
            str(tmp_path / "models"),
            "--target",
            "target_wf_median",
        ],
    )

    assert result.exit_code == 1
    assert "refusing to train" in result.output


def test_eval_robustness_command(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path)  # 60 submissions + verified verdicts carrying cpcv
    # Attach tail scores to every candidate.
    with db_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT forge_candidate_id FROM submissions ORDER BY config_hash"
        ).fetchall()
        for idx, (candidate_id,) in enumerate(rows):
            conn.execute(
                "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
                "composite_score, scored_at, tail_score, tail_model_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    str(candidate_id),
                    "logistic00000000",
                    0.5,
                    0.5,
                    datetime(2026, 6, 10, 17, 30),  # noqa: DTZ001
                    idx / 60.0,
                    "tailmodel0000001",
                ],
            )

    result = runner.invoke(app, ["ranker-model", "eval-robustness", "--forge-db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert "tail_model=tailmodel0000001" in result.output
    assert "decided=60" in result.output
    # P0.5a: the readout labels the ACTUAL --gate (default cpcv_sharpe_p25), not a
    # hardcoded "cpcv_p25" that mislabels every non-cpcv gate.
    assert "spearman(pred,realized cpcv_sharpe_p25)=" in result.output
    assert "realized cpcv_p25)" not in result.output
    assert "top-" in result.output


def test_eval_robustness_command_no_tail_scores(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    _seed_training_db(db_path, n=12)  # verdicts but no tail-scored shadow rows
    result = runner.invoke(app, ["ranker-model", "eval-robustness", "--forge-db", str(db_path)])
    assert result.exit_code == 0, result.output
    assert "no tail-scored verdicts" in result.output


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
