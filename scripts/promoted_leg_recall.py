"""Does the tail target rank PROMOTED BOOK LEGS above what the incumbent does?

THE OPERATOR'S FRAMING (2026-07-26), and it is the right reference class: the only books
worth calibrating against are the PROMOTED ones, because they cleared all 13 gates. A
rejected assembly is not a counter-example to a supply strategy — Crucible's own
`selection_pbo = 0.7778` rejection of a 5-leg MR family reflects their SEARCH breadth
(44,643 candidates deflating to n_trials = 49), not our components, and the promoted books
cleared that same gate at 0.2738.

So the question is not "does the lane avoid families that failed". It is:

    DOES THE LANE RANK HIGHLY THE COMPONENTS THAT ACTUALLY REACHED A PROMOTED BOOK?

That is a recall test against the only positive examples that exist. It is a small sample —
the promoted set is a handful of legs — so it CANNOT establish a rate and is not a
substitute for the prereg's live arm split. What it can do is falsify: a target that ranks
the known winners no better than the incumbent is not pointed at book-grade components,
however good its aggregate tail statistics look.

Every model is fit on data STRICTLY BEFORE each leg's decision, so a leg is never used to
predict itself.

Stage one only (D337). Snapshot only, never the live RW-locked DB.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import UTC, datetime
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
_SB = "target_sharpe_baseline"
_P10 = "target_wf_p10"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_MIN_POS = 30
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


def _topn(v: np.ndarray, n: int) -> np.ndarray:
    return (v >= float(np.sort(v)[-n])).astype(float)


def _promoted_run_ids() -> dict[str, str]:
    """component_run_id -> strategy name, from Crucible's promoted_portfolios export."""
    paths = glob.glob(os.path.expanduser("~/optbt_data/exports/promoted_portfolios_*.json"))
    if not paths:
        return {}
    payload = json.loads(Path(max(paths, key=os.path.getmtime)).read_text())
    out: dict[str, str] = {}
    for book in payload.get("promoted_portfolios", []):
        for comp in book.get("components", []):
            rid = comp.get("component_run_id")
            if rid:
                out[str(rid)] = str(comp.get("strategy_config", {}).get("name", "?"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    legs = _promoted_run_ids()
    if not legs:
        print("no promoted_portfolios export found", file=sys.stderr)
        return 2
    print(f"promoted book legs in the export: {len(legs)}")

    con = duckdb.connect(str(args.db), read_only=True)
    raw = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    con.close()
    keep = raw[_CPCV].is_not_null() & raw[_SB].is_not_null() & raw[_P10].is_not_null()
    fr = raw.filter(keep).sort("decided_at")
    fcols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    cols = {m: np.array(fr[m].to_list(), dtype=float) for m in (_CPCV, _SB, _P10)}
    run_ids = [str(r) for r in fr["crucible_run_id"].to_list()]
    idx_of = {r: i for i, r in enumerate(run_ids)}

    present = {r: n for r, n in legs.items() if r in idx_of}
    print(f"of those, present in our stage-one frame: {len(present)}")
    if not present:
        print("none of the promoted legs are in our frame — cannot run the recall test")
        return 0

    print("\n=== PERCENTILE RANK OF EACH PROMOTED LEG (100 = top of the batch it competed in) ===")
    print("each model is fit ONLY on rows decided strictly before that leg — no self-prediction")
    print(f"\n{'leg':<10} {'cpcv':>7} {'incumbent':>11} {'sharpe_b':>10} {'wf_p10':>9}  name")
    rows: list[tuple[float, float, float]] = []
    for rid, name in sorted(present.items(), key=lambda kv: idx_of[kv[0]]):
        i = idx_of[rid]
        if i < 20_000:  # need a usable training window before the leg
            print(f"{rid[:8]:<10} {'(too early — no prior window)':>40}  {name[:34]}")
            continue
        xt = x[:i]
        scores: dict[str, np.ndarray] = {
            "incumbent": _apply_ridge(x, _fit_ridge(xt, cols[_CPCV][:i])),
        }
        for tag, metric, n in (("sharpe_b", _SB, 800), ("wf_p10", _P10, 200)):
            lab = _topn(cols[metric][:i], n)
            if lab.sum() >= _MIN_POS:
                scores[tag] = _apply_logistic(x, _fit_logistic(xt, lab))
        # percentile among the contemporaneous pool the leg competed against
        lo = max(0, i - 5_000)
        pct = {}
        for tag, sc in scores.items():
            pool = sc[lo : i + 1]
            pct[tag] = 100.0 * float((pool < sc[i]).mean())
        rows.append((pct.get("incumbent", 0.0), pct.get("sharpe_b", 0.0), pct.get("wf_p10", 0.0)))
        print(
            f"{rid[:8]:<10} {cols[_CPCV][i]:>7.4f} {pct.get('incumbent', float('nan')):>10.1f}% "
            f"{pct.get('sharpe_b', float('nan')):>9.1f}% {pct.get('wf_p10', float('nan')):>8.1f}%"
            f"  {name[:34]}"
        )

    if rows:
        arr = np.array(rows)
        print(f"\n{'':<10} {'incumbent':>11} {'sharpe_b':>10} {'wf_p10':>9}")
        print(
            f"{'mean':<10} {arr[:, 0].mean():>10.1f}% {arr[:, 1].mean():>9.1f}% "
            f"{arr[:, 2].mean():>8.1f}%"
        )
        print(
            f"{'median':<10} {np.median(arr[:, 0]):>10.1f}% {np.median(arr[:, 1]):>9.1f}% "
            f"{np.median(arr[:, 2]):>8.1f}%"
        )
        for tag, col in (("sharpe_b", 1), ("wf_p10", 2)):
            wins = int((arr[:, col] > arr[:, 0]).sum())
            print(f"  {tag} ranks the leg above the incumbent on {wins}/{len(arr)} legs")
    print("\nSMALL SAMPLE BY CONSTRUCTION — this can falsify a target, not establish a rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
