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

Prereg 74dbbaee89c7 (`--read persistence`) is the follow-on and is shaped differently: both its
legs read the SAME six windows 24-29, leg A aggregates with `min` because it tests a floor, and
CONFIRMED there means the registered prediction HELD -- the opposite polarity from the (C) legs.
See `PersistenceLeg`.

Reading a prereg whose registry status is no longer 'registered' aborts, so the single-read rule
is enforced against the record rather than against anyone's memory of having read it.

Usage: freeze_registered_read.py SNAPSHOT.db --read {c,persistence}
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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


@dataclass(frozen=True, slots=True)
class PersistenceLeg:
    """Prereg 74dbbaee89c7. Shaped differently from the (C) legs, deliberately.

    Both legs read the SAME six windows, and leg A aggregates with `min` because it tests a
    FLOOR: the question is whether the post-break level held everywhere, so one window below
    the threshold refutes it however good the other five are. And CONFIRMED here means the
    registered prediction held -- the opposite polarity from the (C) legs, where clearing the
    bar means the flat-ceiling claim was falsified. Sharing `_read` would silently invert leg A.
    """

    prereg_id: str
    name: str
    stat: str
    n_prior: int
    threshold: float
    agg: str
    tests: str
    if_confirmed: str
    if_refuted: str

    @property
    def first_new(self) -> int:
        return self.n_prior + 1

    @property
    def last_new(self) -> int:
        return self.n_prior + 6


_PERSISTENCE_LEGS = (
    PersistenceLeg(
        prereg_id="74dbbaee89c7",
        name="LEG A -- persistence (min of the six new windows)",
        stat="tcm",
        n_prior=23,
        threshold=0.7877,
        agg="min",
        tests="did the break HOLD, or was it a transient excursion?",
        if_confirmed="the break is a DURABLE level shift",
        if_refuted="the break was TRANSIENT -- the 2026-08-03 flat reading stands",
    ),
    PersistenceLeg(
        prereg_id="74dbbaee89c7",
        name="LEG B -- continued rise (max of the same six windows)",
        stat="tcm",
        n_prior=23,
        threshold=0.9409,
        agg="max",
        tests="is the ceiling STILL climbing, or did it step once and re-plateau?",
        if_confirmed="the ceiling is STILL RISING -- the freeze is the wrong call",
        if_refuted="the ceiling stepped ONCE and re-plateaued",
    ),
)


def _read_persistence(leg: PersistenceLeg, series: list[float]) -> bool:
    print(f"\n=== {leg.name} ===")
    print(f"  prereg {leg.prereg_id}   windows {leg.first_new}-{leg.last_new}   {leg.tests}")
    if len(series) < leg.last_new:
        print(
            f"  NOT READABLE -- {len(series)} complete windows, need {leg.last_new}. "
            "Refusing a partial read."
        )
        return False
    new = series[leg.first_new - 1 : leg.last_new]
    if any(math.isnan(v) for v in new):
        print("  NOT READABLE -- a registered window is NaN.")
        return False
    print("  NEW  6  : " + " ".join(f"{v:.4f}" for v in new))
    stat = min(new) if leg.agg == "min" else max(new)
    held = stat > leg.threshold
    verdict = "CONFIRMED" if held else "REFUTED"
    print(
        f"  {leg.agg}(new) {stat:.4f}  vs threshold {leg.threshold:.4f}"
        f"   =  {stat - leg.threshold:+.4f}"
    )
    print(f"  >>> {verdict} -- {leg.if_confirmed if held else leg.if_refuted}")
    return True


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


_REGISTRY = Path(__file__).resolve().parent.parent / "config" / "preregistrations.jsonl"


def _basis_guard(win_bases: list[frozenset[str]], first: int, last: int) -> tuple[bool, str]:
    """Refuse a registered read whose windows span more than one generation basis.

    The freeze programme's own scar (D387): (C) was read across the 2026-08-03 universe
    re-rank, comparing two different generators as one series. The marker to prevent it
    already existed -- `enumeration_inputs_hash` carries a universe component -- and the
    instrument simply did not consume it. This is the consumption.

    Untagged windows refuse too. "No basis recorded" is not evidence of a single basis, and
    a guard that passes on absent data is worse than no guard: it certifies.
    """
    spans: set[str] = set()
    for wb in win_bases[first - 1 : last]:
        spans |= wb
    if not spans:
        return False, f"windows {first}-{last} are UNTAGGED -- basis unknown, refusing to read"
    if len(spans) > 1:
        return False, (
            f"windows {first}-{last} span {len(spans)} generation bases "
            f"({', '.join(sorted(spans))}) -- refusing to read across a basis change"
        )
    return True, f"basis-clean: {next(iter(spans))}"


def _registry_status(prereg_id: str, path: Path = _REGISTRY) -> str | None:
    """A prereg that is already resolved must not be read a second time -- that is the
    'single read' rule enforced against the record rather than against memory."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("prereg_id") == prereg_id:
            return str(row.get("status"))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument(
        "--read",
        required=True,
        choices=("c", "persistence"),
        help="which registered read to take: the (C) legs, or prereg 74dbbaee89c7",
    )
    args = ap.parse_args()

    legs: tuple[RegisteredLeg, ...] | tuple[PersistenceLeg, ...] = (
        _LEGS if args.read == "c" else _PERSISTENCE_LEGS
    )
    for leg in legs:
        status = _registry_status(leg.prereg_id)
        if status != "registered":
            print(f"ABORT -- prereg {leg.prereg_id} status is {status!r}, not 'registered'.")
            return 1

    corr, basis_fp = _fx._load_corr()
    if basis_fp != _fx._REF_BASIS_FP:
        print(f"ABORT -- reference book re-based or absent (fp={basis_fp}). Leg 2 cannot read.")
        return 1

    with _fx.db_connection(Path(args.snapshot)) as conn:
        raw = conn.execute(_fx._QUERY).fetchall()
    obs = [(f"{h}/{b}", v, corr.get(ch)) for ch, h, b, v, _u in raw if v is not None]
    bases = [u for _ch, _h, _b, v, u in raw if v is not None]
    n = len(obs)
    joined = sum(1 for o in obs if o[2] is not None)
    counts = _fx.Counter(c for c, _, _ in obs)
    ref = {c: k / n for c, k in counts.items()}
    print(f"honest arm, stage one, with cpcv: n={n}   complete windows: {n // 1200}")
    print(f"corr join: {joined} ({100 * joined / n:.1f}%)   reference basis fp: {basis_fp} OK")

    win_bases = _fx.window_bases(bases, 1200)
    ok = True
    for leg in legs:
        clean, msg = _basis_guard(win_bases, leg.first_new, leg.last_new)
        if not clean:
            print(f"\n=== {leg.name} ===\n  ABORT -- {msg}")
            ok = False
            continue
        print(f"\n[basis guard] windows {leg.first_new}-{leg.last_new}: {msg}")
        series = _fx._series(obs, ref, 1200, True, leg.stat)
        if isinstance(leg, PersistenceLeg):
            ok &= _read_persistence(leg, series)
        else:
            ok &= _read(leg, series)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
