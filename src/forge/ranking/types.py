"""Ranking value types.

Phase 4 produces a `RankedCandidate` per pre-filter-passed config and
fills `PreFilterReport.composite_score` per §6.2. See DESIGN.md §6
(ranker + queue) and `IMPLEMENTATION_DECISIONS.md` D023 (closure D2).

- `RankerWeights` — §6.2 component weights. Validated: each in `[0, 1]`
  and the sum equals 1.0 (tolerance 1e-9).
- `DiversificationConfig` — §6.3 method + similarity metric. Phase 4
  supports `method="greedy"` and `similarity_metric="jaccard"` only;
  DPP is reserved for a future bump.
- `RankerConfig` — the bundle loaded from `config/ranker.yaml`.
- `RankedCandidate` — a `PreFilterReport` plus its composite + prior-
  promotion proximity score. Stored pre-diversification; the
  diversifier consumes a list of these and selects N.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from forge.prefilters.types import PreFilterReport


_WEIGHT_SUM_TOL = 1e-9


def _check_unit_interval(name: str, value: float) -> None:
    if math.isnan(value) or math.isinf(value) or not (0.0 <= value <= 1.0):
        msg = f"{name} must be in [0, 1]; got {value!r}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RankerWeights:
    """§6.2 weights. Sum must equal 1.0; each in `[0, 1]`."""

    signal_density: float
    novelty: float
    regime_diversity: float
    permutation_test: float
    prior_promotion_proximity: float

    def __post_init__(self) -> None:
        for name, val in self._items():
            _check_unit_interval(f"RankerWeights.{name}", val)
        total = sum(v for _, v in self._items())
        if abs(total - 1.0) > _WEIGHT_SUM_TOL:
            msg = f"RankerWeights must sum to 1.0 (tol {_WEIGHT_SUM_TOL}); got {total!r}"
            raise ValueError(msg)

    def _items(self) -> tuple[tuple[str, float], ...]:
        return (
            ("signal_density", self.signal_density),
            ("novelty", self.novelty),
            ("regime_diversity", self.regime_diversity),
            ("permutation_test", self.permutation_test),
            ("prior_promotion_proximity", self.prior_promotion_proximity),
        )


@dataclass(frozen=True, slots=True)
class DiversificationConfig:
    """§6.3 diversification settings. Phase 4 ships greedy + jaccard."""

    method: Literal["greedy"]
    similarity_metric: Literal["jaccard"]


@dataclass(frozen=True, slots=True)
class RankerConfig:
    """Top-level config loaded from `config/ranker.yaml` (§10.3)."""

    weights: RankerWeights
    diversification: DiversificationConfig


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A pre-filter-passed config scored against §6.2.

    `composite_score` is the §6.2 weighted sum *before* §6.3 similarity
    penalties — diversifiers compute the adjusted score at selection
    time from this base. `prior_promotion_score` is recorded separately
    so the §6.2 breakdown stays inspectable.
    """

    report: PreFilterReport
    prior_promotion_score: float
    composite_score: float

    def __post_init__(self) -> None:
        _check_unit_interval("RankedCandidate.composite_score", self.composite_score)
        _check_unit_interval("RankedCandidate.prior_promotion_score", self.prior_promotion_score)


__all__ = [
    "DiversificationConfig",
    "RankedCandidate",
    "RankerConfig",
    "RankerWeights",
]
