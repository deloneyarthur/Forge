"""In-run model training + artifact retention (Batch 5 G0).

WHY here and not a timer: the daily `forge-ranker-eval` trainer refit five models against a
9 GB snapshot every morning (20-34 GB peak) so that a 24/7 daemon could hot-load them. The
weekly run has no daemon behind it: it needs fresh artifacts once, right before it ranks, and it
already owns the only open connection to `forge.db`. So the run trains exactly the families it
LOADS (`ranking.model.load_latest_model` and `load_latest_robustness_model` for
`QUALITY_LANE_TARGET`), publishes each atomically, then prunes each family to its newest few.
The tail-lane models the daemon's extra lanes consumed are NOT trained: nothing in the campaign
loads them, and an artifact nobody reads is the cruft class this plan removes.

Degrade, never crash (the D080 stance): a fit that refuses (thin rows) or raises leaves the
previous artifact in place and lands as a note + journal line; the run continues on it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from forge.feedback.eras import CLEAN_ERA_LABEL_CUT

if TYPE_CHECKING:
    import duckdb
    import polars as pl
    from crucible_contracts import RegistrySnapshot

Echo = Callable[[str], None]
FrameBuilder = Callable[[], "pl.DataFrame"]

# The refusal floors the CLI trainer used (`cli/ranker_model_cmd.py`); kept identical so the
# weekly run trains on the same evidence bar the daily one did.
MIN_TRAIN_ROWS = 50
MIN_TRAIN_POSITIVES = 5
VERDICT_LAMBDA = 1.0
ROBUSTNESS_LAMBDA = 1.0

# Artifact families on disk: the filename up to the `_<stamp>Z_<id8>.json` suffix. The
# robustness family carries its target in the payload, not the name, so it is grouped by
# reading `target` from each file (as `load_latest_robustness_model` does).
_SUFFIX = re.compile(r"_(\d{8}T\d{6})Z_([0-9a-f]{8})\.json$")


@dataclass(frozen=True, slots=True)
class TrainOutcome:
    models: Mapping[str, str]
    """family -> model_id published this run (only the fits that succeeded)."""

    notes: tuple[str, ...]
    pruned: int


def _publish(save: Callable[[Path], Path], models_dir: Path) -> Path:
    """Save into a staging dir under `models_dir` (same filesystem), then rename into place,
    so a reader never sees a half-written artifact (the trainer script's discipline)."""
    staging = models_dir / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    tmp = save(staging)
    final = models_dir / tmp.name
    tmp.replace(final)
    return final


def train_models(
    conn: duckdb.DuckDBPyConnection,
    registry: RegistrySnapshot,
    *,
    models_dir: Path,
    keep: int,
    era_cut: datetime = CLEAN_ERA_LABEL_CUT,
    build_frame: FrameBuilder | None = None,
    echo: Echo = print,
) -> TrainOutcome:
    """Train the two families the run loads, publish atomically, prune. Never raises."""
    from forge.ranking.dataset import build_dataset  # noqa: PLC0415
    from forge.ranking.model import (  # noqa: PLC0415
        QUALITY_LANE_TARGET,
        save_model,
        save_robustness_model,
        train_robustness_model,
        train_verdict_model,
    )

    notes: list[str] = []
    models: dict[str, str] = {}
    try:
        frame = (
            build_frame()
            if build_frame is not None
            else build_dataset(conn, registry, era_cut=era_cut, honest_scope=False)
        )
    except Exception as exc:
        note = f"train: dataset build failed ({type(exc).__name__}: {exc}); previous artifacts stay"
        echo(note)
        return TrainOutcome(models={}, notes=(note,), pruned=0)

    positives = int(frame["label"].sum()) if frame.height and "label" in frame.columns else 0
    if frame.height < MIN_TRAIN_ROWS or positives < MIN_TRAIN_POSITIVES:
        notes.append(
            f"train verdict: refused (rows={frame.height} positives={positives}; "
            f"need >= {MIN_TRAIN_ROWS}/{MIN_TRAIN_POSITIVES}); previous artifact stays"
        )
    else:
        try:
            model = train_verdict_model(frame, lambda_=VERDICT_LAMBDA, era_cut=era_cut)
            path = _publish(lambda d: save_model(model, d), models_dir)
            models["verdict"] = model.model_id
            notes.append(f"train verdict: {model.model_id} rows={model.n_rows} -> {path.name}")
        except Exception as exc:
            notes.append(
                f"train verdict: failed ({type(exc).__name__}: {exc}); previous artifact stays"
            )

    target = QUALITY_LANE_TARGET
    trainable = (
        sum(1 for v in frame[target].to_list() if v is not None)
        if frame.height and target in frame.columns
        else 0
    )
    if trainable < MIN_TRAIN_ROWS:
        notes.append(
            f"train robustness[{target}]: refused ({trainable} rows carry it; need >= "
            f"{MIN_TRAIN_ROWS}); previous artifact stays"
        )
    else:
        try:
            rmodel = train_robustness_model(
                frame, target=target, lambda_=ROBUSTNESS_LAMBDA, era_cut=era_cut
            )
            rpath = _publish(lambda d: save_robustness_model(rmodel, d), models_dir)
            models[f"robustness:{target}"] = rmodel.model_id
            notes.append(
                f"train robustness[{target}]: {rmodel.model_id} rows={rmodel.n_rows} "
                f"-> {rpath.name}"
            )
        except Exception as exc:
            notes.append(
                f"train robustness[{target}]: failed ({type(exc).__name__}: {exc}); "
                "previous artifact stays"
            )

    pruned = prune_models(models_dir, keep=keep)
    if pruned:
        notes.append(f"models: pruned {pruned} older artifact(s), keeping {keep} per family")
    for note in notes:
        echo(note)
    return TrainOutcome(models=models, notes=tuple(notes), pruned=pruned)


def _family(path: Path) -> str | None:
    """`verdict_model_v1`, `tail_model_v1_<base>_n<N>`, or `robustness_model_v1:<target>`."""
    m = _SUFFIX.search(path.name)
    if m is None:
        return None
    stem = path.name[: m.start()]
    if stem.startswith("robustness_model_"):
        try:
            import json  # noqa: PLC0415

            target = json.loads(path.read_text(encoding="utf-8")).get("target")
        except (OSError, ValueError):
            return None
        return f"{stem}:{target}"
    return stem


def prune_models(models_dir: Path, *, keep: int) -> int:
    """REL-12: keep the newest `keep` artifacts per family (by filename stamp, then id), delete
    the rest. Unrecognised files are left alone. Returns the number deleted."""
    if keep < 1 or not models_dir.is_dir():
        return 0
    families: dict[str, list[Path]] = {}
    for path in models_dir.glob("*.json"):
        fam = _family(path)
        if fam is not None:
            families.setdefault(fam, []).append(path)
    deleted = 0
    for paths in families.values():
        ordered = sorted(paths, key=lambda p: p.name[_SUFFIX.search(p.name).start() :])  # type: ignore[union-attr]
        for old in ordered[:-keep]:
            old.unlink(missing_ok=True)
            deleted += 1
    return deleted


__all__ = ["MIN_TRAIN_POSITIVES", "MIN_TRAIN_ROWS", "TrainOutcome", "prune_models", "train_models"]
