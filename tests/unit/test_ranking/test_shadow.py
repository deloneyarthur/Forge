"""Tests for forge.ranking.shadow (D132 / F2) — telemetry-only shadow scoring.

The recorder runs AFTER selection and submission, reads everything and
mutates nothing but the `shadow_scores` table, and must never raise into
the production loop — a missing/corrupt model, a missing table row, or any
internal error degrades to "0 rows recorded" with a structlog warning.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import polars as pl

from forge.persistence.db import db_connection
from forge.prefilters.types import PreFilterReport
from forge.ranking.model import save_model, train_verdict_model
from forge.ranking.shadow import run_shadow_scoring
from forge.ranking.types import RankedCandidate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SCORED_AT = datetime(2026, 6, 10, 22, 0, 0)  # noqa: DTZ001 — naive-UTC convention


def _toy_model_dir(tmp_path: Path) -> Path:
    records = []
    for i in range(30):
        records.append(
            {
                "crucible_run_id": f"run-{i:04d}",
                "config_hash": f"hash{i:012d}",
                "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                "decision": "component" if i % 5 == 0 else "reject",
                "label": int(i % 5 == 0),
                "hypothesis=mean_reversion": 1.0,
                "f_noise": float(i % 3),
            }
        )
    model = train_verdict_model(pl.DataFrame(records), era_cut=_ERA_CUT)
    models_dir = tmp_path / "models"
    save_model(model, models_dir)
    return models_dir


def _candidate(composite: float = 0.7) -> RankedCandidate:
    return RankedCandidate(
        report=PreFilterReport(
            config=minimal_strategy_config(),
            passed=True,
            filter_results={},
            diagnostic_notes=(),
        ),
        prior_promotion_score=0.0,
        composite_score=composite,
    )


def _insert_submission(db: duckdb.DuckDBPyConnection, *, batch_id: str, config_hash: str) -> str:
    candidate_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
        [candidate_id, batch_id, config_hash, _SCORED_AT, "submitted"],
    )
    return candidate_id


def test_shadow_scores_table_created_by_ensure_schema() -> None:
    with db_connection() as conn:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'shadow_scores'",
        ).fetchall()
    assert {c[0] for c in cols} == {
        "forge_candidate_id",
        "model_id",
        "model_score",
        "composite_score",
        "scored_at",
    }


def test_records_scores_for_submitted_candidates(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate(composite=0.7)
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        rows = conn.execute(
            "SELECT model_id, model_score, composite_score FROM shadow_scores",
        ).fetchall()

    assert recorded == 1
    assert len(rows) == 1
    model_id, model_score, composite_score = rows[0]
    assert len(model_id) == 16
    assert 0.0 <= model_score <= 1.0
    assert composite_score == 0.7


def test_no_models_dir_is_noop(tmp_path: Path) -> None:
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=tmp_path / "absent",
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        count = conn.execute("SELECT count(*) FROM shadow_scores").fetchone()

    assert recorded == 0
    assert count is not None
    assert count[0] == 0


def test_corrupt_only_models_dir_is_noop(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "verdict_model_v1_bad.json").write_text("{nope", encoding="utf-8")
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )

    assert recorded == 0


def test_rerun_does_not_duplicate(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        for _ in range(2):
            run_shadow_scoring(
                conn,
                models_dir=models_dir,
                candidates=[candidate],
                registry=_REGISTRY,
                batch_id=batch_id,
                scored_at=_SCORED_AT,
            )
        count = conn.execute("SELECT count(*) FROM shadow_scores").fetchone()

    assert count is not None
    assert count[0] == 1


def test_candidate_without_submission_row_is_skipped(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    with db_connection() as conn:
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[_candidate()],
            registry=_REGISTRY,
            batch_id=str(uuid.uuid4()),
            scored_at=_SCORED_AT,
        )

    assert recorded == 0


def test_submissions_table_is_never_mutated(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        before = conn.execute("SELECT * FROM submissions ORDER BY forge_candidate_id").fetchall()
        run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        after = conn.execute("SELECT * FROM submissions ORDER BY forge_candidate_id").fetchall()

    assert before == after
