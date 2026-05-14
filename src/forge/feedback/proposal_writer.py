"""Append refinement proposals to OPEN_PROPOSALS.md + grammar_proposals (§9.1).

D024/D5: every Phase 5 proposal (tighten or loosen) is appended to
`OPEN_PROPOSALS.md` as a `---`-delimited markdown block AND inserted into
the `grammar_proposals` table with `status='pending'`. The two writes are
the audit pair: humans read the markdown; downstream code reads the table.

Structurally there is NO `apply_loosening` function in this module —
loosenings only flow through `OPEN_PROPOSALS.md` and the operator's
`forge grammar apply-proposal` (Phase 5 module 12). This mirrors the
analogue in `forge.prefilters.calibration` where `apply_tightening` exists
but `apply_loosening` does not (hard rule #4).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

    from forge.feedback.types import GrammarProposal


def _format_markdown_block(proposal: GrammarProposal) -> str:
    evidence_str = json.dumps(proposal.evidence_json, sort_keys=True)
    return (
        "\n---\n"
        f"- proposal_id: {proposal.proposal_id}\n"
        f"- proposed_at: {proposal.proposed_at.isoformat()}\n"
        f"- proposal_type: {proposal.proposal_type}\n"
        f"- target: {proposal.target}\n"
        f"- rationale: {proposal.rationale}\n"
        f"- evidence_json: {evidence_str}\n"
        "- proposal_yaml: |\n"
        + "\n".join(f"    {line}" for line in proposal.proposal_yaml.splitlines())
        + "\n"
    )


def _insert_grammar_proposals_row(
    db: duckdb.DuckDBPyConnection,
    proposal: GrammarProposal,
) -> None:
    db.execute(
        """
        INSERT INTO grammar_proposals
            (proposal_id, proposed_at, proposal_type, proposal_yaml,
             rationale, evidence_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(proposal.proposal_id),
            proposal.proposed_at,
            proposal.proposal_type,
            proposal.proposal_yaml,
            proposal.rationale,
            json.dumps(proposal.evidence_json, sort_keys=True),
            "pending",
        ],
    )


def _has_identical_pending_proposal(
    db: duckdb.DuckDBPyConnection,
    proposal: GrammarProposal,
) -> bool:
    """True if a pending proposal with identical (type, rationale) already exists.

    The auto-tune trigger fires once per batch (§8.4); without dedup, every
    batch where the rolling promotion rate stays below threshold appends a
    new proposal. The semantics are identical — same target, same proposed
    adjustment — so writing each one separately just floods
    OPEN_PROPOSALS.md without surfacing new operator information.

    Match key: `proposal_type + rationale + status='pending'`. Two proposals
    with the same type and rationale convey the same operator-decision-
    needed event; the rationale already encodes the target + magnitude.
    Once the operator decides (approve / reject), the pending row exits
    this match and a fresh proposal can be written.
    """
    row = db.execute(
        """
        SELECT 1 FROM grammar_proposals
        WHERE proposal_type = ?
          AND rationale = ?
          AND status = 'pending'
        LIMIT 1
        """,
        [proposal.proposal_type, proposal.rationale],
    ).fetchone()
    return row is not None


def append_proposal(
    proposal: GrammarProposal,
    *,
    open_proposals_path: Path,
    db: duckdb.DuckDBPyConnection,
) -> bool:
    """Append the proposal to OPEN_PROPOSALS.md and insert a pending row.

    Returns ``True`` when the proposal was written, ``False`` when it was
    skipped because an identical pending proposal already exists. The
    skip-write is the structural prevention of OPEN_PROPOSALS.md flooding
    (§8.4 trigger fires every batch; without dedup, an idle weekend
    accumulates 1000+ identical entries).
    """
    if _has_identical_pending_proposal(db, proposal):
        return False
    open_proposals_path.parent.mkdir(parents=True, exist_ok=True)
    block = _format_markdown_block(proposal)
    with open_proposals_path.open("a", encoding="utf-8") as fh:
        fh.write(block)
    _insert_grammar_proposals_row(db, proposal)
    return True


__all__ = ["append_proposal"]
