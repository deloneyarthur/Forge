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
