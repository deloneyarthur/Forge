"""REL-4 (Batch 5 G6): a stop request must be honoured BETWEEN candidates, never mid-candidate.

`_submit_one` writes the inbox file inside the DB transaction; a stop that fires while a
candidate is in flight must still let that candidate's write + commit finish, and the next
candidate must not start. The observable contract: exactly one inbox file, and it matches the
one committed `submissions` row."""

from __future__ import annotations

from pathlib import Path

from forge.persistence.db import db_connection
from forge.submission.submitter import submit_batch
from tests.unit.test_submission.test_submitter import _candidate, _ctx


def test_stop_between_candidates_leaves_inbox_and_rows_consistent(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"), _candidate("c", "dir_c"))
    seen: list[int] = []

    def should_stop() -> bool:
        # False before the first candidate, True from the second check on: the stop
        # "arrives" while candidate a is in flight and is honoured before b starts.
        seen.append(1)
        return len(seen) > 1

    with db_connection(forge_db) as conn:
        result = submit_batch(
            conn, batch=_ctx(), candidates=cands, inbox_root=inbox, should_stop=should_stop
        )
        rows = conn.execute(
            "SELECT config_hash, status FROM submissions ORDER BY config_hash"
        ).fetchall()
    assert result.submitted_count == 1
    assert result.stopped_early is True
    assert result.remaining_count == 2
    inbox_files = sorted(p.stem for p in inbox.glob("*.json"))
    assert len(inbox_files) == 1
    assert [(str(r[0]), str(r[1])) for r in rows] == [(inbox_files[0], "submitted")]


def test_no_stop_request_submits_everything(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"))
    with db_connection(forge_db) as conn:
        result = submit_batch(
            conn, batch=_ctx(), candidates=cands, inbox_root=inbox, should_stop=lambda: False
        )
    assert result.submitted_count == 2
    assert result.stopped_early is False
    assert result.remaining_count == 0
