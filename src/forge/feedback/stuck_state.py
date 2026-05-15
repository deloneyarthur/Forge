"""Stuck-state detector — log loudly when no promotions for K batches.

Long-term #3 (2026-05-14): if the rolling promotion rate is zero for
K consecutive batches, that is signal — either the grammar is in a
sterile region, the prefilter is letting through doomed candidates, or
a pipeline bug has slipped in. Silence here is worse than noise; the
operator should see "stuck" before they've burned a day of Crucible
compute on nothing.

The detector queries `batch_summaries.promotion_rate` (populated by the
feedback consumer §10) and counts how many recent batches in a row
landed at exactly zero. When the streak crosses the threshold, the
caller can decide what to do (today: emit a journal line; future:
PushNotification, auto-pause, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


# Default streak length before flagging as stuck. 10 batches x ~10 min/batch
# is ~1.5 hours of zero-promotion; long enough to clearly be a stuck state
# (not a single unlucky batch) without burning a full overnight unnoticed.
DEFAULT_STUCK_THRESHOLD: int = 10


def consecutive_zero_promotion_batches(db: duckdb.DuckDBPyConnection) -> int:
    """Return the count of most-recent consecutive zero-promotion batches.

    Reads `batch_summaries` newest-first; counts rows whose
    `promotion_rate` is 0.0, stopping at the first non-zero. Batches
    with NULL `promotion_rate` (feedback not yet consumed) are
    excluded — they neither break the streak nor extend it.

    Returns 0 if the most recent consumed batch had a non-zero rate.
    """
    rows = db.execute(
        """
        SELECT promotion_rate
        FROM batch_summaries
        WHERE promotion_rate IS NOT NULL
        ORDER BY submitted_at DESC
        """
    ).fetchall()
    streak = 0
    for (rate,) in rows:
        if float(rate) == 0.0:
            streak += 1
        else:
            break
    return streak


def is_stuck(
    db: duckdb.DuckDBPyConnection,
    *,
    threshold: int = DEFAULT_STUCK_THRESHOLD,
) -> tuple[bool, int]:
    """Return `(stuck_flag, streak_length)`. `stuck_flag` is True iff
    the streak length is >= threshold.
    """
    streak = consecutive_zero_promotion_batches(db)
    return streak >= threshold, streak


__all__ = [
    "DEFAULT_STUCK_THRESHOLD",
    "consecutive_zero_promotion_batches",
    "is_stuck",
]
