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

### check_grammar_version_bump.py / check_grammar_doc_sync.py

Pre-commit hooks (no CLI args). The first enforces that a changed `grammar.yaml`
bumps `grammar_version` and archives the prior version. The second keeps
`grammar.yaml` rule IDs and `docs/GRAMMAR.md` headings in sync.

---

## CONFIG FILES

Under `config/`. CLI flags override YAML; YAML overrides hardcoded defaults.

| File | Controls |
|---|---|
| `forge.yaml` | Data paths, Crucible wiring, enumeration cap, batch size, rate-limit threshold, feedback cadence. |
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

Timers (independent): `crucible-ingest-daily` (19:00, market data), `crucible-prune-feature-cache` (03:00), `crucible-morning-digest` (06:00).

```
# Inspect any service:
systemctl --user status SERVICE
journalctl --user -u SERVICE -n 50 --no-pager
```
