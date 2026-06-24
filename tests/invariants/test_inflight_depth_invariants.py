"""§7.3 aggregate in-flight-depth block invariants (D196, throttle-proposal Tier 2).

The completion-fraction check (§7.3) and the D137 stall guard both look at a single
batch; neither bounds the AGGREGATE in-flight queue. A zombie batch (permanently >=80%
gated with a residue of never-decided stragglers that aged out of Crucible's export
window) pins the oldest-batch throttle while tens of thousands of configs accumulate
across other batches. The depth block is a third, independent block reason that bounds
genuine in-flight depth directly.

Load-bearing properties:
  (a) Guard-off equivalence — `max_inflight=0` reproduces the pre-feature behaviour
      exactly: the depth fields are inert and `clear` is the completion fraction.
  (b) Block iff over cap — `depth_blocked` is true exactly when genuine in-flight depth
      exceeds the cap, where genuine depth excludes the flushable dead tail.
  (c) Stranded-tail exclusion — rows older than `max(decided_at) - STRANDED_AFTER`
      (the D110 flush watermark) do not count toward depth, so the orphan backlog the
      flush will retire cannot itself trigger or mask the block.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.feedback.consumer import STRANDED_AFTER
from forge.persistence.db import db_connection
from forge.submission import rate_limiter
from forge.submission.rate_limiter import check_rate_limit
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

_NOW = datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _insert_submission(
    forge_db: Path,
    *,
    config_hash: str,
    submitted_at: datetime,
    status: str = "submitted",
    batch_id: uuid.UUID | None = None,
) -> None:
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status, crucible_run_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                str(batch_id or uuid.uuid4()),
                config_hash,
                "{}",
                submitted_at,
                status,
                str(uuid.uuid4()) if status == "gated" else None,
            ],
        )


def _insert_decision(crucible_db: Path, *, config_hash: str, decided_at: datetime) -> None:
    naive = decided_at.astimezone(UTC).replace(tzinfo=None)
    conn = build_synthetic_crucible_db(crucible_db)
    try:
        run_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO runs (run_id, config_hash, source, status, period_start, "
            "period_end, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                config_hash,
                "forge",
                "gated",
                datetime(2026, 1, 1, tzinfo=UTC).date(),
                datetime(2026, 5, 1, tzinfo=UTC).date(),
                naive - timedelta(hours=1),
                naive,
            ],
        )
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [run_id, "reject", "{}", naive, "tester"],
        )
    finally:
        conn.close()


# minutes-ago for submitted rows; the clock is one decision at _NOW.
_subs = st.lists(
    st.tuples(
        st.integers(min_value=1, max_value=20_000),  # minutes ago (spans past the watermark)
        st.sampled_from(["submitted", "gated"]),
    ),
    min_size=0,
    max_size=8,
)


@given(sub_specs=_subs, cap=st.integers(min_value=1, max_value=8))
@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_depth_blocks_iff_over_cap(
    sub_specs: list[tuple[int, str]], cap: int, tmp_path: Path, monkeypatch: object
) -> None:
    """`depth_blocked` iff genuine depth (submitted rows newer than the flush
    watermark) exceeds the cap. Property (b) + (c): the watermark excludes the
    flushable tail, so only recent-enough `submitted` rows count."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    # One decision at _NOW → clock = _NOW, watermark = _NOW - STRANDED_AFTER.
    _insert_decision(crucible_db, config_hash="clock", decided_at=_NOW)
    for i, (mins, status) in enumerate(sub_specs):
        _insert_submission(
            forge_db,
            config_hash=f"s_{i}",
            submitted_at=_NOW - timedelta(minutes=mins),
            status=status,
        )

    watermark = _NOW - STRANDED_AFTER
    expected_depth = sum(
        1
        for mins, status in sub_specs
        if status == "submitted" and (_NOW - timedelta(minutes=mins)) >= watermark
    )

    status = check_rate_limit(
        forge_db,
        crucible_db,
        max_inflight=cap,
        exports_dir=workspace / "noexports",
    )
    assert status.inflight_depth == expected_depth
    assert status.depth_blocked is (expected_depth > cap)


def test_stranded_tail_excluded_from_depth(tmp_path: Path, monkeypatch: object) -> None:
    """Rows older than the flush watermark are the dead tail the D052/D110 flush
    retires; they must not count toward genuine in-flight depth (else the orphan
    backlog would pin the depth block exactly as it pins the oldest-batch one)."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    _insert_decision(crucible_db, config_hash="clock", decided_at=_NOW)
    # 2 genuinely in-flight (just submitted) + 50 dead-tail rows well past the
    # watermark. Cap=10: only the 2 genuine count, so it must NOT block.
    for i in range(2):
        _insert_submission(
            forge_db, config_hash=f"fresh_{i}", submitted_at=_NOW - timedelta(hours=1)
        )
    for i in range(50):
        _insert_submission(
            forge_db,
            config_hash=f"dead_{i}",
            submitted_at=_NOW - STRANDED_AFTER - timedelta(days=3),
        )

    status = check_rate_limit(
        forge_db, crucible_db, max_inflight=10, exports_dir=workspace / "noexports"
    )
    assert status.inflight_depth == 2
    assert status.depth_blocked is False


def test_zombie_batch_pct_clears_but_depth_blocks(tmp_path: Path, monkeypatch: object) -> None:
    """The proposal's core scenario: the oldest batch reads >=threshold gated (pct
    says CLEAR) yet the aggregate in-flight queue is deep. The depth block fires
    where the per-batch completion fraction structurally cannot."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    _insert_decision(crucible_db, config_hash="clock", decided_at=_NOW)

    # Oldest batch: 4 gated + 1 submitted = 80% gated → pct clears at threshold 0.80.
    oldest = uuid.uuid4()
    for i in range(4):
        _insert_submission(
            forge_db,
            config_hash=f"old_g_{i}",
            submitted_at=_NOW - timedelta(hours=2),
            status="gated",
            batch_id=oldest,
        )
    _insert_submission(
        forge_db,
        config_hash="old_s",
        submitted_at=_NOW - timedelta(hours=2),
        status="submitted",
        batch_id=oldest,
    )
    # A deep, newer in-flight backlog across another batch (the queue pct can't see).
    newer = uuid.uuid4()
    for i in range(10):
        _insert_submission(
            forge_db,
            config_hash=f"new_s_{i}",
            submitted_at=_NOW - timedelta(minutes=30),
            status="submitted",
            batch_id=newer,
        )

    status = check_rate_limit(
        forge_db,
        crucible_db,
        threshold=0.80,
        max_inflight=5,
        exports_dir=workspace / "noexports",
    )
    assert status.pct_gated >= 0.80  # the per-batch fraction says "clear"
    assert status.inflight_depth == 11  # 1 (oldest) + 10 (newer), all in-margin
    assert status.depth_blocked is True
    assert status.clear is False  # ...but the aggregate depth blocks


@given(sub_specs=_subs, threshold=st.sampled_from([0.5, 0.8, 1.0]))
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_guard_off_equivalence(
    sub_specs: list[tuple[int, str]], threshold: float, tmp_path: Path, monkeypatch: object
) -> None:
    """`max_inflight=0` (and absent) reproduces the pre-feature contract: depth
    fields inert, `clear` is purely the completion fraction (stall guard also off)."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    _insert_decision(crucible_db, config_hash="clock", decided_at=_NOW)
    for i, (mins, status) in enumerate(sub_specs):
        _insert_submission(
            forge_db,
            config_hash=f"s_{i}",
            submitted_at=_NOW - timedelta(minutes=mins),
            status=status,
        )

    off = check_rate_limit(
        forge_db,
        crucible_db,
        threshold=threshold,
        max_inflight=0,
        exports_dir=workspace / "noexports",
    )
    assert off.depth_blocked is False
    assert off.inflight_depth == 0
    assert off.clear is (off.pct_gated >= threshold)
