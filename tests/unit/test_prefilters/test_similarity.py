"""Unit tests for ``forge.prefilters._similarity``.

``jaccard`` was previously duplicated verbatim in ``novelty.py`` and
``signal_correlation.py``. It is a fixed mathematical definition (not
per-filter policy), so a single shared implementation prevents the two
copies from silently drifting apart.
"""

from __future__ import annotations

from datetime import date

from forge.prefilters._similarity import jaccard


def test_identical_sets_overlap_fully() -> None:
    days = frozenset({date(2026, 1, 2), date(2026, 1, 3)})
    assert jaccard(days, days) == 1.0


def test_disjoint_sets_have_zero_overlap() -> None:
    a = frozenset({date(2026, 1, 2)})
    b = frozenset({date(2026, 1, 3)})
    assert jaccard(a, b) == 0.0


def test_partial_overlap_is_intersection_over_union() -> None:
    a = frozenset({date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 6)})
    b = frozenset({date(2026, 1, 3), date(2026, 1, 6), date(2026, 1, 7)})
    # |{3rd, 6th}| / |{2nd, 3rd, 6th, 7th}| = 2/4
    assert jaccard(a, b) == 0.5


def test_either_side_empty_returns_zero_not_nan() -> None:
    days = frozenset({date(2026, 1, 2)})
    empty: frozenset[date] = frozenset()
    assert jaccard(empty, days) == 0.0
    assert jaccard(days, empty) == 0.0
    assert jaccard(empty, empty) == 0.0


def test_symmetry() -> None:
    a = frozenset({date(2026, 1, 2), date(2026, 1, 3)})
    b = frozenset({date(2026, 1, 3), date(2026, 1, 7)})
    assert jaccard(a, b) == jaccard(b, a)
