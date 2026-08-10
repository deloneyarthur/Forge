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
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from forge.persistence.db import db_connection

# The 4th component of `enumeration_inputs_hash` is the universe fingerprint (D078). It is the
# GENERATION BASIS tag: it changes when Crucible republishes the tier universe and our sampler's
# cache picks it up. LEFT JOIN, not JOIN -- a row whose batch predates the hash must arrive as
# NULL and be refused by the basis guard, never dropped, because silently dropping untagged rows
# would shorten the series and move the window grid (D387).
_QUERY = """
    SELECT s.config_hash,
           json_extract_string(s.config_json,'$.hypothesis'),
           json_extract_string(s.config_json,'$.dte_bucket'),
           TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE),
           split_part(b.enumeration_inputs_hash, '|', 2)
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    LEFT JOIN batch_summaries b ON b.forge_batch_id = s.forge_batch_id
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

Obs = tuple[str, float, float | None]  # (cell, cpcv, |corr to reference book| or None)

# The redundancy leg's reference book. `frozen_b36f49a4` is the minted series of the SECOND
# promotion (2026-07-20), used because it has FULL coverage of our honest arm (13,480 of 13,480
# joined rows) where the newest book reaches only 2,497.
#
# IT DOES NOT TRACK THE DESIGNATION, AND THAT IS DELIBERATE (2026-08-02, agreed with Crucible).
# The operator's designation flipped to `f52a05c8968bdc7a` on 2026-08-01 -- BEFORE this leg's
# prereg cut (13e4d2cece3f, 2026-08-02T17:26Z) -- so the whole registered series was already
# read against one fixed reference and nothing needs re-basing. It stays pinned because a
# coverage-chosen yardstick that chased the designation would inherit a re-base on every future
# flip, and there will be more. Measured on the 2,497 configs carrying both:
#
#   per-config agreement   pearson +0.9582   spearman +0.9531   <- the choice costs ~no ordering
#   leg-2 level            0.4228 (this ref) vs 0.3770 (designated)  = -0.0458
#
# The level gap is 2.6x the leg's own decision bar of 0.0173, and it points DOWN -- so silently
# switching would have printed a large unearned IMPROVEMENT and biased the freeze toward being
# declared MET on a reference change. That is the unrecoverable direction.
_REF_BOOK = "frozen_b36f49a4"

# Fingerprint of the reference book's identity fields as Crucible publishes them, stable across
# all five exports on disk (2026-07-30 .. 2026-08-02). Crucible undertook to flag basis changes
# before shipping them; this makes the undertaking self-checking rather than memory-dependent,
# which is the same lesson both sides drew twice this week. A re-mint can move the level either
# way, so an unnoticed one could manufacture a false PASS.
_REF_BASIS_FIELDS = ("spec_note", "window", "n_days", "weights", "traded_unit", "minted_at")
_REF_BASIS_FP = "ae47a4749c9d"


def _basis_fp(book: dict[str, object]) -> str:
    """Stable short hash over the fields that decide WHICH SERIES the correlations are against."""
    ident = {k: book.get(k) for k in _REF_BASIS_FIELDS}
    return hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:12]


def _load_corr() -> tuple[dict[str, float], str | None]:
    """`({config_hash: |corr to the reference book|}, basis fingerprint)` from the newest export.

    Fail-open on every path: no export, unreadable, the reference book absent, or the reference
    book RE-BASED -> empty map -> the redundancy leg reports as unavailable rather than silently
    reading a number. A leg that quietly passes when its input is missing or changed underneath
    it is worse than one that says it cannot run.
    """
    root = Path.home() / "optbt_data" / "exports"
    try:
        files = sorted(root.glob("corr_to_book_*.json"), key=lambda q: q.stat().st_mtime)
        if not files:
            return {}, None
        payload = json.loads(files[-1].read_text())
    except (OSError, ValueError):
        return {}, None
    book = (payload.get("books") or {}).get(_REF_BOOK)
    if not isinstance(book, dict):
        return {}, None
    fp = _basis_fp(book)
    if fp != _REF_BASIS_FP:
        return {}, fp
    out: dict[str, float] = {}
    for row in payload.get("rows", []):
        c = (row.get("corr") or {}).get(_REF_BOOK)
        h = row.get("config_hash")
        if h and c is not None:
            out[str(h)] = abs(float(c))
    return out, fp


def _wq(obs: list[Obs], w: dict[str, float], p: float) -> float:
    """Weighted quantile: the value where cumulative weight crosses p."""
    pairs = sorted(((v, w.get(c, 0.0)) for c, v, _ in obs), key=lambda t: t[0])
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
    num = sum(w.get(c, 0.0) * v for c, v, _ in obs if v >= thr)
    den = sum(w.get(c, 0.0) for c, v, _ in obs if v >= thr)
    return num / den if den > 0 else float("nan")


def _tcm_corr(obs: list[Obs], w: dict[str, float], p: float = 0.90) -> float:
    """THE REDUNDANCY LEG: weighted mean |corr to book| among the TOP-DECILE-BY-QUALITY configs.

    Deliberately the same population as the quality leg -- same window, same weighted p90
    threshold, same post-stratification -- because the question is not "is our average config
    redundant" but "is the supply that would actually be USED becoming redundant". Crucible
    measured IC(cpcv, corr_to_book) = +0.547 (zero-fill-equivalent, confirmed 2026-08-02): the
    better components ARE the more correlated ones, so a quality-only freeze condition can
    certify "done" exactly when the stream is most efficiently producing supply that dilutes
    their books. Visible in our own data: top decile |corr| 0.3837 against 0.3171 for the rest.

    RISING IS WORSE. The leg passes when this has NOT risen beyond its own measured floor.

    Crucible's two conditions on this use, both honoured: it is a SUPPLY statistic and must
    never become a generation target ("report it, do not tune against it"), and it is
    COHORT-SCOPED -- post-stratified over (hypothesis, dte_bucket), because a pooled read would
    reintroduce exactly the composition drift that contaminated the quality bar.
    """
    thr = _wq(obs, w, p)
    top = [(c, r) for c, v, r in obs if v >= thr and r is not None]
    num = sum(w.get(c, 0.0) * r for c, r in top)
    den = sum(w.get(c, 0.0) for c, _ in top)
    return num / den if den > 0 else float("nan")


def _weights(window: list[Obs], ref: dict[str, float]) -> tuple[dict[str, float], float, float]:
    """Post-stratification weights p_c/q_c, plus reference-mass coverage and the max weight.

    A cell absent from this window cannot be reweighted into it -- coverage reports how much
    reference mass is actually represented, so a thin window declares itself rather than
    silently returning a standardized-looking number built on half the strata.
    """
    n = len(window)
    seen = Counter(c for c, _, _ in window)
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
    clean = {n: [v for v in s if not math.isnan(v)] for n, s in sorted(series_by_width.items())}
    pts = [(n, statistics.pstdev(s) ** 2) for n, s in clean.items() if len(s) >= 3]
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


def window_bases(bases: list[str | None], width: int) -> list[frozenset[str]]:
    """The distinct GENERATION BASES present in each n=width window.

    A window is basis-clean when this is a single element. Two failure modes it must not
    smooth over, both learned on 2026-08-03 (D387):

    * A window that STRADDLES a basis change reports BOTH. It belongs to neither era and must
      never be assigned to one by picking a side -- that is how a 1200-row grid boundary got
      mistaken for a changepoint, 27 minutes from an unrelated publish, and reported to Crucible
      as if it were measured.
    * An UNTAGGED row (basis None -- predating the marker) contributes nothing, so an untagged
      window reports the empty set. Empty is UNKNOWN, not clean; the caller must refuse on it
      rather than read "no bases seen" as "one basis seen".
    """
    return [
        frozenset(b for b in bases[i : i + width] if b)
        for i in range(0, len(bases) - width + 1, width)
    ]


def _series(obs: list[Obs], ref: dict[str, float], width: int, std: bool, stat: str) -> list[float]:
    out = []
    for i in range(0, len(obs) - width + 1, width):
        win = obs[i : i + width]
        w = _weights(win, ref)[0] if std else dict.fromkeys({c for c, _, _ in win}, 1.0)
        if stat == "tcm":
            out.append(_tcm(win, w))
        elif stat == "tcm_corr":
            out.append(_tcm_corr(win, w))
        else:
            out.append(_wq(win, w, 0.90))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--window", type=int, default=1200)
    # THE REGISTERED READ MUST NOT SET ITS OWN BAR. Left to itself this script re-fits a/b on
    # every run -- including the windows under judgement -- so the threshold moves with the data
    # it is meant to judge. That is peeking wearing a formula: leg 2's bar was 0.0173 at
    # registration and 0.0210 one window later, purely from refitting. Pass the bar registered in
    # the prereg (f507e5da0677 / 13e4d2cece3f) and the read is a real test; omit it and the run
    # is labelled EXPLORATORY so no one can mistake a recomputed pass for the registered one.
    ap.add_argument("--leg1-bar", type=float, default=None, help="registered bar, quality leg")
    ap.add_argument("--leg2-bar", type=float, default=None, help="registered bar, redundancy leg")
    args = ap.parse_args()

    with db_connection(Path(args.snapshot)) as conn:
        raw = conn.execute(_QUERY).fetchall()
        censor = conn.execute(_CENSOR_QUERY).fetchall()
    corr, basis_fp = _load_corr()
    obs: list[Obs] = [(f"{h}/{b}", v, corr.get(ch)) for ch, h, b, v, _u in raw if v is not None]
    bases: list[str | None] = [u for _ch, _h, _b, v, u in raw if v is not None]
    joined = sum(1 for o in obs if o[2] is not None)
    n = len(obs)
    ref_counts = Counter(c for c, _, _ in obs)
    ref = {c: k / n for c, k in ref_counts.items()}
    print(
        f"honest arm, stage one, with cpcv: n={n}   cells={len(ref)}   "
        f"joined to corr_to_book: {joined} ({100 * joined / n:.1f}%)"
    )
    print(f"reference book: {_REF_BOOK}  basis_fp={basis_fp or 'ABSENT'} (pinned {_REF_BASIS_FP})")
    if basis_fp != _REF_BASIS_FP:
        print(
            "  *** REFERENCE RE-BASED OR ABSENT -- leg 2 will not run. Re-pin and re-base the\n"
            "      series at the boundary; do NOT compare across the change."
        )

    widths = (300, 400, 600, 800, 1200)
    print(
        f"\n{'series':<28}{'k':>4}{'mean':>10}{'sd@400':>9}{'sd@1200':>10}"
        f"{'b':>9}{'b_up':>9}{'BAR 2b_up':>10}"
    )
    bars: dict[str, float] = {}
    for stat in ("p90", "tcm", "tcm_corr"):
        for std in (False, True):
            by_w = {w: _series(obs, ref, w, std, stat) for w in widths}
            _a, b, b_up = _decompose(by_w)
            s = [v for v in by_w[args.window] if not math.isnan(v)]
            s400 = [v for v in by_w[400] if not math.isnan(v)]
            label = f"{stat} {'STANDARDISED' if std else 'raw (pooled)'}"
            bars[label] = 2 * b_up
            print(
                f"{label:<28}{len(s):>4}{statistics.fmean(s):>10.4f}"
                f"{statistics.pstdev(s400):>9.4f}{statistics.pstdev(s):>10.4f}"
                f"{b:>9.4f}{b_up:>9.4f}{2 * b_up:>9.4f}"
            )

    wb = window_bases(bases, args.window)
    eras = [sorted(s) for s in wb]
    print("\n=== GENERATION BASIS per window (D387) ===")
    print("  " + " ".join("?" if not e else ("*" if len(e) > 1 else e[0][:4]) for e in eras))
    print("  * = window STRADDLES a basis change (belongs to neither era);  ? = untagged")
    changes = [
        i + 1 for i in range(1, len(eras)) if eras[i] and eras[i - 1] and eras[i] != eras[i - 1]
    ]
    print(
        f"  distinct bases seen: {len({b for s in wb for b in s})}"
        f"   basis changes at window(s): {changes or 'none'}"
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
        bar, mode = _bar(args.leg1_bar, bars["tcm STANDARDISED"])
        print(
            f"  newest vs best-prior: {drift:+.4f}  bar 2b={bar:.4f} [{mode}]  -> "
            f"{'MOVING' if drift > bar else 'flat within the drift floor'}"
        )

    _leg2(obs, ref, args.window, joined, n, bars["tcm_corr STANDARDISED"], args.leg2_bar)

    print("\n=== companions (never the trigger) ===")
    _companions(obs, censor, args.window)
    return 0


def _bar(registered: float | None, recomputed: float) -> tuple[float, str]:
    """The registered bar if one was supplied, else the refit one -- labelled either way."""
    if registered is not None:
        return registered, "REGISTERED"
    return recomputed, "EXPLORATORY, refit on the judged data -- NOT the registered read"


def _leg2(
    obs: list[Obs],
    ref: dict[str, float],
    width: int,
    joined: int,
    n: int,
    b_bar: float,
    registered: float | None = None,
) -> None:
    """Leg 2 of freeze condition (C): has the GOOD supply become more redundant?"""
    print("\n=== LEG 2 (redundancy): TCM-corr, composition-standardised ===")
    if joined < 0.5 * n:
        print("  UNAVAILABLE -- corr_to_book join below 50%; the leg does not run.")
    else:
        rser = _series(obs, ref, width, True, "tcm_corr")
        print("  " + " ".join(f"{v:.4f}" for v in rser))
        # DIRECTION: "worse" means MORE redundant, i.e. HIGHER. The reference is therefore the
        # prior MAXIMUM -- exactly parallel to the quality leg asking whether the newest window
        # exceeded its previous best. Comparing against the prior MINIMUM (the first thing this
        # printed) is a max-drawup, which any noisy series clears; it reported WORSENED off a
        # +0.0214 excursion from a lucky low window.
        #
        # BAR: max(2*b_up, 2*sd). The a/b split collapses here -- sd shrinks 0.0154 -> 0.0087
        # from n=400 to n=1200, almost exactly 1/sqrt(n), so the fitted drift term is ~0 and
        # 2*b_up alone would be 0.0034 against a series whose own spread is 0.0087. A bar three
        # times tighter than the noise is not conservatism, it is a leg that always fails.
        # Falling back to 2*sd keeps the test on the spread actually observed at the decision
        # width; the rule reduces to 2*b_up whenever real drift dominates sampling.
        # WHY THE HISTORICAL WINDOWS DRIFT BETWEEN RUNS, stated because a reader will notice it
        # and should not have to wonder: post-stratification weights each window to the mix of
        # the FULL sample, and the full sample grows, so every past window is re-weighted on
        # every run. Registration recorded 0.4190 0.4137 ... max 0.4411; this run reads 0.4186
        # 0.4140 ... max 0.4409. The shift is ~0.0002 -- about 1.2% of the 0.0173 bar -- and
        # cannot flip a decision unless the read lands within 0.0002 of the threshold, in which
        # case the honest call is "at the bar" anyway. The prereg pinned the baseline as a
        # LITERAL (0.4411) precisely so the comparison does not float; use that number, not the
        # recomputed one, when resolving.
        rclean = [v for v in rser if not math.isnan(v)]
        rsd = 2 * statistics.pstdev(rclean)
        rbar, mode = _bar(registered, max(b_bar, rsd))
        if len(rclean) >= 2:
            rise = rclean[-1] - max(rclean[:-1])
            print(
                f"  newest vs worst-prior(highest): {rise:+.4f}  bar={rbar:.4f} [{mode}]"
                f" (refit would be 2b_up={b_bar:.4f}, 2sd={rsd:.4f})"
                f"  -> {'WORSENED' if rise > rbar else 'not worsened within the floor'}"
            )
        print(f"  reference book: {_REF_BOOK}   (RISING = more redundant = worse)")


def _companions(obs: list[Obs], censor: list, width: int) -> None:
    p1 = [
        sum(1 for _, v, _ in obs[i : i + width] if v >= 1.0)
        for i in range(0, len(obs) - width + 1, width)
    ]
    print(
        f"  P(cpcv>=1.0) counts/window: {p1}  (blind spot: p90/TCM cannot see a top-1%-only lift)"
    )
    print("  P(cpcv|submitted) by hypothesis -- a shift here moves the measured population:")
    for h, sub, meas in censor[:6]:
        print(f"    {h!s:<22} {meas:>6}/{sub:<6} = {100 * meas / sub:5.1f}%")


if __name__ == "__main__":
    raise SystemExit(main())
