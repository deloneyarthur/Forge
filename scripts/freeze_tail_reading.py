"""Freeze condition (C), tail half: is the honest-arm p90 still moving?

WHY THIS SCRIPT EXISTS. (C)'s tail half was re-specified (2026-07-31) onto "the max and the
count clearing the 1.5 promotion gate". That statistic carries ONE event in 11,932 honest-arm
configs, and D341 priced detecting a doubling of its rate at ~183 days per arm - so it cannot
be a decision metric, and a 1 -> 1 reading across a 1.6x sample says nothing. The ORIGINAL (C)
(2026-07-22) used p90, and was voided for its BASIS (stage two is the refit trigger, a
collider - D337/D338), not for its statistic. This restores the original statistic on the
corrected basis: p90 on the stage-one honest arm.

WHAT MAKES "STOPPED MOVING" FALSIFIABLE. Nothing, unless you know the noise. So this measures
it rather than assuming a bar, and decomposes the window-to-window variance into

    sd^2(window p90)  =  a^2 / n   +   b^2
                         ^sampling    ^irreducible between-window drift

The `a` term shrinks as windows grow; `b` does not, and `b` is the real floor - the quantity
Crucible's "version-over-version deltas below ~0.15-0.20 are beyond resolution at ANY n"
warning is about. Measuring it on OUR statistic rather than importing their number for a
different one is the whole point: a bar set from someone else's quantity is an assumption
wearing a measurement's clothes.

BASIS, non-negotiable: honest arm (`selection_mode='prefilter_sample'` - the population
unselected by BOTH the prefilter and the ranker), stage one only, never pooled with the refit
lane. Pooling is what made the reading this replaces wrong.

Usage: freeze_tail_reading.py SNAPSHOT.db [--window 1200]
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from forge.persistence.db import db_connection

_QUERY = """
    SELECT s.submitted_at,
           TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE)
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    WHERE s.selection_mode = 'prefilter_sample'
      AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
    ORDER BY s.submitted_at
"""


def _p90(xs: list[float]) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(0.90 * len(s)))]


def _window_p90s(vals: list[float], width: int) -> list[float]:
    return [_p90(vals[i : i + width]) for i in range(0, len(vals) - width + 1, width)]


def _decompose(vals: list[float], widths: tuple[int, ...]) -> tuple[float, float]:
    """Solve sd^2 = a^2/n + b^2 from the smallest and largest usable window widths."""
    pts = []
    for w in widths:
        ps = _window_p90s(vals, w)
        if len(ps) >= 3:
            pts.append((w, statistics.pstdev(ps)))
    if len(pts) < 2:
        return float("nan"), float("nan")
    (n1, s1), (n2, s2) = pts[0], pts[-1]
    denom = (1.0 / n1) - (1.0 / n2)
    if denom <= 0:
        return float("nan"), float("nan")
    a2 = (s1**2 - s2**2) / denom
    b2 = max(0.0, s1**2 - a2 / n1)
    return math_sqrt(a2), math_sqrt(b2)


def math_sqrt(x: float) -> float:
    return x**0.5 if x > 0 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--window", type=int, default=1200)
    args = ap.parse_args()

    with db_connection(Path(args.snapshot)) as conn:
        rows = [(t, v) for t, v in conn.execute(_QUERY).fetchall() if v is not None]
    vals = [v for _, v in rows]
    print(
        f"honest arm, stage one, with cpcv: n={len(vals)}  "
        f"span {rows[0][0].date()} -> {rows[-1][0].date()}"
    )

    widths = (400, 800, 1200)
    print(f"\n{'window':>8}{'k':>5}{'mean p90':>11}{'sd':>9}{'2sd':>9}")
    for w in widths:
        ps = _window_p90s(vals, w)
        if len(ps) < 3:
            continue
        sd = statistics.pstdev(ps)
        print(f"{w:>8}{len(ps):>5}{statistics.fmean(ps):>11.4f}{sd:>9.4f}{2 * sd:>9.4f}")

    a, b = _decompose(vals, widths)
    print(f"\nvariance decomposition:  sampling a={a:.4f}   IRREDUCIBLE DRIFT b={b:.4f}")
    print("  a shrinks as 1/sqrt(n); b does NOT -- b is the real floor.")
    print(f"  => a p90 move is attributable only if it exceeds ~2b = {2 * b:.4f}")

    ps = _window_p90s(vals, args.window)
    if len(ps) >= 2:
        print(f"\ncurrent reading at window={args.window}: {' '.join(f'{p:.3f}' for p in ps)}")
        drift = ps[-1] - max(ps[:-1])
        verdict = "MOVING" if drift > 2 * b else "flat within the drift floor"
        print(f"  newest vs best-prior: {drift:+.4f}  -> {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
