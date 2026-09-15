"""A registered read must not be able to come due silently (D389/D392), now judged at the
weekly run's boot instead of by a separate timer (Batch 5 G0).

Four properties, carried over from the retired `scripts/freeze_read_watcher.py`:
  1. a prereg whose clock is REACHED reports DUE (the boot check fails, the unit pages);
  2. a prereg whose clock is NOT reached reports how far away it is and passes;
  3. a prereg with NO machine-readable clock is UNWATCHABLE and fails loudly: the D389 defect
     was never a broken watcher, it was a claim no watcher could have checked;
  4. the judge never reads the metric: it counts rows in the registered basis and nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path

from forge.feedback.preregistration import assess_watch_clocks, open_registrations_raw

_WATCHABLE = {
    "prereg_id": "aaaaaaaaaaaa",
    "status": "registered",
    "claim": "REQUIRED n: 6 windows of 1200.",
    "cohort_cut": "2026-08-10T16:25:55+00:00",
    "watch": {"n": 7200, "basis_fp": "e1adced727678c8f"},
}
_UNWATCHABLE = {
    "prereg_id": "bbbbbbbbbbbb",
    "status": "registered",
    "claim": "A claim with no observable behind it.",
    "cohort_cut": "2026-08-10T16:25:55+00:00",
}
_RESOLVED = {"prereg_id": "cccccccccccc", "status": "confirmed", "claim": "done"}


def _registry(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    p = tmp_path / "preregistrations.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return p


def test_open_registrations_raw_keeps_only_registered_rows(tmp_path: Path) -> None:
    rows = open_registrations_raw(_registry(tmp_path, [_WATCHABLE, _RESOLVED, _UNWATCHABLE]))
    assert [r["prereg_id"] for r in rows] == ["aaaaaaaaaaaa", "bbbbbbbbbbbb"]
    assert open_registrations_raw(tmp_path / "absent.jsonl") == []


def test_due_read_fails_loudly() -> None:
    report = assess_watch_clocks([_WATCHABLE], lambda basis_fp, since: 7490)
    assert report.status == "due"
    assert any("DUE" in line and "aaaaaaaaaaaa" in line for line in report.lines)


def test_not_yet_due_passes_and_reports_the_gap() -> None:
    report = assess_watch_clocks([_WATCHABLE], lambda basis_fp, since: 5000)
    assert report.status == "ok"
    assert any("2,200 to go" in line for line in report.lines)


def test_unwatchable_registration_fails_loudly() -> None:
    report = assess_watch_clocks([_UNWATCHABLE], lambda basis_fp, since: 0)
    assert report.status == "unwatchable"
    assert any("UNWATCHABLE" in line and "bbbbbbbbbbbb" in line for line in report.lines)


def test_due_outranks_unwatchable() -> None:
    report = assess_watch_clocks([_UNWATCHABLE, _WATCHABLE], lambda basis_fp, since: 99_999)
    assert report.status == "due"


def test_nothing_open_is_ok() -> None:
    report = assess_watch_clocks([], lambda basis_fp, since: 0)
    assert report.status == "ok"
    assert report.lines == ("no open preregistrations",)


def test_counts_are_scoped_to_the_registered_basis() -> None:
    seen: list[tuple[str, str]] = []

    def _count(basis_fp: str, since: str) -> int:
        seen.append((basis_fp, since))
        return 0

    assess_watch_clocks([_WATCHABLE], _count)
    assert seen == [("e1adced727678c8f", "2026-08-10T16:25:55+00:00")]
