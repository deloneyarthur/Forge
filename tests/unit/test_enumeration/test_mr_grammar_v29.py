"""v29 MR grammar — market_realized_vol: the MARKET-level absolute-RV gate.

The fast-follow to v28 (D265): Crucible's convention reply resolved that their
ledger's rv21 is SPY MARKET-level vol, and their preferred protective gate is the
reference underlying's realized vol — which needed a new market-wide registry id.
`CRUCIBLE_market_realized_vol_registered_2026-07-12` is the D258-pattern confirm
this wiring is keyed against: id `market_realized_vol`, family **`macro`**
(deliberate — C1 lets the market gate STACK with the vol-family `rv_rank` and the
idio-family `ivol`, preserving the champion MR leg's existing protections),
version 1, lookback 0 (internal reference warmup, the market_sma_cross pattern),
params reference="SPY"/window=21 defaults, `market_wide_by_design=true`,
semantics byte-matching their rv21 tag (population stdev ddof=0, c2c, sqrt(252))
so the 0.15-0.30 sweep bounds translate 1:1. Refs: D266, OPEN_PROPOSALS (v29).

Emission shapes this admits (their "pair it with EITHER existing gate"):
  - market_realized_vol PRIMARY (R1 seventh gate) + ivol veto
  - rv_rank / vol_regime / realized_vol PRIMARY + market_realized_vol VETO
    (the two-member MR veto pool; per-id C1 family guard — the D263
    generalization seam Q46 anticipated, minimally widened)
Three-gate stacks (rv_rank + market_rv + ivol) remain out of scope (Q46).

⚠️ ABSOLUTE threshold by design — never `use_percentile` (the percentile IS the
diagnosed defect); market-wide → also a coherent gate on MR's rank arm.
"""

from __future__ import annotations

import random

from forge.enumeration.indicator_thresholds import (
    _INDICATOR_THRESHOLD_TABLE,
    sample_threshold_params,
)
from forge.enumeration.sampler import _MR_RANGING_GATES
from forge.enumeration.search_space import _build_regime_pool
from forge.grammar.custom_predicates import (
    _MR_REGIME_VETO_INDICATORS,
    _R1_MARKET_REALIZED_VOL_REGIME_INDICATOR,
)
from forge.grammar.signal_horizon import signal_horizon_days

# --- market_realized_vol admitted to R1 + boosted + veto-pool member -----------


def test_market_realized_vol_r1_constant_defined() -> None:
    assert _R1_MARKET_REALIZED_VOL_REGIME_INDICATOR == "market_realized_vol"


def test_market_realized_vol_enumerable_in_mr_regime_pool() -> None:
    """registered ≠ enumerable (D254): the id must be in the MR primary pool."""
    ids = {
        "iv_rank",
        "gamma_flip_distance_pct",
        "hurst",
        "rv_rank",
        "vol_regime",
        "realized_vol",
        "market_realized_vol",
        "rsi_2",
    }
    pool = _build_regime_pool(ids, single_name_only_ids=frozenset())
    assert "market_realized_vol" in pool["mean_reversion"]


def test_market_realized_vol_boosted_in_mr_ranging_gates() -> None:
    """Their PREFERRED family — at least equal supply to the per-name gates."""
    assert "market_realized_vol" in _MR_RANGING_GATES


def test_mr_veto_pool_is_two_member() -> None:
    """The MR veto pool widens to (ivol, market_realized_vol) — 'pair it with
    EITHER existing gate': market_rv as VETO rides on a volatility primary."""
    assert _MR_REGIME_VETO_INDICATORS == ("ivol", "market_realized_vol")


# --- encoding: ABSOLUTE market RV, op '<', their 1:1-translating sweep ---------


def test_market_realized_vol_regime_range_is_the_asked_sweep() -> None:
    spec = _INDICATOR_THRESHOLD_TABLE["market_realized_vol"]
    assert spec.regime_range == (0.15, 0.30)
    assert spec.regime_percentile_range is None
    assert spec.op_regime == "<"
    assert spec.directional_range is None  # gate-only, never a directional
    assert spec.directional_percentile_range is None


def test_market_realized_vol_emits_absolute_threshold_in_sweep() -> None:
    params = sample_threshold_params("market_realized_vol", "regime_filter", random.Random(0))
    assert "use_percentile" not in params
    assert params["op"] == "<"
    assert 0.15 <= float(params["threshold"]) <= 0.30


def test_market_realized_vol_horizon_gate_only() -> None:
    """Horizon 1 — gate-only, S4 never consults (the vix_term_slope/market_state
    coverage-invariant precedent; the indicator's warmup is writer-internal)."""
    assert signal_horizon_days("market_realized_vol") == 1
