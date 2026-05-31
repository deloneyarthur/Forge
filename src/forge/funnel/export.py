"""Write the pre-filter funnel export to disk (D096 — Part B + Part A map).

Two decoupled JSON artifacts under Forge's own export dir
(`~/forge_data/exports/` by default — the operator's chosen boundary: Forge
owns its export space, Crucible reads it):

- `forge_funnel.json` — the aggregated per-grammar-version funnel (Part B).
- `forge_submission_versions.json` — the `config_hash -> grammar_version`
  join-map Crucible joins against for its funnel Stage 0 (Part A interim).

Each write is atomic (tmp-then-rename) so Crucible's reader never observes a
half-written file. `exported_at` is stamped from the blessed clock
(`forge.core.clock.utc_now`, hard rule #8); injectable for deterministic tests.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from forge.core.clock import utc_now
from forge.funnel.aggregate import build_funnel_export, build_version_map
from forge.funnel.types import SCHEMA_VERSION

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import duckdb

FUNNEL_FILENAME = "forge_funnel.json"
VERSION_MAP_FILENAME = "forge_submission_versions.json"


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """Write `payload` as pretty JSON via tmp-then-rename (atomic on POSIX)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False))
    tmp.rename(path)


def write_funnel_export(
    db: duckdb.DuckDBPyConnection,
    exports_dir: Path,
    *,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    """Refresh both export artifacts from current DB state.

    Returns `(funnel_path, version_map_path)`. Creates `exports_dir` if
    absent. Pure read of the DB; the only write is to the two files.
    """
    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or utc_now()).isoformat()

    export = build_funnel_export(db)
    funnel_payload: dict[str, object] = {"exported_at": stamp, **export.to_dict()}
    funnel_path = exports_dir / FUNNEL_FILENAME
    _atomic_write_json(funnel_path, funnel_payload)

    version_map = build_version_map(db)
    version_map_payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": stamp,
        "config_hash_grammar_version": version_map,
    }
    version_map_path = exports_dir / VERSION_MAP_FILENAME
    _atomic_write_json(version_map_path, version_map_payload)

    return funnel_path, version_map_path


__all__ = ["FUNNEL_FILENAME", "VERSION_MAP_FILENAME", "write_funnel_export"]
