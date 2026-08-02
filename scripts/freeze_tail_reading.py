"""Freeze condition (C), tail half: has the honest-arm quality ceiling stopped moving?

WHY THIS SCRIPT EXISTS. (C)'s tail half was re-specified (2026-07-31) onto "the max and the
count clearing the 1.5 promotion gate". That carries ONE event in 12,084 honest-arm configs,
and D341 priced detecting a doubling of its rate at ~183 days per arm - it cannot be a decision
metric. The ORIGINAL (C) (2026-07-22) used p90 and was voided for its BASIS (stage two is the
refit trigger, a collider - D337/D338), not its statistic.

TWO DEFECTS FOUND 2026-08-02 by a four-agent review, both fixed here:

  1. COMPOSITION DRIFT. The pooled statistic is not a quality reading - it is a quality reading
     CONFOUNDED WITH MIX. Measured: swing_long's share of the honest arm moved 48.4% -> 61.9%
     across ten windows while swing_long's pooled p90 (0.6447) runs 0.149 above swing_mid's
     (0.4955). Mix shift alone therefore moves pooled p90 by ~0.020 - about 63% of the 0.0319
     decision threshold - with no quality change whatever. The traced mechanism is our own
     chain-inception filter (D351/D352) adding and removing swing_long-only names at the
     window-9 boundary. Worse, the previous `b` was FIT ON THAT DRIFTING SERIES, so part of
     what was called irreducible noise was composition. The bar was contaminated in both
     directions at once.
     FIX: post-stratification. Every observation is weighted p_c / q_c, where p_c is the cell's
     share of the full reference sample and q_c its share of this window. Each window is then
     read as if it had the reference mix. Cells are (hypothesis, dte_bucket) - the granularity
     D341 measured as signal (z=+2.02) rather than noise (per-cell z=+0.29).

  2. THE STATISTIC WAS NOT THE BEST AVAILABLE. p90 is one order statistic; the tail-conditional
     mean (mean of everything at or above the window's own p90) uses the whole top decile and
     measures ~40% tighter at identical data cost (MDE 0.039 vs 0.069 at a 2-week horizon).
     p95/p99 were rejected on evidence, not taste: their apparently tiny drift floors are
     artifacts of thin tail density (the sampling term inflates 0.64 -> 1.05 as observations
     per window fall to ~60 and ~12), and p90 is the only quantile where BOTH variance
     components resolve. Median and mean carry drift floors of 43% and 52% OF THEIR OWN LEVEL.

WHAT MAKES "STOPPED MOVING" FALSIFIABLE. Nothing, unless you know the noise, so it is measured
rather than assumed:

    sd^2(window stat)  =  a^2 / n   +   b^2
                          ^sampling     ^irreducible drift

`a` shrinks as windows grow; `b` does not, and `b` is the real floor. Reported for the
STANDARDIZED series, because that is the one the decision uses.

WHAT THIS STILL CANNOT SEE, stated because the criterion must not overclaim: a tail-only
improvement. p90 sits at rank ~120-from-top in a 1,200 window; promotion-grade events sit at
rank ~0.4-5. A grammar change that lifts only the top ~1% cannot move either statistic - that
is arithmetic. `P(cpcv >= 1.0)` is printed as a CORROBORATING series for exactly that blind
spot, and is never the trigger. `P(cpcv|submitted)` is printed too: it varies 72% (trend) to
20% (volatility_event) via Crucible's per-bucket min-trade floors, so a shift in it moves the
measured population for reasons unrelated to grammar quality.

BASIS, non-negotiable: honest arm (`selection_mode='prefilter_sample'` - unselected by BOTH the
prefilter and the ranker), stage one only, never pooled with the refit lane.

Usage: freeze_tail_reading.py SNAPSHOT.db [--window 1200]
"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from pathlib import Path

from forge.persistence.db import db_connection

_QUERY = """
    SELECT json_extract_string(s.config_json,'$.hypothesis'),
           json_extract_string(s.config_json,'$.dte_bucket'),
           TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE)
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    WHERE s.selection_mode = 'prefilter_sample'
      AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
    ORDER BY s.submitted_at
"""

_CENSOR_QUERY = """
    SELECT json_extract_string(s.config_json,'$.hypothesis'),
           COUNT(*),
           COUNT(TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE))
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    WHERE s.selection_mode = 'prefilter_sample'
      AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
    GROUP BY 1 ORDER BY 2 DESC
"""

Obs = tuple[str, float]  # (cell, cpcv)


def _wq(obs: list[Obs], w: dict[str, float], p: float) -> float:
    """Weighted quantile: the value where cumulative weight crosses p."""
    pairs = sorted(((v, w.get(c, 0.0)) for c, v in obs), key=lambda t: t[0])
    total = sum(x for _, x in pairs)
    if total <= 0:
        return float("nan")
    run = 0.0
    for v, x in pairs:
        run += x
        if run >= p * total:
            return v
    return pairs[-1][0]


def _tcm(obs: list[Obs], w: dict[str, float], p: float = 0.90) -> float:
    """Weighted tail-conditional mean: mean of everything at/above the weighted p-quantile."""
    thr = _wq(obs, w, p)
    num = sum(w.get(c, 0.0) * v for c, v in obs if v >= thr)
    den = sum(w.get(c, 0.0) for c, v in obs if v >= thr)
    return num / den if den > 0 else float("nan")


def _weights(window: list[Obs], ref: dict[str, float]) -> tuple[dict[str, float], float, float]:
    """Post-stratification weights p_c/q_c, plus reference-mass coverage and the max weight.

    A cell absent from this window cannot be reweighted into it -- coverage reports how much
    reference mass is actually represented, so a thin window declares itself rather than
    silently returning a standardized-looking number built on half the strata.
    """
    n = len(window)
    seen = Counter(c for c, _ in window)
    w = {c: (ref[c] / (k / n)) for c, k in seen.items() if c in ref and k}
    coverage = sum(ref[c] for c in seen if c in ref)
    return w, coverage, (max(w.values()) if w else float("nan"))


def _decompose(series_by_width: dict[int, list[float]]) -> tuple[float, float, float]:
    """Fit sd^2 = a^2/n + b^2 by OLS across MANY widths. Returns (a, b, b_upper).

    A two-point fit is not good enough here and shipping one would have been a mistake: with
    only 3 and 10 windows the sd estimates are themselves noisy, and when sd happens to shrink
    faster than 1/sqrt(n) the intercept goes negative and `b` clamps to exactly 0. A bar of
    2b = 0 is not "no drift", it is "cannot resolve drift" wearing a decisive-looking number.

    So: regress across five widths, and return a JACKKNIFE UPPER BOUND alongside the point
    estimate. The bar is set from `b_upper`, deliberately. Direction matters -- too SMALL a bar
    calls noise "still moving" and merely delays a freeze, while too LARGE a bar calls real
    movement "flat" and freezes a grammar that is still improving. Only one of those is
    recoverable, so the conservative choice is the wider floor.
    """
    pts = [
        (n, statistics.pstdev(s) ** 2) for n, s in sorted(series_by_width.items()) if len(s) >= 3
    ]
    if len(pts) < 3:
        return float("nan"), float("nan"), float("nan")

    def _fit(sample: list[tuple[int, float]]) -> tuple[float, float]:
        xs = [1.0 / n for n, _ in sample]
        ys = [v for _, v in sample]
        k = len(xs)
        mx, my = sum(xs) / k, sum(ys) / k
        den = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den if den else 0.0
        return slope, my - slope * mx  # (a^2, b^2)

    a2, b2 = _fit(pts)
    # Leave-one-width-out: the spread of the intercept is the honest uncertainty on b.
    b2s = [_fit([p for j, p in enumerate(pts) if j != i])[1] for i in range(len(pts))]
    b_up = max(max(b2s, default=b2), b2)
    return (
        a2**0.5 if a2 > 0 else 0.0,
        max(0.0, b2) ** 0.5,
        max(0.0, b_up) ** 0.5,
    )


def _series(obs: list[Obs], ref: dict[str, float], width: int, std: bool, stat: str) -> list[float]:
    out = []
    for i in range(0, len(obs) - width + 1, width):
        win = obs[i : i + width]
        w = _weights(win, ref)[0] if std else dict.fromkeys({c for c, _ in win}, 1.0)
        out.append(_tcm(win, w) if stat == "tcm" else _wq(win, w, 0.90))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--window", type=int, default=1200)
    args = ap.parse_args()

    with db_connection(Path(args.snapshot)) as conn:
        raw = conn.execute(_QUERY).fetchall()
        censor = conn.execute(_CENSOR_QUERY).fetchall()
    obs: list[Obs] = [(f"{h}/{b}", v) for h, b, v in raw if v is not None]
    n = len(obs)
    ref_counts = Counter(c for c, _ in obs)
    ref = {c: k / n for c, k in ref_counts.items()}
    print(f"honest arm, stage one, with cpcv: n={n}   cells={len(ref)}")

    widths = (300, 400, 600, 800, 1200)
    print(
        f"\n{'series':<28}{'k':>4}{'mean':>10}{'sd@400':>9}{'sd@1200':>10}"
        f"{'b':>9}{'b_up':>9}{'BAR 2b_up':>10}"
    )
    bars: dict[str, float] = {}
    for stat in ("p90", "tcm"):
        for std in (False, True):
            by_w = {w: _series(obs, ref, w, std, stat) for w in widths}
            _a, b, b_up = _decompose(by_w)
            s = by_w[args.window]
            label = f"{stat} {'STANDARDISED' if std else 'raw (pooled)'}"
            bars[label] = 2 * b_up
            print(
                f"{label:<28}{len(s):>4}{statistics.fmean(s):>10.4f}"
                f"{statistics.pstdev(by_w[400]):>9.4f}{statistics.pstdev(s):>10.4f}"
                f"{b:>9.4f}{b_up:>9.4f}{2 * b_up:>9.4f}"
            )

    print(f"\n=== decision series: TCM top-10%, composition-standardised, window={args.window} ===")
    ser = _series(obs, ref, args.window, True, "tcm")
    print("  " + " ".join(f"{v:.4f}" for v in ser))
    cov = [
        _weights(obs[i : i + args.window], ref)[1]
        for i in range(0, len(obs) - args.window + 1, args.window)
    ]
    mx = [
        _weights(obs[i : i + args.window], ref)[2]
        for i in range(0, len(obs) - args.window + 1, args.window)
    ]
    print(
        f"  reference-mass coverage per window: {min(cov):.3f}-{max(cov):.3f}"
        f"   max weight: {max(mx):.2f}"
    )
    if len(ser) >= 2:
        drift = ser[-1] - max(ser[:-1])
        bar = bars["tcm STANDARDISED"]
        print(
            f"  newest vs best-prior: {drift:+.4f}  bar 2b={bar:.4f}  -> "
            f"{'MOVING' if drift > bar else 'flat within the drift floor'}"
        )

    print("\n=== companions (never the trigger) ===")
    p1 = [
        sum(1 for _, v in obs[i : i + args.window] if v >= 1.0)
        for i in range(0, len(obs) - args.window + 1, args.window)
    ]
    print(
        f"  P(cpcv>=1.0) counts/window: {p1}  (blind spot: p90/TCM cannot see a top-1%-only lift)"
    )
    print("  P(cpcv|submitted) by hypothesis -- a shift here moves the measured population:")
    for h, sub, meas in censor[:6]:
        print(f"    {h!s:<22} {meas:>6}/{sub:<6} = {100 * meas / sub:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
