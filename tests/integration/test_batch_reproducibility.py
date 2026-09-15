"""Full-pipeline byte-determinism (§13.1, hard rule #6) on the weekly campaign.

§13.1 promises ``(grammar_version, registry_hash, seed) -> the same sequence of configs``.
``tests/invariants/test_phase2_invariants.py`` covers the enumerator in isolation and the
goldens pin the cold-start draw. This test extends the guarantee to the whole per-run
pipeline as it exists after the cutover (D416): enumerate -> pre-filter battery -> challenger
gate -> in-cell rank -> submit. Two independent runs with identical inputs into two DISJOINT
workspaces (separate forge.db, inbox, records) must produce the same ordered
``submitted_hashes``, the same minted ``batch_id`` and byte-identical inbox files.

The wall-clock fields (``started_at``, ``run_id``) are allowed to differ — the contract is on
enumeration + selection content, not on timestamps.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit.test_campaign.test_run import _env, _run


def _inbox_bytes(inbox: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(inbox.glob("*.json"))}


def test_two_disjoint_workspaces_produce_identical_submissions(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = _run(_env(tmp_path / "a"), dry_run=False)
    second = _run(_env(tmp_path / "b"), dry_run=False)

    assert first.status == "ok"
    assert first.submitted > 0, "the fixture env must fire the exploration floor"
    assert first.submitted_hashes == second.submitted_hashes
    assert first.batch_id == second.batch_id
    assert first.seed == second.seed
    assert first.registry_hash == second.registry_hash

    a = _inbox_bytes(tmp_path / "a" / "inbox")
    b = _inbox_bytes(tmp_path / "b" / "inbox")
    assert a, "the first workspace must hold inbox files"
    assert a == b, "inbox JSON must be byte-identical across workspaces"
    assert sorted(p.removesuffix(".json") for p in a) == sorted(first.submitted_hashes)
