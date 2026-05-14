"""Tests for ``forge.submission.batch`` (D023/D8 — module 7).

`mint_batch_id` derives a UUID from the §13.1 deterministic triple so
re-running the same `(grammar_version, registry_hash, seed)` produces
the same batch ID. `BatchContext` carries the per-batch metadata that
the submitter writes to `batch_summaries`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from forge.submission.batch import BatchContext, mint_batch_id

# ---------------------------------------------------------------------------
# mint_batch_id determinism
# ---------------------------------------------------------------------------


def test_mint_batch_id_is_deterministic_for_same_triple() -> None:
    a = mint_batch_id(seed=42, grammar_version="v1", registry_hash="abc1234567890def")
    b = mint_batch_id(seed=42, grammar_version="v1", registry_hash="abc1234567890def")
    assert a == b


def test_mint_batch_id_changes_with_seed() -> None:
    a = mint_batch_id(seed=1, grammar_version="v1", registry_hash="abc")
    b = mint_batch_id(seed=2, grammar_version="v1", registry_hash="abc")
    assert a != b


def test_mint_batch_id_changes_with_grammar_version() -> None:
    a = mint_batch_id(seed=1, grammar_version="v1", registry_hash="abc")
    b = mint_batch_id(seed=1, grammar_version="v2", registry_hash="abc")
    assert a != b


def test_mint_batch_id_changes_with_registry_hash() -> None:
    a = mint_batch_id(seed=1, grammar_version="v1", registry_hash="abc")
    b = mint_batch_id(seed=1, grammar_version="v1", registry_hash="def")
    assert a != b


def test_mint_batch_id_returns_uuid() -> None:
    bid = mint_batch_id(seed=0, grammar_version="v1", registry_hash="abc")
    assert isinstance(bid, uuid.UUID)


def test_mint_batch_id_version_marker_is_set() -> None:
    """UUID's `version` field should be set (any value 1-5) — confirms
    we're producing a well-formed UUID, not a raw 16-byte blob."""
    bid = mint_batch_id(seed=0, grammar_version="v1", registry_hash="abc")
    assert bid.version is not None
    assert 1 <= bid.version <= 5


# ---------------------------------------------------------------------------
# BatchContext — frozen value type
# ---------------------------------------------------------------------------


def test_batch_context_constructs() -> None:
    bid = mint_batch_id(seed=0, grammar_version="v1", registry_hash="abc")
    ts = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
    ctx = BatchContext(
        batch_id=bid,
        grammar_version="v1",
        registry_hash="abc1234567890def",
        submitted_at=ts,
        seed=0,
    )
    assert ctx.batch_id == bid
    assert ctx.grammar_version == "v1"
    assert ctx.submitted_at == ts
    assert ctx.seed == 0


def test_batch_context_is_frozen() -> None:
    ctx = BatchContext(
        batch_id=mint_batch_id(seed=0, grammar_version="v1", registry_hash="abc"),
        grammar_version="v1",
        registry_hash="abc",
        submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        seed=0,
    )
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        ctx.grammar_version = "v2"  # type: ignore[misc]


def test_batch_context_requires_tz_aware_submitted_at() -> None:
    """Naive datetimes leak silently in DB writes; reject at construction."""
    with pytest.raises(ValueError, match=r"timezone"):
        BatchContext(
            batch_id=mint_batch_id(seed=0, grammar_version="v1", registry_hash="abc"),
            grammar_version="v1",
            registry_hash="abc",
            submitted_at=datetime(2026, 5, 13),  # naive  # noqa: DTZ001
            seed=0,
        )


# ---------------------------------------------------------------------------
# Different inputs to BatchContext yield batch_ids that match mint_batch_id
# ---------------------------------------------------------------------------


def test_batch_context_records_seed_and_registry() -> None:
    """`seed` + `registry_hash` make the BatchContext re-derivable; tests
    that don't pass through `forge run` can build the same context."""
    bid = mint_batch_id(seed=99, grammar_version="v1", registry_hash="zzz")
    ctx = BatchContext(
        batch_id=bid,
        grammar_version="v1",
        registry_hash="zzz",
        submitted_at=datetime(2026, 5, 13, tzinfo=UTC),
        seed=99,
    )
    # Re-mint the same way; should match.
    assert (
        mint_batch_id(
            seed=ctx.seed,
            grammar_version=ctx.grammar_version,
            registry_hash=ctx.registry_hash,
        )
        == ctx.batch_id
    )
