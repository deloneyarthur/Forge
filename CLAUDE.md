# CLAUDE.md

Project: **Forge** — candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

**Source of truth: `docs/DESIGN.md`** (~1,040 lines). If something contradicts the spec, the spec wins. If something isn't in it, ask before inventing.

Forge is a **producer**, not a validator. It enumerates grammar-valid strategy configs, cheaply pre-filters them, and submits survivors to Crucible. Most candidates Forge submits will be rejected by Crucible's gate. **That is correct behavior** (§1.2, §1.3). Forge succeeds when, over time, its submissions become *more likely* to promote — not when individual candidates look good in isolation.

When in doubt, defer to Crucible. Forge is the producer; Crucible is the authority on quality.

---

## TDD workflow — non-negotiable

Every new module follows red → green → refactor:

1. **Re-read the relevant DESIGN.md section.** Quote §numbers when justifying choices.
2. **Write the test first.** Anything in the §13 production-quality requirements or the hard-rules list MUST have its failure-mode test in `tests/invariants/` before the production code lands.
3. **Run the test; confirm it fails for the expected reason.** A red test that fails for the wrong reason is a worse signal than no test.
4. **Write the minimum code to pass.** Do not over-build for hypothetical needs.
5. **Refactor with tests green.** Add types, docstrings (WHY not WHAT), simplify.
6. **Run `ruff + mypy + pytest` on the changed scope** before committing.
7. **Commit small** — one module + its tests per commit when feasible.

**Test layout** (§11):

- `tests/unit/` — pure-logic single-module
- `tests/integration/` — multi-module workflows; contracts integration; end-to-end
- `tests/invariants/` — structural mitigations (every hard rule has a check here)
- `tests/fixtures/` — shared synthetic data (synthetic registry, known promoted strategies, adversarial grammars, synthetic Crucible runs DB)

Never ship a structural invariant without first writing the test that proves it fires.

---

## Hard rules — cannot be relaxed

1. **The 21 v1 grammar rules in §3.5 are operator-owned.** Implement as written. If a rule looks wrong, log to `OPEN_QUESTIONS.md` and surface at the next phase boundary — never silently change. (Note: §3.6 says "25 rules" but only 21 are enumerated; per operator confirmation 2026-05-13 the literal count is 21. See `IMPLEMENTATION_DECISIONS.md` D001.)
2. **No imports from Crucible internals.** All inter-system access via `crucible_contracts`. A missing model is a contracts gap to surface, not to work around with direct imports.
3. **Never propose grammar relaxations that lower Crucible's promotion gate.** Grammar can change; the gate cannot. Loosening proposals are about enumeration scope, never validation strictness.
4. **Auto-tightening can ship without approval; auto-loosening cannot.** Refiner code must structurally enforce this — loosening writes to `OPEN_PROPOSALS.md` and waits, never directly to `grammar.yaml`.
5. **No LLM in the production loop.** Enumerator / pre-filters / ranker / submitter / feedback are deterministic Python. Claude-as-collaborator (grammar refinement sessions with the operator) happens outside the running system.
6. **Enumeration is deterministic.** Given the same `(grammar_version, registry_version, seed)`, enumeration produces the same sequence. Property test enforces.
7. **The grammar must not permit `equity` as a signal family** (§13.6). Validator rejects configs that try. Crucible is options-only; this is the upstream guard.
8. **No `datetime.now()`, no `datetime.utcnow()`, no naked `random.seed()` / `np.random.default_rng()`** outside `forge.core.clock` and `forge.core.seed`. Invariant tests in `tests/invariants/test_phase0_invariants.py` enforce.
9. **Submission idempotency.** The `submissions.config_hash` column is unique-indexed (§13.4); the same hash cannot be submitted twice.
10. **Version bumps required on `grammar.yaml` changes.** Bump `grammar_version`, archive the prior version to `config/grammar_archive/`, append a Decision Log entry. Pre-commit hook will enforce in Phase 1 (§13.2).

---

## Blessed APIs — use these

- **`crucible_contracts`** — the *only* import path for inter-system models and helpers:
  - Models: `StrategyConfig`, `SignalSpec`, `SelectorSpec`, `SizerSpec`, `ExitSpec`, `CombinerSpec`, `IndicatorMetadata`, `RegistrySnapshot`, `RunResult`, `GatedRun`, `PromotionDecision`, `GateResult`, `RefitRequest`, `EquityHedgeSpec`, `LifecycleState`, `SubmissionReceipt`, `ValidationResult`.
  - Helpers: `submit_candidate`, `get_recent_gated_runs`, `get_promoted_strategies`, `request_refit`, `validate_config_against_registry`, `validate_schema_version`.
  - Layouts/invariants: `INBOX_LAYOUT`, `EXPORT_LAYOUT`, `REFIT_LAYOUT`, `MANDATORY_EXIT_IDS`, `ABSOLUTE_MAX_PER_TRADE_RISK_PCT`, `ABSOLUTE_MAX_CONCURRENT_RISK_PCT`.
  - Exceptions: `ConfigInvalid`, `QueryError`, `SchemaVersionMismatch`. **Never silently caught** outside test fixtures.
- **`forge.core.clock.utc_now()`** — the only blessed clock (hard rule #8).
- **`forge.core.seed.SeedHierarchy(root).derive(name) / .rng(name)`** — the only RNG source (hard rule #8).
- **`forge.core.contracts_check.check_contracts_version()`** — at CLI startup; halts on mismatch (§13.5).
- **`forge.persistence.db.db_connection(path)`** — the only way to open Forge's own DB; idempotent schema-ensure on open.
- **`crucible_contracts.submit_candidate(config, inbox_path)`** — the blessed write path to Crucible's inbox. Atomic (tmp-then-rename) and JSON-formatted (see `IMPLEMENTATION_DECISIONS.md` D006: contracts writes JSON, not the YAML named in FORGE_DESIGN.md §7.2).

---

## Per-batch operation order (§2.1) — fixed

1. Load grammar from `config/grammar.yaml`; verify version + archive consistency.
2. Snapshot registry via `crucible_contracts.RegistrySnapshot`.
3. **Enumerator** yields grammar-valid `StrategyConfig`s (lazy, seeded).
4. **Pre-filter battery** runs filters in cost-ascending order (§5.2): structural redundancy → resource feasibility → signal density → expected trades → novelty → regime exposure → permutation test. Short-circuit on first failure.
5. **Ranker** computes composite score (§6.2: 0.30·density + 0.25·novelty + 0.20·regime + 0.15·permutation + 0.10·prior-promotion-proximity).
6. **Diversifier** (greedy) selects top-N with diversity penalty (§6.3).
7. **Submitter** writes each surviving config to Crucible's inbox via `crucible_contracts.submit_candidate` (atomic); records each in `submissions` table.
8. **Rate limiter** waits until ≥80% of prev batch is `gated` in Crucible's runs DB (§7.3).
9. **Feedback consumer** reads gated runs via `crucible_contracts.get_recent_gated_runs`.
10. **Analyzer** updates `batch_summaries`, `pre_filter_logs`, `promoted_patterns`.
11. **Proposer** generates grammar refinement proposals — auto-applies tightenings (with archive + version bump), writes loosenings to `OPEN_PROPOSALS.md`.

Each step is testable in isolation. Cross-step state lives in `forge.db` only — never in process memory across runs.

---

## Style

- `from __future__ import annotations` at the top of every Python file.
- Frozen dataclasses with `slots=True` for value types.
- Pydantic models (`crucible_contracts.*`) for cross-system data; internal types may be stdlib dataclasses.
- One file per pre-filter, per predicate type, per CLI command (blast radius; see §11).
- Type hints on every public function signature (mypy strict).
- Docstrings explain **why**, not what — well-named identifiers show the what.
- No emojis in code or comments unless explicitly requested.

---

## Phase discipline (§12)

- Build phase-by-phase. Phase 0 → 1 → 2 → ... never jump ahead.
- **Phases 1, 3, 5 require close operator review.** State "this phase requires close review; awaiting sign-off" in the handoff. Do not start Phase N+1 until the operator says "proceed."
- **Phases 0, 2, 4, 6 get light review.** State "awaiting review"; may begin Phase N+1 read-only preparation after 24h with no reply, but no code until sign-off.
- Phase done when: §12 deliverables ship; structural invariants green; `tests/invariants/` green; reproducibility test passes (where applicable); ruff + mypy strict zero violations on changed scope; operator approval.
- If a phase is running >50% longer than the §12 estimate, surface immediately — likely scope creep or a hidden design issue.
- Phase boundary artifact: `PHASE_N_HANDOFF.md` at repo root. Template lives in the kickoff prompt.

---

## When to stop and ask

Stop and ask the operator **immediately** if any of:

- Contradiction between sections of `docs/DESIGN.md` that cannot be resolved by careful reading.
- A structural choice would commit to a path that's hard to reverse (grammar predicate types, pre-filter ordering, DB schema).
- `crucible_contracts` is missing a model or field Forge needs — surface as a contracts gap.
- A §3.5 grammar rule appears in tension with itself or with another rule.
- A test that should pass keeps failing in ways you cannot diagnose within an hour.
- You believe a spec requirement is wrong and want to propose a Decision Log entry.
- The current phase's work depends on something the next phase was meant to build.

For everything else: log to `OPEN_QUESTIONS.md` (with severity) and proceed with best interpretation. Operator reviews at phase boundary.

---

## Context-window and session discipline

- Persistent state: `STATUS.md`, `IMPLEMENTATION_DECISIONS.md` (append-only), `OPEN_QUESTIONS.md` (append-only), `PHASE_N_HANDOFF.md` per phase. Update `STATUS.md` after every module.
- End sessions before ~50K cumulative-token context. Write `STATUS.md` first.
- A new session reads `STATUS.md` + latest handoff + relevant spec sections — **not** the prior conversation history.
- Re-read files via `view` rather than relying on context memory; old code may have been edited.

---

## Communication

- Status updates at phase boundaries, not mid-phase (avoids noise).
- Quote `docs/DESIGN.md` § numbers when justifying decisions.
- Brevity > thoroughness in routine updates; thoroughness > brevity when surfacing issues.
- Deviations are proposed as Decision Log entries, not silent edits.

---

## Quick map

- Spec: `docs/DESIGN.md` (§3 grammar, §5 pre-filters, §11 file layout, §12 phase plan, §13 invariants)
- Contracts: `../crucible_contracts/` (sibling repo; installed editable via `[tool.uv.sources]`)
- Pipeline doc: `../PIPELINE.md` (system-of-systems context)
- Grammar (Phase 1): `config/grammar.yaml` + `docs/GRAMMAR.md` (must stay in sync; pre-commit hook to enforce)
- Grammar archive: `config/grammar_archive/v{N}.yaml`
- Open proposals (Phase 5 loosenings): `OPEN_PROPOSALS.md`
- Tests: `tests/{unit,integration,invariants,fixtures}/`
- Source: `src/forge/`
- Forge state: `~/forge_data/forge.db` (DuckDB; schema in `src/forge/persistence/schemas.py`)
- Crucible state (read-only): `~/optbt_data/results.duckdb` (via `crucible_contracts` helpers only)

Build slowly. Test ruthlessly. Trust the grammar. Manage context proactively.

The grammar is the heart of Forge. Get Phase 1 right.
