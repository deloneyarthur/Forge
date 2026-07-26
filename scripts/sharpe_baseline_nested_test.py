"""Crucible's ASK-3 lead, run inside our nested design: does `sharpe_baseline` really
order the tail better than `wf_p10`?

THEIR MEASUREMENT (2026-07-26, single-split, their stored labels, top 5%, scoring
P(cpcv >= 0.9115)):

    hypothesis            n        base    wf_p10   wf_median   sharpe_baseline
    trend_continuation  111,268   0.82%     4.49x      6.21x        14.47x
    mean_reversion       55,311   1.53%     7.86x      9.62x        14.77x
    volatility_event      4,209   0.12%     4.01x     16.03x        20.04x

**They flagged it themselves and we agree**: `sharpe_baseline` and `cpcv_sharpe_p25` are
computed on overlapping data, so part of that lift may be shared-sample co-movement rather
than prediction, while the wf metrics are out-of-sample by construction and handicapped in a
way that has nothing to do with tail-prediction skill. It is also a single-split
retrospective read — the exact shape both sides agreed does not justify shipping.

THE CONTROL THAT MATTERS, and it is the one their table lacks: **`cpcv` exceedance itself**.
If `sharpe_baseline` is simply a proxy for cpcv-on-the-same-window, then a model trained on
"top-N by sharpe_baseline" should behave like one trained on "top-N by cpcv" — and the
incumbent already orders by E[cpcv]. Including cpcv-exceedance separates "sharpe_baseline is
a better tail label" from "sharpe_baseline is cpcv wearing a hat".

Judged at the CORRECTED book-usability floor **0.9115** (Crucible 2026-07-26: our 0.9439 was
wrong, derived from 5 legs when there are 14; the floor-setting leg is `031ea6933bad2e34`,
the only `event_momentum` and only `swing_short` leg ever promoted).

Labels pinned by COUNT. Multi-split with splits-won. Nested selection. Stage one only.
Snapshot only, never the live RW-locked DB.
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
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SPLITS = (0.55, 0.60, 0.65, 0.70, 0.75)
_EARLY, _LATE = _SPLITS[:2], _SPLITS[2:]
_FRACS = (0.01, 0.02, 0.05)
_NPOS = (200, 400, 800, 1600)
_FLOOR = 0.9115  # Crucible's corrected book-usability floor
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


def _tail(pred: np.ndarray, y: np.ndarray, *, frac: float, judge: float) -> float:
    top = np.argsort(-pred)[: max(1, int(frac * len(pred)))]
    return float((y[top] >= judge).mean())


def _gate_value(raw: object, key: str) -> float | None:
    d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    if not isinstance(d, dict):
        return None
    e = d.get(key)
    v = e.get("value") if isinstance(e, dict) else e
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


class Slice:
    def __init__(self, x: np.ndarray, cols: dict[str, np.ndarray]) -> None:
        self.x, self.cols, self.y = x, cols, cols[_CPCV]

    def k(self, s: float) -> int:
        return int(len(self.y) * s)

    def incumbent(self, s: float) -> np.ndarray:
        k = self.k(s)
        return _apply_ridge(self.x[k:], _fit_ridge(self.x[:k], self.y[:k]))

    def fit(self, metric: str, n: int, s: float) -> np.ndarray | None:
        k = self.k(s)
        lab = _topn(self.cols[metric][:k], n)
        if lab.sum() < _MIN_POS:
            return None
        return _apply_logistic(self.x[k:], _fit_logistic(self.x[:k], lab))


def _score(
    sl: Slice, splits: Any, make: Any, *, frac: float, judge: float
) -> tuple[float, int, int]:
    lifts, won, n = [], 0, 0
    for s in splits:
        p = make(s)
        if p is None:
            continue
        k = sl.k(s)
        a = _tail(p, sl.y[k:], frac=frac, judge=judge)
        b = _tail(sl.incumbent(s), sl.y[k:], frac=frac, judge=judge)
        if b > 0:
            lifts.append(a / b)
            won += a > b
            n += 1
    return (float(np.mean(lifts)) if lifts else float("nan")), won, n


def _cell(t: tuple[float, int, int]) -> str:
    m, w, n = t
    return f"{'--':>16}" if n == 0 or np.isnan(m) else f"{m:>10.2f}x {w}/{n}"


def _run_slice(name: str, sl: Slice, metrics: list[str]) -> None:
    print(
        f"\n{'=' * 78}\n=== {name}  (n={len(sl.y):,}, "
        f"P(cpcv>={_FLOOR})={float((sl.y >= _FLOOR).mean()):.3%}) ==="
    )
    print(f"\n{'metric':<22} {'n_pos':>6} " + "".join(f"{'top ' + f'{f:.0%}':>16}" for f in _FRACS))
    for metric in metrics:
        for npos in _NPOS:
            cells = "".join(
                _cell(
                    _score(
                        sl,
                        _SPLITS,
                        lambda s, m=metric, n=npos: sl.fit(m, n, s),
                        frac=fr,
                        judge=_FLOOR,
                    )
                )
                for fr in _FRACS
            )
            print(f"{metric:<22} {npos:>6,} " + cells)
        print()

    print(f"  NESTED (top 2%, judge >= {_FLOOR}) — choose on EARLY, evaluate on LATE")
    scored = []
    for metric in metrics:
        for npos in _NPOS:
            m, _, n = _score(
                sl, _EARLY, lambda s, mm=metric, nn=npos: sl.fit(mm, nn, s), frac=0.02, judge=_FLOOR
            )
            if n:
                scored.append((m, metric, npos))
    if not scored:
        print("    nothing fit on early splits")
        return
    best = max(scored)
    lm, lw, ln = _score(sl, _LATE, lambda s: sl.fit(best[1], best[2], s), frac=0.02, judge=_FLOOR)
    print(f"    chosen on EARLY: {best[1]} top-{best[2]} ({best[0]:.2f}x)")
    print(f"    on LATE: {lm:.2f}x, {lw}/{ln} unseen splits\n")
    print(f"    {'metric':<22} {'n_pos':>6} {'early':>9} {'late':>9} {'won':>7}")
    for _, metric, npos in sorted(scored, key=lambda t: (t[1], t[2])):
        em, _, _ = _score(
            sl, _EARLY, lambda s, m=metric, n=npos: sl.fit(m, n, s), frac=0.02, judge=_FLOOR
        )
        l2, w2, n2 = _score(
            sl, _LATE, lambda s, m=metric, n=npos: sl.fit(m, n, s), frac=0.02, judge=_FLOOR
        )
        star = "  <-" if (metric, npos) == (best[1], best[2]) else ""
        print(f"    {metric:<22} {npos:>6,} {em:>8.2f}x {l2:>8.2f}x {f'{w2}/{n2}':>7}{star}")


def _absolute(name: str, sl: Slice, comp: np.ndarray, metrics: list[str]) -> None:
    print(f"\n  ABSOLUTE, disjoint windows, top 5% — {name}")
    edges = [int(len(sl.y) * f) for f in (0.60, 0.70, 0.80, 0.90, 1.00)]
    rows: list[tuple[str, Any]] = [("incumbent E[cpcv]", None)]
    rows += [(f"{m} top-800", (m, 800)) for m in metrics]
    print(f"  {'model':<26} {'comp':>7} {'STRONG':>8} {'>=1.0':>7} {'max':>7}")
    for label, spec in rows:
        tot = [0, 0, 0, 0.0]
        for lo, hi in pairwise(edges):
            if spec is None:
                p = _apply_ridge(sl.x[lo:hi], _fit_ridge(sl.x[:lo], sl.y[:lo]))
            else:
                metric, n = spec
                lab = _topn(sl.cols[metric][:lo], n)
                if lab.sum() < _MIN_POS:
                    continue
                p = _apply_logistic(sl.x[lo:hi], _fit_logistic(sl.x[:lo], lab))
            top = np.argsort(-p)[: max(1, int(0.05 * (hi - lo)))]
            idx = np.arange(lo, hi)[top]
            v, c = sl.y[idx], comp[idx]
            tot[0] += int(c.sum())
            tot[1] += int((c & (v >= _FLOOR)).sum())
            tot[2] += int((c & (v >= 1.0)).sum())
            tot[3] = max(tot[3], float(v.max()))
        print(f"  {label:<26} {tot[0]:>7,} {tot[1]:>8,} {tot[2]:>7,} {tot[3]:>7.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)
    raw = build_dataset(con, load_registry(), era_cut=_ERA_CUT)
    extra = dict(con.execute("SELECT config_hash, gate_results FROM verdicts").fetchall())
    cfgj = dict(con.execute("SELECT config_hash, config_json FROM submissions").fetchall())
    con.close()

    keep = raw[_CPCV].is_not_null() & raw["target_wf_p10"].is_not_null()
    fr = raw.filter(keep).sort("decided_at")
    hashes = fr["config_hash"].to_list()
    sb = np.array([_gate_value(extra.get(h), "sharpe_baseline") or np.nan for h in hashes])
    ok = np.isfinite(sb)
    fr = fr.filter(pl.Series(ok))
    hashes = [h for h, k in zip(hashes, ok, strict=False) if k]
    sb = sb[ok]

    fcols = _feature_cols(fr)
    x = np.array([[float(r[c]) for c in fcols] for r in fr.iter_rows(named=True)])
    cols = {
        c: np.array(fr[c].to_list(), dtype=float) for c in (_CPCV, "target_wf_p10", "target_wf_p25")
    }
    cols["sharpe_baseline"] = sb
    comp = np.array([d in {"component", "promote"} for d in fr["decision"].to_list()], dtype=bool)
    hyp = np.array([(json.loads(cfgj[h]).get("hypothesis") if cfgj.get(h) else "") for h in hashes])
    print(f"n={len(x):,} with sharpe_baseline  features={len(fcols)}")
    print(
        f"corr(sharpe_baseline, cpcv) = {float(np.corrcoef(sb, cols[_CPCV])[0, 1]):.4f}"
        "   <- the shared-sample concern, quantified"
    )

    metrics = ["sharpe_baseline", "target_wf_p10", "target_wf_p25", _CPCV]
    for label, mask in (
        ("GLOBAL", np.ones(len(x), dtype=bool)),
        ("TREND only", hyp == "trend_continuation"),
        ("MEAN-REVERSION only", hyp == "mean_reversion"),
    ):
        if mask.sum() < 20_000:
            print(f"\n{label}: n={int(mask.sum()):,} too thin, skipped")
            continue
        sl = Slice(x[mask], {k: v[mask] for k, v in cols.items()})
        _run_slice(label, sl, metrics)
        _absolute(label, sl, comp[mask], metrics)
    print("\nthe control that decides: if sharpe_baseline ~= cpcv-exceedance, it is cpcv")
    print("wearing a hat and the incumbent already has it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
