"""`forge alpha-budget` — how much statistical search has been spent, and the
search-luck hurdle it implies (Tier-1a honesty ledger).

Forge submits to Crucible's Deflated-Sharpe gate with ``search_n_trials`` unset, so
the gate charges ``n_trials = 1`` and never deflates for the breadth of the search:
every gated candidate is judged as if it were the only strategy ever tried. This
command reads the trial counts already persisted per batch in ``batch_summaries``
(no new schema) and reports the Bailey & Lopez de Prado false-strategy hurdle — the
Sharpe a candidate must clear to beat the luckiest draw of a search that wide.

DB access mirrors the ``ranker-model`` convention: the live ``forge.db`` holds an
intermittent RW lock, so point ``--forge-db`` at a snapshot
(``cp ~/forge_data/forge.db /tmp/snap.db``) while the daemon runs. Read-only
telemetry — nothing here is written back, and the production loop never reads it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import typer

from forge.feedback.alpha_budget import (
    AlphaBudget,
    BatchRow,
    expected_max_sharpe,
    summarize_budget,
)

_DEFAULT_DB = Path("~/forge_data/forge.db").expanduser()


def read_budget_rows(conn: duckdb.DuckDBPyConnection) -> list[BatchRow]:
    """Pull the (grammar_version, batch_size, enumerated_count) triple per batch."""
    raw = conn.execute(
        "SELECT grammar_version, batch_size, enumerated_count FROM batch_summaries"
    ).fetchall()
    rows: list[BatchRow] = []
    for grammar_version, batch_size, enumerated_count in raw:
        rows.append(
            BatchRow(
                grammar_version=str(grammar_version),
                batch_size=int(batch_size),
                enumerated_count=None if enumerated_count is None else int(enumerated_count),
            )
        )
    return rows


def format_budget(budget: AlphaBudget, *, source: str) -> str:
    """Render the ledger as a glanceable multi-line readout. Pure."""
    lines = [
        f"forge alpha-budget — search breadth vs Crucible deflation (source: {source})",
        "",
        f"  batches recorded:   {budget.n_batches:>14,}",
        f"  configs submitted:  {budget.n_submitted:>14,}   "
        f"(distinct gated; rule #9)  -> luck hurdle {budget.hurdle_submitted:.2f}",
        f"  configs scored:     {budget.n_scored:>14,}   "
        f"(ranker selected among)    -> luck hurdle {budget.hurdle_scored:.2f}",
        f"  scored coverage:    {budget.scored_coverage * 100:>13.0f}%   "
        f"(batches carrying a recorded enumerated_count)",
        "",
        "  Crucible currently charges n_trials=1 (search_n_trials unset) -> deflation 0.00.",
        "  Honest hurdle E[max] of N null trials (Sharpe-stdev units) lies in "
        f"[{budget.hurdle_submitted:.2f}, {budget.hurdle_scored:.2f}].",
    ]
    if budget.by_version:
        lines.append("")
        lines.append("  by grammar version (submitted / scored -> hurdles):")
        for vb in budget.by_version:
            lines.append(
                f"    {vb.grammar_version:<6} {vb.n_submitted:>10,} / {vb.n_scored:>12,}   "
                f"-> {expected_max_sharpe(vb.n_submitted):.2f} / "
                f"{expected_max_sharpe(vb.n_scored):.2f}"
            )
    return "\n".join(lines)


def cmd_alpha_budget(
    forge_db: Path = typer.Option(
        _DEFAULT_DB,
        "--forge-db",
        help="Forge DB to read; snapshot the live DB first if the daemon is running",
    ),
) -> None:
    """Report cumulative search breadth + the search-luck Sharpe hurdle. Read-only."""
    from forge.persistence.db import db_connection

    try:
        with db_connection(forge_db) as conn:
            budget = summarize_budget(read_budget_rows(conn))
    except duckdb.Error as exc:
        typer.echo(f"alpha-budget: cannot open {forge_db}: {exc}", err=True)
        typer.echo(
            "  the live DB holds an RW lock — snapshot first:\n"
            f"  cp {_DEFAULT_DB} /tmp/forge_snap.db && "
            "forge alpha-budget --forge-db /tmp/forge_snap.db",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    typer.echo(format_budget(budget, source=str(forge_db)))


__all__ = ["cmd_alpha_budget", "format_budget", "read_budget_rows"]
