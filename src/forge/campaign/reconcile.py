"""Step 1 of the weekly run: Crucible's verdicts into forge.db, the cell stats, and the two
ranking models the scorer loads (Batch 6 A4 split from run.py).

WHY one function on one connection: reconcile, stats and training read and write the same DB
in one window; the battery and submit open their own later. Training publishes atomically
BEFORE `_scorer` reads the newest artifact (Batch 5 G0 -- this was the daily
forge-ranker-eval timer; a weekly run needs fresh models once, right here)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from forge.campaign.cells import load_cell_stats
from forge.campaign.exports import _EXPORT_GLOBS
from forge.core.paths import newest_file

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from crucible_contracts import RegistrySnapshot

    from forge.campaign.types import CampaignConfig, CellKey, CellStats


@dataclass(frozen=True, slots=True)
class Reconciled:
    stats: Mapping[CellKey, CellStats]
    models: Mapping[str, str]


def reconcile_and_train(
    *,
    forge_db_path: Path,
    exports_dir: Path,
    registry: RegistrySnapshot,
    models_dir: Path,
    cfg: CampaignConfig,
    skip_train: bool,
    notes: list[str],
    echo: Callable[[str], None],
) -> Reconciled:
    """Reconcile the forge-scoped stream, read the cell stats, train; notes and echoes as before.

    The forge-scoped 14-day stream (contracts 1.48.0, D412) is the campaign's ledger: a weekly
    run that boots cold still sees its prior run. Until ~09-28 the retired daemon's rate floods
    it past the 10k cap and it reads `truncated: true` -- then the OLDEST verdicts are the
    missing ones, so no aged-out flush; after cutover a truncated file means something else is
    flooding source='forge' and is worth a relay."""
    from crucible_contracts import load_forge_gated_runs_from_export  # noqa: PLC0415

    from forge.feedback.consumer import reconcile_all_pending  # noqa: PLC0415
    from forge.persistence.db import db_connection  # noqa: PLC0415

    forge_stream = load_forge_gated_runs_from_export(exports_dir)
    with db_connection(forge_db_path) as conn:
        if forge_stream is None:
            # Absent is at least as blind as truncated (Crucible 09-14 §3): the all-source
            # export spans ~24 h and its floating watermark (max decided_at - 5 d) would
            # stamp the whole previous run aged-out. Reconcile what is visible; never flush.
            notes.append(
                "forge_gated_runs: absent; reconciled from the all-source export, "
                "aged-out flush skipped"
            )
            echo(
                "reconcile: forge_gated_runs stream ABSENT; all-source export used, "
                "aged-out flush skipped"
            )
            feedback = reconcile_all_pending(conn, exports_dir=exports_dir, flush_aged_out=False)
        else:
            newest_forge = newest_file(exports_dir, _EXPORT_GLOBS["forge_gated_runs"])
            n_rows = len(forge_stream.gated_runs)
            span = (
                f"{n_rows} rows, lookback {forge_stream.lookback_days} d, "
                f"cap {forge_stream.cap}, truncated={forge_stream.truncated}"
            )
            notes.append(f"forge_gated_runs: {span}")
            warn = (
                "; WINDOW TRUNCATED: oldest verdicts missing, aged-out flush skipped"
                if forge_stream.truncated
                else ""
            )
            echo(f"reconcile: forge_gated_runs {span}{warn}")
            feedback = reconcile_all_pending(
                conn,
                exports_dir=exports_dir,
                runs=forge_stream.gated_runs,
                source_export=newest_forge.name if newest_forge is not None else None,
                flush_aged_out=not forge_stream.truncated,
            )
        reconciled = sum(len(fb.outcomes) for fb in feedback)
        notes.append(f"reconciled {reconciled} outcome(s) across {len(feedback)} batch(es)")
        stats = load_cell_stats(conn)
        models_trained: dict[str, str] = {}
        if skip_train:
            notes.append("train: skipped (--skip-train)")
        else:
            from forge.campaign.train import train_models  # noqa: PLC0415

            trained = train_models(
                conn, registry, models_dir=models_dir, keep=cfg.models_keep, echo=echo
            )
            notes.extend(trained.notes)
            models_trained = dict(trained.models)
    return Reconciled(stats=stats, models=models_trained)
