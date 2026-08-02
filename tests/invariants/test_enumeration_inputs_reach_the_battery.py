"""Every enumeration input `_run_one_iteration` computes must REACH the battery call.

D352, from a live defect: `below_inception` (the chain-inception exclusion set) was computed
per batch, echoed to the journal as `chain_inception: excluding 22 underlying(s) (...)`, and
then **never passed** to `_run_battery_for_seed`. The parameter took its `None` default, so
enumeration ran unfiltered from `fa00daf` through the v53 deploy while the journal line
asserted the opposite. A downstream reader verified the feature against that log line and
recorded a closed loop that did not exist.

The bug class is not "someone forgot one kwarg" — it is that a dropped enumeration input is
SILENT. The value still gets computed, the log still prints, the suite still passes, and the
only symptom is emission that quietly ignores a filter. Hard rule #6 makes this worse than
cosmetic: enumeration inputs are part of the emission identity, so dropping one means the
recorded `(grammar_version, registry_hash, seed)` no longer reproduces the stream.

So this guards the CLASS, statically: any local in `_run_one_iteration` whose name matches a
keyword parameter of `_run_battery_for_seed` must be forwarded under that name. Static
analysis rather than a behavioural test on purpose — the defect is a missing edge in the call
graph, and an emission test would need the whole daemon path (DB, registry, cache) to observe
what `ast` can prove in milliseconds.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MAIN = Path(__file__).resolve().parents[2] / "src" / "forge" / "cli" / "main.py"
_BATTERY = "_run_battery_for_seed"
_ITERATION = "_run_one_iteration"


def _module() -> ast.Module:
    return ast.parse(_MAIN.read_text())


def _func(mod: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(mod):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {_MAIN} — did it get renamed?")


def _battery_call(fn: ast.FunctionDef) -> ast.Call:
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == _BATTERY
        ):
            return node
    raise AssertionError(f"no {_BATTERY}(...) call inside {_ITERATION}")


def _keyword_params(fn: ast.FunctionDef) -> set[str]:
    return {a.arg for a in fn.args.kwonlyargs} | {a.arg for a in fn.args.args}


def _assigned_locals(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_below_inception_reaches_the_battery() -> None:
    """The exact regression. Computed at the top of the iteration, forwarded at the call."""
    call = _battery_call(_func(_module(), _ITERATION))
    forwarded = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    assert "below_inception" in forwarded, (
        "`below_inception` is computed and journal-logged in "
        f"{_ITERATION} but NOT passed to {_BATTERY} — enumeration runs UNFILTERED while the "
        "journal claims names are excluded. This is the D352 defect verbatim."
    )
    value = forwarded["below_inception"]
    # Forward the computed local, not a literal or a rebound name — otherwise the journal line
    # and the emission can disagree again, which is the whole defect.
    assert isinstance(value, ast.Name)
    assert value.id == "below_inception"


def test_no_computed_enumeration_input_is_silently_dropped() -> None:
    """The class guard: any local sharing a name with a battery parameter must be forwarded.

    A name collision between a local in the iteration and a keyword of the battery is not a
    coincidence in this file — it means someone computed the input the battery declares. If it
    is deliberately withheld, pass it explicitly (`x=None`) so the omission is visible in the
    diff rather than inferred from its absence.
    """
    mod = _module()
    iteration = _func(mod, _ITERATION)
    params = _keyword_params(_func(mod, _BATTERY)) - {"self"}
    call = _battery_call(iteration)
    forwarded = {kw.arg for kw in call.keywords if kw.arg}
    # Positional args are forwarded too (grammar, registry, seed, ...); map them by position.
    battery = _func(mod, _BATTERY)
    positional = {a.arg for a in battery.args.args[: len(call.args)]}
    computed = _assigned_locals(iteration) & params
    dropped = sorted(computed - forwarded - positional)
    assert not dropped, (
        f"{_ITERATION} computes {dropped} but does not pass them to {_BATTERY}. "
        "A computed-then-discarded enumeration input is invisible: the value is built, any "
        "log line still prints, and emission silently ignores it (hard rule #6)."
    )
