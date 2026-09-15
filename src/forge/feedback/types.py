"""Frozen value types the reconcile path shares.

`CandidateOutcome` pairs a Forge-side `StrategyConfig` with a Crucible-side
`GatedRun`; both halves must agree on `config_hash`. `BatchFeedback` is the
consumer's per-batch aggregate. The analyzer / proposer / promoted-pattern types
that used to live here left with the daemon era (Batch 5 G3, D420): under the
signed freeze a grammar proposal cannot be applied without a preregistration, so
the machinery that minted them had no reader.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crucible_contracts import GatedRun, StrategyConfig


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


__all__ = ["BatchFeedback", "CandidateOutcome"]
