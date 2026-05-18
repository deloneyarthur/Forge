"""Unit tests for T2.5 / D046 — trade-concentration post-batch analyzer."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from crucible_contracts import (
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
)

from forge.feedback.trade_concentration import (
    ConcentrationFlag,
    analyze_promotion_concentration,
    compute_concentration_proxy,
)


def _gated_run(
    *,
    decision: str,
    profit_factor: float,
    win_rate: float,
    n_trades: int,
) -> GatedRun:
    run = RunResult(
        run_id=str(uuid.uuid4()),
        config_hash="abc123",
        metrics={"profit_factor": profit_factor, "win_rate": win_rate},
        trade_count=n_trades,
        period_start=date(2022, 1, 1),
        period_end=date(2024, 12, 31),
    )
    pd_ = PromotionDecision(
        run_id=run.run_id,
        decision=decision,  # type: ignore[arg-type]
        gate_results={"x": GateResult(gate_name="x", passed=True, value=1.0)},
        decided_at=datetime(2026, 5, 13, tzinfo=UTC),
        decided_by="auto",
    )
    return GatedRun(run=run, decision=pd_)


# ---------------------------------------------------------------------------
# compute_concentration_proxy
# ---------------------------------------------------------------------------


def test_proxy_returns_zero_when_no_trades() -> None:
    assert compute_concentration_proxy(profit_factor=10.0, n_trades=0, win_rate=0.5) == 0.0


def test_proxy_typical_balanced_strategy_is_low() -> None:
    """profit_factor=1.5, n_trades=200, win_rate=0.5 → proxy ≈ 0.015 (well below 0.05)."""
    proxy = compute_concentration_proxy(profit_factor=1.5, n_trades=200, win_rate=0.5)
    assert proxy < 0.05  # below default suspect threshold


def test_proxy_concentrated_strategy_is_high() -> None:
    """profit_factor=5.0, n_trades=50, win_rate=0.3 → proxy ≈ 0.33 (above 0.05)."""
    proxy = compute_concentration_proxy(profit_factor=5.0, n_trades=50, win_rate=0.3)
    assert proxy > 0.05


def test_proxy_uses_win_rate_floor() -> None:
    """Even with win_rate=0, denominator uses the 0.01 floor (no div-by-zero)."""
    proxy = compute_concentration_proxy(profit_factor=2.0, n_trades=100, win_rate=0.0)
    # denom = 100 * 0.01 = 1.0; proxy = 2.0 / 1.0 = 2.0
    assert proxy == 2.0


# ---------------------------------------------------------------------------
# analyze_promotion_concentration
# ---------------------------------------------------------------------------


def test_analyzer_ignores_rejected_runs() -> None:
    """Rejected runs don't count — concentration in rejects is moot."""
    runs = [
        _gated_run(decision="reject", profit_factor=10.0, win_rate=0.1, n_trades=20),
    ]
    flags = analyze_promotion_concentration(runs)
    assert flags == []


def test_analyzer_flags_promoted_concentrated_run() -> None:
    """A promoted run with high proxy is flagged."""
    runs = [
        _gated_run(decision="promote", profit_factor=8.0, win_rate=0.2, n_trades=40),
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 1
    assert flags[0].profit_factor == 8.0
    assert flags[0].n_trades == 40
    assert flags[0].proxy_score > 0.05


def test_analyzer_skips_balanced_promoted_runs() -> None:
    """Balanced promoted runs (typical PF, many trades, decent win rate)
    don't trip the threshold."""
    runs = [
        _gated_run(decision="promote", profit_factor=1.6, win_rate=0.55, n_trades=200),
    ]
    flags = analyze_promotion_concentration(runs)
    assert flags == []


def test_analyzer_sorts_flags_by_proxy_descending() -> None:
    """Most-concentrated flag appears first."""
    runs = [
        # mild concentration
        _gated_run(decision="promote", profit_factor=3.0, win_rate=0.3, n_trades=60),
        # severe concentration
        _gated_run(decision="promote", profit_factor=10.0, win_rate=0.1, n_trades=30),
        # mid concentration
        _gated_run(decision="promote", profit_factor=5.0, win_rate=0.2, n_trades=50),
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 3
    assert flags[0].profit_factor == 10.0
    assert flags[1].profit_factor == 5.0
    assert flags[2].profit_factor == 3.0
    # Strict descending
    assert flags[0].proxy_score > flags[1].proxy_score > flags[2].proxy_score


def test_analyzer_threshold_is_configurable() -> None:
    """Stricter threshold flags more borderline cases."""
    runs = [
        _gated_run(decision="promote", profit_factor=2.0, win_rate=0.4, n_trades=100),
    ]
    # proxy = 2.0 / (100 * 0.4) = 0.05 → at default threshold (>0.05 → reject; ==0.05 → no flag)
    flags_default = analyze_promotion_concentration(runs)
    assert flags_default == []
    # Tighter threshold (0.01) → flagged
    flags_tight = analyze_promotion_concentration(runs, threshold=0.01)
    assert len(flags_tight) == 1


def test_concentration_flag_carries_diagnostic_fields() -> None:
    runs = [
        _gated_run(decision="promote", profit_factor=8.0, win_rate=0.2, n_trades=40),
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 1
    flag = flags[0]
    assert isinstance(flag, ConcentrationFlag)
    assert flag.config_hash == "abc123"
    assert flag.threshold == 0.05  # default
    assert flag.proxy_score > 0.05
