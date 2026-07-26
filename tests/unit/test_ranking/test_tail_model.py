"""Tail-lane model: a logistic on a TOP-N label over a continuous base metric.

WHY THIS SHAPE (prereg `8cfe95f4a6e9`). The quality lane orders by `E[cpcv_p25]`, an
average-shaped objective, while promotion is a tail event. On stage-one cells
spearman(cell MEAN, cell STD) = -0.148 while spearman(cell P(>=1.0), cell STD) = +0.500 —
the mean carries no information about tail production. Offline, ordering by
`P(sharpe_baseline >= top-800)` delivers 307 strong components per 4,520 selected against
the incumbent's 131.

WHY TOP-N AND NOT A QUANTILE. Three independent tuned parameters failed to transfer forward
on this data (the exceedance tau, the `wf_p10` quantile, the blend weight), and `wf_p10`
carries a mass point at zero where a quantile threshold lands inside a tie block and turns
the label into an arbitrary tie-break. A count cannot land in a tie block and carries no
knob to mis-tune.
"""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl
import pytest

from forge.ranking.model import train_tail_model

_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)


def _frame(values: list[float], feature: list[float]) -> pl.DataFrame:
    """A build_dataset-shaped frame carrying one base metric and one feature."""
    records = []
    for i, (v, f) in enumerate(zip(values, feature, strict=True)):
        records.append(
            {
                "crucible_run_id": f"run-{i:04d}",
                "config_hash": f"hash{i:012d}",
                "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                "decision": "reject",
                "label": 0,
                "target_sharpe_baseline": v,
                "f_signal": f,
            }
        )
    return pl.DataFrame(records)


def test_labels_the_top_n_by_the_base_metric() -> None:
    # 40 rows; the top 10 by base metric carry the feature, the rest do not.
    values = [float(i) for i in range(40)]
    feature = [1.0 if i >= 30 else 0.0 for i in range(40)]
    model = train_tail_model(
        _frame(values, feature), base_target="target_sharpe_baseline", n_pos=10, era_cut=_ERA_CUT
    )
    assert model.n_positive == 10
    assert model.n_rows == 40
    assert model.base_target == "target_sharpe_baseline"
    # The feature that perfectly identifies the top-10 must get a positive weight.
    weights = dict(zip(model.feature_names, model.coefficients, strict=True))
    assert weights["f_signal"] > 0.0


def test_top_n_label_is_immune_to_a_mass_point() -> None:
    """A quantile threshold can land INSIDE a tie block and become an arbitrary
    tie-break — the defect that produced `wf_p10`'s 7x cliff between adjacent
    quantiles. `top-N` selects exactly N and cannot."""
    # 90% of rows tied at exactly 0.0; a q<=0.90 threshold would sit in the tie.
    values = [0.0] * 36 + [float(i) for i in range(1, 5)]
    feature = [0.0] * 36 + [1.0] * 4
    model = train_tail_model(
        _frame(values, feature), base_target="target_sharpe_baseline", n_pos=4, era_cut=_ERA_CUT
    )
    assert model.n_positive == 4


def test_rows_with_a_null_base_metric_are_dropped() -> None:
    values = [float(i) for i in range(30)]
    feature = [1.0 if i >= 25 else 0.0 for i in range(30)]
    frame = _frame(values, feature).with_columns(
        pl.when(pl.col("crucible_run_id") == "run-0000")
        .then(None)
        .otherwise(pl.col("target_sharpe_baseline"))
        .alias("target_sharpe_baseline")
    )
    model = train_tail_model(frame, base_target="target_sharpe_baseline", n_pos=5, era_cut=_ERA_CUT)
    assert model.n_rows == 29


def test_refuses_a_degenerate_label() -> None:
    values = [float(i) for i in range(20)]
    with pytest.raises(ValueError, match="single class"):
        train_tail_model(
            _frame(values, [0.0] * 20),
            base_target="target_sharpe_baseline",
            n_pos=20,
            era_cut=_ERA_CUT,
        )


def test_does_not_ingest_target_columns_as_features() -> None:
    """The base metric is the LABEL. If it leaked in as a feature the model would
    trivially reproduce it and learn nothing about configs."""
    values = [float(i) for i in range(40)]
    feature = [1.0 if i >= 30 else 0.0 for i in range(40)]
    model = train_tail_model(
        _frame(values, feature), base_target="target_sharpe_baseline", n_pos=10, era_cut=_ERA_CUT
    )
    assert "target_sharpe_baseline" not in model.feature_names
    assert not any(n.startswith("target_") for n in model.feature_names)


def test_model_id_is_deterministic_for_identical_input() -> None:
    values = [float(i) for i in range(40)]
    feature = [1.0 if i >= 30 else 0.0 for i in range(40)]
    kwargs = {"base_target": "target_sharpe_baseline", "n_pos": 10, "era_cut": _ERA_CUT}
    a = train_tail_model(_frame(values, feature), **kwargs)  # type: ignore[arg-type]
    b = train_tail_model(_frame(values, feature), **kwargs)  # type: ignore[arg-type]
    assert a.model_id == b.model_id


def test_n_pos_changes_the_model_id() -> None:
    """`n_pos` is part of the model's identity — two lanes trained at different
    label sizes must not collide in the models dir."""
    values = [float(i) for i in range(40)]
    feature = [1.0 if i >= 30 else 0.0 for i in range(40)]
    a = train_tail_model(
        _frame(values, feature), base_target="target_sharpe_baseline", n_pos=10, era_cut=_ERA_CUT
    )
    b = train_tail_model(
        _frame(values, feature), base_target="target_sharpe_baseline", n_pos=8, era_cut=_ERA_CUT
    )
    assert a.model_id != b.model_id
