"""Probe: do king's RICH config features predict honest WF quality? (re-target king M -> WF)

WHY: D186 placed decorrelation at assembly, leaving QUALITY as the generation layer's job. A
coarse-cell check showed (hypothesis, directional, dte) ~zero-predicts honest WF-median
(Spearman -0.03) -- WF quality is idiosyncratic at the recipe level. This tests whether the RICH
king features (king/featurize.py: param numerics, indicator/exit/signal-type one-hots, combiner
categoricals) predict it -- i.e. whether the meta-king's machinery, re-targeted from min_margin
(M) to honest WF, is a viable generation-layer quality model and the right thing to fold king
into. The SAME harness also predicts cpcv_p25 (known-predictable, D155 ~+0.35) so the
cpcv-vs-WF contrast on identical features/model/population is clean.

Pure-python ridge (no numpy in env) + k-fold CV; reports out-of-fold Spearman (the IC).
Offline, read-only. Copy the live DB to /tmp first (it holds an RW lock); pass via --db.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from typing import TYPE_CHECKING

import duckdb

from forge.king.featurize import featurize

if TYPE_CHECKING:
    from collections.abc import Sequence

_NUMERIC_COLUMNS = [
    "num:underlying_is_null",
    "num:has_regime_filter",
    "num:has_directional",
    "num:n_signals",
    "num:n_exits",
    "num:n_indicators",
    "num:delta_target",
    "num:dte_min",
    "num:dte_max",
    "num:min_oi",
    "num:min_vol",
    "num:k",
    "num:rank_k",
    "num:risk_frac",
]


def _cat_value(genome: dict, key: str) -> str:
    c = genome.get("combiner") or {}
    s = genome.get("sizer") or {}
    table = {
        "cat:hypothesis": str(genome.get("hypothesis")),
        "cat:dte_bucket": str(genome.get("dte_bucket")),
        "cat:hyp_x_dte": f"{genome.get('hypothesis')}|{genome.get('dte_bucket')}",
        "cat:combiner_type": str(c.get("type")),
        "cat:direction_strategy": str(c.get("direction_strategy")),
        "cat:rebalance": str(c.get("rebalance_frequency")),
        "cat:sizer_type": str(s.get("type") or s.get("kind")),
        "cat:tier": str(genome.get("tier")),
    }
    return table[key]


_CAT_KEYS = [
    "cat:hypothesis",
    "cat:dte_bucket",
    "cat:hyp_x_dte",
    "cat:combiner_type",
    "cat:direction_strategy",
    "cat:rebalance",
    "cat:sizer_type",
    "cat:tier",
]


def build_columns(genomes: Sequence[dict], min_support: int) -> list[str]:
    """Enumerate king-style feature columns present in the data at >= min_support."""
    counts: Counter[str] = Counter()
    for g in genomes:
        for key in _CAT_KEYS:
            counts[f"{key}={_cat_value(g, key)}"] += 1
        inds = {str(i) for s in (g.get("signals") or []) for i in (s.get("indicators") or [])}
        for t in inds:
            counts[f"has_ind:{t}"] += 1
        for ex in genome_exit_ids(g):
            counts[f"has_exit:{ex}"] += 1
        for st in {str(s["type"]) for s in (g.get("signals") or []) if s.get("type")}:
            counts[f"has_sigt:{st}"] += 1
    n = len(genomes)
    one_hot = [c for c, k in counts.items() if min_support <= k <= n - min_support]
    return [*_NUMERIC_COLUMNS, *sorted(one_hot)]


def genome_exit_ids(genome: dict) -> set[str]:
    exits = genome.get("exits") or genome.get("exit_rules") or []
    return {str(ex.get("id")) if isinstance(ex, dict) else str(ex) for ex in exits}


# --------------------------------------------------------------------------- stats


def _rankdata(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    rx, ry = _rankdata(xs), _rankdata(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return cov / ((vx * vy) ** 0.5) if vx > 0 and vy > 0 else 0.0


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gauss-Jordan with partial pivoting; returns x solving matrix @ x = rhs."""
    n = len(matrix)
    aug = [[*matrix[i], rhs[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-12:
            continue
        aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col] / pv
            if f == 0.0:
                continue
            for c in range(col, n + 1):
                aug[r][c] -= f * aug[col][c]
    return [aug[i][n] / aug[i][i] if abs(aug[i][i]) > 1e-12 else 0.0 for i in range(n)]


def ridge_cv_ic(rows: list[list[float]], y: list[float], lam: float, folds: int) -> float:
    """Out-of-fold Spearman (IC) of a ridge predicting y from standardized rows."""
    n = len(rows)
    p = len(rows[0])
    preds = [0.0] * n
    actual = [0.0] * n
    fill = 0
    for f in range(folds):
        tr = [i for i in range(n) if i % folds != f]
        te = [i for i in range(n) if i % folds == f]
        ymean = sum(y[i] for i in tr) / len(tr)
        a = [[0.0] * p for _ in range(p)]
        b = [0.0] * p
        for i in tr:
            xi = rows[i]
            yc = y[i] - ymean
            for j in range(p):
                xij = xi[j]
                if xij == 0.0:
                    continue
                b[j] += xij * yc
                arow = a[j]
                for k in range(p):
                    arow[k] += xij * xi[k]
        for j in range(p):
            a[j][j] += lam
        w = _solve(a, b)
        for i in te:
            xi = rows[i]
            preds[fill] = ymean + sum(xi[j] * w[j] for j in range(p))
            actual[fill] = y[i]
            fill += 1
    return spearman(preds, actual)


def standardize(genomes: Sequence[dict], columns: Sequence[str]) -> list[list[float]]:
    """Featurize each genome, median-impute NaNs, z-score; drop constant columns later."""
    raw = [featurize(g, columns) for g in genomes]
    p = len(columns)
    cols: list[list[float]] = [[] for _ in range(p)]
    for vec in raw:
        for j in range(p):
            v = vec[j]
            if not math.isnan(v):
                cols[j].append(v)
    out = [[0.0] * p for _ in range(len(raw))]
    keep: list[int] = []
    stats = []
    for j in range(p):
        present = cols[j]
        med = sorted(present)[len(present) // 2] if present else 0.0
        full = [med if math.isnan(vec[j]) else vec[j] for vec in raw]
        mean = sum(full) / len(full)
        var = sum((x - mean) ** 2 for x in full) / len(full)
        std = var**0.5
        stats.append((med, mean, std))
        if std > 1e-9:
            keep.append(j)
    for i, vec in enumerate(raw):
        row = []
        for j in keep:
            med, mean, std = stats[j]
            v = med if math.isnan(vec[j]) else vec[j]
            row.append((v - mean) / std)
        out[i] = row
    return out


# --------------------------------------------------------------------------- main


def _gate_value(gate_results: dict, key: str) -> float | None:
    """Pull a gate's numeric value from a verdict's gate_results dict."""
    x = gate_results.get(key)
    return x.get("value") if isinstance(x, dict) else None


def load_components(db_path: str, *, broad_only: bool) -> list[dict]:
    con = duckdb.connect(db_path, read_only=True)
    rows = con.execute(
        "SELECT v.config_hash, v.gate_results, s.config_json "
        "FROM verdicts v JOIN submissions s USING(config_hash) "
        "WHERE v.decision='component' AND v.gate_results IS NOT NULL"
    ).fetchall()
    con.close()
    seen: set[str] = set()
    out: list[dict] = []
    for h, gr, cj in rows:
        if h in seen:
            continue
        seen.add(h)
        g = json.loads(gr) if isinstance(gr, str) else gr
        rc = g.get("regime_coverage", {})
        if "unverified" in str(rc.get("detail") if isinstance(rc, dict) else ""):
            continue
        genome = json.loads(cj)
        if broad_only and (genome.get("combiner") or {}).get("type") != "cross_sectional_rank":
            continue
        out.append(
            {
                "genome": genome,
                "wf_median": _gate_value(g, "walk_forward_sharpe_median"),
                "cpcv_p25": _gate_value(g, "cpcv_sharpe_p25"),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="(snapshot) Forge DB path")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--min-support", type=int, default=20)
    ap.add_argument("--all-cohorts", action="store_true", help="include single-name cohort")
    args = ap.parse_args(argv)

    comps = load_components(args.db, broad_only=not args.all_cohorts)
    print("=" * 74)
    print(f"WF-QUALITY PROBE  (honest {'all' if args.all_cohorts else 'BROAD'} components)")
    print("=" * 74)
    print(f"components: {len(comps)}")
    genomes = [c["genome"] for c in comps]
    columns = build_columns(genomes, args.min_support)
    rows = standardize(genomes, columns)
    print(f"features (support>={args.min_support}, non-constant): {len(rows[0])}")
    print("(out-of-fold Spearman = IC; same features/model/population, only the target changes)\n")
    for target in ("cpcv_p25", "wf_median"):
        idx = [i for i in range(len(comps)) if comps[i][target] is not None]
        x = [rows[i] for i in idx]
        y = [comps[i][target] for i in idx]
        tag = "SANITY (D155 ~+0.35)" if target == "cpcv_p25" else "THE QUESTION"
        line = f"  {target:<12} n={len(y):<5}"
        for lam in (1.0, 10.0, 100.0):
            line += f"  IC(λ={lam:g})={ridge_cv_ic(x, y, lam, args.folds):+.3f}"
        print(line + f"   <- {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
