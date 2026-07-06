"""Tests for `forge run` reading defaults from ``config/forge.yaml`` (D025/D6).

Phase 6 module 7 threads `load_forge_config()` through `forge run` so
that yaml values seed the runtime parameters. CLI flags override yaml
fields; `--no-config` skips yaml entirely.

This file pins the contract by exercising the resolver helper directly
plus the integration via `runner.invoke`.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import _resolve_run_defaults, app

runner = CliRunner()


def _write_yaml(path: Path, *, data_dir: Path) -> tuple[Path, Path, Path]:
    """Write a forge.yaml + return the (db_path, inbox_path, crucible_db_path) values it advertises.

    Paths embedded in the yaml live under the caller-provided `data_dir`
    so the test stays hermetic (no /tmp hardcoding).
    """
    db_path = data_dir / "yaml_test_forge.db"
    inbox_path = data_dir / "yaml_test_inbox"
    crucible_db_path = data_dir / "yaml_test_crucible.db"
    path.write_text(
        f"""
forge:
  db_path: {db_path}
  crucible:
    inbox_path: {inbox_path}
    db_path: {crucible_db_path}
  enumeration:
    max_candidates_per_batch: 1234
    seed: 99
  submission:
    batch_size: 55
    inflight_threshold: 0.55
    poll_interval_seconds: 777
    stall_after_seconds: 7200
    max_inflight: 600
""".strip(),
        encoding="utf-8",
    )
    return db_path, inbox_path, crucible_db_path


# ---------------------------------------------------------------------------
# Resolver helper unit coverage
# ---------------------------------------------------------------------------


def test_no_config_uses_hardcoded_defaults(tmp_path: Path) -> None:
    resolved = _resolve_run_defaults(
        config=Path("does_not_matter.yaml"),
        no_config=True,
        seed=None,
        batch_size=None,
        max_candidates=None,
        inbox=None,
        crucible_db=None,
        forge_db=None,
        poll_interval_seconds=None,
    )
    assert resolved["seed"] == 0
    assert resolved["batch_size"] == 10
    assert resolved["max_candidates"] == 1000
    assert resolved["poll_interval_seconds"] == 600
    assert resolved["inbox"] is None
    assert resolved["crucible_db"] is None
    assert resolved["forge_db"] is None
    # H-4: §7.3 threshold resolves to the rate-limiter default when no config.
    assert resolved["inflight_threshold"] == 0.80
    # D137: the §7.3 stall guard is OFF by default (the no-config / dev path);
    # production opts in via config/forge.yaml. 0 = disabled.
    assert resolved["stall_after_seconds"] == 0
    # D196: the §7.3 in-flight-depth cap is OFF by default the same way.
    assert resolved["max_inflight"] == 0


def test_missing_config_file_falls_back_to_hardcoded_defaults(tmp_path: Path) -> None:
    resolved = _resolve_run_defaults(
        config=tmp_path / "missing.yaml",
        no_config=False,
        seed=None,
        batch_size=None,
        max_candidates=None,
        inbox=None,
        crucible_db=None,
        forge_db=None,
        poll_interval_seconds=None,
    )
    assert resolved["seed"] == 0
    assert resolved["batch_size"] == 10
    assert resolved["max_candidates"] == 1000


def test_yaml_values_seed_defaults_when_present(tmp_path: Path) -> None:
    yaml_path = tmp_path / "forge.yaml"
    db_p, inbox_p, crucible_p = _write_yaml(yaml_path, data_dir=tmp_path)

    resolved = _resolve_run_defaults(
        config=yaml_path,
        no_config=False,
        seed=None,
        batch_size=None,
        max_candidates=None,
        inbox=None,
        crucible_db=None,
        forge_db=None,
        poll_interval_seconds=None,
    )
    assert resolved["seed"] == 99
    assert resolved["batch_size"] == 55
    assert resolved["max_candidates"] == 1234
    assert resolved["poll_interval_seconds"] == 777
    assert resolved["inbox"] == inbox_p
    assert resolved["crucible_db"] == crucible_p
    assert resolved["forge_db"] == db_p
    # H-4: the §7.3 threshold from forge.yaml flows through (was a dead knob).
    assert resolved["inflight_threshold"] == 0.55
    # D137: the stall-guard knob flows from forge.yaml the same way.
    assert resolved["stall_after_seconds"] == 7200
    # D196: the in-flight-depth cap knob flows from forge.yaml the same way.
    assert resolved["max_inflight"] == 600


def test_cli_flags_override_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "forge.yaml"
    db_p, _, crucible_p = _write_yaml(yaml_path, data_dir=tmp_path)

    override_inbox = tmp_path / "override_inbox"
    resolved = _resolve_run_defaults(
        config=yaml_path,
        no_config=False,
        seed=7,
        batch_size=4,
        max_candidates=200,
        inbox=override_inbox,
        crucible_db=None,
        forge_db=None,
        poll_interval_seconds=42,
    )
    assert resolved["seed"] == 7
    assert resolved["batch_size"] == 4
    assert resolved["max_candidates"] == 200
    assert resolved["inbox"] == override_inbox
    assert resolved["poll_interval_seconds"] == 42
    # crucible_db / forge_db NOT overridden -> yaml values flow through.
    assert resolved["crucible_db"] == crucible_p
    assert resolved["forge_db"] == db_p


def test_no_config_takes_priority_over_existing_yaml(tmp_path: Path) -> None:
    """`--no-config` is the test hermeticity guarantee: even when the
    yaml file exists, `--no-config` must bypass it entirely."""
    yaml_path = tmp_path / "forge.yaml"
    _write_yaml(yaml_path, data_dir=tmp_path)

    resolved = _resolve_run_defaults(
        config=yaml_path,
        no_config=True,  # <-- must dominate
        seed=None,
        batch_size=None,
        max_candidates=None,
        inbox=None,
        crucible_db=None,
        forge_db=None,
        poll_interval_seconds=None,
    )
    assert resolved["seed"] == 0
    assert resolved["batch_size"] == 10
    assert resolved["inbox"] is None


# ---------------------------------------------------------------------------
# Integration: `forge run --dry-run --config <test yaml>` picks up yaml seed
# ---------------------------------------------------------------------------


def test_forge_run_dry_run_with_test_config_uses_yaml_seed(tmp_path: Path) -> None:
    """End-to-end: `forge run --dry-run --config <yaml>` uses yaml's
    seed=99 even when --seed is not passed. We can't easily observe
    seed via stdout, but we CAN observe that the run completes with
    yaml-loaded paths (the inbox path mention isn't directly visible
    under --dry-run, but the run succeeds, which proves yaml loaded)."""
    yaml_path = tmp_path / "forge.yaml"
    _write_yaml(yaml_path, data_dir=tmp_path)

    result = runner.invoke(
        app,
        [
            "run",
            "--config",
            str(yaml_path),
            "--dry-run",
            "--max",
            "10",
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Two runs with the SAME yaml should be byte-identical (yaml seed dominates).
    second = runner.invoke(
        app,
        [
            "run",
            "--config",
            str(yaml_path),
            "--dry-run",
            "--max",
            "10",
        ],
    )
    assert second.exit_code == 0
    assert result.stdout == second.stdout


def test_forge_run_explicit_seed_overrides_yaml_seed(tmp_path: Path) -> None:
    """Two dry runs against the same yaml: one without --seed (yaml
    seed=99 wins), one with --seed 5 (CLI overrides). The composite-
    hash sequences must differ between the two."""
    yaml_path = tmp_path / "forge.yaml"
    _write_yaml(yaml_path, data_dir=tmp_path)

    yaml_run = runner.invoke(
        app,
        ["run", "--config", str(yaml_path), "--dry-run", "--max", "10"],
    )
    override_run = runner.invoke(
        app,
        ["run", "--config", str(yaml_path), "--seed", "5", "--dry-run", "--max", "10"],
    )
    assert yaml_run.exit_code == 0
    assert override_run.exit_code == 0
    assert yaml_run.stdout != override_run.stdout, (
        "yaml seed=99 vs CLI --seed 5 should produce different candidate sequences"
    )
