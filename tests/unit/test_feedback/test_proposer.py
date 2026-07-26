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
    # D034 guard: trigger only fires when there's at least one promotion in
    # the batch (otherwise every gate has 100% failure rate against rejects
    # and the signal is degenerate).
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=20,
        outcomes=(_outcome(promote=True),),
    )
    proposals = propose(report, feedback, at=_AT)
    sharpe = [p for p in proposals if "sharpe_gate" in p.evidence_json.get("target", "")]
    assert len(sharpe) == 1
    assert sharpe[0].proposal_type == "tighten"
    assert sharpe[0].target == "prefilter_calibration"
    assert sharpe[0].is_loosen is False


def test_trigger_a_suppressed_when_zero_promotions() -> None:
    """D034: gate-failure trigger is suppressed when promoted_count == 0.

    Reasoning: in a 0-promotion regime EVERY gate fails 100% of rejects
    (because EVERY candidate is rejected). The "tighten the pre-filter for
    gate X" signal becomes degenerate noise — there's nothing to compare
    against to identify which gate is actually the weakest. Pre-D034 this
    flooded OPEN_PROPOSALS.md with one proposal per gate per batch in any
    stretch where the pipeline hadn't found a promotable strategy yet.
    """
    failures = (
        GateFailureRow(gate_name="sharpe_gate", failure_count=19, failure_rate=0.95),
        GateFailureRow(gate_name="trade_count_gate", failure_count=19, failure_rate=0.95),
    )
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=20, outcomes=())
    proposals = propose(report, feedback, at=_AT)
    # No proposals from trigger (a). Other triggers may still fire (none here).
    assert all(p.evidence_json.get("trigger") != "gate_failure_concentration" for p in proposals)


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
    # 5 mean_reversion / swing_short outcomes, 0 promoted -- PLUS a promotion in a
    # DIFFERENT cell, so the batch clears the Q58 guard below and the zero is
    # informative rather than the regime-wide default.
    outcomes = (
        *(
            _outcome(
                name=f"r{i}",
                hypothesis="mean_reversion",
                dte_bucket="swing_short",
                promote=False,
                failed_gates=("sharpe_gate",),
            )
            for i in range(5)
        ),
        _outcome(name="p_other", hypothesis="trend_continuation", dte_bucket="swing_long"),
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=6, outcomes=outcomes)
    report = _report()
    proposals = propose(report, bf, at=_AT)
    c_props = [p for p in proposals if p.evidence_json.get("trigger") == "param_no_promotion"]
    assert len(c_props) >= 1
    assert c_props[0].proposal_type == "tighten"
    assert c_props[0].target == "grammar"


def test_trigger_c_is_guarded_off_in_a_zero_promotion_regime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Q58: a promotion-denominator trigger is meaningless while NOTHING promotes.

    Live ledger 2026-07-25: 4 promotions against ~428k verdicts, so the expected
    promotion count at the 200-sample threshold is ~0.002 and observing zero is the
    expected outcome for EVERY cell. The trigger then measures sample size, not
    quality -- and it duly fired on `(trend_continuation, swing_mid)`, the
    highest-weighted converting cell in the same batch's own learned weights.
    Same degeneracy and same fix as D034's `gate_failure_concentration` guard.
    """
    from forge.feedback import proposer as proposer_mod

    monkeypatch.setattr(proposer_mod, "_PARAM_NO_PROMOTION_MIN_SAMPLES", 5)
    outcomes = tuple(
        _outcome(
            name=f"r{i}",
            hypothesis="trend_continuation",
            dte_bucket="swing_mid",
            promote=False,
            failed_gates=("sharpe_gate",),
        )
        for i in range(5)
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=5, outcomes=outcomes)
    assert bf.promoted_count == 0
    proposals = propose(_report(), bf, at=_AT)
    c_props = [p for p in proposals if p.evidence_json.get("trigger") == "param_no_promotion"]
    assert c_props == []


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


# ---------------------------------------------------------------------------
# T2.1 / D041 — confidence-weighted proposals
# ---------------------------------------------------------------------------


def test_t21_compute_confidence_step_function() -> None:
    """T2.1: confidence step function — <20 = 0.1, 100 = 0.7, 500 = 1.0."""
    from forge.feedback.proposer import compute_confidence

    assert compute_confidence(0) == 0.1
    assert compute_confidence(19) == 0.1
    assert compute_confidence(20) == pytest.approx(0.3, abs=1e-9)
    assert compute_confidence(100) == pytest.approx(0.7, abs=1e-9)
    assert compute_confidence(500) == pytest.approx(1.0, abs=1e-9)
    assert compute_confidence(1000) == 1.0


def test_t21_compute_confidence_rejects_negative() -> None:
    from forge.feedback.proposer import compute_confidence

    with pytest.raises(ValueError, match="sample_size"):
        compute_confidence(-1)


def test_t21_proposal_carries_sample_size_and_confidence() -> None:
    """T2.1: every proposer-emitted proposal exposes sample_size + confidence."""
    failures = (GateFailureRow(gate_name="sharpe_gate", failure_count=300, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=400,
        outcomes=(_outcome(promote=True),),
    )
    proposals = propose(report, feedback, at=_AT)
    assert len(proposals) >= 1
    p = proposals[0]
    assert p.sample_size == 300
    # confidence(300) is in the [0.7, 1.0] band per the step function
    assert 0.7 <= p.confidence <= 1.0
    # Also stored in evidence_json for downstream consumers
    assert p.evidence_json["sample_size"] == 300
    assert p.evidence_json["confidence"] == p.confidence


# ---------------------------------------------------------------------------
# T2.3 / D044 — counterfactual evaluation
# ---------------------------------------------------------------------------


def test_t23_counterfactual_safe_when_no_recent_promotions() -> None:
    """T2.3: 0 recent promotions → rejection_rate=0, safe to auto-apply."""
    from forge.feedback.proposer import evaluate_counterfactual

    failures = (GateFailureRow(gate_name="x", failure_count=300, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=400,
        outcomes=(_outcome(promote=True),),
    )
    p = propose(report, feedback, at=_AT)[0]
    cf = evaluate_counterfactual(p, recent_promoted_count=0)
    assert cf.rejection_rate == 0.0
    assert cf.promoted_count == 0


def test_t23_counterfactual_conservative_when_promotions_exist() -> None:
    """T2.3 phase-1: any recent promotions → 1.0 rejection_rate (worst-case)."""
    from forge.feedback.proposer import evaluate_counterfactual

    failures = (GateFailureRow(gate_name="x", failure_count=300, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=400,
        outcomes=(_outcome(promote=True),),
    )
    p = propose(report, feedback, at=_AT)[0]
    cf = evaluate_counterfactual(p, recent_promoted_count=5)
    assert cf.rejection_rate == 1.0
    assert cf.would_be_rejected_count == 5


# ---------------------------------------------------------------------------
# D053 — counterfactual phase labeling (P1-1 honesty fix)
# ---------------------------------------------------------------------------


def test_d053_counterfactual_result_carries_phase_field() -> None:
    """D053: `CounterfactualResult` carries a `phase` field so consumers can
    distinguish the phase-1 binary safety floor (the current stub) from a
    future per-strategy re-validation. Defaults to `PHASE_1_BINARY` so
    existing call sites stay valid."""
    from forge.feedback.proposer import (
        PHASE_1_BINARY,
        CounterfactualResult,
    )

    cf = CounterfactualResult(promoted_count=0, would_be_rejected_count=0, rejection_rate=0.0)
    assert cf.phase == PHASE_1_BINARY


def test_d053_evaluate_counterfactual_marks_phase_1() -> None:
    """D053: `evaluate_counterfactual` (still the binary safety floor)
    stamps `phase == PHASE_1_BINARY` so the call site has structured data
    to write to evidence_json. When the per-strategy implementation lands
    later, only the function body changes — the field already exists."""
    from forge.feedback.proposer import PHASE_1_BINARY, evaluate_counterfactual

    failures = (GateFailureRow(gate_name="x", failure_count=300, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=400,
        outcomes=(_outcome(promote=True),),
    )
    p = propose(report, feedback, at=_AT)[0]
    cf_safe = evaluate_counterfactual(p, recent_promoted_count=0)
    cf_conservative = evaluate_counterfactual(p, recent_promoted_count=5)
    assert cf_safe.phase == PHASE_1_BINARY
    assert cf_conservative.phase == PHASE_1_BINARY


# ---------------------------------------------------------------------------
# T2.4 / D045 — persistent proposal detection
# ---------------------------------------------------------------------------


def test_t24_persistent_detection_finds_recurring_theme() -> None:
    """T2.4: 3 proposals with same (trigger, target) → 1 PersistentProposal."""
    from forge.feedback.proposer import detect_persistent_proposals

    failures = (GateFailureRow(gate_name="sharpe", failure_count=200, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=300,
        outcomes=(_outcome(promote=True),),
    )
    # Generate 3 proposals (same trigger + target each time)
    proposals = [propose(report, feedback, at=_AT)[0] for _ in range(3)]
    persistent = detect_persistent_proposals(proposals)
    assert len(persistent) == 1
    assert persistent[0].occurrence_count == 3
    assert persistent[0].theme_trigger == "gate_failure_concentration"
    assert persistent[0].theme_detail == "sharpe"


def test_t24_persistent_detection_below_threshold_returns_empty() -> None:
    """T2.4: 2 occurrences with default threshold=3 → no persistent flag."""
    from forge.feedback.proposer import detect_persistent_proposals

    failures = (GateFailureRow(gate_name="sharpe", failure_count=200, failure_rate=0.95),)
    report = _report(gate_failures=failures)
    feedback = BatchFeedback(
        batch_id=report.batch_id,
        submitted_count=300,
        outcomes=(_outcome(promote=True),),
    )
    proposals = [propose(report, feedback, at=_AT)[0] for _ in range(2)]
    persistent = detect_persistent_proposals(proposals)
    assert len(persistent) == 0


def test_t24_persistent_detection_distinguishes_themes() -> None:
    """Different (trigger, target) tuples → separate themes; only those
    reaching threshold are flagged."""
    from forge.feedback.proposer import detect_persistent_proposals

    failures_a = (GateFailureRow(gate_name="sharpe", failure_count=200, failure_rate=0.95),)
    failures_b = (GateFailureRow(gate_name="profit_factor", failure_count=200, failure_rate=0.95),)
    feedback = BatchFeedback(
        batch_id=_report().batch_id,
        submitted_count=300,
        outcomes=(_outcome(promote=True),),
    )
    # 3 sharpe + 1 profit_factor; only sharpe reaches threshold
    proposals = [
        *(propose(_report(gate_failures=failures_a), feedback, at=_AT)[0] for _ in range(3)),
        propose(_report(gate_failures=failures_b), feedback, at=_AT)[0],
    ]
    persistent = detect_persistent_proposals(proposals)
    assert len(persistent) == 1
    assert persistent[0].theme_detail == "sharpe"
