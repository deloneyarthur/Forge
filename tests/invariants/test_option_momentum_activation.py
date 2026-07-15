"""v33 (D276) invariants — option_momentum directional RETIREMENT.

History: v19 (D138) activated option_momentum as a trend_continuation
directional (percentile-only + the probe-audited min_months=3 coverage floor —
see git for the activation-era invariants). A month of live funnel later,
Crucible's generation-health audit (`FORGE_generation_health_capitulation_
addendum_2026-07-15.md` §B) measured the cell 100% structurally dead: 47
configs/wk, median 5 OOS trades over 2018-2026, ~0 component conversions —
the single deadest directional in the grammar. v33 retires it from EMISSION
(pool exclusion; the threshold-table entry and the C2 smart_money family
admission stay, so the submitted lineage remains interpretable and the X2
kelly chain feature is untouched).

The invariant now guards the RETIREMENT: option_momentum must never re-enter
directional emission by accident (a family-derived pool rebuild, a registry
flag change, a C2 edit). Re-admission is a deliberate operator-gated grammar
bump, never a side effect.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import SignalSpec, StrategyConfig

from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import load_grammar
from forge.persistence.registry_loader import load_registry


def _load_space() -> tuple[object, object]:
    grammar_path = Path(__file__).resolve().parents[2] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()
    return build_search_space(grammar, registry), registry


@pytest.fixture(scope="module")
def sampled_configs() -> list[StrategyConfig]:
    """A deterministic population large enough that the retired id would show
    up if it leaked back into any pool (pre-v33 it appeared tens of times in
    4000 draws)."""
    space, registry = _load_space()
    rng = random.Random(0)
    configs: list[StrategyConfig] = []
    for _ in range(4000):
        try:
            configs.append(sample_config(space, registry, rng))
        except SamplerError:
            continue
    return configs


def _is_directional_on(sig: SignalSpec, indicator_id: str) -> bool:
    return sig.role == "directional" and indicator_id in sig.indicators


def test_option_momentum_registry_guard() -> None:
    """Guard against vacuity: the registry (live or fixture fallback) still
    advertises option_momentum — the zero-emission assertions below must mean
    RETIRED, not unregistered."""
    _space, registry = _load_space()
    ids = {ind.id for ind in registry.indicators}  # type: ignore[attr-defined]
    if "option_momentum" not in ids:
        pytest.skip("registry does not serve option_momentum — retirement unobservable")


def test_option_momentum_never_a_directional(sampled_configs: list[StrategyConfig]) -> None:
    """The v33 retirement holds structurally: zero option_momentum directionals
    across the population, for every hypothesis."""
    leaked = [
        cfg
        for cfg in sampled_configs
        if any(_is_directional_on(s, "option_momentum") for s in cfg.signals)
    ]
    assert not leaked, (
        f"{len(leaked)} option_momentum directionals leaked back into emission "
        f"(first: {leaked[0].name} under {leaked[0].hypothesis!r}) — re-admission "
        "must be a deliberate operator-gated bump, not a pool-rebuild side effect"
    )


def test_expected_value_estimator_never_directional(
    sampled_configs: list[StrategyConfig],
) -> None:
    """Unchanged since v19: smart_money in trend's C2 families must NOT make EV
    a directional. It is pinned out (directional range nulled →
    is_threshold_skippable), staying the X2 kelly sizer feature."""
    for cfg in sampled_configs:
        for sig in cfg.signals:
            if sig.role == "directional" and sig.indicators:
                assert sig.indicators[0] != "expected_value_estimator", (
                    f"EV leaked as a directional under {cfg.hypothesis!r}: {sig.params}"
                )
