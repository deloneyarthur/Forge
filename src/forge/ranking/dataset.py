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
    is_ve_ghost_label,
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

# Continuous worst-quartile regression targets (tail-aware ranker T1,
# `docs/proposals/tail-aware-ranker.md`). Each reads `gate_results[gate].value`
# — Forge consumes Crucible's already-computed metrics, never recomputes (§1.2).
# Null when the gate is absent or carried no value. These are LABELS for the
# regression head, never features (excluded from both models' feature sets).
TARGET_COLUMNS: tuple[str, ...] = (
    "target_cpcv_p25",
    "target_wf_median",
    "target_regime_stress",
    # WF floor (D191): the quality-lane target. Gate-time-emitted as a METRIC (not a gate)
    # in `gate_results` from 2026-06-19 (Crucible); null on pre-emission verdicts.
    "target_wf_p25",
    "target_wf_p10",
)
_TARGET_GATE: tuple[tuple[str, str], ...] = (
    ("target_cpcv_p25", "cpcv_sharpe_p25"),
    ("target_wf_median", "walk_forward_sharpe_median"),
    ("target_regime_stress", "regime_stress_p25_return"),
    ("target_wf_p25", "wf_sharpe_p25"),
    ("target_wf_p10", "wf_sharpe_p10"),
)

# A train-time conditioning feature (= the D128 honesty predicate, §8.2): lets
# the regression head discount the noisier `coverage_unverified` cpcv values.
# Fixed to 1.0 at score time (assume verified) to avoid train/serve skew.
# Excluded from the P(component) logistic model — collinear with its honesty label.
COVERAGE_FEATURE: str = "coverage_verified"


def _gate_value(gate_results: Mapping[str, GateResult], name: str) -> float | None:
    """The numeric value Crucible recorded for a gate, or None if absent."""
    result = gate_results.get(name)
    return None if result is None or result.value is None else float(result.value)


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
        # D290: ghost-era ve labels are fiction (Crucible 07-19 close-out) —
        # they never enter the training frame.
        if is_ve_ghost_label(config.hypothesis, decided_at):
            continue
        gate_results = parse_gate_results(gate_results_json)
        features = extract_features(config, registry).as_dict()
        feature_names.update(features)
        records.append(
            {
                "crucible_run_id": str(run_id),
                "config_hash": config_hash,
                "decided_at": decided_at,
                "decision": decision,
                "label": label_for(decision, gate_results),
                COVERAGE_FEATURE: float(honest_regime_coverage_row(gate_results)),
                **{col: _gate_value(gate_results, gate) for col, gate in _TARGET_GATE},
                **features,
            }
        )

    leading = [*_IDENTITY_SCHEMA, *TARGET_COLUMNS, COVERAGE_FEATURE]
    target_floats: dict[str, pl.DataType | type[pl.DataType]] = {
        c: pl.Float64 for c in (*TARGET_COLUMNS, COVERAGE_FEATURE)
    }
    if not records:
        return pl.DataFrame(schema={**_IDENTITY_SCHEMA, **target_floats})

    ordered_features = sorted(feature_names)
    for record in records:
        for name in ordered_features:
            record.setdefault(name, 0.0)

    return pl.DataFrame(records, schema_overrides=target_floats).select(
        [*leading, *ordered_features]
    )


def build_label_frame(
    conn: duckdb.DuckDBPyConnection,
    registry: RegistrySnapshot,
    *,
    label: Mapping[str, float],
    target_name: str,
    stamp: datetime,
) -> pl.DataFrame:
    """Training frame whose target is sourced from a per-component LABEL (e.g. Crucible's
    refit-distribution ``wf_sharpe_p25``) rather than ``gate_results`` — for a target the gate
    never persists per-verdict. Config features come from the submissions configs (same
    ``extract_features`` path as :func:`build_dataset`); ``coverage_verified`` is 1.0 (the refit
    is honest by construction); every row's ``decided_at`` is ``stamp`` (the label's generation
    time → ``trained_through``). ``target_name`` is excluded from features by the trainer.
    """
    empty_schema: dict[str, pl.DataType | type[pl.DataType]] = {
        "config_hash": pl.Utf8,
        "decided_at": pl.Datetime,
        COVERAGE_FEATURE: pl.Float64,
        target_name: pl.Float64,
    }
    hashes = list(label)
    if not hashes:
        return pl.DataFrame(schema=empty_schema)
    placeholders = ",".join("?" * len(hashes))
    rows = conn.execute(
        f"SELECT config_hash, config_json FROM submissions WHERE config_hash IN ({placeholders})",  # noqa: S608 -- placeholders only
        hashes,
    ).fetchall()
    records: list[dict[str, object]] = []
    feature_names: set[str] = set()
    for config_hash, config_json in rows:
        config = StrategyConfig.model_validate_json(config_json)
        features = extract_features(config, registry).as_dict()
        feature_names.update(features)
        records.append(
            {
                "config_hash": config_hash,
                "decided_at": stamp,
                COVERAGE_FEATURE: 1.0,
                target_name: float(label[config_hash]),
                **features,
            }
        )
    if not records:
        return pl.DataFrame(schema=empty_schema)
    ordered_features = sorted(feature_names)
    for record in records:
        for name in ordered_features:
            record.setdefault(name, 0.0)
    overrides = {target_name: pl.Float64, COVERAGE_FEATURE: pl.Float64}
    return pl.DataFrame(records, schema_overrides=overrides).select(
        ["config_hash", "decided_at", COVERAGE_FEATURE, target_name, *ordered_features]
    )
