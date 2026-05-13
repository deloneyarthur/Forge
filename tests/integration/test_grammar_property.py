"""§12 Phase 1 acceptance: property tests.

    1000 random *grammar-valid* configs all pass validation.
    1000 random *grammar-invalid* configs all fail with at least one
    named error.

Sampling strategies + mutators live in
``tests/fixtures/grammar_property_helpers.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings

from forge.grammar import load_grammar, validate
from tests.fixtures.grammar_property_helpers import (
    invalid_strategy_config_case,
    valid_strategy_config,
)
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


@pytest.fixture(scope="module")
def grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> object:
    return minimal_registry_snapshot()


@given(cfg=valid_strategy_config())
@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_1000_valid_configs_pass(
    cfg: object,
    grammar: object,
    registry: object,
) -> None:
    """Every config drawn from the valid-config strategy must pass the
    grammar. If this fails the example printed by Hypothesis is the
    config that broke a rule despite the template claiming validity."""
    result = validate(cfg, grammar, registry)  # type: ignore[arg-type]
    assert result.valid, (
        f"valid config failed unexpectedly:\n  hypothesis={cfg.hypothesis}\n"  # type: ignore[attr-defined]
        f"  errors={result.errors}"
    )


@given(case=invalid_strategy_config_case())
@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_1000_invalid_configs_fail_named(
    case: tuple[object, str],
    grammar: object,
    registry: object,
) -> None:
    """Every mutated config must fail the validator AND the failure list
    must name the rule the mutator broke."""
    cfg, expected_rule = case
    result = validate(cfg, grammar, registry)  # type: ignore[arg-type]
    assert not result.valid, (
        f"mutated config to break {expected_rule} passed validation; "
        f"mutator left no observable failure"
    )
    failing_ids = {e.split(":", 1)[0] for e in result.errors}
    assert expected_rule in failing_ids, (
        f"expected mutator to fail rule {expected_rule}, but validator named: {sorted(failing_ids)}"
    )
