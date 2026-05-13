"""Forge CLI entry point.

Phase 0 ships:
- `forge --help`  : Typer's help text
- `forge version` : prints Forge + crucible_contracts versions
- `forge check`   : validates contracts compat and DB schema applies

Subcommands for enumerate/prefilter/rank/submit/analyze/grammar arrive in
their respective phases.
"""

from __future__ import annotations

import typer

from forge.core.logging import configure_logging
from forge.version import __version__

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Forge — candidate strategy generator.",
)


@app.callback()
def _root(
    log_level: str = typer.Option("INFO", "--log-level", help="logging level"),
    json_logs: bool = typer.Option(False, "--json-logs", help="JSON log output"),
) -> None:
    configure_logging(level=log_level, json_output=json_logs)


@app.command()
def version() -> None:
    """Print Forge and crucible_contracts versions."""
    from forge.core.contracts_check import check_contracts_version

    contracts_version = check_contracts_version()
    typer.echo(f"forge {__version__} (crucible_contracts {contracts_version})")


@app.command()
def check() -> None:
    """Validate contracts compatibility and that the DB schema applies cleanly."""
    from forge.core.contracts_check import check_contracts_version
    from forge.persistence.db import db_connection

    contracts_version = check_contracts_version()
    typer.echo(f"crucible_contracts: {contracts_version} OK")
    with db_connection(":memory:"):
        pass
    typer.echo("forge schema: OK (in-memory)")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
