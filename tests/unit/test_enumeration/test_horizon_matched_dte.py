"""v8 (D102) horizon-matched DTE — sampler behavioral invariants.

These pin the generation-time guarantee the Crucible handoff asked for: the
DTE bucket is DERIVED from the directional signal's Forge-owned horizon
(``k * horizon`` for the oscillator/trend hypotheses, an event-bracket for
volatility_event), not sampled blind. They complement the pure-function tests
in ``tests/unit/test_grammar/test_signal_horizon.py``.

All assertions are against the hand-crafted fixture registry, whose semantic
horizons match ``forge.grammar.signal_horizon`` (the live registry's
``IndicatorMetadata.lookback`` is degenerate — that is exactly why the table
exists, see D102).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot, StrategyConfig

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar
from forge.grammar.signal_horizon import buckets_for_horizon_class, horizon_class
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


def _sample(grammar: Grammar, registry: RegistrySnapshot, seed: int) -> StrategyConfig:
    space = build_search_space(grammar, registry)
    return sample_config(space, registry, random.Random(seed))


def _directional_id(cfg: StrategyConfig) -> str:
    directional = next(s for s in cfg.signals if s.role == "directional")
    assert len(directional.indicators) == 1
    return directional.indicators[0]


def _sample_many(
    grammar: Grammar, registry: RegistrySnapshot, n: int = 400
) -> list[StrategyConfig]:
    return [_sample(grammar, registry, seed) for seed in range(n)]


# ---------------------------------------------------------------------------
# Core invariant: the bucket is always one §3.5 S4 permits for the directional
# ---------------------------------------------------------------------------


def test_bucket_is_permitted_by_directional_horizon_class(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every sampled config's dte_bucket sits in the directional indicator's
    horizon-class-permitted set — the §3.5 S4 guarantee, now horizon-driven and
    valid by construction (the iterator's validator would also catch a breach)."""
    for cfg in _sample_many(grammar, registry):
        allowed = buckets_for_horizon_class(horizon_class(_directional_id(cfg)))
        assert cfg.dte_bucket in allowed, (
            f"{_directional_id(cfg)} (class {horizon_class(_directional_id(cfg))}) "
            f"emitted dte_bucket={cfg.dte_bucket}, allowed={allowed}"
        )


# ---------------------------------------------------------------------------
# Per-hypothesis horizon matching
# ---------------------------------------------------------------------------


def test_volatility_event_brackets_event_short_or_mid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """vol_event uses the event-bracket target (lead + post-window), never a k
    multiple of a long horizon — so it lands swing_short / swing_mid, matching
    the handoff's "brackets the event"."""
    seen = {
        cfg.dte_bucket
        for cfg in _sample_many(grammar, registry)
        if cfg.hypothesis == "volatility_event"
    }
    assert seen, "no volatility_event configs sampled"
    assert seen <= {"swing_short", "swing_mid"}, f"vol_event reached {seen}"


def test_mean_reversion_rsi2_is_pinned_swing_short(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """rsi_2 has a 2-day horizon (short class) -> swing_short for every k."""
    rsi2 = [
        cfg
        for cfg in _sample_many(grammar, registry)
        if cfg.hypothesis == "mean_reversion" and _directional_id(cfg) == "rsi_2"
    ]
    assert rsi2, "no mean_reversion rsi_2 configs sampled"
    assert all(cfg.dte_bucket == "swing_short" for cfg in rsi2)


def test_trend_continuation_long_horizon_reaches_swing_long(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """momentum_252 (252-day horizon, long class) with k in {2,3,4} -> a target
    far past swing_long's midpoint, so trend configs reach swing_long and never
    collapse to swing_short (the pre-v8 degenerate-registry failure)."""
    trend = [
        cfg for cfg in _sample_many(grammar, registry) if cfg.hypothesis == "trend_continuation"
    ]
    assert trend, "no trend_continuation configs sampled"
    assert all(cfg.dte_bucket in {"swing_mid", "swing_long"} for cfg in trend)
    assert any(cfg.dte_bucket == "swing_long" for cfg in trend)


def test_relative_value_pairs_short_or_mid_unchanged(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """relative_value keeps a uniform bucket pick among its S4-permitted set
    (pairs_zscore is medium-class -> swing_short/mid); Crucible adapts the real
    DTE per pair at runtime off the live half-life."""
    rv = [cfg for cfg in _sample_many(grammar, registry) if cfg.hypothesis == "relative_value"]
    assert rv, "no relative_value configs sampled"
    buckets = {cfg.dte_bucket for cfg in rv}
    assert buckets <= {"swing_short", "swing_mid"}, f"relative_value reached {buckets}"


# ---------------------------------------------------------------------------
# Determinism (#6) across the reordered (directional-first) path
# ---------------------------------------------------------------------------


def test_same_seed_same_bucket_directional_regime(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    for seed in range(50):
        a = _sample(grammar, registry, seed)
        b = _sample(grammar, registry, seed)
        assert (a.dte_bucket, a.hypothesis, _directional_id(a)) == (
            b.dte_bucket,
            b.hypothesis,
            _directional_id(b),
        )


def test_k_multiplier_moves_a_boundary_horizon_indicator() -> None:
    """Sanity that k is a live exploration knob, not inert: a ~10-day horizon
    (supertrend) crosses the swing_short/swing_mid boundary as k goes 2->3."""
    from forge.grammar.signal_horizon import nearest_bucket, signal_horizon_days

    allowed = buckets_for_horizon_class(horizon_class("supertrend"))
    h = signal_horizon_days("supertrend")
    assert nearest_bucket(allowed, 2 * h) == "swing_short"
    assert nearest_bucket(allowed, 3 * h) == "swing_mid"
