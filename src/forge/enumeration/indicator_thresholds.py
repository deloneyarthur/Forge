"""Per-indicator threshold sampling for the enumerator.

Background: Crucible's `ThresholdSignal._compare` requires `params['threshold']`
and a `params['op']` (default `<`). Before this module, the Forge enumerator
emitted `SignalSpec(type='threshold', indicators=(id,))` with empty params,
so Crucible's predicate evaluated `params.get("threshold") is None` and
returned False on every bar — zero activations across every config.

This module supplies a per-indicator threshold table grounded in real SPY-data
distributions (see `docs/INDICATOR_THRESHOLDS.md`, audit 2026-05-14). Each
indicator gets:

  * `directional_range`: sampling range for directional signals (extreme/contrarian)
  * `regime_range`: sampling range for regime_filter signals (allow-window)
  * `op_directional` / `op_regime`: comparison operator (`<` low-side, `>` high-side)
  * `is_skip`: indicator can't be thresholded honestly (price-scale, stubs)

Stub indicators (iv_rank, expected_value_estimator, pairs_zscore, put_call_flow,
vix_level) are included with generic thresholds; per operator decision 2026-05-14
they remain enumerable until Crucible ships real implementations, at which point
this table updates with audited ranges. Their fire rate is currently 0 — the
pipeline is structurally honest about that.

Price-scale indicators (ema, ema_50, sma) are flagged `is_skip=True` because
their absolute values (~250-700 USD on SPY) make threshold-style signals
nonsensical. They remain valid for `passthrough` confluence signals where
the predicate is `value != 0`, not a threshold compare.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random


@dataclass(frozen=True, slots=True)
class IndicatorThresholdSpec:
    """One indicator's threshold sampling profile.

    `directional_range` / `regime_range` are `(low, high)` tuples in the
    indicator's native units. The sampler picks uniformly within each.

    `op_directional` / `op_regime`: comparison operator. `<` means the signal
    fires when `indicator_value < threshold`; `>` for the inverse direction.
    Per Crucible's `ThresholdSignal._compare`.
    """

    directional_range: tuple[float, float] | None
    regime_range: tuple[float, float] | None
    op_directional: str = "<"
    op_regime: str = "<"
    is_skip: bool = False


# Stubs returning NaN under real Crucible — generic threshold; 0 fire rate
# until Crucible implements them properly (see CRUCIBLE_STUB_IMPLEMENTATIONS).
_STUB_SPEC = IndicatorThresholdSpec(
    directional_range=(0.3, 0.5),
    regime_range=(0.3, 0.5),
)

# Price-scale indicators — never threshold-style; passthrough-only.
_SKIP_SPEC = IndicatorThresholdSpec(
    directional_range=None,
    regime_range=None,
    is_skip=True,
)


_INDICATOR_THRESHOLD_TABLE: dict[str, IndicatorThresholdSpec] = {
    # ----- Bounded 0-100, oversold/overbought (RSI / ADX) -----
    "rsi": IndicatorThresholdSpec(
        directional_range=(20.0, 35.0),  # oversold: fires when RSI < threshold
        regime_range=(40.0, 70.0),  # allow window: trade when RSI < 70
    ),
    "rsi_14": IndicatorThresholdSpec(
        directional_range=(20.0, 35.0),
        regime_range=(40.0, 70.0),
    ),
    "rsi_2": IndicatorThresholdSpec(
        directional_range=(5.0, 15.0),  # rsi_2 is much more extreme
        regime_range=(20.0, 50.0),
    ),
    "adx": IndicatorThresholdSpec(
        directional_range=(25.0, 35.0),  # trend strong: fires when ADX > threshold
        regime_range=(15.0, 25.0),
        op_directional=">",  # ADX is "strength" — fires when above threshold
        op_regime=">",
    ),
    # ----- Bounded 0-1 / position-in-range -----
    "bb_pct": IndicatorThresholdSpec(
        directional_range=(0.05, 0.20),
        regime_range=(0.10, 0.80),
    ),
    "donchian": IndicatorThresholdSpec(
        directional_range=(0.05, 0.20),
        regime_range=(0.10, 0.80),
    ),
    "keltner_pct": IndicatorThresholdSpec(
        directional_range=(0.05, 0.20),
        regime_range=(0.10, 0.80),
    ),
    "hurst": IndicatorThresholdSpec(
        directional_range=(0.40, 0.50),  # mean-reverting: H < 0.5
        regime_range=(0.40, 0.60),
    ),
    # ----- Volatility (small positive, log-scale) -----
    "realized_vol": IndicatorThresholdSpec(
        directional_range=(0.08, 0.15),  # calm window for entry
        regime_range=(0.12, 0.25),
    ),
    "parkinson_vol": IndicatorThresholdSpec(
        directional_range=(0.08, 0.15),
        regime_range=(0.12, 0.25),
    ),
    "garman_klass_vol": IndicatorThresholdSpec(
        directional_range=(0.08, 0.15),
        regime_range=(0.12, 0.25),
    ),
    "yang_zhang_vol": IndicatorThresholdSpec(
        directional_range=(0.10, 0.18),
        regime_range=(0.15, 0.30),
    ),
    "atr_pct": IndicatorThresholdSpec(
        directional_range=(0.008, 0.015),
        regime_range=(0.012, 0.025),
    ),
    # ----- Z-score / sharpe (signed) -----
    "zscore_returns": IndicatorThresholdSpec(
        directional_range=(-2.0, -1.0),  # extreme low: fires when zscore < -1
        regime_range=(-1.5, 1.5),  # normal range
    ),
    "rolling_sharpe": IndicatorThresholdSpec(
        directional_range=(-0.5, 0.5),  # low sharpe entry
        regime_range=(0.5, 2.5),  # healthy regime: sharpe < 2.5
    ),
    # ----- Returns / momentum (signed) -----
    "momentum_252": IndicatorThresholdSpec(
        directional_range=(0.0, 0.15),  # uptrend entry: fires when momentum > 0-ish
        regime_range=(-0.05, 0.30),
        op_directional=">",
        op_regime=">",
    ),
    "returns_12m_skip1": IndicatorThresholdSpec(
        directional_range=(0.0, 0.15),
        regime_range=(-0.05, 0.30),
        op_directional=">",
        op_regime=">",
    ),
    "macd": IndicatorThresholdSpec(
        directional_range=(-1.0, 0.0),  # bearish cross
        regime_range=(-2.0, 2.0),
    ),
    # ----- Binary / categorical -----
    "ema_cross": IndicatorThresholdSpec(
        directional_range=(0.0, 0.0),  # threshold 0 — fires on sign change to negative
        regime_range=(-1.0, 1.0),
    ),
    "supertrend": IndicatorThresholdSpec(
        directional_range=(0.0, 0.0),
        regime_range=(-1.0, 1.0),
    ),
    "vol_regime": IndicatorThresholdSpec(
        directional_range=(1.0, 1.0),  # fires when regime < 1 (low_vol)
        regime_range=(0.0, 2.0),
    ),
    # ----- Calendar -----
    "days_to_fomc": IndicatorThresholdSpec(
        directional_range=(5.0, 14.0),  # fires when FOMC imminent
        regime_range=(7.0, 60.0),
    ),
    "days_to_earnings": IndicatorThresholdSpec(
        directional_range=(5.0, 30.0),
        regime_range=(7.0, 60.0),
    ),
    # ----- Stubs (NaN until Crucible implements; educated value ranges for v1.1+) -----
    # iv_rank: §3.5 R1 demands threshold <= 50 on mean_reversion regime; honored here.
    "iv_rank": IndicatorThresholdSpec(
        directional_range=(20.0, 40.0),  # low-IV entry
        regime_range=(10.0, 50.0),  # R1: <= 50.0
    ),
    "vix_level": IndicatorThresholdSpec(
        directional_range=(15.0, 22.0),  # low-vol entry window
        regime_range=(15.0, 30.0),  # calm-regime gate
    ),
    "put_call_flow": IndicatorThresholdSpec(
        directional_range=(-0.5, 0.0),  # bearish flow signal
        regime_range=(-0.3, 0.3),
    ),
    "pairs_zscore": IndicatorThresholdSpec(
        directional_range=(-2.0, -1.0),  # extreme divergence entry
        regime_range=(-1.5, 1.5),
    ),
    # expected_value_estimator: temporarily skipped (2026-05-14). Crucible's
    # v2 implementation makes a synchronous DBProxy call from inside its own
    # writer's compute loop, deadlocking the writer (see
    # CRUCIBLE_EV_DEADLOCK_AGENT_PROMPT.md). Restore the threshold ranges +
    # ops below once Crucible ships the BatchContext fix.
    #   directional_range=(0.0, 0.005), op_directional=">",
    #   regime_range=(0.0, 0.01),       op_regime=">",
    "expected_value_estimator": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=None,
        is_skip=True,
    ),
    # ----- Microstructure (low signal on SPY) -----
    "amihud": IndicatorThresholdSpec(
        directional_range=(0.0001, 0.001),
        regime_range=(0.0001, 0.001),
    ),
    # ----- Price-scale: skip from threshold; passthrough/confluence only -----
    "ema": _SKIP_SPEC,
    "ema_50": _SKIP_SPEC,
    "sma": _SKIP_SPEC,
}


def is_threshold_skippable(indicator_id: str) -> bool:
    """True if the indicator should not be used in threshold-style signals.

    Such indicators (price-scale ema/sma) are still valid in `passthrough`
    or comparison signals; this only excludes them from the directional /
    regime_filter threshold paths.
    """
    spec = _INDICATOR_THRESHOLD_TABLE.get(indicator_id)
    return spec is not None and spec.is_skip


def sample_threshold_params(
    indicator_id: str,
    role: str,
    rng: random.Random,
) -> dict[str, object]:
    """Sample `params` for a threshold-style SignalSpec.

    Returns `{"threshold": <float>, "op": <op_str>}` per the audited
    distribution. Unknown indicators get a defensive `{}` (which means the
    predicate never fires — visible upstream rather than silent).
    """
    spec = _INDICATOR_THRESHOLD_TABLE.get(indicator_id)
    if spec is None or spec.is_skip:
        return {}
    if role == "directional":
        if spec.directional_range is None:
            return {}
        low, high = spec.directional_range
        threshold = round(rng.uniform(low, high), 4) if low != high else low
        return {"threshold": threshold, "op": spec.op_directional}
    if role == "regime_filter":
        if spec.regime_range is None:
            return {}
        low, high = spec.regime_range
        threshold = round(rng.uniform(low, high), 4) if low != high else low
        return {"threshold": threshold, "op": spec.op_regime}
    # confluence / unrecognised role — no threshold (passthrough doesn't need one)
    return {}


__all__ = [
    "IndicatorThresholdSpec",
    "is_threshold_skippable",
    "sample_threshold_params",
]
