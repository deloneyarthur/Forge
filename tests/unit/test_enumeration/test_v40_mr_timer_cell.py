"""v40 MR timer cell — Crucible's 2026-07-20 combined relay §1
(``FORGE_combined_relay_2026-07-20.md``; composes with the v36 duration prior,
supersedes its swing_mid-only scoping on new evidence).

Their read: the timer-MR cell CONVERTED — 1,087 components in 5 days, 68 at
cpcv>=1.0, genome-diverse across n_bars 8-12; the head (65316ca4, 11-bar hold)
lifts the 2-leg book to cpcv_p25 1.7236 / WF 2.3407 with honest decorrelation
0.347 — duration is the measured decorrelation axis. Their "15% timer-share"
premise is a mis-attribution (v38's 0.15 touched trend/swing_long's OPTIONAL
draw; MR's timer is a required_from_set pick at ~50%), but the intent is
implementable and we reproduced the direction on OUR verdicts before building
(decided >= 07-14, MR excl. capitulation): timer 10.7% vs target_exit 9.9%
component rate overall, and within timers n_bars 8-12 converts 15.0% vs 13-15
at 11.9% vs param-less default-5 at 5.3% (the worst MR exit cell, n~5,000).

The v40 asks, scoped to mean_reversion EXCLUDING the capitulation directional
(its v35 bare-drop pane is veto-frozen mid-trial — cohort hygiene, D282):
  * the required_from_set pick biases to time_stop at p=0.65 (was uniform 0.5)
    — share moves AWAY from target_exit, the direction Crucible already
    flagged as safe (D257: share shifting TO target_exit "breaks the book");
  * every MR time_stop draw samples n_bars ~ U[8,12] at ALL buckets — the
    measured family box; swing_mid narrows [8,15] -> [8,12], the param-less
    default-5 emission (their engine default) is retired for MR.
Capitulation keeps the uniform pick and D270's U[5,15] at both buckets.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot, StrategyConfig

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar, load_grammar
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


def _exit_ids(cfg: StrategyConfig) -> frozenset[str]:
    return frozenset(e.id for e in cfg.exits)


def _time_stop_nbars(cfg: StrategyConfig) -> int | None:
    for e in cfg.exits:
        if e.id == "time_stop":
            return e.params.get("n_bars")  # type: ignore[return-value]
    return None


def _is_capitulation(cfg: StrategyConfig) -> bool:
    d = next(s for s in cfg.signals if s.role == "directional")
    return d.indicators == ("momentum",)


def _mr_configs(
    grammar: Grammar, registry: RegistrySnapshot, *, n_seeds: int
) -> list[StrategyConfig]:
    space = build_search_space(grammar, registry)
    return [
        sample_config(space, registry, random.Random(seed), forced_hypothesis="mean_reversion")
        for seed in range(n_seeds)
    ]


def test_v40_mr_required_pick_biased_to_time_stop(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Non-capitulation MR draws time_stop from the required set at p=0.65."""
    cfgs = [c for c in _mr_configs(grammar, registry, n_seeds=4000) if not _is_capitulation(c)]
    assert len(cfgs) >= 1000, f"too few non-capitulation MR draws: {len(cfgs)}"
    timer_share = sum(1 for c in cfgs if "time_stop" in _exit_ids(c)) / len(cfgs)
    assert 0.60 < timer_share < 0.70, f"timer share {timer_share:.3f} not ~0.65"


def test_v40_mr_time_stop_nbars_in_8_12_all_buckets(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every non-capitulation MR time_stop draw emits n_bars in [8, 12] — the
    measured family box — at EVERY bucket (the param-less default-5 emission is
    retired for MR; our funnel: 5.3% conversion vs 15.0% in-box)."""
    checked = 0
    for cfg in _mr_configs(grammar, registry, n_seeds=4000):
        if _is_capitulation(cfg):
            continue
        nbars = _time_stop_nbars(cfg)
        if nbars is None:
            assert "time_stop" not in _exit_ids(cfg), (
                f"param-less time_stop survived in MR at bucket {cfg.dte_bucket}"
            )
            continue
        assert 8 <= nbars <= 12, f"n_bars {nbars} outside [8,12] at {cfg.dte_bucket}"
        checked += 1
    assert checked >= 500, f"too few MR time_stop draws checked: {checked}"


def test_v40_trend_required_pick_stays_uniform(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Control: the bias is scoped to MR — trend's required_from_set pick
    (trailing_atr vs chandelier_exit) stays uniform."""
    space = build_search_space(grammar, registry)
    cfgs = [
        sample_config(space, registry, random.Random(seed), forced_hypothesis="trend_continuation")
        for seed in range(3000)
    ]
    chandelier_share = sum(1 for c in cfgs if "chandelier_exit" in _exit_ids(c)) / len(cfgs)
    assert 0.42 < chandelier_share < 0.58, (
        f"trend chandelier required-pick share {chandelier_share:.3f} drifted from ~0.5"
    )
