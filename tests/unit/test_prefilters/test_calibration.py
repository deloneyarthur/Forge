"""Unit tests for ``forge.prefilters.calibration``.

Covers:
- `Calibration` is frozen, nested-dataclass shape matches `config/prefilter.yaml`.
- `load_calibration(path)` round-trips the v1 default YAML.
- Loader rejects unknown top-level keys, missing keys, and invalid types.
- `apply_tightening` is pure and shifts knobs in the stricter direction.
- there is no loosening write path at all (`write_loosening_proposal`, 0 callers, left in
  Batch 5 G4 / D421; grammar changes need a preregistration, hard rule #4) and
  expose a symmetric ``apply_loosening`` that mutates calibration directly
  (Phase 3 closure D3 + CLAUDE.md hard rule #4).
- The exported module surface has no ``apply_loosening`` — structural
  enforcement of the no-auto-loosen invariant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.prefilters import calibration as calibration_module
from forge.prefilters.calibration import (
    AdjustmentProposal,
    apply_tightening,
    load_calibration,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


# ---------------------------------------------------------------------------
# Calibration shape
# ---------------------------------------------------------------------------


def test_calibration_is_frozen() -> None:
    c = load_calibration(_PREFILTER_YAML)
    with pytest.raises((AttributeError, Exception), match=r"cannot assign|frozen"):
        c.signal_density.min_activations = 999  # type: ignore[misc]


def test_calibration_nested_shape_matches_yaml() -> None:
    """Each filter has its own nested calibration dataclass. Verbose-but-honest
    mapping from `config/prefilter.yaml`."""
    c = load_calibration(_PREFILTER_YAML)
    assert c.signal_density.min_activations == 30
    assert c.expected_trade_count.min_trades == 50
    assert c.novelty.max_jaccard_overlap == 0.80
    assert c.regime_exposure.max_single_regime_concentration == 0.80
    assert c.permutation_test.n_permutations == 100
    assert c.permutation_test.p_value_threshold == 0.10
    # D075: forward-horizon parameter for the return comparison.
    assert c.permutation_test.forward_horizon_days == 5


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        load_calibration(missing)


def test_loader_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    """An extra section means the operator added something the code
    doesn't know about — fail loud rather than silently ignore."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """
prefilter:
  signal_density:
    min_activations: 30
  expected_trade_count:
    min_trades: 50
  novelty:
    max_jaccard_overlap: 0.80
  regime_exposure:
    max_single_regime_concentration: 0.80
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
  mystery_filter:
    threshold: 0.5
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mystery_filter"):
        load_calibration(bad)


def test_loader_rejects_missing_required_key(tmp_path: Path) -> None:
    bad = tmp_path / "missing.yaml"
    # Omit predicted_activations + signal_correlation entirely
    bad.write_text(
        """
prefilter:
  signal_density:
    min_activations: 30
  expected_trade_count:
    min_trades: 50
  novelty:
    max_jaccard_overlap: 0.80
  regime_exposure:
    max_single_regime_concentration: 0.80
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="predicted_activations"):
        load_calibration(bad)


def test_loader_rejects_negative_threshold(tmp_path: Path) -> None:
    bad = tmp_path / "negative.yaml"
    bad.write_text(
        """
prefilter:
  signal_density:
    min_activations: -5
  expected_trade_count:
    min_trades: 50
  predicted_activations:
    min_entries: 10
  novelty:
    max_jaccard_overlap: 0.80
  signal_correlation:
    max_jaccard_overlap: 0.85
  regime_exposure:
    max_single_regime_concentration: 0.80
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min_activations"):
        load_calibration(bad)


def test_loader_rejects_jaccard_outside_unit_interval(tmp_path: Path) -> None:
    bad = tmp_path / "jaccard.yaml"
    bad.write_text(
        """
prefilter:
  signal_density:
    min_activations: 30
  expected_trade_count:
    min_trades: 50
  predicted_activations:
    min_entries: 10
  novelty:
    max_jaccard_overlap: 1.5
  signal_correlation:
    max_jaccard_overlap: 0.85
  regime_exposure:
    max_single_regime_concentration: 0.80
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="max_jaccard_overlap"):
        load_calibration(bad)


# ---------------------------------------------------------------------------
# AdjustmentProposal
# ---------------------------------------------------------------------------


def test_proposal_is_frozen() -> None:
    p = AdjustmentProposal(direction="tighten", magnitude_pct=0.10, reason="hit rate above 5%")
    with pytest.raises((AttributeError, Exception), match=r"cannot assign|frozen"):
        p.direction = "loosen"  # type: ignore[misc]


def test_proposal_rejects_unknown_direction() -> None:
    with pytest.raises(ValueError, match="direction"):
        AdjustmentProposal(direction="sideways", magnitude_pct=0.10, reason="x")  # type: ignore[arg-type]


def test_proposal_rejects_zero_or_negative_magnitude() -> None:
    with pytest.raises(ValueError, match="magnitude_pct"):
        AdjustmentProposal(direction="tighten", magnitude_pct=0.0, reason="x")
    with pytest.raises(ValueError, match="magnitude_pct"):
        AdjustmentProposal(direction="tighten", magnitude_pct=-0.1, reason="x")


def test_apply_tightening_returns_new_calibration_with_stricter_thresholds() -> None:
    """Tightening means: fewer candidates pass each filter. For floor
    thresholds (min_activations, min_trades) that means *higher*; for
    ceiling thresholds (max_jaccard, max_regime_concentration) that
    means *lower*; for p-value (stricter) lower."""
    c = load_calibration(_PREFILTER_YAML)
    p = AdjustmentProposal(direction="tighten", magnitude_pct=0.10, reason="x")
    new = apply_tightening(c, p)

    assert new.signal_density.min_activations > c.signal_density.min_activations
    assert new.expected_trade_count.min_trades > c.expected_trade_count.min_trades
    assert new.novelty.max_jaccard_overlap < c.novelty.max_jaccard_overlap
    assert (
        new.regime_exposure.max_single_regime_concentration
        < c.regime_exposure.max_single_regime_concentration
    )
    assert new.permutation_test.p_value_threshold < c.permutation_test.p_value_threshold


def test_apply_tightening_raises_and_caps_min_pass_probability() -> None:
    """M-8 (audit 2026-05-29): `min_pass_probability` is the D076 empirical-prior
    knob — the PRIMARY expected-trades gate for warmed buckets (rejects
    ~3,250/5,000 per batch live). A tighten must make it stricter (higher), not
    leave it untouched, but capped < 1.0 so it can't reject every warmed bucket."""
    from dataclasses import replace

    c = load_calibration(_PREFILTER_YAML)
    p = AdjustmentProposal(direction="tighten", magnitude_pct=0.10, reason="above 5%")
    new = apply_tightening(c, p)
    assert (
        new.expected_trade_count.min_pass_probability > c.expected_trade_count.min_pass_probability
    )
    # Cap holds even starting near 1.0.
    near = replace(
        c, expected_trade_count=replace(c.expected_trade_count, min_pass_probability=0.99)
    )
    assert apply_tightening(near, p).expected_trade_count.min_pass_probability <= 0.95


def test_apply_tightening_is_pure() -> None:
    """The input calibration must not be mutated."""
    c = load_calibration(_PREFILTER_YAML)
    snapshot = (
        c.signal_density.min_activations,
        c.novelty.max_jaccard_overlap,
    )
    apply_tightening(c, AdjustmentProposal(direction="tighten", magnitude_pct=0.10, reason="x"))
    assert (c.signal_density.min_activations, c.novelty.max_jaccard_overlap) == snapshot


def test_apply_tightening_rejects_loosen_proposal() -> None:
    """Type-level guard: `apply_tightening` must not silently apply a
    loosening proposal."""
    c = load_calibration(_PREFILTER_YAML)
    p = AdjustmentProposal(direction="loosen", magnitude_pct=0.10, reason="hit rate < 0.5%")
    with pytest.raises(ValueError, match="loosen"):
        apply_tightening(c, p)


# ---------------------------------------------------------------------------
# Loosening — proposal-only path (D3 + hard rule #4 analogue)
# ---------------------------------------------------------------------------


def test_module_does_not_expose_apply_loosening() -> None:
    """Structural enforcement of CLAUDE.md hard rule #4 (and the spec's
    analogous discipline for pre-filter loosening, D021/D3): there is
    NO ``apply_loosening`` function on this module (and, since D421, no loosening
    proposal writer either); loosening needs a preregistration + the operator."""
    assert not hasattr(calibration_module, "apply_loosening")


def test_calibration_module_public_surface() -> None:
    """Lock the public API so future drift gets caught by this test."""
    expected = {
        "AdjustmentProposal",
        "Calibration",
        "ExpectedTradeCountCalibration",
        "NoveltyCalibration",
        "PermutationTestCalibration",
        "PredictedActivationsCalibration",  # T1.3 (D038)
        "RegimeExposureCalibration",
        "SignalCorrelationCalibration",  # T2.6 (D042)
        "SignalDensityCalibration",
        "apply_tightening",
        "load_calibration",
    }
    assert set(calibration_module.__all__) == expected
