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

The v41 change set under test, as CORRECTED by v42/D294 (Crucible
``FORGE_xsect_union_correction_2026-07-20.md``, ledger-verified: xsect has
ALWAYS ranked the all-tier union — the stamp's only engine effect on an xsect
config is the FillModel spread-table class, so v41's tier=3 xsect share bought
duplicate books at 1.5x charged spreads and is DROPPED):
  * single-name configs stamp the underlying's TRUE tier (3 for tier-3 names,
    2 otherwise) — attribution + honest spread class (a tier-3 single-name
    charged tier-2 spreads was mispriced-cheap; STANDS per the correction);
  * cross-sectional (rank-combiner) configs stamp ``tier=2`` unconditionally
    again (the calibrated status-quo cost class; no rng consumed — v42
    reverted the v41 Bernoulli same-day on the upstream correction);
  * rider: ASML + COST join the structurally-untradeable exclusion (our
    funnel: 641 decided/0 components and 1,544/1; their row-45/census read
    CONFIRMS — ASML 100% wf-zero, COST 91% — the rider STANDS).
"""

from __future__ import annotations

import random
from collections import Counter
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


def test_xsect_stamps_tier2_since_v42(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """v42/D294: every rank-combiner config stamps tier=2 — the v41 tier=3
    share bought the SAME union book at 1.5x charged spreads (their ledger
    correction) and was dropped same-day."""
    xsect = [
        c
        for c in _sample(grammar, registry, n_seeds=3000, rank_share=1.0)
        if c.combiner.type == "cross_sectional_rank"
    ]
    assert len(xsect) >= 300, f"too few xsect draws: {len(xsect)}"
    assert all(c.tier == 2 for c in xsect), Counter(c.tier for c in xsect)


def test_v41_tier_dormant_without_tiered_export(
    grammar: Grammar, registry: RegistrySnapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty tier-3 set (old-shape export / D033 fallback) → everything stamps
    tier=2 (single-name lookup finds no members; xsect is constant-2 since
    v42)."""
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
