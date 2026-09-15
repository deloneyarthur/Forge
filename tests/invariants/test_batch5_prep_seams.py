"""Batch 5 prep seams (plan 2026-09 §12.6): the weekly campaign must not lean on the daemon era.

WHY: Batch 5 deletes the daemon loop (`cli/main.py`), the learned-weight and proposal
machinery, the registry-as-code and the yield auditor. Every helper the campaign borrowed from
those modules was moved to a permanent home; this file is the tripwire that (a) the campaign
path imports none of the doomed modules, so their deletion cannot break it, and (b) the old
names still resolve to the SAME objects until Batch 5 removes them, so nothing in the daemon
era changed behaviour in the move.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src" / "forge"
_CAMPAIGN_FILES = [*sorted((_SRC / "campaign").glob("*.py")), _SRC / "cli" / "campaign_cmd.py"]
_DOOMED = {
    "forge.cli.main",
    "forge.ranking.diversifier",
    "forge.ranking.campaigns",
    "forge.feedback.rejection_weights",
    "forge.feedback.yield_audit",
}


def _forge_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("forge"):
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("forge"))
    return found


@pytest.mark.parametrize("path", _CAMPAIGN_FILES, ids=lambda p: p.name)
def test_campaign_path_imports_nothing_from_the_daemon_era(path: Path) -> None:
    offending = _forge_imports(path) & _DOOMED
    assert not offending, f"{path.name} imports doomed module(s): {sorted(offending)}"


def test_old_names_are_still_bound_to_the_moved_objects() -> None:
    """The daemon-era `cli/main` aliases left in G1 and the ranking re-exports in G2; the
    remaining rebinds belong to `feedback/rejection_weights`, which Batch 5 G3 deletes next,
    and stay bound until then."""
    from forge.feedback import eras, rejection_weights

    assert rejection_weights.CLEAN_ERA_LABEL_CUT is eras.CLEAN_ERA_LABEL_CUT
    assert rejection_weights.VE_GHOST_LABEL_CUT is eras.VE_GHOST_LABEL_CUT
