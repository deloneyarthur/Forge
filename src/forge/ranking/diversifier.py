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

from forge.ranking.signal_key import content_key

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.ranking.types import RankedCandidate


def _signal_keys(config: StrategyConfig) -> frozenset[str]:
    """Content-hash keys for similarity comparison (D024/D10).

    Switched from `signal.id` to `content_key(signal)` in Phase 5 so
    that signals with identical content but different ID strings count
    as the same — required for honest cross-batch proximity scoring.
    """
    return frozenset(content_key(s) for s in config.signals)


def jaccard_signal_ids(a: StrategyConfig, b: StrategyConfig) -> float:
    """Jaccard overlap of two configs' signal content-keys (D024/D10).

    Returns `1.0` for identical sets, `0.0` for disjoint sets, the
    standard intersection-over-union ratio otherwise. Either config
    having an empty signal set yields `0.0` (the diversifier never
    needs to compare such configs in practice — pre-filters reject
    them — but the metric stays defined).

    Function name kept for back-compat; the key is now content-hash.
    """
    a_keys = _signal_keys(a)
    b_keys = _signal_keys(b)
    if not a_keys or not b_keys:
        return 0.0
    intersection = a_keys & b_keys
    union = a_keys | b_keys
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

    # Default-path fast variant: precompute signal-key sets once per
    # candidate so the inner loop is set-arithmetic on cached frozensets
    # rather than re-extracting + re-hashing content keys ~N*K times.
    # On a 1537→200 batch this drops the ranker from ~10min → ~1min.
    if similarity_fn is jaccard_signal_ids:
        return _select_top_n_jaccard(candidates, n)
    return _select_top_n_generic(candidates, n, similarity_fn)


def _select_top_n_jaccard(
    candidates: Sequence[RankedCandidate],
    n: int,
) -> list[RankedCandidate]:
    """Fast path for the default `jaccard_signal_ids` similarity metric."""
    keys = [_signal_keys(c.report.config) for c in candidates]
    remaining_idx = list(range(len(candidates)))
    selected_idx: list[int] = []

    while len(selected_idx) < n and remaining_idx:
        best_rem_pos = -1
        best_adjusted = -1.0
        for rem_pos, idx in enumerate(remaining_idx):
            k_idx = keys[idx]
            if selected_idx and k_idx:
                penalty = 0.0
                for sidx in selected_idx:
                    k_sidx = keys[sidx]
                    if not k_sidx:
                        continue
                    sim = len(k_idx & k_sidx) / len(k_idx | k_sidx)
                    penalty = max(penalty, sim)
            else:
                penalty = 0.0
            adjusted = candidates[idx].composite_score * (1.0 - penalty)
            # Strict `>` mirrors §6.3 — earlier candidates win ties.
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_rem_pos = rem_pos
        if best_rem_pos < 0:
            break
        selected_idx.append(remaining_idx.pop(best_rem_pos))

    return [candidates[i] for i in selected_idx]


def _select_top_n_generic(
    candidates: Sequence[RankedCandidate],
    n: int,
    similarity_fn: Callable[[StrategyConfig, StrategyConfig], float],
) -> list[RankedCandidate]:
    """Original O(N*K) path for callers with a custom similarity metric."""
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
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_index = index
        if best_index < 0:
            break
        selected.append(remaining.pop(best_index))

    return selected


__all__ = ["jaccard_signal_ids", "select_top_n"]
