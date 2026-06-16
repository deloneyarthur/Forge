"""Score a genome with the published durable-score oracle (ridge).

Reproduces ``DurableOracle.score`` (FORGE meta-king A3 relay §2b) bit-for-bit so
the generator can rank candidate genomes locally.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from forge.king.featurize import featurize

if TYPE_CHECKING:
    from collections.abc import Mapping

    from forge.king.oracle import DurableOracle


def score_genome(genome: Mapping[str, Any], oracle: DurableOracle) -> float:
    """Return the oracle's predicted ``cpcv_sharpe_p25`` for ``genome``.

    Featurize -> median-impute NaNs -> standardize -> dot with the ridge
    weights, plus the intercept. Higher is better; this is the durable,
    full-history binding-gate metric, NOT a recency score.
    """
    vector = featurize(genome, oracle.feature_columns)
    total = oracle.intercept
    for value, median, mean, std, weight in zip(
        vector,
        oracle.feature_median,
        oracle.feature_mean,
        oracle.feature_std,
        oracle.weights,
        strict=True,
    ):
        imputed = median if math.isnan(value) else value
        total += ((imputed - mean) / std) * weight
    return total
