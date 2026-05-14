"""Inline demo registry for the Phase 2 ``forge enumerate`` CLI.

Phase 2 ships ahead of the Phase 4 Crucible-registry wiring, so the CLI
needs a registry to run against. This module mirrors
``tests/fixtures/strategy_configs.minimal_registry_snapshot`` in ``src``
so the CLI never reaches into test code. Phase 4 will replace this
helper with a ``crucible_contracts``-driven registry query.

If you change the test fixture's indicator set, mirror it here (or
remove this module entirely once Phase 4 lands).
"""

from __future__ import annotations

from datetime import UTC, datetime

from crucible_contracts import IndicatorMetadata, RegistrySnapshot


def demo_registry() -> RegistrySnapshot:
    """Build a 14-indicator synthetic registry covering every §3.5 v1 family.

    Keep in sync with ``tests/fixtures/strategy_configs.minimal_registry_snapshot``;
    a regression test would catch drift if the fixture's shape mattered to
    a downstream test, but the registries are intentional duplicates for
    Phase 2.
    """
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
                id="rsi_14",
                version=1,
                family="mean_reversion",
                lookback=14,
                params_schema={},
            ),
            IndicatorMetadata(
                id="momentum_252",
                version=1,
                family="trend",
                lookback=252,
                params_schema={},
            ),
            IndicatorMetadata(
                id="iv_rank",
                version=1,
                family="iv_structure",
                lookback=30,
                params_schema={"threshold": {"type": "number"}},
            ),
            IndicatorMetadata(
                id="ema_50",
                version=1,
                family="trend",
                lookback=50,
                params_schema={},
            ),
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
            IndicatorMetadata(
                id="pairs_zscore",
                version=1,
                family="pairs",
                lookback=60,
                params_schema={},
            ),
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
    )
