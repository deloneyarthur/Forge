"""Tests for the joint-quality term in the component-rate reward (D114).

The verdicts-table analysis behind OPEN_QUESTIONS Q32 (2026-06-09) showed the
binary component event is both SLOW (2.4% base rate) and, since Crucible began
enforcing ``regime_coverage`` (~2026-06-08 09:00 PDT), MISLEADING: single-name
configs stopped minting for window-shape reasons unrelated to strategy quality
(66 quality-passing would-be components were rejected on coverage alone in
~30h, including the only config ever to pass both promotion-quality gates).

D114 adds a material quality term to ``_component_run_reward``: the joint
proximity of the run's ``walk_forward_sharpe_median`` and ``cpcv_sharpe_p25``
gate VALUES to their own per-run thresholds, eligible only when the run passed
its own ``min_oos_trade_count`` gate. Properties pinned here:

  - exact math: ``quality = clamp(min(wf/thr_wf, cpcv/thr_cpcv), 0, 1)``;
  - admission-rule robustness: ``regime_coverage`` (or any other gate's
    pass/fail) does not move the reward — only the recorded quality VALUES do;
  - anti-Goodhart preserved for junk volume: zero-quality trading rejects
    still cannot outrank a single component event;
  - the deliberate departure: a cell with SUSTAINED near-gate quality can now
    accumulate reward mass comparable to a sparse component event (that is the
    point — WF/CPCV are the actual promotion axes);
  - H4 isolation: the orthogonal-yield discount's ``m`` stays a pure component
    count — quality contributes nothing to it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
)

from forge.feedback.rejection_weights import (
    COMPONENT_QUALITY_WEIGHT,
    COMPONENT_TIEBREAK_WEIGHT,
    _component_run_reward,
    _joint_quality,
    compute_hypothesis_component_weights,
    compute_orthogonal_yield_discounts,
)
from forge.persistence.db import db_connection

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


def _config(hypothesis: str, name: str, *, underlying: str | None = "AAPL") -> StrategyConfig:
    return StrategyConfig(
        name=name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket="swing_short",
        underlying=underlying,
        tier=1,
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
                params={"threshold": 30.0, "op": "<"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("realized_vol",),
                params={"threshold": 0.20, "op": "<"},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )


def _insert_submission(conn: Any, *, config: StrategyConfig, config_hash: str) -> None:
    conn.execute(
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
            config.model_dump_json(),
            datetime.now(UTC),
            "submitted",
        ],
    )


def _quality_run(
    *,
    config_hash: str,
    decision: str = "reject",
    trade_count: int = 120,
    min_oos_passed: bool | None = True,
    wf: float | None = None,
    wf_threshold: float | None = 2.0,
    cpcv: float | None = None,
    cpcv_threshold: float | None = 1.5,
    regime_coverage_passed: bool | None = None,
) -> GatedRun:
    """A gated run whose gate rows mirror the live export shape (values +
    per-run thresholds on the named quality gates)."""
    run_id = str(uuid.uuid4())
    gates: dict[str, GateResult] = {}
    if min_oos_passed is not None:
        gates["min_oos_trade_count"] = GateResult(
            gate_name="min_oos_trade_count",
            passed=min_oos_passed,
            value=float(trade_count),
            threshold=100.0,
        )
    if wf is not None or wf_threshold is not None:
        gates["walk_forward_sharpe_median"] = GateResult(
            gate_name="walk_forward_sharpe_median",
            passed=bool(wf is not None and wf_threshold is not None and wf >= wf_threshold),
            value=wf,
            threshold=wf_threshold,
        )
    if cpcv is not None or cpcv_threshold is not None:
        gates["cpcv_sharpe_p25"] = GateResult(
            gate_name="cpcv_sharpe_p25",
            passed=bool(cpcv is not None and cpcv_threshold is not None and cpcv >= cpcv_threshold),
            value=cpcv,
            threshold=cpcv_threshold,
        )
    if regime_coverage_passed is not None:
        gates["regime_coverage"] = GateResult(
            gate_name="regime_coverage",
            passed=regime_coverage_passed,
            value=1825.0,
            threshold=1460.0,
        )
    return GatedRun(
        run=RunResult(
            run_id=run_id,
            config_hash=config_hash,
            metrics={},
            trade_count=trade_count,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
        ),
        decision=PromotionDecision(
            run_id=run_id,
            decision=decision,  # type: ignore[arg-type]
            gate_results=gates,
            decided_at=datetime.now(UTC),
            decided_by="test_evaluator/v1",
        ),
    )


def _reward(gr: GatedRun) -> float:
    return _component_run_reward(
        gr,
        tiebreak_weight=COMPONENT_TIEBREAK_WEIGHT,
        quality_weight=COMPONENT_QUALITY_WEIGHT,
    )


# ---------------------------------------------------------------------------
# _joint_quality — exact semantics
# ---------------------------------------------------------------------------


def test_joint_quality_exact_math() -> None:
    """quality = min(wf/thr_wf, cpcv/thr_cpcv): the JOINT requirement — the
    promotion gate needs BOTH axes, so the binding one scores."""
    gr = _quality_run(config_hash="x", wf=1.0, cpcv=0.9)
    # wf 1.0/2.0 = 0.5; cpcv 0.9/1.5 = 0.6 → min = 0.5
    assert _joint_quality(gr) == pytest.approx(0.5)


def test_joint_quality_clamped_to_unit_interval() -> None:
    """Promote-grade values cap at 1.0; negative Sharpe floors at 0.0."""
    assert _joint_quality(_quality_run(config_hash="x", wf=3.0, cpcv=2.0)) == pytest.approx(1.0)
    assert _joint_quality(_quality_run(config_hash="x", wf=1.5, cpcv=-0.4)) == 0.0


def test_joint_quality_requires_own_trade_floor() -> None:
    """Quality is only meaningful at scale: the run must pass its OWN
    min_oos_trade_count gate (per-bucket thresholds ride in the gate row)."""
    failed = _quality_run(config_hash="x", wf=1.8, cpcv=1.2, min_oos_passed=False)
    absent = _quality_run(config_hash="x", wf=1.8, cpcv=1.2, min_oos_passed=None)
    assert _joint_quality(failed) == 0.0
    assert _joint_quality(absent) == 0.0


def test_joint_quality_missing_data_never_inflates() -> None:
    """Absent gate rows, absent values, or degenerate thresholds → 0.0 (the
    _sharpe_reward stance: missing data never inflates)."""
    # cpcv row entirely absent
    no_cpcv_row = _quality_run(config_hash="x", wf=1.8, cpcv=None, cpcv_threshold=None)
    assert _joint_quality(no_cpcv_row) == 0.0
    # value absent on a present row
    assert _joint_quality(_quality_run(config_hash="x", wf=None, cpcv=1.2)) == 0.0
    # threshold absent / zero
    assert _joint_quality(_quality_run(config_hash="x", wf=1.8, wf_threshold=None, cpcv=1.2)) == 0.0
    assert _joint_quality(_quality_run(config_hash="x", wf=1.8, wf_threshold=0.0, cpcv=1.2)) == 0.0


# ---------------------------------------------------------------------------
# Reward integration
# ---------------------------------------------------------------------------


def test_component_event_still_ceiling() -> None:
    """component/promote stay at exactly 1.0 — quality only grades rejects."""
    assert _reward(_quality_run(config_hash="x", decision="component", wf=0.1, cpcv=0.1)) == 1.0
    assert _reward(_quality_run(config_hash="x", decision="promote", wf=2.2, cpcv=1.6)) == 1.0


def test_reject_reward_is_quality_weight_times_score_plus_tiebreak() -> None:
    gr = _quality_run(config_hash="x", wf=1.0, cpcv=0.9)  # quality 0.5
    gates = gr.decision.gate_results
    gate_fraction = sum(1 for g in gates.values() if g.passed) / len(gates)
    # _sharpe_reward reads the wf gate row: 1.0/2.0 ramp = 0.5
    tiebreak = COMPONENT_TIEBREAK_WEIGHT * (gate_fraction + 0.5) / 2.0
    assert _reward(gr) == pytest.approx(COMPONENT_QUALITY_WEIGHT * 0.5 + tiebreak)


def test_regime_coverage_cannot_move_the_reward() -> None:
    """THE Q32 pin: two runs identical in every quality value, one failing
    regime_coverage (the post-2026-06-08 admission gate) — near-identical
    rewards, and the coverage-killed promote-grade reject keeps full quality
    credit. (Only the epsilon tiebreak's gate_fraction sees the extra failed
    gate; bounded by the tiebreak scale.)"""
    clean = _quality_run(config_hash="a", wf=2.2, cpcv=1.55, regime_coverage_passed=True)
    rc_killed = _quality_run(config_hash="b", wf=2.2, cpcv=1.55, regime_coverage_passed=False)
    assert _joint_quality(clean) == _joint_quality(rc_killed) == 1.0
    assert _reward(rc_killed) >= COMPONENT_QUALITY_WEIGHT  # full quality credit survives
    assert abs(_reward(clean) - _reward(rc_killed)) < COMPONENT_TIEBREAK_WEIGHT


def test_zero_quality_volume_still_cannot_outrank_component(tmp_path: Path) -> None:
    """The D105 anti-Goodhart invariant survives D114 for JUNK volume: a cell
    of 20 trading-but-zero-quality rejects stays below a cell with one real
    component among 19 silent rejects."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(20):  # junk volume: trades, passes its floor, quality ~0
            ch = f"junk_{i:03d}"
            _insert_submission(conn, config=_config("relative_value", f"j{i}"), config_hash=ch)
            gated.append(_quality_run(config_hash=ch, wf=0.0, cpcv=-0.2))
        for i in range(19):  # minting cell context: silent rejects
            ch = f"ve_{i:03d}"
            _insert_submission(conn, config=_config("volatility_event", f"v{i}"), config_hash=ch)
            gated.append(
                _quality_run(
                    config_hash=ch,
                    trade_count=0,
                    min_oos_passed=False,
                    wf=None,
                    cpcv=None,
                    wf_threshold=None,
                    cpcv_threshold=None,
                )
            )
        _insert_submission(conn, config=_config("volatility_event", "vc"), config_hash="ve_comp")
        gated.append(_quality_run(config_hash="ve_comp", decision="component", wf=1.3, cpcv=0.9))
        weights = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("relative_value", "volatility_event")
        )
    assert weights["volatility_event"] == pytest.approx(1.0)
    assert weights["relative_value"] < weights["volatility_event"]


def test_sustained_quality_can_rival_a_sparse_component(tmp_path: Path) -> None:
    """The deliberate D114 departure from D105's epsilon bound: a cell whose
    rejects sit AT the promotion frontier (quality 1.0, e.g. coverage-killed
    post-Q32) accumulates reward mass that can exceed one lucky component among
    junk. 1/quality_weight frontier rejects ≈ one component event."""
    n_frontier = int(1.0 / COMPONENT_QUALITY_WEIGHT) + 1
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(n_frontier):
            ch = f"front_{i:03d}"
            _insert_submission(conn, config=_config("volatility_event", f"f{i}"), config_hash=ch)
            gated.append(_quality_run(config_hash=ch, wf=2.2, cpcv=1.55))
        for i in range(n_frontier - 1):  # same n: junk context around one component
            ch = f"mr_{i:03d}"
            _insert_submission(conn, config=_config("mean_reversion", f"m{i}"), config_hash=ch)
            gated.append(
                _quality_run(
                    config_hash=ch,
                    trade_count=0,
                    min_oos_passed=False,
                    wf=None,
                    cpcv=None,
                    wf_threshold=None,
                    cpcv_threshold=None,
                )
            )
        _insert_submission(conn, config=_config("mean_reversion", "mc"), config_hash="mr_comp")
        gated.append(_quality_run(config_hash="mr_comp", decision="component", wf=1.0, cpcv=0.8))
        weights = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("volatility_event", "mean_reversion")
        )
    # frontier cell: n_frontier * quality_weight > 1.0 component event
    assert weights["volatility_event"] == pytest.approx(1.0)
    assert weights["mean_reversion"] < 1.0


# ---------------------------------------------------------------------------
# H4 isolation + cold start
# ---------------------------------------------------------------------------


def test_h4_discounts_blind_to_quality(tmp_path: Path) -> None:
    """The orthogonal-yield discount's m is a pure COMPONENT count: a cell of
    frontier-quality rejects must stay ABSENT from the discount map, and a
    minting cell's discount must not move when quality rows appear."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(10):  # frontier-quality rejects, zero components
            ch = f"fq_{i:03d}"
            _insert_submission(
                conn, config=_config("volatility_event", f"q{i}", underlying="NVDA"), config_hash=ch
            )
            gated.append(_quality_run(config_hash=ch, wf=2.2, cpcv=1.55))
        _insert_submission(
            conn, config=_config("volatility_event", "c0", underlying="AAPL"), config_hash="comp"
        )
        gated.append(_quality_run(config_hash="comp", decision="component", wf=1.0, cpcv=0.9))
        discounts = compute_orthogonal_yield_discounts(conn, gated)
    assert ("volatility_event", "rsi_2", "NVDA") not in discounts
    assert discounts[("volatility_event", "rsi_2", "AAPL")] == pytest.approx(2.0**-0.15)


def test_cold_start_contract_unchanged(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_hypothesis_component_weights(conn, [], hypotheses=("mean_reversion",)) == {}


def test_deterministic(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("mean_reversion", "d"), config_hash="d")
        gated = [_quality_run(config_hash="d", wf=1.4, cpcv=1.0)]
        first = compute_hypothesis_component_weights(conn, gated, hypotheses=("mean_reversion",))
        second = compute_hypothesis_component_weights(conn, gated, hypotheses=("mean_reversion",))
    assert first == second
