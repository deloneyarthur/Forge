"""Honest-era training frame for the learned verdict model (D132 / F1).

``build_dataset`` joins ``verdicts ⋈ submissions`` on config_hash (1:1 — the
hash is unique-indexed in submissions per §13.4), hard-cuts rows at the
clean-era label boundary, labels with the D128 honesty predicate imported
from the feedback module (one source of truth), and keeps every refit row:
same config_hash + new crucible_run_id is an independent gate evaluation
(D124 continuity). Row order is ``(decided_at, crucible_run_id)`` so the
frame is deterministic given the DB snapshot.

Design: `docs/proposals/learned-ranker.md` §4 F1.
"""

from __future__ import annotations

import json
from datetime import UTC
from typing import TYPE_CHECKING

import polars as pl
from crucible_contracts import StrategyConfig
from crucible_contracts.models import GateResult

from forge.feedback.rejection_weights import (
    CLEAN_ERA_LABEL_CUT,
    honest_regime_coverage_row,
)
from forge.ranking.features import extract_features

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    import duckdb
    from crucible_contracts import RegistrySnapshot

# A positive label requires BOTH a positive decision and honest coverage;
# any reject variant is 0.
_POSITIVE_DECISIONS: frozenset[str] = frozenset({"component", "promote"})


def parse_gate_results(raw: str) -> dict[str, GateResult]:
    """Rehydrate a verdicts.gate_results JSON payload."""
    return {name: GateResult.model_validate(p) for name, p in json.loads(raw).items()}


def label_for(decision: str, gate_results: Mapping[str, GateResult]) -> int:
    """THE label: positive decision AND D128-honest coverage. Shared by the
    dataset builder and `forge.ranking.evaluation` so they cannot drift."""
    return int(decision in _POSITIVE_DECISIONS and honest_regime_coverage_row(gate_results))


_IDENTITY_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "crucible_run_id": pl.Utf8,
    "config_hash": pl.Utf8,
    "decided_at": pl.Datetime,
    "decision": pl.Utf8,
    "label": pl.Int64,
}


def build_dataset(
    conn: duckdb.DuckDBPyConnection,
    registry: RegistrySnapshot,
    *,
    era_cut: datetime = CLEAN_ERA_LABEL_CUT,
) -> pl.DataFrame:
    """One row per honest-era verdict: identity columns, label, wide features.

    Feature columns are the sorted union of names emitted across rows;
    absent features fill 0.0 (one-hots that did not fire).
    """
    cut = era_cut
    if cut.tzinfo is not None:
        # DuckDB TIMESTAMP columns are naive-UTC by repo convention.
        cut = cut.astimezone(UTC).replace(tzinfo=None)

    rows = conn.execute(
        """
        SELECT v.crucible_run_id, v.config_hash, v.decision, v.decided_at,
               v.gate_results, s.config_json
        FROM verdicts v
        JOIN submissions s ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ?
        ORDER BY v.decided_at, v.crucible_run_id
        """,
        [cut],
    ).fetchall()

    records: list[dict[str, object]] = []
    feature_names: set[str] = set()
    for run_id, config_hash, decision, decided_at, gate_results_json, config_json in rows:
        config = StrategyConfig.model_validate_json(config_json)
        label = label_for(decision, parse_gate_results(gate_results_json))
        features = extract_features(config, registry).as_dict()
        feature_names.update(features)
        records.append(
            {
                "crucible_run_id": str(run_id),
                "config_hash": config_hash,
                "decided_at": decided_at,
                "decision": decision,
                "label": label,
                **features,
            }
        )

    if not records:
        return pl.DataFrame(schema=dict(_IDENTITY_SCHEMA))

    ordered_features = sorted(feature_names)
    for record in records:
        for name in ordered_features:
            record.setdefault(name, 0.0)

    return pl.DataFrame(records).select([*_IDENTITY_SCHEMA, *ordered_features])
