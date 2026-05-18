"""Hypothesis strategies + mutators for the §12 property tests.

The §12 Phase 1 acceptance criterion:

    1000 random *grammar-valid* configs all pass validation.
    1000 random *grammar-invalid* configs all fail with at least one
    named error.

To generate grammar-valid configs the strategies sample from a small set
of hand-built **templates** — one per hypothesis — that satisfy every
§3.5 rule against the fixture registry. Each template specifies the
exact directional indicator, regime gate, required exits, and DTE
window the hypothesis's rules require; sampling varies the remaining
free fields (tier, name suffix, dte_bucket within the template's
allowed set, etc.).

To generate grammar-*invalid* configs we mutate a valid config to break
exactly one rule. Each mutator returns `(mutated_config, broken_rule_id)`
so the property test can assert the validator named the same rule.

This is intentionally a templated approach, not a CSP-style search over
the full enumeration space. Phase 1's deliverable is grammar
*evaluation*; Phase 2 is the enumerator. The templates exercise enough
diversity to cover the validator's positive/negative paths.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
)
from hypothesis import strategies as st

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


@dataclass(frozen=True, slots=True)
class _Template:
    hypothesis: str
    directional_indicator: str
    regime_indicator: str
    regime_params: dict[str, Any]
    extra_required_exits: tuple[ExitSpec, ...]
    valid_dte_buckets: tuple[str, ...]


# Templates built against `tests.fixtures.strategy_configs.minimal_registry_snapshot`.
# All exits per §3.5 S5 are explicit; default sizer is fixed_risk_pct so X1/X2
# are vacuous. DTE bucket is varied via _DTE_BUCKET_SELECTOR_RANGES.
_TEMPLATES: tuple[_Template, ...] = (
    _Template(
        hypothesis="mean_reversion",
        directional_indicator="rsi_2",  # mean_reversion family, lookback=2 → short
        regime_indicator="iv_rank",
        regime_params={"threshold": 50},
        extra_required_exits=(ExitSpec(id="time_stop"),),
        valid_dte_buckets=("swing_short",),
    ),
    _Template(
        hypothesis="trend_continuation",
        directional_indicator="ema_50",  # trend family, lookback=50 → medium
        regime_indicator="adx",
        regime_params={"threshold": 25},
        extra_required_exits=(
            ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30}),
        ),
        valid_dte_buckets=("swing_short", "swing_mid"),
    ),
    _Template(
        hypothesis="regime_arbitrage",
        # any family OK per C2 (regime_arbitrage exception); pairs gives a
        # non-trivial C2 verification path.
        directional_indicator="pairs_zscore",
        regime_indicator="iv_rank",
        regime_params={"threshold": 50},
        extra_required_exits=(ExitSpec(id="regime_flip_exit"),),
        # pairs_zscore lookback=60 → medium_lookback; per S4 allowed buckets
        # are swing_short or swing_mid (not swing_long).
        valid_dte_buckets=("swing_short", "swing_mid"),
    ),
    _Template(
        hypothesis="relative_value",
        directional_indicator="pairs_zscore",
        regime_indicator="iv_rank",
        regime_params={"threshold": 50},
        extra_required_exits=(ExitSpec(id="convergence_exit"),),
        valid_dte_buckets=("swing_short", "swing_mid"),
    ),
    _Template(
        hypothesis="volatility_event",
        directional_indicator="put_call_flow",  # flow family, lookback=5 → short
        # T1.4 / grammar v2 / D039: switched from days_to_earnings to
        # days_to_fomc because the property-test fixture hardcodes
        # underlying="SPY" (an ETF) and R3 v2 rejects days_to_earnings
        # on ETFs (sentinel-999 silent-failure case). days_to_fomc is
        # ETF-compatible.
        regime_indicator="days_to_fomc",
        regime_params={"threshold": 7},
        extra_required_exits=(
            ExitSpec(id="iv_crush_exit"),
            ExitSpec(id="event_passed_exit"),
        ),
        valid_dte_buckets=("swing_short",),
    ),
    _Template(
        hypothesis="tail_hedge",
        directional_indicator="vix_level",  # macro family, lookback=1 → short
        regime_indicator="iv_rank",
        regime_params={"threshold": 50},
        extra_required_exits=(ExitSpec(id="roll_on_schedule_exit"),),
        valid_dte_buckets=("swing_short",),
    ),
)


_DTE_BUCKET_SELECTOR_RANGES: dict[str, dict[str, Any]] = {
    "swing_short": {
        "dte_min_range": (14, 18),
        "dte_max_range": (19, 21),
        "delta_range": (0.40, 0.55),
    },
    "swing_mid": {
        "dte_min_range": (30, 38),
        "dte_max_range": (39, 45),
        "delta_range": (0.30, 0.45),
    },
    "swing_long": {
        "dte_min_range": (60, 74),
        "dte_max_range": (75, 90),
        "delta_range": (0.20, 0.35),
    },
}


@st.composite
def valid_strategy_config(draw: st.DrawFn) -> StrategyConfig:
    """Hypothesis strategy that yields ``StrategyConfig`` instances
    satisfying every §3.5 rule against ``minimal_registry_snapshot``."""
    template = draw(st.sampled_from(_TEMPLATES))
    dte_bucket = draw(st.sampled_from(template.valid_dte_buckets))
    sel = _DTE_BUCKET_SELECTOR_RANGES[dte_bucket]
    dte_min = draw(st.integers(*sel["dte_min_range"]))
    dte_max = draw(st.integers(*sel["dte_max_range"]))
    delta_target = draw(st.floats(*sel["delta_range"], allow_nan=False))
    tier = draw(st.integers(min_value=1, max_value=3))
    risk_pct = draw(st.floats(min_value=0.005, max_value=0.02, allow_nan=False))
    name_suffix = draw(st.integers(min_value=0, max_value=10_000))

    signals = (
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=(template.directional_indicator,),
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=(template.regime_indicator,),
            params=template.regime_params,
        ),
    )

    return StrategyConfig(
        name=f"prop_{template.hypothesis}_{name_suffix}",
        hypothesis=template.hypothesis,
        dte_bucket=dte_bucket,
        underlying="SPY",
        tier=tier,
        signals=signals,
        combiner=CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1),
        selector=SelectorSpec(
            delta_target=delta_target,
            delta_tolerance=0.05,
            dte_min=dte_min,
            dte_max=dte_max,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct", per_trade_risk_pct=risk_pct),
        exits=(*_MANDATORY_EXITS, *template.extra_required_exits),
    )


# ---------------------------------------------------------------------------
# Mutators — each returns (mutated_config, expected_failing_rule_id).
# ---------------------------------------------------------------------------


_Mutation = Callable[[StrategyConfig], tuple[StrategyConfig, str]]


def _break_s2_zero_directional(cfg: StrategyConfig) -> tuple[StrategyConfig, str]:
    """Remove the directional signal; S2 must report cardinality != 1."""
    new_signals = tuple(s for s in cfg.signals if s.role != "directional")
    # add a placeholder so signals != () (StrategyConfig requires at least 1)
    if not new_signals:
        new_signals = (
            SignalSpec(
                id="sig_filler",
                type="threshold",
                role="filter",
                indicators=("rsi_14",),
            ),
        )
    return cfg.model_copy(update={"signals": new_signals}), "S2"


def _break_s3_zero_regime(cfg: StrategyConfig) -> tuple[StrategyConfig, str]:
    """Strip regime_filter signals; S3 must report cardinality < 1."""
    new_signals = tuple(s for s in cfg.signals if s.role != "regime_filter")
    return cfg.model_copy(update={"signals": new_signals}), "S3"


def _break_c3_too_many_signals(cfg: StrategyConfig) -> tuple[StrategyConfig, str]:
    """Inflate the signal count past 4 → C3."""
    extras = tuple(
        SignalSpec(
            id=f"sig_extra_{i}",
            type="threshold",
            role="filter",
            indicators=("hurst",),
        )
        for i in range(5)
    )
    return cfg.model_copy(update={"signals": (*cfg.signals, *extras)}), "C3"


def _break_p4_risk_below_min(cfg: StrategyConfig) -> tuple[StrategyConfig, str]:
    """Drop per_trade_risk_pct below the 0.005 floor → P4."""
    new_sizer = SizerSpec(mode=cfg.sizer.mode, per_trade_risk_pct=0.001)
    return cfg.model_copy(update={"sizer": new_sizer}), "P4"


def _break_s5_drop_required_exit(cfg: StrategyConfig) -> tuple[StrategyConfig, str]:
    """Drop the hypothesis-required exit (S5)."""
    required_by_hypothesis = {
        "mean_reversion": "time_stop",
        "trend_continuation": "trailing_atr",
        "regime_arbitrage": "regime_flip_exit",
        "relative_value": "convergence_exit",
        "volatility_event": "iv_crush_exit",
        "tail_hedge": "roll_on_schedule_exit",
    }
    target = required_by_hypothesis[cfg.hypothesis]
    new_exits = tuple(e for e in cfg.exits if e.id != target)
    return cfg.model_copy(update={"exits": new_exits}), "S5"


def _break_p2_wrong_dte_window(cfg: StrategyConfig) -> tuple[StrategyConfig, str]:
    """Move the DTE window outside the bucket → P2."""
    new_selector = SelectorSpec(
        delta_target=cfg.selector.delta_target,
        delta_tolerance=cfg.selector.delta_tolerance,
        dte_min=1,
        dte_max=2,
    )
    return cfg.model_copy(update={"selector": new_selector}), "P2"


_MUTATIONS: tuple[_Mutation, ...] = (
    _break_s2_zero_directional,
    _break_s3_zero_regime,
    _break_c3_too_many_signals,
    _break_p4_risk_below_min,
    _break_s5_drop_required_exit,
    _break_p2_wrong_dte_window,
)


@st.composite
def invalid_strategy_config_case(
    draw: st.DrawFn,
) -> tuple[StrategyConfig, str]:
    """Generates ``(invalid_config, expected_rule_id)`` pairs by taking a
    valid config and applying one mutator."""
    base = draw(valid_strategy_config())
    mutator = draw(st.sampled_from(_MUTATIONS))
    return mutator(base)


__all__ = [
    "invalid_strategy_config_case",
    "valid_strategy_config",
]
