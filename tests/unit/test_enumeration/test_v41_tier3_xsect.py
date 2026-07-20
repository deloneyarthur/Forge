"""v41 tier unpin — Crucible's 2026-07-20 tier-unpin reply
(``FORGE_tier_unpin_and_promote_2026-07-20.md``; triage D292, scoping
``docs/proposals/v41-tier3-xsect.md``).

Their correction (verified): tier-3 names were never absent — the folded
export ``tier_2`` key has fed the enumerator all 94 for weeks. The REAL pin is
the literal ``tier=2`` stamp, and its cost is cross-sectional: the engine
resolves an xsect config's ranking pool from the STAMP against PIT membership,
so every xsect config ever emitted ranked the TRUE 20-name curated tier-2 pool
(rank_k=20 = take-everything) and the 94-name tier-3 xsect pool has never been
sampled.

The v41 change set under test:
  * single-name configs stamp the underlying's TRUE tier (3 for tier-3 names,
    2 otherwise) — attribution fix, engine behavior unchanged for single-name;
  * cross-sectional (rank-combiner) configs stamp ``tier=3`` at p=0.15 (their
    10-20% band, xsect-first per their suggestion) — the engine then ranks the
    tier-3 PIT pool; the other ~85% keep the true-tier-2 pool as today;
  * export-gated dormancy: an empty tier-3 set (old-shape export / D033
    fallback) short-circuits BEFORE any rng draw — everything stamps 2;
  * rider: ASML + COST join the structurally-untradeable exclusion (our
    funnel: 641 decided/0 components and 1,544/1 — the v37 dead-cell class).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot, StrategyConfig

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot
from tests.fixtures.universe_snapshot import UNIVERSE_TIER3_SNAPSHOT_2026_07_20

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(
        _REPO_ROOT / "config" / "grammar.yaml",
        archive_dir=_REPO_ROOT / "config" / "grammar_archive",
    )


@pytest.fixture
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


def _sample(
    grammar: Grammar,
    registry: RegistrySnapshot,
    *,
    n_seeds: int,
    rank_share: float = 0.0,
) -> list[StrategyConfig]:
    space = build_search_space(grammar, registry)
    share = (
        {h: rank_share for h in ("trend_continuation", "mean_reversion", "event_momentum")}
        if rank_share
        else None
    )
    return [
        sample_config(space, registry, random.Random(seed), rank_combiner_share=share)
        for seed in range(n_seeds)
    ]


def test_v41_single_name_stamps_true_tier(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """A single-name config's tier is the underlying's TRUE tier from the
    tiered export: 3 for tier-3 members, 2 otherwise."""
    seen_t3 = seen_t2 = 0
    for cfg in _sample(grammar, registry, n_seeds=1500):
        if cfg.underlying is None:
            continue
        if cfg.underlying in UNIVERSE_TIER3_SNAPSHOT_2026_07_20:
            assert cfg.tier == 3, (cfg.underlying, cfg.tier)
            seen_t3 += 1
        else:
            assert cfg.tier == 2, (cfg.underlying, cfg.tier)
            seen_t2 += 1
    assert seen_t3 >= 100, f"too few tier-3 single-name draws: {seen_t3}"
    assert seen_t2 >= 50, f"too few tier-2 single-name draws: {seen_t2}"


def test_v41_xsect_tier3_share(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Rank-combiner configs stamp tier=3 at ~0.15; the rest keep tier=2."""
    xsect = [
        c
        for c in _sample(grammar, registry, n_seeds=3000, rank_share=1.0)
        if c.combiner.type == "cross_sectional_rank"
    ]
    assert len(xsect) >= 300, f"too few xsect draws: {len(xsect)}"
    assert all(c.tier in (2, 3) for c in xsect)
    share = sum(1 for c in xsect if c.tier == 3) / len(xsect)
    assert 0.10 < share < 0.20, f"xsect tier-3 share {share:.3f} not ~0.15"


def test_v41_tier_dormant_without_tiered_export(
    grammar: Grammar, registry: RegistrySnapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty tier-3 set (old-shape export / D033 fallback) → everything stamps
    tier=2 and the xsect share draw is short-circuited (export-gated dormancy,
    the D258 empty-pool convention)."""
    import forge.enumeration.sampler as sampler_mod

    monkeypatch.setattr(sampler_mod, "_tier3_symbols", frozenset)
    for cfg in _sample(grammar, registry, n_seeds=600, rank_share=1.0):
        assert cfg.tier == 2, (cfg.name, cfg.underlying, cfg.tier)


def test_v41_asml_cost_never_drawn(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The D292 rider: ASML/COST join the structural exclusion (drawn-but-dead
    single-name: 641 decided/0 components, 1,544/1 on our funnel)."""
    drawn = {c.underlying for c in _sample(grammar, registry, n_seeds=2000) if c.underlying}
    assert "ASML" not in drawn
    assert "COST" not in drawn
    assert len(drawn) > 60, f"pool unexpectedly small: {len(drawn)}"


def test_v41_universe_fingerprint_carries_tier_split(
    grammar: Grammar, registry: RegistrySnapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H-3: the fingerprint must move when the tier SPLIT moves (same union,
    different split → different emission since v41), and must reduce to the
    pre-v41 value when tier-3 is empty (continuity for old-shape exports)."""
    import forge.enumeration.sampler as sampler_mod

    with_t3 = sampler_mod.universe_fingerprint()
    monkeypatch.setattr(sampler_mod, "_tier3_symbols", frozenset)
    without_t3 = sampler_mod.universe_fingerprint()
    assert with_t3 != without_t3
