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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from forge.feedback.types import GrammarProposal

if TYPE_CHECKING:
    from collections.abc import Sequence
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


def compute_confidence(sample_size: int) -> float:
    """T2.1 / D041 — coarse confidence step function over evidence sample size.

    Returns a value in [0.0, 1.0]:
      - sample_size < 20:    confidence = 0.1  (very low — likely noise)
      - 20 <= sample_size < 100: linear ramp 0.3 → 0.7
      - sample_size >= 100:  linear ramp 0.7 → 1.0 over the next 400 samples

    The draft (PROMPT_5_FORGE_V1_1_DRAFT.md §Enhancement 6) describes a
    Wilson-interval lower bound; this step function is a faster
    approximation that delivers the same operator-facing semantics
    (confidence flag visible; T2.3 uses >= 0.7 as the auto-apply gate).
    A full Wilson interval can replace this if a future analysis shows
    the step approximation is too coarse — same call site.
    """
    if sample_size < 0:
        msg = f"sample_size must be >= 0, got {sample_size}"
        raise ValueError(msg)
    if sample_size < 20:
        return 0.1
    if sample_size < 100:
        return 0.3 + 0.4 * (sample_size - 20) / 80
    return min(1.0, 0.7 + 0.3 * (sample_size - 100) / 400)


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
    # T2.1: sample size = how many candidates failed this gate.
    sample_size = int(row.failure_count)
    confidence = compute_confidence(sample_size)
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
            "sample_size": sample_size,
            "confidence": confidence,
        },
        sample_size=sample_size,
        confidence=confidence,
    )


def _proposals_from_gate_failures(
    report: AnalysisReport,
    feedback: BatchFeedback,
    *,
    at: datetime,
) -> list[GrammarProposal]:
    """Gate-failure-concentration trigger.

    D034 guard: only fire when `feedback.promoted_count > 0`. In a
    0-promotion regime EVERY gate has 100% failure rate against rejects;
    the trigger becomes degenerate noise that just floods
    OPEN_PROPOSALS.md with one tighten-proposal per gate per batch.
    The signal is only informative when SOME candidates pass — then a
    gate that fails 95%+ of the remaining rejects (while letting the
    promoted ones through) is a real "tighten the pre-filter earlier"
    candidate.
    """
    if feedback.promoted_count == 0:
        return []
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
    sample_size = int(pattern.sample_size)
    confidence = compute_confidence(sample_size)
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
            "sample_size": sample_size,
            "confidence": confidence,
        },
        sample_size=sample_size,
        confidence=confidence,
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
    sample_size = int(pattern.sample_size)
    confidence = compute_confidence(sample_size)
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
            "sample_size": sample_size,
            "confidence": confidence,
        },
        sample_size=sample_size,
        confidence=confidence,
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
        sample_size = len(outs)
        confidence = compute_confidence(sample_size)
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
                    "sample_size": sample_size,
                    "confidence": confidence,
                },
                sample_size=sample_size,
                confidence=confidence,
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
    proposals.extend(_proposals_from_gate_failures(report, feedback, at=at))
    proposals.extend(_proposals_from_patterns(report, at=at))
    proposals.extend(_proposals_from_param_history(feedback, at=at))
    return proposals


# D053 — phase identifiers for `CounterfactualResult.phase`. Phase-1 is the
# binary safety floor (any-promotions → escalate); phase-2 is the per-strategy
# re-validation (P1-1 option b — deferred). When phase-2 lands, the function
# body changes; consumers reading `evidence_json["counterfactual_phase"]` can
# tell which signal they're looking at without reading source.
PHASE_1_BINARY = "1_binary_safety_floor"
PHASE_2_PER_STRATEGY = "2_per_strategy_revalidation"

# Human-readable disclaimer written alongside the phase identifier so
# operators reading raw evidence_json see the limitation without having
# to know the codebase. Keep in sync with `evaluate_counterfactual`'s
# docstring.
COUNTERFACTUAL_PHASE_1_NOTE = (
    "phase-1 binary safety floor: rejection_rate is a worst-case "
    "assumption (1.0 if any recent promotion, 0.0 otherwise), not a "
    "per-strategy measurement. Implements draft Enhancement 8 phase 1."
)


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    """T2.3 / D044 — result of a counterfactual evaluation against
    the proposal's effect on prior promoted strategies.

    D053: `phase` identifies which evaluation implementation produced
    the result. Phase-1 is the binary safety floor (current default);
    phase-2 will be per-strategy re-validation once `submissions.config_json`
    history queries are wired (draft Enhancement 8 phase 2).
    """

    promoted_count: int
    would_be_rejected_count: int
    rejection_rate: float
    would_be_rejected_ids: tuple[str, ...] = ()
    phase: str = PHASE_1_BINARY


def evaluate_counterfactual(
    proposal: GrammarProposal,
    recent_promoted_count: int,
) -> CounterfactualResult:
    """T2.3 / D044 — would applying ``proposal`` regress any promoted
    strategy?

    Phase 1 (framework, current): coarse rejection-rate estimate from raw
    promotion count. The full per-strategy re-validation (draft
    Enhancement 8 phase 2) requires re-running the pre-filter battery
    against each promoted strategy's historical activations — deferred
    P1-1 option (b). When that lands, replace the body and bump the
    returned `phase` to `PHASE_2_PER_STRATEGY`.

    Conservative phase-1 interpretation:
    - 0 promoted → 0.0 rejection_rate, safe.
    - >0 promoted → 1.0 rejection_rate (worst-case assumption); the
      caller's `should_auto_apply_proposal` will escalate to operator
      review.

    D053: the result carries `phase=PHASE_1_BINARY` so the call site
    can stamp evidence_json with structured phase metadata; operators
    reading proposals know the rejection_rate is a binary safety floor,
    not a real measurement.
    """
    del proposal  # phase-1 framework doesn't use the proposal's specifics
    if recent_promoted_count == 0:
        return CounterfactualResult(
            promoted_count=0,
            would_be_rejected_count=0,
            rejection_rate=0.0,
            phase=PHASE_1_BINARY,
        )
    return CounterfactualResult(
        promoted_count=recent_promoted_count,
        # Worst-case: we conservatively assume any tightening could
        # affect promoted strategies until the per-strategy check is wired.
        would_be_rejected_count=recent_promoted_count,
        rejection_rate=1.0,
        phase=PHASE_1_BINARY,
    )


def should_auto_apply_proposal(
    proposal: GrammarProposal,
    counterfactual: CounterfactualResult,
    *,
    min_confidence: float = 0.7,
) -> tuple[bool, str | None]:
    """T2.3 / D044 — decision gate for any future auto-apply path.

    Returns ``(should_apply, escalation_reason)``. Today no caller
    auto-applies proposer-generated proposals (operator runs
    `forge grammar apply-proposal`); this function is the framework
    a future auto-apply path consumes.

    Decision rule (per draft Enhancement 8):
    1. ``counterfactual.rejection_rate > 0.0`` → escalate (would harm
       a promoted strategy).
    2. ``proposal.confidence < min_confidence`` → escalate (insufficient
       evidence; sample too small to act on without operator review).
    3. Otherwise: safe to auto-apply.
    """
    if counterfactual.rejection_rate > 0.0:
        return (
            False,
            f"counterfactual: would reject {counterfactual.would_be_rejected_count} "
            f"of {counterfactual.promoted_count} recent promoted strategies",
        )
    if proposal.confidence < min_confidence:
        return (
            False,
            f"confidence={proposal.confidence:.2f} below auto-apply threshold "
            f"{min_confidence:.2f}",
        )
    return (True, None)


# ---------------------------------------------------------------------------
# T2.4 / D045 — persistent proposal detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PersistentProposal:
    """T2.4 — a proposal "theme" (proposal_type + trigger + detail) that
    has appeared across multiple batches without being applied. Escalated
    to operators with stronger urgency than a single-batch proposal."""

    theme_trigger: str
    theme_detail: str
    occurrence_count: int
    proposal_ids: tuple[str, ...]


_PERSISTENT_THRESHOLD: int = 3


def detect_persistent_proposals(
    proposals: Sequence[GrammarProposal],
    *,
    min_occurrences: int = _PERSISTENT_THRESHOLD,
) -> list[PersistentProposal]:
    """T2.4 / D045 — find proposal "themes" that have appeared in
    ``min_occurrences`` or more recent proposals.

    Theme = ``(evidence.trigger, evidence.target | hypothesis | family)``
    — same dedup key as D034's intent_key (proposal_writer). Two proposals
    sharing a theme convey "the data keeps insisting on this." Persistent
    detection surfaces them with a `[PERSISTENT]` flag for the operator
    to either re-evaluate their rejection or fix the proposer's noise
    source.

    Returns a list of `PersistentProposal` summaries in descending
    `occurrence_count` order. Empty list when no theme reaches the
    threshold.
    """
    by_theme: dict[tuple[str, str], list[GrammarProposal]] = {}
    for p in proposals:
        ev = p.evidence_json or {}
        trigger = str(ev.get("trigger", ""))
        if not trigger:
            continue
        detail = str(
            ev.get("target") or ev.get("hypothesis") or ev.get("family") or "",
        )
        by_theme.setdefault((trigger, detail), []).append(p)

    persistent: list[PersistentProposal] = []
    for (trigger, detail), props in by_theme.items():
        if len(props) >= min_occurrences:
            persistent.append(
                PersistentProposal(
                    theme_trigger=trigger,
                    theme_detail=detail,
                    occurrence_count=len(props),
                    proposal_ids=tuple(str(p.proposal_id) for p in props),
                ),
            )
    persistent.sort(key=lambda pp: pp.occurrence_count, reverse=True)
    return persistent


__all__ = [
    "CounterfactualResult",
    "PersistentProposal",
    "compute_confidence",
    "detect_persistent_proposals",
    "evaluate_counterfactual",
    "propose",
    "should_auto_apply_proposal",
]
