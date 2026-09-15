"""`scripts/campaign_run.sh` is the campaign timer's ExecStart. Its one job beyond exec is the
mode switch: the phase (dry-run vs live) is an operator decision written in the unit, and any
other value is refused. These tests drive the script with a fake `uv` so nothing real runs."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "campaign_run.sh"


def _fake_uv(tmp_path: Path) -> Path:
    """A stand-in `uv` that records its argv and exits 0."""
    uv = tmp_path / "uv"
    log = tmp_path / "uv.argv"
    uv.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{log}"\nexit 0\n')
    uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
    return uv


def _fake_snapshot(tmp_path: Path) -> Path:
    """A stand-in live_db_snapshot.sh that prints a fixed path (the real one copies 9 GB)."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    snap = proj / "scripts" / "live_db_snapshot.sh"
    snap.write_text('#!/usr/bin/env bash\necho "/fake/snapshot.db"\n')
    snap.chmod(snap.stat().st_mode | stat.S_IEXEC)
    return proj


def _run(tmp_path: Path, mode: str | None) -> subprocess.CompletedProcess[str]:
    proj = _fake_snapshot(tmp_path)
    env = {
        **os.environ,
        "FORGE_PROJ": str(proj),
        "FORGE_UV": str(_fake_uv(tmp_path)),
    }
    env.pop("FORGE_CAMPAIGN_MODE", None)
    if mode is not None:
        env["FORGE_CAMPAIGN_MODE"] = mode
    return subprocess.run(
        ["bash", str(_SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def test_script_parses() -> None:
    assert subprocess.run(["bash", "-n", str(_SCRIPT)], check=False).returncode == 0


def test_dry_run_mode_uses_the_snapshot_and_submits_nothing(tmp_path: Path) -> None:
    result = _run(tmp_path, "dry-run")
    assert result.returncode == 0, result.stderr
    argv = (tmp_path / "uv.argv").read_text().split("\n")
    assert argv[:4] == ["run", "forge", "campaign", "--dry-run"]
    assert "--forge-db" in argv
    assert argv[argv.index("--forge-db") + 1] == "/fake/snapshot.db"


def test_live_mode_runs_on_the_live_db(tmp_path: Path) -> None:
    result = _run(tmp_path, "live")
    assert result.returncode == 0, result.stderr
    argv = (tmp_path / "uv.argv").read_text().split("\n")
    assert argv[:3] == ["run", "forge", "campaign"]
    assert "--dry-run" not in argv
    assert "--forge-db" not in argv


@pytest.mark.parametrize("mode", [None, "", "LIVE", "dryrun"])
def test_unknown_mode_is_refused(tmp_path: Path, mode: str | None) -> None:
    result = _run(tmp_path, mode)
    assert result.returncode == 2
    assert "FORGE_CAMPAIGN_MODE" in result.stderr
