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
