# HOW-TO: Running the Pipeline

Operator guide for the **Forge → Crucible → QuantIQ** pipeline. For per-command
details see `MANPAGE.md`.

## The pipeline in one breath

Once a week (`forge-campaign.timer`, Sunday 03:00 UTC) Forge reads the designated book and
Crucible's verdicts, decides whether any cell is worth generating for, and writes at most a few
hundred challengers to Crucible's inbox → Crucible backtests + gates them → publishes results.
The 24/7 daemon is retired (D416, 2026-09-14).
Promoted strategies flow to QuantIQ for live/paper trading.

```
Forge ──inbox/*.json──► Crucible ──exports/gated_runs──► Forge (feedback)
                            │
                            └──exports/promoted_strategies──► QuantIQ
```

All inter-system communication is **files under `~/optbt_data/`** — no direct DB
sharing. Everything runs as **systemd user services**.

## Start / stop

Forge has no long-running service since the cutover (D416): `forge-campaign.timer` (Sunday
03:00 UTC) and `forge-backup.timer` (Sunday 04:30 UTC) are the whole schedule, and a reboot
re-arms them onto whatever this tree contains. Crucible's fleet is theirs to start and stop
(writer first, then everything else; reverse to stop) — `MANPAGE.md` PIPELINE SERVICES lists the
Forge-relevant subset. To run the weekly campaign by hand: `systemctl --user start
forge-campaign.service` (live mode — it submits if a trigger fires) or
`forge campaign --dry-run` for a plan that submits nothing.

## Daily health check

```bash
# Anything failed? (a FAILED forge-campaign / forge-backup unit is the only Forge page)
systemctl --user list-units 'crucible*' 'forge*' --state=failed

# Is Crucible processing? (templated runner instances)
journalctl --user -u crucible-runner@1.service -n 10 --no-pager

# Are exports fresh? (should be < 2 min old)
ls -lt ~/optbt_data/exports/gated_runs_*.json | head -1

# Last weekly backup fresh? (forge-backup timer, Sunday 04:30 UTC, after the campaign run)
ls -lt ~/forge_data/backups/forge_db_*.duckdb | head -1

# Weekly campaign ran? (forge-campaign timer, Sunday 03:00 UTC; a failed unit = a refused mode,
# a boot check — incl. a prereg read that came DUE or is UNWATCHABLE, D389/D392 — or a run error;
# read the block, plan 2026-09 §12; `forge campaign status` for the records)
journalctl --user -u forge-campaign.service -n 30 --no-pager
```

The weekly run trains the verdict + robustness models it ranks with in-run (record field `models`,
Batch 5 G0). Deeper digging (forge.db queries, cohort analysis, known traps):
`tasks/investigate-live.md`.

## Common situations

### Too many submissions? The weekly cap and the boot backlog check

The daemon's §7.3 rate limiter (`blocked: prev batch N% gated` / `crucible stalled` /
`in-flight depth N exceeds cap M`) was deleted in Batch 5 G4 (D421). Two things replaced it: the
weekly cap (`campaign.weekly_cap`, default in `forge.campaign.types.CampaignConfig`) bounds what one
run may submit, and the boot check refuses the whole run when the inbox backlog exceeds
`campaign.inbox_backlog_ceiling` (a FAILED unit is the page). If Crucible's publishers die, the
run's reconcile sees a stale export: `systemctl --user status
crucible-gated-runs-publisher.service crucible-publisher@forge_gated_runs.service`.

### Exports are stale / Forge can't see results

The DB is single-writer. Forge never reads `runs.duckdb` directly — it reads the
file exports. If exports are old, restart the relevant publisher (see above).

### Crucible offline

`forge feedback` exits non-zero with `error: Crucible DB unreachable: ...`. No partial
mutations to Forge state. Re-invoke once the path is reachable; affected submissions
stay `status='submitted'` until a matching gated run appears. Orphaned Crucible rows
(no `promotion_decisions` row) are silently skipped — those submissions also stay
`submitted` while the rest of the batch processes normally.

### Stuck submission (`status='pending'`)

The contracts `submit_candidate` write was interrupted between DB insert and inbox
write. Inspect `~/optbt_data/inbox/<batch_id>/`: if the JSON file is present, update
the row to `status='submitted'` manually; if absent, re-run the batch — the
`config_hash` UNIQUE INDEX (§13.4) makes resubmission a safe no-op.

### Restore forge.db (or models/) from a backup

Weekly backups land in `~/forge_data/backups/` (the `forge-backup` timer, Sunday 04:30 UTC, after the campaign run): validated
`forge_db_<UTC>.duckdb` snapshots + `models_<UTC>.tar.gz`; the newest `FORGE_BACKUP_KEEP` are
kept (set on the unit, `deploy/systemd/forge-backup.service`; script default 14). To restore:

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

### Tune the generator from real results

Threshold-range retraining is RETIRED (D206, made permanent D298 — the axis
measured flat on CPCV-p25 with monoculture risk; the proposer script lives in
git history). `config/auto_tightened_thresholds.yaml` stays empty; the sampler
uses the D031 audited baselines.

Any change that deploys on restart (config edits, new ranges, code) should clear
`scripts/deploy_preflight.sh` first — it's step 0 of the deploy ritual (`tasks/deploy.md`).
Review any **loosening** proposals (these need operator sign-off) in `OPEN_PROPOSALS.md`.

### Weekly campaign run (the pipeline since the 2026-09-14 cutover)

`forge-campaign.timer` (Sunday 03:00 UTC) runs `scripts/campaign_run.sh`, which in the unit's
`live` mode (since the 2026-09-14 cutover, D416) submits whatever the triggers select, at most a few
hundred configs, no operator input. Check it Monday with
`journalctl --user -u forge-campaign.service -n 30 --no-pager` (a FAILED unit is the page). For a plan
that submits nothing, run `forge campaign --dry-run --skip-train --forge-db "$(scripts/live_db_snapshot.sh)"`
by hand. Read the
journal block top to bottom: one `boot <check> ok|FAIL` line per precondition (any FAIL → exit 2,
nothing submitted, the unit goes FAILED — that is the only page); one `trigger <name> FIRED|quiet
<reason>` line per trigger; one `campaign <trigger> cells=N budget=B` line per campaign; then
`selection: enumerated=… kept=… survived=… gated_out={…} planned=…` and the closing
`campaign <run_id>: submitted N` (or `DRY RUN — planned N` / `no trigger; boot OK`). The record
lands in `~/forge_data/campaigns/<run_id>.json`; `forge campaign status --forge-db "$SNAP"`
(with `SNAP=$(scripts/live_db_snapshot.sh)`) shows what each run's submissions earned. A second
`--dry-run` on the same exports must print the same plan — if it does not, an export changed
under it (compare the record's `watermarks`).

### Changing the grammar

The grammar is FROZEN at v55 (D390). Step 0: `forge prereg register` with a required n; the
`freeze-governance` pre-commit hook refuses a `grammar.yaml` content change without an open
prereg (`FORGE_FREEZE_REOPENER=D###` for a §5 reopener, with that D-entry staged).

The grammar (`config/grammar.yaml`) is operator-owned. Auto-tightenings apply
themselves; loosenings never do. To approve a refinement proposal:

```bash
forge grammar list-proposals --forge-db ~/forge_data/forge.db
forge grammar approve-proposal --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
# then edit config/grammar.yaml by hand, bump grammar_version, archive the prior
# version to config/grammar_archive/, and commit (pre-commit hook enforces this).
```

Full change procedure (worktree, tests, deploy ritual): `tasks/grammar-change.md`.

## Where things live

| Path | Contents |
|---|---|
| `~/optbt_data/inbox/` | Forge's submitted configs (`*.json`); `processed/` + `errors/` subdirs |
| `~/optbt_data/exports/` | Crucible snapshots: `gated_runs_*`, `promoted_strategies_*`, `registry_snapshot_*` |
| `~/optbt_data/refit_inbox/` | QuantIQ's quarterly re-validation requests |
| `~/optbt_data/runs.duckdb` | Crucible's results DB (writer-locked; never read directly) |
| `~/forge_data/forge.db` | Forge's own state (submissions, batches, proposals) |
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
