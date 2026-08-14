"""A registered read must not be able to come due silently.

D389: `3b0cbca7ae17` reached its clock and nothing fired. STATUS.md described a watcher as
armed; there was no systemd unit and no cron entry behind the claim. Because a preregistration
forbids extension ("no peeking, no early call, no extension"), a read that drifts past its
trigger is not a scheduling annoyance -- it is a slow corruption of the instrument, and the
longer it drifts the more the sample differs from the one that was registered.

Crucible named the class in the same week: "a revisit trigger with no observable, a monitor for
a load-bearing feed that did not exist." The disposition agreed on both sides is **arm it or
delete the claim**.

Four properties:

  1. A prereg whose clock is REACHED reports DUE and exits non-zero. A watcher that reports a
     due read on stdout and exits 0 is a watcher a timer will never surface.
  2. A prereg whose clock is NOT reached reports how far away it is and exits 0. Quiet when
     there is nothing to do, or it gets muted.
  3. A prereg with NO machine-readable clock is UNWATCHABLE and says so loudly. This is the
     D389 defect itself: the failure was not a broken watcher, it was a claim that no watcher
     could ever have checked.
  4. The watcher never reads the metric. It counts rows and compares fingerprints. A monitor
     that peeks to decide whether to page has taken the read.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "freeze_read_watcher", _ROOT / "scripts" / "freeze_read_watcher.py"
)
assert _spec is not None
assert _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["freeze_read_watcher"] = _mod
_spec.loader.exec_module(_mod)


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


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "preregistrations.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return p


def test_due_read_exits_nonzero(tmp_path: Path) -> None:
    """Property 1: a due read must be loud enough for a timer to notice."""
    code, report = _mod.assess(
        _registry(tmp_path, [_WATCHABLE, _RESOLVED]),
        count_rows=lambda basis_fp, since: 7490,
    )
    assert code == _mod.EXIT_DUE
    assert "DUE" in report
    assert "aaaaaaaaaaaa" in report


def test_not_yet_due_is_quiet_and_reports_the_gap(tmp_path: Path) -> None:
    code, report = _mod.assess(
        _registry(tmp_path, [_WATCHABLE]),
        count_rows=lambda basis_fp, since: 5000,
    )
    assert code == _mod.EXIT_OK
    assert "2,200 to go" in report or "2200 to go" in report


def test_unwatchable_prereg_is_reported_loudly(tmp_path: Path) -> None:
    """Property 3: the D389 defect -- a claim no watcher could ever have checked."""
    code, report = _mod.assess(
        _registry(tmp_path, [_UNWATCHABLE]),
        count_rows=lambda basis_fp, since: 0,
    )
    assert code == _mod.EXIT_UNWATCHABLE
    assert "UNWATCHABLE" in report
    assert "bbbbbbbbbbbb" in report


def test_due_outranks_unwatchable(tmp_path: Path) -> None:
    """Both are non-zero, but a due read is the one needing action today."""
    code, _ = _mod.assess(
        _registry(tmp_path, [_UNWATCHABLE, _WATCHABLE]),
        count_rows=lambda basis_fp, since: 99_999,
    )
    assert code == _mod.EXIT_DUE


def test_no_open_preregs_is_silent_success(tmp_path: Path) -> None:
    code, report = _mod.assess(
        _registry(tmp_path, [_RESOLVED]),
        count_rows=lambda basis_fp, since: 0,
    )
    assert code == _mod.EXIT_OK
    assert "no open" in report.lower()


def test_counts_are_scoped_to_the_registered_basis(tmp_path: Path) -> None:
    """Property 4 in its concrete form: the watcher asks for rows IN THE BASIS, so a
    foreign-basis backlog can never make a read look due (the D387/D391 failure shape)."""
    seen: list[tuple[str, str]] = []

    def _count(basis_fp: str, since: str) -> int:
        seen.append((basis_fp, since))
        return 0

    _mod.assess(_registry(tmp_path, [_WATCHABLE]), count_rows=_count)
    assert seen == [("e1adced727678c8f", "2026-08-10T16:25:55+00:00")]
