#!/usr/bin/env bash
# The Route C cutover (plan 2026-09 §12.6 Batch 4), run unattended by forge-cutover.timer at the
# instant relayed to Crucible (D413). Idempotent: every step checks before acting, so a re-run
# after a partial failure finishes the job instead of repeating it.
#
# WHAT IT DOES, in order:
#   1. precondition checks (deploy surface clean, unit carries a mode line, forge stream present)
#   2. stop AND DISABLE forge.service — disable matters: a reboot auto-starts enabled units onto the
#      tree (D104); after the cutover the daemon must never come back on its own
#   3. stop + disable forge-healthcheck.timer (its checks assume a daemon; hourly CRITICALs would be
#      noise). forge-ranker-eval, forge-prereg-watch and forge-backup KEEP running until Batch 5
#      folds training + the DUE judge into the campaign and re-times the backup.
#   4. flip forge-campaign.service to FORGE_CAMPAIGN_MODE=live + daemon-reload + commit
#   5. first live run NOW (synchronous), then the timer owns Sundays 03:00 UTC
#   6. write ~/forge_data/campaigns/CUTOVER.json and disarm forge-cutover.timer
# Exit non-zero on any failure (the cutover unit goes FAILED = the page). `--check` runs step 1 only.
set -euo pipefail
PROJ="${FORGE_PROJ:-$HOME/proj/Forge}"
UNIT="$PROJ/deploy/systemd/forge-campaign.service"
RECORDS="${FORGE_CAMPAIGN_RECORDS:-$HOME/forge_data/campaigns}"
EXPORTS="${FORGE_EXPORTS_DIR:-$HOME/optbt_data/exports}"
cd "$PROJ"
log() { echo "cutover: $*"; }

# 1. preconditions
dirty="$(git status --porcelain -- src config pyproject.toml uv.lock deploy | wc -l)"
[ "$dirty" -eq 0 ] || { log "REFUSED: deploy surface dirty ($dirty paths)"; exit 2; }
grep -q '^Environment=FORGE_CAMPAIGN_MODE=' "$UNIT" || { log "REFUSED: unit has no mode line"; exit 2; }
ls "$EXPORTS"/forge_gated_runs_*.json >/dev/null 2>&1 || { log "REFUSED: no forge_gated_runs export"; exit 2; }
log "preconditions OK (mode=$(sed -n 's/^Environment=FORGE_CAMPAIGN_MODE=//p' "$UNIT"))"
[ "${1:-}" = "--check" ] && exit 0

# 2. the daemon: stop + disable
if systemctl --user is-active --quiet forge.service; then
  systemctl --user stop forge.service; log "forge.service stopped $(date -u +%FT%TZ)"
fi
systemctl --user disable forge.service >/dev/null 2>&1 || true
if systemctl --user is-enabled --quiet forge.service; then log "FAILED: forge.service still enabled"; exit 1; fi
log "forge.service disabled (a reboot will not restart it)"

# 3. the daemon-shaped monitor
systemctl --user disable --now forge-healthcheck.timer >/dev/null 2>&1 || true
log "forge-healthcheck.timer disabled"

# 4. flip the unit to live + commit
if grep -q '^Environment=FORGE_CAMPAIGN_MODE=dry-run$' "$UNIT"; then
  sed -i 's/^Environment=FORGE_CAMPAIGN_MODE=dry-run$/Environment=FORGE_CAMPAIGN_MODE=live/' "$UNIT"
fi
grep -q '^Environment=FORGE_CAMPAIGN_MODE=live$' "$UNIT" || { log "FAILED: mode flip did not take"; exit 1; }
systemctl --user daemon-reload
systemctl --user show forge-campaign.service -p Environment | grep -q 'FORGE_CAMPAIGN_MODE=live' \
  || { log "FAILED: loaded unit does not carry live"; exit 1; }
if ! git diff --quiet -- "$UNIT"; then
  git add "$UNIT"
  git commit -q -m "cutover: forge-campaign.service FORGE_CAMPAIGN_MODE dry-run -> live at $(date -u +%FT%TZ) (Route C, plan §12.6 Batch 4; D413); forge.service stopped + disabled; forge-healthcheck.timer disabled

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_017Hm1trjopTQYu5mMtNuZ8h"
  log "unit flip committed $(git rev-parse --short HEAD)"
fi

# 5. first live run, synchronous
if systemctl --user start forge-campaign.service; then result=success; else result=failed; fi
log "first live run: $result"

# 6. record + disarm
mkdir -p "$RECORDS"
printf '{"schema_version": "cutover/v1", "instant": "%s", "first_live_run": "%s", "daemon_disabled": true}\n' \
  "$(date -u +%FT%TZ)" "$result" > "$RECORDS/CUTOVER.json"
systemctl --user disable --now forge-cutover.timer >/dev/null 2>&1 || true
if git push origin main >/dev/null 2>&1; then log "pushed"; else log "push skipped (no agent in this context); push by hand"; fi
[ "$result" = success ]
