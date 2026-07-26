"""Does ordering by P(cpcv >= tau) beat ordering by E[cpcv] on the TAIL?

WHY. Promotion is a tail event -- 4 promotions in ~428k verdicts -- but every learned
component we run is average-shaped: F3 predicts P(component), the quality lane orders by
E[cpcv_p25], the feedback weights are Beta posteriors over RATES. The winner prior made the
cost explicit when it lifted q25 by +0.013 and cut q99 by -0.032 (D338): fitting a
conditional mean pulls toward the mode, which is exactly wrong when only the tail pays.

And the two moments are orthogonal in our data. On stage-one cells with n>=300:

    spearman(cell MEAN, cell STD)      = -0.148     mean says nothing about spread
    spearman(cell P(>=1.0), cell STD)  = +0.500     variance IS the tail driver

Measured consequence in production: the ranker's two heaviest bets are
`trend/rolling_sharpe/swing_mid` at 14.80x selection preference (P(>=1.0) = 0.37%) and
`trend/donchian/swing_mid` at 12.53x (0.61%) -- both BELOW average tail rate -- while
`trend/sma_slope/swing_long`, the highest-mean cell we have (0.253) at a 0.82% tail rate,
is starved at 0.05x. That is not a broken ranker; it is a ranker correctly optimising
CONVERSION, which Crucible warned is not a quality ordering.

WHAT THIS MEASURES. Same swap as the Q59 rank_k fix: change what the model is ASKED, not
the pipeline. Rank by predicted exceedance instead of predicted mean, and judge on the
REALISED tail rate of the selected top decile -- not IC, not median, because those are the
statistics that got us here.

DISCIPLINE, every piece of it earned this week:
  * STAGE ONE only (D337) -- stage-two admission is a collider.
  * MULTI-SPLIT, not one split -- a paired bootstrap on a single split said P(>0)=100% for
    the `n_signals` one-hot, which then flipped sign on 2 of 4 splits and was withdrawn.
  * Report the THROUGHPUT cost alongside. swing_long converts worse (Crucible: 42.5 vs 54.6
    components per 1k), so a tail-shaped objective may trade supply for tail rate. That
    tradeoff is the operator's to price; this script's job is to price it honestly.

Prereg `4ad0ccf642d5`, registered before this file existed.
Read-only against a SNAPSHOT, never the live RW-locked DB.
"""

from __future__ import annotations

import argparse
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
_TARGET = "target_cpcv_p25"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_TOP_FRAC = 0.10
_SPLITS = (0.5, 0.6, 0.7, 0.8)
# Exceedance thresholds. 1.5 is the promotion gate but yields only ~22 rows ever, far too
# few to fit; 1.0 and 1.25 are the reachable proxies with n=2,143 and n=256.
_TAUS = (0.75, 1.0, 1.25)
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


def _judge(pred: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Top-decile REALISED tail rates. The decision metric, not IC."""
    top = np.argsort(-pred)[: max(1, int(_TOP_FRAC * len(pred)))]
    sel = y[top]
    return {
        "p_ge_1.0": float((sel >= 1.0).mean()),
        "p_ge_1.25": float((sel >= 1.25).mean()),
        "median": float(np.median(sel)),
        "max": float(sel.max()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True, help="snapshot path, NOT the live DB")
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    fr = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    con.close()
    fr = fr.filter(fr[_TARGET].is_not_null()).sort("decided_at")
    cols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in cols] for r in fr.iter_rows(named=True)])
    y = np.array(fr[_TARGET].to_list(), dtype=float)
    print(f"stage one n={len(y):,}  features={len(cols)}")
    r1, r2 = float((y >= 1.0).mean()), float((y >= 1.25).mean())
    print(f"base rates: P(>=1.0)={r1:.4%}  P(>=1.25)={r2:.4%}\n")

    print("=== TOP-DECILE REALISED TAIL RATE, by ordering target and split ===")
    print("(the decision metric: what fraction of what we SELECT actually reaches the tail)")
    print(
        f"{'target':<26} {'split':>6} {'n_top':>7} {'P(>=1.0)':>10} "
        f"{'P(>=1.25)':>11} {'median':>8} {'max':>7}"
    )
    wins: dict[str, list[float]] = {}
    for frac in _SPLITS:
        k = int(len(y) * frac)
        xt, yt, xe, ye = x[:k], y[:k], x[k:], y[k:]
        variants: dict[str, np.ndarray] = {
            "E[cpcv]  (incumbent)": _apply_ridge(xe, _fit_ridge(xt, yt)),
        }
        for tau in _TAUS:
            lab = (yt >= tau).astype(float)
            if lab.sum() < 30 or lab.sum() == len(lab):
                continue
            variants[f"P(cpcv >= {tau})"] = _apply_logistic(xe, _fit_logistic(xt, lab))
        for name, pred in variants.items():
            m = _judge(pred, ye)
            wins.setdefault(name, []).append(m["p_ge_1.0"])
            print(
                f"{name:<26} {frac:>6.1f} {int(_TOP_FRAC * len(ye)):>7,} "
                f"{m['p_ge_1.0']:>10.4%} {m['p_ge_1.25']:>11.4%} "
                f"{m['median']:>8.4f} {m['max']:>7.3f}"
            )
        print()

    print("=== ACROSS-SPLIT SUMMARY (the n_signals lesson: one split is not a result) ===")
    base = wins.get("E[cpcv]  (incumbent)", [])
    print(f"{'target':<26} {'mean P(>=1.0)':>14} {'vs incumbent':>14} {'splits won':>11}")
    for name, vals in wins.items():
        rel = np.mean(vals) / np.mean(base) if base and np.mean(base) > 0 else float("nan")
        won = sum(1 for a, b in zip(vals, base, strict=False) if a > b)
        print(f"{name:<26} {np.mean(vals):>14.4%} {rel:>13.2f}x {won:>7}/{len(base)}")
    print("\nprereg 4ad0ccf642d5 predicts >= 1.20x on top-decile P(>=1.0), majority of splits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
