"""Pytest configuration and shared fixtures for Forge."""

from __future__ import annotations

from pathlib import Path

import pytest


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


@pytest.fixture(autouse=True)
def _dormant_earnings_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the sampler's earnings-coverage set to `()` — the dormant/pre-publish
    default — for every test (D274).

    `_isolated_home` cannot cover this path: `sampler._UNIVERSE_EXPORT_DIR` is
    resolved at module IMPORT time, before `Path.home()` is patched, so the v32
    coverage loader (D272) reads the operator's LIVE
    `earnings_covered_symbols*.json` once Crucible started publishing it
    (2026-07-13T23:32Z) — which silently activated the earnings-gated pool
    intersection inside test runs and broke every cold-start golden. Tests that
    exercise manifest behaviour (`test_earnings_coverage_manifest.py`) monkeypatch
    their own coverage set per test, overriding this default; the loader-path
    tests there call the original function object directly (module-attr patching
    does not touch it) with `_UNIVERSE_EXPORT_DIR` pointed at tmp_path plus
    `cache_clear`, so they stay hermetic too.
    """
    import forge.enumeration.sampler as sampler_mod

    monkeypatch.setattr(sampler_mod, "_load_earnings_covered_symbols", lambda: ())
