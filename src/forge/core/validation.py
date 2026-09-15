"""Shared value checks (Batch 6 A2).

WHY: the "a score is a finite number in [0, 1]" rule was written twice, once for
`RankedCandidate.composite_score` and once for `FilterResult.score`, with the same NaN/inf
guard. One function, one error message shape.
"""

from __future__ import annotations

import math


def check_unit_interval(name: str, value: float) -> None:
    """Raise ``ValueError`` unless ``value`` is a finite float in ``[0, 1]``."""
    if math.isnan(value) or math.isinf(value) or not (0.0 <= value <= 1.0):
        msg = f"{name} must be in [0, 1]; got {value!r}"
        raise ValueError(msg)


__all__ = ["check_unit_interval"]
