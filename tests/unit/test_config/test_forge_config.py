"""Tests for forge.config.forge_config.

Since Batch 5 G5 (D422) `forge.yaml` carries three things: Forge's DB path, Crucible's
inbox path and the `campaign:` knob overrides. `extra="forbid"` makes every retired
daemon-era key (`enumeration.*`, `submission.*`, `crucible.db_path`, and the D247 set)
fail loud rather than parse silently — a stale key that steers nothing is the D185
anti-inertness class.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from forge.config import ForgeConfig, load_forge_config

_DEFAULT_YAML: dict[str, object] = {
    "forge": {
        "db_path": "~/forge_data/forge.db",
        "crucible": {"inbox_path": "~/optbt_data/inbox"},
    }
}


def _write_yaml(tmp_path: Path, data: dict[str, object] | None = None) -> Path:
    p = tmp_path / "forge.yaml"
    p.write_text(yaml.safe_dump(data or _DEFAULT_YAML), encoding="utf-8")
    return p


def _forge_section(**extra: object) -> dict[str, object]:
    section = dict(_DEFAULT_YAML["forge"])  # type: ignore[arg-type]
    section.update(extra)
    return {"forge": section}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_returns_validated_config(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    assert isinstance(cfg, ForgeConfig)
    assert cfg.campaign == {}


def test_load_expands_tilde_in_paths(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    assert "~" not in str(cfg.db_path)
    assert "~" not in str(cfg.crucible.inbox_path)


def test_load_paths_are_absolute(tmp_path: Path) -> None:
    cfg = load_forge_config(_write_yaml(tmp_path))
    assert cfg.db_path.is_absolute()
    assert cfg.crucible.inbox_path.is_absolute()


def test_campaign_section_is_carried_raw(tmp_path: Path) -> None:
    """The dataclass owns every default; the loader only carries the overrides through."""
    cfg = load_forge_config(_write_yaml(tmp_path, _forge_section(campaign={"weekly_cap": 50})))
    assert dict(cfg.campaign) == {"weekly_cap": 50}


def test_repo_forge_yaml_loads() -> None:
    """The committed file is the deploy: it must always parse against the schema."""
    repo_yaml = Path(__file__).resolve().parents[3] / "config" / "forge.yaml"
    cfg = load_forge_config(repo_yaml)
    assert cfg.db_path.name == "forge.db"
    assert cfg.crucible.inbox_path.name == "inbox"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_load_rejects_missing_forge_section(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="forge"):
        load_forge_config(_write_yaml(tmp_path, {"not_forge": {}}))


def test_load_rejects_unknown_keys(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_forge_config(_write_yaml(tmp_path, _forge_section(weird_extra=42)))


def test_load_rejects_missing_required_subsection(tmp_path: Path) -> None:
    section = dict(_DEFAULT_YAML["forge"])  # type: ignore[arg-type]
    del section["crucible"]
    with pytest.raises(ValueError):
        load_forge_config(_write_yaml(tmp_path, {"forge": section}))


@pytest.mark.parametrize(
    ("retired_key", "value"),
    [
        ("data_root", "~/forge_data"),
        ("log_root", "~/forge_data/logs"),
        ("feedback", {"light_consumption_after_every": 1}),
        ("enumeration", {"max_candidates_per_batch": 5000, "seed": 42}),
        ("submission", {"batch_size": 200, "inflight_threshold": 0.8}),
    ],
)
def test_load_rejects_retired_keys(tmp_path: Path, retired_key: str, value: object) -> None:
    """D247 (`data_root`, `log_root`, `feedback.*`) and D422 (`enumeration.*`, `submission.*`):
    keys removed from the schema fail loudly via `extra="forbid"`."""
    with pytest.raises(ValueError):
        load_forge_config(_write_yaml(tmp_path, _forge_section(**{retired_key: value})))


def test_load_rejects_crucible_db_path(tmp_path: Path) -> None:
    """D422: Crucible is read only through its exports (hard rule #2); a `crucible.db_path`
    key has no reader and must not parse silently."""
    bad = _forge_section(
        crucible={"inbox_path": "~/optbt_data/inbox", "db_path": "~/optbt_data/runs.duckdb"}
    )
    with pytest.raises(ValueError):
        load_forge_config(_write_yaml(tmp_path, bad))
