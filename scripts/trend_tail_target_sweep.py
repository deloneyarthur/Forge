"""Find a TREND-specific tail target — or establish that none exists.

WHY. Every target sweep so far was GLOBAL, and every one landed on mean-reversion. That is
not a flaw in the winners, it is what we asked them to do: the MR tail is ~3x denser than the
trend tail (`MR/rsi/swing_mid` P(cpcv>=1.0) = 1.82% vs `trend/donchian/mid` 0.61% and
`trend/momentum_252/long` 0.52%), so any single optimiser walks to MR and stays. The
consequence is measured: `wf_p10` selection is ~90% `{keltner_pct, rsi, rsi_14} x swing_mid`
and drops `trend/donchian/mid` from 20.2% to 4.2%.

That matters because all four promoted books share ONE trend spine (`91324e5d_dsjv45`), so a
stream that stops emitting trend candidates makes that dependency permanent.

Hence the two-leg ranked lane: an MR leg (`wf_p10` top-300, which the global sweeps already
found) and a TREND leg with its own target. This script looks for that target.

THE ARM THAT DECIDES WHETHER A SEPARATE LEG IS EVEN NEEDED (arm 0). Two ways to fill a trend
leg:
    (a) take the GLOBAL model and simply restrict selection to trend candidates
    (b) fit a model on trend rows only
If (a) ~= (b), no separate target is justified -- just reserve trend slots and reuse the
global model, which is far less machinery. Only if (b) clearly beats (a) does a second target
earn its place. We test that first, because a negative result there ends the work.

DISCIPLINE, all of it earned this week:
  * LABELS PINNED BY COUNT, never quantile -- `wf_p10` has a mass point at zero and tuned
    parameters have failed to transfer forward 3 for 3.
  * MULTI-SPLIT with splits-won beside every mean; nested selection where a choice is made.
  * Judged on REALISED cpcv, at the book-usability floor (0.9439 -- the weakest component
    ever used in a promoted book) as well as the round numbers, because the thin trend tail
    makes >=1.0 sparse.

Stage one only (D337). Snapshot only, never the live RW-locked DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import polars as pl

from forge.persistence.registry_loader import load_registry
from forge.ranking.dataset import TARGET_COLUMNS, build_dataset
from forge.ranking.model import _fit_irls, _sigmoid_vec

_LIVE_DB = Path.home() / "forge_data" / "forge.db"
_CPCV = "target_cpcv_p25"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SPLITS = (0.55, 0.60, 0.65, 0.70, 0.75)
_EARLY, _LATE = _SPLITS[:2], _SPLITS[2:]
# 0.5% added 2026-07-27: a trend ARM would be ~20-40 slots of ~3,188 survivors (~1%),
# so the decision-relevant fractions are the tight ones, not top-10%.
_FRACS = (0.005, 0.01, 0.02, 0.05)
_NPOS = (100, 200, 400, 800, 1600)
_BOOK_FLOOR = 0.9439
_JUDGES = (_BOOK_FLOOR, 1.0)
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


def _topn_label(v: np.ndarray, n: int) -> np.ndarray:
    """'Top N by this metric' -- immune to mass points, and carries no tunable knob."""
    return (v >= float(np.sort(v)[-n])).astype(float)


def _tail(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


def _cell(m: float, w: int, n: int) -> str:
    return f"{'--':>16}" if n == 0 or np.isnan(m) else f"{m:>10.2f}x {w}/{n}"


class TrendBook:
    """Trend-only design matrices, plus the global frame for the arm-0 comparison."""

    def __init__(
        self,
        xt: np.ndarray,
        cols_t: dict[str, np.ndarray],
        xg: np.ndarray,
        cols_g: dict[str, np.ndarray],
        is_trend: np.ndarray,
    ) -> None:
        self.x, self.cols, self.y = xt, cols_t, cols_t[_CPCV]
        self.xg, self.colsg, self.is_trend = xg, cols_g, is_trend

    def k(self, s: float) -> int:
        return int(len(self.y) * s)

    def incumbent(self, s: float) -> np.ndarray:
        k = self.k(s)
        return _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], self.y[:k]))

    def trend_fit(self, metric: str, n: int, s: float) -> np.ndarray | None:
        k = self.k(s)
        lab = _topn_label(self.cols[metric][:k], n)
        if lab.sum() < _MIN_POS:
            return None
        return _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab))

    def global_fit_restricted(self, metric: str, n: int, s: float) -> np.ndarray | None:
        """Fit on ALL rows, then score only the trend test rows -- arm 0's option (a)."""
        kt = self.k(s)
        # global train window ends at the same wall-clock position as the trend one
        n_before = int(np.searchsorted(np.cumsum(self.is_trend), kt) + 1)
        kg = min(n_before, len(self.colsg[_CPCV]) - 1)
        lab = _topn_label(self.colsg[metric][:kg], n)
        if lab.sum() < _MIN_POS:
            return None
        fit = _fit_logistic(self.xg[:kg], lab)
        return _apply_logistic(self.x[kt:], fit)


def _score(
    book: TrendBook, splits: Any, make: Any, *, frac: float, judge: float
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


def _arm0(book: TrendBook) -> None:
    print("\n=== ARM 0 — is a SEPARATE trend target even needed? ===")
    print("(a) global model restricted to trend candidates  vs  (b) trend-fit model")
    print("if these tie, reserve trend slots and reuse the global model -- no second target\n")
    print(f"{'metric':<18} {'fit':<10} " + "".join(f"{'top ' + f'{f:.0%}':>16}" for f in _FRACS))
    for metric in ("target_sharpe_baseline", "target_wf_p10", "target_wf_p25", _CPCV):
        for kind in ("global", "trend"):
            fn = book.global_fit_restricted if kind == "global" else book.trend_fit
            cells = [
                _cell(
                    *_score(
                        book,
                        _SPLITS,
                        lambda s, m=metric, f=fn: f(m, 300, s),
                        frac=fr,
                        judge=_BOOK_FLOOR,
                    )
                )
                for fr in _FRACS
            ]
            print(f"{metric:<18} {kind:<10} " + "".join(cells))
        print()


def _arm1(book: TrendBook) -> None:
    print("=== ARM 1 — every base metric x positive count, TREND-FIT (judge = book floor) ===")
    print(f"{'metric':<20} {'n_pos':>6} " + "".join(f"{'top ' + f'{f:.0%}':>16}" for f in _FRACS))
    for metric in TARGET_COLUMNS:
        if metric not in book.cols:
            continue
        for npos in _NPOS:
            cells = [
                _cell(
                    *_score(
                        book,
                        _SPLITS,
                        lambda s, m=metric, n=npos: book.trend_fit(m, n, s),
                        frac=fr,
                        judge=_BOOK_FLOOR,
                    )
                )
                for fr in _FRACS
            ]
            print(f"{metric:<20} {npos:>6,} " + "".join(cells))
        print()


def _arm2(book: TrendBook) -> None:
    print("=== ARM 2 — the harder judge (realised cpcv >= 1.0), top 2% and 5% ===")
    print(f"{'metric':<20} {'n_pos':>6} {'top2% j>=1.0':>17} {'top5% j>=1.0':>17}")
    for metric in TARGET_COLUMNS:
        if metric not in book.cols:
            continue
        for npos in (200, 800):
            row = [
                _cell(
                    *_score(
                        book,
                        _SPLITS,
                        lambda s, m=metric, n=npos: book.trend_fit(m, n, s),
                        frac=fr,
                        judge=1.0,
                    )
                )
                for fr in (0.02, 0.05)
            ]
            print(f"{metric:<20} {npos:>6,} " + "".join(row))
    print()


def _arm3(book: TrendBook) -> None:
    print("=== ARM 3 — NESTED: choose (metric, n_pos) on EARLY, evaluate on LATE (top 2%) ===")
    scored = []
    for metric in TARGET_COLUMNS:
        if metric not in book.cols:
            continue
        for npos in _NPOS:
            m, _, n = _score(
                book,
                _EARLY,
                lambda s, mm=metric, nn=npos: book.trend_fit(mm, nn, s),
                frac=0.02,
                judge=_BOOK_FLOOR,
            )
            if n:
                scored.append((m, metric, npos))
    if not scored:
        print("  nothing fit on the early splits")
        return
    best = max(scored)
    lm, lw, ln = _score(
        book, _LATE, lambda s: book.trend_fit(best[1], best[2], s), frac=0.02, judge=_BOOK_FLOOR
    )
    print(f"  chosen on EARLY: {best[1]} top-{best[2]} (early {best[0]:.2f}x)")
    print(f"  evaluated on LATE: {lm:.2f}x, {lw}/{ln} unseen splits\n")
    print(f"  {'metric':<20} {'n_pos':>6} {'early':>9} {'late':>9} {'late won':>10}")
    for _, metric, npos in sorted(scored, key=lambda t: (t[1], t[2])):
        em, _, _ = _score(
            book,
            _EARLY,
            lambda s, m=metric, n=npos: book.trend_fit(m, n, s),
            frac=0.02,
            judge=_BOOK_FLOOR,
        )
        l2, w2, n2 = _score(
            book,
            _LATE,
            lambda s, m=metric, n=npos: book.trend_fit(m, n, s),
            frac=0.02,
            judge=_BOOK_FLOOR,
        )
        star = "  <- chosen" if (metric, npos) == (best[1], best[2]) else ""
        print(f"  {metric:<20} {npos:>6,} {em:>8.2f}x {l2:>8.2f}x {f'{w2}/{n2}':>10}{star}")


def _arm4(book: TrendBook, comp: np.ndarray) -> None:
    print("\n=== ARM 4 — DISJOINT windows, absolute STRONG-component counts ===")
    edges = [int(len(book.y) * f) for f in (0.60, 0.70, 0.80, 0.90, 1.00)]
    cands: list[tuple[str, Any]] = [("incumbent E[cpcv]", None)]
    cands += [
        (f"{m} top-{n}", (m, n))
        for m in ("target_sharpe_baseline", "target_wf_p10", "target_wf_p25", _CPCV)
        for n in (200, 800, 1600)
    ]
    print(f"{'model':<28} {'n_sel':>7} {'comp':>7} {'STRONG':>8} {'>=1.0':>7} {'max':>7}")
    for name, spec in cands:
        tot = [0, 0, 0, 0, 0.0]
        for lo, hi in pairwise(edges):
            if spec is None:
                p = _apply_ridge(book.x[lo:hi], _fit_ridge(book.x[:lo], book.y[:lo]))
            else:
                metric, n = spec
                lab = _topn_label(book.cols[metric][:lo], n)
                if lab.sum() < _MIN_POS:
                    continue
                p = _apply_logistic(book.x[lo:hi], _fit_logistic(book.x[:lo], lab))
            top = np.argsort(-p)[: max(1, int(0.05 * (hi - lo)))]
            idx = np.arange(lo, hi)[top]
            v, c = book.y[idx], comp[idx]
            tot[0] += len(idx)
            tot[1] += int(c.sum())
            tot[2] += int((c & (v >= _BOOK_FLOOR)).sum())
            tot[3] += int((c & (v >= 1.0)).sum())
            tot[4] = max(tot[4], float(v.max()))
        print(f"{name:<28} {tot[0]:>7,} {tot[1]:>7,} {tot[2]:>8,} {tot[3]:>7,} {tot[4]:>7.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    raw = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    cfg = dict(con.execute("SELECT config_hash, config_json FROM submissions").fetchall())
    con.close()
    keep = raw[_CPCV].is_not_null()
    for t in ("target_wf_p10", "target_wf_p25"):
        keep = keep & raw[t].is_not_null()
    fr = raw.filter(keep).sort("decided_at")

    hyp = []
    for h in fr["config_hash"].to_list():
        cj = cfg.get(h)
        hyp.append(json.loads(cj).get("hypothesis") if cj else None)
    is_trend = np.array([h == "trend_continuation" for h in hyp], dtype=bool)

    fcols = _feature_cols(fr)
    xg = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    have = [t for t in TARGET_COLUMNS if t in fr.columns]
    cols_g = {t: np.array(fr[t].to_list(), dtype=float) for t in have}
    comp_all = np.array(
        [d in {"component", "promote"} for d in fr["decision"].to_list()], dtype=bool
    )

    xt = xg[is_trend]
    cols_t = {k: v[is_trend] for k, v in cols_g.items()}
    # a metric is unusable on the trend slice if it is all-null there
    cols_t = {k: v for k, v in cols_t.items() if np.isfinite(v).sum() > 1000}
    comp_t = comp_all[is_trend]
    yt = cols_t[_CPCV]

    print(f"global n={len(xg):,}   TREND n={len(xt):,} ({is_trend.mean():.1%})")
    print(
        f"trend component rate {comp_t.mean():.2%}   "
        f">=book floor {_BOOK_FLOOR}: {int((yt >= _BOOK_FLOOR).sum()):,}  "
        f">=1.0: {int((yt >= 1.0).sum()):,}  >=1.5: {int((yt >= 1.5).sum()):,}"
    )
    print(f"usable base metrics on the trend slice: {sorted(cols_t)}")

    book = TrendBook(xt, cols_t, xg, cols_g, is_trend)
    _arm0(book)
    _arm1(book)
    _arm2(book)
    _arm3(book)
    _arm4(book, comp_t)
    print("\nARM 0 decides whether a second target is justified at all; ARM 3 decides which.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
