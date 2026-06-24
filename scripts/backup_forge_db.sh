#!/usr/bin/env bash
# Nightly disaster-recovery backup of the live Forge state.
#
# WHY: ~/forge_data/forge.db (DuckDB, ~4.5 GB) is the sole copy of every submission,
# verdict, grammar version/proposal, promoted pattern, and shadow score -- months of
# state the feedback loop cannot reconstruct. ~/forge_data/models holds the daily
# learned verdict + wf_p25 robustness artifacts. Neither is under git; a disk, fs, or
# operator fault would lose them permanently. This makes a verified, versioned copy.
#
# METHOD: the live DB holds an intermittent RW lock, so a read-only open can fail
# (docs/tasks/investigate-live.md). The house convention is to `cp` the single DuckDB
# file between the daemon's write bursts (scripts/daily_ranker_eval.sh does the same).
# We cp, then VALIDATE the copy by opening it read-only and querying a core table; a
# torn mid-write copy fails validation and we retry. Only a validated copy is published
# (atomic rename on the same filesystem), and retention prunes ONLY after a new good
# backup exists -- so a failed run never deletes the last good backup.
#
# DR SCOPE: FORGE_BACKUP_DEST defaults to a same-disk path, which protects against the
# common faults (accidental deletion, bad migration, fs/logical corruption) but NOT a
# physical disk failure -- this box has a single NVMe. For true off-box DR, point
# FORGE_BACKUP_DEST at a mounted external/remote target; nothing else changes.
#
# Deterministic-loop rules (#6/#8) do not apply: this is ops glue, not src/ -- it reads
# the DB and the wall clock exactly as daily_ranker_eval.sh already does, touches no
# grammar/weights/config/service, and cannot change what Forge submits. Reverting =
# disable the timer; the backups dir is inert data.
#
# Created 2026-06-23 (operator: ops-hardening sprint -- backup/DR, the Tier-1 blocker).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

LIVE_DB="${FORGE_BACKUP_LIVE_DB:-$HOME/forge_data/forge.db}"
MODELS_DIR="${FORGE_BACKUP_MODELS_DIR:-$HOME/forge_data/models}"
DEST="${FORGE_BACKUP_DEST:-$HOME/forge_data/backups}"
KEEP="${FORGE_BACKUP_KEEP:-14}"                       # most-recent backups to retain
PYTHON="${FORGE_BACKUP_PYTHON:-$HOME/proj/Forge/.venv/bin/python}"
MIN_FREE_MB="${FORGE_BACKUP_MIN_FREE_MB:-8192}"       # refuse if dest free < ~1 DB + headroom
MAX_CP_ATTEMPTS=3

log()  { echo "forge-backup: $*"; }
warn() { echo "forge-backup: $*" >&2; }
fail() { echo "forge-backup: FATAL $*" >&2; exit 1; }

[ -f "$LIVE_DB" ] || fail "live DB not found: $LIVE_DB"
[ -x "$PYTHON" ] || fail "validation python not found/executable: $PYTHON"
mkdir -p -- "$DEST" || fail "cannot create dest: $DEST"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$DEST/.forge_db_inprogress_$$.duckdb"
cleanup() { rm -f -- "$TMP"; }
trap cleanup EXIT

# --- disk-space guard (never fill the disk; retention keeps it bounded) --------
free_mb="$(df -Pm -- "$DEST" | awk 'NR==2 {print $4}')"
if [ -n "$free_mb" ] && [ "$free_mb" -lt "$MIN_FREE_MB" ]; then
    fail "only ${free_mb}MB free at $DEST (< ${MIN_FREE_MB}MB) -- refusing to risk filling the disk"
fi

# --- validate: open the copy read-only and query a core table (catches a torn cp) ---
validate_db() {
    "$PYTHON" - "$1" <<'PY'
import sys

import duckdb

con = duckdb.connect(sys.argv[1], read_only=True)
try:
    n = con.execute("select count(*) from submissions").fetchone()[0]
finally:
    con.close()
if n is None or n < 0:
    raise SystemExit("submissions count invalid")
print(n)
PY
}

# --- snapshot the live DB (cp between write bursts) + validate, with retry -----
published=""
for attempt in $(seq 1 "$MAX_CP_ATTEMPTS"); do
    log "snapshot attempt ${attempt}/${MAX_CP_ATTEMPTS}: cp $LIVE_DB"
    if ! cp -- "$LIVE_DB" "$TMP"; then
        warn "cp failed (attempt ${attempt})"
        rm -f -- "$TMP"
        continue
    fi
    if rows="$(validate_db "$TMP" 2>/dev/null)"; then
        FINAL="$DEST/forge_db_${TS}.duckdb"
        mv -f -- "$TMP" "$FINAL" || fail "atomic publish failed: $FINAL"
        log "published $(basename "$FINAL") (submissions rows=${rows}, $(du -h "$FINAL" | cut -f1))"
        published="$FINAL"
        break
    fi
    warn "validation failed (attempt ${attempt}) -- likely a torn mid-write copy; retrying"
    rm -f -- "$TMP"
done
[ -n "$published" ] || fail "no validated DB backup after ${MAX_CP_ATTEMPTS} attempts -- existing backups untouched"

# --- back up models/ (tiny; tar.gz, validated) --------------------------------
if [ -d "$MODELS_DIR" ]; then
    models_tar="$DEST/models_${TS}.tar.gz"
    if tar -czf "$models_tar" -C "$(dirname "$MODELS_DIR")" "$(basename "$MODELS_DIR")" \
        && tar -tzf "$models_tar" >/dev/null 2>&1; then
        log "published $(basename "$models_tar")"
    else
        warn "models backup failed (DB backup still good): $models_tar"
        rm -f -- "$models_tar"
    fi
else
    warn "models dir absent ($MODELS_DIR) -- skipping models backup"
fi

# --- retention: keep newest $KEEP of each kind; prune ONLY after a good backup -
#     Caller globs (nullglob -> zero args when none); our timestamped names sort
#     lexically == chronologically, and bash pathname expansion is already sorted.
prune_kind() {
    local kind="$1"; shift
    local files=( "$@" )
    local count=${#files[@]}
    if (( count > KEEP )); then
        local n_prune=$(( count - KEEP ))
        log "retention: $kind $count > keep=$KEEP -- pruning $n_prune oldest"
        local old
        for old in "${files[@]:0:$n_prune}"; do
            if rm -f -- "$old"; then log "  pruned $(basename "$old")"; fi
        done
    fi
}
shopt -s nullglob
prune_kind "db-backups"     "$DEST"/forge_db_*.duckdb
prune_kind "models-backups" "$DEST"/models_*.tar.gz
shopt -u nullglob

log "done -- backup dir $DEST ($(du -sh "$DEST" 2>/dev/null | cut -f1) total)"
