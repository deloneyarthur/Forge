"""forge.submission — Crucible inbox submitter (Phase 4).

The §7.3 rate limiter left in Batch 5 G4 (D421): the weekly campaign is capped by
`CampaignConfig.weekly_cap` and refuses at boot on an inbox backlog, so nothing paces a
24/7 stream any more."""

from __future__ import annotations

from forge.submission.batch import BatchContext, mint_batch_id
from forge.submission.pre_filter_logger import record_pre_filter_logs
from forge.submission.submitter import (
    BatchSubmissionResult,
    SubmissionRecord,
    SubmissionStatus,
    submit_batch,
)

__all__ = [
    "BatchContext",
    "BatchSubmissionResult",
    "SubmissionRecord",
    "SubmissionStatus",
    "mint_batch_id",
    "record_pre_filter_logs",
    "submit_batch",
]
