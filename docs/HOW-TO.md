# HOW-TO: Running the Pipeline

Operator guide for the **Forge → Crucible → QuantIQ** pipeline. For per-command
details see `MANPAGE.md`.

## The pipeline in one breath

Forge generates candidate option strategies → writes them to Crucible's inbox →
Crucible backtests + gates them → publishes results → Forge learns and refines.
Promoted strategies flow to QuantIQ for live/paper trading.

```
Forge ──inbox/*.json──► Crucible ──exports/gated_runs──► Forge (feedback)
                            │
                            └──exports/promoted_strategies──► QuantIQ
```

All inter-system communication is **files under `~/optbt_data/`** — no direct DB
sharing. Everything runs as **systemd user services**.

## Start everything

Order matters: the DB writer holds the exclusive lock and must come up first.

```bash
# 1. Crucible foundation (writer first, then everything else)
systemctl --user start crucible-db-writer.service
systemctl --user start crucible-registry-publisher.service   # timer-driven oneshot (~6h republish, D166)
systemctl --user start crucible-inbox-watcher.service
systemctl --user start crucible-runner@1.service crucible-runner@2.service   # templated; plain crucible-runner.service is unused
systemctl --user start crucible-gated-runs-publisher.service
systemctl --user start crucible-failed-runs-publisher.service    # D240: Forge retires runner-FAILED runs from this export
systemctl --user start crucible-promoted-strategies-publisher.service
systemctl --user start crucible-universe-publisher.service      # timer-driven oneshot (universe_tickers)
systemctl --user start crucible-component-contributions-publisher.service
systemctl --user start crucible-refit-watcher.service

# 2. Forge (safe to start last; retries if inbox not ready)
systemctl --user start forge.service
```

Check it all came up:

```bash
systemctl --user list-units 'crucible*' 'forge*'
```

## Stop everything

Reverse order — stop readers/publishers first so the writer drains cleanly.

```bash
systemctl --user stop forge.service
systemctl --user stop crucible-runner@1.service crucible-runner@2.service crucible-inbox-watcher.service crucible-refit-watcher.service
systemctl --user stop crucible-gated-runs-publisher.service crucible-failed-runs-publisher.service crucible-promoted-strategies-publisher.service crucible-component-contributions-publisher.service
systemctl --user stop crucible-db-writer.service
```

## Daily health check

```bash
# One-shot daemon health — alive AND productive (exit 0/1/2 = OK/WARN/CRITICAL). The
# forge-healthcheck timer runs this hourly; only a CRITICAL fails the unit (WARN is
# informational), so a WARN won't show in --state=failed — read the journal for it.
(cd ~/proj/Forge && uv run forge healthcheck)

# Are all services alive? (forge-healthcheck shows here on CRITICAL)
systemctl --user list-units 'crucible*' 'forge*' --state=failed

# Is Forge submitting / rate-limited?
journalctl --user -u forge.service -n 20 --no-pager

# Is Crucible processing? (templated runner instances)
journalctl --user -u crucible-runner@1.service -n 10 --no-pager

# Are exports fresh? (should be < 2 min old)
ls -lt ~/optbt_data/exports/gated_runs_*.json | head -1

# Is the stream improving? Curated learning clocks (no tail|json spelunking)
(cd ~/proj/Forge && uv run forge status)
journalctl --user -u forge-ranker-eval.service -n 20 --no-pager

# Last nightly backup fresh? (forge-backup timer, 04:00)
ls -lt ~/forge_data/backups/forge_db_*.duckdb | head -1
```

The `forge-ranker-eval` timer trains + evaluates the shadow verdict model each morning and records
the consecutive-PASS streak; the streak files are telemetry-only — they track *whether the learning
is improving*, not what the daemon submits (the live ranker/quality-lane models are loaded on their
own paths). `forge status` pretty-prints both clocks; don't hand-run train/eval at checkpoints
anymore. Deeper digging (forge.db queries, cohort analysis, known traps): `tasks/investigate-live.md`.

## Common situations

### Forge says "blocked: ... 0% gated, waiting for >=80%"

Forge won't submit a new batch until 80% of the previous batch has been gated by
Crucible. This is the rate limiter (correct behavior). If it's stuck for hours:

1. **Check the publisher is alive** — Forge reads gated state from exports, not
   the DB. A dead publisher = stale exports = permanent block.
   ```bash
   systemctl --user status crucible-gated-runs-publisher.service
   systemctl --user restart crucible-gated-runs-publisher.service   # if failed
   ```
2. **Check the runner is making progress** — if Crucible has a deep backlog the
   batch may simply not be reached yet.
   ```bash
   journalctl --user -u crucible-runner@1.service -n 5 --no-pager
   ```
3. **Skip a stale batch** if it predates a code change and you don't need its
   results (stop Forge, mark its rows `skipped`, restart):
   ```bash
   systemctl --user stop forge.service
   python -c "
   import duckdb; from pathlib import Path
   db = duckdb.connect(str(Path.home()/'forge_data/forge.db'))
   db.execute(\"UPDATE submissions SET status='skipped' WHERE forge_batch_id='<UUID>' AND status='submitted'\")
   db.close()"
   systemctl --user start forge.service
   ```

### Forge says "blocked: crucible stalled — no decisions since …"

A *different* block from the one above (D137 stall guard, `submission.stall_after_seconds`,
default 3 h). It means Crucible has had Forge's work in its queue for ≥3 h and decided
nothing — its decision clock (`max(decided_at)`) is stale while configs submitted after it
sit pending. This is the guard working: it stops Forge from pouring thousands of configs
into a gate that has gone quiet (the 2026-06-10 wedge). It **self-clears** the moment one
fresh decision lands — no intervention needed once Crucible recovers.

What to do: this points upstream, not at Forge. Diagnose the runner (is it wedged? a
`futex_do_wait` at 0% CPU with byte-identical exports is the signature), restart it if
needed, and relay a wedge prompt (`PROMPT_CRUCIBLE_RUNNER_WEDGE.md` is the template). Do
**not** lower `stall_after_seconds` to "unblock" — that just resumes feeding the dead gate.

### Forge says "blocked: in-flight depth N exceeds cap M"

The §7.3 backpressure block (`submission.max_inflight`, deployed ON per D196/D200): the
*aggregate* learnable queue — genuine in-flight `submitted` rows newer than the D110 flush
watermark, summed across all batches — exceeds the cap. Unlike the per-batch "N% gated"
line, it fires even when the oldest batch reads ≥80% (a permanent zombie batch can't mask
it). It means Crucible is draining slower than Forge submits; Forge is correctly waiting so
the queue stays shallow enough to learn from. It self-clears as Crucible drains below the cap.

Since D240 the feedback consumer also auto-retires runner-FAILED runs each poll (from
Crucible's `failed_runs_*.json` export), so failures no longer sit `submitted` and pin the
depth metric for days. A *persistent* depth block therefore points at either the
`crucible-failed-runs-publisher` being down (failed runs invisible again) or a genuine
Crucible backlog. To diagnose which, join forge.db's `submitted` rows against Crucible's
`run.status` / the failed_runs export on `config_hash` (the D205/D240 join —
`docs/tasks/investigate-live.md`).

What to do: usually nothing — it's the throttle working. If it blocks persistently, Crucible
is the bottleneck (see the stall guidance above / diagnose the runner), not Forge. To retune,
raise/lower `submission.max_inflight` in `config/forge.yaml` (0 = disable; the live value is set
at ≈3× batch_size per D200). Don't disable it to "unblock" — that just re-deepens the un-learnable
queue. Changing it is a config edit that deploys on restart — run the deploy ritual (below).

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

Nightly backups land in `~/forge_data/backups/` (the `forge-backup` timer, 04:00): validated
`forge_db_<UTC>.duckdb` snapshots + `models_<UTC>.tar.gz`; the newest `FORGE_BACKUP_KEEP` are
kept (set on the unit, `deploy/systemd/forge-backup.service`; script default 14). To restore:

```bash
systemctl --user stop forge.service          # release the writer's lock on forge.db
LATEST=$(ls -1 ~/forge_data/backups/forge_db_*.duckdb | sort | tail -1)
# verify it opens before swapping:
~/proj/Forge/.venv/bin/python -c "import duckdb,sys; print(duckdb.connect(sys.argv[1],read_only=True).execute('select count(*) from submissions').fetchone())" "$LATEST"
cp -- "$LATEST" ~/forge_data/forge.db        # overwrite the corrupted/lost DB
# models, if needed: tar -xzf "$(ls -1 ~/forge_data/backups/models_*.tar.gz | sort | tail -1)" -C ~/forge_data
systemctl --user start forge.service
```

Caveat: same-disk backups don't survive a *physical disk* failure — for that, `FORGE_BACKUP_DEST`
must point at a mounted off-box target (see `backup_forge_db.sh` in `MANPAGE.md`).

### Tune the generator from real results

After a few hundred new gated runs accumulate, retrain the threshold ranges:

```bash
cd ~/proj/Forge
.venv/bin/python scripts/propose_threshold_tightenings.py   # writes config/auto_tightened_thresholds.yaml
scripts/deploy_preflight.sh                                  # D199 GO/NO-GO gate (tree clean + full suite)
systemctl --user restart forge.service                       # pick up new ranges (only on GO)
```

Any change that deploys on restart (config edits, new ranges, code) should clear
`scripts/deploy_preflight.sh` first — it's step 0 of the deploy ritual (`tasks/deploy.md`).
Review any **loosening** proposals (these need operator sign-off) in `OPEN_PROPOSALS.md`.

### Changing the grammar

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
| `~/forge_data/backups/` | Nightly DR snapshots of `forge.db` + `models/` (`forge-backup` timer, 04:00; retention = `FORGE_BACKUP_KEEP` on the unit) |

## Manual runs (without the daemon)

```bash
cd ~/proj/Forge

forge check                      # sanity: contracts + DB schema
forge enumerate --max 20 --summary    # preview generated configs (no submission)
forge run --dry-run --max 100         # full cycle, no inbox writes
forge run --inbox ~/optbt_data/inbox --forge-db ~/forge_data/forge.db   # one real batch
```

See `MANPAGE.md` for every command and flag.
