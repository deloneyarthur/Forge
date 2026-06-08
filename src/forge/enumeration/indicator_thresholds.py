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
    "expected_value_estimator": IndicatorThresholdSpec(
        directional_range=(0.0, 0.005),  # marginal EV
        regime_range=(0.0, 0.01),
        op_directional=">",  # fire when EV > threshold
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
      3. The indicator has no range for the requested role (D077: rv_rank
         has a regime_range but no directional_range).

    Such indicators are still valid in `passthrough` / `confluence`
    signals; this only excludes them from directional / regime_filter
    threshold paths.
    """
    spec = _INDICATOR_THRESHOLD_TABLE.get(indicator_id)
    if spec is None:
        return True
    if spec.is_skip:
        return True
    if role == "directional" and spec.directional_range is None:
        return True
    return role == "regime_filter" and spec.regime_range is None


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
        if spec.directional_range is None:
            return {}
        # v6 (D099): percentile-eligible indicators emit a [0,1] percentile
        # threshold + use_percentile, bypassing the native-unit auto-tightening.
        if spec.directional_percentile_range is not None:
            return _percentile_params(
                spec.directional_percentile_range,
                spec.op_directional,
                rng,
            )
        # D073: prefer auto-tightened range over D031 baseline when present.
        low, high = _effective_range(indicator_id, role, spec.directional_range)
        threshold = round(rng.uniform(low, high), 4) if low != high else low
        return {"threshold": threshold, "op": spec.op_directional}
    if role == "regime_filter":
        if spec.regime_range is None:
            return {}
        if spec.regime_percentile_range is not None:
            return _percentile_params(
                spec.regime_percentile_range,
                spec.op_regime,
                rng,
            )
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
