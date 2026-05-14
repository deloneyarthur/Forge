"""`forge feedback` — manual single-batch feedback consumer + analyzer + proposer.

D024/D6: this command runs the per-batch feedback chain once over the
target batch (current latest by default; or explicit `--batch-id`).
Auto-tune is invoked unconditionally so calibration loosenings get
proposed even when the proposer fires no §8.4 triggers.

See `cli/main.py` for `forge run --consume-feedback` (the inline daemon
hook).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from forge.core.clock import utc_now

if TYPE_CHECKING:
    pass


def _resolve_paths(
    *,
    config: Path | None,
    no_config: bool,
    crucible_db: Path | None,
    forge_db: Path | None,
) -> tuple[Path, Path]:
    """Resolve crucible_db and forge_db from CLI flags + optional yaml."""
    if no_config or config is None:
        if crucible_db is None or forge_db is None:
            typer.echo(
                "error: with --no-config, both --crucible-db and --forge-db are required",
                err=True,
            )
            raise typer.Exit(code=2)
        return crucible_db, forge_db
    if not config.exists():
        typer.echo(f"error: config {config} not found (use --no-config to skip)", err=True)
        raise typer.Exit(code=2)
    from forge.config import load_forge_config

    cfg = load_forge_config(config)
    return (
        crucible_db or cfg.crucible.db_path,
        forge_db or cfg.db_path,
    )


def cmd_feedback(
    batch_id: str | None = typer.Option(
        None, "--batch-id", help="explicit batch UUID (default: latest submitted batch)"
    ),
    since: str | None = typer.Option(
        None, "--since", help="ISO datetime cutoff for Crucible runs (default: batch.submitted_at)"
    ),
    config: Path = typer.Option(Path("config/forge.yaml"), "--config", help="path to forge.yaml"),
    no_config: bool = typer.Option(False, "--no-config", help="skip yaml, require explicit paths"),
    forge_db: Path | None = typer.Option(None, "--forge-db", help="override yaml forge db path"),
    crucible_db: Path | None = typer.Option(
        None, "--crucible-db", help="override yaml Crucible db path"
    ),
    open_proposals: Path = typer.Option(
        Path("OPEN_PROPOSALS.md"), "--open-proposals", help="proposal audit markdown"
    ),
    prefilter_yaml: Path = typer.Option(
        Path("config/prefilter.yaml"), "--prefilter-yaml", help="prefilter calibration yaml"
    ),
) -> None:
    """Read Crucible's gated runs, analyze, propose refinements."""
    crucible_db_path, forge_db_path = _resolve_paths(
        config=config,
        no_config=no_config,
        crucible_db=crucible_db,
        forge_db=forge_db,
    )

    from forge.enumeration._demo_registry import demo_registry
    from forge.feedback.analyzer import analyze_batch
    from forge.feedback.auto_tune import auto_tune
    from forge.feedback.consumer import consume_batch_results
    from forge.feedback.promoted_patterns import record_promoted_patterns
    from forge.feedback.proposal_writer import append_proposal
    from forge.feedback.proposer import propose
    from forge.persistence.db import db_connection
    from forge.prefilters.calibration import load_calibration

    resolved_batch_id = uuid.UUID(batch_id) if batch_id else None
    parsed_since = datetime.fromisoformat(since) if since else None
    if parsed_since is not None and parsed_since.tzinfo is None:
        parsed_since = parsed_since.replace(tzinfo=UTC)

    now = utc_now()

    with db_connection(forge_db_path) as conn:
        feedback = consume_batch_results(
            conn,
            crucible_db_path,
            batch_id=resolved_batch_id,
            since=parsed_since,
        )

        registry = demo_registry()
        report = analyze_batch(feedback, registry)

        if report.promoted_patterns:
            record_promoted_patterns(conn, report.promoted_patterns, discovered_at=now)

        proposals = propose(report, feedback, at=now)
        for proposal in proposals:
            append_proposal(proposal, open_proposals_path=open_proposals, db=conn)

        if prefilter_yaml.exists():
            calibration = load_calibration(prefilter_yaml)
            auto_tune(
                db=conn,
                calibration=calibration,
                prefilter_yaml_path=prefilter_yaml,
                open_proposals_path=open_proposals,
                at=now,
            )

    typer.echo(
        f"batch_id={feedback.batch_id} "
        f"submitted_count={feedback.submitted_count} "
        f"gated_count={feedback.gated_count} "
        f"promoted_count={feedback.promoted_count} "
        f"rejected_count={feedback.rejected_count} "
        f"pending_count={feedback.pending_count} "
        f"proposals={len(proposals)} "
        f"patterns={len(report.promoted_patterns)}"
    )


__all__ = ["cmd_feedback"]
