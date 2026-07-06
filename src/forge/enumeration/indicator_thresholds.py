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
  * `is_skip`: indicator can't be thresholded honestly (price-scale only)

D030's "stub" framing for iv_rank, vix_level, pairs_zscore, put_call_flow,
expected_value_estimator is obsolete as of D031 (2026-05-15) — Crucible
shipped real `version=2` implementations of all five and they were
re-calibrated with audited SPY-OOS ranges. They are now treated identically
to other bounded/signed indicators in this table.

Price-scale indicators (ema, ema_50, sma) are flagged `is_skip=True` because
their absolute values (~250-700 USD on SPY) make threshold-style signals
nonsensical. They remain valid for `passthrough` confluence signals where
the predicate is `value != 0`, not a threshold compare.
"""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

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
    # v6 (D099): when set for a role, the sampler emits a PERCENTILE threshold
    # (a value in [0, 1]) + use_percentile/percentile_window, instead of an
    # absolute value — Crucible ranks the latest indicator value against its
    # trailing window and compares that percentile. Scope = mean_reversion-
    # family directional oscillators + the adx/hurst trend regime gate (D099).
    directional_percentile_range: tuple[float, float] | None = None
    regime_percentile_range: tuple[float, float] | None = None


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
        directional_percentile_range=(0.05, 0.20),  # v6 (D099): enter in bottom 5-20%
    ),
    "rsi_14": IndicatorThresholdSpec(
        directional_range=(20.0, 35.0),
        regime_range=(40.0, 70.0),
        directional_percentile_range=(0.05, 0.20),  # v6 (D099): enter in bottom 5-20%
    ),
    "rsi_2": IndicatorThresholdSpec(
        directional_range=(5.0, 15.0),  # rsi_2 is much more extreme
        regime_range=(20.0, 50.0),
        directional_percentile_range=(0.05, 0.20),  # v6 (D099): the diagnosed-too-tight culprit
    ),
    "adx": IndicatorThresholdSpec(
        directional_range=(25.0, 35.0),  # trend strong: fires when ADX > threshold
        regime_range=(15.0, 25.0),
        op_directional=">",  # ADX is "strength" — fires when above threshold
        op_regime=">",
        regime_percentile_range=(0.25, 0.50),  # v6 (D099): loosen gate — allow ~top 50-75%
    ),
    # ----- Bounded 0-1 / position-in-range -----
    "bb_pct": IndicatorThresholdSpec(
        directional_range=(0.05, 0.20),
        regime_range=(0.10, 0.80),
        directional_percentile_range=(0.05, 0.20),  # v6 (D099): lower-band entry, bottom 5-20%
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
        directional_range=(0.40, 0.50),  # mean-reverting H<0.5 (mean_reversion directional)
        regime_range=(0.40, 0.60),
        op_regime=">",  # v7 (D100/Q26): trend regime = allow when TRENDING (H high)
        regime_percentile_range=(0.25, 0.50),  # v7 (D100): allow ~top 50-75%, mirrors adx
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
        directional_range=(-1.5, -0.5),  # D031 widened: -2/-1 was too extreme on SPY OOS
        regime_range=(-1.5, 1.5),  # normal range
        directional_percentile_range=(0.05, 0.20),  # v6 (D099): oversold z, bottom 5-20%
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
    # v23 (Crucible signal-quality handoff §2.1, D236): sma_slope (SMA-200
    # slope) is the best cross-sectional trend signal — rank-IC 0.078 @63d,
    # DOMINATES momentum_252 (0.059; momentum_252 adds -0.012 incremental once
    # sma_slope is held). Brand-new registry id (family=trend) with NO
    # Forge-side value distribution → PERCENTILE-ONLY directional (the
    # option_momentum / D138 precedent): fire when the slope ranks in the top
    # decile of its trailing window = strong, established uptrend. op ">"
    # high-side, distribution-free (no absolute range to mis-calibrate). The
    # swap sharpens SELECTION quality (WF), NOT the CPCV-p25 wall (handoff §0);
    # momentum_252 is RETAINED so the learned D106 directional weight ranks
    # sma_slope against it on live evidence rather than a hard swap.
    "sma_slope": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=None,
        op_directional=">",
        directional_percentile_range=(0.80, 0.90),
    ),
    # v23 (§2.5): ad_slope (accumulation/distribution-line slope), the volume-
    # family champion (registry family=trend). Weak standalone IC (0.016) but a
    # distinct volume-based read; added for sampling-space coverage per the
    # handoff. Same percentile-only pattern.
    "ad_slope": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=None,
        op_directional=">",
        directional_percentile_range=(0.80, 0.90),
    ),
    # v23 (§2.2, D236): returns_12m_skip1 is rank-corr 1.0 with momentum_252
    # (identical 12-1 computation) — PRUNED from the directional pool so the
    # same signal is not double-sampled (eff-N / alpha-budget hygiene). The
    # directional role is nulled → is_threshold_skippable('directional')=True;
    # the (unused) regime fields are kept dormant so the id stays documented.
    "returns_12m_skip1": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(-0.05, 0.30),
        op_regime=">",
    ),
    # v23 (§2.3, D236): macd is anti-momentum at 3-6m (negative IC) — PRUNED as
    # a trend directional (directional role nulled). Kept documented.
    "macd": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(-2.0, 2.0),
    ),
    # ----- Binary / categorical -----
    # v23 (§2.3, D236): ema_cross(12/26) + supertrend are anti-momentum or
    # redundant with sma_slope (golden-cross ema_cross_50_200 is a separate,
    # unregistered id) — PRUNED as trend directionals (directional role nulled).
    "ema_cross": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(-1.0, 1.0),
    ),
    "supertrend": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(-1.0, 1.0),
    ),
    "vol_regime": IndicatorThresholdSpec(
        directional_range=(1.0, 1.0),  # fires when regime < 1 (low_vol)
        regime_range=(0.0, 2.0),
    ),
    # ----- Calendar -----
    "days_to_fomc": IndicatorThresholdSpec(
        directional_range=(5.0, 14.0),  # fires when FOMC imminent
        # D236 (v23, §2d): event-proximity window tightened 60d → 14d. VE books
        # fired at a median ~31d (mostly 21-40d) — too wide; the directional
        # dealer-wall / call-wall edge concentrates ≤~10d pre-FOMC and decays
        # wider, while ≤5d loses too many trades. op '<' → fires when
        # days_to_fomc < threshold, so [7, 14] centres firing on the ~10d sweet
        # spot (median 10.5d). FOMC-only: cpi/nfp/opex keep their ranges pending
        # their own evidence (handoff ranks FOMC > opex > cpi/nfp).
        regime_range=(7.0, 14.0),
    ),
    "days_to_earnings": IndicatorThresholdSpec(
        directional_range=(5.0, 30.0),
        regime_range=(7.0, 60.0),
    ),
    # M-9 (audit 2026-05-29): T1.4/D039 widened R3's event-proximity pool to
    # these macro-calendar indicators to make `volatility_event` usable on ETFs
    # (which return sentinel 999 for days_to_earnings). They were never added
    # here, so `is_threshold_skippable(..., 'regime_filter')` filtered them out
    # and the widening was inert. Mirror days_to_fomc's "event imminent" /
    # allow-window ranges (all are days-to-event countdowns with the same scale).
    "days_to_cpi": IndicatorThresholdSpec(
        directional_range=(5.0, 14.0),
        regime_range=(7.0, 60.0),
    ),
    "days_to_nfp": IndicatorThresholdSpec(
        directional_range=(5.0, 14.0),
        regime_range=(7.0, 60.0),
    ),
    "days_to_opex": IndicatorThresholdSpec(
        directional_range=(3.0, 10.0),  # OPEX is monthly — tighter imminence window
        regime_range=(5.0, 30.0),
    ),
    # ----- H2 (v12 / D109): event_momentum / PEAD -----
    # `sue` (standardized unexpected earnings) is event_momentum's DIRECTIONAL:
    # a strong positive surprise predicts upward drift -> long calls. Fires when
    # sue > threshold; the range targets a meaningful 1-2 sigma beat (SUE is unit-
    # standardized, so these are sigmas, not native units). Directional-only —
    # the post-event TIMING is the days_since_earnings regime gate below.
    # NB: provisional calibration (operator-reviewable, like every table entry);
    # no live SUE distribution audit yet — see docs/INDICATOR_THRESHOLDS.md.
    "sue": IndicatorThresholdSpec(
        directional_range=(1.0, 2.0),
        regime_range=None,
        op_directional=">",
    ),
    # `days_since_earnings` is the post-event WINDOW gate: "fire within N td
    # AFTER the print" → op "<", threshold in {3..10} td. This is the PEAD edge —
    # entering after the print sidesteps the pre-print IV crush the vol_event
    # sleeves ride, so the component is structurally orthogonal to them.
    # Regime-only (calendar family, post-§2.1) — never a directional.
    "days_since_earnings": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(3.0, 10.0),
        op_regime="<",
    ),
    # ----- IV / event / pairs / macro (post-D031 real Crucible v2 implementations) -----
    # iv_rank: §3.5 R1 demands threshold <= 50 on mean_reversion regime; honored here.
    "iv_rank": IndicatorThresholdSpec(
        directional_range=(20.0, 40.0),  # low-IV entry
        regime_range=(10.0, 50.0),  # R1: <= 50.0
    ),
    "vix_level": IndicatorThresholdSpec(
        # D031: widened from (15, 22). Real SPY VIX OOS mean=16.7 with most
        # days 14-22; old range sampled thresholds often below median, firing <20%.
        directional_range=(18.0, 25.0),
        regime_range=(15.0, 30.0),  # calm-regime gate
    ),
    "put_call_flow": IndicatorThresholdSpec(
        directional_range=(-0.5, 0.0),  # bearish flow signal
        regime_range=(-0.3, 0.3),
    ),
    "pairs_zscore": IndicatorThresholdSpec(
        # D031: widened from (-2, -1). relative_value's only directional pool
        # is pairs_zscore, so fire-rate dominates trade_count for that hypothesis.
        directional_range=(-1.5, -0.5),
        regime_range=(-1.5, 1.5),
    ),
    # D138 (v19): directional_range NULLED to pin EV out of the directional
    # path. Admitting `smart_money` to trend_continuation's C2 pool (for
    # option_momentum) would otherwise make EV a directional candidate; EV is the
    # X2 fractional-kelly sizer feature (runs-DB, reference-keyed) — never an
    # honest per-name directional. Regime/gate use (op ">") is untouched.
    # Behavior-preserving on v18 (smart_money was in no C2 hypothesis → EV was
    # never a directional anyway).
    "expected_value_estimator": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(0.0, 0.01),
        op_regime=">",
    ),
    # ----- Realized-vol percentile rank (D077, Crucible rv_rank.py) -----
    # 0 = vol at trailing min (cheap), 100 = vol at trailing max (expensive).
    # PTS thesis: enter when vol is LOW → op_regime = "<".
    "rv_rank": IndicatorThresholdSpec(
        directional_range=None,  # rv_rank is regime-only; not a directional signal
        regime_range=(25.0, 75.0),  # [25, 50, 75] per PTS calibration
        op_regime="<",  # fire when rv_rank < threshold (vol is cheap)
    ),
    # ----- D131 (v17) activations — Crucible 2026-06-10 indicator batch -----
    # iv_minus_rv: per-name ATM IV minus trailing 21d realized vol, annualized
    # decimals (Crucible as-built: AAPL 2024 median +0.01, range -0.14..+0.25).
    # The Goyal-Saretto (JFE 2009) single-name premium conditioner. For the
    # net-debit book (their Q34 answer: every MR/ve template is long premium)
    # the documented edge buys where IV is CHEAP vs realized → op "<", with
    # the range spanning "clearly cheap" (-0.05) to "at the median" (+0.01) —
    # selectivity ~10-50%. Provenance is their one-name summary stats; refine
    # against funnel evidence (D131). volatility_event DIRECTIONAL via C2
    # (iv_structure); regime use deliberately None (the R1-sibling question
    # stays open per Q34's coda — admitting it as a GATE is a future rule
    # decision, not an activation).
    "iv_minus_rv": IndicatorThresholdSpec(
        directional_range=(-0.05, 0.01),
        regime_range=None,
        op_directional="<",  # fire when IV cheap vs the name's own realized
    ),
    # ----- D135 (v18) adoption — Crucible shelf indicators -----
    # iv_term_slope: per-name ATM IV at ~back_dte(90cal) minus ATM IV at
    # ~front_dte(30cal), annualized decimals (Vasquez JFQA 2017: upward slope
    # positively predicts the name's option returns → op ">", buy steep
    # contango). Range AUDITED against the live feature cache (2026-06-11
    # probe, 6 names x ~2,119 bars): median ≈ +0.005..+0.01; "> 0.01" fires
    # on ~44-49% of bars, "> 0.04" on ~5-20% — so (0.01, 0.04) spans
    # above-median to clearly-steep at the same ~10-50% selectivity band as
    # iv_minus_rv. Known failure mode (their as-built note): imminent
    # earnings inflate FRONT IV → fake-NEGATIVE slope → the ">" gate goes
    # quiet pre-earnings (a conservative miss, not a false fire).
    # volatility_event DIRECTIONAL via C2 (iv_structure); the second
    # medium-horizon ve anchor (A2 → full Q28 lift). Regime use deliberately
    # None (the R1-sibling gate question stays open, as with iv_minus_rv).
    "iv_term_slope": IndicatorThresholdSpec(
        directional_range=(0.01, 0.04),
        regime_range=None,
        op_directional=">",
    ),
    # option_momentum: ACTIVATED v19 (D138) as a trend_continuation directional
    # (smart_money pinned to trend's C2 families). PERCENTILE-ONLY by design —
    # Crucible's coverage handoff (2026-06-12) showed the as-built straddle
    # return (front-expiry, ~34→4 DTE) is a near-total theta harvest whose level
    # scales with the name's IV, so a fixed ABSOLUTE threshold is a cross-
    # sectional inverse-IV sort (a confound their gate would reject), NOT the
    # Heston-et-al. momentum signal. Percentile over the name's own history
    # normalizes that offset. op ">" buys the name's recent option-return
    # winners; (0.80, 0.90) is the top-10-20% winner extreme (mirrors the
    # bottom-5-20% oversold percentile ranges). directional_range=None → no
    # absolute threshold is ever sampled (the percentile-only path). The
    # min_months=3 coverage knob rides _sample_option_momentum_params (probe-
    # audited: clears the §5.3.3 min_activations=30 floor on all 10 probed
    # names; scripts/probe_option_momentum_min_months.py). Horizon 126 td (long)
    # already in signal_horizon → swing_long DTE. Regime use None.
    "option_momentum": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=None,
        op_directional=">",
        directional_percentile_range=(0.80, 0.90),
    ),
    # pre_earnings_setup: composed binary conditioner — 1.0 iff
    # days_to_earnings ∈ [enter_min, enter_max] AND rv_rank < rv_q (Chung &
    # Louis / Gao-Xing-Zhang: buy premium ~5-10 td pre-announcement when
    # recent realized vol is LOW; Crucible's mandatory earnings_exit forces
    # the pre-event exit, dodging the decayed announcement-hold leg). Gate
    # `> 0.5` is degenerate by design (binary emission — the market_state
    # precedent); the real knobs (enter window / rv_q) ride the same params
    # via the sampler (`_sample_pre_earnings_setup_params`). Regime-only:
    # an R3-class event-proximity gate, never a directional. Probe
    # (2026-06-11): fires 114-152 days/name at [7,14]/q50 — comfortably
    # above the min_activations floor.
    "pre_earnings_setup": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(0.5, 0.5),
        op_regime=">",
    ),
    # market_state: sign of the reference's trailing 252-session return,
    # emits ±1 (0 only on an exactly-flat window). Threshold is degenerate by
    # design: the only meaningful cut is 0 (up-market vs down-market —
    # Cooper/Gutierrez/Hameed JF 2004; momentum pays after up-markets).
    # (0.0, 0.0) makes the sampler emit exactly threshold=0.0. Gate-only:
    # R2 pool member as of v17 (D131).
    "market_state": IndicatorThresholdSpec(
        directional_range=None,
        regime_range=(0.0, 0.0),
        op_regime=">",  # fire in up-market state
    ),
    # ----- Microstructure (low signal on SPY) -----
    "amihud": IndicatorThresholdSpec(
        directional_range=(0.0001, 0.001),
        regime_range=(0.0001, 0.001),
    ),
    # ----- Dealer positioning (§4.3.5) — wall / flip distances are bounded
    # percentages, so honest threshold sampling is feasible. GEX/VEX/CEX are
    # raw $-scale aggregates that vary by orders of magnitude across
    # underlyings, so they ship as confluence-only for v1 — add empirical
    # ranges after first sweep produces real distributions. -----
    "call_wall_distance_pct": IndicatorThresholdSpec(
        # Fires when call wall is sitting just above spot (resistance pin):
        # typical SPY range during low-vol regimes is +1% to +5% above spot.
        directional_range=(0.005, 0.025),
        regime_range=(0.0, 0.05),
        op_directional="<",
        op_regime="<",
    ),
    "put_wall_distance_pct": IndicatorThresholdSpec(
        # Negative-valued (wall below spot). Fires when support nearby:
        # -3% to -0.5% — wall close above means stretched/stressed regime.
        directional_range=(-0.03, -0.005),
        regime_range=(-0.05, 0.0),
        op_directional=">",  # fires when distance > -0.X (close to spot)
        op_regime=">",
    ),
    "gamma_flip_distance_pct": IndicatorThresholdSpec(
        # Positive = flip above spot → dealers short gamma → vol amplifying.
        # Directional fires on transition into short-gamma regime; regime
        # gates wide around the flip.
        directional_range=(0.0, 0.03),
        regime_range=(-0.05, 0.05),
        op_directional=">",
        op_regime=">",
    ),
    "gex": _SKIP_SPEC,  # raw $-scale; confluence-only until sampled distribution
    "vex": _SKIP_SPEC,
    "cex": _SKIP_SPEC,
    # ----- Price-scale: skip from threshold; passthrough/confluence only -----
    "ema": _SKIP_SPEC,
    "ema_50": _SKIP_SPEC,
    "sma": _SKIP_SPEC,
    # atr returns price-scale values (true range in dollars). Like ema/sma,
    # threshold semantics depend on the underlying's absolute price level,
    # which makes a fixed (low, high) range honest-impossible. Skip from
    # directional/regime; still available as a confluence indicator.
    "atr": _SKIP_SPEC,
}


# D073 / Phase 3 — auto-tightened threshold overrides.
#
# `config/auto_tightened_thresholds.yaml` (written by
# `scripts/propose_threshold_tightenings.py` from gated_runs outcomes)
# carries per-(indicator, role) range overrides derived from configs
# that produced ≥10 trades. The sampler prefers these ranges over the
# D031 audited defaults ONLY WHEN the proposed range is strictly
# tighter than D031 (hard rule #4: no auto-loosening).
#
# Loaded lazily on first sampler call, cached for the rest of the
# process lifetime. Restart forge.service to pick up a new YAML.
_AUTO_TIGHTENINGS_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "auto_tightened_thresholds.yaml"
)


@functools.lru_cache(maxsize=1)
def _auto_tightenings() -> dict[tuple[str, str], tuple[float, float]]:
    """Return per-(indicator_id, role) → (low, high) auto-tightened ranges.

    Empty dict when the YAML is absent (cold-start, or proposer not yet
    run). Each entry is validated against the D031 baseline:
    proposed_low >= baseline_low AND proposed_high <= baseline_high.
    Loosening entries are silently skipped (the proposer is supposed to
    route loosening to OPEN_PROPOSALS.md, but this loader is defensive).
    """
    if not _AUTO_TIGHTENINGS_PATH.exists():
        return {}
    try:
        raw = yaml.safe_load(_AUTO_TIGHTENINGS_PATH.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}
    out: dict[tuple[str, str], tuple[float, float]] = {}
    for entry in raw.get("tightenings", []):
        ind_id = entry.get("indicator_id")
        role = entry.get("role")
        proposed = entry.get("proposed_range")
        if not (
            isinstance(ind_id, str)
            and isinstance(role, str)
            and isinstance(proposed, list)
            and len(proposed) == 2
        ):
            continue
        p_low, p_high = float(proposed[0]), float(proposed[1])
        # Validate against D031 baseline (defensive — proposer should already
        # have done this).
        spec = _INDICATOR_THRESHOLD_TABLE.get(ind_id)
        if spec is None or spec.is_skip:
            continue
        if role == "directional":
            base = spec.directional_range
        elif role == "regime_filter":
            base = spec.regime_range
        else:
            continue
        if base is None:
            continue
        b_low, b_high = base
        if not (p_low >= b_low and p_high <= b_high and p_low <= p_high):
            continue  # loosening or degenerate — skip
        out[(ind_id, role)] = (p_low, p_high)
    return out


def _effective_range(
    indicator_id: str,
    role: str,
    baseline: tuple[float, float],
) -> tuple[float, float]:
    """Return the auto-tightened range if present, else the D031 baseline."""
    return _auto_tightenings().get((indicator_id, role), baseline)


def auto_tightenings_fingerprint() -> str:
    """H-3: stable 16-hex fingerprint of the ACTIVE auto-tightenings.

    These ranges (D073) shadow the sampler's threshold draws but aren't in
    `registry_hash` or `grammar_version`, so a proposer rewrite of
    `auto_tightened_thresholds.yaml` silently changed the enumerated sequence
    with no change to the recorded identity (hard rule #6 violation). This
    fingerprint folds into `mint_batch_id` + `batch_summaries` so the identity
    tracks the inputs. Hashes the VALIDATED set (post-baseline-filter), so
    comment/formatting churn in the YAML doesn't move the hash — only the
    ranges that actually affect enumeration do. Empty set → fixed hash.
    """
    normalized = sorted(
        [ind, role, low, high] for (ind, role), (low, high) in _auto_tightenings().items()
    )
    payload = json.dumps(normalized, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def is_threshold_skippable(indicator_id: str, role: str = "directional") -> bool:
    """True if the indicator should not be used in threshold-style signals.

    Returns True in three cases:
      1. Explicit `is_skip=True` in the table (price-scale ema/sma/atr).
      2. Indicator is NOT in the table at all — defensive: if the registry
         adds an indicator that lacks an audited threshold range, we don't
         silently emit a `type='threshold'` SignalSpec with empty params
         (which Crucible's predicate treats as "never fires" → 0 trades
         → gate-reject on min_oos_trade_count). The audit-test in
         `tests/unit/test_enumeration/test_no_empty_threshold_leak.py`
         enforces this invariant.
      3. The indicator has no absolute AND no percentile range for the
         requested role (D077: rv_rank has a regime_range but no
         directional_range; D138: option_momentum is percentile-only — a
         directional_percentile_range with no directional_range IS samplable).

    Such indicators are still valid in `passthrough` / `confluence`
    signals; this only excludes them from directional / regime_filter
    threshold paths.
    """
    spec = _INDICATOR_THRESHOLD_TABLE.get(indicator_id)
    if spec is None:
        return True
    if spec.is_skip:
        return True
    # Samplable in a role iff it has EITHER an absolute range OR a percentile
    # range for that role (D138: the percentile-only path, e.g. option_momentum).
    if role == "directional":
        return spec.directional_range is None and spec.directional_percentile_range is None
    if role == "regime_filter":
        return spec.regime_range is None and spec.regime_percentile_range is None
    return False


# v6 (D099): percentile-emission window. Crucible ranks the latest indicator
# value against its trailing `_PERCENTILE_WINDOW` bars; the default mirrors
# Crucible's percentile-mode default (1 trading year).
_PERCENTILE_WINDOW = 252


def is_percentile_emitting(indicator_id: str, role: str = "directional") -> bool:
    """True if `(indicator_id, role)` emits a PERCENTILE threshold under v6.

    Percentile-eligible pairs (D099) emit `use_percentile=True` + a `threshold`
    in [0, 1] instead of an absolute value. Exposed so the native-unit
    auto-tightening path (D073) and the threshold proposer can stay out of
    percentile space — a native-unit tightening is meaningless for a [0, 1]
    percentile (and the loader's baseline check would reject it anyway).
    """
    spec = _INDICATOR_THRESHOLD_TABLE.get(indicator_id)
    if spec is None or spec.is_skip:
        return False
    if role == "directional":
        return spec.directional_percentile_range is not None
    if role == "regime_filter":
        return spec.regime_percentile_range is not None
    return False


def _percentile_params(
    prange: tuple[float, float],
    op: str,
    rng: random.Random,
) -> dict[str, object]:
    """Build percentile-mode `params` for a threshold SignalSpec (D099).

    `prange` is a `(low, high)` PERCENTILE range in [0, 1]. The draw consumes
    the same single `rng.uniform` as the absolute path, so the seeded sequence
    is unchanged (hard rule #6) — only the emitted value + the two extra keys
    differ. `op` is carried over unchanged from the absolute table: percentile
    mode swaps the units of `threshold`, never the firing direction.
    """
    low, high = prange
    threshold = round(rng.uniform(low, high), 4) if low != high else low
    return {
        "threshold": threshold,
        "op": op,
        "use_percentile": True,
        "percentile_window": _PERCENTILE_WINDOW,
    }


def sample_threshold_params(  # noqa: PLR0911 — one return per (role, percentile/absolute) branch
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
        # v6 (D099) / D138: percentile-eligible indicators emit a [0,1]
        # percentile threshold + use_percentile, bypassing the native-unit
        # auto-tightening. Checked BEFORE the absolute-range guard so a
        # PERCENTILE-ONLY directional (directional_range None, percentile set —
        # option_momentum) still emits. Dual-range indicators hit this same
        # branch as before, consuming one rng.uniform either way, so the seeded
        # sequence is unchanged (#6).
        if spec.directional_percentile_range is not None:
            return _percentile_params(
                spec.directional_percentile_range,
                spec.op_directional,
                rng,
            )
        if spec.directional_range is None:
            return {}
        # D073: prefer auto-tightened range over D031 baseline when present.
        low, high = _effective_range(indicator_id, role, spec.directional_range)
        threshold = round(rng.uniform(low, high), 4) if low != high else low
        return {"threshold": threshold, "op": spec.op_directional}
    if role == "regime_filter":
        # D138: percentile-first, mirroring the directional branch (supports a
        # future percentile-only regime gate without an empty-params leak).
        if spec.regime_percentile_range is not None:
            return _percentile_params(
                spec.regime_percentile_range,
                spec.op_regime,
                rng,
            )
        if spec.regime_range is None:
            return {}
        low, high = _effective_range(indicator_id, role, spec.regime_range)
        threshold = round(rng.uniform(low, high), 4) if low != high else low
        return {"threshold": threshold, "op": spec.op_regime}
    # confluence / unrecognised role — no threshold (passthrough doesn't need one)
    return {}


__all__ = [
    "IndicatorThresholdSpec",
    "is_percentile_emitting",
    "is_threshold_skippable",
    "sample_threshold_params",
]
