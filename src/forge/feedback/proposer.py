"""§8.4 proposer — three trigger types over an AnalysisReport + BatchFeedback.

D024/D3: ships all three trigger types from §8.4:
  (a) gate-failure concentration: any gate failing 95%+ of rejected
      candidates -> tighten pre-filter calibration.
  (b) family / hypothesis dominance: an 80%+-dominant promoted pattern
      -> tighten grammar (hypothesis) or ranker weights (family).
  (c) param no-promotion: a (hypothesis, dte_bucket) cell with N+ samples
      and 0 promotions -> tighten grammar param range.

For Phase 5, trigger (c) reads the current batch only. The §8.4 spirit
("0 promotions in 200+ submissions") needs cross-batch history; Phase 6
will extend by sampling submissions across the last K batches.

All proposals are tighten-direction. Loosening is reserved for the
`auto_tune` module (calibration loosening writes to OPEN_PROPOSALS.md
and never auto-applies — hard rule #4).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from forge.feedback.types import GrammarProposal

if TYPE_CHECKING:
    from datetime import datetime

    from forge.feedback.types import (
        AnalysisReport,
        BatchFeedback,
        CandidateOutcome,
        GateFailureRow,
        PromotedPattern,
    )


_GATE_FAILURE_THRESHOLD: float = 0.95
_DOMINANCE_MIN_PROMOTED: int = 4
_PARAM_NO_PROMOTION_MIN_SAMPLES: int = 200


def _proposal_from_gate_failure(
    row: GateFailureRow,
    *,
    at: datetime,
) -> GrammarProposal:
    rationale = (
        f"{row.failure_count} of all rejected candidates failed `{row.gate_name}` "
        f"({row.failure_rate:.0%}); propose tightening the pre-filter that "
        "catches this earlier."
    )
    yaml_snippet = (
        f"# Proposed tightening — pre-filter for {row.gate_name}\n"
        f"# Triggered by failure_rate={row.failure_rate:.2f}\n"
    )
    return GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=at,
        proposal_type="tighten",
        target="prefilter_calibration",
        proposal_yaml=yaml_snippet,
        rationale=rationale,
        evidence_json={
            "trigger": "gate_failure_concentration",
            "target": row.gate_name,
            "failure_count": row.failure_count,
            "failure_rate": row.failure_rate,
        },
    )


def _proposals_from_gate_failures(
    report: AnalysisReport,
    *,
    at: datetime,
) -> list[GrammarProposal]:
    return [
        _proposal_from_gate_failure(row, at=at)
        for row in report.gate_failures
        if row.failure_rate >= _GATE_FAILURE_THRESHOLD
    ]


def _proposal_from_hypothesis_pattern(
    pattern: PromotedPattern,
    *,
    at: datetime,
) -> GrammarProposal:
    hypothesis = str(pattern.pattern.get("hypothesis"))
    rationale = (
        f"{pattern.promoted_count} of {pattern.sample_size} promoted strategies "
        f"used hypothesis `{hypothesis}` ({pattern.dominance_rate:.0%}); "
        "propose tightening enumeration to favor this hypothesis."
    )
    yaml_snippet = (
        f"# Proposed grammar tightening — favor hypothesis `{hypothesis}`\n"
        f"# Triggered by dominance_rate={pattern.dominance_rate:.2f}\n"
    )
    return GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=at,
        proposal_type="tighten",
        target="grammar",
        proposal_yaml=yaml_snippet,
        rationale=rationale,
        evidence_json={
            "trigger": "hypothesis_dominance",
            "hypothesis": hypothesis,
            "promoted_count": pattern.promoted_count,
            "sample_size": pattern.sample_size,
        },
    )


def _proposal_from_family_pattern(
    pattern: PromotedPattern,
    *,
    at: datetime,
) -> GrammarProposal:
    family = str(pattern.pattern.get("family"))
    rationale = (
        f"{pattern.promoted_count} of {pattern.sample_size} promoted strategies "
        f"used directional family `{family}` ({pattern.dominance_rate:.0%}); "
        "propose re-weighting the ranker toward this family."
    )
    yaml_snippet = (
        f"# Proposed ranker re-weighting — favor family `{family}`\n"
        f"# Triggered by dominance_rate={pattern.dominance_rate:.2f}\n"
    )
    return GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=at,
        proposal_type="tighten",
        target="ranker_weights",
        proposal_yaml=yaml_snippet,
        rationale=rationale,
        evidence_json={
            "trigger": "family_dominance",
            "family": family,
            "promoted_count": pattern.promoted_count,
            "sample_size": pattern.sample_size,
        },
    )


def _proposals_from_patterns(
    report: AnalysisReport,
    *,
    at: datetime,
) -> list[GrammarProposal]:
    out: list[GrammarProposal] = []
    for pat in report.promoted_patterns:
        if pat.promoted_count < _DOMINANCE_MIN_PROMOTED:
            continue
        if pat.pattern_type == "hypothesis_dominance":
            out.append(_proposal_from_hypothesis_pattern(pat, at=at))
        elif pat.pattern_type == "signal_family_dominance":
            out.append(_proposal_from_family_pattern(pat, at=at))
    return out


def _proposals_from_param_history(
    feedback: BatchFeedback,
    *,
    at: datetime,
) -> list[GrammarProposal]:
    """Trigger (c): find (hypothesis, dte_bucket) cells with N+ samples
    and 0 promotions. For Phase 5 the window is the current batch only."""
    cells: dict[tuple[str, str], list[CandidateOutcome]] = {}
    for o in feedback.outcomes:
        key = (str(o.config.hypothesis), str(o.config.dte_bucket))
        cells.setdefault(key, []).append(o)

    out: list[GrammarProposal] = []
    for (hypothesis, dte_bucket), outs in cells.items():
        if len(outs) < _PARAM_NO_PROMOTION_MIN_SAMPLES:
            continue
        if any(o.promoted for o in outs):
            continue
        rationale = (
            f"0 of {len(outs)} ({hypothesis}, {dte_bucket}) candidates promoted; "
            "propose tightening grammar to skip this cell."
        )
        yaml_snippet = (
            f"# Proposed grammar tightening — remove ({hypothesis}, {dte_bucket}) cell\n"
            f"# Triggered by samples={len(outs)}, promoted=0\n"
        )
        out.append(
            GrammarProposal(
                proposal_id=uuid.uuid4(),
                proposed_at=at,
                proposal_type="tighten",
                target="grammar",
                proposal_yaml=yaml_snippet,
                rationale=rationale,
                evidence_json={
                    "trigger": "param_no_promotion",
                    "hypothesis": hypothesis,
                    "dte_bucket": dte_bucket,
                    "sample_size": len(outs),
                },
            )
        )
    return out


def propose(
    report: AnalysisReport,
    feedback: BatchFeedback,
    *,
    at: datetime,
) -> list[GrammarProposal]:
    """Run all three §8.4 triggers against the report + feedback."""
    if at.tzinfo is None:
        msg = "propose: `at` must be timezone-aware"
        raise ValueError(msg)
    proposals: list[GrammarProposal] = []
    proposals.extend(_proposals_from_gate_failures(report, at=at))
    proposals.extend(_proposals_from_patterns(report, at=at))
    proposals.extend(_proposals_from_param_history(feedback, at=at))
    return proposals


__all__ = ["propose"]
