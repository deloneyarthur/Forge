"""Deterministic config populations for emission-property tests.

WHY: every emission test draws `sample_config(space, registry, random.Random(seed))` for
`seed in range(n)` and asserts a share or a param range over the draws. One helper keeps the
seed convention identical everywhere (draw `k` of any population is draw `k` of every larger
population on the same inputs), so populations can be shared as module fixtures and sliced.
`random.Random(seed)` is deliberate: it is the sampler's own RNG contract (hard rule #6 pins
the sequence to the seed), not a clock or a global seed.
"""

from __future__ import annotations

import random

from crucible_contracts import RegistrySnapshot, StrategyConfig

from forge.enumeration.sampler import sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import Grammar

_RANKABLE_HYPOTHESES = ("trend_continuation", "mean_reversion", "event_momentum")


def sample_configs(
    grammar: Grammar,
    registry: RegistrySnapshot,
    *,
    n: int,
    hypothesis: str | None = None,
    rank_share: float | None = None,
) -> list[StrategyConfig]:
    space = build_search_space(grammar, registry)
    share = {h: rank_share for h in _RANKABLE_HYPOTHESES} if rank_share else None
    return [
        sample_config(
            space,
            registry,
            random.Random(seed),
            forced_hypothesis=hypothesis,
            rank_combiner_share=share,
        )
        for seed in range(n)
    ]
