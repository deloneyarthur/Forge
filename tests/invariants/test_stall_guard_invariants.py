"""§7.3 stall-guard invariants (Q38 / D137).

Three load-bearing properties of the decision-clock predicate (design §4, §7):

  (a) Deadlock immunity — `stall_blocked` iff a genuine witness exists (a
      'submitted' row that postdates Crucible's last decision by >= T). The
      guard can never block a state where Crucible has no undecided work older
      than T, so Forge being quiet can never deadlock itself.
  (b) Stateless recovery — appending ONE fresh decision clears any blocked
      state on the next check. The predicate has no memory; it cannot latch
      (the D110 lesson, made structural).
  (c) Guard-off equivalence — `stall_after_seconds=0` reproduces the
      pre-feature behaviour exactly: pure completion-fraction, no stall fields.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.persistence.db import db_connection
from forge.submission import rate_limiter
from forge.submission.rate_limiter import check_rate_limit
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_T_SECONDS = 10800  # 3 h


def _insert_submission(
    forge_db: Path, *, config_hash: str, submitted_at: datetime, status: str = "submitted"
) -> None:
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status, crucible_run_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                config_hash,
                "{}",
                submitted_at,
                status,
                str(uuid.uuid4()) if status == "gated" else None,
            ],
        )


def _insert_decision(crucible_db: Path, *, config_hash: str, decided_at: datetime) -> None:
    # Store naive-UTC: the synthetic crucible DB is not UTC-session-pinned, so
    # the round-trip through `get_recent_gated_runs` is only identity for naive
    # values (relabelled UTC on read). See the unit-test helper for the rationale.
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
            [run_id, "reject", json.dumps({}), naive, "tester"],
        )
    finally:
        conn.close()


# Minute-offsets-ago, kept whole to avoid sub-second storage skew at the
# boundary comparisons. At least one decision so the clock exists.
_decisions = st.lists(st.integers(min_value=1, max_value=2880), min_size=1, max_size=5)
_subs = st.lists(
    st.tuples(
        st.integers(min_value=1, max_value=2880),  # minutes ago
        st.sampled_from(["submitted", "gated"]),
    ),
    min_size=0,
    max_size=6,
)


@given(decision_mins=_decisions, sub_specs=_subs)
@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_deadlock_immunity_block_iff_witness(
    decision_mins: list[int],
    sub_specs: list[tuple[int, str]],
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """`stall_blocked` is true exactly when a real witness row exists.

    Corollary (the deadlock guard): if every 'submitted' row predates the last
    decision, no witness exists → the guard stays silent even with an arbitrarily
    stale clock. Forge's own quiet can never block Forge.
    """
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    for i, m in enumerate(decision_mins):
        _insert_decision(crucible_db, config_hash=f"d_{i}", decided_at=_NOW - timedelta(minutes=m))
    for i, (m, status) in enumerate(sub_specs):
        _insert_submission(
            forge_db, config_hash=f"s_{i}", submitted_at=_NOW - timedelta(minutes=m), status=status
        )

    max_decided = _NOW - timedelta(minutes=min(decision_mins))
    cutoff = _NOW - timedelta(seconds=_T_SECONDS)
    witness_exists = any(
        status == "submitted"
        and (_NOW - timedelta(minutes=m)) > max_decided
        and (_NOW - timedelta(minutes=m)) <= cutoff
        for m, status in sub_specs
    )

    status = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=workspace / "noexports"
    )
    assert status.stall_blocked is witness_exists


@given(stale_mins=st.integers(min_value=200, max_value=2880))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_stateless_recovery_one_decision_clears(
    stale_mins: int, tmp_path: Path, monkeypatch: object
) -> None:
    """A blocked state clears the moment a single fresh decision lands — no
    counter, no hysteresis, nothing to reset."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    _insert_decision(
        crucible_db, config_hash="old", decided_at=_NOW - timedelta(minutes=stale_mins)
    )
    # A witness: postdates the clock (offset < stale_mins) AND older than
    # T=180 min. stale_mins >= 200 ⇒ (stale_mins - 10) is in (180, stale_mins).
    _insert_submission(
        forge_db, config_hash="pending", submitted_at=_NOW - timedelta(minutes=stale_mins - 10)
    )
    blocked = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=workspace / "noexports"
    )
    assert blocked.stall_blocked is True

    # One fresh decision now → advances the clock past every witness.
    _insert_decision(crucible_db, config_hash="fresh", decided_at=_NOW)
    recovered = check_rate_limit(
        forge_db, crucible_db, stall_after_seconds=_T_SECONDS, exports_dir=workspace / "noexports"
    )
    assert recovered.stall_blocked is False


@given(
    decision_mins=_decisions,
    sub_specs=_subs,
    threshold=st.sampled_from([0.5, 0.8, 1.0]),
)
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_guard_off_equivalence(
    decision_mins: list[int],
    sub_specs: list[tuple[int, str]],
    threshold: float,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """With the guard disabled, `clear` is purely the completion fraction and
    the stall fields are inert — byte-for-byte the pre-feature contract."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir()
    forge_db = workspace / "forge.db"
    crucible_db = workspace / "crucible.duckdb"
    build_synthetic_crucible_db(crucible_db).close()
    monkeypatch.setattr(rate_limiter, "utc_now", lambda: _NOW)  # type: ignore[attr-defined]

    for i, m in enumerate(decision_mins):
        _insert_decision(crucible_db, config_hash=f"d_{i}", decided_at=_NOW - timedelta(minutes=m))
    for i, (m, status) in enumerate(sub_specs):
        _insert_submission(
            forge_db, config_hash=f"s_{i}", submitted_at=_NOW - timedelta(minutes=m), status=status
        )

    off = check_rate_limit(
        forge_db,
        crucible_db,
        threshold=threshold,
        stall_after_seconds=0,
        exports_dir=workspace / "noexports",
    )
    assert off.stall_blocked is False
    assert off.last_decided_at is None
    assert off.stall_pending_count == 0
    # clear is exactly the completion-fraction verdict.
    assert off.clear is (off.pct_gated >= threshold)
