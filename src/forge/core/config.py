"""Configuration loading for Forge.

Phase 0 ships a minimal YAML reader. Phase-specific Pydantic models for
`forge.yaml`, `prefilter.yaml`, `ranker.yaml` arrive as their consumers do.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file into a mapping. Raises if the top level is not a dict."""
    with path.expanduser().open("r", encoding="utf-8") as f:
        result = yaml.safe_load(f)
    if not isinstance(result, dict):
        msg = f"Expected mapping at top of {path}, got {type(result).__name__}"
        raise ValueError(msg)
    return result
