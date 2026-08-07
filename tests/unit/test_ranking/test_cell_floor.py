"""Tests for ``forge.ranking.cell_floor`` (D307, Theme 2b) — the young-CELL
exploration floor.

The D287 lesson generalized: a (directional, regime) CELL can be starved at
selection even when both of its arms are individually mature (vix_term_slope
matured within days of v27, so the D136 arm floor could not scope to the
resid x vix PAIR — it took a hand pin). This floor makes any cell younger
than K honest-era verdicts floor-eligible automatically. (The hand-pin
override phase was removed 2026-08-06 — pin set empty since D305.)

Flag-gated OFF in production (`FORGE_YOUNG_CELL_FLOOR`); `mature_cells=None`
keeps every path byte-identical — the deploy window flips the env.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import duckdb
import pytest
from crucible_contracts import SignalSpec

from forge.feedback.rejection_weights import VE_GHOST_LABEL_CUT
from forge.persistence.db import open_db
from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.cell_floor import (
    CELL_FLOOR_BATCH_FRACTION,
    CELL_FLOOR_SLOTS_PER_CELL,
    YOUNG_CELL_VERDICT_THRESHOLD,
    compute_mature_cells,
)
from forge.ranking.diversifier import select_top_n
from forge.ranking.types import RankedCandidate
from tests.fixtures.strategy_configs import minimal_strategy_config

_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# compute_mature_cells — the verdict-count query
# ---------------------------------------------------------------------------


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    return open_db(":memory:")


def _insert_decided_cell(
    conn: duckdb.DuckDBPyConnection,
    *,
    directional: str,
    regime: str,
    hypothesis: str = "mean_reversion",
    decided_at: datetime | None = None,
    count: int = 1,
) -> None:
    decided = (decided_at or _NOW).astimezone(UTC).replace(tzinfo=None)
    config_json = json.dumps(
        {
            "hypothesis": hypothesis,
            "signals": [
                {"role": "directional", "indicators": [directional]},
                {"role": "regime_filter", "indicators": [regime]},
            ],
        }
    )
    for _ in range(count):
        config_hash = uuid.uuid4().hex[:16]
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status, crucible_run_id, selection_mode)
            VALUES (?, ?, ?, ?, ?, 'submitted', NULL, 'ranked')
            """,
            [str(uuid.uuid4()), str(uuid.uuid4()), config_hash, config_json, decided],
        )
        conn.execute(
            """
            INSERT INTO verdicts
                (crucible_run_id, config_hash, decision, decided_at, trade_count,
                 grammar_version, gate_results, recorded_at)
            VALUES (?, ?, 'reject', ?, NULL, 'v42', '{}', ?)
            """,
            [str(uuid.uuid4()), config_hash, decided, decided],
        )


def test_cell_matures_at_threshold(conn: duckdb.DuckDBPyConnection) -> None:
    _insert_decided_cell(conn, directional="rsi_2", regime="iv_rank", count=25)
    _insert_decided_cell(conn, directional="hurst", regime="iv_rank", count=24)
    mature = compute_mature_cells(conn)
    assert ("rsi_2", "iv_rank") in mature
    assert ("hurst", "iv_rank") not in mature


def test_ghost_era_ve_rows_do_not_mature_a_cell(conn: duckdb.DuckDBPyConnection) -> None:
    ghost_day = VE_GHOST_LABEL_CUT - timedelta(days=3)
    _insert_decided_cell(
        conn,
        directional="iv_spike",
        regime="iv_rank",
        hypothesis="volatility_event",
        decided_at=ghost_day,
        count=40,
    )
    assert ("iv_spike", "iv_rank") not in compute_mature_cells(conn)


def test_pre_era_rows_do_not_count(conn: duckdb.DuckDBPyConnection) -> None:
    _insert_decided_cell(
        conn,
        directional="rsi_2",
        regime="iv_rank",
        decided_at=datetime(2026, 5, 1, tzinfo=UTC),
        count=40,
    )
    assert compute_mature_cells(conn) == frozenset()


def test_default_constants_match_the_d136_shape() -> None:
    assert YOUNG_CELL_VERDICT_THRESHOLD == 25
    assert CELL_FLOOR_SLOTS_PER_CELL == 2
    assert pytest.approx(0.10) == CELL_FLOOR_BATCH_FRACTION


# ---------------------------------------------------------------------------
# Diversifier phase 0c — young-cell reservation
# ---------------------------------------------------------------------------


def _candidate(
    name: str,
    *,
    directional: str,
    regime: str | None,
    composite_score: float,
) -> RankedCandidate:
    signals: tuple[SignalSpec, ...] = (
        SignalSpec(
            id=f"{name}_d",
            type="threshold",
            role="directional",
            indicators=(directional,),
            params={"threshold": 30.0, "key": f"{name}_d"},
        ),
    )
    if regime is not None:
        signals = (
            *signals,
            SignalSpec(
                id=f"{name}_r",
                type="threshold",
                role="regime_filter",
                indicators=(regime,),
                params={"threshold": 50.0, "key": f"{name}_r"},
            ),
        )
    config = minimal_strategy_config().model_copy(update={"name": name, "signals": signals})
    report = PreFilterReport(
        config=config,
        passed=True,
        filter_results=MappingProxyType(
            {"structural_redundancy": FilterResult(passed=True, score=1.0)}
        ),
        diagnostic_notes=(),
    )
    return RankedCandidate(
        report=report, prior_promotion_score=0.0, composite_score=composite_score
    )


def test_none_mature_cells_is_byte_identical() -> None:
    candidates = [
        _candidate("a", directional="rsi_2", regime="iv_rank", composite_score=0.9),
        _candidate("b", directional="hurst", regime="vix_term_slope", composite_score=0.1),
        _candidate("c", directional="rsi_2", regime="vol_regime", composite_score=0.5),
    ]
    legacy = select_top_n(candidates, 2)
    with_param = select_top_n(candidates, 2, mature_cells=None)
    assert [c.report.config.name for c in legacy] == [c.report.config.name for c in with_param]


def test_young_cell_reserved_over_higher_scores() -> None:
    """A young cell's best member gets a slot even at a rock-bottom composite —
    the model-independent coverage the D287 pathology needed."""
    candidates = [
        _candidate(f"m{i}", directional="rsi_2", regime="iv_rank", composite_score=0.9 - i * 0.01)
        for i in range(4)
    ] + [
        _candidate("young", directional="hurst", regime="vix_term_slope", composite_score=0.0),
    ]
    mature = frozenset({("rsi_2", "iv_rank")})
    # NB the cap is int(n * fraction) — at production n=200 the default 0.10
    # gives 20; at test n=3 it gives 0, so the fraction is explicit here.
    selected = select_top_n(candidates, 3, mature_cells=mature, cell_floor_batch_fraction=0.5)
    names = [c.report.config.name for c in selected]
    assert "young" in names


def test_mature_cells_get_no_reservation() -> None:
    candidates = [
        _candidate("hi", directional="rsi_2", regime="iv_rank", composite_score=0.9),
        _candidate("lo", directional="rsi_2", regime="iv_rank", composite_score=0.0),
        _candidate("other", directional="hurst", regime="iv_rank", composite_score=0.8),
    ]
    mature = frozenset({("rsi_2", "iv_rank"), ("hurst", "iv_rank")})
    selected = select_top_n(candidates, 2, mature_cells=mature)
    names = [c.report.config.name for c in selected]
    assert names == ["hi", "other"]  # pure merit — no floor fired


def test_cell_floor_cap_bounds_reservations() -> None:
    """Many young cells: reservations stop at int(n * fraction)."""
    young = [
        _candidate(f"y{i}", directional=f"d{i}", regime=f"r{i}", composite_score=0.0)
        for i in range(10)
    ]
    mature_fill = [
        _candidate(f"m{i}", directional="rsi_2", regime="iv_rank", composite_score=0.9 - i * 0.01)
        for i in range(10)
    ]
    selected = select_top_n(
        [*mature_fill, *young],
        10,
        mature_cells=frozenset({("rsi_2", "iv_rank")}),
        cell_floor_slots=2,
        cell_floor_batch_fraction=0.2,  # cap = 2 reservations
    )
    young_selected = [c for c in selected if c.report.config.name.startswith("y")]
    assert len(young_selected) == 2  # cap, not 10


def test_bare_configs_without_a_cell_never_floor() -> None:
    candidates = [
        _candidate("gateless", directional="momentum", regime=None, composite_score=0.0),
        *[
            _candidate(f"m{i}", directional="rsi_2", regime="iv_rank", composite_score=0.9)
            for i in range(3)
        ],
    ]
    selected = select_top_n(candidates, 2, mature_cells=frozenset({("rsi_2", "iv_rank")}))
    assert all(c.report.config.name != "gateless" for c in selected)
