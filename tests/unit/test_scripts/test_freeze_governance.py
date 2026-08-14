"""The signed freeze must be structurally enforced, not merely written down.

D390 signed the grammar freeze; D390's own "not done here" section records that the freeze was
**procedural** -- no script, config or service read the declaration, and the existing pre-commit
version-bump scanner would happily pass a post-freeze grammar bump. Hard rule #4 already settles
the principle for the analogous case: auto-loosening "writes to OPEN_PROPOSALS.md and waits --
never directly to grammar.yaml. Structurally enforced." A freeze that depends on remembering is
the same shape as a watcher described as armed with no unit behind it (D389).

Four properties:

  1. BEFORE signature, the guard is inert. A freeze that blocks edits it was never signed to
     block would make the declaration retroactive, which is worse than not enforcing it.
  2. AFTER signature, a grammar content change REFUSES without an open preregistration. This is
     the sequencing half of section 6 -- prereg BEFORE the edit -- and it is the half a machine
     can check.
  3. The prereg must state a required n (D363/D364). An open prereg with no stated n is the
     "registered a claim with no observable" defect, so it must not satisfy the guard.
  4. The reopener override leaves a PERMANENT RECORD or it does not work. Section 5 reopeners are
     first-class and operator-gated, so the guard must not make them impossible -- but an
     override that can be used silently is a hole, not an escape hatch.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "check_freeze_governance", _ROOT / "scripts" / "check_freeze_governance.py"
)
assert _spec is not None
assert _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_freeze_governance"] = _mod
_spec.loader.exec_module(_mod)


_SIGNED = "# Grammar freeze — DECLARATION (**SIGNED 2026-08-14**)\n\n**Status: ✅ SIGNED — operator"
_UNSIGNED = (
    "# Grammar freeze — DECLARATION (RE-FOUNDED, awaiting operator signature)\n\n"
    "**Status: ⚠️ NOT SIGNED. Ready for signature"
)

_OPEN_WITH_N = {
    "prereg_id": "aaaaaaaaaaaa",
    "status": "registered",
    "claim": "A cell retirement. REQUIRED n, STATED AT REGISTRATION: 6 windows of n=1200.",
}
_OPEN_NO_N = {
    "prereg_id": "bbbbbbbbbbbb",
    "status": "registered",
    "claim": "A cell retirement that never says how much evidence would settle it.",
}
_RESOLVED = {
    "prereg_id": "cccccccccccc",
    "status": "confirmed",
    "claim": "Already read. REQUIRED n: 1500 rows.",
}


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "preregistrations.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return p


def _declaration(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "declaration.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_inert_before_signature(tmp_path: Path) -> None:
    """Property 1: an unsigned freeze blocks nothing, even with no prereg at all."""
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=_declaration(tmp_path, _UNSIGNED),
        registry=_registry(tmp_path, [_RESOLVED]),
        reopener=None,
        staged_decision_log="",
    )
    assert ok, msg
    assert "not signed" in msg.lower()


def test_inert_when_grammar_untouched(tmp_path: Path) -> None:
    """A signed freeze must not block commits that do not touch the grammar."""
    ok, _ = _mod.evaluate(
        grammar_changed=False,
        declaration=_declaration(tmp_path, _SIGNED),
        registry=_registry(tmp_path, []),
        reopener=None,
        staged_decision_log="",
    )
    assert ok


def test_refuses_signed_grammar_change_without_open_prereg(tmp_path: Path) -> None:
    """Property 2: the sequencing half of section 6, enforced."""
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=_declaration(tmp_path, _SIGNED),
        registry=_registry(tmp_path, [_RESOLVED]),
        reopener=None,
        staged_decision_log="",
    )
    assert not ok
    assert "prereg" in msg.lower()


def test_open_prereg_without_required_n_does_not_satisfy(tmp_path: Path) -> None:
    """Property 3: a claim with no observable is not a preregistration."""
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=_declaration(tmp_path, _SIGNED),
        registry=_registry(tmp_path, [_OPEN_NO_N]),
        reopener=None,
        staged_decision_log="",
    )
    assert not ok
    assert "required n" in msg.lower()


def test_open_prereg_with_required_n_passes(tmp_path: Path) -> None:
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=_declaration(tmp_path, _SIGNED),
        registry=_registry(tmp_path, [_RESOLVED, _OPEN_WITH_N]),
        reopener=None,
        staged_decision_log="",
    )
    assert ok, msg
    assert "aaaaaaaaaaaa" in msg


@pytest.mark.parametrize("staged", ["", "## D999 — an unrelated entry.\n"])
def test_reopener_override_without_a_record_is_refused(tmp_path: Path, staged: str) -> None:
    """Property 4a: an override that leaves no trace does not work."""
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=_declaration(tmp_path, _SIGNED),
        registry=_registry(tmp_path, []),
        reopener="D400",
        staged_decision_log=staged,
    )
    assert not ok
    assert "D400" in msg


def test_reopener_override_with_a_staged_decision_entry_passes(tmp_path: Path) -> None:
    """Property 4b: section 5 reopeners stay possible -- on the record."""
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=_declaration(tmp_path, _SIGNED),
        registry=_registry(tmp_path, []),
        reopener="D400",
        staged_decision_log="## D400 — Path-C un-parked; grammar reopens under reopener (3).\n",
    )
    assert ok, msg
    assert "D400" in msg


def test_missing_declaration_is_inert_not_fatal(tmp_path: Path) -> None:
    """A guard that crashes on a missing file blocks every commit in a fresh checkout."""
    ok, msg = _mod.evaluate(
        grammar_changed=True,
        declaration=tmp_path / "absent.md",
        registry=_registry(tmp_path, []),
        reopener=None,
        staged_decision_log="",
    )
    assert ok
    assert "no declaration" in msg.lower()


def test_the_live_declaration_reads_as_signed() -> None:
    """The guard and the repo cannot drift apart silently: if the real declaration stops
    parsing as signed, this fails rather than the guard going quietly inert."""
    assert _mod.is_signed(_ROOT / "docs" / "proposals" / "grammar-freeze-declaration.md")
