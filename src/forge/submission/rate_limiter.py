"""§7.3 in-flight rate limiter — clear-to-submit check for `forge run`.

The rate limiter answers a single question: may the next batch submit?
Per §7.3 Forge waits until >=80% of the previous batch's candidates
are gated in Crucible before queuing a new one. This keeps the inbox
from growing into a queue Forge can't learn from.

D023/D6.a — Phase 4 ships the check function. The 10-minute poll loop
is Phase 5/6 daemon work; `forge run` calls this once and either
proceeds or exits with a "waiting" message.

A missing Crucible DB is treated as "0% gated" — conservative: if we
can't prove the prior batch finished, we stay blocked. The cost of a
false-block is a "waiting" message; the cost of a false-clear is
flooding the inbox.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from crucible_contracts import get_recent_gated_runs
from crucible_contracts.exceptions import QueryError

from forge.persistence.db import db_connection

_DEFAULT_THRESHOLD = 0.80
# Pull a generous slice of recent gated runs; the cross-reference is
# bounded by `submitted_count`, so the limit only needs to exceed the
# typical batch size (200 per §6.4) with headroom for parallelism.
_GATED_QUERY_LIMIT_FACTOR = 4
_GATED_QUERY_MIN = 1000


@dataclass(frozen=True, slots=True)
class RateLimitStatus:
    """Outcome of `check_rate_limit`.

    `clear` is the only field `forge run` strictly needs; the rest are
    for the CLI's "waiting" message and for `pre_filter_logs`/audit.
    """

    clear: bool
    pct_gated: float
    blocking_batch_id: uuid.UUID | None
    submitted_count: int
    gated_count: int


def check_rate_limit(
    forge_db_path: Path,
    crucible_db_path: Path,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
) -> RateLimitStatus:
    """Return whether a new batch may submit.

    Steps:
    1. Find the most-recent `forge_batch_id` in `submissions`.
    2. Collect that batch's `config_hash`es.
    3. Query Crucible's gated runs (read-only) and intersect.
    4. Clear if `intersection / batch_size >= threshold`.

    If the Forge DB has no submissions, `clear=True` (first-run case).
    If the Crucible DB is missing or unreadable, the gated-count is
    treated as 0 (blocked).
    """
    with db_connection(forge_db_path) as conn:
        row = conn.execute(
            "SELECT forge_batch_id FROM submissions ORDER BY submitted_at DESC LIMIT 1",
        ).fetchone()
        if row is None:
            return RateLimitStatus(
                clear=True,
                pct_gated=1.0,
                blocking_batch_id=None,
                submitted_count=0,
                gated_count=0,
            )
        latest_batch_id = uuid.UUID(str(row[0]))
        hash_rows = conn.execute(
            "SELECT config_hash FROM submissions WHERE forge_batch_id = ?",
            [str(latest_batch_id)],
        ).fetchall()

    submitted_count = len(hash_rows)
    batch_hashes = {str(h[0]) for h in hash_rows}

    if submitted_count == 0:
        # The batch row exists but has no candidates. Treat as clear.
        return RateLimitStatus(
            clear=True,
            pct_gated=1.0,
            blocking_batch_id=None,
            submitted_count=0,
            gated_count=0,
        )

    gated_count = 0
    try:
        recent = get_recent_gated_runs(
            crucible_db_path,
            limit=max(submitted_count * _GATED_QUERY_LIMIT_FACTOR, _GATED_QUERY_MIN),
        )
        gated_count = sum(1 for r in recent if r.run.config_hash in batch_hashes)
    except QueryError:
        # Crucible DB missing or unreadable -> 0 gated; remain blocked.
        gated_count = 0

    pct = gated_count / submitted_count
    return RateLimitStatus(
        clear=pct >= threshold,
        pct_gated=pct,
        blocking_batch_id=None if pct >= threshold else latest_batch_id,
        submitted_count=submitted_count,
        gated_count=gated_count,
    )


__all__ = ["RateLimitStatus", "check_rate_limit"]
