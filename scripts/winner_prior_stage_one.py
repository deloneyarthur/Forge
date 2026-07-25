"""Winner-prior STAGE-ONE re-derivation, hyperparameter sweep, and gate-rate read.

WHY THIS EXISTS. The winner-neighborhood prior was PARKED on 2026-07-24 at an effect of
+0.0087 (p90, honest ARM) needing ~20,000/arm ~= 57 days of accrual to detect. Both its
fit and its judge ran on `measurement_basis='fullhist_refit'` = STAGE TWO, whose
admission is the refit TRIGGER -- a function of config quality, therefore a COLLIDER.
Q59 then proved (D337) that this conditioning can SIGN-FLIP a parameter effect: rank_k=5
measured +0.0776 on stage two and -0.1712 on stage one, we shipped it in v50 and reverted
it in v51 the next night. So the parking number was untrustworthy in both directions, AND
its "~57 days" power problem was an artifact of measuring on a 302-row conditioned slice
while ~234k unconditioned rows sat in the same table.

WHAT IT ANSWERS. Four things the original probes never did:
  A. The effect on STAGE ONE (all decided clean-era verdicts, unselected), with the same
     read on STAGE TWO through identical code so the collider delta is visible.
  B. The four hyperparameters, none of which had ever been varied off their defaults
     (exploration_floor=0.25, max_weight=3.0, shrinkage_n=10.0, n_bins=4).
  C. Bootstrap CI + split stability -- one point estimate at one cut is not a verdict.
  D. The decision metric: does the prior raise the RATE of gate-clearing configs? The
     p90 and the median disagree in sign, so only the gate rate settles it.

RESULT (2026-07-25, n=233,829): REFUTED. The prior lifts the body of the distribution
and compresses the tail -- monotone from +0.0129 at q25 to -0.0326 at q99 -- and cuts the
share of configs clearing cpcv 1.5 to 0.64x. Hyperparameters are inert (all 64 combos
within 0.002). See STATUS 2026-07-25 and D338.

Read-only against a SNAPSHOT. Never the live RW-locked DB (`docs/tasks/investigate-live.md`):

    cp ~/forge_data/forge.db ~/.cache/rv/wp.db   # real disk, NOT tmpfs; delete when done
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT, is_ve_ghost_label
from forge.ranking.winner_prior import fit_winner_prior

_LIVE_DB = Path.home() / "forge_data" / "forge.db"
_TARGET_GATE = "cpcv_sharpe_p25"
_HONEST_ARM = "prefilter_sample"
_HAND_PINNED_DIRECTIONALS = frozenset({"residual_momentum", "momentum"})
_TRAINED_THROUGH = datetime(2026, 7, 25, tzinfo=UTC)


def _gate_value(gate_results: object, key: str) -> float | None:
    if gate_results is None:
        return None
    if isinstance(gate_results, dict):
        d: dict[str, Any] = gate_results
    elif isinstance(gate_results, (str, bytes, bytearray)):
        try:
            d = json.loads(gate_results)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        return None
    entry = d.get(key)
    if isinstance(entry, dict):
        v = entry.get("value")
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    if isinstance(entry, (int, float)) and not isinstance(entry, bool):
        return float(entry)
    return None


def _dte_bucket(dte_max: float | None) -> str:
    d = dte_max or 0
    return "swing_short" if d <= 25 else "swing_mid" if d <= 55 else "swing_long"


def _cell_and_params(cfg: dict[str, Any]) -> tuple[tuple[str, ...], dict[str, float]]:
    """Verbatim from `winner_prior_shadow.py` so the two reads stay comparable."""
    combiner = cfg.get("combiner") or {}
    xs = "xsect" if combiner.get("type") == "cross_sectional_rank" else "named"
    directional = ""
    regimes: list[str] = []
    params: dict[str, float] = {}
    for sig in cfg.get("signals", []):
        role = sig.get("role")
        inds = tuple(sig.get("indicators", []))
        if role == "directional":
            directional = inds[0] if inds else ""
        elif role == "regime":
            regimes.extend(inds)
        for k, v in (sig.get("params") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                params[f"{role}_{k}"] = float(v)

    selector = cfg.get("selector") or {}
    if isinstance(selector.get("delta_target"), (int, float)):
        params["delta_target"] = float(selector["delta_target"])
    sizer = cfg.get("sizer") or {}
    if isinstance(sizer.get("per_trade_risk_pct"), (int, float)):
        params["per_trade_risk_pct"] = float(sizer["per_trade_risk_pct"])
    if isinstance(combiner.get("rank_k"), (int, float)):
        params["rank_k"] = float(combiner["rank_k"])
    for ex in cfg.get("exits", []):
        exit_id = ex.get("id")
        for k, v in (ex.get("params") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                params[f"exit_{exit_id}_{k}"] = float(v)

    cell = (
        str(cfg.get("hypothesis")),
        directional,
        "+".join(sorted(regimes)),
        xs,
        _dte_bucket(selector.get("dte_max")),
    )
    return cell, params


def load_observations(db_path: Path) -> list[dict[str, Any]]:
    """EVERY decided clean-era verdict -- no `measurement_basis` filter.

    That absence IS the point: stage one is the unselected population. Each row keeps its
    `basis` so the stage-two subset can be re-cut through identical code, which is the
    only way to attribute a difference to the conditioning rather than to the code.
    """
    cut = CLEAN_ERA_LABEL_CUT
    if cut.tzinfo is not None:
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        raw = con.execute(
            """
            SELECT s.config_json, v.gate_results, s.selection_mode,
                   v.decided_at, v.measurement_basis
            FROM verdicts v
            JOIN submissions s ON s.config_hash = v.config_hash
            WHERE v.decided_at >= ?
            ORDER BY v.decided_at
            """,
            [cut],
        ).fetchall()
    finally:
        con.close()

    out: list[dict[str, Any]] = []
    for cfg_json, gate_results, arm, decided_at, basis in raw:
        try:
            cfg = json.loads(cfg_json)
        except (json.JSONDecodeError, TypeError):
            continue
        # D290 ghost-era ve labels are fiction -- the same cut the trainer applies.
        da = decided_at if decided_at.tzinfo else decided_at.replace(tzinfo=UTC)
        if is_ve_ghost_label(cfg.get("hypothesis"), da):
            continue
        outcome = _gate_value(gate_results, _TARGET_GATE)
        if outcome is None:
            continue
        cell, params = _cell_and_params(cfg)
        if not params:
            continue
        out.append(
            {
                "cell": cell,
                "params": params,
                "outcome": outcome,
                "arm": arm,
                "decided_at": decided_at,
                "basis": basis,
            }
        )
    return out


def _config_weight(prior: Any, obs: dict[str, Any]) -> float:
    """A config's draw multiplier: the PRODUCT over its params, because the sampler draws
    each one and the joint density compounds. Products can collapse effective sample
    size, which is why every read below reports ESS."""
    m = 1.0
    for name, value in obs["params"].items():
        m *= prior.weight(obs["cell"], name, value)
    return m


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    return float(np.interp(q, np.cumsum(w) / np.sum(w), v))


def _exempt(observations: list[dict[str, Any]]) -> set[tuple[str, ...]]:
    return {o["cell"] for o in observations if o["cell"][1] in _HAND_PINNED_DIRECTIONALS}


def temporal_split(
    rows: list[dict[str, Any]], frac: float = 0.7
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda o: o["decided_at"])
    cut = int(len(ordered) * frac)
    return ordered[:cut], ordered[cut:]


def _fit_and_weight(
    train: list[dict[str, Any]], test: list[dict[str, Any]], exempt: set[tuple[str, ...]], **kw: Any
) -> tuple[np.ndarray, np.ndarray]:
    prior = fit_winner_prior(train, trained_through=_TRAINED_THROUGH, exempt_cells=exempt, **kw)
    v = np.array([o["outcome"] for o in test], dtype=float)
    w = np.array([_config_weight(prior, o) for o in test], dtype=float)
    return v, w


def _deltas(v: np.ndarray, w: np.ndarray) -> dict[str, float]:
    ess = float(w.sum() ** 2 / np.sum(w**2))
    return {
        "d_med": _weighted_quantile(v, w, 0.50) - float(np.median(v)),
        "d_p90": _weighted_quantile(v, w, 0.90) - float(np.percentile(v, 90)),
        "d_mean": float(np.sum(w * v) / np.sum(w) - v.mean()),
        "ess_frac": ess / len(v),
    }


_SPLITS = (0.5, 0.6, 0.7, 0.8, 0.9)
_ROW = "{:>+9.4f}"


def _arm_a(rows: list[dict[str, Any]], two: list[dict[str, Any]], ex: set[tuple[str, ...]]) -> None:
    print("\n=== A. DEFAULTS: STAGE ONE vs STAGE TWO through identical code ===")
    print(f"{'population':<28} {'n_fit':>9} {'n_judge':>9} {'d_med':>9} {'d_p90':>9} {'ESS%':>7}")
    for name, (a, b) in (
        ("STAGE ONE (unselected)", temporal_split(rows)),
        ("STAGE TWO (the parked read)", temporal_split(two)),
    ):
        if len(b) < 40:
            continue
        d = _deltas(*_fit_and_weight(a, b, ex))
        print(
            f"{name:<28} {len(a):>9,} {len(b):>9,} "
            f"{d['d_med']:>+9.4f} {d['d_p90']:>+9.4f} {d['ess_frac']:>6.1%}"
        )


def _arm_b(tr: list[dict[str, Any]], te: list[dict[str, Any]], ex: set[tuple[str, ...]]) -> None:
    print("\n=== B. HYPERPARAMETER SWEEP ON STAGE ONE (never swept before) ===")
    print(
        f"{'bins':>5} {'shrink':>7} {'maxw':>6} {'floor':>6} {'d_med':>9} {'d_p90':>9} {'ESS%':>7}"
    )
    best: tuple[float, tuple[Any, ...]] | None = None
    for n_bins in (3, 4, 6, 8):
        for shrinkage_n in (5.0, 10.0, 25.0, 50.0):
            for max_weight in (1.5, 3.0):
                for floor in (0.25, 0.5):
                    d = _deltas(
                        *_fit_and_weight(
                            tr,
                            te,
                            ex,
                            n_bins=n_bins,
                            shrinkage_n=shrinkage_n,
                            max_weight=max_weight,
                            exploration_floor=floor,
                        )
                    )
                    print(
                        f"{n_bins:>5} {shrinkage_n:>7.0f} {max_weight:>6.1f} {floor:>6.2f} "
                        f"{d['d_med']:>+9.4f} {d['d_p90']:>+9.4f} {d['ess_frac']:>6.1%}"
                    )
                    if best is None or d["d_p90"] > best[0]:
                        best = (d["d_p90"], (n_bins, shrinkage_n, max_weight, floor))
    if best:
        print(f"\nbest d_p90 across all 64 combos: {best[0]:+.4f} at {best[1]}")


def _arm_c(
    rows: list[dict[str, Any]], ex: set[tuple[str, ...]], v: np.ndarray, w: np.ndarray, n: int
) -> None:
    print("\n=== C. SPLIT STABILITY + BOOTSTRAP ===")
    print(f"{'fit frac':>9} {'n_judge':>9} {'d_med':>9} {'d_p90':>9} {'d_p99':>9}")
    for frac in _SPLITS:
        a, b = temporal_split(rows, frac)
        vv, ww = _fit_and_weight(a, b, ex)
        print(
            f"{frac:>9.1f} {len(b):>9,} "
            + " ".join(
                _ROW.format(_weighted_quantile(vv, ww, q) - float(np.percentile(vv, q * 100)))
                for q in (0.50, 0.90, 0.99)
            )
        )

    rng = np.random.RandomState(0)
    boot: dict[str, list[float]] = {"d_med": [], "d_p90": []}
    for _ in range(n):
        idx = rng.randint(0, len(v), len(v))
        vv, ww = v[idx], w[idx]
        boot["d_med"].append(_weighted_quantile(vv, ww, 0.50) - float(np.median(vv)))
        boot["d_p90"].append(_weighted_quantile(vv, ww, 0.90) - float(np.percentile(vv, 90)))
    print(f"\nbootstrap at the 70/30 cut ({n} resamples of the judge set):")
    for name, draws in boot.items():
        arr = np.asarray(draws, dtype=float)
        lo, hi = np.percentile(arr, [2.5, 97.5])
        pos = float(np.mean(arr > 0))
        print(f"  {name}: {arr.mean():+.4f}  CI [{lo:+.4f}, {hi:+.4f}]  P(>0) = {pos:.1%}")


def _arm_de(
    rows: list[dict[str, Any]], ex: set[tuple[str, ...]], v: np.ndarray, w: np.ndarray
) -> None:
    print("\n=== D. WHERE IT ACTS -- outcome quantiles, uniform vs prior-weighted ===")
    print(f"{'q':>6} {'uniform':>10} {'weighted':>10} {'delta':>10}")
    for q in (0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99):
        u, x = float(np.percentile(v, q * 100)), _weighted_quantile(v, w, q)
        print(f"{q:>6.2f} {u:>10.4f} {x:>10.4f} {x - u:>+10.4f}")

    print("\n=== E. THE DECISION METRIC -- share clearing the gate, at every split ===")
    print("(the median and the p90 disagree in sign, so only this settles it)")
    print(f"{'fit frac':>9} {'>=1.5 uni':>10} {'>=1.5 wtd':>10} {'rel':>7} {'>=1.0 rel':>10}")
    for frac in _SPLITS:
        a, b = temporal_split(rows, frac)
        vv, ww = _fit_and_weight(a, b, ex)
        cells = [f"{frac:>9.1f}"]
        for gate in (1.5, 1.0):
            u = float(np.mean(vv >= gate))
            x = float(np.sum(ww * (vv >= gate)) / np.sum(ww))
            rel = x / u if u > 0 else float("nan")
            cells.append(
                f" {u:>10.4%} {x:>10.4%} {rel:>6.2f}x" if gate == 1.5 else f" {rel:>9.2f}x"
            )
        print("".join(cells))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True, help="snapshot path, NOT the live DB")
    ap.add_argument("--bootstrap", type=int, default=500)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"snapshot not found: {args.db}\n  cp {_LIVE_DB} {args.db}", file=sys.stderr)
        return 2

    rows = load_observations(args.db)
    two = [o for o in rows if o["basis"] == "fullhist_refit"]
    arm = len([o for o in two if o["arm"] == _HONEST_ARM])
    ex = _exempt(rows)
    print(f"STAGE ONE (unselected)          n = {len(rows):,}")
    print(f"STAGE TWO (fullhist_refit lane) n = {len(two):,}   of which honest ARM n = {arm:,}")
    print(f"cells {len({o['cell'] for o in rows}):,}   hand-pinned held neutral {len(ex):,}")

    tr, te = temporal_split(rows)
    v, w = _fit_and_weight(tr, te, ex)
    _arm_a(rows, two, ex)
    _arm_b(tr, te, ex)
    _arm_c(rows, ex, v, w, args.bootstrap)
    _arm_de(rows, ex, v, w)
    print("\nreference: the PARKED stage-two honest-arm read was d_p90 = +0.0087")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
