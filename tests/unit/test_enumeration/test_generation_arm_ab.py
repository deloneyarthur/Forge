"""Tier 1 — the concurrent generation A/B (draw-weight arms).

WHY CONCURRENT. A grammar or weighting change evaluated across TIME confounds the change with
the measurement window: Crucible's drift floor puts version-over-version deltas below
~0.15-0.20 beyond resolution at any n, because the noise is BETWEEN windows and does not shrink
with sample size. The two-leg ranked lane is the proof the fix works -- same batches, same
days, only the objective differing, read at z=+6.27. This gives the generation side the same
instrument: both weight sets draw inside every batch, so drift cancels.

WHAT THE ARMS DIFFER BY. Only the regime-gate yield weights. The incumbent map scores a cell by
its COMPONENT rate; arm B scores it by BOOK-USABLE rate (cpcv >= 0.9439). The honest-arm
scorecard says those are not the same thing -- 22 of 38 measured cells produce components and
zero book-usable output -- so "which of the two should steer the regime draw" is a real
question with a measurable answer.

`generation_arm` is the contracts 1.39.0 field built for exactly this (additive, and
HASH-EXCLUDED so an identical config drawn by both arms does not dedup into two strategies and
turn the comparison into a measurement of dedup).

DETERMINISM (hard rule #6): with the feature off, no arm coin is drawn and no rng is consumed,
so enumeration is byte-identical to the pre-feature stream.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

from forge.enumeration import enumerate_candidates
from forge.grammar.loader import load_grammar
from forge.grammar.models import Grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SHARE = {"trend_continuation": 0.6, "mean_reversion": 0.6}


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(
        _REPO_ROOT / "config" / "grammar.yaml",
        archive_dir=_REPO_ROOT / "config" / "grammar_archive",
    )


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


def _hashes(grammar: Grammar, registry: RegistrySnapshot, **kw: object) -> list[str]:
    return [
        c.config_hash
        for c in enumerate_candidates(
            grammar, registry, seed=4242, max_candidates=400, rank_combiner_share=_SHARE, **kw
        )
    ]


def test_off_is_byte_identical(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """The kill-switch contract: no arm share -> no coin -> no rng consumed."""
    base = _hashes(grammar, registry)
    assert _hashes(grammar, registry, generation_arm_b_share=0.0) == base
    assert _hashes(grammar, registry, generation_arm_b_weights={}) == base


def test_off_leaves_generation_arm_unset(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Absence must map to 'unset', never to the control arm — a config tagged 'baseline'
    when no A/B is running would silently enter a future arm comparison as data."""
    for cfg in enumerate_candidates(
        grammar, registry, seed=4242, max_candidates=60, rank_combiner_share=_SHARE
    ):
        assert cfg.generation_arm is None


def test_both_arms_are_tagged_and_present(grammar: Grammar, registry: RegistrySnapshot) -> None:
    arms = Counter(
        cfg.generation_arm
        for cfg in enumerate_candidates(
            grammar,
            registry,
            seed=4242,
            max_candidates=400,
            rank_combiner_share=_SHARE,
            generation_arm_b_share=0.5,
            generation_arm_b_weights={("trend_continuation", "donchian", "swing_mid", "adx"): 9.0},
        )
    )
    assert arms["baseline"] > 0
    assert arms["book_usable"] > 0
    assert None not in arms
    # ~50/50 within sampling noise on 400 draws.
    assert 0.3 < arms["book_usable"] / sum(arms.values()) < 0.7


def test_the_split_is_deterministic(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Same seed -> same arm assignment, or the A/B is not reproducible (hard rule #6)."""
    kw = {
        "generation_arm_b_share": 0.5,
        "generation_arm_b_weights": {("trend_continuation", "donchian", "swing_mid", "adx"): 9.0},
    }
    a = [
        (c.config_hash, c.generation_arm)
        for c in enumerate_candidates(
            grammar, registry, seed=99, max_candidates=200, rank_combiner_share=_SHARE, **kw
        )
    ]
    b = [
        (c.config_hash, c.generation_arm)
        for c in enumerate_candidates(
            grammar, registry, seed=99, max_candidates=200, rank_combiner_share=_SHARE, **kw
        )
    ]
    assert a == b


def test_arm_tag_does_not_enter_the_config_hash(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """The precondition contracts 1.39.0 calls out: if the arm entered the hash, the same
    config drawn both ways would dedup as two strategies and the A/B would measure dedup
    rather than the weighting."""
    cfg = next(
        iter(
            enumerate_candidates(
                grammar, registry, seed=7, max_candidates=1, rank_combiner_share=_SHARE
            )
        )
    )
    assert cfg.model_copy(update={"generation_arm": "book_usable"}).config_hash == cfg.config_hash
