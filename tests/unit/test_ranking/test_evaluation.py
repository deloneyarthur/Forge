"""Tests for forge.ranking.evaluation (D132 / F2) — shadow vs incumbent readout.

Labels MUST agree with the dataset builder's labeling (single `label_for`
source), and the metrics feed the F3 promotion criterion: model AUC ≥
incumbent + 0.05 AND precision@K ≥ incumbent's, per checkpoint window.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import duckdb
import pytest

from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.evaluation import evaluate_shadow

_SINCE = datetime(2026, 6, 10, 17, 17, 13)  # noqa: DTZ001 — naive-UTC convention


def _gated_run(*, config_hash: str, decision: str, honest: bool = True):
    from datetime import date

    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

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
            gate_results={
                "regime_coverage": GateResult(
                    gate_name="regime_coverage",
                    passed=True,
                    value=None,
                    threshold=None,
                    detail="" if honest else "coverage_unverified",
                ),
            },
            decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
            decided_by="runner.forge_minimal",
        ),
    )


def _seed(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, float, float, str]],
    *,
    model_id: str = "aaaa1111bbbb2222",
) -> None:
    """rows: (config_hash, model_score, composite_score, decision)."""
    for config_hash, model_score, composite_score, decision in rows:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), config_hash, _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
            [candidate_id, model_id, model_score, composite_score, _SINCE],
        )
        record_verdicts(conn, [_gated_run(config_hash=config_hash, decision=decision)])


def test_perfect_model_beats_inverted_incumbent() -> None:
    rows = [
        ("aaaa000000000001", 0.9, 0.1, "component"),
        ("aaaa000000000002", 0.8, 0.2, "component"),
        ("aaaa000000000003", 0.2, 0.8, "reject"),
        ("aaaa000000000004", 0.1, 0.9, "reject"),
    ]
    with db_connection() as conn:
        _seed(conn, rows)
        evaluations = evaluate_shadow(conn, since=_SINCE)

    assert len(evaluations) == 1
    ev = evaluations[0]
    assert ev.model_id == "aaaa1111bbbb2222"
    assert ev.n_decided == 4
    assert ev.n_positive == 2
    assert ev.model_auc == pytest.approx(1.0)
    assert ev.incumbent_auc == pytest.approx(0.0)
    assert ev.auc_margin == pytest.approx(1.0)
    assert ev.model_precision_at_k == pytest.approx(1.0)
    assert ev.incumbent_precision_at_k == pytest.approx(0.0)
    assert 0.0 <= ev.model_brier <= 0.1


def test_dishonest_component_labels_zero_in_eval() -> None:
    # Labels must match the dataset builder: a coverage_unverified component is 0.
    with db_connection() as conn:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), "aaaa000000000009", _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
            [candidate_id, "aaaa1111bbbb2222", 0.9, 0.5, _SINCE],
        )
        record_verdicts(
            conn,
            [_gated_run(config_hash="aaaa000000000009", decision="component", honest=False)],
        )
        evaluations = evaluate_shadow(conn, since=_SINCE)

    assert evaluations[0].n_positive == 0
    # Single class — rank metrics undefined, reported as None rather than fake.
    assert evaluations[0].model_auc is None
    assert evaluations[0].auc_margin is None


def test_window_filter_excludes_older_verdicts() -> None:
    rows = [
        ("aaaa000000000001", 0.9, 0.1, "component"),
        ("aaaa000000000002", 0.1, 0.9, "reject"),
    ]
    with db_connection() as conn:
        _seed(conn, rows)
        evaluations = evaluate_shadow(
            conn,
            since=datetime(2026, 6, 11, 0, 0),  # noqa: DTZ001
        )

    assert evaluations == ()


def test_no_shadow_rows_returns_empty() -> None:
    with db_connection() as conn:
        assert evaluate_shadow(conn, since=_SINCE) == ()
