"""Integration tests for scripts/backup_forge_db.sh (DR backup of forge.db + models/).

Exercises the parts where a bug is dangerous: the script must publish a *validated*,
openable copy; retention must keep exactly the newest N and prune the rest; and a
validation failure (a torn / garbage source) must abort WITHOUT deleting existing good
backups. The script is invoked via subprocess with env overrides so the test never
touches the live ~/forge_data.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_forge_db.sh"


def _make_live_db(path: Path, n_submissions: int = 5) -> None:
    """Write a minimal but valid DuckDB carrying the core `submissions` table."""
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE submissions (config_hash VARCHAR, status VARCHAR)")
        con.executemany(
            "INSERT INTO submissions VALUES (?, ?)",
            [(f"h{i}", "submitted") for i in range(n_submissions)],
        )
    finally:
        con.close()


def _run_backup(
    dest: Path, live_db: Path, models_dir: Path, keep: int
) -> subprocess.CompletedProcess[str]:
    env = os.environ | {
        "FORGE_BACKUP_LIVE_DB": str(live_db),
        "FORGE_BACKUP_MODELS_DIR": str(models_dir),
        "FORGE_BACKUP_DEST": str(dest),
        "FORGE_BACKUP_KEEP": str(keep),
        "FORGE_BACKUP_PYTHON": sys.executable,  # has duckdb; app-independent validation
        "FORGE_BACKUP_MIN_FREE_MB": "0",  # decouple from host free space
    }
    return subprocess.run(
        ["bash", str(BACKUP_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.fixture
def live_db(tmp_path: Path) -> Path:
    db = tmp_path / "forge.db"
    _make_live_db(db)
    return db


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    d = tmp_path / "models"
    d.mkdir()
    (d / "verdict_model_v1_x.json").write_text('{"ok": true}', encoding="utf-8")
    return d


def test_backup_produces_validated_db_and_models(
    tmp_path: Path, live_db: Path, models_dir: Path
) -> None:
    dest = tmp_path / "backups"
    res = _run_backup(dest, live_db, models_dir, keep=14)
    assert res.returncode == 0, res.stderr

    db_backups = list(dest.glob("forge_db_*.duckdb"))
    assert len(db_backups) == 1, res.stdout
    # The published copy is a real, queryable DuckDB carrying our rows.
    con = duckdb.connect(str(db_backups[0]), read_only=True)
    try:
        assert con.execute("select count(*) from submissions").fetchone()[0] == 5
    finally:
        con.close()

    assert len(list(dest.glob("models_*.tar.gz"))) == 1
    # No in-progress temp left behind on success.
    assert not list(dest.glob(".forge_db_inprogress_*"))


def test_retention_keeps_newest_n_after_a_good_backup(
    tmp_path: Path, live_db: Path, models_dir: Path
) -> None:
    dest = tmp_path / "backups"
    dest.mkdir()
    # Pre-seed 5 older db backups (2020 timestamps sort before the fresh 2026 one).
    seeded = []
    for i in range(1, 6):
        f = dest / f"forge_db_202001{i:02d}T000000Z.duckdb"
        f.write_bytes(b"old")
        seeded.append(f)

    res = _run_backup(dest, live_db, models_dir, keep=3)
    assert res.returncode == 0, res.stderr

    remaining = sorted(p.name for p in dest.glob("forge_db_*.duckdb"))
    assert len(remaining) == 3, remaining
    # The 3 oldest seeded files were pruned; the freshly-published real one survives.
    assert seeded[0].name not in remaining
    assert seeded[1].name not in remaining
    assert seeded[2].name not in remaining
    assert any(n.startswith("forge_db_2026") for n in remaining), remaining


def test_validation_failure_aborts_without_deleting_backups(
    tmp_path: Path, models_dir: Path
) -> None:
    dest = tmp_path / "backups"
    dest.mkdir()
    # An existing good backup that must survive a failed run.
    keeper = dest / "forge_db_20260101T000000Z.duckdb"
    keeper.write_bytes(b"precious")

    # A garbage "live DB" that is not a valid DuckDB file -> every validation fails.
    bad_db = tmp_path / "forge.db"
    bad_db.write_text("not a duckdb file", encoding="utf-8")

    res = _run_backup(dest, bad_db, models_dir, keep=14)
    assert res.returncode != 0, res.stdout
    # The pre-existing backup is untouched, and no partial/temp file remains.
    assert keeper.exists()
    assert keeper.read_bytes() == b"precious"
    assert sorted(p.name for p in dest.glob("forge_db_*.duckdb")) == [keeper.name]
    assert not list(dest.glob(".forge_db_inprogress_*"))
