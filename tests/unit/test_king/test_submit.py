"""Meta-king submission: provenance stamping, DB recording, idempotency.

The submit path is distinct from the §7 battery submitter (kings carry no
PreFilterReport). It must: stamp source/search_n_trials/grammar_version (all
hash-excluded → config_hash unchanged), write submissions + batch_summaries
rows, write the inbox JSON, and be idempotent on the config_hash unique index.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from crucible_contracts import StrategyConfig

from forge.king.search import King
from forge.king.submit import submit_kings
from forge.persistence.db import db_connection
from forge.submission.batch import BatchContext, mint_batch_id
from tests.fixtures.strategy_configs import grammar_valid_baseline


def _ctx(seed: int = 1) -> BatchContext:
    return BatchContext(
        batch_id=mint_batch_id(
            seed=seed, grammar_version="v22", registry_hash="rh", extra_inputs="meta_king|test"
        ),
        grammar_version="v22",
        registry_hash="rh",
        submitted_at=datetime(2026, 6, 16, 12, tzinfo=UTC),
        seed=seed,
    )


def _kings() -> list[King]:
    a = grammar_valid_baseline(name="king_a")
    b = grammar_valid_baseline(name="king_b")
    return [King(config=a, predicted_score=0.74), King(config=b, predicted_score=0.70)]


def test_submit_stamps_provenance_and_records(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    kings = _kings()
    with db_connection(":memory:") as db:
        result = submit_kings(db, batch=_ctx(), kings=kings, inbox_root=inbox, search_n_trials=2000)
        assert result.submitted_count == 2
        assert result.skipped_duplicate_count == 0
        assert result.failed_count == 0

        rows = db.execute(
            "SELECT config_hash, config_json, status FROM submissions ORDER BY config_hash"
        ).fetchall()
        assert len(rows) == 2
        for config_hash, config_json, status in rows:
            assert status == "submitted"
            payload = json.loads(config_json)
            assert payload["source"] == "meta_king"
            assert payload["search_n_trials"] == 2000
            assert payload["grammar_version"] == "v22"
            # hash-excluded fields don't change the identity hash / inbox filename
            assert (inbox / f"{config_hash}.json").exists()

        # the batch_summaries row was written (funnel/feedback joins need it)
        (n_batches,) = db.execute("SELECT COUNT(*) FROM batch_summaries").fetchone()
        assert n_batches == 1


def test_submit_is_idempotent(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    kings = _kings()
    with db_connection(":memory:") as db:
        first = submit_kings(db, batch=_ctx(), kings=kings, inbox_root=inbox, search_n_trials=500)
        second = submit_kings(db, batch=_ctx(), kings=kings, inbox_root=inbox, search_n_trials=500)
    assert first.submitted_count == 2
    assert second.submitted_count == 0
    assert second.skipped_duplicate_count == 2


def test_submit_does_not_change_config_hash(tmp_path: Path) -> None:
    """The submitted inbox filename == the bare config's hash (fields hash-excluded)."""
    bare: StrategyConfig = grammar_valid_baseline(name="king_c")
    bare_hash = bare.config_hash
    with db_connection(":memory:") as db:
        submit_kings(
            db,
            batch=_ctx(),
            kings=[King(config=bare, predicted_score=0.5)],
            inbox_root=tmp_path / "inbox",
            search_n_trials=10,
        )
    assert (tmp_path / "inbox" / f"{bare_hash}.json").exists()


def test_submit_empty_batch(tmp_path: Path) -> None:
    with db_connection(":memory:") as db:
        result = submit_kings(
            db, batch=_ctx(), kings=[], inbox_root=tmp_path / "inbox", search_n_trials=0
        )
    assert result.submitted_count == 0
    assert result.records == ()
