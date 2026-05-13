"""Tests for ``forge.grammar.path_resolver.resolve``.

Covers: bare attribute, dotted path, list projection, §3.4 sugar filter,
JSONPath filter, indexed access, error cases. Two syntaxes for filter
(§3.4 sugar + JSONPath) are exercised against the same fixture.
"""

from __future__ import annotations

import pytest

from forge.grammar.path_resolver import resolve
from tests.fixtures.strategy_configs import minimal_strategy_config


def test_resolve_bare_attribute() -> None:
    cfg = minimal_strategy_config()
    assert resolve(cfg, "hypothesis") == ["mean_reversion"]


def test_resolve_dotted_scalar() -> None:
    cfg = minimal_strategy_config()
    assert resolve(cfg, "sizer.per_trade_risk_pct") == [0.02]


def test_resolve_list_attribute_flattens() -> None:
    cfg = minimal_strategy_config()
    result = resolve(cfg, "signals")
    assert len(result) == 2
    assert {s.id for s in result} == {"sig_directional", "sig_regime"}


def test_resolve_list_projection() -> None:
    cfg = minimal_strategy_config()
    result = resolve(cfg, "signals.id")
    assert result == ["sig_directional", "sig_regime"]


def test_resolve_sugar_filter_directional() -> None:
    """§3.4 sugar: ``signals.role.directional`` — filter signals where
    role equals ``directional``."""
    cfg = minimal_strategy_config()
    result = resolve(cfg, "signals.role.directional")
    assert len(result) == 1
    assert result[0].id == "sig_directional"


def test_resolve_sugar_filter_regime() -> None:
    cfg = minimal_strategy_config()
    result = resolve(cfg, "signals.role.regime_filter")
    assert len(result) == 1
    assert result[0].id == "sig_regime"


def test_resolve_sugar_filter_no_match() -> None:
    cfg = minimal_strategy_config()
    assert resolve(cfg, "signals.role.confluence") == []


def test_resolve_jsonpath_filter() -> None:
    """JSONPath primitive — equivalent to the §3.4 sugar form."""
    cfg = minimal_strategy_config()
    result = resolve(cfg, 'signals[?(@.role=="directional")]')
    assert len(result) == 1
    assert result[0].id == "sig_directional"


def test_resolve_sugar_and_jsonpath_agree() -> None:
    cfg = minimal_strategy_config()
    sugar = resolve(cfg, "signals.role.directional")
    jsonpath = resolve(cfg, 'signals[?(@.role=="directional")]')
    assert sugar == jsonpath


def test_resolve_indexed_access() -> None:
    cfg = minimal_strategy_config()
    result = resolve(cfg, "signals[0].id")
    assert result == ["sig_directional"]


def test_resolve_indexed_into_list_value() -> None:
    cfg = minimal_strategy_config()
    result = resolve(cfg, "signals[0].indicators")
    assert result == ["rsi_2"]


def test_resolve_unknown_attribute_raises() -> None:
    cfg = minimal_strategy_config()
    with pytest.raises(AttributeError):
        resolve(cfg, "nonexistent_field")


def test_resolve_empty_path_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        resolve(minimal_strategy_config(), "")


def test_resolve_unbalanced_brackets_rejected() -> None:
    with pytest.raises(ValueError, match="unbalanced"):
        resolve(minimal_strategy_config(), "signals[0")


def test_resolve_index_on_non_list_raises() -> None:
    with pytest.raises(TypeError):
        resolve(minimal_strategy_config(), "hypothesis[0]")


def test_resolve_unrecognized_bracket_raises() -> None:
    with pytest.raises(ValueError, match="unrecognized"):
        resolve(minimal_strategy_config(), "signals[oops]")


def test_resolve_on_dict_root() -> None:
    """Path resolver supports plain dicts so it can be used against arbitrary
    nested structures (e.g., the ``IndicatorMetadata.params_schema``)."""
    result = resolve({"a": {"b": 42}}, "a.b")
    assert result == [42]


def test_resolve_returns_list_for_scalar() -> None:
    cfg = minimal_strategy_config()
    result = resolve(cfg, "tier")
    assert result == [1]
