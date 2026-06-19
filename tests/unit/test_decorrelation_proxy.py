"""Unit tests for the decorrelation-proxy analysis script's pure math/feature helpers.

The script lives in scripts/ (not a package), so it is loaded by path. These tests cover the
risky logic -- rank correlation, Jaccard, quantiles, symmetric cohort labelling -- without
constructing a StrategyConfig; end-to-end config access is validated by running the script
against a live DB snapshot.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "decorrelation_proxy_alignment.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("decorr_proxy_alignment", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass(slots=True) resolves __module__ via sys.modules
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def test_pearson_perfect_positive() -> None:
    assert mod._pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)


def test_pearson_perfect_negative() -> None:
    assert mod._pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == pytest.approx(-1.0)


def test_pearson_constant_series_is_none() -> None:
    assert mod._pearson([1.0, 1.0, 1.0], [2.0, 4.0, 6.0]) is None


def test_spearman_monotonic_nonlinear_is_one() -> None:
    # Spearman is 1.0 for any monotonic relation, unlike Pearson.
    assert mod.spearman([1.0, 2.0, 3.0, 4.0], [1.0, 4.0, 9.0, 16.0]) == pytest.approx(1.0)


def test_spearman_too_few_points_is_none() -> None:
    assert mod.spearman([1.0, 2.0], [1.0, 2.0]) is None


def test_rankdata_handles_ties_with_average() -> None:
    assert mod._rankdata([10.0, 20.0, 20.0, 40.0]) == [1.0, 2.5, 2.5, 4.0]


def test_jaccard_disjoint_identical_partial() -> None:
    assert mod.jaccard(frozenset("a"), frozenset("b")) == pytest.approx(0.0)
    assert mod.jaccard(frozenset("ab"), frozenset("ab")) == pytest.approx(1.0)
    assert mod.jaccard(frozenset("ab"), frozenset("bc")) == pytest.approx(1.0 / 3.0)


def test_jaccard_both_empty_is_identical() -> None:
    assert mod.jaccard(frozenset(), frozenset()) == pytest.approx(1.0)


def test_cohort_pair_label_is_symmetric() -> None:
    assert mod.cohort_pair_label("xsect", "single") == mod.cohort_pair_label("single", "xsect")
    assert mod.cohort_pair_label("xsect", "single") == "single-vs-xsect"


def test_quantile_interpolates() -> None:
    assert mod._quantile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert mod._quantile([5.0], 0.9) == pytest.approx(5.0)
