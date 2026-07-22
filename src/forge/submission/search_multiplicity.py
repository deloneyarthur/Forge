"""Per-slot cumulative ``search_n_trials`` stamping, self-gated (D310/D330).

Crucible's DSR gate charges multiple-comparison deflation at
``n_trials = max(search_n_trials or 1, selection_n_trials or 1)``. Forge
owes the search half (their 07-08 Q1/Q2 answers, D304): the per-slot
cumulative distinct-config count, slot = hypothesis x dte_bucket x
xsect-vs-named, measured from OUR submissions table at submit time —
deliberately slightly ahead of their decided-count.

SELF-GATING — the D306 hazard. Their original Q2 ("populate + no flip")
was internally inconsistent with their live verdict predicate: stamping
against the OLD binding gate would have flipped the bulk of the
component stream to reject (a de-facto standing-gate flip + feedback-era
boundary). Their (a) resolution shipped record-not-bind for
forge-source minimal decisions (§20 ``dsr-record-not-binding-forge-
minimal``), and rows built under that code carry a
``recorded_not_binding`` marker in the ``deflated_sharpe`` gate detail —
their designated deployment signal. Stamping therefore arms only once
that marker is OBSERVED in our own verdicts table; until then every
config ships with ``search_n_trials`` unset (their ``n_trials=1`` path,
today's behavior). Safe under any restart ordering, self-heals when
their runners roll — the D290 dormancy-pull pattern.

Why counts come from ``submissions``, not ``verdicts``: the stamp should
lead the decided count (a config's own trial belongs in its multiplicity
before its verdict exists), and ``config_hash`` is unique-indexed so
``count(*)`` per slot IS the distinct-config count.

OPEN (D330, joint with Crucible — do NOT change unilaterally): whether
the cumulative all-time count is the right denominator at all. Forge
takes no cross-batch argmax — it ships the ranked top-N of each batch as
a stream — so the across-time multiplicity arguably belongs to Crucible's
``selection_n_trials`` (charged at assembly, where a real argmax happens),
and charging both double-counts one search. Changing it would contradict
the agreed D304/Q1 semantic. It is also operationally inert while DSR is
record-not-binding for forge-source rows (§20
``dsr-record-not-binding-forge-minimal``); it only affects what the
recorded number MEANS. Note the practical stakes are small either way:
deflation goes as ``sqrt(2 ln N)``, so N=1,950 and N=105,000 differ by
0.43 annualized Sharpe on the bar, and BOTH sit above this population's
observed maximum (1.964) — see
``~/proj/freeze/analysis/forge_dsr_saturation_mechanism_and_durable_fix_2026-07-22.md``.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import duckdb
    from crucible_contracts import StrategyConfig

    from forge.ranking.types import RankedCandidate

# Their (a) resolution ship date (relay FORGE_search_n_trials_resolution_
# 2026-07-20). Bounding the marker scan here is defensive as well as cheap:
# a stray pre-ship occurrence of the string can never arm the stamp.
_MARKER_SHIP_DATE = "2026-07-20"
_MARKER = "recorded_not_binding"

_XSECT_COMBINER_TYPE = "cross_sectional_rank"

SlotKey = tuple[str, str, str]


def slot_key(config: StrategyConfig) -> SlotKey:
    """Their Q1 slot measure: (hypothesis, dte_bucket, xsect-vs-named)."""
    axis = "xsect" if config.combiner.type == _XSECT_COMBINER_TYPE else "named"
    return (config.hypothesis, config.dte_bucket, axis)


def crucible_record_not_bind_live(db: duckdb.DuckDBPyConnection) -> bool:
    """True once their record-not-bind code is observed live in a verdict.

    The marker rides the ``deflated_sharpe`` gate detail of rows built
    under their new runner code; ``verdicts.gate_results`` preserves it
    verbatim on every reconcile pass.
    """
    row = db.execute(
        """
        SELECT 1 FROM verdicts
        WHERE decided_at >= ? AND gate_results LIKE ?
        LIMIT 1
        """,
        [_MARKER_SHIP_DATE, f"%{_MARKER}%"],
    ).fetchone()
    return row is not None


def slot_counts(db: duckdb.DuckDBPyConnection) -> dict[SlotKey, int]:
    """Cumulative distinct-config count per slot, all-time, from submissions."""
    rows = db.execute(
        """
        SELECT
            json_extract_string(config_json, '$.hypothesis'),
            json_extract_string(config_json, '$.dte_bucket'),
            CASE
                WHEN json_extract_string(config_json, '$.combiner.type') = ?
                THEN 'xsect' ELSE 'named'
            END,
            count(*)
        FROM submissions
        GROUP BY 1, 2, 3
        """,
        [_XSECT_COMBINER_TYPE],
    ).fetchall()
    return {(h, d, axis): int(n) for h, d, axis, n in rows}


def stamp_search_n_trials(
    candidates: Sequence[RankedCandidate],
    counts: Mapping[SlotKey, int],
) -> list[RankedCandidate]:
    """Stamp every candidate with its slot's search CARDINALITY, batch-constant.

    DSR's ``n_trials`` is the size of the set the selection was drawn from,
    not the index of a member within it. All configs a batch emits for one
    slot are a single selection event, so they carry the same value: the
    slot's post-batch cumulative count (``prior_count + n_in_batch``). A
    fresh slot contributing one config therefore stamps 1 — the count
    includes the trial itself, matching their ``or 1`` floor.

    D330 corrects D310's per-config increment, which made a config's
    declared multiplicity depend on its queue position within the batch
    (Crucible, ``crucible_search_n_trials_looks_like_a_counter_2026-07-22``:
    "the penalty a config carries depends on where it happened to land in
    the queue"). Numerically tiny — deflation goes as ``sqrt(2 ln N)``, so
    the observed within-batch span moved the bar 0.000285 sd — but the old
    value was not the quantity the field names.

    ``search_n_trials`` is hash-excluded (contracts 1.19.0), so the stamped
    config keeps its identity — §13.4 idempotency and the enumeration
    determinism of hard rule #6 are untouched (pinned by
    ``tests/invariants/test_search_n_trials_hash_excluded.py``).
    """
    batch_counts: dict[SlotKey, int] = {}
    for candidate in candidates:
        key = slot_key(candidate.report.config)
        batch_counts[key] = batch_counts.get(key, 0) + 1

    stamped: list[RankedCandidate] = []
    for candidate in candidates:
        config = candidate.report.config
        key = slot_key(config)
        n = counts.get(key, 0) + batch_counts[key]
        new_config = config.model_copy(update={"search_n_trials": n})
        stamped.append(
            dataclasses.replace(
                candidate,
                report=dataclasses.replace(candidate.report, config=new_config),
            )
        )
    return stamped
