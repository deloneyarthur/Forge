"""Head-to-head validation: `sharpe_baseline` vs `wf_p10` before anything ships.

WHY THIS EXISTS. The tail-lane build rests on ONE run (`sharpe_baseline_nested_test.py`):
5 splits, one estimator, one lambda, one judge threshold, and absolute counts SUMMED over 4
windows rather than won per-window. That run said `sharpe_baseline` top-800 delivers 307
strong components per 4,520 selected against `wf_p10`'s 244 and the incumbent's 131. A single
configuration is not a basis for a production lane, and this session has already withdrawn
two conclusions that looked solid on one read (`n_signals`, and the wf_p25-is-cheaper
framing).

WHAT THIS ADDS over that run:
  * 8 splits instead of 5, with a 4/4 early-late nested cut instead of 2/3.
  * n_pos from 100 to 3200 — `sharpe_baseline` looked FLAT over 200..1600 and flatness is
    the property we are buying, so it has to be probed past the tested edge.
  * THREE judge thresholds (0.9439 book floor / 1.0 / 1.25), because a target that only
    wins at the easiest judge is not a tail target.
  * Estimator + lambda robustness — logistic and ridge-on-binary at lambda 1/10/100. If the
    edge is a property of the LABEL it survives the estimator swap; if it is a property of
    the fit it does not.
  * PER-WINDOW absolute strong-component counts with WIN COUNTS, not a sum. 307-vs-244 as a
    total could be one lucky window; 4/4 windows cannot.
  * The MR slice at the real operating point (~30 of ~3,188 survivors ~= 1%), since the lane
    is sized at ~30 slots by Crucible's saturation measurement.

Fits are cached per (metric, n_pos, split, lambda, kind) — the previous run refit the
incumbent inside every scoring call and took an hour for less coverage.

Judged on realised cpcv. Stage one only (D337). Snapshot only, never the live RW-locked DB.
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
from forge.ranking.dataset import build_dataset
from forge.ranking.model import _fit_irls, _sigmoid_vec

_LIVE_DB = Path.home() / "forge_data" / "forge.db"
_CPCV = "target_cpcv_p25"
_SB = "target_sharpe_baseline"
_P10 = "target_wf_p10"
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SPLITS = (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75)
_EARLY, _LATE = _SPLITS[:4], _SPLITS[4:]
_NPOS = (100, 200, 400, 800, 1600, 3200)
_FRACS = (0.01, 0.02, 0.05)
_JUDGES = (0.9439, 1.0, 1.25)
_LAMBDAS = (1.0, 10.0, 100.0)
_FLOOR = 0.9439
_MIN_POS = 30
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


def _topn(v: np.ndarray, n: int) -> np.ndarray:
    return (v >= float(np.sort(v)[-n])).astype(float)


def _tail(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


class Cache:
    def __init__(self, x: np.ndarray, cols: dict[str, np.ndarray], comp: np.ndarray) -> None:
        self.x, self.cols, self.y, self.comp = x, cols, cols[_CPCV], comp
        self._c: dict[tuple[Any, ...], np.ndarray | None] = {}

    def k(self, s: float) -> int:
        return int(len(self.y) * s)

    def incumbent(self, s: float, lam: float = 10.0) -> np.ndarray:
        key = ("BASE", s, lam)
        if key not in self._c:
            k = self.k(s)
            self._c[key] = _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], self.y[:k], lam))
        out = self._c[key]
        assert out is not None
        return out

    def fit(
        self, metric: str, n: int, s: float, lam: float = 10.0, kind: str = "logistic"
    ) -> np.ndarray | None:
        key = (metric, n, s, lam, kind)
        if key in self._c:
            return self._c[key]
        k = self.k(s)
        lab = _topn(self.cols[metric][:k], n)
        if lab.sum() < _MIN_POS or lab.sum() >= k:
            self._c[key] = None
        elif kind == "ridge":
            self._c[key] = _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], lab, lam))
        else:
            self._c[key] = _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab, lam))
        return self._c[key]


def _score(
    c: Cache,
    splits: Any,
    metric: str,
    n: int,
    *,
    frac: float,
    judge: float,
    lam: float = 10.0,
    kind: str = "logistic",
) -> tuple[float, int, int]:
    lifts, won, cnt = [], 0, 0
    for s in splits:
        p = c.fit(metric, n, s, lam, kind)
        if p is None:
            continue
        k = c.k(s)
        a = _tail(p, c.y[k:], frac=frac, judge=judge)
        b = _tail(c.incumbent(s, lam), c.y[k:], frac=frac, judge=judge)
        if b > 0:
            lifts.append(a / b)
            won += a > b
            cnt += 1
    return (float(np.mean(lifts)) if lifts else float("nan")), won, cnt


def _cell(t: tuple[float, int, int]) -> str:
    m, w, n = t
    return f"{'--':>16}" if n == 0 or np.isnan(m) else f"{m:>10.2f}x {w}/{n}"


def _arm_grid(c: Cache, label: str) -> None:
    print(f"\n=== {label} — ARM 1: n_pos x judge threshold (top 2%, 8 splits) ===")
    print(f"{'metric':<24} {'n_pos':>6} " + "".join(f"{'judge>=' + str(j):>16}" for j in _JUDGES))
    for metric in (_SB, _P10):
        for n in _NPOS:
            cells = "".join(
                _cell(_score(c, _SPLITS, metric, n, frac=0.02, judge=j)) for j in _JUDGES
            )
            print(f"{metric:<24} {n:>6,} " + cells)
        print()


def _arm_estimator(c: Cache, label: str) -> None:
    print(f"=== {label} — ARM 2: estimator x lambda (top 2%, judge >= {_FLOOR}) ===")
    print("(ridge-on-binary is the control: same LABEL, different estimator)")
    hdr = "".join(f"{k + ' L=' + str(int(v)):>17}" for k in ("logi", "ridge") for v in _LAMBDAS)
    print(f"{'metric':<24} {'n_pos':>6} " + hdr)
    for metric in (_SB, _P10):
        for n in (400, 800, 1600):
            parts = []
            for k in ("logistic", "ridge"):
                for v in _LAMBDAS:
                    m, w, _ = _score(c, _SPLITS, metric, n, frac=0.02, judge=_FLOOR, lam=v, kind=k)
                    parts.append(f"{m:>11.2f}x {w}/8")
            cells = "".join(parts)
            print(f"{metric:<24} {n:>6,} " + cells)
    print()


def _arm_nested(c: Cache, label: str) -> None:
    print(f"=== {label} — ARM 3: NESTED, choose on 4 EARLY splits, judge on 4 LATE ===")
    scored = []
    for metric in (_SB, _P10):
        for n in _NPOS:
            m, _, cnt = _score(c, _EARLY, metric, n, frac=0.02, judge=_FLOOR)
            if cnt:
                scored.append((m, metric, n))
    if not scored:
        print("  nothing fit on the early splits")
        return
    best = max(scored)
    lm, lw, ln = _score(c, _LATE, best[1], best[2], frac=0.02, judge=_FLOOR)
    print(f"  chosen on EARLY: {best[1]} top-{best[2]} ({best[0]:.2f}x)")
    print(f"  on LATE: {lm:.2f}x, {lw}/{ln} unseen splits\n")
    print(f"  {'metric':<24} {'n_pos':>6} {'early':>9} {'late':>9} {'won':>7}")
    for _, metric, n in sorted(scored, key=lambda t: (t[1], t[2])):
        em, _, _ = _score(c, _EARLY, metric, n, frac=0.02, judge=_FLOOR)
        l2, w2, n2 = _score(c, _LATE, metric, n, frac=0.02, judge=_FLOOR)
        star = "  <-" if (metric, n) == (best[1], best[2]) else ""
        print(f"  {metric:<24} {n:>6,} {em:>8.2f}x {l2:>8.2f}x {f'{w2}/{n2}':>7}{star}")
    print()


def _arm_absolute(c: Cache, label: str) -> None:
    """PER-WINDOW strong-component counts, not a sum. 307-vs-244 as a total could be
    one lucky window; a 4/4 per-window win cannot."""
    print(f"=== {label} — ARM 4: PER-WINDOW strong components (disjoint, top 1% and 5%) ===")
    edges = [int(len(c.y) * f) for f in (0.60, 0.70, 0.80, 0.90, 1.00)]
    for frac in (0.01, 0.05):
        print(f"\n  top {frac:.0%}:")
        print(
            f"  {'model':<26} "
            + "".join(f"{'w' + str(i + 1):>7}" for i in range(4))
            + f"{'total':>8} {'beats incumbent':>17}"
        )
        per: dict[str, list[int]] = {}
        for name, spec in (
            ("incumbent E[cpcv]", None),
            (f"{_SB} top-800", (_SB, 800)),
            (f"{_SB} top-1600", (_SB, 1600)),
            (f"{_P10} top-200", (_P10, 200)),
            (f"{_P10} top-800", (_P10, 800)),
        ):
            counts = []
            for lo, hi in pairwise(edges):
                if spec is None:
                    p = _apply_ridge(c.x[lo:hi], _fit_ridge(c.x[:lo], c.y[:lo]))
                else:
                    metric, n = spec
                    lab = _topn(c.cols[metric][:lo], n)
                    if lab.sum() < _MIN_POS:
                        counts.append(0)
                        continue
                    p = _apply_logistic(c.x[lo:hi], _fit_logistic(c.x[:lo], lab))
                top = np.argsort(-p)[: max(1, int(frac * (hi - lo)))]
                idx = np.arange(lo, hi)[top]
                counts.append(int((c.comp[idx] & (c.y[idx] >= _FLOOR)).sum()))
            per[name] = counts
            base = per.get("incumbent E[cpcv]", counts)
            wins = sum(1 for a, b in zip(counts, base, strict=False) if a > b)
            tag = "--" if spec is None else f"{wins}/4"
            print(
                f"  {name:<26} "
                + "".join(f"{v:>7,}" for v in counts)
                + f"{sum(counts):>8,} {tag:>17}"
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    raw = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    cfgj = dict(con.execute("SELECT config_hash, config_json FROM submissions").fetchall())
    con.close()

    keep = raw[_CPCV].is_not_null() & raw[_P10].is_not_null() & raw[_SB].is_not_null()
    fr = raw.filter(keep).sort("decided_at")
    fcols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    cols = {m: np.array(fr[m].to_list(), dtype=float) for m in (_CPCV, _SB, _P10)}
    comp = np.array([d in _POSITIVE for d in fr["decision"].to_list()], dtype=bool)
    hyp = np.array(
        [
            (json.loads(cfgj[h]).get("hypothesis") if cfgj.get(h) else "")
            for h in fr["config_hash"].to_list()
        ]
    )
    print(f"n={len(x):,}  features={len(fcols)}  splits={len(_SPLITS)}")
    print(f"corr(sharpe_baseline, cpcv) = {float(np.corrcoef(cols[_SB], cols[_CPCV])[0, 1]):.4f}")

    for label, mask in (
        ("GLOBAL", np.ones(len(x), dtype=bool)),
        ("MR only (the lane's slice)", hyp == "mean_reversion"),
    ):
        c = Cache(x[mask], {k: v[mask] for k, v in cols.items()}, comp[mask])
        print(f"\n{'#' * 78}\n### {label}  n={int(mask.sum()):,}\n{'#' * 78}")
        _arm_grid(c, label)
        _arm_estimator(c, label)
        _arm_nested(c, label)
        _arm_absolute(c, label)

    print("\nSHIP ONLY IF: sharpe_baseline beats wf_p10 across judge thresholds (ARM 1),")
    print("survives the estimator swap (ARM 2), wins on unseen late splits (ARM 3), and")
    print("beats the incumbent per-window rather than only in total (ARM 4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
