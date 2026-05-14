"""Tests for ``forge.ranking.diversifier`` (§6.3, greedy + jaccard).

D023/D3.a — greedy DPP-style selection. At each step, pick the
remaining candidate with the highest `composite_score * (1 -
max_similarity_to_selected)`. Similarity = Jaccard of signal IDs.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest
from crucible_contracts import SignalSpec, StrategyConfig

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.diversifier import jaccard_signal_ids, select_top_n
from forge.ranking.types import RankedCandidate
from tests.fixtures.strategy_configs import minimal_strategy_config


def _named_config(name: str, signal_ids: tuple[str, ...]) -> StrategyConfig:
    """Build a config with the given signal IDs (first is directional,
    rest are regime-filter)."""
    if not signal_ids:
        msg = "_named_config: need at least one signal"
        raise ValueError(msg)
    signals: tuple[SignalSpec, ...] = (
        SignalSpec(
            id=signal_ids[0],
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"threshold": 30.0},
        ),
        *tuple(
            SignalSpec(
                id=sid,
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0},
            )
            for sid in signal_ids[1:]
        ),
    )
    return minimal_strategy_config().model_copy(update={"name": name, "signals": signals})


def _candidate(
    name: str,
    *,
    signals: tuple[str, ...],
    composite_score: float,
) -> RankedCandidate:
    cfg = _named_config(name, signals)
    rep = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
            }
        ),
        diagnostic_notes=(),
    )
    return RankedCandidate(
        report=rep,
        prior_promotion_score=0.0,
        composite_score=composite_score,
    )


# ---------------------------------------------------------------------------
# jaccard_signal_ids — pure metric
# ---------------------------------------------------------------------------


def test_jaccard_identical_signals_is_one() -> None:
    a = _named_config("a", ("X", "Y"))
    b = _named_config("b", ("X", "Y"))
    assert jaccard_signal_ids(a, b) == pytest.approx(1.0)


def test_jaccard_disjoint_signals_is_zero() -> None:
    a = _named_config("a", ("X", "Y"))
    b = _named_config("b", ("P", "Q"))
    assert jaccard_signal_ids(a, b) == pytest.approx(0.0)


def test_jaccard_half_overlap() -> None:
    """{X, Y} vs {X, Z} -> 1 shared / 3 union = 1/3."""
    a = _named_config("a", ("X", "Y"))
    b = _named_config("b", ("X", "Z"))
    assert jaccard_signal_ids(a, b) == pytest.approx(1 / 3)


def test_jaccard_is_symmetric() -> None:
    a = _named_config("a", ("X", "Y"))
    b = _named_config("b", ("X", "Z"))
    assert jaccard_signal_ids(a, b) == jaccard_signal_ids(b, a)


def test_jaccard_disjoint_no_zero_division() -> None:
    """Two configs with no signal-ID overlap — union is non-empty, so the
    metric is well-defined and returns 0.0."""
    a = _named_config("a", ("A",))
    b = _named_config("b", ("B",))
    assert jaccard_signal_ids(a, b) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# select_top_n — boundary behaviors
# ---------------------------------------------------------------------------


def test_empty_candidates_returns_empty_list() -> None:
    assert select_top_n((), n=10) == []


def test_n_zero_returns_empty_list() -> None:
    cands = (
        _candidate("a", signals=("X",), composite_score=0.9),
        _candidate("b", signals=("Y",), composite_score=0.5),
    )
    assert select_top_n(cands, n=0) == []


def test_n_negative_raises() -> None:
    with pytest.raises(ValueError, match=r"n must be >= 0"):
        select_top_n((), n=-1)


def test_n_greater_than_candidates_returns_all() -> None:
    cands = (
        _candidate("a", signals=("X",), composite_score=0.9),
        _candidate("b", signals=("Y",), composite_score=0.5),
    )
    out = select_top_n(cands, n=10)
    assert len(out) == 2
    # Both selected, in some order (no penalty since signals are disjoint).
    selected_names = {c.report.config.name for c in out}
    assert selected_names == {"a", "b"}


# ---------------------------------------------------------------------------
# select_top_n — greedy + diversification
# ---------------------------------------------------------------------------


def test_picks_highest_composite_first() -> None:
    """With one slot, the highest-composite candidate wins. Other
    candidates are irrelevant for the first pick."""
    cands = (
        _candidate("hi", signals=("X",), composite_score=0.9),
        _candidate("lo", signals=("Y",), composite_score=0.1),
    )
    out = select_top_n(cands, n=1)
    assert len(out) == 1
    assert out[0].report.config.name == "hi"


def test_diversifier_skips_near_duplicate() -> None:
    """top (score=0.9, signals X,Y); twin (score=0.85, signals X,Y);
    different (score=0.50, signals A,B). With n=2, greedy picks top
    first, then different — because twin's adjusted_score = 0.85 *
    (1 - 1.0) = 0.0 while different's is 0.50 * (1 - 0.0) = 0.50."""
    top = _candidate("top", signals=("X", "Y"), composite_score=0.90)
    twin = _candidate("twin", signals=("X", "Y"), composite_score=0.85)
    different = _candidate("different", signals=("A", "B"), composite_score=0.50)
    out = select_top_n((top, twin, different), n=2)
    names = [c.report.config.name for c in out]
    assert names == ["top", "different"]


def test_diversifier_picks_twin_when_no_alternative() -> None:
    """If only two configs exist and both share signals, the second slot
    still gets the twin — diversification is a penalty, not a hard filter."""
    top = _candidate("top", signals=("X",), composite_score=0.90)
    twin = _candidate("twin", signals=("X",), composite_score=0.85)
    out = select_top_n((top, twin), n=2)
    names = [c.report.config.name for c in out]
    assert names == ["top", "twin"]


def test_emits_candidates_in_selection_order() -> None:
    """Selection order = greedy iteration order, NOT composite_score
    order. With penalties, lower-composite candidates can outrank
    higher-composite ones at later steps."""
    a = _candidate("a", signals=("X", "Y"), composite_score=0.90)
    b = _candidate("b", signals=("X", "Y"), composite_score=0.85)
    c = _candidate("c", signals=("P", "Q"), composite_score=0.60)
    out = select_top_n((a, b, c), n=3)
    names = [r.report.config.name for r in out]
    # First: a (highest composite).
    # Second: c (adjusted=0.60 vs b's adjusted=0.0).
    # Third: b (only one left).
    assert names == ["a", "c", "b"]


# ---------------------------------------------------------------------------
# Determinism + invariants
# ---------------------------------------------------------------------------


def test_select_is_deterministic_for_same_inputs() -> None:
    cands = (
        _candidate("a", signals=("X",), composite_score=0.9),
        _candidate("b", signals=("Y",), composite_score=0.5),
        _candidate("c", signals=("Z",), composite_score=0.7),
    )
    a = select_top_n(cands, n=3)
    b = select_top_n(cands, n=3)
    assert [r.report.config.name for r in a] == [r.report.config.name for r in b]


def test_select_returns_exactly_n_when_pool_is_large_enough() -> None:
    cands = tuple(
        _candidate(f"c{i}", signals=(f"sig_{i}",), composite_score=0.5 + i * 0.01)
        for i in range(10)
    )
    out = select_top_n(cands, n=4)
    assert len(out) == 4


def test_select_does_not_repeat_candidates() -> None:
    cands = tuple(_candidate(f"c{i}", signals=(f"sig_{i}",), composite_score=0.5) for i in range(5))
    out = select_top_n(cands, n=5)
    names = [r.report.config.name for r in out]
    assert len(names) == len(set(names))
