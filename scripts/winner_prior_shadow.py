"""Fit the winner-neighborhood prior on the honest slice and SHADOW-DIFF it.

This is the gate the proposal puts before any enumeration change
(`generation-model-levers.md` §6.1 discipline, restated in
`docs/proposals/v50-winner-neighborhood-priors.md` §8 step 2): build the artifact, show
exactly how it would reshape intra-cell param draws, and decide on that evidence —
BEFORE touching the sampler. Nothing here writes to the sampler, the grammar, or the
daemon. It reads a snapshot and writes an artifact.

Two things it reports:

  1. WHAT THE PRIOR LEARNED - per (cell, param), the fitted bin multipliers, so a human
     can check them against the hand-tuned priors we already ship. If the prior says
     "MR timers want 8-12 bars" it has independently rediscovered D291, which is the
     strongest available evidence it is learning real structure rather than noise.

  2. WHAT IT WOULD DO - the shadow diff, measured the way the proposal pre-registers
     it: CONFIG-level and OUT-OF-SAMPLE. A config's draw weight is the PRODUCT of its
     per-param weights (the sampler draws each param, so the joint density compounds);
     the prior is fit on half the honest rows and the reweighted distribution is read
     on the held-out half. Headline is the **p90** -- "can the grammar throw a
     promotion-grade extreme without the ranker's help" -- because the centre drifts on
     cell mix. Effective sample size is reported beside it: a lift bought by collapsing
     the draw onto a handful of configs is not a lift, it is lost exploration.

     NB a per-param MARGINAL read understates this by ~10x. Weighting one param at a
     time ignores that the sampler draws them all, so the marginal shift is not the
     quantity the sampler would actually realize. Reported below the judge, labelled.

HONEST BOUND, restated so the output is not over-read: this reorders draws inside a
distribution whose ceiling is sub-gate (0/302 honest configs clear cpcv 1.5). A
positive shift here is a component-RATE / pool-quality claim, NOT a promotion claim --
a p90 lift of a few hundredths against a ~1.15 gap to the gate does not approach it.
The binding read remains the pre-registered post-ship `prefilter_sample` comparison.

    cp ~/forge_data/forge.db ~/.cache/rv/forge_snap.db   # ~6s, delete when done
    uv run python scripts/winner_prior_shadow.py --write-artifact
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from forge.core.clock import utc_now
from forge.ranking.winner_prior import fit_winner_prior, save_winner_prior

_DEFAULT_SNAPSHOT = Path("~/.cache/rv/forge_snap.db").expanduser()
_LIVE_DB = Path("~/forge_data/forge.db").expanduser()
_DEFAULT_MODELS_DIR = Path("~/forge_data/models").expanduser()

# The honest gate metric — the target the sweep settled and Crucible endorsed.
_TARGET_GATE = "cpcv_sharpe_p25"

# Cells whose params an operator already pinned by hand; the prior must not re-tilt
# them on the same evidence (spec §9c). Keyed on the directional id, which is how the
# sampler scopes each pin: D276 (resid params/gates), D291+D282 (MR/trend timers via
# the capitulation carve-out).
_HAND_PINNED_DIRECTIONALS = frozenset({"residual_momentum", "momentum"})

_MIN_CELL_N = 30  # below this a cell's own mean is too noisy to tilt against


def _gate_value(gate_results: object, key: str) -> float | None:
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


def _dte_bucket(dte_max: float | None) -> str:
    d = dte_max or 0
    return "swing_short" if d <= 25 else "swing_mid" if d <= 55 else "swing_long"


def _cell_and_params(cfg: dict[str, Any]) -> tuple[tuple[str, ...], dict[str, float]]:
    """The cell the prior operates inside, and the intra-cell params it may reshape.

    Params deliberately EXCLUDE dte_min/dte_max: those proxy the bucket, which is part
    of the cell key and already steered by the sampler's bucket weights. Reshaping them
    here would double-count cell-level steering.
    """
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
        if ex.get("type") == "time_stop":
            n_bars = (ex.get("params") or {}).get("n_bars", ex.get("n_bars"))
            if isinstance(n_bars, (int, float)) and not isinstance(n_bars, bool):
                params["time_stop_n_bars"] = float(n_bars)

    cell = (
        str(cfg.get("hypothesis")),
        directional,
        "+".join(sorted(regimes)),
        xs,
        _dte_bucket(selector.get("dte_max")),
    )
    return cell, params


def load_observations(db_path: Path) -> list[dict[str, Any]]:
    """Honest-lane observations only: `measurement_basis='fullhist_refit'` with a real
    cpcv value. Never the 5yr `standard_window` screen (spec §2)."""
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

    out: list[dict[str, Any]] = []
    for cfg_json, gate_results in raw:
        try:
            cfg = json.loads(cfg_json)
        except (json.JSONDecodeError, TypeError):
            continue
        outcome = _gate_value(gate_results, _TARGET_GATE)
        if outcome is None:
            continue
        cell, params = _cell_and_params(cfg)
        if not params:
            continue
        out.append({"cell": cell, "params": params, "outcome": outcome})
    return out


def _expected_outcome_shift(
    observations: list[dict[str, Any]], prior: Any, param: str, cell: tuple[str, ...]
) -> tuple[float, float, int] | None:
    """Uniform vs prior-weighted expected outcome for ONE (cell, param) — the MARGINAL
    view, useful for eyeballing individual params against the hand-tuned priors.

    Understates the realized effect by ~10x: the sampler draws every param, so what it
    actually realizes is the compounded config-level weight (`_config_weight`).
    """
    rows = [o for o in observations if o["cell"] == cell and param in o["params"]]
    if len(rows) < _MIN_CELL_N:
        return None
    uniform = sum(o["outcome"] for o in rows) / len(rows)
    weights = [prior.weight(cell, param, o["params"][param]) for o in rows]
    total = sum(weights)
    if total <= 0:
        return None
    weighted = sum(w * o["outcome"] for w, o in zip(weights, rows, strict=True)) / total
    return uniform, weighted, len(rows)


def _config_weight(prior: Any, obs: Mapping[str, Any]) -> float:
    """A config's overall draw multiplier: the product over its params, because the
    sampler draws each param and the joint density compounds."""
    m = 1.0
    for name, value in obs["params"].items():
        m *= prior.weight(obs["cell"], name, value)
    return m


def _weighted_quantile(values: Sequence[float], weights: Sequence[float], q: float) -> float:
    order = np.argsort(np.asarray(values))
    v = np.asarray(values, dtype=float)[order]
    w = np.asarray(weights, dtype=float)[order]
    cum = np.cumsum(w) / np.sum(w)
    return float(np.interp(q, cum, v))


def _judge(
    observations: list[dict[str, Any]], exempt: set[tuple[str, ...]], n_splits: int = 5
) -> None:
    """The pre-registered read: fit on half, measure the reweighted distribution on the
    held-out half, report median / p90 / effective sample size."""
    print("\n=== THE JUDGE: config-level, OUT-OF-SAMPLE reweighted honest distribution ===")
    print(
        "(fit on 50% of honest rows, read on the held-out 50%; p90 is the pre-registered metric)\n"
    )
    print(f"{'split':>6} {'uni med':>9} {'wtd med':>9} {'uni p90':>9} {'wtd p90':>9} {'d_p90':>9}")
    d_med: list[float] = []
    d_p90: list[float] = []
    for seed in range(n_splits):
        # Seeded numpy RNG (not `random`): matches `target_sweep.py` and keeps the
        # split reproducible without touching the production seed hierarchy.
        idx = list(np.random.RandomState(seed).permutation(len(observations)))
        half = len(idx) // 2
        train = [observations[i] for i in idx[:half]]
        test = [observations[i] for i in idx[half:]]
        prior = fit_winner_prior(train, trained_through=utc_now(), exempt_cells=exempt)
        vals = [o["outcome"] for o in test]
        w = [_config_weight(prior, o) for o in test]
        um, wm = float(np.median(vals)), _weighted_quantile(vals, w, 0.50)
        u9, w9 = float(np.percentile(vals, 90)), _weighted_quantile(vals, w, 0.90)
        d_med.append(wm - um)
        d_p90.append(w9 - u9)
        print(f"{seed:>6} {um:>9.3f} {wm:>9.3f} {u9:>9.3f} {w9:>9.3f} {w9 - u9:>+9.4f}")
    print(f"\nmean OOS delta   median {np.mean(d_med):+.4f}   p90 {np.mean(d_p90):+.4f}")
    print(
        f"p90 lift as a share of the gap to the gate (0.351 -> 1.5): {np.mean(d_p90) / 1.149:.2%}"
    )

    full = fit_winner_prior(observations, trained_through=utc_now(), exempt_cells=exempt)
    w_all = np.array([_config_weight(full, o) for o in observations])
    w_all = w_all / w_all.sum()
    ess = 1.0 / float(np.sum(w_all**2))
    print(
        f"effective sample size of the reweighted draw: {ess:,.0f} / {len(observations):,} "
        f"({ess / len(observations):.1%} exploration retained)"
    )


def _marginal_table(observations: list[dict[str, Any]], prior: Any, top: int = 20) -> None:
    """Per-(cell, param) marginal shifts — for eyeballing individual params against the
    hand-tuned priors we already ship. NOT the judge: see `_judge`."""
    print("\n=== MARGINAL view: one param at a time (UNDERSTATES the judge by ~10x) ===")
    print("in-sample; useful only for eyeballing individual params against the hand priors")
    print(f"\n{'cell / param':58} {'n':>5} {'uniform':>8} {'prior':>8} {'delta':>8}")
    shifts: list[tuple[float, str, int]] = []
    seen: set[tuple[tuple[str, ...], str]] = set()
    for o in observations:
        for param in o["params"]:
            key = (o["cell"], param)
            if key in seen:
                continue
            seen.add(key)
            got = _expected_outcome_shift(observations, prior, param, o["cell"])
            if got is None:
                continue
            uniform, weighted, n = got
            hyp, direc, _, _, bucket = o["cell"]
            label = f"{hyp[:11]}/{direc[:16]}/{bucket[6:]}  {param}"[:58]
            shifts.append(
                (weighted - uniform, f"{label:58} {n:>5} {uniform:>8.3f} {weighted:>8.3f}", n)
            )
    shifts.sort(key=lambda s: -s[0])
    for delta, line, _ in shifts[:top]:
        print(f"{line} {delta:>+8.3f}")
    if len(shifts) > top:
        print(f"  … {len(shifts) - top} more (cell,param) pairs")
    if shifts:
        total_n = sum(n for _, _, n in shifts)
        pooled = sum(d * n for d, _, n in shifts) / total_n
        pos = sum(1 for d, _, _ in shifts if d > 0)
        print(f"\nn-weighted mean marginal delta over {len(shifts)} pairs: {pooled:+.4f}")
        print(f"pairs improved: {pos}/{len(shifts)}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", type=Path, default=_DEFAULT_SNAPSHOT, help="forge.db SNAPSHOT path")
    ap.add_argument(
        "--write-artifact",
        action="store_true",
        help="persist the fitted prior (default: shadow only, write nothing)",
    )
    ap.add_argument("--models-dir", type=Path, default=_DEFAULT_MODELS_DIR)
    args = ap.parse_args()

    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"snapshot not found: {args.db}\n  cp {_LIVE_DB} {args.db}", file=sys.stderr)
        return 2

    observations = load_observations(args.db)
    if not observations:
        print("no honest observations found", file=sys.stderr)
        return 1

    by_cell: dict[tuple[str, ...], int] = defaultdict(int)
    for o in observations:
        by_cell[o["cell"]] += 1
    exempt = {c for c in by_cell if c[1] in _HAND_PINNED_DIRECTIONALS}

    prior = fit_winner_prior(observations, trained_through=utc_now(), exempt_cells=exempt)
    print(f"honest observations: {len(observations)}   cells: {len(by_cell)}")
    print(f"hand-pinned cells held neutral: {len(exempt)}")
    print(f"fitted (cell,param) entries: {len(prior.weights)}   prior_id: {prior.prior_id}")
    print(
        f"bounds: [{prior.exploration_floor}, {prior.max_weight}]  shrinkage_n={prior.shrinkage_n}"
    )

    _judge(observations, exempt)
    _marginal_table(observations, prior)

    if args.write_artifact:
        path = save_winner_prior(prior, args.models_dir)
        print(f"\nartifact written: {path}")
    else:
        print("\n(shadow only — no artifact written; pass --write-artifact to persist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
