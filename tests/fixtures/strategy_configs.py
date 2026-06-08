"""Shared ``StrategyConfig`` + ``RegistrySnapshot`` fixtures for grammar tests.

A minimal grammar-valid ``StrategyConfig`` (one directional signal, one
regime-filter signal, mandatory exits, fixed_risk_pct sizer) plus a small
``RegistrySnapshot`` that knows about the indicators / exits / sizers the
fixture references. Tests override fields via ``minimal_strategy_config(**)``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    IndicatorMetadata,
    RegistrySnapshot,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
)

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


def minimal_strategy_config(**overrides: Any) -> StrategyConfig:
    """Construct a minimum grammar-shaped StrategyConfig. Pass keyword
    arguments to override individual fields. Default is a mean_reversion
    swing_short with one directional RSI signal + one regime IV-rank gate."""
    base: dict[str, Any] = {
        "name": "fixture_strategy",
        "hypothesis": "mean_reversion",
        "dte_bucket": "swing_short",
        "underlying": "SPY",
        "tier": 1,
        "signals": (
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
                params={"period": 2, "threshold": 30.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
        "combiner": CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1),
        "selector": SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        "sizer": SizerSpec(mode="fixed_risk_pct"),
        "exits": _MANDATORY_EXITS,
    }
    base.update(overrides)
    return StrategyConfig(**base)


def minimal_registry_snapshot() -> RegistrySnapshot:
    """Registry that knows about the indicators / exits / sizers
    ``minimal_strategy_config`` references plus all indicators referenced
    by the §3.5 predicate tests."""
    return RegistrySnapshot(
        indicators=(
            # Short-lookback (S4 short bucket; D010 threshold ≤ 6)
            IndicatorMetadata(
                id="rsi_2",
                version=1,
                family="mean_reversion",
                lookback=2,
                params_schema={},
            ),
            # Medium-lookback (S4 medium bucket)
            IndicatorMetadata(
                id="rsi_14",
                version=1,
                family="mean_reversion",
                lookback=14,
                params_schema={},
            ),
            # Long-lookback (S4 long bucket; ≥ 90)
            IndicatorMetadata(
                id="momentum_252",
                version=1,
                family="trend",
                lookback=252,
                params_schema={},
            ),
            # iv_rank — the regime-gate indicator §3.5 R1 references by name.
            IndicatorMetadata(
                id="iv_rank",
                version=1,
                family="iv_structure",
                lookback=30,
                params_schema={"threshold": {"type": "number"}},
            ),
            # Trend family — for C2 trend_continuation
            IndicatorMetadata(
                id="ema_50",
                version=1,
                family="trend",
                lookback=50,
                params_schema={},
            ),
            # Trend-strength regime gates (R2). `trend_strength` is its own
            # family (contracts v1.4.0 / D019) so adx/hurst can gate a
            # trend-family directional without triggering C1.
            IndicatorMetadata(
                id="adx",
                version=1,
                family="trend_strength",
                lookback=14,
                params_schema={},
            ),
            IndicatorMetadata(
                id="hurst",
                version=1,
                family="trend_strength",
                lookback=100,
                params_schema={},
            ),
            # Event-proximity regime gates (R3)
            IndicatorMetadata(
                id="days_to_earnings",
                version=1,
                family="calendar",
                lookback=0,
                params_schema={},
            ),
            IndicatorMetadata(
                id="days_to_fomc",
                version=1,
                family="calendar",
                lookback=0,
                params_schema={},
            ),
            # H2 (v12 / D109) — event_momentum / PEAD pair. `days_since_earnings`
            # is the post-event TIMING gate ("fire within N days AFTER the
            # print"); Crucible reclassified it to the `calendar` family (the
            # backward twin of days_to_earnings, override exports.py:207), so it
            # is C1-distinct from the `sue` directional below.
            IndicatorMetadata(
                id="days_since_earnings",
                version=1,
                family="calendar",
                lookback=0,
                params_schema={},
            ),
            # `sue` (standardized unexpected earnings) is event_momentum's
            # DIRECTIONAL — the surprise drives post-earnings drift. Its own
            # `post_event_drift` family, so C1 lets it coexist with the
            # calendar-family days_since_earnings gate in one config.
            IndicatorMetadata(
                id="sue",
                version=1,
                family="post_event_drift",
                lookback=0,
                params_schema={},
            ),
            # Sizer-mode required indicators (X1, X2)
            IndicatorMetadata(
                id="realized_vol",
                version=1,
                family="volatility",
                lookback=20,
                params_schema={},
            ),
            IndicatorMetadata(
                id="expected_value_estimator",
                version=1,
                family="smart_money",
                lookback=60,
                params_schema={},
            ),
            # Pairs family (C2 relative_value)
            IndicatorMetadata(
                id="pairs_zscore",
                version=1,
                family="pairs",
                lookback=60,
                params_schema={},
            ),
            # Flow / macro families (C2 volatility_event, tail_hedge)
            IndicatorMetadata(
                id="put_call_flow",
                version=1,
                family="flow",
                lookback=5,
                params_schema={},
            ),
            IndicatorMetadata(
                id="vix_level",
                version=1,
                family="macro",
                lookback=1,
                params_schema={},
            ),
            # rv_rank — realized-vol percentile rank regime gate (R2, D077).
            # `volatility` family: C1 satisfied against `trend`-family directionals.
            IndicatorMetadata(
                id="rv_rank",
                version=1,
                family="volatility",
                lookback=252,
                params_schema={
                    "rv_window": {"type": "integer"},
                    "window": {"type": "integer"},
                },
            ),
            # D062: dealer-positioning family (gex/walls/gamma-flip). Used to
            # exercise C2's `volatility_event` and `mean_reversion` allowlist
            # extensions added alongside Crucible commit 5af63ad.
            IndicatorMetadata(
                id="gex",
                version=1,
                family="dealer_positioning",
                lookback=0,
                params_schema={},
            ),
            IndicatorMetadata(
                id="call_wall_distance_pct",
                version=1,
                family="dealer_positioning",
                lookback=0,
                params_schema={},
            ),
        ),
        signal_types=("threshold", "rule", "passthrough"),
        exit_ids=(
            "expiry_exit",
            "theta_cliff_exit",
            "earnings_exit",
            "liquidity_exit",
            "trailing_atr",
            "time_stop",
            "regime_flip_exit",
            "convergence_exit",
            "iv_crush_exit",
            "event_passed_exit",
            "roll_on_schedule_exit",
            "hard_profit_target",
            "premium_stop_loss",
            "atr_underlying_stop_loss",
        ),
        sizer_modes=("fixed_risk_pct", "vol_target", "fractional_kelly"),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
        data_start_date=date(2022, 1, 1),
    )


def grammar_valid_baseline(**overrides: Any) -> StrategyConfig:
    """A StrategyConfig that satisfies every §3.5 rule against
    ``minimal_registry_snapshot``. Tests for individual §3.5 predicates
    start here and modify one field to provoke that rule's failure.

    Profile: ``mean_reversion`` swing_short with rsi_2 directional +
    iv_rank regime gate (threshold ≤ 50, satisfies R1) and a
    ``time_stop`` exit (satisfies S5).
    """
    base: dict[str, Any] = {
        "name": "baseline_strategy",
        "hypothesis": "mean_reversion",
        "dte_bucket": "swing_short",
        "underlying": "SPY",
        "tier": 1,
        "signals": (
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
                params={"period": 2, "threshold": 30.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
        "combiner": CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1),
        "selector": SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        "sizer": SizerSpec(mode="fixed_risk_pct"),
        "exits": (
            *_MANDATORY_EXITS,
            ExitSpec(id="time_stop"),
        ),
    }
    base.update(overrides)
    return StrategyConfig(**base)


__all__ = [
    "grammar_valid_baseline",
    "minimal_registry_snapshot",
    "minimal_strategy_config",
]
