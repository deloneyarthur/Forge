"""Per-batch context + deterministic batch_id minting.

`mint_batch_id` derives a UUID from the §13.1 deterministic triple
`(grammar_version, registry_hash, seed)`. Same triple → same UUID;
re-running the exact same batch produces the same batch_id, which
combined with `submissions.config_hash` unique-indexing means a re-run
is a no-op (hard rule #9 idempotency).

`BatchContext` is the frozen value the submitter passes to every
candidate-write call. It carries the metadata that lands in
`batch_summaries` and on each `submissions` row.

D023/D8 — module 7.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime


def mint_batch_id(
    *,
    seed: int,
    grammar_version: str,
    registry_hash: str,
) -> uuid.UUID:
    """Derive a deterministic UUID from the §13.1 triple.

    The same `(seed, grammar_version, registry_hash)` always produces
    the same UUID. The submitter relies on this so a re-run with
    identical inputs is a structural no-op: the unique-indexed
    `submissions.config_hash` rejects every duplicate insertion.

    The output is a UUID4-shape (version 4 set); the bytes are derived
    from SHA-256 of the triple, then truncated to 16 bytes and tagged.
    """
    payload = f"forge|{grammar_version}|{registry_hash}|{seed}".encode()
    digest = hashlib.sha256(payload).digest()[:16]
    return uuid.UUID(bytes=digest, version=4)


@dataclass(frozen=True, slots=True)
class BatchContext:
    """The per-batch metadata the submitter carries.

    `submitted_at` must be tz-aware (use `forge.core.clock.utc_now()`).
    Naive datetimes leak into DuckDB as ambiguous timestamps, so the
    constructor rejects them.
    """

    batch_id: uuid.UUID
    grammar_version: str
    registry_hash: str
    submitted_at: datetime
    seed: int

    def __post_init__(self) -> None:
        if self.submitted_at.tzinfo is None:
            msg = "BatchContext.submitted_at must be timezone-aware; use forge.core.clock.utc_now()"
            raise ValueError(msg)


__all__ = ["BatchContext", "mint_batch_id"]
