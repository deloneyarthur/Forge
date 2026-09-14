"""Loader + Pydantic models for `config/forge.yaml` (DESIGN.md §10.1).

D024/D8: original full §10.1 coverage; closes Phase 4 OQ-3 and OQ-5
(default forge-db location comes from yaml). CLI flags are merged on top
by the consumers (`forge.cli.main._resolve_run_defaults`), not here.

D247 deviation from §10.1 (operator-approved): `data_root`, `log_root`,
and the `feedback.*` cadence keys were never read at runtime and were
retired from both the schema and `config/forge.yaml` — the feedback
cadence is actually driven by `--consume-feedback` each loop iteration,
and the CLI commands take `--data-root` as their own option. The unused
`with_overrides` helper went with them.
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
    model_config = ConfigDict(frozen=True, extra="forbid")

    inbox_path: Path
    db_path: Path

    @field_validator("inbox_path", "db_path", mode="after")
    @classmethod
    def _expand_paths(cls, v: Path) -> Path:
        return _expand(v)


class EnumerationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_candidates_per_batch: int = Field(ge=1)
    seed: int


class SubmissionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_size: int = Field(ge=1)
    inflight_threshold: float = Field(ge=0.0, le=1.0)
    poll_interval_seconds: int = Field(ge=1)
    # Q38/D137 §7.3 stall guard: block submission when Crucible has had new work
    # in hand for >= this many seconds and decided nothing. Optional; 0 (and
    # absent) = disabled. Production opts in via config/forge.yaml (10800 = 3 h);
    # the default-off keeps the no-config/dev path on the completion-fraction
    # contract unchanged.
    stall_after_seconds: int = Field(default=0, ge=0)
    # D196 §7.3 aggregate in-flight-depth cap: block submission when the genuine
    # in-flight queue (submitted rows newer than the D110 flush watermark) exceeds
    # this many configs. Optional; 0 (and absent) = disabled. Production opts in via
    # config/forge.yaml; the default-off keeps the dev/no-config path byte-identical.
    max_inflight: int = Field(default=0, ge=0)


class ForgeConfig(BaseModel):
    """All-in-one §10.1 forge config — every CLI surface reads through this."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    db_path: Path
    crucible: CrucibleConfig
    enumeration: EnumerationConfig
    submission: SubmissionConfig
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
    "EnumerationConfig",
    "ForgeConfig",
    "SubmissionConfig",
    "campaign_config",
    "load_forge_config",
]
