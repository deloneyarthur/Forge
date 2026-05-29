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
    extra_inputs: str = "",
) -> uuid.UUID:
    """Derive a deterministic UUID from the §13.1 enumeration identity.

    The same identity always produces the same UUID, so a re-run with
    identical inputs is a structural no-op: the unique-indexed
    `submissions.config_hash` rejects every duplicate insertion.

    H-7 (audit 2026-05-29): `(seed, grammar_version, registry_hash)` is NOT
    the full enumeration identity — `auto_tightened_thresholds.yaml` (D073)
    and the universe pool (D078) also shadow the sampler's draws. The proposer
    rewriting the tightenings YAML (the whole point of D073) changed the config
    population WITHOUT bumping grammar_version, so the old triple minted the
    same UUID for a different batch, corrupting `batch_summaries`/`promotion_rate`.
    `extra_inputs` (a fingerprint of those shadow inputs) closes that. Empty
    `extra_inputs` reproduces the pre-fix UUID exactly (back-compat).

    The output is a UUID4-shape (version 4 set); the bytes are SHA-256 of the
    identity, truncated to 16 and tagged.
    """
    payload = f"forge|{grammar_version}|{registry_hash}|{seed}"
    if extra_inputs:
        payload += f"|{extra_inputs}"
    digest = hashlib.sha256(payload.encode()).digest()[:16]
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
    # H-3/M-14: fingerprint of the enumeration-shadowing inputs (auto-tightenings
    # YAML + universe pool) that registry_hash/grammar_version don't capture.
    # Persisted to batch_summaries so a batch is reproducible from recorded state.
    enumeration_inputs_hash: str = ""

    def __post_init__(self) -> None:
        if self.submitted_at.tzinfo is None:
            msg = "BatchContext.submitted_at must be timezone-aware; use forge.core.clock.utc_now()"
            raise ValueError(msg)


__all__ = ["BatchContext", "mint_batch_id"]
