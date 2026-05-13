"""Phase 0 invariants — discipline checks for the bootstrap skeleton.

Each row of FORGE_DESIGN.md §13 (production-quality requirements) and each
kickoff hard rule that is testable at this phase has a check here. New phases
add rows; nothing is removed without explicit operator approval.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "forge"

_DATETIME_NOW = re.compile(r"\bdatetime\.now\s*\(")
_DATETIME_UTCNOW = re.compile(r"\bdatetime\.utcnow\s*\(")
_RANDOM_SEED = re.compile(r"\brandom\.seed\s*\(")
_NP_DEFAULT_RNG = re.compile(r"\bnp\.random\.default_rng\s*\(")


def _src_files_excluding(blessed: set[Path]) -> list[Path]:
    return [p for p in SRC_ROOT.rglob("*.py") if p.resolve() not in blessed]


def test_no_naive_datetime_outside_blessed_clock() -> None:
    """Hard rule #8: only forge.core.clock may import datetime.now / utcnow."""
    blessed = {(SRC_ROOT / "core" / "clock.py").resolve()}
    offenders: list[tuple[str, str]] = []
    for py in _src_files_excluding(blessed):
        text = py.read_text(encoding="utf-8")
        if _DATETIME_NOW.search(text) or _DATETIME_UTCNOW.search(text):
            offenders.append((str(py.relative_to(REPO_ROOT)), "datetime.now/utcnow"))
    assert not offenders, f"Naive datetime usage outside forge/core/clock.py: {offenders}"


def test_no_naked_rng_outside_blessed_seed() -> None:
    """Hard rule #8: only forge.core.seed may seed RNGs."""
    blessed = {(SRC_ROOT / "core" / "seed.py").resolve()}
    offenders: list[tuple[str, str]] = []
    for py in _src_files_excluding(blessed):
        text = py.read_text(encoding="utf-8")
        if _RANDOM_SEED.search(text) or _NP_DEFAULT_RNG.search(text):
            offenders.append((str(py.relative_to(REPO_ROOT)), "naked RNG"))
    assert not offenders, f"Naked RNG usage outside forge/core/seed.py: {offenders}"


def test_required_top_level_files_exist() -> None:
    """Operating discipline: persistent state files must be present at repo root."""
    required = ["STATUS.md", "IMPLEMENTATION_DECISIONS.md", "OPEN_QUESTIONS.md", "CLAUDE.md"]
    missing = [f for f in required if not (REPO_ROOT / f).exists()]
    assert not missing, f"Missing persistent state files: {missing}"


def test_grammar_archive_dir_exists() -> None:
    """§13.2: grammar.yaml changes must archive prior versions; dir must exist now."""
    assert (REPO_ROOT / "config" / "grammar_archive").is_dir()
