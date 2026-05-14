"""forge.ranking — composite scorer, greedy diversifier, batch queue (Phase 4)."""

from __future__ import annotations

from forge.ranking.config import load_ranker_config
from forge.ranking.prior_promotion import compute_prior_promotion_proximity
from forge.ranking.scorer import Ranker
from forge.ranking.types import (
    DiversificationConfig,
    RankedCandidate,
    RankerConfig,
    RankerWeights,
)

__all__ = [
    "DiversificationConfig",
    "RankedCandidate",
    "Ranker",
    "RankerConfig",
    "RankerWeights",
    "compute_prior_promotion_proximity",
    "load_ranker_config",
]
