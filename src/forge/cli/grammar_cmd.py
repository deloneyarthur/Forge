"""`forge grammar` subcommands — operator workflow for §8.5 proposals.

Phase 5 module 12 ships:
  - `forge grammar list-proposals`     show pending proposals
  - `forge grammar approve-proposal`   mark approved (operator initials)
  - `forge grammar reject-proposal`    mark rejected (operator initials)

Approval records the operator initials in `grammar_proposals.decided_by`
and timestamps `decided_at`. It does NOT auto-mutate `grammar.yaml` —
that's left to the operator's manual edit + pre-commit hook (§13.2 +
hard rule #10). Phase 6 polish may add a yaml-merge convenience.

The subcommands are wired into the main `app` via Typer's add_typer
in cli/main.py.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import typer

from forge.core.clock import utc_now
from forge.persistence.db import db_connection

grammar_app = typer.Typer(
    no_args_is_help=True,
    help="Operator workflow for §8.5 grammar refinement proposals.",
)


@grammar_app.command("list-proposals")
def cmd_list_proposals(
    forge_db: Path = typer.Option(Path(":memory:"), "--forge-db", help="Forge state DB"),
) -> None:
    """List pending refinement proposals."""
    with db_connection(forge_db) as conn:
        rows = conn.execute(
            """
            SELECT proposal_id, proposed_at, proposal_type, rationale
            FROM grammar_proposals
            WHERE status = 'pending'
            ORDER BY proposed_at
            """
        ).fetchall()
    if not rows:
        typer.echo("0 pending proposals")
        return
    typer.echo(f"{len(rows)} pending proposal(s):")
    for proposal_id, proposed_at, proposal_type, rationale in rows:
        typer.echo(f"  - {proposal_id} [{proposal_type}] {proposed_at}")
        typer.echo(f"      {rationale}")


def _update_proposal_status(
    forge_db: Path, *, proposal_id: uuid.UUID, status: str, initials: str
) -> None:
    if not initials.strip():
        typer.echo("error: --initials must be non-empty", err=True)
        raise typer.Exit(code=2)
    now = utc_now()
    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT status FROM grammar_proposals WHERE proposal_id = ?",
            [str(proposal_id)],
        ).fetchone()
        if row is None:
            typer.echo(f"error: proposal {proposal_id} not found", err=True)
            raise typer.Exit(code=1)
        conn.execute(
            """
            UPDATE grammar_proposals
            SET status = ?, decided_at = ?, decided_by = ?
            WHERE proposal_id = ?
            """,
            [status, now, initials, str(proposal_id)],
        )
    typer.echo(f"proposal {proposal_id} -> {status} (by {initials})")


@grammar_app.command("approve-proposal")
def cmd_approve_proposal(
    proposal_id: str = typer.Option(..., "--id", help="proposal UUID to approve"),
    initials: str = typer.Option(..., "--initials", help="operator initials for audit"),
    forge_db: Path = typer.Option(Path(":memory:"), "--forge-db", help="Forge state DB"),
) -> None:
    """Mark a proposal as approved (operator audit row)."""
    _update_proposal_status(
        forge_db,
        proposal_id=uuid.UUID(proposal_id),
        status="approved",
        initials=initials,
    )


@grammar_app.command("reject-proposal")
def cmd_reject_proposal(
    proposal_id: str = typer.Option(..., "--id", help="proposal UUID to reject"),
    initials: str = typer.Option(..., "--initials", help="operator initials for audit"),
    forge_db: Path = typer.Option(Path(":memory:"), "--forge-db", help="Forge state DB"),
) -> None:
    """Mark a proposal as rejected (operator audit row)."""
    _update_proposal_status(
        forge_db,
        proposal_id=uuid.UUID(proposal_id),
        status="rejected",
        initials=initials,
    )


__all__ = ["grammar_app"]
