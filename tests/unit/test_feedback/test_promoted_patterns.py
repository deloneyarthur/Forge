"""Tests for feedback.promoted_patterns (Phase 5 module 4).

`record_promoted_patterns(db, patterns, *, discovered_at)` inserts each
PromotedPattern as one row in the `promoted_patterns` table (§9.1). Each
call generates fresh pattern_ids — re-running over the same patterns is
NOT a no-op (each call is a fresh discovery).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from forge.feedback.promoted_patterns import record_promoted_patterns
from forge.feedback.types import PromotedPattern
from forge.persistence.db import db_connection


def _pattern(
    *, pattern_type: str = "hypothesis_dominance", promoted: int = 8, sample: int = 10
) -> PromotedPattern:
    return PromotedPattern(
        pattern_type=pattern_type,  # type: ignore[arg-type]
        pattern={"hypothesis": "mean_reversion"},
        promoted_count=promoted,
        sample_size=sample,
    )


# ---------------------------------------------------------------------------
# Single-pattern insert
# ---------------------------------------------------------------------------


def test_record_inserts_one_row_per_pattern(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    p1 = _pattern()
    p2 = _pattern(pattern_type="signal_family_dominance")
    with db_connection(forge_db) as conn:
        ids = record_promoted_patterns(
            conn,
            (p1, p2),
            discovered_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
        rows = conn.execute("SELECT COUNT(*) FROM promoted_patterns").fetchone()
    assert len(ids) == 2
    assert rows is not None
    assert int(rows[0]) == 2


def test_record_writes_pattern_json_roundtrips(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    p = _pattern()
    with db_connection(forge_db) as conn:
        record_promoted_patterns(conn, (p,), discovered_at=datetime(2026, 5, 13, tzinfo=UTC))
        row = conn.execute("SELECT pattern_json FROM promoted_patterns").fetchone()
    assert row is not None
    parsed = json.loads(row[0])
    assert parsed["hypothesis"] == "mean_reversion"


def test_record_writes_pattern_type_promoted_count_sample_size(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    p = _pattern(pattern_type="signal_family_dominance", promoted=5, sample=7)
    with db_connection(forge_db) as conn:
        record_promoted_patterns(conn, (p,), discovered_at=datetime(2026, 5, 13, tzinfo=UTC))
        row = conn.execute(
            "SELECT pattern_type, promoted_count, sample_size FROM promoted_patterns"
        ).fetchone()
    assert row is not None
    assert row[0] == "signal_family_dominance"
    assert row[1] == 5
    assert row[2] == 7


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_record_empty_iterable_is_a_no_op(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        ids = record_promoted_patterns(conn, (), discovered_at=datetime(2026, 5, 13, tzinfo=UTC))
        rows = conn.execute("SELECT COUNT(*) FROM promoted_patterns").fetchone()
    assert ids == []
    assert rows is not None
    assert int(rows[0]) == 0


# ---------------------------------------------------------------------------
# Each call generates fresh UUIDs (not idempotent across calls)
# ---------------------------------------------------------------------------


def test_record_twice_writes_two_rows_per_pattern(tmp_path: Path) -> None:
    """Each invocation is a fresh "discovery" — pattern_ids are uuid4 so
    the same pattern can recur over time."""
    forge_db = tmp_path / "forge.db"
    p = _pattern()
    with db_connection(forge_db) as conn:
        ids_a = record_promoted_patterns(
            conn, (p,), discovered_at=datetime(2026, 5, 13, tzinfo=UTC)
        )
        ids_b = record_promoted_patterns(
            conn, (p,), discovered_at=datetime(2026, 5, 14, tzinfo=UTC)
        )
        rows = conn.execute("SELECT COUNT(*) FROM promoted_patterns").fetchone()
    assert ids_a != ids_b
    assert rows is not None
    assert int(rows[0]) == 2


# ---------------------------------------------------------------------------
# Naive datetime guard
# ---------------------------------------------------------------------------


def test_record_rejects_naive_discovered_at(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    p = _pattern()
    with db_connection(forge_db) as conn, pytest.raises(ValueError, match="timezone-aware"):
        record_promoted_patterns(
            conn,
            (p,),
            discovered_at=datetime(2026, 5, 13),  # noqa: DTZ001 — intentional naive
        )
