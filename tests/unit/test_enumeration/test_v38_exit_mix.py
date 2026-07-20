"""v38 exit-CLASS mix shift — Crucible's 2026-07-16 relay
(``FORGE_trend_swinglong_exit_mix_2026-07-16.md``; composes with the v36
exit-duration prior, does not replace it).

Their weekly-census read (n=45,850 decided trend/swing_long/xsect, 07-02→07-16;
reproduced on OUR verdicts to within ~1pp before building): exit class orders
the whole conversion surface — chandelier-only 39.1% component rate >
other-discretionary 30.7% > timer-carrying 16.9%, replicating in the
confluence stratum and the swing_mid census window. 46% of the cell carried a
timer (the p=0.5 optional draw); chandelier-only was 22% (0.5 required-pick x
0.5 no-timer).

The ask, scoped to (trend_continuation, swing_long) ONLY: carry timers less
(share well below 46%), chandelier-only well above 22%, keep U[8,10] n_bars
for the timer draws that remain. Implementation: the time_stop
optional-additions Bernoulli drops 0.5 → 0.15 in this cell — one knob; the
chandelier-only share rises mechanically (0.5 x 0.85 ≈ 42%) and trailing_atr
(D236: not refuted, kept alongside) keeps its required-pick share. Every other
(hypothesis, bucket) keeps p=0.5 — their "do not touch other buckets on this
evidence" (swing_mid's spread is small; MR swing_mid's timer HELPS and is a
required_from_set pick, not an optional, so it is structurally untouched).
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


def _trend_configs_by_bucket(
    grammar: Grammar, registry: RegistrySnapshot, *, n_seeds: int
) -> dict[str, list[StrategyConfig]]:
    space = build_search_space(grammar, registry)
    out: dict[str, list[StrategyConfig]] = {}
    for seed in range(n_seeds):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="trend_continuation"
        )
        out.setdefault(cfg.dte_bucket, []).append(cfg)
    return out


def test_v38_trend_swing_long_timer_share_reduced(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The scoped cell draws time_stop at p=0.15 (was 0.5): census evidence says
    the timer class converts at 0.43x chandelier-only and its median config
    contributes nothing (solo-p25 med 0.026)."""
    by_bucket = _trend_configs_by_bucket(grammar, registry, n_seeds=3000)
    swing_long = by_bucket.get("swing_long", [])
    assert len(swing_long) >= 300, f"too few swing_long draws: {len(swing_long)}"
    timer_share = sum(1 for c in swing_long if "time_stop" in _exit_ids(c)) / len(swing_long)
    assert 0.10 < timer_share < 0.21, f"timer share {timer_share:.3f} not ~0.15"


def test_v38_trend_swing_long_chandelier_only_share_rises(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Chandelier-only (discretionary set exactly {chandelier_exit}) rises
    mechanically well above the census 22% once fewer timers are stacked."""
    by_bucket = _trend_configs_by_bucket(grammar, registry, n_seeds=3000)
    swing_long = by_bucket.get("swing_long", [])
    assert len(swing_long) >= 300
    mandatory = frozenset.intersection(*(_exit_ids(c) for c in swing_long))
    chan_only = sum(
        1 for c in swing_long if (_exit_ids(c) - mandatory) == {"chandelier_exit"}
    ) / len(swing_long)
    assert chan_only > 0.30, f"chandelier-only share {chan_only:.3f} not well above 0.22"


def test_v38_trend_swing_mid_timer_share_unchanged(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """ "Do not touch other buckets": swing_mid keeps the p=0.5 optional draw."""
    by_bucket = _trend_configs_by_bucket(grammar, registry, n_seeds=3000)
    swing_mid = by_bucket.get("swing_mid", [])
    assert len(swing_mid) >= 300, f"too few swing_mid draws: {len(swing_mid)}"
    timer_share = sum(1 for c in swing_mid if "time_stop" in _exit_ids(c)) / len(swing_mid)
    assert 0.42 < timer_share < 0.58, f"swing_mid timer share moved: {timer_share:.3f}"


def test_v38_remaining_swing_long_timers_keep_u810(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The v36 U[8,10] n_bars prior composes: every surviving swing_long timer
    still samples n_bars in [8, 10]."""
    by_bucket = _trend_configs_by_bucket(grammar, registry, n_seeds=3000)
    carriers = [c for c in by_bucket.get("swing_long", []) if "time_stop" in _exit_ids(c)]
    assert carriers, "no surviving timer draws to check"
    for cfg in carriers:
        params = next(e.params for e in cfg.exits if e.id == "time_stop")
        assert params.get("n_bars") in (8, 9, 10), (cfg.name, params)


def test_v38_mr_time_stop_share(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """MR's timer is a required_from_set pick (structurally not an optional
    draw) — v38's evidence did not move it (~50% then). D291 (v40) later biased
    the pick to 0.65 on the combined relay's timer-cell evidence; this guard
    now pins THAT level so the v38 optional-draw knob still cannot leak into
    MR's required pick."""
    space = build_search_space(grammar, registry)
    n_timer = 0
    n = 1500
    for seed in range(n):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="mean_reversion"
        )
        n_timer += int("time_stop" in _exit_ids(cfg))
    share = n_timer / n
    assert 0.60 < share < 0.70, f"MR time_stop share moved off 0.65: {share:.3f}"
