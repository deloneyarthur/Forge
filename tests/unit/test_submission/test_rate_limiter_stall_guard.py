"""§7.3 stall-guard predicate tests (Q38 / D137).

The stall guard is a SECOND, independent reason `check_rate_limit` may block:
Crucible has had new work in hand for >= T and decided nothing in that time.
It catches the blind spot the completion-fraction signal misses — the
2026-06-10 wedge, where the oldest in-flight batch read 99.5% gated (so the
§7.3 pct check said "clear") while ~13,000 newer configs piled into a gate
that had stopped deciding (export still fresh-by-mtime).

Predicate (design §4):
    stall_blocked ⇔ export readable
                  ∧ ∃ submissions row: status='submitted'
                                     ∧ submitted_at > max(decided_at)
                                     ∧ submitted_at <= utc_now() - T

Time is pinned by monkeypatching the module's blessed `utc_now`; Crucible's
decision clock (`max(decided_at)`) is controlled via synthetic gated rows.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from forge.persistence.db import db_connection
from forge.submission import rate_limiter
from forge.submission.rate_limiter import check_rate_limit
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

# Fixed "now" for every test; gaps are expressed relative to it.
_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_T_SECONDS = 10800  # 3 h — the approved default (design §5)


def _ago(**kw: float) -> datetime:
    return _NOW - timedelta(**kw)


@pytest.fixture(autouse=True)
def _freeze_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the module clock so the stall window is deterministic."""
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)


def _insert_submission(
    forge_db_path: Path,
    *,
    forge_batch_id: uuid.UUID,
    config_hash: str,
    submitted_at: datetime,
    status: str = "submitted",
    crucible_run_id: str | None = None,
) -> None:
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


def _insert_crucible_gated_at(
    crucible_db_path: Path, *, config_hash: str, decided_at: datetime
) -> None:
    """A Crucible decision at a controllable `decided_at` (the decision clock).

    The synthetic crucible DB is not UTC-session-pinned the way Forge's
    `db_connection` is, so an aware datetime would round-trip through
    `get_recent_gated_runs` with a local-offset skew. Store naive-UTC: the
    read path relabels naive as UTC, making the round-trip identity (the
    production export path already serves tz-aware UTC, so this only matters
    for the DB-fallback fixtures).
    """
    naive = decided_at.astimezone(UTC).replace(tzinfo=None)
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
                datetime(2026, 1, 1, tzinfo=UTC).date(),
                datetime(2026, 5, 1, tzinfo=UTC).date(),
                naive - timedelta(hours=1),
                naive,
            ],
        )
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [run_id, "reject", json.dumps({}), naive, "tester"],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Predicate truth table (design §7 plan item 1)
# ---------------------------------------------------------------------------


def test_stale_clock_with_pending_after_clock_blocks(tmp_path: Path) -> None:
    """Clock 10 h stale; a submitted row postdates it and is >= T old → stall."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    # Decision clock: last decision 10 h ago.
    _insert_crucible_gated_at(crucible_db, config_hash="decided_0", decided_at=_ago(hours=10))
    # A config submitted 5 h ago (after the clock, and >= 3 h old) → witness.
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=_ago(hours=5),
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is True
    assert status.clear is False
    assert status.stall_pending_count == 1
    assert status.last_decided_at is not None
    assert status.last_decided_at.replace(tzinfo=UTC) == _ago(hours=10)


def test_stale_clock_but_no_submission_after_clock_is_silent(tmp_path: Path) -> None:
    """Deadlock-immunity: the clock is stale only because FORGE was quiet
    (every submission predates the last decision) → guard must NOT fire, or it
    would block us for being idle while we're the thing that has to feed them."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    _insert_crucible_gated_at(crucible_db, config_hash="decided_0", decided_at=_ago(hours=10))
    # Submitted BEFORE the last decision → not a witness.
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=_ago(hours=12),
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is False
    assert status.stall_pending_count == 0
    assert status.last_decided_at is not None  # clock observed, just not stale-with-work


def test_fresh_decisions_clear_the_stall(tmp_path: Path) -> None:
    """A recent decision advances the clock past every submission → no witness."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    _insert_crucible_gated_at(crucible_db, config_hash="decided_0", decided_at=_ago(minutes=1))
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=_ago(hours=5),
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is False


def test_pending_younger_than_T_does_not_block(tmp_path: Path) -> None:
    """Work postdates the clock but is only 1 h old (< T=3 h) → not yet a stall."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    _insert_crucible_gated_at(crucible_db, config_hash="decided_0", decided_at=_ago(hours=10))
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=_ago(hours=1),
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is False
    assert status.stall_pending_count == 0


def test_guard_disabled_never_blocks_even_in_a_stall(tmp_path: Path) -> None:
    """stall_after_seconds=0 → the predicate is skipped entirely (guard-off)."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    _insert_crucible_gated_at(crucible_db, config_hash="decided_0", decided_at=_ago(hours=10))
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=_ago(hours=5),
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=0, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is False
    assert status.last_decided_at is None
    assert status.stall_pending_count == 0


def test_no_export_is_conservative_not_a_stall(tmp_path: Path) -> None:
    """No readable decisions at all → the guard cannot assert a stall; the
    existing pct path (export_overlap=0) stays in charge."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()  # no gated rows
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=_ago(hours=5),
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is False
    assert status.last_decided_at is None


def test_stall_overrides_a_clearing_completion_pct(tmp_path: Path) -> None:
    """The wedge: the oldest in-flight batch is 80% gated (pct says CLEAR), but
    a newer config postdates a stale clock → the stall guard forces a block.
    This is the exact case the completion-fraction signal misses."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    old_batch = uuid.uuid4()
    new_batch = uuid.uuid4()
    # Old batch: 4 of 5 locally reconciled to 'gated' with REAL run ids → pct 0.8.
    for i in range(4):
        _insert_submission(
            forge_db,
            forge_batch_id=old_batch,
            config_hash=f"old_{i}",
            submitted_at=_ago(hours=20),
            status="gated",
            crucible_run_id=str(uuid.uuid4()),
        )
        _insert_crucible_gated_at(crucible_db, config_hash=f"old_{i}", decided_at=_ago(hours=10))
    _insert_submission(
        forge_db,
        forge_batch_id=old_batch,
        config_hash="old_4",
        submitted_at=_ago(hours=20),
    )
    # New batch piled in AFTER the clock stalled, >= T old → witness.
    _insert_submission(
        forge_db,
        forge_batch_id=new_batch,
        config_hash="new_0",
        submitted_at=_ago(hours=5),
    )
    status = check_rate_limit(
        forge_db,
        crucible_db,
        threshold=0.8,
        stall_after_seconds=_T_SECONDS,
        exports_dir=tmp_path / "noexports",
    )
    # The oldest *submitted* batch is `old_batch` (old_4 still in flight); its
    # pct is 4/5 = 0.8 → would clear. The stall guard overrides.
    assert status.pct_gated == pytest.approx(0.8)
    assert status.stall_blocked is True
    assert status.clear is False
    assert status.blocking_batch_id is not None


# ---------------------------------------------------------------------------
# §5 historical replay — the 2/2-true, 0/2-false backtest (design plan item 4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "gap_hours", "had_work_after_clock", "expect_block"),
    [
        ("2026-05-30 H-1 wedge", 17.12, True, True),
        ("2026-06-04 healthy-slow CPCV", 2.02, True, False),
        ("2026-06-07 Forge-quiet migration", 3.38, False, False),
        ("2026-06-11 Q38 wedge", 18.08, True, True),
    ],
)
def test_historical_episode_replay(
    tmp_path: Path,
    label: str,
    gap_hours: float,
    had_work_after_clock: bool,
    expect_block: bool,
) -> None:
    """Replay each >2 h inter-decision gap on record at T=3 h. Stalls fire;
    the healthy-slow gap and the Forge-quiet gap stay silent."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    _insert_crucible_gated_at(
        crucible_db, config_hash="decided_0", decided_at=_ago(hours=gap_hours)
    )
    # A config submitted either just after the clock (work pending) or before it
    # (Forge-quiet — the migration window had 0 submissions during the gap).
    submitted_at = (
        _ago(hours=gap_hours - 0.5) if had_work_after_clock else _ago(hours=gap_hours + 1)
    )
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="pending_0",
        submitted_at=submitted_at,
    )
    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=tmp_path / "noexports"
    )
    assert status.stall_blocked is expect_block, label
