"""REL-4 gap test: `forge run` must convert SIGTERM into the clean-stop path.

WHY: systemd stops the daemon with SIGTERM. `cmd_run` handles only
`KeyboardInterrupt` (SIGINT), and the submitter's rollback-on-`BaseException`
guard (`submitter.py`, M-10) only fires when the interrupt arrives as a Python
exception. A raw SIGTERM kills the process between `submit_candidate` (inbox
file written) and `COMMIT` — an inbox file with no committed row (the July
reliability audit's REL-4 tear). Until a handler exists this test XFAILs
strictly; when Batch 5 installs one it flips loud and the marker comes off.
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
    reason="REL-4: cmd_run installs no SIGTERM handler; fixed in Batch 5 (plan 2026-09 §6)",
)
def test_run_installs_sigterm_handler_that_raises_keyboard_interrupt(tmp_path: Path) -> None:
    """After `forge run` starts, SIGTERM must route through the SIGINT path so the
    submitter's transaction guard sees an exception, not a process death."""
    before = signal.getsignal(signal.SIGTERM)
    try:
        result = runner.invoke(
            app,
            [
                "run",
                "--no-config",
                "--seed",
                "0",
                "--batch-size",
                "2",
                "--max",
                "20",
                "--dry-run",
                "--forge-db",
                str(tmp_path / "forge.db"),
                "--inbox",
                str(tmp_path / "inbox"),
            ],
        )
        assert result.exit_code == 0, result.stdout
        handler = signal.getsignal(signal.SIGTERM)
        assert handler not in (signal.SIG_DFL, signal.SIG_IGN, None), (
            "SIGTERM still has the default disposition after `forge run`"
        )
        assert callable(handler)
        with pytest.raises(KeyboardInterrupt):
            handler(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGTERM, before)
