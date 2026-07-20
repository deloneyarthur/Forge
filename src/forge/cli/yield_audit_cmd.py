"""`forge yield-audit` — the standing dead-cell detector (D302, Theme 4).

Prints dead-name and cold-cell flags over decided verdicts, plus a STAGED
RIDER DRAFT the operator can lift into a grammar-bump proposal (v34/v37
frozen-list terms). Detection only — writes NOTHING (no grammar.yaml, no
OPEN_PROPOSALS.md, no DB); shipping an exclusion stays operator-gated.

Point ``--forge-db`` at a /tmp SNAPSHOT of the live DB (RW-lock pitfall,
docs/tasks/investigate-live.md).
"""

from __future__ import annotations

from pathlib import Path

import typer

_DEFAULT_FORGE_DB = Path("~/forge_data/forge.db")


def cmd_yield_audit(
    forge_db: Path = typer.Option(
        _DEFAULT_FORGE_DB,
        "--forge-db",
        help="forge.db path (use a /tmp snapshot of the live DB — RW-lock pitfall)",
    ),
    since: str = typer.Option(
        "",
        "--since",
        help="ISO date floor for decided_at (default: the clean-era label cut)",
    ),
    min_name_n: int = typer.Option(
        0, "--min-name-n", help="Decided-row floor for a dead-name flag (default 500)"
    ),
    min_cell_n: int = typer.Option(
        0, "--min-cell-n", help="Decided-row floor for a cold-cell flag (default 1000)"
    ),
) -> None:
    """Dead-name + cold-cell yield reads; prints staged rider drafts, writes nothing."""
    from datetime import UTC, datetime

    from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT
    from forge.feedback.yield_audit import (
        DEFAULT_MIN_CELL_N,
        DEFAULT_MIN_NAME_N,
        audit_yield,
    )
    from forge.persistence.db import db_connection

    since_dt = datetime.fromisoformat(since).replace(tzinfo=UTC) if since else CLEAN_ERA_LABEL_CUT
    with db_connection(forge_db.expanduser()) as conn:
        report = audit_yield(
            conn,
            since=since_dt,
            min_name_n=min_name_n or DEFAULT_MIN_NAME_N,
            min_cell_n=min_cell_n or DEFAULT_MIN_CELL_N,
        )

    typer.echo(
        f"yield-audit: {report.rows_considered} decided rows since {report.since} "
        f"(ghost-cut {report.ghost_rows_cut} pre-07-18 ve rows)"
    )
    if report.exempt_hypotheses:
        typer.echo("cell-flag exempt (farming campaigns): " + ", ".join(report.exempt_hypotheses))

    for cell in report.cold_cells:
        typer.echo(
            f"COLD CELL {cell.hypothesis} x {cell.dte_bucket}: "
            f"{cell.converted}/{cell.decided} = {cell.cell_rate:.4f} "
            f"vs hypothesis baseline {cell.baseline_rate:.4f}"
        )
    for row in report.excluded_names:
        typer.echo(
            f"excluded-name activity (retire-review, not a flag): {row.underlying} "
            f"{row.converted}/{row.decided}"
        )

    if report.dead_names:
        names = ", ".join(f.underlying for f in report.dead_names)
        typer.echo(f"DEAD NAMES ({len(report.dead_names)}): {names}")
        typer.echo("")
        typer.echo("--- STAGED RIDER DRAFT (not written anywhere; operator lifts it) ---")
        typer.echo(
            "Rider: structural exclusion, v34/v37 frozen-list terms (re-admission "
            "on Crucible's relay; list retires whole when their liquidity "
            "preflight ships). Evidence (decided/converted since "
            f"{report.since}, ghost-cut applied):"
        )
        for flag in report.dead_names:
            typer.echo(f"  {flag.underlying}: {flag.decided} decided / {flag.converted} converted")
        typer.echo(
            "Next steps: prereg the claim (forge prereg register, D207) -> stage as "
            "a rider on the next grammar bump -> Crucible row-45 cross-check in the "
            "deploy relay."
        )
    else:
        typer.echo("no dead-name flags at the current floors")


__all__ = ["cmd_yield_audit"]
