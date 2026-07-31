"""Can we MEASURE grammar exhaustion? A power assessment of candidate tail statistics.

The freeze criterion's condition (C) says the grammar is exhausted when the honest arm's tail
stops moving. That is only a criterion if the tail statistic can actually resolve a change --
otherwise it can be neither satisfied nor refuted, and "not yet exhausted" becomes permanent by
construction rather than by evidence.

This script asks, for each candidate tail statistic: how many honest-arm configs are needed to
detect a meaningful change with 80% power at alpha=0.05, and how many DAYS that is at the
observed accrual rate.

Candidates, in increasing base rate (and therefore increasing power):

  1. P(cpcv >= 1.5)      -- exceedance of the promotion gate. What we most want to know, and
                            the rarest: ~1 in 1,900 (stage two).
  2. P(cpcv >= 0.9439)   -- exceedance of the book-usability floor, the weakest component ever
                            used in a promoted book. ~25x more common.
  3. p95 / p99 quantiles -- continuous tail statistics. A quantile uses every observation near
                            it rather than counting rare crossings, so its standard error
                            shrinks far faster than an exceedance rate's.

STAGE DISCIPLINE, and it is why this script exists in this form: stage one (a config's original
measurement) and stage two (`fullhist_refit`, which only ADMITTED configs receive) are different
populations, and pooling them mixes bases. Crucible's honest-arm baseline was stage two; a
2026-07-31 Forge read pooled the two and reported 2 gate-clearers where each stage has 1.
Everything below is computed per stage and never pooled.

Usage: exhaustion_power_assessment.py SNAPSHOT.db
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

from forge.persistence.db import db_connection

BOOK_FLOOR = 0.9439
PROMOTION_GATE = 1.5
_Z_ALPHA = 1.959963985  # two-sided 0.05
_Z_BETA = 0.8416212336  # 80% power


def _n_for_rate_change(p0: float, ratio: float) -> float:
    """Configs PER ARM to detect p0 -> p0*ratio at 80% power, two-proportion z."""
    p1 = min(p0 * ratio, 1.0)
    if p1 <= p0:
        return float("inf")
    num = (_Z_ALPHA + _Z_BETA) ** 2 * (p0 * (1 - p0) + p1 * (1 - p1))
    return num / (p1 - p0) ** 2


def _quantile_se(values: list[float], q: float) -> float:
    """SE of a sample quantile, from the empirical density at that quantile.

    SE = sqrt(q(1-q)/n) / f(x_q); f estimated by the slope of the empirical CDF across a
    window straddling the quantile, which avoids importing a KDE for a one-off read."""
    n = len(values)
    ordered = sorted(values)
    idx = int(q * n)
    lo = max(0, idx - n // 40)
    hi = min(n - 1, idx + n // 40)
    span = ordered[hi] - ordered[lo]
    if span <= 0:
        return float("inf")
    density = (hi - lo) / n / span
    return math.sqrt(q * (1 - q) / n) / density


def _n_for_quantile_shift(values: list[float], q: float, shift: float) -> float:
    """Configs PER ARM to detect a `shift` in the q-quantile at 80% power."""
    se = _quantile_se(values, q)
    if not math.isfinite(se) or shift <= 0:
        return float("inf")
    # Two independent arms -> SE of the difference is se*sqrt(2) at the observed n.
    n = len(values)
    se_unit = se * math.sqrt(n)  # SE at n=1, so SE(n) = se_unit/sqrt(n)
    return 2 * ((_Z_ALPHA + _Z_BETA) * se_unit / shift) ** 2


def main() -> int:
    snap = Path(sys.argv[1])
    with db_connection(snap) as conn:
        rows = conn.execute(
            """
            SELECT v.measurement_basis,
                   TRY_CAST(
                       json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
                   ),
                   s.submitted_at
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.selection_mode = 'prefilter_sample'
            """
        ).fetchall()

    stages: dict[str, list[float]] = {"stage one": [], "stage two": []}
    span: dict[str, list] = {"stage one": [], "stage two": []}
    for basis, cpcv, submitted in rows:
        if cpcv is None:
            continue
        key = "stage two" if basis == "fullhist_refit" else "stage one"
        stages[key].append(float(cpcv))
        span[key].append(submitted)

    for stage, values in stages.items():
        n = len(values)
        if n < 100:
            continue
        days = max((max(span[stage]) - min(span[stage])).total_seconds() / 86400.0, 0.5)
        per_day = n / days
        ge_gate = sum(1 for v in values if v >= PROMOTION_GATE)
        ge_floor = sum(1 for v in values if v >= BOOK_FLOOR)
        p_gate = ge_gate / n
        p_floor = ge_floor / n

        print(f"\n{'=' * 78}\n{stage.upper()}  n={n}  accrual={per_day:.0f}/day over {days:.1f}d")
        print(f"  median {statistics.median(values):.4f}   max {max(values):.4f}")
        print(f"  >= {PROMOTION_GATE} gate : {ge_gate} ({100 * p_gate:.4f}%)")
        print(f"  >= {BOOK_FLOOR} floor: {ge_floor} ({100 * p_floor:.4f}%)")
        print(f"\n  {'statistic':<34}{'effect to detect':<22}{'n/arm':>12}{'days/arm':>11}")
        print(f"  {'-' * 77}")

        checks: list[tuple[str, str, float]] = []
        if p_gate > 0:
            checks.append(
                (f"P(cpcv >= {PROMOTION_GATE})", "doubling", _n_for_rate_change(p_gate, 2.0))
            )
            checks.append((f"P(cpcv >= {PROMOTION_GATE})", "10x", _n_for_rate_change(p_gate, 10.0)))
        if p_floor > 0:
            checks.append(
                (f"P(cpcv >= {BOOK_FLOOR})", "doubling", _n_for_rate_change(p_floor, 2.0))
            )
            checks.append((f"P(cpcv >= {BOOK_FLOOR})", "+50%", _n_for_rate_change(p_floor, 1.5)))
        for q in (0.95, 0.99):
            for shift in (0.05, 0.10):
                checks.append(
                    (
                        f"p{int(q * 100)} quantile",
                        f"+{shift:.2f} cpcv",
                        _n_for_quantile_shift(values, q, shift),
                    )
                )

        for name, effect, n_needed in checks:
            days_needed = n_needed / per_day if per_day else float("inf")
            n_str = f"{n_needed:,.0f}" if math.isfinite(n_needed) else "inf"
            d_str = f"{days_needed:,.0f}" if math.isfinite(days_needed) else "inf"
            print(f"  {name:<34}{effect:<22}{n_str:>12}{d_str:>11}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
