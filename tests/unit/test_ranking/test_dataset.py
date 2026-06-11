"""Tests for forge.ranking.dataset (D132 / F1) — honest-era training frame.

``build_dataset`` joins ``verdicts ⋈ submissions`` on config_hash, hard-cuts
rows at the clean-era boundary, labels with the D128 honesty predicate, and
keeps every refit row (same config_hash, new crucible_run_id — independent
gate evaluations per D124). Design: `docs/proposals/learned-ranker.md` §4 F1.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import duckdb

from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.dataset import build_dataset
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()

# Naive-UTC datetimes throughout: the verdicts/export era is uniformly UTC
# post-D117 and DuckDB TIMESTAMP columns are naive by convention.
_POST_CUT = datetime(2026, 6, 10, 18, 0, 0)  # noqa: DTZ001
_PRE_CUT = datetime(2026, 6, 10, 12, 0, 0)  # noqa: DTZ001


def _insert_submission(db: duckdb.DuckDBPyConnection, *, config_hash: str) -> None:
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            minimal_strategy_config().model_dump_json(),
            datetime(2026, 6, 10, 11, 0),  # noqa: DTZ001
            "gated",
        ],
    )


def _gated_run(
    *,
    config_hash: str,
    decision: str = "reject",
    decided_at: datetime = _POST_CUT,
    honest_coverage: bool = True,
    coverage_row: bool = True,
    run_id: str | None = None,
):
    from datetime import date

    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

    rid = run_id or str(uuid.uuid4())
    gate_results = {
        "min_oos_trade_count": GateResult(
            gate_name="min_oos_trade_count",
            passed=True,
            value=120.0,
            threshold=100.0,
        ),
    }
    if coverage_row:
        gate_results["regime_coverage"] = GateResult(
            gate_name="regime_coverage",
            passed=True,
            value=None,
            threshold=None,
            detail="" if honest_coverage else "coverage_unverified: legacy admission",
        )
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v17",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results=gate_results,
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )


def test_joins_labels_and_orders_rows() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        _insert_submission(conn, config_hash="bbbb000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="bbbb000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 18, 30),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 2
    # Ordered by (decided_at, crucible_run_id): the reject decided first.
    assert frame["config_hash"].to_list() == ["bbbb000011112222", "aaaa000011112222"]
    assert frame["label"].to_list() == [0, 1]
    # Feature columns rode along.
    assert frame["hypothesis=mean_reversion"].to_list() == [1.0, 1.0]


def test_era_cut_excludes_pre_boundary_rows() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=_PRE_CUT,
                ),
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=_POST_CUT,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 1
    assert frame["label"].to_list() == [0]


def test_refit_children_kept_as_independent_rows() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 21, 0),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 2
    assert frame["label"].to_list() == [0, 1]


def test_dishonest_component_labels_zero() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    honest_coverage=False,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["label"].to_list() == [0]


def test_component_without_coverage_row_labels_zero() -> None:
    # Absent regime_coverage row = cannot verify = fail-closed (D124 key 2).
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    coverage_row=False,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["label"].to_list() == [0]


def test_verdict_without_submission_is_skipped() -> None:
    with db_connection() as conn:
        record_verdicts(
            conn,
            [_gated_run(config_hash="cccc000011112222", decision="component")],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 0
