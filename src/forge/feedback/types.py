"""Frozen value types for the Phase 5 feedback machinery.

`CandidateOutcome` pairs a Forge-side `StrategyConfig` with a Crucible-side
`GatedRun`; both halves must agree on `config_hash`.
`BatchFeedback` is the consumer's output — aggregates per batch.
`AnalysisReport` is the analyzer's output — patterns the proposer reads.
`Trigger` captures the condition that fired in the proposer.
`GrammarProposal` is the persisted proposal record (mirrors §9.1
`grammar_proposals` columns; also covers calibration proposals per D024/D4).

All types are immutable dataclasses with explicit `__post_init__` validation.
The proposer's `is_loosen` flag is the structural lever for hard rule #4:
loosen-direction proposals route to `OPEN_PROPOSALS.md` and never auto-apply.

See DESIGN.md §8 (feedback), §9.1 (schema), §13.3 (no silent grammar changes).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from crucible_contracts import GatedRun, StrategyConfig


ProposalType = Literal["tighten", "loosen", "add_rule", "remove_rule"]
ProposalTarget = Literal["grammar", "prefilter_calibration", "ranker_weights"]
TriggerKind = Literal[
    "gate_failure_concentration",
    "family_dominance",
    "param_no_promotion",
]
PatternType = Literal[
    "hypothesis_dominance",
    "signal_family_dominance",
    "parameter_cluster",
]

_PROPOSAL_TYPES: frozenset[str] = frozenset({"tighten", "loosen", "add_rule", "remove_rule"})
_PROPOSAL_TARGETS: frozenset[str] = frozenset(
    {"grammar", "prefilter_calibration", "ranker_weights"}
)
_TRIGGER_KINDS: frozenset[str] = frozenset(
    {"gate_failure_concentration", "family_dominance", "param_no_promotion"}
)
_PATTERN_TYPES: frozenset[str] = frozenset(
    {"hypothesis_dominance", "signal_family_dominance", "parameter_cluster"}
)

_LOOSEN_PROPOSAL_TYPES: frozenset[str] = frozenset({"loosen", "remove_rule"})


def _check_unit_interval(name: str, value: float) -> None:
    if math.isnan(value) or math.isinf(value) or not (0.0 <= value <= 1.0):
        msg = f"{name} must be a finite float in [0, 1]; got {value!r}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    """One Forge submission paired with its Crucible-side gated result.

    The two halves must agree on `config_hash` — the model-validator
    rejects mismatched pairs because they'd silently scramble per-batch
    analysis. The `promoted` shortcut reads through to the decision.
    """

    config: StrategyConfig
    gated_run: GatedRun

    def __post_init__(self) -> None:
        if self.config.config_hash != self.gated_run.run.config_hash:
            msg = (
                f"CandidateOutcome.config_hash mismatch: "
                f"config={self.config.config_hash!r} vs "
                f"gated_run={self.gated_run.run.config_hash!r}"
            )
            raise ValueError(msg)

    @property
    def config_hash(self) -> str:
        return self.config.config_hash

    @property
    def promoted(self) -> bool:
        return self.gated_run.decision.decision == "promote"


@dataclass(frozen=True, slots=True)
class BatchFeedback:
    """Per-batch aggregate emitted by `feedback.consumer.consume_batch_results`.

    `submitted_count` reflects what Forge wrote to the inbox (rows in
    `submissions`); `outcomes` are only those that Crucible has gated.
    The difference is `pending_count` — still in flight.
    """

    batch_id: uuid.UUID
    submitted_count: int
    outcomes: tuple[CandidateOutcome, ...]

    def __post_init__(self) -> None:
        if self.submitted_count < 0:
            msg = f"BatchFeedback.submitted_count must be >= 0; got {self.submitted_count}"
            raise ValueError(msg)
        if len(self.outcomes) > self.submitted_count:
            msg = (
                f"BatchFeedback.outcomes ({len(self.outcomes)}) exceeds "
                f"submitted_count ({self.submitted_count})"
            )
            raise ValueError(msg)

    @property
    def gated_count(self) -> int:
        return len(self.outcomes)

    @property
    def promoted_count(self) -> int:
        return sum(1 for o in self.outcomes if o.promoted)

    @property
    def rejected_count(self) -> int:
        return self.gated_count - self.promoted_count

    @property
    def pending_count(self) -> int:
        return self.submitted_count - self.gated_count

    @property
    def promotion_rate(self) -> float:
        if self.submitted_count == 0:
            return 0.0
        return self.promoted_count / self.submitted_count


@dataclass(frozen=True, slots=True)
class GateFailureRow:
    """One gate's failure summary across a batch.

    `failure_rate` is the share of *rejected* candidates that failed this
    specific gate (not of total submissions). §8.4's "95%+ rejected by
    gate X" trigger reads this field.
    """

    gate_name: str
    failure_count: int
    failure_rate: float

    def __post_init__(self) -> None:
        if not self.gate_name:
            msg = "GateFailureRow.gate_name must be non-empty"
            raise ValueError(msg)
        if self.failure_count < 0:
            msg = f"GateFailureRow.failure_count must be >= 0; got {self.failure_count}"
            raise ValueError(msg)
        _check_unit_interval("GateFailureRow.failure_rate", self.failure_rate)


@dataclass(frozen=True, slots=True)
class HypothesisMetrics:
    """Per-hypothesis distribution row in an `AnalysisReport`.

    `avg_sharpe` is optional because a hypothesis with zero gated runs has
    no meaningful Sharpe; the report still carries the row so downstream
    re-weighting code sees the hypothesis is represented.
    """

    hypothesis: str
    sample_size: int
    promotion_rate: float
    avg_sharpe: float | None

    def __post_init__(self) -> None:
        if not self.hypothesis:
            msg = "HypothesisMetrics.hypothesis must be non-empty"
            raise ValueError(msg)
        if self.sample_size < 0:
            msg = f"HypothesisMetrics.sample_size must be >= 0; got {self.sample_size}"
            raise ValueError(msg)
        _check_unit_interval("HypothesisMetrics.promotion_rate", self.promotion_rate)
        if self.avg_sharpe is not None and (
            math.isnan(self.avg_sharpe) or math.isinf(self.avg_sharpe)
        ):
            msg = f"HypothesisMetrics.avg_sharpe must be finite or None; got {self.avg_sharpe!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PromotedPattern:
    """A structural pattern extracted from promoted strategies (§8.3).

    `pattern_type` matches `promoted_patterns.pattern_type` in §9.1.
    `dominance_rate` is the share of the sampled batch in which this
    pattern appeared.
    """

    pattern_type: PatternType
    pattern: dict[str, Any]
    promoted_count: int
    sample_size: int

    def __post_init__(self) -> None:
        if self.pattern_type not in _PATTERN_TYPES:
            msg = (
                f"PromotedPattern.pattern_type must be one of {sorted(_PATTERN_TYPES)}; "
                f"got {self.pattern_type!r}"
            )
            raise ValueError(msg)
        if self.sample_size <= 0:
            msg = f"PromotedPattern.sample_size must be > 0; got {self.sample_size}"
            raise ValueError(msg)
        if self.promoted_count < 0 or self.promoted_count > self.sample_size:
            msg = (
                f"PromotedPattern.promoted_count ({self.promoted_count}) must be in "
                f"[0, sample_size={self.sample_size}]"
            )
            raise ValueError(msg)

    @property
    def dominance_rate(self) -> float:
        return self.promoted_count / self.sample_size


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Aggregated learnings for one batch (analyzer output).

    Composed of subreports the proposer iterates over to fire its three
    §8.4 trigger types. `promotion_rate` mirrors `BatchFeedback`'s value
    to spare downstream code from passing both around.
    """

    batch_id: uuid.UUID
    promotion_rate: float
    gate_failures: tuple[GateFailureRow, ...]
    hypothesis_metrics: tuple[HypothesisMetrics, ...]
    promoted_patterns: tuple[PromotedPattern, ...]

    def __post_init__(self) -> None:
        _check_unit_interval("AnalysisReport.promotion_rate", self.promotion_rate)


@dataclass(frozen=True, slots=True)
class Trigger:
    """A single firing of a §8.4 / §5.5 condition inside the proposer.

    Captured for `evidence_json` on the persisted `GrammarProposal`.
    """

    kind: TriggerKind
    target: str
    threshold: float
    observed: float

    def __post_init__(self) -> None:
        if self.kind not in _TRIGGER_KINDS:
            msg = f"Trigger.kind must be one of {sorted(_TRIGGER_KINDS)}; got {self.kind!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class GrammarProposal:
    """A persisted refinement proposal — mirrors §9.1 grammar_proposals.

    `proposal_type ∈ {tighten, loosen, add_rule, remove_rule}` maps to
    the table column; `is_loosen` is the structural lever for hard rule
    #4 — loosen-direction proposals never auto-apply.
    """

    proposal_id: uuid.UUID
    proposed_at: datetime
    proposal_type: ProposalType
    target: ProposalTarget
    proposal_yaml: str
    rationale: str
    evidence_json: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.proposed_at.tzinfo is None:
            msg = "GrammarProposal.proposed_at must be timezone-aware"
            raise ValueError(msg)
        if self.proposal_type not in _PROPOSAL_TYPES:
            msg = (
                f"GrammarProposal.proposal_type must be one of {sorted(_PROPOSAL_TYPES)}; "
                f"got {self.proposal_type!r}"
            )
            raise ValueError(msg)
        if self.target not in _PROPOSAL_TARGETS:
            msg = (
                f"GrammarProposal.target must be one of {sorted(_PROPOSAL_TARGETS)}; "
                f"got {self.target!r}"
            )
            raise ValueError(msg)

    @property
    def is_loosen(self) -> bool:
        return self.proposal_type in _LOOSEN_PROPOSAL_TYPES


__all__ = [
    "AnalysisReport",
    "BatchFeedback",
    "CandidateOutcome",
    "GateFailureRow",
    "GrammarProposal",
    "HypothesisMetrics",
    "PatternType",
    "PromotedPattern",
    "ProposalTarget",
    "ProposalType",
    "Trigger",
    "TriggerKind",
]
