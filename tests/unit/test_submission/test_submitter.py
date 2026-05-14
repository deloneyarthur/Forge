"""Tests for ``forge.submission.submitter`` (§7, D023/D7).

End-to-end submit-batch: write each candidate's config to the Crucible
inbox via `crucible_contracts.submit_candidate`, insert a `submissions`
row keyed on config_hash (idempotency via §13.4 unique-index), record
pre-filter logs, write a `batch_summaries` row.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import pytest
from crucible_contracts import SignalSpec, StrategyConfig

from forge.persistence.db import db_connection
from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.types import RankedCandidate
from forge.submission.batch import BatchContext, mint_batch_id
from forge.submission.submitter import (
    BatchSubmissionResult,
    SubmissionRecord,
    submit_batch,
)
from tests.fixtures.strategy_configs import minimal_strategy_config


def _ctx(*, seed: int = 0, submitted_at: datetime | None = None) -> BatchContext:
    bid = mint_batch_id(seed=seed, grammar_version="v1", registry_hash="abc")
    return BatchContext(
        batch_id=bid,
        grammar_version="v1",
        registry_hash="abc",
        submitted_at=submitted_at or datetime(2026, 5, 13, 12, tzinfo=UTC),
        seed=seed,
    )


def _named_config(name: str, directional_id: str) -> StrategyConfig:
    return minimal_strategy_config().model_copy(
        update={
            "name": name,
            "signals": (
                SignalSpec(
                    id=directional_id,
                    type="threshold",
                    role="directional",
                    indicators=("rsi_2",),
                    params={"threshold": 30.0},
                ),
                SignalSpec(
                    id=f"iv_rg_{name}",
                    type="threshold",
                    role="regime_filter",
                    indicators=("iv_rank",),
                    params={"threshold": 50.0},
                ),
            ),
        },
    )


def _candidate(name: str, directional_id: str, composite: float = 0.7) -> RankedCandidate:
    cfg = _named_config(name, directional_id)
    rep = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "resource_feasibility": FilterResult(passed=True, score=0.95),
                "signal_density": FilterResult(passed=True, score=0.80),
                "expected_trades": FilterResult(passed=True, score=0.70),
                "novelty": FilterResult(passed=True, score=0.90),
                "regime_exposure": FilterResult(passed=True, score=0.60),
                "permutation_test": FilterResult(passed=True, score=0.85),
            }
        ),
        diagnostic_notes=(),
    )
    return RankedCandidate(
        report=rep,
        prior_promotion_score=0.0,
        composite_score=composite,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_empty_candidates_returns_zero_counts(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    with db_connection(forge_db) as conn:
        result = submit_batch(conn, batch=_ctx(), candidates=(), inbox_root=inbox)
    assert isinstance(result, BatchSubmissionResult)
    assert result.submitted_count == 0
    assert result.skipped_duplicate_count == 0
    assert result.failed_count == 0
    assert result.records == ()


def test_writes_one_inbox_file_per_candidate(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    batch = _ctx(seed=1)
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"))
    with db_connection(forge_db) as conn:
        result = submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
    assert result.submitted_count == 2
    files = sorted(inbox.glob("*.json"))
    assert len(files) == 2
    for f in files:
        payload = json.loads(f.read_text())
        # `config_hash` is a derived property, not a serialized field —
        # the inbox file holds the full config and Crucible re-derives.
        assert "name" in payload
        assert "hypothesis" in payload
        assert "signals" in payload


def test_records_one_submissions_row_per_candidate(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"))
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)
        rows = conn.execute(
            "SELECT config_hash, status FROM submissions ORDER BY config_hash"
        ).fetchall()
    assert len(rows) == 2
    for _, status in rows:
        assert status == "submitted"


def test_writes_pre_filter_logs(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"),)
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)
        result = conn.execute("SELECT COUNT(*) FROM pre_filter_logs").fetchone()
        assert result is not None
        count = int(result[0])
    # 7 filter results in the candidate's report.
    assert count == 7


def test_writes_batch_summaries_row(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    batch = _ctx()
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"))
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
        rows = conn.execute(
            "SELECT forge_batch_id, batch_size, grammar_version, registry_version "
            "FROM batch_summaries"
        ).fetchall()
    assert len(rows) == 1
    bid, batch_size, gv, rv = rows[0]
    assert str(bid) == str(batch.batch_id)
    assert int(batch_size) == 2
    assert gv == "v1"
    assert rv == "abc"


def test_records_carry_outcome_and_inbox_path(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"),)
    with db_connection(forge_db) as conn:
        result = submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)
    assert len(result.records) == 1
    record = result.records[0]
    assert isinstance(record, SubmissionRecord)
    assert record.status == "submitted"
    assert record.inbox_path is not None
    assert record.inbox_path.endswith(".json")
    assert record.error is None


# ---------------------------------------------------------------------------
# Idempotency: duplicate config_hash is skipped (D023/D7 step 5)
# ---------------------------------------------------------------------------


def test_duplicate_hash_skipped_not_fatal(tmp_path: Path) -> None:
    """Re-submitting the same config_hash should skip, not raise."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cand = _candidate("a", "dir_a")
    with db_connection(forge_db) as conn:
        r1 = submit_batch(conn, batch=_ctx(seed=1), candidates=(cand,), inbox_root=inbox)
        r2 = submit_batch(conn, batch=_ctx(seed=2), candidates=(cand,), inbox_root=inbox)
    assert r1.submitted_count == 1
    assert r2.submitted_count == 0
    assert r2.skipped_duplicate_count == 1
    assert r2.records[0].status == "skipped_duplicate"


def test_re_running_same_batch_is_idempotent(tmp_path: Path) -> None:
    """Running submit_batch twice with the same (batch, candidates)
    produces no new submissions and no new inbox files (file is
    overwritten with same content)."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"))
    with db_connection(forge_db) as conn:
        first = submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)
        second = submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)
        rows_result = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
        assert rows_result is not None
        row_count = int(rows_result[0])
    assert first.submitted_count == 2
    assert second.submitted_count == 0
    assert second.skipped_duplicate_count == 2
    assert row_count == 2


# ---------------------------------------------------------------------------
# BatchSubmissionResult shape
# ---------------------------------------------------------------------------


def test_batch_submission_result_is_frozen(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    with db_connection(forge_db) as conn:
        result = submit_batch(conn, batch=_ctx(), candidates=(), inbox_root=inbox)
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        result.submitted_count = 99  # type: ignore[misc]


def test_submission_record_is_frozen(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"),)
    with db_connection(forge_db) as conn:
        result = submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)
    record = result.records[0]
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        record.status = "skipped_duplicate"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# batch_id reuse: subsequent calls with same batch_id append to batch_summaries
# ---------------------------------------------------------------------------


def test_repeat_call_with_same_batch_id_does_not_duplicate_batch_summary(
    tmp_path: Path,
) -> None:
    """`batch_summaries.forge_batch_id` is PRIMARY KEY; second call
    with the same batch_id mustn't blow up."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    batch = _ctx()
    cands = (_candidate("a", "dir_a"),)
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
        # Same batch_id, different candidates -> shouldn't insert another
        # batch_summaries row (idempotent re-run protection).
        submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
        result = conn.execute("SELECT COUNT(*) FROM batch_summaries").fetchone()
        assert result is not None
        count = int(result[0])
    assert count == 1


# ---------------------------------------------------------------------------
# Inbox layout (D026 — flat, matching crucible_contracts.INBOX_LAYOUT)
# ---------------------------------------------------------------------------


def test_inbox_files_land_flat_at_inbox_root(tmp_path: Path) -> None:
    """`{inbox_root}/{config_hash}.json` — flat, per `INBOX_LAYOUT`.

    Crucible's contract-compliant inbox watcher only scans top-level
    `.json` files (skips subdirectories); per-batch grouping must live
    in Forge's `submissions.forge_batch_id` column, not the filesystem.
    """
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    batch = _ctx(seed=5)
    cands = (_candidate("a", "dir_a"),)
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
    files = list(inbox.glob("*.json"))
    assert len(files) == 1
    # No per-batch subdirectory should exist.
    subdirs = [p for p in inbox.iterdir() if p.is_dir()]
    assert subdirs == []
