"""v28 MR grammar — absolute realized-vol regime gate (Crucible mr_absolute_vol ask).

The rules-touching slice: admits `realized_vol` as the SIXTH accepted §3.5 R1
mean_reversion regime gate — an ABSOLUTE annualized-RV threshold (op "<", sweep
0.15-0.30), the systematic-vol complement to the percentile gates. Operator-approved
loosening (hard rules #1 + #4), OPEN_PROPOSALS `2121cafe`, grammar v27→v28. Refs:
`IMPLEMENTATION_DECISIONS.md` D265, handoff
`../Crucible/docs/handoffs/FORGE_mr_absolute_vol_gate_request_2026-07-12.md` (+ their
2026-07-12 convention reply).

  Defect     The champion MR leg's `rv_rank < 62` PERCENTILE gate normalizes in
             regime-WIDE vol spikes (every name volatile → ranks mid-distribution).
             Probe (live writer, per-name, 2026-07-12): 2022-12 shows rv_rank<62
             open 21/21 days on ALL of HAL/CVX/SLB/TGT/BAC while absolute rv ≥ 0.25.
  Semantics  Per-name absolute RV (registry realized_vol v2, lookback 20,
             market_wide_by_design=False). Crucible's reply prefers a MARKET-level
             variant too — that needs a new market-wide registry id (relayed,
             future bump); this family is their "valid second family".
  C1         realized_vol is family `volatility` = same family as rv_rank /
             vol_regime → the absolute gate REPLACES the percentile in the vol
             slot (never both in one config); the D263 `ivol` veto
             (idiosyncratic_vol) still STACKS on top — the asked both-gates shape.

⚠️ ABSOLUTE threshold by design — never `use_percentile` (a percentile IS rv_rank,
the diagnosed defect).
"""

from __future__ import annotations

import random

from forge.enumeration.indicator_thresholds import (
    _INDICATOR_THRESHOLD_TABLE,
    sample_threshold_params,
)
from forge.enumeration.sampler import _MR_RANGING_GATES
from forge.enumeration.search_space import _build_regime_pool
from forge.grammar.custom_predicates import _R1_REALIZED_VOL_REGIME_INDICATOR

# --- realized_vol admitted to R1 + boosted; prior set kept ---------------------


def test_realized_vol_r1_constant_defined() -> None:
    assert _R1_REALIZED_VOL_REGIME_INDICATOR == "realized_vol"


def test_realized_vol_enumerable_in_mr_regime_pool() -> None:
    """registered ≠ enumerable: realized_vol must be in the MR regime pool (not
    just R1-accepted) or the sampler never picks it (the D254 lesson)."""
    ids = {
        "iv_rank",
        "gamma_flip_distance_pct",
        "hurst",
        "rv_rank",
        "vol_regime",
        "realized_vol",
        "rsi_2",
    }
    pool = _build_regime_pool(ids, single_name_only_ids=frozenset())
    assert "realized_vol" in pool["mean_reversion"]


def test_realized_vol_boosted_in_mr_ranging_gates() -> None:
    """Same calm-vol thesis class as rv_rank / vol_regime → same 3x boost, so the
    new family gets real supply for Crucible's fold-column selection."""
    assert "realized_vol" in _MR_RANGING_GATES


def test_prior_ranging_gate_set_kept() -> None:
    """ADD not replace: the D254 boost set survives; hurst stays deliberately
    un-boosted (null-to-negative as an MR gate, D254)."""
    assert {"rv_rank", "gamma_flip_distance_pct", "vol_regime"} <= _MR_RANGING_GATES
    assert "hurst" not in _MR_RANGING_GATES


# --- encoding: ABSOLUTE annualized RV, op '<', the asked 0.15-0.30 sweep -------


def test_realized_vol_regime_range_matches_asked_sweep() -> None:
    """The handoff's sweep bounds, replacing the D031-era generic (0.12, 0.25).
    ABSOLUTE — regime_percentile_range stays None (percentile IS the defect)."""
    spec = _INDICATOR_THRESHOLD_TABLE["realized_vol"]
    assert spec.regime_range == (0.15, 0.30)
    assert spec.regime_percentile_range is None
    assert spec.op_regime == "<"


def test_realized_vol_emits_absolute_threshold_in_sweep() -> None:
    params = sample_threshold_params("realized_vol", "regime_filter", random.Random(0))
    assert "use_percentile" not in params
    assert params["op"] == "<"
    assert 0.15 <= float(params["threshold"]) <= 0.30
