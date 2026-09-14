"""`forge campaign` — the weekly, zero-input challenger run (plan 2026-09 §12; D406/D409).

`forge campaign` runs one week's decision: boot checks -> reconcile -> read the
designated book -> triggers -> rejection-sample the unchanged v55 population ->
battery -> challenger gate -> in-cell rank -> submit (<= the weekly cap). The
operator supplies nothing; every knob has a default (`config/forge.yaml`
``campaign:`` overrides them). `--dry-run` executes the same decision path and
submits nothing, so two dry runs on the same exports can be compared plan for
plan. `status` prints the recent run records with the verdicts their
submissions earned.

Exit codes are the paging contract for `forge-campaign.service` (no
``SuccessExitStatus``): 0 = ok or no trigger, 2 = a boot check failed (nothing
submitted), 1 = an error after boot (an ``error`` record was written first).
"""

from __future__ import annotations

from pathlib import Path

import typer

campaign_app = typer.Typer(
    invoke_without_command=True,
    help="Weekly zero-input challenger run for the designated book (plan 2026-09 §12).",
)

_DEFAULT_CONFIG = Path("config/forge.yaml")
_DEFAULT_EXPORTS = Path("~/optbt_data/exports")
_DEFAULT_RECORDS = Path("~/forge_data/campaigns")
_DEFAULT_FORGE_DB = Path("~/forge_data/forge.db")
_DEFAULT_INBOX = Path("~/optbt_data/inbox")
_DEFAULT_CRUCIBLE_DB = Path("~/optbt_data/runs.duckdb")
_EXIT_BOOT_FAILED = 2
_EXIT_ERROR = 1


def _repo_config_root() -> Path:
    return Path(__file__).resolve().parents[3] / "config"


@campaign_app.callback()
def cmd_campaign(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Decide and rank, submit nothing; the record lists the plan."
    ),
    budget: int | None = typer.Option(
        None, "--budget", min=0, help="Cap this run's total submissions below the weekly cap."
    ),
    config: Path = typer.Option(
        _DEFAULT_CONFIG, "--config", help="forge.yaml (db/inbox/crucible paths + campaign: knobs)."
    ),
    no_config: bool = typer.Option(
        False, "--no-config", help="Ignore forge.yaml; use defaults and explicit paths only."
    ),
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (default: forge.yaml or ~/forge_data/forge.db)."
    ),
    inbox: Path | None = typer.Option(
        None, "--inbox", help="Crucible inbox dir (default: forge.yaml or ~/optbt_data/inbox)."
    ),
    crucible_db: Path | None = typer.Option(
        None, "--crucible-db", help="Crucible runs.duckdb, the consumer's fallback path only."
    ),
    exports_dir: Path = typer.Option(
        _DEFAULT_EXPORTS, "--exports-dir", help="Crucible exports dir (registry, gated, book)."
    ),
    records_dir: Path = typer.Option(
        _DEFAULT_RECORDS, "--records-dir", help="Where run records (campaign_run/v1) are written."
    ),
    models_dir: Path | None = typer.Option(
        None, "--models-dir", help="Model artifacts dir (default: <forge_db dir>/models)."
    ),
    config_root: Path | None = typer.Option(
        None, "--config-root", help="Grammar/prefilter config dir (default: the repo's config/)."
    ),
) -> None:
    """Run this week's campaign (boot, reconcile, decide, generate, gate, submit)."""
    if ctx.invoked_subcommand is not None:
        return
    from forge.campaign.run import run_campaign
    from forge.config.forge_config import campaign_config, load_forge_config

    cfg_file = None if no_config else load_forge_config(config)
    knobs = campaign_config(cfg_file)
    db_path = (forge_db or (cfg_file.db_path if cfg_file else _DEFAULT_FORGE_DB)).expanduser()
    inbox_path = (
        inbox or (cfg_file.crucible.inbox_path if cfg_file else _DEFAULT_INBOX)
    ).expanduser()
    crucible_path = (
        crucible_db or (cfg_file.crucible.db_path if cfg_file else _DEFAULT_CRUCIBLE_DB)
    ).expanduser()
    try:
        record = run_campaign(
            forge_db_path=db_path,
            exports_dir=exports_dir.expanduser(),
            inbox_root=inbox_path,
            models_dir=(models_dir or db_path.parent / "models").expanduser(),
            records_dir=records_dir.expanduser(),
            config_root=(config_root or _repo_config_root()).expanduser(),
            crucible_db=crucible_path,
            cfg=knobs,
            dry_run=dry_run,
            budget_override=budget,
        )
    except Exception as exc:
        typer.echo(f"campaign: error {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=_EXIT_ERROR) from exc
    if record.status == "boot_failed":
        raise typer.Exit(code=_EXIT_BOOT_FAILED)


@campaign_app.command("status")
def cmd_status(
    records_dir: Path = typer.Option(
        _DEFAULT_RECORDS, "--records-dir", help="Where run records are read from."
    ),
    last: int = typer.Option(8, "--last", min=1, help="How many recent runs to print."),
    forge_db: Path | None = typer.Option(
        None,
        "--forge-db",
        help=(
            "forge.db to join verdicts from; point at a scripts/live_db_snapshot.sh copy "
            "while a daemon holds the live file (RW-lock pitfall)."
        ),
    ),
) -> None:
    """Print recent campaign runs and the verdicts their submissions earned."""
    from forge.campaign.report import format_status, load_records
    from forge.persistence.db import db_connection

    records = load_records(records_dir.expanduser())
    if forge_db is None:
        typer.echo(format_status(records, None, last=last))
        return
    with db_connection(forge_db.expanduser()) as conn:
        typer.echo(format_status(records, conn, last=last))


__all__ = ["campaign_app"]
