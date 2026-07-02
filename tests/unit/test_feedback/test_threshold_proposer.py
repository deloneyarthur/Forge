"""Tests for `forge.feedback.threshold_proposer` (D073 / Phase 3)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from crucible_contracts import (
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
)

from forge.feedback.threshold_proposer import (
    ThresholdProposal,
    propose_threshold_tightenings,
    write_loosening_proposals_to_open_proposals,
    write_tightenings_to_yaml,
)
from forge.persistence.db import db_connection


def _gated_run(*, config_hash: str, trade_count: int) -> GatedRun:
    """Minimal GatedRun with a given trade_count for the test."""
    run_id = uuid.uuid4()
    return GatedRun(
        run=RunResult(
            run_id=str(run_id),
            config_hash=config_hash,
            metrics={"n_trades": float(trade_count)},
            trade_count=trade_count,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
        ),
        decision=PromotionDecision(
            run_id=str(run_id),
            decision="reject",
            gate_results={
                "min_oos_trade_count": GateResult(
                    gate_name="min_oos_trade_count",
                    passed=trade_count >= 30,
                    value=float(trade_count),
                    threshold=30.0,
                ),
            },
            decided_at=datetime.now(UTC),
            decided_by="test/v1",
        ),
    )


def _config_json(
    indicator_id: str,
    role: str,
    threshold: float,
    hypothesis: str = "mean_reversion",
) -> str:
    """Minimal config_json with one threshold signal."""
    return json.dumps(
        {
            "name": f"cfg_{indicator_id}_{threshold}",
            "hypothesis": hypothesis,
            "signals": [
                {
                    "id": "sig_directional",
                    "type": "threshold",
                    "role": role,
                    "indicators": [indicator_id],
                    "params": {"threshold": threshold, "op": "<"},
                }
            ],
        }
    )


def _insert_submission(conn: object, *, config_hash: str, config_json: str) -> None:
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            config_json,
            datetime.now(UTC),
            "submitted",
        ],
    )


def test_proposes_tightening_when_high_trade_configs_cluster(tmp_path: Path) -> None:
    """6 high-trade configs use rsi_2 thresholds clustered in [8, 12]. The D031
    baseline is (5.0, 15.0). Proposed range should fit inside that → tighten."""
    forge_db = tmp_path / "forge.db"
    gated = []
    with db_connection(forge_db) as conn:
        # 6 high-trade configs around threshold ~10
        for i, thr in enumerate([8.0, 9.0, 9.5, 10.5, 11.0, 12.0]):
            ch = f"high_{i:03d}"
            cj = _config_json("rsi_2", "directional", thr)
            _insert_submission(conn, config_hash=ch, config_json=cj)
            gated.append(_gated_run(config_hash=ch, trade_count=20))  # high
        # 3 zero-trade configs at extreme thresholds (should NOT bias the proposal)
        for i, thr in enumerate([5.5, 6.0, 14.5]):
            ch = f"zero_{i:03d}"
            cj = _config_json("rsi_2", "directional", thr)
            _insert_submission(conn, config_hash=ch, config_json=cj)
            gated.append(_gated_run(config_hash=ch, trade_count=0))

        baseline = {"rsi_2": (5.0, 15.0, 20.0, 50.0)}
        proposals = propose_threshold_tightenings(
            conn,
            gated,
            baseline_table=baseline,
            high_trade_floor=10,
            min_high_trade_samples=5,
        )

    assert len(proposals) == 1
    p = proposals[0]
    assert p.indicator_id == "rsi_2"
    assert p.role == "directional"
    assert p.direction == "tighten"
    assert p.baseline_low == 5.0
    assert p.baseline_high == 15.0
    # Proposed range should fit inside baseline (tightened)
    assert p.proposed_low >= 5.0
    assert p.proposed_high <= 15.0
    # And should be derived from the high-trade band (8-12), not the extremes
    assert p.proposed_low >= 8.0
    assert p.proposed_high <= 12.0


def test_min_samples_floor_skips_low_evidence(tmp_path: Path) -> None:
    """Fewer than `min_high_trade_samples` configs → no proposal."""
    forge_db = tmp_path / "forge.db"
    gated = []
    with db_connection(forge_db) as conn:
        for i, thr in enumerate([8.0, 10.0]):  # only 2 high-trade samples
            ch = f"h_{i}"
            cj = _config_json("rsi_2", "directional", thr)
            _insert_submission(conn, config_hash=ch, config_json=cj)
            gated.append(_gated_run(config_hash=ch, trade_count=50))

        baseline = {"rsi_2": (5.0, 15.0, 20.0, 50.0)}
        proposals = propose_threshold_tightenings(
            conn,
            gated,
            baseline_table=baseline,
            high_trade_floor=10,
            min_high_trade_samples=5,
        )

    assert proposals == []


def test_loosening_detected_when_high_trade_outside_baseline(tmp_path: Path) -> None:
    """High-trade configs cluster OUTSIDE the D031 baseline → loosen direction."""
    forge_db = tmp_path / "forge.db"
    gated = []
    with db_connection(forge_db) as conn:
        # High-trade thresholds at 18-22 — outside the baseline (5, 15)
        for i, thr in enumerate([18.0, 19.0, 20.0, 21.0, 22.0, 22.5]):
            ch = f"o_{i}"
            cj = _config_json("rsi_2", "directional", thr)
            _insert_submission(conn, config_hash=ch, config_json=cj)
            gated.append(_gated_run(config_hash=ch, trade_count=30))

        baseline = {"rsi_2": (5.0, 15.0, 20.0, 50.0)}
        proposals = propose_threshold_tightenings(
            conn,
            gated,
            baseline_table=baseline,
            high_trade_floor=10,
            min_high_trade_samples=5,
        )

    assert len(proposals) == 1
    assert proposals[0].direction == "loosen"


def test_yaml_writer_only_includes_tightenings(tmp_path: Path) -> None:
    """write_tightenings_to_yaml writes only `direction='tighten'` entries."""
    proposals = [
        ThresholdProposal(
            indicator_id="rsi_2",
            role="directional",
            baseline_low=5.0,
            baseline_high=15.0,
            proposed_low=8.0,
            proposed_high=12.0,
            direction="tighten",
            n_high_trade_samples=6,
            high_trade_floor=10,
            cohort_size=100,
        ),
        ThresholdProposal(
            indicator_id="iv_rank",
            role="regime_filter",
            baseline_low=10.0,
            baseline_high=50.0,
            proposed_low=5.0,
            proposed_high=55.0,  # loosening
            direction="loosen",
            n_high_trade_samples=8,
            high_trade_floor=10,
            cohort_size=100,
        ),
    ]
    out_yaml = tmp_path / "auto_tightened_thresholds.yaml"
    n = write_tightenings_to_yaml(proposals, out_yaml, cohort_size=100)
    assert n == 1
    body = out_yaml.read_text()
    assert "rsi_2" in body
    assert "iv_rank" not in body  # loosening excluded
    assert "tightenings:" in body
    assert "cohort_size: 100" in body


def test_loosening_writer_appends_to_open_proposals(tmp_path: Path) -> None:
    """write_loosening_proposals_to_open_proposals appends a markdown table."""
    proposals = [
        ThresholdProposal(
            indicator_id="iv_rank",
            role="regime_filter",
            baseline_low=10.0,
            baseline_high=50.0,
            proposed_low=5.0,
            proposed_high=55.0,
            direction="loosen",
            n_high_trade_samples=8,
            high_trade_floor=10,
            cohort_size=100,
        ),
        ThresholdProposal(
            indicator_id="rsi_2",
            role="directional",
            baseline_low=5.0,
            baseline_high=15.0,
            proposed_low=8.0,
            proposed_high=12.0,
            direction="tighten",
            n_high_trade_samples=6,
            high_trade_floor=10,
            cohort_size=100,
        ),
    ]
    op_md = tmp_path / "OPEN_PROPOSALS.md"
    op_md.write_text("# existing content\n")
    n = write_loosening_proposals_to_open_proposals(proposals, op_md, cohort_size=100)
    assert n == 1
    body = op_md.read_text()
    assert "# existing content" in body
    assert "iv_rank" in body
    assert "regime_filter" in body
    # Tightening must NOT appear in loosening section
    assert "rsi_2" not in body.split("D073")[1]


def test_empty_gated_runs_returns_no_proposals(tmp_path: Path) -> None:
    """Cold-start path: no gated_runs → no proposals."""
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        proposals = propose_threshold_tightenings(
            conn,
            [],
            baseline_table={"rsi_2": (5.0, 15.0, 20.0, 50.0)},
        )
    assert proposals == []
