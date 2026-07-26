"""EXTREME sweep: is `P(cpcv >= 1.0)` really the right target, or did we get lucky?

The narrow sweep (`exceedance_target_sweep.py`) found ordering by `P(cpcv >= 1.0)` beats
ordering by `E[cpcv]` at 1.48x on top-decile tail rate, 4/4 temporal splits. That answered
ONE question at ONE operating point with ONE estimator. This answers whether the choice
survives contact with every axis it was implicitly conditioned on.

THE OVERFITTING HAZARD THIS SCRIPT EXISTS TO CONTROL. Sweeping 8 thresholds x 5 selection
fractions x 3 judge metrics x 3 regularisations is ~360 comparisons; at that width something
always looks excellent by chance. Two guards, both mandatory:

  * ARM D is the load-bearing one -- NESTED selection. Pick tau on the EARLY splits and
    evaluate it on LATE splits it never saw. A tau chosen by looking at all splits is
    chosen with hindsight, and that is precisely how the tau=1.25 variant nearly shipped
    (raw 1.22x, but 1/4 splits, and best-in-show on the single 0.8 split).
  * Nothing is called a winner on a single cell. Every arm reports SPLITS WON alongside the
    mean, because the `n_signals` withdrawal turned on exactly that distinction.

ARMS
  A  tau x judge-threshold      does the winner depend on which tail we score?
  B  selection fraction         top-10% is not the production operating point; the ranked
                                lane keeps ~190 of ~3,188 prefilter survivors (~6%), and a
                                target tuned at 10% may invert at 1%.
  C  estimator + lambda         is the win a property of the TARGET or of the logistic fit?
                                Includes a linear-probability control (ridge on the same
                                binary label), which isolates target-vs-estimator.
  D  NESTED tau selection       the honest test. Choose on early, evaluate on late.
  E  base metric                is cpcv_sharpe_p25 even the right underlying quantity? The
                                same exceedance trick is applied to every target column, so
                                a better tail substrate would surface here.

STAGE ONE only (D337): stage-two admission is the refit TRIGGER, a collider.
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
from forge.ranking.dataset import TARGET_COLUMNS, build_dataset
from forge.ranking.model import _fit_irls, _sigmoid_vec

_LIVE_DB = Path.home() / "forge_data" / "forge.db"
_TARGET = "target_cpcv_p25"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SPLITS = (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8)
_EARLY = (0.45, 0.5, 0.55, 0.6)
_LATE = (0.65, 0.7, 0.75, 0.8)
_TAUS = (0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5)
_JUDGE = (0.75, 1.0, 1.25)
_FRACS = (0.01, 0.02, 0.05, 0.10, 0.20)
_LAMBDAS = (1.0, 10.0, 100.0)
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


def _tail_rate(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


class Fold:
    """One temporal split, with the design matrices materialised once."""

    def __init__(self, x: np.ndarray, y: np.ndarray, frac: float) -> None:
        k = int(len(y) * frac)
        self.xt, self.yt, self.xe, self.ye = x[:k], y[:k], x[k:], y[k:]
        self.frac = frac
        self._cache: dict[tuple[Any, ...], np.ndarray] = {}

    def pred(self, tau: float | None, lam: float, kind: str) -> np.ndarray | None:
        """`tau=None` is the incumbent E[y] ridge; otherwise an exceedance model."""
        key = (tau, lam, kind)
        if key in self._cache:
            return self._cache[key]
        if tau is None:
            out = _apply_ridge(self.xe, _fit_ridge(self.xt, self.yt, lam))
        else:
            lab = (self.yt >= tau).astype(float)
            if lab.sum() < _MIN_POS or lab.sum() == len(lab):
                return None
            out = (
                _apply_ridge(self.xe, _fit_ridge(self.xt, lab, lam))
                if kind == "ridge"
                else _apply_logistic(self.xe, _fit_logistic(self.xt, lab, lam))
            )
        self._cache[key] = out
        return out


def _summary(
    folds: dict[float, Fold], tau: float | None, *, frac: float, judge: float, lam: float, kind: str
) -> tuple[float, int, int]:
    """(mean tail rate, splits beaten vs incumbent, n splits evaluated)."""
    vals, won, n = [], 0, 0
    for f in folds.values():
        p = f.pred(tau, lam, kind)
        if p is None:
            continue
        incumbent = f.pred(None, lam, "ridge")
        if incumbent is None:  # unreachable: tau=None always fits
            continue
        v = _tail_rate(p, f.ye, frac=frac, judge=judge)
        base = _tail_rate(incumbent, f.ye, frac=frac, judge=judge)
        vals.append(v)
        won += v > base
        n += 1
    return (float(np.mean(vals)) if vals else float("nan")), won, n


def _rel(folds: dict[float, Fold], tau: float | None, **kw: Any) -> float:
    m, _, _ = _summary(folds, tau, **kw)
    b, _, _ = _summary(folds, None, **kw)
    return m / b if b > 0 else float("nan")


def _arm_a(folds: dict[float, Fold]) -> None:
    print("\n=== ARM A — tau x judge threshold (top 10%) : relative lift, splits won ===")
    print(f"{'tau':>6} " + "".join(f"{'judge>=' + str(j):>22}" for j in _JUDGE))
    for tau in _TAUS:
        cells = []
        for j in _JUDGE:
            m, w, n = _summary(folds, tau, frac=0.10, judge=j, lam=10.0, kind="logistic")
            if n == 0:
                cells.append(f"{'(too few pos)':>22}")
                continue
            b, _, _ = _summary(folds, None, frac=0.10, judge=j, lam=10.0, kind="ridge")
            cells.append(f"{m / b:>16.2f}x {w}/{n}")
        print(f"{tau:>6.2f} " + "".join(cells))


def _arm_b(folds: dict[float, Fold]) -> None:
    print("\n=== ARM B — selection fraction (judge >=1.0) : does the winner hold at 1%? ===")
    print(f"{'tau':>6} " + "".join(f"{'top ' + f'{f:.0%}':>18}" for f in _FRACS))
    for tau in _TAUS:
        cells = []
        for f in _FRACS:
            m, w, n = _summary(folds, tau, frac=f, judge=1.0, lam=10.0, kind="logistic")
            if n == 0:
                cells.append(f"{'--':>18}")
                continue
            b, _, _ = _summary(folds, None, frac=f, judge=1.0, lam=10.0, kind="ridge")
            cells.append(f"{m / b:>12.2f}x {w}/{n}")
        print(f"{tau:>6.2f} " + "".join(cells))


def _arm_c(folds: dict[float, Fold]) -> None:
    print("\n=== ARM C — estimator and regularisation (top 10%, judge >=1.0) ===")
    print("(ridge-on-binary is the control: same TARGET, different estimator)")
    hdr = "".join(f"{k + ' L=' + str(int(lam)):>17}" for k in ("logi", "ridge") for lam in _LAMBDAS)
    print(f"{'tau':>6} " + hdr)
    for tau in _TAUS:
        cells = []
        for kind in ("logistic", "ridge"):
            for lam in _LAMBDAS:
                m, w, n = _summary(folds, tau, frac=0.10, judge=1.0, lam=lam, kind=kind)
                if n == 0:
                    cells.append(f"{'--':>17}")
                    continue
                b, _, _ = _summary(folds, None, frac=0.10, judge=1.0, lam=lam, kind="ridge")
                cells.append(f"{m / b:>11.2f}x {w}/{n}")
        print(f"{tau:>6.2f} " + "".join(cells))


def _arm_d(folds: dict[float, Fold]) -> None:
    print("\n=== ARM D — NESTED tau selection (the honest test) ===")
    print("choose tau on EARLY splits only, then evaluate it on LATE splits it never saw")
    early = {f: folds[f] for f in _EARLY}
    late = {f: folds[f] for f in _LATE}
    scored = []
    for tau in _TAUS:
        m, w, n = _summary(early, tau, frac=0.10, judge=1.0, lam=10.0, kind="logistic")
        if n:
            scored.append((m, tau))
    if not scored:
        print("  no tau had enough positives on the early splits")
    else:
        best = max(scored)[1]
        eb, _, _ = _summary(early, None, frac=0.10, judge=1.0, lam=10.0, kind="ridge")
        print(f"  tau chosen on EARLY = {best}  (early lift {max(scored)[0] / eb:.2f}x)")
        m, w, n = _summary(late, best, frac=0.10, judge=1.0, lam=10.0, kind="logistic")
        b, _, _ = _summary(late, None, frac=0.10, judge=1.0, lam=10.0, kind="ridge")
        print(f"  evaluated on LATE   = {m / b:.2f}x lift, winning {w}/{n} unseen splits")
        print(f"  {'tau':>6} {'early lift':>12} {'late lift':>12} {'late won':>10}")
        for _, tau in sorted(scored, key=lambda s: s[1]):
            em, _, _ = _summary(early, tau, frac=0.10, judge=1.0, lam=10.0, kind="logistic")
            lm, lw, ln = _summary(late, tau, frac=0.10, judge=1.0, lam=10.0, kind="logistic")
            star = "  <- chosen" if tau == best else ""
            print(f"  {tau:>6.2f} {em / eb:>11.2f}x {lm / b:>11.2f}x {f'{lw}/{ln}':>10}{star}")


def _arm_e(raw: pl.DataFrame, cols: list[str], ycpcv: np.ndarray) -> None:
    print("\n=== ARM E — is cpcv_sharpe_p25 the right BASE metric? ===")
    print("same exceedance trick on every target column; judge is always realised cpcv >=1.0")
    print(f"{'base target':<22} {'n':>8} {'tau':>6} {'lift':>8} {'won':>7}")
    for tgt in TARGET_COLUMNS:
        sub = raw.filter(raw[tgt].is_not_null() & raw[_TARGET].is_not_null()).sort("decided_at")
        if sub.height < 20_000:
            print(f"{tgt:<22} {sub.height:>8,} {'--':>6} {'(thin)':>8}")
            continue
        xs = np.array([[float(r[c]) for c in cols] for r in sub.iter_rows(named=True)])
        yb = np.array(sub[tgt].to_list(), dtype=float)
        yj = np.array(sub[_TARGET].to_list(), dtype=float)
        # tau = the base metric's own quantile matching cpcv's P(>=1.0) prevalence
        prev = float((ycpcv >= 1.0).mean())
        tau_b = float(np.quantile(yb, 1.0 - prev))
        lifts, wons, ns = [], 0, 0
        for frac_split in _LATE:
            k = int(len(yj) * frac_split)
            lab = (yb[:k] >= tau_b).astype(float)
            if lab.sum() < _MIN_POS:
                continue
            p = _apply_logistic(xs[k:], _fit_logistic(xs[:k], lab))
            # Incumbent baseline is always the same thing: ridge on E[cpcv].
            base = _apply_ridge(xs[k:], _fit_ridge(xs[:k], yj[:k]))
            a = _tail_rate(p, yj[k:], frac=0.10, judge=1.0)
            b = _tail_rate(base, yj[k:], frac=0.10, judge=1.0)
            if b > 0:
                lifts.append(a / b)
                wons += a > b
                ns += 1
        if lifts:
            print(
                f"{tgt:<22} {sub.height:>8,} {tau_b:>6.3f} "
                f"{np.mean(lifts):>7.2f}x {f'{wons}/{ns}':>7}"
            )
        else:
            print(f"{tgt:<22} {sub.height:>8,} {tau_b:>6.3f} {'(no fit)':>8}")


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
    fr = raw.filter(raw[_TARGET].is_not_null()).sort("decided_at")
    cols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in cols] for r in fr.iter_rows(named=True)])
    y = np.array(fr[_TARGET].to_list(), dtype=float)
    folds = {f: Fold(x, y, f) for f in _SPLITS}
    print(f"stage one n={len(y):,}  features={len(cols)}  splits={len(_SPLITS)}")
    for j in _JUDGE:
        print(f"  base rate P(>={j}) = {float((y >= j).mean()):.4%}  (n={int((y >= j).sum()):,})")

    _arm_a(folds)
    _arm_b(folds)
    _arm_c(folds)
    _arm_d(folds)
    _arm_e(raw, cols, y)
    print("\nARM D is the one that decides. A tau that wins everywhere except unseen")
    print("late splits was chosen with hindsight, which is how tau=1.25 nearly shipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
