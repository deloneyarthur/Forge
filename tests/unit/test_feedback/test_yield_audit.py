"""Tests for ``forge.feedback.yield_audit`` (D302) — the dead-cell detector.

Theme 4 of the post-promotion process review (docs/proposals/yield-auditor.md):
every structural exclusion so far was found by CRUCIBLE's census on OUR
verdicts. This module runs the same reads locally, min-n guarded, with the
ghost-era label cut and farming-campaign exemptions applied — and only ever
PRINTS staged rider drafts (auto-tightening detection; shipping stays behind
the operator-gated grammar-bump ritual).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import duckdb
import pytest

from forge.feedback.rejection_weights import VE_GHOST_LABEL_CUT
from forge.feedback.yield_audit import (
    CONVERTING_DECISIONS,
    YieldAuditReport,
    audit_yield,
)
from forge.persistence.db import open_db
from forge.ranking.campaigns import Campaign

_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
_SINCE = datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    return open_db(":memory:")


def _insert_decided(
    conn: duckdb.DuckDBPyConnection,
    *,
    underlying: str | None,
    hypothesis: str,
    dte_bucket: str = "swing_mid",
    decision: str = "reject",
    decided_at: datetime | None = None,
    count: int = 1,
) -> None:
    decided = (decided_at or _NOW).astimezone(UTC).replace(tzinfo=None)
    for _ in range(count):
        config_hash = uuid.uuid4().hex[:16]
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status, crucible_run_id, selection_mode)
            VALUES (?, ?, ?, ?, ?, 'submitted', NULL, 'ranked')
            """,
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                config_hash,
                json.dumps(
                    {
                        "underlying": underlying,
                        "hypothesis": hypothesis,
                        "dte_bucket": dte_bucket,
                    }
                ),
                decided - timedelta(days=1),
            ],
        )
        conn.execute(
            """
            INSERT INTO verdicts
                (crucible_run_id, config_hash, decision, decided_at, trade_count,
                 grammar_version, gate_results, recorded_at)
            VALUES (?, ?, ?, ?, NULL, 'v42', '{}', ?)
            """,
            [str(uuid.uuid4()), config_hash, decision, decided, decided],
        )


def _audit(conn: duckdb.DuckDBPyConnection, **kwargs: object) -> YieldAuditReport:
    defaults: dict[str, object] = {
        "since": _SINCE,
        "min_name_n": 10,
        "min_cell_n": 20,
        "campaigns": (),
    }
    defaults.update(kwargs)
    return audit_yield(conn, **defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Dead-name detection
# ---------------------------------------------------------------------------


def test_dead_name_flagged_at_min_n_with_zero_conversions(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _insert_decided(conn, underlying="XYZ", hypothesis="trend_continuation", count=10)
    _insert_decided(conn, underlying="SPY", hypothesis="trend_continuation", count=5)
    report = _audit(conn)
    (flag,) = report.dead_names
    assert flag.underlying == "XYZ"
    assert flag.decided == 10
    assert flag.converted == 0


def test_name_below_min_n_not_flagged(conn: duckdb.DuckDBPyConnection) -> None:
    _insert_decided(conn, underlying="XYZ", hypothesis="trend_continuation", count=9)
    report = _audit(conn)
    assert report.dead_names == ()


def test_single_conversion_unflags_name(conn: duckdb.DuckDBPyConnection) -> None:
    _insert_decided(conn, underlying="XYZ", hypothesis="trend_continuation", count=9)
    _insert_decided(conn, underlying="XYZ", hypothesis="trend_continuation", decision="component")
    report = _audit(conn)
    assert report.dead_names == ()


def test_promote_counts_as_converting(conn: duckdb.DuckDBPyConnection) -> None:
    assert "promote" in CONVERTING_DECISIONS
    _insert_decided(conn, underlying="XYZ", hypothesis="trend_continuation", count=9)
    _insert_decided(conn, underlying="XYZ", hypothesis="trend_continuation", decision="promote")
    report = _audit(conn)
    assert report.dead_names == ()


def test_already_excluded_name_reported_not_flagged(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """ASML is in the sampler's structural exclusion — old decided rows must go
    to the retire-review report, never re-flag."""
    _insert_decided(conn, underlying="ASML", hypothesis="trend_continuation", count=15)
    report = _audit(conn)
    assert report.dead_names == ()
    (row,) = report.excluded_names
    assert row.underlying == "ASML"
    assert row.decided == 15


def test_underlying_none_rows_skip_name_audit(conn: duckdb.DuckDBPyConnection) -> None:
    _insert_decided(conn, underlying=None, hypothesis="trend_continuation", count=25)
    report = _audit(conn)
    assert report.dead_names == ()


# ---------------------------------------------------------------------------
# Ghost-era + window cuts
# ---------------------------------------------------------------------------


def test_ve_ghost_rows_cut_before_the_label_cut(conn: duckdb.DuckDBPyConnection) -> None:
    ghost_day = VE_GHOST_LABEL_CUT - timedelta(days=5)
    _insert_decided(
        conn, underlying="XYZ", hypothesis="volatility_event", decided_at=ghost_day, count=12
    )
    report = _audit(conn)
    assert report.dead_names == ()  # the rows are unrankable fiction, not evidence
    assert report.ghost_rows_cut == 12


def test_non_ve_rows_before_ghost_cut_are_kept(conn: duckdb.DuckDBPyConnection) -> None:
    before_cut = VE_GHOST_LABEL_CUT - timedelta(days=5)
    _insert_decided(
        conn, underlying="XYZ", hypothesis="trend_continuation", decided_at=before_cut, count=10
    )
    report = _audit(conn)
    assert report.ghost_rows_cut == 0
    assert len(report.dead_names) == 1


def test_since_window_cut(conn: duckdb.DuckDBPyConnection) -> None:
    _insert_decided(
        conn,
        underlying="XYZ",
        hypothesis="trend_continuation",
        decided_at=_SINCE - timedelta(days=1),
        count=10,
    )
    report = _audit(conn)
    assert report.dead_names == ()
    assert report.rows_considered == 0


# ---------------------------------------------------------------------------
# Cold-cell detection
# ---------------------------------------------------------------------------


def _fill_cells(conn: duckdb.DuckDBPyConnection, hypothesis: str) -> None:
    """Baseline cell converts at 10% (n=20); cold cell at 0% (n=20) ->
    hypothesis baseline 5%, cold cell rate 0 < 0.25 x 0.05."""
    _insert_decided(
        conn, underlying="SPY", hypothesis=hypothesis, dte_bucket="swing_short", count=18
    )
    _insert_decided(
        conn,
        underlying="SPY",
        hypothesis=hypothesis,
        dte_bucket="swing_short",
        decision="component",
        count=2,
    )
    _insert_decided(
        conn, underlying="SPY", hypothesis=hypothesis, dte_bucket="swing_long", count=20
    )


def test_cold_cell_flagged_vs_hypothesis_baseline(conn: duckdb.DuckDBPyConnection) -> None:
    _fill_cells(conn, "trend_continuation")
    report = _audit(conn)
    (flag,) = report.cold_cells
    assert flag.hypothesis == "trend_continuation"
    assert flag.dte_bucket == "swing_long"
    assert flag.decided == 20
    assert flag.converted == 0
    assert flag.baseline_rate == pytest.approx(0.05)


def test_cold_cell_below_min_n_not_flagged(conn: duckdb.DuckDBPyConnection) -> None:
    _fill_cells(conn, "trend_continuation")
    report = _audit(conn, min_cell_n=21)
    assert report.cold_cells == ()


def test_farming_campaign_hypothesis_exempt_from_cell_flags(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _fill_cells(conn, "mean_reversion")
    campaign = Campaign(
        name="mr-campaign",
        status="farming",
        origin="test",
        decision_refs=("D000",),
        opened="2026-07-01",
        funnel_read="test",
        retire_on="test",
        hypothesis="mean_reversion",
    )
    report = _audit(conn, campaigns=(campaign,))
    assert report.cold_cells == ()
    assert "mean_reversion" in report.exempt_hypotheses
    # A RETIRED campaign stops exempting.
    retired = Campaign(
        name="mr-campaign",
        status="retired",
        origin="test",
        decision_refs=("D000",),
        opened="2026-07-01",
        funnel_read="test",
        retire_on="test",
        hypothesis="mean_reversion",
    )
    report2 = _audit(conn, campaigns=(retired,))
    assert len(report2.cold_cells) == 1


def test_zero_baseline_hypothesis_yields_no_cell_flags(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """A hypothesis converting 0 everywhere is a name/hypothesis story, not a
    cell story — flags would be meaningless."""
    _insert_decided(
        conn, underlying="SPY", hypothesis="trend_continuation", dte_bucket="swing_short", count=25
    )
    _insert_decided(
        conn, underlying="SPY", hypothesis="trend_continuation", dte_bucket="swing_long", count=25
    )
    report = _audit(conn)
    assert report.cold_cells == ()
