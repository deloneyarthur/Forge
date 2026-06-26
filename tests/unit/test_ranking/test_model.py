"""Tests for forge.ranking.model (D132 / F2) — pure-Python IRLS logistic model.

Determinism is the load-bearing property (hard-rule #5 posture): zero-init
Newton-IRLS on a convex objective with fixed iteration order and NO RNG —
the same training frame must produce a byte-identical artifact. The
operational minimum-rows guards live at the CLI, not here, so tiny toy
sets stay trainable in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from forge.ranking.model import (
    VerdictModel,
    auc_score,
    load_latest_model,
    load_model,
    save_model,
    score_features,
    train_verdict_model,
)

_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)


def _frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    """Build a build_dataset-shaped frame from feature dicts + labels."""
    feature_names = sorted({k for r in rows for k in r if k != "label"})
    records = []
    for i, row in enumerate(rows):
        record: dict[str, object] = {
            "crucible_run_id": f"run-{i:04d}",
            "config_hash": f"hash{i:012d}",
            "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
            "decision": "component" if row["label"] else "reject",
            "label": row["label"],
        }
        for name in feature_names:
            record[name] = float(row.get(name, 0.0))  # type: ignore[arg-type]
        records.append(record)
    return pl.DataFrame(records)


def _separable_rows(n_pos: int = 12, n_neg: int = 28) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(n_pos):
        rows.append({"label": 1, "f_good": 1.0, "f_noise": float(i % 2)})
    for i in range(n_neg):
        rows.append({"label": 0, "f_good": 0.0, "f_noise": float(i % 2)})
    return rows


# ---------------------------------------------------------------------------
# Training mechanics
# ---------------------------------------------------------------------------


def test_separable_signal_is_learned() -> None:
    model = train_verdict_model(_frame(_separable_rows()), lambda_=0.1, era_cut=_ERA_CUT)
    high = score_features(model, {"f_good": 1.0})
    low = score_features(model, {"f_good": 0.0})
    assert high > 0.5 > low
    coef = dict(zip(model.feature_names, model.coefficients, strict=True))
    assert coef["f_good"] > 0.0


def test_heavy_lambda_shrinks_to_base_rate() -> None:
    rows = _separable_rows(n_pos=10, n_neg=30)
    model = train_verdict_model(_frame(rows), lambda_=1e9, era_cut=_ERA_CUT)
    base_rate = 10 / 40
    assert score_features(model, {"f_good": 1.0}) == pytest.approx(base_rate, abs=0.01)
    assert all(abs(c) < 1e-3 for c in model.coefficients)


def test_zero_variance_column_dropped() -> None:
    rows = _separable_rows()
    for row in rows:
        row["always_one"] = 1.0
    model = train_verdict_model(_frame(rows), era_cut=_ERA_CUT)
    assert "always_one" not in model.feature_names
    assert "f_good" in model.feature_names


def test_single_class_raises() -> None:
    rows: list[dict[str, object]] = [{"label": 0, "f_good": 0.0} for _ in range(10)]
    with pytest.raises(ValueError, match="single class"):
        train_verdict_model(_frame(rows), era_cut=_ERA_CUT)


def test_metadata_recorded() -> None:
    model = train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT)
    assert model.n_rows == 40
    assert model.n_positive == 12
    assert model.era_cut == _ERA_CUT
    # trained_through = max decided_at in the frame.
    assert model.trained_through == datetime(2026, 6, 10, 18, 0, 39)  # noqa: DTZ001
    metrics = dict(model.train_metrics)
    assert metrics["auc"] == pytest.approx(1.0)
    assert 0.0 <= metrics["brier"] <= 0.25


# ---------------------------------------------------------------------------
# Rare-id collapse + unseen-id scoring
# ---------------------------------------------------------------------------


def _rows_with_ids() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    # 20 rows carry a common directional id (mixed labels), 3 a rare one.
    for i in range(20):
        rows.append({"label": int(i < 8), "dir_id=common_ind": 1.0, "f_noise": float(i % 2)})
    for i in range(3):
        rows.append({"label": 1, "dir_id=rare_ind": 1.0, "f_noise": float(i % 2)})
    for i in range(17):
        rows.append({"label": 0, "f_noise": float(i % 2)})
    return rows


def test_rare_id_collapses_to_other_bucket() -> None:
    model = train_verdict_model(_frame(_rows_with_ids()), era_cut=_ERA_CUT)
    assert "dir_id=common_ind" in model.feature_names
    assert "dir_id=rare_ind" not in model.feature_names
    assert "dir_id=__other__" in model.feature_names


def test_unseen_id_scores_via_other_bucket() -> None:
    model = train_verdict_model(_frame(_rows_with_ids()), era_cut=_ERA_CUT)
    # A brand-new arm's id maps onto the __other__ bucket — identical to any
    # other id outside the trained vocabulary.
    unseen = score_features(model, {"dir_id=never_seen": 1.0})
    rare = score_features(model, {"dir_id=rare_ind": 1.0})
    assert unseen == pytest.approx(rare)
    assert unseen != pytest.approx(score_features(model, {}))


# ---------------------------------------------------------------------------
# Determinism + artifact round-trip
# ---------------------------------------------------------------------------


def test_training_is_deterministic() -> None:
    a = train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT)
    b = train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT)
    assert a == b
    assert a.model_id == b.model_id


def test_artifact_bytes_identical_across_retrains(tmp_path: Path) -> None:
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    path_a = save_model(train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT), dir_a)
    path_b = save_model(train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT), dir_b)
    assert path_a.name == path_b.name
    assert path_a.read_bytes() == path_b.read_bytes()


def test_model_id_is_content_keyed() -> None:
    base = train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT)
    flipped_rows = _separable_rows()
    flipped_rows[0]["label"] = 0
    flipped = train_verdict_model(_frame(flipped_rows), era_cut=_ERA_CUT)
    assert base.model_id != flipped.model_id


def test_save_load_round_trip(tmp_path: Path) -> None:
    model = train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT)
    path = save_model(model, tmp_path)
    assert load_model(path) == model
    assert isinstance(load_model(path), VerdictModel)


def test_load_latest_model_picks_newest_trained_through(tmp_path: Path) -> None:
    rows_old = _separable_rows()
    old = train_verdict_model(_frame(rows_old), era_cut=_ERA_CUT)
    rows_new = _separable_rows(n_pos=13, n_neg=27)
    new = train_verdict_model(_frame(rows_new), era_cut=_ERA_CUT)
    # Same trained_through (same synthetic timestamps) — perturb via row count.
    save_model(old, tmp_path)
    save_model(new, tmp_path)
    latest = load_latest_model(tmp_path)
    assert latest is not None
    assert latest in (old, new)


def test_load_latest_model_empty_dir_returns_none(tmp_path: Path) -> None:
    assert load_latest_model(tmp_path) is None
    assert load_latest_model(tmp_path / "does_not_exist") is None


def test_corrupt_artifact_is_skipped_by_loader(tmp_path: Path) -> None:
    model = train_verdict_model(_frame(_separable_rows()), era_cut=_ERA_CUT)
    save_model(model, tmp_path)
    (tmp_path / "verdict_model_v1_garbage.json").write_text("{not json", encoding="utf-8")
    latest = load_latest_model(tmp_path)
    assert latest == model


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def test_auc_perfect_and_inverted_and_ties() -> None:
    assert auc_score([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == pytest.approx(1.0)
    assert auc_score([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == pytest.approx(0.0)
    assert auc_score([1, 0, 1, 0], [0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.5)


def test_auc_single_class_raises() -> None:
    with pytest.raises(ValueError, match="single class"):
        auc_score([1, 1], [0.5, 0.6])


# ---------------------------------------------------------------------------
# Tail-aware regression head (T1) — predicts continuous cpcv_p25 robustness
# ---------------------------------------------------------------------------


def _reg_frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    """build_dataset-shaped frame carrying regression targets + coverage flag."""
    reserved = {"target_cpcv_p25", "target_wf_median", "target_regime_stress", "coverage_verified"}
    feature_names = sorted({k for r in rows for k in r if k not in reserved})
    records = []
    for i, row in enumerate(rows):
        record: dict[str, object] = {
            "crucible_run_id": f"run-{i:04d}",
            "config_hash": f"hash{i:012d}",
            "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
            "decision": "component",
            "label": 1,
            "target_cpcv_p25": row.get("target_cpcv_p25"),
            "target_wf_median": row.get("target_wf_median", 1.0),
            "target_regime_stress": row.get("target_regime_stress", 0.5),
            "coverage_verified": float(row.get("coverage_verified", 1.0)),  # type: ignore[arg-type]
        }
        for name in feature_names:
            record[name] = float(row.get(name, 0.0))  # type: ignore[arg-type]
        records.append(record)
    return pl.DataFrame(records)


def _reg_rows() -> list[dict[str, object]]:
    # target_cpcv_p25 is linear in f_good (1.1 when set, 0.3 when not) + noise;
    # coverage_verified varies (24/6) so it survives standardization as a feature.
    rows: list[dict[str, object]] = []
    for i in range(30):
        good = float(i % 2)
        rows.append(
            {
                "f_good": good,
                "f_noise": float(i % 3),
                "coverage_verified": float(i % 5 != 0),
                "target_cpcv_p25": 0.3 + 0.8 * good,
            }
        )
    return rows


def test_robustness_learns_continuous_target() -> None:
    from forge.ranking.model import score_robustness, train_robustness_model

    model = train_robustness_model(_reg_frame(_reg_rows()), lambda_=0.01, era_cut=_ERA_CUT)
    high = score_robustness(model, {"f_good": 1.0})
    low = score_robustness(model, {"f_good": 0.0})
    assert high > low
    assert model.target == "target_cpcv_p25"


def test_robustness_excludes_other_targets_keeps_coverage_feature() -> None:
    from forge.ranking.model import train_robustness_model

    model = train_robustness_model(_reg_frame(_reg_rows()), era_cut=_ERA_CUT)
    assert "coverage_verified" in model.feature_names
    assert not any(n.startswith("target_") for n in model.feature_names)


def test_robustness_score_defaults_coverage_verified_to_one() -> None:
    # Score-time convention (§8.2): coverage_verified is a train-time-only signal;
    # absent at score time it is fixed to 1.0 (predict the verified-quality value).
    from forge.ranking.model import score_robustness, train_robustness_model

    model = train_robustness_model(_reg_frame(_reg_rows()), era_cut=_ERA_CUT)
    assert score_robustness(model, {"f_good": 1.0}) == pytest.approx(
        score_robustness(model, {"f_good": 1.0, "coverage_verified": 1.0})
    )


def test_robustness_drops_null_target_rows() -> None:
    from forge.ranking.model import train_robustness_model

    rows = _reg_rows()
    rows.append({"f_good": 1.0, "target_cpcv_p25": None})
    model = train_robustness_model(_reg_frame(rows), era_cut=_ERA_CUT)
    assert model.n_rows == 30  # the null-target row dropped


def test_robustness_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    from forge.ranking.model import (
        load_robustness_model,
        save_robustness_model,
        train_robustness_model,
    )

    a = train_robustness_model(_reg_frame(_reg_rows()), era_cut=_ERA_CUT)
    b = train_robustness_model(_reg_frame(_reg_rows()), era_cut=_ERA_CUT)
    assert a == b
    path = save_robustness_model(a, tmp_path)
    assert load_robustness_model(path) == a


def test_robustness_excludes_the_target_column_from_features() -> None:
    # A label-sourced target (e.g. target_wf_p25, not in TARGET_COLUMNS) must still be
    # excluded from the feature set — else the target leaks in and predicts itself.
    from forge.ranking.model import train_robustness_model

    frame = _reg_frame(_reg_rows()).with_columns(pl.col("target_cpcv_p25").alias("target_wf_p25"))
    model = train_robustness_model(frame, target="target_wf_p25", era_cut=_ERA_CUT)
    assert model.target == "target_wf_p25"
    assert "target_wf_p25" not in model.feature_names


def test_robustness_tail_norm_bounded_and_monotone() -> None:
    # The §6.2 prior BLEND needs the unbounded robustness prediction mapped to (0, 1),
    # monotone in the prediction so the validated rank-IC is preserved.
    from forge.ranking.model import robustness_tail_norm, train_robustness_model

    model = train_robustness_model(_reg_frame(_reg_rows()), lambda_=0.01, era_cut=_ERA_CUT)
    high = robustness_tail_norm(model, {"f_good": 1.0})
    low = robustness_tail_norm(model, {"f_good": 0.0})
    assert 0.0 < low < high < 1.0
    # Deterministic: same inputs -> same output.
    assert robustness_tail_norm(model, {"f_good": 1.0}) == high


def test_load_latest_robustness_model_filters_by_target(tmp_path: Path) -> None:
    # R1: the loader must select the newest model OF A REQUESTED TARGET, not the newest
    # of any target — the quality lane (wf_p25) and the §8.6 shadow co-exist with the
    # cpcv robustness model in one dir, and the cpcv one is retrained daily so it is
    # almost always the newest. Target-blind load would never surface the wf_p25 model.
    from forge.ranking.model import (
        load_latest_robustness_model,
        save_robustness_model,
        train_robustness_model,
    )

    wf_frame = _reg_frame(_reg_rows()).with_columns(
        pl.col("target_cpcv_p25").alias("target_wf_p25")
    )
    wf_model = train_robustness_model(wf_frame, target="target_wf_p25", era_cut=_ERA_CUT)
    # A cpcv model trained "a day later" so it is unambiguously the newest artifact.
    cpcv_frame = _reg_frame(_reg_rows()).with_columns(
        (pl.col("decided_at") + pl.duration(days=1)).alias("decided_at")
    )
    cpcv_model = train_robustness_model(cpcv_frame, era_cut=_ERA_CUT)
    assert cpcv_model.trained_through > wf_model.trained_through
    save_robustness_model(wf_model, tmp_path)
    save_robustness_model(cpcv_model, tmp_path)

    # Target-blind (default) → newest of any target = the cpcv model.
    blind = load_latest_robustness_model(tmp_path)
    assert blind is not None
    assert blind.target == "target_cpcv_p25"
    # Target-aware → the wf_p25 model even though the cpcv one is newer.
    wf = load_latest_robustness_model(tmp_path, target="target_wf_p25")
    assert wf is not None
    assert wf.model_id == wf_model.model_id
    assert wf.target == "target_wf_p25"
    # Target-aware → the cpcv model when asked.
    cpcv = load_latest_robustness_model(tmp_path, target="target_cpcv_p25")
    assert cpcv is not None
    assert cpcv.model_id == cpcv_model.model_id
    # A target with no artifact → None (not a fallback to a different target).
    assert load_latest_robustness_model(tmp_path, target="target_regime_stress") is None


def test_gate_tail_rank_score_gates_then_ranks_by_tail() -> None:
    """Two-part lane: P(component) gates eligibility; the tail prediction does the ordering."""
    from forge.ranking.model import gate_tail_rank_score

    # Eligible (P >= floor): the score IS the tail prediction — P never enters the order.
    assert gate_tail_rank_score(0.9, -1.0, p_floor=0.5) == -1.0
    assert gate_tail_rank_score(0.5, 2.0, p_floor=0.5) == 2.0

    # An eligible config with a POOR tail still outranks an ineligible one with a GREAT tail.
    eligible_poor = gate_tail_rank_score(0.9, -1.0, p_floor=0.5)
    ineligible_great = gate_tail_rank_score(0.1, 5.0, p_floor=0.5)
    assert eligible_poor > ineligible_great

    # Among eligibles, higher tail ranks higher even when its P is lower (P is anti-signal).
    high_tail_low_p = gate_tail_rank_score(0.51, 2.0, p_floor=0.5)
    low_tail_high_p = gate_tail_rank_score(0.99, 1.0, p_floor=0.5)
    assert high_tail_low_p > low_tail_high_p
