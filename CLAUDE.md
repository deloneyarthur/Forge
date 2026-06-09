# CLAUDE.md

Project: **Forge** — candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.
Forge is a **producer**, not a validator: it enumerates grammar-valid strategy configs, cheaply
pre-filters them, and submits survivors to Crucible's gate. Most submissions are rejected —
**that is correct behavior** (§1.2, §1.3). Forge succeeds when its stream becomes *more likely*
to promote over time. Crucible is the authority on quality; when in doubt, defer to it.

**Source of truth: `docs/DESIGN.md`.** If anything contradicts the spec, the spec wins; if
something isn't in it, ask before inventing. Quote § numbers when justifying decisions.

## This working tree IS production

`forge.service` (systemd user unit) runs the daemon from THIS directory via editable install.

- Build risky or grammar-gated changes in a worktree (`git worktree add ../Forge-build`), never
  in this tree while the service runs. Keep this tree `git status`-clean: a reboot auto-starts
  the service onto whatever the tree contains, committed or not (D104).
- Deploys follow `docs/tasks/deploy.md`: stop service → full uncontended suite → commit →
  restart → verify journal. Never restart the service casually.

## Stack & commands

Python 3.12 · uv · Typer · Pydantic v2 · Polars · DuckDB · structlog · pytest (+ Hypothesis).

```bash
uv venv && uv pip install -e ".[dev]"     # setup (contracts dep: ../crucible_contracts, editable)
uv run pytest                             # full suite ~1,400; scope: uv run pytest tests/unit/test_grammar
uv run ruff check src tests scripts       # lint (strict select-set in pyproject.toml)
uv run ruff format <changed files only>   # tree is NOT format-clean — never format tree-wide
uv run mypy --strict src                  # zero violations required
uv run forge --help                       # CLI reference: docs/MANPAGE.md
```

## Hard rules — cannot be relaxed

1. **The 21 v1 grammar rules in §3.5 are operator-owned.** Implement as written. If a rule looks
   wrong, log to `OPEN_QUESTIONS.md` — never silently change. (§3.6 says "25"; literal count is
   21 per operator confirmation, D001.)
2. **No imports from Crucible internals.** All inter-system access via `crucible_contracts`.
   A missing model is a contracts gap to surface, not to work around.
3. **Never propose grammar relaxations that lower Crucible's promotion gate.** Grammar can
   change; the gate cannot.
4. **Auto-tightening can ship without approval; auto-loosening cannot.** Loosening writes to
   `OPEN_PROPOSALS.md` and waits — never directly to `grammar.yaml`. Structurally enforced.
5. **No LLM in the production loop.** Enumerator / pre-filters / ranker / submitter / feedback
   are deterministic Python.
6. **Enumeration is deterministic.** Same `(grammar_version, registry_hash, seed)` → same
   sequence. Property-tested; versionless changes must be cold-start byte-identical.
7. **The grammar must not permit `equity` as a signal family** (§13.6). Crucible is options-only.
8. **No `datetime.now()` / `datetime.utcnow()` / naked `random.seed()` / `np.random.default_rng()`**
   outside `forge.core.clock` and `forge.core.seed`. Invariant tests enforce.
9. **Submission idempotency.** `submissions.config_hash` is unique-indexed (§13.4); the same hash
   cannot be submitted twice.
10. **Version bumps required on `grammar.yaml` changes** — ANY byte change, comments included.
    Bump `grammar_version`, archive to `config/grammar_archive/`, append a Decision Log entry.
    Pre-commit hook + loader enforce.

## Blessed APIs — use these, nothing else

- **`crucible_contracts`** — the only inter-system import path. Models (StrategyConfig,
  SignalSpec, RegistrySnapshot, GatedRun, PromotionDecision, …), helpers (`submit_candidate`,
  `get_recent_gated_runs`, `get_promoted_strategies`, `validate_config_against_registry`, …),
  layout/limit constants, exceptions (`ConfigInvalid`, `QueryError`, `SchemaVersionMismatch` —
  never silently caught outside test fixtures).
- **`forge.core.clock.utc_now()`** — the only clock. **`forge.core.seed.SeedHierarchy`** — the
  only RNG source (rule #8).
- **`forge.core.contracts_check.check_contracts_version()`** at CLI startup; the
  `FORGE_EXPECTED_CONTRACT_VERSION` pin lives there (§13.5).
- **`forge.persistence.db.db_connection(path)`** — the only way to open Forge's DB.
- **`crucible_contracts.submit_candidate(config, inbox_path)`** — the write path to Crucible's
  inbox (atomic tmp-then-rename, JSON per D006).

## TDD & style — non-negotiable

Red → green → refactor: re-read the relevant DESIGN.md section → write the failing test FIRST
(hard-rule/§13 behavior gets its failure-mode test in `tests/invariants/` before production code)
→ confirm it fails for the expected reason → minimum code to pass → refactor green → ruff + mypy
+ pytest on changed scope → commit small (one module + tests). Layout: `tests/README.md`.

Style: `from __future__ import annotations` everywhere; frozen dataclasses (`slots=True`) for
value types; Pydantic only for cross-system data; one file per pre-filter / predicate type / CLI
command; type hints on every public signature; docstrings say WHY, not what; no emojis.

## Pitfalls (recurring, verified)

- Live `~/forge_data/forge.db` holds an intermittent RW lock — even read-only opens fail.
  `cp` to /tmp and query the copy (`docs/tasks/investigate-live.md`).
- Timestamps before 2026-06-07 are PDT (old box); after, UTC. Convert before joining.
- Crucible's gated export is a rolling top-10k window with pre-v5 re-gate pollution; split
  cohorts by `grammar_version` and time-cut v9 at 2026-06-06T06:48:49Z (D104).
- ~10 test files monkeypatch `forge.cli.main` internals — its structure is deliberate
  (D065/D105/D106); don't refactor it casually.
- "blocked: prev batch N% gated" = the §7.3 limiter working; `crucible-ingest-daily` "failed"
  is benign (rfr-only). Don't "fix" either.

## Operator gates — when to stop and ask

Grammar bumps, loosenings, deploys/restarts, and §3.5 rule edits are operator-gated. Phases 0–6
are complete (`PHASE_N_HANDOFF.md`); work proceeds as operator-gated increments — each gets a
D-entry in `IMPLEMENTATION_DECISIONS.md` plus a `STATUS.md` update.

Stop immediately if: DESIGN.md self-contradicts; a hard-to-reverse structural choice looms
(predicate types, filter ordering, DB schema); `crucible_contracts` lacks a needed model/field;
a §3.5 rule seems wrong or in tension; a test fails undiagnosed for >1 hour; you want to propose
a spec deviation. Everything else: log to `OPEN_QUESTIONS.md` with severity and proceed with the
best interpretation. Deviations are proposed as Decision Log entries, never silent edits.

## Session discipline

`STATUS.md` is the live state (newest block on top; update after every unit of work). New
sessions read `STATUS.md` + the routing below — not prior conversation history. Re-read files
rather than trusting context memory.

## Where to look

| Need | Read |
|---|---|
| Spec / intent | `docs/DESIGN.md` (§3 grammar, §5 prefilters, §12 phases, §13 invariants) |
| Live state, recent decisions | `STATUS.md` (top block), `IMPLEMENTATION_DECISIONS.md` (D###) |
| As-built map, data flow, change taxonomy, root-file taxonomy | `docs/architecture.md` |
| CLI commands / flags / scripts / services / DB tables | `docs/MANPAGE.md` |
| Operating the pipeline (start/stop/recover) | `docs/HOW-TO.md` |
| Grammar rules narrative (sync-enforced with grammar.yaml) | `docs/GRAMMAR.md` |
| Changing grammar / enumeration policy | `docs/tasks/grammar-change.md` |
| Deploying to the live service | `docs/tasks/deploy.md` |
| Feedback / learned-weight changes | `docs/tasks/feedback-change.md` |
| Debugging live behavior, DB/export queries | `docs/tasks/investigate-live.md` |
| Lint / test / commit / hooks | `docs/tasks/quality-gates.md` |
| Crucible / contracts coordination | `docs/tasks/crucible-handoff.md` |
| Domain terms | `docs/glossary.md` |
| Indicator value distributions | `docs/INDICATOR_THRESHOLDS.md` |
| New machine / migration | `deploy/NEW_BOX_TRANSFER.md` |

Build slowly. Test ruthlessly. Trust the grammar — it is the heart of Forge.
