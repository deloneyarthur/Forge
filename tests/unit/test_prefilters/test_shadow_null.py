"""Unit tests for `forge.prefilters.shadow_null` (strategy-audit P1-2).

The shadow-count aggregator: given, per config that REACHED the §5.3.7
permutation_test, its pass/fail under the PRODUCTION null and under the
CORRECTED null (cumulative_trading + volatility_event |move|), summarize the
per-family survival delta. Pure — no feature cache, no RNG, no I/O — so the
flip's predicted effect can be unit-checked independently of the live pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.prefilters.calibration import load_calibration
from forge.prefilters.shadow_null import (
    FamilyShadowDelta,
    ShadowNullRecord,
    cumulative_only_calibration,
    summarize_shadow_null,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _rec(hypothesis: str, prod: bool, corr: bool) -> ShadowNullRecord:
    return ShadowNullRecord(hypothesis=hypothesis, prod_passed=prod, corr_passed=corr)


def test_empty_records_empty_summary() -> None:
    summary = summarize_shadow_null([])
    assert summary.per_family == ()
    assert summary.total_reached == 0
    assert summary.total_pass_prod == 0
    assert summary.total_pass_corr == 0
    assert summary.total_gained == 0
    assert summary.total_lost == 0
    assert summary.total_net_delta == 0


def test_single_family_all_four_cells() -> None:
    # PP, PF (lost), FP (gained), FF — one of each.
    records = [
        _rec("trend_continuation", True, True),  # PP
        _rec("trend_continuation", True, False),  # PF -> lost
        _rec("trend_continuation", False, True),  # FP -> gained
        _rec("trend_continuation", False, False),  # FF
    ]
    summary = summarize_shadow_null(records)
    assert len(summary.per_family) == 1
    fam = summary.per_family[0]
    assert fam.hypothesis == "trend_continuation"
    assert fam.reached == 4
    assert fam.pass_prod == 2  # PP + PF
    assert fam.pass_corr == 2  # PP + FP
    assert fam.gained == 1  # FP
    assert fam.lost == 1  # PF
    assert fam.net_delta == 0  # gained - lost
    assert fam.prod_rate == pytest.approx(0.5)
    assert fam.corr_rate == pytest.approx(0.5)


def test_net_delta_is_gained_minus_lost_identity() -> None:
    # ve is the family the correction is expected to HELP: several FP flips.
    records = [
        _rec("volatility_event", False, True),  # gained
        _rec("volatility_event", False, True),  # gained
        _rec("volatility_event", True, False),  # lost
        _rec("volatility_event", True, True),  # PP
    ]
    fam = summarize_shadow_null(records).per_family[0]
    assert fam.gained == 2
    assert fam.lost == 1
    assert fam.net_delta == fam.gained - fam.lost == 1
    assert fam.pass_corr - fam.pass_prod == fam.net_delta


def test_multiple_families_sorted_and_totalled() -> None:
    records = [
        _rec("volatility_event", False, True),  # gained
        _rec("trend_continuation", True, False),  # lost
        _rec("mean_reversion", True, True),  # PP
        _rec("volatility_event", False, True),  # gained
        _rec("mean_reversion", False, False),  # FF
    ]
    summary = summarize_shadow_null(records)
    # Deterministic order: sorted by hypothesis regardless of input order.
    assert [f.hypothesis for f in summary.per_family] == [
        "mean_reversion",
        "trend_continuation",
        "volatility_event",
    ]
    ve = next(f for f in summary.per_family if f.hypothesis == "volatility_event")
    assert ve.reached == 2
    assert ve.gained == 2
    assert ve.net_delta == 2
    # Totals.
    assert summary.total_reached == 5
    assert summary.total_gained == 2
    assert summary.total_lost == 1
    assert summary.total_net_delta == 1  # 2 gained - 1 lost
    assert summary.total_pass_prod == 2  # trend(T) + mr(T)
    assert summary.total_pass_corr == 3  # ve(T) + ve(T) + mr(T)


def test_summarize_is_order_independent() -> None:
    a = [_rec("x", True, False), _rec("x", False, True), _rec("y", True, True)]
    b = [a[2], a[0], a[1]]
    assert summarize_shadow_null(a) == summarize_shadow_null(b)


def test_family_delta_rejects_inconsistent_counts() -> None:
    # pass_corr must equal pass_prod + gained - lost.
    with pytest.raises(ValueError, match="net-delta identity"):
        FamilyShadowDelta(hypothesis="x", reached=4, pass_prod=2, pass_corr=3, gained=0, lost=0)


def test_family_delta_rejects_pass_exceeding_reached() -> None:
    with pytest.raises(ValueError, match="reached"):
        FamilyShadowDelta(hypothesis="x", reached=2, pass_prod=3, pass_corr=3, gained=0, lost=0)


def test_family_delta_rejects_negative_flip_counts() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        FamilyShadowDelta(hypothesis="x", reached=2, pass_prod=1, pass_corr=0, gained=-1, lost=0)


def test_cumulative_only_flips_only_the_null_knob() -> None:
    from dataclasses import replace

    # Test the builder on a KNOWN single_day base — decoupled from the live config, which
    # ships `cumulative_trading` since the D237 flip. The builder's contract (flip ONLY the
    # null mode, leave every other section identity) is what this guards. (The flip-2
    # `corrected_null_calibration` builder was removed at D301 — dropped at D235.)
    base = load_calibration(_REPO_ROOT / "config" / "prefilter.yaml")
    prod = replace(
        base,
        permutation_test=replace(
            base.permutation_test,
            forward_return_mode="single_day",
        ),
    )
    b = cumulative_only_calibration(prod)
    assert b.permutation_test.forward_return_mode == "cumulative_trading"
    # Nothing else about the null moved (horizon / n_permutations / threshold).
    assert b.permutation_test.forward_horizon_days == prod.permutation_test.forward_horizon_days
    assert b.permutation_test.n_permutations == prod.permutation_test.n_permutations
    assert b.permutation_test.p_value_threshold == prod.permutation_test.p_value_threshold
    # Every OTHER filter section is untouched (identity), so the population that
    # reaches permutation_test is identical under both calibrations.
    assert b.signal_density == prod.signal_density
    assert b.expected_trade_count == prod.expected_trade_count
    assert b.predicted_activations == prod.predicted_activations
    assert b.novelty == prod.novelty
    assert b.signal_correlation == prod.signal_correlation
    assert b.regime_exposure == prod.regime_exposure
    assert b.auto_tune == prod.auto_tune
