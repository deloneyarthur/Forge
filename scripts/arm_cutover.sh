#!/usr/bin/env bash
# One-shot operator script: commit + push the prepared cutover files, DELIVER the instant to
# Crucible (a commit in ~/proj/freeze is delivery), and ARM forge-cutover.timer for
# 2026-09-15T07:00:00Z. Written because the assistant's harness refuses to run these steps itself
# (D413). Idempotent: re-running skips what is already done. Retire with the cutover files in Batch 5.
set -euo pipefail

INSTANT="2026-09-15T07:00:00Z"
PROJ="$HOME/proj/Forge"
FREEZE="$HOME/proj/freeze"
RELAY="$FREEZE/relays/FORGE_CUTOVER_INSTANT_2026-09-15T07-00-00Z_the_daemon_stops_forge_campaign_goes_live_first_live_run_at_the_instant_truncated_stays_true_until_the_daemon_tail_ages_out_2026-09-14.md"
ATTRIB=$'\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017Hm1trjopTQYu5mMtNuZ8h'
say() { echo "arm_cutover: $*"; }

# 0. The notice period: Crucible asked for the instant >= 24 h ahead. Refuse if that is no longer true.
now_s="$(date -u +%s)"; instant_s="$(date -u -d "$INSTANT" +%s)"
if [ "$now_s" -gt $((instant_s - 24 * 3600)) ] && [ ! -f "$RELAY" ]; then
  say "REFUSED: fewer than 24 h remain before $INSTANT and the relay is not delivered yet."
  say "Edit INSTANT here and OnCalendar in deploy/systemd/forge-cutover.timer to a LATER round hour, then re-run."
  exit 2
fi

# 1. Forge: commit + push the prepared files
cd "$PROJ"
for f in scripts/cutover_campaign.sh deploy/systemd/forge-cutover.service deploy/systemd/forge-cutover.timer; do
  [ -f "$f" ] || { say "missing $f — nothing to arm"; exit 2; }
done
grep -q "OnCalendar=2026-09-15 07:00:00 UTC" deploy/systemd/forge-cutover.timer || { say "timer file does not carry $INSTANT"; exit 2; }
git add scripts/cutover_campaign.sh scripts/arm_cutover.sh deploy/systemd/forge-cutover.service deploy/systemd/forge-cutover.timer \
        IMPLEMENTATION_DECISIONS.md STATUS.md docs/proposals/repo-simplification-2026-09.md
if git diff --cached --quiet; then
  say "Forge: nothing to commit (already committed)"
else
  git commit -q -m "D413: cutover scheduled $INSTANT — forge-cutover timer + cutover script + operator arming script${ATTRIB}"
  say "Forge: committed $(git rev-parse --short HEAD)"
fi
git push origin main && say "Forge: pushed" || say "Forge: push failed — push by hand later (not blocking)"
scripts/cutover_campaign.sh --check

# 2. Crucible: deliver the instant (commit in the freeze repo = delivery)
if [ -f "$RELAY" ]; then
  say "relay already exists — not rewritten"
else
cat > "$RELAY" <<'EOF'
# FORGE → CRUCIBLE — cutover instant: **2026-09-15T07:00:00Z** (≥ 24 h ahead). The daemon stops, `forge campaign` goes live, first live run at the instant; `truncated: true` stays for up to 14 days while the daemon's tail ages out (2026-09-14)

**Re:** your `CRUCIBLE_forge_gated_runs_stream_LIVE_…_2026-09-14` §3 ("relay the cutover instant, ≥ 24 h ahead"). Operator decision 2026-09-14: cut over as soon as the notice period allows.

## The instant

**2026-09-15T07:00:00Z** (Tuesday 00:00 PDT). Record it as the `ranked`-arm boundary: `selection_arm='ranked'`
rows decided before it are ranker-selected by the daemon; after it, campaign-sampled (Forge's own ledger
carries `selection_mode='campaign:<trigger>'`).

## What happens at the instant (automated, `forge-cutover.timer`, persistent)

1. `forge.service` stopped **and disabled** (a reboot will not restart it). Daemon submissions end here;
   ~11k/day → ≤ 400/week.
2. `forge-healthcheck.timer` disabled (its checks assume a daemon). `forge-ranker-eval`, `forge-prereg-watch`,
   `forge-backup` keep running until our Batch 5 folds them in.
3. `forge-campaign.service` flipped to `FORGE_CAMPAIGN_MODE=live`; **first live run immediately** (synchronous),
   then Sundays 03:00 UTC. A failed step leaves the cutover unit FAILED and the daemon stopped; nothing partial
   submits.

## What you will see, and what is NOT a problem

- **`truncated: true` on the forge stream for up to 14 days after the instant.** The window still holds the
  daemon's last 14 days (~10k+/day), so the 10k cap keeps binding until that tail ages out (~2026-09-29).
  Campaign verdicts are the newest rows, so each Sunday's reconcile still sees its own run; our aged-out
  flush stays off while truncated. **A truncated file after ~09-29 is the anomaly** you described, and we
  will relay it.
- The morning digest's Forge section goes quiet; `~/forge_data/campaigns/<run_id>.json` keeps writing
  (weekly, plus `CUTOVER.json` at the instant). `forge_funnel.json` keeps its aggregate shape.

## If the instant moves

Only later, never earlier, and only by a relay from us before the new instant. If you see the daemon still
submitting after 07:00Z on the 15th, the cutover unit failed and we owe you a relay.
EOF
  say "relay written"
fi
cd "$FREEZE"
if ! grep -q "Cutover instant RELAYED: $INSTANT" INDEX_forge_answered.md; then
  python3 - "$INSTANT" <<'PY'
import sys
from pathlib import Path
instant = sys.argv[1]
p = Path("INDEX_forge_answered.md"); s = p.read_text()
s = s.replace("**Cutover waits only on the operator's date.**",
              f"**Cutover instant RELAYED: {instant}** (`FORGE_CUTOVER_INSTANT…`). We owe a relay if it moves (later only) or if the cutover unit fails; a `truncated: true` forge file after ~09-29 is ours to relay.", 1)
s = s.replace("- Cutover instant relayed (2026-09-15T07:00:00Z); moves only later and only by relay;", "- Cutover instant relayed (2026-09-15T07:00:00Z); moves only later and only by relay;", 1)
s = s.replace("- Relay the campaign-mode **cutover instant (UTC) before** stopping `forge.service`; never emit",
              f"- Cutover instant relayed ({instant}); moves only later and only by relay; never emit", 1)
p.write_text(s)
PY
fi
git add -A relays INDEX_forge_answered.md
if git diff --cached --quiet; then
  say "freeze: relay already delivered"
else
  git commit -q -m "relay(crucible): CUTOVER INSTANT $INSTANT — daemon stops + forge campaign goes live at the instant; truncated stays true until the daemon tail ages out (~09-29)${ATTRIB}"
  say "freeze: relay DELIVERED $(git rev-parse --short HEAD)"
fi

# 3. Arm the timer
cd "$PROJ"
ln -sf "$PROJ/deploy/systemd/forge-cutover.service" "$PROJ/deploy/systemd/forge-cutover.timer" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now forge-cutover.timer
systemctl --user list-timers --all --no-pager forge-cutover.timer
say "ARMED for $INSTANT. Nothing changes until then. After it fires: journalctl --user -u forge-cutover.service -n 40"
