"""Tests for ``forge.campaign.cells`` (plan 2026-09 §12, D406/D409).

The cell key is the census key; the book comes from Crucible's exports through
the contracts loaders; the stats come from Forge's own verdict ledger with the
same honesty cuts the yield auditor applies. Every claim the triggers and the
gate make rests on these three reads, so they are pinned here first.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from crucible_contracts import GatedRun, StrategyConfig
from crucible_contracts.models import (
    PortfolioComponent,
    PromotedPortfolio,
    PromotionDecision,
    RunResult,
)

from forge.campaign.cells import (
    cell_key,
    cell_key_from_json,
    classify_dead,
    load_book,
    load_cell_stats,
)
from forge.campaign.types import CampaignConfig, CellStats
from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT, VE_GHOST_LABEL_CUT
from forge.persistence.db import open_db
from tests.fixtures.strategy_configs import grammar_valid_baseline, minimal_strategy_config

# ---------------------------------------------------------------------------
# cell key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("builder", [minimal_strategy_config, grammar_valid_baseline])
def test_cell_key_model_and_json_agree(builder: object) -> None:
    cfg = builder()  # type: ignore[operator]
    assert cell_key(cfg) == cell_key_from_json(cfg.model_dump())


def test_cell_key_shape_on_the_fixture() -> None:
    cfg = minimal_strategy_config()
    assert cell_key(cfg) == ("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")


def test_cell_key_xsect_axis_from_combiner_type() -> None:
    payload = minimal_strategy_config().model_dump()
    payload["combiner"] = {"type": "cross_sectional_rank"}
    assert cell_key_from_json(payload)[2] == "xsect"


def test_cell_key_no_gate_fallback_keeps_directional() -> None:
    payload = minimal_strategy_config().model_dump()
    payload["signals"] = [s for s in payload["signals"] if s["role"] == "directional"]
    assert cell_key_from_json(payload)[3:] == ("rsi_2", "(nogate)")


def test_cell_key_absent_roles_are_marked() -> None:
    assert cell_key_from_json({"hypothesis": "mean_reversion"}) == (
        "mean_reversion",
        "-",
        "named",
        "-",
        "(nogate)",
    )


# ---------------------------------------------------------------------------
# book
# ---------------------------------------------------------------------------


def _gated_run(config_hash: str, decided_at: datetime) -> GatedRun:
    rid = str(uuid.uuid4())
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v55",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision="promote",
            gate_results={},
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )


def _portfolio(legs: list[StrategyConfig], decided_at: datetime) -> tuple[str, dict[str, object]]:
    """The contracts model derives the book id from its components (no hand-edited
    drift), so the id is computed first and returned with the payload."""
    components = tuple(
        PortfolioComponent(
            strategy_config=cfg,
            weight=1.0 / len(legs),
            component_run_id=f"run-{cfg.config_hash}",
        )
        for cfg in legs
    )
    portfolio_id = PromotedPortfolio.compute_config_hash(components, None, "equal")
    book = PromotedPortfolio(
        portfolio_id=portfolio_id,
        components=components,
        gated_run=_gated_run(portfolio_id, decided_at),
        weighting_scheme="equal",
        rebalance_freq="daily",
        assembled_at=decided_at,
        hypotheses=tuple(sorted({c.hypothesis for c in legs})),
        underlyings=tuple(sorted({c.underlying or "" for c in legs})),
    )
    return portfolio_id, json.loads(book.model_dump_json())


@dataclass(frozen=True, slots=True)
class _Exports:
    leg_a: StrategyConfig
    leg_b: StrategyConfig
    leg_c: StrategyConfig
    book_a: str
    book_b: str


def _write_exports(exports_dir: Path, *, designate_a: bool) -> _Exports:
    """Two promoted books; ``leg_c`` sits in both, so the contributions payload
    carries it under the last-iterated book (the Crucible 09-13 §1 caveat)."""
    at = datetime(2026, 8, 6, tzinfo=UTC)
    leg_a = minimal_strategy_config(name="a")
    leg_b = minimal_strategy_config(
        name="b", hypothesis="trend_continuation", dte_bucket="swing_long"
    )
    leg_c = minimal_strategy_config(name="c", dte_bucket="swing_mid")
    book_a, payload_a = _portfolio([leg_a, leg_c], at - timedelta(days=1))
    book_b, payload_b = _portfolio([leg_b, leg_c], at)
    payload = {
        "schema_version": "1.0",
        "exported_at": at.isoformat(),
        "promoted_portfolios": [payload_a, payload_b],
    }
    (exports_dir / "promoted_portfolios_2026-09-14T000000Z.json").write_text(json.dumps(payload))
    contributions = {
        "schema_version": "1.0",
        "schema": "component_contributions/v1",
        "exported_at": at.isoformat(),
        "contributions": {
            leg_a.config_hash: {
                "portfolio_id": book_a,
                "correlation_to_incumbent": 0.1,
                "marginal_sharpe": 1.5,
            },
            leg_b.config_hash: {
                "portfolio_id": book_b,
                "correlation_to_incumbent": 0.2,
                "marginal_sharpe": 0.7,
            },
            leg_c.config_hash: {
                "portfolio_id": book_b,
                "correlation_to_incumbent": 0.3,
                "marginal_sharpe": -0.2,
            },
        },
    }
    (exports_dir / "component_contributions_2026-09-14T000000Z.json").write_text(
        json.dumps(contributions)
    )
    if designate_a:
        (exports_dir / "designation_history_2026-09-14T000000Z.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "exported_at": at.isoformat(),
                    "designated": {"portfolio_id": book_a, "designated_at": "2026-08-06"},
                    "history": [{"portfolio_id": book_a, "designated_at": "2026-08-06"}],
                }
            )
        )
    return _Exports(leg_a, leg_b, leg_c, book_a, book_b)


def test_load_book_reads_designation_legs_protection_and_filtered_marginals(
    tmp_path: Path,
) -> None:
    ex = _write_exports(tmp_path, designate_a=True)
    book = load_book(tmp_path)
    assert book.designated_id == ex.book_a
    assert book.designated_at == "2026-08-06"
    assert {leg.config_hash for leg in book.legs} == {
        ex.leg_a.config_hash,
        ex.leg_b.config_hash,
        ex.leg_c.config_hash,
    }
    # every promoted book's cells are protected, not just the designated book's
    assert book.protected_cells == {cell_key(ex.leg_a), cell_key(ex.leg_b), cell_key(ex.leg_c)}
    # marginals are filtered to the designated book: leg_c is filed under book B, so
    # it is unknown to the designated book, never "healthy"
    assert book.marginal_sharpe == {ex.leg_a.config_hash: 1.5}
    leg = next(leg for leg in book.legs if leg.config_hash == ex.leg_a.config_hash)
    assert leg.portfolio_id == ex.book_a
    assert leg.hypothesis == "mean_reversion"
    assert leg.signal_ids
    assert all(isinstance(k, str) for k in leg.signal_ids)


def test_load_book_without_designation_file_has_no_designated_book(tmp_path: Path) -> None:
    _write_exports(tmp_path, designate_a=False)
    book = load_book(tmp_path)
    assert book.designated_id is None
    assert book.marginal_sharpe == {}
    assert len(book.legs) == 4  # leg_c appears in both books


def test_load_book_on_empty_exports_dir_is_empty(tmp_path: Path) -> None:
    book = load_book(tmp_path)
    assert book.legs == ()
    assert book.protected_cells == frozenset()
    assert book.designated_id is None


# ---------------------------------------------------------------------------
# cell stats
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    return open_db(":memory:")


def _seed(
    conn: duckdb.DuckDBPyConnection,
    *,
    hypothesis: str = "mean_reversion",
    dte_bucket: str = "swing_short",
    decision: str | None = "reject",
    decided_at: datetime = _NOW,
    cpcv: float | None = None,
    count: int = 1,
) -> None:
    for _ in range(count):
        config_hash = uuid.uuid4().hex[:16]
        payload = minimal_strategy_config(hypothesis=hypothesis, dte_bucket=dte_bucket).model_dump(
            mode="json"
        )
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
                json.dumps(payload),
                (decided_at - timedelta(days=1)).replace(tzinfo=None),
            ],
        )
        if decision is None:
            continue
        gate_results = (
            {} if cpcv is None else {"cpcv_sharpe_p25": {"value": cpcv, "passed": cpcv >= 1.5}}
        )
        conn.execute(
            """
            INSERT INTO verdicts
                (crucible_run_id, config_hash, decision, decided_at, trade_count,
                 grammar_version, gate_results, recorded_at)
            VALUES (?, ?, ?, ?, NULL, 'v55', ?, ?)
            """,
            [
                str(uuid.uuid4()),
                config_hash,
                decision,
                decided_at.replace(tzinfo=None),
                json.dumps(gate_results),
                decided_at.replace(tzinfo=None),
            ],
        )


def test_cell_stats_counts_submitted_decided_converting_best_and_newest(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    _seed(conn, decision="reject", cpcv=0.4, count=3)
    _seed(conn, decision="component", cpcv=1.7, decided_at=_NOW - timedelta(days=2))
    _seed(conn, decision=None)  # submitted, never decided
    stats = load_cell_stats(conn)
    key = ("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")
    assert set(stats) == {key}
    cell = stats[key]
    assert (cell.submitted, cell.decided, cell.converting) == (5, 4, 1)
    assert cell.best_cpcv_p25 == pytest.approx(1.7)
    assert cell.newest_decided_at == _NOW


def test_cell_stats_apply_the_clean_era_and_ghost_cuts(conn: duckdb.DuckDBPyConnection) -> None:
    _seed(conn, decided_at=CLEAN_ERA_LABEL_CUT - timedelta(days=1))  # pre-clean-era: no evidence
    _seed(conn, hypothesis="volatility_event", decided_at=VE_GHOST_LABEL_CUT - timedelta(hours=1))
    _seed(conn, hypothesis="volatility_event", decided_at=VE_GHOST_LABEL_CUT + timedelta(hours=1))
    stats = load_cell_stats(conn)
    mr = stats[("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")]
    ve = stats[("volatility_event", "swing_short", "named", "rsi_2", "iv_rank")]
    assert (mr.submitted, mr.decided) == (1, 0)  # submitted counts all time, decided only in-era
    assert (ve.submitted, ve.decided) == (2, 1)  # the ghost-era ve verdict is not evidence


def test_cell_stats_since_override(conn: duckdb.DuckDBPyConnection) -> None:
    _seed(conn, decided_at=_NOW - timedelta(days=10))
    _seed(conn, decided_at=_NOW)
    stats = load_cell_stats(conn, since=_NOW - timedelta(days=1))
    assert stats[("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")].decided == 1


# ---------------------------------------------------------------------------
# dead cells
# ---------------------------------------------------------------------------


def _stats(key: tuple[str, str, str, str, str], decided: int, converting: int) -> CellStats:
    return CellStats(
        key=key,
        submitted=decided,
        decided=decided,
        converting=converting,
        best_cpcv_p25=None,
        newest_decided_at=None,
    )


_MR_A = ("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")
_MR_B = ("mean_reversion", "swing_mid", "named", "rsi_2", "iv_rank")
_TR_A = ("trend_continuation", "swing_long", "named", "momentum_252", "hurst")


@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        # zero conversions at the volume floor, hypothesis baseline positive -> dead
        ([_stats(_MR_A, 1000, 0), _stats(_MR_B, 1000, 50)], {_MR_A}),
        # below the volume floor -> never dead, however bad
        ([_stats(_MR_A, 999, 0), _stats(_MR_B, 1000, 50)], set()),
        # converting but far below the hypothesis baseline (5% vs 0.25 * 5% = 1.25%) -> dead
        ([_stats(_MR_A, 1000, 5), _stats(_MR_B, 1000, 100)], {_MR_A}),
        # a zero-baseline hypothesis flags nothing (a hypothesis-level story, not a cell one)
        ([_stats(_MR_A, 1000, 0), _stats(_MR_B, 1000, 0)], set()),
        # baselines are per hypothesis: trend's conversions do not judge MR cells
        ([_stats(_MR_A, 1000, 0), _stats(_TR_A, 1000, 100)], set()),
    ],
)
def test_classify_dead_table(stats: list[CellStats], expected: set[tuple[str, ...]]) -> None:
    result = classify_dead({s.key: s for s in stats}, CampaignConfig())
    assert result == frozenset(expected)
