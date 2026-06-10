"""Tests for `forge.persistence.registry_loader`.

Phase 9 v3 prep: reading Crucible's `EXPORT_LAYOUT`-compliant snapshots
with a graceful demo-registry fallback while Crucible's v3 export wiring
is being built.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

from forge.enumeration._demo_registry import demo_registry
from forge.persistence.registry_loader import (
    find_latest_snapshot,
    load_registry,
)


def _write_snapshot(path: Path, snapshot: RegistrySnapshot) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_find_latest_snapshot_returns_none_when_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert find_latest_snapshot(missing) is None


def test_find_latest_snapshot_returns_none_when_dir_empty(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    assert find_latest_snapshot(exports) is None


def test_find_latest_snapshot_ignores_non_matching_files(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "promoted_strategies_2026.json").write_text("[]")
    (exports / "registry_snapshot.json").write_text("{}")  # missing the underscore-suffix
    (exports / "notes.txt").write_text("hi")
    assert find_latest_snapshot(exports) is None


def test_find_latest_snapshot_picks_newest_by_mtime(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    snap = demo_registry()
    a = _write_snapshot(exports / "registry_snapshot_2026-05-01.json", snap)
    time.sleep(0.01)  # ensure distinct mtimes on fast filesystems
    b = _write_snapshot(exports / "registry_snapshot_2026-05-02.json", snap)
    found = find_latest_snapshot(exports)
    assert found == b
    # And the older file isn't selected even though both match the glob:
    assert found != a


def test_load_registry_parses_export(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    snap = demo_registry()
    _write_snapshot(exports / "registry_snapshot_2026-05-13T22-00-00Z.json", snap)
    loaded = load_registry(exports_dir=exports)
    # Round-trip equality on the indicator set:
    loaded_ids = {i.id for i in loaded.indicators}
    original_ids = {i.id for i in snap.indicators}
    assert loaded_ids == original_ids


def test_load_registry_falls_back_to_demo_when_missing(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing = tmp_path / "exports"  # dir doesn't exist
    with caplog.at_level(logging.WARNING):
        registry = load_registry(exports_dir=missing, allow_demo_fallback=True)
    # Demo fallback returns a real RegistrySnapshot
    assert isinstance(registry, RegistrySnapshot)
    # Warning recorded
    assert any(
        "registry_demo_fallback" in r.message or getattr(r, "msg", "") == "registry_demo_fallback"
        for r in caplog.records
    )


def test_load_registry_raises_when_missing_and_fallback_disabled(tmp_path: Path) -> None:
    missing = tmp_path / "exports"  # dir doesn't exist
    with pytest.raises(FileNotFoundError, match="EXPORT_LAYOUT"):
        load_registry(exports_dir=missing, allow_demo_fallback=False)


def test_load_registry_default_is_fail_loud(tmp_path: Path) -> None:
    """The demo fallback must be opt-in, not the default. Crucible's v3
    export wiring shipped 2026-05-15; the module docstring always said
    production flips to fail-loud once it did. With the default True, a
    missing/empty exports dir silently fed the live enumerator a frozen
    2026-05-13 registry (stale versions, no sue/dse — 2026-06-09 sweep)."""
    missing = tmp_path / "exports"  # dir doesn't exist
    with pytest.raises(FileNotFoundError, match="EXPORT_LAYOUT"):
        load_registry(exports_dir=missing)


def test_load_registry_warns_when_snapshot_stale(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Crucible republishes the registry at every deploy/boot; a snapshot
    14+ days old means the publisher is likely wedged. Warn — don't halt:
    an old snapshot is still valid if the registry content didn't change
    (registry_hash is the integrity key)."""
    from datetime import UTC, datetime, timedelta

    exports = tmp_path / "exports"
    snap = demo_registry().model_copy(
        update={"snapshot_taken_at": datetime.now(UTC) - timedelta(days=20)}
    )
    _write_snapshot(exports / "registry_snapshot_old.json", snap)
    with caplog.at_level(logging.WARNING):
        load_registry(exports_dir=exports)
    assert any("registry_snapshot_stale" in r.getMessage() for r in caplog.records)


def test_load_registry_no_stale_warning_when_fresh(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from datetime import UTC, datetime, timedelta

    exports = tmp_path / "exports"
    snap = demo_registry().model_copy(
        update={"snapshot_taken_at": datetime.now(UTC) - timedelta(days=2)}
    )
    _write_snapshot(exports / "registry_snapshot_fresh.json", snap)
    with caplog.at_level(logging.WARNING):
        load_registry(exports_dir=exports)
    assert not any("registry_snapshot_stale" in r.getMessage() for r in caplog.records)


def test_load_registry_propagates_validation_error_on_malformed_json(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "registry_snapshot_corrupt.json").write_text("{not valid json")
    # Pydantic raises ValidationError; we don't catch it. Allow either
    # ValidationError or JSONDecodeError shape — both are honest signals.
    with pytest.raises(Exception):  # noqa: B017
        load_registry(exports_dir=exports)
