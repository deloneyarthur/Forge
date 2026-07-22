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
from forge.enumeration.search_space import (
    RANK_COMBINER_HYPOTHESES,
    build_search_space,
    rank_excluded_indicator_ids,
)
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


def test_event_momentum_retired_not_rank_forceable() -> None:
    """D328 (v47): event_momentum is retired into DISABLED_HYPOTHESES (§2.4's
    cross-sectional PEAD form never materialized — `sue` is rank-excluded, so em
    was single-name-only + dead; Crucible withdrew the xsect-PEAD ask). It is no
    longer samplable, so forcing it raises — the rank-vs-single-name question is
    moot."""
    import pytest

    from forge.enumeration.sampler import SamplerError

    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    with pytest.raises(SamplerError):
        sample_config(space, reg, random.Random(0), forced_hypothesis="event_momentum")


def test_rank_draw_blocked_for_kelly_ev_sizer_chain() -> None:
    """D125 (v16) — deliberate INVERSION of the v15 over-cut guard.

    v15 exempted the X2 kelly EV chain (role="confluence") from the rank skip
    on the premise that it was EV-as-SIZING. D122 corrected the premise from
    Crucible's code: EV-as-sizing has no live wiring anywhere (no template
    passes `expected_value` into the sizer), and on the rank path a confluence
    signal IS a rank-score factor — where a warm EV is provably output-neutral
    (uniform across names → zero-variance → all-zero z-scores) and a cold one
    freezes the config (uniform NaN → empty scores → rebalance no-ops).
    Eligibility buys nothing and carries the freeze class, so v16 keys the
    rank skip on `rank_per_name_coherent` for ALL roles, confluence included.
    Kelly-chain draws keep full single-name weight (X2 untouched there)."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"trend_continuation": 1.0}
    seen_kelly_confluence = seen_rank = 0
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
            assert cfg.combiner.type == "confluence", cfg.name
            assert cfg.underlying is not None, cfg.name
            seen_kelly_confluence += 1
        elif cfg.combiner.type == "cross_sectional_rank":
            seen_rank += 1
    # Non-vacuous both ways: kelly chains are still drawn (single-name), and
    # the rank arm still emits for non-kelly trend draws.
    assert seen_kelly_confluence > 0
    assert seen_rank > 0


def test_rank_exclusion_keys_on_registry_flags_not_identity() -> None:
    """D125 (v16) — the rank skip reads `rank_per_name_coherent` off the
    registry, not an explicit id list: flipping a known-coherent bar-only id
    (adx) to False/False in an otherwise identical registry must pull every
    adx-using trend draw off the rank branch. This is the auto-inherit
    property — a future indicator with fail-closed flags is excluded the same
    way without any Forge release (under v15 it was rank-eligible the moment
    it appeared: the fail-open hole behind the dealer/iv_rank confounded
    eras). A *truly* novel id can't even be drawn until it has a
    threshold-table entry, so the flag check is exercised through an id the
    sampler can actually draw."""
    grammar = _grammar()
    base = minimal_registry_snapshot()
    flipped = base.model_copy(
        update={
            "indicators": tuple(
                ind.model_copy(
                    update={"rank_per_name_coherent": False, "market_wide_by_design": False}
                )
                if ind.id == "adx"
                else ind
                for ind in base.indicators
            )
        }
    )
    space = build_search_space(grammar, flipped)
    share = {"trend_continuation": 1.0}
    seen_adx = seen_rank_without_adx = 0
    for seed in range(300):
        cfg = sample_config(
            space,
            flipped,
            random.Random(seed),
            forced_hypothesis="trend_continuation",
            rank_combiner_share=share,
        )
        uses_adx = any("adx" in s.indicators for s in cfg.signals)
        if uses_adx:
            assert cfg.combiner.type == "confluence", cfg.name
            assert cfg.underlying is not None, cfg.name
            seen_adx += 1
        elif cfg.combiner.type == "cross_sectional_rank":
            seen_rank_without_adx += 1
    # Non-vacuous: adx draws happen and get pinned single-name; the rank arm
    # survives on the still-coherent gates.
    assert seen_adx > 0
    assert seen_rank_without_adx > 0


def test_dealer_family_excluded_even_if_flagged_coherent() -> None:
    """D125 (v16) green-both-sides guard: the dealer cut is NOT flag-keyed.

    D115's re-admission clause needs the reference-gate built AND coherent
    single-name MRxgamma evidence — a Crucible flag flip alone is only half
    the trigger (and the D112 ~100x runner-cost rationale is independent of
    coherence). A future registry that flips dealer ids to
    `rank_per_name_coherent=True` must still never rank."""
    grammar = _grammar()
    base = minimal_registry_snapshot()
    flipped = base.model_copy(
        update={
            "indicators": tuple(
                ind.model_copy(update={"rank_per_name_coherent": True})
                if ind.family == "dealer_positioning"
                else ind
                for ind in base.indicators
            )
        }
    )
    space = build_search_space(grammar, flipped)
    dealer = _dealer_ids(flipped)
    share = {"mean_reversion": 1.0, "trend_continuation": 1.0}
    seen_dealer = 0
    for seed in range(300):
        for offset, hyp in enumerate(("mean_reversion", "trend_continuation")):
            cfg = sample_config(
                space,
                flipped,
                random.Random(seed * 2 + offset),
                forced_hypothesis=hyp,
                rank_combiner_share=share,
            )
            if any(ind in dealer for s in cfg.signals for ind in s.indicators):
                assert cfg.combiner.type == "confluence", cfg.name
                seen_dealer += 1
    assert seen_dealer > 0


# ---------------------------------------------------------------------------
# D112 (v13) — dealer indicators are single-name only: no rank draw carries one
# ---------------------------------------------------------------------------


def _dealer_ids(reg: RegistrySnapshot) -> frozenset[str]:
    return frozenset(ind.id for ind in reg.indicators if ind.family == "dealer_positioning")


def _single_name_only_ids(reg: RegistrySnapshot) -> frozenset[str]:
    # D125 (v16) re-pin: the exclusion set is flag-derived production truth
    # (was a hand-rolled dealer|{iv_rank,put_call_flow} mirror through v15).
    # Using the production function keeps the forced-rank test's skip filter
    # from silently drifting as Crucible flips flags.
    return rank_excluded_indicator_ids(reg)


def test_rank_draw_skipped_for_dealer_signal_configs() -> None:
    """D112 (v13): a config that drew ANY dealer_positioning signal must not
    take the rank branch even at share 1.0 — it stays single-name confluence.

    Cross-sectional x dealer is Crucible's ~100x headline-cost runner tail
    (5-14 min vs 1-3 s single-name), and the decided universe-wide dealer
    cohort cleared no §8.7 gate. The single-name dealer frontier is untouched:
    the config keeps its signals and a pinned underlying — it just never
    multiplies a per-bar greek grid across the universe.

    D116 (v14) re-pin: the non-dealer MR draws used to take the rank branch;
    they are iv_rank-gated (R1) and iv_rank is chain-reading, so they skip too.
    D151 (v21) re-pin: MR's hurst gate is bar-based and per-name-coherent (Q33),
    so a hurst-gated MR config now RANKS — the skip applies ONLY to the
    single-name-only families (dealer, chain-reading iv_rank). Assert confluence
    for those gates specifically; hurst-gated MR is covered by
    `test_mean_reversion_hurst_gate_ranks_chain_gate_does_not`."""
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
        sig_inds = {ind for s in cfg.signals for ind in s.indicators}
        has_dealer = any(ind in dealer for ind in sig_inds)
        has_iv_rank = "iv_rank" in sig_inds
        if has_dealer or has_iv_rank:
            # the single-name-only skip (dealer D112 / chain-reading iv_rank D116)
            # keeps these confluence even at share 1.0 — D151 left this guard intact.
            assert cfg.combiner.type == "confluence", cfg.name
            assert cfg.underlying is not None, cfg.name
            if has_dealer:
                seen_dealer += 1
            else:
                seen_chain_only += 1
    # Both skip mechanisms must actually be exercised, or the test is vacuous.
    assert seen_dealer > 0
    assert seen_chain_only > 0


# ---------------------------------------------------------------------------
# D116 (v14) — chain-reading indicators are single-name only: they never rank.
# (D151/v21: this is now gate-specific — the hurst-gated MR draw DOES rank.)
# ---------------------------------------------------------------------------


def test_rank_draw_skipped_for_chain_reading_gate_configs() -> None:
    """D116 (v14): a config that drew a chain-reading regime gate (iv_rank,
    put_call_flow) must not take the rank branch even at share 1.0 — on Crucible's
    rank path those default their chain underlying to SPY regardless of the ranked
    name (iv_rank fires on noise, Q33 fail-open sweep), so they stay single-name.
    D151 (v21) re-pin: this is now keyed on the published `rank_per_name_coherent`
    flag (`space.rank_excluded_ids`) — iv_rank (False) stays confluence; the
    bar-based hurst gate (True) ranks (covered separately). Assert confluence
    specifically for the iv_rank-gated draw."""
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
        if any(s.role == "regime_filter" and "iv_rank" in s.indicators for s in cfg.signals):
            # chain-reading gate → flag-based skip keeps it single-name confluence
            assert cfg.combiner.type == "confluence", cfg.name
            assert cfg.underlying is not None, cfg.name
            seen_iv_rank_gate += 1
    # Non-vacuous: the chain-gated shape (the v13 noise-gated arm) was drawn.
    assert seen_iv_rank_gate > 0


def test_mean_reversion_hurst_gate_ranks_chain_gate_does_not() -> None:
    """D151 (v21): Q33 ANSWERED YES — `hurst.rank_per_name_coherent = True` (the rank
    runner reads each name's own price-autocorrelation hurst, no reference chain). So
    hurst-gated mean_reversion now RANKS (the breadth lever); the D150
    `_RANK_INELIGIBLE_HYPOTHESES` hold is removed. The chain-reading iv_rank gate
    stays single-name confluence via the flag-based skip (`space.rank_excluded_ids`,
    keyed on the published `rank_per_name_coherent` flag) — D116 stays correct for it."""
    grammar = _grammar()
    reg = minimal_registry_snapshot()
    space = build_search_space(grammar, reg)
    share = {"mean_reversion": 1.0}
    hurst_rank = 0
    iv_rank_seen = 0
    for seed in range(300):
        cfg = sample_config(
            space,
            reg,
            random.Random(seed),
            forced_hypothesis="mean_reversion",
            rank_combiner_share=share,
        )
        regimes = {ind for s in cfg.signals if s.role == "regime_filter" for ind in s.indicators}
        if "hurst" in regimes and cfg.combiner.type == "cross_sectional_rank":
            hurst_rank += 1
        if "iv_rank" in regimes:
            # chain-reader: D116 flag-based skip keeps it single-name confluence
            assert cfg.combiner.type == "confluence", f"chain-gated mr ranked: {cfg.name}"
            iv_rank_seen += 1
    assert hurst_rank > 0  # D151: hurst-gated mr now ranks (the enable)
    assert iv_rank_seen > 0  # non-vacuous: iv_rank drawn + stayed confluence (flag-based skip)


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
