"""Step 12 of the weekly run: submit the ranked candidates and record the funnel counts
(Batch 6 A4 split from run.py).

WHY a module: the submit path owns Crucible-facing side effects (inbox files, the funnel
aggregate, shadow scores) and the SIGTERM stop contract (D423); keeping it apart from the
decision code makes the write boundary easy to audit."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from forge.core.clock import utc_now

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot

    from forge.prefilters.types import PreFilterReport
    from forge.ranking.types import RankedCandidate


def _real_feature_cache(registry: RegistrySnapshot, seed: int) -> object:
    from forge.prefilters.factory import build_feature_cache  # noqa: PLC0415

    return build_feature_cache(registry, seed, require_real=True)


def _submit(
    ranked: Sequence[RankedCandidate],
    *,
    lanes: Mapping[str, frozenset[str]],
    forge_db_path: Path,
    inbox_root: Path,
    models_dir: Path,
    registry: RegistrySnapshot,
    grammar_version: str,
    reg_hash: str,
    enum_inputs: str,
    seed: int,
    reports: Sequence[PreFilterReport],
    notes: list[str],
) -> tuple[str, int, int]:
    """Submit the ranked candidates; returns (batch_id, submitted, unsubmitted_after_stop).

    Funnel contract (D096): `enumerated_count` is the KEPT sample that went through the
    battery (`reports`), `survived_count` the reports that passed, and the per-filter rejection
    counts recorded right after the batch row so `forge_funnel.json` satisfies
    sum(rejection_breakdown) == enumerated - survived for campaign batches too (G6).
    """
    from forge.campaign.stop import stop_requested  # noqa: PLC0415
    from forge.funnel.export import write_funnel_export  # noqa: PLC0415
    from forge.persistence.db import db_connection  # noqa: PLC0415
    from forge.ranking.model import QUALITY_LANE_TARGET  # noqa: PLC0415
    from forge.ranking.shadow import run_shadow_scoring  # noqa: PLC0415
    from forge.submission.batch import BatchContext, mint_batch_id  # noqa: PLC0415
    from forge.submission.search_multiplicity import (  # noqa: PLC0415
        crucible_record_not_bind_live,
        slot_counts,
        stamp_search_n_trials,
    )
    from forge.submission.submitter import (  # noqa: PLC0415
        record_prefilter_rejections,
        submit_batch,
    )

    batch = BatchContext(
        batch_id=mint_batch_id(
            seed=seed,
            grammar_version=grammar_version,
            registry_hash=reg_hash,
            extra_inputs=f"{enum_inputs}|campaign",
        ),
        grammar_version=grammar_version,
        registry_hash=reg_hash,
        submitted_at=utc_now(),
        seed=seed,
        enumeration_inputs_hash=enum_inputs,
    )
    candidates = list(ranked)
    with db_connection(forge_db_path) as conn:
        if crucible_record_not_bind_live(conn):
            candidates = stamp_search_n_trials(candidates, slot_counts(conn))
            notes.append("search_n_trials: stamped")
        result = submit_batch(
            conn,
            batch=batch,
            candidates=candidates,
            inbox_root=inbox_root,
            enumerated_count=len(reports),
            survived_count=sum(1 for report in reports if report.passed),
            enumerated_by_hypothesis=dict(Counter(report.config.hypothesis for report in reports)),
            extra_lane_hashes=lanes,
            should_stop=stop_requested,
        )
        # D062/D064 per-filter rejection counts -> batch_summaries (same connection, so the
        # UPDATE sees the row submit_batch just inserted); the funnel export reads them.
        record_prefilter_rejections(conn, batch_id=result.batch_id, reports=reports)
        try:
            funnel_path, _ = write_funnel_export(conn, forge_db_path.parent / "exports")
            notes.append(f"funnel_export: {funnel_path.name}")
        except Exception as exc:
            notes.append(f"funnel_export skipped: {type(exc).__name__}: {exc}")
        shadow = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=candidates,
            registry=registry,
            batch_id=str(result.batch_id),
            scored_at=batch.submitted_at,
            robustness_target=QUALITY_LANE_TARGET,
        )
        if shadow:
            notes.append(f"shadow_scores={shadow}")
    notes.append(
        f"submit: {result.submitted_count} submitted, {result.skipped_duplicate_count} duplicate, "
        f"{result.failed_count} failed"
    )
    return (
        str(result.batch_id),
        result.submitted_count,
        result.remaining_count if result.stopped_early else 0,
    )
