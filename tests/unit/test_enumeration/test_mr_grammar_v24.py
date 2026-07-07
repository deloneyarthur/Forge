"""v24 MR grammar — Crucible cross-sectional MR champion-hunt (§2b.1 + R1 note).

The rules-touching slice of the trend/MR grammar upgrade (the trend slice is v23:
`test_trend_grammar_v23*.py`). Because it edits the §3.5 R1 rule (admits a new
accepted MR regime gate) it is a grammar_version bump v23→v24, operator-approved
(the vol_regime loosening is hard-rule-#1 + #4 gated). Refs: `IMPLEMENTATION_DECISIONS.md`
D254, handoff `../Crucible/docs/handoffs/FORGE_signal_quality_champions_2026-07-03.md`.

  §2b.1 gate  vol_regime<2 (exclude the high-vol tercile) beats the rv_rank cost
              gate by +0.244 CPCV-p25 in ALL 6 comps — the single biggest MR
              finding. Admitted to R1 (D107/D150/D167 widening precedent), boosted
              in the sampler; hurst (null-to-negative as an MR gate) stays R1-
              accepted but is dropped from the ranging-gate boost (bias away).
  §2b.1 rankr bb_pct is the xsect MR oversold champion — a sampling-weight
              preference delegated to the learned D106 weight (no structural
              directional-weight knob exists; D236 restraint). zscore_returns is
              #2 by the backtest and is NOT dropped (the single-name §2b "drop"
              was an IC artifact; §2b.1 supersedes it for Forge's xsect MR).

⚠️ vol_regime is a DISCRETE tercile (0/1/2) — gated with a RAW threshold `< 2`,
never `use_percentile` (degenerate on a 3-value series).
"""

from __future__ import annotations

import random

from forge.enumeration.indicator_thresholds import (
    _INDICATOR_THRESHOLD_TABLE,
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.sampler import _MR_RANGING_GATES
from forge.enumeration.search_space import _build_regime_pool
from forge.grammar.custom_predicates import _R1_VOL_REGIME_INDICATOR

# --- vol_regime admitted to R1 + boosted; hurst kept-but-deweighted -----------


def test_vol_regime_r1_constant_defined() -> None:
    assert _R1_VOL_REGIME_INDICATOR == "vol_regime"


def test_vol_regime_enumerable_in_mr_regime_pool() -> None:
    """registered ≠ enumerable: vol_regime must be in the MR regime pool (not just
    R1-accepted) or the sampler never picks it."""
    ids = {
        "iv_rank",
        "gamma_flip_distance_pct",
        "hurst",
        "rv_rank",
        "vol_regime",
        "rsi_2",
    }
    pool = _build_regime_pool(ids, single_name_only_ids=frozenset())
    assert "vol_regime" in pool["mean_reversion"]


def test_vol_regime_boosted_in_mr_ranging_gates() -> None:
    """§2b.1: prefer vol_regime — boosted alongside rv_rank / gamma_flip."""
    assert "vol_regime" in _MR_RANGING_GATES


def test_hurst_dropped_from_mr_ranging_gate_boost() -> None:
    """§2b.1: hurst is null-to-negative as an MR gate (-0.27 vs rv_rank, 0/6) ->
    bias the sampler AWAY. It stays R1-accepted (still in the OR), just no longer
    3x-boosted."""
    assert "hurst" not in _MR_RANGING_GATES


def test_rv_rank_and_gamma_flip_stay_boosted() -> None:
    assert {"rv_rank", "gamma_flip_distance_pct"} <= _MR_RANGING_GATES


# --- vol_regime encoding: RAW discrete tercile, op '<', threshold 2 -----------


def test_vol_regime_regime_range_pinned_to_two() -> None:
    """Pinned to the ~10-day-equivalent sweet spot: threshold 2 excludes the
    high-vol tercile; `< 1` (strict calm) starves the book."""
    spec = _INDICATOR_THRESHOLD_TABLE["vol_regime"]
    assert spec.regime_range == (2.0, 2.0)
    assert spec.regime_percentile_range is None  # RAW, never percentile


def test_vol_regime_emits_raw_exclude_high_tercile() -> None:
    params = sample_threshold_params("vol_regime", "regime_filter", random.Random(0))
    assert params.get("use_percentile") is not True
    assert params["threshold"] == 2.0
    assert params["op"] == "<"  # fire when vol_regime < 2 (exclude high tercile)


# --- zscore_returns kept (§2b.1 supersedes §2b) -------------------------------


def test_zscore_returns_kept_as_mr_directional() -> None:
    """§2b.1 ranks zscore_returns #2 by the xsect backtest (0.442) — do NOT drop
    it (the single-name §2b 'drop' was an IC artifact)."""
    assert not is_threshold_skippable("zscore_returns", "directional")
