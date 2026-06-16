"""Deterministic oracle-ranked king search: determinism, dedup, validity, order.

Uses the shared minimal registry (proven to yield >=50 configs in
``test_iterator``) and the real v1 grammar.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

from forge.grammar import Grammar, load_grammar, validate
from forge.king import load_oracle, search_kings
from forge.king.oracle import DurableOracle
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO = Path(__file__).resolve().parents[3]
_GRAMMAR_PATH = _REPO / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO / "config" / "grammar_archive"
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "king"
_ORACLE_FIXTURE = _FIXTURES / "oracle_published_2026-06-16T215346Z.json"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


@pytest.fixture(scope="module")
def oracle() -> DurableOracle:
    return load_oracle(_ORACLE_FIXTURE)


def test_search_is_deterministic(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    a = search_kings(grammar, registry, oracle, seed=7, n_search=40, top_k=5)
    b = search_kings(grammar, registry, oracle, seed=7, n_search=40, top_k=5)
    assert [k.config.config_hash for k in a.kings] == [k.config.config_hash for k in b.kings]
    assert [k.predicted_score for k in a.kings] == [k.predicted_score for k in b.kings]


def test_kings_are_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    result = search_kings(grammar, registry, oracle, seed=3, n_search=40, top_k=5)
    assert result.kings
    for king in result.kings:
        assert validate(king.config, grammar, registry).valid


def test_kings_sorted_descending(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    result = search_kings(grammar, registry, oracle, seed=11, n_search=50, top_k=8)
    scores = [k.predicted_score for k in result.kings]
    assert scores == sorted(scores, reverse=True)


def test_dedup_excludes_tried(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    base = search_kings(grammar, registry, oracle, seed=5, n_search=40, top_k=10)
    assert base.kings
    tried = {base.kings[0].config.config_hash}
    deduped = search_kings(
        grammar, registry, oracle, seed=5, n_search=40, top_k=10, tried_hashes=tried
    )
    hashes = {k.config.config_hash for k in deduped.kings}
    assert tried.isdisjoint(hashes)
    assert deduped.n_deduped >= 1


def test_n_searched_tracks_trials(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    result = search_kings(grammar, registry, oracle, seed=9, n_search=50, top_k=5)
    # enumerate_candidates yields exactly n_search valid configs.
    assert result.n_searched == 50
    assert result.n_unique <= result.n_searched
    assert len(result.kings) <= 5


@pytest.mark.parametrize(("n_search", "top_k"), [(0, 5), (10, 0)])
def test_rejects_bad_args(
    grammar: Grammar,
    registry: RegistrySnapshot,
    oracle: DurableOracle,
    n_search: int,
    top_k: int,
) -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        search_kings(grammar, registry, oracle, seed=0, n_search=n_search, top_k=top_k)


def test_per_cell_diversity_caps_each_cell(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    result = search_kings(
        grammar, registry, oracle, seed=11, n_search=50, top_k=20, per_cell_cap=2
    )
    assert result.kings, "expected at least one positively-scored king"
    cells = Counter((k.config.hypothesis, k.config.dte_bucket) for k in result.kings)
    assert all(count <= 2 for count in cells.values())
    # Per-cell mode only surfaces positively-scored kings.
    assert all(k.predicted_score > 0.0 for k in result.kings)


def test_per_cell_cap_zero_raises(
    grammar: Grammar, registry: RegistrySnapshot, oracle: DurableOracle
) -> None:
    with pytest.raises(ValueError, match="per_cell_cap"):
        search_kings(grammar, registry, oracle, seed=0, n_search=10, top_k=5, per_cell_cap=0)
