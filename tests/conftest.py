"""Pytest configuration and shared fixtures for Forge."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the tests/fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect `Path.home()` to a per-test tmp dir.

    Code paths that default to `~/optbt_data/...` (rate limiter exports_dir,
    feedback consumer exports_dir, registry loader exports_dir) would
    otherwise pick up real artifacts from the operator's home during local
    test runs and conflict with synthetic test fixtures. Routing
    `Path.home()` to tmp_path keeps each test hermetic.
    """
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    return fake_home
