"""Tests for `forge.grammar.version_audit` — the grammar_versions provenance trail.

D051: `ensure_grammar_version_recorded` self-heals the hard-rule-#10 audit row for
a MANUAL grammar bump (the common path). Extracted (D325) from the retired
`feedback.auto_tune` module tests — the §5.5 auto-tune trigger these once shared a
file with was dead and removed; the provenance writer is the live remainder.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from forge.grammar.version_audit import ensure_grammar_version_recorded
from forge.persistence.db import db_connection

_AT = datetime(2026, 5, 13, 12, tzinfo=UTC)


def _real_grammar() -> tuple[object, Path]:
    """Load the project's actual `config/grammar.yaml` for D051 tests.

    The helper needs a real `Grammar` object (with `grammar_version` +
    `rules`) and the matching on-disk yaml file for the sha256 hash.
    Using the production yaml keeps the test honest — if the grammar
    archive becomes inconsistent, this test fails alongside the loader.
    """
    from forge.grammar import load_grammar

    yaml_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = yaml_path.parent / "grammar_archive"
    grammar = load_grammar(yaml_path, archive_dir=archive_dir)
    return grammar, yaml_path


def test_ensure_grammar_version_writes_row_when_missing(tmp_path: Path) -> None:
    """D051: an empty `grammar_versions` table gets a `manual_bump` row
    matching the active grammar on first call."""
    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    with db_connection(forge_db) as conn:
        # Pre-condition: table is empty.
        rows = conn.execute("SELECT COUNT(*) FROM grammar_versions").fetchone()
        assert rows[0] == 0
        wrote = ensure_grammar_version_recorded(
            conn,
            grammar=grammar,
            yaml_path=yaml_path,
            at=_AT,
        )
        assert wrote is True
        # Post-condition: exactly one row, matching the active grammar.
        result = conn.execute(
            "SELECT version, change_type, rule_count, yaml_sha256 FROM grammar_versions"
        ).fetchall()
    assert len(result) == 1
    version, change_type, rule_count, sha = result[0]
    assert str(version) == grammar.grammar_version
    assert str(change_type) == "manual_bump"
    assert int(rule_count) == len(grammar.rules)
    # sha256 is 64 lowercase hex chars and matches the on-disk yaml.
    import hashlib

    expected_sha = hashlib.sha256(yaml_path.read_bytes()).hexdigest()
    assert str(sha) == expected_sha


def test_ensure_grammar_version_is_idempotent(tmp_path: Path) -> None:
    """D051: a second call after the row exists is a SELECT-only no-op."""
    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    with db_connection(forge_db) as conn:
        first = ensure_grammar_version_recorded(conn, grammar=grammar, yaml_path=yaml_path, at=_AT)
        second = ensure_grammar_version_recorded(conn, grammar=grammar, yaml_path=yaml_path, at=_AT)
        count = conn.execute("SELECT COUNT(*) FROM grammar_versions").fetchone()
    assert first is True
    assert second is False
    assert count[0] == 1


def test_ensure_grammar_version_skips_when_existing_row_present(tmp_path: Path) -> None:
    """D051: an existing row for the active grammar (e.g. written by an earlier
    apply-proposal) is left intact — the self-healing helper never overwrites."""
    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    with db_connection(forge_db) as conn:
        conn.execute(
            """
            INSERT INTO grammar_versions
                (version, rule_count, yaml_sha256, changed_at, change_type,
                 change_description, operator_initials)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                grammar.grammar_version,
                42,
                "f" * 64,
                _AT,
                "apply_proposal",
                "explicit operator-driven entry",
                "AJ",
            ],
        )
        wrote = ensure_grammar_version_recorded(conn, grammar=grammar, yaml_path=yaml_path, at=_AT)
        rows = conn.execute(
            "SELECT change_type, rule_count, operator_initials FROM grammar_versions"
        ).fetchall()
    assert wrote is False
    assert len(rows) == 1
    change_type, rule_count, initials = rows[0]
    # The pre-existing row is untouched — not overwritten with manual_bump.
    assert str(change_type) == "apply_proposal"
    assert int(rule_count) == 42
    assert str(initials) == "AJ"


def test_d058_ensure_grammar_version_no_duplicate_under_concurrent_writers(
    tmp_path: Path,
) -> None:
    """D058 / P3-3: two concurrent processes (autonomous loop +
    operator-driven `cmd_apply_proposal`/`cmd_revert`) could in principle
    both observe an empty `grammar_versions` table for the active version,
    then both INSERT — producing two rows. The `version VARCHAR(20)
    PRIMARY KEY` constraint catches that and raises ConstraintException
    on the loser's INSERT. This test pins the contract:

      Outcome A — winner-loser sequence: exactly one row lands; the
      loser either returns False (SELECT-then-INSERT but the row exists)
      OR raises a ConstraintException (race on INSERT). Either way the
      DB stays consistent.

      Outcome B — table never grows beyond 1 row for the version.

    Pre-D058 the helper had no race-condition test — D051's idempotency
    test was sequential. A future refactor that switched from
    SELECT-then-INSERT to a different idempotency mechanism (e.g.,
    INSERT-OR-IGNORE) would risk silently dropping the audit row; this
    test ensures the contract holds whichever mechanism is chosen.
    """
    import threading

    import duckdb

    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    # Initialize schema with one ephemeral connection so concurrent
    # writers don't race on schema creation.
    with db_connection(forge_db):
        pass

    barrier = threading.Barrier(2)
    results: list[tuple[bool | None, str | None]] = [(None, None), (None, None)]

    def _worker(idx: int) -> None:
        try:
            conn = duckdb.connect(str(forge_db))
            try:
                barrier.wait(timeout=5.0)
                wrote = ensure_grammar_version_recorded(
                    conn,
                    grammar=grammar,
                    yaml_path=yaml_path,
                    at=_AT,
                )
                results[idx] = (wrote, None)
            finally:
                conn.close()
        except duckdb.ConstraintException as exc:
            results[idx] = (None, f"constraint: {exc}")
        except duckdb.Error as exc:
            results[idx] = (None, f"duckdb: {exc}")

    t0 = threading.Thread(target=_worker, args=(0,))
    t1 = threading.Thread(target=_worker, args=(1,))
    t0.start()
    t1.start()
    t0.join(timeout=10.0)
    t1.join(timeout=10.0)

    with db_connection(forge_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM grammar_versions WHERE version = ?",
            [grammar.grammar_version],
        ).fetchone()[0]
    assert count == 1, f"expected exactly 1 row for {grammar.grammar_version}, got {count}"
    # At least one writer succeeded (wrote=True OR rolled-back via
    # ConstraintException). Both returning (False, None) would mean
    # neither thought it needed to insert — which only happens if the
    # row already existed when both started, contradicting our fresh-db
    # setup.
    saw_success = any(r[0] is True for r in results)
    saw_constraint = any(r[1] is not None and "constraint" in r[1] for r in results)
    saw_loser_noop = any(r[0] is False for r in results)
    assert saw_success, f"no writer reported success: {results}"
    assert saw_constraint or saw_loser_noop, (
        f"expected one writer to either skip (False) or hit constraint, got: {results}"
    )
