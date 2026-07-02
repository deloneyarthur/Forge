"""Unit tests for `forge.ranking.sequential_test` (learned-audit B5 / P3.1).

A Wald SPRT for the mean of per-checkpoint PAIRED deltas (challenger - incumbent),
replacing the ad-hoc "k consecutive PASS" streak gate (0.5^k false-promote under a
coin-flip null). H0: mean = 0; H1: mean = min_effect. Decides promote / reject /
continue with explicit Type-I (alpha) and Type-II (beta). Pure + deterministic.
"""

from __future__ import annotations

import math

import pytest

from forge.ranking.sequential_test import SprtResult, sequential_mean_test

_A = 0.05
_B = 0.20
_EFF = 0.05


def test_empty_is_continue() -> None:
    r = sequential_mean_test([], alpha=_A, beta=_B, min_effect=_EFF)
    assert r.decision == "continue"
    assert r.n == 0
    assert r.log_lr == 0.0


def test_boundaries_match_wald() -> None:
    r = sequential_mean_test([0.1, 0.1, 0.1], alpha=_A, beta=_B, min_effect=_EFF)
    assert r.upper == pytest.approx(math.log((1 - _B) / _A))
    assert r.lower == pytest.approx(math.log(_B / (1 - _A)))
    assert r.upper > 0 > r.lower


def test_strong_positive_stream_promotes() -> None:
    # Deltas well above the effect size with low variance → cross the upper boundary.
    deltas = [0.20, 0.22, 0.18, 0.21, 0.19, 0.20]
    r = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF)
    assert r.decision == "promote"
    assert r.log_lr >= r.upper
    assert r.mean_delta == pytest.approx(sum(deltas) / len(deltas))


def test_zero_centered_stream_rejects() -> None:
    # Deltas centered at ~0 (challenger no better) → cross the lower boundary → reject H1.
    deltas = [0.001, -0.002, 0.0, 0.001, -0.001, 0.0, 0.0, 0.001]
    r = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF)
    assert r.decision == "reject"
    assert r.log_lr <= r.lower


def test_min_observations_guard_defers_decision() -> None:
    # Even a strong signal is held at "continue" until min_observations is reached.
    deltas = [0.5, 0.5]
    r = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF, min_observations=3)
    assert r.decision == "continue"
    assert r.n == 2


def test_negative_mean_gives_negative_log_lr() -> None:
    r = sequential_mean_test([-0.1, -0.1, -0.1], alpha=_A, beta=_B, min_effect=_EFF)
    assert r.log_lr < 0.0
    assert r.decision in {"reject", "continue"}


def test_sigma_override_is_respected() -> None:
    deltas = [0.06, 0.06, 0.06, 0.06]
    tight = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF, sigma=0.01)
    loose = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF, sigma=1.0)
    # Same data, smaller sigma → more evidence per observation → larger |log_lr|.
    assert tight.sigma == pytest.approx(0.01)
    assert loose.sigma == pytest.approx(1.0)
    assert tight.log_lr > loose.log_lr


def test_deterministic() -> None:
    deltas = [0.1, 0.05, 0.2, -0.03, 0.15]
    a = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF)
    b = sequential_mean_test(deltas, alpha=_A, beta=_B, min_effect=_EFF)
    assert a == b


def test_result_is_frozen_dataclass() -> None:
    r = sequential_mean_test([0.1, 0.1, 0.1], alpha=_A, beta=_B, min_effect=_EFF)
    assert isinstance(r, SprtResult)
    with pytest.raises((AttributeError, TypeError)):
        r.decision = "promote"  # type: ignore[misc]


def test_invalid_params_raise() -> None:
    with pytest.raises(ValueError, match="alpha"):
        sequential_mean_test([0.1], alpha=0.0, beta=_B, min_effect=_EFF)
    with pytest.raises(ValueError, match="beta"):
        sequential_mean_test([0.1], alpha=_A, beta=1.0, min_effect=_EFF)
    with pytest.raises(ValueError, match="min_effect"):
        sequential_mean_test([0.1], alpha=_A, beta=_B, min_effect=0.0)
