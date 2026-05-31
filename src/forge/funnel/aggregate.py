"""Pure aggregation for the pre-filter funnel export (D096 — Part B).

Two reads over Forge's DB, both clock-free and filesystem-free:

- `build_funnel_export` rolls `batch_summaries` up per grammar version into
  the two upstream funnel stages (`enumerated`, `survived_prefilters`) plus
  the rejection-by-filter and enumerated-by-hypothesis breakdowns.
- `build_version_map` produces the `config_hash -> grammar_version` join-map
  (`submissions` ⋈ `batch_summaries`) — Forge's interim source for Crucible's
  funnel Stage 0 until the durable contracts field lands (D096 Part A).

Only batches that carry the D096 funnel counts are aggregated; pre-
instrumentation batches (NULL `enumerated_count`) are excluded so the funnel
invariant `sum(rejection_breakdown) == enumerated - survived` holds exactly.
The exclusion count is reported in `FunnelExport.coverage`, never silent.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

from forge.funnel.types import SCHEMA_VERSION, FunnelExport, PerGrammarVersionFunnel

if TYPE_CHECKING:
    import duckdb


def _loads(raw: object) -> dict[str, int]:
    """Parse a JSON count-map column; tolerate NULL and already-decoded dicts."""
    decoded = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(decoded, dict):
        return {}
    return {str(k): int(v) for k, v in decoded.items()}


def build_funnel_export(db: duckdb.DuckDBPyConnection) -> FunnelExport:
    """Aggregate `batch_summaries` into a per-grammar-version funnel.

    Pre-instrumentation batches (NULL `enumerated_count`) are skipped to keep
    the funnel invariant exact; the total-vs-included batch counts are recorded
    in `coverage`.
    """
    total_row = db.execute("SELECT COUNT(*) FROM batch_summaries").fetchone()
    batches_total = int(total_row[0]) if total_row is not None else 0

    rows = db.execute(
        """
        SELECT grammar_version, batch_size, enumerated_count, survived_count,
               prefilter_rejections, enumerated_by_hypothesis
        FROM batch_summaries
        WHERE enumerated_count IS NOT NULL
        """
    ).fetchall()

    batches: Counter[str] = Counter()
    enumerated: Counter[str] = Counter()
    survived: Counter[str] = Counter()
    submitted: Counter[str] = Counter()
    rejections: dict[str, Counter[str]] = {}
    by_hyp: dict[str, Counter[str]] = {}

    for gv, batch_size, enum_count, surv_count, rej_json, hyp_json in rows:
        version = str(gv)
        batches[version] += 1
        enumerated[version] += int(enum_count)
        survived[version] += int(surv_count or 0)
        submitted[version] += int(batch_size or 0)
        for fname, count in _loads(rej_json).items():
            rejections.setdefault(version, Counter())[fname] += count
        for hyp, count in _loads(hyp_json).items():
            by_hyp.setdefault(version, Counter())[hyp] += count

    per_version = {
        version: PerGrammarVersionFunnel(
            grammar_version=version,
            batches=batches[version],
            enumerated=enumerated[version],
            survived_prefilters=survived[version],
            submitted=submitted[version],
            rejection_breakdown=dict(rejections.get(version, Counter())),
            enumerated_by_hypothesis=dict(by_hyp.get(version, Counter())),
        )
        for version in batches
    }

    return FunnelExport(
        schema_version=SCHEMA_VERSION,
        per_grammar_version=per_version,
        coverage={
            "batches_total": batches_total,
            "batches_with_funnel_counts": len(rows),
        },
    )


def build_version_map(db: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Return `{config_hash: grammar_version}` for every submitted config.

    Well-defined as a function: hard rule #9 unique-indexes
    `submissions.config_hash`, so each hash belongs to exactly one batch and
    therefore one grammar version. This is the interim Stage-0 source Crucible
    joins against (`runs.config_hash` -> grammar version).
    """
    rows = db.execute(
        """
        SELECT s.config_hash, b.grammar_version
        FROM submissions s
        JOIN batch_summaries b ON s.forge_batch_id = b.forge_batch_id
        """
    ).fetchall()
    return {str(config_hash): str(grammar_version) for config_hash, grammar_version in rows}


__all__ = ["build_funnel_export", "build_version_map"]
