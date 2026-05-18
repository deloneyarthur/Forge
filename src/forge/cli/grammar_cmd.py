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
    """Mark a proposal as approved (operator audit row).

    This command does NOT auto-mutate `config/grammar.yaml`. The actual
    yaml edit, version bump, archive, and Decision Log entry stay manual
    so each grammar change crosses the §13.2 review boundary intentionally
    (hard rule #10). After approval, the operator edits the yaml directly
    and the pre-commit hook enforces the four-step contract.
    """
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


@grammar_app.command("apply-proposal")
def cmd_apply_proposal(
    proposal_id: str = typer.Option(..., "--id", help="proposal UUID to apply"),
    initials: str = typer.Option(..., "--initials", help="operator initials for audit"),
    forge_db: Path = typer.Option(Path(":memory:"), "--forge-db", help="Forge state DB"),
    prefilter_yaml: Path = typer.Option(
        Path("config/prefilter.yaml"),
        "--prefilter-yaml",
        help="path to prefilter.yaml (target=prefilter_calibration proposals)",
    ),
) -> None:
    """Apply a pending proposal — yaml edit + audit row + grammar_versions entry.

    The §13.2 contract for a prefilter_calibration tighten is: (1) edit
    prefilter.yaml with the new threshold values; (2) record the
    operator's approval in `grammar_proposals.decided_by`; (3) append
    a `grammar_versions` row for the audit trail. `approve-proposal`
    only does step 2. This command does all three atomically, the same
    way `auto_tune` does for its own auto-applied tightens — reusing
    `propose_adjustment` + `apply_tightening` for the actual delta.

    Today only `target=prefilter_calibration` proposals are supported.
    `target=grammar` proposals stay manual (operator edits
    `config/grammar.yaml` directly) because the changes there are too
    structurally varied for a single CLI shape.
    """
    import json

    from forge.core.clock import utc_now
    from forge.feedback.auto_tune import _write_grammar_versions_row, write_calibration_yaml
    from forge.prefilters.calibration import (
        apply_tightening,
        load_calibration,
        propose_adjustment,
    )

    # Proposals whose evidence_json.trigger lands in this set route to the
    # prefilter_calibration tighten path (parsed prefilter.yaml, 10% step,
    # write back). Other triggers (e.g., 'hypothesis_dominance') target the
    # grammar yaml itself and stay on the manual §13.2 path.
    supported_triggers = {"gate_failure_concentration"}

    if not initials.strip():
        typer.echo("error: --initials must be non-empty", err=True)
        raise typer.Exit(code=2)
    pid = uuid.UUID(proposal_id)
    now = utc_now()
    with db_connection(forge_db) as conn:
        row = conn.execute(
            """
            SELECT proposal_type, status, evidence_json
            FROM grammar_proposals
            WHERE proposal_id = ?
            """,
            [str(pid)],
        ).fetchone()
        if row is None:
            typer.echo(f"error: proposal {pid} not found", err=True)
            raise typer.Exit(code=1)
        proposal_type, status, evidence_raw = row
        if status not in ("pending", "approved"):
            typer.echo(
                f"error: proposal {pid} status={status!r} — must be pending or approved",
                err=True,
            )
            raise typer.Exit(code=1)
        if proposal_type != "tighten":
            # Loosens stay on the manual path — hard rule #4 + §13.2 reserve
            # loosening for an explicit, narrowly-scoped operator yaml edit.
            typer.echo(
                f"error: apply-proposal supports proposal_type='tighten' only; "
                f"got {proposal_type!r}. Edit {prefilter_yaml.name} manually "
                "for loosens.",
                err=True,
            )
            raise typer.Exit(code=1)
        evidence: dict[str, object] = (
            json.loads(evidence_raw) if isinstance(evidence_raw, str) else (evidence_raw or {})
        )
        trigger = evidence.get("trigger")
        if trigger not in supported_triggers:
            typer.echo(
                f"error: apply-proposal does not yet support trigger={trigger!r} "
                f"(supported: {sorted(supported_triggers)}). Edit "
                f"{prefilter_yaml.name} or config/grammar.yaml manually.",
                err=True,
            )
            raise typer.Exit(code=1)
        if not prefilter_yaml.exists():
            typer.echo(f"error: prefilter yaml missing: {prefilter_yaml}", err=True)
            raise typer.Exit(code=1)
        calibration = load_calibration(prefilter_yaml)
        adjustment = propose_adjustment(
            calibration,
            direction="tighten",
            reason=f"manual apply-proposal {pid} by {initials}",
        )
        new_cal = apply_tightening(calibration, adjustment)
        write_calibration_yaml(new_cal, prefilter_yaml)
        _write_grammar_versions_row(
            conn,
            change_type="manual_tighten_calibration",
            description=(
                f"step_pct={calibration.auto_tune.adjustment_pct_per_step:.4f} "
                f"applied_via=apply-proposal proposal_id={pid}"
            ),
            at=now,
        )
        conn.execute(
            """
            UPDATE grammar_proposals
            SET status = 'applied', decided_at = ?, decided_by = ?
            WHERE proposal_id = ?
            """,
            [now, initials, str(pid)],
        )
    typer.echo(
        f"proposal {pid} -> applied (by {initials}); "
        f"{prefilter_yaml.name} tightened by "
        f"{calibration.auto_tune.adjustment_pct_per_step:.0%}"
    )


@grammar_app.command("revert")
def cmd_revert(
    to_version: str = typer.Option(
        ...,
        "--to-version",
        help="prior archived grammar_version to revert to (e.g., 'v1')",
    ),
    initials: str = typer.Option(..., "--initials", help="operator initials for audit"),
    forge_db: Path = typer.Option(Path(":memory:"), "--forge-db", help="Forge state DB"),
    grammar_yaml: Path = typer.Option(
        Path("config/grammar.yaml"),
        "--grammar-yaml",
        help="path to current grammar.yaml",
    ),
    archive_dir: Path = typer.Option(
        Path("config/grammar_archive"),
        "--archive-dir",
        help="directory of archived grammar versions",
    ),
) -> None:
    """T2.2 (PROMPT_5_FORGE_V1_1_REVISED / Draft Enhancement 7) — revert
    grammar.yaml to a prior archived version by promoting it forward as
    a new bumped version.

    Mechanics:
      1. Read `<archive_dir>/<to_version>.yaml`.
      2. Validate it loads cleanly (rejects malformed archive entries).
      3. Compute new version string = max(existing_versions) + 1.
      4. Write the prior content (with the new grammar_version field
         substituted in) to `grammar.yaml`.
      5. Archive the new version (preserves the audit trail — the bad
         version stays in `archive/` for forensics).
      6. Append a `grammar_versions` row to forge_db tagged as 'revert'.
      7. Print a reminder for the operator to log the rationale in
         `IMPLEMENTATION_DECISIONS.md`.

    Why "increment forward" instead of overwrite: hard rule #10's
    archive contract is "every grammar_version maps to a fixed file".
    Overwriting v2.yaml with v1's content would corrupt the audit
    trail. Bumping to v3 (= v1's content with the v3 label) keeps the
    history complete and the corrupted v2 recoverable.
    """
    import re

    from forge.feedback.auto_tune import _write_grammar_versions_row
    from forge.grammar import load_grammar
    from forge.grammar.archive import (
        archive_grammar,
        find_archived_grammar,
        list_archived_versions,
    )

    if not initials.strip():
        typer.echo("error: --initials must be non-empty", err=True)
        raise typer.Exit(code=2)

    prior_path = find_archived_grammar(to_version, archive_dir)
    if prior_path is None:
        typer.echo(
            f"error: no archive entry for version {to_version!r} in "
            f"{archive_dir}. Available: {list_archived_versions(archive_dir)}",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        load_grammar(prior_path, archive_dir=archive_dir)
    except Exception as exc:
        typer.echo(
            f"error: archived grammar {to_version} failed validation: {exc}",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # Compute new version: max(v{N}) + 1. Skips non-numeric tags.
    nums: list[int] = []
    for v in list_archived_versions(archive_dir):
        if v.startswith("v") and v[1:].isdigit():
            nums.append(int(v[1:]))
    new_version_num = (max(nums) + 1) if nums else 1
    new_version = f"v{new_version_num}"

    if new_version == to_version:
        typer.echo(
            f"error: refusing no-op revert (to_version={to_version} == "
            f"new_version={new_version}). Did you mean a different "
            f"--to-version?",
            err=True,
        )
        raise typer.Exit(code=1)

    prior_content = prior_path.read_text(encoding="utf-8")
    new_content = re.sub(
        r"^grammar_version:\s*\S+\s*$",
        f"grammar_version: {new_version}",
        prior_content,
        count=1,
        flags=re.MULTILINE,
    )
    now = utc_now()
    header = (
        f"# REVERT: this version's content is identical to {to_version}.\n"
        f"# Promoted forward to {new_version} via `forge grammar revert "
        f"--to-version {to_version}` by {initials} at {now.isoformat()}.\n"
        f"# See IMPLEMENTATION_DECISIONS.md for the operator rationale.\n\n"
    )
    grammar_yaml.write_text(header + new_content, encoding="utf-8")

    archive_grammar(grammar_yaml, archive_dir, new_version)

    with db_connection(forge_db) as conn:
        _write_grammar_versions_row(
            conn,
            change_type="revert",
            description=(
                f"reverted to {to_version} content as new {new_version}; "
                f"operator={initials}"
            ),
            at=now,
        )

    typer.echo(
        f"grammar.yaml reverted: {to_version} content promoted to "
        f"{new_version}. Reminder: add a D-entry to "
        f"IMPLEMENTATION_DECISIONS.md with the operator's rationale "
        f"for the revert."
    )


__all__ = ["grammar_app"]
