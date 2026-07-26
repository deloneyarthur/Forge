"""Blend `wf_p10` + `wf_p25` at MATCHED positive counts. Do two complementary tail
signals beat either alone?

WHY THIS PAIR, AFTER REFUTING THE OTHER ONE. The cpcv+wf merge was refuted: the rank-blend
was monotone in w, so every gram of cpcv weight strictly hurt (`exceedance_merge_sweep.py`).
This pair is different in the way that matters:

  * BOTH ARE STRONG. At matched positive counts, `wf_p10` runs 27-29x and `wf_p25` 19-21x at
    top 0.5%, against cpcv's 7-8x. The refuted merge was strong+weak; this is strong+strong.
  * THEY DISAGREE. Jaccard on top-1% picks is only 0.168-0.298, and each surfaces >=1.0
    configs the other misses (`wf_p10`-only 19/27/64/69/54, `wf_p25`-only 17/14/19/23/20).
    Low overlap plus two real signals is the setup where a union normally wins.

LABELS ARE PINNED BY POSITIVE COUNT, NOT QUANTILE. `wf_p10` has a mass point at zero
(q0.98 = 0.0000, 1,641-row tie block: ~98% of configs have a non-positive worst-decile
walk-forward window), so a quantile threshold can land inside the ties and turn the label
into an arbitrary tie-break -- that was the entire 7x cliff between q=0.990 and q=0.995.
"Top N by the metric" cannot land in the mass, and it also sidesteps the quantile
time-instability that made auto-tuning unsafe (ARM D, `exceedance_extreme_sweep.py`).

Each metric is ALSO tested at its OWN optimum, not just at matched n: `wf_p10` degrades hard
past ~750 positives while `wf_p25` is flat from 150 to 3,000, so forcing a shared n would
handicap one of them and quietly bias the comparison.

FORMS
  rank-blend    w * rank(wf10) + (1-w) * rank(wf25), w swept -- scale-free
  product       P(wf10) * P(wf25)
  OR-label      ONE model on 'in the top-N of EITHER metric' -- a broader definition of
                good, not a combination of two models
  AND-label     ONE model on 'in the top-N of BOTH'

GUARDS: nested selection (choose w on early splits, evaluate on late) and splits-won beside
every mean. Judge is realised cpcv. Stage one only (D337). Snapshot only.
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
_SPLITS = (0.55, 0.60, 0.65, 0.70, 0.75)
_EARLY, _LATE = _SPLITS[:2], _SPLITS[2:]
_FRACS = (0.005, 0.01, 0.05)
_WEIGHTS = (0.0, 0.25, 0.40, 0.50, 0.60, 0.75, 1.0)
_NON_FEATURES = frozenset(
    {"crucible_run_id", "config_hash", "decided_at", "decision", "label", "coverage_verified"}
)
# Each metric at ITS optimum: wf_p10 dies past ~750 positives, wf_p25 is flat to 3,000.
_N_P10, _N_P25 = 300, 1500


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
    r = np.argsort(np.argsort(a, kind="stable")).astype(float)
    return r / max(1.0, len(a) - 1.0)


def _tail(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


def _topn_label(v: np.ndarray, n: int) -> np.ndarray:
    """'In the top N by this metric' -- immune to mass points, unlike a quantile."""
    return (v >= float(np.sort(v)[-n])).astype(float)


class Book:
    def __init__(self, x: np.ndarray, cols: dict[str, np.ndarray]) -> None:
        self.x, self.cols, self.y = x, cols, cols[_CPCV]
        self._c: dict[tuple[Any, ...], np.ndarray] = {}

    def k(self, s: float) -> int:
        return int(len(self.y) * s)

    def incumbent(self, s: float) -> np.ndarray:
        key = ("BASE", s)
        if key not in self._c:
            k = self.k(s)
            self._c[key] = _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], self.y[:k]))
        return self._c[key]

    def single(self, metric: str, n: int, s: float) -> np.ndarray:
        key = (metric, n, s)
        if key not in self._c:
            k = self.k(s)
            lab = _topn_label(self.cols[metric][:k], n)
            self._c[key] = _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab))
        return self._c[key]

    def combo_label(self, s: float, mode: str) -> np.ndarray | None:
        """ONE model on a combined label, rather than a blend of two models."""
        key = ("COMBO", mode, s)
        if key in self._c:
            return self._c[key]
        k = self.k(s)
        a = _topn_label(self.cols[_P10][:k], _N_P10).astype(bool)
        b = _topn_label(self.cols[_P25][:k], _N_P25).astype(bool)
        lab = ((a | b) if mode == "or" else (a & b)).astype(float)
        if lab.sum() < 30:
            return None
        self._c[key] = _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab))
        return self._c[key]

    def blend(self, s: float, w: float) -> np.ndarray:
        return w * _rank01(self.single(_P10, _N_P10, s)) + (1.0 - w) * _rank01(
            self.single(_P25, _N_P25, s)
        )


def _score(
    book: Book, splits: tuple[float, ...], make: Any, *, frac: float, judge: float = 1.0
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


def _cell(t: tuple[float, int, int]) -> str:
    m, w, n = t
    return f"{'--':>16}" if n == 0 or np.isnan(m) else f"{m:>10.2f}x {w}/{n}"


def _arm_forms(book: Book) -> None:
    print(f"\n=== ARM 1 — every form (wf_p10 @ top-{_N_P10}, wf_p25 @ top-{_N_P25}) ===")
    print(f"{'form':<34} " + "".join(f"{'top ' + f'{f:.1%}':>16}" for f in _FRACS))
    rows: list[tuple[str, Any]] = [
        (f"wf_p25 alone  (top-{_N_P25})", lambda s: book.single(_P25, _N_P25, s)),
        (f"wf_p10 alone  (top-{_N_P10})", lambda s: book.single(_P10, _N_P10, s)),
    ]
    rows += [(f"rank-blend w={w:.2f}", lambda s, w=w: book.blend(s, w)) for w in _WEIGHTS]
    rows += [
        (
            "product P(p10) x P(p25)",
            lambda s: book.single(_P10, _N_P10, s) * book.single(_P25, _N_P25, s),
        ),
        ("OR-label  (top-N of EITHER)", lambda s: book.combo_label(s, "or")),
        ("AND-label (top-N of BOTH)", lambda s: book.combo_label(s, "and")),
    ]
    for name, fn in rows:
        print(f"{name:<34} " + "".join(_cell(_score(book, _SPLITS, fn, frac=f)) for f in _FRACS))


def _arm_matched(book: Book) -> None:
    print("\n=== ARM 2 — MATCHED n for both components (removes the asymmetry) ===")
    for n in (150, 300, 750):
        print(f"\n  both at top-{n}:")
        print(f"  {'form':<32} " + "".join(f"{'top ' + f'{f:.1%}':>16}" for f in _FRACS))

        def blend_n(s: float, w: float, n: int = n) -> np.ndarray:
            return w * _rank01(book.single(_P10, n, s)) + (1.0 - w) * _rank01(
                book.single(_P25, n, s)
            )

        forms: list[tuple[str, Any]] = [
            ("wf_p25 alone", lambda s, n=n: book.single(_P25, n, s)),
            ("wf_p10 alone", lambda s, n=n: book.single(_P10, n, s)),
        ]
        forms += [
            (f"rank-blend w={w:.2f}", lambda s, w=w: blend_n(s, w)) for w in (0.25, 0.5, 0.75)
        ]
        for name, fn in forms:
            print(
                f"  {name:<32} " + "".join(_cell(_score(book, _SPLITS, fn, frac=f)) for f in _FRACS)
            )


def _arm_nested(book: Book) -> None:
    print("\n=== ARM 3 — NESTED: choose w on EARLY, evaluate on LATE (top 1%) ===")
    scored = []
    for w in _WEIGHTS:
        m, _, n = _score(book, _EARLY, lambda s, w=w: book.blend(s, w), frac=0.01)
        if n:
            scored.append((m, w))
    if not scored:
        print("  nothing fit on early splits")
        return
    best = max(scored)[1]
    lm, lw, ln = _score(book, _LATE, lambda s: book.blend(s, best), frac=0.01)
    print(f"  w chosen on EARLY = {best:.2f} (early {max(scored)[0]:.2f}x)")
    print(f"  evaluated on LATE = {lm:.2f}x, {lw}/{ln} unseen splits\n")
    print(f"  {'w':>6} {'early':>9} {'late':>9} {'late won':>10}")
    for _, w in sorted(scored, key=lambda t: t[1]):
        em, _, _ = _score(book, _EARLY, lambda s, w=w: book.blend(s, w), frac=0.01)
        l2, w2, n2 = _score(book, _LATE, lambda s, w=w: book.blend(s, w), frac=0.01)
        star = "  <- chosen" if w == best else ""
        print(f"  {w:>6.2f} {em:>8.2f}x {l2:>8.2f}x {f'{w2}/{n2}':>10}{star}")


def _arm_disjoint(book: Book) -> None:
    print("\n=== ARM 4 — DISJOINT windows, absolute counts (distinct configs) ===")
    edges = [int(len(book.y) * f) for f in (0.60, 0.70, 0.80, 0.90, 1.00)]
    models: dict[str, Any] = {
        "incumbent E[cpcv]": None,
        f"wf_p25 top-{_N_P25}": lambda xt, xe, lo: book_fit(book, xt, xe, lo, _P25, _N_P25),
        f"wf_p10 top-{_N_P10}": lambda xt, xe, lo: book_fit(book, xt, xe, lo, _P10, _N_P10),
        "rank-blend w=0.50": "blend",
        "OR-label": "or",
    }
    print(f"{'model':<24} {'n_sel':>7} {'>=1.0':>7} {'>=1.25':>8} {'>=1.5':>7} {'max':>7}")
    for name, spec in models.items():
        tot = [0, 0, 0, 0, 0.0]
        for lo, hi in pairwise(edges):
            xt, xe, ye = book.x[:lo], book.x[lo:hi], book.y[lo:hi]
            if spec is None:
                p = _apply_ridge(xe, _fit_ridge(xt, book.y[:lo]))
            elif spec == "blend":
                a = _apply_logistic(
                    xe, _fit_logistic(xt, _topn_label(book.cols[_P10][:lo], _N_P10))
                )
                b = _apply_logistic(
                    xe, _fit_logistic(xt, _topn_label(book.cols[_P25][:lo], _N_P25))
                )
                p = 0.5 * _rank01(a) + 0.5 * _rank01(b)
            elif spec == "or":
                la = _topn_label(book.cols[_P10][:lo], _N_P10).astype(bool)
                lb = _topn_label(book.cols[_P25][:lo], _N_P25).astype(bool)
                p = _apply_logistic(xe, _fit_logistic(xt, (la | lb).astype(float)))
            else:
                p = spec(xt, xe, lo)
            top = np.argsort(-p)[: max(1, int(0.05 * len(ye)))]
            sel = ye[top]
            tot[0] += len(sel)
            tot[1] += int((sel >= 1.0).sum())
            tot[2] += int((sel >= 1.25).sum())
            tot[3] += int((sel >= 1.5).sum())
            tot[4] = max(tot[4], float(sel.max()))
        print(f"{name:<24} {tot[0]:>7,} {tot[1]:>7,} {tot[2]:>8,} {tot[3]:>7,} {tot[4]:>7.3f}")


def book_fit(
    book: Book, xt: np.ndarray, xe: np.ndarray, lo: int, metric: str, n: int
) -> np.ndarray:
    return _apply_logistic(xe, _fit_logistic(xt, _topn_label(book.cols[metric][:lo], n)))


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
    keep = raw[_CPCV].is_not_null() & raw[_P10].is_not_null() & raw[_P25].is_not_null()
    fr = raw.filter(keep).sort("decided_at")
    fcols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    cols = {c: np.array(fr[c].to_list(), dtype=float) for c in (_CPCV, _P10, _P25)}
    print(f"stage one n={len(fr):,}  features={len(fcols)}")

    book = Book(x, cols)
    _arm_forms(book)
    _arm_matched(book)
    _arm_nested(book)
    _arm_disjoint(book)
    print("\nARM 3 decides whether the blend is real. A weight that only wins on the")
    print("splits it was chosen from is a fit, not a merge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
