"""§6.2 composite scorer.

`Ranker` is a frozen wrapper around `RankerWeights`. Per
`IMPLEMENTATION_DECISIONS.md` D023/D2.a (Phase 4 closure) the weights
load once from `config/ranker.yaml` and are reused for every candidate
in a batch. Same pattern as Phase 3 `Calibration`.

Naming note: the §5.3.6 filter is `regime_exposure`; §6.2 (post-Phase-6
D025/D7 rename) uses `regime_exposure_score` for the same factor.
Forge's code keeps the weight key as ``regime_diversity`` for yaml
back-compat — the rename is intentionally doc-only. The scorer reads
``filters["regime_exposure"].score`` and multiplies it by
``weights.regime_diversity``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.prefilters.types import PreFilterReport
    from forge.ranking.types import RankerWeights


_REQUIRED_FILTER_KEYS = (
    "signal_density",
    "novelty",
    "regime_exposure",
    "permutation_test",
)


def _check_unit_interval(name: str, value: float) -> None:
    if math.isnan(value) or math.isinf(value) or not (0.0 <= value <= 1.0):
        msg = f"{name} must be in [0, 1]; got {value!r}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Ranker:
    """Apply §6.2 weights to a `PreFilterReport` + prior-promotion score.

    Constructed once per batch; the same instance scores every
    pre-filter-passed candidate.
    """

    weights: RankerWeights

    def score(self, report: PreFilterReport, prior_promotion_score: float) -> float:
        """Return the §6.2 weighted composite in `[0, 1]`.

        **Precondition (D060 / P2-4):** the caller MUST only invoke
        `score` on reports with `report.passed == True`. A short-circuited
        report (any filter rejected; remaining filters skipped) is
        missing the four ranker-relevant filter results and the method
        raises `ValueError` to surface the misuse loudly rather than
        producing a meaningless 0.0. Today the production caller is
        `forge.ranking.batch_ranker.rank_batch` which iterates only
        passed reports; this contract pins that requirement.

        Raises:
            ValueError: if the report is missing any of the four
                ranker-relevant filter results (incomplete short-circuit
                report) or if `prior_promotion_score` is out of range.
        """
        _check_unit_interval("Ranker.score: prior_promotion_score", prior_promotion_score)
        filters = report.filter_results
        for key in _REQUIRED_FILTER_KEYS:
            if key not in filters:
                msg = f"Ranker.score: PreFilterReport missing filter result {key!r}"
                raise ValueError(msg)
        composite = (
            self.weights.signal_density * filters["signal_density"].score
            + self.weights.novelty * filters["novelty"].score
            + self.weights.regime_diversity * filters["regime_exposure"].score
            + self.weights.permutation_test * filters["permutation_test"].score
            + self.weights.prior_promotion_proximity * prior_promotion_score
        )
        # Weights sum to 1.0 by RankerWeights invariant; each component in
        # [0, 1]; composite is in [0, 1] modulo float rounding. Clamp to
        # absorb 1e-17-scale drift before returning.
        return max(0.0, min(1.0, composite))


__all__ = ["Ranker"]
