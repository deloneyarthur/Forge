"""Phase 6 — resilience scenario: Crucible's gated export absent or corrupt (§12 / D025/D3.i).

Since D422 Forge reads Crucible ONLY through its exports (hard rule #2; the direct
`runs.duckdb` fallback is gone). Two failure modes, two contracts:

  1. An ABSENT export (dir or file) is zero runs: the consumer completes, and the
     Forge DB is left unchanged — no partial mutation to `submissions.status` or
     `batch_summaries.promotion_rate`. Presence is the weekly run's boot check.
  2. A CORRUPT export must surface as `QueryError` (a corrupt snapshot is not
     "0 gated"), again leaving the Forge DB unchanged.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crucible_contracts.exceptions import QueryError

from forge.feedback.consumer import consume_batch_results
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_strategy_config


def _seed_forge_db_with_submitted_batch(forge_db: Path) -> uuid.UUID:
    """Insert a batch_summaries row + one submitted submission; return batch_id."""
    batch_id = uuid.uuid4()
    cfg = minimal_strategy_config()
    submitted_at = datetime(2026, 5, 13, 12, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
            "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
            [str(batch_id), 1, submitted_at, "v1", "abc"],
        )
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                str(batch_id),
                cfg.config_hash,
                cfg.model_dump_json(),
                submitted_at,
                "submitted",
            ],
        )
    return batch_id


def _read_submission_state(forge_db: Path) -> dict[str, object]:
    with db_connection(forge_db) as conn:
        sub_row = conn.execute("SELECT status, crucible_run_id FROM submissions").fetchone()
        bs_row = conn.execute(
            "SELECT promotion_rate, common_failures, completed_at FROM batch_summaries"
        ).fetchone()
    assert sub_row is not None
    assert bs_row is not None
    return {
        "status": sub_row[0],
        "crucible_run_id": sub_row[1],
        "promotion_rate": bs_row[0],
        "common_failures": bs_row[1],
        "completed_at": bs_row[2],
    }


def _consume(forge_db: Path, exports_dir: Path, batch_id: uuid.UUID) -> object:
    with db_connection(forge_db) as conn:
        return consume_batch_results(conn, batch_id=batch_id, exports_dir=exports_dir)


def test_absent_export_is_zero_runs_and_leaves_submissions_unchanged(tmp_path: Path) -> None:
    """Zero runs is a legitimate (if empty) reconcile: no submission row moves. The batch
    summary is recomputed from what is known (nothing gated → promotion_rate 0.0), exactly as
    it is when an export exists but names none of the batch's hashes — that recompute is
    idempotent and is not the partial-mutation hazard this scenario guards against."""
    forge_db = tmp_path / "forge.db"
    batch_id = _seed_forge_db_with_submitted_batch(forge_db)
    before = _read_submission_state(forge_db)
    assert before["status"] == "submitted"
    missing_dir = tmp_path / "no_exports"
    assert not missing_dir.exists()
    feedback = _consume(forge_db, missing_dir, batch_id)
    assert getattr(feedback, "gated_count", None) == 0
    after = _read_submission_state(forge_db)
    assert after["status"] == "submitted"
    assert after["crucible_run_id"] is None
    assert after["completed_at"] is None


def test_empty_export_dir_is_zero_runs(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    batch_id = _seed_forge_db_with_submitted_batch(forge_db)
    empty_dir = tmp_path / "exports"
    empty_dir.mkdir()
    feedback = _consume(forge_db, empty_dir, batch_id)
    assert getattr(feedback, "gated_count", None) == 0
    assert _read_submission_state(forge_db)["status"] == "submitted"


def test_corrupt_export_raises_query_error_and_leaves_forge_db_unchanged(tmp_path: Path) -> None:
    """A corrupt snapshot is not "0 gated": the loader's QueryError must propagate (never be
    swallowed, CLAUDE.md blessed exceptions) and nothing in the Forge DB may move."""
    forge_db = tmp_path / "forge.db"
    batch_id = _seed_forge_db_with_submitted_batch(forge_db)
    before = _read_submission_state(forge_db)
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "gated_runs_0001.json").write_text("this is not json", encoding="utf-8")
    with pytest.raises(QueryError):
        _consume(forge_db, exports, batch_id)
    assert _read_submission_state(forge_db) == before  # the raise precedes every write
