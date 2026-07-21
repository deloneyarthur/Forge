"""Active-behavior tests for the D320 refutation effects in the sampler.

Byte-identity of the cold-start (no-effect) path is covered by the enumeration
goldens; these assert the effects actually BITE when applied, and that the MR
scope guard holds (trend x hurst is never touched).
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from forge.enumeration.refutations import DEPRIORITIZE_WEIGHT, RefutationEffects
from forge.enumeration.sampler import _build_selector, _pick_regime
from forge.enumeration.search_space import build_search_space
from forge.grammar import load_grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO = Path(__file__).resolve().parent.parent.parent.parent
_HURST_MR_GATES = ("hurst", "iv_rank", "rv_rank")


def _space() -> object:
    grammar = load_grammar(
        _REPO / "config" / "grammar.yaml", archive_dir=_REPO / "config" / "grammar_archive"
    )
    return build_search_space(grammar, minimal_registry_snapshot())


# ---------------------------------------------------------------------------
# _pick_regime — hurst deprioritize (hurst-mr-conditioner)
# ---------------------------------------------------------------------------


def test_hurst_deprioritized_share_drops() -> None:
    base = Counter(
        _pick_regime("mean_reversion", _HURST_MR_GATES, random.Random(s), None) for s in range(4000)
    )
    guarded = Counter(
        _pick_regime(
            "mean_reversion",
            _HURST_MR_GATES,
            random.Random(s),
            None,
            deprioritized_gates=frozenset({"hurst"}),
        )
        for s in range(4000)
    )
    # hurst share falls sharply; the other gates absorb the freed mass.
    assert guarded["hurst"] < base["hurst"] * 0.5
    assert guarded["iv_rank"] > base["iv_rank"]


def test_pick_regime_empty_gates_is_byte_identical() -> None:
    """Hard rule #6: no deprioritized gates → the exact same rng draw as the
    pre-D320 call (the uniform branch stays rng.choice)."""
    for s in range(200):
        assert _pick_regime(
            "mean_reversion", _HURST_MR_GATES, random.Random(s), None
        ) == _pick_regime(
            "mean_reversion",
            _HURST_MR_GATES,
            random.Random(s),
            None,
            deprioritized_gates=frozenset(),
        )


def test_pick_regime_gate_not_in_pool_is_byte_identical() -> None:
    """A deprioritize for a gate absent from this pool must not perturb the
    draw (no overlap → original path)."""
    for s in range(200):
        assert _pick_regime(
            "mean_reversion", _HURST_MR_GATES, random.Random(s), None
        ) == _pick_regime(
            "mean_reversion",
            _HURST_MR_GATES,
            random.Random(s),
            None,
            deprioritized_gates=frozenset({"not_a_real_gate"}),
        )


# ---------------------------------------------------------------------------
# _build_selector — delta clip (deep-itm-directional blocklist)
# ---------------------------------------------------------------------------


def test_delta_clip_removes_the_deep_itm_sliver() -> None:
    space = _space()
    # trend swing_long band reaches 0.55, so unclipped draws land >= 0.50.
    unclipped = [
        _build_selector(space, "trend_continuation", "swing_long", random.Random(s)).delta_target
        for s in range(2000)
    ]
    clipped = [
        _build_selector(
            space, "trend_continuation", "swing_long", random.Random(s), delta_clip_upper=0.499
        ).delta_target
        for s in range(2000)
    ]
    assert any(d >= 0.50 for d in unclipped)  # the sliver exists unclipped
    assert all(d < 0.50 for d in clipped)  # and is gone once clipped


def test_delta_clip_leaves_interior_band_untouched() -> None:
    """A bucket whose band never reaches the clip draws byte-identically."""
    space = _space()
    for s in range(300):
        # mean_reversion swing_long band is (0.2, 0.35) — entirely below the
        # 0.499 clip, so the clip is a no-op and the draw is byte-identical.
        a = _build_selector(space, "mean_reversion", "swing_long", random.Random(s)).delta_target
        b = _build_selector(
            space, "mean_reversion", "swing_long", random.Random(s), delta_clip_upper=0.499
        ).delta_target
        assert a == b


# ---------------------------------------------------------------------------
# The resolved-effects object threads through (integration sanity)
# ---------------------------------------------------------------------------


def test_effects_object_carries_the_weight() -> None:
    eff = RefutationEffects(
        deprioritized_regime_gates={"mean_reversion": frozenset({"hurst"})},
        delta_upper_clip=0.499,
        deprioritize_diversified_hypotheses=frozenset({"volatility_event"}),
    )
    assert eff.deprioritize_weight == DEPRIORITIZE_WEIGHT
    assert not eff.is_empty()
