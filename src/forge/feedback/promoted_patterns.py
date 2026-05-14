"""§9.1 `promoted_patterns` writer.

`record_promoted_patterns(db, patterns, *, discovered_at)` inserts one row
per PromotedPattern. Each call mints fresh `pattern_id` UUIDs — re-running
is NOT a no-op because the same pattern can recur over time and each
discovery deserves its own row (the analyzer's job is to call this at the
right cadence, not to dedupe).

The writer is kept separate from the analyzer so the analyzer stays pure
(D024/D2 — easier to test, easier to call from operator-facing CLI).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    import duckdb

    from forge.feedback.types import PromotedPattern


def record_promoted_patterns(
    db: duckdb.DuckDBPyConnection,
    patterns: Iterable[PromotedPattern],
    *,
    discovered_at: datetime,
) -> list[uuid.UUID]:
    """Insert each pattern; return the minted `pattern_id`s in input order."""
    if discovered_at.tzinfo is None:
        msg = "record_promoted_patterns: discovered_at must be timezone-aware"
        raise ValueError(msg)
    ids: list[uuid.UUID] = []
    for p in patterns:
        pid = uuid.uuid4()
        db.execute(
            """
            INSERT INTO promoted_patterns
                (pattern_id, discovered_at, pattern_type, pattern_json,
                 promoted_count, sample_size)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(pid),
                discovered_at,
                p.pattern_type,
                json.dumps(p.pattern, sort_keys=True),
                p.promoted_count,
                p.sample_size,
            ],
        )
        ids.append(pid)
    return ids


__all__ = ["record_promoted_patterns"]
