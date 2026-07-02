# Fable audit — codebase quality & structure (2026-07-01)

Full-repo quality/structure audit of Forge, performed 2026-07-01 by Claude Fable 5
(session "codebase quality forge"). This folder is the durable record, written so a
later agent (e.g. Opus) can execute the workplan without re-deriving the findings.

## Contents

| File | Purpose |
|---|---|
| `README.md` | This file: verdict, method, and the rules of engagement a picking-up agent MUST respect. |
| `FINDINGS.md` | Complete findings with file:line evidence, per area (src, tests, tooling/ops, repo/docs hygiene), plus the explicitly-verified-healthy list. |
| `WORKPLAN.md` | Prioritized items P0–P3 (numbered 1–18), each with action, effort, gating, verification steps, and pitfalls. |

## Snapshot the audit was taken against

- Date: 2026-07-01. HEAD = `ceeefa4` ("fix(ranking): gate-then-tail uses an absolute P floor"), last commit 2026-06-26.
- The working tree was DIRTY at audit time: 12 modified tracked files + 18 untracked paths
  (the in-flight D216 flag-OFF work in `src/forge/cli/main.py`, `src/forge/cli/healthcheck_cmd.py`,
  `src/forge/feedback/rejection_weights.py` + tests, plus ledger updates and untracked
  record/relay files). All file:line references in FINDINGS.md are against this dirty tree.
- Full test suite at audit time: **1,744 passed, 1 failed** in 160.75s. The single failure is
  `tests/integration/test_cli_help.py::test_every_command_is_mentioned_in_manpage`
  (missing: `forge ranker-model eval-rewire`). See WORKPLAN item 2.
- `uv run ruff check src tests scripts` → clean. `uv run mypy --strict src` → clean (96 files).
  BUT `uv run ruff format --check src tests scripts` fails on 28 files, and
  `uv run mypy --strict scripts` fails with 22 errors — see WORKPLAN items 3 and 6.

## Method

Four parallel deep-dive subagent audits (src architecture; test suite; tooling/scripts/
packaging/ops; repo & docs hygiene) plus a full uncontended-enough suite run and direct
recon (lint, mypy, git state, TODO scan). Read-only: the audit itself modified nothing
outside this folder.

## Overall verdict

**No high-severity code defects. No hard-rule violations.** All 10 CLAUDE.md hard rules
hold in code AND have invariant tests. The debt is concentrated in:

1. **Process** — no CI; pre-commit hooks demonstrably bypassed (`--no-verify`), which also
   bypasses the grammar-version-bump enforcement (hard rule #10's pre-commit half); the
   production tree carries days-old uncommitted records (D104 exposure).
2. **Duplication clusters** — nine near-identical learned-weight loaders in `cli/main.py`
   (each re-parsing the same export per daemon iteration); a persistence quadruplet in
   `ranking/model.py`; a `GatedRun` test factory copy-pasted across 7+ test files.
3. **Small hygiene** — dead legacy code stratum in `rejection_weights.py`, one type-level
   layering inversion, dead `king/` pycache dirs, root-file archive sweep cadence lapsed,
   ledgers nearing 1MB.

## Rules of engagement for the agent that picks this up

These come from `CLAUDE.md`, `docs/tasks/*.md`, and project memory. Violating them is worse
than leaving the findings unfixed.

1. **This working tree IS production.** `forge.service` (systemd user unit) runs the daemon
   from this directory via editable install. A reboot auto-starts the service onto whatever
   the tree contains, committed or not (D104). Never restart the service casually; deploys
   follow `docs/tasks/deploy.md` (stop service → full uncontended suite → commit → restart →
   verify journal). Committing files does NOT touch the running service; editing imported
   modules in-tree DOES risk the next daemon import.
2. **Operator gates.** Grammar bumps, loosenings, deploys/restarts, §3.5 rule edits are
   operator-gated. Every increment gets a D-entry in `IMPLEMENTATION_DECISIONS.md` plus a
   `STATUS.md` update (newest block on top). WORKPLAN items marked "operator-gated" need
   explicit operator sign-off before execution.
3. **Never format tree-wide** by default — the tree is not format-clean and `ruff format`
   would touch ~28 unrelated files. WORKPLAN item 3 proposes a ONE-TIME deliberate
   format-only commit as the root-cause fix; that is an operator decision, not a default.
4. **`src/forge/cli/main.py` structure is deliberate** (D065/D105/D106). ~10 test files
   import or monkeypatch its internals. Any refactor must keep every existing name bound in
   `forge.cli.main` (re-export/delegate is fine; moving-without-alias is not). Tests patch
   `_run_one_iteration` at 4 sites in `tests/unit/test_cli/test_run_loop.py:583–746` and
   import by name: `_orthogonal_family_floors`, `_select_feedback_target_batch`,
   `_resolve_run_defaults`, `_format_*_line`, `_run_battery_for_seed`,
   `_next_iteration_number`, `_effective_seed`, `_build_feature_cache`.
5. **TDD is non-negotiable**: failing test first (hard-rule/§13 behavior → failure-mode test
   in `tests/invariants/` before production code), then minimum code, then
   `ruff check` + `ruff format <changed files only>` + `mypy --strict src` + scoped pytest.
   Commit small (one module + tests).
6. **Determinism (hard rule #6)**: versionless changes to enumeration must be cold-start
   byte-identical. Any refactor near `enumeration/sampler.py` or the weight pipeline needs
   the existing golden-sequence pins green (`tests/unit/test_enumeration/test_sampler.py:1708,1900`).
7. **Coordinate with in-flight work**: `rejection_weights.py`, `main.py`,
   `healthcheck_cmd.py` and their tests are dirty with unlanded D216 work. Do not refactor
   these files until that work is committed or reverted (WORKPLAN item 1).
8. **Do not "fix" known-benign signals**: "blocked: prev batch N% gated" is the §7.3 limiter
   working; `crucible-ingest-daily` "failed" is benign (rfr-only). Live `~/forge_data/forge.db`
   holds an intermittent RW lock — `cp` to /tmp and query the copy.
9. All inter-system access via `crucible_contracts` only (hard rule #2). A missing model is
   a contracts gap to surface, not to work around.

## Suggested pickup order

Work P0 first (items 1–4; small, the tree is red/exposed today), then P1 (5–8, process
gaps), then P2 (9–14, structural refactors — each an independent small increment), then P3
(15–18, batched housekeeping). Items are independent unless a dependency is called out in
WORKPLAN.md. Re-verify each finding against the tree state at pickup time — especially
anything touching the dirty files listed above, since D216 may have landed by then.
