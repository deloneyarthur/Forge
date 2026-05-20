"""§7.3 in-flight rate limiter — clear-to-submit check for `forge run`.

The rate limiter answers a single question: may the next batch submit?
Per §7.3 Forge waits until >=threshold of the in-flight batch's candidates
are gated in Crucible before queuing a new one. This keeps the inbox
from growing into a queue Forge can't learn from.

D023/D6.a — Phase 4 ships the check function. The 10-minute poll loop
is Phase 5/6 daemon work; `forge run` calls this once and either
proceeds or exits with a "waiting" message.

D036 (2026-05-17) — threshold dropped 0.80 → 0.50 tactically while we
wait for D033 Tier-2 throughput to stabilize. See IMPLEMENTATION_DECISIONS.

D046 (2026-05-18) — pick the OLDEST batch with `submitted` rows as the
blocker, not the LATEST. The latest-batch heuristic was correct when
Crucible processed a batch within one Forge poll cycle; once latency
exceeded that, Forge always blocked on the newest batch (which Crucible
hadn't yet reached) while older batches accumulated unread gate results.
By 2026-05-17 the system had 11 stranded batches and 3,712 un-reconciled
candidates. Oldest-batch semantics make the blocker the actual front of
Crucible's queue, and the natural drain order matches.

A missing Crucible DB is treated as "0% gated" — conservative: if we
can't prove the prior batch finished, we stay blocked. The cost of a
false-block is a "waiting" message; the cost of a false-clear is
flooding the inbox.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from crucible_contracts import (
    get_recent_gated_runs,
    load_recent_gated_runs_from_export,
)
from crucible_contracts.exceptions import QueryError

from forge.persistence.db import db_connection

# D036 (2026-05-17) — tactical drop from 0.80 → 0.50 while we wait for the
# Tier 2 (D033) batch to actually ship. The pre-D033 batch 550e24a2 was
# gating at ~80 min/run (vs prior 17-27 min); at the 0.80 threshold, the
# first D033 batch ETA was Tuesday morning. We're already past 50% gated,
# so dropping to 0.5 unblocks immediately and lets D033 actually exercise.
# Revisit once D033 ships its first batch and we see real Tier 2 throughput —
# the 0.80 default was sized for v1 / SPY-only, may or may not still fit.
#
# D070 (2026-05-19) — restored to 0.80. Post-D069 (param-aware fingerprint)
# Forge is producing 200 ranked submissions per ~7-min iter = ~1,600
# configs/hour, while Crucible's gauntlet (post-vectorization, with 4
# parallel CPCV workers per config) processes ~24 configs/hour. The 67x
# submission-vs-gauntlet mismatch fills Crucible's inbox faster than it
# can drain; the 0.80 threshold is the §7.3 design-time safeguard for
# exactly this situation. See IMPLEMENTATION_DECISIONS.md D070.
_DEFAULT_THRESHOLD = 0.80
# Pull a generous slice of recent gated runs; the cross-reference is
# bounded by `submitted_count`, so the limit only needs to exceed the
# typical batch size (200 per §6.4) with headroom for parallelism.
_GATED_QUERY_LIMIT_FACTOR = 4
_GATED_QUERY_MIN = 1000

# Default exports dir resolved at call time (not module-load) so tests can
# monkeypatch `Path.home()` without the import side-effect locking in the
# operator's real home directory.


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
    threshold: float = _DEFAULT_THRESHOLD


def check_rate_limit(
    forge_db_path: Path,
    crucible_db_path: Path,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
    exports_dir: Path | None = None,
) -> RateLimitStatus:
    """Return whether a new batch may submit.

    Steps:
    1. Find the OLDEST `forge_batch_id` with `status='submitted'` rows
       (D046: was "latest batch" — that locked the loop once Crucible
       processing exceeded one poll cycle).
    2. Collect that batch's `config_hash`es plus the count already gated
       in Forge's local DB.
    3. Query Crucible's gated runs and intersect with any still-submitted
       hashes. Production path reads `EXPORT_LAYOUT`-published
       `gated_runs_*.json` (contracts v1.8.0+); Crucible's db_writer
       holds an exclusive file lock so direct read-only DuckDB opens
       fail. Falls back to `get_recent_gated_runs` (direct DuckDB) for
       test fixtures where no exports dir exists.
    4. Clear if `(local_gated + export_overlap) / batch_size >= threshold`.

    If the Forge DB has no `submitted` rows, `clear=True` — nothing is
    in flight. If both the export and direct-DB paths fail, the export
    contribution is 0 (the local gated count still counts) — conservative.
    """
    if exports_dir is None:
        exports_dir = Path.home() / "optbt_data" / "exports"
    with db_connection(forge_db_path) as conn:
        # D046: pick the oldest batch with any still-`submitted` rows.
        # That's the actual queue front; the latest batch is the back.
        oldest = conn.execute(
            """
            SELECT forge_batch_id
            FROM submissions
            WHERE status = 'submitted'
            GROUP BY forge_batch_id
            ORDER BY MIN(submitted_at) ASC
            LIMIT 1
            """,
        ).fetchone()
        if oldest is None:
            # No `submitted` rows anywhere — either first run or everything
            # has been reconciled to `gated`. Clear.
            return RateLimitStatus(
                clear=True,
                pct_gated=1.0,
                blocking_batch_id=None,
                submitted_count=0,
                gated_count=0,
            )
        oldest_batch_id = uuid.UUID(str(oldest[0]))
        rows = conn.execute(
            """
            SELECT config_hash, status
            FROM submissions
            WHERE forge_batch_id = ?
            """,
            [str(oldest_batch_id)],
        ).fetchall()

    submitted_count = len(rows)
    still_submitted_hashes = {str(h) for h, s in rows if str(s) == "submitted"}
    local_gated_count = sum(1 for _h, s in rows if str(s) == "gated")

    if submitted_count == 0:
        # The batch row exists but has no candidates. Treat as clear.
        return RateLimitStatus(
            clear=True,
            pct_gated=1.0,
            blocking_batch_id=None,
            submitted_count=0,
            gated_count=0,
            threshold=threshold,
        )

    export_overlap = 0
    if still_submitted_hashes:
        limit = max(submitted_count * _GATED_QUERY_LIMIT_FACTOR, _GATED_QUERY_MIN)
        try:
            # Production path: read the EXPORT_LAYOUT-published snapshot.
            recent = load_recent_gated_runs_from_export(exports_dir, limit=limit)
            if not recent:
                # No export present (or empty). Fall back to direct DuckDB for
                # tests/fixtures where no writer service is running.
                recent = get_recent_gated_runs(crucible_db_path, limit=limit)
            export_overlap = sum(
                1 for r in recent if r.run.config_hash in still_submitted_hashes
            )
        except QueryError:
            # Both paths failed; trust only the local gated count.
            export_overlap = 0

    gated_count = local_gated_count + export_overlap
    pct = gated_count / submitted_count
    return RateLimitStatus(
        clear=pct >= threshold,
        pct_gated=pct,
        blocking_batch_id=None if pct >= threshold else oldest_batch_id,
        submitted_count=submitted_count,
        gated_count=gated_count,
        threshold=threshold,
    )


__all__ = ["RateLimitStatus", "check_rate_limit"]
