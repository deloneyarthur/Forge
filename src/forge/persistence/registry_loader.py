"""Registry loader — read Crucible's published `RegistrySnapshot` snapshots.

Per `crucible_contracts.EXPORT_LAYOUT`, Crucible publishes registry snapshots
to ``~/optbt_data/exports/registry_snapshot_*.json``. Forge consumes the
newest file (by mtime) as the authoritative `RegistrySnapshot` for
enumeration. This module is the read-side of that contract.

Phase-2 history: Forge originally enumerated against an in-Forge stub
(`forge.enumeration._demo_registry`) because Crucible hadn't yet wired the
export. The 2026-05-13 go-live attempt surfaced the resulting mismatch
(Q11/Q12 in `OPEN_QUESTIONS.md`); Crucible Phase 9 v3 closed it by
publishing real snapshots (2026-05-15).

The fallback is therefore opt-in: production paths fail loudly when no
snapshot exists, because silently enumerating against the frozen Phase-2
demo means stale indicator versions/lookbacks and missing families
(2026-06-09 integration sweep). Dev-preview commands that are documented
to work offline pass ``allow_demo_fallback=True`` explicitly.
"""

from __future__ import annotations

import logging
from datetime import UTC
from pathlib import Path

from crucible_contracts import RegistrySnapshot

from forge.core.clock import utc_now

_LOG = logging.getLogger(__name__)

DEFAULT_EXPORTS_DIR = Path.home() / "optbt_data" / "exports"

_SNAPSHOT_GLOB = "registry_snapshot_*.json"

# Crucible republishes the registry at every deploy/boot (oneshot publisher
# unit); 14 quiet days means the publisher is likely wedged. Warn-only — an
# old snapshot is still valid when the registry content hasn't changed, and
# registry_hash (not age) is the integrity key enumeration runs under.
_STALE_WARN_DAYS = 14


def find_latest_snapshot(exports_dir: Path = DEFAULT_EXPORTS_DIR) -> Path | None:
    """Return the path to the newest registry snapshot in ``exports_dir``.

    Files matching ``registry_snapshot_*.json`` are ranked by mtime; the
    most recently written wins. Returns ``None`` if the directory does not
    exist or contains no matching files.
    """
    if not exports_dir.exists():
        return None
    candidates = sorted(
        exports_dir.glob(_SNAPSHOT_GLOB),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def load_registry(
    *,
    exports_dir: Path = DEFAULT_EXPORTS_DIR,
    allow_demo_fallback: bool = False,
) -> RegistrySnapshot:
    """Load the latest Crucible-published `RegistrySnapshot`.

    When an `EXPORT_LAYOUT`-compliant snapshot is present in ``exports_dir``,
    parse and return it. Otherwise raise ``FileNotFoundError`` so the caller
    surfaces the missing dependency to the operator — unless
    ``allow_demo_fallback`` is explicitly true, in which case log a warning
    and return the frozen Forge-internal demo registry (offline dev only).

    The malformed-JSON case is intentionally not caught — Pydantic's
    `ValidationError` propagates so the corruption surfaces loudly.
    """
    latest = find_latest_snapshot(exports_dir)
    if latest is not None:
        _LOG.info(
            "registry_loaded_from_export",
            extra={"path": str(latest)},
        )
        snapshot = RegistrySnapshot.model_validate_json(latest.read_text(encoding="utf-8"))
        taken_at = snapshot.snapshot_taken_at
        if taken_at.tzinfo is None:
            taken_at = taken_at.replace(tzinfo=UTC)
        age_days = (utc_now() - taken_at).total_seconds() / 86400.0
        if age_days > _STALE_WARN_DAYS:
            _LOG.warning(
                "registry_snapshot_stale",
                extra={
                    "path": str(latest),
                    "age_days": round(age_days, 1),
                    "warn_after_days": _STALE_WARN_DAYS,
                },
            )
        return snapshot

    if not allow_demo_fallback:
        raise FileNotFoundError(
            f"No {_SNAPSHOT_GLOB} found in {exports_dir} "
            "and allow_demo_fallback=False. "
            "Crucible must publish a registry snapshot per EXPORT_LAYOUT."
        )

    _LOG.warning(
        "registry_demo_fallback",
        extra={"exports_dir": str(exports_dir)},
    )
    from forge.enumeration._demo_registry import demo_registry  # noqa: PLC0415

    return demo_registry()


__all__ = [
    "DEFAULT_EXPORTS_DIR",
    "find_latest_snapshot",
    "load_registry",
]
