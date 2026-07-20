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


@pytest.fixture(autouse=True)
def _pinned_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the sampler's underlying pool to the frozen 2026-07-16 snapshot — for
    every test (Q50 durable fix, D286/v37; the universe half of the D274 pattern).

    Same import-time gotcha as the earnings pin above: `_UNIVERSE_EXPORT_DIR` is
    resolved when `sampler` is imported, so `_load_underlyings()` reads the
    operator's LIVE `universe_tickers*.json` inside test runs — Crucible's July
    tier export landed 17 minutes before the v36 deploy gate and broke 9 goldens
    at position 0 (the second live-export bite in two days; v34's was the first).
    Tests that exercise the loader/fingerprint paths re-bind the real function via
    `real_universe_loader`; tests that pin their own pool (e.g. event_momentum)
    override this default per-test as before.
    """
    import forge.enumeration.sampler as sampler_mod
    from tests.fixtures.universe_snapshot import (
        UNIVERSE_SNAPSHOT_2026_07_16,
        UNIVERSE_TIER3_SNAPSHOT_2026_07_20,
    )

    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: UNIVERSE_SNAPSHOT_2026_07_16)
    # D292/v41: the tier half of the same pin — `_tier3_symbols` feeds the
    # true-tier stamp + the xsect tier-3 share, so a live tiered export must
    # never move test draws either. Tier-dormancy tests override per-test.
    monkeypatch.setattr(sampler_mod, "_tier3_symbols", lambda: UNIVERSE_TIER3_SNAPSHOT_2026_07_20)


@pytest.fixture
def real_universe_loader(_pinned_universe: None, monkeypatch: pytest.MonkeyPatch) -> object:
    """Re-bind the REAL cached `_load_underlyings` (undoing the autouse pin) for
    loader/fingerprint tests. Depends on `_pinned_universe` so the re-bind is
    ordered after the pin; returns the original function object (which carries
    `cache_clear`)."""
    import forge.enumeration.sampler as sampler_mod

    monkeypatch.setattr(sampler_mod, "_load_underlyings", _REAL_LOAD_UNDERLYINGS)
    return _REAL_LOAD_UNDERLYINGS


def _capture_real_loader() -> object:
    import forge.enumeration.sampler as sampler_mod

    return sampler_mod._load_underlyings


# Captured at conftest import — before any fixture patches the module attr.
_REAL_LOAD_UNDERLYINGS = _capture_real_loader()
