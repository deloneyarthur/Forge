"""REL-2 gap test: the rate limiter must signal an export outage, not just block.

WHY: `check_rate_limit` catches `QueryError` from both the export and the
direct-DB path and silently sets `export_overlap = 0`. The caller cannot tell
"Crucible has not gated the batch yet" from "we cannot read Crucible at all";
both render as the same `blocked` line. The conservative block is correct and
already tested (`test_rate_limiter.py`, missing-Crucible case); what is missing
is the explicit signal. Either an attribute on `RateLimitStatus` or a WARNING
log record satisfies this test. Strict XFAIL until Batch 5.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import pytest

from forge.core.clock import utc_now
from forge.submission.rate_limiter import check_rate_limit
from tests.unit.test_submission.test_rate_limiter import _insert_submission


@pytest.mark.xfail(
    strict=True,
    reason="REL-2: check_rate_limit swallows QueryError without a signal; fixed in Batch 5",
)
def test_rate_limit_signals_export_outage_explicitly(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    forge_db = tmp_path / "forge.db"
    _insert_submission(
        forge_db,
        forge_batch_id=uuid.uuid4(),
        config_hash="hash1",
        submitted_at=utc_now().replace(tzinfo=None),
    )
    with caplog.at_level(logging.WARNING):
        status = check_rate_limit(
            forge_db, tmp_path / "does_not_exist.duckdb", exports_dir=tmp_path / "noexports"
        )
    assert status.clear is False  # the existing conservative behaviour, unchanged

    logged = any(
        record.levelno >= logging.WARNING
        and ("QueryError" in record.getMessage() or "export" in record.getMessage().lower())
        for record in caplog.records
    )
    flagged = bool(getattr(status, "crucible_unreachable", False))
    assert logged or flagged, "export outage is indistinguishable from a not-yet-gated batch"
