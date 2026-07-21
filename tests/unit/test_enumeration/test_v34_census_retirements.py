"""v34 census dead-dimension retirements — Crucible's 2026-07-15 census #2
(D278; `docs/proposals/v34-census-dead-dimensions.md`).

Enumeration-policy bump (`rules:` text untouched; both items EMISSION-side, so
the submitted lineage stays grammar-valid under the unchanged predicates):

  1. BKNG + BRK.B excluded from single-name sampling — 100% WF=0.0 at
     n=703/431: per-contract volume never clears the v1 selector liquidity
     floor, so every config on them is born dead. Frozen list by design
     (the mechanism is Crucible-measured per-name, not ticker-classifiable);
     retirable when their queue-time liquidity preflight ships.
  2. gamma_flip_distance_pct retired as a REGIME GATE from every hypothesis's
     emission pool — census: 12,088 uses, 0.1% component rate, 79% WF=0.0
     (~1/100th of healthy gates, everywhere). Supersedes v33's narrower
     assumption that single-gated cells were alive. It remains a valid
     vol_event DIRECTIONAL (C2 dealer family) and the R1/R2 predicates still
     accept it as a gate (lineage validity).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot, SignalSpec

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot
from tests.unit.test_enumeration.test_v33_generation_health import _v33_registry

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


# --- item 1: structurally untradeable underlyings ------------------------------


def test_v34_untradeable_names_never_drawn(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """BKNG/BRK.B are live tier-2 names, but zero of their contracts clear the
    selector's OI/volume floor on a sampled day — the exclusion must hold on
    every single-name draw regardless of hypothesis or gate."""
    reg = _v33_registry(registry)
    space = build_search_space(grammar, reg)
    drawn = set()
    for seed in range(500):
        cfg = sample_config(space, reg, random.Random(seed))
        if cfg.underlying is not None:
            drawn.add(cfg.underlying)
    assert drawn  # the sweep actually sampled single names
    assert not drawn & {"BKNG", "BRK.B"}, sorted(drawn & {"BKNG", "BRK.B"})


def test_v34_untradeable_exclusion_applies_to_the_pool_itself() -> None:
    """Pool-level pin (survives weighted draws + the earnings-gated branch):
    the exclusion filters the pool BEFORE any draw, on both branches."""
    import forge.enumeration.sampler as sampler_mod

    # D286 (v37): +SOXX/LLY/GS/MSTR — the row-45 trailing-window guard cohort.
    # D292 (v41): +ASML/COST — the tier-unpin reply's dead tier-3 exemplars,
    # confirmed on OUR funnel (641 decided/0 components, 1,544/1).
    # D309 (v43): +30 — the first yield-audit cohort (each >=500 decided / 0
    # conversions since the clean era; operator "Ship all 30"; prereg 44a4e08aef4f).
    assert (
        frozenset(
            {
                "BKNG",
                "BRK.B",
                "SOXX",
                "LLY",
                "GS",
                "MSTR",
                "ASML",
                "COST",
                "AAL",
                "ADBE",
                "AMZN",
                "ARKK",
                "BSX",
                "DIA",
                "DVN",
                "EEM",
                "EFA",
                "GE",
                "INTC",
                "KO",
                "LRCX",
                "LUV",
                "MS",
                "MSFT",
                "NEM",
                "NKE",
                "PEP",
                "TXN",
                "UNG",
                "UPS",
                "VZ",
                "WFC",
                "XBI",
                "XLF",
                "XLI",
                "XLP",
                "XLV",
                "XOM",
            }
        )
        == sampler_mod._STRUCTURALLY_UNTRADEABLE_UNDERLYINGS
    )


# --- item 2: gamma_flip retired as a regime gate everywhere --------------------


def test_v34_gamma_flip_not_in_any_regime_pool(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """12,088 uses at 0.1% component / 79% WF=0.0 across EVERY pairing — dead
    at the volume of a first-class dimension. Retired from emission for all
    hypotheses (MR's R1 pool / trend's R2 pool / the any-id pools)."""
    space = build_search_space(grammar, _v33_registry(registry))
    for hyp, pool in space.regime_indicators_by_hypothesis.items():
        assert "gamma_flip_distance_pct" not in pool, hyp


def test_v34_gamma_flip_survives_as_a_vol_event_directional(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The retirement is gate-scoped: the C2 dealer-family DIRECTIONAL use in
    volatility_event is untouched (its dead cells were the pre_earnings
    pairing, retired in v33; the census §5 share question is Crucible's open
    adjudication, not this bump)."""
    space = build_search_space(grammar, _v33_registry(registry))
    assert (
        "gamma_flip_distance_pct" in space.directional_indicators_by_hypothesis["volatility_event"]
    )


def test_v34_r1_r2_predicates_still_accept_gamma_flip_gates() -> None:
    """EMISSION-side retirement only (hard rule #1): both rule predicates keep
    accepting gamma_flip-gated configs, so the submitted lineage stays valid."""
    from forge.grammar.custom_predicates import (
        _R1_GAMMA_REGIME_INDICATOR,
        _R2_TREND_CONTINUATION_REGIME_INDICATORS,
    )

    assert _R1_GAMMA_REGIME_INDICATOR == "gamma_flip_distance_pct"
    assert "gamma_flip_distance_pct" in _R2_TREND_CONTINUATION_REGIME_INDICATORS


def test_v34_dsj_gamma_flip_veto_filter_kept_as_defense_in_depth() -> None:
    """The v33 pairing filter stays live even though gamma_flip gates are no
    longer emitted — if the gate is ever re-admitted, the dead pairing must
    not silently come back with it. Unit-level (the emission path can no
    longer produce a gamma_flip primary gate to test against)."""
    from typing import ClassVar

    from forge.enumeration.sampler import _eligible_regime_vetoes

    class _FakeSpace:
        regime_veto_indicators_by_hypothesis: ClassVar[dict[str, tuple[str, ...]]] = {
            "trend_continuation": ("days_since_jump",)
        }
        regime_veto_family_by_id: ClassVar[dict[str, str]] = {"days_since_jump": "volatility"}
        indicators_by_family: ClassVar[dict[str, tuple[str, ...]]] = {"volatility": ()}

    gamma_gated = [
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("gamma_flip_distance_pct",),
            params={"threshold": 0.0, "op": ">"},
        )
    ]
    hurst_gated = [
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("hurst",),
            params={"threshold": 0.5, "op": ">"},
        )
    ]
    space = _FakeSpace()
    assert _eligible_regime_vetoes(gamma_gated, space, "trend_continuation") == ()  # type: ignore[arg-type]
    assert _eligible_regime_vetoes(hurst_gated, space, "trend_continuation") == (  # type: ignore[arg-type]
        "days_since_jump",
    )
