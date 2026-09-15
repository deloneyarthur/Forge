"""Ranking value types.

`RankedCandidate` is a pre-filter-passed config plus the two scores the submitter records
(`composite_score`, `prior_promotion_score`). Under the weekly campaign the in-cell scorer
fills both from the learned models (verdict P(component) x robustness tail_norm); the §6.2
weighted composite, its weights, and the diversification config left with the daemon
(Batch 5 G2, D419). The unit-interval check stays: a score outside [0, 1] is a scorer bug, not
a value to persist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from forge.core.validation import check_unit_interval

if TYPE_CHECKING:
    from forge.prefilters.types import PreFilterReport


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
        check_unit_interval("RankedCandidate.composite_score", self.composite_score)
        check_unit_interval("RankedCandidate.prior_promotion_score", self.prior_promotion_score)


__all__ = ["RankedCandidate"]
