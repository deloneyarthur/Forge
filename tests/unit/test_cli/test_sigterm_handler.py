"""REL-4 (July reliability audit; fixed Batch 5 G6): systemd stops the `forge-campaign` oneshot
with SIGTERM. `submitter.py` writes the inbox file inside the DB transaction, so a raw SIGTERM
between the inbox write and the commit would leave an inbox file with no `submissions` row.

The fix is a handler that sets a stop flag instead of raising: `submit_batch` checks the flag
BETWEEN candidates, the in-flight candidate finishes its write + commit, and the run records
`status: error` and exits non-zero. A SECOND SIGTERM (flag already set) raises
`KeyboardInterrupt` — the operator's deliberate hard stop, mirroring SIGINT.

Re-targeted from `forge run` (deleted, Batch 5 G1) to the weekly `forge campaign` oneshot.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import forge.campaign.run as run_mod
from forge.campaign import stop
from forge.cli.main import app

runner = CliRunner()


def test_campaign_installs_a_stop_flag_handler_for_the_run_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """During the run SIGTERM is bound to the stop-flag handler; after it the previous
    disposition is restored (tests share one process). The boot step is the spy point: the
    handler must already be live before boot, so an early boot failure (empty exports dir,
    exit 2) is enough to observe it."""
    before = signal.getsignal(signal.SIGTERM)
    captured: dict[str, object] = {}
    real_boot = run_mod.boot

    def spy(**kwargs: object) -> object:
        captured["handler"] = signal.getsignal(signal.SIGTERM)
        return real_boot(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(run_mod, "boot", spy)
    exports = tmp_path / "exports"
    exports.mkdir()
    result = runner.invoke(
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
    assert result.exit_code == 2  # boot failed: no exports
    handler = captured["handler"]
    assert handler not in (signal.SIG_DFL, signal.SIG_IGN, None)
    assert callable(handler)
    assert signal.getsignal(signal.SIGTERM) is before, "handler not restored after the run"


def test_handler_sets_the_flag_then_hard_stops_on_a_second_signal() -> None:
    stop.reset_stop()
    try:
        assert stop.stop_requested() is False
        stop.sigterm_handler(signal.SIGTERM, None)
        assert stop.stop_requested() is True
        with pytest.raises(KeyboardInterrupt):
            stop.sigterm_handler(signal.SIGTERM, None)
    finally:
        stop.reset_stop()


def test_guard_restores_the_previous_handler_and_clears_the_flag() -> None:
    before = signal.getsignal(signal.SIGTERM)
    with stop.sigterm_guard():
        assert signal.getsignal(signal.SIGTERM) is stop.sigterm_handler
        stop.request_stop()
        assert stop.stop_requested() is True
    assert signal.getsignal(signal.SIGTERM) is before
    assert stop.stop_requested() is False
