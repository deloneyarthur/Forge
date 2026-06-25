"""Cumulative alpha-budget / multiple-testing ledger (Tier-1a measurement spine).

WHY this exists. Forge runs a millions-wide, learned-weighted search and submits
the survivors to Crucible's Deflated-Sharpe gate with ``search_n_trials`` unset.
``crucible_contracts`` folds an absent count into ``n_trials = 1``, so the gate
deflates each gated candidate *as if it were the only strategy ever tried*. The
breadth of the search is never charged against significance. This module measures
that gap so the operator (and a future Crucible coordination item) can reason about
how much of any apparent edge is search luck.

It does NOT invent new bookkeeping: the two counts it needs are already persisted
per batch in ``batch_summaries`` (D085/D096), so this is pure read-side telemetry —
never written to ``grammar.yaml`` and never read by the production loop.

The honest trial count is bracketed, not asserted, by two quantities:

* ``n_submitted`` = sum of ``batch_size`` — distinct configs actually gated
  (hard rule #9 makes every submission a unique ``config_hash``). The conservative
  floor: Crucible faced at least this many bets.
* ``n_scored`` = sum of ``enumerated_count`` — the configs the ranker selected
  among to produce those submissions. The breadth ceiling (redundant, so an
  over-count of *independent* trials).

For each end of the bracket it reports the Bailey & Lopez de Prado (2014)
"false strategy" benchmark :func:`expected_max_sharpe`: the Sharpe (in cross-trial
Sharpe-stdev units) the best of ``N`` *null* strategies is expected to reach by luck
alone. A candidate must clear it to be distinguishable from the luckiest draw of a
search that wide.

Deliberately left to the operator / a Crucible handoff, NOT pre-judged here:

* the accounting boundary — per-grammar-version (a bounded search) vs cumulative
  (the whole history mines the same underlying). Both are reported; neither is "the"
  answer.
* the effective-N redundancy reduction (clustering near-duplicate configs, per
  Lopez de Prado 2019). ``n_scored`` is the *nominal* breadth; effective N lies
  between the two reported ends. That reduction is a scoped follow-up.
"""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

# Euler-Mascheroni constant; the second-order term weight in the LdP benchmark.
_EULER_MASCHERONI: Final[float] = 0.5772156649015329


def expected_max_sharpe(n_trials: int) -> float:
    """Expected maximum of ``n_trials`` independent null Sharpe ratios.

    Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio", eq. for the
    expected maximum of N draws from a standard normal:

        E[max_N] ~= (1 - g) * Z^-1(1 - 1/N) + g * Z^-1(1 - 1/(N*e))

    where ``Z^-1`` is the standard-normal quantile and ``g`` is Euler-Mascheroni.
    The result is in units of the cross-trial Sharpe standard deviation (sigma=1),
    i.e. the haircut a single candidate's Sharpe must overcome purely to beat the
    best of N coin-flips. ``n_trials <= 1`` returns 0.0 — with nothing to select
    among there is no multiple-testing inflation.
    """
    if n_trials <= 1:
        return 0.0
    nd = statistics.NormalDist()  # standard normal: mean 0, sigma 1
    first = nd.inv_cdf(1.0 - 1.0 / n_trials)
    second = nd.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return (1.0 - _EULER_MASCHERONI) * first + _EULER_MASCHERONI * second


@dataclass(frozen=True, slots=True)
class BatchRow:
    """One ``batch_summaries`` row, reduced to the columns the ledger needs.

    ``enumerated_count`` is ``None`` for batches recorded before the D096 column
    existed; the ledger coalesces those to ``batch_size`` (we know at least that
    many configs existed) and reports the resulting coverage gap.
    """

    grammar_version: str
    batch_size: int
    enumerated_count: int | None


@dataclass(frozen=True, slots=True)
class VersionBudget:
    """Trial counts for a single grammar version (a bounded search cohort)."""

    grammar_version: str
    n_submitted: int
    n_scored: int


@dataclass(frozen=True, slots=True)
class AlphaBudget:
    """The cumulative ledger across all recorded batches."""

    n_batches: int
    n_submitted: int
    n_scored: int
    scored_coverage: float  # fraction of batches with a real enumerated_count
    by_version: tuple[VersionBudget, ...]
    hurdle_submitted: float  # expected_max_sharpe(n_submitted)
    hurdle_scored: float  # expected_max_sharpe(n_scored)


def _version_key(version: str) -> tuple[int, str]:
    """Natural order for ``vN`` tags so v9 precedes v22 (lexical sort gets it wrong).

    Non-``vN`` strings sort after all numeric versions, then lexically among
    themselves — they never collide with a real version's numeric slot.
    """
    m = re.fullmatch(r"v(\d+)", version)
    return (int(m.group(1)), "") if m is not None else (1_000_000_000, version)


def summarize_budget(rows: Iterable[BatchRow]) -> AlphaBudget:
    """Aggregate per-batch rows into the cumulative + per-version ledger. Pure."""
    materialized = list(rows)
    n_batches = len(materialized)
    n_submitted = sum(r.batch_size for r in materialized)
    n_scored = sum(_scored_for(r) for r in materialized)
    n_known = sum(1 for r in materialized if r.enumerated_count is not None)
    coverage = (n_known / n_batches) if n_batches else 0.0

    agg: dict[str, list[int]] = {}
    for r in materialized:
        bucket = agg.setdefault(r.grammar_version, [0, 0])
        bucket[0] += r.batch_size
        bucket[1] += _scored_for(r)
    by_version = tuple(
        VersionBudget(grammar_version=version, n_submitted=sub, n_scored=sco)
        for version, (sub, sco) in sorted(agg.items(), key=lambda kv: _version_key(kv[0]))
    )

    return AlphaBudget(
        n_batches=n_batches,
        n_submitted=n_submitted,
        n_scored=n_scored,
        scored_coverage=coverage,
        by_version=by_version,
        hurdle_submitted=expected_max_sharpe(n_submitted),
        hurdle_scored=expected_max_sharpe(n_scored),
    )


def _scored_for(row: BatchRow) -> int:
    """Configs selected among for this batch; legacy NULL coalesces to submitted."""
    return row.enumerated_count if row.enumerated_count is not None else row.batch_size


__all__ = [
    "AlphaBudget",
    "BatchRow",
    "VersionBudget",
    "expected_max_sharpe",
    "summarize_budget",
]
