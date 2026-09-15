"""INBOX_LAYOUT contract — submitter writes flat top-level files.

Phase 6 missed this invariant; a per-batch subdirectory layout silently
diverged from `crucible_contracts.INBOX_LAYOUT` and Crucible's
contract-compliant inbox watcher (which skips subdirectories) never
picked up Forge's submissions.

Hard rule #2: missing-or-divergent contract surface is a contracts gap
to surface upstream — but here the contract was correct and Forge was
the diverging side. Logged as D026 (post-Phase-6 hotfix).

See: `crucible_contracts.formats.INBOX_LAYOUT`; Crucible
`src/optbt/data/inbox.py::_iter_inbox_files`.
"""

from __future__ import annotations

from pathlib import Path

from crucible_contracts import INBOX_LAYOUT

from forge.persistence.db import db_connection
from forge.ranking.types import RankedCandidate
from forge.submission.batch import BatchContext
from forge.submission.submitter import submit_batch
from tests.fixtures.contexts import make_batch_context, make_candidate, named_config


def _ctx() -> BatchContext:
    return make_batch_context(seed=7)


def _candidate(name: str, directional_id: str) -> RankedCandidate:
    return make_candidate(named_config(name, directional_id))


def test_submitter_writes_files_flat_at_inbox_root(tmp_path: Path) -> None:
    """`submit_batch` lands every config at `inbox_root/{hash}.json` directly."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"), _candidate("b", "dir_b"))
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)

    top_level_jsons = sorted(inbox.glob("*.json"))
    assert len(top_level_jsons) == 2, (
        f"submitter wrote {len(top_level_jsons)} top-level *.json files; "
        "Crucible's INBOX_LAYOUT-compliant watcher only scans top-level."
    )


def test_submitter_creates_no_per_batch_subdirectory(tmp_path: Path) -> None:
    """No `inbox/{batch_id}/` subdir; batch grouping lives only in `submissions`."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (_candidate("a", "dir_a"),)
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=_ctx(), candidates=cands, inbox_root=inbox)

    subdirs = [p for p in inbox.iterdir() if p.is_dir()]
    # `processed/` and `errors/` are part of INBOX_LAYOUT and may exist if
    # Crucible has already run, but the submitter itself must not create
    # any subdirectory of its own under inbox_root.
    forbidden = [p for p in subdirs if p.name not in {"processed", "errors"}]
    assert forbidden == [], (
        f"submitter created unexpected subdirectories: {forbidden}; "
        "INBOX_LAYOUT permits only top-level *.json + processed/ + errors/."
    )


def test_inbox_layout_contract_advertises_flat_layout() -> None:
    """`INBOX_LAYOUT` itself lists `*.json` (flat) — no subdir glob.

    Defensive guard: if the contract ever changes to permit per-batch
    subdirectories, this test should fail loudly so the submitter and
    its peer invariants can be revisited together.
    """
    assert "*.json" in INBOX_LAYOUT.files
    # No per-batch subdirectory glob should appear.
    allowed_subdirs = {"processed/", "errors/"}
    extra_subdirs = [f for f in INBOX_LAYOUT.files if f.endswith("/") and f not in allowed_subdirs]
    assert extra_subdirs == []
