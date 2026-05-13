# Forge — Status

**Current phase:** 1 (Grammar engine) — **HALTED at kickoff. Awaiting operator decision on Q7 (contracts gap; see OPEN_QUESTIONS.md).**
**Previous phase:** 0 (Bootstrap) — complete, committed at `74f0ffa`.
**Phase started:** 2026-05-13
**Phase finished:** 2026-05-13
**Budget vs actual:** 3-5 days budgeted (§12); 1 session actual.

## Phase 0 deliverables (§12)

- [x] Project skeleton (pyproject.toml, .gitignore, pre-commit, ruff/mypy strict)
- [x] Directory tree per §11 (`src/forge/{core,grammar,…,persistence,cli}`; tests; docs; config)
- [x] `crucible_contracts` integration (import + SemVer major-version check at startup)
- [x] DuckDB schema for Forge's own DB (all 6 tables from §9.1 + `config_hash` unique index)
- [x] CLI skeleton (`forge --help`, `forge version`, `forge check`)
- [x] Test scaffolding (`tests/{unit,integration,invariants,fixtures}/`) — 18 tests, all passing
- [x] Synthetic Crucible runs DB fixture (Phase 0 read-path proof)
- [x] Logging via structlog
- [x] Persistent state docs (CLAUDE.md, STATUS.md, IMPLEMENTATION_DECISIONS.md, OPEN_QUESTIONS.md)
- [x] Spec relocated to `docs/DESIGN.md` (was `FORGE_DESIGN.md` at root)
- [x] Quality gates green (`ruff check`, `mypy --strict`, `pytest` all pass)
- [x] `PHASE_0_HANDOFF.md` written

## Pending operator action

- **Spawn a fresh agent** in `/home/aj/proj/crucible_contracts/` using `CONTRACTS_V1_2_AGENT_PROMPT.md` (in this repo root) as the kickoff message. That agent ships `crucible_contracts` v1.2.0.
- After contracts v1.2.0 lands, trigger a new Forge session to resume Phase 1. The first action in that session will be to bump `FORGE_EXPECTED_CONTRACT_VERSION` in `src/forge/core/contracts_check.py` from `"1.1.0"` → `"1.2.0"`, re-read `docs/DESIGN.md` §3, and proceed with predicate-type implementation.
- (Optional, separate doc-only PR) Address the four documentation inconsistencies surfaced in `PHASE_0_HANDOFF.md` — rule count typo, inbox format, decisions-file layout, "five phases" prose. None block Phase 1.

## Active blockers

**Q7 — contracts-gap (high severity).** §3.5 grammar rules reference `hypothesis`, `signals[*].role`, and `signals[*].family` — none of which exist (or exist in a reconciled form) on `crucible_contracts.StrategyConfig`/`SignalSpec`. The mandatory-exit count also differs (spec E1 says 3; contracts `MANDATORY_EXIT_IDS` has 4). See `OPEN_QUESTIONS.md` for the full table and four options presented to the operator.

Recommended path: option 1 (extend `crucible_contracts` to add `hypothesis`, `role`, reconcile `family` enum, accept contracts' 4 mandatory exits; minor version bump 1.1 → 1.2). Awaiting operator decision before any Phase 1 code.

## Open questions

- **Q7 (active, high):** contracts gap — see above and `OPEN_QUESTIONS.md`.
- Q1–Q6 (resolved 2026-05-13): see `IMPLEMENTATION_DECISIONS.md` D001–D006.

## Session log

- 2026-05-13 (session 1): first-session confirmation; Q1–Q6 answered. Phase 0 cleared to begin.
- 2026-05-13 (session 1, cont.): Phase 0 skeleton written end-to-end. Quality gates green: 18/18 tests, ruff clean, mypy strict clean. `forge --help / version / check` working. Committed `74f0ffa`.
- 2026-05-13 (session 1, cont.): Phase 1 kickoff began. Read `crucible_contracts.models.py` to ground predicate-field paths; discovered structural gaps between §3.5 grammar rules and the contracts model surface. Logged as Q7 (high severity). **Halted before any code.** Awaiting operator decision on the four presented options.
- 2026-05-13 (session 1, cont.): Operator chose option 1 (extend contracts to v1.2.0) + 11-family canonical list. Logged as D007. Wrote `CONTRACTS_V1_2_AGENT_PROMPT.md` as the brief for a fresh agent in the contracts repo. Forge session ending; Forge resumes Phase 1 once contracts v1.2.0 lands.
