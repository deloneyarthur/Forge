"""Already-tried ``config_hash`` sets for king dedup (FORGE meta-king A3 §4).

Phase 0 dedups against Crucible's gated-runs export — lock-free via the blessed
``load_recent_gated_runs_from_export`` helper. This is the rolling top-window of
gated runs, NOT the full tried universe; the authoritative
``submissions.config_hash`` dedup (and the unique-index idempotency guard, hard
rule #9) belong to the submission phase, which is gated on the Crucible
provenance/DSR coordination and is not built here.
"""

from __future__ import annotations

from pathlib import Path

from crucible_contracts import load_recent_gated_runs_from_export


def gated_tried_hashes(
    exports_dir: Path | None = None,
    *,
    limit: int = 10_000,
) -> frozenset[str]:
    """Return the ``config_hash`` set of the most recent gated runs.

    ``exports_dir`` defaults to ``~/optbt_data/exports``. Returns an empty set
    when the export directory or file is absent (a fresh / offline box) — dedup
    is best-effort for the dry run, not a correctness guard.
    """
    directory = exports_dir if exports_dir is not None else Path.home() / "optbt_data" / "exports"
    runs = load_recent_gated_runs_from_export(directory, limit=limit)
    return frozenset(gated.run.config_hash for gated in runs)
