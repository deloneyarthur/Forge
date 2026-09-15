"""Loader + Pydantic models for `config/forge.yaml`.

Since Batch 5 G5 (D422) the file carries three things: Forge's DB path, Crucible's
inbox path, and the weekly run's `campaign:` knob overrides. Everything the daemon
needed (`enumeration.*`, `submission.*`, `crucible.db_path`) left with the daemon;
`extra="forbid"` makes a stale key fail loud instead of steering nothing (the D185
anti-inertness lesson). Precedence: CLI flag > this file > dataclass defaults;
`--no-config` = defaults + explicit paths.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from forge.campaign.types import CampaignConfig


def _expand(p: Path | str) -> Path:
    return Path(str(p)).expanduser().resolve()


class CrucibleConfig(BaseModel):
    """Where the run writes. Crucible is READ only through its exports (hard rule #2), so
    there is no `db_path` here any more (D422)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    inbox_path: Path

    @field_validator("inbox_path", mode="after")
    @classmethod
    def _expand_paths(cls, v: Path) -> Path:
        return _expand(v)


class ForgeConfig(BaseModel):
    """The whole of `config/forge.yaml`: paths + campaign knobs (D422)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    db_path: Path
    crucible: CrucibleConfig
    campaign: Mapping[str, Any] = Field(default_factory=dict)
    """Overrides for `forge.campaign.types.CampaignConfig` (plan §12.7). Kept as a raw
    mapping so the dataclass stays the single home of every default; validated by
    `campaign_config()` below (unknown keys fail loud)."""

    @field_validator("db_path", mode="after")
    @classmethod
    def _expand_paths(cls, v: Path) -> Path:
        return _expand(v)


def campaign_config(cfg: ForgeConfig | None) -> CampaignConfig:
    """Resolve the weekly-run knobs: yaml `campaign:` keys over the dataclass defaults.

    A key the dataclass does not know fails loud rather than silently steering
    nothing (the D185 anti-inertness lesson); ``cfg=None`` (``--no-config``)
    yields the pure defaults so the run needs no input."""
    section: Mapping[str, Any] = cfg.campaign if cfg is not None else {}
    known = {f.name for f in dataclasses.fields(CampaignConfig)}
    unknown = sorted(set(section) - known)
    if unknown:
        msg = f"forge.yaml campaign: unknown key(s) {unknown}; known: {sorted(known)}"
        raise ValueError(msg)
    return dataclasses.replace(CampaignConfig(), **dict(section))


def load_forge_config(path: Path) -> ForgeConfig:
    """Read and validate `config/forge.yaml` into a `ForgeConfig`."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "forge" not in raw:
        msg = "forge.yaml: top-level must be a mapping with a 'forge' key"
        raise ValueError(msg)
    return ForgeConfig.model_validate(raw["forge"])


__all__ = [
    "CampaignConfig",
    "CrucibleConfig",
    "ForgeConfig",
    "campaign_config",
    "load_forge_config",
]
