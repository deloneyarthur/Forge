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
from pathlib import Path
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


# Scalar quality metrics already present in gate_results (wave-1 sweep targets).
TARGET_GATES = [
    "cpcv_sharpe_p25",
    "walk_forward_sharpe_median",
    "sharpe_baseline",
    "deflated_sharpe",
    "profit_factor",
    "regime_stress_p25_return",
    "max_drawdown_ceiling",
    "pbo",
]
# Computed composites: 2-gate proximities (D114) + the all-gate min_margin (King's M target).
_COMPOSITE_TARGETS = ["joint_min", "joint_prod", "min_margin_z"]
# WF refit percentile/derived targets (from Crucible's wf_percentile_refit label; --wf-label).
_WF_REFIT_TARGETS = [
    "wf_p95",
    "wf_p90",
    "wf_p75",
    "wf_p50_refit",
    "wf_p25",
    "wf_p10",
    "wf_min",
    "wf_mean",
    "wf_trimmed_mean",
    "wf_top_quartile_mean",
    "wf_frac_positive",
    "wf_iqr",
    "wf_cov",
]
# Targets computed from the per-fold series (set to None together when folds are absent).
_WF_FOLD_DERIVED = (
    "wf_mean",
    "wf_trimmed_mean",
    "wf_top_quartile_mean",
    "wf_frac_positive",
    "wf_p90",
    "wf_p10",
    "wf_min",
    "wf_iqr",
    "wf_cov",
)
# CPCV refit distribution targets (round-2 A: provided percentiles + cpcv_paths-derived extras).
_CPCV_REFIT_TARGETS = [
    "cpcv_p95",
    "cpcv_p90",
    "cpcv_p75",
    "cpcv_p50_refit",
    "cpcv_p25_refit",
    "cpcv_p10",
    "cpcv_min",
    "cpcv_mean",
    "cpcv_trimmed_mean",
    "cpcv_top_quartile_mean",
    "cpcv_frac_positive",
    "cpcv_iqr",
    "cpcv_cov",
]
# Regime-stress refit distribution targets (round-2 B rerun; regime-AGNOSTIC return bootstrap).
_REGIME_STRESS_TARGETS = [
    "rs_p5",
    "rs_p10",
    "rs_p25",
    "rs_p50",
    "rs_p75",
    "rs_p90",
    "rs_p95",
    "rs_mean",
    "rs_frac_positive",
    "rs_cov",
]
_LOWER_IS_BETTER = {
    "max_drawdown_ceiling",
    "pbo",
    "wf_iqr",
    "wf_cov",
    "cpcv_iqr",
    "cpcv_cov",
    "rs_cov",
}
# Sizing/selection knobs that mechanically drive risk metrics (dropped in the ablation).
_MECHANICAL_COLUMNS = {
    "num:risk_frac",
    "num:rank_k",
    "num:delta_target",
    "num:dte_min",
    "num:dte_max",
    "num:min_oi",
    "num:min_vol",
    "num:k",
}


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
        metrics: dict[str, float | None] = {k: _gate_value(g, k) for k in TARGET_GATES}
        wf, cp = metrics["walk_forward_sharpe_median"], metrics["cpcv_sharpe_p25"]
        both = wf is not None and cp is not None
        metrics["joint_min"] = min(wf / 2.0, cp / 1.5) if both else None
        metrics["joint_prod"] = (wf / 2.0) * (cp / 1.5) if both else None
        out.append({"config_hash": h, "genome": genome, "metrics": metrics})
    return out


def add_min_margin(comps: list[dict]) -> None:
    """Add an all-gate `min_margin_z` (worst per-gate z-score, direction-aware) to each component.

    Approximates King's `min_margin` (M): standardize each gate's value across the population,
    flip lower-is-better gates, take the min -> 'how the component fares on its weakest gate'.
    """
    stats: dict[str, tuple[float, float] | None] = {}
    for gate in TARGET_GATES:
        present = [c["metrics"][gate] for c in comps if c["metrics"].get(gate) is not None]
        if len(present) < 2:
            stats[gate] = None
            continue
        mean = sum(present) / len(present)
        std = (sum((x - mean) ** 2 for x in present) / len(present)) ** 0.5
        stats[gate] = (mean, std if std > 1e-9 else 1.0)
    for c in comps:
        zs: list[float] = []
        for gate in TARGET_GATES:
            v = c["metrics"].get(gate)
            st = stats[gate]
            if v is None or st is None:
                continue
            z = (v - st[0]) / st[1]
            zs.append(-z if gate in _LOWER_IS_BETTER else z)
        c["metrics"]["min_margin_z"] = min(zs) if zs else None


def _pctile(srt: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not srt:
        return float("nan")
    if len(srt) == 1:
        return srt[0]
    pos = q * (len(srt) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(srt) - 1)
    frac = pos - lo
    return srt[lo] * (1.0 - frac) + srt[hi] * frac


def _series_extras(series: list, prefix: str, m: dict) -> None:
    """Distribution extras (p90/min/mean/trimmed/top-q/frac-pos/IQR/CoV) from a value series."""
    vals = [x for x in series if x is not None]
    keys = (
        f"{prefix}_p90",
        f"{prefix}_min",
        f"{prefix}_mean",
        f"{prefix}_trimmed_mean",
        f"{prefix}_top_quartile_mean",
        f"{prefix}_frac_positive",
        f"{prefix}_iqr",
        f"{prefix}_cov",
    )
    if not vals:
        for k in keys:
            m[k] = None
        return
    srt = sorted(vals)
    n = len(srt)
    mean = sum(vals) / n
    std = (sum((x - mean) ** 2 for x in vals) / n) ** 0.5
    q = max(1, n // 4)
    trim = max(1, n // 10)
    m[f"{prefix}_p90"] = _pctile(srt, 0.90)
    m[f"{prefix}_min"] = srt[0]
    m[f"{prefix}_mean"] = mean
    m[f"{prefix}_trimmed_mean"] = sum(srt[trim : n - trim]) / max(1, n - 2 * trim)
    m[f"{prefix}_top_quartile_mean"] = sum(srt[-q:]) / q
    m[f"{prefix}_frac_positive"] = sum(1 for x in vals if x > 0) / n
    m[f"{prefix}_iqr"] = _pctile(srt, 0.75) - _pctile(srt, 0.25)
    m[f"{prefix}_cov"] = std / abs(mean) if abs(mean) > 1e-9 else None


def _load_label_components(label_path: str) -> list:
    """Return the components array from a Crucible label file (list, or dict with 'components')."""
    data = json.loads(Path(label_path).read_text())
    if isinstance(data, list):
        return data
    if "components" in data:
        return data["components"]
    return next((v for v in data.values() if isinstance(v, list)), [])


def add_wf_refit_targets(comps: list[dict], label_path: str) -> int:
    """Join Crucible's WF refit label by config_hash; add WF targets. Returns # matched."""
    by_hash = {r["config_hash"]: r for r in _load_label_components(label_path)}
    matched = 0
    for c in comps:
        r = by_hash.get(c["config_hash"])
        m = c["metrics"]
        if r is None:
            for t in (*_WF_REFIT_TARGETS, *_CPCV_REFIT_TARGETS):
                m[t] = None
            continue
        matched += 1
        m["wf_p95"] = r.get("wf_sharpe_p95")
        m["wf_p75"] = r.get("wf_sharpe_p75")
        m["wf_p50_refit"] = r.get("wf_sharpe_p50")
        m["wf_p25"] = r.get("wf_sharpe_p25")
        folds = [f[2] for f in (r.get("wf_folds") or []) if f and f[2] is not None]
        if folds:
            srt = sorted(folds)
            n = len(srt)
            mean = sum(folds) / n
            std = (sum((x - mean) ** 2 for x in folds) / n) ** 0.5
            q = max(1, n // 4)
            trim = max(1, n // 10)
            m["wf_mean"] = mean
            m["wf_trimmed_mean"] = sum(srt[trim : n - trim]) / max(1, n - 2 * trim)
            m["wf_top_quartile_mean"] = sum(srt[-q:]) / q
            m["wf_frac_positive"] = sum(1 for x in folds if x > 0) / n
            m["wf_p90"] = _pctile(srt, 0.90)
            m["wf_p10"] = _pctile(srt, 0.10)
            m["wf_min"] = srt[0]
            m["wf_iqr"] = _pctile(srt, 0.75) - _pctile(srt, 0.25)
            m["wf_cov"] = std / abs(mean) if abs(mean) > 1e-9 else None
        else:
            for key in _WF_FOLD_DERIVED:
                m[key] = None
        m["cpcv_p95"] = r.get("cpcv_sharpe_p95")
        m["cpcv_p75"] = r.get("cpcv_sharpe_p75")
        m["cpcv_p50_refit"] = r.get("cpcv_sharpe_p50")
        m["cpcv_p25_refit"] = r.get("cpcv_sharpe_p25")
        m["cpcv_p10"] = r.get("cpcv_sharpe_p10")
        _series_extras(r.get("cpcv_paths") or [], "cpcv", m)
    return matched


def add_regime_stress_targets(comps: list[dict], label_path: str) -> int:
    """Join the regime-stress label by config_hash; add rs_* targets. Returns # matched."""
    by_hash = {r["config_hash"]: r for r in _load_label_components(label_path)}
    matched = 0
    for c in comps:
        r = by_hash.get(c["config_hash"])
        m = c["metrics"]
        if r is None:
            for t in _REGIME_STRESS_TARGETS:
                m[t] = None
            continue
        matched += 1
        m["rs_p5"] = r.get("regime_stress_p5")
        m["rs_p10"] = r.get("regime_stress_p10")
        m["rs_p25"] = r.get("regime_stress_p25")
        m["rs_p50"] = r.get("regime_stress_p50")
        m["rs_p75"] = r.get("regime_stress_p75")
        m["rs_p90"] = r.get("regime_stress_p90")
        m["rs_p95"] = r.get("regime_stress_p95")
        m["rs_mean"] = r.get("regime_stress_mean")
        m["rs_frac_positive"] = r.get("regime_stress_frac_positive")
        mean = r.get("regime_stress_mean")
        std = r.get("regime_stress_std")
        m["rs_cov"] = std / abs(mean) if mean and abs(mean) > 1e-9 and std is not None else None
    return matched


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="(snapshot) Forge DB path")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--min-support", type=int, default=20)
    ap.add_argument("--all-cohorts", action="store_true", help="include single-name cohort")
    ap.add_argument("--drop-mechanical", action="store_true", help="ablation: drop sizing knobs")
    ap.add_argument("--wf-label", help="Crucible refit_distributions label (.json): WF + CPCV")
    ap.add_argument("--rs-label", help="Crucible regime_stress_distribution label (.json)")
    args = ap.parse_args(argv)

    comps = load_components(args.db, broad_only=not args.all_cohorts)
    add_min_margin(comps)
    sweep_targets = [*TARGET_GATES, *_COMPOSITE_TARGETS]
    matched = 0
    if args.wf_label:
        matched = add_wf_refit_targets(comps, args.wf_label)
        sweep_targets = [*sweep_targets, *_WF_REFIT_TARGETS, *_CPCV_REFIT_TARGETS]
    if args.rs_label:
        add_regime_stress_targets(comps, args.rs_label)
        sweep_targets = [*sweep_targets, *_REGIME_STRESS_TARGETS]
    print("=" * 74)
    mode = "  [ABLATION: mechanical knobs dropped]" if args.drop_mechanical else ""
    print(f"WF-QUALITY PROBE  (honest {'all' if args.all_cohorts else 'BROAD'} components){mode}")
    print("=" * 74)
    suffix = f"   WF-label matched: {matched}" if args.wf_label else ""
    print(f"components: {len(comps)}{suffix}")
    genomes = [c["genome"] for c in comps]
    columns = build_columns(genomes, args.min_support)
    if args.drop_mechanical:
        columns = [c for c in columns if c not in _MECHANICAL_COLUMNS]
    rows = standardize(genomes, columns)
    print(f"features (support>={args.min_support}, non-constant): {len(rows[0])}")
    print("(out-of-fold Spearman = IC; same features/model/population, only the target changes)\n")
    results: list[tuple[str, int, float | None]] = []
    for target in sweep_targets:
        idx = [i for i in range(len(comps)) if comps[i]["metrics"].get(target) is not None]
        if len(idx) < 100:
            results.append((target, len(idx), None))
            continue
        x = [rows[i] for i in idx]
        y = [comps[i]["metrics"][target] for i in idx]
        results.append((target, len(idx), ridge_cv_ic(x, y, 10.0, args.folds)))
    ranked = sorted(results, key=lambda r: (r[2] is None, -abs(r[2] or 0.0)))
    print("  ranked by |IC| (out-of-fold Spearman, λ=10):")
    for target, n, ic in ranked:
        if ic is None:
            print(f"    {target:<26} n={n:<5} (too few, skipped)")
            continue
        flag = " (lower=better)" if target in _LOWER_IS_BETTER else ""
        anchor = "  <- D155 sanity" if target == "cpcv_sharpe_p25" else ""
        print(f"    {target:<26} n={n:<5} IC={ic:+.3f}{flag}{anchor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
