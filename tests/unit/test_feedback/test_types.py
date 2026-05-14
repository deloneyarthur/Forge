"""Tests for feedback.types (Phase 5 module 1, D024/D11).

Frozen dataclasses with slots and explicit validation. Each type pairs to
its consumer/analyzer/proposer downstream module.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from forge.feedback.types import (
    AnalysisReport,
    BatchFeedback,
    CandidateOutcome,
    GateFailureRow,
    GrammarProposal,
    HypothesisMetrics,
    PromotedPattern,
    Trigger,
)

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


# ---------------------------------------------------------------------------
# GateFailureRow
# ---------------------------------------------------------------------------


def test_gate_failure_row_unit_interval() -> None:
    row = GateFailureRow(gate_name="sharpe_gate", failure_count=18, failure_rate=0.9)
    assert row.failure_rate == 0.9


def test_gate_failure_row_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="failure_rate"):
        GateFailureRow(gate_name="sharpe_gate", failure_count=1, failure_rate=1.5)


def test_gate_failure_row_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="failure_count"):
        GateFailureRow(gate_name="sharpe_gate", failure_count=-1, failure_rate=0.1)


def test_gate_failure_row_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="gate_name"):
        GateFailureRow(gate_name="", failure_count=1, failure_rate=0.1)


# ---------------------------------------------------------------------------
# HypothesisMetrics
# ---------------------------------------------------------------------------


def test_hypothesis_metrics_allows_none_sharpe() -> None:
    m = HypothesisMetrics(
        hypothesis="trend_continuation",
        sample_size=20,
        promotion_rate=0.10,
        avg_sharpe=None,
    )
    assert m.avg_sharpe is None


def test_hypothesis_metrics_rejects_nan_sharpe() -> None:
    with pytest.raises(ValueError, match="avg_sharpe"):
        HypothesisMetrics(
            hypothesis="trend_continuation",
            sample_size=20,
            promotion_rate=0.10,
            avg_sharpe=math.nan,
        )


def test_hypothesis_metrics_rejects_empty_hypothesis() -> None:
    with pytest.raises(ValueError, match="hypothesis"):
        HypothesisMetrics(hypothesis="", sample_size=10, promotion_rate=0.1, avg_sharpe=None)


# ---------------------------------------------------------------------------
# PromotedPattern
# ---------------------------------------------------------------------------


def test_promoted_pattern_carries_pattern_json() -> None:
    p = PromotedPattern(
        pattern_type="hypothesis_dominance",
        pattern={"hypothesis": "mean_reversion"},
        promoted_count=8,
        sample_size=20,
    )
    assert p.dominance_rate == pytest.approx(0.40)


def test_promoted_pattern_rejects_promoted_exceeds_sample() -> None:
    with pytest.raises(ValueError, match="promoted_count"):
        PromotedPattern(
            pattern_type="hypothesis_dominance",
            pattern={"hypothesis": "mean_reversion"},
            promoted_count=11,
            sample_size=10,
        )


def test_promoted_pattern_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="pattern_type"):
        PromotedPattern(
            pattern_type="surprise_thing",  # type: ignore[arg-type]
            pattern={},
            promoted_count=1,
            sample_size=2,
        )


# ---------------------------------------------------------------------------
# AnalysisReport
# ---------------------------------------------------------------------------


def test_analysis_report_aggregates_subreports() -> None:
    r = AnalysisReport(
        batch_id=uuid.uuid4(),
        promotion_rate=0.05,
        gate_failures=(GateFailureRow(gate_name="g1", failure_count=10, failure_rate=0.5),),
        hypothesis_metrics=(
            HypothesisMetrics(
                hypothesis="trend_continuation",
                sample_size=10,
                promotion_rate=0.1,
                avg_sharpe=1.0,
            ),
        ),
        promoted_patterns=(),
    )
    assert r.promotion_rate == 0.05
    assert len(r.gate_failures) == 1


def test_analysis_report_promotion_rate_in_unit_interval() -> None:
    with pytest.raises(ValueError, match="promotion_rate"):
        AnalysisReport(
            batch_id=uuid.uuid4(),
            promotion_rate=1.5,
            gate_failures=(),
            hypothesis_metrics=(),
            promoted_patterns=(),
        )


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------


def test_trigger_carries_threshold_observed_target() -> None:
    t = Trigger(
        kind="gate_failure_concentration",
        target="sharpe_gate",
        threshold=0.95,
        observed=0.97,
    )
    assert t.kind == "gate_failure_concentration"
    assert t.observed >= t.threshold


def test_trigger_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        Trigger(kind="other", target="x", threshold=0.0, observed=0.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GrammarProposal
# ---------------------------------------------------------------------------


def test_grammar_proposal_serializes_via_evidence_json() -> None:
    pid = uuid.uuid4()
    p = GrammarProposal(
        proposal_id=pid,
        proposed_at=datetime(2026, 5, 13, tzinfo=UTC),
        proposal_type="tighten",
        target="grammar",
        proposal_yaml="rules:\n  - id: P4_v2\n",
        rationale="0/200 promoted with dte_bucket=long",
        evidence_json={"trigger": "param_no_promotion", "target": "dte_bucket"},
    )
    assert p.proposal_id == pid
    assert p.is_loosen is False


def test_grammar_proposal_is_loosen_for_remove_rule() -> None:
    p = GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=datetime(2026, 5, 13, tzinfo=UTC),
        proposal_type="remove_rule",
        target="grammar",
        proposal_yaml="rules:\n  - id: C1\n    active: false\n",
        rationale="C1 rejects 35% of high-pre-filter-score candidates",
        evidence_json={},
    )
    assert p.is_loosen is True


def test_grammar_proposal_is_loosen_for_loosen() -> None:
    p = GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=datetime(2026, 5, 13, tzinfo=UTC),
        proposal_type="loosen",
        target="prefilter_calibration",
        proposal_yaml="",
        rationale="rate <0.5% for 2 batches",
        evidence_json={},
    )
    assert p.is_loosen is True


def test_grammar_proposal_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="proposed_at"):
        GrammarProposal(
            proposal_id=uuid.uuid4(),
            proposed_at=datetime(2026, 5, 13),  # noqa: DTZ001 — intentional naive datetime
            proposal_type="tighten",
            target="grammar",
            proposal_yaml="",
            rationale="r",
            evidence_json={},
        )


def test_grammar_proposal_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="proposal_type"):
        GrammarProposal(
            proposal_id=uuid.uuid4(),
            proposed_at=datetime(2026, 5, 13, tzinfo=UTC),
            proposal_type="bogus",  # type: ignore[arg-type]
            target="grammar",
            proposal_yaml="",
            rationale="r",
            evidence_json={},
        )


def test_grammar_proposal_rejects_unknown_target() -> None:
    with pytest.raises(ValueError, match="target"):
        GrammarProposal(
            proposal_id=uuid.uuid4(),
            proposed_at=datetime(2026, 5, 13, tzinfo=UTC),
            proposal_type="tighten",
            target="bogus",  # type: ignore[arg-type]
            proposal_yaml="",
            rationale="r",
            evidence_json={},
        )
