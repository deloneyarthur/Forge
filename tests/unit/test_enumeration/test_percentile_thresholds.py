"""v6 grammar (D099) — percentile-parameterized threshold emission.

Scope (operator decision 2026-06-02, "exclude dealer_positioning directional"):
percentile-ize the ``mean_reversion``-family directional oscillators and the
``trend_continuation`` ``adx``/``hurst`` regime gate; leave dealer_positioning
directional, already-rank indicators (``iv_rank``/``rv_rank``), and the whole
``volatility_event`` indicator set on ABSOLUTE thresholds.

Contract (coordinated with Crucible ``494cf96`` + the feature-cache-writer
handoff): an opted-in signal emits ``params = {threshold: float in [0,1], op,
use_percentile: True, percentile_window: 252}``; Crucible ranks the latest
indicator value against its trailing window and compares the percentile to
``threshold`` via ``op``. See ``IMPLEMENTATION_DECISIONS.md`` D099.
"""

from __future__ import annotations

import random
from pathlib import Path

from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import load_grammar
from forge.persistence.registry_loader import load_registry

# (indicator, role) pairs that MUST emit percentile params under v6.
_PERCENTILE_DIRECTIONAL = ("rsi_2", "rsi_14", "rsi", "zscore_returns", "bb_pct")
_PERCENTILE_REGIME = ("adx", "hurst")

# (indicator, role) pairs that MUST stay absolute (out of scope). The dealer_*
# distances are the mean_reversion-directional overlap with volatility_event;
# rv_rank/iv_rank are already-rank; days_to_*/vix are volatility_event's.
_ABSOLUTE_DIRECTIONAL = (
    "call_wall_distance_pct",
    "put_wall_distance_pct",
    "gamma_flip_distance_pct",
    "put_call_flow",
    "momentum_252",
)
_ABSOLUTE_REGIME = ("rv_rank", "iv_rank", "days_to_fomc", "days_to_earnings", "vix_level")


def _load_space():
    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()
    return build_search_space(grammar, registry), registry


def test_in_scope_directional_emits_percentile_params() -> None:
    for ind in _PERCENTILE_DIRECTIONAL:
        params = sample_threshold_params(ind, "directional", random.Random(0))
        assert params.get("use_percentile") is True, ind
        assert params["percentile_window"] == 252, ind
        assert 0.0 <= float(params["threshold"]) <= 1.0, (ind, params)
        assert "op" in params, ind


def test_in_scope_regime_emits_percentile_params() -> None:
    for ind in _PERCENTILE_REGIME:
        params = sample_threshold_params(ind, "regime_filter", random.Random(0))
        assert params.get("use_percentile") is True, ind
        assert params["percentile_window"] == 252, ind
        assert 0.0 <= float(params["threshold"]) <= 1.0, (ind, params)


def test_out_of_scope_indicators_stay_absolute() -> None:
    for ind in _ABSOLUTE_DIRECTIONAL:
        params = sample_threshold_params(ind, "directional", random.Random(0))
        if params:  # only assert for indicators that actually threshold-sample
            assert "use_percentile" not in params, (ind, params)
    for ind in _ABSOLUTE_REGIME:
        params = sample_threshold_params(ind, "regime_filter", random.Random(0))
        if params:
            assert "use_percentile" not in params, (ind, params)


def test_percentile_threshold_in_unit_interval_across_seeds() -> None:
    for ind, role in (
        ("rsi_2", "directional"),
        ("rsi_14", "directional"),
        ("adx", "regime_filter"),
        ("hurst", "regime_filter"),
    ):
        for seed in range(100):
            params = sample_threshold_params(ind, role, random.Random(seed))
            assert 0.0 <= float(params["threshold"]) <= 1.0, (ind, role, seed, params)
            assert params["use_percentile"] is True


def test_percentile_emission_is_deterministic() -> None:
    """Hard rule #6 — same seed reproduces the same draw."""
    a = sample_threshold_params("rsi_2", "directional", random.Random(7))
    b = sample_threshold_params("rsi_2", "directional", random.Random(7))
    assert a == b


def test_percentile_preserves_op_direction() -> None:
    """The op is unchanged from the absolute table — percentile only swaps the
    units of `threshold`, not the firing direction. rsi_2 = oversold low-side;
    adx = trend-strong high-side."""
    assert sample_threshold_params("rsi_2", "directional", random.Random(0))["op"] == "<"
    assert sample_threshold_params("adx", "regime_filter", random.Random(0))["op"] == ">"


def test_threshold_key_present_for_percentile_signals() -> None:
    """The §13 no-empty-threshold invariant still holds — percentile params
    carry a (percentile-valued) `threshold` key."""
    params = sample_threshold_params("rsi_2", "directional", random.Random(0))
    assert "threshold" in params


def test_volatility_event_never_emits_percentile() -> None:
    """Operator scope (D099): volatility_event must stay fully absolute. Its
    directional families (iv_structure/flow/dealer_positioning) and R3 regime
    gate (days_to_*) contain no percentile-eligible (indicator, role) pair, so
    no sampled volatility_event config may carry `use_percentile`."""
    space, registry = _load_space()
    rng = random.Random(0)
    checked = 0
    for _ in range(1500):
        try:
            cfg = sample_config(space, registry, rng)
        except SamplerError:
            continue
        if cfg.hypothesis != "volatility_event":
            continue
        checked += 1
        for sig in cfg.signals:
            assert "use_percentile" not in sig.params, (
                f"volatility_event leaked percentile mode: id={sig.id} "
                f"indicators={sig.indicators} role={sig.role} params={sig.params}"
            )
    assert checked >= 30, f"only {checked} volatility_event configs sampled; check setup"


def test_mean_reversion_rsi_directional_emits_percentile() -> None:
    """The diagnosed failure: mean_reversion's rsi_2/rsi_14 directional draws
    must now carry percentile mode (the fix's positive case)."""
    space, registry = _load_space()
    rng = random.Random(1)
    saw_percentile = 0
    for _ in range(1500):
        try:
            cfg = sample_config(space, registry, rng)
        except SamplerError:
            continue
        if cfg.hypothesis != "mean_reversion":
            continue
        for sig in cfg.signals:
            if sig.role == "directional" and sig.indicators[0] in ("rsi_2", "rsi_14"):
                assert sig.params.get("use_percentile") is True, sig.params
                saw_percentile += 1
    assert saw_percentile >= 5, (
        f"expected some mean_reversion rsi directional percentile signals; saw {saw_percentile}"
    )


def test_option_momentum_emits_percentile_only() -> None:
    """v19 (D138): option_momentum is the first PERCENTILE-ONLY directional (no
    `directional_range`). Crucible's coverage handoff showed the absolute
    threshold is a cross-sectional inverse-IV sort; percentile over the name's
    own history is the honest form. This also exercises the percentile-only path
    in sample_threshold_params (percentile range present, absolute range None)."""
    params = sample_threshold_params("option_momentum", "directional", random.Random(0))
    assert params.get("use_percentile") is True, params
    assert params["op"] == ">", params  # momentum: buy recent option-return winners
    assert 0.0 <= float(params["threshold"]) <= 1.0, params
    assert params["percentile_window"] == 252
    assert "threshold" in params  # §13 no-empty-threshold leak still holds


def test_option_momentum_not_skippable_despite_no_absolute_range() -> None:
    """The percentile-only support: a directional with a percentile range but no
    absolute range is samplable (not skippable); its percentile emission is
    asserted by the sampling test above."""
    assert not is_threshold_skippable("option_momentum", "directional")
    # No regime range AND no regime percentile range -> still skippable as a gate.
    assert is_threshold_skippable("option_momentum", "regime_filter")


def test_expected_value_estimator_directional_pinned_out() -> None:
    """v19 (D138): nulling EV's directional range pins it out of the directional
    path — admitting smart_money to trend_continuation's C2 pool (for
    option_momentum) would otherwise make EV a directional. It stays the X2
    fractional-kelly sizer feature; its regime/gate use is untouched."""
    assert is_threshold_skippable("expected_value_estimator", "directional")
    assert (
        sample_threshold_params("expected_value_estimator", "directional", random.Random(0)) == {}
    )


def test_hurst_regime_op_is_trending_but_directional_unchanged() -> None:
    """v7 (D100/Q26): trend_continuation's hurst regime gate flips to op ">"
    (allow when TRENDING — high hurst), not "<" (mean-reverting). Its separate
    mean_reversion DIRECTIONAL use stays op "<" (fire when mean-reverting). Only
    the regime op moved; the directional op is correct as-is."""
    for seed in range(20):
        reg = sample_threshold_params("hurst", "regime_filter", random.Random(seed))
        assert reg["op"] == ">", reg
        assert reg["use_percentile"] is True
        assert 0.0 <= float(reg["threshold"]) <= 1.0
    # mean_reversion directional use of hurst must NOT have flipped (absolute path).
    dir_ = sample_threshold_params("hurst", "directional", random.Random(0))
    assert dir_["op"] == "<", dir_
    assert "use_percentile" not in dir_  # directional hurst stays absolute
