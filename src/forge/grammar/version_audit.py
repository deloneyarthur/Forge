"""Grammar-version audit trail — the `grammar_versions` provenance table.

Hard rule #10 requires every `grammar_version` map to a recorded row so each
submitted `config_hash` is traceable to the exact grammar that produced it, and
the D035 stuck-state floor can read `MAX(grammar_versions.changed_at)`.

D051 (2026-05-18): `ensure_grammar_version_recorded` self-heals that row for a
MANUAL operator yaml bump (the common path — all bumps to date), which does not
pass through `apply-proposal` / `revert`. The daemon calls it at the top of
every cycle; it is a SELECT-only no-op once the row exists.

Extracted (D325) from the retired `feedback.auto_tune` module: the §5.5
auto-tune TRIGGER that once shared this file was dead (never fired) and was
removed; these provenance writers are the live remainder. `_write_grammar_versions_row`
stays importable for `grammar_cmd`'s `apply-proposal` / `revert` calibration rows.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import duckdb

    from forge.grammar.models import Grammar


def _write_grammar_versions_row(
    db: duckdb.DuckDBPyConnection,
    *,
    change_type: str,
    description: str,
    at: datetime,
) -> None:
    db.execute(
        """
        INSERT INTO grammar_versions
            (version, rule_count, yaml_sha256, changed_at, change_type,
             change_description, operator_initials)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"calib_{uuid.uuid4().hex[:8]}",
            0,
            "0" * 64,  # calibration changes don't touch grammar.yaml
            at,
            change_type,
            description,
            None,
        ],
    )


def ensure_grammar_version_recorded(
    db: duckdb.DuckDBPyConnection,
    *,
    grammar: Grammar,
    yaml_path: Path,
    at: datetime,
) -> bool:
    """Write a `grammar_versions` audit row for `grammar.grammar_version` if missing.

    D051 (2026-05-18): bridges the hard-rule-#10 audit trail for MANUAL operator
    yaml bumps, which don't pass through `apply-proposal` / `revert` (the other
    write paths). The D035 stuck-state grammar-change floor reads
    `MAX(grammar_versions.changed_at)`; without this self-healing helper, a
    manual grammar bump (like D039's R3 v1→v2) never wrote a row, so the stuck
    counter never reset on the bump.

    Idempotent: if a row for `grammar.grammar_version` already exists, this is
    a SELECT-only no-op. Returns True if a row was written, False if one was
    already present.
    """
    rows = db.execute(
        "SELECT 1 FROM grammar_versions WHERE version = ?",
        [grammar.grammar_version],
    ).fetchall()
    if rows:
        return False
    yaml_bytes = yaml_path.read_bytes()
    sha = hashlib.sha256(yaml_bytes).hexdigest()
    db.execute(
        """
        INSERT INTO grammar_versions
            (version, rule_count, yaml_sha256, changed_at, change_type,
             change_description, operator_initials)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            grammar.grammar_version,
            len(grammar.rules),
            sha,
            at,
            "manual_bump",
            f"auto-recorded on first load post-bump for {grammar.grammar_version}",
            None,
        ],
    )
    return True


__all__ = ["ensure_grammar_version_recorded"]


def ensure_grammar_version_recorded_silently(
    forge_db_path: Path,
    *,
    grammar: object,
    yaml_path: Path,
) -> None:
    """D051: self-heal the grammar_versions audit row for the active grammar.

    Called after every live campaign submit (formerly at the start of every daemon iteration)
    submit (moved here from `cli/main.py`, Batch 5 prep). Idempotent — a SELECT-only
    no-op when the row already exists.
    Errors are swallowed (logged-by-omission rather than crashing the
    iteration) because this is the audit-trail, not a production-data path.
    """
    import typer  # noqa: PLC0415 — journal line, as before

    from forge.core.clock import utc_now  # noqa: PLC0415
    from forge.persistence.db import db_connection  # noqa: PLC0415

    try:
        with db_connection(forge_db_path) as conn:
            wrote = ensure_grammar_version_recorded(
                conn,
                grammar=grammar,  # type: ignore[arg-type]  # Grammar import is lazy
                yaml_path=yaml_path,
                at=utc_now(),
            )
        if wrote:
            typer.echo(
                f"grammar_versions: recorded manual_bump row for "
                f"{getattr(grammar, 'grammar_version', '?')}"
            )
    except Exception as exc:  # audit row, never crash production
        typer.echo(
            f"grammar_versions: skipped audit row ({type(exc).__name__}: {exc})",
            err=True,
        )
