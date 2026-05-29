"""Phase 0 invariants — discipline checks for the bootstrap skeleton.

Each row of FORGE_DESIGN.md §13 (production-quality requirements) and each
kickoff hard rule that is testable at this phase has a check here. New phases
add rows; nothing is removed without explicit operator approval.
"""

from __future__ import annotations

import re
from pathlib import Path

from forge.persistence.db import db_connection

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "forge"

_DATETIME_NOW = re.compile(r"\bdatetime\.now\s*\(")
_DATETIME_UTCNOW = re.compile(r"\bdatetime\.utcnow\s*\(")
_RANDOM_SEED = re.compile(r"\brandom\.seed\s*\(")
_NP_DEFAULT_RNG = re.compile(r"\bnp\.random\.default_rng\s*\(")
# L-15 (audit 2026-05-29): the original RNG scan matched only `random.seed(`
# and `np.random.default_rng(` — `random.Random()`, `rng.seed(x)`,
# `np.random.RandomState/Generator/PCG64/SeedSequence`, and `secrets.*` all
# slipped through. Broaden to a path-aware allow-list (only seed.py may
# construct/seed RNGs) so any determinism-breaking pattern is caught.
_RANDOM_RANDOM_CTOR = re.compile(r"\brandom\.Random\s*\(")
_ANY_SEED_CALL = re.compile(r"\.seed\s*\(")
_NP_RANDOMSTATE = re.compile(r"\bnp\.random\.RandomState\s*\(")
_NP_GENERATOR = re.compile(r"\bnp\.random\.Generator\s*\(")
_NP_PCG64 = re.compile(r"\bnp\.random\.PCG64\s*\(")
_NP_SEEDSEQUENCE = re.compile(r"\bnp\.random\.SeedSequence\s*\(")
_SECRETS_USE = re.compile(r"\bsecrets\.")
_RNG_CONSTRUCTORS = (
    _RANDOM_SEED,
    _NP_DEFAULT_RNG,
    _RANDOM_RANDOM_CTOR,
    _ANY_SEED_CALL,
    _NP_RANDOMSTATE,
    _NP_GENERATOR,
    _NP_PCG64,
    _NP_SEEDSEQUENCE,
    _SECRETS_USE,
)
# Hard rule #2: no Crucible-internal imports. Only `crucible_contracts`
# (and its public subpackages like `crucible_contracts.exceptions`) may
# be imported. Direct reaches into `optbt`/`crucible` are forbidden.
_OPTBT_IMPORT = re.compile(r"^\s*(from\s+optbt|import\s+optbt)\b", re.MULTILINE)
_CRUCIBLE_INTERNAL_IMPORT = re.compile(
    r"^\s*(from\s+crucible(?!_contracts)|import\s+crucible(?!_contracts))\b", re.MULTILINE,
)
# Hard rule #5: no LLM SDK in the production loop. Claude-as-collaborator
# happens outside the running system; the enumerator/pre-filters/ranker/
# submitter/feedback are deterministic Python.
_LLM_IMPORTS = re.compile(
    r"^\s*(from\s+(anthropic|openai|google\.generativeai|cohere)|"
    r"import\s+(anthropic|openai|google\.generativeai|cohere))\b",
    re.MULTILINE,
)


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
    """Hard rule #8: only forge.core.seed may construct/seed RNGs.

    Path-aware allow-list (L-15): `seed.py` is the sole exemption. Every other
    src file is scanned for the full RNG-construction surface, not just the two
    literal forms the original scan matched.
    """
    blessed = {(SRC_ROOT / "core" / "seed.py").resolve()}
    offenders: list[tuple[str, str]] = []
    for py in _src_files_excluding(blessed):
        text = py.read_text(encoding="utf-8")
        for pat in _RNG_CONSTRUCTORS:
            if pat.search(text):
                offenders.append((str(py.relative_to(REPO_ROOT)), pat.pattern))
    assert not offenders, f"Naked RNG usage outside forge/core/seed.py: {offenders}"


def test_clock_and_rng_invariant_regexes_match_known_offenders() -> None:
    """L-16: positive controls. The clock/RNG scans are pure negative checks
    (`assert not offenders`); a silent regex regression would leave them green
    forever. Feed each pattern a representative offender (must match) and a clean
    string (must not) so the scans themselves are proven live.
    """
    offender_samples = {
        _DATETIME_NOW: "ts = datetime.now()",
        _DATETIME_UTCNOW: "ts = datetime.utcnow()",
        _RANDOM_SEED: "random.seed(42)",
        _NP_DEFAULT_RNG: "rng = np.random.default_rng(0)",
        _RANDOM_RANDOM_CTOR: "rng = random.Random(42)",
        _ANY_SEED_CALL: "rng.seed(7)",
        _NP_RANDOMSTATE: "rng = np.random.RandomState(1)",
        _NP_GENERATOR: "rng = np.random.Generator(bits)",
        _NP_PCG64: "bits = np.random.PCG64(1)",
        _NP_SEEDSEQUENCE: "ss = np.random.SeedSequence(1)",
        _SECRETS_USE: "tok = secrets.token_hex()",
    }
    for pat, sample in offender_samples.items():
        assert pat.search(sample), f"{pat.pattern!r} failed to match offender {sample!r}"

    # Negative control: blessed-path usage must trip none of them.
    clean = "ts = utc_now()\ndraw = ctx.rng_factory('permutation_test').random()\n"
    for pat in (_DATETIME_NOW, _DATETIME_UTCNOW, *_RNG_CONSTRUCTORS):
        assert not pat.search(clean), f"{pat.pattern!r} false-matched clean code"


def test_required_top_level_files_exist() -> None:
    """Operating discipline: persistent state files must be present at repo root."""
    required = ["STATUS.md", "IMPLEMENTATION_DECISIONS.md", "OPEN_QUESTIONS.md", "CLAUDE.md"]
    missing = [f for f in required if not (REPO_ROOT / f).exists()]
    assert not missing, f"Missing persistent state files: {missing}"


def test_grammar_archive_dir_exists() -> None:
    """§13.2: grammar.yaml changes must archive prior versions; dir must exist now."""
    assert (REPO_ROOT / "config" / "grammar_archive").is_dir()


def test_no_crucible_internal_imports() -> None:
    """Hard rule #2: all inter-system access goes via `crucible_contracts`.
    Direct imports of `optbt` (Crucible's package root) or any `crucible.*`
    submodule that isn't `crucible_contracts` violate the integration
    boundary. A missing model is a contracts gap to surface, not a
    workaround to ship.
    """
    offenders: list[tuple[str, str]] = []
    for py in SRC_ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _OPTBT_IMPORT.search(text):
            offenders.append((str(py.relative_to(REPO_ROOT)), "optbt import"))
        if _CRUCIBLE_INTERNAL_IMPORT.search(text):
            offenders.append(
                (
                    str(py.relative_to(REPO_ROOT)),
                    "crucible-internal import (not crucible_contracts)",
                )
            )
    assert not offenders, (
        "Crucible-internal imports found (hard rule #2 — only crucible_contracts "
        f"may bridge the two systems): {offenders}"
    )


def test_no_llm_sdk_in_production_loop() -> None:
    """Hard rule #5: no LLM SDK (anthropic / openai / google.generativeai /
    cohere) in the production loop. Claude-as-collaborator with the operator
    happens outside the running system; enumerator / pre-filters / ranker /
    submitter / feedback are deterministic Python.

    `crucible_contracts` is the only inter-system surface; if a generative
    model is ever needed, it lives behind the contracts boundary, not in a
    Forge module.
    """
    offenders: list[tuple[str, str]] = []
    for py in SRC_ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _LLM_IMPORTS.search(text):
            offenders.append((str(py.relative_to(REPO_ROOT)), "LLM SDK import"))
    assert not offenders, (
        "LLM SDK imports found in src/forge (hard rule #5 — production loop "
        f"is deterministic Python only): {offenders}"
    )


def test_db_connection_pins_session_timezone_to_utc() -> None:
    """D061: every connection from `db_connection` must have session TZ=UTC.

    All Forge timestamps flow through `forge.core.clock.utc_now()` (hard
    rule #8). On-disk naive TIMESTAMP values are therefore implicit-UTC
    wall clocks. Without pinning, DuckDB coerces them via the host's
    session TZ on read, silently shifting aware-vs-naive comparisons —
    the D052 aged-out flush no-op'd in production for exactly this reason
    on a PDT (UTC-7) host. Pinning the session TZ at connection open is
    the structural defense; this invariant ensures it can never regress.
    """
    with db_connection(":memory:") as conn:
        (tz,) = conn.execute("SELECT current_setting('TimeZone')").fetchone()
    assert tz == "UTC", (
        f"db_connection must pin session TZ to UTC (got {tz!r}). "
        "D061: see src/forge/persistence/db.py."
    )
