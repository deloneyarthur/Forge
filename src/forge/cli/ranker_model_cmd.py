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

# P1.3 calibration criterion (co-primary with AUC, but for the OTHER consumption). The
# AUC verdict blesses the model for the blend (RANKING); this one blesses P for the
# absolute gate-then-tail floor (CALIBRATION). A checkpoint PASSes when its max calibration
# error over adequately-populated bins is <= this bar. 0.20 is PROVISIONAL — the live
# dominant model's high-P bins run ~0.15-0.36 off (learned-audit §1), so this starts as an
# honest FAIL until the P is recalibrated (the recalibrator lands with P1.1's floor
# re-derivation). Telemetry only: reported + JSONL-tracked; it gates no live behavior and
# is kept separate from the AUC streak so a well-ranking-but-miscalibrated model isn't
# wrongly failed for ranking.
_MAX_CE_CRITERION = 0.20

# §8.6 tail (T1) streak criterion — PROVISIONAL, pending operator finalization of the
# margin once the pooled distribution is visible (D147). A checkpoint PASSes when the
# pooled Spearman(tail_score, realized cpcv_p25) clears this; the streak counts
# consecutive qualifying PASSes. 0.30 is a deliberately modest bar (both live models
# sit ~+0.41/+0.45); the raw Spearman is recorded per row so the operator can re-judge
# at any threshold without a re-run. The per-checkpoint min-n is the daily script's
# MIN_FRESH_TAIL (well below F3's 150 — the verified-coverage+cpcv population is far
# sparser than the full verdict stream).
_TAIL_SPEARMAN_CRITERION = 0.30

# Gate-then-tail re-wire streak criterion — PROVISIONAL (docs/proposals/quality-lane-rewire.md).
# A checkpoint PASSes when the fresh-window delta (gate-then-tail top-K minus the P(component)-
# baseline top-K, on realized wf_sharpe_p25) clears this margin; the streak counts consecutive
# qualifying PASSes. The A/B's recent-window delta was ~+0.16 (full-pool -0.07 — the win is
# recency-dependent on the improving tail models); +0.05 is a modest "meaningfully beats the
# deployed lane" bar. Raw delta is recorded per row so the operator can re-judge without a re-run.
_REWIRE_DELTA_CRITERION = 0.05


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


def _resolve_models_dir(models_dir: Path | None, config: Path) -> Path:
    """Artifact dir: explicit, else the CONFIG db_path's parent ``/models`` (where
    the daemon reads) — never derived from ``--forge-db``, which is a /tmp snapshot."""
    if models_dir is not None:
        return models_dir
    if not config.exists():
        typer.echo(f"error: config {config} not found — pass --models-dir explicitly", err=True)
        raise typer.Exit(code=2)
    from forge.config import load_forge_config

    return load_forge_config(config).db_path.parent / "models"


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
    models_dir = _resolve_models_dir(models_dir, config)
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
    from forge.ranking.evaluation import (
        evaluate_shadow,
        shadow_auc_verdict,
        shadow_calibration_verdict,
    )

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
            typer.echo(
                f"  auc: model={ev.model_auc:.3f} incumbent={ev.incumbent_auc:.3f} "
                f"auc_margin={ev.auc_margin:+.3f} "
                f"criterion(+{_AUC_MARGIN_CRITERION:.2f})="
                f"{shadow_auc_verdict(ev, auc_margin_criterion=_AUC_MARGIN_CRITERION)}"
            )
        if ev.model_precision_at_k is not None and ev.incumbent_precision_at_k is not None:
            typer.echo(
                f"  precision@{ev.n_positive}: model={ev.model_precision_at_k:.3f} "
                f"incumbent={ev.incumbent_precision_at_k:.3f}"
            )
        typer.echo(f"  brier(model)={ev.model_brier:.4f}")
        # P1.3: calibration diagnostics + the co-primary floor criterion (telemetry only).
        max_ce = "n/a" if ev.model_max_ce is None else f"{ev.model_max_ce:.3f}"
        platt = "n/a" if ev.model_ece_platt is None else f"{ev.model_ece_platt:.3f}"
        cal_verdict = shadow_calibration_verdict(ev, max_ce_criterion=_MAX_CE_CRITERION)
        typer.echo(
            f"  calibration: ece={ev.model_ece:.4f} max_ce={max_ce} ece_platt={platt} "
            f"criterion(max_ce<={_MAX_CE_CRITERION:.2f})={cal_verdict}"
        )
        cal = " | ".join(
            f"[{lo:.1f}) n={n} mean={mean:.3f} rate={rate:.3f}"
            for lo, n, mean, rate in ev.calibration
        )
        typer.echo(f"  reliability: {cal}")


@ranker_model_app.command("eval-robustness")
def cmd_eval_robustness(
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies db_path default)"
    ),
    since: str | None = typer.Option(
        None, "--since", help="ISO window start (default: the clean-era boundary)"
    ),
    gate: str = typer.Option(
        "cpcv_sharpe_p25",
        "--gate",
        help="realized worst-quartile gate to correlate against (e.g. wf_sharpe_p25)",
    ),
) -> None:
    """Tail-aware (T1) shadow readout (D141 data): does ranking by the predicted tail value
    (tail_score) surface configs with higher REALIZED worst-quartile robustness? Prints
    Spearman(tail_score, realized `--gate` value) + top-K mean realized value (tail model vs
    the incumbent composite) per tail_model_id, over verified-coverage decided verdicts. The
    §8.6 criterion margin is set once the shadow distribution is visible, so this prints the
    metrics with no PASS/FAIL yet. Design: docs/proposals/tail-aware-ranker.md."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.ranking.evaluation import evaluate_tail_shadow

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(since)

    with db_connection(forge_db) as conn:
        evaluations = evaluate_tail_shadow(conn, since=cut, gate=gate)

    if not evaluations:
        typer.echo(
            f"no tail-scored verdicts decided since {cut.isoformat()} "
            "(tail shadow not yet accruing — needs the D141 code live + a robustness model)"
        )
        return
    for ev in evaluations:
        sp = f"{ev.spearman:+.3f}" if ev.spearman is not None else "n/a"
        typer.echo(
            f"tail_model={ev.tail_model_id} decided={ev.n_decided} "
            f"spearman(pred,realized {gate})={sp}"
        )
        mk = "n/a" if ev.model_top_k_mean_cpcv is None else f"{ev.model_top_k_mean_cpcv:.3f}"
        ik = (
            "n/a" if ev.incumbent_top_k_mean_cpcv is None else f"{ev.incumbent_top_k_mean_cpcv:.3f}"
        )
        ok = "n/a" if ev.overall_mean_cpcv is None else f"{ev.overall_mean_cpcv:.3f}"
        typer.echo(
            f"  top-{ev.k} mean realized {gate}: tail-model={mk} vs incumbent={ik} (overall={ok})"
        )
    typer.echo(
        "  criterion: §8.6 margin not yet set (fixed once the shadow distribution is visible)"
    )


@ranker_model_app.command("eval-rewire")
def cmd_eval_rewire(
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies db_path default)"
    ),
    since: str | None = typer.Option(
        None, "--since", help="ISO window start (default: the clean-era boundary)"
    ),
    gate: str = typer.Option(
        "wf_sharpe_p25", "--gate", help="realized worst-quartile gate to score against"
    ),
    p_floor: float = typer.Option(
        0.02,
        "--p-floor",
        help="absolute P(component) eligibility floor (production-calibrated default 0.02)",
    ),
) -> None:
    """Gate-then-tail re-wire shadow: does an eligibility gate on P(component) + ordering the
    survivors by the predicted WF floor surface configs with a higher REALIZED `--gate` than
    ranking by P(component) alone (the deployed lane ≈ this baseline)? Prints the gate-then-tail
    vs P-baseline top-K mean realized value over verified-coverage decided verdicts. Telemetry
    only — no PASS/FAIL until the §8.6-style margin is set. Design:
    docs/proposals/quality-lane-rewire.md."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.ranking.evaluation import evaluate_rewire_shadow

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(since)

    with db_connection(forge_db) as conn:
        ev = evaluate_rewire_shadow(conn, since=cut, gate=gate, p_floor=p_floor)

    if ev is None:
        typer.echo(
            f"no tail-scored verdicts decided since {cut.isoformat()} "
            "(re-wire shadow not yet accruing — needs a target_wf_p25 robustness model live)"
        )
        return
    g = "n/a" if ev.gate_top_k_mean is None else f"{ev.gate_top_k_mean:+.3f}"
    b = "n/a" if ev.base_top_k_mean is None else f"{ev.base_top_k_mean:+.3f}"
    d = "n/a" if ev.delta is None else f"{ev.delta:+.3f}"
    o = "n/a" if ev.overall_mean is None else f"{ev.overall_mean:+.3f}"
    typer.echo(f"gate-then-tail re-wire shadow (gate={gate} p_floor={ev.p_floor:.4f}):")
    typer.echo(
        f"  n_decided={ev.n_decided} top-{ev.k} mean realized {gate}: "
        f"gate-then-tail={g} vs P-baseline={b} (Δ={d}, overall={o})"
    )


@ranker_model_app.command("eval-prior-weight")
def cmd_eval_prior_weight(
    forge_db: Path | None = typer.Option(
        None, "--forge-db", help="forge.db path (use a /tmp snapshot of the live DB)"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies db_path default)"
    ),
    since: str | None = typer.Option(
        None, "--since", help="ISO window start (default: the clean-era boundary)"
    ),
    weights: str = typer.Option(
        "0.10,0.30,0.50,0.70,1.0",
        "--weights",
        help="comma-separated prior weights to A/B (0.10 = the live composite slot)",
    ),
) -> None:
    """Prior-weight A/B (B2): how much realized promotion-ranking does the §6.2 composite's
    0.10 prior (P(component)) slot leave on the table? Re-scores the submitted shadow rows
    under each `--weights` value (holding the four hygiene terms' relative proportions) and
    prints the top-K realized component yield (precision@K, AUC) per weight. Rising with
    weight ⇒ the hygiene terms dilute a promotion-relevant prior. Offline + censored (only
    submitted configs carry verdicts) — a first-pass signal; confirm the winner on a live
    shadow lane before any `ranker.yaml` change. fable-audit learned-systems P1.4/B2."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.ranking.evaluation import evaluate_prior_weight_ab

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(since)
    try:
        parsed = [float(w) for w in weights.split(",") if w.strip()]
    except ValueError:
        typer.echo(f"invalid --weights {weights!r}: expected comma-separated floats", err=True)
        raise typer.Exit(code=2) from None

    with db_connection(forge_db) as conn:
        evals = evaluate_prior_weight_ab(conn, since=cut, weights=parsed)

    if not evals:
        typer.echo(
            f"no decided verdicts since {cut.isoformat()} (prior-weight A/B has nothing to score)"
        )
        return
    typer.echo(
        f"prior-weight A/B (n_decided={evals[0].n_decided}, "
        f"n_components={evals[0].n_positive}, K={evals[0].k}):"
    )
    for ev in evals:
        pk = "n/a" if ev.precision_at_k is None else f"{ev.precision_at_k:.3f}"
        au = "n/a" if ev.auc is None else f"{ev.auc:.3f}"
        live = "  (live)" if ev.weight == 0.10 else ""
        typer.echo(f"  weight={ev.weight:.2f}  precision@K={pk}  AUC={au}{live}")
    typer.echo(
        "  higher precision@K/AUC at higher weight => the 0.10 slot under-weights the prior; "
        "the diversifier (D103/D136 floors) preserves variety independently."
    )


@ranker_model_app.command("train-robustness")
def cmd_train_robustness(
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
    target: str = typer.Option(
        "target_cpcv_p25", "--target", help="continuous gate value to predict (T1)"
    ),
    label: Path | None = typer.Option(
        None, "--label", help="per-component label JSON sourcing the target column"
    ),
    label_col: str = typer.Option(
        "wf_sharpe_p25", "--label-col", help="label column to use as the target (requires --label)"
    ),
    models_dir: Path | None = typer.Option(
        None, "--models-dir", help="artifact dir (default: <config db_path parent>/models)"
    ),
) -> None:
    """Train the tail-aware robustness model (T1): a ridge fit predicting a continuous
    worst-quartile gate value (default cpcv_sharpe_p25). Manual, at the daily
    checkpoints like `train`; the model never touches ranking before its own gate.
    Design: docs/proposals/tail-aware-ranker.md."""
    from forge.core.contracts_check import check_contracts_version

    check_contracts_version()

    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.ranking.dataset import build_dataset
    from forge.ranking.model import save_robustness_model, train_robustness_model

    forge_db = _resolve_forge_db(forge_db, config)
    cut = _resolve_era_cut(era_cut)
    models_dir = _resolve_models_dir(models_dir, config)
    registry = load_registry(exports_dir=exports_dir) if exports_dir else load_registry()

    with db_connection(forge_db) as conn:
        if label is not None:
            import json
            from datetime import UTC, datetime

            from forge.ranking.dataset import build_label_frame

            raw = json.loads(label.read_text())
            recs = (
                raw["components"]
                if isinstance(raw, dict) and "components" in raw
                else raw
                if isinstance(raw, list)
                else next((v for v in raw.values() if isinstance(v, list)), [])
            )
            label_map = {
                str(r["config_hash"]): float(r[label_col])
                for r in recs
                if isinstance(r, dict) and r.get(label_col) is not None
            }
            gen = raw.get("generated_at") if isinstance(raw, dict) else None
            stamp = datetime.fromisoformat(gen) if gen else cut
            if stamp.tzinfo is not None:
                stamp = stamp.astimezone(UTC).replace(tzinfo=None)
            frame = build_label_frame(
                conn, registry, label=label_map, target_name=target, stamp=stamp
            )
            typer.echo(f"label-sourced frame: {len(label_map)} components [{label_col}]")
        else:
            frame = build_dataset(conn, registry, era_cut=cut)

    if target not in frame.columns:
        typer.echo(f"error: target column {target!r} not in dataset", err=True)
        raise typer.Exit(code=2)
    trainable = sum(1 for v in frame[target].to_list() if v is not None) if frame.height else 0
    if trainable < _MIN_TRAIN_ROWS:
        typer.echo(
            f"refusing to train: {trainable} rows carry {target} (need >= {_MIN_TRAIN_ROWS})",
            err=True,
        )
        raise typer.Exit(code=1)

    model = train_robustness_model(frame, target=target, lambda_=lambda_, era_cut=cut)
    path = save_robustness_model(model, models_dir)
    metrics = dict(model.train_metrics)
    typer.echo(
        f"trained robustness[{target}]: model_id={model.model_id} rows={model.n_rows}, "
        f"features={len(model.feature_names)}, train_r2={metrics['r2']:.3f} "
        f"rmse={metrics['rmse']:.4f} -> {path}"
    )
    top = sorted(
        zip(model.feature_names, model.coefficients, strict=True),
        key=lambda pair: -abs(pair[1]),
    )[:8]
    typer.echo("top coefficients: " + ", ".join(f"{n}={c:+.3f}" for n, c in top))
