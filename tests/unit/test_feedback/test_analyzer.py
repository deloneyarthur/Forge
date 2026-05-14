"""Tests for feedback.analyzer (Phase 5 module 3, D024/D2).

`analyze_batch(feedback, registry) -> AnalysisReport` is a pure function:
no DB writes (those happen in promoted_patterns module). It extracts §8.3
patterns from a BatchFeedback.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from crucible_contracts import (
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
    SignalSpec,
)

from forge.feedback.analyzer import analyze_batch
from forge.feedback.types import BatchFeedback, CandidateOutcome
from tests.fixtures.strategy_configs import minimal_registry_snapshot, minimal_strategy_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gated_run(
    *,
    config_hash: str,
    decision: str = "promote",
    metrics: dict[str, float] | None = None,
    failed_gates: tuple[str, ...] = (),
) -> GatedRun:
    run = RunResult(
        run_id=str(uuid.uuid4()),
        config_hash=config_hash,
        metrics=metrics or {"walk_forward_sharpe_median": 1.2},
        trade_count=80,
        period_start=date(2022, 1, 1),
        period_end=date(2024, 12, 31),
    )
    gates: dict[str, GateResult] = {}
    if failed_gates:
        for g in failed_gates:
            gates[g] = GateResult(gate_name=g, passed=False, value=0.2)
    else:
        gates["sharpe_gate"] = GateResult(gate_name="sharpe_gate", passed=True, value=1.2)
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
    hypothesis: str = "mean_reversion",
    name: str | None = None,
    promote: bool = True,
    failed_gates: tuple[str, ...] = (),
    metrics: dict[str, float] | None = None,
    indicators: tuple[str, ...] = ("rsi_2",),
) -> CandidateOutcome:
    overrides: dict[str, Any] = {"hypothesis": hypothesis}
    if name is not None:
        overrides["name"] = name
    if indicators != ("rsi_2",):
        overrides["signals"] = (
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=indicators,
                params={"threshold": 30.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        )
    cfg = minimal_strategy_config(**overrides)
    gr = _gated_run(
        config_hash=cfg.config_hash,
        decision="promote" if promote else "reject",
        failed_gates=failed_gates,
        metrics=metrics,
    )
    return CandidateOutcome(config=cfg, gated_run=gr)


# ---------------------------------------------------------------------------
# Empty feedback
# ---------------------------------------------------------------------------


def test_analyze_empty_batch_returns_zeros() -> None:
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=0, outcomes=())
    r = analyze_batch(bf, minimal_registry_snapshot())
    assert r.promotion_rate == 0.0
    assert r.gate_failures == ()
    assert r.hypothesis_metrics == ()
    assert r.promoted_patterns == ()


def test_analyze_promotion_rate_matches_feedback() -> None:
    out = _outcome(promote=True)
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=2, outcomes=(out,))
    r = analyze_batch(bf, minimal_registry_snapshot())
    assert r.promotion_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Gate failure breakdown
# ---------------------------------------------------------------------------


def test_analyze_aggregates_gate_failures_across_rejected_outcomes() -> None:
    o1 = _outcome(name="r1", promote=False, failed_gates=("sharpe_gate", "trade_count_gate"))
    o2 = _outcome(name="r2", promote=False, failed_gates=("sharpe_gate",))
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=2, outcomes=(o1, o2))
    r = analyze_batch(bf, minimal_registry_snapshot())
    gate_counts = {row.gate_name: row.failure_count for row in r.gate_failures}
    assert gate_counts["sharpe_gate"] == 2
    assert gate_counts["trade_count_gate"] == 1


def test_analyze_gate_failure_rate_is_share_of_rejected() -> None:
    o1 = _outcome(name="r1", promote=False, failed_gates=("sharpe_gate",))
    o2 = _outcome(name="r2", promote=False, failed_gates=("sharpe_gate",))
    o3 = _outcome(name="p1", promote=True)
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=3, outcomes=(o1, o2, o3))
    r = analyze_batch(bf, minimal_registry_snapshot())
    sharpe_row = next(row for row in r.gate_failures if row.gate_name == "sharpe_gate")
    # 2 sharpe failures / 2 rejected
    assert sharpe_row.failure_rate == pytest.approx(1.0)


def test_analyze_skips_promoted_outcomes_in_gate_failures() -> None:
    p = _outcome(promote=True)
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=1, outcomes=(p,))
    r = analyze_batch(bf, minimal_registry_snapshot())
    assert r.gate_failures == ()


# ---------------------------------------------------------------------------
# Hypothesis metrics
# ---------------------------------------------------------------------------


def test_analyze_groups_by_hypothesis() -> None:
    outcomes = (
        _outcome(hypothesis="mean_reversion", name="m1", promote=True),
        _outcome(hypothesis="mean_reversion", name="m2", promote=False),
        _outcome(hypothesis="trend_continuation", name="t1", promote=True),
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=3, outcomes=outcomes)
    r = analyze_batch(bf, minimal_registry_snapshot())
    by_h = {row.hypothesis: row for row in r.hypothesis_metrics}
    assert by_h["mean_reversion"].sample_size == 2
    assert by_h["mean_reversion"].promotion_rate == pytest.approx(0.5)
    assert by_h["trend_continuation"].sample_size == 1
    assert by_h["trend_continuation"].promotion_rate == pytest.approx(1.0)


def test_analyze_avg_sharpe_computed_from_metrics() -> None:
    outcomes = (
        _outcome(name="o1", promote=True, metrics={"walk_forward_sharpe_median": 1.0}),
        _outcome(name="o2", promote=True, metrics={"walk_forward_sharpe_median": 2.0}),
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=2, outcomes=outcomes)
    r = analyze_batch(bf, minimal_registry_snapshot())
    row = next(iter(r.hypothesis_metrics))
    assert row.avg_sharpe == pytest.approx(1.5)


def test_analyze_avg_sharpe_none_when_no_metric() -> None:
    out = _outcome(metrics={"some_other_metric": 1.0})
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=1, outcomes=(out,))
    r = analyze_batch(bf, minimal_registry_snapshot())
    row = next(iter(r.hypothesis_metrics))
    assert row.avg_sharpe is None


# ---------------------------------------------------------------------------
# Promoted-pattern extraction — hypothesis dominance
# ---------------------------------------------------------------------------


def test_analyze_detects_hypothesis_dominance_at_100pct() -> None:
    outcomes = tuple(
        _outcome(hypothesis="mean_reversion", name=f"o{i}", promote=True) for i in range(4)
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=4, outcomes=outcomes)
    r = analyze_batch(bf, minimal_registry_snapshot())
    patterns = [p for p in r.promoted_patterns if p.pattern_type == "hypothesis_dominance"]
    assert len(patterns) == 1
    assert patterns[0].pattern["hypothesis"] == "mean_reversion"
    assert patterns[0].dominance_rate == pytest.approx(1.0)


def test_analyze_no_hypothesis_dominance_below_threshold() -> None:
    outcomes = (
        _outcome(hypothesis="mean_reversion", name="m1", promote=True),
        _outcome(hypothesis="trend_continuation", name="t1", promote=True),
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=2, outcomes=outcomes)
    r = analyze_batch(bf, minimal_registry_snapshot())
    patterns = [p for p in r.promoted_patterns if p.pattern_type == "hypothesis_dominance"]
    assert patterns == []


def test_analyze_no_patterns_when_no_promoted() -> None:
    out = _outcome(promote=False, failed_gates=("sharpe_gate",))
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=1, outcomes=(out,))
    r = analyze_batch(bf, minimal_registry_snapshot())
    assert r.promoted_patterns == ()


# ---------------------------------------------------------------------------
# Promoted-pattern extraction — signal family dominance
# ---------------------------------------------------------------------------


def test_analyze_detects_signal_family_dominance() -> None:
    # All promoted outcomes use rsi_2 (mean_reversion family per fixture registry)
    outcomes = tuple(_outcome(name=f"mr{i}", promote=True, indicators=("rsi_2",)) for i in range(3))
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=3, outcomes=outcomes)
    r = analyze_batch(bf, minimal_registry_snapshot())
    fam_patterns = [p for p in r.promoted_patterns if p.pattern_type == "signal_family_dominance"]
    assert len(fam_patterns) >= 1
    # The dominant family is whatever family rsi_2 is in the fixture registry
    assert "family" in fam_patterns[0].pattern


def test_analyze_pattern_json_roundtrips() -> None:
    outcomes = tuple(
        _outcome(hypothesis="mean_reversion", name=f"o{i}", promote=True) for i in range(2)
    )
    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=2, outcomes=outcomes)
    r = analyze_batch(bf, minimal_registry_snapshot())
    # Every pattern dict must JSON-serialize (it goes into promoted_patterns.pattern_json)
    for p in r.promoted_patterns:
        json.dumps(p.pattern)
