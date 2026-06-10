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

from crucible_contracts import CombinerSpec, RegistrySnapshot

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
    # D116 (v14) re-pin: this test forced mean_reversion through D112's window,
    # but MR's whole R1 regime pool ({iv_rank, gamma_flip}) is single-name-only
    # now, so MR structurally never ranks — trend_continuation (bar-only R2
    # gates: adx/hurst/rv_rank) is the rank arm that still emits.
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    single_name_only = _single_name_only_ids(reg)
    share = {"trend_continuation": 1.0}  # force the rank branch
    ks: set[int] = set()
    rebs: set[str | None] = set()
    dirs: set[str | None] = set()
    for seed in range(120):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="trend_continuation",
            rank_combiner_share=share,
        )
        if any(ind in single_name_only for s in cfg.signals for ind in s.indicators):
            # D112/D116: single-name-only draws never take the rank branch —
            # covered by the skip tests below.
            continue
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
    """§2.4 said event_momentum's productive form is cross-sectional PEAD —
    D118 (v15) re-pin: em structurally never ranks. Crucible's indicator→mode
    map (`rank_gate_class_map.json`) classifies H2's WHOLE signal set as broken
    on the rank path: `sue` and `days_since_earnings` are per-name events keyed
    on ``params["symbol"]``, which the rank path never threads — the sue
    directional would rank the universe on NaN (the dealer-directional 0/8
    pattern) and the timing gate is inert fail-open. Every em draw stays
    single-name confluence (the composable path pins the symbol; both
    indicators are coherent there) until Crucible threads per-name symbols on
    the rank path. Keep-side asserted: the sue directional + dse gate pair is
    still emitted single-name at full weight."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"event_momentum": 1.0}
    seen_sue_directional = seen_dse_gate = 0
    for seed in range(120):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="event_momentum",
            rank_combiner_share=share,
        )
        assert cfg.combiner.type == "confluence", cfg.name
        assert cfg.underlying is not None, cfg.name
        assert validate(cfg, grammar, reg).valid  # type: ignore[arg-type]
        if any(s.role == "directional" and "sue" in s.indicators for s in cfg.signals):
            seen_sue_directional += 1
        if any(
            s.role == "regime_filter" and "days_since_earnings" in s.indicators for s in cfg.signals
        ):
            seen_dse_gate += 1
    # Non-vacuous: the H2 signal pair is still drawn — the cut moved the
    # combiner, not the hypothesis's single-name emission.
    assert seen_sue_directional > 0
    assert seen_dse_gate > 0


def test_rank_draw_allowed_for_kelly_ev_sizer_chain() -> None:
    """D118 (v15) role-scoping pin: `expected_value_estimator` is excluded from
    the rank branch only as a GATE or DIRECTIONAL (on the rank path an EV gate
    is the reference underlying's runs-DB EV for every name —
    hidden_uniform_reference per Crucible's map — never the ranked name's own).
    The X2 fractional_kelly sizer chain (role="confluence" passthrough) is
    reference-keyed on EVERY path — single-name kelly configs size off the same
    default-underlying EV with empty params — so it must NOT block the rank
    branch. Guards against over-cutting: a kelly-sized trend rank config is as
    coherent as any other trend rank config."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"trend_continuation": 1.0}
    seen_kelly_rank = 0
    for seed in range(300):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="trend_continuation",
            rank_combiner_share=share,
        )
        has_ev_chain = any(
            s.role == "confluence" and "expected_value_estimator" in s.indicators
            for s in cfg.signals
        )
        if has_ev_chain:
            assert cfg.combiner.type == "cross_sectional_rank", cfg.name
            seen_kelly_rank += 1
    # Non-vacuous: the kelly-sized rank shape must actually be drawn.
    assert seen_kelly_rank > 0


# ---------------------------------------------------------------------------
# D112 (v13) — dealer indicators are single-name only: no rank draw carries one
# ---------------------------------------------------------------------------


def _dealer_ids(reg: RegistrySnapshot) -> frozenset[str]:
    return frozenset(ind.id for ind in reg.indicators if ind.family == "dealer_positioning")


def _single_name_only_ids(reg: RegistrySnapshot) -> frozenset[str]:
    return _dealer_ids(reg) | frozenset({"iv_rank", "put_call_flow"})


def test_rank_draw_skipped_for_dealer_signal_configs() -> None:
    """D112 (v13): a config that drew ANY dealer_positioning signal must not
    take the rank branch even at share 1.0 — it stays single-name confluence.

    Cross-sectional x dealer is Crucible's ~100x headline-cost runner tail
    (5-14 min vs 1-3 s single-name), and the decided universe-wide dealer
    cohort cleared no §8.7 gate. The single-name dealer frontier is untouched:
    the config keeps its signals and a pinned underlying — it just never
    multiplies a per-bar greek grid across the universe.

    D116 (v14) re-pin: the non-dealer MR draws used to take the rank branch;
    they are iv_rank-gated (R1) and iv_rank is chain-reading, so they now skip
    too — every MR draw stays single-name. Both shapes are still asserted
    distinctly so the dealer-skip and chain-skip mechanisms stay individually
    covered."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    dealer = _dealer_ids(reg)
    assert dealer, "fixture registry must carry dealer indicators for this test"
    share = {"mean_reversion": 1.0}
    seen_dealer = seen_chain_only = 0
    for seed in range(300):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="mean_reversion",
            rank_combiner_share=share,
        )
        assert cfg.combiner.type == "confluence", cfg.name
        assert cfg.underlying is not None, cfg.name
        if any(ind in dealer for s in cfg.signals for ind in s.indicators):
            seen_dealer += 1
        else:
            # No dealer signal -> the skip was the chain-reading iv_rank gate.
            seen_chain_only += 1
    # Both skip mechanisms must actually be exercised, or the test is vacuous.
    assert seen_dealer > 0
    assert seen_chain_only > 0


# ---------------------------------------------------------------------------
# D116 (v14) — chain-reading indicators are single-name only: MR never ranks
# ---------------------------------------------------------------------------


def test_rank_draw_skipped_for_chain_reading_gate_configs() -> None:
    """D116 (v14): a config that drew ANY chain-reading signal (iv_rank,
    put_call_flow — Q33, Crucible's fail-open sweep) must not take the rank
    branch even at share 1.0. On Crucible's rank path the chain underlying is
    read from ``params["underlying"]`` (default SPY) regardless of the ranked
    name, so iv_rank fires on noise (SPY's chain IV interpolated at the name's
    spot) and put_call_flow is a hidden uniform SPY gate. §3.5 R1 pins
    mean_reversion's regime pool to {iv_rank, gamma_flip_distance_pct} and both
    are single-name only → EVERY mean_reversion draw stays single-name
    confluence; the rank branch is structurally unreachable for MR until a
    coherent reference-underlying gate exists Crucible-side (the Q33 trigger)."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"mean_reversion": 1.0}
    seen_iv_rank_gate = 0
    for seed in range(300):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="mean_reversion",
            rank_combiner_share=share,
        )
        assert cfg.combiner.type == "confluence", cfg.name
        assert cfg.underlying is not None, cfg.name
        if any(s.role == "regime_filter" and "iv_rank" in s.indicators for s in cfg.signals):
            seen_iv_rank_gate += 1
    # Non-vacuous: the chain-gated shape (the v13 noise-gated arm) was drawn.
    assert seen_iv_rank_gate > 0


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
