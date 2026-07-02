"""Tests for ``forge.ranking.calibration`` — P1.3 calibration diagnostics.

Pure, deterministic functions: reliability table, ECE, Brier decomposition, and a
dependency-free Platt recalibrator. The properties pinned here are the ones the eval
readout + the co-primary ECE criterion + the floor's eligible-fraction monitor rely on.
"""

from __future__ import annotations

import math

import pytest

from forge.ranking.calibration import (
    brier_decomposition,
    expected_calibration_error,
    logit,
    platt_apply,
    platt_fit,
    reliability_table,
)

# ---------------------------------------------------------------------------
# logit
# ---------------------------------------------------------------------------


def test_logit_is_inverse_of_sigmoid() -> None:
    for p in (0.1, 0.3, 0.5, 0.9):
        assert math.isclose(1.0 / (1.0 + math.exp(-logit(p))), p, abs_tol=1e-9)


def test_logit_clips_the_open_interval() -> None:
    # 0.0 and 1.0 do not blow up (clipped by eps).
    assert math.isfinite(logit(0.0))
    assert math.isfinite(logit(1.0))
    assert logit(0.0) < 0.0 < logit(1.0)


# ---------------------------------------------------------------------------
# reliability_table
# ---------------------------------------------------------------------------


def test_reliability_table_bins_and_aggregates() -> None:
    # Two clean bins: preds 0.15 (rate 0) and 0.85 (rate 1).
    labels = [0, 0, 1, 1]
    probs = [0.15, 0.15, 0.85, 0.85]
    rows = reliability_table(labels, probs, n_bins=10)
    assert len(rows) == 2
    lo0, n0, mean0, rate0 = rows[0]
    lo1, n1, mean1, rate1 = rows[1]
    assert (lo0, n0, rate0) == (0.1, 2, 0.0)
    assert math.isclose(mean0, 0.15)
    assert (lo1, n1, rate1) == (0.8, 2, 1.0)
    assert math.isclose(mean1, 0.85)


def test_reliability_table_clamps_prob_one_into_last_bin() -> None:
    rows = reliability_table([1], [1.0], n_bins=10)
    assert len(rows) == 1
    assert rows[0][0] == 0.9  # p=1.0 lands in the last bin, not a phantom 11th


# ---------------------------------------------------------------------------
# expected_calibration_error
# ---------------------------------------------------------------------------


def test_ece_zero_when_perfectly_calibrated() -> None:
    # Each bin's mean prediction equals its realized rate.
    labels = [0, 1, 0, 1, 1, 1, 1, 1, 1, 1]  # 0.8 rate in the 0.8 bin
    probs = [0.05] * 0 + [0.8] * 10
    # build a bin where mean==rate exactly: 8 of 10 positive at pred 0.8
    labels = [1] * 8 + [0] * 2
    probs = [0.8] * 10
    assert expected_calibration_error(labels, probs, n_bins=10) == pytest.approx(0.0)


def test_ece_flags_overconfidence() -> None:
    # Predict 0.9 for everything; realized rate 0.5 -> |0.9-0.5| = 0.4.
    labels = [1, 0] * 50
    probs = [0.9] * 100
    assert expected_calibration_error(labels, probs, n_bins=10) == pytest.approx(0.4)


def test_ece_is_frequency_weighted_across_bins() -> None:
    # Bin A: 90 rows pred 0.9 rate 1.0 (err 0.1). Bin B: 10 rows pred 0.1 rate 1.0 (err 0.9).
    labels = [1] * 100
    probs = [0.9] * 90 + [0.1] * 10
    expected = (90 / 100) * 0.1 + (10 / 100) * 0.9
    assert expected_calibration_error(labels, probs, n_bins=10) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# brier_decomposition (Murphy)
# ---------------------------------------------------------------------------


def test_brier_decomposition_uncertainty_is_base_rate_variance() -> None:
    labels = [1] * 30 + [0] * 70
    probs = [0.5] * 100
    _rel, _res, unc = brier_decomposition(labels, probs, n_bins=10)
    assert unc == pytest.approx(0.3 * 0.7)


def test_brier_decomposition_identity_holds() -> None:
    # Murphy identity brier == reliability - resolution + uncertainty is EXACT when each
    # bin holds a single forecast value; these 10 probs each land alone in a distinct bin.
    labels = [1, 0, 1, 1, 0, 0, 1, 0, 1, 0] * 10
    probs = [0.95, 0.25, 0.75, 0.65, 0.35, 0.15, 0.85, 0.45, 0.55, 0.05] * 10
    rel, res, unc = brier_decomposition(labels, probs, n_bins=10)
    brier = sum((p - y) ** 2 for p, y in zip(probs, labels, strict=True)) / len(labels)
    assert brier == pytest.approx(rel - res + unc, abs=1e-9)


# ---------------------------------------------------------------------------
# platt_fit / platt_apply
# ---------------------------------------------------------------------------


def test_platt_apply_identity_params() -> None:
    # a=1, b=0 -> sigmoid of the raw score (logit) recovers the probability.
    for p in (0.2, 0.5, 0.8):
        assert platt_apply(1.0, 0.0, logit(p)) == pytest.approx(p, abs=1e-9)


def test_platt_apply_is_monotone_in_score() -> None:
    a, b = 1.3, -0.4
    assert platt_apply(a, b, -1.0) < platt_apply(a, b, 0.0) < platt_apply(a, b, 1.0)


def test_platt_recalibration_reduces_ece_on_overconfident_scores() -> None:
    # Separable-but-overconfident: positives predicted 0.95, negatives 0.6, base rate 0.3.
    labels = [1] * 300 + [0] * 700
    probs = [0.95] * 300 + [0.60] * 700
    logits = [logit(p) for p in probs]
    pre = expected_calibration_error(labels, probs, n_bins=10)
    a, b = platt_fit(logits, labels)
    recal = [platt_apply(a, b, z) for z in logits]
    post = expected_calibration_error(labels, recal, n_bins=10)
    assert pre > 0.3  # badly over-predicted to start
    assert post < pre
    assert post < 0.05  # recalibration lands ~on the diagonal


def test_platt_fit_is_deterministic() -> None:
    labels = [1, 0, 1, 0, 1, 1, 0, 0] * 20
    logits = [1.2, -0.3, 0.8, -1.1, 0.4, 1.5, -0.7, -0.2] * 20
    assert platt_fit(logits, labels) == platt_fit(logits, labels)


def test_platt_fit_rejects_single_class() -> None:
    with pytest.raises(ValueError, match="single class"):
        platt_fit([0.1, 0.2, 0.3], [1, 1, 1])
