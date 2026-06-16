"""Phase-0 invariants for the meta-king arm (FORGE meta-king A3).

Two guarantees the arm must never silently lose:

1. Determinism (hard rule #6): a fixed ``(grammar, registry, oracle, seed,
   n_search)`` produces a byte-identical king sequence.
2. The Crucible write path (``submit_candidate``) lives ONLY in
   ``forge.king.submit`` — the explicit, operator-invoked submission path. The
   generation/scoring core (oracle/featurize/score/search/dedup) must never
   submit as a side effect: a king reaches the gate only as a deliberate
   proposal running the unchanged §8.7 gauntlet (hard rule #3/#6), never via a
   dry-run or a search. We fail loudly if the token leaks into any other module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

import forge.king
from forge.grammar import Grammar, load_grammar
from forge.king import load_oracle, search_kings
from forge.king.oracle import DurableOracle
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO = Path(__file__).resolve().parents[2]
_GRAMMAR_PATH = _REPO / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO / "config" / "grammar_archive"
_ORACLE_FIXTURE = _REPO / "tests" / "fixtures" / "king" / "oracle_published_2026-06-16T215346Z.json"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


@pytest.fixture(scope="module")
def oracle() -> DurableOracle:
    return load_oracle(_ORACLE_FIXTURE)


def test_search_determinism_invariant(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    first = search_kings(grammar, registry, oracle, seed=2026, n_search=50, top_k=10)
    second = search_kings(grammar, registry, oracle, seed=2026, n_search=50, top_k=10)
    assert [(k.config.config_hash, k.predicted_score) for k in first.kings] == [
        (k.config.config_hash, k.predicted_score) for k in second.kings
    ]
    assert (first.n_searched, first.n_unique, first.n_deduped) == (
        second.n_searched,
        second.n_unique,
        second.n_deduped,
    )


def test_only_submit_module_reaches_the_inbox() -> None:
    """`submit_candidate` may appear ONLY in `forge.king.submit`.

    The generation/scoring core must never submit as a side effect — kings reach
    Crucible only through the deliberate, operator-invoked submit path.
    """
    package_dir = Path(forge.king.__file__).parent
    offenders = [
        py.name
        for py in package_dir.glob("*.py")
        if py.name != "submit.py" and "submit_candidate" in py.read_text(encoding="utf-8")
    ]
    assert not offenders, f"only forge.king.submit may submit; offenders: {offenders}"
