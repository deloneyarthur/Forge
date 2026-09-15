#!/usr/bin/env bash
# The ExecStart of forge-campaign.service: run the weekly campaign in the mode the unit declares.
#
# WHY A WRAPPER. The unit carries ONE operator decision, Environment=FORGE_CAMPAIGN_MODE:
#   live    - the weekly run submits what its triggers select (since the 2026-09-14 cutover, D416);
#   dry-run - snapshot the DB and plan only (the pre-cutover weeks, D411; still useful for a manual
#             rehearsal of a code change before Sunday).
# Any other value is refused so a typo cannot silently turn a live week into nothing.
# (The pre-cutover guard that refused `live` while a daemon held the live DB left with the daemon,
# Batch 6 A3 - there is no forge.service to be active.)
#
# Exit codes propagate (no SuccessExitStatus on the unit): a refused mode, a snapshot failure, a
# boot-check failure (2) or a run error (1) leaves the unit FAILED — the operator's only page.
set -euo pipefail

PROJ="${FORGE_PROJ:-$HOME/proj/Forge}"
MODE="${FORGE_CAMPAIGN_MODE:-}"
UV="${FORGE_UV:-$HOME/.local/bin/uv}"
cd "$PROJ"

case "$MODE" in
  dry-run)
    SNAP="$("$PROJ/scripts/live_db_snapshot.sh" --max-age-min "${FORGE_CAMPAIGN_SNAPSHOT_MAX_AGE_MIN:-720}")"
    echo "campaign_run: mode=dry-run forge_db=$SNAP (snapshot; nothing is submitted)"
    exec "$UV" run forge campaign --dry-run --forge-db "$SNAP" "$@"
    ;;
  live)
    echo "campaign_run: mode=live (submits to Crucible's inbox)"
    exec "$UV" run forge campaign "$@"
    ;;
  *)
    echo "campaign_run: REFUSED — FORGE_CAMPAIGN_MODE must be 'dry-run' or 'live' (got '${MODE}'); set it in forge-campaign.service" >&2
    exit 2
    ;;
esac
