#!/usr/bin/env bash
# Daily learned-model train + eval for the Forge F-track (D132 / F2-F3 / D140-D141).
#
# Automates the manual checkpoint rhythm (STATUS: "cp snapshot -> ranker-model
# train -> eval"): snapshot the live forge.db, refresh BOTH shadow-model artifacts
# (the P(component) verdict model, D134; and the tail-aware cpcv_p25 robustness
# model, D140/D141), evaluate the live shadow model, and append the F3
# consecutive-PASS streak to a JSONL log so the operator reads the clock at a glance.
#
# Deterministic Python only (hard rule #5 -- no LLM in this loop). Telemetry only:
# it NEVER touches grammar.yaml, weights, config, the ranking path, or any service.
# The trained artifact rolls the *shadow* model forward; F3 (live wiring) remains
# its own operator gate, so this cannot change what Forge submits.
#
# The streak is judged on a PER-CHECKPOINT FRESH window (verdicts decided since the
# previous run), because the F3 criterion is ">=150 *fresh* verdicts on >=3
# consecutive checkpoints". A cumulative-since-clean-era window (the manual CLI
# default) would let the streak climb on the same frozen verdicts -- the journal
# still prints that cumulative view for continuity with `forge ranker-model eval`.
#
# Safety:
#   * Live DB holds an intermittent RW lock -> cp to /tmp and read the copy
#     (docs/tasks/investigate-live.md). PID-suffixed: no clash with the eod-check.
#   * Train writes to a staging dir on the same filesystem, then atomically mv's
#     the artifact into ~/forge_data/models -- the 24/7 daemon (load_latest_model
#     every batch) never sees a half-written file.
#   * A trap removes the snapshot AND staging dir on every exit path.
#
# Created 2026-06-13 (operator: automate the daily F3 criterion clock).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

PROJ="$HOME/proj/Forge"
LIVE_DB="$HOME/forge_data/forge.db"
MODELS_DIR="$HOME/forge_data/models"
SNAP="/tmp/forge_ranker_eval_$$.db"
STAGING="$HOME/forge_data/models_staging_$$"
OUT_DIR="$HOME/forge_data/ranker_eval"
STREAK_LOG="$OUT_DIR/streak.jsonl"
MIN_FRESH=150   # F3: >=150 fresh shadow-scored verdicts for a checkpoint to count

cleanup() { rm -rf -- "$SNAP" "$STAGING"; }
trap cleanup EXIT

mkdir -p "$OUT_DIR" "$STAGING" "$MODELS_DIR"
cd "$PROJ"

# --- snapshot (DuckDB single file; cp between the daemon's ~90s write bursts,
#     the house convention for reading the live DB) -----------------------------
if ! cp -- "$LIVE_DB" "$SNAP"; then
    echo "daily-ranker-eval: FATAL could not snapshot $LIVE_DB" >&2
    exit 1
fi

# --- train -> staging, then atomic publish ------------------------------------
echo "daily-ranker-eval: train"
if uv run forge ranker-model train --forge-db "$SNAP" --models-dir "$STAGING"; then
    shopt -s nullglob
    for art in "$STAGING"/verdict_model_*.json; do
        mv -f -- "$art" "$MODELS_DIR/"   # same fs -> atomic rename
        echo "daily-ranker-eval: published $(basename "$art")"
    done
    shopt -u nullglob
else
    echo "daily-ranker-eval: train non-zero (insufficient rows or registry load) -- still evaluating" >&2
fi

# --- train-robustness -> staging, then atomic publish (tail-aware T1, D140/D141) --
#     Refreshes the cpcv_p25 robustness artifact the inert shadow hook scores with
#     (D141). Same staging+atomic-mv discipline; never read by the loop. Independent
#     of the logistic train above -- it can refuse (no cpcv rows) without affecting it.
echo "daily-ranker-eval: train-robustness"
if uv run forge ranker-model train-robustness --forge-db "$SNAP" --models-dir "$STAGING"; then
    shopt -s nullglob
    for art in "$STAGING"/robustness_model_*.json; do
        mv -f -- "$art" "$MODELS_DIR/"   # same fs -> atomic rename
        echo "daily-ranker-eval: published $(basename "$art")"
    done
    shopt -u nullglob
else
    echo "daily-ranker-eval: train-robustness non-zero (insufficient cpcv rows or registry) -- continuing" >&2
fi

# --- eval + streak (single DB pass; criterion constant imported from the CLI so
#     it cannot drift from the manual `forge ranker-model eval`) ----------------
echo "daily-ranker-eval: eval + streak"
uv run python - "$SNAP" "$STREAK_LOG" "$MIN_FRESH" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

from forge.cli.ranker_model_cmd import _AUC_MARGIN_CRITERION as CRIT
from forge.core.clock import utc_now
from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT
from forge.persistence.db import db_connection
from forge.ranking.evaluation import evaluate_shadow

snap, streak_log_path, min_fresh = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])


def verdict_of(ev):
    if ev.auc_margin is None:
        return "INSUFFICIENT"
    p_ok = (
        ev.model_precision_at_k is not None
        and ev.incumbent_precision_at_k is not None
        and ev.model_precision_at_k >= ev.incumbent_precision_at_k
    )
    return "PASS" if (ev.auc_margin >= CRIT and p_ok) else "FAIL"


def show(ev):
    if ev.auc_margin is None:
        return f"    model={ev.model_id} decided={ev.n_decided} pos={ev.n_positive} criterion=INSUFFICIENT"
    return (
        f"    model={ev.model_id} decided={ev.n_decided} pos={ev.n_positive} "
        f"auc model={ev.model_auc:.3f} incumbent={ev.incumbent_auc:.3f} "
        f"margin={ev.auc_margin:+.3f} -> {verdict_of(ev)}"
    )


# Fresh-window start = previous run's ts (F3 per-checkpoint window). First run has
# no prior -> the clean-era boundary (its fresh window is everything to date).
since_fresh = CLEAN_ERA_LABEL_CUT
if streak_log_path.exists():
    prior = [ln for ln in streak_log_path.read_text().splitlines() if ln.strip()]
    if prior:
        since_fresh = datetime.fromisoformat(json.loads(prior[-1])["ts"])

with db_connection(Path(snap)) as conn:
    cumulative = evaluate_shadow(conn, since=CLEAN_ERA_LABEL_CUT)
    fresh_evals = evaluate_shadow(conn, since=since_fresh)

print(f"  [cumulative since {CLEAN_ERA_LABEL_CUT.isoformat()} -- matches manual CLI]")
for ev in cumulative:
    print(show(ev))
print(f"  [fresh since {since_fresh.isoformat()} -- drives the streak]")
for ev in fresh_evals:
    print(show(ev))

if not fresh_evals:
    print("  no shadow-scored verdicts decided in the fresh window -- nothing to record")
    sys.exit(0)

# Dominant = most decided verdicts in the FRESH window: the model that was live
# and scoring over the last checkpoint. A model trained moments ago has 0 decided.
dominant = max(fresh_evals, key=lambda e: e.n_decided)
fresh_decided = sum(e.n_decided for e in fresh_evals)
verdict = verdict_of(dominant)
qualifies = fresh_decided >= min_fresh and verdict in ("PASS", "FAIL")

record = {
    "ts": utc_now().isoformat(),
    "window_since": since_fresh.isoformat(),
    "dominant_model": dominant.model_id,
    "fresh_decided": fresh_decided,
    "n_positive": dominant.n_positive,
    "model_auc": dominant.model_auc,
    "incumbent_auc": dominant.incumbent_auc,
    "auc_margin": dominant.auc_margin,
    "verdict": verdict,
    "qualifies": qualifies,
    "n_models_fresh": len(fresh_evals),
}
with streak_log_path.open("a") as fh:
    fh.write(json.dumps(record) + "\n")

# Streak = trailing consecutive *qualifying* PASS. A qualifying FAIL breaks it;
# non-qualifying rows (stall day / single-class window) are skipped, not counted.
streak = 0
for line in reversed([ln for ln in streak_log_path.read_text().splitlines() if ln.strip()]):
    row = json.loads(line)
    if not row.get("qualifies"):
        continue
    if row.get("verdict") == "PASS":
        streak += 1
    else:
        break

tail = "" if qualifies else f"  (NOT counted: fresh={fresh_decided}<{min_fresh} or verdict={verdict})"
print(
    f"daily-ranker-eval: dominant={dominant.model_id} verdict={verdict} "
    f"fresh_decided={fresh_decided} -> consecutive PASS streak = {streak}/3{tail}"
)
PY

echo "daily-ranker-eval: done"
