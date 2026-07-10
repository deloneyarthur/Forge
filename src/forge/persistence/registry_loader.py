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

from crucible_contracts import RegistrySnapshot, parse_skipping_unknown_literals

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


def _parse_registry_tolerating_unknown_family(text: str) -> RegistrySnapshot:
    """Parse a `RegistrySnapshot`, tolerating indicators whose `family` is an
    unknown `Literal` value, via the contracts-owned tolerant reader.

    D261 (the ivol reclassification outage) showed a Crucible `family` added to
    `crucible_contracts` ahead of Forge's pin adoption makes the whole snapshot
    fail with a `literal_error` — not an extra field, so `parse_forward_compatible`
    (D250) re-raises it and the daemon fails every poll (soft outage). Crucible
    shipped `parse_skipping_unknown_literals` (contracts 1.29.0) as the shared
    tolerant reader for that face: it DROPS `skip_in` collection elements carrying
    an unknown enum member (and prunes additive unknown fields in the same pass),
    keeping the rest, and returns the skips; every other error stays strict (a
    `literal_error` outside `skip_in`, or any genuine error, re-raises). Forge
    wires it here (hard rule #2 — inter-system tolerance lives in contracts, the
    D250 seam) rather than hand-rolling the prune, and re-emits any skips as its
    own structured ``registry_unknown_family_skipped`` WARN so `forge healthcheck`
    (`check_registry_unknown_family`, a separate process) can detect the degrade
    from the journal. Dropping an unknown-family indicator changes no enumerated
    config (Forge can't grammar-place it anyway); the WARN is the load-bearing
    signal to adopt the newer contracts (D262).
    """
    snapshot, skipped = parse_skipping_unknown_literals(
        RegistrySnapshot, text, skip_in=("indicators",), logger=_LOG
    )
    if skipped:
        _LOG.warning(
            "registry_unknown_family_skipped",
            extra={"skipped": list(skipped), "count": len(skipped)},
        )
    return snapshot


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

    Malformed JSON and genuine schema violations are intentionally not caught —
    Pydantic's `ValidationError` propagates so corruption surfaces loudly. The one
    tolerated case is an indicator with an unknown `family` Literal value (a
    Crucible family added ahead of Forge's contracts-pin adoption): it is dropped
    with a WARN and the rest loads, so an asymmetric upgrade degrades gracefully
    instead of failing every poll (D261; see `_parse_registry_tolerating_unknown_family`).
    """
    latest = find_latest_snapshot(exports_dir)
    if latest is not None:
        _LOG.info(
            "registry_loaded_from_export",
            extra={"path": str(latest)},
        )
        snapshot = _parse_registry_tolerating_unknown_family(latest.read_text(encoding="utf-8"))
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
