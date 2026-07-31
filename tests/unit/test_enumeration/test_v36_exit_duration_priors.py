"""v36 exit-duration prior concentration — Crucible's 2026-07-15 relay
(``FORGE_exit_duration_priors_2026-07-15.md``; scoping confirmed/vetoed in
``FORGE_v36_scoping_response_2026-07-15.md``; full scoping:
``docs/proposals/v36-exit-duration-priors.md``).

Crucible's exit registry defaults time_stop ``n_bars`` to 5; Forge only ever
emitted ``n_bars`` on the capitulation directional (D270, U[5,15]). Their
probes (18 real WF+CPCV evals / champion-proxy sweep):

  * trend swing_long: the day-5 timer takes 84-88% of exits and CUTS WINNERS
    (time_stop-bucket win-rate 0.45->0.74 with longer holds); n_bars=10
    improves cpcv 6/6, wf 5/6 AND maxDD, inside their declared [3,10] box;
    do NOT pass 10 (n=21 buys cpcv by re-opening the tail, comp0 maxDD -44%)
    -> n_bars ~ U[8,10].
  * MR swing_mid: the [5,15] box is right, the floor is actively harmful
    (-0.382 p25-proxy at 5 vs +0.161 at 8; plateau 8-20, peak 12; [6,7] is
    unsampled interpolation against a known-bad floor) -> n_bars ~ U[8,15],
    zero floor mass (their confirmed strong form).
  * capitulation inheritance VETOED (cohort hygiene, not merits): the
    directional keeps D270's U[5,15] at BOTH buckets until the v34-vs-v35
    capitulation pane is read — resolved BEFORE the bucket checks.

Every other time_stop carrier keeps the param-less exit (registry default 5)
— their "do not touch other buckets on this evidence".
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


def _time_stop_params(cfg: StrategyConfig) -> dict[str, object] | None:
    """The time_stop exit's params, or None when the config doesn't carry it."""
    for e in cfg.exits:
        if e.id == "time_stop":
            return dict(e.params)
    return None


def _is_capitulation(cfg: StrategyConfig) -> bool:
    d = next(s for s in cfg.signals if s.role == "directional")
    return d.indicators == ("momentum",)


# --- trend swing_long: U[8,10] ---------------------------------------------------


def test_v36_trend_swing_long_time_stop_in_8_10(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every trend swing_long config carrying time_stop samples n_bars in
    [8,10]; the box is fully covered across seeds (and NEVER exceeds 10 —
    their tail warning)."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    seen_nbars: set[object] = set()
    for seed in range(600):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        if cfg.dte_bucket != "swing_long":
            continue
        ts = _time_stop_params(cfg)
        if ts is None:
            continue
        n_bars = ts.get("n_bars")
        assert isinstance(n_bars, int), ts
        assert 8 <= n_bars <= 10, ts
        seen_nbars.add(n_bars)
    assert seen_nbars == {8, 9, 10}, seen_nbars


def test_v36_trend_other_buckets_keep_the_bare_time_stop(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Their explicit "do not touch other buckets on this evidence": trend
    swing_mid / swing_short time_stops stay param-less (registry default 5)."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    checked = 0
    for seed in range(600):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="trend_continuation")
        if cfg.dte_bucket == "swing_long":
            continue
        ts = _time_stop_params(cfg)
        if ts is None:
            continue
        checked += 1
        assert ts == {}, (cfg.dte_bucket, ts)
    assert checked > 0, "no non-swing_long trend time_stop draws sampled"


# --- MR: v36 shipped swing_mid U[8,15]; D291 (v40) narrowed to U[8,12] and went
# bucket-wide — the v36-era assertions ([8,15] box, bare swing_short timer) are
# SUPERSEDED; the family-box behavior itself is owned by test_v40_mr_timer_cell.
# The floor-mass claim (no n_bars < 8) is v36's surviving invariant.


def test_mr_swing_mid_time_stop_in_8_12_since_v40(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """Every NON-capitulation MR swing_mid config carrying time_stop samples
    n_bars in [8,12] — v36's zero-floor-mass invariant survives; the top edge
    narrowed 15 -> 12 on D291's measured family box (our funnel: 8-12 converts
    15.0% vs 13-15 at 11.9%), with both box edges reached across seeds."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    seen_nbars: set[object] = set()
    for seed in range(600):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        if _is_capitulation(cfg) or cfg.dte_bucket != "swing_mid":
            continue
        ts = _time_stop_params(cfg)
        if ts is None:
            continue
        n_bars = ts.get("n_bars")
        assert isinstance(n_bars, int), ts
        assert 8 <= n_bars <= 12, ts
        seen_nbars.add(n_bars)
    assert seen_nbars, "no MR swing_mid time_stop draws sampled"
    assert {8, 12} <= seen_nbars, seen_nbars


def test_mr_swing_short_time_stop_in_family_box_since_v40(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """v36 kept swing_short param-less ("swing_mid ONLY"); D291 (v40) retired
    the bare default-5 emission for MR (worst MR cell, 5.3% conversion) — the
    U[8,12] family box now applies at every non-capitulation MR bucket."""
    reg = _v31_registry(registry)
    space = build_search_space(grammar, reg)
    checked = 0
    for seed in range(600):
        cfg = sample_config(space, reg, random.Random(seed), forced_hypothesis="mean_reversion")
        if _is_capitulation(cfg) or cfg.dte_bucket == "swing_mid":
            continue
        ts = _time_stop_params(cfg)
        if ts is None:
            continue
        checked += 1
        n_bars = ts.get("n_bars")
        assert isinstance(n_bars, int), (cfg.dte_bucket, ts)
        assert 8 <= n_bars <= 12, (cfg.dte_bucket, ts)
    assert checked > 0, "no non-capitulation MR swing_short time_stop draws sampled"


# --- the capitulation veto: D270's U[5,15] survives at BOTH buckets ---------------
