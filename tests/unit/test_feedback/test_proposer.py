"""Tests for feedback.proposer (Phase 5 module 5, D024/D3).

`propose(report, feedback, *, at)` fires three §8.4 triggers:
  (a) gate-failure concentration: 95%+ rejected by one gate
  (b) family/hypothesis dominance: 80%+ promoted share one trait
  (c) param no-promotion: cell with N+ samples and 0 promotions

Trigger (c) operates on the current batch for Phase 5 (DESIGN.md §8.4's
"200+ submissions" is the spirit; the multi-batch query is Phase 6).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from crucible_contracts import (
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
)

from forge.feedback.proposer import propose
from forge.feedback.types import (
    AnalysisReport,
    BatchFeedback,
    CandidateOutcome,
    GateFailureRow,
    HypothesisMetrics,
    PromotedPattern,
)
from tests.fixtures.strategy_configs import minimal_strategy_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_AT = datetime(2026, 5, 13, 12, tzinfo=UTC)


def _gated_run(*, config_hash: str, decision: str, failed_gates: tuple[str, ...] = ()) -> GatedRun:
    run = RunResult(
        run_id=str(uuid.uuid4()),
        config_hash=config_hash,
        metrics={"walk_forward_sharpe_median": 1.2},
        trade_count=80,
        period_start=date(2022, 1, 1),
        period_end=date(2024, 12, 31),
    )
    if failed_gates:
        gates = {g: GateResult(gate_name=g, passed=False, value=0.2) for g in failed_gates}
    else:
        gates = {"sharpe_gate": GateResult(gate_name="sharpe_gate", passed=True, value=1.2)}
    pd_ = PromotionDecision(
        run_id=run.run_id,
        decision=decision,  # type: ignore[arg-type]
        gate_results=gates,
        decided_at=datetime(2026, 5, 13, tzinfo=UTC),
        decided_by="gate_v1",
    )
    return GatedRun(run=run, decision=pd_)


def _outcome(
    *,
    name: str | None = None,
    hypothesis: str = "mean_reversion",
    dte_bucket: str = "swing_short",
    promote: bool = True,
    failed_gates: tuple[str, ...] = (),
) -> CandidateOutcome:
    overrides: dict[str, Any] = {"hypothesis": hypothesis, "dte_bucket": dte_bucket}
    if name is not None:
        overrides["name"] = name
    cfg = minimal_strategy_config(**overrides)
    gr = _gated_run(
        config_hash=cfg.config_hash,
        decision="promote" if promote else "reject",
        failed_gates=failed_gates,
    )
    return CandidateOutcome(config=cfg, gated_run=gr)


def _report(
    *,
    gate_failures: tuple[GateFailureRow, ...] = (),
    hypothesis_metrics: tuple[HypothesisMetrics, ...] = (),
    promoted_patterns: tuple[PromotedPattern, ...] = (),
    promotion_rate: float = 0.0,
) -> AnalysisReport:
    return AnalysisReport(
        batch_id=uuid.uuid4(),
        promotion_rate=promotion_rate,
        gate_failures=gate_failures,
        hypothesis_metrics=hypothesis_metrics,
        promoted_patterns=promoted_patterns,
    )


# ---------------------------------------------------------------------------
# Empty input → empty proposals
# ---------------------------------------------------------------------------


def test_propose_empty_report_returns_no_proposals() -> None:
    report = _report()
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=0, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    assert proposals == []


# ---------------------------------------------------------------------------
# Trigger (a) — gate failure concentration
# ---------------------------------------------------------------------------


def test_trigger_a_fires_at_95pct_gate_concentration() -> None:
    failures = (GateFailureRow(gate_name="sharpe_gate", failure_count=19, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=20, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    sharpe = [p for p in proposals if "sharpe_gate" in p.evidence_json.get("target", "")]
    assert len(sharpe) == 1
    assert sharpe[0].proposal_type == "tighten"
    assert sharpe[0].target == "prefilter_calibration"
    assert sharpe[0].is_loosen is False


def test_trigger_a_does_not_fire_below_threshold() -> None:
    failures = (GateFailureRow(gate_name="sharpe_gate", failure_count=18, failure_rate=0.90),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=20, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    assert proposals == []


# ---------------------------------------------------------------------------
# Trigger (b) — family / hypothesis dominance
# ---------------------------------------------------------------------------


def test_trigger_b_fires_on_hypothesis_dominance_pattern() -> None:
    pattern = PromotedPattern(
        pattern_type="hypothesis_dominance",
        pattern={"hypothesis": "mean_reversion"},
        promoted_count=8,
        sample_size=8,
    )
    report = _report(promoted_patterns=(pattern,))
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=8, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    p = next(p for p in proposals if "hypothesis" in p.evidence_json)
    assert p.proposal_type == "tighten"


def test_trigger_b_fires_on_family_dominance_pattern() -> None:
    pattern = PromotedPattern(
        pattern_type="signal_family_dominance",
        pattern={"family": "mean_reversion"},
        promoted_count=8,
        sample_size=8,
    )
    report = _report(promoted_patterns=(pattern,))
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=8, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    p = next(p for p in proposals if p.target == "ranker_weights")
    assert p.proposal_type == "tighten"
    assert p.evidence_json["family"] == "mean_reversion"


def test_trigger_b_does_not_fire_below_min_promoted() -> None:
    pattern = PromotedPattern(
        pattern_type="hypothesis_dominance",
        pattern={"hypothesis": "mean_reversion"},
        promoted_count=2,  # below default min (4)
        sample_size=2,
    )
    report = _report(promoted_patterns=(pattern,))
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=2, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    # No trigger-b proposals; pattern-driven ones look for hypothesis or family
    assert proposals == []


# ---------------------------------------------------------------------------
# Trigger (c) — param no-promotion
# ---------------------------------------------------------------------------


def test_trigger_c_fires_when_cell_has_zero_promotions(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lower the threshold for this test
    from forge.feedback import proposer as proposer_mod

    monkeypatch.setattr(proposer_mod, "_PARAM_NO_PROMOTION_MIN_SAMPLES", 5)
    # 5 mean_reversion / swing_short outcomes, 0 promoted
    outcomes = tuple(
        _outcome(
            name=f"r{i}",
            hypothesis="mean_reversion",
            dte_bucket="swing_short",
            promote=False,
            failed_gates=("sharpe_gate",),
        )
        for i in range(5)
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=5, outcomes=outcomes)
    report = _report()
    proposals = propose(report, bf, at=_AT)
    c_props = [p for p in proposals if p.evidence_json.get("trigger") == "param_no_promotion"]
    assert len(c_props) >= 1
    assert c_props[0].proposal_type == "tighten"
    assert c_props[0].target == "grammar"


def test_trigger_c_does_not_fire_when_cell_has_at_least_one_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forge.feedback import proposer as proposer_mod

    monkeypatch.setattr(proposer_mod, "_PARAM_NO_PROMOTION_MIN_SAMPLES", 5)
    outcomes = (
        *(
            _outcome(
                name=f"r{i}",
                promote=False,
                failed_gates=("sharpe_gate",),
            )
            for i in range(4)
        ),
        _outcome(name="p1", promote=True),
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=5, outcomes=outcomes)
    report = _report()
    proposals = propose(report, bf, at=_AT)
    c_props = [p for p in proposals if p.evidence_json.get("trigger") == "param_no_promotion"]
    assert c_props == []


def test_trigger_c_skips_cells_below_min_samples() -> None:
    # Default min-samples is 200; with 5 outcomes nothing should fire
    outcomes = tuple(
        _outcome(name=f"r{i}", promote=False, failed_gates=("sharpe_gate",)) for i in range(5)
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=5, outcomes=outcomes)
    report = _report()
    proposals = propose(report, bf, at=_AT)
    c_props = [p for p in proposals if p.evidence_json.get("trigger") == "param_no_promotion"]
    assert c_props == []


# ---------------------------------------------------------------------------
# Proposal shape — every proposal is loosen=False, has rationale
# ---------------------------------------------------------------------------


def test_all_proposals_are_tighten_direction() -> None:
    """Phase 5 proposer fires only tighten triggers; loosening is reserved
    for the auto_tune module (calibration loosening). This is the
    structural enforcement of hard rule #4 at the proposer level."""
    failures = (GateFailureRow(gate_name="sharpe_gate", failure_count=19, failure_rate=0.95),)
    pattern = PromotedPattern(
        pattern_type="hypothesis_dominance",
        pattern={"hypothesis": "mean_reversion"},
        promoted_count=8,
        sample_size=8,
    )
    report = _report(gate_failures=failures, promoted_patterns=(pattern,))
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=20, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    assert proposals, "expected at least one proposal in this fixture"
    assert all(p.is_loosen is False for p in proposals)


def test_proposal_rationale_is_non_empty() -> None:
    failures = (GateFailureRow(gate_name="sharpe_gate", failure_count=19, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=20, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    assert all(p.rationale for p in proposals)


# ---------------------------------------------------------------------------
# tz-aware guard
# ---------------------------------------------------------------------------


def test_propose_rejects_naive_at() -> None:
    report = _report()
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=0, outcomes=())
    with pytest.raises(ValueError, match="timezone-aware"):
        propose(
            report,
            feedback,
            at=datetime(2026, 5, 13),  # noqa: DTZ001 — intentional naive
        )
