"""Unit tests for `forge.ranking.drift` (learned-audit P3.2 / B6).

Population Stability Index (score/feature-distribution drift), its severity banding,
and the adoption verdict (don't rotate to a model whose fresh-window signal is
non-positive). Pure + deterministic (hard rules #5/#6).
"""

from __future__ import annotations

import pytest

from forge.ranking.drift import adoption_verdict, population_stability_index, psi_severity


def test_psi_identical_distribution_is_near_zero() -> None:
    xs = [float(i) for i in range(100)]
    psi = population_stability_index(xs, list(xs), n_bins=10)
    assert psi is not None
    assert psi == pytest.approx(0.0, abs=1e-9)


def test_psi_shifted_distribution_is_large() -> None:
    ref = [float(i) for i in range(100)]
    cur = [x + 100.0 for x in ref]  # fully shifted out of the reference support
    psi = population_stability_index(ref, cur, n_bins=10)
    assert psi is not None
    assert psi > 0.25  # "major" drift


def test_psi_mild_shift_between_thresholds() -> None:
    ref = [float(i) for i in range(1000)]
    cur = [x + 40.0 for x in ref]  # a modest shift
    psi = population_stability_index(ref, cur, n_bins=10)
    assert psi is not None
    assert 0.0 < psi < 1.0


def test_psi_none_on_thin_samples() -> None:
    assert population_stability_index([1.0], [1.0, 2.0], n_bins=10) is None
    assert population_stability_index([1.0, 2.0], [], n_bins=10) is None


def test_psi_is_deterministic() -> None:
    ref = [float(i % 7) for i in range(50)]
    cur = [float(i % 5) for i in range(50)]
    assert population_stability_index(ref, cur) == population_stability_index(ref, cur)


def test_psi_severity_bands() -> None:
    assert psi_severity(None) == "unknown"
    assert psi_severity(0.05) == "stable"
    assert psi_severity(0.10) == "stable"  # boundary inclusive-below
    assert psi_severity(0.11) == "moderate"
    assert psi_severity(0.25) == "moderate"
    assert psi_severity(0.30) == "major"


def test_adoption_verdict() -> None:
    assert adoption_verdict(None) == "UNKNOWN"
    assert adoption_verdict(0.12) == "ADOPT"
    assert adoption_verdict(0.0) == "BLOCK"  # not strictly positive
    assert adoption_verdict(-0.03) == "BLOCK"
    # Custom floor: require a margin, not just positivity.
    assert adoption_verdict(0.02, min_signal=0.05) == "BLOCK"
    assert adoption_verdict(0.06, min_signal=0.05) == "ADOPT"
