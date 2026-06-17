"""Deterministic, oracle-ranked king search (FORGE meta-king A3 §4).

Phase-0 search: draw a deterministic stream of grammar-valid configs from the
existing §4.2 enumerator (valid-by-construction), score each with the published
durable oracle, dedup against already-tried genomes, and keep the top-K by
predicted durable score. This is on-manifold by construction — the enumerator
samples the same grammar space that produced the oracle's training corpus.

Determinism (hard rule #6): for a fixed ``(grammar, registry, oracle, seed,
n_search)`` the king sequence is byte-identical — the enumerator is seeded, the
scorer is pure, and ties break on ``config_hash``.

``n_searched`` is recorded as the trial count ``N`` that the future DSR
trial-laundering guard must account for (A3 §4): picking the top-K of ``N``
oracle-scored genomes is a search multiplicity that single-config DSR cannot
see. Phase 0 counts and reports ``N``; it cannot yet *transmit* it to Crucible
(no contract channel — that gap is the subject of the provenance/DSR relay).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from forge.enumeration import enumerate_candidates
from forge.king.score import score_genome

if TYPE_CHECKING:
    from collections.abc import Iterable

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar.models import Grammar
    from forge.king.oracle import DurableOracle


@dataclass(frozen=True, slots=True)
class King:
    """One candidate genome and its oracle-predicted durable score."""

    config: StrategyConfig
    predicted_score: float


@dataclass(frozen=True, slots=True)
class KingSearchResult:
    """The top-K kings plus the search-multiplicity bookkeeping.

    ``n_searched`` is the DSR trial count ``N`` (genomes scored against the
    oracle); ``n_deduped`` were skipped as already-tried; ``n_unique`` is the
    count of distinct ``config_hash`` seen this search.
    """

    kings: tuple[King, ...]
    n_searched: int
    n_deduped: int
    n_unique: int


def search_kings(
    grammar: Grammar,
    registry: RegistrySnapshot,
    oracle: DurableOracle,
    *,
    seed: int,
    n_search: int,
    top_k: int,
    tried_hashes: Iterable[str] = (),
    per_cell_cap: int | None = None,
    min_score: float = -1.0,
) -> KingSearchResult:
    """Search ``n_search`` grammar-valid genomes; return the surfaced kings.

    Genomes whose ``config_hash`` is in ``tried_hashes`` (or already seen this
    search) are excluded from the kings but still counted toward ``n_searched``
    — they were trials.

    Selection (see :func:`_select_diverse`): with ``per_cell_cap is None`` the
    result is the global top-``top_k`` by predicted score (``min_score`` is
    ignored — global ranking already prefers the best). With ``per_cell_cap``
    set it is Crucible's recommended diversity quota (A3 response) — at most
    ``per_cell_cap`` kings from each ``(hypothesis, dte_bucket)`` cell whose
    predicted score clears ``min_score``, capped at ``top_k`` — which breaks the
    ``mean_reversion/swing_short`` monoculture so the stream can feed a
    decorrelated complement ([[D172]]).

    ``min_score`` is the per-cell admission floor, and it is *objective-relative*
    — the live oracle's score range moves when Crucible flips the target (cpcv ->
    p_component -> min_margin, D180). For the published ``min_margin`` oracle the
    durable score is an all-gate margin in roughly ``[-4.2, -0.2]`` (every value
    negative — no single component clears the gauntlet); the default ``-1.0`` is
    the corpus median, which a dry-run confirms keeps an above-median, *diverse*
    top-K spanning ~7 ``(hypothesis, dte)`` cells. A tighter floor (e.g. the
    relay-suggested ``-0.8`` top-quartile) collapses back to the single strongest
    cell — the monoculture per-cell mode exists to break — so prefer the median.
    (P(component) wanted ``0.5``; cpcv wanted ``0.0``. Always set the floor from
    the live score range, never a value carried over from the prior objective.)

    A floor above *every* scored genome is a mis-set floor, not an empty result:
    per-cell mode raises rather than silently surfacing nothing (so ``--submit``
    can never queue an empty batch when the objective flips out from under a
    stale floor).

    Raises:
        ValueError: ``n_search`` or ``top_k`` is non-positive, ``per_cell_cap``
            is non-positive when supplied, or per-cell selection admitted zero of
            the scored genomes (every one fell below ``min_score``).
        forge.enumeration.EnumerationCapped: the registry slice is too sparse to
            yield ``n_search`` configs within the enumerator's retry budget.
    """
    if n_search <= 0:
        msg = f"n_search must be > 0, got {n_search}"
        raise ValueError(msg)
    if top_k <= 0:
        msg = f"top_k must be > 0, got {top_k}"
        raise ValueError(msg)
    if per_cell_cap is not None and per_cell_cap <= 0:
        msg = f"per_cell_cap must be > 0 when supplied, got {per_cell_cap}"
        raise ValueError(msg)

    already = frozenset(tried_hashes)
    seen: set[str] = set()
    scored: list[King] = []
    n_searched = 0
    n_deduped = 0

    for config in enumerate_candidates(
        grammar,
        registry,
        seed=seed,
        max_candidates=n_search,
    ):
        n_searched += 1
        config_hash = config.config_hash
        if config_hash in seen:
            continue
        seen.add(config_hash)
        if config_hash in already:
            n_deduped += 1
            continue
        predicted = score_genome(config.model_dump(mode="json"), oracle)
        scored.append(King(config=config, predicted_score=predicted))

    scored.sort(key=lambda king: (-king.predicted_score, king.config.config_hash))
    selected = _select_diverse(scored, top_k=top_k, per_cell_cap=per_cell_cap, min_score=min_score)
    if per_cell_cap is not None and scored and not selected:
        # The floor rejected every scored genome — a stale floor for the live
        # objective, not a real empty result. Fail loud with the live target and
        # the observed score range so the operator can set a floor that bites.
        lo = scored[-1].predicted_score
        hi = scored[0].predicted_score
        msg = (
            f"per-cell selection admitted 0 of {len(scored)} scored genomes: every one "
            f"scored below min_score={min_score} (oracle target={oracle.target!r}, scores "
            f"ranged [{lo:.4f}, {hi:.4f}]). The floor is mis-set for this objective — set "
            f"--min-score within the observed range (the corpus median is the diverse default)."
        )
        raise ValueError(msg)
    return KingSearchResult(
        kings=tuple(selected),
        n_searched=n_searched,
        n_deduped=n_deduped,
        n_unique=len(seen),
    )


def _select_diverse(
    scored: list[King],
    *,
    top_k: int,
    per_cell_cap: int | None,
    min_score: float,
) -> list[King]:
    """Pick which kings to surface from the score-sorted candidates.

    ``scored`` must already be sorted by descending predicted score. Global mode
    (``per_cell_cap is None``) returns the first ``top_k`` (no floor — the global
    ranking already prefers the best). Per-cell mode keeps at most
    ``per_cell_cap`` kings whose score clears ``min_score`` per ``(hypothesis,
    dte_bucket)`` cell, preserving the global score order, then caps at ``top_k``
    — Crucible's A3-response diversity quota. A king below ``min_score`` is never
    surfaced, so a cell with no clearing genomes contributes nothing.
    """
    if per_cell_cap is None:
        return scored[:top_k]
    per_cell: dict[tuple[str, str], int] = {}
    chosen: list[King] = []
    for king in scored:
        if king.predicted_score < min_score:
            continue
        cell = (king.config.hypothesis, king.config.dte_bucket)
        if per_cell.get(cell, 0) >= per_cell_cap:
            continue
        per_cell[cell] = per_cell.get(cell, 0) + 1
        chosen.append(king)
        if len(chosen) >= top_k:
            break
    return chosen
