"""Resilience: production runs must not silently degrade to the synthetic cache.

RCA (2026-05-28): after the PC rebooted, Crucible's writer socket was not yet
up. `_build_feature_cache` caught `FeatureCacheUnavailableError` and *silently*
fell back to `SyntheticFeatureCache`, whose noise-only returns make the whole
pre-filter battery meaningless — `permutation_test` then rejected every config
(prefetch=0.00s, 0 survivors). The same silent path could equally *pass*
garbage and submit it.

The fix has two halves, both checked here:
  1. `_build_feature_cache(require_real=True)` RAISES instead of degrading when
     the real cache is unavailable (and always logs loudly on fallback).
  2. A production `forge run --require-real-cache` whose cache is unavailable
     SKIPS the iteration (no batch submitted, no inbox files) rather than
     filtering against noise — the daemon loop then retries on the next poll.

The flag defaults off so dev/test flows (no writer socket) keep working on the
synthetic cache; the systemd service opts in.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crucible_contracts import FeatureCacheUnavailableError
from typer.testing import CliRunner

from forge.cli.main import _build_feature_cache, app
from forge.prefilters.feature_cache import SyntheticFeatureCache
from tests.fixtures.strategy_configs import minimal_registry_snapshot

runner = CliRunner()


# ---------------------------------------------------------------------------
# Unit: `_build_feature_cache` fallback vs. require_real, hermetic via data_root
# ---------------------------------------------------------------------------


def test_falls_back_to_synthetic_when_not_required(tmp_path: Path) -> None:
    """No writer socket under `data_root` + require_real=False -> synthetic.

    `data_root=tmp_path` has no `db_writer.sock`, so the real-cache branch is
    skipped regardless of whether a live writer exists on the host.
    """
    cache = _build_feature_cache(
        minimal_registry_snapshot(), seed=0, require_real=False, data_root=tmp_path
    )
    assert isinstance(cache, SyntheticFeatureCache)


def test_raises_when_required_and_socket_absent(tmp_path: Path) -> None:
    """No writer socket + require_real=True -> raise, never degrade silently."""
    with pytest.raises(FeatureCacheUnavailableError):
        _build_feature_cache(
            minimal_registry_snapshot(), seed=0, require_real=True, data_root=tmp_path
        )


# ---------------------------------------------------------------------------
# Integration: production run skips (no submit) when real cache is required
# but unavailable. Monkeypatch the builder to simulate a writer-down event,
# since the CLI derives the socket path from the host and the writer may be
# up on this machine.
# ---------------------------------------------------------------------------


def test_forge_run_skips_and_does_not_submit_when_real_cache_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise FeatureCacheUnavailableError("writer socket broken: simulated")

    monkeypatch.setattr("forge.cli.main._build_feature_cache", _raise)

    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--require-real-cache",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "50",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
        ],
    )

    # Clean skip, not a crash.
    assert result.exit_code == 0, result.stdout
    assert "skip" in result.stdout.lower()
    # Critical invariant: nothing submitted on the synthetic/absent cache.
    if inbox.exists():
        assert not list(inbox.rglob("*.json")), "skip must not write inbox files"
    from forge.persistence.db import db_connection

    with db_connection(forge_db) as conn:
        row = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    assert row is not None
    assert row[0] == 0, "skip must not insert submissions"


def test_forge_run_without_flag_still_submits_on_synthetic(tmp_path: Path) -> None:
    """Back-compat guard: default (flag off) keeps the synthetic-fallback submit
    path so dev/test flows without a writer socket still produce a batch."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert inbox.is_dir()
    assert list(inbox.glob("*.json")), "default path should still submit on synthetic"
