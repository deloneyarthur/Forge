"""Tests for ``forge.submission.pre_filter_logger`` (D023/D8, §9.1).

Writes one row per (candidate, filter) to the `pre_filter_logs` table.
Phase 4 wires what Phase 3 (D021/D8) deferred — chicken-and-egg: the
table needs a `forge_candidate_id` which only exists once the
submitter mints one.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import duckdb
import pytest

from forge.persistence.db import db_connection
from forge.prefilters.types import FilterResult, PreFilterReport
from forge.submission.pre_filter_logger import record_pre_filter_logs
from tests.fixtures.strategy_configs import minimal_strategy_config


def _report(*, n_filters: int = 7) -> PreFilterReport:
    names = (
        "structural_redundancy",
        "resource_feasibility",
        "signal_density",
        "expected_trades",
        "novelty",
        "regime_exposure",
        "permutation_test",
    )
    filters: dict[str, FilterResult] = {}
    for i in range(n_filters):
        filters[names[i]] = FilterResult(
            passed=True,
            score=0.5 + i * 0.05,
            details=MappingProxyType({"diag": f"info_{i}"}),
        )
    return PreFilterReport(
        config=minimal_strategy_config(),
        passed=True,
        filter_results=MappingProxyType(filters),
        diagnostic_notes=(),
    )


def _row_count(forge_db_path: Path) -> int:
    with db_connection(forge_db_path) as conn:
        result = conn.execute("SELECT COUNT(*) FROM pre_filter_logs").fetchone()
        assert result is not None
        return int(result[0])


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_writes_one_row_per_filter(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    report = _report(n_filters=7)
    ts = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        written = record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=report,
            evaluated_at=ts,
        )
    assert written == 7
    assert _row_count(forge_db) == 7


def test_rows_preserve_filter_name_passed_score(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    report = _report(n_filters=3)
    ts = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=report,
            evaluated_at=ts,
        )
        rows = conn.execute(
            "SELECT filter_name, passed, score "
            "FROM pre_filter_logs WHERE forge_candidate_id = ? "
            "ORDER BY filter_name",
            [str(candidate_id)],
        ).fetchall()
    names = {r[0] for r in rows}
    assert names == {"resource_feasibility", "signal_density", "structural_redundancy"}
    for _, passed, score in rows:
        assert passed is True
        assert 0.0 <= float(score) <= 1.0


def test_details_round_trip_as_json(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    report = _report(n_filters=1)
    ts = datetime(2026, 5, 13, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=report,
            evaluated_at=ts,
        )
        rows = conn.execute(
            "SELECT details_json FROM pre_filter_logs WHERE forge_candidate_id = ?",
            [str(candidate_id)],
        ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0]) if isinstance(rows[0][0], str) else rows[0][0]
    assert payload == {"diag": "info_0"}


def test_evaluated_at_is_recorded(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    report = _report(n_filters=1)
    ts = datetime(2026, 5, 13, 14, 30, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=report,
            evaluated_at=ts,
        )
        rows = conn.execute(
            "SELECT evaluated_at FROM pre_filter_logs WHERE forge_candidate_id = ?",
            [str(candidate_id)],
        ).fetchall()
    assert len(rows) == 1
    # DuckDB TIMESTAMP is tz-naive — the value round-trips as a local-time
    # representation of the inserted instant. The exact wall-clock hour
    # depends on the test process's local TZ, so the assertion just
    # confirms the date round-tripped intact (something better than `null`
    # was recorded).
    written = rows[0][0]
    assert written is not None
    assert written.year == 2026
    assert written.month == 5


# ---------------------------------------------------------------------------
# Multi-candidate accumulation
# ---------------------------------------------------------------------------


def test_multiple_candidates_accumulate(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    ts = datetime(2026, 5, 13, tzinfo=UTC)
    a, b = uuid.uuid4(), uuid.uuid4()
    with db_connection(forge_db) as conn:
        record_pre_filter_logs(conn, candidate_id=a, report=_report(n_filters=3), evaluated_at=ts)
        record_pre_filter_logs(conn, candidate_id=b, report=_report(n_filters=3), evaluated_at=ts)
    assert _row_count(forge_db) == 6


# ---------------------------------------------------------------------------
# Primary-key — (candidate_id, filter_name) unique
# ---------------------------------------------------------------------------


def test_duplicate_candidate_filter_raises(tmp_path: Path) -> None:
    """The §9.1 PRIMARY KEY (forge_candidate_id, filter_name) prevents
    writing the same row twice — an honest signal that something
    upstream re-ran a candidate without minting a fresh UUID."""
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    report = _report(n_filters=2)
    ts = datetime(2026, 5, 13, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=report,
            evaluated_at=ts,
        )
        with pytest.raises(duckdb.ConstraintException):
            record_pre_filter_logs(
                conn,
                candidate_id=candidate_id,
                report=report,
                evaluated_at=ts,
            )


# ---------------------------------------------------------------------------
# Short-circuited report (passed=False) is still loggable
# ---------------------------------------------------------------------------


def test_failed_report_writes_partial_filter_results(tmp_path: Path) -> None:
    """A short-circuited report has fewer filter_results entries. The
    writer should faithfully record only what's there."""
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    # Pretend only the first three filters ran; third failed.
    failed_report = PreFilterReport(
        config=minimal_strategy_config(),
        passed=False,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "resource_feasibility": FilterResult(passed=True, score=0.95),
                "signal_density": FilterResult(passed=False, score=0.10),
            }
        ),
        diagnostic_notes=("rejected by signal_density",),
    )
    ts = datetime(2026, 5, 13, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        n = record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=failed_report,
            evaluated_at=ts,
        )
    assert n == 3
    assert _row_count(forge_db) == 3


def test_naive_evaluated_at_raises(tmp_path: Path) -> None:
    """Naive datetimes leak silently; reject at the boundary."""
    forge_db = tmp_path / "forge.db"
    candidate_id = uuid.uuid4()
    report = _report(n_filters=1)
    with (
        db_connection(forge_db) as conn,
        pytest.raises(ValueError, match=r"timezone"),
    ):
        record_pre_filter_logs(
            conn,
            candidate_id=candidate_id,
            report=report,
            evaluated_at=datetime(2026, 5, 13),  # noqa: DTZ001
        )
