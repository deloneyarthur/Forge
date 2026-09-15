"""forge.config — `config/forge.yaml` loader: paths + campaign knobs (D422).

Re-exports the loader and models so callers can `from forge.config import load_forge_config`.
"""

from __future__ import annotations

from forge.config.forge_config import (
    CrucibleConfig,
    ForgeConfig,
    campaign_config,
    load_forge_config,
)

__all__ = [
    "CrucibleConfig",
    "ForgeConfig",
    "campaign_config",
    "load_forge_config",
]
