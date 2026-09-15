#!/usr/bin/env bash
#
# stage_transfer.sh — stage the Forge migration bundle onto a flash drive.
#
# WHY this exists: a new-box transfer of Forge has non-obvious traps —
#   (1) crucible_contracts has NO git remote, so it cannot be cloned and must
#       physically travel as a sibling of Forge (Forge resolves it via the
#       relative path ../crucible_contracts in pyproject [tool.uv.sources]).
#   (2) ~/forge_data/forge.db is multi-GB of accumulated learning state, is
#       gitignored, and is held OPEN while a weekly run is in progress — copy it
#       out-of-band (this script), never during a run, and disable the Forge timers
#       first (--stop-service) so no run starts mid-copy.
#   (3) the non-portable .venv (uv bakes absolute interpreter paths) must NOT
#       travel — setup_new_box.sh rebuilds it on the new box.
# This script bundles (1)+(2) correctly and excludes the .venv per (3).
#
# Safe by default: PREVIEWS (rsync --dry-run) unless --go is passed, and never
# touches the Forge timers unless --stop-service is passed (which disables them so
# no run can open forge.db mid-copy; DuckDB + WAL stay consistent). There is no
# daemon since the 2026-09-14 cutover (D416).
#
# Bundle layout produced at <dest>:
#   <dest>/proj/Forge/               working tree incl. .git (committed through the version in config/grammar.yaml)
#   <dest>/proj/crucible_contracts/  shared editable dep (the pinned version)
#   <dest>/forge_data/forge.db       accumulated state
#
# Usage:
#   deploy/stage_transfer.sh /media/aj/FLASHDRIVE                     # preview
#   deploy/stage_transfer.sh /media/aj/FLASHDRIVE --stop-service --go # real copy
#
set -euo pipefail

PROJ="${PROJ:-$HOME/proj}"
FORGE_DATA="${FORGE_DATA:-$HOME/forge_data}"

DEST=""
GO=0
STOP_SERVICE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --go) GO=1 ;;
    --stop-service) STOP_SERVICE=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^#\{1,2\} \{0,1\}//'; exit 0 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) DEST="$1" ;;
  esac
  shift
done

[ -n "$DEST" ] || { echo "usage: $0 <dest> [--stop-service] [--go]" >&2; exit 2; }

say()  { printf '\n=== %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

[ -d "$PROJ/Forge" ]              || { echo "missing $PROJ/Forge" >&2; exit 1; }
[ -d "$PROJ/crucible_contracts" ] || { echo "missing $PROJ/crucible_contracts — Forge will not install without it" >&2; exit 1; }

if [ "$GO" -eq 0 ]; then
  say "DRY RUN — nothing is copied. Re-run with --go to write to $DEST"
fi

# Quiesce forge.db before copying (consistent snapshot of an open DuckDB file). Only a weekly
# run opens it (D416): refuse during one; with --stop-service disable both timers so none starts.
TIMERS_WERE_DISABLED=0
if systemctl --user is-active --quiet forge-campaign.service 2>/dev/null; then
  echo "forge-campaign.service is RUNNING (a weekly run holds forge.db). Wait for it to finish." >&2
  exit 1
fi
if [ "$STOP_SERVICE" -eq 1 ]; then
  say "Disabling forge-campaign.timer + forge-backup.timer so no run starts mid-copy"
  if [ "$GO" -eq 1 ]; then
    if systemctl --user disable --now forge-campaign.timer forge-backup.timer 2>/dev/null; then
      TIMERS_WERE_DISABLED=1
    else
      warn "could not disable the Forge timers (not installed here?)"
    fi
  fi
else
  warn "Forge timers left armed — a Sunday 03:00 UTC run could open forge.db mid-copy."
  warn "Re-run with --stop-service for a guaranteed-quiet copy."
fi

EXCLUDES=(--exclude '.venv' --exclude '__pycache__' --exclude '.mypy_cache'
          --exclude '.ruff_cache' --exclude '.pytest_cache' --exclude '.hypothesis'
          --exclude '.claude')

RSYNC=(rsync -aH --info=stats1)
[ "$GO" -eq 1 ] || RSYNC+=(--dry-run)

if [ "$GO" -eq 1 ]; then
  mkdir -p "$DEST/proj" "$DEST/forge_data"
fi

say "Forge working tree (incl. .git, committed through the version in config/grammar.yaml) -> $DEST/proj/Forge"
"${RSYNC[@]}" "${EXCLUDES[@]}" "$PROJ/Forge/" "$DEST/proj/Forge/"

say "crucible_contracts (shared editable dep) -> $DEST/proj/crucible_contracts"
"${RSYNC[@]}" "${EXCLUDES[@]}" "$PROJ/crucible_contracts/" "$DEST/proj/crucible_contracts/"

say "Forge state DB -> $DEST/forge_data/forge.db"
if [ -f "$FORGE_DATA/forge.db" ]; then
  printf 'forge.db size: %s\n' "$(du -h "$FORGE_DATA/forge.db" | cut -f1)"
  if [ "$GO" -eq 1 ]; then
    "${RSYNC[@]}" "$FORGE_DATA/forge.db" "$DEST/forge_data/forge.db"
  else
    # The dir-to-dir rsyncs above preview without a dest; a single-file copy
    # would need $DEST/forge_data to exist, which we only create under --go.
    printf '(dry run) would copy forge.db -> %s\n' "$DEST/forge_data/forge.db"
  fi
else
  warn "no forge.db at $FORGE_DATA — nothing to bundle (new box will start fresh)"
fi

say "Done."
if [ "$GO" -eq 1 ]; then
  printf 'Bundle staged at: %s\n' "$DEST"
  du -sh "$DEST/proj/Forge" "$DEST/proj/crucible_contracts" "$DEST/forge_data" 2>/dev/null || true
  if [ "$TIMERS_WERE_DISABLED" -eq 1 ]; then
    warn "Forge timers left DISABLED on this box. To resume production here:"
    printf '       systemctl --user enable --now forge-campaign.timer forge-backup.timer\n'
  fi
else
  printf 'Preview only. Re-run with --stop-service --go to write the bundle.\n'
fi
