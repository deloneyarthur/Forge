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

from forge.ranking.arm_floor import (
    ARM_FLOOR_BATCH_FRACTION,
    ARM_FLOOR_SLOTS_PER_ARM,
    extract_arms,
)
from forge.ranking.signal_key import content_key

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from crucible_contracts import StrategyConfig

    from forge.ranking.arm_floor import Arm
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
    min_per_hypothesis: int = 0,
    mature_arms: AbstractSet[Arm] | None = None,
    arm_floor_slots: int = ARM_FLOOR_SLOTS_PER_ARM,
    arm_floor_batch_fraction: float = ARM_FLOOR_BATCH_FRACTION,
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

    ``min_per_hypothesis`` (D103) reserves a per-hypothesis floor of the
    `n` slots so an orthogonal sleeve (relative_value) can't be starved to
    ~0 by a higher-scoring hypothesis monopolizing the composite (the
    midday mean_reversion-flood failure mode). `0` (default) keeps the
    legacy unfloored greedy exactly.

    ``mature_arms`` (D136) activates the per-arm exploration floor: any
    `(role, indicator_id)` arm NOT in the set is *young* (this naturally
    covers never-seen arms), and a reservation phase grants up to
    ``arm_floor_slots`` of the `n` slots per young arm — capped at
    ``int(n * arm_floor_batch_fraction)`` total — to the highest-composite
    survivors carrying that arm, before the D103 hypothesis floor and the
    greedy fill run as today. The floor never invents candidates: if no
    survivor carries a young arm, nothing is reserved (generation-side
    starvation stays visible in the funnel). `None` (default) keeps the
    legacy paths byte-identical.
    """
    if n < 0:
        msg = f"n must be >= 0; got {n}"
        raise ValueError(msg)
    if n == 0 or not candidates:
        return []

    if min_per_hypothesis > 0 or mature_arms is not None:
        return _select_top_n_floored(
            candidates,
            n,
            similarity_fn,
            min_per_hypothesis,
            mature_arms=mature_arms,
            arm_floor_slots=arm_floor_slots,
            arm_floor_batch_fraction=arm_floor_batch_fraction,
        )

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


def _young_arm_pools(
    arms_by_candidate: Sequence[frozenset[Arm]],
    mature_arms: AbstractSet[Arm],
) -> dict[Arm, list[int]]:
    """Candidate indices per YOUNG arm (any arm not in ``mature_arms`` —
    which naturally covers arms that have never produced a verdict)."""
    pools: dict[Arm, list[int]] = {}
    for idx, arms in enumerate(arms_by_candidate):
        for arm in arms:
            if arm not in mature_arms:
                pools.setdefault(arm, []).append(idx)
    return pools


def _select_top_n_floored(
    candidates: Sequence[RankedCandidate],
    n: int,
    similarity_fn: Callable[[StrategyConfig, StrategyConfig], float],
    min_per_hypothesis: int,
    *,
    mature_arms: AbstractSet[Arm] | None = None,
    arm_floor_slots: int = ARM_FLOOR_SLOTS_PER_ARM,
    arm_floor_batch_fraction: float = ARM_FLOOR_BATCH_FRACTION,
) -> list[RankedCandidate]:
    """Greedy selection with the per-arm (D136) and per-hypothesis (D103)
    floors.

    Three phases, all using the same §6.3 greedy rule (highest
    ``composite_score * (1 - max_similarity_to_selected)``, strict-``>``
    tie-break so earlier candidates win):

      0. **Arm reservation (D136)** — when ``mature_arms`` is provided: for
         each YOUNG arm present among the candidates, in deterministic
         (sorted) order, greedily reserve up to ``arm_floor_slots`` slots
         for candidates carrying that arm (counting candidates already
         selected for it via another arm), capped at
         ``int(n * arm_floor_batch_fraction)`` reservations total.
      1. **Hypothesis floor (D103)** — for each hypothesis in sorted order,
         greedily reserve up to ``min_per_hypothesis`` of its candidates (or
         all of them if fewer), scored against the running global selection so
         cross-hypothesis diversity still applies. Stops early once ``n`` fills.
      2. **Fill** — greedily take the remaining ``n - selected`` from the whole
         unselected pool.

    Determinism (hard rule #6) holds: sorted arm + hypothesis order and the
    strict-``>`` greedy tie-break. Uses cached signal-key frozensets on the
    default Jaccard path (production); falls back to ``similarity_fn`` for a
    custom metric.
    """
    use_jaccard = similarity_fn is jaccard_signal_ids
    keys = [_signal_keys(c.report.config) for c in candidates] if use_jaccard else []

    selected_idx: list[int] = []
    selected_set: set[int] = set()

    def _penalty(idx: int) -> float:
        if not selected_idx:
            return 0.0
        if use_jaccard:
            k_idx = keys[idx]
            if not k_idx:
                return 0.0
            best = 0.0
            for sidx in selected_idx:
                k_sidx = keys[sidx]
                if not k_sidx:
                    continue
                sim = len(k_idx & k_sidx) / len(k_idx | k_sidx)
                best = max(best, sim)
            return best
        return max(
            similarity_fn(candidates[idx].report.config, candidates[s].report.config)
            for s in selected_idx
        )

    def _take(pool: Sequence[int], count: int) -> None:
        for _ in range(count):
            if len(selected_idx) >= n:
                return
            best_idx = -1
            best_adjusted = -1.0
            for idx in pool:
                if idx in selected_set:
                    continue
                adjusted = candidates[idx].composite_score * (1.0 - _penalty(idx))
                # Strict `>` mirrors §6.3 — earlier candidates win ties.
                if adjusted > best_adjusted:
                    best_adjusted = adjusted
                    best_idx = idx
            if best_idx < 0:
                return
            selected_idx.append(best_idx)
            selected_set.add(best_idx)

    # Phase 0 (D136) — young-arm reservation. Arms in sorted order; a
    # candidate selected for one young arm counts toward every young arm it
    # carries, so overlapping-arm candidates don't double-spend the cap.
    if mature_arms is not None and arm_floor_slots > 0:
        reservation_cap = int(n * arm_floor_batch_fraction)
        arms_by_candidate = [extract_arms(c.report.config) for c in candidates]
        reserved_total = 0
        for arm, pool in sorted(_young_arm_pools(arms_by_candidate, mature_arms).items()):
            if reserved_total >= reservation_cap or len(selected_idx) >= n:
                break
            already = sum(1 for sidx in selected_idx if arm in arms_by_candidate[sidx])
            want = min(arm_floor_slots - already, reservation_cap - reserved_total)
            if want <= 0:
                continue
            before = len(selected_idx)
            _take(pool, want)
            reserved_total += len(selected_idx) - before

    by_hyp: dict[str, list[int]] = {}
    for idx, cand in enumerate(candidates):
        by_hyp.setdefault(cand.report.config.hypothesis, []).append(idx)
    for hyp in sorted(by_hyp):
        if len(selected_idx) >= n:
            break
        _take(by_hyp[hyp], min(min_per_hypothesis, len(by_hyp[hyp])))

    _take(range(len(candidates)), n - len(selected_idx))
    return [candidates[i] for i in selected_idx]


__all__ = ["jaccard_signal_ids", "select_top_n"]
