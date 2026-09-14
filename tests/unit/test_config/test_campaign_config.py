"""`campaign_config` resolves the weekly-run knobs with the dataclass as the only home of
defaults: yaml keys override, unknown keys fail loud (a silently ignored knob would steer
nothing, the D185 anti-inertness class), and no config at all yields the pure defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.campaign.types import CampaignConfig
from forge.config.forge_config import campaign_config, load_forge_config

_BASE = """
forge:
  db_path: ~/forge_data/forge.db
  crucible:
    inbox_path: ~/optbt_data/inbox
    db_path: ~/optbt_data/runs.duckdb
  enumeration:
    max_candidates_per_batch: 100
    seed: 1
  submission:
    batch_size: 10
    inflight_threshold: 0.8
    poll_interval_seconds: 60
"""


def _write(tmp_path: Path, extra: str) -> Path:
    p = tmp_path / "forge.yaml"
    p.write_text(_BASE + extra, encoding="utf-8")
    return p


def test_no_config_yields_defaults() -> None:
    assert campaign_config(None) == CampaignConfig()


def test_absent_section_yields_defaults(tmp_path: Path) -> None:
    assert campaign_config(load_forge_config(_write(tmp_path, ""))) == CampaignConfig()


def test_yaml_keys_override_only_what_they_name(tmp_path: Path) -> None:
    section = "  campaign:\n    weekly_cap: 50\n    exploration_min: 5\n"
    cfg = load_forge_config(_write(tmp_path, section))
    resolved = campaign_config(cfg)
    assert resolved.weekly_cap == 50
    assert resolved.exploration_min == 5
    assert resolved.leg_health_budget == CampaignConfig().leg_health_budget


def test_unknown_key_fails_loud(tmp_path: Path) -> None:
    cfg = load_forge_config(_write(tmp_path, "  campaign:\n    weekly_cpa: 50\n"))
    with pytest.raises(ValueError, match="unknown key"):
        campaign_config(cfg)
