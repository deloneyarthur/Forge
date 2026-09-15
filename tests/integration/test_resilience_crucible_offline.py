"""Phase 6 — resilience scenario: Crucible offline (§12 / D025/D3.i).

When `forge feedback` is invoked against a non-existent or unreachable
``--crucible-db``, it must:

  1. Exit with a non-zero status (no silent success).
  2. Surface a clean error message naming the unreachable DB (not a
     bare stack trace).
  3. Leave the Forge DB unchanged — no partial mutations to
     ``submissions.status`` or ``batch_summaries.promotion_rate``.

Property (3) is the resilience invariant that matters most: a missing
Crucible DB must not corrupt Forge state.
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


def _consume(forge_db: Path, crucible_db: Path, batch_id: uuid.UUID) -> None:
    """The consumer call `forge feedback` used to wrap (the CLI left in Batch 5 G1). No gated
    export exists under `noexports`, so the consumer falls through to the direct-DB path — the
    "Crucible offline" condition (D025/D3.i) it must surface, never swallow."""
    with db_connection(forge_db) as conn:
        consume_batch_results(
            conn, crucible_db, batch_id=batch_id, exports_dir=forge_db.parent / "noexports"
        )


def test_missing_crucible_db_raises_query_error(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    batch_id = _seed_forge_db_with_submitted_batch(forge_db)
    missing_crucible = tmp_path / "does_not_exist.db"
    assert not missing_crucible.exists()
    with pytest.raises(QueryError):
        _consume(forge_db, missing_crucible, batch_id)


def test_missing_crucible_db_leaves_forge_db_unchanged(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    batch_id = _seed_forge_db_with_submitted_batch(forge_db)
    before = _read_submission_state(forge_db)
    assert before["status"] == "submitted"
    assert before["crucible_run_id"] is None
    assert before["promotion_rate"] is None
    with pytest.raises(QueryError):
        _consume(forge_db, tmp_path / "does_not_exist.db", batch_id)
    after = _read_submission_state(forge_db)
    assert after == before, (
        f"forge_db mutated despite Crucible offline: before={before}, after={after}"
    )


def test_unreadable_crucible_db_does_not_crash_silently(tmp_path: Path) -> None:
    """An empty/bogus file at the crucible_db path (a different failure mode than 'missing')
    also surfaces as a clean QueryError rather than an unhandled crash."""
    forge_db = tmp_path / "forge.db"
    batch_id = _seed_forge_db_with_submitted_batch(forge_db)
    bogus_crucible = tmp_path / "not_a_db.db"
    bogus_crucible.write_bytes(b"this is not a duckdb file")
    with pytest.raises(QueryError):
        _consume(forge_db, bogus_crucible, batch_id)
