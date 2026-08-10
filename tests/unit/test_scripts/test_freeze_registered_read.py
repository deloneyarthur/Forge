"""The registered read must be bounded on BOTH sides, and must refuse rather than partially read.

Two properties, both of which look like edge cases and are actually the whole discipline:

  1. It reads EXACTLY the registered windows. A 17th window existing does not entitle leg 1 to
     read seven; that is an extension, and an extension chosen after seeing the data is the same
     defect as moving the bar. Slicing bugs here are silent -- the number still looks plausible.

  2. It REFUSES a short or NaN-holed slice instead of reporting a partial result. An early read
     that happens to pass is indistinguishable from peeking-to-threshold, so "not enough data"
     has to be a different outcome from "confirmed", not a quieter version of it.

The registered constants are asserted against the prereg registry itself, so the script and the
record cannot drift apart without a test failing.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "freeze_registered_read", _ROOT / "scripts" / "freeze_registered_read.py"
)
assert _spec is not None
assert _spec.loader is not None
frr = importlib.util.module_from_spec(_spec)
# Registered before exec: `dataclass(slots=True)` re-creates the class and resolves its
# annotations through `sys.modules[cls.__module__]`, which is absent for a bare importlib load.
sys.modules["freeze_registered_read"] = frr
_spec.loader.exec_module(frr)

_LEG1, _LEG2 = frr._LEGS


def _series(n: int, value: float = 0.5) -> list[float]:
    return [value] * n


def test_the_registered_constants_match_the_prereg_registry() -> None:
    """The script hard-codes the prereg; if the record says otherwise, the script is wrong."""
    rows = {
        json.loads(line)["prereg_id"]: json.loads(line)
        for line in (_ROOT / "config" / "preregistrations.jsonl").read_text().splitlines()
        if line.strip()
    }
    for leg in frr._LEGS:
        claim = rows[leg.prereg_id]["claim"]
        assert f"{leg.baseline:.4f}" in claim, f"{leg.prereg_id} baseline not in its own claim"
        assert f"{leg.bar:.4f}" in claim, f"{leg.prereg_id} bar not in its own claim"
    assert (_LEG1.n_prior, _LEG1.baseline, _LEG1.bar) == (10, 0.7548, 0.0242)
    assert (_LEG2.n_prior, _LEG2.baseline, _LEG2.bar) == (11, 0.4411, 0.0173)


def test_leg1_reads_windows_11_to_16_and_ignores_a_seventeenth(capsys) -> None:
    """A 17th window exists in the real data. Reading it would be an unregistered extension."""
    ser = _series(17, 0.70)
    ser[16] = 99.0  # window 17 -- wildly falsifying IF it were (wrongly) included
    assert frr._read(_LEG1, ser) is True
    out = capsys.readouterr().out
    assert "CONFIRMED" in out
    assert "99.0" not in out, "window 17 leaked into leg 1's registered slice"


def test_each_leg_reads_its_own_six_windows(capsys) -> None:
    """Leg 1 is 11-16, leg 2 is 12-17 -- offset by one because it was registered later."""
    ser = [float(i) for i in range(1, 18)]
    frr._read(_LEG1, ser)
    assert "11.0000 12.0000 13.0000 14.0000 15.0000 16.0000" in capsys.readouterr().out
    frr._read(_LEG2, ser)
    assert "12.0000 13.0000 14.0000 15.0000 16.0000 17.0000" in capsys.readouterr().out


@pytest.mark.parametrize("have", [0, 10, 15])
def test_a_short_series_refuses_rather_than_reporting_a_partial_pass(capsys, have: int) -> None:
    assert frr._read(_LEG1, _series(have, 0.70)) is False
    out = capsys.readouterr().out
    assert "NOT READABLE" in out
    assert "CONFIRMED" not in out, "a partial read must never render a verdict"


def test_a_nan_in_a_registered_window_refuses(capsys) -> None:
    """Leg 2's windows go NaN when corr coverage lags; that is 'cannot read', not 'passed'."""
    ser = _series(17, 0.40)
    ser[16] = math.nan
    assert frr._read(_LEG2, ser) is False
    assert "NOT READABLE" in capsys.readouterr().out


def test_the_falsifier_fires_above_the_bar_and_only_above_it(capsys) -> None:
    """Both legs are one-sided UPWARD: leg 1 on quality rising, leg 2 on redundancy worsening."""
    for leg in frr._LEGS:
        ser = _series(leg.last_new, leg.baseline)
        ser[leg.last_new - 1] = leg.baseline + leg.bar + 1e-4
        frr._read(leg, ser)
        assert "FALSIFIED" in capsys.readouterr().out

        ser[leg.last_new - 1] = leg.baseline + leg.bar - 1e-4
        frr._read(leg, ser)
        assert "CONFIRMED" in capsys.readouterr().out

        # Falling is never a falsification for either leg.
        frr._read(leg, _series(leg.last_new, leg.baseline - 10.0))
        assert "CONFIRMED" in capsys.readouterr().out


# --- prereg 74dbbaee89c7 (post-break persistence) -------------------------------------------
#
# Structurally different from the (C) legs and the differences are the whole point:
#   * both legs read the SAME six windows (24-29), not offset slices;
#   * leg A aggregates with MIN, not MAX -- it asks whether the floor held, so one bad window
#     refutes it no matter how good the other five are;
#   * CONFIRMED means "the registered prediction held", not "the ceiling is flat". Reusing the
#     (C) legs' FALSIFIED-above-bar wiring here would inverse the reading of leg A.


_LEG_A, _LEG_B = frr._PERSISTENCE_LEGS


def test_persistence_constants_match_the_prereg_registry() -> None:
    rows = {
        json.loads(line)["prereg_id"]: json.loads(line)
        for line in (_ROOT / "config" / "preregistrations.jsonl").read_text().splitlines()
        if line.strip()
    }
    for leg in frr._PERSISTENCE_LEGS:
        row = rows[leg.prereg_id]
        text = row["claim"] + row["predicted"]
        assert f"{leg.threshold:.4f}" in text, f"{leg.prereg_id}: threshold not in its own record"
    assert (_LEG_A.n_prior, _LEG_A.threshold, _LEG_A.agg) == (23, 0.7877, "min")
    assert (_LEG_B.n_prior, _LEG_B.threshold, _LEG_B.agg) == (23, 0.9409, "max")


def test_the_single_read_rule_is_enforced_against_the_registry_not_memory(tmp_path) -> None:
    """The guard must key on STATUS, not on a snapshot of it.

    An earlier version of this test asserted the live registry still said 'registered' — which
    was true when written and false the instant the read resolved it, i.e. a test that passes
    only until the script is used for its purpose. What is durable is the SCRIPT's behaviour:
    reading a prereg the registry has already resolved must abort.
    """
    reg = tmp_path / "preregistrations.jsonl"
    reg.write_text(
        '{"prereg_id": "aaaa11112222", "status": "registered"}\n'
        '{"prereg_id": "bbbb33334444", "status": "confirmed"}\n',
        encoding="utf-8",
    )
    assert frr._registry_status("aaaa11112222", path=reg) == "registered"
    assert frr._registry_status("bbbb33334444", path=reg) == "confirmed"
    assert frr._registry_status("cccc55556666", path=reg) is None, "unknown id must not read"


def test_both_persistence_legs_read_windows_24_to_29_and_ignore_a_thirtieth(capsys) -> None:
    ser = [float(i) for i in range(1, 31)]
    for leg in frr._PERSISTENCE_LEGS:
        frr._read_persistence(leg, ser)
        out = capsys.readouterr().out
        assert "24.0000 25.0000 26.0000 27.0000 28.0000 29.0000" in out
        assert "30.0000" not in out, "window 30 leaked into the registered slice"


def test_leg_a_is_refuted_by_a_single_low_window(capsys) -> None:
    """MIN, not MAX: the floor is what leg A tests, so one dip below it is decisive."""
    ser = _series(29, 0.95)
    ser[26] = 0.7877 - 1e-4  # window 27 alone
    frr._read_persistence(_LEG_A, ser)
    assert "REFUTED" in capsys.readouterr().out

    ser[26] = 0.7877 + 1e-4
    frr._read_persistence(_LEG_A, ser)
    assert "CONFIRMED" in capsys.readouterr().out


def test_leg_b_needs_one_window_above_its_threshold(capsys) -> None:
    ser = _series(29, 0.90)
    frr._read_persistence(_LEG_B, ser)
    assert "REFUTED" in capsys.readouterr().out

    ser[28] = 0.9409 + 1e-4
    frr._read_persistence(_LEG_B, ser)
    assert "CONFIRMED" in capsys.readouterr().out


@pytest.mark.parametrize("have", [0, 23, 28])
def test_a_short_persistence_series_refuses(capsys, have: int) -> None:
    assert frr._read_persistence(_LEG_A, _series(have, 0.95)) is False
    out = capsys.readouterr().out
    assert "NOT READABLE" in out
    assert "CONFIRMED" not in out


def test_a_nan_in_a_persistence_window_refuses(capsys) -> None:
    ser = _series(29, 0.95)
    ser[28] = math.nan
    assert frr._read_persistence(_LEG_A, ser) is False
    assert "NOT READABLE" in capsys.readouterr().out


# --- basis-era guard (D387) -----------------------------------------------------------------
#
# The 2026-08-03 lesson: a window-grid boundary is not a changepoint, and a statistic read
# across a generation-basis change compares two different generators. The instrument already
# had the marker -- `enumeration_inputs_hash` carries a universe component -- and simply did
# not consume it. These pin the consumption.


def test_window_bases_reports_the_distinct_bases_per_window() -> None:
    bases = ["A"] * 10 + ["B"] * 10
    assert frr._fx.window_bases(bases, 5) == [
        frozenset({"A"}),
        frozenset({"A"}),
        frozenset({"B"}),
        frozenset({"B"}),
    ]


def test_a_window_straddling_a_basis_change_reports_BOTH() -> None:
    """The straddling window is the one that must not pass silently -- it is not assignable
    to either era, so it can never be 'the clean one' by picking a side."""
    bases = ["A"] * 7 + ["B"] * 3
    assert frr._fx.window_bases(bases, 5) == [frozenset({"A"}), frozenset({"A", "B"})]


def test_missing_basis_tags_are_not_silently_treated_as_one_era() -> None:
    """Rows predating the tag carry None. An untagged run must be UNKNOWN, not clean."""
    assert frr._fx.window_bases([None, None, "A", "A"], 2) == [frozenset(), frozenset({"A"})]


def test_the_registered_read_refuses_when_its_windows_span_a_basis_change(capsys) -> None:
    wb = [frozenset({"A"})] * 26 + [frozenset({"A", "B"})] + [frozenset({"B"})] * 2
    ok, msg = frr._basis_guard(wb, first=24, last=29)
    assert ok is False
    assert "2 generation bases" in msg


def test_the_registered_read_passes_a_basis_clean_slice() -> None:
    wb = [frozenset({"A"})] * 23 + [frozenset({"B"})] * 6
    ok, msg = frr._basis_guard(wb, first=24, last=29)
    assert ok is True, msg


def test_an_untagged_slice_refuses_rather_than_assuming_clean() -> None:
    ok, msg = frr._basis_guard([frozenset()] * 29, first=24, last=29)
    assert ok is False
    assert "untagged" in msg.lower()


def test_filter_to_basis_keeps_only_matching_rows_and_stays_aligned() -> None:
    """The obs list and the bases list are positionally paired; a filter that drops from one
    and not the other silently mis-attributes every window after the first drop."""
    obs = [("a/x", 1.0, None), ("a/x", 2.0, None), ("a/x", 3.0, None)]
    bases = ["A", "B", "A"]
    kept_obs, kept_bases = frr._fx.filter_to_basis(obs, bases, "A")
    assert kept_obs == [("a/x", 1.0, None), ("a/x", 3.0, None)]
    assert kept_bases == ["A", "A"]


def test_filter_to_basis_drops_untagged_rows() -> None:
    obs = [("a/x", 1.0, None), ("a/x", 2.0, None)]
    assert frr._fx.filter_to_basis(obs, [None, "A"], "A")[0] == [("a/x", 2.0, None)]


# --- prereg 3b0cbca7ae17 (within-basis (C) replication) --------------------------------------


def test_within_basis_constants_match_the_prereg_registry() -> None:
    rows = {
        json.loads(line)["prereg_id"]: json.loads(line)
        for line in (_ROOT / "config" / "preregistrations.jsonl").read_text().splitlines()
        if line.strip()
    }
    for leg in frr._WITHIN_BASIS_LEGS:
        text = rows[leg.prereg_id]["claim"] + rows[leg.prereg_id]["predicted"]
        assert f"{leg.baseline:.4f}" in text, f"{leg.prereg_id}: baseline not in its own record"
        assert f"{leg.bar:.4f}" in text, f"{leg.prereg_id}: bar not in its own record"
    w1, w2 = frr._WITHIN_BASIS_LEGS
    assert (w1.n_prior, w1.baseline, w1.bar) == (11, 0.9193, 0.0536)
    assert (w2.n_prior, w2.baseline, w2.bar) == (11, 0.4484, 0.0135)
    assert frr._WITHIN_BASIS_FP == "e1adced727678c8f"


def test_within_basis_legs_read_windows_12_to_17_of_the_BASIS_LOCAL_grid(capsys) -> None:
    """Both legs read the same six, because both were registered together off one 11-window
    prior -- unlike the original (C) legs, whose slices are offset by one."""
    ser = [float(i) for i in range(1, 19)]
    for leg in frr._WITHIN_BASIS_LEGS:
        frr._read(leg, ser)
        out = capsys.readouterr().out
        assert "12.0000 13.0000 14.0000 15.0000 16.0000 17.0000" in out
        assert "18.0000" not in out, "window 18 leaked into the registered slice"


def test_the_basis_guard_says_SHORT_not_untagged_when_the_windows_do_not_exist_yet() -> None:
    """Two different refusals that must not wear the same message.

    A slice past the end of the series produces an empty basis set, which reads identically to
    "these windows carry no tag" unless the guard checks length first. The first means WAIT; the
    second means INVESTIGATE THE MARKER. Conflating them sends a reader hunting a bug that is
    actually three days of accrual.
    """
    ok, msg = frr._basis_guard([frozenset({"A"})] * 11, first=12, last=17)
    assert ok is False
    assert "11 complete windows, need 17" in msg
    assert "untagged" not in msg.lower()
