"""forge.config — `config/forge.yaml` loader (Phase 5, D024/D8).

Re-exports `ForgeConfig` + `load_forge_config` from the submodule so the
operator can `from forge.config import load_forge_config`.
"""

from __future__ import annotations

from forge.config.forge_config import (
    CrucibleConfig,
    EnumerationConfig,
    ForgeConfig,
    SubmissionConfig,
    load_forge_config,
)

__all__ = [
    "CrucibleConfig",
    "EnumerationConfig",
    "ForgeConfig",
    "SubmissionConfig",
    "load_forge_config",
]
