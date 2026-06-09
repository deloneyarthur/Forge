"""Jaccard overlap of activation-date sets, shared across pre-filters.

Both the temporal-novelty filter (§5.3.5) and the empirical
signal-correlation filter (T2.6) compare firing-date sets with the same
Jaccard definition. It is a fixed mathematical formula, not per-filter
policy, so one shared implementation keeps the two filters' notion of
"overlap" from drifting apart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


def jaccard(a: frozenset[date], b: frozenset[date]) -> float:
    """Intersection over union; 0.0 when either side is empty (no overlap signal)."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)
