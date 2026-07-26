"""Is `wf_p10`'s advantage REAL, or an artifact of extremity and label sparsity?

THE PROBLEM. `wf_p10` at q=0.999 looked best in the merge sweep (24.28x at top 0.5%, 6/6
splits, 8 gate-clearers vs `wf_p25`'s 4) but collapses to 2.92x / 4-of-6 at q=0.990 -- a 7x
discontinuity between adjacent quantiles. Two clues say be suspicious:

  * EVENTS PER VARIABLE. q=0.999 on a ~147k train window yields ~146 positives against 115
    features -- 1.3 events per feature, where the standard floor is 10. `wf_p25` q=0.990
    yields ~1,468 (12.8 per feature). The two champions are not on equal statistical footing.
  * REGULARISATION RESPONSE. `wf_p10` q=0.999 IMPROVES with heavier ridging (12.79 -> 13.40
    -> 14.13 for lambda 1 -> 10 -> 100), the signature of a fit straining against too few
    positives. `wf_p25` is flat (9.10 / 9.15 / 9.13), the signature of a fit that is not.

THE CONFOUND, stated exactly: the quantile sets BOTH how extreme the label is AND how many
positives exist. Comparing `wf_p10` q=0.999 against `wf_p25` q=0.990 varies both at once, so
neither "wf_p10 is the better metric" nor "extreme labels are better" is identified.

FOUR ARMS THAT SEPARATE THEM
  1  DISTRIBUTION FORENSICS   does wf_p10 have mass points / ties that make low quantiles
                              degenerate? That alone would explain the cliff without any
                              claim about signal.
  2  MATCHED POSITIVE COUNTS  the decisive arm. Choose q PER METRIC so every target trains
                              on the SAME number of positives. If wf_p10 still wins at
                              matched n, the metric is better. If its edge only appears at
                              tiny n, the edge is extremity, not wf_p10.
  3  SELECTION OVERLAP        do wf_p10 and wf_p25 pick the same configs? If overlap is
                              high, the 8-vs-4 gate-clearer gap is noise on a shared signal
                              rather than a distinct region worth its own lane.
  4  DISJOINT TEST WINDOWS    the merge sweep summed NESTED windows, so a config could be
                              counted up to 3x. This re-counts on non-overlapping blocks so
                              the gate-clearer totals are distinct configs.

Judge is always realised cpcv. Stage one only (D337). Snapshot only.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl

from forge.persistence.registry_loader import load_registry
from forge.ranking.dataset import build_dataset
from forge.ranking.model import _fit_irls, _sigmoid_vec

_LIVE_DB = Path.home() / "forge_data" / "forge.db"
_CPCV = "target_cpcv_p25"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SPLITS = (0.55, 0.60, 0.65, 0.70, 0.75)
_BASES = ("target_wf_p25", "target_wf_p10", _CPCV)
_NPOS = (150, 300, 750, 1500, 3000)
_FRACS = (0.005, 0.01, 0.05)
_NON_FEATURES = frozenset(
    {"crucible_run_id", "config_hash", "decided_at", "decision", "label", "coverage_verified"}
)


def _feature_cols(frame: pl.DataFrame) -> list[str]:
    return [c for c in frame.columns if c not in _NON_FEATURES and not c.startswith("target_")]


def _fit_ridge(x: np.ndarray, y: np.ndarray, lam: float = 10.0) -> np.ndarray:
    xm, xs = x.mean(0), x.std(0) + 1e-9
    xz = (x - xm) / xs
    w = np.linalg.solve(xz.T @ xz + lam * np.eye(xz.shape[1]), xz.T @ (y - y.mean()))
    return np.concatenate([[y.mean()], w / xs, [-(w / xs) @ xm]])


def _apply_ridge(x: np.ndarray, coef: np.ndarray) -> np.ndarray:
    return np.asarray(coef[0] + x @ coef[1:-1] + coef[-1], dtype=float)


def _fit_logistic(x: np.ndarray, y: np.ndarray, lam: float = 10.0) -> tuple[Any, ...]:
    xm, xs = x.mean(0), x.std(0) + 1e-9
    intercept, coefs = _fit_irls((x - xm) / xs, [int(v) for v in y], lam)
    return intercept, np.asarray(coefs, dtype=float), xm, xs


def _apply_logistic(x: np.ndarray, fit: tuple[Any, ...]) -> np.ndarray:
    intercept, coefs, xm, xs = fit
    return np.asarray(_sigmoid_vec(intercept + ((x - xm) / xs) @ coefs), dtype=float)


def _tail(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


def _arm1_distribution(cols: dict[str, np.ndarray]) -> None:
    print("\n=== ARM 1 — distribution forensics: is the wf_p10 cliff a DEGENERACY? ===")
    print(
        f"{'metric':<18} {'unique%':>9} {'max tie block':>14} "
        + "".join(f"{'q' + f'{q}':>10}" for q in (0.98, 0.99, 0.995, 0.999))
    )
    for name, v in cols.items():
        uniq = len(np.unique(v)) / len(v)
        _, counts = np.unique(v, return_counts=True)
        qs = "".join(f"{float(np.quantile(v, q)):>10.4f}" for q in (0.98, 0.99, 0.995, 0.999))
        print(f"{name:<18} {uniq:>8.2%} {int(counts.max()):>13,} " + qs)
    print("\n  a large tie block means a quantile threshold can land INSIDE it, making the")
    print("  label an arbitrary tie-break rather than a selection -- that alone makes low")
    print("  quantiles degenerate without any claim about signal quality.")


def _arm2_matched(x: np.ndarray, cols: dict[str, np.ndarray], y: np.ndarray) -> None:
    print("\n=== ARM 2 — MATCHED POSITIVE COUNTS (the decisive arm) ===")
    print("q is chosen PER METRIC so every target trains on the same number of positives.")
    print("If wf_p10 wins here, the METRIC is better. If it only wins at tiny n, it is the")
    print("EXTREMITY that helps, and wf_p10 is not special.\n")
    print(f"{'n_pos':>7} {'metric':<18} " + "".join(f"{'top ' + f'{f:.1%}':>16}" for f in _FRACS))
    for npos in _NPOS:
        for base in _BASES:
            lifts: dict[float, list[float]] = {f: [] for f in _FRACS}
            wons: dict[float, int] = {f: 0 for f in _FRACS}
            n = 0
            for s in _SPLITS:
                k = int(len(y) * s)
                yb = cols[base][:k]
                if npos >= k:
                    continue
                thresh = float(np.sort(yb)[-npos])
                lab = (yb >= thresh).astype(float)
                if lab.sum() < 30:
                    continue
                p = _apply_logistic(x[k:], _fit_logistic(x[:k], lab))
                b = _apply_ridge(x[k:], _fit_ridge(x[:k], y[:k]))
                n += 1
                for f in _FRACS:
                    a = _tail(p, y[k:], frac=f, judge=1.0)
                    bb = _tail(b, y[k:], frac=f, judge=1.0)
                    if bb > 0:
                        lifts[f].append(a / bb)
                        wons[f] += a > bb
            cells = "".join(
                f"{np.mean(lifts[f]):>10.2f}x {wons[f]}/{len(lifts[f])}"
                if lifts[f]
                else f"{'--':>16}"
                for f in _FRACS
            )
            print(f"{npos:>7,} {base:<18} " + cells)
        print()


def _arm3_overlap(x: np.ndarray, cols: dict[str, np.ndarray], y: np.ndarray) -> None:
    print("=== ARM 3 — selection OVERLAP: distinct region, or the same picks? ===")
    print(f"{'split':>6} {'jaccard(top1%)':>16} {'wf10-only >=1.0':>17} {'wf25-only >=1.0':>17}")
    for s in _SPLITS:
        k = int(len(y) * s)
        preds = {}
        for base, q in (("target_wf_p25", 0.990), ("target_wf_p10", 0.999)):
            yb = cols[base][:k]
            lab = (yb >= float(np.quantile(yb, q))).astype(float)
            preds[base] = _apply_logistic(x[k:], _fit_logistic(x[:k], lab))
        ye = y[k:]
        m = max(1, int(0.01 * len(ye)))
        a = set(np.argsort(-preds["target_wf_p10"])[:m].tolist())
        b = set(np.argsort(-preds["target_wf_p25"])[:m].tolist())
        jac = len(a & b) / len(a | b)
        a_only = [i for i in a - b]
        b_only = [i for i in b - a]
        print(
            f"{s:>6.2f} {jac:>16.3f} "
            f"{int((ye[a_only] >= 1.0).sum()) if a_only else 0:>17,} "
            f"{int((ye[b_only] >= 1.0).sum()) if b_only else 0:>17,}"
        )
    print()


def _arm4_disjoint(x: np.ndarray, cols: dict[str, np.ndarray], y: np.ndarray) -> None:
    print("=== ARM 4 — DISJOINT test windows: distinct gate-clearer counts ===")
    print("(the merge sweep summed NESTED windows, inflating counts up to 3x)")
    edges = [int(len(y) * f) for f in (0.60, 0.70, 0.80, 0.90, 1.00)]
    models = {
        "incumbent E[cpcv]": None,
        "wf_p25 q=0.990": ("target_wf_p25", 0.990),
        "wf_p25 q=0.999": ("target_wf_p25", 0.999),
        "wf_p10 q=0.999": ("target_wf_p10", 0.999),
    }
    print(f"{'model':<22} {'n_sel':>7} {'>=1.0':>7} {'>=1.25':>8} {'>=1.5':>7} {'max':>7}")
    for name, spec in models.items():
        tot = [0, 0, 0, 0, 0.0]
        for lo, hi in pairwise(edges):
            xt, yt = x[:lo], y[:lo]
            xe, ye = x[lo:hi], y[lo:hi]
            if spec is None:
                p = _apply_ridge(xe, _fit_ridge(xt, yt))
            else:
                base, q = spec
                yb = cols[base][:lo]
                lab = (yb >= float(np.quantile(yb, q))).astype(float)
                if lab.sum() < 30:
                    continue
                p = _apply_logistic(xe, _fit_logistic(xt, lab))
            top = np.argsort(-p)[: max(1, int(0.05 * len(ye)))]
            sel = ye[top]
            tot[0] += len(sel)
            tot[1] += int((sel >= 1.0).sum())
            tot[2] += int((sel >= 1.25).sum())
            tot[3] += int((sel >= 1.5).sum())
            tot[4] = max(tot[4], float(sel.max()))
        print(f"{name:<22} {tot[0]:>7,} {tot[1]:>7,} {tot[2]:>8,} {tot[3]:>7,} {tot[4]:>7.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    raw = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    con.close()
    keep = raw[_CPCV].is_not_null()
    for b in _BASES:
        keep = keep & raw[b].is_not_null()
    fr = raw.filter(keep).sort("decided_at")
    fcols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    cols = {b: np.array(fr[b].to_list(), dtype=float) for b in _BASES}
    y = cols[_CPCV]
    print(f"stage one n={len(y):,}  features={len(fcols)}")

    _arm1_distribution(cols)
    _arm2_matched(x, cols, y)
    _arm3_overlap(x, cols, y)
    _arm4_disjoint(x, cols, y)
    print("\nARM 2 decides. wf_p10 is only 'better' if it wins at MATCHED positive counts;")
    print("otherwise its edge is label extremity, available to any metric.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
