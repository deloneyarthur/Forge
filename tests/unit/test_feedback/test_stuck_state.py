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


# ---------------------------------------------------------------------------
# D035 — grammar-change floor (`since` parameter)
# ---------------------------------------------------------------------------


def _insert_grammar_version(
    conn: object,
    *,
    version: str,
    changed_at: datetime,
) -> None:
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO grammar_versions
            (version, rule_count, yaml_sha256, changed_at, change_type, change_description)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [version, 21, "0" * 64, changed_at, "manual", "test"],
    )


def test_d035_since_floor_excludes_pre_floor_zeros(tmp_path: Path) -> None:
    """D035 invariant: zero-promotion batches before `since` are excluded.

    Pre-D035 a streak that crossed a grammar bump kept climbing — the
    operator's structural fix didn't visibly reset the alarm. Now passing
    `since=most_recent_grammar_change` floors the count at the bump.
    """
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        # 10 zero-promotion batches before the floor.
        for i in range(10):
            _insert_batch(
                conn,
                promotion_rate=0.0,
                submitted_at=now - timedelta(hours=24, minutes=10 - i),
            )
        floor = now - timedelta(hours=12)
        # 2 zero batches AFTER the floor.
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=20))
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=10))

        # Without floor: streak = 12 (everything).
        assert consecutive_zero_promotion_batches(conn) == 12
        # With floor: streak = 2 (only post-floor batches counted).
        assert consecutive_zero_promotion_batches(conn, since=floor) == 2


def test_d035_is_stuck_resets_on_grammar_change(tmp_path: Path) -> None:
    """`is_stuck(since=most_recent_grammar_change(...))` resets at the bump.

    Concretely: 15 zero-promotion batches over the prior 6 hours, then a
    grammar bump happens, then 2 more zero-promotion batches. Without the
    floor, the operator sees stuck=True with streak=17. With the floor
    (most-recent grammar bump), they see stuck=False with streak=2 — the
    correct "warming up after a structural change" picture.
    """
    now = datetime.now(UTC)
    with db_connection(tmp_path / "forge.db") as conn:
        # Pre-bump zero streak.
        for i in range(15):
            _insert_batch(
                conn,
                promotion_rate=0.0,
                submitted_at=now - timedelta(hours=6, minutes=15 - i),
            )
        bump_at = now - timedelta(minutes=30)
        _insert_grammar_version(conn, version="v2", changed_at=bump_at)
        # Post-bump batches still zero.
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=20))
        _insert_batch(conn, promotion_rate=0.0, submitted_at=now - timedelta(minutes=10))

        from forge.feedback.stuck_state import most_recent_grammar_change

        floor = most_recent_grammar_change(conn)
        # DuckDB TIMESTAMP returns tz-naive (in the column's storage tz).
        # We only need the streak-floor behavior; we don't pin the exact
        # value here.
        assert floor is not None

        # Without floor: stuck=True.
        flag_all_time, streak_all_time = is_stuck(conn)
        assert flag_all_time is True
        assert streak_all_time == 17

        # With floor: stuck=False, streak=2.
        flag_floored, streak_floored = is_stuck(conn, since=floor)
        assert flag_floored is False
        assert streak_floored == 2


def test_d035_most_recent_grammar_change_returns_none_when_empty(tmp_path: Path) -> None:
    """No grammar_versions rows → `most_recent_grammar_change` returns None."""
    with db_connection(tmp_path / "forge.db") as conn:
        from forge.feedback.stuck_state import most_recent_grammar_change

        assert most_recent_grammar_change(conn) is None
        # And is_stuck with since=None falls back to all-time behavior.
        assert is_stuck(conn, since=None) == (False, 0)
