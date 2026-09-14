"""`forge campaign` is the operator's only handle on the weekly run, so its help and its
exit codes (0 ok / no trigger, 2 boot failed, 1 error) are the paging contract for the
systemd unit — pinned here through the real Typer app."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app

runner = CliRunner()


def test_help_lists_the_run_options_and_status() -> None:
    result = runner.invoke(app, ["campaign", "--help"])
    assert result.exit_code == 0, result.output
    assert "--dry-run" in result.output
    assert "status" in result.output
    assert runner.invoke(app, ["campaign", "status", "--help"]).exit_code == 0


def test_status_with_no_records_is_a_clean_zero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["campaign", "status", "--records-dir", str(tmp_path / "none")])
    assert result.exit_code == 0, result.output
    assert "no campaign runs recorded yet" in result.output


def test_boot_failure_exits_2_and_leaves_a_record(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    records = tmp_path / "campaigns"
    result = runner.invoke(
        app,
        [
            "campaign",
            "--dry-run",
            "--no-config",
            "--exports-dir",
            str(exports),
            "--records-dir",
            str(records),
            "--forge-db",
            str(tmp_path / "forge.db"),
            "--inbox",
            str(tmp_path / "inbox"),
        ],
    )
    assert result.exit_code == 2, result.output
    assert "BOOT FAILED" in result.output
    assert "registry" in result.output
    assert list(records.glob("*.json"))
    assert not (tmp_path / "inbox").exists()
