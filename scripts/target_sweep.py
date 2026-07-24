"""Exhaustive target sweep: what should the ranker and generation models train on?

WHY: picking a training target by intuition is how a learned system ends up
optimizing something correlated-with-but-not-equal-to what we want. D155 measured
exactly that failure (gate-pass was learnable, but training on it would have bred
the trend monoculture). So every candidate target is scored on TWO axes, because a
target can win one and lose the other:

  (1) LEARNABILITY - within-cell OOS rank-IC of params -> target, vs a shuffled-label
      null. "Can a model predict this at all from what we control?"
  (2) ALIGNMENT    - train on the target, rank held-out configs by the prediction,
      then measure the REALIZED gate metrics of the top decile. "If we optimize this,
      what do we actually get?" A learnable-but-misaligned target scores high on (1)
      and flat on (2). `min_oos_trade_count` is carried as the deliberate control:
      params mechanically determine trade count, so it should ace (1) and do nothing
      on (2).

CANDIDATES are not hand-picked: every numeric metric present in `gate_results` on the
honest lane is swept, plus derived composites. Metrics that are 0-by-construction for
single-config submissions (`pbo`, `ablation_arm`) carry no variance and are dropped
automatically.

POPULATIONS, and the tie-break rule:
  Run A - per-cell over all `fullhist_refit` rows. Powered, but includes
          ranker-selected rows, so it can reward a target the ranker already chased.
  Run B - the honest arm (`selection_mode='prefilter_sample'`) only, pooled with
          within-cell demeaning. Uncontaminated but thin.
  On disagreement, RUN B WINS. That is the pre-agreed rule with Crucible: a target
  decided on ranker-selected data is circular.

Reads a SNAPSHOT of forge.db, never the live RW-locked DB (`docs/tasks/investigate-live.md`):

    cp ~/forge_data/forge.db ~/.cache/rv/forge_snap.db   # ~6s, delete when done
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

_DEFAULT_SNAPSHOT = Path("~/.cache/rv/forge_snap.db").expanduser()
_LIVE_DB = Path("~/forge_data/forge.db").expanduser()

_MIN_CELL_N = 80  # per-cell floor for Run A
_MIN_HONEST_CELL_N = 8  # per-cell floor for Run B pooling
_N_SHUFFLES = 40
_RIDGE_ALPHA = 10.0
_TOP_FRAC = 0.10  # alignment reads the top decile, within cell

# Metrics whose gate direction is "lower is better" -> negated so every target is
# oriented "higher is better" and ICs are comparable in sign.
_LOWER_IS_BETTER = frozenset({"max_drawdown_ceiling"})

# 0-by-construction on single-config submissions (no sweep, no selection): carry no
# variance and are dropped by the variance filter anyway; named so the drop is legible.
_STRUCTURALLY_CONSTANT = frozenset({"pbo", "ablation_arm"})

# Not quality metrics -- coverage bookkeeping, swept only as a negative control.
_NON_QUALITY = frozenset({"regime_coverage"})

# The metric Crucible actually gates promotion on. Alignment is measured against it.
_DECISION_METRIC = "cpcv_sharpe_p25"


def _gate_value(gate_results: object, key: str) -> float | None:
    """One metric out of a verdict's `gate_results`, tolerant of both stored shapes
    ({gate: value} and {gate: {value: ...}})."""
    if gate_results is None:
        return None
    if isinstance(gate_results, dict):
        d: dict[str, Any] = gate_results
    elif isinstance(gate_results, (str, bytes, bytearray)):
        d = json.loads(gate_results)
    else:
        return None
    v = d.get(key)
    if isinstance(v, dict):
        v = v.get("value", v.get("observed"))
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _gates_passed(gate_results: object) -> float | None:
    """Count of gates reporting `passed` -- a 'how close to clearing everything'
    target that is not any single metric."""
    if gate_results is None:
        return None
    if isinstance(gate_results, dict):
        d: dict[str, Any] = gate_results
    elif isinstance(gate_results, (str, bytes, bytearray)):
        d = json.loads(gate_results)
    else:
        return None
    n = 0
    for v in d.values():
        if isinstance(v, dict) and v.get("passed") is True:
            n += 1
    return float(n)


def _dte_bucket(dte_max: float | None) -> str:
    d = dte_max or 0
    return "short" if d <= 25 else "mid" if d <= 55 else "long"


def _cell_key(cfg: dict[str, Any]) -> tuple[Any, ...]:
    """Everything the sampler already steers at cell level, plus the dte-bucket."""
    combiner = (cfg.get("combiner") or {}).get("type", "confluence")
    xs = "xsect" if combiner == "cross_sectional_rank" else "named"
    directional = None
    regimes: list[str] = []
    for sig in cfg.get("signals", []):
        role = sig.get("role")
        inds = tuple(sig.get("indicators", []))
        if role == "directional":
            directional = inds[0] if inds else None
        elif role == "regime":
            regimes.extend(inds)
    bucket = _dte_bucket((cfg.get("selector") or {}).get("dte_max"))
    return (cfg.get("hypothesis"), directional, tuple(sorted(regimes)), xs, bucket)


def _features(cfg: dict[str, Any]) -> dict[str, float | None]:
    """The intra-cell param surface. `dte_min`/`dte_max` are deliberately EXCLUDED:
    they proxy the bucket, which is already in the cell key and already steered by
    the sampler's bucket weights, so including them would inflate every target's IC
    with cell-level signal the models do not need to learn."""
    f: dict[str, float | None] = {}
    sel = cfg.get("selector") or {}
    f["delta_target"] = sel.get("delta_target")
    f["risk_pct"] = (cfg.get("sizer") or {}).get("per_trade_risk_pct")
    combiner = cfg.get("combiner") or {}
    f["rank_k"] = combiner.get("rank_k")
    f["long_short"] = 1.0 if combiner.get("direction_mode") == "long_short" else 0.0
    f["monthly"] = 1.0 if combiner.get("rebalance") == "monthly" else 0.0
    n_bars = None
    kinds: set[str] = set()
    for ex in cfg.get("exits", []):
        t = ex.get("type")
        kinds.add(t)
        if t == "time_stop":
            n_bars = (ex.get("params") or {}).get("n_bars", ex.get("n_bars"))
    f["timer_nbars"] = n_bars
    f["has_timer"] = 1.0 if "time_stop" in kinds else 0.0
    f["has_chandelier"] = 1.0 if "chandelier" in kinds else 0.0
    for sig in cfg.get("signals", []):
        for k, v in (sig.get("params") or {}).items():
            if isinstance(v, (int, float)):
                f[f"{sig.get('role')}_{k}"] = float(v)
    return f


def _rank(a: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(a, kind="stable")).astype(float)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = _rank(a), _rank(b)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / denom) if denom > 1e-12 else 0.0


def _oos_pred(x: np.ndarray, y: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """5-fold out-of-sample ridge predictions."""
    n = len(y)
    folds = np.array_split(rng.permutation(n), 5)
    pred = np.zeros(n)
    for i in range(5):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(5) if j != i])
        xt = x[train]
        w = np.linalg.solve(
            xt.T @ xt + _RIDGE_ALPHA * np.eye(xt.shape[1]), xt.T @ (y[train] - y[train].mean())
        )
        pred[test] = x[test] @ w + y[train].mean()
    return pred


def _oos_ic_vs_null(
    x: np.ndarray, y: np.ndarray, rng: np.random.RandomState
) -> tuple[float, float, np.ndarray]:
    """(OOS rank-IC, null95, OOS predictions). The null is the standard permutation
    test: shuffle labels, refit, recompute the same statistic."""
    pred = _oos_pred(x, y, rng)
    ic = _spearman(pred, y)
    null = []
    for _ in range(_N_SHUFFLES):
        y_shuf = rng.permutation(y)
        null.append(_spearman(_oos_pred(x, y_shuf, rng), y_shuf))
    null.sort()
    return ic, null[int(0.95 * len(null))], pred


def _matrix(rows: list[dict[str, Any]], keys: list[str]) -> np.ndarray | None:
    x = np.array(
        [
            [(r["f"].get(k) if isinstance(r["f"].get(k), (int, float)) else np.nan) for k in keys]
            for r in rows
        ],
        dtype=float,
    )
    if x.size == 0:
        return None
    for j in range(x.shape[1]):
        col = x[:, j]
        med = np.nanmedian(col)
        col[np.isnan(col)] = 0.0 if np.isnan(med) else med
        x[:, j] = col
    keep = [j for j in range(x.shape[1]) if np.std(x[:, j]) > 1e-9]
    if not keep:
        return None
    x = x[:, keep]
    return (x - x.mean(0)) / (x.std(0) + 1e-9)


def _feature_keys(rows: list[dict[str, Any]]) -> list[str]:
    return [
        k
        for k in {k for r in rows for k in r["f"]}
        if sum(1 for r in rows if isinstance(r["f"].get(k), (int, float))) >= 0.6 * len(rows)
    ]


def load(db_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Every honest-lane verdict joined to its config, with every numeric
    `gate_results` metric discovered (not hand-listed) and derived targets attached."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        raw = con.execute(
            """
            SELECT s.config_json, v.gate_results, v.decision, s.selection_mode
            FROM verdicts v
            JOIN submissions s ON s.config_hash = v.config_hash
            WHERE v.measurement_basis = 'fullhist_refit'
            """
        ).fetchall()
    finally:
        con.close()

    # Discover candidate metric names from the data itself.
    discovered: set[str] = set()
    for _, gate_results, _, _ in raw[:2000]:
        if gate_results is None:
            continue
        d = gate_results if isinstance(gate_results, dict) else json.loads(gate_results)
        discovered.update(d.keys())
    metrics = sorted(discovered - _STRUCTURALLY_CONSTANT)

    recs: list[dict[str, Any]] = []
    for cfg_json, gate_results, decision, arm in raw:
        try:
            cfg = json.loads(cfg_json)
        except (json.JSONDecodeError, TypeError):
            continue
        rec: dict[str, Any] = {
            "cell": _cell_key(cfg),
            "f": _features(cfg),
            "arm": arm,
            "component": 1.0 if decision == "component" else 0.0,
            "n_gates_passed": _gates_passed(gate_results),
        }
        ok = True
        for m in metrics:
            v = _gate_value(gate_results, m)
            if v is None:
                ok = False
                break
            rec[m] = -v if m in _LOWER_IS_BETTER else v
        if not ok or rec.get(_DECISION_METRIC) is None:
            continue
        recs.append(rec)

    # Derived composites, standardized WITHIN cell (the gate is a joint AND, so
    # `both_min_z` is the AND-shaped composite; `both_rankavg` the OR-ish one).
    by_cell: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_cell[r["cell"]].append(r)
    for rows in by_cell.values():
        cp = np.array([r[_DECISION_METRIC] for r in rows])
        wf = np.array([r.get("wf_sharpe_p25", 0.0) for r in rows])
        zc = (cp - cp.mean()) / (cp.std() + 1e-9)
        zw = (wf - wf.mean()) / (wf.std() + 1e-9)
        pc = _rank(cp) / max(len(cp) - 1, 1)
        pw = _rank(wf) / max(len(wf) - 1, 1)
        for i, r in enumerate(rows):
            r["both_min_z"] = float(min(zc[i], zw[i]))
            r["both_rankavg"] = float((pc[i] + pw[i]) / 2)

    targets = [m for m in metrics if m not in _NON_QUALITY]
    targets += ["component", "n_gates_passed", "both_min_z", "both_rankavg"]
    return recs, targets


def _run_a(
    recs: list[dict[str, Any]],
    targets: list[str],
    by_cell: dict[tuple[Any, ...], list[dict[str, Any]]],
    fat: list[tuple[Any, ...]],
    rng: np.random.RandomState,
) -> None:
    """Powered read: per-cell learnability + realized-outcome alignment."""
    print(
        f"\n=== RUN A: per-cell learnability + alignment ({len(fat)} cells, n>={_MIN_CELL_N}) ==="
    )
    print("LEARNABILITY: cells where OOS IC beats its shuffled null95; median IC across cells.")
    print("ALIGNMENT: rank by each target's model, take top decile WITHIN cell,")
    print("           then measure the REALIZED cpcv of those picks.\n")

    base_c = np.array([r[_DECISION_METRIC] for r in recs])
    hdr = (
        f"{'target':>28} {'cells>null':>11} {'medIC':>7} | "
        f"{'top10% cpcv med':>15} {'p90':>7} {'frac>=1.0':>10}"
    )
    print(hdr)
    print(
        f"{'(baseline: no model)':>28} {'-':>11} {'-':>7} | "
        f"{float(np.median(base_c)):>15.3f} {float(np.percentile(base_c, 90)):>7.3f} "
        f"{float(np.mean(base_c >= 1.0)):>9.1%}"
    )

    summary: list[tuple[str, int, float, float, float, float]] = []
    for t in targets:
        ics: list[float] = []
        beat = 0
        sel_cpcv: list[float] = []
        for cell in fat:
            rows = by_cell[cell]
            y_raw = [r.get(t) for r in rows]
            if any(v is None for v in y_raw):
                continue
            y = np.array(y_raw, dtype=float)
            if y.std() < 1e-9:
                continue
            x = _matrix(rows, _feature_keys(rows))
            if x is None:
                continue
            ic, null95, pred = _oos_ic_vs_null(x, y, rng)
            ics.append(ic)
            beat += int(ic > null95)
            k = max(1, int(_TOP_FRAC * len(rows)))
            top = np.argsort(-pred)[:k]
            sel_cpcv.extend(rows[i][_DECISION_METRIC] for i in top)
        if not ics or not sel_cpcv:
            continue
        arr = np.array(sel_cpcv)
        summary.append(
            (
                t,
                beat,
                float(np.median(ics)),
                float(np.median(arr)),
                float(np.percentile(arr, 90)),
                float(np.mean(arr >= 1.0)),
            )
        )

    for t, beat, med_ic, med_c, p90_c, frac in sorted(summary, key=lambda s: -s[3]):
        print(
            f"{t:>28} {f'{beat}/{len(fat)}':>11} {med_ic:>7.3f} | "
            f"{med_c:>15.3f} {p90_c:>7.3f} {frac:>9.1%}"
        )


def _run_b(honest: list[dict[str, Any]], targets: list[str], rng: np.random.RandomState) -> None:
    """Uncontaminated tie-break: honest arm only, pooled, within-cell demeaned."""
    print("\n=== RUN B: HONEST ARM only, pooled + within-cell demeaned (TIE-BREAK) ===")
    hb: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in honest:
        hb[r["cell"]].append(r)
    use = [r for rows in hb.values() if len(rows) >= _MIN_HONEST_CELL_N for r in rows]
    n_cells = sum(1 for rows in hb.values() if len(rows) >= _MIN_HONEST_CELL_N)
    print(f"rows: {len(use)} across {n_cells} cells (floor n>={_MIN_HONEST_CELL_N})\n")
    if len(use) < 60:
        print("  too thin for a Run B read -- accrue more honest arm.")
        return

    x = _matrix(use, _feature_keys(use))
    if x is None:
        print("  no usable features.")
        return
    cells_ = np.array([str(r["cell"]) for r in use])
    print(f"{'target':>28} {'OOS IC':>8} {'null95':>8}  verdict")
    rows_b: list[tuple[str, float, float]] = []
    for t in targets:
        y_raw = [r.get(t) for r in use]
        if any(v is None for v in y_raw):
            continue
        y = np.array(y_raw, dtype=float)
        for c in set(cells_.tolist()):
            m = cells_ == c
            y[m] = y[m] - y[m].mean()
        if y.std() < 1e-9:
            continue
        ic, null95, _ = _oos_ic_vs_null(x, y, rng)
        rows_b.append((t, ic, null95))
    for t, ic, null95 in sorted(rows_b, key=lambda s: -(s[1] - s[2])):
        print(f"{t:>28} {ic:>8.3f} {null95:>8.3f}  {'CLEARS' if ic > null95 else 'fails null'}")

    print("\nDecision rule: a target must CLEAR its null on Run B (uncontaminated) AND")
    print("lift realized cpcv on Run A alignment. Learnable-but-flat = the D155 trap.")


def run(db_path: Path) -> int:
    recs, targets = load(db_path)
    honest = [r for r in recs if r["arm"] == "prefilter_sample"]
    counts = f"honest-lane rows: {len(recs)}   honest ARM rows: {len(honest)}"
    print(f"{counts}   candidates: {len(targets)}")

    by_cell: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_cell[r["cell"]].append(r)
    fat = [c for c in by_cell if len(by_cell[c]) >= _MIN_CELL_N]

    rng = np.random.RandomState(0)
    _run_a(recs, targets, by_cell, fat, rng)
    _run_b(honest, targets, rng)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", type=Path, default=_DEFAULT_SNAPSHOT, help="forge.db SNAPSHOT path")
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"snapshot not found: {args.db}\n  cp {_LIVE_DB} {args.db}", file=sys.stderr)
        return 2
    return run(args.db)


if __name__ == "__main__":
    raise SystemExit(main())
