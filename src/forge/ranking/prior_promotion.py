"""§6.2 prior_promotion_proximity_score.

For each candidate, compute the maximum Jaccard overlap of signal IDs
vs each previously-promoted strategy. Empty `promoted_configs` → 0.0.

The metric mirrors the §5.3.5 novelty filter's set construction (signal
IDs), keeping the pipeline's structural-similarity definition coherent.
A future contracts bump may switch to content-hash keys (Phase 5 open
question 4 from `PHASE_3_HANDOFF.md`); the function's signature won't
change.

D023/D1.a — Phase 4 ships the real implementation. Week 1 batches with
no promoted history naturally use only the other 90% of §6.2 weights.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from forge.ranking.signal_key import content_key

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig


def _signal_keys(config: StrategyConfig) -> frozenset[str]:
    """Content-hash keys for proximity comparison (D024/D10)."""
    return frozenset(content_key(s) for s in config.signals)


def compute_prior_promotion_proximity(
    config: StrategyConfig,
    promoted_configs: Iterable[StrategyConfig],
) -> float:
    """Max Jaccard overlap of `config`'s signal content-keys vs each promoted's.

    Returns `0.0` if `promoted_configs` is empty or if no promoted entry
    shares any signals with the candidate. Returns `1.0` if any promoted
    config has the identical signal set.

    Phase 5 closes Phase 3 OQ-4 by switching from signal.id to content_key —
    cross-batch comparisons now compare on content, not on the (potentially
    drifting) ID strings.
    """
    candidate = _signal_keys(config)
    if not candidate:
        return 0.0
    best = 0.0
    for promoted in promoted_configs:
        promoted_keys = _signal_keys(promoted)
        if not promoted_keys:
            continue
        intersection = candidate & promoted_keys
        union = candidate | promoted_keys
        overlap = len(intersection) / len(union)
        best = max(best, overlap)
    return best


__all__ = ["compute_prior_promotion_proximity"]
