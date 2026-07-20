"""The D307 young-cell floor env gate (`FORGE_YOUNG_CELL_FLOOR`).

Pins the OFF-default: `_load_mature_cells` must return None (phase 0c
inactive, selection byte-identical) unless the env is exactly "on" — a reboot
onto this code before the operator's activation window must change nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.cli.main import _load_mature_cells
from forge.persistence.db import open_db


def test_flag_absent_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORGE_YOUNG_CELL_FLOOR", raising=False)
    db = tmp_path / "forge.db"
    open_db(db).close()
    assert _load_mature_cells(db) is None


def test_flag_off_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_YOUNG_CELL_FLOOR", "off")
    db = tmp_path / "forge.db"
    open_db(db).close()
    assert _load_mature_cells(db) is None


def test_flag_on_computes_over_the_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_YOUNG_CELL_FLOOR", "on")
    db = tmp_path / "forge.db"
    open_db(db).close()
    # Empty DB -> empty mature set (every cell young; the batch-fraction cap
    # bounds the floor) — NOT None: the floor is ACTIVE.
    assert _load_mature_cells(db) == frozenset()


def test_flag_on_memory_db_still_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_YOUNG_CELL_FLOOR", "on")
    assert _load_mature_cells(Path(":memory:")) is None
