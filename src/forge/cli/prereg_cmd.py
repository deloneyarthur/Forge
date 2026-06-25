"""`forge prereg` — pre-register a prune/retarget, then resolve it on a later cohort.

The honesty discipline (Tier-1a, D207): before tightening grammar, down-weighting a
family, or retargeting the ranker because a cohort showed a pattern, record the claim
WITH a cohort cut. Confirm it only on data that postdates the cut — never the cohort
that motivated it. Commit the registry line so the prediction is on record before its
test; git supplies the tamper-evidence.

This drives the registry in :mod:`forge.feedback.preregistration`. Resolution is
operator-supplied evidence (the operator runs the post-cut query) — the tested
`confirm_promotion_claim` guard is available programmatically for callers that can
express their predicate. Read/write of a git-tracked JSONL; nothing here touches the
production loop or the grammar.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import typer

from forge.core.clock import utc_now
from forge.feedback.preregistration import (
    Outcome,
    PreregEntry,
    append_preregistration,
    load_preregistrations,
    resolve_preregistration,
)

_DEFAULT_PATH = Path("config/preregistrations.jsonl")
_VALID_OUTCOMES = ("confirmed", "refuted", "insufficient")

prereg_app = typer.Typer(
    help="Pre-register prunes/retargets and confirm them on later cohorts (D207)."
)


def _prereg_id(claim: str, created_at: str) -> str:
    """Deterministic short id from the claim + its registration time (no RNG)."""
    return hashlib.sha256(f"{claim}|{created_at}".encode()).hexdigest()[:12]


@prereg_app.command("register")
def register(
    claim: str = typer.Option(..., "--claim", help="The predicted pattern, in words"),
    predicted: str = typer.Option(..., "--predicted", help="Predicted bound, e.g. '<= 0.005'"),
    action: str = typer.Option(..., "--action", help="What to do if the claim is confirmed"),
    metric: str = typer.Option("promotion_rate", "--metric", help="What is measured"),
    cohort_cut: str = typer.Option(
        "", "--cohort-cut", help="ISO cut; default=now. Only data AFTER this confirms the claim."
    ),
    path: Path = typer.Option(_DEFAULT_PATH, "--path", help="Registry JSONL (git-tracked)"),
) -> None:
    """Record a claim BEFORE its confirming data exists."""
    created_at = utc_now().isoformat()
    cut = cohort_cut or created_at
    entry = PreregEntry(
        prereg_id=_prereg_id(claim, created_at),
        created_at=created_at,
        claim=claim,
        metric=metric,
        predicted=predicted,
        cohort_cut=cut,
        action_if_confirmed=action,
        status="registered",
        resolved_at=None,
        evidence=None,
    )
    append_preregistration(path, entry)
    typer.echo(f"registered {entry.prereg_id}: {claim}  (cohort_cut={cut})")
    typer.echo(f"  commit {path} so the prediction is recorded before its test.")


@prereg_app.command("list")
def list_(
    path: Path = typer.Option(_DEFAULT_PATH, "--path", help="Registry JSONL"),
    open_only: bool = typer.Option(False, "--open-only", help="Only unresolved entries"),
) -> None:
    """List pre-registrations (newest decisions are appended last)."""
    entries = load_preregistrations(path)
    if open_only:
        entries = [e for e in entries if e.status == "registered"]
    if not entries:
        typer.echo("(no pre-registrations)")
        return
    for e in entries:
        typer.echo(f"[{e.status:<11}] {e.prereg_id}  cut={e.cohort_cut[:16]}  {e.claim}")
        if e.evidence:
            typer.echo(f"      evidence: {e.evidence}")


@prereg_app.command("resolve")
def resolve(
    prereg_id: str = typer.Argument(..., help="ID from `forge prereg list`"),
    outcome: str = typer.Option(..., "--outcome", help="confirmed | refuted | insufficient"),
    evidence: str = typer.Option(
        ..., "--evidence", help="Post-cut measurement, e.g. 'rate 0.002 (n=120)'"
    ),
    path: Path = typer.Option(_DEFAULT_PATH, "--path", help="Registry JSONL"),
) -> None:
    """Resolve a claim using POST-CUT evidence only (the discipline you registered)."""
    if outcome not in _VALID_OUTCOMES:
        typer.echo(f"invalid --outcome {outcome!r}; use {' | '.join(_VALID_OUTCOMES)}", err=True)
        raise typer.Exit(code=2)
    try:
        updated = resolve_preregistration(
            path,
            prereg_id,
            outcome=cast(Outcome, outcome),
            evidence=evidence,
            resolved_at=utc_now().isoformat(),
        )
    except KeyError as exc:
        typer.echo(f"no pre-registration {prereg_id!r} in {path}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"{updated.prereg_id} -> {updated.status}")


__all__ = ["prereg_app"]
