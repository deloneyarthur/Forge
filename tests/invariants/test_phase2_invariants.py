"""Phase 2 invariants — enumeration-discipline checks.

Each invariant maps to a CLAUDE.md hard rule or a §13 production-quality
requirement. Owned by the enumeration phase; new rules add tests here.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import pytest

from forge.enumeration import (
    EnumerationCapped,
    enumerate_candidates,
    registry_hash,
)
from forge.enumeration._demo_registry import demo_registry
from forge.grammar import Grammar, load_grammar, validate
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


# ---------------------------------------------------------------------------
# §13.1 / CLAUDE.md hard rule #6 — enumeration determinism
# ---------------------------------------------------------------------------


def test_enumeration_byte_identical_for_same_triple(grammar: Grammar) -> None:
    """Two enumerations under the same (grammar_version, registry_hash, seed)
    must yield byte-identical config hashes in byte-identical order."""
    registry = demo_registry()
    seed = 137
    n = 100
    a = [c.config_hash for c in enumerate_candidates(grammar, registry, seed, max_candidates=n)]
    b = [c.config_hash for c in enumerate_candidates(grammar, registry, seed, max_candidates=n)]
    assert a == b
    # Triple-log sanity: registry_hash matches between calls (no time-dep).
    assert registry_hash(registry) == registry_hash(demo_registry())


def test_enumeration_diverges_when_seed_changes(grammar: Grammar) -> None:
    registry = demo_registry()
    a = [c.config_hash for c in enumerate_candidates(grammar, registry, 1, max_candidates=20)]
    b = [c.config_hash for c in enumerate_candidates(grammar, registry, 2, max_candidates=20)]
    assert a != b


# ---------------------------------------------------------------------------
# CLAUDE.md hard rule #7 — no equity-family signal in any yielded config
# ---------------------------------------------------------------------------


def test_no_equity_family_indicator_in_any_yielded_config(grammar: Grammar) -> None:
    """The contracts ``IndicatorMetadata.family`` Literal already forbids
    'equity', but defense in depth: every enumerated config's signals must
    only reference indicators whose family is non-'equity'."""
    registry = demo_registry()
    by_id = {ind.id: ind for ind in registry.indicators}
    for cfg in enumerate_candidates(grammar, registry, seed=0, max_candidates=50):
        for sig in cfg.signals:
            for ind_id in sig.indicators:
                family = by_id[ind_id].family
                assert family != "equity", (
                    f"hard rule #7 violated: signal {sig.id!r} uses "
                    f"indicator {ind_id!r} of family 'equity'"
                )


# ---------------------------------------------------------------------------
# D5 — Forge never emits equity_hedge_metadata
# ---------------------------------------------------------------------------


def test_equity_hedge_metadata_is_none_for_every_yielded_config(grammar: Grammar) -> None:
    registry = demo_registry()
    for cfg in enumerate_candidates(grammar, registry, seed=3, max_candidates=50):
        assert cfg.equity_hedge_metadata is None, (
            f"D5 violated: config {cfg.name!r} carries equity_hedge_metadata"
        )


# ---------------------------------------------------------------------------
# §4.5 — output cardinality contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", [1, 10, 100, 500])
def test_iterator_yields_exactly_max_candidates(grammar: Grammar, target: int) -> None:
    registry = demo_registry()
    count = sum(1 for _ in enumerate_candidates(grammar, registry, 0, max_candidates=target))
    assert count == target


# ---------------------------------------------------------------------------
# §4.5 — property: 1000 enumerated configs all pass the Phase 1 validator
# ---------------------------------------------------------------------------


def test_enumerated_configs_pass_grammar_validation_at_1000_scale(
    grammar: Grammar,
) -> None:
    """The §4.2 contract: every yielded config is grammar-valid. If the
    sampler ever leaks an invalid config, the iterator's safety-net
    `validate()` is supposed to drop it — this test confirms the contract
    holds at scale."""
    registry = demo_registry()
    failures: list[str] = []
    n = 0
    for cfg in enumerate_candidates(grammar, registry, seed=2026, max_candidates=1000):
        n += 1
        result = validate(cfg, grammar, registry)
        if not result.valid:
            failures.append(f"{cfg.config_hash}: {result.errors}")
    assert n == 1000
    assert not failures, f"{len(failures)} invalid configs leaked: {failures[:5]}"


def test_v1_fixture_rejection_rate_is_zero(grammar: Grammar) -> None:
    """The closure-plan path (a) contract: v1-fixture enumeration should
    produce 100% sampler→validator success. Catches regressions where the
    sampler stops being valid-by-construction."""
    counter: Counter[str] = Counter()
    list(
        enumerate_candidates(
            grammar,
            minimal_registry_snapshot(),
            seed=0,
            max_candidates=200,
            rejection_counter=counter,
        )
    )
    assert sum(counter.values()) == 0, f"unexpected rejections: {dict(counter)}"


# ---------------------------------------------------------------------------
# §4.5 — perf: 100K configs in < 5 min
# ---------------------------------------------------------------------------


def test_perf_100k_configs_under_five_minutes(grammar: Grammar) -> None:
    """§4.5 acceptance criterion: enumerating 100K configs must complete in
    under 5 min (300s). On the v1 fixture we're typically ~15s, leaving
    20x headroom. If this slows down dramatically, suspect a regression
    in sampler or validator."""
    registry = demo_registry()
    t0 = time.perf_counter()
    count = 0
    for _ in enumerate_candidates(grammar, registry, seed=0, max_candidates=100_000):
        count += 1
    elapsed = time.perf_counter() - t0
    assert count == 100_000
    assert elapsed < 300.0, f"perf regression: 100K configs took {elapsed:.1f}s (budget 300s)"


# ---------------------------------------------------------------------------
# Hard-failure surfacing — EnumerationCapped reaches the caller
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# D066 — overlay-only hypotheses (tail_hedge) must never be enumerated as
# a StrategyConfig. Crucible's runner rejects them at dispatch as
# RunnerError; pre-D066, 1851/4039 = 45.8% of inbox configs were wasted
# tail_hedge round-trips.
# ---------------------------------------------------------------------------


def test_d066_no_overlay_only_hypothesis_in_any_yielded_config(
    grammar: Grammar,
) -> None:
    """At N=500 across a small seed sweep, the iterator must never emit a
    config whose ``hypothesis`` is in ``OVERLAY_ONLY_HYPOTHESES``."""
    from forge.enumeration.search_space import OVERLAY_ONLY_HYPOTHESES

    registry = demo_registry()
    seen_overlay: list[str] = []
    for seed in (0, 1, 7, 137, 2026):
        for cfg in enumerate_candidates(
            grammar,
            registry,
            seed=seed,
            max_candidates=100,
        ):
            if cfg.hypothesis in OVERLAY_ONLY_HYPOTHESES:
                seen_overlay.append(f"seed={seed} hash={cfg.config_hash} hyp={cfg.hypothesis}")
    assert not seen_overlay, (
        f"D066 violated: {len(seen_overlay)} overlay-only configs leaked: {seen_overlay[:5]}"
    )


def test_d066_overlay_only_hypothesis_blocked_when_forced(grammar: Grammar) -> None:
    """The sampler must reject a ``forced_hypothesis`` in the overlay-only
    set — the production iterator's D037 rotation should never select one,
    but a direct sampler call must still surface SamplerError so test
    callers don't accidentally bypass D066."""
    import random

    from forge.enumeration.sampler import SamplerError, sample_config
    from forge.enumeration.search_space import build_search_space

    registry = demo_registry()
    space = build_search_space(grammar, registry)
    with pytest.raises(SamplerError, match=r"forced_hypothesis='tail_hedge'"):
        sample_config(
            space,
            registry,
            random.Random(0),
            forced_hypothesis="tail_hedge",
        )


# ---------------------------------------------------------------------------
# D098 (v5) — regime_arbitrage dropped from enumeration (low-yield by
# construction: its mandatory regime_filter stacks contradictory regime
# concepts that rarely co-align — 81% zero-trade, no edge thesis). It stays a
# valid hand-authored hypothesis (grammar.yaml S1 lists it; hard rule #1) but
# Forge's runtime policy never enumerates it. See `DISABLED_HYPOTHESES`.
# ---------------------------------------------------------------------------


def test_d098_no_disabled_hypothesis_in_any_yielded_config(grammar: Grammar) -> None:
    """Across a seed sweep at N=200, the iterator must never emit a config
    whose ``hypothesis`` is in ``DISABLED_HYPOTHESES`` (regime_arbitrage)."""
    from forge.enumeration.search_space import DISABLED_HYPOTHESES

    registry = demo_registry()
    leaked: list[str] = []
    for seed in (0, 1, 7, 137, 2026):
        for cfg in enumerate_candidates(grammar, registry, seed=seed, max_candidates=200):
            if cfg.hypothesis in DISABLED_HYPOTHESES:
                leaked.append(f"seed={seed} hash={cfg.config_hash} hyp={cfg.hypothesis}")
    assert not leaked, (
        f"D098 violated: {len(leaked)} disabled-hypothesis configs leaked: {leaked[:5]}"
    )


def test_d098_relative_value_underlying_is_none_at_scale(grammar: Grammar) -> None:
    """Every enumerated relative_value config carries underlying=None — it's a
    pairs strategy whose legs Crucible resolves itself (reverts D079)."""
    registry = demo_registry()
    seen_relative_value = False
    for cfg in enumerate_candidates(grammar, registry, seed=2026, max_candidates=500):
        if cfg.hypothesis == "relative_value":
            seen_relative_value = True
            assert cfg.underlying is None, (
                f"D098 violated: relative_value config {cfg.config_hash} has "
                f"underlying={cfg.underlying!r}, expected None"
            )
    assert seen_relative_value, "expected at least one relative_value config in 500"


def test_capped_is_loud_for_unsatisfiable_registries(grammar: Grammar) -> None:
    from datetime import UTC, date, datetime

    from crucible_contracts import MANDATORY_EXIT_IDS, RegistrySnapshot

    bad = RegistrySnapshot(
        indicators=(),
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
        data_start_date=date(2022, 1, 1),
    )
    with pytest.raises(EnumerationCapped):
        list(enumerate_candidates(grammar, bad, seed=0, max_candidates=1))


# ---------------------------------------------------------------------------
# D037 — stratified hypothesis sampling floor
# ---------------------------------------------------------------------------


def test_d037_stratification_floor_guarantees_each_hypothesis(grammar: Grammar) -> None:
    """D037: with min_hypothesis_fraction > 0 every samplable hypothesis
    appears at least ``ceil(max_candidates * fraction)`` times.

    Pre-D037 the Bayesian failure-weights collapsed enumeration onto
    1-4 hypotheses: across 4020 historical submissions only ONE was
    `mean_reversion` and ZERO were `trend_continuation`. The 2% floor
    forces a minimum representation per samplable hypothesis.
    """
    registry = demo_registry()
    max_candidates = 600
    fraction = 0.05  # → ceil(600 * 0.05) = 30 per hypothesis
    configs = list(
        enumerate_candidates(
            grammar,
            registry,
            seed=137,
            max_candidates=max_candidates,
            min_hypothesis_fraction=fraction,
        )
    )
    assert len(configs) == max_candidates
    from collections import Counter

    hyps = Counter(c.hypothesis for c in configs)
    expected_floor = 30
    samplable = [h for h, _ in hyps.most_common() if hyps[h] >= 1]
    # Every hypothesis that's present at all must clear the floor.
    # (Some hypotheses may not be samplable on the demo registry —
    # those legitimately have 0 picks; the floor only binds for hypotheses
    # that have non-empty directional + regime pools.)
    for h in samplable:
        assert hyps[h] >= expected_floor, (
            f"hypothesis {h} only got {hyps[h]} picks (< floor {expected_floor})"
        )


def test_d037_stratification_disabled_when_fraction_zero(grammar: Grammar) -> None:
    """fraction=0 disables D037 — preserves legacy behavior for tests
    that pin specific config sequences."""
    registry = demo_registry()
    configs = list(
        enumerate_candidates(
            grammar,
            registry,
            seed=137,
            max_candidates=100,
            min_hypothesis_fraction=0.0,
        )
    )
    # With fraction=0 and weighted sampling, distribution should follow
    # the natural Bayesian weights — i.e., it can collapse onto 1-2
    # hypotheses. We just assert the run completed successfully.
    assert len(configs) == 100


def test_d037_floor_caps_at_50pct_of_budget(grammar: Grammar) -> None:
    """A tiny ``max_candidates`` with a large ``fraction`` doesn't starve
    the weighted-sample path. The floor is capped so total forced ≤ 50%
    of the budget.

    Without the cap: a test with max_candidates=4 and fraction=0.5 would
    request 2 forced picks per hypothesis x ~6 hypotheses = 12 forced
    picks for a 4-config budget => EnumerationCapped.
    """
    registry = demo_registry()
    # Should NOT raise EnumerationCapped under the 50% cap.
    configs = list(
        enumerate_candidates(
            grammar,
            registry,
            seed=42,
            max_candidates=4,
            min_hypothesis_fraction=0.5,  # would request 2/hyp without cap
        )
    )
    assert len(configs) == 4


def test_d037_determinism_preserved_with_stratification(grammar: Grammar) -> None:
    """Same triple + same fraction → identical sequence (hard rule #6)."""
    registry = demo_registry()
    a = [
        c.config_hash
        for c in enumerate_candidates(
            grammar,
            registry,
            seed=2026,
            max_candidates=120,
            min_hypothesis_fraction=0.05,
        )
    ]
    b = [
        c.config_hash
        for c in enumerate_candidates(
            grammar,
            registry,
            seed=2026,
            max_candidates=120,
            min_hypothesis_fraction=0.05,
        )
    ]
    assert a == b
