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

### forge king

Meta-king generator (FORGE meta-king A3). Reads Crucible's published durable-score
oracle (`~/optbt_data/exports/meta_king_oracle_latest.json`), searches `--search`
grammar-valid genomes, scores each with the oracle, dedups against the gated-runs
export, and ranks the top-`--top-k` by predicted `cpcv_sharpe_p25` ("kings").

**Without `--submit` it is a DRY-RUN preview** (writes nothing to Crucible).
**With `--submit`** it stamps each king `source="meta_king"` + `search_n_trials=N`
(both hash-excluded in contracts 1.19.0 → `config_hash` unchanged), records them in
Forge's `submissions`/`batch_summaries` (idempotent on the `config_hash` unique
index, hard rule #9), and writes them to Crucible's inbox — where they run the
full, unchanged §8.7 gauntlet as proposals (hard rule #3/#6). `--search` is the
DSR trial count `N` Crucible folds into the single-config DSR (the A3 §4
trial-laundering guard). Kings are realistically portfolio **components**, not
promoted standalones (oracle max predicted ~0.78 « the 1.5 promotion wall). The
unbiased oracle-argmax is a `mean_reversion/swing_short` monoculture, so pass
`--per-cell` when submitting to queue a decorrelated set.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `0` | RNG root seed (determinism, hard rule #6). |
| `--search`, `-n` | int | `2000` | Genomes to score against the oracle (the DSR trial count `N`; min 1). |
| `--top-k`, `-k` | int | `10` | Number of kings to surface (min 1). |
| `--oracle` | path | latest published | Override the durable-score oracle JSON. |
| `--out` | path | stdout only | Also write the kings (with full configs) as JSON here. |
| `--no-dedup` | flag | off | Skip the gated-export dedup pass. |
| `--per-cell` | int | `0` | Diversity quota: max kings per `(hypothesis,dte)` cell (`0` = global top-K). Use a small cap (e.g. 2) to break the oracle-argmax monoculture into a decorrelated set. |
| `--submit` | flag | off | Submit the kings to Crucible's inbox + record them (default: dry-run). |
| `--inbox` | path | forge.yaml | Crucible inbox dir for `--submit` (else `crucible.inbox_path`). |
| `--forge-db` | path | forge.yaml | Forge state DB for `--submit` (else `db_path`). |
| `--config` | path | — | `forge.yaml` path for the `--inbox`/`--forge-db` fallback under `--submit`. |

```
forge king --search 2500 --top-k 15 --seed 1 --per-cell 3            # dry-run preview
forge king --search 2500 --top-k 15 --per-cell 3 --submit \
  --inbox ~/optbt_data/inbox --forge-db ~/forge_data/king_submissions.db
```

**Live-fire routing (D178):** point `--inbox` at the real inbox but `--forge-db` at a
**separate** king DB — NOT the shared `forge.yaml` `db_path`. The `forge.service`
daemon holds an intermittent RW lock on the live `forge.db`, so a second writer there
would collide; the separate king DB also keeps `meta_king` submissions out of the forge
ranker's feedback (arms-independent). Vary `--seed` across fires to grow the stream
(same seed → same kings → idempotent skip).

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

### forge run

The full cycle: enumerate → prefilter → rank → submit. With `--loop` it runs as a
daemon; with `--consume-feedback` it runs the feedback chain after each submit.
This is what `forge.service` runs.

Config precedence: `--config` YAML (`config/forge.yaml`) → CLI flags override →
hardcoded fallback (used only with `--no-config`). The Default column shows the
shipped YAML value, with the `--no-config` fallback in parentheses.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `42` (`0`) | RNG root seed. |
| `--batch-size` | int | `200` (`10`) | Top-N ranked candidates to submit. |
| `--max`, `-n` | int | `5000` (`1000`) | Enumeration cap before pre-filtering (min 1). |
| `--inbox` | path | — | Crucible inbox dir. Required unless `--dry-run`. |
| `--crucible-db` | path | — | Crucible runs DB (rate limiter, §7.3). |
| `--forge-db` | path | in-memory | Forge state DB. Pass a file path for persistence. |
| `--dry-run` | flag | off | Run pipeline but skip inbox writes + DB persistence. |
| `--loop` | flag | off | Daemon mode: repeat, sleeping `--poll-interval-seconds` between cycles. |
| `--max-iterations` | int | unbounded | Cap loop iterations (testing). |
| `--poll-interval-seconds` | int | `60` (`600`) | Sleep between loop iterations. |
| `--consume-feedback` | flag | off | Run feedback chain (consumer/analyzer/proposer/auto-tune) after submit. |
| `--open-proposals` | path | `OPEN_PROPOSALS.md` | Where loosening proposals are written. |
| `--prefilter-yaml` | path | `config/prefilter.yaml` | Prefilter calibration (auto-tune target). |
| `--config` | path | `config/forge.yaml` | YAML defaults file. |
| `--no-config` | flag | off | Ignore YAML; use hardcoded defaults + CLI flags only. |

```
# One real batch, persisted:
forge run --inbox ~/optbt_data/inbox --forge-db ~/forge_data/forge.db --batch-size 200

# Daemon (what the service runs):
forge run --loop --consume-feedback

# Dry run, no side effects:
forge run --dry-run --max 100
```

**§7.3 backpressure (yaml-only knobs under `submission:`).** Before each batch the loop
asks `check_rate_limit` whether to submit; it can block for two independent reasons:

- **Completion fraction** (`inflight_threshold`, default `0.80`): wait until ≥80% of the
  oldest in-flight batch is gated. Journal: `blocked: oldest in-flight batch … N% gated`.
- **Stall guard** (`stall_after_seconds`, default `10800` = 3 h; `0` disables — D137): block
  when Crucible has had new work in its queue for ≥ that long and decided nothing (the
  decision clock `max(decided_at)` is stale while configs submitted after it sit pending).
  Catches the wedge the completion fraction misses — a 99%-gated front batch while newer
  configs pile into a dead gate. Stateless and deadlock-immune (a clock left stale by
  Forge's *own* quiet has no submission postdating it, so the guard stays silent). Journal:
  `blocked: crucible stalled — no decisions since <ts> (<X.X>h); <N> configs pending ≥3h`.

### forge feedback

Manual single-batch feedback: read Crucible's gated runs, analyze, propose grammar
refinements. Auto-tune always runs. (Daemon equivalent: `forge run --consume-feedback`.)

| Option | Type | Default | Description |
|---|---|---|---|
| `--batch-id` | str | latest | Explicit batch UUID to analyze. |
| `--since` | str | batch time | ISO datetime cutoff for Crucible runs. |
| `--config` | path | `config/forge.yaml` | YAML defaults. |
| `--no-config` | flag | off | Skip YAML; require explicit paths. |
| `--forge-db` | path | yaml | Override Forge DB path. |
| `--crucible-db` | path | yaml | Override Crucible DB path. |
| `--open-proposals` | path | `OPEN_PROPOSALS.md` | Proposal audit file. |
| `--prefilter-yaml` | path | `config/prefilter.yaml` | Prefilter calibration. |

```
forge feedback --batch-id 1a41005f-... --forge-db ~/forge_data/forge.db
```

### forge ranker-model dataset

Build the learned verdict model's honest-era training frame (D132 / F1):
`verdicts ⋈ submissions` on config_hash, rows hard-cut at the clean-era label
boundary, label = component/promote AND D128-honest coverage, one feature
column per emitted feature name (wide, missing → 0.0). The live forge.db holds
an intermittent RW lock — point `--forge-db` at a `/tmp` snapshot.

| Option | Type | Default | Description |
|---|---|---|---|
| `--out` | path | required | Output parquet path. |
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override (naive = UTC). |

```
cp ~/forge_data/forge.db /tmp/forge_snap.db
forge ranker-model dataset --forge-db /tmp/forge_snap.db --out /tmp/verdict_dataset.parquet
```

### forge ranker-model train

Train the verdict model on the honest era and save the artifact (D132 / F2 —
manual, run at the daily checkpoints). Refuses datasets under 50 rows / 5
positives. Artifacts are append-only canonical JSON with coefficients by
feature name; the daemon shadow-scores against the newest artifact in
`<forge_data>/models/` from its next batch (telemetry only until F3).

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML defaults (db_path, models dir). |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override. |
| `--lambda` | float | 1.0 | L2 regularization strength. |
| `--models-dir` | path | `<config db_path parent>/models` | Artifact dir (NOT derived from `--forge-db` — that's a snapshot). |

### forge ranker-model train-robustness

Train the tail-aware T1 model (D140) — a deterministic ridge fit predicting a
continuous worst-quartile gate value (default `cpcv_sharpe_p25`) instead of
P(component). Same honest-era dataset, manual at the daily checkpoints; refuses
when under 50 rows carry the target. Saves an append-only `robustness_model_*.json`
artifact. Offline/analysis-side — does NOT shadow-score in the daemon yet (deferred,
daemon-gated; see `docs/proposals/tail-aware-ranker.md`). Design: §8.3 / §1.2 (Forge
consumes Crucible's `gate_results` values, computes none).

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML defaults (db_path, models dir). |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override. |
| `--lambda` | float | 1.0 | L2 regularization strength. |
| `--target` | str | `target_cpcv_p25` | Continuous gate value to predict (`target_wf_median`, `target_regime_stress`). |
| `--models-dir` | path | `<config db_path parent>/models` | Artifact dir (NOT derived from `--forge-db`). |

### forge ranker-model eval

Shadow vs incumbent readout on decided verdicts (the F3 criterion: model AUC ≥
incumbent + 0.05 AND precision@K ≥ incumbent's, on ≥3 consecutive daily
checkpoints of ≥150 fresh verdicts each). Prints AUC/precision@K/Brier and a
calibration table per model_id.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--since` | str | clean-era boundary | ISO window start (naive = UTC). |

```
cp ~/forge_data/forge.db /tmp/forge_snap.db
forge ranker-model train --forge-db /tmp/forge_snap.db
forge ranker-model eval --forge-db /tmp/forge_snap.db --since 2026-06-11T00:00:00Z
```

### forge ranker-model eval-robustness

Tail-aware (T1, D143) readout: does ranking by the predicted `cpcv_p25` (the D141 `tail_score`)
surface configs with higher REALIZED worst-quartile robustness? Per `tail_model_id`, over
verified-coverage decided verdicts, prints **Spearman(tail_score, realized `cpcv_p25`)** and
**top-K mean realized `cpcv_p25`** (tail model vs the incumbent composite). No PASS/FAIL — the
§8.6 criterion margin is set once the shadow distribution is visible. Reports "not yet accruing"
until the D141 shadow code is live (post-restart) and a robustness model has scored batches.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--since` | str | clean-era boundary | ISO window start (naive = UTC). |

**Automated daily** by the `forge-ranker-eval` systemd timer (05:00; `scripts/daily_ranker_eval.sh`)
— it snapshots the DB, trains BOTH shadow models (`train` for P(component) + `train-robustness`
for the tail-aware `cpcv_p25` model, D142; each atomic-published to `~/forge_data/models/`),
evaluates (`eval` for the streak + `eval-robustness` for the tail readout, D143), and appends **TWO
consecutive-PASS clocks**: the F3 verdict-model streak to `~/forge_data/ranker_eval/streak.jsonl`,
and the **§8.6 tail-robustness streak to `~/forge_data/ranker_eval/robustness_streak.jsonl`** (D147 —
pooled across the daily-rolling tail models, since `tail_score` is a `cpcv_p25` prediction in the
same units; PROVISIONAL `_TAIL_SPEARMAN_CRITERION`=0.30 / `MIN_FRESH_TAIL`=50, raw spearman+n
recorded each row for operator re-judging). Both judge a **fresh per-checkpoint window** (verdicts
decided since the prior run), NOT the cumulative `--since` default — read the clocks there instead
of re-deriving them. Reaching 3/3 on either wires NOTHING; both models stay shadow-only until their
own operator gate (F3 for verdict, §8.6 for tail).

### forge grammar list-proposals

List pending refinement proposals. Recurring themes (3+ pending) tagged `[PERSISTENT]`.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | `:memory:` | Forge state DB. |

```
forge grammar list-proposals --forge-db ~/forge_data/forge.db
```

### forge grammar approve-proposal / reject-proposal

Record an operator decision (audit row). **Approve does NOT mutate `grammar.yaml`** —
you still edit it by hand and let the pre-commit hook enforce version + archive.

| Option | Type | Default | Description |
|---|---|---|---|
| `--id` | str | *required* | Proposal UUID. |
| `--initials` | str | *required* | Operator initials (audit). |
| `--forge-db` | path | `:memory:` | Forge state DB. |

```
forge grammar approve-proposal --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
forge grammar reject-proposal  --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
```

### forge grammar apply-proposal

Atomically apply a pending proposal (YAML edit + audit row + `grammar_versions`
entry). **Only `target=prefilter_calibration` (tighten-only) proposals** are
supported; grammar proposals stay manual.

| Option | Type | Default | Description |
|---|---|---|---|
| `--id` | str | *required* | Proposal UUID. |
| `--initials` | str | *required* | Operator initials. |
| `--forge-db` | path | `:memory:` | Forge state DB. |
| `--prefilter-yaml` | path | `config/prefilter.yaml` | Target YAML for calibration proposals. |

```
forge grammar apply-proposal --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
```

### forge grammar revert

Revert `grammar.yaml` to a prior archived version by promoting it forward as a new
bumped version (preserves the audit trail — no history rewrite).

| Option | Type | Default | Description |
|---|---|---|---|
| `--to-version` | str | *required* | Archived version to revert to (e.g. `v3`). |
| `--initials` | str | *required* | Operator initials. |
| `--forge-db` | path | `:memory:` | Forge state DB. |
| `--grammar-yaml` | path | `config/grammar.yaml` | Current grammar file. |
| `--archive-dir` | path | `config/grammar_archive` | Archived versions dir. |

```
forge grammar revert --to-version v3 --initials AJ --forge-db ~/forge_data/forge.db
```

---

## SCRIPTS

Run via `.venv/bin/python scripts/NAME.py` from the Forge repo root.

### backfill_verdicts.py

One-time catch-up for the `verdicts` table (D111): ingest a gated-runs export
snapshot through the production `record_verdicts` path so the current rolling
window survives before it rolls off. Idempotent (PK `crucible_run_id`). Run
while `forge.service` is STOPPED (single-writer DB) — slot into the deploy
stop-window.

| Option | Type | Default | Description |
|---|---|---|---|
| `--export-json` | path | newest in `~/optbt_data/exports` | Specific export snapshot. |
| `--forge-db` | path | `~/forge_data/forge.db` | Forge DB (service stopped). |
| `--dry-run` | flag | off | Report would-insert count; write nothing. |

```
.venv/bin/python scripts/backfill_verdicts.py --dry-run
```

### migrate_verdicts_decided_at.py

One-time repair of mixed-era `verdicts.decided_at` values (D117): rows ingested
before Crucible's 2026-06-09T22:55Z decided_at fix carry stale naive-local
timestamps (+7h late). Sets matched rows from the corrected tz-aware export;
shifts rolled-off rows +7h only when they provably equal the pre-fix snapshot
value (idempotent — cannot double-shift). Run while `forge.service` is STOPPED.

| Option | Type | Default | Description |
|---|---|---|---|
| `--export-json` | path | newest in `~/optbt_data/exports` | Corrected (post-fix) export. |
| `--prefix-snapshot` | path | `~/forge_data/backfill_source_gated_runs_20260609.json` | Pre-fix snapshot the backfill ingested. |
| `--forge-db` | path | `~/forge_data/forge.db` | Forge DB (service stopped). |
| `--dry-run` | flag | off | Report per-class counts; write nothing. |

### propose_threshold_tightenings.py

Walk the latest `gated_runs_*.json` export, cross-reference config hashes against
the `submissions` table, and compute tighter per-(indicator, role) threshold ranges
from configs that produced ≥10 trades. Writes `config/auto_tightened_thresholds.yaml`
(tighten-only) and appends loosenings to `OPEN_PROPOSALS.md`. Restart `forge.service`
after to pick up new ranges.

| Option | Type | Default | Description |
|---|---|---|---|
| `--gated-runs-export` | path | latest in exports-dir | Specific export file. |
| `--exports-dir` | path | `~/optbt_data/exports` | Dir to scan for latest export. |
| `--forge-db` | path | `~/forge_data/forge.db` | Submissions DB. |
| `--out-yaml` | path | `config/auto_tightened_thresholds.yaml` | Output. |
| `--open-proposals` | path | `OPEN_PROPOSALS.md` | Loosening proposals. |
| `--high-trade-floor` | int | `10` | Min trades to count as a "trading" config. |
| `--min-samples` | int | `5` | Min samples per (indicator, role) to propose. |
| `--dry-run` | flag | off | Print proposals; write nothing. |

```
.venv/bin/python scripts/propose_threshold_tightenings.py --dry-run
```

### requeue_high_value_configs.py

One-off recovery: re-queue historically valuable configs whose past results were
confounded by infrastructure bugs. Filters by current `grammar_version`.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | `~/forge_data/forge.db` | Submissions DB. |
| `--inbox-dir` | path | `~/optbt_data/inbox` | Write destination. |
| `--processed-dir` | path | `~/optbt_data/inbox/processed` | Source archive. |
| `--top-n` | int | `50` | Top-N by recent submission. |
| `--include-tail-hedge` | flag | on | Include all `tail_hedge` configs. |
| `--include-relative-value` | flag | on | Include all `relative_value` configs. |
| `--grammar-yaml` | path | `config/grammar.yaml` | For version filter. |
| `--skip-grammar-filter` | flag | off | Bypass the version filter. |
| `--dry-run` | flag | off | Print only. |

```
.venv/bin/python scripts/requeue_high_value_configs.py --top-n 100 --dry-run
```

### daily_ranker_eval.sh

**Bash, not Python** — the `ExecStart` of the `forge-ranker-eval` timer (05:00 daily), runnable by
hand too. Snapshots the live DB to `/tmp`, trains the verdict model AND the tail-aware
`cpcv_p25` robustness model (D142) into a staging dir and **atomically** publishes each to
`~/forge_data/models/` (the daemon's `load_latest_model` never reads a half-written file),
evaluates the live shadow models, and appends one JSON row to EACH of two clocks — the F3 verdict
streak `~/forge_data/ranker_eval/streak.jsonl` and the §8.6 tail-robustness streak
`~/forge_data/ranker_eval/robustness_streak.jsonl` (D147; pooled across tail models) — both judged
on a fresh per-checkpoint window. Deterministic (no LLM, hard rule #5); telemetry-only — never
touches grammar/weights/config/ranking. Trap-cleans the snapshot + staging on every exit. No args.

```
scripts/daily_ranker_eval.sh        # or: systemctl --user start forge-ranker-eval.service
```

### check_grammar_version_bump.py / check_grammar_doc_sync.py

Pre-commit hooks (no CLI args). The first enforces that a changed `grammar.yaml`
bumps `grammar_version` and archives the prior version. The second keeps
`grammar.yaml` rule IDs and `docs/GRAMMAR.md` headings in sync.

---

## CONFIG FILES

Under `config/`. CLI flags override YAML; YAML overrides hardcoded defaults.

| File | Controls |
|---|---|
| `forge.yaml` | Data paths, Crucible wiring, enumeration cap, batch size, rate-limit threshold, stall-guard window (`submission.stall_after_seconds`, D137), feedback cadence. |
| `grammar.yaml` | The 21 grammar rules (S/C/R/X families). Operator-owned; version-bumped + archived on change. |
| `prefilter.yaml` | Per-filter thresholds (signal density, expected trades, novelty, regime exposure, permutation, auto-tune bounds). |
| `ranker.yaml` | Composite-score weights + diversification method. |
| `auto_tightened_thresholds.yaml` | Generated indicator threshold overrides (tighten-only). Sampler prefers these when tighter than baseline. |
| `grammar_archive/v{N}.yaml` | Frozen copies of each prior grammar version. |

---

## FORGE STATE DB

`~/forge_data/forge.db` (DuckDB). Tables:

| Table | Holds |
|---|---|
| `submissions` | One row per submitted config. `config_hash` is unique-indexed (idempotency). `status` ∈ submitted/gated/skipped. |
| `batch_summaries` | Per-batch stats: size, grammar/registry version, promotion rate, prefilter rejections. |
| `pre_filter_logs` | Per-(candidate, filter) pass/score/details. |
| `verdicts` | Durable per-candidate Crucible decisions (D111): decision, decided_at, trade_count, grammar_version, full gate_results JSON. PK `crucible_run_id`, so re-gates append. Populated on every reconcile pass; survives the rolling export window. |
| `grammar_versions` | Grammar change history (version, sha256, operator initials). |
| `grammar_proposals` | Refinement proposals (pending/approved/rejected/applied). |
| `promoted_patterns` | Discovered patterns across promoted strategies. |
| `shadow_scores` | D132/F2 telemetry: per (submitted candidate, model_id) the verdict model's P(component) next to the incumbent §6.2 composite. D140/D141 add `tail_score` + `tail_model_id` (the tail-aware model's predicted `cpcv_p25`, NULL until one is trained). Written post-submission; never read by the loop. |

---

## PIPELINE SERVICES

systemd **user** services (`systemctl --user ...`). Start the writer first; stop it last.

| Service | Runs | Role |
|---|---|---|
| `crucible-db-writer` | `start_db_writer.py` | Single-writer DuckDB process; holds the exclusive lock. All others depend on it. |
| `crucible-inbox-watcher` | `start_inbox_watcher.py` | Polls `inbox/`, validates configs, queues runs. |
| `crucible-runner` | `start_runner.py` | Backtests queued runs through the full gate; writes promotion decisions. |
| `crucible-gated-runs-publisher` | `export_gated_runs.py --poll-interval 60` | Exports gated-run snapshots every 60s (Forge's read path). |
| `crucible-promoted-strategies-publisher` | `export_promoted_strategies.py --poll-interval 60` | Exports promoted strategies every 60s (QuantIQ's read path). |
| `crucible-registry-publisher` | `export_registry.py` | Oneshot at startup: publishes indicator registry snapshot. |
| `crucible-refit-watcher` | `start_refit_watcher.py` | Polls `refit_inbox/` for QuantIQ re-validation requests. |
| `forge` | `forge run --loop --consume-feedback` | The Forge daemon: generate → submit → learn. |

Timers (independent): `crucible-ingest-daily` (19:00, market data), `crucible-prune-feature-cache` (03:00), `crucible-morning-digest` (06:00). **Forge timers:** `forge-ranker-eval` (05:00, daily train of both shadow models — verdict + tail-aware robustness, D142 — + eval & eval-robustness, D143 → two clocks: `streak.jsonl` (F3 verdict) + `robustness_streak.jsonl` (§8.6 tail, D147), both under `~/forge_data/ranker_eval/`; `scripts/daily_ranker_eval.sh`), `forge-eod-check` (21:00, headless EOD pipeline read). Forge timer units live in `deploy/systemd/`, symlinked into `~/.config/systemd/user/`.

```
# Inspect any service:
systemctl --user status SERVICE
journalctl --user -u SERVICE -n 50 --no-pager
```
