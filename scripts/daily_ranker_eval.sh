#!/usr/bin/env bash
# Daily learned-model train + eval for the Forge F-track (D132 / F2-F3 / D140-D141).
#
# Automates the manual checkpoint rhythm (STATUS: "cp snapshot -> ranker-model
# train -> eval"): snapshot the live forge.db, refresh BOTH shadow-model artifacts
# (the P(component) verdict model, D134; and the tail-aware wf_p25 robustness model,
# D191/D192 — the quality lane's), evaluate the live shadow models, and append TWO
# consecutive-PASS clocks to JSONL logs so the operator reads them at a glance: the F3
# verdict-model streak (streak.jsonl; judged on the hygiene incumbent once populated,
# D284) and the gate-then-tail re-wire streak (rewire_streak_wfp25.jsonl).
#
# The §8.6 wf_p25 tail streak (robustness_streak_wfp25.jsonl) was RETIRED 2026-07-16
# (D285): after the gate-tail flip the incumbent it paired against was the recorded
# production ranking score — the lane's own value — so its delta pinned to ≈0 by
# construction. History stays on disk; eval-robustness below remains the observational
# per-model tail readout.
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
#     (docs/tasks/investigate-live.md). PID-suffixed: no clash with other snapshots.
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
REWIRE_STREAK_LOG="$OUT_DIR/rewire_streak_wfp25.jsonl"   # gate-then-tail lane clock (live, D252)
TAIL_GATE="wf_sharpe_p25"   # realized worst-quartile metric the tail model is judged against
# §8.6 tail min-fresh: the verified-coverage+wf population is ~10-100x sparser than
# the full verdict stream, so the per-checkpoint floor is far below F3's 150. PROVISIONAL
# (operator finalizes the §8.6 margin once the pooled distribution is visible).
MIN_FRESH_TAIL=50

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

# --- train-robustness -> staging, then atomic publish (tail-aware T1, D191/D192) --
#     Refreshes the wf_p25 robustness artifact the quality lane scores with (and the
#     shadow hook shadows). Same staging+atomic-mv discipline. Independent of the
#     logistic train above -- it can refuse (no wf_p25 rows) without affecting it. wf_p25
#     is gate-emitted as a metric in gate_results from 2026-06-19 (Crucible), so the
#     continuous gate_results path (D192) trains it -- no --label dependency.
echo "daily-ranker-eval: train-robustness (wf_p25)"
if uv run forge ranker-model train-robustness --target target_wf_p25 --forge-db "$SNAP" --models-dir "$STAGING"; then
    shopt -s nullglob
    for art in "$STAGING"/robustness_model_*.json; do
        mv -f -- "$art" "$MODELS_DIR/"   # same fs -> atomic rename
        echo "daily-ranker-eval: published $(basename "$art")"
    done
    shopt -u nullglob
else
    echo "daily-ranker-eval: train-robustness non-zero (insufficient wf_p25 rows or registry) -- continuing" >&2
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
from forge.cli.ranker_model_cmd import _MAX_CE_CRITERION as CAL_CRIT
from forge.core.clock import utc_now
from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT
from forge.persistence.db import db_connection
from forge.ranking.evaluation import (
    evaluate_shadow,
    shadow_auc_verdict,
    shadow_calibration_verdict,
)

snap, streak_log_path, min_fresh = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])


def verdict_of(ev):
    # Single source of truth — the same AUC/precision verdict `forge ranker-model eval`
    # prints, so the streak cannot drift from the manual CLI. (P1.3 centralized this.)
    return shadow_auc_verdict(ev, auc_margin_criterion=CRIT)


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
    # Comparator fix: the same fresh window judged against the model-free §6.2 hygiene
    # composite (paired rows only). Under gate-tail mode the legacy incumbent
    # (composite_score) is the lane's OWN value — self-referential — so the streak
    # judges on the hygiene incumbent as soon as it carries a qualifying window;
    # empty until the post-fix daemon populates the column (needs a service restart).
    fresh_hygiene = evaluate_shadow(conn, since=since_fresh, incumbent="hygiene")

print(f"  [cumulative since {CLEAN_ERA_LABEL_CUT.isoformat()} -- matches manual CLI]")
for ev in cumulative:
    print(show(ev))
print(f"  [fresh since {since_fresh.isoformat()} -- drives the streak]")
for ev in fresh_evals:
    print(show(ev))
print("  [fresh, hygiene incumbent -- judges the streak once populated]")
for ev in fresh_hygiene:
    print(show(ev))
if not fresh_hygiene:
    print("    (no hygiene-scored rows yet -- column populates after the next restart)")

if not fresh_evals:
    print("  no shadow-scored verdicts decided in the fresh window -- nothing to record")
    sys.exit(0)

# Dominant = most decided verdicts in the FRESH window: the model that was live
# and scoring over the last checkpoint. A model trained moments ago has 0 decided.
dominant = max(fresh_evals, key=lambda e: e.n_decided)
fresh_decided = sum(e.n_decided for e in fresh_evals)
hygiene_decided = sum(e.n_decided for e in fresh_hygiene)
dominant_hygiene = max(fresh_hygiene, key=lambda e: e.n_decided) if fresh_hygiene else None
# Judge on the hygiene incumbent when its window is data-sufficient on its own terms;
# otherwise the legacy ranking-score incumbent (and say which in `margin_source`).
use_hygiene = (
    dominant_hygiene is not None
    and hygiene_decided >= min_fresh
    and verdict_of(dominant_hygiene) in ("PASS", "FAIL")
)
judged = dominant_hygiene if use_hygiene else dominant
judged_decided = hygiene_decided if use_hygiene else fresh_decided
verdict = verdict_of(judged)
qualifies = judged_decided >= min_fresh and verdict in ("PASS", "FAIL")

record = {
    "ts": utc_now().isoformat(),
    "window_since": since_fresh.isoformat(),
    "dominant_model": judged.model_id,
    "fresh_decided": judged_decided,
    "n_positive": judged.n_positive,
    "model_auc": judged.model_auc,
    "incumbent_auc": judged.incumbent_auc,
    "auc_margin": judged.auc_margin,
    "verdict": verdict,
    "qualifies": qualifies,
    "n_models_fresh": len(fresh_evals),
    # Comparator provenance: which incumbent judged this row, plus both margins for
    # continuity (the legacy view keeps the pre-fix series comparable).
    "margin_source": "hygiene" if use_hygiene else "ranking",
    "ranking_auc_margin": dominant.auc_margin,
    "hygiene_auc_margin": dominant_hygiene.auc_margin if dominant_hygiene else None,
    "hygiene_fresh_decided": hygiene_decided,
    # P1.3 calibration telemetry (tracks drift across checkpoints; gates no live behavior).
    "model_ece": judged.model_ece,
    "model_max_ce": judged.model_max_ce,
    "model_ece_platt": judged.model_ece_platt,
    "calibration_verdict": shadow_calibration_verdict(judged, max_ce_criterion=CAL_CRIT),
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

tail = "" if qualifies else f"  (NOT counted: fresh={judged_decided}<{min_fresh} or verdict={verdict})"
print(
    f"daily-ranker-eval: dominant={judged.model_id} verdict={verdict} "
    f"incumbent={record['margin_source']} "
    f"fresh_decided={judged_decided} -> consecutive PASS streak = {streak}/3{tail}"
)
# P1.3 calibration readout (the floor-relevant co-primary; telemetry only).
mce = "n/a" if judged.model_max_ce is None else f"{judged.model_max_ce:.3f}"
plt = "n/a" if judged.model_ece_platt is None else f"{judged.model_ece_platt:.3f}"
print(
    f"daily-ranker-eval: calibration ece={judged.model_ece:.4f} max_ce={mce} "
    f"ece_platt={plt} verdict={record['calibration_verdict']} (max_ce<={CAL_CRIT})"
)
PY

# --- tail-aware (T1) readout (D143) -------------------------------------------
#     Observation only: prints Spearman(tail_score, realized wf_p25) + top-K mean
#     realized wf_p25 (tail model vs incumbent) so the §8.6 criterion margin can be set
#     once the distribution is visible.
echo "daily-ranker-eval: eval-robustness (tail T1, wf_p25)"
uv run forge ranker-model eval-robustness --forge-db "$SNAP" --gate "$TAIL_GATE" || \
    echo "daily-ranker-eval: eval-robustness non-zero -- continuing" >&2

# --- gate-then-tail re-wire streak (quality-lane re-wire, shadow-first) --------
#     The shadow clock for the gate-then-tail re-wire candidate
#     (docs/proposals/quality-lane-rewire.md): does a P(component) eligibility gate +
#     tail-ordered survivors beat ranking by P(component) alone (≈ the deployed lane) on
#     realized wf_p25? Judged on the same FRESH per-checkpoint window as the streaks above;
#     PASS when the Δ clears the PROVISIONAL _REWIRE_DELTA_CRITERION. Telemetry only -- the
#     lane flip is its own operator gate (D104); raw Δ recorded for re-judging.
echo "daily-ranker-eval: re-wire streak (gate-then-tail, wf_p25)"
uv run python - "$SNAP" "$REWIRE_STREAK_LOG" "$MIN_FRESH_TAIL" "$TAIL_GATE" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

import os

from forge.cli.ranker_model_cmd import _REWIRE_DELTA_CRITERION as CRIT
from forge.core.clock import utc_now
from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT
from forge.persistence.db import db_connection
from forge.ranking.evaluation import evaluate_rewire_shadow

snap, streak_log_path, min_fresh, gate = (
    sys.argv[1],
    Path(sys.argv[2]),
    int(sys.argv[3]),
    sys.argv[4],
)


def verdict_of(ev):
    if ev is None or ev.delta is None:
        return "INSUFFICIENT"
    return "PASS" if ev.delta >= CRIT else "FAIL"


def show(ev, label):
    if ev is None:
        print(f"    {label}: no verified-coverage {gate}-bearing tail verdicts in window")
        return
    d = "n/a" if ev.delta is None else f"{ev.delta:+.3f}"
    g = "n/a" if ev.gate_top_k_mean is None else f"{ev.gate_top_k_mean:.3f}"
    b = "n/a" if ev.base_top_k_mean is None else f"{ev.base_top_k_mean:.3f}"
    print(
        f"    {label}: n={ev.n_decided} top{ev.k} {gate} gate-tail={g} vs P-base={b} "
        f"delta={d} -> {verdict_of(ev)}"
    )


# Fresh-window start = previous run's ts (per-checkpoint window). First run -> clean era.
since_fresh = CLEAN_ERA_LABEL_CUT
if streak_log_path.exists():
    prior = [ln for ln in streak_log_path.read_text().splitlines() if ln.strip()]
    if prior:
        since_fresh = datetime.fromisoformat(json.loads(prior[-1])["ts"])

# Absolute P floor -- the calibrated production gate (FORGE_REWIRE_P_FLOOR, default 0.02);
# the shadow gates on the SAME floor so the streak tracks the gate the live scorer runs.
p_floor = float(os.environ.get("FORGE_REWIRE_P_FLOOR", "0.02"))
with db_connection(Path(snap)) as conn:
    cumulative = evaluate_rewire_shadow(conn, since=CLEAN_ERA_LABEL_CUT, gate=gate, p_floor=p_floor)
    fresh = evaluate_rewire_shadow(conn, since=since_fresh, gate=gate, p_floor=p_floor)

print(f"  [cumulative since {CLEAN_ERA_LABEL_CUT.isoformat()}]")
show(cumulative, "cumulative")
print(f"  [fresh since {since_fresh.isoformat()} -- drives the streak]")
show(fresh, "fresh")

if fresh is None:
    print("  no re-wire verdicts in the fresh window -- nothing to record")
    sys.exit(0)

verdict = verdict_of(fresh)
# P1.2: the first-ever run has no prior record, so its window is the whole clean-era pool
# (a contaminated "look", not a fresh per-checkpoint window). NEVER let it count toward the
# streak/flip gate — only genuinely fresh windows (a prior record exists) qualify.
is_first_look = since_fresh == CLEAN_ERA_LABEL_CUT
qualifies = (not is_first_look) and fresh.n_decided >= min_fresh and fresh.delta is not None

record = {
    "ts": utc_now().isoformat(),
    "window_since": since_fresh.isoformat(),
    "gate": gate,
    "fresh_decided": fresh.n_decided,
    "k": fresh.k,
    "p_floor": fresh.p_floor,
    "keep_frac": fresh.keep_frac,
    "gate_top_k_mean": fresh.gate_top_k_mean,
    "base_top_k_mean": fresh.base_top_k_mean,
    "delta": fresh.delta,
    "eligible_fraction": fresh.eligible_fraction,  # P1.3: floor keep-rate (watch for drift)
    "criterion": CRIT,
    "verdict": verdict,
    "qualifies": qualifies,
    "is_first_look": is_first_look,  # P1.2: full-pool window, excluded from the flip gate
}
with streak_log_path.open("a") as fh:
    fh.write(json.dumps(record) + "\n")

# Streak = trailing consecutive *qualifying* PASS (mirrors the streaks above).
streak = 0
for line in reversed([ln for ln in streak_log_path.read_text().splitlines() if ln.strip()]):
    row = json.loads(line)
    if not row.get("qualifies"):
        continue
    if row.get("verdict") == "PASS":
        streak += 1
    else:
        break

d_str = "n/a" if fresh.delta is None else f"{fresh.delta:+.3f}"
note = "" if qualifies else f"  (NOT counted: fresh={fresh.n_decided}<{min_fresh})"
print(
    f"daily-ranker-eval: re-wire n={fresh.n_decided} delta={d_str} "
    f"verdict={verdict} -> consecutive PASS streak = {streak}/3{note}"
)
PY

# --- campaign region-carriage audit (D302, Theme 5c) ---------------------------
# One JSONL row per day: per-campaign ranked-vs-holdout carriage over the last 7d
# (forge.ranking.campaign_audit — the D287 selection-starvation detector). The
# healthcheck's `campaign carriage` check WARNs on a starved campaign or a stale
# file. Read-only on the snapshot; non-fatal so the streak sections above are
# never blocked by it.
echo "daily-ranker-eval: campaign carriage audit"
uv run python - "$SNAP" "$OUT_DIR/campaign_audit.jsonl" <<'PY' || echo "daily-ranker-eval: campaign audit failed -- continuing" >&2
import json
import sys
from pathlib import Path

from forge.core.clock import utc_now
from forge.persistence.db import db_connection
from forge.ranking.campaign_audit import audit_carriage

snap, out = sys.argv[1], Path(sys.argv[2])
with db_connection(snap) as conn:
    results, unauditable = audit_carriage(conn, now=utc_now())

row = {
    "ts": utc_now().isoformat(),
    "starved": [r.name for r in results if r.starved],
    "unauditable": unauditable,
    "results": [
        {
            "name": r.name,
            "ranked_members": r.ranked_members,
            "holdout_members": r.holdout_members,
            "ranked_total": r.ranked_total,
            "holdout_total": r.holdout_total,
            "carriage_ratio": r.carriage_ratio,
            "starved": r.starved,
            "decisions": dict(r.decisions),
        }
        for r in results
    ],
}
with out.open("a") as fh:
    fh.write(json.dumps(row) + "\n")
for r in results:
    ratio = "n/a" if r.carriage_ratio is None else f"{r.carriage_ratio:.3f}"
    print(f"daily-ranker-eval: campaign {r.name} ratio={ratio} starved={r.starved}")
PY

echo "daily-ranker-eval: done"
