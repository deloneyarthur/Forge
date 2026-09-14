"""Behaviour tests for `scripts/live_db_snapshot.sh` — the blessed read-only snapshot.

WHY: the 06:30 `forge-prereg-watch` timer's `ExecStart` depends on this script,
and every investigation ritual does too, yet nothing exercised it. Its three
promises — refuse RAM-backed dirs (the 62 GB tmpfs incident), reuse a fresh
snapshot, clean up on request — are each a one-line regression waiting to happen.
The script is driven via subprocess with its env knobs so the live
`~/forge_data` is never touched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from forge.persistence.db import db_connection

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "live_db_snapshot.sh"


def _fstype(path: Path) -> str:
    out = subprocess.run(
        ["stat", "-f", "-c", "%T", str(path)], capture_output=True, text=True, check=False
    )
    return out.stdout.strip()


def _run(live_db: Path, snap_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ | {
        "FORGE_LIVE_DB": str(live_db),
        "FORGE_SNAPSHOT_DIR": str(snap_dir),
    }
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
    )


@pytest.fixture
def live_db(tmp_path: Path) -> Path:
    db = tmp_path / "forge.db"
    with db_connection(db):
        pass  # schema applied; an empty but valid Forge DB
    return db


@pytest.fixture
def real_disk_dir() -> Iterator[Path]:
    """A directory on real disk (`.pytest_cache/` is gitignored and lives on the repo
    filesystem); pytest's `tmp_path` is on tmpfs on the production box."""
    base = REPO_ROOT / ".pytest_cache"
    base.mkdir(exist_ok=True)
    if _fstype(base) in {"tmpfs", "ramfs"}:
        pytest.skip("no real-disk scratch directory available on this host")
    path = Path(tempfile.mkdtemp(prefix="snapshot_test_", dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_refuses_a_ram_backed_snapshot_dir(live_db: Path, tmp_path: Path) -> None:
    snap_dir = tmp_path / "snap"
    if _fstype(tmp_path) not in {"tmpfs", "ramfs"}:
        pytest.skip("tmp_path is not RAM-backed on this host; refusal path not exercisable")
    result = _run(live_db, snap_dir)
    assert result.returncode == 1
    assert "REFUSING" in result.stderr
    assert not (snap_dir / "forge_live.db").exists()


def test_missing_live_db_is_a_clean_failure(tmp_path: Path, real_disk_dir: Path) -> None:
    result = _run(tmp_path / "absent.db", real_disk_dir)
    assert result.returncode == 1
    assert "live DB not found" in result.stderr


def test_snapshot_reuse_force_and_clean(live_db: Path, real_disk_dir: Path) -> None:
    first = _run(live_db, real_disk_dir)
    assert first.returncode == 0, first.stderr
    snap = Path(first.stdout.strip())
    assert snap == real_disk_dir / "forge_live.db"
    assert snap.is_file()
    assert "snapshot refreshed" in first.stderr
    # The copy is a readable Forge DB (the whole reason the snapshot exists).
    con = duckdb.connect(str(snap), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM submissions").fetchone() == (0,)
    finally:
        con.close()

    second = _run(live_db, real_disk_dir)
    assert second.returncode == 0
    assert second.stdout.strip() == str(snap)
    assert "reusing snapshot" in second.stderr

    forced = _run(live_db, real_disk_dir, "--force")
    assert forced.returncode == 0
    assert "snapshot refreshed" in forced.stderr

    cleaned = _run(live_db, real_disk_dir, "--clean")
    assert cleaned.returncode == 0
    assert not snap.exists()
