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

**D035 (2026-05-16)**: detector is now grammar-change-aware. Pre-D035 a
streak that crossed structural fix events (grammar version bumps,
calibration tweaks, code restarts) kept climbing, generating
false-positive "stuck" flags after operators shipped fixes intended to
reset the picture. The fix: `is_stuck` and `consecutive_zero_promotion_batches`
both accept an optional `since: datetime` floor; the CLI passes the most
recent `grammar_versions.changed_at`. Pre-floor batches don't break or
extend the streak — they're considered prior history.

Calibration-only changes (D031/D032/D033) that don't bump grammar
intentionally do NOT reset the streak — those are tweaks, not structural
shifts. To force a reset for a calibration cycle, bump grammar version
or insert a row into `grammar_versions` with `change_type='calibration'`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    import duckdb


# Default streak length before flagging as stuck. 10 batches x ~10 min/batch
# is ~1.5 hours of zero-promotion; long enough to clearly be a stuck state
# (not a single unlucky batch) without burning a full overnight unnoticed.
DEFAULT_STUCK_THRESHOLD: int = 10


def most_recent_grammar_change(
    db: duckdb.DuckDBPyConnection,
) -> datetime | None:
    """Return the timestamp of the most recent grammar_versions row.

    Returns None if the table is empty (e.g., fresh DB or grammar never
    bumped since Phase 1). Callers should treat None as "no floor"
    and fall back to all-time streak counting.
    """
    row = db.execute(
        "SELECT MAX(changed_at) FROM grammar_versions",
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return row[0]  # type: ignore[no-any-return]


def consecutive_zero_promotion_batches(
    db: duckdb.DuckDBPyConnection,
    *,
    since: datetime | None = None,
) -> int:
    """Return the count of most-recent consecutive zero-promotion batches.

    Reads `batch_summaries` newest-first; counts rows whose
    `promotion_rate` is 0.0, stopping at the first non-zero. Batches
    with NULL `promotion_rate` (feedback not yet consumed) are
    excluded — they neither break the streak nor extend it.

    `since` (D035): optional datetime floor. Only batches submitted at or
    after this time are considered. Pre-floor batches are treated as
    prior history (no influence on streak). Pass the most recent
    `grammar_versions.changed_at` to reset the counter at every grammar
    bump.

    Returns 0 if the most recent consumed batch had a non-zero rate, or
    if no consumed batches exist at-or-after `since`.
    """
    if since is None:
        rows = db.execute(
            """
            SELECT promotion_rate
            FROM batch_summaries
            WHERE promotion_rate IS NOT NULL
            ORDER BY submitted_at DESC
            """,
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT promotion_rate
            FROM batch_summaries
            WHERE promotion_rate IS NOT NULL
              AND submitted_at >= ?
            ORDER BY submitted_at DESC
            """,
            [since],
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
    since: datetime | None = None,
) -> tuple[bool, int]:
    """Return `(stuck_flag, streak_length)`. `stuck_flag` is True iff
    the streak length is >= threshold.

    `since` (D035): forwarded to `consecutive_zero_promotion_batches`.
    When supplied, the streak only counts batches at-or-after `since`
    — so a grammar bump resets the counter without manual intervention.
    Callers that want the all-time streak (e.g., for audit summaries)
    should leave `since=None`.
    """
    streak = consecutive_zero_promotion_batches(db, since=since)
    return streak >= threshold, streak


__all__ = [
    "DEFAULT_STUCK_THRESHOLD",
    "consecutive_zero_promotion_batches",
    "is_stuck",
    "most_recent_grammar_change",
]
