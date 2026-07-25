"""Pre-build gate for the winner-neighborhood-priors generation lever.

WHY this exists: before spending search budget on a learned prior that concentrates
the sampler draw toward the param neighborhoods of honest gate-passers
(`docs/proposals/v50-winner-neighborhood-priors.md`), we must know the target is
real signal and not noise we would overfit. This script answers one question with
data we already have:

    Within a fixed cell (hypothesis x directional x regime x xsect x dte-bucket), do
    a config's PARAMS predict its honest `cpcv_sharpe_p25` OUT OF SAMPLE, above a
    shuffled-label null, AFTER removing the dte features that merely proxy the bucket
    (which the sampler's existing bucket weights already steer)?

If yes in the fat honest cells, the winner-prior is fitting real, marginal structure
and the prototype is justified. If the OOS IC collapses to the null, param-
neighborhood concentration is noise in that cell and we do not build (or keep
hand-tuning only the cells that survive).

Honest bounds this probe does NOT establish (see the proposal S6): (1) it measures
within-cell RANK of cpcv, never whether concentration crosses the 1.5 promotion gate
(the magnitude wall stands); (2) it cannot separate "automatable signal" from the
v36/v38/v40 hand-tuned priors already baked into these cells -- only the honest-arm
before/after shadow-diff settles marginal value over hand-tuning.

The training/probe population is `measurement_basis='fullhist_refit'` -- the honest,
floor-anchored slice, biased high (would-be-components) but exactly the population a
winner-prior trains on. Never the 5yr standard_window screen.

Reads a SNAPSHOT of forge.db, never the live RW-locked DB (standing pitfall,
`docs/tasks/investigate-live.md`). Snapshot to real disk, not tmpfs:

    cp ~/forge_data/forge.db ~/.cache/rv/forge_snap.db   # ~6s, delete when done

⚠️ COLLIDER WARNING — READ BEFORE TRUSTING ANY PARAMETER EFFECT FROM THIS SCRIPT.
`measurement_basis='fullhist_refit'` is STAGE TWO, and stage-two admission is the refit
TRIGGER — a function of config quality. Conditioning on it is a COLLIDER, so a parameter
correlated with trigger probability gets a biased and sometimes SIGN-FLIPPED estimate.
This is not hypothetical: on 2026-07-24 a rank_k=5 effect measured +0.0776 here and
-0.1712 on stage one (same metric, same configs, only the conditioning differs), we
shipped the bias in v50, and it had to be reverted in v51 the next night (D337). Berkson's
paradox. Stratifying WITHIN this population does NOT help — the collider is at its
boundary.

RULE: parameter effects are estimated on STAGE ONE (all decided verdicts, unselected)
ONLY. The stage-two honest arm remains valid as a yardstick for grammar-VERSION deltas,
because the conditioning is identical on both sides of that comparison. Those are
different uses; do not conflate them.
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

# Grammar dte-bucket boundaries (swing_short <=25, swing_mid <=55, else swing_long),
# used to fold the bucket into the cell key so dte variation WITHIN a bucket is the
# only dte signal a feature can carry. Approximate boundaries are sufficient here --
# the point is to separate cross-bucket (cell-level, already steered) from
# within-bucket param signal, not to reproduce the exact §3.5 S4 snap.
_SHORT_MAX_DTE = 25
_MID_MAX_DTE = 55

_MIN_CELL_N = 80  # below this, per-cell OOS IC is too noisy to read
_N_SHUFFLES = 40  # null distribution size; ICs sit far above null95 so 40 suffices
_RIDGE_ALPHA = 10.0
_SIGNAL_IC_FLOOR = 0.05  # an IC must clear both null95 AND this to count as signal


def _dte_bucket(dte_max: float | None) -> str:
    d = dte_max or 0
    if d <= _SHORT_MAX_DTE:
        return "short"
    if d <= _MID_MAX_DTE:
        return "mid"
    return "long"


def _cpcv_p25(gate_results: object) -> float | None:
    """The honest gate metric from a verdict's `gate_results` blob, tolerant of the
    two shapes seen in the ledger ({gate: value} and {gate: {value: ...}})."""
    if gate_results is None:
        return None
    if isinstance(gate_results, dict):
        d: dict[str, Any] = gate_results
    elif isinstance(gate_results, (str, bytes, bytearray)):
        d = json.loads(gate_results)
    else:
        return None
    v = d.get("cpcv_sharpe_p25")
    if isinstance(v, dict):
        v = v.get("value", v.get("observed"))
    return float(v) if isinstance(v, (int, float)) else None


def _cell_key(cfg: dict[str, Any]) -> tuple[Any, ...]:
    """The orthogonality unit the winner-prior operates inside: everything the
    sampler already steers at the cell level, PLUS the dte-bucket. Any param signal
    measured within this key is marginal over cell-level steering by construction."""
    hyp = cfg.get("hypothesis")
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
    return (hyp, directional, tuple(sorted(regimes)), xs, bucket)


def _features(cfg: dict[str, Any]) -> dict[str, float | None]:
    """The intra-cell param surface: selector band, sizer risk, combiner breadth/
    direction, exit duration + class flags, and every numeric signal threshold. These
    are the knobs the cell-level weights do NOT touch -- the winner-prior's domain."""
    f: dict[str, float | None] = {}
    sel = cfg.get("selector") or {}
    for k in ("delta_target", "dte_min", "dte_max"):
        f[k] = sel.get(k)
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


def _ridge_weights(x: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    p = x.shape[1]
    return np.linalg.solve(x.T @ x + alpha * np.eye(p), x.T @ y)


def _oos_ic(x: np.ndarray, y: np.ndarray, rng: np.random.RandomState) -> float:
    """5-fold out-of-sample rank-IC: predict each held-out fold from the other four,
    Spearman the pooled OOS predictions against truth. A constant (cell-mean) model
    scores 0, so any positive value is signal marginal over the cell level."""
    n = len(y)
    folds = np.array_split(rng.permutation(n), 5)
    pred = np.zeros(n)
    for i in range(5):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(5) if j != i])
        w = _ridge_weights(x[train], y[train] - y[train].mean(), _RIDGE_ALPHA)
        pred[test] = x[test] @ w + y[train].mean()
    return _spearman(pred, y)


def _matrix(
    rows: list[tuple[dict[str, float | None], float]], keys: list[str]
) -> tuple[np.ndarray, np.ndarray] | None:
    """Standardized feature matrix + target over `keys`, median-imputed, zero-variance
    columns dropped. None if no usable column survives."""
    y = np.array([yy for _, yy in rows])
    x = np.array(
        [
            [(f.get(k) if isinstance(f.get(k), (int, float)) else np.nan) for k in keys]
            for f, _ in rows
        ],
        dtype=float,
    )
    for j in range(x.shape[1]):
        col = x[:, j]
        med = np.nanmedian(col)
        col[np.isnan(col)] = 0.0 if np.isnan(med) else med
        x[:, j] = col
    keep = [j for j in range(x.shape[1]) if np.std(x[:, j]) > 1e-9]
    if not keep:
        return None
    x = x[:, keep]
    return (x - x.mean(0)) / (x.std(0) + 1e-9), y


def probe(db_path: Path) -> list[dict[str, Any]]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        raw = con.execute(
            """
            SELECT s.config_json, v.gate_results
            FROM verdicts v
            JOIN submissions s ON s.config_hash = v.config_hash
            WHERE v.measurement_basis = 'fullhist_refit'
            """
        ).fetchall()
    finally:
        con.close()

    by_cell: dict[tuple[Any, ...], list[tuple[dict[str, float | None], float]]] = defaultdict(list)
    for cfg_json, gate_results in raw:
        try:
            cfg = json.loads(cfg_json)
            y = _cpcv_p25(gate_results)
            if y is None:
                continue
            by_cell[_cell_key(cfg)].append((_features(cfg), y))
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    rng = np.random.RandomState(0)
    results: list[dict[str, Any]] = []
    for cell in sorted(by_cell, key=lambda c: -len(by_cell[c])):
        rows = by_cell[cell]
        if len(rows) < _MIN_CELL_N:
            continue
        all_keys = [
            k
            for k in {k for f, _ in rows for k in f}
            if sum(1 for f, _ in rows if isinstance(f.get(k), (int, float))) >= 0.6 * len(rows)
        ]
        full = _matrix(rows, all_keys)
        no_dte = _matrix(rows, [k for k in all_keys if k not in ("dte_min", "dte_max")])
        if full is None or no_dte is None:
            continue
        x_full, y_target = full
        x_nodte, _ = no_dte
        ic_full = _oos_ic(x_full, y_target, rng)
        ic_nodte = _oos_ic(x_nodte, y_target, rng)
        null = sorted(_oos_ic(x_nodte, rng.permutation(y_target), rng) for _ in range(_N_SHUFFLES))
        null95 = null[int(0.95 * len(null))]
        hyp, directional, regimes, xs, bucket = cell
        results.append(
            {
                "hypothesis": hyp,
                "directional": directional,
                "regimes": list(regimes),
                "xsect": xs,
                "bucket": bucket,
                "n": len(rows),
                "ic_full": round(ic_full, 3),
                "ic_no_dte": round(ic_nodte, 3),
                "null95": round(null95, 3),
                "marginal_signal": bool(ic_nodte > null95 and ic_nodte > _SIGNAL_IC_FLOOR),
            }
        )
    return results


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", type=Path, default=_DEFAULT_SNAPSHOT, help="forge.db SNAPSHOT path")
    ap.add_argument("--json", type=Path, default=None, help="also write results as JSON here")
    args = ap.parse_args()

    if args.db == _LIVE_DB:
        print(
            "refuse: that is the live RW-locked DB. Snapshot first (see module docstring).",
            file=sys.stderr,
        )
        return 2
    if not args.db.exists():
        print(f"snapshot not found: {args.db}\n  cp {_LIVE_DB} {args.db}", file=sys.stderr)
        return 2

    results = probe(args.db)
    cols = f"{'cell (hyp/directional/bucket)':46} {'n':>4} {'IC_full':>7} {'IC_noDTE':>8}"
    print("Within-cell OOS param->cpcv rank-IC. IC_noDTE (dte dropped) is the marginal test.\n")
    print(f"{cols} {'null95':>7}  signal")
    marginal = 0
    for r in results:
        label = f"{r['hypothesis'][:11]}/{r['directional'][:20]}/{r['bucket']}"[:46]
        flag = "SIGNAL" if r["marginal_signal"] else "~null"
        marginal += r["marginal_signal"]
        stats = f"{r['ic_full']:>7.3f} {r['ic_no_dte']:>8.3f} {r['null95']:>7.3f}"
        print(f"{label:46} {r['n']:>4} {stats}  {flag}")
    kept = f"{marginal}/{len(results)}"
    print(f"\ncells (n>={_MIN_CELL_N}): {kept} keep marginal param signal after dropping dte")

    if args.json is not None:
        args.json.write_text(json.dumps(results, indent=2))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
