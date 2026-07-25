"""Q59 validation sweep: does removing the honest-scope DROP actually fix the ranker?

WHY THIS EXISTS. Three times in three days a large, well-controlled, replicated finding
evaporated under the right control (rank_k=5, swing_long, and our own 5x-inflated
winner-prior shadow). The Q59 fix proposal currently rests on ONE coefficient
(`rank_k`) checked against ONE ground truth. That is exactly the evidential weight that
has failed us repeatedly, so it gets a sweep before it gets a deploy.

THE CLAIM UNDER TEST. `honest_regime_coverage_row` DROPS ~87% of training rows, and the
drop is quality-correlated, so it is a collider: coefficients on any feature correlated
with coverage-resolution absorb a biased — sometimes sign-flipped — estimate. Fix by not
dropping (F3) or by modelling the conditioning explicitly as a two-part hurdle model
(robustness regressor).

FIVE ARMS, each answering a way the claim could be WRONG:

  A. COEFFICIENT CENSUS — conditioned vs unconditioned coefficients for every feature.
     If only rank_k flips, the problem is narrow and a targeted fix suffices; if many
     flip, the population is the problem. Tests "is rank_k special or typical?"

  B. RANKING VALIDATION ON STAGE ONE — the decision-relevant test. Fit each variant on a
     temporal TRAIN split, rank the held-out LATER split, and measure the realized
     UNCONDITIONED outcome of the picks. The ranker's job is to choose configs that do
     well in the world, not in the filtered sample, so the judge is always stage one.

  C. F3 VARIANTS — does turning the drop off give F3 the right rank_k sign, and does its
     discrimination (AUC) survive? A fix that corrects the sign but destroys the model is
     not a fix.

  D. TWO-PART PRODUCT — P(convert) x E[cpcv|converted] versus each factor alone, scored
     on stage one. Crucible's design is theoretically right; that is not the same as
     empirically better, and it is cheap to check.

  F. ENCODING x CONDITIONING, VALIDATED OUT OF SAMPLE — added 2026-07-25 after arm C's
     "refutation" turned out to be incomplete. `rank_k`'s relation to conversion is
     NON-MONOTONIC (P(label): k5 0.073, k10 0.133, k20 0.000 — the D004 breadth floor),
     so a LINEAR feature averages the peak against the cliff and comes out negative. And
     the drop deletes the entire k=20 stratum (55,820 rows -> 0), so a conditioned model
     cannot learn the cliff at any encoding. Both fixes are needed and only together do
     they work. Judged on OOS AUC, never train AUC: one-hot ADDS parameters, so the
     in-sample gain is confounded by construction.

  E. D331 REGRESSION — D331 Part B turned the drop ON and measured a benefit (it fixed
     the ranker's inverted cell allocation). Removing it must not undo that. A fix that
     trades one inversion for another is the week's mistake pattern repeating.

EVERY judgement is on the UNCONDITIONED (stage-one) population, per the rule both sides
adopted after the rank_k retraction. Temporal splits throughout: fit on the past, judge
on the future, which is how the ranker is actually used.

    cp ~/forge_data/forge.db ~/.cache/rv/forge_snap.db   # ~6s, delete when done
    uv run python scripts/collider_fix_sweep.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from forge.persistence.registry_loader import load_registry
from forge.ranking.dataset import build_dataset
from forge.ranking.model import (
    _REGRESSION_NON_FEATURES,
    train_robustness_model,
    train_verdict_model,
)

_DEFAULT_SNAPSHOT = Path("~/.cache/rv/forge_snap.db").expanduser()
_LIVE_DB = Path("~/forge_data/forge.db").expanduser()
_FACTOR1_LABELS = Path("~/optbt_data/exports/stage_two_conversion_2026-07-25.json").expanduser()

_TARGET = "target_cpcv_p25"
_TRAIN_FRAC = 0.70  # temporal: fit on the first 70%, judge on the last 30%
_TOP_FRAC = 0.10


def _era_cut() -> Any:
    from datetime import UTC, datetime

    return datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)


def _feature_cols(frame: Any) -> list[str]:
    return [c for c in frame.columns if c not in _REGRESSION_NON_FEATURES and c != _TARGET]


def _matrix(frame: Any, cols: list[str]) -> np.ndarray:
    return np.array([[float(r[c]) for c in cols] for r in frame.iter_rows(named=True)])


def _rank(a: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(a, kind="stable")).astype(float)


def _ic(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = _rank(a) - _rank(a).mean(), _rank(b) - _rank(b).mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 1e-12 else 0.0


def _fit_ridge(x: np.ndarray, y: np.ndarray, lam: float = 10.0) -> np.ndarray:
    xm, xs = x.mean(0), x.std(0) + 1e-9
    xz = (x - xm) / xs
    w = np.linalg.solve(xz.T @ xz + lam * np.eye(xz.shape[1]), xz.T @ (y - y.mean()))
    return np.concatenate([[y.mean()], w / xs, [-(w / xs) @ xm]])


def _apply(x: np.ndarray, coef: np.ndarray) -> np.ndarray:
    return np.asarray(coef[0] + x @ coef[1:-1] + coef[-1], dtype=float)


def arm_a_coefficient_census(con: Any, registry: Any) -> set[str]:
    """Conditioned vs unconditioned coefficients, every feature. Returns flipped names."""
    print("\n=== ARM A — coefficient census: is rank_k special, or typical? ===")
    cut = _era_cut()
    out: dict[bool, dict[str, float]] = {}
    for scope in (True, False):
        fr = build_dataset(con, registry, era_cut=cut, honest_scope=scope)
        fr = fr.filter(fr[_TARGET].is_not_null())
        m = train_robustness_model(fr, target=_TARGET, era_cut=cut)
        out[scope] = dict(zip(m.feature_names, m.coefficients, strict=False))
        print(f"  honest_scope={scope!s:5} n={fr.height:>7} features={len(m.feature_names)}")

    shared = sorted(set(out[True]) & set(out[False]))
    flipped = [
        f
        for f in shared
        if out[True][f] * out[False][f] < 0 and min(abs(out[True][f]), abs(out[False][f])) > 0.005
    ]
    print(f"\n  shared features: {len(shared)}   SIGN-FLIPPED (both |coef|>0.005): {len(flipped)}")
    print(f"  {'feature':34} {'conditioned':>12} {'unconditioned':>14}")
    for f in sorted(flipped, key=lambda f: -abs(out[False][f] - out[True][f]))[:12]:
        star = "  <-- the one we found" if f == "rank_k" else ""
        print(f"  {f:34} {out[True][f]:>+12.5f} {out[False][f]:>+14.5f}{star}")
    if "rank_k" not in flipped:
        print("  NB rank_k did NOT flip under this fit — the headline claim needs re-checking.")
    return set(flipped)


def arm_b_ranking_validation(con: Any, registry: Any) -> None:
    """The decision test: which variant picks configs that do well on STAGE ONE?"""
    print("\n=== ARM B — ranking validation, judged on the UNCONDITIONED population ===")
    cut = _era_cut()
    full = build_dataset(con, registry, era_cut=cut, honest_scope=False)
    full = full.filter(full[_TARGET].is_not_null()).sort("decided_at")
    k = int(full.height * _TRAIN_FRAC)
    train_all, test = full[:k], full[k:]
    cols = _feature_cols(full)
    x_te, y_te = _matrix(test, cols), np.array(test[_TARGET].to_list(), dtype=float)

    # conditioned arm: same TRAIN window, but only coverage-resolved rows
    cov = np.array(train_all["coverage_verified"].to_list(), dtype=float) > 0.5
    x_tr_all, y_tr_all = (
        _matrix(train_all, cols),
        np.array(train_all[_TARGET].to_list(), dtype=float),
    )

    print(f"  train n={k}  test n={test.height} (later in time)   judge = stage-one cpcv\n")
    print(f"  {'variant':30} {'train n':>9} {'OOS IC':>9} {'top10% cpcv':>12} {'vs base':>9}")
    base_med = float(np.median(y_te))
    print(f"  {'(baseline: no model)':30} {'-':>9} {'-':>9} {base_med:>12.4f} {'-':>9}")

    for label, mask in (("UNCONDITIONED (no drop)", None), ("CONDITIONED (honest-scope)", cov)):
        xt = x_tr_all if mask is None else x_tr_all[mask]
        yt = y_tr_all if mask is None else y_tr_all[mask]
        coef = _fit_ridge(xt, yt)
        pred = _apply(x_te, coef)
        top = np.argsort(-pred)[: max(1, int(_TOP_FRAC * len(pred)))]
        med = float(np.median(y_te[top]))
        stats = f"{_ic(pred, y_te):>9.4f} {med:>12.4f} {med - base_med:>+9.4f}"
        print(f"  {label:30} {len(yt):>9} {stats}")


def arm_c_f3_variants(con: Any, registry: Any) -> None:
    """Does the F3 fix correct the sign WITHOUT destroying discrimination?"""
    print("\n=== ARM C — F3 verdict model: sign vs discrimination ===")
    cut = _era_cut()
    print(f"  {'variant':30} {'n':>8} {'positives':>10} {'rank_k':>10} {'train AUC':>10}")
    for scope in (True, False):
        fr = build_dataset(con, registry, era_cut=cut, honest_scope=scope)
        m = train_verdict_model(fr, era_cut=cut)
        rk = dict(zip(m.feature_names, m.coefficients, strict=False)).get("rank_k", float("nan"))
        mt = dict(m.train_metrics)
        label = "CONDITIONED (honest-scope)" if scope else "UNCONDITIONED (no drop)"
        print(
            f"  {label:30} {m.n_rows:>8} {m.n_positive:>10} {rk:>+10.4f} "
            f"{mt.get('auc', float('nan')):>10.4f}"
        )
    print("  ground truth (stage one, unconditioned): k=10 converts 1.59x k=5 -> want rank_k > 0")


def arm_d_two_part(con: Any, registry: Any) -> None:
    """P(convert) x E[cpcv|converted] vs each factor alone, judged on stage one."""
    print("\n=== ARM D — two-part product vs each factor alone ===")
    if not _FACTOR1_LABELS.exists():
        print(f"  Factor-1 labels not found: {_FACTOR1_LABELS}")
        return
    lab = json.loads(_FACTOR1_LABELS.read_text())
    conv = {r["config_hash"]: (1.0 if r["reached_stage_two"] else 0.0) for r in lab["rows"]}

    cut = _era_cut()
    full = build_dataset(con, registry, era_cut=cut, honest_scope=False)
    full = full.filter(full[_TARGET].is_not_null()).sort("decided_at")
    hashes = full["config_hash"].to_list()
    keep = [i for i, h in enumerate(hashes) if h in conv]
    if len(keep) < 2000:
        print(f"  too few joined rows ({len(keep)}) for a two-part read")
        return
    full = full[keep]
    y_conv = np.array([conv[h] for h in full["config_hash"].to_list()], dtype=float)
    cols = _feature_cols(full)
    x = _matrix(full, cols)
    y = np.array(full[_TARGET].to_list(), dtype=float)
    cov = np.array(full["coverage_verified"].to_list(), dtype=float) > 0.5

    k = int(len(y) * _TRAIN_FRAC)
    base_med = float(np.median(y[k:]))
    print(f"  joined n={len(y)}  train={k}  test={len(y) - k}   judge = stage-one cpcv\n")
    print(f"  {'variant':34} {'OOS IC':>9} {'top10% cpcv':>12} {'vs base':>9}")
    print(f"  {'(baseline: no model)':34} {'-':>9} {base_med:>12.4f} {'-':>9}")

    f1 = _apply(x[k:], _fit_ridge(x[:k], y_conv[:k]))
    f2 = _apply(x[k:], _fit_ridge(x[:k][cov[:k]], y[:k][cov[:k]]))
    variants = {
        "Factor 1 alone  P(convert)": f1,
        "Factor 2 alone  E[cpcv|conv]": f2,
        "TWO-PART  F1 x F2": f1 * f2,
        "unconditioned single model": _apply(x[k:], _fit_ridge(x[:k], y[:k])),
    }
    for name, pred in variants.items():
        top = np.argsort(-pred)[: max(1, int(_TOP_FRAC * len(pred)))]
        med = float(np.median(y[k:][top]))
        print(f"  {name:34} {_ic(pred, y[k:]):>9.4f} {med:>12.4f} {med - base_med:>+9.4f}")


def arm_e_d331_regression(con: Any, registry: Any) -> None:
    """D331 Part B turned the drop ON to fix inverted CELL allocation. Does removing it
    undo that? Compares each variant's top-decile hypothesis mix against the mix that
    actually converts on stage one."""
    print("\n=== ARM E — D331 regression: does the cell allocation stay fixed? ===")
    cut = _era_cut()
    full = build_dataset(con, registry, era_cut=cut, honest_scope=False)
    full = full.filter(full[_TARGET].is_not_null()).sort("decided_at")
    cols = _feature_cols(full)
    hyp_cols = [c for c in full.columns if c.startswith("hypothesis=")]
    if not hyp_cols:
        print("  no hypothesis columns in the frame; skipping")
        return
    x = _matrix(full, cols)
    y = np.array(full[_TARGET].to_list(), dtype=float)
    cov = np.array(full["coverage_verified"].to_list(), dtype=float) > 0.5
    k = int(len(y) * _TRAIN_FRAC)
    hyp_te = {h: np.array(full[h].to_list(), dtype=float)[k:] for h in hyp_cols}

    # ground truth: which hypothesis actually carries high stage-one cpcv?
    print(f"  {'':34} " + " ".join(f"{h.split('=')[1][:11]:>12}" for h in hyp_cols))
    thr = np.quantile(y[k:], 0.9)
    truth = {h: float(v[y[k:] >= thr].mean()) for h, v in hyp_te.items()}
    print(
        f"  {'GROUND TRUTH (top-decile cpcv)':34} "
        + " ".join(f"{truth[h]:>12.3f}" for h in hyp_cols)
    )
    for label, mask in (("UNCONDITIONED (no drop)", None), ("CONDITIONED (honest-scope)", cov)):
        xt = x[:k] if mask is None else x[:k][mask[:k]]
        yt = y[:k] if mask is None else y[:k][mask[:k]]
        pred = _apply(x[k:], _fit_ridge(xt, yt))
        top = np.argsort(-pred)[: max(1, int(_TOP_FRAC * len(pred)))]
        mix = {h: float(v[top].mean()) for h, v in hyp_te.items()}
        print(f"  {label:34} " + " ".join(f"{mix[h]:>12.3f}" for h in hyp_cols))
    print("  (closer to GROUND TRUTH = better allocation; D331's fix must not regress)")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", type=Path, default=_DEFAULT_SNAPSHOT)
    args = ap.parse_args()
    if args.db == _LIVE_DB:
        print("refuse: that is the live RW-locked DB. Snapshot first.", file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"snapshot not found: {args.db}\n  cp {_LIVE_DB} {args.db}", file=sys.stderr)
        return 2

    registry = load_registry()
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        flipped = arm_a_coefficient_census(con, registry)
        arm_b_ranking_validation(con, registry)
        arm_c_f3_variants(con, registry)
        arm_d_two_part(con, registry)
        arm_e_d331_regression(con, registry)
    finally:
        con.close()

    print("\n=== VERDICT RULE ===")
    print("  Ship the fix only if: (A) the flip is not confined to one coefficient OR")
    print("  rank_k's flip is corroborated by (B); (B) the unconditioned/two-part variant")
    print("  ranks BETTER on stage one; (C) F3's AUC survives; (E) D331's allocation does")
    print("  not regress. Any arm failing sends this back to diagnosis, not to deploy.")
    print(f"  [arm A found {len(flipped)} sign-flipped coefficients]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
