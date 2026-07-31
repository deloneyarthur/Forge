"""v52 (D328 freeze programme, second prune) — capitulation retirement.

`momentum` is retired as a `mean_reversion` directional, and with it the R1
per-directional bare-drop exemption that exists only to serve it. Two tables shrink to
empty: `_C2_HYPOTHESIS_EXTRA_IDS` (the D270/v31 per-id carve-out admitting `momentum`
into MR's directional pool) and `_R1_GATE_EXEMPT_DIRECTIONALS` (the D280/v35 bare-drop).

WHY (prereg `0a5ddc861aae`). The v47 exemption carried a defined close-out — the cell folds
into a later prune if it fails its adoption episode. All-time across every momentum-as-MR
cell: 619 submitted, 603 decided, **0 components, 0 promotes**, median CPCV negative in both
bare-drop buckets (-0.3142 swing_mid, -0.2621 swing_short), best-ever 1.1598 against a
0.9439 book-usability floor.

THE LESSON THE TRIAL TAUGHT, because it generalises past this cell: the v35 bare-drop
improved every INTERMEDIATE metric — median 13 OOS trades vs 4, WF-zero 70% vs 97.3% — and
both improvements held while producing zero components. Trade-count and WF-zero gains are
not evidence of component production.

This is an emission-policy tightening (hard rule #4), so the enumeration sequence shifts and
the sampler goldens re-pin; `sample_config` itself is untouched.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

from forge.enumeration import enumerate_candidates
from forge.grammar.custom_predicates import (
    _C2_HYPOTHESIS_EXTRA_IDS,
    _R1_GATE_EXEMPT_DIRECTIONALS,
)
from forge.grammar.loader import load_grammar
from forge.grammar.models import Grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
# xsect must actually draw so trend/MR keep a live form (the converting core).
_SHARE = {"trend_continuation": 0.6, "mean_reversion": 0.6}


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(
        _REPO_ROOT / "config" / "grammar.yaml",
        archive_dir=_REPO_ROOT / "config" / "grammar_archive",
    )


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    """The registry that SERVES `momentum` (the D270 setup). The minimal fixture does not,
    so every emission assertion below would pass vacuously on it — proving nothing about a
    retirement whose whole content is that an id stops being emitted."""
    from tests.unit.test_enumeration.test_sampler import _v31_registry

    return _v31_registry(minimal_registry_snapshot())


def _configs(grammar: Grammar, registry: RegistrySnapshot, n: int = 6000) -> list:
    return list(
        enumerate_candidates(
            grammar, registry, seed=0, max_candidates=n, rank_combiner_share=_SHARE
        )
    )


def _directional(cfg) -> str | None:  # type: ignore[no-untyped-def]
    return next((s.indicators[0] for s in cfg.signals if s.role == "directional"), None)


def test_momentum_is_no_longer_an_mr_directional(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The emission proof the prereg predicts: zero momentum mean_reversion configs."""
    offenders = [
        cfg.name
        for cfg in _configs(grammar, registry)
        if cfg.hypothesis == "mean_reversion" and _directional(cfg) == "momentum"
    ]
    assert offenders == []


def test_the_two_carve_out_tables_are_empty() -> None:
    """Both loosenings are withdrawn, not merely bypassed — a bypassed carve-out is a
    latent re-admission the next person to touch the sampler cannot see."""
    assert _C2_HYPOTHESIS_EXTRA_IDS == {}
    assert frozenset() == _R1_GATE_EXEMPT_DIRECTIONALS


def test_no_single_name_trend_or_mr_remains(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """v47 retired single-name trend/MR with capitulation as the sole exemption; with the
    exemption withdrawn the axis is now empty, which is the whole point of the prune."""
    for cfg in _configs(grammar, registry):
        if cfg.hypothesis not in ("trend_continuation", "mean_reversion"):
            continue
        assert cfg.combiner.type == "cross_sectional_rank", cfg.name


def test_every_mr_config_carries_a_regime_gate(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """R1 is whole again: the bare-drop was the only gate-less MR arm, so no MR config
    may now ship without a regime gate."""
    for cfg in _configs(grammar, registry):
        if cfg.hypothesis != "mean_reversion":
            continue
        assert any(s.role == "regime_filter" for s in cfg.signals), cfg.name


def test_the_converting_core_is_untouched(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The prune must not cost xsect supply — the prereg's falsifier is a conversion drop,
    and the cheapest way to cause one is to starve the slot the dead cell shared."""
    axes = Counter(
        (cfg.hypothesis, "xsect" if cfg.combiner.type == "cross_sectional_rank" else "named")
        for cfg in _configs(grammar, registry)
    )
    assert axes[("trend_continuation", "xsect")] > 0
    assert axes[("mean_reversion", "xsect")] > 0
