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

Prereg 3b0cbca7ae17 (`--read within-basis`) replicates (C) INSIDE one generation basis
(D387): the series is filtered to the basis BEFORE it is gridded, so window numbers are
basis-local and no window straddles the seam. Same leg shape and same rule as the
originals -- the point of a replication is that the rule does not move.

Usage: freeze_registered_read.py SNAPSHOT.db --read {c,persistence,within-basis}
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
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


# Prereg 3b0cbca7ae17 -- (C) replicated INSIDE one generation basis. Same SHAPE as the original
# (C) legs (max-of-new vs a fixed baseline, FALSIFIED above the bar), so `RegisteredLeg` and
# `_read` are reused deliberately: the point of a replication is that the rule does not move.
# What differs is upstream -- the series is filtered to this basis BEFORE it is gridded, so the
# window numbers are basis-local and there is no straddling window to reason about.
_WITHIN_BASIS_FP = "e1adced727678c8f"

_WITHIN_BASIS_LEGS = (
    RegisteredLeg(
        prereg_id="3b0cbca7ae17",
        name="WITHIN-BASIS LEG 1 -- quality (standardised TCM, basis-local grid)",
        stat="tcm",
        n_prior=11,
        baseline=0.9193,
        bar=0.0536,
        falsifier="the ceiling is STILL RISING inside a fixed basis -- the freeze is wrong",
    ),
    RegisteredLeg(
        prereg_id="3b0cbca7ae17",
        name="WITHIN-BASIS LEG 2 -- redundancy (standardised TCM-corr, basis-local grid)",
        stat="tcm_corr",
        n_prior=11,
        baseline=0.4484,
        bar=0.0135,
        falsifier="the GOOD supply has become MORE REDUNDANT inside a fixed basis",
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
    if len(win_bases) < last:
        return False, (
            f"NOT READABLE -- {len(win_bases)} complete windows, need {last}. "
            "Refusing a partial read (this is 'wait', not 'the marker is broken')."
        )
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
        choices=("c", "persistence", "within-basis"),
        help="which registered read to take: (C), 74dbbaee89c7, or 3b0cbca7ae17",
    )
    ap.add_argument(
        "--resolve",
        action="store_true",
        help=(
            "write the outcome to the preregistration registry. Without this the read is "
            "printed and NOT recorded -- which is how 3b0cbca7ae17's resolution came to be "
            "entered by hand (D389). A read that is taken should be a read that is recorded."
        ),
    )
    args = ap.parse_args()

    legs: tuple[RegisteredLeg, ...] | tuple[PersistenceLeg, ...] = {
        "c": _LEGS,
        "persistence": _PERSISTENCE_LEGS,
        "within-basis": _WITHIN_BASIS_LEGS,
    }[args.read]
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

    if args.read == "within-basis":
        obs, bases = _fx.filter_to_basis(obs, bases, _WITHIN_BASIS_FP)
        n = len(obs)
        ref = {c: k / n for c, k in _fx.Counter(c for c, _, _ in obs).items()}
        print(f"BASIS-SCOPED to {_WITHIN_BASIS_FP}: n={n}, {n // 1200} windows (grid is local)")
    win_bases = _fx.window_bases(bases, 1200)
    ok = True
    readable = True
    for leg in legs:
        clean, msg = _basis_guard(win_bases, leg.first_new, leg.last_new)
        if not clean:
            print(f"\n=== {leg.name} ===\n  ABORT -- {msg}")
            ok = False
            readable = False
            continue
        print(f"\n[basis guard] windows {leg.first_new}-{leg.last_new}: {msg}")
        series = _fx._series(obs, ref, 1200, True, leg.stat)
        if isinstance(leg, PersistenceLeg):
            ok &= _read_persistence(leg, series)
        else:
            ok &= _read(leg, series)

    if args.resolve:
        _resolve(legs, ok, readable)
    else:
        print(
            "\n[not recorded] --resolve was not passed, so the registry is UNCHANGED. "
            "The read is only taken once; record it before the number is lost (D389)."
        )
    return 0 if ok else 1


def _resolve(
    legs: tuple[RegisteredLeg, ...] | tuple[PersistenceLeg, ...],
    ok: bool,
    readable: bool,
) -> None:
    """Write the outcome to the registry, once, using the repo's own resolver.

    A leg that could not be read is `insufficient`, NOT `refuted` -- "not enough data" has to
    be a different outcome from a verdict, or an early read that happens to pass becomes
    indistinguishable from peeking-to-threshold.
    """
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from forge.core.clock import utc_now
    from forge.feedback.preregistration import resolve_preregistration

    outcome = "confirmed" if ok else ("refuted" if readable else "insufficient")
    ids = sorted({leg.prereg_id for leg in legs})
    for pid in ids:
        try:
            updated = resolve_preregistration(
                _REPO_ROOT / "config" / "preregistrations.jsonl",
                pid,
                outcome=outcome,
                evidence=(
                    f"Auto-recorded by freeze_registered_read.py --resolve at "
                    f"{utc_now().isoformat()}. See the run output and the D-entry for the "
                    f"per-leg numbers; this line exists so the read cannot be taken and lost."
                ),
                resolved_at=utc_now().isoformat(),
            )
            print(f"[registry] {updated.prereg_id} -> {updated.status}")
        except KeyError:
            print(f"[registry] ABORT -- no preregistration {pid!r} to resolve", file=sys.stderr)
        except ValueError as exc:
            # Already resolved: the single-read guard upstream should have caught this, so
            # say so loudly rather than treating a double-read as a no-op.
            print(f"[registry] REFUSED for {pid}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
