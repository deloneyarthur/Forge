"""Forge-owned signal-horizon table — the input to §3.5 S4 and the v8
horizon-matched DTE derivation (D102).

WHY this exists (and why the horizon is not read from the registry):
Crucible's published ``RegistrySnapshot`` does not carry a usable
``IndicatorMetadata.lookback``. On the live snapshot the service loads,
**34 of 43 indicators report ``lookback=0``** and the 9 that are populated
are not signal horizons (``rsi_2`` reports 14, ``ema_50`` reports 200, while
``adx``/``hurst``/``macd``/``bb_pct``/``zscore_returns`` all report 0). Used
directly that field collapses §3.5 S4 to "almost everything -> swing_short"
and actively produces horizon-*mismatched* configs (a MACD trend signal at a
2-3 week DTE).

So Forge owns the horizon the same way it already owns per-indicator
threshold ranges in ``forge.enumeration.indicator_thresholds`` — as
auditable enumeration-policy domain knowledge keyed by indicator id. The
period is encoded in the indicator's identity (``rsi_2`` vs ``rsi_14`` vs
``momentum_252``), which is exactly what this table recovers.

The number is a *signal horizon* (how long the thesis takes to play out),
NOT a *measurement/warmup window*. They differ for slow regime measures:
``iv_rank`` summarises 252 days but its level mean-reverts over ~weeks, so its
horizon here is 30, not 252. Likewise the dealer-positioning / event-proximity
indicators are near-instantaneous reads, horizon ~1-5.

Confirmed by Crucible (`FORGE_horizon_dte_response.md`, 2026-06-05):
``IndicatorMetadata.lookback`` IS a warmup/measurement window by contract (the
rows masked NaN before the indicator is computable), NOT a signal horizon — so
it was never the right §3.5 S4 input, and this Forge-owned table is the
**permanent** end state. **Do NOT migrate S4 back onto the registry field** — it
would be a category error (e.g. ``iv_rank`` warmup 252 vs its ~30-day mean-
reversion horizon). The registry's populated values are correct warmups read
wrong (``ema_50=200`` is EWM convergence, ``rsi_2=14`` is the RSI warmup); the 0s
are benign under-population (``compute()`` self-masks the true, param-dependent
warmup), not a live bug.

Operator-owned in spirit (it parameterises §3.5 S4): change values with a
``grammar_version`` bump and a Decision Log entry, as with the threshold table.
"""

from __future__ import annotations

from collections.abc import Sequence

# §3.5 S4 / D010 horizon-class thresholds, in trading days. A signal whose
# (max-over-indicators) horizon is <= SHORT_MAX is "short_lookback"; <=
# MEDIUM_MAX is "medium_lookback"; otherwise "long_lookback". These mirror the
# operator-confirmed D010 bucketing (Phase 1 kickoff Q2, 2026-05-13) — only the
# *input* moves from registry lookback to this table (D102).
HORIZON_SHORT_MAX = 6
HORIZON_MEDIUM_MAX = 89  # long_lookback is anything >= 90

# Fallback for indicators not yet in the table (a future registry addition).
# Medium keeps a newcomer explorable across swing_short/swing_mid rather than
# pinning it; the coverage invariant test forbids real threshold-eligible
# indicators from relying on it.
_DEFAULT_HORIZON_DAYS = 20

# indicator_id -> signal horizon in trading days. Grouped by family/role.
_SIGNAL_HORIZON_TABLE: dict[str, int] = {
    # ----- mean_reversion family directionals (oscillator period) -----
    "rsi_2": 2,  # 2-day RSI — the fast reversion read
    "rsi_14": 14,
    "rsi": 14,  # default RSI period
    "bb_pct": 20,  # %B over the default 20-bar band
    "keltner_pct": 20,
    "zscore_returns": 20,  # ~1-month return z-score
    # ----- trend family directionals (trend lookback) -----
    "macd": 26,  # slow-EMA leg of MACD(12,26,9)
    "momentum_252": 252,  # 12-month momentum
    "returns_12m_skip1": 252,
    # v23 (Crucible signal-quality handoff §2.1/§2.5): the SMA-200 slope is a
    # slow trend read — long_lookback, the SAME DTE-bucket class as the
    # momentum_252 it is meant to out-rank (a clean signal swap, not a bucket
    # move). ad_slope (A/D-line slope) is a faster volume-trend read → medium.
    "sma_slope": 200,  # SMA-200 slope
    "ad_slope": 60,  # accumulation/distribution-line slope (~quarter)
    # D264 (v27): residual momentum's DRIFT horizon (~a quarter), NOT its
    # formation window (the sampled `window` param, 63-252 td, rides SignalSpec
    # params and is invisible to S4). 63 → medium_lookback, and the D102
    # k∈{2,3,4} derivation snaps every target (126/189/252) to swing_mid — the
    # Crucible-validated probe chassis. Deliberate: one id gets one horizon, so
    # swing_mid-vs-swing_long was NOT expressible; the operator chose the
    # validated bucket (OPEN_PROPOSALS 0a4d8da8).
    "residual_momentum": 63,
    "ema_cross": 50,  # slow leg of the cross
    "ema_50": 50,
    "ema": 20,
    "sma": 50,
    "supertrend": 10,  # ATR(10) trailing trend
    "rolling_sharpe": 60,  # ~quarter rolling Sharpe
    "donchian": 20,  # 20-bar channel breakout
    # ----- trend_strength regimes -----
    "adx": 14,  # ADX(14)
    "hurst": 100,  # Hurst exponent needs a long window
    "rv_rank": 252,  # realized-vol rank over 1y
    # D258 (v25): days_since_jump saturates at a 252-td window (min_bars 253), so
    # it mirrors rv_rank's 1y class. S4 reads ONLY the directional signal's
    # horizon (not regime gates), so this value does not constrain which DTE
    # bucket may carry the veto — it attaches on the champion's short holds too.
    "days_since_jump": 252,
    # D263 (v26): ivol = per-name CAPM-residual idiosyncratic vol over a 63-td
    # window (the Crucible-validated MR veto window). Regime-only gate; S4 reads
    # only the directional signal's horizon, so this does not constrain the DTE
    # bucket — present for the horizon-coverage invariant.
    "ivol": 63,
    # ----- volatility family (regime / X1 chain) -----
    "realized_vol": 20,  # 21-day realized vol
    "parkinson_vol": 20,
    "garman_klass_vol": 20,
    "yang_zhang_vol": 20,
    "atr_pct": 14,
    "atr": 14,
    "vol_regime": 20,
    "amihud": 20,
    # ----- iv_structure / event directional + regime -----
    # Signal horizon (level mean-reverts over ~weeks), NOT the 252-day window.
    "iv_rank": 30,
    # D131 (v17): the IV-vs-realized spread converges over roughly its own
    # realized window (21 td) — medium_lookback → swing_short/swing_mid (S4),
    # which is what makes ve x swing_mid reachable (the partial Q28 lift; the
    # full lift adds iv_term_slope at the post-their-v10 cut, roadmap A2).
    "iv_minus_rv": 21,
    # D135 (v18): per-name IV term-structure slope (Vasquez JFQA 2017 —
    # monthly-sorted predictor; the slope mean-reverts over ~a month).
    # medium_lookback → swing_short/swing_mid: the SECOND medium-horizon ve
    # anchor, satisfying the roadmap A2 condition (full Q28 ve x swing_mid
    # lift; iv_minus_rv was the first, v17).
    "iv_term_slope": 21,
    # D135 (v18): trailing 6-completed-month straddle-return mean (Heston et
    # al. JF 2023; persistence 6-36 months). long_lookback → swing_mid/long.
    # Shelf-classed only — NOT activated in v18 (no threshold entry): the
    # 2026-06-11 live probe showed the series data-starved on the current
    # tier (Q39). The entry makes the eventual activation a one-line flip.
    "option_momentum": 126,
    # D131 (v17): trailing-252-session sign — a long, slow regime. Gate-only
    # (no directional_range), so S4 never consults this; the entry satisfies
    # the thresholdable-coverage invariant honestly.
    "market_state": 252,
    "vix_level": 1,  # spot VIX
    # D264 (v27): spot term-structure read, mirrors vix_level. Gate-only (no
    # directional range), so S4 never consults this; the entry satisfies the
    # thresholdable-coverage invariant honestly (the market_state precedent).
    "vix_term_slope": 1,
    # ----- flow / calendar (event proximity — near-instant reads) -----
    "put_call_flow": 5,
    "days_to_earnings": 5,
    "days_to_fomc": 5,
    "days_to_cpi": 5,
    "days_to_nfp": 5,
    "days_to_opex": 5,
    # H2 (v12 / D109): days_since_earnings is the calendar countdown AFTER the
    # print (backward twin of days_to_earnings) — a near-instant read, horizon 5.
    "days_since_earnings": 5,
    # D135 (v18): composed days_to_earnings x rv_rank pre-earnings conditioner —
    # an event-proximity read like its parents. Gate-only (no directional_range),
    # so S4 never consults this; the entry satisfies the thresholdable-coverage
    # invariant honestly (the market_state precedent).
    "pre_earnings_setup": 5,
    # ----- post_event_drift (H2 / PEAD directional) -----
    # `sue` (standardized unexpected earnings): the surprise is known instantly,
    # but its DRIFT — the tradeable edge — plays out over ~5-20 td. The signal
    # horizon is that drift window (10 td → medium_lookback → swing_short/mid),
    # NOT the instant the number prints.
    "sue": 10,
    # ----- dealer_positioning (instantaneous gamma/wall geometry) -----
    "call_wall_distance_pct": 1,
    "put_wall_distance_pct": 1,
    "gamma_flip_distance_pct": 1,
    "gex": 1,
    "vex": 1,
    "cex": 1,
    # ----- smart_money / pairs -----
    "expected_value_estimator": 60,  # X2 kelly chain feature
    "pairs_zscore": 60,  # cointegration spread ~quarter
}

# §3.5 S4: horizon class -> allowed DTE buckets. Replaces the registry-driven
# ``custom_predicates._LOOKBACK_DTE_TABLE`` as the single source of truth (D102).
BUCKETS_FOR_HORIZON_CLASS: dict[str, tuple[str, ...]] = {
    "short_lookback": ("swing_short",),
    "medium_lookback": ("swing_short", "swing_mid"),
    "long_lookback": ("swing_mid", "swing_long"),
}

# Midpoints of the §3.5 P2 entry-DTE windows (14-21 / 30-45 / 60-90). The v8
# derivation snaps a continuous ``k * horizon`` target to the nearest bucket by
# these midpoints. Kept as literals to avoid a grammar<-enumeration import
# cycle; ``test_signal_horizon.test_bucket_midpoints_match_p2_windows`` guards
# them against ``custom_predicates._P2_ENTRY_DTE`` drift.
_BUCKET_MIDPOINTS: dict[str, float] = {
    "swing_short": 17.5,
    "swing_mid": 37.5,
    "swing_long": 75.0,
}

# Canonical order for deterministic nearest-bucket tie-breaking (#6): a target
# equidistant from two buckets resolves to the shorter (lower-DTE) one.
_BUCKET_ORDER: dict[str, int] = {"swing_short": 0, "swing_mid": 1, "swing_long": 2}


def signal_horizon_days(indicator_id: str) -> int:
    """Signal horizon for ``indicator_id`` in trading days (table or default)."""
    return _SIGNAL_HORIZON_TABLE.get(indicator_id, _DEFAULT_HORIZON_DAYS)


def horizon_class_for_days(days: int) -> str:
    """Bucket a horizon (trading days) into the §3.5 S4 lookback class."""
    if days <= HORIZON_SHORT_MAX:
        return "short_lookback"
    if days <= HORIZON_MEDIUM_MAX:
        return "medium_lookback"
    return "long_lookback"


def horizon_class(indicator_id: str) -> str:
    """The §3.5 S4 lookback class of a single indicator, by its horizon."""
    return horizon_class_for_days(signal_horizon_days(indicator_id))


def buckets_for_horizon_class(klass: str) -> tuple[str, ...]:
    """DTE buckets §3.5 S4 permits for a horizon class (``()`` if unknown)."""
    return BUCKETS_FOR_HORIZON_CLASS.get(klass, ())


def nearest_bucket(allowed: Sequence[str], target_days: float) -> str:
    """Snap a continuous DTE target to the nearest bucket in ``allowed`` (#8).

    "Nearest" is by the §3.5 P2 window midpoint. Ties resolve to the shorter
    bucket via the canonical order, so the choice is fully deterministic (#6).
    ``allowed`` must be non-empty (callers pass a horizon-class-permitted set
    that is guaranteed non-empty for any real horizon).
    """
    return min(
        allowed,
        key=lambda b: (abs(_BUCKET_MIDPOINTS[b] - target_days), _BUCKET_ORDER[b]),
    )


__all__ = [
    "BUCKETS_FOR_HORIZON_CLASS",
    "HORIZON_MEDIUM_MAX",
    "HORIZON_SHORT_MAX",
    "buckets_for_horizon_class",
    "horizon_class",
    "horizon_class_for_days",
    "nearest_bucket",
    "signal_horizon_days",
]
