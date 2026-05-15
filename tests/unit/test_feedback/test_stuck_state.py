"""Tests for the stuck-state detector (long-term #3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from forge.feedback.stuck_state import (
    DEFAULT_STUCK_THRESHOLD,
    consecutive_zero_promotion_batches,
    is_stuck,
)
from forge.persistence.db import db_connection


def _insert_batch(
    conn: object,
    *,
    promotion_rate: float | None,
    submitted_at: datetime,
) -> None:
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO batch_summaries
            (forge_batch_id, batch_size, submitted_at,
             promotion_rate, grammar_version, registry_version)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid.uuid4()),
            200,
            submitted_at,
            promotion_rate,
            "v1",
            "v1",
        ],
    )


def test_no_batches_means_zero_streak(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        assert consecutive_zero_promotion_batches(conn) == 0
        flag, streak = is_stuck(conn)
        assert (flag, streak) == (False, 0)


def test_recent_nonzero_batch_breaks_streak(tmp_path: Path) -> None:
    """A non-zero promotion-rate batch newer than zeros sets streak to 0."""
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=30))
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=20))
        _insert_batch(conn, promotion_rate=0.05, submitted_at=now - timedelta(minutes=10))
        assert consecutive_zero_promotion_batches(conn) == 0


def test_run_of_zeros_increments_streak(tmp_path: Path) -> None:
    """5 consecutive zero-promotion batches → streak=5."""
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        for i in range(5):
            _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=10 - i))
        assert consecutive_zero_promotion_batches(conn) == 5


def test_null_promotion_rate_batches_excluded(tmp_path: Path) -> None:
    """Batches with NULL promotion_rate (feedback not yet consumed) are
    skipped — they neither break nor extend the streak.
    """
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=20))
        _insert_batch(conn, promotion_rate=None, submitted_at=now - timedelta(minutes=15))
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=10))
        assert consecutive_zero_promotion_batches(conn) == 2


def test_is_stuck_true_at_threshold(tmp_path: Path) -> None:
    """is_stuck returns True exactly when streak >= threshold."""
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        for i in range(DEFAULT_STUCK_THRESHOLD):
            _insert_batch(
                conn,
                promotion_rate=0.0,
                submitted_at=now - timedelta(minutes=DEFAULT_STUCK_THRESHOLD - i),
            )
        flag, streak = is_stuck(conn)
        assert flag is True
        assert streak == DEFAULT_STUCK_THRESHOLD


def test_is_stuck_false_below_threshold(tmp_path: Path) -> None:
    """One short of threshold → not stuck."""
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        for i in range(DEFAULT_STUCK_THRESHOLD - 1):
            _insert_batch(
                conn,
                promotion_rate=0.0,
                submitted_at=now - timedelta(minutes=DEFAULT_STUCK_THRESHOLD - i),
            )
        flag, streak = is_stuck(conn)
        assert flag is False
        assert streak == DEFAULT_STUCK_THRESHOLD - 1


def test_is_stuck_custom_threshold(tmp_path: Path) -> None:
    """Custom threshold overrides default."""
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        for i in range(3):
            _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=3 - i))
        flag, streak = is_stuck(conn, threshold=3)
        assert (flag, streak) == (True, 3)
        flag, _ = is_stuck(conn, threshold=4)
        assert flag is False
