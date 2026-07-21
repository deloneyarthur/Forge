"""Tests for ``forge.ranking.campaign_audit`` (D299) — the carriage audit.

The D287 failure class: generation feeds a confirmed region but the learned
lane starves it at selection. The holdout lane bypasses ranking, so a
campaign's share among holdout rows is an unbiased estimate of its share in
the passed pool; ranked share massively below holdout share == selection
starvation. That signature was caught by hand once (D287: 14 hurst / 0 vix,
the lone vix arrival via holdout) — this audit makes it a standing check.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import duckdb
import pytest

from forge.persistence.db import open_db
from forge.ranking.campaign_audit import (
    MIN_HOLDOUT_MEMBERS,
    STARVATION_RATIO,
    CampaignCarriage,
    audit_carriage,
)
from forge.ranking.campaigns import Campaign

_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)


def _campaign(name: str, hypothesis: str) -> Campaign:
    return Campaign(
        name=name,
        status="farming",
        origin="test",
        decision_refs=("D000",),
        opened="2026-07-01",
        funnel_read="test read",
        retire_on="test close",
        hypothesis=hypothesis,
    )


def _insert_submission(
    conn: duckdb.DuckDBPyConnection,
    *,
    hypothesis: str,
    selection_mode: str | None,
    submitted_at: datetime,
    config_hash: str,
) -> None:
    conn.execute(
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status, crucible_run_id, selection_mode)
        VALUES (?, ?, ?, ?, ?, 'submitted', NULL, ?)
        """,
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            json.dumps({"hypothesis": hypothesis}),
            submitted_at.astimezone(UTC).replace(tzinfo=None),
            selection_mode,
        ],
    )


def _insert_verdict(conn: duckdb.DuckDBPyConnection, *, config_hash: str, decision: str) -> None:
    conn.execute(
        """
        INSERT INTO verdicts
            (crucible_run_id, config_hash, decision, decided_at, trade_count,
             grammar_version, gate_results, recorded_at)
        VALUES (?, ?, ?, ?, NULL, 'v42', '{}', ?)
        """,
        [
            str(uuid.uuid4()),
            config_hash,
            decision,
            _NOW.replace(tzinfo=None),
            _NOW.replace(tzinfo=None),
        ],
    )


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    return open_db(":memory:")


def _fill(
    conn: duckdb.DuckDBPyConnection,
    *,
    hypothesis: str,
    mode: str | None,
    count: int,
    prefix: str,
    at: datetime | None = None,
) -> list[str]:
    hashes = []
    for i in range(count):
        h = f"{prefix}{i:04d}"
        _insert_submission(
            conn,
            hypothesis=hypothesis,
            selection_mode=mode,
            submitted_at=at or (_NOW - timedelta(days=1)),
            config_hash=h,
        )
        hashes.append(h)
    return hashes


def test_starved_campaign_flagged(conn: duckdb.DuckDBPyConnection) -> None:
    """The D287 signature: 1% ranked share vs 30% holdout share -> STARVED."""
    _fill(conn, hypothesis="aaa", mode="ranked", count=1, prefix="ar")
    _fill(conn, hypothesis="zzz", mode="ranked", count=99, prefix="zr")
    _fill(conn, hypothesis="aaa", mode="holdout", count=3, prefix="ah")
    _fill(conn, hypothesis="zzz", mode="holdout", count=7, prefix="zh")

    results, unauditable = audit_carriage(
        conn, now=_NOW, days=7, campaigns=(_campaign("starved-one", "aaa"),)
    )
    assert unauditable == []
    (row,) = results
    assert isinstance(row, CampaignCarriage)
    assert row.ranked_total == 100
    assert row.holdout_total == 10
    assert row.ranked_members == 1
    assert row.holdout_members == 3
    assert row.ranked_share == pytest.approx(0.01)
    assert row.holdout_share == pytest.approx(0.3)
    assert row.carriage_ratio == pytest.approx(0.01 / 0.3)
    assert row.starved is True


def test_healthy_campaign_not_flagged(conn: duckdb.DuckDBPyConnection) -> None:
    _fill(conn, hypothesis="bbb", mode="ranked", count=20, prefix="br")
    _fill(conn, hypothesis="zzz", mode="ranked", count=80, prefix="zr")
    _fill(conn, hypothesis="bbb", mode="holdout", count=2, prefix="bh")
    _fill(conn, hypothesis="zzz", mode="holdout", count=8, prefix="zh")

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("healthy", "bbb"),))
    (row,) = results
    assert row.carriage_ratio == pytest.approx(1.0)
    assert row.starved is False


def test_min_holdout_guard_suppresses_small_n(conn: duckdb.DuckDBPyConnection) -> None:
    """Below MIN_HOLDOUT_MEMBERS the ratio is noise — never flag on it."""
    _fill(conn, hypothesis="ccc", mode="holdout", count=MIN_HOLDOUT_MEMBERS - 1, prefix="ch")
    _fill(conn, hypothesis="zzz", mode="holdout", count=8, prefix="zh")
    _fill(conn, hypothesis="zzz", mode="ranked", count=100, prefix="zr")

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("small-n", "ccc"),))
    (row,) = results
    assert row.ranked_members == 0
    assert row.holdout_members == MIN_HOLDOUT_MEMBERS - 1
    assert row.starved is False


def test_zero_ranked_members_with_holdout_supply_is_starved(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """The exact D287 shape: 0 ranked members while holdout keeps arriving."""
    _fill(conn, hypothesis="ddd", mode="holdout", count=MIN_HOLDOUT_MEMBERS, prefix="dh")
    _fill(conn, hypothesis="zzz", mode="holdout", count=7, prefix="zh")
    _fill(conn, hypothesis="zzz", mode="ranked", count=100, prefix="zr")

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("dark", "ddd"),))
    (row,) = results
    assert row.ranked_members == 0
    assert row.carriage_ratio == pytest.approx(0.0)
    assert row.starved is True


def test_window_cut_and_null_mode(conn: duckdb.DuckDBPyConnection) -> None:
    """Rows older than the window are excluded; NULL selection_mode counts as
    ranked (pre-P3.3 semantics, mirrored from the schema comment)."""
    _fill(conn, hypothesis="eee", mode=None, count=2, prefix="en")  # NULL -> ranked
    _fill(
        conn,
        hypothesis="eee",
        mode="ranked",
        count=5,
        prefix="eo",
        at=_NOW - timedelta(days=10),  # outside the 7d window
    )
    _fill(conn, hypothesis="zzz", mode="ranked", count=8, prefix="zr")

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("windowed", "eee"),))
    (row,) = results
    assert row.ranked_total == 10  # 2 NULL + 8 ranked; the 5 old rows cut
    assert row.ranked_members == 2
    assert row.holdout_total == 0
    assert row.holdout_share is None
    assert row.carriage_ratio is None
    assert row.starved is False


def test_verdict_decisions_counted_for_members(conn: duckdb.DuckDBPyConnection) -> None:
    hashes = _fill(conn, hypothesis="fff", mode="ranked", count=3, prefix="fr")
    _fill(conn, hypothesis="zzz", mode="ranked", count=7, prefix="zr")
    _insert_verdict(conn, config_hash=hashes[0], decision="component")
    _insert_verdict(conn, config_hash=hashes[1], decision="rejected")
    _insert_verdict(conn, config_hash="zr0000", decision="component")  # non-member

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("decided", "fff"),))
    (row,) = results
    assert dict(row.decisions) == {"component": 1, "rejected": 1}


def test_unauditable_campaign_listed_not_guessed(conn: duckdb.DuckDBPyConnection) -> None:
    bare = Campaign(
        name="no-signature",
        status="farming",
        origin="test",
        decision_refs=("D000",),
        opened="2026-07-01",
        funnel_read="test",
        retire_on="test",
    )
    results, unauditable = audit_carriage(conn, now=_NOW, days=7, campaigns=(bare,))
    assert results == []
    assert unauditable == ["no-signature"]


def test_non_farming_campaigns_skipped(conn: duckdb.DuckDBPyConnection) -> None:
    retired = Campaign(
        name="done",
        status="retired",
        origin="test",
        decision_refs=("D000",),
        opened="2026-07-01",
        funnel_read="test",
        retire_on="test",
        hypothesis="aaa",
    )
    results, unauditable = audit_carriage(conn, now=_NOW, days=7, campaigns=(retired,))
    assert results == []
    assert unauditable == []


def test_starvation_ratio_boundary(conn: duckdb.DuckDBPyConnection) -> None:
    """ratio exactly AT the threshold is not starved (strict <)."""
    # ranked: 1 member of 12 -> share 1/12; holdout: 3 of 9 -> share 1/3.
    # ratio = (1/12)/(1/3) = 0.25 == STARVATION_RATIO -> NOT flagged.
    _fill(conn, hypothesis="ggg", mode="ranked", count=1, prefix="gr")
    _fill(conn, hypothesis="zzz", mode="ranked", count=11, prefix="zr")
    _fill(conn, hypothesis="ggg", mode="holdout", count=3, prefix="gh")
    _fill(conn, hypothesis="zzz", mode="holdout", count=6, prefix="zh")

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("boundary", "ggg"),))
    (row,) = results
    assert row.carriage_ratio == pytest.approx(STARVATION_RATIO)
    assert row.starved is False


def test_young_explore_rows_count_in_neither_lane(conn: duckdb.DuckDBPyConnection) -> None:
    """D315 (2d): young_explore rows are neither merit-ranked nor an unweighted
    draw — they must not distort the ranked share OR the holdout denominator."""
    _fill(conn, hypothesis="hhh", mode="ranked", count=10, prefix="hr")
    _fill(conn, hypothesis="hhh", mode="holdout", count=2, prefix="hh")
    _fill(conn, hypothesis="hhh", mode="young_explore", count=50, prefix="hy")

    results, _ = audit_carriage(conn, now=_NOW, days=7, campaigns=(_campaign("quota", "hhh"),))
    (row,) = results
    assert row.ranked_total == 10  # the 50 young rows are excluded entirely
    assert row.holdout_total == 2
    assert row.ranked_members == 10
    assert row.holdout_members == 2
