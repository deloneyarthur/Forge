"""v19 (D138) invariants — option_momentum activation honesty guarantees.

option_momentum is activated as a `trend_continuation` directional (the
operator-pinned C2 home for `smart_money`; the Heston-Jones-Khorram-Li option-
momentum continuation thesis). Three properties must hold structurally, not by
sampler luck — Crucible's coverage handoff
(`../Crucible/docs/handoffs/FORGE_option_momentum_coverage_response.md`) showed
the *absolute*-threshold form is a cross-sectional inverse-IV-level sort (a
confound their gate would reject), and that the series is only viable at a
relaxed `min_months`:

  1. Every sampled option_momentum directional emits PERCENTILE mode
     (`use_percentile=True`) — never an absolute threshold. Percentile over the
     name's own history normalizes the IV-level offset (the honest form).
  2. Every option_momentum directional carries `min_months=3` (the probe-audited
     coverage floor: clears §5.3.3 min_activations=30 on all 10 probed names;
     `scripts/probe_option_momentum_min_months.py`).
  3. option_momentum appears ONLY under `trend_continuation` (the pin), and its
     smart_money sibling `expected_value_estimator` is NEVER a directional (it
     is the X2 fractional-kelly sizer feature, reference-keyed — pinned out of
     the directional path by nulling its directional range).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import SignalSpec, StrategyConfig

from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import load_grammar
from forge.persistence.registry_loader import load_registry

_SELECT_LOW, _SELECT_HIGH = 0.80, 0.90


def _load_space() -> tuple[object, object]:
    grammar_path = Path(__file__).resolve().parents[2] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()
    return build_search_space(grammar, registry), registry


@pytest.fixture(scope="module")
def sampled_configs() -> list[StrategyConfig]:
    """A deterministic population large enough to exercise option_momentum.

    Sampled once and shared (option_momentum is ~1 of ~11 trend directionals
    in ~1 of 5 enumerable hypotheses, so a few thousand draws yield tens of it).
    """
    space, registry = _load_space()
    rng = random.Random(0)
    configs: list[StrategyConfig] = []
    for _ in range(4000):
        try:
            configs.append(sample_config(space, registry, rng))
        except SamplerError:
            continue
    return configs


def _is_option_momentum_directional(sig: SignalSpec) -> bool:
    return sig.role == "directional" and "option_momentum" in sig.indicators


def _option_momentum_directionals(configs: list[StrategyConfig]) -> list[StrategyConfig]:
    return [c for c in configs if any(_is_option_momentum_directional(s) for s in c.signals)]


def test_option_momentum_is_actually_sampled(sampled_configs: list[StrategyConfig]) -> None:
    """Guard: the live registry advertises option_momentum and the activation
    reaches the funnel — otherwise the invariants below are vacuously true."""
    hits = _option_momentum_directionals(sampled_configs)
    assert len(hits) >= 10, (
        f"only {len(hits)} option_momentum directional configs in "
        f"{len(sampled_configs)} draws — registry may lack it, or C2 rejects it"
    )


def test_option_momentum_directional_always_percentile(
    sampled_configs: list[StrategyConfig],
) -> None:
    """Invariant 1+2: percentile mode + the audited min_months on every draw."""
    for cfg in _option_momentum_directionals(sampled_configs):
        sig = next(s for s in cfg.signals if s.role == "directional")
        params = sig.params
        assert params.get("use_percentile") is True, params
        assert params.get("op") == ">", params
        assert params.get("min_months") == 3, params
        assert params.get("months") == 6, params
        assert _SELECT_LOW <= float(params["threshold"]) <= _SELECT_HIGH, params
        assert params["percentile_window"] == 252, params


def test_option_momentum_dte_bucket_is_s4_long(
    sampled_configs: list[StrategyConfig],
) -> None:
    """§3.5 S4: horizon 126 td → long_lookback → {swing_mid, swing_long} only,
    never swing_short. swing_mid appears when a chain/confluence signal narrows
    chain-compat DTE; the unconstrained draw snaps k*126 to swing_long."""
    for cfg in _option_momentum_directionals(sampled_configs):
        assert cfg.dte_bucket in ("swing_mid", "swing_long"), cfg.dte_bucket


def test_option_momentum_only_under_trend_continuation(
    sampled_configs: list[StrategyConfig],
) -> None:
    """Invariant 3a: the pin holds — option_momentum never leaks to another
    hypothesis (smart_money is in trend_continuation's C2 families only)."""
    for cfg in _option_momentum_directionals(sampled_configs):
        assert cfg.hypothesis == "trend_continuation", (
            f"option_momentum directional under {cfg.hypothesis!r} — C2 pin breach"
        )


def test_expected_value_estimator_never_directional(
    sampled_configs: list[StrategyConfig],
) -> None:
    """Invariant 3b: admitting smart_money to trend_continuation's C2 pool must
    NOT make EV a directional. It is pinned out (directional range nulled →
    is_threshold_skippable), staying the X2 kelly sizer feature."""
    for cfg in sampled_configs:
        for sig in cfg.signals:
            if sig.role == "directional" and sig.indicators:
                assert sig.indicators[0] != "expected_value_estimator", (
                    f"EV leaked as a directional under {cfg.hypothesis!r}: {sig.params}"
                )
