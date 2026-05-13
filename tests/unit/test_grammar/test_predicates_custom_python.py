"""Tests for the ``custom_python`` predicate dispatch + registry pattern.

The registry pattern is the load-bearing security boundary per D017: YAML
can name functions but cannot define them, so a malicious or typo'd
``grammar.yaml`` cannot execute arbitrary code.

Two stub predicates ship with Phase 1: ``always_pass`` and ``always_fail``.
They exist solely to exercise the dispatch path end-to-end. The 16 §3.5
predicate functions land in subsequent modules.
"""

from __future__ import annotations

import pytest

from forge.grammar import evaluate
from forge.grammar.custom_predicates import REGISTRY, register
from forge.grammar.models import (
    CustomPythonPredicate,
    GrammarLoadError,
    PredicateResult,
)
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)


def _registry() -> object:
    return minimal_registry_snapshot()


def test_always_pass_stub_dispatches() -> None:
    p = CustomPythonPredicate(type="custom_python", function="always_pass")
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert result.passed
    assert result.detail == ""


def test_always_fail_stub_dispatches() -> None:
    p = CustomPythonPredicate(type="custom_python", function="always_fail")
    result = evaluate(p, minimal_strategy_config(), _registry())
    assert not result.passed
    assert "always_fail" in result.detail


def test_unknown_function_raises_grammar_load_error() -> None:
    """A custom_python predicate naming an unregistered function must
    raise at evaluation (the loader will additionally reject this at load
    time; the predicate-level check is the second line of defense)."""
    p = CustomPythonPredicate(type="custom_python", function="not_in_registry")
    with pytest.raises(GrammarLoadError) as exc:
        evaluate(p, minimal_strategy_config(), _registry())
    assert "not_in_registry" in str(exc.value)
    assert "registry" in str(exc.value)


def test_registry_contains_phase1_stubs() -> None:
    """Phase 1 ships the two stub functions; the registry must expose them
    by name. (Subsequent modules add S4/S5/etc. — those go in their own
    tests.)"""
    assert "always_pass" in REGISTRY
    assert "always_fail" in REGISTRY


def test_register_rejects_duplicate_name() -> None:
    """The ``register`` helper guards against silent overwrites — the
    grammar must have a one-to-one mapping from name to function."""
    with pytest.raises(ValueError, match="already registered"):
        register("always_pass", lambda c, r: PredicateResult(passed=True))


def test_register_adds_new_function() -> None:
    """Adding a fresh name works; afterwards `evaluate` can dispatch to it."""
    name = "test_fixture_added"
    if name in REGISTRY:
        # ensure clean slate even if a prior failed test left a dangling entry
        del REGISTRY[name]

    def _fixture_predicate(config: object, registry: object) -> PredicateResult:
        del config, registry
        return PredicateResult(passed=True, detail="")

    register(name, _fixture_predicate)
    try:
        p = CustomPythonPredicate(type="custom_python", function=name)
        result = evaluate(p, minimal_strategy_config(), _registry())
        assert result.passed
    finally:
        del REGISTRY[name]


def test_registry_functions_callable_with_correct_signature() -> None:
    """Each registered function takes (config, registry) and returns
    PredicateResult. Smoke-check the stubs."""
    cfg = minimal_strategy_config()
    reg = minimal_registry_snapshot()
    for name, fn in REGISTRY.items():
        result = fn(cfg, reg)
        assert isinstance(result, PredicateResult), f"{name} returned non-PredicateResult"
