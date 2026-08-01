"""Arm-B weights for the Tier-1 generation A/B: regime gates scored by BOOK-USABLE rate.

The incumbent `compute_regime_gate_yield_weights` scores a regime gate by its COMPONENT rate,
learned from Crucible's gated-runs export. This module answers the competing hypothesis: that
the draw should follow BOOK-USABLE production instead -- cpcv >= the weakest component ever
used in a promoted book -- because the two diverge. Which is right is an empirical question,
and the Tier-1 A/B is what settles it.

TWO DESIGN CHOICES, BOTH FORCED BY MEASUREMENT RATHER THAN TASTE.

1. THE HONEST ARM ONLY. The incumbent map learns from every gated run, i.e. from a population
   the ranker selected. Selection is a function of predicted quality, so a rate measured on it
   is collider-conditioned (D337/D338) and a cell's apparent lift can invert. `prefilter_sample`
   is the one population unselected by both prefilter and ranker, so it is the only unbiased
   estimate of what a cell PRODUCES. Stage one only -- the refit lane is admitted-only, a
   second collider, and pooling the two mixes bases.

2. SHRINK TO THE REGIME MARGINAL, NOT THE CELL. A 2026-07-31 dispersion test over the honest
   arm found the (hyp, dir, bucket, regime) CELL rates are NOT distinguishable from a single
   common rate (X2=38.9, df=37, z=+0.29) -- the top cell was 1-of-41 with a 95% CI of
   [0.43%, 12.60%]. Weighting on those point estimates would chase noise. The REGIME GATE
   marginal does carry signal (z=+2.16): rv_rank 12/816 = 1.47% against market_state 1/631 =
   0.16% and vix_term_slope 0/548 = 0.00%. So the estimator is a regime-marginal rate with a
   per-cell correction that only survives where the cell has the evidence to earn it.

Cold start / thin data -> {} and the caller keeps the incumbent map, so the arm is inert
rather than wrong (hard rule #6).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

# The weakest component ever used in a promoted book, at ADMISSION time. Crucible's later
# 0.9115 refit was retracted; this is the figure their 2026-07-26 correction restored.
#
# DO NOT REFRESH THIS FROM A POST-2026-08-02 PROMOTED POPULATION WHILE THE GENERATION A/B IS
# RUNNING (prereg `4e369b779ca9`). It is not a diagnostic here — it *defines* arm B, whose
# regime weights are scored on the book-usable rate. Crucible's search lane switched its
# traded unit on 08-02 (tail overlay OFF, enforcing the 07-09 §20 decision it had drifted
# past), which reads ~0.05-0.11 higher on the Sharpe family. That lifts book cards across
# §8.7, admits more components, and can drag this floor DOWN for UNIT reasons rather than
# supply ones — loosening arm B's definition mid-flight. A pinned literal is what keeps the
# experiment honest across that boundary; if the floor is ever re-derived, carry the
# tail-ON-era and tail-OFF-era figures as separate constants rather than blending them.
BOOK_FLOOR: float = 0.9439

# Beta prior on the regime marginal. Deliberately weak: the marginal has ~150-800 configs per
# gate, so a strong prior would erase the very spread the A/B exists to test.
_PRIOR_ALPHA: float = 1.0
_PRIOR_BETA: float = 99.0

# A cell must clear this before its own rate is allowed to move it off the regime marginal.
# Below it the cell contributes its data to the marginal and nothing else -- the dispersion
# test says per-cell estimates at n < 100 are indistinguishable from the pooled rate.
_MIN_CELL_N: int = 100

# Floor on the emitted weight. A gate measuring 0 book-usable must be de-emphasised, never
# ZEROED: zeroing removes it from the draw entirely, which is a grammar decision (a prune)
# and belongs in an operator-gated version bump, not in a weight map that reloads every batch.
_MIN_WEIGHT: float = 0.05


def _cell_of(config_json: str) -> tuple[str, str, str, str] | None:
    try:
        cfg = json.loads(config_json)
    except (TypeError, ValueError):
        return None
    hypothesis = cfg.get("hypothesis")
    # D119 guard, inherited: relative_value's pairs runner never evaluates the regime gate, so
    # its label is a dead tag and weighting it would repeat the D119 sampling artifact.
    if not isinstance(hypothesis, str) or hypothesis == "relative_value":
        return None
    directional = ""
    gates: list[str] = []
    signals = cfg.get("signals")
    if not isinstance(signals, list):
        return None
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        inds = sig.get("indicators")
        if not isinstance(inds, list) or not inds:
            continue
        if sig.get("role") == "directional":
            directional = str(inds[0])
        elif sig.get("role") == "regime_filter":
            gates.extend(str(i) for i in inds)
    if not directional or not gates:
        return None
    return (hypothesis, directional, str(cfg.get("dte_bucket", "")), "+".join(sorted(gates)))


def compute_book_usable_regime_weights(
    db: duckdb.DuckDBPyConnection,
    *,
    book_floor: float = BOOK_FLOOR,
    min_cell_n: int = _MIN_CELL_N,
) -> dict[tuple[str, str, str, str], float]:
    """``(hypothesis, directional, dte_bucket, regime_gate)`` -> relative draw weight.

    The weight is the cell's book-usable rate where the cell has earned its own estimate, and
    the regime-gate marginal everywhere else, normalised so the mean weight is 1.0 (the scale
    the sampler's compositional weighting expects).
    """
    rows = db.execute(
        """
        SELECT s.config_json,
               TRY_CAST(
                   json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
               )
        FROM submissions s
        JOIN verdicts v ON v.config_hash = s.config_hash
        WHERE s.selection_mode = 'prefilter_sample'
          AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
        """
    ).fetchall()

    cell_n: dict[tuple[str, str, str, str], int] = {}
    cell_k: dict[tuple[str, str, str, str], int] = {}
    regime_n: dict[str, int] = {}
    regime_k: dict[str, int] = {}
    for config_json, cpcv in rows:
        if cpcv is None:
            continue
        cell = _cell_of(config_json)
        if cell is None:
            continue
        hit = 1 if float(cpcv) >= book_floor else 0
        cell_n[cell] = cell_n.get(cell, 0) + 1
        cell_k[cell] = cell_k.get(cell, 0) + hit
        regime = cell[3]
        regime_n[regime] = regime_n.get(regime, 0) + 1
        regime_k[regime] = regime_k.get(regime, 0) + hit

    if not cell_n:
        return {}

    marginal = {
        r: (regime_k[r] + _PRIOR_ALPHA) / (regime_n[r] + _PRIOR_ALPHA + _PRIOR_BETA)
        for r in regime_n
    }
    raw: dict[tuple[str, str, str, str], float] = {}
    for cell, n in cell_n.items():
        rate = marginal[cell[3]]
        if n >= min_cell_n:
            # Earned its own estimate; still Beta-smoothed so a 0/120 cell lands low
            # rather than at zero.
            rate = (cell_k[cell] + _PRIOR_ALPHA) / (n + _PRIOR_ALPHA + _PRIOR_BETA)
        raw[cell] = rate

    mean = sum(raw.values()) / len(raw)
    if mean <= 0:
        return {}
    return {cell: max(_MIN_WEIGHT, rate / mean) for cell, rate in raw.items()}


__all__ = ["BOOK_FLOOR", "compute_book_usable_regime_weights"]
