"""v47 (D328) — single-name trend/MR retirement + relval/event_momentum disable.

Crucible reads: single-name trend/MR = 0 consumption across all 106 assemblies
(FORGE_single_name_trend_mr_retirement_read); event_momentum single-name-only +
dead, its book use the D268 SOXL degenerate (FORGE_event_momentum_soxl_degenerate
_reply, xsect-PEAD withdrawn); capitulation EXEMPTED (the momentum cell is the
program's only positive-slot-delta cell, FORGE_capitulation_exempt_v47).

Mechanism: `relative_value` + `event_momentum` -> DISABLED_HYPOTHESES; the iterator
filters retired single-name (confluence) trend/MR, keeping xsect (the converting
core) + the momentum/capitulation single-name cell. `sample_config` is byte-
identical (the sampler goldens hold); this is an emission-policy filter.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

from forge.enumeration import enumerate_candidates
from forge.grammar.loader import load_grammar
from forge.grammar.models import Grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
# xsect must actually draw so trend/MR keep a live form under the filter.
_SHARE = {"trend_continuation": 0.6, "mean_reversion": 0.6}


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(
        _REPO_ROOT / "config" / "grammar.yaml",
        archive_dir=_REPO_ROOT / "config" / "grammar_archive",
    )


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


def _configs(grammar: Grammar, registry: RegistrySnapshot, n: int = 6000) -> list:
    return list(
        enumerate_candidates(
            grammar, registry, seed=0, max_candidates=n, rank_combiner_share=_SHARE
        )
    )


def _directional(cfg) -> str | None:  # type: ignore[no-untyped-def]
    return next((s.indicators[0] for s in cfg.signals if s.role == "directional"), None)


def test_relative_value_and_event_momentum_disabled(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    hyps = {cfg.hypothesis for cfg in _configs(grammar, registry)}
    assert "relative_value" not in hyps
    assert "event_momentum" not in hyps


def test_no_single_name_trend_or_mr_except_capitulation(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every confluence (single-name) trend/MR config is retired, EXCEPT the
    momentum/capitulation cell (single-name-only, exempt)."""
    for cfg in _configs(grammar, registry):
        if cfg.hypothesis not in ("trend_continuation", "mean_reversion"):
            continue
        if cfg.combiner.type == "cross_sectional_rank":
            continue  # xsect — the converting core, kept
        # the only surviving single-name trend/MR is the momentum capitulation cell
        assert cfg.hypothesis == "mean_reversion", cfg.name
        assert _directional(cfg) == "momentum", cfg.name


def test_xsect_trend_and_mr_preserved(grammar: Grammar, registry: RegistrySnapshot) -> None:
    axes = Counter(
        (cfg.hypothesis, "xsect" if cfg.combiner.type == "cross_sectional_rank" else "named")
        for cfg in _configs(grammar, registry)
    )
    assert axes[("trend_continuation", "xsect")] > 0
    assert axes[("mean_reversion", "xsect")] > 0


def test_capitulation_cell_still_emits_single_name(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    # capitulation needs the registry that serves `momentum` (the D270 setup);
    # the minimal fixture does not.
    from tests.unit.test_enumeration.test_sampler import _v31_registry

    reg = _v31_registry(registry)
    momentum_mr = [
        cfg
        for cfg in _configs(grammar, reg)
        if cfg.hypothesis == "mean_reversion" and _directional(cfg) == "momentum"
    ]
    assert momentum_mr, "capitulation (momentum MR) must survive the retirement"
    # it is single-name only (momentum is rank-excluded) — the exemption holds
    assert all(cfg.combiner.type != "cross_sectional_rank" for cfg in momentum_mr)


def test_retired_single_name_is_counted_as_a_rejection(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    counter: Counter[str] = Counter()
    list(
        enumerate_candidates(
            grammar,
            registry,
            seed=0,
            max_candidates=500,
            rank_combiner_share=_SHARE,
            rejection_counter=counter,
        )
    )
    assert counter["retired_single_name"] > 0
