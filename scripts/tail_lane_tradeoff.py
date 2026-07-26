"""The price of the tail lane: what supply do we give up per extra tail config?

WHY THIS EXISTS. Every sweep so far measured what the tail targets BUY (`wf_p10` top-300 and
the AND-label find 2.3x the >=1.0 configs and 4-vs-0 at the gate versus the live incumbent).
None measured what they COST. We priced it once for cpcv exceedance -- component rate
22.88% -> 11.61%, roughly halved -- and never re-ran it for the wf targets, which select a
MORE extreme and probably LOWER-converting region. Recommending a lane without that number
would be handing the operator a decision with one side of the ledger missing.

Crucible's assembly consumes components; the pipeline's purpose is promotions. Trading the
first for the second is a real trade and it is the operator's to make, not the model's.

WHAT IT REPORTS
  * component rate and absolute components delivered, per model, per selection fraction
  * the tail counts alongside (>=1.0 / >=1.25 / >=1.5), same rows, same windows
  * THE EXCHANGE RATE -- components sacrificed per additional >=1.25 config, which is the
    number the lane-size decision actually turns on
  * a per-batch translation, since the ranked lane ships ~190 configs per batch and the
    question in practice is "how many of those 190 slots"

DISJOINT windows, so counts are distinct configs -- the nested windows used earlier inflated
totals up to 3x and we had to retract them. Stage one only (D337). Snapshot only.
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
_P10, _P25 = "target_wf_p10", "target_wf_p25"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_FRACS = (0.005, 0.01, 0.02, 0.05, 0.10)
_N_P10, _N_P25 = 300, 1500
_RANKED_PER_BATCH = 190  # the live ranked lane's slot count
_POSITIVE = frozenset({"component", "promote"})
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


def _topn_label(v: np.ndarray, n: int) -> np.ndarray:
    return (v >= float(np.sort(v)[-n])).astype(float)


def main() -> int:  # noqa: PLR0915
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    raw = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    con.close()
    keep = raw[_CPCV].is_not_null() & raw[_P10].is_not_null() & raw[_P25].is_not_null()
    fr = raw.filter(keep).sort("decided_at")
    fcols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    y = np.array(fr[_CPCV].to_list(), dtype=float)
    p10 = np.array(fr[_P10].to_list(), dtype=float)
    p25 = np.array(fr[_P25].to_list(), dtype=float)
    comp = np.array([d in _POSITIVE for d in fr["decision"].to_list()], dtype=bool)
    print(f"stage one n={len(y):,}  overall component rate {comp.mean():.2%}")
    print(
        f"overall tail: >=1.0 {int((y >= 1.0).sum()):,}  >=1.25 {int((y >= 1.25).sum()):,}  "
        f">=1.5 {int((y >= 1.5).sum()):,}\n"
    )

    edges = [int(len(y) * f) for f in (0.60, 0.70, 0.80, 0.90, 1.00)]

    def predict(lo: int, hi: int, model: str) -> np.ndarray:
        xt, xe = x[:lo], x[lo:hi]
        if model == "incumbent":
            return _apply_ridge(xe, _fit_ridge(xt, y[:lo]))
        if model == "wf_p10":
            return _apply_logistic(xe, _fit_logistic(xt, _topn_label(p10[:lo], _N_P10)))
        if model == "wf_p25":
            return _apply_logistic(xe, _fit_logistic(xt, _topn_label(p25[:lo], _N_P25)))
        a = _topn_label(p10[:lo], _N_P10).astype(bool)
        b = _topn_label(p25[:lo], _N_P25).astype(bool)
        return _apply_logistic(xe, _fit_logistic(xt, (a & b).astype(float)))

    models = ("incumbent", "wf_p25", "wf_p10", "AND-label")
    results: dict[tuple[str, float], dict[str, float]] = {}
    for model in models:
        for frac in _FRACS:
            tot = {"n": 0.0, "comp": 0.0, "t10": 0.0, "t125": 0.0, "t15": 0.0}
            for lo, hi in pairwise(edges):
                p = predict(lo, hi, model)
                top = np.argsort(-p)[: max(1, int(frac * (hi - lo)))]
                idx = np.arange(lo, hi)[top]
                tot["n"] += len(idx)
                tot["comp"] += float(comp[idx].sum())
                tot["t10"] += float((y[idx] >= 1.0).sum())
                tot["t125"] += float((y[idx] >= 1.25).sum())
                tot["t15"] += float((y[idx] >= 1.5).sum())
            results[(model, frac)] = tot

    print("=== THE LEDGER — both sides, disjoint windows, distinct configs ===")
    print(
        f"{'model':<12} {'frac':>6} {'n_sel':>7} {'comp':>7} {'comp rate':>10} "
        f"{'>=1.0':>7} {'>=1.25':>7} {'>=1.5':>6}"
    )
    for frac in _FRACS:
        for model in models:
            t = results[(model, frac)]
            print(
                f"{model:<12} {frac:>6.1%} {int(t['n']):>7,} {int(t['comp']):>7,} "
                f"{t['comp'] / t['n']:>10.2%} {int(t['t10']):>7,} {int(t['t125']):>7,} "
                f"{int(t['t15']):>6,}"
            )
        print()

    print("=== THE EXCHANGE RATE — components given up per EXTRA >=1.25 config ===")
    print("(vs the live incumbent at the same selection fraction; this is the number the")
    print(" lane-size decision turns on)")
    print(f"{'model':<12} {'frac':>6} {'d_comp':>9} {'d_>=1.25':>10} {'comp per extra':>16}")
    for frac in _FRACS:
        base = results[("incumbent", frac)]
        for model in models[1:]:
            t = results[(model, frac)]
            dc = t["comp"] - base["comp"]
            dt = t["t125"] - base["t125"]
            rate = f"{-dc / dt:>13.1f}" if dt > 0 else f"{'n/a':>13}"
            print(f"{model:<12} {frac:>6.1%} {int(dc):>+9,} {int(dt):>+10,} {rate}")
        print()

    print("=== PER-BATCH TRANSLATION — the ranked lane ships ~190 configs/batch ===")
    print("if a tail lane took N of those 190 slots, expected per batch:")
    print(f"{'model':<12} {'slots':>6} {'components':>12} {'>=1.0':>8} {'>=1.25':>8}")
    frac = 0.01
    for model in models:
        t = results[(model, frac)]
        cr, r10, r125 = t["comp"] / t["n"], t["t10"] / t["n"], t["t125"] / t["n"]
        for slots in (19, 47, 190):
            tag = model if slots == 19 else ""
            print(
                f"{tag:<12} {slots:>6} {cr * slots:>12.1f} {r10 * slots:>8.2f} {r125 * slots:>8.3f}"
            )
        print()
    print("read the rows as: at this per-slot rate, a lane of N slots yields this much.")
    print("the incumbent rows are what those slots produce TODAY -- the difference is the trade.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
