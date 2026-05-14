"""§8.3 analyzer — extract patterns from a BatchFeedback.

`analyze_batch(feedback, registry) -> AnalysisReport` is pure: no DB writes.
The §8.3 spec lists four learnings:
  1. Promotion rate — read directly from feedback.
  2. Gate failure breakdown — count failures per gate name across rejected.
  3. Metric distributions per hypothesis — group outcomes by config.hypothesis.
  4. Promoted strategy structural patterns — heuristics over the promoted subset.

DB writes for `promoted_patterns` happen in the separate `feedback.promoted_patterns`
module (D024/D11); this analyzer just returns the candidates.

D024/D2: in-memory return; caller chains to the proposer without re-reading.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from forge.feedback.types import (
    AnalysisReport,
    GateFailureRow,
    HypothesisMetrics,
    PromotedPattern,
)

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.feedback.types import BatchFeedback, CandidateOutcome


# Pattern-detection thresholds. Phase 5 hardcodes; config/forge.yaml
# wire-up later (Phase 5/6 polish) makes them tunable.
_HYPOTHESIS_DOMINANCE_THRESHOLD: float = 0.80
_SIGNAL_FAMILY_DOMINANCE_THRESHOLD: float = 0.80
_MIN_PROMOTED_FOR_PATTERN: int = 2


def _gate_failure_rows(feedback: BatchFeedback) -> tuple[GateFailureRow, ...]:
    rejected = [o for o in feedback.outcomes if not o.promoted]
    if not rejected:
        return ()
    counts: dict[str, int] = {}
    for o in rejected:
        for gate_name, gate in o.gated_run.decision.gate_results.items():
            if not gate.passed:
                counts[gate_name] = counts.get(gate_name, 0) + 1
    rejected_count = len(rejected)
    return tuple(
        GateFailureRow(
            gate_name=name,
            failure_count=cnt,
            failure_rate=cnt / rejected_count,
        )
        for name, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )


def _hypothesis_metric_rows(feedback: BatchFeedback) -> tuple[HypothesisMetrics, ...]:
    by_h: dict[str, list[CandidateOutcome]] = {}
    for o in feedback.outcomes:
        by_h.setdefault(o.config.hypothesis, []).append(o)

    rows: list[HypothesisMetrics] = []
    for hypothesis, outcomes in sorted(by_h.items()):
        sample = len(outcomes)
        promoted = sum(1 for o in outcomes if o.promoted)
        sharpes = [
            o.gated_run.run.metrics["walk_forward_sharpe_median"]
            for o in outcomes
            if "walk_forward_sharpe_median" in o.gated_run.run.metrics
        ]
        avg = (sum(sharpes) / len(sharpes)) if sharpes else None
        if avg is not None and (math.isnan(avg) or math.isinf(avg)):
            avg = None
        rows.append(
            HypothesisMetrics(
                hypothesis=hypothesis,
                sample_size=sample,
                promotion_rate=promoted / sample if sample else 0.0,
                avg_sharpe=avg,
            )
        )
    return tuple(rows)


def _hypothesis_dominance_patterns(
    promoted: list[CandidateOutcome],
) -> list[PromotedPattern]:
    if len(promoted) < _MIN_PROMOTED_FOR_PATTERN:
        return []
    counts: dict[str, int] = {}
    for o in promoted:
        counts[o.config.hypothesis] = counts.get(o.config.hypothesis, 0) + 1
    sample = len(promoted)
    out: list[PromotedPattern] = []
    for h, cnt in counts.items():
        if cnt / sample >= _HYPOTHESIS_DOMINANCE_THRESHOLD:
            out.append(
                PromotedPattern(
                    pattern_type="hypothesis_dominance",
                    pattern={"hypothesis": h},
                    promoted_count=cnt,
                    sample_size=sample,
                )
            )
    return out


def _directional_family(config: StrategyConfig, indicator_index: dict[str, str]) -> str | None:
    """Look up the family of the strategy's first directional signal.

    `indicator_index` maps `IndicatorMetadata.id -> family`. Returns None
    if no directional signal exists or its indicator has no registry entry
    — defensive against synthetic test data.
    """
    for s in config.signals:
        if s.role != "directional":
            continue
        for ind_id in s.indicators:
            fam = indicator_index.get(ind_id)
            if fam is not None:
                return fam
        break
    return None


def _signal_family_dominance_patterns(
    promoted: list[CandidateOutcome],
    registry: RegistrySnapshot,
) -> list[PromotedPattern]:
    if len(promoted) < _MIN_PROMOTED_FOR_PATTERN:
        return []
    indicator_index = {ind.id: str(ind.family) for ind in registry.indicators}
    counts: dict[str, int] = {}
    for o in promoted:
        fam = _directional_family(o.config, indicator_index)
        if fam is None:
            continue
        counts[fam] = counts.get(fam, 0) + 1
    sample = sum(counts.values())
    if sample < _MIN_PROMOTED_FOR_PATTERN:
        return []
    out: list[PromotedPattern] = []
    for fam, cnt in counts.items():
        if cnt / sample >= _SIGNAL_FAMILY_DOMINANCE_THRESHOLD:
            out.append(
                PromotedPattern(
                    pattern_type="signal_family_dominance",
                    pattern={"family": fam},
                    promoted_count=cnt,
                    sample_size=sample,
                )
            )
    return out


def _promoted_pattern_rows(
    feedback: BatchFeedback, registry: RegistrySnapshot
) -> tuple[PromotedPattern, ...]:
    promoted = [o for o in feedback.outcomes if o.promoted]
    patterns: list[PromotedPattern] = []
    patterns.extend(_hypothesis_dominance_patterns(promoted))
    patterns.extend(_signal_family_dominance_patterns(promoted, registry))
    return tuple(patterns)


def analyze_batch(feedback: BatchFeedback, registry: RegistrySnapshot) -> AnalysisReport:
    """Pure §8.3 analysis over a `BatchFeedback`."""
    return AnalysisReport(
        batch_id=feedback.batch_id,
        promotion_rate=feedback.promotion_rate,
        gate_failures=_gate_failure_rows(feedback),
        hypothesis_metrics=_hypothesis_metric_rows(feedback),
        promoted_patterns=_promoted_pattern_rows(feedback, registry),
    )


__all__ = ["analyze_batch"]
