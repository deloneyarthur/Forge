"""Registered ``custom_python`` predicate functions.

The grammar's ``custom_python`` predicate type names a function by string;
``REGISTRY`` maps that string to the actual callable. Unknown names raise
``GrammarLoadError`` at load time (enforced by the loader), so by the time
``evaluate_custom_python`` runs, the registry lookup is guaranteed to
succeed.

Why a name registry instead of ``eval``/``exec``: see D017 + CLAUDE.md
hard rule on no-LLM-in-the-loop. The grammar YAML must never resolve to
arbitrary Python; it can only name functions that have been explicitly
registered in this module.

Module structure:

- Stub predicates (``always_pass`` / ``always_fail``) ship with Phase 1
  for testing the dispatch machinery. They have no production use.
- The 16 §3.5 predicate functions (S4/S5/C1/C2/C4/P1-P3/E1-E3/R1-R3/X1-X2)
  land in subsequent modules as the ``grammar.yaml`` is populated.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from forge.grammar.models import PredicateResult

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig


CustomPredicateFn = Callable[["StrategyConfig", "RegistrySnapshot"], PredicateResult]


def _always_pass(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Stub: returns passed=True regardless of input. Used to test the
    dispatch path end-to-end without requiring a real domain function."""
    del config, registry
    return PredicateResult(passed=True)


def _always_fail(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Stub: returns passed=False. Companion to ``_always_pass``."""
    del config, registry
    return PredicateResult(passed=False, detail="custom_python: always_fail stub")


REGISTRY: dict[str, CustomPredicateFn] = {
    "always_pass": _always_pass,
    "always_fail": _always_fail,
}


def register(name: str, fn: CustomPredicateFn) -> None:
    """Register a custom-predicate function. Duplicate names raise
    ``ValueError`` so the registry can't be silently overwritten.

    Intended for use within this module (declarative registration of the
    §3.5 predicate functions in subsequent modules). External callers
    should add their function to this module directly rather than reaching
    in at import time.
    """
    if name in REGISTRY:
        msg = f"custom-predicate name {name!r} already registered"
        raise ValueError(msg)
    REGISTRY[name] = fn


__all__ = ["REGISTRY", "CustomPredicateFn", "register"]
