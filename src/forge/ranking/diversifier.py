"""§6.3 greedy diversifier with Jaccard similarity penalty.

D023/D3.a — `select_top_n` implements the §6.3 pseudocode: at each
step, pick the remaining candidate with the highest
`composite_score * (1 - max_similarity_to_selected)`. Similarity is
Jaccard overlap of signal IDs, mirroring the §5.3.5 novelty filter.

Returns the selected `RankedCandidate`s in selection order — that order
is the diversifier's ranking, NOT the raw composite-score order. The
caller can use the returned list directly as the submission queue.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.ranking.types import RankedCandidate


def _signal_ids(config: StrategyConfig) -> frozenset[str]:
    return frozenset(s.id for s in config.signals)


def jaccard_signal_ids(a: StrategyConfig, b: StrategyConfig) -> float:
    """Jaccard overlap of two configs' signal IDs.

    Returns `1.0` for identical sets, `0.0` for disjoint sets, the
    standard intersection-over-union ratio otherwise. Either config
    having an empty signal set yields `0.0` (the diversifier never
    needs to compare such configs in practice — pre-filters reject
    them — but the metric stays defined).
    """
    a_ids = _signal_ids(a)
    b_ids = _signal_ids(b)
    if not a_ids or not b_ids:
        return 0.0
    intersection = a_ids & b_ids
    union = a_ids | b_ids
    return len(intersection) / len(union)


def select_top_n(
    candidates: Sequence[RankedCandidate],
    n: int,
    *,
    similarity_fn: Callable[[StrategyConfig, StrategyConfig], float] = jaccard_signal_ids,
) -> list[RankedCandidate]:
    """Greedy DPP-style selection of `n` candidates from `candidates`.

    Each iteration: scan remaining candidates, pick the one with the
    highest `composite_score * (1 - max_similarity_to_selected)`. The
    first pick has no prior selections, so it's the highest-composite
    candidate. Subsequent picks balance score against similarity to
    already-selected candidates.

    Returns up to `n` candidates in selection order. If `n` exceeds the
    pool size, all candidates are returned. Raises `ValueError` if
    `n < 0`.
    """
    if n < 0:
        msg = f"n must be >= 0; got {n}"
        raise ValueError(msg)
    if n == 0 or not candidates:
        return []

    remaining = list(candidates)
    selected: list[RankedCandidate] = []

    while len(selected) < n and remaining:
        best_index = -1
        best_adjusted = -1.0
        for index, candidate in enumerate(remaining):
            if selected:
                penalty = max(
                    similarity_fn(candidate.report.config, s.report.config) for s in selected
                )
            else:
                penalty = 0.0
            adjusted = candidate.composite_score * (1.0 - penalty)
            # Strict `>` mirrors the §6.3 pseudocode — earlier (lower-index)
            # candidates win ties, which preserves the stable
            # composite-sorted seed on the first iteration.
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_index = index
        if best_index < 0:
            # Defensive: every adjusted_score < 0.0 (impossible by
            # construction since composite_score >= 0). Stop rather than
            # loop forever.
            break
        selected.append(remaining.pop(best_index))

    return selected


__all__ = ["jaccard_signal_ids", "select_top_n"]
