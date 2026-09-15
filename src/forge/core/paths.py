"""The two path facts every reader of Crucible's exports used to restate (Batch 6 A2).

WHY: five modules each hand-built ``~/optbt_data/exports`` and four each re-implemented
"newest file matching a glob, by mtime". One home means a moved exports directory or a changed
selection rule lands once. ``newest_file`` treats a missing directory, an unreadable one and an
empty match identically (``None``) because every caller already did — the difference between
"no directory" and "no file" is never a decision here.
"""

from __future__ import annotations

from pathlib import Path


def default_exports_dir() -> Path:
    """Crucible's publisher directory: the only place Forge reads Crucible from (hard rule #2)."""
    return Path.home() / "optbt_data" / "exports"


def default_data_root() -> Path:
    """Crucible's data root (the writer socket lives under it)."""
    return Path.home() / "optbt_data"


def newest_file(directory: Path, glob: str) -> Path | None:
    """The newest file in ``directory`` matching ``glob`` by mtime, or ``None``.

    Publishers write timestamped snapshots and readers want the latest; mtime is the
    contract every Crucible export reader has used. A directory that does not exist or
    cannot be listed yields ``None`` rather than raising — the caller decides whether an
    absent export is a boot failure (the campaign) or a fail-open empty read (refutations).
    """
    try:
        files = sorted(directory.glob(glob), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    return files[-1] if files else None


__all__ = ["default_data_root", "default_exports_dir", "newest_file"]
