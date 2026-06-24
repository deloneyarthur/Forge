# Phase 0 Handoff: Bootstrap

**Status:** complete
**Started:** 2026-05-13
**Finished:** 2026-05-13
**Sessions:** 1

---

## Deliverables (against FORGE_DESIGN.md §12)

| Deliverable | Status | Notes |
|---|---|---|
| Project skeleton (`pyproject.toml`, ruff strict, mypy strict, `.gitignore`) | done | `[tool.uv.sources]` points at sibling `../crucible_contracts/` editable install. |
| Directory tree per §11 (`src/forge/{core,grammar,enumeration,prefilters,ranking,submission,feedback,persistence,cli}`, `tests/{unit,integration,invariants,fixtures}`, `docs/`, `config/{grammar_archive/}`, `scripts/`) | done | All component packages have `__init__.py` placeholders so future phases can drop modules in. |
| `crucible_contracts` integration | done | SemVer major-version compat check at `forge.core.contracts_check.check_contracts_version()`. Forge declares `FORGE_EXPECTED_CONTRACT_VERSION = "1.1.0"`. |
| First successful read of Crucible's runs DB (synthetic) | done | `tests/fixtures/synthetic_crucible_db.py` builds the read-side schema (`runs`, `promotion_decisions`, `metrics`, `trades`) matching `crucible_contracts.queries._GATED_QUERY_BASE`. Integration test calls `get_recent_gated_runs` against an empty DB. |
| DuckDB schema for Forge's own DB (§9.1) | done | All 6 tables; `config_hash` unique index for hard rule #9 (§13.4). |
| Logging via `structlog` | done | `forge.core.logging.configure_logging(level, json_output)`; called by CLI root callback. |
| Basic CLI | done | `forge --help`, `forge version`, `forge check` all working. |
| Pre-commit hooks (ruff, mypy, hygiene) | done | `.pre-commit-config.yaml` with ruff 0.6.9, mypy 1.11.2, standard hygiene hooks. Grammar version-bump scanner deferred to Phase 1 (cannot exist before `grammar.yaml` does). |
| Persistent state docs | done | `CLAUDE.md`, `STATUS.md`, `IMPLEMENTATION_DECISIONS.md` (D001-D006), `OPEN_QUESTIONS.md`, `README.md`. |
| Spec relocated per §11 | done | `FORGE_DESIGN.md` → `docs/DESIGN.md`. |

---

## Tests

**Passing:** 18 / 18 across 5 files.

| File | Count | Coverage |
|---|---|---|
| `tests/unit/test_phase0_smoke.py` | 6 | `__version__`, `utc_now()`, `SeedHierarchy.{derive,rng}` determinism, name divergence, root divergence |
| `tests/unit/test_persistence.py` | 3 | All 6 schema tables created; idempotent re-apply; `config_hash` unique constraint enforced |
| `tests/integration/test_contracts_integration.py` | 3 | Contracts version compat; required model imports reachable; major-version mismatch raises `SchemaVersionMismatch` |
| `tests/integration/test_crucible_read.py` | 2 | `get_recent_gated_runs` returns `[]` on empty synthetic DB; DB file lifecycle |
| `tests/invariants/test_phase0_invariants.py` | 4 | No naive datetime outside `forge.core.clock`; no naked RNG outside `forge.core.seed`; required top-level state files present; grammar archive dir exists |

**Failing:** none.
**Skipped:** none.

`ruff check`: clean. `mypy src` (strict): clean (one harmless note about `networkx.*` override section not yet exercised; networkx lands in Phase 2). `pytest`: 1.16s.

---

## Decisions made during this phase

All logged in `IMPLEMENTATION_DECISIONS.md`:

- **D001** — v1 grammar is 21 rules, not 25 (§3.5 enumerates 21; §3.6 says 25; operator confirmed §3.6 typo).
- **D002** — `crucible_contracts` lives at `/home/aj/proj/crucible_contracts/`, referenced as `../crucible_contracts`.
- **D003** — `FORGE_DESIGN.md` moved to `docs/DESIGN.md` per §11.
- **D004** — Synthetic Crucible runs DB fixture mirrors `crucible_contracts.queries` join shape.
- **D005** — `CLAUDE.md` outline-copied from Crucible's; content from FORGE_DESIGN.md + kickoff.
- **D006** — Inbox files are **JSON**, not YAML. `crucible_contracts.submit_candidate` is the blessed write helper; FORGE_DESIGN.md §7.2 (which says YAML) diverges from the contracts ADR.

---

## Open questions surfaced

None — all live operator questions from Q1-Q6 were answered before Phase 0 began. See `OPEN_QUESTIONS.md`.

---

## Spec ambiguities / inconsistencies found

These should be addressed in `docs/DESIGN.md` before/during Phase 1:

1. **Rule count typo** (§3.5 vs §3.6 vs §14): §3.5 enumerates **21** rules but §3.6 and §14 (Decision Log row) cite "25 rules". Per D001 the literal count is 21. Recommend amending §3.6 and §14 to read "21 rules across 6 categories." Cross-references to "25 v1 grammar rules" elsewhere (e.g., Phase 1 deliverables in §12) should also be updated.

2. **Inbox format**: §7.2 says "Write the config to `{crucible_data_root}/inbox/{forge_batch_id}/{candidate_id}.yaml`." The `crucible_contracts` package writes **JSON** via `submit_candidate` (file: `{inbox_path}/{config_hash}.json`) and carries an explicit ADR in `queries.py` stating "PIPELINE.md and CRUCIBLE_CHANGES.md references to YAML inboxes are forward-looking; the contracts ship JSON as v1." Recommend updating §7.2 to match the contracts package (and to drop the `forge_batch_id` subdir, which the helper does not create — Forge would have to wrap the helper, or the spec should drop the batch subdir). Per D006 Forge uses the helper as-is in Phase 4.

3. **`docs/DECISIONS.md` vs `IMPLEMENTATION_DECISIONS.md`**: §11 lists `docs/DECISIONS.md` as "implementation decisions log" but the kickoff prompt prescribes `IMPLEMENTATION_DECISIONS.md` at repo root for the *agent's* day-to-day choices. Phase 0 keeps both (the docs one as a stub for *design-level* decisions that supersede §14; the root one as the agent's log). Recommend updating §11 to clarify the two-tier model, or designate one as authoritative.

4. **Phase count**: §12 prose intro says "Five phases" then enumerates seven (0 through 6). Cosmetic but worth correcting.

None of these block Phase 1; they're recommended doc cleanups.

---

## Recommendations for Phase 1

- Phase 1 is **close-review**. Surface the §3.5 grammar rules to the operator one final time before writing `grammar.yaml`; the 21 vs 25 question is now settled (D001) but each rule's predicate-type binding (cardinality / requires / forbids / compatibility / numerical_range / custom_python) should be reviewed.
- Add the grammar version-bump pre-commit hook to `.pre-commit-config.yaml` once `grammar.yaml` exists. The hook needs to read the prior committed version's `grammar_version` field and refuse the commit unless either (a) the YAML is byte-identical or (b) `grammar_version` is bumped *and* the prior version is archived under `config/grammar_archive/`.
- `GRAMMAR.md` per §3.1 must stay in sync with `grammar.yaml`. Recommend a second pre-commit hook that confirms every `id:` in the YAML has a matching `## {id}:` header in `GRAMMAR.md`.
- Property test from §3.6 / §12 Phase 1: "1000 random valid configs all pass validation; 1000 random invalid configs all fail." Build the fuzzer in `tests/fixtures/` (cannot live in `forge.grammar.fuzzer` — that would couple tests to production); use `hypothesis` for the framework but seed it deterministically.
- The §3.4 `custom_python` predicate type needs careful sandboxing. Function names are resolved against `forge.grammar.custom_predicates`; do not exec arbitrary strings.

---

## Files changed in this phase

Phase 0 is the *first* commit — there is no prior SHA to diff against. Full file inventory:

```
.gitignore
.pre-commit-config.yaml
CLAUDE.md
IMPLEMENTATION_DECISIONS.md
OPEN_QUESTIONS.md
PHASE_0_HANDOFF.md            ← this file
README.md
STATUS.md
config/forge.yaml
config/prefilter.yaml
config/ranker.yaml
config/grammar_archive/.gitkeep
docs/DESIGN.md                ← moved from repo root (FORGE_DESIGN.md → here)
docs/DECISIONS.md             ← stub
docs/GRAMMAR.md               ← stub (Phase 1)
pyproject.toml
src/forge/__init__.py
src/forge/version.py
src/forge/core/__init__.py
src/forge/core/clock.py
src/forge/core/config.py
src/forge/core/contracts_check.py
src/forge/core/logging.py
src/forge/core/seed.py
src/forge/cli/__init__.py
src/forge/cli/main.py
src/forge/enumeration/__init__.py
src/forge/feedback/__init__.py
src/forge/grammar/__init__.py
src/forge/persistence/__init__.py
src/forge/persistence/db.py
src/forge/persistence/schemas.py
src/forge/prefilters/__init__.py
src/forge/ranking/__init__.py
src/forge/submission/__init__.py
tests/__init__.py
tests/conftest.py
tests/fixtures/__init__.py
tests/fixtures/synthetic_crucible_db.py
tests/integration/__init__.py
tests/integration/test_contracts_integration.py
tests/integration/test_crucible_read.py
tests/invariants/__init__.py
tests/invariants/test_phase0_invariants.py
tests/unit/__init__.py
tests/unit/test_persistence.py
tests/unit/test_phase0_smoke.py
```

---

## Awaiting review

Phase 0 is light-review. **Awaiting operator review.** May begin Phase 1 read-only preparation (re-reading §3, drafting `grammar.yaml` skeleton, sketching predicate-type implementations) after 24h with no reply, but no code written until explicit "proceed to Phase 1" sign-off — Phase 1 is **close review** per the kickoff prompt.
