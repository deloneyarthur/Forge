"""REL-4 (July reliability audit): systemd stops a unit with SIGTERM. `submitter.py` writes the
inbox file inside the DB transaction, so a SIGTERM between the inbox write and the commit leaves an
inbox file with no `submissions` row. The fix is a SIGTERM handler that raises `KeyboardInterrupt`
so the transaction guard sees an exception, not a process death. Known bug, pinned as a strict
xfail so the suite stays green and flips LOUD when Batch 5 G6 lands the handler.

Re-targeted from `forge run` (deleted, Batch 5 G1) to the weekly `forge campaign` oneshot.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli.main import app

runner = CliRunner()


@pytest.mark.xfail(
    strict=True,
    reason="REL-4: forge campaign installs no SIGTERM handler; fixed in Batch 5 G6 (plan §13)",
)
def test_campaign_installs_sigterm_handler_raising_keyboard_interrupt(tmp_path: Path) -> None:
    """The handler must be installed before boot, so an early boot failure (empty exports dir,
    exit 2) is enough to observe it."""
    before = signal.getsignal(signal.SIGTERM)
    try:
        exports = tmp_path / "exports"
        exports.mkdir()
        runner.invoke(
            app,
            [
                "campaign",
                "--dry-run",
                "--skip-train",
                "--no-config",
                "--exports-dir",
                str(exports),
                "--forge-db",
                str(tmp_path / "forge.db"),
                "--inbox",
                str(tmp_path / "inbox"),
                "--records-dir",
                str(tmp_path / "campaigns"),
            ],
        )
        handler = signal.getsignal(signal.SIGTERM)
        assert handler not in (signal.SIG_DFL, signal.SIG_IGN, None), (
            "SIGTERM still has the default disposition after `forge campaign`"
        )
        assert callable(handler)
        with pytest.raises(KeyboardInterrupt):
            handler(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGTERM, before)
