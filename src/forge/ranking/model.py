"""Pure-Python L2 logistic regression for the learned verdict model (D132 / F2).

Zero new dependencies (D132 decision 2): Newton-IRLS on the convex penalized
log-likelihood, zero-init, fixed iteration order, NO RNG anywhere — the same
training frame produces a byte-identical artifact (invariant-tested). At the
window cap (10k rows x ~90 features) a train run is minutes of CPU in pure
Python; accepted in D132 over adding numpy/sklearn.

Artifacts are canonical JSON with coefficients BY FEATURE NAME so the operator
can read what the model believes at every eval. The models directory is
append-only (the `grammar_archive/` analog): same content → same filename →
idempotent rewrite; new content → new content-hashed name.

Rare id-level features (``dir_id=…`` / ``regime_id=…`` / ``exit=…`` columns
with < 10 nonzero training rows) collapse into a per-prefix ``__other__``
bucket; at score time an id outside the trained vocabulary maps onto the same
bucket — this is how a newly activated arm gets a feature-based prior on day
one instead of starting blind.

The operational minimum-rows guards live at the CLI (`ranker_model_cmd`), not
here — the library trains any two-class frame.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from forge.ranking.dataset import COVERAGE_FEATURE, TARGET_COLUMNS
from forge.ranking.features import FEATURE_SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import polars as pl

_LOG = structlog.get_logger(__name__)

# Frame columns that are row identity, not features (build_dataset contract).
_IDENTITY_COLUMNS = frozenset({"crucible_run_id", "config_hash", "decided_at", "decision", "label"})

# Columns the P(component) logistic model must NEVER ingest as features: the
# regression targets (labels for the tail-aware head) and coverage_verified
# (collinear with the honesty label). Keeps this model byte-identical to F2.
_LOGISTIC_NON_FEATURES = _IDENTITY_COLUMNS | set(TARGET_COLUMNS) | {COVERAGE_FEATURE}

# Id-level feature prefixes whose rare members collapse into "<prefix>=__other__".
_COLLAPSIBLE_PREFIXES = ("dir_id", "regime_id", "exit")
_OTHER = "__other__"
_MIN_ID_ROWS = 10

_MAX_ITERATIONS = 100
_CONVERGENCE_TOL = 1e-10
_PROB_CLIP = 1e-9


@dataclass(frozen=True, slots=True)
class VerdictModel:
    """A trained, fully self-describing artifact. All tuples align by index."""

    schema_version: int
    model_id: str
    trained_through: datetime
    era_cut: datetime
    n_rows: int
    n_positive: int
    lambda_: float
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    stds: tuple[float, ...]
    intercept: float
    coefficients: tuple[float, ...]
    train_metrics: tuple[tuple[str, float], ...]


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def auc_score(labels: Sequence[int], scores: Sequence[float]) -> float:
    """Mann-Whitney AUC with average ranks for ties."""
    n_pos = sum(1 for y in labels if y == 1)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        msg = "AUC undefined on a single class"
        raise ValueError(msg)
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    rank_sum_pos = sum(r for r, y in zip(ranks, labels, strict=True) if y == 1)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def brier_score(labels: Sequence[int], probs: Sequence[float]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels, strict=True)) / len(labels)


def _log_loss(labels: Sequence[int], probs: Sequence[float]) -> float:
    total = 0.0
    for p, y in zip(probs, labels, strict=True):
        clipped = min(1.0 - _PROB_CLIP, max(_PROB_CLIP, p))
        total += -(y * math.log(clipped) + (1 - y) * math.log(1.0 - clipped))
    return total / len(labels)


def _sigmoid(z: float) -> float:
    if z >= 35.0:
        return 1.0
    if z <= -35.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


# ---------------------------------------------------------------------------
# Linear algebra (dense, symmetric-exploiting)
# ---------------------------------------------------------------------------


def _solve_linear(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting. Deterministic."""
    n = len(matrix)
    aug = [[*row, rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            msg = "singular system in IRLS solve"
            raise ValueError(msg)
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_row = aug[col]
        pivot_value = pivot_row[col]
        for r in range(col + 1, n):
            factor = aug[r][col] / pivot_value
            if factor != 0.0:
                row = aug[r]
                for c in range(col, n + 1):
                    row[c] -= factor * pivot_row[c]
    solution = [0.0] * n
    for r in range(n - 1, -1, -1):
        acc = aug[r][n]
        row = aug[r]
        for c in range(r + 1, n):
            acc -= row[c] * solution[c]
        solution[r] = acc / row[r]
    return solution


def _fit_irls(
    x_rows: list[list[float]], labels: list[int], lambda_: float
) -> tuple[float, list[float]]:
    """Newton-IRLS on the L2-penalized log-likelihood; intercept unpenalized."""
    d = len(x_rows[0]) if x_rows else 0
    beta = [0.0] * (d + 1)  # beta[0] = intercept
    for _ in range(_MAX_ITERATIONS):
        probs = [
            _sigmoid(beta[0] + sum(b * v for b, v in zip(beta[1:], row, strict=True)))
            for row in x_rows
        ]
        gradient = [0.0] * (d + 1)
        hessian = [[0.0] * (d + 1) for _ in range(d + 1)]
        for row, y, p in zip(x_rows, labels, probs, strict=True):
            residual = y - p
            weight = max(p * (1.0 - p), _PROB_CLIP)
            gradient[0] += residual
            hessian[0][0] += weight
            for j in range(d):
                xj = row[j]
                if xj == 0.0:
                    continue
                gradient[j + 1] += xj * residual
                wxj = weight * xj
                hessian[0][j + 1] += wxj
                for k in range(j, d):
                    xk = row[k]
                    if xk != 0.0:
                        hessian[j + 1][k + 1] += wxj * xk
        # Symmetrize + L2 penalty (intercept exempt).
        for j in range(1, d + 1):
            hessian[j][0] = hessian[0][j]
            gradient[j] -= lambda_ * beta[j]
            hessian[j][j] += lambda_
            for k in range(j + 1, d + 1):
                hessian[k][j] = hessian[j][k]
        delta = _solve_linear(hessian, gradient)
        beta = [b + s for b, s in zip(beta, delta, strict=True)]
        if max(abs(s) for s in delta) < _CONVERGENCE_TOL:
            break
    return beta[0], beta[1:]


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def _other_name(prefix: str) -> str:
    return f"{prefix}={_OTHER}"


def _collapsible_prefix(name: str) -> str | None:
    prefix = name.split("=", 1)[0]
    return prefix if prefix in _COLLAPSIBLE_PREFIXES else None


def _standardize_design(
    columns: dict[str, list[float]], raw_names: list[str], n_rows: int
) -> tuple[list[str], list[float], list[float], list[list[float]]]:
    """Collapse rare id-level columns into per-prefix ``__other__`` buckets, drop
    zero-variance columns, and standardize the rest. Returns
    ``(feature_names, means, stds, x_rows)``. Shared by the logistic and ridge
    trainers so both featurize identically (behavior pinned by their suites)."""
    merged: dict[str, list[float]] = {}
    for name in raw_names:
        values = columns[name]
        prefix = _collapsible_prefix(name)
        if prefix is not None and sum(1 for v in values if v != 0.0) < _MIN_ID_ROWS:
            bucket = merged.setdefault(_other_name(prefix), [0.0] * n_rows)
            for i, v in enumerate(values):
                bucket[i] += v
        else:
            merged[name] = values

    feature_names: list[str] = []
    means: list[float] = []
    stds: list[float] = []
    standardized_columns: list[list[float]] = []
    for name in sorted(merged):
        values = merged[name]
        mean = sum(values) / n_rows
        variance = sum((v - mean) ** 2 for v in values) / n_rows
        if variance <= 0.0:
            continue
        std = math.sqrt(variance)
        feature_names.append(name)
        means.append(mean)
        stds.append(std)
        standardized_columns.append([(v - mean) / std for v in values])

    x_rows = [[col[i] for col in standardized_columns] for i in range(n_rows)]
    return feature_names, means, stds, x_rows


def train_verdict_model(
    frame: pl.DataFrame,
    *,
    lambda_: float = 1.0,
    era_cut: datetime,
) -> VerdictModel:
    """Fit on a `build_dataset` frame. Raises ValueError on empty/single-class."""
    labels = [int(v) for v in frame["label"].to_list()]
    n_rows = len(labels)
    n_positive = sum(labels)
    if n_rows == 0 or n_positive in (0, n_rows):
        msg = f"cannot train on a single class ({n_positive}/{n_rows} positive)"
        raise ValueError(msg)

    raw_names = [c for c in frame.columns if c not in _LOGISTIC_NON_FEATURES]
    columns = {name: [float(v) for v in frame[name].to_list()] for name in raw_names}
    feature_names, means, stds, x_rows = _standardize_design(columns, raw_names, n_rows)
    intercept, coefficients = _fit_irls(x_rows, labels, lambda_)

    probs = [
        _sigmoid(intercept + sum(b * v for b, v in zip(coefficients, row, strict=True)))
        for row in x_rows
    ]
    metrics = (
        ("auc", auc_score(labels, probs)),
        ("brier", brier_score(labels, probs)),
        ("log_loss", _log_loss(labels, probs)),
    )

    trained_through = max(frame["decided_at"].to_list())
    payload = _payload(
        trained_through=trained_through,
        era_cut=era_cut,
        n_rows=n_rows,
        n_positive=n_positive,
        lambda_=lambda_,
        feature_names=tuple(feature_names),
        means=tuple(means),
        stds=tuple(stds),
        intercept=intercept,
        coefficients=tuple(coefficients),
        train_metrics=metrics,
    )
    model_id = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:16]
    return VerdictModel(
        schema_version=FEATURE_SCHEMA_VERSION,
        model_id=model_id,
        trained_through=trained_through,
        era_cut=era_cut,
        n_rows=n_rows,
        n_positive=n_positive,
        lambda_=lambda_,
        feature_names=tuple(feature_names),
        means=tuple(means),
        stds=tuple(stds),
        intercept=intercept,
        coefficients=tuple(coefficients),
        train_metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_features(model: VerdictModel, features: Mapping[str, float]) -> float:
    """Calibrated P(component) for one feature dict (`FeatureVector.as_dict()`).

    Features outside the trained vocabulary map onto their prefix's
    ``__other__`` bucket when one exists; everything else is ignored.
    """
    index = {name: i for i, name in enumerate(model.feature_names)}
    x = [0.0] * len(model.feature_names)
    for name, value in features.items():
        i = index.get(name)
        if i is None:
            prefix = _collapsible_prefix(name)
            if prefix is None:
                continue
            i = index.get(_other_name(prefix))
            if i is None:
                continue
        x[i] += value
    z = model.intercept
    for i, (coef, mean, std) in enumerate(
        zip(model.coefficients, model.means, model.stds, strict=True)
    ):
        z += coef * (x[i] - mean) / std
    return _sigmoid(z)


# ---------------------------------------------------------------------------
# Artifact persistence (append-only models dir)
# ---------------------------------------------------------------------------


def _payload(**fields: object) -> dict[str, object]:
    out: dict[str, object] = {"schema_version": FEATURE_SCHEMA_VERSION}
    for key, value in fields.items():
        name = key.rstrip("_") if key == "lambda_" else key
        if isinstance(value, datetime):
            out[name] = value.isoformat()
        elif isinstance(value, tuple) and value and isinstance(value[0], tuple):
            out[name] = {k: v for k, v in value}  # train_metrics
        elif isinstance(value, tuple):
            out[name] = list(value)
        else:
            out[name] = value
    return out


def _canonical(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def save_model(model: VerdictModel, models_dir: Path) -> Path:
    """Write the canonical artifact; content-hashed name makes this idempotent."""
    models_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload(
        trained_through=model.trained_through,
        era_cut=model.era_cut,
        n_rows=model.n_rows,
        n_positive=model.n_positive,
        lambda_=model.lambda_,
        feature_names=model.feature_names,
        means=model.means,
        stds=model.stds,
        intercept=model.intercept,
        coefficients=model.coefficients,
        train_metrics=model.train_metrics,
    )
    payload["model_id"] = model.model_id
    stamp = model.trained_through.strftime("%Y%m%dT%H%M%S")
    path = models_dir / f"verdict_model_v{model.schema_version}_{stamp}Z_{model.model_id[:8]}.json"
    path.write_text(_canonical(payload), encoding="utf-8")
    return path


def load_model(path: Path) -> VerdictModel:
    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = tuple(sorted((str(k), float(v)) for k, v in raw["train_metrics"].items()))
    return VerdictModel(
        schema_version=int(raw["schema_version"]),
        model_id=str(raw["model_id"]),
        trained_through=datetime.fromisoformat(raw["trained_through"]),
        era_cut=datetime.fromisoformat(raw["era_cut"]),
        n_rows=int(raw["n_rows"]),
        n_positive=int(raw["n_positive"]),
        lambda_=float(raw["lambda"]),
        feature_names=tuple(raw["feature_names"]),
        means=tuple(raw["means"]),
        stds=tuple(raw["stds"]),
        intercept=float(raw["intercept"]),
        coefficients=tuple(raw["coefficients"]),
        train_metrics=metrics,
    )


def load_latest_model(models_dir: Path) -> VerdictModel | None:
    """Newest valid artifact by (trained_through, model_id); corrupt files skipped."""
    if not models_dir.is_dir():
        return None
    candidates: list[VerdictModel] = []
    for path in sorted(models_dir.glob("verdict_model_*.json")):
        try:
            candidates.append(load_model(path))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            _LOG.warning("verdict_model_artifact_unreadable", path=str(path), error=str(exc))
    if not candidates:
        return None
    return max(candidates, key=lambda m: (m.trained_through, m.model_id))


# ---------------------------------------------------------------------------
# Tail-aware robustness head (T1) — ridge regression on a continuous gate value
# ---------------------------------------------------------------------------

# Regression features = everything except identity and the regression TARGETS.
# coverage_verified IS kept here (a train-time conditioning signal, §8.2) —
# unlike the logistic model, which drops it as label-collinear.
_REGRESSION_NON_FEATURES = _IDENTITY_COLUMNS | set(TARGET_COLUMNS)


@dataclass(frozen=True, slots=True)
class RobustnessModel:
    """A trained ridge model predicting a continuous worst-quartile gate value
    (default ``cpcv_sharpe_p25``). Self-describing; tuples align by index."""

    schema_version: int
    model_id: str
    trained_through: datetime
    era_cut: datetime
    target: str
    n_rows: int
    lambda_: float
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    stds: tuple[float, ...]
    target_mean: float
    coefficients: tuple[float, ...]
    train_metrics: tuple[tuple[str, float], ...]


def _solve_ridge(x_rows: list[list[float]], y_centered: list[float], lambda_: float) -> list[float]:
    """Ridge normal equations ``(XᵀX + λI)β = Xᵀy`` on standardized X (so the
    intercept is just the unpenalized target mean). Deterministic — the same
    dense Gaussian solve as IRLS; λ>0 keeps the system positive-definite."""
    d = len(x_rows[0]) if x_rows else 0
    if d == 0:
        return []
    ata = [[0.0] * d for _ in range(d)]
    aty = [0.0] * d
    for row, yi in zip(x_rows, y_centered, strict=True):
        for j in range(d):
            xj = row[j]
            if xj == 0.0:
                continue
            aty[j] += xj * yi
            for k in range(j, d):
                ata[j][k] += xj * row[k]
    for j in range(d):
        ata[j][j] += lambda_
        for k in range(j + 1, d):
            ata[k][j] = ata[j][k]
    return _solve_linear(ata, aty)


def _robustness_fields(**fields: object) -> dict[str, object]:
    """Canonical, model_id-free payload — the content the model_id hashes."""
    out: dict[str, object] = {"schema_version": FEATURE_SCHEMA_VERSION, "kind": "robustness"}
    for key, value in fields.items():
        name = key.rstrip("_") if key == "lambda_" else key
        if isinstance(value, datetime):
            out[name] = value.isoformat()
        elif isinstance(value, tuple) and value and isinstance(value[0], tuple):
            out[name] = {k: v for k, v in value}  # train_metrics
        elif isinstance(value, tuple):
            out[name] = list(value)
        else:
            out[name] = value
    return out


def train_robustness_model(
    frame: pl.DataFrame,
    *,
    target: str = "target_cpcv_p25",
    lambda_: float = 1.0,
    era_cut: datetime,
) -> RobustnessModel:
    """Fit a ridge model predicting ``target`` from config features (+
    coverage_verified). Rows whose target is null are dropped; raises ValueError
    if none carry it."""
    if target not in frame.columns:
        msg = f"target column {target!r} not in frame"
        raise ValueError(msg)

    target_raw = frame[target].to_list()
    keep = [i for i, v in enumerate(target_raw) if v is not None]
    n_rows = len(keep)
    if n_rows == 0:
        msg = f"no rows carry a non-null {target}"
        raise ValueError(msg)
    y = [float(target_raw[i]) for i in keep]

    raw_names = [c for c in frame.columns if c not in _REGRESSION_NON_FEATURES]
    raw_columns = {name: frame[name].to_list() for name in raw_names}
    columns = {name: [float(raw_columns[name][i]) for i in keep] for name in raw_names}
    feature_names, means, stds, x_rows = _standardize_design(columns, raw_names, n_rows)

    target_mean = sum(y) / n_rows
    coefficients = _solve_ridge(x_rows, [yi - target_mean for yi in y], lambda_)

    preds = [
        target_mean + sum(b * v for b, v in zip(coefficients, row, strict=True)) for row in x_rows
    ]
    ss_res = sum((t - p) ** 2 for t, p in zip(y, preds, strict=True))
    ss_tot = sum((t - target_mean) ** 2 for t in y)
    # Sorted so the artifact round-trips identically (load_robustness_model sorts).
    metrics = tuple(
        sorted(
            (
                ("rmse", math.sqrt(ss_res / n_rows)),
                ("r2", 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0),
            )
        )
    )

    trained_through = max(frame["decided_at"].to_list())
    fields = _robustness_fields(
        target=target,
        trained_through=trained_through,
        era_cut=era_cut,
        n_rows=n_rows,
        lambda_=lambda_,
        feature_names=tuple(feature_names),
        means=tuple(means),
        stds=tuple(stds),
        target_mean=target_mean,
        coefficients=tuple(coefficients),
        train_metrics=metrics,
    )
    model_id = hashlib.sha256(_canonical(fields).encode("utf-8")).hexdigest()[:16]
    return RobustnessModel(
        schema_version=FEATURE_SCHEMA_VERSION,
        model_id=model_id,
        trained_through=trained_through,
        era_cut=era_cut,
        target=target,
        n_rows=n_rows,
        lambda_=lambda_,
        feature_names=tuple(feature_names),
        means=tuple(means),
        stds=tuple(stds),
        target_mean=target_mean,
        coefficients=tuple(coefficients),
        train_metrics=metrics,
    )


def score_robustness(model: RobustnessModel, features: Mapping[str, float]) -> float:
    """Predicted worst-quartile value for one feature dict. ``coverage_verified``
    is fixed to 1.0 when absent (the §8.2 score-time convention: predict the
    verified-quality value). Unseen ids map onto their ``__other__`` bucket."""
    index = {name: i for i, name in enumerate(model.feature_names)}
    x = [0.0] * len(model.feature_names)
    enriched = dict(features)
    enriched.setdefault(COVERAGE_FEATURE, 1.0)
    for name, value in enriched.items():
        i = index.get(name)
        if i is None:
            prefix = _collapsible_prefix(name)
            if prefix is None:
                continue
            i = index.get(_other_name(prefix))
            if i is None:
                continue
        x[i] += value
    pred = model.target_mean
    for i, (coef, mean, std) in enumerate(
        zip(model.coefficients, model.means, model.stds, strict=True)
    ):
        pred += coef * (x[i] - mean) / std
    return pred


def save_robustness_model(model: RobustnessModel, models_dir: Path) -> Path:
    """Write the canonical artifact; content-hashed name → idempotent rewrite."""
    models_dir.mkdir(parents=True, exist_ok=True)
    fields = _robustness_fields(
        target=model.target,
        trained_through=model.trained_through,
        era_cut=model.era_cut,
        n_rows=model.n_rows,
        lambda_=model.lambda_,
        feature_names=model.feature_names,
        means=model.means,
        stds=model.stds,
        target_mean=model.target_mean,
        coefficients=model.coefficients,
        train_metrics=model.train_metrics,
    )
    fields["model_id"] = model.model_id
    stamp = model.trained_through.strftime("%Y%m%dT%H%M%S")
    name = f"robustness_model_v{model.schema_version}_{stamp}Z_{model.model_id[:8]}.json"
    path = models_dir / name
    path.write_text(_canonical(fields), encoding="utf-8")
    return path


def load_robustness_model(path: Path) -> RobustnessModel:
    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = tuple(sorted((str(k), float(v)) for k, v in raw["train_metrics"].items()))
    return RobustnessModel(
        schema_version=int(raw["schema_version"]),
        model_id=str(raw["model_id"]),
        trained_through=datetime.fromisoformat(raw["trained_through"]),
        era_cut=datetime.fromisoformat(raw["era_cut"]),
        target=str(raw["target"]),
        n_rows=int(raw["n_rows"]),
        lambda_=float(raw["lambda"]),
        feature_names=tuple(raw["feature_names"]),
        means=tuple(raw["means"]),
        stds=tuple(raw["stds"]),
        target_mean=float(raw["target_mean"]),
        coefficients=tuple(raw["coefficients"]),
        train_metrics=metrics,
    )
