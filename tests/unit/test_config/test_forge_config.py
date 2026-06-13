"""Tests for forge.config.forge_config (Phase 5 module 9, D024/D8).

`load_forge_config(path) -> ForgeConfig` reads DESIGN.md §10.1 yaml and
returns a validated config. CLI flags become overrides on top of yaml
via `override_with()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.config import ForgeConfig, load_forge_config

_DEFAULT_YAML: dict[str, object] = {
    "forge": {
        "data_root": "~/forge_data",
        "db_path": "~/forge_data/forge.db",
        "log_root": "~/forge_data/logs",
        "crucible": {
            "inbox_path": "~/optbt_data/inbox",
            "db_path": "~/optbt_data/results.duckdb",
            "contracts_version": "1.6",
        },
        "enumeration": {"max_candidates_per_batch": 100000, "seed": 42},
        "submission": {
            "batch_size": 200,
            "inflight_threshold": 0.80,
            "poll_interval_seconds": 600,
        },
        "feedback": {
            "light_consumption_after_every": 1,
            "full_analysis_after_every": 10,
            "deep_review_after_every": 50,
        },
    }
}


def _write_yaml(tmp_path: Path, data: dict[str, object] | None = None) -> Path:
    p = tmp_path / "forge.yaml"
    p.write_text(yaml.safe_dump(data or _DEFAULT_YAML), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_returns_validated_config(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path)
    cfg = load_forge_config(path)
    assert isinstance(cfg, ForgeConfig)
    assert cfg.crucible.contracts_version == "1.6"
    assert cfg.submission.batch_size == 200
    assert cfg.feedback.full_analysis_after_every == 10


def test_load_expands_tilde_in_paths(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path)
    cfg = load_forge_config(path)
    assert "~" not in str(cfg.db_path)
    assert "~" not in str(cfg.crucible.inbox_path)


def test_load_paths_are_absolute(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path)
    cfg = load_forge_config(path)
    assert cfg.db_path.is_absolute()
    assert cfg.crucible.inbox_path.is_absolute()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_load_rejects_missing_forge_section(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, {"not_forge": {}})
    with pytest.raises(ValueError, match="forge"):
        load_forge_config(path)


def test_load_rejects_unknown_keys(tmp_path: Path) -> None:
    bad = dict(_DEFAULT_YAML)
    bad_forge = dict(bad["forge"])  # type: ignore[arg-type]
    bad_forge["weird_extra"] = 42
    path = _write_yaml(tmp_path, {"forge": bad_forge})
    with pytest.raises(ValueError):
        load_forge_config(path)


def test_load_rejects_negative_batch_size(tmp_path: Path) -> None:
    bad = dict(_DEFAULT_YAML)
    forge_section = dict(bad["forge"])  # type: ignore[arg-type]
    forge_section["submission"] = {
        "batch_size": -10,
        "inflight_threshold": 0.80,
        "poll_interval_seconds": 600,
    }
    path = _write_yaml(tmp_path, {"forge": forge_section})
    with pytest.raises(ValueError):
        load_forge_config(path)


def test_load_rejects_inflight_threshold_above_one(tmp_path: Path) -> None:
    bad = dict(_DEFAULT_YAML)
    forge_section = dict(bad["forge"])  # type: ignore[arg-type]
    forge_section["submission"] = {
        "batch_size": 200,
        "inflight_threshold": 1.5,
        "poll_interval_seconds": 600,
    }
    path = _write_yaml(tmp_path, {"forge": forge_section})
    with pytest.raises(ValueError):
        load_forge_config(path)


def test_load_rejects_missing_required_subsection(tmp_path: Path) -> None:
    bad = dict(_DEFAULT_YAML)
    forge_section = dict(bad["forge"])  # type: ignore[arg-type]
    del forge_section["feedback"]
    path = _write_yaml(tmp_path, {"forge": forge_section})
    with pytest.raises(ValueError):
        load_forge_config(path)


# ---------------------------------------------------------------------------
# D137 — §7.3 stall-guard knob (submission.stall_after_seconds)
# ---------------------------------------------------------------------------


def test_stall_after_seconds_defaults_to_zero_when_absent(tmp_path: Path) -> None:
    """The knob is optional; absent → 0 (guard disabled). `_DEFAULT_YAML` omits
    it, so the happy-path config exercises the absent-disables contract."""
    cfg = load_forge_config(_write_yaml(tmp_path))
    assert cfg.submission.stall_after_seconds == 0


def test_stall_after_seconds_parses_when_present(tmp_path: Path) -> None:
    forge_section = dict(_DEFAULT_YAML["forge"])  # type: ignore[arg-type]
    forge_section["submission"] = {
        "batch_size": 200,
        "inflight_threshold": 0.80,
        "poll_interval_seconds": 600,
        "stall_after_seconds": 10800,
    }
    cfg = load_forge_config(_write_yaml(tmp_path, {"forge": forge_section}))
    assert cfg.submission.stall_after_seconds == 10800


def test_load_rejects_negative_stall_after_seconds(tmp_path: Path) -> None:
    forge_section = dict(_DEFAULT_YAML["forge"])  # type: ignore[arg-type]
    forge_section["submission"] = {
        "batch_size": 200,
        "inflight_threshold": 0.80,
        "poll_interval_seconds": 600,
        "stall_after_seconds": -1,
    }
    path = _write_yaml(tmp_path, {"forge": forge_section})
    with pytest.raises(ValueError):
        load_forge_config(path)


# ---------------------------------------------------------------------------
# Override
# ---------------------------------------------------------------------------


def test_override_with_replaces_specified_fields(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    new = cfg.with_overrides(batch_size=50, seed=99)
    assert new.submission.batch_size == 50
    assert new.enumeration.seed == 99
    # Untouched fields stay
    assert new.feedback.full_analysis_after_every == cfg.feedback.full_analysis_after_every


def test_override_with_no_overrides_returns_equivalent(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    same = cfg.with_overrides()
    assert same.submission.batch_size == cfg.submission.batch_size


def test_override_with_forge_db_path(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    new_db = tmp_path / "alt.db"
    new = cfg.with_overrides(db_path=new_db)
    assert new.db_path == new_db


def test_override_rejects_unknown_field(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    with pytest.raises(ValueError, match="unknown override"):
        cfg.with_overrides(weird_field=1)
