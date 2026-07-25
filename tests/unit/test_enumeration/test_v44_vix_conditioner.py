"""v44 (D317) + v45 (D319) — the Q46 optional SECOND regime gate: a vix_term_slope
CONDITIONER, refined.

Crucible `FORGE_q46_reply_repin_and_go_2026-07-21` GO, then
`FORGE_q46_readdesign_and_scope_refine_2026-07-21` (v45). The §3.5 `rules:` text is
untouched (S3 `>=1` has always permitted a second gate) — emission-policy. On the
xsect trend arm, `vix_term_slope` is ANDed onto a HURST primary (v45: hurst-only,
was {adx,hurst} in v44 — adx x residual_momentum is dead) as the confirmed
resid_vix price-axis pair — the double-gate the sampler never emitted
(vix_term_slope was only ever an R2 PRIMARY). v45 also adds a residual_momentum
pilot DIAL (~2x its weighted-draw share) for the in-book read's power.

Design invariants under test:
  - Fires ONLY on trend_continuation x cross_sectional_rank with a HURST primary
    (v45); never adx, never MR, never single-name, never capitulation, never a
    macro primary (C1 — no macro x macro stack).
  - Shares the SINGLE optional second-gate slot with the veto (mutually
    exclusive → max 2 regime gates total).
  - Dormant under a registry that does not serve vix_term_slope as a trend gate
    (the minimal fixture — byte-identical cold path, hard rule #6; the 210
    test_sampler goldens are the byte-identity proof).
  - Fires at ~the target share (0.125) of eligible configs.
  - v45 dial: residual_momentum's weighted-path draw share ~doubles.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crucible_contracts import IndicatorMetadata, RegistrySnapshot

import forge.enumeration.sampler as sampler_mod
from forge.enumeration import enumerate_candidates
from forge.enumeration.sampler import (
    _CAPITULATION_DIRECTIONAL_ID as _CAPITULATION_ID,
)
from forge.enumeration.sampler import (
    _RESID_MOMENTUM_PILOT_WEIGHT,
    _VIX_CONDITIONER_ID,
    _VIX_CONDITIONER_PRIMARY_GATES,
    _VIX_CONDITIONER_SHARE,
)
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "config"


def _grammar() -> Grammar:
    return load_grammar(_CONFIG_ROOT / "grammar.yaml", archive_dir=_CONFIG_ROOT / "grammar_archive")


def _meta(
    ind_id: str,
    family: str,
    *,
    version: int = 1,
    lookback: int = 0,
    rank_coherent: bool = False,
    market_wide: bool = False,
) -> IndicatorMetadata:
    return IndicatorMetadata(
        id=ind_id,
        version=version,
        family=family,
        lookback=lookback,
        params_schema={},
        rank_per_name_coherent=rank_coherent,
        market_wide_by_design=market_wide,
    )


def _v44_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + the ids the conditioner path touches, families/flags
    exactly as the live registry publishes them (the _v33 helper pattern).
    vix_term_slope (macro, market_wide) becomes an R2 trend gate here, so the
    conditioner leaves its minimal-fixture dormancy and emits."""
    extra = (
        _meta("residual_momentum", "trend", lookback=504, rank_coherent=True),
        _meta("vix_term_slope", "macro", market_wide=True),
        _meta("days_since_jump", "volatility", version=3, lookback=252, rank_coherent=True),
        _meta("market_state", "macro", market_wide=True),
    )
    return base.model_copy(update={"indicators": (*base.indicators, *extra)})


def _trend_xsect(configs: list) -> list:
    return [
        c
        for c in configs
        if c.hypothesis == "trend_continuation" and c.combiner.type == "cross_sectional_rank"
    ]


def _gates(config) -> list[str]:
    return [s.indicators[0] for s in config.signals if s.role == "regime_filter"]


@pytest.fixture(scope="module")
def v44_configs() -> list:
    reg = _v44_registry(minimal_registry_snapshot())
    return list(enumerate_candidates(grammar=_grammar(), registry=reg, seed=7, max_candidates=8000))


# --- the served registry: vix_term_slope is a trend regime gate ----------------


def test_vix_is_a_trend_regime_gate_when_served() -> None:
    reg = _v44_registry(minimal_registry_snapshot())
    space = build_search_space(_grammar(), reg)
    assert _VIX_CONDITIONER_ID in space.regime_indicators_by_hypothesis["trend_continuation"]


# --- dormancy under the minimal fixture (byte-identical cold path) -------------


def test_conditioner_dormant_without_vix_as_trend_gate() -> None:
    """The minimal fixture serves no vix_term_slope trend gate → the conditioner
    is inert; NO config carries a vix-as-second-gate. (The 210 test_sampler
    goldens are the full byte-identity proof; this is the direct assertion.)"""
    configs = list(
        enumerate_candidates(
            grammar=_grammar(), registry=minimal_registry_snapshot(), seed=7, max_candidates=4000
        )
    )
    for c in configs:
        gates = _gates(c)
        # vix may not appear at all (not served); certainly never as a 2nd gate.
        assert _VIX_CONDITIONER_ID not in gates


# --- emission: fires on the confirmed cell ------------------------------------


def test_conditioner_emits_double_gate_on_adx_hurst_primary(v44_configs: list) -> None:
    doubles = [
        c
        for c in _trend_xsect(v44_configs)
        if _VIX_CONDITIONER_ID in _gates(c)
        and any(g in _VIX_CONDITIONER_PRIMARY_GATES for g in _gates(c))
    ]
    assert doubles, "the vix conditioner never produced a double-gate"
    for c in doubles:
        gates = _gates(c)
        assert len(gates) == 2  # primary + vix — max 2, never 3
        others = [g for g in gates if g != _VIX_CONDITIONER_ID]
        assert len(others) == 1
        assert others[0] in _VIX_CONDITIONER_PRIMARY_GATES


# --- C1: never a macro x macro stack ------------------------------------------


def test_conditioner_never_stacks_on_macro_primary(v44_configs: list) -> None:
    """vix_term_slope is macro; C1 forbids a second macro gate. Whenever vix is
    a SECOND gate, the other gate is a trend-strength (adx/hurst) primary —
    never market_state / vix-as-primary (both macro)."""
    for c in _trend_xsect(v44_configs):
        gates = _gates(c)
        if gates.count(_VIX_CONDITIONER_ID) and len(gates) >= 2:
            others = [g for g in gates if g != _VIX_CONDITIONER_ID]
            # the D317 conditioner only ever pairs vix with adx/hurst; a macro
            # 'other' would be a C1 violation. days_since_jump appears only as
            # the veto on a vix-PRIMARY config (pre-existing), never with a
            # trend-strength gate (conditioner ⇒ no veto, mutual exclusion).
            allowed = (*_VIX_CONDITIONER_PRIMARY_GATES, "days_since_jump")
            assert all(o in allowed for o in others)
            if any(o in _VIX_CONDITIONER_PRIMARY_GATES for o in others):
                assert "days_since_jump" not in others


# --- mutual exclusion with the veto (max 2 total) -----------------------------


def test_conditioner_and_veto_never_coexist(v44_configs: list) -> None:
    """The single optional slot holds EITHER the vix conditioner OR the veto,
    never both — so no config carries a trend-strength primary + vix + dsj."""
    for c in _trend_xsect(v44_configs):
        gates = _gates(c)
        has_conditioner = _VIX_CONDITIONER_ID in gates and any(
            g in _VIX_CONDITIONER_PRIMARY_GATES for g in gates
        )
        if has_conditioner:
            assert "days_since_jump" not in gates
            assert len(gates) == 2


# --- scope: never MR, never single-name ---------------------------------------


def test_conditioner_never_on_single_name_trend(v44_configs: list) -> None:
    """The conditioner is xsect-only. On single-name trend, vix_term_slope may
    still be the R2 PRIMARY (optionally + a dsj veto), but the conditioner's
    signature — a trend-STRENGTH primary AND vix_term_slope together — never
    appears (that pairing is what the xsect-only conditioner uniquely creates)."""
    for c in v44_configs:
        if c.hypothesis == "trend_continuation" and c.combiner.type != "cross_sectional_rank":
            gates = _gates(c)
            has_trend_strength = any(g in _VIX_CONDITIONER_PRIMARY_GATES for g in gates)
            assert not (has_trend_strength and _VIX_CONDITIONER_ID in gates)


def test_conditioner_never_on_mean_reversion(v44_configs: list) -> None:
    for c in v44_configs:
        if c.hypothesis == "mean_reversion":
            assert _VIX_CONDITIONER_ID not in _gates(c)


# --- share ~ target -----------------------------------------------------------


def test_conditioner_fires_near_target_share() -> None:
    """Over a wide draw the conditioner fires on ~12.5% of ELIGIBLE configs.

    ELIGIBILITY IS KEYED ON THE PRIMARY GATE'S SIGNAL ID (`sig_regime`), mirroring
    `_vix_conditioner_eligible`, which is evaluated BEFORE any optional second gate is
    appended. An earlier version of this test instead required every gate on the FINAL
    config to sit in an allowed-set {hurst, vix_term_slope} — which silently dropped
    every eligible config that took a regime VETO (`days_since_jump`) instead of the
    conditioner. Those are all NON-FIRING configs, so removing them inflated the
    measured rate to ~0.22 against a 0.125 constant, and the band had been fitted to
    that artifact rather than to the target (Q57, resolved 2026-07-24: 176/795 = 0.2214
    under the old predicate vs 176/1457 = 0.1208 under this one; 662 dropped, 0 of them
    fired). The sampler was correct throughout.
    """
    reg = _v44_registry(minimal_registry_snapshot())
    configs = list(
        enumerate_candidates(grammar=_grammar(), registry=reg, seed=11, max_candidates=20000)
    )
    eligible = 0
    fired = 0
    for c in _trend_xsect(configs):
        primary = next((s.indicators[0] for s in c.signals if s.id == "sig_regime"), None)
        directional = next((s.indicators[0] for s in c.signals if s.role == "directional"), None)
        if primary in _VIX_CONDITIONER_PRIMARY_GATES and directional != _CAPITULATION_ID:
            eligible += 1
            if _VIX_CONDITIONER_ID in _gates(c):
                fired += 1
    assert eligible >= 20, f"too few eligible configs to test the share ({eligible})"
    rate = fired / eligible
    # Tight band around the CONSTANT now that the denominator is right (measured 0.1208).
    assert 0.09 <= rate <= 0.17, f"fire rate {rate:.3f} off target {_VIX_CONDITIONER_SHARE}"


# --- validity -----------------------------------------------------------------


def test_double_gate_configs_are_grammar_valid(v44_configs: list) -> None:
    """The iterator only yields validate()-passing configs; assert the
    double-gate ones actually flowed through (C1/R2/S3/C4 all hold)."""
    doubles = [
        c
        for c in _trend_xsect(v44_configs)
        if _VIX_CONDITIONER_ID in _gates(c)
        and any(g in _VIX_CONDITIONER_PRIMARY_GATES for g in _gates(c))
        and len(_gates(c)) == 2
    ]
    assert doubles  # yielded ⇒ grammar-valid


# --- v45: hurst-only (adx dropped) --------------------------------------------


def test_conditioner_never_on_adx_primary_since_v45(v44_configs: list) -> None:
    """v45 restricts the conditioner primary to hurst. adx and vix_term_slope
    therefore never co-occur as gates on a trend-xsect config (adx is neither a
    conditioner primary nor a veto, so {adx, vix} can only have come from the
    now-removed adx conditioner arm)."""
    assert "adx" not in _VIX_CONDITIONER_PRIMARY_GATES  # the constant tightened
    for c in _trend_xsect(v44_configs):
        gates = _gates(c)
        assert not ("adx" in gates and _VIX_CONDITIONER_ID in gates)


# --- v45: residual_momentum pilot dial ----------------------------------------


def test_resid_momentum_dial_lifts_share_in_weighted_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dial (~2x) multiplies residual_momentum's option weight in the LEARNED
    weighted draw path. Isolate it: equal base bucket_weights (so every
    directional falls back to the same pair weight), then residual_momentum's
    realized trend-directional share ~doubles between mult=1.0 and mult=2.0.
    Share is sub-linear in weight, so the band is loose — this guards direction +
    rough magnitude, and confirms the dial touches only the weighted path."""
    reg = _v44_registry(minimal_registry_snapshot())
    grammar = _grammar()
    bucket_weights = {
        ("trend_continuation", b): 1.0 for b in ("swing_short", "swing_mid", "swing_long")
    }

    def _resid_share(mult: float) -> float:
        monkeypatch.setattr(sampler_mod, "_RESID_MOMENTUM_PILOT_WEIGHT", mult)
        n = 0
        r = 0
        for cfg in enumerate_candidates(
            grammar=grammar,
            registry=reg,
            seed=7,
            max_candidates=9000,
            bucket_weights=bucket_weights,
            # D328 (v47): single-name trend is retired, so non-resid trend must go
            # xsect to survive the filter — otherwise the only surviving trend is
            # the xsect-pinned residual_momentum and its share is trivially 1.0.
            rank_combiner_share={"trend_continuation": 0.6},
        ):
            if cfg.hypothesis != "trend_continuation":
                continue
            n += 1
            d = next((s.indicators[0] for s in cfg.signals if s.role == "directional"), None)
            if d == "residual_momentum":
                r += 1
        return r / max(n, 1)

    share_1x = _resid_share(1.0)
    share_2x = _resid_share(2.0)
    assert share_1x > 0.0, "residual_momentum must draw at all for the dial to test"
    ratio = share_2x / share_1x
    # Share lift is SUB-LINEAR in weight (the denominator grows too), and it
    # depends on the base share — this synthetic equal-weight setup gives resid a
    # ~17% base, so the 2x weight lands ~1.35x; at production's ~10% base the same
    # weight gives ~1.8x (the double-gate cell target). Guard direction + that the
    # lift is material; the production cell-count target is checked by emission
    # proof at deploy, not here.
    assert 1.25 <= ratio <= 2.3, f"dial lift {ratio:.2f} (share {share_1x:.3f}->{share_2x:.3f})"


def test_dial_retired_to_neutral() -> None:
    """D328 (v48): the v45 pilot dial is RETIRED to 1.0 (neutral). Its accrual
    target was met (891 resid trend-xsect runs in v47 alone) and at 2.0 it had
    crowded resid to 40.8% of trend-xsect while momentum_252 fell to 0.64%."""
    assert _RESID_MOMENTUM_PILOT_WEIGHT == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
