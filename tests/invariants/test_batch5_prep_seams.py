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
    from forge.campaign import cell_key
    from forge.cli import main
    from forge.feedback import eras, rejection_weights, trade_rate_priors, yield_audit
    from forge.grammar import version_audit
    from forge.persistence import fingerprints, verdicts
    from forge.prefilters import factory
    from forge.ranking import campaigns, diversifier, model, prior_promotion, signal_key

    assert main._build_feature_cache is factory.build_feature_cache
    assert (
        main._load_prior_structural_fingerprints is fingerprints.load_prior_structural_fingerprints
    )
    assert main._load_trade_rate_priors is trade_rate_priors.load_trade_rate_priors
    assert (
        main._ensure_grammar_version_recorded_silently
        is version_audit.ensure_grammar_version_recorded_silently
    )
    assert main._QUALITY_LANE_TARGET == model.QUALITY_LANE_TARGET == "target_cpcv_p25"
    assert diversifier._signal_keys is signal_key.signal_keys
    assert diversifier.jaccard_signal_ids is signal_key.jaccard_signal_keys
    assert prior_promotion._signal_keys is signal_key.signal_keys
    assert rejection_weights.CLEAN_ERA_LABEL_CUT is eras.CLEAN_ERA_LABEL_CUT
    assert rejection_weights.VE_GHOST_LABEL_CUT is eras.VE_GHOST_LABEL_CUT
    assert yield_audit.CONVERTING_DECISIONS is verdicts.CONVERTING_DECISIONS
    assert campaigns.config_cell_from_json is cell_key.config_cell_from_json
    assert campaigns.config_cell is cell_key.config_cell
    assert campaigns.ExperimentCell == cell_key.ExperimentCell


def test_the_fallback_patch_seam_still_reaches_the_daemon_call_site() -> None:
    """`test_feature_cache_fallback.py` patches `forge.cli.main._build_feature_cache`; the
    daemon's call sites resolve that module global at call time, so the alias must be a
    plain module attribute (not a wrapper) or the patch would be bypassed."""
    import inspect

    from forge.cli import main

    src = inspect.getsource(main)
    assert "_build_feature_cache(" in src
    assert "def _build_feature_cache(" not in src
