"""v23 trend-grammar — exit + event-window upgrades (corrected 2026-07-06 handoff).

Second slice of the v23 enumeration-policy bump (the sma_slope/ad_slope slice
lives in `test_trend_grammar_v23.py`). These ride the SAME grammar_version v23:
they are Python-side enumeration changes (`grammar.yaml` `rules:` untouched), so
they fold into the still-unshipped v23 bump rather than minting a new version.
Refs: `IMPLEMENTATION_DECISIONS.md` D236 (addendum), handoff
`../Crucible/docs/handoffs/FORGE_signal_quality_champions_2026-07-03.md`.

  §2.7  chandelier_exit becomes the DEFAULT discretionary trend exit — the
        refuted incumbent parabolic_sar_exit is dropped from the trend
        required_from_set (chandelier beats it +0.29 CPCV-p25 AND higher WF in
        Crucible's real-backtest exit sweep). The tuned trail rides an
        `atr_multiplier` swept in [2.0, 3.0] (2.0 = tail-priority, 3.0 =
        balanced center; +0.155 CPCV-p25 over the 3.0 default at the tight end).
  §2d   volatility_event's days_to_fomc event-proximity gate tightens toward the
        ~10-day sweet spot: books fired at a median ~31d (regime window to 60d)
        which is too wide; the call-wall edge concentrates ≤~10d pre-FOMC and
        ≤5d loses too many trades.

MR asks (§2b, and §2d's MR rsi_14 bullet) are deliberately HELD pending the
operator's MR experiment — not in this slice.
"""

from __future__ import annotations

import random
import statistics

from forge.enumeration.indicator_thresholds import (
    _INDICATOR_THRESHOLD_TABLE,
    sample_threshold_params,
)
from forge.enumeration.sampler import _exit_params
from forge.grammar.custom_predicates import _S5_HYPOTHESIS_EXITS

# --- §2.7: chandelier default trend exit, parabolic_sar dropped ---------------


def test_parabolic_sar_dropped_from_trend_exit_pool() -> None:
    """Refuted incumbent: chandelier beats parabolic_sar +0.29 CPCV-p25 + WF."""
    pool = _S5_HYPOTHESIS_EXITS["trend_continuation"]["required_from_set"]
    assert "parabolic_sar_exit" not in pool
    assert "chandelier_exit" in pool


def test_trend_exit_pool_is_trailing_atr_and_chandelier() -> None:
    """The 3-way trend exit choice loses parabolic_sar; trailing_atr (not
    refuted) is kept alongside the chandelier winner."""
    assert _S5_HYPOTHESIS_EXITS["trend_continuation"]["required_from_set"] == (
        "trailing_atr",
        "chandelier_exit",
    )


def test_chandelier_exit_emits_atr_multiplier_sweep() -> None:
    """Crucible's chandelier template reads atr_multiplier from the exit params
    (the D169 event_passed / D138 option_momentum precedent); a tighter trail
    (≈2.0) lifts CPCV-p25 over the 3.0 default. Sweep [2.0, 3.0]."""
    rng = random.Random(0)
    seen: set[float] = set()
    for _ in range(200):
        params = _exit_params("chandelier_exit", rng)
        assert "atr_multiplier" in params, "chandelier leaked empty params"
        m = params["atr_multiplier"]
        assert isinstance(m, float)
        assert 2.0 <= m <= 3.0
        seen.add(m)
    assert len(seen) > 1, "atr_multiplier must be swept, not constant"


def test_chandelier_atr_multiplier_deterministic() -> None:
    """Same seed → same param (hard rules #6/#8)."""
    assert _exit_params("chandelier_exit", random.Random(42)) == _exit_params(
        "chandelier_exit", random.Random(42)
    )


def test_parabolic_sar_exit_params_unchanged() -> None:
    """Dropping parabolic_sar from the trend pool does not give it params — it
    is simply no longer sampled (still a KNOWN exit id for other paths)."""
    assert _exit_params("parabolic_sar_exit", random.Random(0)) == {}


# --- §2d: volatility_event days_to_fomc event-window tightened toward ~10d -----


def test_days_to_fomc_event_window_tightened() -> None:
    """Regime (event-proximity) window narrows 60d → 14d; low end stays ≥5d
    (≤5d loses too many trades per the response-curve sweep)."""
    spec = _INDICATOR_THRESHOLD_TABLE["days_to_fomc"]
    assert spec.regime_range is not None
    low, high = spec.regime_range
    assert (low, high) == (7.0, 14.0)
    assert high <= 14.0
    assert low >= 5.0


def test_days_to_fomc_regime_fires_when_event_imminent() -> None:
    """op '<' = fire when days_to_fomc < threshold (event imminent), so the
    window bound is an upper bound on days-to-event."""
    params = sample_threshold_params("days_to_fomc", "regime_filter", random.Random(0))
    assert params["op"] == "<"


def test_days_to_fomc_regime_samples_near_ten_day_sweetspot() -> None:
    """Median sampled window ≈ 10d (was ≈ 33.5d under the (7, 60) range)."""
    rng = random.Random(0)
    vals = [
        float(sample_threshold_params("days_to_fomc", "regime_filter", rng)["threshold"])  # type: ignore[arg-type]
        for _ in range(500)
    ]
    assert all(7.0 <= v <= 14.0 for v in vals)
    assert 9.0 <= statistics.median(vals) <= 12.0
