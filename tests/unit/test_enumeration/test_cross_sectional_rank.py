"""H1 (v12 / D109) — cross_sectional_rank combiner (the breadth lever).

The binding constraint on promotion is breadth: ``min_oos_trade_count >= 100``
kills ~98% of candidates, and directional archetypes fire ~1 trade on a single
name. The cross_sectional_rank combiner replaces per-name boolean firing with
score → rank → trade-top-K → rebalance, so trade count becomes deterministic
(``~rank_k * rebalances`` ≫ 100) — defeating the floor for the breadth-starved
directional archetypes (trend_continuation, mean_reversion, event_momentum).

It is an opt-in combiner OPTION gated on ``rank_combiner_share`` so the cold
path stays byte-identical (hard rule #6). The runner routes a config whose
``combiner.type == 'cross_sectional_rank'`` to Crucible's composable rank runner
(reads ``combiner.rank_k``); the directional signal drives the rank score, the
regime_filter signal gates. ``underlying`` is None — the runner ranks
``universe.tickers(asof, tier)``, so a single name is meaningless.
"""

from __future__ import annotations

import random
from pathlib import Path

from crucible_contracts import CombinerSpec

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import RANK_COMBINER_HYPOTHESES, build_search_space
from forge.grammar import load_grammar, validate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


def _grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


# ---------------------------------------------------------------------------
# Scope — §1.2: only the breadth-starved directional archetypes
# ---------------------------------------------------------------------------


def test_rank_eligible_set() -> None:
    assert (
        frozenset({"trend_continuation", "mean_reversion", "event_momentum"})
        == RANK_COMBINER_HYPOTHESES
    )


# ---------------------------------------------------------------------------
# Emission — a forced rank draw produces a valid rank config
# ---------------------------------------------------------------------------


def test_rank_combiner_emitted_when_forced() -> None:
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"mean_reversion": 1.0}  # force the rank branch
    ks: set[int] = set()
    rebs: set[str | None] = set()
    dirs: set[str | None] = set()
    for seed in range(120):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="mean_reversion",
            rank_combiner_share=share,
        )
        assert cfg.combiner.type == "cross_sectional_rank"
        assert cfg.combiner.rank_k in (5, 10, 20)
        assert cfg.combiner.rebalance_frequency in ("weekly", "monthly")
        assert cfg.combiner.direction_mode in ("long_only", "long_short")
        # The runner ranks the universe; a single underlying is meaningless.
        assert cfg.underlying is None
        # Signals are preserved: directional drives the rank score, regime gates.
        roles = {s.role for s in cfg.signals}
        assert "directional" in roles
        assert "regime_filter" in roles
        assert validate(cfg, grammar, reg).valid, validate(cfg, grammar, reg).errors  # type: ignore[arg-type]
        ks.add(cfg.combiner.rank_k)
        rebs.add(cfg.combiner.rebalance_frequency)
        dirs.add(cfg.combiner.direction_mode)
    # All option values are exercised over the seed sweep.
    assert ks == {5, 10, 20}
    assert rebs == {"weekly", "monthly"}
    assert dirs == {"long_only", "long_short"}


def test_rank_combiner_emitted_for_event_momentum() -> None:
    """§2.4 — event_momentum's productive form is cross-sectional PEAD."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    cfg = sample_config(
        space,
        reg,
        random.Random(7),
        forced_hypothesis="event_momentum",
        rank_combiner_share={"event_momentum": 1.0},
    )
    assert cfg.combiner.type == "cross_sectional_rank"
    assert cfg.underlying is None
    assert validate(cfg, grammar, reg).valid  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Determinism — hard rule #6: the cold path is byte-identical
# ---------------------------------------------------------------------------


def test_cold_path_byte_identical() -> None:
    """No rank_combiner_share (None or {}) → byte-identical to the bare call.
    The rank block must consume zero rng draws on the cold path."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    for seed in range(80):
        bare = sample_config(space, reg, random.Random(seed))
        none_ = sample_config(space, reg, random.Random(seed), rank_combiner_share=None)
        empty = sample_config(space, reg, random.Random(seed), rank_combiner_share={})
        assert bare == none_
        assert bare == empty
        assert bare.combiner.type == "confluence"


def test_rank_share_zero_is_byte_identical() -> None:
    """A 0.0 share for an eligible hypothesis must short-circuit (no rng draw) →
    byte-identical, combiner stays confluence."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"trend_continuation": 0.0}
    for seed in range(60):
        base = sample_config(
            space, reg, random.Random(seed), forced_hypothesis="trend_continuation"
        )
        zero = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="trend_continuation",
            rank_combiner_share=share,
        )
        assert base == zero
        assert zero.combiner.type == "confluence"


def test_rank_share_does_not_perturb_ineligible_hypothesis() -> None:
    """volatility_event is event-single-name, NOT rank-eligible (§1.2). A share map
    including it must leave its draw byte-identical and its combiner confluence."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"volatility_event": 1.0}
    for seed in range(60):
        base = sample_config(space, reg, random.Random(seed), forced_hypothesis="volatility_event")
        withshare = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="volatility_event",
            rank_combiner_share=share,
        )
        assert base == withshare
        assert withshare.combiner.type == "confluence"


# ---------------------------------------------------------------------------
# Dedup / config_hash — §1.3.5: rank fields are identity-bearing for rank type
# ---------------------------------------------------------------------------


def test_rank_configs_hash_distinctly() -> None:
    def _rank(**kw: object):
        spec: dict[str, object] = {
            "type": "cross_sectional_rank",
            "rank_k": 5,
            "rebalance_frequency": "weekly",
            "direction_mode": "long_only",
        }
        spec.update(kw)
        return minimal_strategy_config(combiner=CombinerSpec(**spec), underlying=None)

    confluence = minimal_strategy_config()  # default confluence
    hashes = {
        confluence.config_hash,
        _rank().config_hash,
        _rank(rank_k=10).config_hash,
        _rank(rebalance_frequency="monthly").config_hash,
        _rank(direction_mode="long_short").config_hash,
    }
    # Confluence + 4 distinct rank variants → 5 distinct identity hashes.
    assert len(hashes) == 5
