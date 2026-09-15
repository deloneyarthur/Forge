"""Tests for feedback.types — the two reconcile-path value types that survived Batch 5 G3."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from forge.feedback.types import BatchFeedback, CandidateOutcome

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _gated_run(*, run_id: str = "r1", config_hash: str = "h1", promote: bool = True) -> Any:
    from datetime import date

    from crucible_contracts import (
        GatedRun,
        GateResult,
        PromotionDecision,
        RunResult,
    )

    run = RunResult(
        run_id=run_id,
        config_hash=config_hash,
        metrics={"walk_forward_sharpe_median": 1.2},
        trade_count=80,
        period_start=date(2022, 1, 1),
        period_end=date(2024, 12, 31),
    )
    if promote:
        gates = {"sharpe_gate": GateResult(gate_name="sharpe_gate", passed=True, value=1.2)}
        decision = PromotionDecision(
            run_id=run_id,
            decision="promote",
            gate_results=gates,
            decided_at=datetime(2026, 5, 13, tzinfo=UTC),
            decided_by="gate_v1",
        )
    else:
        gates = {"sharpe_gate": GateResult(gate_name="sharpe_gate", passed=False, value=0.4)}
        decision = PromotionDecision(
            run_id=run_id,
            decision="reject",
            gate_results=gates,
            decided_at=datetime(2026, 5, 13, tzinfo=UTC),
            decided_by="gate_v1",
        )
    return GatedRun(run=run, decision=decision)


def _strategy_config() -> Any:
    from tests.fixtures.strategy_configs import minimal_strategy_config

    return minimal_strategy_config()


# ---------------------------------------------------------------------------
# CandidateOutcome
# ---------------------------------------------------------------------------


def test_candidate_outcome_carries_config_and_gated_run() -> None:
    cfg = _strategy_config()
    gr = _gated_run(config_hash=cfg.config_hash)
    co = CandidateOutcome(config=cfg, gated_run=gr)
    assert co.config_hash == cfg.config_hash
    assert co.promoted is True


def test_candidate_outcome_promoted_false_when_rejected() -> None:
    cfg = _strategy_config()
    gr = _gated_run(config_hash=cfg.config_hash, promote=False)
    co = CandidateOutcome(config=cfg, gated_run=gr)
    assert co.promoted is False


def test_candidate_outcome_rejects_mismatched_hashes() -> None:
    cfg = _strategy_config()
    gr = _gated_run(config_hash="some_other_hash")
    with pytest.raises(ValueError, match="config_hash"):
        CandidateOutcome(config=cfg, gated_run=gr)


def test_candidate_outcome_is_frozen() -> None:
    cfg = _strategy_config()
    gr = _gated_run(config_hash=cfg.config_hash)
    co = CandidateOutcome(config=cfg, gated_run=gr)
    with pytest.raises(AttributeError):
        co.config = cfg  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BatchFeedback
# ---------------------------------------------------------------------------


def test_batch_feedback_computes_counts_from_outcomes() -> None:
    cfg = _strategy_config()
    promoted = CandidateOutcome(config=cfg, gated_run=_gated_run(config_hash=cfg.config_hash))
    rejected = CandidateOutcome(
        config=cfg,
        gated_run=_gated_run(config_hash=cfg.config_hash, run_id="r2", promote=False),
    )
    bf = BatchFeedback(
        batch_id=uuid.uuid4(),
        submitted_count=10,
        outcomes=(promoted, rejected),
    )
    assert bf.gated_count == 2
    assert bf.promoted_count == 1
    assert bf.rejected_count == 1
    assert bf.pending_count == 8


def test_batch_feedback_with_no_outcomes() -> None:
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=5, outcomes=())
    assert bf.gated_count == 0
    assert bf.pending_count == 5
    assert bf.promotion_rate == 0.0


def test_batch_feedback_promotion_rate_is_promoted_over_submitted() -> None:
    cfg = _strategy_config()
    promoted = CandidateOutcome(config=cfg, gated_run=_gated_run(config_hash=cfg.config_hash))
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=10, outcomes=(promoted,))
    assert bf.promotion_rate == pytest.approx(0.10)


def test_batch_feedback_rejects_negative_submitted_count() -> None:
    with pytest.raises(ValueError, match="submitted_count"):
        BatchFeedback(batch_id=uuid.uuid4(), submitted_count=-1, outcomes=())


def test_batch_feedback_rejects_more_gated_than_submitted() -> None:
    cfg = _strategy_config()
    outcomes = tuple(
        CandidateOutcome(
            config=cfg,
            gated_run=_gated_run(config_hash=cfg.config_hash, run_id=f"r{i}"),
        )
        for i in range(5)
    )
    with pytest.raises(ValueError, match="submitted_count"):
        BatchFeedback(batch_id=uuid.uuid4(), submitted_count=3, outcomes=outcomes)
