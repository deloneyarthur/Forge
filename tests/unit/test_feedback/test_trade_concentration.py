"""Unit tests for T2.5 / D047 — trade-concentration post-batch analyzer.

D050: Crucible 6a57ee5 shipped `top_3_trade_pnl_share` as a real metric;
the analyzer prefers it over the heuristic proxy when present. Tests
cover both paths (real-metric and fallback-proxy) plus the transition
behavior (mix of pre-/post-6a57ee5 runs in the same export).
"""

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
    profit_factor: float = 1.5,
    win_rate: float = 0.5,
    n_trades: int = 100,
    top_3_trade_pnl_share: float | None = None,
) -> GatedRun:
    metrics: dict[str, object] = {
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "n_trades": n_trades,
    }
    if top_3_trade_pnl_share is not None:
        metrics["top_3_trade_pnl_share"] = top_3_trade_pnl_share
    run = RunResult(
        run_id=str(uuid.uuid4()),
        config_hash="abc123",
        metrics=metrics,
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
# compute_concentration_proxy (fallback path)
# ---------------------------------------------------------------------------


def test_proxy_returns_zero_when_no_trades() -> None:
    assert compute_concentration_proxy(profit_factor=10.0, n_trades=0, win_rate=0.5) == 0.0


def test_proxy_typical_balanced_strategy_is_low() -> None:
    """PF=1.5, n=200, wr=0.5 → proxy ≈ 0.015 (below 0.05 threshold)."""
    proxy = compute_concentration_proxy(profit_factor=1.5, n_trades=200, win_rate=0.5)
    assert proxy < 0.05


def test_proxy_concentrated_strategy_is_high() -> None:
    """PF=5, n=50, wr=0.3 → proxy ≈ 0.33 (above threshold)."""
    proxy = compute_concentration_proxy(profit_factor=5.0, n_trades=50, win_rate=0.3)
    assert proxy > 0.05


def test_proxy_uses_win_rate_floor() -> None:
    proxy = compute_concentration_proxy(profit_factor=2.0, n_trades=100, win_rate=0.0)
    assert proxy == 2.0


# ---------------------------------------------------------------------------
# analyze_promotion_concentration — real metric path (D050)
# ---------------------------------------------------------------------------


def test_real_metric_path_passes_balanced_distribution() -> None:
    """top_3_share = 0.1 (top 3 trades = 10% of P&L) — broad distribution, passes."""
    runs = [_gated_run(decision="promote", top_3_trade_pnl_share=0.10, n_trades=200)]
    flags = analyze_promotion_concentration(runs)
    assert flags == []


def test_real_metric_path_flags_concentrated_distribution() -> None:
    """top_3_share = 0.65 (top 3 trades = 65% of P&L) — concentrated, rejects."""
    runs = [_gated_run(decision="promote", top_3_trade_pnl_share=0.65, n_trades=40)]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 1
    flag = flags[0]
    assert flag.metric_type == "top_3_share"
    assert flag.score == 0.65
    assert flag.threshold == 0.40  # default top_3_share threshold


def test_real_metric_path_threshold_exact_boundary() -> None:
    """At threshold (==0.40) → NOT flagged (filter uses strict >)."""
    runs = [_gated_run(decision="promote", top_3_trade_pnl_share=0.40)]
    flags = analyze_promotion_concentration(runs)
    assert flags == []


def test_real_metric_path_just_above_threshold() -> None:
    runs = [_gated_run(decision="promote", top_3_trade_pnl_share=0.45)]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 1
    assert flags[0].metric_type == "top_3_share"


# ---------------------------------------------------------------------------
# Fallback path (pre-Crucible-6a57ee5 runs)
# ---------------------------------------------------------------------------


def test_fallback_path_when_top3_share_absent() -> None:
    """Pre-Crucible-6a57ee5 runs have no top_3_trade_pnl_share key.
    Analyzer uses the heuristic proxy + the fallback threshold (0.05)."""
    runs = [
        _gated_run(
            decision="promote",
            profit_factor=8.0,
            win_rate=0.2,
            n_trades=40,
            top_3_trade_pnl_share=None,
        ),
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 1
    assert flags[0].metric_type == "fallback_proxy"
    assert flags[0].threshold == 0.05


def test_fallback_path_balanced_passes() -> None:
    runs = [
        _gated_run(
            decision="promote",
            profit_factor=1.6,
            win_rate=0.55,
            n_trades=200,
            top_3_trade_pnl_share=None,
        ),
    ]
    flags = analyze_promotion_concentration(runs)
    assert flags == []


# ---------------------------------------------------------------------------
# Mixed export (transition period)
# ---------------------------------------------------------------------------


def test_mixed_export_uses_real_metric_when_available_proxy_otherwise() -> None:
    """An export with pre- and post-deploy rows: each row uses its own metric."""
    runs = [
        # Pre-deploy: no top_3_share, proxy says concentrated
        _gated_run(
            decision="promote",
            profit_factor=8.0,
            win_rate=0.2,
            n_trades=40,
            top_3_trade_pnl_share=None,
        ),
        # Post-deploy: real metric says concentrated
        _gated_run(decision="promote", top_3_trade_pnl_share=0.55, n_trades=100),
        # Post-deploy: real metric says balanced
        _gated_run(decision="promote", top_3_trade_pnl_share=0.12, n_trades=300),
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 2
    metric_types = {f.metric_type for f in flags}
    assert metric_types == {"top_3_share", "fallback_proxy"}


# ---------------------------------------------------------------------------
# Common behaviors
# ---------------------------------------------------------------------------


def test_analyzer_ignores_rejected_runs() -> None:
    """Rejected runs don't count — concentration in rejects is moot."""
    runs = [_gated_run(decision="reject", top_3_trade_pnl_share=0.95)]
    flags = analyze_promotion_concentration(runs)
    assert flags == []


def test_analyzer_sorts_flags_by_score_descending() -> None:
    runs = [
        _gated_run(decision="promote", top_3_trade_pnl_share=0.45),  # mild
        _gated_run(decision="promote", top_3_trade_pnl_share=0.85),  # severe
        _gated_run(decision="promote", top_3_trade_pnl_share=0.60),  # mid
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 3
    assert flags[0].score == 0.85
    assert flags[1].score == 0.60
    assert flags[2].score == 0.45


def test_concentration_flag_carries_diagnostic_fields() -> None:
    runs = [
        _gated_run(
            decision="promote",
            top_3_trade_pnl_share=0.55,
            profit_factor=4.5,
            n_trades=80,
            win_rate=0.35,
        ),
    ]
    flags = analyze_promotion_concentration(runs)
    assert len(flags) == 1
    flag = flags[0]
    assert isinstance(flag, ConcentrationFlag)
    assert flag.config_hash == "abc123"
    assert flag.metric_type == "top_3_share"
    assert flag.score == 0.55
    assert flag.profit_factor == 4.5
    assert flag.n_trades == 80
    assert flag.win_rate == 0.35


def test_threshold_overrides_are_applied() -> None:
    """Strict top_3 threshold (0.20) catches a borderline-balanced run."""
    runs = [_gated_run(decision="promote", top_3_trade_pnl_share=0.25, n_trades=100)]
    # Default 0.40 → not flagged
    assert analyze_promotion_concentration(runs) == []
    # Strict 0.20 → flagged
    flags = analyze_promotion_concentration(runs, top_3_share_threshold=0.20)
    assert len(flags) == 1
