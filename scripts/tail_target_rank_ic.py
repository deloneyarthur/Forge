"""Resolve prereg `7f675a79ca57`: does a cpcv-TARGETED robustness model order realised CPCV
better out-of-sample than the wf-targeted one?

WHY THIS SCRIPT EXISTS. The prereg's action ALREADY SHIPPED — the production quality lane was
re-targeted to `target_cpcv_p25` at v50 (2026-07-24), one day after the prereg's own cohort cut —
but the prereg was never resolved, so the deployed change has never been tested on post-cut data.
That is the same pattern as the v52 capitulation retirement: the action lands, the prediction is
left open, and nobody notices because the change looks settled.

The registered claim measured 0.2835 (cpcv-targeted) against 0.2541 (wf-targeted) on n_test=5,283
of a common n=26,416. The daily job trains both targets, but publishes only in-sample
`train_metrics`; nothing on disk carries an OOS rank IC. So the comparison has to be recomputed.

WHAT IS COMPARED, and the one thing that makes it a fair test: TWO MODELS, ONE YARDSTICK. Both
ridges are scored against the SAME realised `target_cpcv_p25` on the SAME test rows. The wf-
targeted model is not being asked to predict wf — it is being asked to predict CPCV, which is
the question the production lane actually needs answered. Scoring each model against its own
target would compare two different quantities and could not rank them.

BASIS, mirroring `robustness_oos_r2` exactly so this is the trainer's own split and not a new one:
  * TEMPORAL holdout ordered by `decided_at`, last 20% is test. Deterministic, no RNG.
  * COMMON POPULATION — only rows carrying BOTH targets, so the two models see an identical
    train set and an identical test set. Without this the comparison is confounded by coverage:
    the targets have different non-null footprints and the wf model would be scored on a
    different, easier or harder, slice.
  * Standardisation over the full design (the trainer's own negligible leak — feature
    distributions only, never the target); COEFFICIENTS fit on the train split alone.

RANK IC, not R², because the lane RANKS candidates — it never consumes the predicted level. A
model can carry a poor R² and still order the field correctly, and ordering is the whole job.

Usage: tail_target_rank_ic.py SNAPSHOT.db [--holdout 0.2] [--lambda 1.0]
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import numpy as np

from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT
from forge.persistence.db import db_connection
from forge.persistence.registry_loader import load_registry
from forge.ranking.dataset import build_dataset
from forge.ranking.model import (
    _REGRESSION_NON_FEATURES,
    _solve_ridge,
    _standardize_design,
)

_PRIMARY = "target_cpcv_p25"
_RIVAL = "target_wf_p25"


def _spearman(a: list[float], b: list[float]) -> float:
    """Rank correlation with average ranks for ties (ties are common in gate values)."""

    def ranks(z: list[float]) -> list[float]:
        order = sorted(range(len(z)), key=lambda i: z[i])
        out = [0.0] * len(z)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and z[order[j + 1]] == z[order[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    da = [x - ma for x in ra]
    db = [x - mb for x in rb]
    den = (sum(x * x for x in da) * sum(x * x for x in db)) ** 0.5
    return sum(x * y for x, y in zip(da, db, strict=True)) / den if den else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--lam", type=float, default=1.0)
    args = ap.parse_args()

    registry = load_registry()
    with db_connection(Path(args.snapshot)) as conn:
        frame = build_dataset(conn, registry, era_cut=CLEAN_ERA_LABEL_CUT, honest_scope=True)

    for col in (_PRIMARY, _RIVAL, "decided_at"):
        if col not in frame.columns:
            print(f"missing column {col!r} in dataset")
            return 2

    prim_raw = frame[_PRIMARY].to_list()
    rival_raw = frame[_RIVAL].to_list()
    # COMMON population: both targets present, or the two models are not comparable.
    keep = [
        i
        for i, (a, b) in enumerate(zip(prim_raw, rival_raw, strict=True))
        if a is not None and b is not None
    ]
    n = len(keep)
    print(f"rows carrying {_PRIMARY}: {sum(1 for v in prim_raw if v is not None)}")
    print(f"rows carrying {_RIVAL}: {sum(1 for v in rival_raw if v is not None)}")
    print(f"COMMON population (both targets): n={n}")
    if n < 200:
        print("too thin for a meaningful split")
        return 1

    y_prim = [float(prim_raw[i]) for i in keep]
    y_rival = [float(rival_raw[i]) for i in keep]
    names = [c for c in frame.columns if c not in _REGRESSION_NON_FEATURES]
    raw_cols = {name: frame[name].to_list() for name in names}
    columns = {name: [float(raw_cols[name][i]) for i in keep] for name in names}
    _, _, _, x_rows = _standardize_design(columns, names, n)

    decided = frame["decided_at"].to_list()
    order = sorted(range(n), key=lambda j: decided[keep[j]])
    n_test = round(n * args.holdout)
    train_idx, test_idx = order[: n - n_test], order[n - n_test :]
    print(f"temporal split: train={len(train_idx)}  test={len(test_idx)}  features={len(names)}")

    # THE YARDSTICK: realised cpcv on the test rows, identical for both models.
    truth = [y_prim[j] for j in test_idx]

    results: dict[str, float] = {}
    for label, y in ((_PRIMARY, y_prim), (_RIVAL, y_rival)):
        y_train = [y[j] for j in train_idx]
        mean = sum(y_train) / len(y_train)
        coef = _solve_ridge(x_rows[train_idx], [y[j] - mean for j in train_idx], args.lam)
        preds = mean + x_rows[test_idx] @ np.asarray(coef, dtype=np.float64)
        results[label] = _spearman([float(v) for v in preds], truth)

    print(f"\nOOS rank IC vs REALISED {_PRIMARY} (same test rows, same yardstick):")
    print(
        f"  model targeted on {_PRIMARY:<18} {results[_PRIMARY]:+.4f}"
        "   <- production lane since v50"
    )
    print(f"  model targeted on {_RIVAL:<18} {results[_RIVAL]:+.4f}")
    delta = results[_PRIMARY] - results[_RIVAL]
    print(f"  delta                                {delta:+.4f}")
    # A rank-IC difference is not free: the paired MDE at ~80% power is ~2.8/sqrt(n_test).
    mde = 2.8 / (len(test_idx) ** 0.5)
    print(f"  MDE at n_test={len(test_idx)}: {mde:.4f}  (2.8/sqrt(n))")
    verdict = (
        "CONFIRMED — cpcv-targeting orders realised CPCV better"
        if delta > mde
        else "NOT SEPARATED at this n — the advantage does not clear its own MDE"
        if delta > 0
        else "REVERSED — the wf-targeted model orders realised CPCV better"
    )
    print(f"  >>> {verdict}")
    print("\n  registered comparison was 0.2835 vs 0.2541 (delta +0.0294) at n_test=5,283")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
