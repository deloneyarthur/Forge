"""REL-1 gap test: a Crucible export outage must leave an explicit journal line.

WHY: `_reconcile_pending_silently` swallows `QueryError` (export missing AND the
direct-DB fallback failing) and returns `()` without printing anything. The
loop then reports only the benign-looking `blocked: prev batch N% gated`, which
is exactly how the D205/D240/D245 wedges hid for hours. The promoted-configs
loader already has the right shape (a warn-once memo naming the exception,
`main.py` `_PROMOTED_CONFIGS_LOAD_FAILED_LOGGED`); the reconciler needs the
same. Strict XFAIL until Batch 5 adds the line.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from forge.core.clock import utc_now
from forge.persistence.db import db_connection


def _insert_submitted_row(forge_db: Path) -> None:
    """A single in-flight row so the reconciler actually attempts the fetch."""
    with db_connection(forge_db) as conn:
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "deadbeefdeadbeef",
                "{}",
                utc_now().replace(tzinfo=None),
                "submitted",
            ],
        )


@pytest.mark.xfail(
    strict=True,
    reason="REL-1: _reconcile_pending_silently swallows QueryError unlogged; fixed in Batch 5",
)
def test_reconcile_export_outage_is_logged_explicitly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from forge.cli.main import _reconcile_pending_silently

    forge_db = tmp_path / "forge.db"
    _insert_submitted_row(forge_db)
    # No exports dir (isolated home) AND no Crucible DB -> the "offline" condition.
    feedbacks = _reconcile_pending_silently(forge_db, tmp_path / "does_not_exist.duckdb")
    assert feedbacks == ()

    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "QueryError" in text or "export_unreadable" in text, (
        "export outage produced no explicit journal line (only the benign `blocked` line "
        "would follow) — the D205/D240/D245 blind spot"
    )
