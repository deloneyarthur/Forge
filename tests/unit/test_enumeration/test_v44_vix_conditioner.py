"""v44 (D317) — the Q46 optional SECOND regime gate: a vix_term_slope CONDITIONER.

Crucible `FORGE_q46_reply_repin_and_go_2026-07-21` GO on the scope. The §3.5
`rules:` text is untouched (S3 `>=1` has always permitted a second gate; the
v25/v26/v29/v39 vetoes exercise it) — this is an emission-policy add. On the
xsect trend arm, `vix_term_slope` may be ANDed onto a trend-STRENGTH primary
(adx/hurst) as the confirmed resid_vix price-axis pair — the double-gate the
sampler never emitted (vix_term_slope was only ever an R2 PRIMARY).

Design invariants under test:
  - Fires ONLY on trend_continuation x cross_sectional_rank with an adx/hurst
    primary; never MR, never single-name, never capitulation, never a macro
    primary (C1 — no macro x macro stack).
  - Shares the SINGLE optional second-gate slot with the veto (mutually
    exclusive → max 2 regime gates total).
  - Dormant under a registry that does not serve vix_term_slope as a trend gate
    (the minimal fixture — byte-identical cold path, hard rule #6; the 210
    test_sampler goldens are the byte-identity proof).
  - Fires at ~the target share (0.125) of eligible configs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crucible_contracts import IndicatorMetadata, RegistrySnapshot

from forge.enumeration import enumerate_candidates
from forge.enumeration.sampler import (
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
    """Over a wide draw, the conditioner fires on ~12.5% of ELIGIBLE configs
    (trend-xsect, adx/hurst primary, no other second gate). Band is wide — the
    eligible cell is narrow, so this guards the mechanism, not a tight rate."""
    reg = _v44_registry(minimal_registry_snapshot())
    configs = list(
        enumerate_candidates(grammar=_grammar(), registry=reg, seed=11, max_candidates=20000)
    )
    eligible = 0
    fired = 0
    for c in _trend_xsect(configs):
        gates = _gates(c)
        ts = [g for g in gates if g in _VIX_CONDITIONER_PRIMARY_GATES]
        allowed = (*_VIX_CONDITIONER_PRIMARY_GATES, _VIX_CONDITIONER_ID)
        if len(ts) == 1 and all(g in allowed for g in gates):
            eligible += 1
            if _VIX_CONDITIONER_ID in gates:
                fired += 1
    assert eligible >= 20, f"too few eligible configs to test the share ({eligible})"
    rate = fired / eligible
    assert 0.05 <= rate <= 0.22, f"fire rate {rate:.3f} off target {_VIX_CONDITIONER_SHARE}"


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
