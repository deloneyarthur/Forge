"""Audit test: no `type='threshold'` SignalSpec leaves the sampler with empty params.

2026-05-15: Crucible operator confirmed a ~2% of Forge-submitted strategies
had a `type='threshold'` directional or regime_filter signal with NO
`threshold` key in `params`. Crucible's predicate maps that to
`lambda _v: False` — the signal never fires, the strategy logs 0 trades,
and Crucible's `min_oos_trade_count` gate rejects it.

Root cause: `is_threshold_skippable` only flagged indicators with
`is_skip=True`, not indicators MISSING from `_INDICATOR_THRESHOLD_TABLE`.
`atr` (a price-scale volatility indicator) was in the registry but
absent from the threshold table; `_directional_signal_params` /
`_regime_signal_params` fell through `sample_threshold_params`'s
"unknown indicator" branch and returned `{}`.

This test asserts the invariant: across a representative sample of
production-grammar configs, no `type='threshold'` signal lacks the
'threshold' key. It would fail under the pre-fix `is_threshold_skippable`
and pass under the fixed version.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from forge.enumeration.indicator_thresholds import (
    _INDICATOR_THRESHOLD_TABLE,
    is_threshold_skippable,
)
from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import load_grammar
from forge.persistence.registry_loader import load_registry


def test_is_threshold_skippable_returns_true_for_missing_entries() -> None:
    """An indicator not in the table is skippable for threshold roles."""
    assert is_threshold_skippable("definitely_not_a_real_indicator_xyz")


def test_is_threshold_skippable_returns_true_for_atr() -> None:
    """atr is price-scale and now explicitly marked is_skip=True."""
    assert "atr" in _INDICATOR_THRESHOLD_TABLE
    assert is_threshold_skippable("atr")


def test_known_threshold_indicators_are_not_skippable() -> None:
    """rsi / adx / etc. ARE samplable — sanity check we didn't over-filter."""
    for ind in ("rsi", "rsi_2", "adx", "iv_rank"):
        assert not is_threshold_skippable(ind), f"{ind} should be samplable"


def test_rv_rank_skippable_as_directional_but_not_regime() -> None:
    """D077: rv_rank is regime-only — no directional_range."""
    assert is_threshold_skippable("rv_rank", "directional")
    assert not is_threshold_skippable("rv_rank", "regime_filter")


def test_no_empty_threshold_leak_across_500_samples() -> None:
    """End-to-end: 500 sampled configs, zero empty-threshold leaks.

    Pre-fix, atr leaked ~2% of the time → ~10 leaks in 500 trials.
    Post-fix, the sampler structurally cannot produce one.
    """
    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()
    space = build_search_space(grammar, registry)
    rng = random.Random(0)

    sampled = 0
    for _ in range(500):
        try:
            cfg = sample_config(space, registry, rng)
        except SamplerError:
            continue
        sampled += 1
        for sig in cfg.signals:
            if sig.type != "threshold":
                continue
            assert "threshold" in sig.params, (
                f"empty-threshold leak: signal id={sig.id} "
                f"indicators={sig.indicators} role={sig.role} params={sig.params}"
            )
    # Sanity: enough samples must succeed to actually exercise the invariant.
    # The new sampler raises SamplerError more often (it filters indicators
    # without threshold ranges), so we accept a lower yield than the
    # 500-trial budget would otherwise produce.
    assert sampled >= 300, f"only {sampled}/500 configs sampled; check grammar/registry"


def test_sampler_raises_on_synthetic_threshold_leak() -> None:
    """If the table somehow drops an indicator without filter coverage, the
    runtime assertion in sample_config catches it before emit.

    Simulated by stripping the entry mid-sample and verifying SamplerError.
    """
    # Construct a config that would hit atr if it were re-enabled; check the
    # belt-and-suspenders by temporarily patching is_threshold_skippable to
    # let atr through to the spec-construction path.
    from forge.enumeration import sampler as sampler_mod

    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()
    space = build_search_space(grammar, registry)
    rng = random.Random(0)

    # Patch is_threshold_skippable to always return False so atr-shaped
    # leaks could in principle propagate; the assert in sample_config
    # must still catch any threshold signal with empty params if the
    # indicator falls through sample_threshold_params's unknown branch.
    original = sampler_mod.is_threshold_skippable
    sampler_mod.is_threshold_skippable = lambda _id, _role="directional": False  # type: ignore[assignment]
    try:
        # Don't bet on the seed hitting atr; just verify the path exists. If
        # the assert is structurally correct, deletion of the atr entry from
        # the table makes the sampler raise within a reasonable trial budget.
        original_table = dict(_INDICATOR_THRESHOLD_TABLE)
        _INDICATOR_THRESHOLD_TABLE.pop("atr", None)
        leaked = False
        for _ in range(2000):
            try:
                cfg = sample_config(space, registry, rng)
            except SamplerError as exc:
                if "empty-threshold leak" in str(exc):
                    leaked = True
                    break
                continue
            for sig in cfg.signals:
                if sig.type == "threshold" and "threshold" not in sig.params:
                    pytest.fail(f"assert in sample_config failed to fire on leak: {sig}")
        # Restore table for any subsequent tests
        _INDICATOR_THRESHOLD_TABLE.clear()
        _INDICATOR_THRESHOLD_TABLE.update(original_table)
        assert leaked, "expected sample_config to raise SamplerError on synthetic leak"
    finally:
        sampler_mod.is_threshold_skippable = original  # type: ignore[assignment]


def test_m9_all_r3_event_proximity_indicators_are_regime_samplable() -> None:
    """M-9 (audit 2026-05-29): every R3 event-proximity indicator must have a
    regime threshold entry, else it's silently unsamplable as a regime gate.

    T1.4/D039 widened R3's pool to days_to_cpi/nfp/opex specifically to make
    `volatility_event` usable on ETFs — but those three were never added to
    `_INDICATOR_THRESHOLD_TABLE`, so `is_threshold_skippable(..., 'regime_filter')`
    returned True and the sampler filtered them out, making the widening inert.
    """
    from forge.enumeration.indicator_thresholds import is_threshold_skippable
    from forge.grammar.custom_predicates import _R3_EVENT_PROXIMITY_INDICATORS

    skippable = [
        ind
        for ind in _R3_EVENT_PROXIMITY_INDICATORS
        if is_threshold_skippable(ind, "regime_filter")
    ]
    assert not skippable, (
        f"R3 event-proximity indicators not samplable as regime gates: {skippable} "
        "(add regime_range + op_regime entries to _INDICATOR_THRESHOLD_TABLE)"
    )
