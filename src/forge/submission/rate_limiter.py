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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crucible_contracts import (
    GatedRun,
    get_recent_gated_runs,
    load_recent_gated_runs_from_export,
)
from crucible_contracts.exceptions import QueryError

from forge.core.clock import utc_now
from forge.feedback.consumer import STRANDED_AFTER
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
# H-1 (audit 2026-05-29): rows aged-out by D052 carry status='gated' with this
# nil-UUID sentinel `crucible_run_id` — they are NOT real Crucible decisions and
# must be excluded from the §7.3 completion count, or the sentinel flush silently
# voids the throttle (live: 91.6% of `gated` rows were sentinels). Must stay
# equal to consumer._AGED_OUT_SENTINEL_RUN_ID (guarded by a drift test).
_SENTINEL_RUN_ID = "00000000-0000-0000-0000-000000000000"
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

    Q38/D137 stall-guard fields are inert (`False`/`None`/`0`) unless a
    positive `stall_after_seconds` is passed: `stall_blocked` is the second,
    independent block reason (Crucible has held new work >= T and decided
    nothing); `last_decided_at` is Crucible's decision clock for the journal
    line; `stall_pending_count` is the number of configs caught behind it.

    D196 depth fields are inert (`False`/`0`) unless a positive `max_inflight`
    is passed: `depth_blocked` is the third, independent block reason (the
    aggregate genuine in-flight queue exceeds the cap); `inflight_depth` is that
    measured depth for the journal line.
    """

    clear: bool
    pct_gated: float
    blocking_batch_id: uuid.UUID | None
    submitted_count: int
    gated_count: int
    threshold: float = _DEFAULT_THRESHOLD
    stall_blocked: bool = False
    last_decided_at: datetime | None = None
    stall_pending_count: int = 0
    depth_blocked: bool = False
    inflight_depth: int = 0


def check_rate_limit(
    forge_db_path: Path,
    crucible_db_path: Path,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
    exports_dir: Path | None = None,
    stall_after_seconds: int = 0,
    max_inflight: int = 0,
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
    4. Clear if `(local_gated + export_overlap) / batch_size >= threshold`
       AND the stall guard (below) is not tripped.

    If the Forge DB has no `submitted` rows, `clear=True` — nothing is
    in flight. If both the export and direct-DB paths fail, the export
    contribution is 0 (the local gated count still counts) — conservative.

    Q38/D137 stall guard (`stall_after_seconds > 0`): a second, independent
    block reason for the wedge the completion fraction misses — Crucible's
    gate stops deciding while its export stays fresh-by-mtime, so the oldest
    in-flight batch reads ~100% gated (pct says "clear") while newer configs
    pile into a dead gate. The predicate (design §4) blocks iff a `submitted`
    row postdates Crucible's decision clock `max(decided_at)` by >= T. The
    "postdates the clock" clause is the deadlock guard: if the clock is stale
    only because Forge was quiet, no submission postdates it and the guard
    stays silent. Stateless — a single fresh decision clears it next poll.
    `stall_after_seconds=0` disables it (the production knob lives in
    `forge.yaml`; the function default is off to keep determinism and the
    completion-fraction contract byte-identical).
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
            SELECT config_hash, status, crucible_run_id
            FROM submissions
            WHERE forge_batch_id = ?
            """,
            [str(oldest_batch_id)],
        ).fetchall()

    submitted_count = len(rows)
    still_submitted_hashes = {str(h) for h, s, _r in rows if str(s) == "submitted"}
    # H-1: count only REAL gates. Normal reconcile (consumer.py:131) writes the
    # Crucible run id; the D052 sentinel flush (consumer.py:355) writes the nil
    # UUID. A null/sentinel run_id on a 'gated' row means "no real decision yet"
    # and must not satisfy §7.3.
    local_gated_count = sum(
        1 for _h, s, r in rows if str(s) == "gated" and r is not None and str(r) != _SENTINEL_RUN_ID
    )

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
    recent: list[GatedRun] = []
    if still_submitted_hashes:
        limit = max(submitted_count * _GATED_QUERY_LIMIT_FACTOR, _GATED_QUERY_MIN)
        try:
            # Production path: read the EXPORT_LAYOUT-published snapshot.
            recent = load_recent_gated_runs_from_export(exports_dir, limit=limit)
            if not recent:
                # No export present (or empty). Fall back to direct DuckDB for
                # tests/fixtures where no writer service is running.
                recent = get_recent_gated_runs(crucible_db_path, limit=limit)
            export_overlap = sum(1 for r in recent if r.run.config_hash in still_submitted_hashes)
        except QueryError:
            # Both paths failed; trust only the local gated count.
            export_overlap = 0
            recent = []

    # Q38/D137 stall guard: evaluate the decision-clock predicate over the
    # already-fetched export slice (no extra parse) plus one COUNT on
    # `submissions`. Inert when disabled or when no decisions are readable —
    # the latter falls through to the conservative completion-fraction path.
    stall_blocked, last_decided_at, stall_pending_count = _evaluate_stall_guard(
        forge_db_path, recent, stall_after_seconds=stall_after_seconds
    )
    # D196 — third independent block reason: bound the aggregate genuine in-flight
    # queue. The per-batch completion fraction and the stall guard both miss it.
    depth_blocked, inflight_depth = _evaluate_inflight_depth(
        forge_db_path, recent, max_inflight=max_inflight
    )

    gated_count = local_gated_count + export_overlap
    pct = gated_count / submitted_count
    clear = pct >= threshold and not stall_blocked and not depth_blocked
    return RateLimitStatus(
        clear=clear,
        pct_gated=pct,
        blocking_batch_id=None if clear else oldest_batch_id,
        submitted_count=submitted_count,
        gated_count=gated_count,
        threshold=threshold,
        stall_blocked=stall_blocked,
        last_decided_at=last_decided_at,
        stall_pending_count=stall_pending_count,
        depth_blocked=depth_blocked,
        inflight_depth=inflight_depth,
    )


def _evaluate_stall_guard(
    forge_db_path: Path,
    recent: list[GatedRun],
    *,
    stall_after_seconds: int,
) -> tuple[bool, datetime | None, int]:
    """Decision-clock staleness predicate (Q38/D137, design §4).

    Returns `(stall_blocked, last_decided_at, pending_count)`. Blocks iff a
    `submitted` row postdates Crucible's decision clock `max(decided_at)` and
    is itself at least `stall_after_seconds` old — i.e. Crucible has had new
    work in hand for >= T and decided nothing. The `submitted_at > clock`
    clause IS the deadlock guard: a clock left stale by Forge's own quiet has
    no submission postdating it, so the guard cannot block us for being idle.

    Inert (returns `(False, None, 0)`) when disabled or when the decision clock
    is unreadable (no export / empty) — the caller's pct path stays in charge.
    """
    if stall_after_seconds <= 0 or not recent:
        return (False, None, 0)
    # Crucible's decision clock = newest decision in the fetched slice. D061:
    # normalize to aware UTC (export rows may be naive) for the max, then strip
    # to naive UTC to match the `submitted_at` column convention.
    decided_ats: list[datetime] = []
    for gr in recent:
        d = gr.decision.decided_at
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        decided_ats.append(d)
    last_decided_at = max(decided_ats)
    max_decided_naive = last_decided_at.astimezone(UTC).replace(tzinfo=None)
    cutoff_naive = (
        (utc_now() - timedelta(seconds=stall_after_seconds)).astimezone(UTC).replace(tzinfo=None)
    )
    with db_connection(forge_db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM submissions
            WHERE status = 'submitted'
              AND submitted_at > ?
              AND submitted_at <= ?
            """,
            [max_decided_naive, cutoff_naive],
        ).fetchone()
    pending = int(row[0]) if row is not None else 0
    return (pending > 0, last_decided_at, pending)


def _evaluate_inflight_depth(
    forge_db_path: Path,
    recent: list[GatedRun],
    *,
    max_inflight: int,
) -> tuple[bool, int]:
    """Aggregate in-flight-depth block (D196, throttle-proposal Tier 2).

    A third, independent block reason for what the per-batch completion fraction
    and the stall guard both miss: the TOTAL learnable queue. Genuine in-flight
    depth = `submitted` rows newer than the D052/D110 flush watermark
    (`max(decided_at) - STRANDED_AFTER`); rows older than that are the dead tail
    the flush retires, so they are excluded — else the orphan backlog would pin
    the depth block exactly as it pinned D046's oldest-batch limiter (the very
    failure this fixes). Blocks iff depth > `max_inflight`.

    Inert (`(False, 0)`) when disabled (`max_inflight <= 0`) or when the decision
    clock is unreadable (no export / empty): without a clock the watermark is
    undefined, so genuine depth can't be separated from the dead tail and we fall
    through to the completion-fraction path. `max_inflight=0` keeps the result
    byte-identical to the pre-D196 contract.
    """
    if max_inflight <= 0 or not recent:
        return (False, 0)
    # Decision clock = newest decision in the fetched slice (D061: normalize naive
    # export rows to aware UTC for the max, then strip to naive UTC to match the
    # `submitted_at` column). Watermark mirrors consumer._flush_aged_out_submissions
    # exactly, so depth counts precisely the rows the flush leaves behind.
    decided_ats: list[datetime] = []
    for gr in recent:
        d = gr.decision.decided_at
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        decided_ats.append(d)
    watermark = (max(decided_ats) - STRANDED_AFTER).astimezone(UTC).replace(tzinfo=None)
    with db_connection(forge_db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM submissions
            WHERE status = 'submitted'
              AND submitted_at >= ?
            """,
            [watermark],
        ).fetchone()
    depth = int(row[0]) if row is not None else 0
    return (depth > max_inflight, depth)


__all__ = ["RateLimitStatus", "check_rate_limit"]
