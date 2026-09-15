# HOW-TO: Running the Pipeline

Operator guide for the **Forge → Crucible → QuantIQ** pipeline. Per-command details: `MANPAGE.md`.
Deeper digging (DB queries, cohort traps): `tasks/investigate-live.md`.

## The pipeline in one breath

Once a week (`forge-campaign.timer`, Sunday 03:00 UTC) Forge reads the designated book and
Crucible's verdicts, decides whether any cell of the strategy space deserves challengers, and writes
at most a few hundred configs to Crucible's inbox → Crucible backtests + gates them → publishes
results; promoted books flow to QuantIQ. A week with no trigger submits nothing — that quiet result
is the design. The 24/7 daemon is retired (D416, 2026-09-14).

```
Forge ──inbox/<batch>/*.json──────────────────────────────────────────► Crucible
Forge ◄──exports/forge_gated_runs_*   (verdicts: the 14-day forge-scoped stream)──── Crucible
Forge ◄──exports/promoted_portfolios_* · designation_history_* · component_contributions_*
         · registry_snapshot_* · universe_tickers_* · refutations_*   (the book + inputs)── Crucible
                                              Crucible ──exports/promoted_portfolios_*──► QuantIQ
```

All inter-system communication is **files under `~/optbt_data/`** — no direct DB sharing.
Everything is a systemd **user** unit: Crucible's services, Forge's two timers.

## Start / stop

Forge has no long-running service: `forge-campaign.timer` (Sunday 03:00 UTC) and
`forge-backup.timer` (Sunday 04:30 UTC) are the whole schedule, and a reboot re-arms them onto
whatever this tree contains. Crucible's fleet is theirs to start and stop (writer first, then
everything else; reverse to stop) — `MANPAGE.md` PIPELINE SERVICES lists the Forge-relevant subset.

- Run the weekly campaign by hand, LIVE (submits if a trigger fires — operator-gated):
  `systemctl --user start forge-campaign.service`
- See this week's plan without submitting:
  `forge campaign --dry-run --skip-train --forge-db "$(scripts/live_db_snapshot.sh)"`
- Pause Forge: `systemctl --user disable --now forge-campaign.timer`; resume with `enable --now`.

## Weekly check (Monday)

```bash
# Anything failed? (a FAILED forge-campaign / forge-backup unit is the only Forge page)
systemctl --user list-units 'crucible*' 'forge*' --state=failed

# The run's block: boot rows, triggers, selection line, closing line
journalctl --user -u forge-campaign.service -n 40 --no-pager

# What recent runs did and what their submissions earned
SNAP=$(scripts/live_db_snapshot.sh); forge campaign status --last 4 --forge-db "$SNAP"

# Exports fresh? (the forge stream is minutes old while Crucible's publishers run)
ls -lt ~/optbt_data/exports/forge_gated_runs_*.json | head -1

# Backup fresh? (Sunday 04:30 UTC, after the run)
ls -lt ~/forge_data/backups/forge_db_*.duckdb | head -1
```

Reading the block top to bottom: one `boot <check> ok|FAIL` line per precondition (any FAIL → exit
2, nothing submitted, the unit goes FAILED); one `trigger <name> FIRED|quiet <reason>` line per
trigger; one `campaign <trigger> cells=N budget=B` line per campaign; then `selection: enumerated=…
kept=… survived=… gated_out={…} planned=…` and the closing `campaign <run_id>: submitted N` (or
`DRY RUN — planned N` / `no trigger; boot OK`). The record lands in
`~/forge_data/campaigns/<run_id>.json` (fields: `MANPAGE.md`). A failed unit is one of: a refused
mode, a boot check (including a preregistration read that came DUE or is UNWATCHABLE, D389/D392), or
a run error (an `error` record). The run trains the two models it ranks with in-run (record field
`models`); a fit that refuses or fails is a `notes` entry, never a crash. A second `--dry-run` on the
same exports must print the same plan — if it does not, an export changed under it (compare the
record's `watermarks`).

## Common situations

### Too many submissions? The weekly cap and the boot backlog check

The daemon's §7.3 rate limiter (`blocked: prev batch N% gated` / `crucible stalled` /
`in-flight depth N exceeds cap M`) was deleted in Batch 5 G4 (D421). Two things replaced it: the
weekly cap (`campaign.weekly_cap`, default in `forge.campaign.types.CampaignConfig`) bounds what one
run may submit, and the boot check refuses the whole run when the inbox backlog exceeds
`campaign.inbox_backlog_ceiling` (a FAILED unit is the page).

### Exports are stale / Forge can't see results

The DB is single-writer. Forge never reads `runs.duckdb` directly — it reads the file exports. If
they are old, Crucible's publishers are down: `systemctl --user status
crucible-publisher@forge_gated_runs.service crucible-gated-runs-publisher.service
crucible-promoted-portfolios-publisher.service`. The run refuses to start (boot checks `gated_runs`
/ `failed_runs` / `registry`) when the exports are missing or the registry snapshot is older than
`campaign.registry_max_age_days`.

### Crucible offline

The run needs Crucible three times: the exports at boot (`registry`, `universe`, `gated_runs`,
`failed_runs`), the writer socket for the battery's real feature cache (`require_real=True` — it
never filters against the synthetic one), and the inbox to submit. With Crucible down the run ends
with exit 2 (boot) or 1 (an `error` record), submits nothing, and the unit goes FAILED — the page.
Nothing partial to repair: reconcile is idempotent, and enumeration/battery write nothing to `forge.db`.
Recovery: once Crucible is back, wait for next Sunday or start the unit by hand (above).
Submissions stay `status='submitted'` until a matching verdict appears in the forge stream.
Crucible relays planned fleet-down windows in advance (`tasks/crucible-handoff.md`).

### Stuck submission (`status='pending'`)

The contracts `submit_candidate` write was interrupted between DB insert and inbox
write. Inspect `~/optbt_data/inbox/<batch_id>/`: if the JSON file is present, update
the row to `status='submitted'` manually; if absent, re-run the batch — the
`config_hash` UNIQUE INDEX (§13.4) makes resubmission a safe no-op.

### Restore forge.db (or models/) from a backup

Weekly backups land in `~/forge_data/backups/` (the `forge-backup` timer, Sunday 04:30 UTC, after
the campaign run): validated `forge_db_<UTC>.duckdb` snapshots + `models_<UTC>.tar.gz`; the newest
`FORGE_BACKUP_KEEP` are kept (set on the unit, `deploy/systemd/forge-backup.service`; script default
14). To restore:

```bash
systemctl --user is-active forge-campaign.service && echo 'a run is in progress: wait for it'   # nothing else writes forge.db
LATEST=$(ls -1 ~/forge_data/backups/forge_db_*.duckdb | sort | tail -1)
# verify it opens before swapping:
~/proj/Forge/.venv/bin/python -c "import duckdb,sys; print(duckdb.connect(sys.argv[1],read_only=True).execute('select count(*) from submissions').fetchone())" "$LATEST"
cp -- "$LATEST" ~/forge_data/forge.db        # overwrite the corrupted/lost DB
# models, if needed: tar -xzf "$(ls -1 ~/forge_data/backups/models_*.tar.gz | sort | tail -1)" -C ~/forge_data
# the next Sunday run picks the restored DB up; nothing to restart
```

Caveat: same-disk backups don't survive a *physical disk* failure — for that, `FORGE_BACKUP_DEST`
must point at a mounted off-box target (see `backup_forge_db.sh` in `MANPAGE.md`).

### Changing what a run targets (selection policy)

Which cells a run generates for, how much budget each trigger gets, and what the challenger gate
refuses are code in `src/forge/campaign/` (`triggers.py`, `gate.py`, `cells.py`) with defaults in
`forge.campaign.types.CampaignConfig`, overridable per key under `campaign:` in `config/forge.yaml`
(unknown keys fail loud). Edit like any other code: TDD, full suite, `scripts/deploy_preflight.sh`,
commit; the next Sunday run deploys (`tasks/deploy.md`). The enumerated POPULATION must not move
(the sampler goldens + `test_campaign_invariants`) — that would be a grammar change. Threshold-range
retraining and the daemon's learned draw weights are retired (D206/D298, D420);
`config/auto_tightened_thresholds.yaml` stays empty and fingerprint-load-bearing.

### Changing the grammar

The grammar is FROZEN at v55 (D390). Step 0: `forge prereg register` with a required n; the
`freeze-governance` pre-commit hook refuses a `grammar.yaml` content change without an open prereg
(`FORGE_FREEZE_REOPENER=D###` for a §5 reopener, with that D-entry staged). Then, by hand: edit
`config/grammar.yaml`, bump `grammar_version`, archive the new version to `config/grammar_archive/`,
commit (the version-bump and doc-sync hooks enforce this), and relay the version string plus the
first live run's instant to Crucible. No code proposes or applies grammar changes (hard rule #4).
Full procedure (worktree, tests, emission proof): `tasks/grammar-change.md`.

## Eras (boundaries that silently wreck joins)

Before any cohort read: split by `grammar_version` (pre-v5 re-gated rows carry `None` — exclude
them or they dominate "recent" aggregates, D103); fullhist-refit children re-gate under the same
`config_hash` with a new `run_id` (`verdicts` holds both; lineage at
`universe_json.submission_metadata.fullhist_refit_of`, D124); condition on
`submissions.selection_mode` (`campaign:<trigger>` since the cutover; daemon-era `ranked` /
`holdout` / …). Then the time boundaries (UTC unless noted):

| Boundary | What changed | Handle it |
|---|---|---|
| 2026-06-06T06:48:49Z | v9 code cutover (reboot-deploy) — not the 06-07 migration | time-cut v9 cohorts here (D104) |
| 2026-06-07 | box migration: timestamps before are PDT, after UTC | convert before joining DB rows or journals |
| 2026-06-09T22:52:57Z | cost floor: gate VALUES decided before were priced with zero slippage | never learn from or compare WF/CPCV/Sharpe values across it (D124) |
| 2026-06-09T22:55Z | export `decided_at` tz-aware UTC from here; older on-disk files carry naive LOCAL (+7 h) | `verdicts` was repaired once (D117); rows since are correct at ingest |
| 2026-06-10T01:00:02Z (pairs) / 01:28:03Z (rank) | real regime-coverage floors live | coverage honesty is a ROW marker: `gate_results["regime_coverage"].passed` AND `detail` without `coverage_unverified` (D124) |
| 2026-06-10T17:05:01Z, exit side from Crucible's next runner restart | forward earnings calendar exists; `earnings_exit` fires from the restart | every single-name backtest before the exit boundary HELD THROUGH EARNINGS; after it protection is PARTIAL (~32.5% late anchors) (D130) |
| 2026-07-17 → 2026-08-11 | canonical `open_interest` was a volume alias | the min-OI fill floor was a volume floor (D404) |
| 2026-08-12 → 2026-09-06T07:32:41Z | canonical OI NULL; IBKR near-ATM strikes skipped, `spread_too_wide` bound hard | a verdict's era is its `decided_at` (D386 gap); watch the weekly median `min_oos_trade_count` at boundaries — basis, not supply (D405) |
| 2026-09-06T07:32:41Z | CBOE panel OI folds onto canonical rows | near-ATM selectable again; the 07-17 alias replaced where the panel has the contract |
| 2026-08-06 17:10 PDT | Crucible's stage-two quality lane (`verdicts.refit_selection`) | the untagged cohort is TOP-DEPLETED from here — the rule and the recovery-window trap: `tasks/investigate-live.md` §Refit-lane cohorts |
| 2026-09-14T23:52:05Z | Route C cutover: the daemon's last batch | `forge_gated_runs` reads `truncated: true` until that tail leaves the 14-day window (D412/D415); campaign rows carry `selection_mode = campaign:<trigger>` |

## Where things live

| Path | Contents |
|---|---|
| `~/optbt_data/inbox/` | Forge's submitted configs (`<batch_id>/*.json`); `processed/` + `errors/` subdirs |
| `~/optbt_data/exports/` | Crucible snapshots: `forge_gated_runs_*` (the verdict stream), `gated_runs_*` / `failed_runs_*`, `promoted_portfolios_*`, `designation_history_*`, `component_contributions_*`, `registry_snapshot_*`, `universe_tickers_*`, `refutations_*` |
| `~/optbt_data/refit_inbox/` | QuantIQ's quarterly re-validation requests |
| `~/optbt_data/runs.duckdb` | Crucible's results DB (writer-locked; never read directly) |
| `~/forge_data/forge.db` | Forge's own state (submissions, verdicts, batch summaries, shadow scores) |
| `~/forge_data/campaigns/` | One `campaign_run/v1` record per weekly run |
| `~/forge_data/models/` | The verdict + robustness model artifacts (newest `campaign.models_keep` per family) |
| `~/forge_data/backups/` | Weekly DR snapshots of `forge.db` + `models/` (`forge-backup` timer, Sunday 04:30 UTC; retention = `FORGE_BACKUP_KEEP` on the unit) |

## Manual runs

```bash
cd ~/proj/Forge

forge check                                    # sanity: contracts + DB schema
forge enumerate --max 20 --summary             # preview generated configs (demo registry, no submission)
forge prefilter --max 20 --summary             # the §5.2 battery on those configs (diagnosis)
forge campaign --dry-run                       # this week's plan, nothing submitted
forge campaign status --last 4                 # recent runs + what their submissions earned
```

See `MANPAGE.md` for every command and flag.
