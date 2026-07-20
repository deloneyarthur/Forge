"""v39 ve-program repairs — Crucible's 2026-07-19 close-out relay
(``FORGE_ve_program_relay_2026-07-19.md``; scoping ``docs/proposals/v39-ve-program.md``).

Their §3 bug, confirmed in our emission (D289): every ve config carried
``event_passed_exit`` (required_always) with NO ``event_indicator`` — always their
FALLBACK mode, a hard cut at entry+n_bars. The v22/D169 ladder {3,5,8,13,21} put 60%
of every ve batch in the cratered exit region (their sweep: 13/16/21 bars → cpcv
0.81/0.42/0.29); ve conversion collapsed v21 5.9% → v22 0.7% → ~0 and never recovered.

The v39 repairs (operator-approved):
  1. ve exits: ``event_passed_exit`` OUT of the schema (their "either true-event mode
     or omit" — with a timer present it fires 0/68, decoration); ``time_stop`` becomes
     REQUIRED with ``n_bars ~ U[4,7]`` (their sweet spot around 5).
  2. ``ref_trailing_return`` joins the ve regime-VETO pool — SAMPLED, never pinned
     (their honesty block: parameterization is knife-edged, variants span 1.27-1.55):
     threshold U[-0.03, -0.02] op ">", reference ∈ {SPY, QQQ}, window ∈ [3, 10].
  3. ``iv_term_slope`` directional range loosened x1.3 on the easy edge
     ((0.01, 0.04) → (0.0077, 0.04)) — the x1.3 loosening was worth +0.21 cpcv on
     their honest chassis; we sample the widened axis, never pin the recipe value.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot, StrategyConfig
from crucible_contracts.models import IndicatorMetadata

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar, validate
from tests.fixtures.strategy_configs import minimal_registry_snapshot

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


def _rtr_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + ref_trailing_return — mirrors the live v4 registry entry
    (macro family, market-wide; verified live 2026-07-19)."""
    rtr = IndicatorMetadata(
        id="ref_trailing_return",
        version=1,
        family="macro",
        lookback=10,
        params_schema={},
        rank_per_name_coherent=False,
        market_wide_by_design=True,
    )
    return base.model_copy(update={"indicators": (*base.indicators, rtr)})


def _ve_configs(
    grammar: Grammar, registry: RegistrySnapshot, *, n_seeds: int
) -> list[StrategyConfig]:
    space = build_search_space(grammar, registry)
    return [
        sample_config(space, registry, random.Random(seed), forced_hypothesis="volatility_event")
        for seed in range(n_seeds)
    ]


def test_v39_ve_never_emits_event_passed(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The fallback-mode truncation is gone: no ve config carries event_passed_exit."""
    for cfg in _ve_configs(grammar, registry, n_seeds=400):
        assert "event_passed_exit" not in {e.id for e in cfg.exits}, cfg.name


def test_v39_ve_time_stop_required_with_u47(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """time_stop is the required ve hold, n_bars ~ U[4,7] (their sweet spot;
    longer craters), and iv_crush_exit stays required."""
    for cfg in _ve_configs(grammar, registry, n_seeds=400):
        ids = {e.id for e in cfg.exits}
        assert "time_stop" in ids, cfg.name
        assert "iv_crush_exit" in ids, cfg.name
        params = next(e.params for e in cfg.exits if e.id == "time_stop")
        assert params.get("n_bars") in (4, 5, 6, 7), (cfg.name, params)


def test_v39_ve_emission_stays_grammar_valid(grammar: Grammar, registry: RegistrySnapshot) -> None:
    for cfg in _ve_configs(grammar, registry, n_seeds=150):
        result = validate(cfg, grammar, registry)
        assert result.valid, (cfg.name, result.errors)


def test_v39_ve_veto_sampled_when_registry_serves_rtr(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """ref_trailing_return rides the generic ~0.5 veto-share draw in ve cells:
    present in a substantial minority-to-half of configs, params SAMPLED in the
    relay's boxes, never pinned to the recipe values."""
    reg = _rtr_registry(registry)
    space = build_search_space(grammar, reg)
    n_veto = 0
    refs: set[str] = set()
    windows: set[int] = set()
    thresholds: list[float] = []
    n = 600
    for seed in range(n):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="volatility_event")
        veto = next(
            (
                s
                for s in cfg.signals
                if s.role == "regime_filter" and s.indicators == ("ref_trailing_return",)
            ),
            None,
        )
        if veto is None:
            continue
        n_veto += 1
        assert veto.params.get("op") == ">", veto.params
        thr = veto.params.get("threshold")
        assert isinstance(thr, float), veto.params
        assert -0.03 <= thr <= -0.02, veto.params
        ref = veto.params.get("reference")
        assert ref in ("SPY", "QQQ"), veto.params
        win = veto.params.get("window")
        assert isinstance(win, int), veto.params
        assert 3 <= win <= 10, veto.params
        refs.add(str(ref))
        windows.add(int(win))
        thresholds.append(float(thr))
        assert validate(cfg, grammar, reg).valid, cfg.name

    share = n_veto / n
    assert 0.20 < share < 0.60, f"ve veto share {share:.2f} (C1 guard eats some draws)"
    assert refs == {"SPY", "QQQ"}, refs  # both references explored
    assert len(windows) >= 4, windows  # the window axis is sampled, not pinned
    assert len(set(thresholds)) > 10  # the threshold axis is sampled, not pinned


def test_v39_ve_veto_absent_without_registry_support(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Registry not serving ref_trailing_return → empty ve veto pool → no veto,
    no rng consumed (the D258 empty-pool convention)."""
    for cfg in _ve_configs(grammar, registry, n_seeds=200):
        assert all(s.indicators != ("ref_trailing_return",) for s in cfg.signals), cfg.name


def _its_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Fixture registry + iv_term_slope (the ve C2 iv_structure directional)."""
    its = IndicatorMetadata(
        id="iv_term_slope",
        version=1,
        family="iv_structure",
        lookback=90,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    return base.model_copy(update={"indicators": (*base.indicators, its)})


def test_v39_iv_term_slope_range_loosened(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The directional threshold axis reaches the x1.3-loosened region
    (below the old 0.01 floor) while keeping the 0.04 ceiling."""
    lows: list[float] = []
    for cfg in _ve_configs(grammar, _its_registry(registry), n_seeds=800):
        d = next(s for s in cfg.signals if s.role == "directional")
        if d.indicators[0] != "iv_term_slope":
            continue
        thr = d.params.get("threshold")
        if isinstance(thr, float):
            lows.append(thr)
    assert lows, "no iv_term_slope directional draws"
    assert min(lows) < 0.0095, f"loosened region unsampled: min={min(lows):.4f}"
    assert max(lows) <= 0.04 + 1e-9
    assert min(lows) >= 0.0077 - 1e-9


def test_v39_other_hypotheses_exits_untouched(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The ve schema edit must not leak: event_momentum keeps its required
    time_stop; MR keeps its required-pick timer share (~50% at v39; 0.65 since
    D291/v40 biased the pick on the combined relay's timer-cell evidence)."""
    space = build_search_space(grammar, registry)
    n_mr_timer = 0
    for seed in range(600):
        mr = sample_config(space, registry, random.Random(seed), forced_hypothesis="mean_reversion")
        n_mr_timer += int("time_stop" in {e.id for e in mr.exits})
    assert 0.60 < n_mr_timer / 600 < 0.70
