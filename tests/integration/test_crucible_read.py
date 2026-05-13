"""Phase 0 integration: Forge can read a Crucible-shape runs DB via crucible_contracts.

Verifies that the read path Forge will use in Phase 5 works end-to-end against
an empty synthetic Crucible DB. The §12 Phase 0 deliverable: "first successful
read of Crucible's runs DB (synthetic data; Crucible may not be built yet)."
"""

from __future__ import annotations

from pathlib import Path

from crucible_contracts import get_recent_gated_runs

from tests.fixtures.synthetic_crucible_db import ephemeral_crucible_db


def test_empty_crucible_db_returns_empty_list(tmp_path: Path) -> None:
    with ephemeral_crucible_db(tmp_path) as db_path:
        runs = get_recent_gated_runs(db_path, limit=10)
    assert runs == []


def test_crucible_db_file_created(tmp_path: Path) -> None:
    with ephemeral_crucible_db(tmp_path) as db_path:
        assert db_path.exists()
