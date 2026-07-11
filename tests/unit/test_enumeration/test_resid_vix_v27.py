"""v27 resid_vix activation — Crucible generation request (2026-07-11).

Enforces the enumeration-policy changes that ride grammar_version v27
(`docs/tasks/grammar-change.md` classification #2/#3; the §3.5 `rules:` text is
untouched; loosening operator-approved via OPEN_PROPOSALS `0a4d8da8`). Refs:
`IMPLEMENTATION_DECISIONS.md` D264, the handoff
`../Crucible/docs/handoffs/FORGE_resid_vix_generation_request_2026-07-11.md` —
their probe on this signal pair produced the first walk-forward-gate pass in
program history (WF median 2.0611 vs gate 2.0, in-book at 20%).

  * residual_momentum becomes an enumerable trend_continuation DIRECTIONAL:
    percentile-only (the sma_slope/option_momentum precedent — brand-new id
    with no Forge-side value distribution), (0.60, 0.90) op ">", with the
    Crucible computation knobs `window` [63, 252] / `skip` [0, 21] riding the
    SignalSpec params (their sweep bounds; probe used 126/21).
  * vix_term_slope becomes an accepted R2 trend regime gate (REVERSES the
    v17/D131 deliberate exclusion — its "validated for vol returns, not trend
    conditioning" rationale is superseded by Crucible's direct campaign-grade
    measurement of exactly this use), regime_range (0.0, 2.0) op ">" so the
    uniform draw natively covers their tighter-gate failure-mode ask
    (slope > 0.5..1.0).
  * Horizon: residual_momentum 63 td → medium_lookback; the D102 k∈{2,3,4}
    derivation then snaps every target to swing_mid — the validated probe
    chassis. (swing_mid-vs-swing_long is not expressible for one id under
    horizon-matched DTE; the swing_long arm was consciously left out, see the
    proposal.) vix_term_slope 1 td, gate-only (coverage-invariant honesty).
"""

from __future__ import annotations

import random

from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.sampler import _directional_signal_params
from forge.grammar.custom_predicates import _R2_TREND_CONTINUATION_REGIME_INDICATORS
from forge.grammar.signal_horizon import (
    _DEFAULT_HORIZON_DAYS,
    buckets_for_horizon_class,
    horizon_class,
    nearest_bucket,
    signal_horizon_days,
)

# --- residual_momentum: percentile-only trend directional ----------------------


def test_residual_momentum_is_enumerable_directional() -> None:
    assert not is_threshold_skippable("residual_momentum", "directional")


def test_residual_momentum_is_not_a_regime_gate() -> None:
    """Directional-only: the regime side ships no range (the handoff pairs it
    with a gate, it never IS one)."""
    assert is_threshold_skippable("residual_momentum", "regime_filter")


def test_residual_momentum_percentile_only_emission() -> None:
    """Distribution-free activation (no Forge-side value audit exists): a [0,1]
    percentile threshold + use_percentile, never an absolute value. Range
    (0.60, 0.90) op ">" spans the handoff's sweep bounds around the probe's
    winning >0.8 entry; percentile_window stays the shared 252 default (the
    probe's exact ranking window)."""
    for seed in range(50):
        params = sample_threshold_params("residual_momentum", "directional", random.Random(seed))
        assert params.get("use_percentile") is True
        assert params.get("op") == ">"
        assert params.get("percentile_window") == 252
        threshold = params["threshold"]
        assert isinstance(threshold, float)
        assert 0.60 <= threshold <= 0.90


def test_residual_momentum_window_skip_ride_directional_params() -> None:
    """The Crucible computation knobs ride the same params dict as the
    percentile threshold (the option_momentum/pairs precedent). Sweep bounds
    are the handoff's: window 63-252, skip 0-21 (probe: 126/21)."""
    for seed in range(50):
        params = _directional_signal_params("residual_momentum", random.Random(seed))
        window = params.get("window")
        skip = params.get("skip")
        assert isinstance(window, int)
        assert 63 <= window <= 252
        assert isinstance(skip, int)
        assert 0 <= skip <= 21
        # the threshold keys must still be present alongside the knobs
        assert params.get("use_percentile") is True
        assert "threshold" in params


def test_residual_momentum_params_deterministic() -> None:
    """Hard rule #6: same seed → same params, draw for draw."""
    a = _directional_signal_params("residual_momentum", random.Random(1234))
    b = _directional_signal_params("residual_momentum", random.Random(1234))
    assert a == b


def test_residual_momentum_horizon_medium_snaps_to_swing_mid() -> None:
    """63 td → medium_lookback → S4 permits swing_short/swing_mid, and the D102
    horizon-matched derivation (k in {2,3,4} x 63 = 126/189/252) snaps every
    target to swing_mid — the validated probe chassis, always."""
    assert signal_horizon_days("residual_momentum") == 63
    assert signal_horizon_days("residual_momentum") != _DEFAULT_HORIZON_DAYS
    assert horizon_class("residual_momentum") == "medium_lookback"
    allowed = buckets_for_horizon_class("medium_lookback")
    assert allowed == ("swing_short", "swing_mid")
    for k in (2, 3, 4):
        assert nearest_bucket(allowed, float(k * 63)) == "swing_mid"


# --- vix_term_slope: R2 calm-market trend gate ---------------------------------


def test_vix_term_slope_is_enumerable_regime_gate() -> None:
    assert not is_threshold_skippable("vix_term_slope", "regime_filter")


def test_vix_term_slope_is_not_a_directional() -> None:
    """Gate-only: the vol term structure conditions trend entries, it never
    anchors one."""
    assert is_threshold_skippable("vix_term_slope", "directional")


def test_vix_term_slope_regime_params_absolute_contango() -> None:
    """Native-unit threshold in [0.0, 2.0], op ">" (fire in contango = calm).
    The uniform draw covers both the probe's >0 gate and their failure-mode ask
    to explore tighter gates (>0.5..1.0 — the stale-contango bear-onset
    quarters). Never percentile: the slope's zero crossing is the economically
    meaningful cut."""
    for seed in range(50):
        params = sample_threshold_params("vix_term_slope", "regime_filter", random.Random(seed))
        assert params.get("op") == ">"
        assert "use_percentile" not in params
        threshold = params["threshold"]
        assert isinstance(threshold, float)
        assert 0.0 <= threshold <= 2.0


def test_vix_term_slope_horizon_explicit() -> None:
    """Gate-only entry (S4 never consults it) — present for the horizon-coverage
    invariant, like market_state/pre_earnings_setup. Spot term-structure read →
    1 td, mirroring vix_level."""
    assert signal_horizon_days("vix_term_slope") == 1


def test_vix_term_slope_in_r2_pool() -> None:
    """The R2 python-side pool accepts vix_term_slope (v27/D264) — reversing the
    v17/D131 deliberate exclusion on Crucible's direct evidence."""
    assert "vix_term_slope" in _R2_TREND_CONTINUATION_REGIME_INDICATORS
