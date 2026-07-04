"""v23 trend-grammar hygiene — Crucible signal-quality handoff (2026-07-03).

Enforces the enumeration-policy changes that ride grammar_version v23
(`docs/tasks/grammar-change.md` classification #2; the §3.5 `rules:` text is
untouched). Refs: `IMPLEMENTATION_DECISIONS.md` D-entry, the handoff
`../Crucible/docs/handoffs/FORGE_signal_quality_champions_2026-07-03.md`.

  §2.1  sma_slope + ad_slope become enumerable trend directionals. They are
        brand-new registry ids with no Forge-side value distribution, so they
        use PERCENTILE-ONLY directional ranges (the option_momentum / D138
        precedent) — distribution-free, no Crucible data dependency.
  §2.2  returns_12m_skip1 (≡ momentum_252, cross-sectional rank-corr 1.0) is
        pruned from the DIRECTIONAL pool so the same 12-1 momentum signal is
        not double-sampled (eff-N / alpha-budget hygiene). momentum_252 is
        RETAINED — the learned D106 directional weight decides
        sma_slope-vs-momentum_252 organically, not a hard swap.
  §2.3  macd / ema_cross(12/26) / supertrend are pruned as trend directionals
        (anti-momentum at 3-6m or redundant with sma_slope per the IC audit).

These are Forge-owned enumeration-policy tables; the swap sharpens SELECTION
quality (WF), not the CPCV-p25 promotion wall (handoff §0).
"""

from __future__ import annotations

import random

from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.grammar.signal_horizon import (
    _DEFAULT_HORIZON_DAYS,
    horizon_class,
    signal_horizon_days,
)

# --- §2.1: sma_slope + ad_slope are now enumerable trend directionals ---------


def test_sma_slope_is_enumerable_directional() -> None:
    assert not is_threshold_skippable("sma_slope", "directional")


def test_ad_slope_is_enumerable_directional() -> None:
    assert not is_threshold_skippable("ad_slope", "directional")


def test_new_slope_directionals_are_percentile_only() -> None:
    """Distribution-free: no absolute range shipped without a value distribution.

    Mirrors option_momentum (D138): a directional_percentile_range with no
    directional_range still emits a valid [0,1] percentile threshold + the
    use_percentile flag, so no empty-params leak.
    """
    for ind in ("sma_slope", "ad_slope"):
        params = sample_threshold_params(ind, "directional", random.Random(0))
        assert params.get("use_percentile") is True, f"{ind} must emit a percentile threshold"
        assert "threshold" in params, f"{ind} leaked empty params"
        threshold = params["threshold"]
        assert isinstance(threshold, float)
        assert 0.0 <= threshold <= 1.0


def test_new_directionals_have_explicit_horizons() -> None:
    """A real threshold-eligible directional must not rely on the S4 default."""
    for ind in ("sma_slope", "ad_slope"):
        assert signal_horizon_days(ind) != _DEFAULT_HORIZON_DAYS, (
            f"{ind} needs an explicit _SIGNAL_HORIZON_TABLE entry"
        )


def test_sma_slope_horizon_is_long_like_momentum() -> None:
    """SMA-200 slope is a slow trend read → long_lookback, the same DTE bucket
    class as the momentum_252 it is meant to out-rank (clean swap, not a bucket
    move)."""
    assert signal_horizon_days("sma_slope") == 200
    assert horizon_class("sma_slope") == "long_lookback"


def test_ad_slope_horizon_is_medium() -> None:
    assert signal_horizon_days("ad_slope") == 60
    assert horizon_class("ad_slope") == "medium_lookback"


# --- §2.2 / §2.3: pruned trend directionals are no longer enumerable ----------


def test_returns_12m_skip1_pruned_as_directional() -> None:
    """≡ momentum_252 (rank-corr 1.0) — keep exactly one 12-1 momentum."""
    assert is_threshold_skippable("returns_12m_skip1", "directional")


def test_weak_trend_directionals_pruned() -> None:
    """macd / ema_cross(12/26) / supertrend: anti-momentum or redundant."""
    for ind in ("macd", "ema_cross", "supertrend"):
        assert is_threshold_skippable(ind, "directional"), f"{ind} not pruned"


def test_momentum_252_retained() -> None:
    """§2.2 keeps exactly one 12-1 momentum; momentum_252 stays enumerable so
    the learned D106 weight can rank sma_slope against it on live evidence."""
    assert not is_threshold_skippable("momentum_252", "directional")
