"""Unit tests for the WF-quality probe's pure numerics (loaded by path; scripts/ isn't a package).

Covers the risky linear algebra and CV harness independently of the end-to-end run: the Gaussian
solver, rank correlation, and that ridge_cv_ic recovers a planted linear signal while staying ~0 on
an unrelated target. The end-to-end harness is separately validated by the cpcv_p25 sanity (~+0.44).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "wf_quality_probe.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wf_quality_probe", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def test_solve_diagonal() -> None:
    assert mod._solve([[2.0, 0.0], [0.0, 4.0]], [2.0, 8.0]) == pytest.approx([1.0, 2.0])


def test_solve_dense_system() -> None:
    # 2x + y = 3 ; x + 3y = 5  ->  x=0.8, y=1.4
    assert mod._solve([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0]) == pytest.approx([0.8, 1.4])


def test_spearman_monotonic_is_one() -> None:
    assert mod.spearman([1.0, 2.0, 3.0, 4.0], [1.0, 8.0, 27.0, 64.0]) == pytest.approx(1.0)


def test_rankdata_average_ties() -> None:
    assert mod._rankdata([5.0, 9.0, 9.0, 1.0]) == [2.0, 3.5, 3.5, 1.0]


def test_ridge_cv_ic_recovers_planted_signal() -> None:
    xs = [float(i) - 29.5 for i in range(60)]
    rows = [[x] for x in xs]
    y = list(xs)  # y is exactly the (single) feature -> IC should be ~1
    assert mod.ridge_cv_ic(rows, y, lam=1.0, folds=5) > 0.9


def test_ridge_cv_ic_is_near_zero_on_unrelated_target() -> None:
    rows = [[float(i)] for i in range(60)]
    y = [float(i % 2) for i in range(60)]  # alternating, no monotonic relation to the feature
    assert abs(mod.ridge_cv_ic(rows, y, lam=1.0, folds=5)) < 0.4
