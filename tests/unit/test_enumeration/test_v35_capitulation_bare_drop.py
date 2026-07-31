"""v35 capitulation BARE-DROP — the gate-drop Crucible adjudicated 2026-07-15
(D280; OPEN_PROPOSALS `4d35a046` operator-APPROVED;
`FORGE_adjudications_capitulation_ve_floor_2026-07-15.md`).

The v31 pinned rv_rank gate ([50,80] kernel units) BINDS harmfully — clean
drop-day median rv_rank ~50 → co-fire strangled (69/69 decided dead, median 4
OOS trades) — and their clean-data sweep reads the gate unhelpful-to-harmful
at every threshold. The bare-drop single-name arm posted the first positive
slot delta of the program (cpcv +0.0267 / wf +0.0794 at the 0.175 slot;
value hypothesis = marginal CENTER lever, bear-block delta 0.0). Changes:

  * R1 per-directional carve-out: a mean_reversion config whose DIRECTIONAL is
    the capitulation `momentum` id needs NO regime gate (the first R1
    exemption; the D270 C2-carve-out pattern one level deeper —
    operator-approved rule-surface change, `rules:` text untouched).
  * Sampler: the rv_rank pin is dropped and NO regime gate is emitted for this
    directional; NO replacement gate (their explicit instruction —
    market_rv x drop co-fires 2x/8.4y, born-dead); the calm-side veto skip
    stays; the v31 chain shape is preserved (vol_target never hosts
    capitulation; kelly may).
  * swing_short rider (their "still fine, low stakes"): k gains 1 for this
    directional only → 15 td target snaps swing_short; k∈{2,3,4} keep
    swing_mid. Other directionals keep D102's k∈{2,3,4} exactly.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot, SignalSpec, StrategyConfig

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar, validate
from tests.fixtures.strategy_configs import minimal_registry_snapshot
from tests.unit.test_enumeration.test_sampler import _v31_registry

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


def _capitulation_configs(
    grammar: Grammar, reg: RegistrySnapshot, n_seeds: int = 800
) -> list[StrategyConfig]:
    space = build_search_space(grammar, reg)
    out = []
    for seed in range(n_seeds):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators == ("momentum",):
            out.append(cfg)
    return out


# --- the R1 carve-out (rule surface, operator-approved) ------------------------


def _gateless_config(directional: SignalSpec) -> StrategyConfig:
    from tests.fixtures.strategy_configs import minimal_strategy_config

    return minimal_strategy_config(signals=(directional,))


def test_v35_r1_accepts_gateless_capitulation_config(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """A gate-less momentum-directional MR config is grammar-VALID."""
    reg = _v31_registry(registry)
    cfg = _gateless_config(
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("momentum",),
            params={"threshold": -0.05, "op": "<", "lookback": 5, "skip": 0},
        )
    )
    result = validate(cfg, grammar, reg)
    r1_errors = [e for e in result.errors if "iv_rank" in str(e) or "R1" in str(e)]
    assert not r1_errors, r1_errors


def test_v35_r1_still_requires_a_gate_for_other_mr_directionals(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The exemption is per-directional: a gate-less rsi_2 MR config still
    fails R1 (the carve-out must not loosen the whole hypothesis)."""
    reg = _v31_registry(registry)
    cfg = _gateless_config(
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"period": 2, "threshold": 25.0, "op": "<"},
        )
    )
    result = validate(cfg, grammar, reg)
    assert any("iv_rank" in str(e) or "R1" in str(e) for e in result.errors)


# --- emission: bare drop, no veto, preserved chassis ---------------------------


def test_v35_capitulation_emits_no_regime_gate(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every emitted capitulation config is BARE-DROP: no regime_filter signal
    at all (no rv_rank pin, no replacement gate, no veto)."""
    caps = _capitulation_configs(grammar, _v31_registry(registry))
    assert caps, "no capitulation configs drawn — the exemption broke admission"
    for cfg in caps:
        assert not [s for s in cfg.signals if s.role == "regime_filter"], cfg.name


def test_v35_capitulation_chassis_preserved(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The v31 chassis survives the gate-drop: drop trigger in the audited band
    (op '<', threshold in [-0.083,-0.041], lookback 3-10, skip 0); vol_target
    never hosts capitulation (the v31 shape — with no gate to C1-conflict, the
    exclusion is now explicit policy, not a side effect)."""
    caps = _capitulation_configs(grammar, _v31_registry(registry))
    assert caps
    for cfg in caps:
        d = next(s for s in cfg.signals if s.role == "directional")
        assert d.params["op"] == "<", cfg.name
        assert -0.083 <= d.params["threshold"] <= -0.041, cfg.name
        assert 3 <= d.params["lookback"] <= 10, cfg.name
        assert d.params["skip"] == 0, cfg.name
        assert cfg.sizer.mode != "vol_target", cfg.name


def test_v35_capitulation_swing_short_rider(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """k gains 1 for this directional only: swing_short (k=1 → 15 td) appears
    alongside swing_mid (k∈{2,3,4} → 30/45/60), and nothing else."""
    caps = _capitulation_configs(grammar, _v31_registry(registry), n_seeds=1200)
    buckets = {c.dte_bucket for c in caps}
    assert buckets == {"swing_short", "swing_mid"}, buckets
