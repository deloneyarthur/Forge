"""Which Crucible export each name means, and the content watermarks a run records.

WHY its own module (Batch 6 A4): `boot` and `generate` both read the glob table, and both are
imported by the orchestrator, so the table cannot live in `run.py` without an import cycle.
Watermarks are sha256 of file CONTENT, never mtime: a republished byte-identical file must not
look like a new basis (Crucible republishes daily heartbeats)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from forge.core.paths import newest_file

_EXPORT_GLOBS: Mapping[str, str] = MappingProxyType(
    {
        "registry": "registry_snapshot_*.json",
        "universe": "universe_tickers_*.json",
        "gated_runs": "gated_runs_*.json",
        "forge_gated_runs": "forge_gated_runs_*.json",
        "failed_runs": "failed_runs_*.json",
        "refutations": "refutations_*.json",
        "promoted_portfolios": "promoted_portfolios_*.json",
        "component_contributions": "component_contributions_*.json",
        "designation_history": "designation_history*.json",
    }
)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def watermarks(exports_dir: Path) -> dict[str, str]:
    """``export -> "<file>@<sha256[:12]>"`` for every export the run reads (content, not mtime)."""
    out: dict[str, str] = {}
    for name, glob in _EXPORT_GLOBS.items():
        newest = newest_file(exports_dir, glob)
        if newest is not None:
            out[name] = f"{newest.name}@{sha256_of(newest)[:12]}"
    return out
