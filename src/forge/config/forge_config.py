"""Loader + Pydantic models for `config/forge.yaml` (DESIGN.md §10.1).

D024/D8: full §10.1 coverage. CLI flags become overrides on top of the
yaml via `ForgeConfig.with_overrides(**kwargs)`. Closes Phase 4 OQ-3 and
OQ-5 (default forge-db location now comes from yaml).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _expand(p: Path | str) -> Path:
    return Path(str(p)).expanduser().resolve()


class CrucibleConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    inbox_path: Path
    db_path: Path
    contracts_version: str = Field(min_length=1)

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


class FeedbackConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    light_consumption_after_every: int = Field(ge=1)
    full_analysis_after_every: int = Field(ge=1)
    deep_review_after_every: int = Field(ge=1)


class ForgeConfig(BaseModel):
    """All-in-one §10.1 forge config — every CLI surface reads through this."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_root: Path
    db_path: Path
    log_root: Path
    crucible: CrucibleConfig
    enumeration: EnumerationConfig
    submission: SubmissionConfig
    feedback: FeedbackConfig

    @field_validator("data_root", "db_path", "log_root", mode="after")
    @classmethod
    def _expand_paths(cls, v: Path) -> Path:
        return _expand(v)

    def with_overrides(self, **overrides: Any) -> ForgeConfig:
        """Return a new ForgeConfig with selected fields replaced.

        Accepts flat kwargs that map to nested fields:
          - `db_path`, `data_root`, `log_root`     (top-level)
          - `batch_size`, `inflight_threshold`,
            `poll_interval_seconds`                (submission.*)
          - `seed`, `max_candidates_per_batch`     (enumeration.*)
        Unknown keys raise `ValueError`.
        """
        top: dict[str, Any] = {}
        submission_updates: dict[str, Any] = {}
        enumeration_updates: dict[str, Any] = {}
        known_top = {"db_path", "data_root", "log_root"}
        known_submission = {"batch_size", "inflight_threshold", "poll_interval_seconds"}
        known_enumeration = {"max_candidates_per_batch", "seed"}
        for key, value in overrides.items():
            if value is None:
                continue
            if key in known_top:
                top[key] = value
            elif key in known_submission:
                submission_updates[key] = value
            elif key in known_enumeration:
                enumeration_updates[key] = value
            else:
                msg = f"with_overrides: unknown override {key!r}"
                raise ValueError(msg)
        update: dict[str, Any] = dict(top)
        if submission_updates:
            update["submission"] = self.submission.model_copy(update=submission_updates)
        if enumeration_updates:
            update["enumeration"] = self.enumeration.model_copy(update=enumeration_updates)
        return self.model_copy(update=update)


def load_forge_config(path: Path) -> ForgeConfig:
    """Read and validate `config/forge.yaml` into a `ForgeConfig`."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "forge" not in raw:
        msg = "forge.yaml: top-level must be a mapping with a 'forge' key"
        raise ValueError(msg)
    return ForgeConfig.model_validate(raw["forge"])


__all__ = [
    "CrucibleConfig",
    "EnumerationConfig",
    "FeedbackConfig",
    "ForgeConfig",
    "SubmissionConfig",
    "load_forge_config",
]
