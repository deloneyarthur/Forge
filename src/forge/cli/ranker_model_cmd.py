"""`forge ranker-model` — learned verdict model commands (D132).

F1: `dataset` (the honest-era training frame). F2: `train` (manual, at the
daily checkpoints — auto-train deliberately not chosen, D132 decision 1) and
`eval` (shadow vs incumbent on decided verdicts; feeds the F3 criterion:
model AUC ≥ incumbent + 0.05 AND precision@K ≥ incumbent's, on ≥3 consecutive
checkpoints of ≥150 fresh verdicts). The model never touches production
ranking before F3 — its own operator gate.

The live `~/forge_data/forge.db` holds an intermittent RW lock — point
`--forge-db` at a `/tmp` snapshot of it (`docs/tasks/investigate-live.md`).
`--models-dir` defaults from the CONFIG's db_path (where the daemon reads
artifacts), NOT from `--forge-db` — the snapshot's parent is /tmp.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

ranker_model_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Learned verdict model (D132): dataset / train / eval.",
)

# Operational floor for a meaningful fit (the library itself trains any
# two-class frame; these guard the production artifact path).
_MIN_TRAIN_ROWS = 50
_MIN_TRAIN_POSITIVES = 5

_AUC_MARGIN_CRITERION = 0.05


def _resolve_forge_db(forge_db: Path | None, config: Path) -> Path:
    if forge_db is not None:
        return forge_db
    if not config.exists():
        typer.echo(f"error: config {config} not found — pass --forge-db explicitly", err=True)
        raise typer.Exit(code=2)
    from forge.config import load_forge_config

    return load_forge_config(config).db_path


def _resolve_era_cut(era_cut: str | None) -> datetime:
    from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT

    if era_cut is None:
        return CLEAN_ERA_LABEL_CUT
    cut = datetime.fromisoformat(era_cut)
    return cut.replace(tzinfo=UTC) if cut.tzinfo is None else cut


@ranker_model_app.command("dataset")
def cmd_dataset(
    out: Path = typer.Option(..., "--out", help="output parquet path"),
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies db_path default)"
    ),
    exports_dir: Path | None = typer.Option(
        None, "--exports-dir", help="Crucible exports dir override (registry snapshot)"
    ),
    era_cut: str | None = typer.Option(
        None,
        "--era-cut",
        help="ISO label-era cutoff override (default: CLEAN_ERA_LABEL_CUT, 2026-06-10T17:17:13Z)",
    ),
) -> None:
    """Build the honest-era training frame (verdicts ⋈ submissions) as parquet."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.ranking.dataset import build_dataset

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(era_cut)
    registry = load_registry(exports_dir=exports_dir) if exports_dir else load_registry()

    with db_connection(forge_db) as conn:
        frame = build_dataset(conn, registry, era_cut=cut)

    out.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(out)
    positives = int(frame["label"].sum()) if frame.height else 0
    typer.echo(
        f"dataset: {frame.height} rows ({positives} positive), "
        f"{max(frame.width - 5, 0)} feature columns, era_cut={cut.isoformat()} -> {out}"
    )


@ranker_model_app.command("train")
def cmd_train(
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (db_path + models dir defaults)"
    ),
    exports_dir: Path | None = typer.Option(
        None, "--exports-dir", help="Crucible exports dir override (registry snapshot)"
    ),
    era_cut: str | None = typer.Option(
        None, "--era-cut", help="ISO label-era cutoff override (naive = UTC)"
    ),
    lambda_: float = typer.Option(1.0, "--lambda", help="L2 regularization strength"),
    models_dir: Path | None = typer.Option(
        None,
        "--models-dir",
        help="artifact dir (default: <config db_path parent>/models — where the daemon reads)",
    ),
) -> None:
    """Train the verdict model on the honest era and save the artifact (F2, manual)."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.ranking.dataset import build_dataset
    from forge.ranking.model import save_model, train_verdict_model

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(era_cut)
    if models_dir is None:
        if not config.exists():
            typer.echo(f"error: config {config} not found — pass --models-dir explicitly", err=True)
            raise typer.Exit(code=2)
        from forge.config import load_forge_config

        models_dir = load_forge_config(config).db_path.parent / "models"
    registry = load_registry(exports_dir=exports_dir) if exports_dir else load_registry()

    with db_connection(forge_db) as conn:
        frame = build_dataset(conn, registry, era_cut=cut)

    positives = int(frame["label"].sum()) if frame.height else 0
    if frame.height < _MIN_TRAIN_ROWS or positives < _MIN_TRAIN_POSITIVES:
        typer.echo(
            f"refusing to train: rows={frame.height} positives={positives} "
            f"(need >= {_MIN_TRAIN_ROWS} rows / {_MIN_TRAIN_POSITIVES} positives)",
            err=True,
        )
        raise typer.Exit(code=1)

    model = train_verdict_model(frame, lambda_=lambda_, era_cut=cut)
    path = save_model(model, models_dir)
    metrics = dict(model.train_metrics)
    typer.echo(
        f"trained: model_id={model.model_id} rows={model.n_rows} "
        f"({model.n_positive} positive), features={len(model.feature_names)}, "
        f"train_auc={metrics['auc']:.3f} brier={metrics['brier']:.4f} -> {path}"
    )
    top = sorted(
        zip(model.feature_names, model.coefficients, strict=True),
        key=lambda pair: -abs(pair[1]),
    )[:8]
    typer.echo("top coefficients: " + ", ".join(f"{n}={c:+.3f}" for n, c in top))


@ranker_model_app.command("eval")
def cmd_eval(
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies db_path default)"
    ),
    since: str | None = typer.Option(
        None, "--since", help="ISO window start (default: the clean-era boundary)"
    ),
) -> None:
    """Shadow vs incumbent on decided verdicts — the F3 criterion readout."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.ranking.evaluation import evaluate_shadow

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(since)

    with db_connection(forge_db) as conn:
        evaluations = evaluate_shadow(conn, since=cut)

    if not evaluations:
        typer.echo(f"no shadow-scored verdicts decided since {cut.isoformat()}")
        return
    for ev in evaluations:
        typer.echo(f"model={ev.model_id} decided={ev.n_decided} positives={ev.n_positive}")
        if ev.auc_margin is None:
            typer.echo("  auc: insufficient (single-class window) — criterion=INSUFFICIENT")
        else:
            verdict = (
                "PASS"
                if (
                    ev.auc_margin >= _AUC_MARGIN_CRITERION
                    and ev.model_precision_at_k is not None
                    and ev.incumbent_precision_at_k is not None
                    and ev.model_precision_at_k >= ev.incumbent_precision_at_k
                )
                else "FAIL"
            )
            typer.echo(
                f"  auc: model={ev.model_auc:.3f} incumbent={ev.incumbent_auc:.3f} "
                f"auc_margin={ev.auc_margin:+.3f} "
                f"criterion(+{_AUC_MARGIN_CRITERION:.2f})={verdict}"
            )
        if ev.model_precision_at_k is not None and ev.incumbent_precision_at_k is not None:
            typer.echo(
                f"  precision@{ev.n_positive}: model={ev.model_precision_at_k:.3f} "
                f"incumbent={ev.incumbent_precision_at_k:.3f}"
            )
        typer.echo(f"  brier(model)={ev.model_brier:.4f}")
        cal = " | ".join(
            f"[{lo:.1f}) n={n} mean={mean:.3f} rate={rate:.3f}"
            for lo, n, mean, rate in ev.calibration
        )
        typer.echo(f"  calibration: {cal}")
