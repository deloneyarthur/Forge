"""`forge campaigns` — the discover -> concentrate -> farm loop, visible (D299).

`list` prints the campaign registry (``forge.ranking.campaigns``): what is
farming, on whose evidence, and which decision read each campaign waits on —
the state that previously lived only in STATUS.md watch lines.

`audit` runs the region-carriage check (``forge.ranking.campaign_audit``):
ranked-lane share vs holdout share per campaign, the standing detector for
the D287 failure class (generation feeds a region, selection starves it).
Exits 1 when any campaign is STARVED so a timer/script can trip on it.

Point ``--forge-db`` at a /tmp SNAPSHOT of the live DB — the live file holds
an intermittent RW lock (docs/tasks/investigate-live.md).
"""

from __future__ import annotations

from pathlib import Path

import typer

from forge.core.clock import utc_now

campaigns_app = typer.Typer(help="Campaign registry + region-carriage audit (D299).")

_DEFAULT_FORGE_DB = Path("~/forge_data/forge.db")


@campaigns_app.command("list")
def cmd_list() -> None:
    """Print every registry record with its lifecycle state and decision read."""
    from forge.ranking.campaigns import CAMPAIGNS, campaign_member_fn

    for campaign in CAMPAIGNS:
        typer.echo(f"{campaign.name}  [{campaign.status}]  opened {campaign.opened}")
        typer.echo(f"  origin:  {campaign.origin}")
        typer.echo(f"  refs:    {', '.join(campaign.decision_refs)}")
        if campaign.selection_cell is not None:
            directional, regime = campaign.selection_cell
            typer.echo(
                f"  floor:   {directional} x {regime} "
                f"({campaign.selection_slots} slots/batch, diversifier phase 0b)"
            )
        if campaign.hypothesis is not None:
            typer.echo(f"  hyp:     {campaign.hypothesis}")
        if campaign_member_fn(campaign) is None:
            typer.echo("  audit:   UNAUDITABLE (no membership signature)")
        typer.echo(f"  read:    {campaign.funnel_read}")
        typer.echo(f"  retire:  {campaign.retire_on}")
        if campaign.converted_note is not None:
            typer.echo(f"  CONVERTED: {campaign.converted_note}")
        typer.echo("")


@campaigns_app.command("audit")
def cmd_audit(
    forge_db: Path = typer.Option(
        _DEFAULT_FORGE_DB,
        "--forge-db",
        help="forge.db path (use a /tmp snapshot of the live DB — RW-lock pitfall)",
    ),
    days: int = typer.Option(7, "--days", help="Audit window in days"),
) -> None:
    """Ranked-vs-holdout carriage per farming campaign; exit 1 on starvation."""
    from forge.persistence.db import db_connection
    from forge.ranking.campaign_audit import (
        MIN_HOLDOUT_MEMBERS,
        STARVATION_RATIO,
        audit_carriage,
    )

    with db_connection(forge_db.expanduser()) as conn:
        results, unauditable = audit_carriage(conn, now=utc_now(), days=days)

    any_starved = False
    for row in results:
        ranked_share = f"{row.ranked_share:.4f}" if row.ranked_share is not None else "n/a"
        holdout_share = f"{row.holdout_share:.4f}" if row.holdout_share is not None else "n/a"
        ratio = f"{row.carriage_ratio:.3f}" if row.carriage_ratio is not None else "n/a"
        typer.echo(
            f"{row.name}: ranked {row.ranked_members}/{row.ranked_total} "
            f"({ranked_share}) | holdout {row.holdout_members}/{row.holdout_total} "
            f"({holdout_share}) | ratio {ratio} | window {row.window_days}d"
        )
        if row.decisions:
            decided = ", ".join(f"{k}={v}" for k, v in sorted(row.decisions.items()))
            typer.echo(f"  decided: {decided}")
        if row.starved:
            any_starved = True
            typer.echo(
                f"  STARVED — ranked share < {STARVATION_RATIO} x holdout share "
                f"(holdout n >= {MIN_HOLDOUT_MEMBERS}): the selection layer is "
                "eating this campaign (the D287 class). Check the P-gate "
                "eligibility of its members before touching generation."
            )
    for name in unauditable:
        typer.echo(f"{name}: UNAUDITABLE — no membership signature in the registry")
    if any_starved:
        raise typer.Exit(1)


__all__ = ["campaigns_app"]
