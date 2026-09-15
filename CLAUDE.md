# CLAUDE.md

Project: **Forge** — candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.
Forge is a **producer**, not a validator: once a week it decides whether any cell of the strategy
space deserves challengers, enumerates grammar-valid configs, cheaply pre-filters them, and submits
survivors to Crucible's gate. Most submissions are rejected — **that is correct behavior** (§1.2,
§1.3) — and a week that submits nothing is the design. Crucible is the authority on quality; when
in doubt, defer to it.

**Sources of truth:** `docs/DESIGN.md` for intent and invariants (§ numbers are the citation
currency; bannered sections record what left the tree), `docs/architecture.md` for what is built.
If something is in neither, ask before inventing. Quote § numbers when justifying decisions.

## This working tree IS production

`forge-campaign.timer` (systemd user unit, Sunday 03:00 UTC) runs `forge campaign` from THIS
directory via editable install. There is no daemon (D416, 2026-09-14).

- Keep this tree `git status`-clean: the timer fires onto whatever the tree contains, committed or
  not (D104). Grammar bumps build in a worktree (`git worktree add ../Forge-build`); other work
  here, in short dirty windows.
- A commit IS the deploy (`docs/tasks/deploy.md`: preflight → commit → the next Sunday run picks it
  up; verify with `forge campaign --dry-run`). Starting the service by hand submits for real.

## Stack & commands

Python 3.12 · uv · Typer · Pydantic v2 · Polars · DuckDB · structlog · pytest (+ Hypothesis).

```bash
uv venv && uv pip install -e ".[dev]"     # setup (contracts dep: ../crucible_contracts, editable)
uv run pytest                             # full suite (count: STATUS.md); scope: uv run pytest tests/unit/test_grammar
uv run ruff check src tests scripts       # lint (strict select-set in pyproject.toml)
uv run ruff format <changed files only>   # tree is NOT format-clean — never format tree-wide
uv run mypy --strict src                  # zero violations required
uv run forge --help                       # CLI reference: docs/MANPAGE.md
```

## Hard rules — cannot be relaxed

1. **The 21 v1 grammar rules in §3.5 are operator-owned.** Implement as written. If a rule looks
   wrong, log to `OPEN_QUESTIONS.md` — never silently change.
2. **No imports from Crucible internals.** All inter-system access via `crucible_contracts`.
   A missing model is a contracts gap to surface, not to work around.
3. **Never propose grammar relaxations that lower Crucible's promotion gate.** Grammar can
   change; the gate cannot.
4. **Grammar changes require a preregistration and the operator's signature.** No code writes
   `config/grammar.yaml` at runtime; the pre-commit `freeze-governance` and `grammar-version-bump`
   hooks enforce it (D390/D392). `OPEN_PROPOSALS.md` is a static, machine-parsed record.
5. **No LLM in the production loop.** Every stage of the weekly run (reconcile / train / enumerate /
   prefilter / gate / rank / submit) is deterministic Python — classical ML is fine, LLMs are not.
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

- **`crucible_contracts`** — the only inter-system import path: models (StrategyConfig,
  RegistrySnapshot, GatedRun, …), helpers (`submit_candidate`, `load_forge_gated_runs_from_export`
  — the verdict stream, never the all-source glob — `get_recent_gated_runs`,
  `get_promoted_strategies`), layout/limit constants, exceptions (`ConfigInvalid`, `QueryError`,
  `SchemaVersionMismatch` — never silently caught outside test fixtures).
- **`forge.core.clock.utc_now()`** — the only clock. **`forge.core.seed.SeedHierarchy`** — the
  only RNG source (rule #8).
- **`forge.core.contracts_check.check_contracts_version()`** at CLI startup and in the campaign
  boot check; the `FORGE_EXPECTED_CONTRACT_VERSION` pin lives there (§13.5).
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

- A run in progress holds an RW lock on `~/forge_data/forge.db` — even read-only opens fail.
  Use `scripts/live_db_snapshot.sh` (never /tmp — a 62 GB tmpfs; `docs/tasks/investigate-live.md`).
- Era boundaries silently wreck joins (PDT→UTC 2026-06-07, the v9 time-cut, the cost floor, the
  OI eras, the refit-lane skim): read `docs/HOW-TO.md` §Eras before any cohort analysis.
- Crucible's forge stream reads `truncated: true` until the daemon era's tail leaves the 14-day
  window (STATUS has the date); after that a truncated file is a relay, not a shrug. The run skips
  the aged-out flush whenever the window is incomplete or absent (D415).
- `submitted_hashes` in campaign records is Crucible's join key — never rename or drop it; the
  `selection_arm` sent to Crucible must be a value their Literal admits (campaign lanes stamp `ranked`).
- `crucible-ingest-daily` "failed" is benign (rfr-only). Don't "fix" it.

## Operator gates — when to stop and ask

Operator-gated: grammar bumps (FROZEN at v55, D390 — open prereg first; §5 reopeners only), §3.5
rule edits, `deploy/systemd/` edits, a live `systemctl --user start forge-campaign.service`. Each
increment gets a D-entry plus a `STATUS.md` update.

Stop immediately if: DESIGN.md self-contradicts; a hard-to-reverse structural choice looms
(predicate types, filter ordering, DB schema, the run-record fields Crucible joins on);
`crucible_contracts` lacks a needed model/field; a §3.5 rule seems wrong; a test fails undiagnosed
for >1 hour; you want to propose a spec deviation. Everything else: log to `OPEN_QUESTIONS.md` with
severity and proceed with the best interpretation. Deviations are Decision Log entries, never silent edits.

## Session discipline

`STATUS.md` is the live state (newest block on top; update after every unit of work). New
sessions read `STATUS.md` + the routing below — not prior conversation history. Re-read files
rather than trusting context memory.

Docs are part of the change: if a commit alters a CLI command/flag, a ritual, a config file's
meaning, or module layout, update the doc that owns it (routing table below) in the same commit.
Volatile facts (versions, weights, counts, dates that will pass) belong in `STATUS.md`/D-entries,
never in docs — a doc may state where a value lives, never the value.
Records discipline (sweep-on-land, block size, rotation, relay location) is enforced by
`tests/invariants/test_regrowth_invariants.py`; the rules are in `docs/tasks/quality-gates.md`.

## Where to look

| Need | Read |
|---|---|
| Spec / intent | `docs/DESIGN.md` (§3 grammar, §5 prefilters, §13 invariants) |
| Live state, recent decisions | `STATUS.md` (top block), `IMPLEMENTATION_DECISIONS.md` (D###) |
| As-built map, data flow, change taxonomy, root-file taxonomy, terms | `docs/architecture.md` |
| CLI commands / flags / scripts / services / DB tables / the run record | `docs/MANPAGE.md` |
| Operating the weekly run (check, recover, eras) | `docs/HOW-TO.md` |
| Grammar rules narrative (sync-enforced with grammar.yaml) | `docs/GRAMMAR.md` |
| Changing grammar / enumeration policy (frozen — prereg first) | `docs/tasks/grammar-change.md` |
| Deploying (the tree is the deploy; the Sunday run picks it up) | `docs/tasks/deploy.md` |
| Debugging a run, DB/export queries | `docs/tasks/investigate-live.md` |
| Lint / test / commit / hooks | `docs/tasks/quality-gates.md` |
| Crucible / contracts coordination (relays: `~/proj/freeze/relays/`) | `docs/tasks/crucible-handoff.md` |
| The plan of record for the final state | `docs/proposals/repo-simplification-2026-09.md` (§12); terminal proposals: `_archive/PROPOSAL_*.md` |
| New machine / migration | `deploy/NEW_BOX_TRANSFER.md` |

Build slowly. Test ruthlessly. Trust the grammar — it is the heart of Forge.
