# MANPAGE: forge & pipeline commands

Reference for every `forge` CLI command, helper script, and pipeline service.
For operational workflow see `HOW-TO.md`.

---

## NAME

**forge** — candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

## SYNOPSIS

```
forge [GLOBAL OPTIONS] COMMAND [ARGS]
```

## GLOBAL OPTIONS

Apply to every command.

| Option | Type | Default | Description |
|---|---|---|---|
| `--log-level` | str | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `--json-logs` | flag | off | Emit structured JSON logs instead of console format. |

---

## COMMANDS

### forge version

Print Forge and `crucible_contracts` versions. No options.

```
forge version
```

### forge check

Validate that the installed `crucible_contracts` is compatible and that the DB
schema applies cleanly (tested in-memory). Run after any contracts bump.

```
forge check
```

### forge enumerate

Preview grammar-valid configs against the newest registry snapshot in
`~/optbt_data/exports/` (falls back to a built-in demo registry, with a warning,
when no export exists). Useful for eyeballing what the grammar produces. The
`(demo registry)` suffix in its output is a stale Phase-2 label either way —
trust the printed `registry_hash`.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `0` | RNG root seed (determinism). |
| `--max`, `-n` | int | `10` | Max configs to yield (min 1). |
| `--summary` | flag | off | Print per-rule rejection counts at the end. |

```
forge enumerate --seed 7 --max 50 --summary
```

### forge prefilter

Run the §5.2 pre-filter battery against enumerated candidates and report per-filter
pass/fail counts. Phase 3 diagnostic.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `0` | RNG root seed. |
| `--max`, `-n` | int | `10` | Max configs to run through the battery (min 1). |
| `--summary` | flag | off | Print per-filter rejection counts. |
| `--synthetic-cache` | flag | off | Force `SyntheticFeatureCache` instead of the Crucible-backed cache. Use for fast high-`--max` diagnostics. |

```
forge prefilter --max 500 --summary --synthetic-cache
```

### forge campaign

The weekly, zero-input challenger run — Forge's final state (plan 2026-09 §12; D406/D409).
`forge campaign` executes one week's decision end to end: boot checks (contracts pin, grammar +
archive, registry snapshot age, universe, gated/failed exports present, inbox backlog, open
preregistrations) → reconcile the gated/failed exports → read the designated book
(`designation_history`, `promoted_portfolios`, `component_contributions`) and Forge's own
per-cell verdict stats → evaluate the five triggers (T1 designation flip → replacement cells;
T2 refutation retraction, content-diff only; T3 new indicator id in an existing family; T4
near-floor cells with stale evidence; T5 dark-cell exploration on a deterministic weekly
rotation) → rejection-sample the UNCHANGED v55 population (cold-start draw, no learned weights,
seed derived from `(grammar_version, registry_hash, ISO week)`) to the chosen cells → prefilter
battery → structural challenger gate (protected book cells unless a replacement names them;
Jaccard signal overlap ≥ `duplicate_jaccard` to a book leg; dead cells) → in-cell rank by F3
`P(component)` × robustness `tail_norm` → submit at most `weekly_cap`. Rows carry
`selection_mode = campaign:<trigger>` locally and `selection_arm = ranked` to Crucible (their
09-13 §3). Knobs: `config/forge.yaml` `campaign:` over `forge.campaign.types.CampaignConfig`
(the single home of defaults; unknown keys fail loud).

`--dry-run` runs the same decision path and submits nothing; the record's `submitted_hashes`
then lists the plan, so two dry runs on the same exports compare plan for plan. `--budget N`
caps one run below the weekly cap. Path options (`--config`/`--no-config`, `--forge-db`,
`--inbox`, `--crucible-db`, `--exports-dir`, `--records-dir`, `--models-dir`, `--config-root`)
exist for hermetic runs; production passes none.

**Exit codes are the paging contract** for `forge-campaign.service` (no `SuccessExitStatus`):
0 = ok or no trigger (a no-trigger week still enumerates, proving the path boots), 2 = a boot
check failed (nothing submitted, a `boot_failed` record written), 1 = an error after boot (an
`error` record written, then re-raised).

**Run record** `~/forge_data/campaigns/<run_id>.json`, schema `campaign_run/v1` — the replay
key; Crucible's morning digest reads it once the daemon's journal lines stop:
`schema_version`, `run_id` (`<ISO week>-<UTC stamp>`), `started_at`/`finished_at` (ISO 8601),
`dry_run`, `status` (`ok` | `no_trigger` | `boot_failed` | `error`), `grammar_version`,
`registry_hash`, `enumeration_inputs_hash`, `seed`, `iso_week`, `watermarks`
(export → `<file>@<sha256[:12]>`), `boot` (name/ok/detail rows), `designated_id`, `triggers`
(trigger/fired/reason/campaign), `campaigns` (trigger/cells/budget/reason/replacement_for/
indicator_ids; cells are 5-element lists `[hypothesis, dte_bucket, axis, directional, regime]`),
`enumerated`, `kept_in_cells`, `survived_battery`, `gated_out` (reason → count), `submitted`,
`submitted_hashes`, `batch_id`, `baselines` (book_cells, refutation_hash/ids, registry_ids/
families — what the next run's T1/T2/T3 compare against), `notes`.

`forge campaign status [--last N] [--records-dir …] [--forge-db …]` prints recent runs newest
first (status, fired triggers, campaigns, funnel counts) and, given a DB, the verdicts each run's
submissions earned — point `--forge-db` at a `scripts/live_db_snapshot.sh` copy while a daemon
holds the live file.

Reconcile reads Crucible's **forge-scoped 14-day gated stream** (`forge_gated_runs_*.json`, contracts
1.48.0, via `load_forge_gated_runs_from_export` — never by glob, the all-source `gated_runs_*` glob
would collide) so a run that boots cold still sees its prior run's verdicts. While the daemon runs the
file reads `truncated: true` (its rate floods the 10k cap; the OLDEST verdicts are the missing ones)
and the run skips the D052 aged-out flush; after the cutover every file must read `truncated: false`
— a truncated file then means something else is flooding `source='forge'` and is worth a relay
(D412). An absent stream falls back to the all-source export and says so in the record.

**In-run training (Batch 5 G0).** After reconcile the run trains the two model families its
ranking loads — the verdict model and the robustness model for `ranking.model.QUALITY_LANE_TARGET`
— from `forge.db` directly, publishes each atomically (staging + rename) into `--models-dir`, then
prunes every artifact family to the newest `campaign.models_keep` (default 4; REL-12). A fit that
refuses (thin rows) or fails is a `notes` entry and the run ranks on the previous artifact — never a
crash. The trained ids land in the record's `models` field. `--skip-train` ranks on the newest
existing artifacts (hermetic/diagnostic runs). The boot check `preregistrations` is the DUE judge
that was `forge-prereg-watch`: an open registration whose clock has come due, or one with no
`watch: {n, basis_fp}` clock at all, FAILS the boot (exit 2, unit FAILED) — a registered read must
not come due silently (D389/D392).

Units: `forge-campaign.timer` (Sunday 03:00 UTC) → `forge-campaign.service` →
`scripts/campaign_run.sh`. The unit's `Environment=FORGE_CAMPAIGN_MODE` is the one operator decision it
carries: `live` since the 2026-09-14 cutover (D416) — the run submits what the triggers select;
`dry-run` made the wrapper snapshot the DB and plan only (the pre-cutover weeks, D411). The wrapper
refuses any other value. `MemoryHigh=32G` / `MemoryMax=48G` (the run trains its models in-process,
25-27 GB peak measured, D417) fail the unit rather than starve Crucible. No `SuccessExitStatus`: a
failed unit is the only page.

The one env knob the run itself reads is `FORGE_REFUTATION_GUARD` (default on): `off` disables the
D320 refutation routing in the enumerator and therefore CHANGES `enumeration_inputs_hash` — it is a
kill-switch for a Crucible-registry incident, not a tuning knob; leave it unset.

```
forge campaign --dry-run            # decide + rank, submit nothing, write the record
forge campaign                      # the weekly run (what the timer executes)
forge campaign status --last 4
```

### forge prereg

Pre-register a prune/retarget, then confirm it on a *later* cohort (Tier-1a honesty discipline,
D208). The §8.4 auto-tightening triggers — and most manual prunes — observe a pattern in a cohort
and act on the same cohort that revealed it (post-selection bias). `forge prereg register` records
the claim with a `--cohort-cut`; only data after the cut may confirm it, and `forge prereg resolve`
takes operator-supplied post-cut evidence. The registry is a git-tracked JSONL
(`config/preregistrations.jsonl`) so the prediction is committed before its test; the
`confirm_promotion_claim` guard (in `forge.feedback.preregistration`) structurally drops pre-cut
rows for programmatic callers. Read/write only — no production-loop or grammar change.

```
forge prereg register --claim "adx<10 never promotes" --predicted "<= 0.005" \
    --action "tighten adx lower bound" --cohort-cut 2026-06-25T00:00:00
forge prereg list --open-only
forge prereg resolve <id> --outcome confirmed --evidence "post-cut rate 0.002 (n=120)"
```

---

## SCRIPTS

Run via `.venv/bin/python scripts/NAME.py` from the Forge repo root.

### backup_forge_db.sh

**Bash, not Python** — the `ExecStart` of the `forge-backup` timer (Sunday 04:30 UTC, after the
campaign run; nightly until Batch 5 G0), runnable by hand too. Disaster-recovery backup of the non-git state. `cp`s the live `forge.db`
between write bursts, **validates** the copy (opens it read-only and queries `submissions`; a torn
mid-write copy fails and retries ≤3×), then publishes it via atomic same-fs rename as
`forge_db_<UTC>.duckdb`; `~/forge_data/models/` is tar.gz'd alongside. Retention keeps the newest
`FORGE_BACKUP_KEEP` (default 14) of each and prunes **only after** a validated new backup exists, so
a failed run never deletes the last good one. Validation uses the venv python directly (no `forge`
import) so a broken deploy can't break the backup. Env knobs: `FORGE_BACKUP_DEST` (default
`~/forge_data/backups` — **same-disk**; point at a mounted external/remote target for true off-box
DR), `FORGE_BACKUP_KEEP`, `FORGE_BACKUP_MIN_FREE_MB`. Deterministic-loop rules don't apply (ops glue,
not `src/`); reverting = disable the timer. No args.

```
scripts/backup_forge_db.sh          # or: systemctl --user start forge-backup.service
```

### deploy_preflight.sh

**Bash** — a read-only GO/NO-GO gate for the D104 deploy ritual (`docs/tasks/deploy.md`),
run before committing + restarting. Checks (1) the git tree is clean (uncommitted tracked
changes deploy on reboot) and (2) the FULL suite passes — which covers the contracts-pin
equality test (D176) and the loop/single-iteration forward tests (D185), so a green suite
proves pin-adoption + anti-inertness in one shot. Exit 0 = GO (prints the stop→restart
steps); non-zero = NO-GO (prints the blocking reason). Never stops/starts the service or
mutates the tree. No args.

```
scripts/deploy_preflight.sh
```

### check_grammar_version_bump.py / check_grammar_doc_sync.py

Pre-commit hooks (no CLI args). The first enforces that a changed `grammar.yaml`
bumps `grammar_version` and archives the prior version. The second keeps
`grammar.yaml` rule IDs and `docs/GRAMMAR.md` headings in sync.

### Full scripts inventory (every file in `scripts/`, classed)

**Standing rule (2026-08-06): a one-off analysis script is DELETED with a retirement-ledger
row below once its D-entry lands** — the conclusion lives in the ledger, the code in git
history. `scripts/` holds only wired, ritual, and in-flight instruments.

| Class | Scripts |
|---|---|
| WIRED — machinery executes them | `backup_forge_db.sh` (Sun 04:30 UTC timer), `check_grammar_version_bump.py` + `check_grammar_doc_sync.py` + `check_freeze_governance.py` (pre-commit), `freeze_read_watcher.py` (06:30 `forge-prereg-watch` timer), `deploy_preflight.sh` (deploy step 0), `live_db_snapshot.sh` (the blessed DB-snapshot idiom), `campaign_run.sh` (the `forge-campaign` timer's ExecStart: mode-guarded dry-run/live wrapper, D411) |
| RITUAL / standing monitor | `tail_verified_alignment.py` (D155 verified-coverage alignment monitor; run against a `live_db_snapshot.sh` snapshot), `production_by_group.py` (per-arm/per-category production reads) |
| IN-FLIGHT freeze/ceiling instruments | `ceiling_record_test.py`, `joint_frontier.py` (D368), `second_gate_contrast.py` (carries the D360 measurement_basis pooling defect — repair queued in the freeze declaration), `threshold_resolution_value.py` (D353), `promoted_leg_recall.py` |

Retired 2026-07-05 (D241 follow-through; recoverable from git history): `signal_correlation_regime_pair_audit.py` (D227 evidence), `decorrelation_proxy_alignment.py` (D186), `wf_quality_probe.py` (D186→D189).
Retired 2026-07-20 (D295 post-promotion sweep; recoverable from git history, tests removed with them): `backfill_verdicts.py` (D111 one-time catch-up, completed), `migrate_verdicts_decided_at.py` (D117 one-time era repair, completed), `requeue_high_value_configs.py` (one-off recovery, completed), `probe_option_momentum_min_months.py` (Q39 one-shot probe + its `probe_results/` output; Q39 resolved at v19/D138).
Retired 2026-07-20 (D298 — D206 made permanent): `propose_threshold_tightenings.py` + `forge.feedback.threshold_proposer` (D073 threshold-range proposer; the axis measured flat on CPCV-p25, monoculture risk; `auto_tightened_thresholds.yaml` stays empty and the reader/fingerprint stay — determinism-load-bearing).
Retired 2026-08-06 (repo-simplification Step C; conclusions all shipped and D-cited): the tail-target sweep chain `exceedance_target_sweep.py`, `exceedance_extreme_sweep.py`, `exceedance_merge_sweep.py`, `wf_blend_sweep.py`, `wf_p10_validation.py`, `sharpe_baseline_nested_test.py`, `tail_target_headtohead.py`, `tail_lane_tradeoff.py`, `trend_tail_target_sweep.py`, `target_sweep.py` (→ the live `FORGE_TAIL_LANE_SLOTS`/`FORGE_TREND_LANE_SLOTS` values + the cpcv retarget, D336/D345-era); the winner-prior trio `winner_prior_signal_probe.py`, `winner_prior_shadow.py`, `winner_prior_stage_one.py` (programme parked, prereg `916d79109b4d` refuted); `collider_fix_sweep.py` (Q59 → `FORGE_HONEST_LABEL_SCOPE=off`); `vix_conditioner_stage_decomposition.py`, `resid_vix_construct_split.py` (D339; superseded by the inline share computation in `daily_ranker_eval.sh`); the freeze-prep set `tail_lane_model_era_split.py`, `trend_lane_arm_read.py`, `exhaustion_power_assessment.py`, `honest_cell_scorecard.py`, `export_generation_by_version.py`, `tail_target_rank_ic.py` (preregs resolved / Tier-1 A/B closed D351).
Retired 2026-08-06 (Step E2, D373 — the alpha-budget question is ANSWERED): `forge alpha-budget` (`feedback/alpha_budget.py` + `cli/alpha_budget_cmd.py` + tests) and `scripts/alpha_budget.py`. Its prereg `098ea730d5f2` resolved confirmed 2026-07-21; the exhaustion monitor it closed cannot reopen (dossier §0); the *standing* multiplicity accounting lives in `submission/search_multiplicity.py` (D310), which is unrelated code and stays. Spec/results record: `_archive/ALPHA_BUDGET_SCOPE.md`.
Retired 2026-09-14 (Batch 5 G0 — the daemon era's timers folded into the weekly run; recoverable from git history, tests removed with them): `daily_ranker_eval.sh` (the 05:00 trainer — `forge campaign` now trains the two families it loads in-run, step 0.5, and prunes artifacts per `campaign.models_keep`; the streak clocks, campaign-carriage audit, activation probe, freeze census and vix-share rows had no consumer left), `search_multiplicity_census.py` (freeze metric B — the freeze is signed and hook-enforced, §8.4), `freeze_read_watcher.py` (its DUE/UNWATCHABLE judge is the boot check `preregistrations`, `feedback.preregistration.assess_watch_clocks`), `freeze_registered_read.py` + `freeze_tail_reading.py` (the registered-read instruments; a §5 reopener brings its own, §8.7), `cutover_campaign.sh` + `arm_cutover.sh` (the Route C cutover ran 2026-09-14T23:52:05Z, D416). Units retired with them: `forge-ranker-eval.{service,timer}`, `forge-prereg-watch.{service,timer}`, `forge-cutover.{service,timer}`.

---

## CONFIG FILES

Under `config/`. CLI flags override YAML; YAML overrides hardcoded defaults.

| File | Controls |
|---|---|
| `forge.yaml` | Three keys (D422): `db_path` (Forge's DuckDB), `crucible.inbox_path` (where the weekly run writes), and the optional `campaign:` overrides for `forge.campaign.types.CampaignConfig` (every field has a default there; unknown keys fail loud). The schema is `extra="forbid"`: the daemon-era keys (`enumeration.*`, `submission.*`, `crucible.db_path` — Crucible is read only through its exports, hard rule #2) fail loud if re-added. |
| `grammar.yaml` | The 21 grammar rules (S/C/R/X families). Operator-owned; version-bumped + archived on change. |
| `prefilter.yaml` | Per-filter thresholds (signal density, expected trades, predicted activations, novelty, signal correlation, regime exposure, permutation test). Operator-owned; nothing writes it (the auto-tune trigger and its `auto_tune:` key left with the daemon, D422). |
| `auto_tightened_thresholds.yaml` | RETIRED-EMPTY (`tightenings: []`, D206, permanent per D298). Retained because its fingerprint feeds `enumeration_inputs_hash` — deleting it changes the determinism identity. |
| `grammar_archive/v{N}.yaml` | Frozen copies of each prior grammar version. |

---

## FORGE STATE DB

`~/forge_data/forge.db` (DuckDB). Tables:

| Table | Holds |
|---|---|
| `submissions` | One row per submitted config. `config_hash` is unique-indexed (idempotency, hard rule #9). `status` lifecycle: `pending` (insert) → `submitted` \| `skipped_duplicate` \| `submission_failed`, then `gated` once Crucible decides — set on reconcile, on age-out, or on the D240 failed-run retirement (runner-FAILED runs from `failed_runs_*.json` are retired each poll with the aged-out sentinel `crucible_run_id`; `feedback/consumer.py`). `selection_mode` (P3.3/B7) tags each row `ranked` vs `holdout` so evals can split biased-vs-unbiased labels. |
| `batch_summaries` | Per-batch stats: size, grammar/registry version, promotion rate, prefilter rejections. |
| `pre_filter_logs` | Per-(candidate, filter) pass/score/details. |
| `verdicts` | Durable per-candidate Crucible decisions (D111): decision, decided_at, trade_count, grammar_version, full gate_results JSON. PK `crucible_run_id`, so re-gates append. Populated on every reconcile pass; survives the rolling export window. |
| `grammar_versions` | Grammar change history (version, sha256, operator initials). |
| `grammar_proposals` | Daemon-era refinement proposals. No writer since D420 (Batch 5 G3); kept for old DBs. |
| `promoted_patterns` | Daemon-era pattern rows (8 ever). No writer since D420; kept for old DBs. |
| `shadow_scores` | D132/F2 telemetry: per (submitted candidate, model_id) the verdict model's P(component) next to the incumbent §6.2 composite. D140/D141 add `tail_score` + `tail_model_id` (the tail-aware model's predicted worst-quartile value — `wf_p25` per D191/D192, NULL until one is trained). Written post-submission; never read by the loop. |

---

## PIPELINE SERVICES

systemd **user** services (`systemctl --user ...`). Start the writer first; stop it last.
The Crucible rows below are the **Forge-relevant subset**, not Crucible's full unit inventory —
`systemctl --user list-unit-files 'crucible-*'` for the whole set.

| Service | Runs | Role |
|---|---|---|
| `crucible-db-writer` | `start_db_writer.py` | Single-writer DuckDB process; holds the exclusive lock. All others depend on it. |
| `crucible-inbox-watcher` | `start_inbox_watcher.py` | Polls `inbox/`, validates configs, queues runs. |
| `crucible-runner@1` / `crucible-runner@2` | `start_runner.py` (templated instances) | Backtest queued runs through the full gate; write promotion decisions. Production runs the templated instances; the plain `crucible-runner.service` is inactive. |
| `crucible-gated-runs-publisher` | `export_gated_runs.py --poll-interval 60` | Exports gated-run snapshots every 60s (Forge's read path). |
| `crucible-failed-runs-publisher` | `export_failed_runs.py --poll-interval 300` | Exports `failed_runs_*.json` — runner-FAILED runs that never reach the gated export. Forge's D240 read path: the feedback consumer retires matching `submitted` rows each poll (`feedback/consumer.py` `_flush_failed_runs`) so failures stop pinning §7.3 in-flight depth. |
| `crucible-promoted-strategies-publisher` | `export_promoted_strategies.py --poll-interval 60` | Exports promoted strategies every 60s (QuantIQ's read path). |
| `crucible-component-contributions-publisher` | `export_component_contributions.py --poll-interval 60` | Exports per-promoted-portfolio contribution scores (D216); consumed by `forge healthcheck`'s soft presence check — empty until the first promotion. |
| `crucible-registry-publisher` | `export_registry.py` | Publishes the indicator registry snapshot every ~6h (timer-driven oneshot, D166; was oneshot-at-startup pre-2026-06-15). Forge re-reads the newest snapshot by mtime. |
| `crucible-universe-publisher` | `export_universe.py` | Timer-driven oneshot publishing `universe_tickers` (the underlying set enumeration draws from). |
| `crucible-refit-watcher` | `start_refit_watcher.py` | Polls `refit_inbox/` for QuantIQ re-validation requests. |
| `forge` | RETIRED 2026-09-14 (D416) | The Forge daemon (`forge run --loop …`) is gone; the weekly `forge-campaign.timer` is the pipeline (plan 2026-09 §12). |

Timers (independent): `crucible-ingest-daily` (19:00, market data), `crucible-morning-digest` (06:00). **Forge timers:** `forge-campaign` (Sunday 03:00 UTC, `scripts/campaign_run.sh`, mode `live` since the 2026-09-14 cutover, D416) and `forge-backup` (Sunday 04:30 UTC, `scripts/backup_forge_db.sh` → `~/forge_data/backups`; retention `FORGE_BACKUP_KEEP` on the unit). `forge-ranker-eval`, `forge-prereg-watch`, `forge-healthcheck` and the daemon itself are retired (Batch 5).

```
# Inspect any service:
systemctl --user status SERVICE
journalctl --user -u SERVICE -n 50 --no-pager
```
