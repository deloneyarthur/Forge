"""Learned-ranker invariants (D132 / F1) — era cut, honesty reuse, skew-proof.

The design (`docs/proposals/learned-ranker.md` §5) pins three F1 failure modes
before production code:

1. Training rows are hard-cut at the composite clean-era boundary
   2026-06-10T17:17:13Z (earnings-exit live + chain-fixed registry + v17,
   D130/D131) — a model must never learn labels from the polluted engine.
2. The label reuses the D128 honesty predicate from the feedback module —
   one source of truth, drift impossible.
3. Feature extraction is one codepath: a config rehydrated from
   ``submissions.config_json`` extracts byte-identically to the in-memory
   object (train/serve skew-proof).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import duckdb
from crucible_contracts import GatedRun, StrategyConfig
from crucible_contracts.models import GateResult, PromotionDecision, RunResult

from forge.feedback.rejection_weights import (
    CLEAN_ERA_LABEL_CUT,
    _honest_regime_coverage,
    honest_regime_coverage_row,
)
from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.dataset import build_dataset
from forge.ranking.features import extract_features
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()


def _gated_run(
    *,
    config_hash: str,
    decision: str,
    decided_at: datetime,
    gate_results: dict[str, GateResult] | None = None,
) -> GatedRun:
    rid = str(uuid.uuid4())
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
            gate_results=gate_results or {},
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )


def _insert_submission(db: duckdb.DuckDBPyConnection, *, config_hash: str) -> None:
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            minimal_strategy_config().model_dump_json(),
            datetime(2026, 6, 10, 11, 0),  # noqa: DTZ001 — naive-UTC column convention
            "gated",
        ],
    )


def _coverage(passed: bool, detail: str) -> dict[str, GateResult]:
    return {
        "regime_coverage": GateResult(
            gate_name="regime_coverage",
            passed=passed,
            value=None,
            threshold=None,
            detail=detail,
        ),
    }


# ---------------------------------------------------------------------------
# 1 — era cut
# ---------------------------------------------------------------------------


def test_clean_era_label_cut_is_the_composite_boundary() -> None:
    """The constant is the exit-era runner restart, byte-exact (D130/D131)."""
    assert datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC) == CLEAN_ERA_LABEL_CUT


def test_era_cut_is_inclusive_at_the_boundary_second() -> None:
    """17:17:12 is the polluted engine; 17:17:13 is the clean one."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 17, 17, 12),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 17, 17, 13),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 1
    assert frame["decided_at"].to_list()[0] == datetime(2026, 6, 10, 17, 17, 13)  # noqa: DTZ001


# ---------------------------------------------------------------------------
# 2 — honesty predicate is single-sourced
# ---------------------------------------------------------------------------


def test_honesty_row_helper_and_feedback_predicate_cannot_drift() -> None:
    """The row helper IS the predicate `_honest_regime_coverage` delegates to."""
    cases = [
        _coverage(passed=True, detail=""),
        _coverage(passed=True, detail="coverage_unverified: legacy admission"),
        _coverage(passed=False, detail=""),
        {},  # absent row — fail-closed
    ]
    for gate_results in cases:
        run = _gated_run(
            config_hash="aaaa000011112222",
            decision="component",
            decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
            gate_results=dict(gate_results),
        )
        assert _honest_regime_coverage(run) == honest_regime_coverage_row(run.decision.gate_results)


def test_dishonest_component_never_labels_positive() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
                    gate_results=_coverage(
                        passed=True, detail="coverage_unverified: legacy admission"
                    ),
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["label"].to_list() == [0]


# ---------------------------------------------------------------------------
# 3 — train/serve skew-proof
# ---------------------------------------------------------------------------


def test_feature_extraction_roundtrips_through_config_json() -> None:
    config = minimal_strategy_config()
    rehydrated = StrategyConfig.model_validate_json(config.model_dump_json())
    assert extract_features(config, _REGISTRY) == extract_features(rehydrated, _REGISTRY)
