"""D055 / P1-3 — `scripts/requeue_high_value_configs.py` grammar_version filter.

Pre-D055 the re-queue script copied v1-era processed configs back into
Crucible's inbox while v2 was the active grammar. v1-only signals silently
reject on Crucible's side, invisible to Forge. This test pins the filter
that skips non-current-version configs and reports per-version skip counts.
"""

from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime
from pathlib import Path

from forge.persistence.db import db_connection

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "requeue_high_value_configs.py"


def _load_script() -> object:
    """Load the script as a module so its functions are testable."""
    spec = importlib.util.spec_from_file_location("requeue_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _insert_batch_with_submissions(
    db_path: Path,
    *,
    grammar_version: str,
    config_hashes: list[str],
) -> None:
    """Insert a batch_summaries row + N submissions rows under that batch."""
    batch_id = uuid.uuid4()
    ts = datetime(2026, 5, 13, 12, tzinfo=UTC)
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
            "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
            [str(batch_id), len(config_hashes), ts, grammar_version, "reg_abc"],
        )
        for h in config_hashes:
            conn.execute(
                "INSERT INTO submissions (forge_candidate_id, forge_batch_id, "
                "config_hash, config_json, submitted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [str(uuid.uuid4()), str(batch_id), h, "{}", ts, "submitted"],
            )


def test_d055_filter_keeps_only_current_grammar_version(tmp_path: Path) -> None:
    """D055: configs submitted under a stale grammar are skipped; current-version
    configs pass through unchanged."""
    mod = _load_script()
    forge_db = tmp_path / "forge.db"
    _insert_batch_with_submissions(
        forge_db,
        grammar_version="v1",
        config_hashes=["v1_hash_aaa", "v1_hash_bbb"],
    )
    _insert_batch_with_submissions(
        forge_db,
        grammar_version="v2",
        config_hashes=["v2_hash_ccc"],
    )
    matching, skipped = mod.filter_to_current_grammar_version(
        forge_db,
        ["v1_hash_aaa", "v1_hash_bbb", "v2_hash_ccc"],
        current_grammar_version="v2",
    )
    assert matching == ["v2_hash_ccc"]
    assert skipped == {"v1": 2}


def test_d055_filter_handles_unknown_hashes(tmp_path: Path) -> None:
    """D055: a hash not present in submissions falls into a special
    `(unknown)` bucket so the operator can tell when their re-queue
    selection contains non-Forge-originating configs."""
    mod = _load_script()
    forge_db = tmp_path / "forge.db"
    _insert_batch_with_submissions(
        forge_db,
        grammar_version="v2",
        config_hashes=["v2_hash_ccc"],
    )
    matching, skipped = mod.filter_to_current_grammar_version(
        forge_db,
        ["v2_hash_ccc", "ghost_hash"],
        current_grammar_version="v2",
    )
    assert matching == ["v2_hash_ccc"]
    assert skipped == {"(unknown)": 1}


def test_d055_filter_no_skips_when_all_match(tmp_path: Path) -> None:
    """D055: identity case — every candidate is current; empty skip dict."""
    mod = _load_script()
    forge_db = tmp_path / "forge.db"
    _insert_batch_with_submissions(
        forge_db,
        grammar_version="v2",
        config_hashes=["a", "b", "c"],
    )
    matching, skipped = mod.filter_to_current_grammar_version(
        forge_db,
        ["a", "b", "c"],
        current_grammar_version="v2",
    )
    assert sorted(matching) == ["a", "b", "c"]
    assert skipped == {}
