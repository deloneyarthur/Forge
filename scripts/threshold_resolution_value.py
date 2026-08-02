"""Does THRESHOLD RESOLUTION buy anything? The converge programme's open question.

Thresholds are drawn `round(rng.uniform(low, high), 4)` — a continuous draw quantised to four
decimals, so ~10,000 effective points per range and **every emitted config is unique by
construction**. That matters because DSR's `search_n_trials` is the cardinality of the set the
selection was drawn from (D310/D313), per slot, cumulative and unbounded: our own search
breadth permanently inflates our own promotion hurdle, and it never stops growing.

Crucible measured one half of the value question on their side (2026-08-01, n=7,439): a
percentile-threshold spread buys **zero decorrelation** - |d rsi_pct| t=+0.4, |d ivol_pct|
t=-0.6, whole threshold model R^2 0.0018. This script measures the other half on ours: does
threshold POSITION predict component QUALITY? If it buys neither, a coarser grid is a pure
tightening that slows the n_trials treadmill for nothing lost.

BASIS DISCIPLINE, and it is the whole validity of the result:
  * HONEST ARM ONLY (`selection_mode='prefilter_sample'`) — the population unselected by both
    the prefilter and the ranker. Measuring on ranked rows would measure our own selection,
    not the grammar (the D337/D338 collider).
  * STAGE ONE ONLY (`measurement_basis IS DISTINCT FROM 'fullhist_refit'`) — never pooled with
    the refit lane.
  * WITHIN A CELL, never across. Thresholds live in different units per indicator, so a pooled
    regression would read cell differences as a threshold effect.

TWO STATISTICS, because the centre is a weak guide to the tail (D341: spearman(cell median,
P(>=floor)) = +0.389 against p90's +0.654):
  1. Spearman(threshold, cpcv) per cell — rank association over the whole distribution.
  2. Top-decile concentration — do the best configs sit in a particular threshold region?
     Permutation-tested, because that is the question a coarser grid would actually harm: if
     the good outcomes cluster somewhere specific, resolution is needed to land there.

A NULL IS ONLY MEANINGFUL WITH POWER, so the report prints the minimum |rho| each cell could
detect. Reading "no signal" off an underpowered cell is the error we corrected Crucible on.

Usage: threshold_resolution_value.py SNAPSHOT.db [--min-n 150] [--resamples 2000]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

from forge.core.seed import SeedHierarchy
from forge.persistence.db import db_connection

_QUERY = """
    SELECT s.config_json,
           TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE)
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    WHERE s.selection_mode = 'prefilter_sample'
      AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
"""


def _rank(xs: list[float]) -> list[float]:
    """Average ranks, so ties (quantised thresholds do tie) do not bias the correlation."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    rx, ry = _rank(xs), _rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return num / (dx * dy) if dx and dy else 0.0


def _min_detectable_rho(n: int, alpha_z: float = 1.96, power_z: float = 0.84) -> float:
    """|rho| detectable at ~80% power, two-sided 0.05 — via Fisher's z."""
    if n <= 4:
        return float("nan")
    z = (alpha_z + power_z) / math.sqrt(n - 3)
    return math.tanh(z)


def _top_decile_shift(
    th: list[float], cpcv: list[float], rng: random.Random, resamples: int
) -> tuple[float, float]:
    """Standardised mean-threshold shift of the top-cpcv decile, and its permutation p.

    The question a coarse grid would fail: do the BEST configs concentrate in a particular
    threshold region? Permutation rather than a t-test — thresholds are bounded-uniform and
    cpcv is heavily skewed, so the normal approximation is not earned.
    """
    n = len(th)
    k = max(5, n // 10)
    order = sorted(range(n), key=lambda i: cpcv[i], reverse=True)
    top = [th[i] for i in order[:k]]
    sd = statistics.pstdev(th) or 1e-12
    observed = (statistics.fmean(top) - statistics.fmean(th)) / sd
    idx = list(range(n))
    hits = 0
    for _ in range(resamples):
        rng.shuffle(idx)
        perm = [th[idx[i]] for i in range(k)]
        if abs((statistics.fmean(perm) - statistics.fmean(th)) / sd) >= abs(observed):
            hits += 1
    return observed, hits / resamples


def _summarise(rows_out: list[tuple]) -> list[tuple]:
    """Print the two verdicts separately and return the significant regime rows.

    Directional and regime thresholds get separate summaries deliberately: pooling them was
    the first draft's error, and it hid a real regime signal under a directional null.
    """
    rhos = [r[2] for r in rows_out]
    dir_sig = [r for r in rows_out if abs(r[2]) > r[6]]
    reg_rows = [r for r in rows_out if not r[7] and not math.isnan(r[3])]
    reg_sig = [r for r in reg_rows if abs(r[3]) > r[6]]
    perm_sig = [r for r in rows_out if r[5] < 0.05]

    print("=== DIRECTIONAL threshold ===")
    print(
        f"  rho: mean {statistics.fmean(rhos):+.4f}  median {statistics.median(rhos):+.4f}  "
        f"|rho| max {max(abs(r) for r in rhos):.4f}"
    )
    print(f"  cells clearing their own MDE: {len(dir_sig)}/{len(rows_out)}")
    print(
        f"  top-decile permutation p<0.05: {len(perm_sig)}/{len(rows_out)} "
        f"(chance ~{0.05 * len(rows_out):.1f})"
    )

    print("\n=== REGIME-GATE threshold (varying gates only) ===")
    if reg_rows:
        rr = [r[3] for r in reg_rows]
        print(
            f"  rho: mean {statistics.fmean(rr):+.4f}  median {statistics.median(rr):+.4f}  "
            f"negative in {sum(1 for x in rr if x < 0)}/{len(rr)}"
        )
        print(f"  cells clearing their own MDE: {len(reg_sig)}/{len(reg_rows)}")
        for r in sorted(reg_sig, key=lambda x: x[3]):
            print(f"    {r[0]:<50} n={r[1]:<6} rho_reg={r[3]:+.3f}  MDE={r[6]:.3f}  gate={r[8]}")
    flat = sum(1 for r in rows_out if r[7])
    print(f"  cells with a FLAT (categorical) regime threshold: {flat}")
    return reg_sig


def _selection_check(rows: list[tuple[str, float | None]], gates: list[str]) -> None:
    """Does the threshold drive whether a cpcv is OBSERVED? Not optional — it is the validity.

    Within a cell the sampler assigns the threshold at random, which makes the comparison an
    experiment rather than a fit. That holds ONLY if the threshold does not also decide whether
    the config reaches a cpcv at all; if it does, conditioning on "has a cpcv" conditions on a
    collider and the association is manufactured. Measured on live data: `adx` is flat across
    its range (clean), `vix_term_slope` falls 75.9% -> 50.7% (confounded — its rho must not be
    read causally, and the drop is itself a finding: a quarter of that range emits configs that
    never reach measurement).
    """
    if not gates:
        return
    print("\n=== SELECTION CHECK: does the threshold drive whether a cpcv exists? ===")
    obs: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for cj, cpcv in rows:
        for sig in json.loads(cj).get("signals", []):
            inds = sig.get("indicators") or []
            if sig.get("role") != "regime_filter" or not inds or inds[0] not in gates:
                continue
            t = sig.get("params", {}).get("threshold")
            if t is not None:
                obs[inds[0]].append((float(t), cpcv is not None))
    for gate in gates:
        vals = sorted(obs.get(gate, []))
        if len(vals) < 50:
            continue
        q = len(vals) // 5
        rates = [
            sum(1 for _, ok in (vals[i * q : (i + 1) * q] if i < 4 else vals[4 * q :]) if ok)
            / len(vals[i * q : (i + 1) * q] if i < 4 else vals[4 * q :])
            for i in range(5)
        ]
        spread = max(rates) - min(rates)
        verdict = "CONFOUNDED - do not read causally" if spread > 0.10 else "clean"
        pretty = "  ".join(f"Q{i + 1} {100 * r:.1f}%" for i, r in enumerate(rates))
        print(f"  {gate:<18} {pretty}   spread={100 * spread:.1f}pp  -> {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--min-n", type=int, default=150)
    ap.add_argument("--resamples", type=int, default=2000)
    args = ap.parse_args()

    with db_connection(Path(args.snapshot)) as conn:
        rows = conn.execute(_QUERY).fetchall()

    cells: dict[tuple, list[tuple[float, float | None, float]]] = defaultdict(list)
    for cj, cpcv in rows:
        if cpcv is None:
            continue
        cfg = json.loads(cj)
        d_id = r_id = d_th = r_th = None
        for sig in cfg.get("signals", []):
            p, inds = sig.get("params", {}), (sig.get("indicators") or [])
            if not inds:
                continue
            if sig.get("role") == "directional":
                d_id, d_th = inds[0], p.get("threshold")
            elif sig.get("role") == "regime_filter" and r_id is None:
                r_id, r_th = inds[0], p.get("threshold")
        if d_id is None or d_th is None:
            continue
        key = (cfg.get("hypothesis"), cfg.get("dte_bucket"), d_id, r_id)
        cells[key].append((float(d_th), None if r_th is None else float(r_th), float(cpcv)))

    big = {k: v for k, v in cells.items() if len(v) >= args.min_n}
    print(f"honest-arm stage-one rows with cpcv: {sum(len(v) for v in cells.values())}")
    print(f"cells: {len(cells)}   cells at n >= {args.min_n}: {len(big)}\n")

    rng = SeedHierarchy(42).rng("threshold_resolution")
    hdr = f"{'cell':<58}{'n':>6}{'rho_dir':>9}{'rho_reg':>9}{'top10%':>9}{'perm_p':>8}{'MDE':>7}"
    print(hdr)
    print("-" * len(hdr))
    rows_out = []
    for key, vals in sorted(big.items(), key=lambda kv: -len(kv[1])):
        n = len(vals)
        dth = [v[0] for v in vals]
        cp = [v[2] for v in vals]
        rho_d = _spearman(dth, cp)
        reg = [(v[1], v[2]) for v in vals if v[1] is not None]
        rho_r = (
            _spearman([a for a, _ in reg], [b for _, b in reg])
            if len(reg) >= args.min_n
            else float("nan")
        )
        shift, pval = _top_decile_shift(dth, cp, rng, args.resamples)
        mde = _min_detectable_rho(n)
        # A constant threshold (a categorical gate like `market_state`) yields rho == 0 by
        # construction. That is NO VARIATION, not "no effect" — reporting it as a null would
        # be the same category error as reading a zero count off an underpowered sample.
        reg_th = [a for a, _ in reg]
        reg_flat = len(set(reg_th)) <= 1 if reg_th else True
        label = f"{key[0][:14]}/{key[2]}x{key[3]}"
        rr = "  flat " if reg_flat else f"{rho_r:>7.3f}"
        print(f"{label:<58}{n:>6}{rho_d:>9.3f}{rr:>9}{shift:>9.3f}{pval:>8.3f}{mde:>7.3f}")
        rows_out.append((label, n, rho_d, rho_r, shift, pval, mde, reg_flat, key[3]))

    reg_sig = _summarise(rows_out)
    _selection_check(rows, sorted({r[8] for r in reg_sig if r[8]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
