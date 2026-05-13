"""Shared ``StrategyConfig`` + ``RegistrySnapshot`` fixtures for grammar tests.

A minimal grammar-valid ``StrategyConfig`` (one directional signal, one
regime-filter signal, mandatory exits, fixed_risk_pct sizer) plus a small
``RegistrySnapshot`` that knows about the indicators / exits / sizers the
fixture references. Tests override fields via ``minimal_strategy_config(**)``.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
                indicators=("iv_rank_30",),
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
    ``minimal_strategy_config`` references."""
    return RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="rsi_2",
                version=1,
                family="mean_reversion",
                lookback=2,
                params_schema={},
            ),
            IndicatorMetadata(
                id="iv_rank_30",
                version=1,
                family="iv_structure",
                lookback=30,
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
        ),
        sizer_modes=("fixed_risk_pct", "vol_target", "fractional_kelly"),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
    )


__all__ = ["minimal_registry_snapshot", "minimal_strategy_config"]
