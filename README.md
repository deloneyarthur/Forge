# Forge

Candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

Forge enumerates grammar-valid options strategy configurations, pre-filters them through cheap statistical checks, and submits survivors to Crucible for full backtest validation. It learns from Crucible's promotion decisions and refines its hypothesis grammar over time.

See `docs/DESIGN.md` for the authoritative spec (§1 overview, §12 phase plan, §13 invariants).
See `../PIPELINE.md` for the system-of-systems context.
See `CLAUDE.md` for implementation discipline (TDD, hard rules, blessed APIs, phase boundaries).

## Quick start

```bash
uv venv
uv pip install -e ".[dev]"
forge --help
forge check    # validates crucible_contracts compat + DB schema
pytest         # full test suite
```

## Commands

| Command | Phase | Purpose |
|---|---|---|
| `forge version` | 0 | Print Forge + `crucible_contracts` versions. |
| `forge check` | 0 | Validate contracts compat + DB schema applies. |
| `forge enumerate` | 2 | Preview grammar-valid configs against the demo registry. |
| `forge prefilter` | 3 | Run the §5.2 battery against enumerated candidates. |
| `forge run` | 4 | Full single-batch cycle (enumerate → prefilter → rank → submit). `--loop` for daemon, `--consume-feedback` for inline feedback. |
| `forge feedback` | 5 | Read Crucible's gated runs, analyze, propose grammar refinements. |
| `forge grammar list-proposals` | 5 | List pending grammar refinement proposals. |
| `forge grammar approve-proposal` | 5 | Mark a proposal approved with operator initials (manual yaml-merge still required per §13.2). |
| `forge grammar reject-proposal` | 5 | Mark a proposal rejected with operator initials. |
| `forge grammar apply-proposal` | 5 | Apply a pending tighten — yaml edit + audit row + grammar_versions entry, atomic. |

## Architecture (§2.1)

Five components, in order of execution per batch:

1. **Enumerator** — yields grammar-valid `StrategyConfig`s (CSP-style, deterministic).
2. **Pre-filter battery** — 7 filters in cost-ascending order; rejects ~90%.
3. **Ranker & queue** — composite score + greedy diversification.
4. **Submitter** — writes to Crucible's inbox via `crucible_contracts`.
5. **Feedback & grammar refiner** — reads Crucible's gated runs; auto-tightens grammar; surfaces loosening proposals.

The grammar (`config/grammar.yaml` + `docs/GRAMMAR.md`) is the conceptual heart. See §3.

## Project status

See `STATUS.md` for live phase state and `IMPLEMENTATION_DECISIONS.md` for closure plans.

Phase plan (§12): 0 Bootstrap → 1 Grammar engine → 2 Enumerator → 3 Pre-filter battery → 4 Ranking and submission → 5 Feedback and refinement → 6 Polish. Phases 1, 3, 5 receive close operator review; phases 0, 2, 4, 6 receive light review.

## Honest expectations (§1.3)

Promotion rates start near zero. Target 1-3% by month 3-6, 3-5% by month 6-12. Significantly above 5% is suspicious — likely grammar over-tuned to Crucible's gate. Forge succeeds slowly.

## Repository layout

```
forge/
├── docs/DESIGN.md             # spec (source of truth)
├── docs/GRAMMAR.md            # narrative grammar doc (Phase 1)
├── config/
│   ├── forge.yaml             # main config
│   ├── prefilter.yaml         # filter thresholds
│   ├── ranker.yaml            # composite scorer weights
│   ├── grammar.yaml           # machine-readable grammar (Phase 1)
│   └── grammar_archive/       # prior versions
├── src/forge/                 # Python source
├── tests/{unit,integration,invariants,fixtures}/
├── CLAUDE.md                  # implementation discipline
├── STATUS.md                  # live phase/task state
├── IMPLEMENTATION_DECISIONS.md
└── OPEN_QUESTIONS.md
```

## Operations

Forge runs autonomously in a single-process loop. Default operating cadence: `forge run --loop --consume-feedback --poll-interval-seconds 600` (10-min poll per §7.3).

### Normal operation

```bash
# Single batch (smoke / debug)
forge run --seed 0 --batch-size 200 --max 10000 \
    --forge-db ~/forge_data/forge.db \
    --inbox ~/optbt_data/inbox \
    --crucible-db ~/optbt_data/results.duckdb

# Daemon loop (production)
forge run --loop --poll-interval-seconds 600 --consume-feedback \
    --forge-db ~/forge_data/forge.db \
    --inbox ~/optbt_data/inbox \
    --crucible-db ~/optbt_data/results.duckdb

# Manual feedback consume (e.g. when a batch finishes between scheduled polls)
forge feedback --batch-id <UUID> \
    --forge-db ~/forge_data/forge.db \
    --crucible-db ~/optbt_data/results.duckdb

# Operator workflow for grammar proposals
forge grammar list-proposals --forge-db ~/forge_data/forge.db
forge grammar approve-proposal --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
```

### Monitoring queries

All Forge state lives in `~/forge_data/forge.db` (DuckDB). Read-only samples:

```sql
-- Recent batches + promotion rate
SELECT forge_batch_id, submitted_at, batch_size, promotion_rate, common_failures
FROM batch_summaries
ORDER BY submitted_at DESC
LIMIT 10;

-- Per-submission status breakdown for the latest batch
SELECT status, COUNT(*) FROM submissions
WHERE forge_batch_id = (SELECT forge_batch_id FROM batch_summaries ORDER BY submitted_at DESC LIMIT 1)
GROUP BY status;

-- Pending grammar proposals
SELECT proposal_id, proposed_at, proposal_type, rationale
FROM grammar_proposals
WHERE status = 'pending'
ORDER BY proposed_at;

-- Auto-tune history (audit trail per §13.3)
SELECT version, change_type, change_description, decided_at, operator_initials
FROM grammar_versions
ORDER BY decided_at DESC
LIMIT 20;
```

### Recovery procedures

- **Crucible offline.** `forge feedback` exits non-zero with `error: Crucible DB unreachable: ...`. No partial mutations to Forge state. Recover by ensuring `--crucible-db` points at a reachable DuckDB file and re-invoke. The Forge submissions stay in `status='submitted'` until a matching `gated_runs` row appears.
- **Rate-limited (prior batch <80% gated).** `forge run` exits 0 with a `blocked: prev batch ... is N% gated` message. No new rows are written. Just wait — once Crucible processes more runs, the next invocation clears.
- **Corrupt / incomplete Crucible row.** Orphaned runs (no `promotion_decisions` row) are silently skipped by `crucible_contracts.get_recent_gated_runs`; the affected Forge submissions stay at `status='submitted'`. Other rows in the same batch process normally.
- **Approved grammar proposal → yaml merge.** `forge grammar approve-proposal` records `approved` + operator initials only. The actual `config/grammar.yaml` edit stays manual (§13.2 + hard rule #10): edit the rule, bump `grammar_version`, archive the prior version to `config/grammar_archive/`, append a Decision Log entry, then `git commit` (pre-commit hook enforces all four).
- **Stuck submission (`status='pending'`).** Indicates the contracts `submit_candidate` write was interrupted between DB row insert and inbox write. Inspect `~/optbt_data/inbox/<batch_id>/`; if the JSON file is present, update the row to `status='submitted'` manually. If absent, re-run the batch — the `config_hash` UNIQUE INDEX (§13.4) makes resubmission a safe no-op.

### Config files

| File | Owner | Purpose |
|---|---|---|
| `config/forge.yaml` | operator | Main runtime config (paths, batch size, poll interval). §10.1. |
| `config/grammar.yaml` | operator | 21 v1 grammar rules. Manual edits only; pre-commit enforces §13.2. |
| `config/grammar_archive/v{N}.yaml` | operator | Frozen prior grammar versions. |
| `config/prefilter.yaml` | operator + auto-tune | Filter thresholds. Auto-tightening writes here per §5.5. |
| `config/ranker.yaml` | operator | §6.2 composite-score weights. |
| `~/forge_data/forge.db` | Forge | DuckDB state (submissions, batch_summaries, grammar_versions, proposals, patterns, pre_filter_logs). |
| `OPEN_PROPOSALS.md` | Forge + operator | Loosening proposals queued for operator review. |

### §13 invariant bookmarks

| Invariant | Where it's enforced |
|---|---|
| §13.1 — deterministic enumeration | `tests/invariants/test_phase2_invariants.py`, `tests/integration/test_batch_reproducibility.py` |
| §13.2 — grammar version safety | `scripts/check_grammar_version_bump.py`, `scripts/check_grammar_doc_sync.py` (pre-commit hooks) |
| §13.3 — no silent grammar changes | `tests/invariants/test_phase5_invariants.py` (audit row + structural hard rule #4) |
| §13.4 — submission idempotency | `tests/invariants/test_phase4_invariants.py`, `tests/invariants/test_phase6_properties.py` (Hypothesis-driven) |
| §13.5 — Crucible-version compatibility | `forge.core.contracts_check.check_contracts_version` (called at CLI startup) |
| §13.6 — no equity exposure | `tests/invariants/test_phase1_invariants.py` |
| §13.7 — resource limits | carry-forward (Crucible doesn't yet expose `worker_mem_limit_mb` via contracts) |

For phase-specific test inventories see each `PHASE_N_HANDOFF.md`.
