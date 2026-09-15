"""Every enumeration input the weekly run computes must REACH `enumerate_candidates`.

D352 (v53 deploy, 2026-08-02): the daemon computed and journal-logged `below_inception` but never
passed it to the enumerator, so generation ran UNFILTERED while the log claimed names were
excluded — a journal line is not an emission proof. Re-targeted (Batch 5 G1) from
`cli/main._run_one_iteration` to `campaign/run.enumerate_population`, the one place the weekly
run enumerates. Guarded statically: the call must forward the structural inputs by keyword, and
any local the function computes whose name is an `enumerate_candidates` parameter must be
forwarded (pass `x=None` explicitly if deliberately withheld, so the omission is visible in a diff).
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "forge"
_RUN = _SRC / "campaign" / "run.py"
_ITERATOR = _SRC / "enumeration" / "iterator.py"
_ENUMERATE = "enumerate_population"
_CALLEE = "enumerate_candidates"
_STRUCTURAL_INPUTS = ("below_inception", "refutation_effects", "min_hypothesis_fraction")


def _func(path: Path, name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path} — did it get renamed?")


def _callee_call(fn: ast.FunctionDef) -> ast.Call:
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == _CALLEE
        ):
            return node
    raise AssertionError(f"no {_CALLEE}(...) call inside {_ENUMERATE}")


def _assigned_locals(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_structural_inputs_are_forwarded_by_keyword() -> None:
    """The exact D352 regression class: chain-inception exclusions and refutation effects."""
    call = _callee_call(_func(_RUN, _ENUMERATE))
    forwarded = {kw.arg for kw in call.keywords if kw.arg}
    missing = [name for name in _STRUCTURAL_INPUTS if name not in forwarded]
    assert not missing, (
        f"{_ENUMERATE} does not pass {missing} to {_CALLEE} — enumeration would run without "
        "them while the run record claims otherwise (D352 verbatim)."
    )


def test_no_computed_enumeration_input_is_silently_dropped() -> None:
    fn = _func(_RUN, _ENUMERATE)
    callee = _func(_ITERATOR, _CALLEE)
    params = {a.arg for a in callee.args.kwonlyargs} | {a.arg for a in callee.args.args}
    call = _callee_call(fn)
    forwarded = {kw.arg for kw in call.keywords if kw.arg}
    positional = {a.arg for a in callee.args.args[: len(call.args)]}
    computed = _assigned_locals(fn) & params
    dropped = sorted(computed - forwarded - positional)
    assert not dropped, (
        f"{_ENUMERATE} computes {dropped} but does not pass them to {_CALLEE}. A "
        "computed-then-discarded enumeration input is invisible (hard rule #6)."
    )
