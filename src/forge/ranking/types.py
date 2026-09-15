"""Ranking value types.

`RankedCandidate` is a pre-filter-passed config plus the two scores the submitter records
(`composite_score`, `prior_promotion_score`). Under the weekly campaign the in-cell scorer
fills both from the learned models (verdict P(component) x robustness tail_norm); the §6.2
weighted composite, its weights, and the diversification config left with the daemon
(Batch 5 G2, D419). The unit-interval check stays: a score outside [0, 1] is a scorer bug, not
a value to persist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.prefilters.types import PreFilterReport


def _check_unit_interval(name: str, value: float) -> None:
    if math.isnan(value) or math.isinf(value) or not (0.0 <= value <= 1.0):
        msg = f"{name} must be in [0, 1]; got {value!r}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A pre-filter-passed config with the scores the submitter persists.

    `prior_promotion_score` is recorded separately so the score breakdown stays inspectable
    in `submissions` / `shadow_scores`.
    """

    report: PreFilterReport
    prior_promotion_score: float
    composite_score: float

    def __post_init__(self) -> None:
        _check_unit_interval("RankedCandidate.composite_score", self.composite_score)
        _check_unit_interval("RankedCandidate.prior_promotion_score", self.prior_promotion_score)


__all__ = ["RankedCandidate"]
