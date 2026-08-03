"""THE registered read of freeze condition (C). Run once per prereg, then never again.

This is deliberately a separate script from `freeze_tail_reading.py`. That one is the
exploratory instrument: it re-fits the variance floor on every run, compares the newest window
against the running maximum, and grows its window count as data arrives. All three are useful
while specifying a criterion and all three are WRONG at the moment of decision, because each
lets the data move the test. This script instead hard-codes what the preregistrations fixed in
advance and refuses to compute any of it:

    prereg          f507e5da0677 (leg 1, quality)     13e4d2cece3f (leg 2, redundancy)
    prior windows   1..10                             1..11
    baseline        0.7548 (best of prior)            0.4411 (max of prior)
    NEW WINDOWS     11..16                            12..17
    bar             0.0242                            0.0173
    falsified when  max(new) - baseline > bar         max(new) - baseline > bar

Both falsifiers are one-sided UPWARD, for opposite reasons: leg 1 asks whether the quality
ceiling is still rising, leg 2 whether redundancy has worsened -- and more redundant means
higher. So "best of the new six" is the maximum in both cases.

The window slice is exact and bounded on BOTH sides. Leg 1 reads windows 11-16 even when a
17th exists, because reading a seventh window is an extension, and an extension chosen after
seeing the data is the same defect as moving the bar. If fewer than the registered windows have
accrued, this refuses to read at all rather than reporting a partial result -- an early read
that happens to pass is indistinguishable from peeking-to-threshold.

Usage: freeze_registered_read.py SNAPSHOT.db
"""

from __future__ import annotations

import argparse
import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path

_INSTRUMENT = Path(__file__).resolve().parent / "freeze_tail_reading.py"
_spec = importlib.util.spec_from_file_location("freeze_tail_reading", _INSTRUMENT)
assert _spec is not None
assert _spec.loader is not None
_fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fx)


@dataclass(frozen=True, slots=True)
class RegisteredLeg:
    """Everything the prereg fixed. No field here may be derived from the judged data."""

    prereg_id: str
    name: str
    stat: str
    n_prior: int
    baseline: float
    bar: float
    falsifier: str

    @property
    def first_new(self) -> int:
        """1-indexed window number of the first NEW window."""
        return self.n_prior + 1

    @property
    def last_new(self) -> int:
        return self.n_prior + 6


_LEGS = (
    RegisteredLeg(
        prereg_id="f507e5da0677",
        name="LEG 1 -- quality (standardised TCM, top decile by cpcv)",
        stat="tcm",
        n_prior=10,
        baseline=0.7548,
        bar=0.0242,
        falsifier="the quality ceiling is STILL RISING -- the grammar is not exhausted",
    ),
    RegisteredLeg(
        prereg_id="13e4d2cece3f",
        name="LEG 2 -- redundancy (standardised TCM-corr over the same top decile)",
        stat="tcm_corr",
        n_prior=11,
        baseline=0.4411,
        bar=0.0173,
        falsifier="the GOOD supply has become MORE REDUNDANT over the window",
    ),
)


def _read(leg: RegisteredLeg, series: list[float]) -> bool:
    print(f"\n=== {leg.name} ===")
    print(f"  prereg {leg.prereg_id}   windows {leg.first_new}-{leg.last_new} vs baseline")
    if len(series) < leg.last_new:
        print(
            f"  NOT READABLE -- {len(series)} complete windows, need {leg.last_new}. "
            "Refusing a partial read."
        )
        return False
    new = series[leg.first_new - 1 : leg.last_new]
    if any(math.isnan(v) for v in new):
        print("  NOT READABLE -- a registered window is NaN (corr coverage incomplete).")
        return False
    print("  prior   : " + " ".join(f"{v:.4f}" for v in series[: leg.n_prior]))
    print("  NEW  6  : " + " ".join(f"{v:.4f}" for v in new))
    best = max(new)
    excess = best - leg.baseline
    verdict = "FALSIFIED" if excess > leg.bar else "CONFIRMED"
    print(
        f"  best-of-new {best:.4f}  -  baseline {leg.baseline:.4f}  =  {excess:+.4f}"
        f"   against bar {leg.bar:.4f}"
    )
    print(f"  >>> {verdict}" + (f" -- {leg.falsifier}" if verdict == "FALSIFIED" else ""))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    args = ap.parse_args()

    corr, basis_fp = _fx._load_corr()
    if basis_fp != _fx._REF_BASIS_FP:
        print(f"ABORT -- reference book re-based or absent (fp={basis_fp}). Leg 2 cannot read.")
        return 1

    with _fx.db_connection(Path(args.snapshot)) as conn:
        raw = conn.execute(_fx._QUERY).fetchall()
    obs = [(f"{h}/{b}", v, corr.get(ch)) for ch, h, b, v in raw if v is not None]
    n = len(obs)
    joined = sum(1 for o in obs if o[2] is not None)
    counts = _fx.Counter(c for c, _, _ in obs)
    ref = {c: k / n for c, k in counts.items()}
    print(f"honest arm, stage one, with cpcv: n={n}   complete windows: {n // 1200}")
    print(f"corr join: {joined} ({100 * joined / n:.1f}%)   reference basis fp: {basis_fp} OK")

    ok = True
    for leg in _LEGS:
        ok &= _read(leg, _fx._series(obs, ref, 1200, True, leg.stat))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
