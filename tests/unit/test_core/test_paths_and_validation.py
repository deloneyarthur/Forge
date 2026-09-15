"""`core.paths` and `core.validation` (Batch 6 A2): the one newest-file rule every Crucible
export reader shares, the one exports-dir fact, and the one finite-unit-interval check."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from forge.core.paths import default_data_root, default_exports_dir, newest_file
from forge.core.validation import check_unit_interval


def test_newest_file_none_when_dir_missing_or_empty(tmp_path: Path) -> None:
    assert newest_file(tmp_path / "absent", "*.json") is None
    assert newest_file(tmp_path, "*.json") is None


def test_newest_file_ignores_non_matching_and_picks_by_mtime(tmp_path: Path) -> None:
    old = tmp_path / "gated_runs_0001.json"
    new = tmp_path / "gated_runs_0002.json"
    other = tmp_path / "registry_snapshot_0001.json"
    for p in (old, new, other):
        p.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now, now))
    os.utime(other, (now + 100, now + 100))
    assert newest_file(tmp_path, "gated_runs_*.json") == new


def test_newest_file_none_when_dir_unreadable(tmp_path: Path) -> None:
    """A file where a directory is expected raises OSError on glob; the rule is None,
    not a crash."""
    not_a_dir = tmp_path / "file"
    not_a_dir.write_text("x", encoding="utf-8")
    assert newest_file(not_a_dir, "*.json") is None


def test_exports_dir_lives_under_the_data_root() -> None:
    assert default_exports_dir() == default_data_root() / "exports"
    assert default_exports_dir().name == "exports"


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_unit_interval_accepts_the_closed_interval(value: float) -> None:
    check_unit_interval("x", value)


@pytest.mark.parametrize("value", [-0.001, 1.001, float("nan"), float("inf"), float("-inf")])
def test_unit_interval_rejects_outside_and_non_finite(value: float) -> None:
    with pytest.raises(ValueError, match=r"x must be in \[0, 1\]"):
        check_unit_interval("x", value)
