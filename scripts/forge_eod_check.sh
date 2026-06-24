#!/usr/bin/env bash
# Scheduled EOD pipeline check for Forge -> Crucible -> QuantIQ (created 2026-06-10).
# Runs a headless Claude session that snapshots forge.db, compares against the
# clean-era baseline in project memory, and writes a report. Report-only by design.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

REPORT_DIR="$HOME/forge_data/eod_checks"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/eod-$(date +%F).md"

cd "$HOME/proj/Forge"

PROMPT_TEXT="$(cat <<'EOF'
You are the scheduled end-of-day pipeline check for the Forge -> Crucible -> QuantIQ
project (systemd unit forge-eod-check, created 2026-06-10). You run headless on the
production box with cwd ~/proj/Forge.

HARD CONSTRAINTS - report-only run: do not modify, commit, or format anything inside
~/proj/Forge; do not touch grammar.yaml, weights, config, or any systemd service; do
not submit candidates or relay prompts. Your ONLY write is the report file named at
the end (overwrite it if it already exists).

Context: read ~/.claude/projects/-home-aj-proj-Forge/memory/pipeline-vision-roadmap.md
for the roadmap, EOD checklist, and baseline. Reference baseline (2026-06-10T18:53:47Z,
~78 min after the v17 deploy): v17 submissions 600; verdicts on v17 configs 5 component
/ 171 reject; post-exit-era (decided_at >= 2026-06-10 17:17:13 UTC) verdicts 18
component / 321 reject; new arms thin in submissions (iv_minus_rv 2/600, market_state
3/600); all-time 99,589 submissions, 481 component / 12,616 reject / 0 promotions.

Data access: the live DB holds an intermittent lock - copy first:
cp ~/forge_data/forge.db /tmp/forge_eod_check.db
then query the copy with: uv run python (duckdb, read_only=True). DB timestamps are UTC.

Collect:
1. v17 submissions count (json_extract_string(config_json,'$.grammar_version')='v17')
   and verdicts on v17 configs by decision (join verdicts to submissions on config_hash).
2. Verdicts by decision for decided_at >= '2026-06-10 17:17:13' (exit era) and
   >= '2026-06-10 17:36:10' (v17 deploy), with component rates.
3. New-arm flow: v17 submissions whose config_json contains 'iv_minus_rv' and
   'market_state'; for iv_minus_rv also those containing 'swing_mid' (first-ever
   ve x swing_mid). Any verdicts on those config_hashes yet?
4. All-time decision counts. If any decision other than reject/component has EVER
   appeared (a first promotion), lead the report with it.
5. journalctl --user -u forge.service --since "24 hours ago": most recent
   hypothesis_weights line (drift vs em=1.000 tc=0.813 mr=0.794 rv=0.750 ve=0.524),
   any error/traceback lines, count of "blocked: prev batch" lines (benign limiter -
   count only, do not flag as a problem).
6. If older reports exist in ~/forge_data/eod_checks/, compare day-over-day as well.

Report format (markdown): lead with a 3-5 sentence TLDR (what changed vs baseline, any
red flags), then the numbers, then "Questions / actions for the operator". Apply the
tiny-n caveat throughout: flag signals and anomalies; do NOT conclude edges or recommend
grammar changes. Specifically assess: are the new v17 arms (iv_minus_rv, market_state)
reaching Crucible in volume, or still starved at the ranker (cold start)?

Write the report to: __REPORT_PATH__
EOF
)"
PROMPT_TEXT="${PROMPT_TEXT//__REPORT_PATH__/$REPORT}"

# stdin + --flag=value: --allowedTools is variadic and would swallow a trailing
# positional prompt argument
printf '%s' "$PROMPT_TEXT" | claude -p --model sonnet --allowedTools="Bash,Read,Write,Grep,Glob"

echo "forge-eod-check: report at $REPORT"
