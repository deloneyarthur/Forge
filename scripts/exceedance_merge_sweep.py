"""Full parameter sweep of the two wf exceedance targets, plus MERGES with cpcv.

CONTEXT. The extreme sweep (`exceedance_extreme_sweep.py`) found that ordering by
`P(wf_sharpe_p25 >= q)` predicts the realised cpcv tail better than the incumbent
`E[cpcv_p25]` ridge -- 8/8 splits in all 12 grid cells, early lift 2.11/2.31/2.92 matching
late lift 2.14/2.24/2.83 with no drift. `wf_p10` peaked higher (10.88x at top 1%) but swung
0.58x -> 3.83x across quantiles, and ARM D of that sweep proved the quantile knob is
time-unstable and cannot be auto-tuned. So the champion was picked for FLATNESS, not peak.

This script asks the two questions that decision left open:

  1. FULL PARAMETER SWEEP of both wf targets -- finer quantile grid, every selection
     fraction, both estimators, three regularisations, two judge thresholds. If wf_p25's
     flatness is real it should survive all of it; if wf_p10's fragility is real it should
     keep showing up as split-instability rather than a lower mean.

  2. MERGE. cpcv and wf measure different things (D336: wf is a poor MEAN predictor;
     this line of work: wf is a strong TAIL predictor), so a combination may beat either.
     Four merge forms, because the right one is not obvious a priori:
        rank-blend    w * rank(wf) + (1-w) * rank(cpcv), w swept -- scale-free, robust
        product       P(wf) * P(cpcv)                  -- the two-part/hurdle form
        joint label   fit ONE model on (wf exceeds AND cpcv exceeds)
        gate-then-rank  screen on wf exceedance, order within by cpcv  -- the live
                        gate-tail shape, so it is the cheapest thing to actually ship

GUARDS, both mandatory and both earned the hard way this week:
  * NESTED selection -- choose on early splits, evaluate on late. A blend weight chosen by
    looking at all splits is chosen with hindsight.
  * SPLITS WON beside every mean. The `n_signals` one-hot had a 100%-confident bootstrap on
    one split and flipped sign on two of four.

Judge is always REALISED cpcv, because that is the gate. Stage one only (D337).
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
_CPCV = "target_cpcv_p25"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SPLITS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)
_EARLY, _LATE = _SPLITS[:3], _SPLITS[3:]
_QS = (0.980, 0.985, 0.990, 0.995, 0.999)
_FRACS = (0.005, 0.01, 0.02, 0.05, 0.10)
_LAMBDAS = (1.0, 10.0, 100.0)
_WEIGHTS = (0.0, 0.25, 0.50, 0.75, 1.0)
_BASES = ("target_wf_p25", "target_wf_p10", _CPCV)
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


def _rank01(a: np.ndarray) -> np.ndarray:
    """Ranks scaled to [0,1] -- makes two differently-scaled scores blendable."""
    r = np.argsort(np.argsort(a, kind="stable")).astype(float)
    return r / max(1.0, len(a) - 1.0)


def _tail(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


class Book:
    """Every fit this sweep needs, computed once per (base, q, split, lam, kind)."""

    def __init__(self, x: np.ndarray, cols: dict[str, np.ndarray], judge_y: np.ndarray) -> None:
        self.x, self.cols, self.y = x, cols, judge_y
        self._p: dict[tuple[Any, ...], np.ndarray | None] = {}
        self._b: dict[tuple[float, float], np.ndarray] = {}

    def k(self, split: float) -> int:
        return int(len(self.y) * split)

    def incumbent(self, split: float, lam: float = 10.0) -> np.ndarray:
        key = (split, lam)
        if key not in self._b:
            k = self.k(split)
            self._b[key] = _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], self.y[:k], lam))
        return self._b[key]

    def exceed(
        self, base: str, q: float, split: float, lam: float = 10.0, kind: str = "logistic"
    ) -> np.ndarray | None:
        key = (base, q, split, lam, kind)
        if key in self._p:
            return self._p[key]
        k = self.k(split)
        yb = self.cols[base][:k]
        lab = (yb >= float(np.quantile(yb, q))).astype(float)
        if lab.sum() < _MIN_POS or lab.sum() == len(lab):
            self._p[key] = None
        elif kind == "ridge":
            self._p[key] = _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], lab, lam))
        else:
            self._p[key] = _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab, lam))
        return self._p[key]

    def joint(self, base: str, q: float, split: float, tau_cpcv: float = 1.0) -> np.ndarray | None:
        """One model on 'exceeds on BOTH axes' -- a different label, not a blend."""
        key = ("JOINT", base, q, split, tau_cpcv)
        if key in self._p:
            return self._p[key]
        k = self.k(split)
        yb, yc = self.cols[base][:k], self.y[:k]
        lab = ((yb >= float(np.quantile(yb, q))) & (yc >= tau_cpcv)).astype(float)
        self._p[key] = (
            None
            if lab.sum() < _MIN_POS
            else _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab))
        )
        return self._p[key]


def _score(
    book: Book, splits: tuple[float, ...], make: Any, *, frac: float, judge: float
) -> tuple[float, int, int]:
    lifts, won, n = [], 0, 0
    for s in splits:
        p = make(s)
        if p is None:
            continue
        k = book.k(s)
        a = _tail(p, book.y[k:], frac=frac, judge=judge)
        b = _tail(book.incumbent(s), book.y[k:], frac=frac, judge=judge)
        if b > 0:
            lifts.append(a / b)
            won += a > b
            n += 1
    return (float(np.mean(lifts)) if lifts else float("nan")), won, n


def _cell(m: float, w: int, n: int, width: int = 16) -> str:
    return f"{'--':>{width}}" if n == 0 or np.isnan(m) else f"{m:>{width - 6}.2f}x {w}/{n}"


def _arm_quantile(book: Book) -> None:
    print("\n=== ARM 1 — quantile x selection fraction, both wf targets + cpcv (6 splits) ===")
    print(f"{'base':<16} {'q':>7} " + "".join(f"{'top ' + f'{f:.1%}':>16}" for f in _FRACS))
    for base in _BASES:
        for q in _QS:
            cells = [
                _cell(
                    *_score(
                        book,
                        _SPLITS,
                        lambda s, b=base, q=q: book.exceed(b, q, s),
                        frac=f,
                        judge=1.0,
                    )
                )
                for f in _FRACS
            ]
            print(f"{base:<16} {q:>7.3f} " + "".join(cells))
        print()


def _arm_estimator(book: Book) -> None:
    print("=== ARM 2 — estimator x lambda (top 1%, judge >=1.0) ===")
    hdr = "".join(f"{k + ' L=' + str(int(lam)):>17}" for k in ("logi", "ridge") for lam in _LAMBDAS)
    print(f"{'base':<16} {'q':>7} " + hdr)
    for base in ("target_wf_p25", "target_wf_p10"):
        for q in (0.990, 0.999):
            cells = []
            for kind in ("logistic", "ridge"):
                for lam in _LAMBDAS:
                    cells.append(
                        _cell(
                            *_score(
                                book,
                                _SPLITS,
                                lambda s, b=base, q=q, la=lam, ki=kind: book.exceed(
                                    b, q, s, la, ki
                                ),
                                frac=0.01,
                                judge=1.0,
                            ),
                            width=17,
                        )
                    )
            print(f"{base:<16} {q:>7.3f} " + "".join(cells))
    print()


def _arm_judge(book: Book) -> None:
    print("=== ARM 3 — the harder tail: judge >=1.25 (top 1% and 5%) ===")
    print("(>=1.5 is the gate but only ~22 rows ever exist; 1.25 is the reachable proxy)")
    print(f"{'base':<16} {'q':>7} {'top1% j>=1.0':>16} {'top1% j>=1.25':>16} {'top5% j>=1.25':>16}")
    for base in _BASES:
        for q in (0.990, 0.999):
            row = [
                _cell(
                    *_score(
                        book, _SPLITS, lambda s, b=base, q=q: book.exceed(b, q, s), frac=fr, judge=j
                    )
                )
                for fr, j in ((0.01, 1.0), (0.01, 1.25), (0.05, 1.25))
            ]
            print(f"{base:<16} {q:>7.3f} " + "".join(row))
    print()


def _arm_merge(book: Book) -> None:
    print("=== ARM 4 — MERGE: cpcv + the wf champion (top 1%, judge >=1.0) ===")
    print("rank-blend w: 0.0 = pure cpcv exceedance, 1.0 = pure wf exceedance\n")
    champ, qc, qw = "target_wf_p25", 0.990, 0.990

    def blend(s: float, w: float) -> np.ndarray | None:
        a, b = book.exceed(champ, qw, s), book.exceed(_CPCV, qc, s)
        if a is None or b is None:
            return None
        return w * _rank01(a) + (1.0 - w) * _rank01(b)

    print(f"{'form':<34} " + "".join(f"{'top ' + f'{f:.1%}':>16}" for f in _FRACS))
    for w in _WEIGHTS:
        cells = [
            _cell(*_score(book, _SPLITS, lambda s, w=w: blend(s, w), frac=f, judge=1.0))
            for f in _FRACS
        ]
        print(f"{'rank-blend w=' + f'{w:.2f}':<34} " + "".join(cells))

    def product(s: float) -> np.ndarray | None:
        a, b = book.exceed(champ, qw, s), book.exceed(_CPCV, qc, s)
        return None if a is None or b is None else a * b

    def gate_then_rank(s: float) -> np.ndarray | None:
        """Live gate-tail shape: wf exceedance screens, cpcv orders inside the screen."""
        a, b = book.exceed(champ, qw, s), book.exceed(_CPCV, qc, s)
        if a is None or b is None:
            return None
        keep = _rank01(a) >= 0.90
        return np.where(keep, 1.0 + _rank01(b), _rank01(b) * 0.5)

    for name, fn in (
        ("product  P(wf) x P(cpcv)", product),
        ("joint label (both exceed)", lambda s: book.joint(champ, qw, s)),
        ("gate-then-rank (wf gates, cpcv orders)", gate_then_rank),
    ):
        cells = [_cell(*_score(book, _SPLITS, fn, frac=f, judge=1.0)) for f in _FRACS]
        print(f"{name:<34} " + "".join(cells))
    print()

    print("=== ARM 5 — NESTED merge selection: choose w on EARLY, evaluate on LATE (top 1%) ===")
    scored = []
    for w in _WEIGHTS:
        m, _, n = _score(book, _EARLY, lambda s, w=w: blend(s, w), frac=0.01, judge=1.0)
        if n:
            scored.append((m, w))
    if not scored:
        print("  no blend weight fit on the early splits")
        return
    best = max(scored)[1]
    print(f"  w chosen on EARLY = {best:.2f}  (early lift {max(scored)[0]:.2f}x)")
    lm, lw, ln = _score(book, _LATE, lambda s: blend(s, best), frac=0.01, judge=1.0)
    print(f"  evaluated on LATE = {lm:.2f}x, winning {lw}/{ln} unseen splits\n")
    print(f"  {'w':>6} {'early':>9} {'late':>9} {'late won':>10}")
    for _, w in sorted(scored, key=lambda t: t[1]):
        em, _, _ = _score(book, _EARLY, lambda s, w=w: blend(s, w), frac=0.01, judge=1.0)
        lm2, lw2, ln2 = _score(book, _LATE, lambda s, w=w: blend(s, w), frac=0.01, judge=1.0)
        star = "  <- chosen" if w == best else ""
        print(f"  {w:>6.2f} {em:>8.2f}x {lm2:>8.2f}x {f'{lw2}/{ln2}':>10}{star}")


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
    print(f"stage one n={len(y):,}  features={len(fcols)}  splits={len(_SPLITS)}")
    print(
        f"judge = realised cpcv; base P(>=1.0)={float((y >= 1.0).mean()):.4%} "
        f"P(>=1.25)={float((y >= 1.25).mean()):.4%}"
    )

    book = Book(x, cols, y)
    _arm_quantile(book)
    _arm_estimator(book)
    _arm_judge(book)
    _arm_merge(book)
    print("\nARM 5 decides the merge. A weight that wins on splits it was chosen from")
    print("proves nothing -- only the unseen late splits do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
