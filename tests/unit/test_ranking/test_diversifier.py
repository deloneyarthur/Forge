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
    rest are regime-filter).

    Phase 5 D024/D10: similarity scoring uses content_key (not id), so
    each unique signal_id input also varies the params dict — that way
    these tests, which use signal_ids as a proxy for "different signal,"
    keep producing distinct content keys under the new scheme.
    """
    if not signal_ids:
        msg = "_named_config: need at least one signal"
        raise ValueError(msg)
    signals: tuple[SignalSpec, ...] = (
        SignalSpec(
            id=signal_ids[0],
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"threshold": 30.0, "key": signal_ids[0]},
        ),
        *tuple(
            SignalSpec(
                id=sid,
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0, "key": sid},
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


# ---------------------------------------------------------------------------
# D103 (v9) — per-hypothesis submission-diversity floor. Guarantees each
# enumerable hypothesis a minimum number of submitted slots so the orthogonal
# (relative_value) sleeve can't be starved to ~0 by a feedback oscillation
# (the midday mean_reversion flood). The greedy §6.3 diversity rule is preserved
# both within the floor and in the fill phase.
# ---------------------------------------------------------------------------


def _candidate_h(
    name: str,
    hypothesis: str,
    signals: tuple[str, ...],
    composite_score: float,
) -> RankedCandidate:
    cfg = _named_config(name, signals).model_copy(update={"hypothesis": hypothesis})
    rep = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=MappingProxyType(
            {"structural_redundancy": FilterResult(passed=True, score=1.0)}
        ),
        diagnostic_notes=(),
    )
    return RankedCandidate(
        report=rep,
        prior_promotion_score=0.0,
        composite_score=composite_score,
    )


def test_d103_floor_rescues_starved_hypothesis() -> None:
    """A high-scoring hypothesis monopolizes the unfloored top-N; the floor
    guarantees the low-scoring orthogonal sleeve a minimum slot count."""
    cands = [
        _candidate_h(f"mr_{i}", "mean_reversion", (f"mrd{i}", f"mrr{i}"), 0.9) for i in range(30)
    ]
    cands += [
        _candidate_h(f"rv_{i}", "relative_value", (f"rvd{i}", f"rvr{i}"), 0.2) for i in range(5)
    ]
    no_floor = select_top_n(cands, 20)
    n_rv_nofloor = sum(1 for c in no_floor if c.report.config.hypothesis == "relative_value")
    floored = select_top_n(cands, 20, min_per_hypothesis=3)
    n_rv_floored = sum(1 for c in floored if c.report.config.hypothesis == "relative_value")
    assert n_rv_nofloor == 0  # starved without the floor
    assert n_rv_floored >= 3  # rescued by the floor
    assert len(floored) == 20


def test_d103_floor_degrades_when_few_survivors() -> None:
    """A hypothesis with fewer than `min_per_hypothesis` survivors contributes
    all it has — no crash, no over-reservation."""
    cands = [
        _candidate_h(f"mr_{i}", "mean_reversion", (f"mrd{i}", f"mrr{i}"), 0.9) for i in range(10)
    ]
    cands += [_candidate_h("rv_0", "relative_value", ("rvd0", "rvr0"), 0.1)]  # only 1 available
    floored = select_top_n(cands, 8, min_per_hypothesis=3)
    n_rv = sum(1 for c in floored if c.report.config.hypothesis == "relative_value")
    assert n_rv == 1
    assert len(floored) == 8


def test_d103_floor_zero_is_legacy_identical() -> None:
    """min_per_hypothesis=0 reproduces the legacy greedy selection byte-for-byte."""
    cands = [
        _candidate_h(
            f"c_{i}",
            "mean_reversion" if i % 2 else "relative_value",
            (f"d{i}", f"r{i}"),
            1.0 - i * 0.01,
        )
        for i in range(15)
    ]
    legacy = select_top_n(cands, 8)
    explicit_zero = select_top_n(cands, 8, min_per_hypothesis=0)
    assert [c.report.config.name for c in legacy] == [c.report.config.name for c in explicit_zero]


def test_d103_floor_never_exceeds_n() -> None:
    """Σ floors > n must not over-select; the floor phase stops at n."""
    cands = []
    for hyp in (
        "mean_reversion",
        "trend_continuation",
        "volatility_event",
        "relative_value",
        "regime_arbitrage",
    ):
        cands += [
            _candidate_h(f"{hyp}_{i}", hyp, (f"{hyp}d{i}", f"{hyp}r{i}"), 0.5) for i in range(10)
        ]
    floored = select_top_n(cands, 12, min_per_hypothesis=5)  # 5*5=25 reserved > 12
    assert len(floored) == 12


def test_d103_floor_deterministic() -> None:
    cands = [
        _candidate_h(
            f"c_{i}",
            "mean_reversion" if i % 3 else "relative_value",
            (f"d{i}", f"r{i}"),
            1.0 - i * 0.005,
        )
        for i in range(20)
    ]
    a = select_top_n(cands, 10, min_per_hypothesis=2)
    b = select_top_n(cands, 10, min_per_hypothesis=2)
    assert [c.report.config.name for c in a] == [c.report.config.name for c in b]


# ---------------------------------------------------------------------------
# D136 — per-arm exploration floor (young-arm reservation phase)
# ---------------------------------------------------------------------------


def _arm_candidate(
    name: str,
    *,
    directional: str,
    regime: str,
    composite_score: float,
) -> RankedCandidate:
    """Candidate whose config carries the (directional, regime) arms; params
    keyed by name so content-keys (and thus Jaccard) stay distinct."""
    cfg = minimal_strategy_config(
        name=name,
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=(directional,),
                params={"threshold": 1.0, "key": name},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=(regime,),
                params={"threshold": 1.0, "key": name},
            ),
        ),
    )
    rep = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=MappingProxyType(
            {"structural_redundancy": FilterResult(passed=True, score=1.0)}
        ),
        diagnostic_notes=(),
    )
    return RankedCandidate(report=rep, prior_promotion_score=0.0, composite_score=composite_score)


def _mature_pool(n: int) -> list[RankedCandidate]:
    """n distinct high-scoring candidates all carrying the same MATURE arms."""
    return [
        _arm_candidate(
            f"mature_{i:02d}", directional="rsi_2", regime="iv_rank", composite_score=1.0
        )
        for i in range(n)
    ]


_MATURE_ARMS = frozenset({("directional", "rsi_2"), ("regime_filter", "iv_rank")})


def test_young_arm_candidate_reserved_despite_low_score() -> None:
    """The point of the floor: a survivor carrying a never-seen arm gets a
    slot even when every incumbent outscores it."""
    pool = _mature_pool(20)
    young = _arm_candidate(
        "young", directional="iv_term_slope", regime="iv_rank", composite_score=0.0
    )
    selected = select_top_n([*pool, young], 10, mature_arms=_MATURE_ARMS)
    names = [c.report.config.name for c in selected]
    assert "young" in names
    assert len(selected) == 10


def test_arm_floor_cap_bounds_total_reservation() -> None:
    """≤ int(n * fraction) slots total go to the reservation phase, however
    many young arms exist (n=10 → cap 1 at the 0.10 default)."""
    pool = _mature_pool(20)
    youngs = [
        _arm_candidate(
            f"young_{i}", directional=f"new_ind_{i}", regime="iv_rank", composite_score=0.0
        )
        for i in range(6)
    ]
    selected = select_top_n([*pool, *youngs], 10, mature_arms=_MATURE_ARMS)
    young_picked = [c for c in selected if c.report.config.name.startswith("young_")]
    assert len(young_picked) == 1  # cap = int(10 * 0.10)
    assert len(selected) == 10


def test_at_most_two_slots_per_young_arm() -> None:
    pool = _mature_pool(20)
    youngs = [
        _arm_candidate(
            f"young_{i}", directional="iv_term_slope", regime="iv_rank", composite_score=0.0
        )
        for i in range(3)
    ]
    selected = select_top_n([*pool, *youngs], 20, mature_arms=_MATURE_ARMS)
    young_picked = [c for c in selected if c.report.config.name.startswith("young_")]
    assert len(young_picked) == 2  # ARM_FLOOR_SLOTS_PER_ARM, under cap int(20*0.10)=2


def test_mature_arms_none_is_byte_identical_to_legacy() -> None:
    pool = [
        *_mature_pool(8),
        _arm_candidate("x", directional="macd", regime="adx", composite_score=0.5),
    ]
    legacy = select_top_n(pool, 5)
    assert select_top_n(pool, 5, mature_arms=None) == legacy


def test_floor_never_invents_when_no_young_arm_survives() -> None:
    """All candidate arms mature → the reservation phase is a no-op and the
    selection equals the legacy greedy exactly (starvation stays visible
    upstream rather than papered over)."""
    pool = [
        *_mature_pool(8),
        _arm_candidate("x", directional="rsi_2", regime="iv_rank", composite_score=0.5),
    ]
    legacy = select_top_n(pool, 5)
    floored = select_top_n(pool, 5, mature_arms=_MATURE_ARMS)
    assert floored == legacy


def test_arm_floor_composes_with_hypothesis_floor() -> None:
    """Both floors active: the young arm still lands, and the result is
    deterministic across repeated calls."""
    pool = _mature_pool(20)
    young = _arm_candidate(
        "young", directional="iv_term_slope", regime="iv_rank", composite_score=0.0
    )
    a = select_top_n([*pool, young], 10, mature_arms=_MATURE_ARMS, min_per_hypothesis=2)
    b = select_top_n([*pool, young], 10, mature_arms=_MATURE_ARMS, min_per_hypothesis=2)
    assert a == b
    assert "young" in [c.report.config.name for c in a]
