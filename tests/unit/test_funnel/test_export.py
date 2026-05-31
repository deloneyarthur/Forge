"""Tests for ``forge.funnel.export`` (D096 — atomic write of both artifacts)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from forge.funnel.export import (
    FUNNEL_FILENAME,
    VERSION_MAP_FILENAME,
    write_funnel_export,
)
from forge.persistence.db import db_connection

_FIXED_NOW = datetime(2026, 5, 29, 20, 53, tzinfo=UTC)


def _seed_batch(conn: object, *, config_hash: str, grammar_version: str = "v4") -> None:
    bid = uuid.uuid4()
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO batch_summaries
            (forge_batch_id, batch_size, submitted_at, grammar_version,
             registry_version, prefilter_rejections, enumerated_count,
             survived_count, enumerated_by_hypothesis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(bid),
            1,
            _FIXED_NOW,
            grammar_version,
            "reg",
            json.dumps({"expected_trades": 90}),
            100,
            10,
            json.dumps({"regime_arbitrage": 100}),
        ],
    )
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [str(uuid.uuid4()), str(bid), config_hash, "{}", _FIXED_NOW, "submitted"],
    )


def test_writes_both_artifacts(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    exports = tmp_path / "exports"
    with db_connection(forge_db) as conn:
        _seed_batch(conn, config_hash="hash1")
        funnel_path, vm_path = write_funnel_export(conn, exports, now=_FIXED_NOW)

    assert funnel_path == exports / FUNNEL_FILENAME
    assert vm_path == exports / VERSION_MAP_FILENAME
    assert funnel_path.exists()
    assert vm_path.exists()


def test_funnel_file_shape(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    exports = tmp_path / "exports"
    with db_connection(forge_db) as conn:
        _seed_batch(conn, config_hash="hash1")
        funnel_path, _ = write_funnel_export(conn, exports, now=_FIXED_NOW)

    doc = json.loads(funnel_path.read_text())
    assert doc["schema_version"] == "1.0"
    assert doc["exported_at"] == _FIXED_NOW.isoformat()
    v4 = doc["per_grammar_version"]["v4"]
    assert v4["enumerated"] == 100
    assert v4["survived_prefilters"] == 10
    assert v4["submitted"] == 1
    assert v4["rejection_breakdown"] == {"expected_trades": 90}
    assert v4["enumerated_by_hypothesis"] == {"regime_arbitrage": 100}


def test_version_map_file_shape(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    exports = tmp_path / "exports"
    with db_connection(forge_db) as conn:
        _seed_batch(conn, config_hash="hash1", grammar_version="v4")
        _seed_batch(conn, config_hash="hash2", grammar_version="v3")
        _, vm_path = write_funnel_export(conn, exports, now=_FIXED_NOW)

    doc = json.loads(vm_path.read_text())
    assert doc["schema_version"] == "1.0"
    assert doc["exported_at"] == _FIXED_NOW.isoformat()
    assert doc["config_hash_grammar_version"] == {"hash1": "v4", "hash2": "v3"}


def test_atomic_no_tmp_left_behind(tmp_path: Path) -> None:
    """tmp-then-rename leaves no `.tmp` sibling for Crucible's reader to trip on."""
    forge_db = tmp_path / "forge.db"
    exports = tmp_path / "exports"
    with db_connection(forge_db) as conn:
        _seed_batch(conn, config_hash="hash1")
        write_funnel_export(conn, exports, now=_FIXED_NOW)
    assert list(exports.glob("*.tmp")) == []


def test_creates_exports_dir_if_absent(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    exports = tmp_path / "nested" / "exports"  # does not exist yet
    assert not exports.exists()
    with db_connection(forge_db) as conn:
        write_funnel_export(conn, exports, now=_FIXED_NOW)
    assert exports.exists()


def test_overwrites_previous_export(tmp_path: Path) -> None:
    """A second write replaces the first (refreshed per batch)."""
    forge_db = tmp_path / "forge.db"
    exports = tmp_path / "exports"
    with db_connection(forge_db) as conn:
        _seed_batch(conn, config_hash="hash1")
        write_funnel_export(conn, exports, now=_FIXED_NOW)
        _seed_batch(conn, config_hash="hash2")
        funnel_path, vm_path = write_funnel_export(conn, exports, now=_FIXED_NOW)
    vm = json.loads(vm_path.read_text())["config_hash_grammar_version"]
    assert vm == {"hash1": "v4", "hash2": "v4"}
    assert json.loads(funnel_path.read_text())["per_grammar_version"]["v4"]["submitted"] == 2
