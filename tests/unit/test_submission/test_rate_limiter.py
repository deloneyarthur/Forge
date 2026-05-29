"""Tests for ``forge.submission.rate_limiter`` (§7.3, D023/D6.a).

`check_rate_limit` decides whether `forge run` may submit a new batch:
clear iff >=80% of the *previous* batch's candidates are gated in
Crucible. No prior batch -> clear. Crucible DB missing -> blocked (we
can't prove the prior batch finished).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from forge.persistence.db import db_connection
from forge.submission.rate_limiter import RateLimitStatus, check_rate_limit
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

# ---------------------------------------------------------------------------
# Helpers: seed a Forge submissions row + a Crucible gated row
# ---------------------------------------------------------------------------


def _insert_submission(
    forge_db_path: Path,
    *,
    forge_batch_id: uuid.UUID,
    config_hash: str,
    submitted_at: datetime,
    status: str = "submitted",
    crucible_run_id: str | None = None,
) -> None:
    """Test fixture: insert a submission row directly.

    Production submitter inserts as 'pending' then transitions to
    'submitted' after the inbox write succeeds (or to 'submission_failed').
    Tests skip the inbox-write step, so we go straight to 'submitted' —
    that's the steady state for an in-flight candidate the rate-limiter
    expects to see. `crucible_run_id` lets a test mark a 'gated' row as a
    real Crucible decision (a real UUID) vs a D052 sentinel flush (nil UUID).
    """
    with db_connection(forge_db_path) as conn:
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status, crucible_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                str(forge_batch_id),
                config_hash,
                "{}",
                submitted_at,
                status,
                crucible_run_id,
            ],
        )


def _insert_crucible_gated(
    crucible_db_path: Path,
    *,
    config_hash: str,
    decision: str = "promote",
) -> None:
    """Insert one runs + promotion_decisions row pair."""
    conn = build_synthetic_crucible_db(crucible_db_path)
    try:
        run_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO runs (run_id, config_hash, source, status, "
            "period_start, period_end, started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                config_hash,
                "forge",
                "gated",
                date(2026, 1, 1),
                date(2026, 5, 1),
                datetime(2026, 5, 1, 9, tzinfo=UTC),
                datetime(2026, 5, 1, 18, tzinfo=UTC),
            ],
        )
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [
                run_id,
                decision,
                json.dumps({}),
                datetime(2026, 5, 1, 19, tzinfo=UTC),
                "tester",
            ],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Empty Forge DB
# ---------------------------------------------------------------------------


def test_returns_clear_when_no_prior_batch(tmp_path: Path) -> None:
    """No submissions yet → first-run is always clear."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    with db_connection(forge_db):
        pass  # schema-ensure only
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is True
    assert status.blocking_batch_id is None
    assert status.submitted_count == 0


# ---------------------------------------------------------------------------
# Crucible DB missing
# ---------------------------------------------------------------------------


def test_returns_blocked_when_crucible_db_missing_and_prior_batch_exists(
    tmp_path: Path,
) -> None:
    """We can't prove the prior batch is gated without Crucible's DB.
    Conservative: stay blocked."""
    forge_db = tmp_path / "forge.db"
    batch = uuid.uuid4()
    _insert_submission(
        forge_db,
        forge_batch_id=batch,
        config_hash="hash1",
        submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
    )
    missing_crucible = tmp_path / "does_not_exist.duckdb"
    status = check_rate_limit(forge_db, missing_crucible, exports_dir=tmp_path / "noexports")
    assert status.clear is False
    assert status.blocking_batch_id == batch
    assert status.gated_count == 0
    assert status.submitted_count == 1


# ---------------------------------------------------------------------------
# 0% gated
# ---------------------------------------------------------------------------


def test_blocked_when_zero_percent_gated(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    for i in range(5):
        _insert_submission(
            forge_db,
            forge_batch_id=batch,
            config_hash=f"hash_{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is False
    assert status.pct_gated == pytest.approx(0.0)
    assert status.gated_count == 0
    assert status.submitted_count == 5


# ---------------------------------------------------------------------------
# 80% gated -> clear; 79% -> blocked
# ---------------------------------------------------------------------------


def test_clear_at_threshold_exactly(tmp_path: Path) -> None:
    """4 of 5 gated == 80% -- clear at the threshold."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    for i in range(5):
        _insert_submission(
            forge_db,
            forge_batch_id=batch,
            config_hash=f"hash_{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
    for i in range(4):
        _insert_crucible_gated(crucible_db, config_hash=f"hash_{i}")
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is True
    assert status.pct_gated == pytest.approx(0.8)
    assert status.gated_count == 4


def test_blocked_just_below_threshold(tmp_path: Path) -> None:
    """1 of 5 gated == 20% -- below 50% threshold.

    D036 dropped `_DEFAULT_THRESHOLD` from 0.80 → 0.50 while waiting on
    the Tier 2 batch to ship. Test now exercises the "below threshold"
    branch against the new default.
    """
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    for i in range(5):
        _insert_submission(
            forge_db,
            forge_batch_id=batch,
            config_hash=f"hash_{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
    # 1 of 5 = 20%; below the 0.50 default → blocked.
    _insert_crucible_gated(crucible_db, config_hash="hash_0")
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is False
    assert status.pct_gated == pytest.approx(0.2)
    assert status.gated_count == 1


def test_clear_at_full_completion(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    for i in range(3):
        _insert_submission(
            forge_db,
            forge_batch_id=batch,
            config_hash=f"hash_{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
        _insert_crucible_gated(crucible_db, config_hash=f"hash_{i}")
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is True
    assert status.pct_gated == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Threshold parameter
# ---------------------------------------------------------------------------


def test_custom_threshold_is_respected(tmp_path: Path) -> None:
    """50% of submissions gated; threshold=0.5 -> clear; threshold=0.8 -> blocked."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    for i in range(4):
        _insert_submission(
            forge_db,
            forge_batch_id=batch,
            config_hash=f"h{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
    for i in range(2):
        _insert_crucible_gated(crucible_db, config_hash=f"h{i}")
    blocked = check_rate_limit(
        forge_db, crucible_db, threshold=0.8, exports_dir=tmp_path / "noexports"
    )
    cleared = check_rate_limit(
        forge_db, crucible_db, threshold=0.5, exports_dir=tmp_path / "noexports"
    )
    assert blocked.clear is False
    assert cleared.clear is True


# ---------------------------------------------------------------------------
# Multi-batch — D046 oldest-unfinished-batch semantics
# ---------------------------------------------------------------------------


def test_uses_oldest_unfinished_batch(tmp_path: Path) -> None:
    """D046: with multiple batches stranded in `status='submitted'`, the
    rate limiter blocks on the OLDEST one — not the latest.

    The latest-batch heuristic was the pre-D046 behavior; once Crucible
    processing exceeded one Forge poll cycle it silently deadlocked the
    loop because the newest batch (at the back of Crucible's queue) was
    always 0% gated while older batches accumulated unread results.
    """
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    old_batch = uuid.uuid4()
    new_batch = uuid.uuid4()
    for i in range(2):
        _insert_submission(
            forge_db,
            forge_batch_id=old_batch,
            config_hash=f"old_{i}",
            submitted_at=datetime(2026, 5, 10, tzinfo=UTC),
        )
    for i in range(2):
        _insert_submission(
            forge_db,
            forge_batch_id=new_batch,
            config_hash=f"new_{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is False
    assert status.blocking_batch_id == old_batch


def test_oldest_batch_with_local_gated_rows_clears_to_next(tmp_path: Path) -> None:
    """D046: once the oldest batch's rows have all reconciled to `status='gated'`
    locally, it's no longer the blocker — the next-oldest with `submitted` rows
    takes over."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    old_batch = uuid.uuid4()
    new_batch = uuid.uuid4()
    for i in range(2):
        _insert_submission(
            forge_db,
            forge_batch_id=old_batch,
            config_hash=f"old_{i}",
            submitted_at=datetime(2026, 5, 10, tzinfo=UTC),
            status="gated",
        )
    for i in range(2):
        _insert_submission(
            forge_db,
            forge_batch_id=new_batch,
            config_hash=f"new_{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is False
    assert status.blocking_batch_id == new_batch
    assert status.gated_count == 0
    assert status.submitted_count == 2


def test_no_submitted_rows_clears_completely(tmp_path: Path) -> None:
    """D046: when every row is already `gated` locally there's nothing in
    flight; rate limit is trivially clear."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    for i in range(3):
        _insert_submission(
            forge_db,
            forge_batch_id=batch,
            config_hash=f"h{i}",
            submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
            status="gated",
        )
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert status.clear is True
    assert status.blocking_batch_id is None
    assert status.submitted_count == 0


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_returns_rate_limit_status(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    with db_connection(forge_db):
        pass
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    assert isinstance(status, RateLimitStatus)


def test_status_is_frozen(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    with db_connection(forge_db):
        pass
    status = check_rate_limit(forge_db, crucible_db, exports_dir=tmp_path / "noexports")
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        status.clear = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# H-1 (audit 2026-05-29) — D052 sentinel-flushed rows must NOT satisfy §7.3
# ---------------------------------------------------------------------------

_SENTINEL = "00000000-0000-0000-0000-000000000000"


def test_sentinel_flushed_gated_rows_do_not_count_toward_pct(tmp_path: Path) -> None:
    """A row aged-out by D052 (`status='gated'`, nil-UUID `crucible_run_id`) is
    NOT a real Crucible decision. §7.3 throttles on real completion, so the
    rate limiter must exclude sentinels from `pct_gated` — otherwise the
    sentinel flush silently opens the throttle (the live 91.6%-sentinel state)."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    batch = uuid.uuid4()
    at = datetime(2026, 5, 13, tzinfo=UTC)
    # 1 still in flight, 1 genuinely gated (real run_id), 3 sentinel-flushed.
    _insert_submission(forge_db, forge_batch_id=batch, config_hash="sub_0", submitted_at=at)
    _insert_submission(
        forge_db, forge_batch_id=batch, config_hash="real_0", submitted_at=at,
        status="gated", crucible_run_id=str(uuid.uuid4()),
    )
    for i in range(3):
        _insert_submission(
            forge_db, forge_batch_id=batch, config_hash=f"sent_{i}", submitted_at=at,
            status="gated", crucible_run_id=_SENTINEL,
        )
    status = check_rate_limit(
        forge_db, crucible_db, threshold=0.8, exports_dir=tmp_path / "noexports"
    )
    # 5 rows; only the 1 real gate counts (NOT 4) -> pct 0.2 -> blocked.
    assert status.gated_count == 1
    assert status.pct_gated == pytest.approx(0.2)
    assert status.clear is False


def test_rate_limiter_sentinel_constant_matches_consumer() -> None:
    """Drift guard: the rate limiter's sentinel must equal the one the
    consumer writes (D052), or the exclusion silently stops working."""
    from forge.feedback.consumer import _AGED_OUT_SENTINEL_RUN_ID
    from forge.submission.rate_limiter import _SENTINEL_RUN_ID

    assert _SENTINEL_RUN_ID == _AGED_OUT_SENTINEL_RUN_ID
