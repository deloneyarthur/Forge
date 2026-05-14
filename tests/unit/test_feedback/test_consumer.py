"""Tests for feedback.consumer (Phase 5 module 2, D024/D1).

`consume_batch_results` joins Crucible's gated runs to Forge's submissions
by config_hash, updates the submissions row (status: submitted -> gated;
crucible_run_id set), updates batch_summaries (promotion_rate, common_failures,
completed_at on 100%), and returns an in-memory BatchFeedback.

The function is idempotent: re-running over the same data is a no-op.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import pytest
from crucible_contracts import (
    StrategyConfig,
)

from forge.feedback.consumer import consume_batch_results
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _insert_forge_submission(
    db: duckdb.DuckDBPyConnection,
    *,
    config: StrategyConfig,
    batch_id: uuid.UUID,
    status: str = "submitted",
    submitted_at: datetime | None = None,
) -> uuid.UUID:
    candidate_id = uuid.uuid4()
    ts = submitted_at or datetime(2026, 5, 13, 12, tzinfo=UTC)
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(candidate_id),
            str(batch_id),
            config.config_hash,
            config.model_dump_json(),
            ts,
            status,
        ],
    )
    return candidate_id


def _insert_batch_summary(
    db: duckdb.DuckDBPyConnection,
    *,
    batch_id: uuid.UUID,
    batch_size: int,
    submitted_at: datetime | None = None,
) -> None:
    ts = submitted_at or datetime(2026, 5, 13, 12, tzinfo=UTC)
    db.execute(
        "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
        "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
        [str(batch_id), batch_size, ts, "v1", "abc1234"],
    )


def _insert_crucible_gated(
    crucible_db: Path,
    *,
    config_hash: str,
    decision: str = "promote",
    failed_gate: str | None = None,
) -> str:
    conn = duckdb.connect(str(crucible_db))
    try:
        run_id = str(uuid.uuid4())
        if failed_gate is not None:
            gate_results = {failed_gate: {"gate_name": failed_gate, "passed": False, "value": 0.4}}
        else:
            gate_results = {
                "sharpe_gate": {"gate_name": "sharpe_gate", "passed": True, "value": 1.2}
            }
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
                json.dumps(gate_results),
                datetime(2026, 5, 13, 14, tzinfo=UTC),
                "gate_v1",
            ],
        )
        conn.execute(
            "INSERT INTO metrics (run_id, metric_name, value) VALUES (?, ?, ?)",
            [run_id, "walk_forward_sharpe_median", 1.2],
        )
        return run_id
    finally:
        conn.close()


def _setup_paths(tmp_path: Path) -> tuple[Path, Path]:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    return forge_db, crucible_db


# ---------------------------------------------------------------------------
# Empty / pending-only cases
# ---------------------------------------------------------------------------


def test_consume_returns_empty_outcomes_when_crucible_db_empty(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=2)
        _insert_forge_submission(conn, config=minimal_strategy_config(), batch_id=batch_id)
        result = consume_batch_results(conn, crucible_db, batch_id=batch_id)
    assert result.batch_id == batch_id
    assert result.gated_count == 0
    assert result.pending_count == 1


def test_consume_raises_when_neither_batch_id_nor_since(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    with db_connection(forge_db) as conn, pytest.raises(ValueError, match="batch_id"):
        consume_batch_results(conn, crucible_db)


def test_consume_auto_discovers_latest_batch_with_submitted_rows(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    old_batch = uuid.uuid4()
    new_batch = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(
            conn,
            batch_id=old_batch,
            batch_size=1,
            submitted_at=datetime(2026, 5, 10, 12, tzinfo=UTC),
        )
        _insert_batch_summary(
            conn,
            batch_id=new_batch,
            batch_size=1,
            submitted_at=datetime(2026, 5, 13, 12, tzinfo=UTC),
        )
        _insert_forge_submission(
            conn,
            config=minimal_strategy_config().model_copy(update={"name": "old_batch_cfg"}),
            batch_id=old_batch,
            submitted_at=datetime(2026, 5, 10, 12, tzinfo=UTC),
        )
        _insert_forge_submission(
            conn,
            config=minimal_strategy_config().model_copy(update={"name": "new_batch_cfg"}),
            batch_id=new_batch,
            submitted_at=datetime(2026, 5, 13, 12, tzinfo=UTC),
        )
        result = consume_batch_results(conn, crucible_db, since=datetime(2026, 5, 1, tzinfo=UTC))
    assert result.batch_id == new_batch


# ---------------------------------------------------------------------------
# Join + status updates
# ---------------------------------------------------------------------------


def test_consume_joins_matching_config_hashes(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash, decision="promote")
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        result = consume_batch_results(conn, crucible_db, batch_id=batch_id)
    assert result.gated_count == 1
    assert result.promoted_count == 1
    assert result.rejected_count == 0


def test_consume_updates_submission_status_to_gated(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    run_id = _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        candidate_id = _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        consume_batch_results(conn, crucible_db, batch_id=batch_id)
        row = conn.execute(
            "SELECT status, crucible_run_id FROM submissions WHERE forge_candidate_id = ?",
            [str(candidate_id)],
        ).fetchone()
    assert row is not None
    assert row[0] == "gated"
    assert str(row[1]) == run_id


def test_consume_skips_unrelated_crucible_runs(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash="unrelated_hash_xx")
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        result = consume_batch_results(conn, crucible_db, batch_id=batch_id)
    assert result.gated_count == 0


def test_consume_updates_batch_summary_promotion_rate(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash, decision="promote")
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=2)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        consume_batch_results(conn, crucible_db, batch_id=batch_id)
        row = conn.execute(
            "SELECT promotion_rate FROM batch_summaries WHERE forge_batch_id = ?",
            [str(batch_id)],
        ).fetchone()
    assert row is not None
    # 1 promoted / 1 submitted = 1.0 (we only count actually-submitted rows)
    assert row[0] == pytest.approx(1.0)


def test_consume_sets_completed_at_when_all_gated(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        consume_batch_results(conn, crucible_db, batch_id=batch_id)
        row = conn.execute(
            "SELECT completed_at FROM batch_summaries WHERE forge_batch_id = ?",
            [str(batch_id)],
        ).fetchone()
    assert row is not None
    assert row[0] is not None


def test_consume_leaves_completed_at_null_when_pending_exists(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=3)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        _insert_forge_submission(
            conn,
            config=minimal_strategy_config().model_copy(update={"name": "decoy"}),
            batch_id=batch_id,
        )
        consume_batch_results(conn, crucible_db, batch_id=batch_id)
        row = conn.execute(
            "SELECT completed_at FROM batch_summaries WHERE forge_batch_id = ?",
            [str(batch_id)],
        ).fetchone()
    assert row is not None
    assert row[0] is None


def test_consume_common_failures_aggregates_gate_failures(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg_a = minimal_strategy_config()
    cfg_b = minimal_strategy_config().model_copy(update={"name": "second"})
    _insert_crucible_gated(
        crucible_db,
        config_hash=cfg_a.config_hash,
        decision="reject",
        failed_gate="sharpe_gate",
    )
    _insert_crucible_gated(
        crucible_db,
        config_hash=cfg_b.config_hash,
        decision="reject",
        failed_gate="sharpe_gate",
    )
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=2)
        _insert_forge_submission(conn, config=cfg_a, batch_id=batch_id)
        _insert_forge_submission(conn, config=cfg_b, batch_id=batch_id)
        consume_batch_results(conn, crucible_db, batch_id=batch_id)
        row = conn.execute(
            "SELECT common_failures FROM batch_summaries WHERE forge_batch_id = ?",
            [str(batch_id)],
        ).fetchone()
    assert row is not None
    common = json.loads(row[0])
    assert common.get("sharpe_gate") == 2


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_consume_is_idempotent(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        first = consume_batch_results(conn, crucible_db, batch_id=batch_id)
        second = consume_batch_results(conn, crucible_db, batch_id=batch_id)
    assert first.gated_count == second.gated_count
    assert first.promoted_count == second.promoted_count


def test_consume_returns_outcomes_in_stable_order(tmp_path: Path) -> None:
    """Re-consume must return outcomes in the same order. Otherwise
    downstream analyzer reports would non-deterministically vary."""
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfgs = [minimal_strategy_config().model_copy(update={"name": f"s{i}"}) for i in range(3)]
    for cfg in cfgs:
        _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=3)
        for cfg in cfgs:
            _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        first = consume_batch_results(conn, crucible_db, batch_id=batch_id)
        second = consume_batch_results(conn, crucible_db, batch_id=batch_id)
    first_hashes = [o.config_hash for o in first.outcomes]
    second_hashes = [o.config_hash for o in second.outcomes]
    assert first_hashes == second_hashes


# ---------------------------------------------------------------------------
# `since` filter
# ---------------------------------------------------------------------------


def test_consume_respects_since_cutoff(tmp_path: Path) -> None:
    """Runs decided before `since` are ignored even if config_hash matches."""
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    # Crucible decision at 2026-05-13 14:00 UTC
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        # since is AFTER the decided_at — should not match
        result = consume_batch_results(
            conn,
            crucible_db,
            batch_id=batch_id,
            since=datetime(2026, 5, 14, tzinfo=UTC),
        )
    assert result.gated_count == 0


# ---------------------------------------------------------------------------
# Naive datetime guard
# ---------------------------------------------------------------------------


def test_consume_rejects_naive_since(tmp_path: Path) -> None:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        with pytest.raises(ValueError, match="tzinfo"):
            consume_batch_results(
                conn,
                crucible_db,
                batch_id=batch_id,
                since=datetime(2026, 5, 13),  # noqa: DTZ001 — intentional naive
            )
