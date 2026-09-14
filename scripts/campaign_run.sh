#!/usr/bin/env bash
# The ExecStart of forge-campaign.service: run the weekly campaign in the mode the unit declares.
#
# WHY A WRAPPER. The same timer serves two phases of plan 2026-09 §12.6. During the dry-run weeks
# the daemon still owns the live forge.db (an RW lock, and the campaign's reconcile step WRITES),
# so the run must read a snapshot and submit nothing. At cutover the daemon stops and the run goes
# live on the real DB. Which phase applies is an OPERATOR decision recorded in the unit file
# (Environment=FORGE_CAMPAIGN_MODE=dry-run|live) — never inferred from whether the daemon happens
# to be running, because an accidental daemon stop must not turn the next Sunday into a live
# submitting run before Crucible's 14-day stream exists (D409 §4.1).
#
# Exit codes propagate (no SuccessExitStatus on the unit): a refused mode, a snapshot failure, a
# boot-check failure (2) or a run error (1) leaves the unit FAILED — the operator's only page.
set -euo pipefail

PROJ="${FORGE_PROJ:-$HOME/proj/Forge}"
MODE="${FORGE_CAMPAIGN_MODE:-}"
# Test seam: the command that answers "is the daemon holding the live DB?" (default: systemd).
DAEMON_ACTIVE_CMD="${FORGE_CAMPAIGN_DAEMON_ACTIVE_CMD:-systemctl --user is-active --quiet forge.service}"
UV="${FORGE_UV:-$HOME/.local/bin/uv}"
cd "$PROJ"

case "$MODE" in
  dry-run)
    SNAP="$("$PROJ/scripts/live_db_snapshot.sh" --max-age-min "${FORGE_CAMPAIGN_SNAPSHOT_MAX_AGE_MIN:-720}")"
    echo "campaign_run: mode=dry-run forge_db=$SNAP (snapshot; nothing is submitted)"
    exec "$UV" run forge campaign --dry-run --forge-db "$SNAP" "$@"
    ;;
  live)
    if bash -c "$DAEMON_ACTIVE_CMD"; then
      echo "campaign_run: REFUSED — mode=live but forge.service is active (it owns the live DB; stop it first, plan §12.6 Batch 4)" >&2
      exit 2
    fi
    echo "campaign_run: mode=live (submits to Crucible's inbox)"
    exec "$UV" run forge campaign "$@"
    ;;
  *)
    echo "campaign_run: REFUSED — FORGE_CAMPAIGN_MODE must be 'dry-run' or 'live' (got '${MODE}'); set it in forge-campaign.service" >&2
    exit 2
    ;;
esac
