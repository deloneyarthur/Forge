"""`forge ranker-model` — learned verdict model commands (D132).

F1 ships `dataset` (the honest-era training frame). The F2 commands
(`train`, `eval`) land behind their own operator gate; the model never
touches production ranking before F3.

The live `~/forge_data/forge.db` holds an intermittent RW lock — point
`--forge-db` at a `/tmp` snapshot of it (`docs/tasks/investigate-live.md`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

ranker_model_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Learned verdict model (D132): dataset / train / eval.",
)


@ranker_model_app.command("dataset")
def cmd_dataset(
    out: Path = typer.Option(..., "--out", help="output parquet path"),
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies db_path default)"
    ),
    exports_dir: Path | None = typer.Option(
        None, "--exports-dir", help="Crucible exports dir override (registry snapshot)"
    ),
    era_cut: str | None = typer.Option(
        None,
        "--era-cut",
        help="ISO label-era cutoff override (default: CLEAN_ERA_LABEL_CUT, 2026-06-10T17:17:13Z)",
    ),
) -> None:
    """Build the honest-era training frame (verdicts ⋈ submissions) as parquet."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT
    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.ranking.dataset import build_dataset

    if forge_db is None:
        if not config.exists():
            typer.echo(f"error: config {config} not found — pass --forge-db explicitly", err=True)
            raise typer.Exit(code=2)
        from forge.config import load_forge_config

        forge_db = load_forge_config(config).db_path

    cut = CLEAN_ERA_LABEL_CUT
    if era_cut is not None:
        cut = datetime.fromisoformat(era_cut)
        if cut.tzinfo is None:
            cut = cut.replace(tzinfo=UTC)

    if exports_dir is not None:
        registry = load_registry(exports_dir=exports_dir)
    else:
        registry = load_registry()

    with db_connection(forge_db) as conn:
        frame = build_dataset(conn, registry, era_cut=cut)

    out.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(out)
    positives = int(frame["label"].sum()) if frame.height else 0
    typer.echo(
        f"dataset: {frame.height} rows ({positives} positive), "
        f"{max(frame.width - 5, 0)} feature columns, era_cut={cut.isoformat()} -> {out}"
    )
