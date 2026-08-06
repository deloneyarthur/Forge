"""Phase 6 invariants — polish + operational discipline guardrails.

Each invariant maps to a Phase 6 deliverable (§12) or to a D025 closure
plan item. New polish commitments add their guardrails here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_README = _REPO_ROOT / "README.md"
_OPEN_QUESTIONS = _REPO_ROOT / "OPEN_QUESTIONS.md"
_GRAMMAR_CMD = _REPO_ROOT / "src" / "forge" / "cli" / "grammar_cmd.py"
_DESIGN = _REPO_ROOT / "docs" / "DESIGN.md"
# 2026-06-09 docs restructure: the README's Operations/Commands content moved
# to the dedicated docs below (README is now a slim entry point). The D025
# guardrails follow the content to its new owners.
_HOWTO = _REPO_ROOT / "docs" / "HOW-TO.md"
_MANPAGE = _REPO_ROOT / "docs" / "MANPAGE.md"
_ARCHITECTURE = _REPO_ROOT / "docs" / "architecture.md"


def _load_pyproject() -> dict[str, object]:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# D025/D10.i — networkx is no longer a dependency or mypy override target
# ---------------------------------------------------------------------------


def test_networkx_is_not_a_runtime_dependency() -> None:
    pyproject = _load_pyproject()
    deps = pyproject["project"]["dependencies"]  # type: ignore[index]
    assert isinstance(deps, list)
    matched = [d for d in deps if "networkx" in str(d).lower()]
    assert not matched, f"networkx should be unused — found dep entries: {matched}"


def test_networkx_mypy_override_is_removed() -> None:
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert "networkx" not in text, (
        "pyproject.toml still references networkx — D025/D10.i prune incomplete"
    )


# ---------------------------------------------------------------------------
# D025/D5 — README ships an Operations section + Commands table
# ---------------------------------------------------------------------------


def test_howto_has_operations_content() -> None:
    """D025/D5 — operating procedures exist (moved README → HOW-TO.md, 2026-06-09)."""
    text = _HOWTO.read_text(encoding="utf-8")
    assert "## Common situations" in text, (
        "docs/HOW-TO.md missing the ## Common situations section (D025/D5)"
    )


def test_manpage_has_commands_section() -> None:
    """D025/D4 — the commands reference exists (moved README → MANPAGE.md, 2026-06-09)."""
    text = _MANPAGE.read_text(encoding="utf-8")
    assert "## COMMANDS" in text, "docs/MANPAGE.md missing the ## COMMANDS section (D025/D4)"


def test_howto_lists_recovery_procedures() -> None:
    text = _HOWTO.read_text(encoding="utf-8")
    # Recovery topics that must stay documented (renamed with the 2026-06-09
    # restructure: rate-limit recovery lives under the "blocked" situation,
    # grammar.yaml repair under "Changing the grammar").
    for needle in ("Crucible offline", "rate limiter", "Changing the grammar"):
        assert needle in text, f"docs/HOW-TO.md missing recovery topic: {needle!r}"


def test_architecture_maps_invariants_to_test_files() -> None:
    text = _ARCHITECTURE.read_text(encoding="utf-8")
    # The §13 invariant bookmarks table must call out each invariant by name
    # (moved README → architecture.md, 2026-06-09).
    for needle in ("§13.1", "§13.2", "§13.3", "§13.4", "§13.5", "§13.6"):
        assert needle in text, f"docs/architecture.md invariant table missing {needle}"


# ---------------------------------------------------------------------------
# D025/D6 — forge run reads forge.yaml defaults; forge feedback already does
# ---------------------------------------------------------------------------


def test_resolve_run_defaults_helper_is_exposed() -> None:
    from forge.cli.main import _resolve_run_defaults

    assert callable(_resolve_run_defaults)


def test_forge_run_advertises_config_and_no_config_flags() -> None:
    from forge.cli.main import app

    run_cmd = next(c for c in app.registered_commands if (c.name or "") == "run")
    assert run_cmd.callback is not None
    import inspect

    sig = inspect.signature(run_cmd.callback)
    assert "config" in sig.parameters, "forge run is missing --config"
    assert "no_config" in sig.parameters, "forge run is missing --no-config"


def test_forge_feedback_advertises_config_and_no_config_flags() -> None:
    import inspect

    from forge.cli.feedback_cmd import cmd_feedback

    sig = inspect.signature(cmd_feedback)
    assert "config" in sig.parameters
    assert "no_config" in sig.parameters


# ---------------------------------------------------------------------------
# D025/D8 + D9 — deferrals are logged in OPEN_QUESTIONS.md
# ---------------------------------------------------------------------------


def test_q9_cross_batch_trigger_deferral_is_logged() -> None:
    text = _OPEN_QUESTIONS.read_text(encoding="utf-8")
    assert "Q9" in text, "Q9 (cross-batch trigger deferral) missing from OPEN_QUESTIONS.md"
    assert "param-no-promotion" in text or "param no-promotion" in text


def test_q10_feature_cache_deferral_is_logged() -> None:
    # Q10 is RESOLVED (real cache shipped 2026-07-05); resolved entries rotate to the
    # archive (Step A3, 2026-08-06), so the record check spans live file + archive.
    text = _OPEN_QUESTIONS.read_text(encoding="utf-8")
    archive = _OPEN_QUESTIONS.parent / "_archive" / "OPEN_QUESTIONS_RESOLVED.md"
    if archive.exists():
        text += archive.read_text(encoding="utf-8")
    assert "Q10" in text, "Q10 (FeatureCache deferral) missing from the Q-ledger record"
    assert "FeatureCache" in text


# ---------------------------------------------------------------------------
# D025/D10.ii — grammar approve-proposal docstring keeps the §13.2 note
# ---------------------------------------------------------------------------


def test_grammar_approve_proposal_docstring_calls_out_manual_yaml_edit() -> None:
    text = _GRAMMAR_CMD.read_text(encoding="utf-8")
    # The clarifying note added in D025/D10.ii lives inside the
    # approve-proposal callback's docstring; assert both the function
    # name and the §13.2 keyword appear in the file.
    assert "cmd_approve_proposal" in text
    assert "§13.2" in text


# ---------------------------------------------------------------------------
# D025/D7 — §6.2 doc uses regime_exposure_score (Phase 4 OQ-1 closed)
# ---------------------------------------------------------------------------


def test_design_section_6_2_uses_regime_exposure_score() -> None:
    text = _DESIGN.read_text(encoding="utf-8")
    assert "regime_exposure_score" in text, (
        "DESIGN.md §6.2 should use regime_exposure_score after D025/D7 rename"
    )
    # The §6.2 formula line must use the new name. Find the formula
    # block (between the `score = (` opener and the trailing `)`).
    start = text.find("score = (")
    end = text.find(")", start) if start >= 0 else -1
    formula_block = text[start:end] if start >= 0 and end > start else ""
    assert "regime_diversity_score" not in formula_block, (
        "DESIGN.md §6.2 formula still uses regime_diversity_score"
    )
    assert "regime_exposure_score" in formula_block, (
        "DESIGN.md §6.2 formula should use regime_exposure_score"
    )
