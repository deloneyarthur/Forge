#!/usr/bin/env bash
# ONE reusable, real-disk snapshot of the live Forge DB. Prints its path on stdout.
#
# WHY THIS EXISTS (2026-08-02). The standing ritual was `cp ~/forge_data/forge.db
# /tmp/forge_snapshot.db`, and `/tmp` on this box is a **62 GB tmpfs** — RAM. The live DB is
# **6.7 GB**. Nine investigation snapshots in one session filled tmpfs completely and took the
# shell down twice: every command, including `true`, returned exit 1 with no output, because
# the harness could not write its own output capture. The failure does not look like "disk
# full", it looks like the tooling is broken, which is what makes it expensive.
#
# Three properties, each fixing one half of that:
#   1. REAL DISK, enforced. Refuses to write to a tmpfs rather than trusting the caller to
#      remember. `/` has ~333 GB; tmpfs has whatever RAM is left.
#   2. ONE snapshot, REUSED. A snapshot younger than --max-age-min is returned as-is, so ten
#      queries in a session cost 6.7 GB of I/O once instead of ten times.
#   3. --clean, so the disposable thing is disposable on purpose.
#
# Usage:
#   SNAP=$(scripts/live_db_snapshot.sh)          # fresh-enough snapshot, path on stdout
#   SNAP=$(scripts/live_db_snapshot.sh --force)  # force a re-copy
#   scripts/live_db_snapshot.sh --clean          # remove it
#
# The copy is consistent (DuckDB single-file copy) and read-only safe while the daemon holds
# its intermittent RW lock — which is the reason we snapshot at all.
set -euo pipefail

LIVE="${FORGE_LIVE_DB:-$HOME/forge_data/forge.db}"
SNAP_DIR="${FORGE_SNAPSHOT_DIR:-$HOME/forge_data/.snapshots}"
SNAP="$SNAP_DIR/forge_live.db"
MAX_AGE_MIN=15
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --clean)        rm -f "$SNAP"; echo "removed $SNAP" >&2; exit 0 ;;
    --force)        FORCE=1; shift ;;
    --max-age-min)  MAX_AGE_MIN="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f "$LIVE" ] || { echo "live DB not found: $LIVE" >&2; exit 1; }
mkdir -p "$SNAP_DIR"

# (1) Real disk, enforced — the whole point. Checked on the DIRECTORY, because that is what
# the copy lands on, and checked every run, because a mount can change under us.
FSTYPE="$(stat -f -c '%T' "$SNAP_DIR" 2>/dev/null || echo unknown)"
if [ "$FSTYPE" = "tmpfs" ] || [ "$FSTYPE" = "ramfs" ]; then
  echo "REFUSING: $SNAP_DIR is $FSTYPE (RAM). The live DB is $(du -h "$LIVE" | cut -f1)." >&2
  echo "Set FORGE_SNAPSHOT_DIR to a real-disk path." >&2
  exit 1
fi

# Enough headroom for the copy, or say so plainly rather than half-writing a 6.7 GB file.
NEED_KB=$(du -k "$LIVE" | cut -f1)
FREE_KB=$(df -Pk "$SNAP_DIR" | awk 'NR==2 {print $4}')
if [ "$FREE_KB" -lt "$NEED_KB" ]; then
  echo "REFUSING: need $((NEED_KB / 1024)) MB, only $((FREE_KB / 1024)) MB free on $SNAP_DIR" >&2
  exit 1
fi

# (2) Reuse a fresh-enough snapshot.
if [ "$FORCE" -eq 0 ] && [ -f "$SNAP" ] \
   && [ -z "$(find "$SNAP" -mmin "+$MAX_AGE_MIN" -print -quit)" ]; then
  echo "reusing snapshot ($(stat -c %y "$SNAP" | cut -d. -f1))" >&2
  echo "$SNAP"
  exit 0
fi

cp "$LIVE" "$SNAP.tmp"   # tmp-then-rename so a reader never sees a half-copied file
mv "$SNAP.tmp" "$SNAP"
echo "snapshot refreshed: $(du -h "$SNAP" | cut -f1) on $FSTYPE" >&2
echo "$SNAP"
