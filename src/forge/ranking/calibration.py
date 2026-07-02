"""Calibration diagnostics + Platt recalibration for the P(component) model (P1.3).

The F3 verdict model's ``score_features`` returns a raw logistic probability that
recent artifacts over-predict ~3-5x above p≈0.3 (fable-audit learned-systems §1) —
harmless for RANKING (AUC is monotone-invariant) but wrong for the ABSOLUTE
gate-then-tail eligibility floor, which reads P on its own scale. This module
quantifies that miscalibration (reliability table, ECE, Brier decomposition) and
supplies a deterministic, dependency-free Platt recalibrator ``(a, b)`` so a held-out
fit can map raw logits back onto the diagonal.

Consumption of the recalibrator on the LIVE score path is deferred to the floor
re-derivation (P1.1) — recalibrating the P that fills the §6.2 prior slot would change
the composite sort and confound the in-flight prior-weight prereg. Here the pieces only
power telemetry: the eval readout, the co-primary ECE criterion, and the floor's
eligible-fraction monitor.

Pure functions, no RNG, no new deps (hard rules #5/#6): identical inputs give identical
numbers, so a checkpoint's ECE is reproducible.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from forge.ranking.model import _fit_irls, _sigmoid

if TYPE_CHECKING:
    from collections.abc import Sequence

_EPS = 1e-6
# A whisper of ridge keeps the 1-D Platt IRLS finite on (near-)separable eval windows
# without meaningfully biasing the fit; the base model's fit is untouched.
_PLATT_RIDGE = 1e-6

# One reliability row: (bin_low_edge, n, mean_prediction, empirical_rate).
ReliabilityRow = tuple[float, int, float, float]


def logit(p: float, *, eps: float = _EPS) -> float:
    """Inverse sigmoid, clipped to the open interval so p∈{0,1} stays finite."""
    q = min(1.0 - eps, max(eps, p))
    return math.log(q / (1.0 - q))


def _bin_index(prob: float, n_bins: int) -> int:
    """Equal-width bin on [0, 1]; p==1.0 clamps into the last bin (no phantom bin)."""
    return min(int(prob * n_bins), n_bins - 1)


def reliability_table(
    labels: Sequence[int], probs: Sequence[float], *, n_bins: int = 10
) -> tuple[ReliabilityRow, ...]:
    """Group predictions into ``n_bins`` equal-width bins; return only non-empty bins as
    ``(bin_low_edge, n, mean_prediction, empirical_rate)`` in ascending bin order."""
    bins: dict[int, list[tuple[float, int]]] = {}
    for prob, label in zip(probs, labels, strict=True):
        bins.setdefault(_bin_index(prob, n_bins), []).append((prob, label))
    rows: list[ReliabilityRow] = []
    for index in sorted(bins):
        members = bins[index]
        n = len(members)
        rows.append(
            (
                index / n_bins,
                n,
                sum(p for p, _ in members) / n,
                sum(y for _, y in members) / n,
            )
        )
    return tuple(rows)


def expected_calibration_error(
    labels: Sequence[int], probs: Sequence[float], *, n_bins: int = 10
) -> float:
    """Frequency-weighted mean gap between predicted probability and realized rate —
    the standard ECE. 0.0 on an empty input (nothing miscalibrated)."""
    total = len(labels)
    if total == 0:
        return 0.0
    return sum(
        (n / total) * abs(mean_pred - rate)
        for _lo, n, mean_pred, rate in reliability_table(labels, probs, n_bins=n_bins)
    )


def brier_decomposition(
    labels: Sequence[int], probs: Sequence[float], *, n_bins: int = 10
) -> tuple[float, float, float]:
    """Murphy decomposition ``(reliability, resolution, uncertainty)``.

    ``brier == reliability - resolution + uncertainty`` (exact when each bin holds a
    single forecast value; approximate otherwise). Lower reliability = better calibration;
    higher resolution = the forecaster separates outcomes; uncertainty is the irreducible
    base-rate variance. 0/0/0 on empty input.
    """
    total = len(labels)
    if total == 0:
        return 0.0, 0.0, 0.0
    base_rate = sum(labels) / total
    uncertainty = base_rate * (1.0 - base_rate)
    reliability = 0.0
    resolution = 0.0
    for _lo, n, mean_pred, rate in reliability_table(labels, probs, n_bins=n_bins):
        weight = n / total
        reliability += weight * (mean_pred - rate) ** 2
        resolution += weight * (rate - base_rate) ** 2
    return reliability, resolution, uncertainty


def platt_fit(scores: Sequence[float], labels: Sequence[int]) -> tuple[float, float]:
    """Fit ``P = sigmoid(a * score + b)`` by 1-D IRLS on ``scores`` (pass model logits for
    classic Platt/temperature scaling). Returns ``(a, b)``. Deterministic — reuses the
    verdict model's Newton-IRLS solver, no RNG. Raises ``ValueError`` on a single class."""
    positives = sum(labels)
    if positives == 0 or positives == len(labels):
        msg = f"cannot Platt-fit on a single class ({positives}/{len(labels)} positive)"
        raise ValueError(msg)
    intercept, coefficients = _fit_irls([[s] for s in scores], list(labels), _PLATT_RIDGE)
    return coefficients[0], intercept


def platt_apply(a: float, b: float, score: float) -> float:
    """Recalibrated probability ``sigmoid(a * score + b)`` (a=1, b=0 is the identity)."""
    return _sigmoid(a * score + b)


__all__ = [
    "ReliabilityRow",
    "brier_decomposition",
    "expected_calibration_error",
    "logit",
    "platt_apply",
    "platt_fit",
    "reliability_table",
]
