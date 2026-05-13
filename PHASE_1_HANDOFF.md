# Phase 1 Handoff: Grammar Engine

**Status:** complete — **awaiting close review.**
**Started:** 2026-05-13 (kickoff session)
**Paused:** 2026-05-13 (Q7 contracts gap; D007 → contracts v1.2.0 + v1.3.0 side-trips)
**Resumed:** 2026-05-13
**Finished:** 2026-05-13
**Sessions:** 2 (Phase 1 kickoff + resume)
**Budget vs actual:** 7-10 days budgeted (§12); ~1 calendar day actual (heavy single session).

---

## Deliverables (against DESIGN.md §12 Phase 1)

| Deliverable | Status | Notes |
|---|---|---|
| `grammar.yaml` parser and validator | done | `forge.grammar.loader.load_grammar(path)` → Pydantic `Grammar`. Custom-predicate name validation + archive-consistency check at load time. |
| All 6 predicate types | done | `cardinality`, `numerical_range`, `requires`, `forbids`, `compatibility`, `custom_python`. Discriminated-union models in `models.py`; pure-functional evaluators in `predicates.py`. |
| Rule loader with version archive | done | `archive.py` helpers + loader check refuses silent drift via `GrammarVersionError`. Pre-commit hook (`scripts/check_grammar_version_bump.py`) enforces at commit time. |
| Validator with named errors | done | `validate(config, grammar, registry) -> crucible_contracts.ValidationResult`. No short-circuit. Errors prefixed with rule id. |
| `config/grammar.yaml` with 21 v1 rules | done | All §3.5 rules (S1-S5, C1-C4, P1-P4, E1-E3, R1-R3, X1-X2) encoded. Categories balanced 5-4-4-3-3-2 = 21 per D001. |
| `docs/GRAMMAR.md` narrative | done | One section per rule (What / Why / Cost / Evidence to relax). Heading ids paired to grammar.yaml ids — both loader (soft check) and pre-commit hook (strict check) enforce. |
| Validation < 10ms per config | done | `test_validate_under_10ms_mean` — 100-config mean per §12. Observed ~0.2-0.5ms in practice. |
| Property test: 1000 valid pass, 1000 invalid fail with named errors | done | Hypothesis-driven, template-keyed sampling + 6 mutators. Each mutator tagged with the rule it breaks; validator must name that rule. |

**Tests passing**: 218 / 218.
**Test files**: 22 Python files across `unit/`, `integration/`, `invariants/`, `fixtures/`.
**Quality gates**: `ruff check`, `ruff format --check`, `mypy --strict` all clean. Coverage non-trivial on `src/forge/grammar/`.

---

## Decisions logged during this phase

`IMPLEMENTATION_DECISIONS.md` entries **D008 – D018** (eleven). Summary:

- **D008** — Adopted `crucible_contracts` v1.2.0 (commit `7d0f359` in contracts repo); `FORGE_EXPECTED_CONTRACT_VERSION` → `"1.2.0"`. Closed Q7.
- **D009** — Path resolver supports both §3.4 sugar (`signals.role.directional`) and JSONPath (`signals[?(@.role=="directional")]`).
- **D010** — S4 lookback bucketing thresholds: short ≤ 6, medium 7-89, long ≥ 90; max-over-indicators for multi-indicator directional signals.
- **D011** — Canonical exit-id vocabulary lives in contracts (`KNOWN_EXIT_IDS` — 14 ids). Triggered v1.3.0 contracts release (commit `1d5b51f`).
- **D012** — E2 stop-loss classifier in contracts (`STOP_LOSS_EXIT_IDS` — `premium_stop_loss`, `atr_underlying_stop_loss`, `trailing_atr`).
- **D013** — R1 simplified: dropped the redundant directional-family AND-clause (tautological given C2).
- **D014** — §3.5 E1 (3 mandatory exits cited) vs contracts (4 in `MANDATORY_EXIT_IDS`): contracts count wins per D007. Spec doc-cleanup tracked.
- **D015** — S5 stays as one `custom_python` rule (preserves rule count = 21 per D001); `requires`/`forbids` predicate types exercised via synthetic test rules.
- **D016** — Adopted contracts v1.3.0; `FORGE_EXPECTED_CONTRACT_VERSION` → `"1.3.0"`.
- **D017** — Grammar rule-engine architecture: Pydantic discriminated union; pure-functional evaluators; custom-predicate function-name registry (no eval).
- **D018** — S4 reclassified `compatibility` → `custom_python`. §3.4's `field1: signals.directional.lookback` requires registry-aware path resolution that doesn't fit the pure rule-engine architecture; `compatibility` stays a generic key→target lookup; S4's logic lives in `custom_predicates.lookback_class_matches_dte_bucket`. **Deviation from operator-approved encoding** — flag for close-review.

---

## Open questions / spec ambiguities surfaced

These don't block Phase 2 but warrant operator-level decision before Phase 5 (refinement) or before contracts v2:

1. **§3.5 R2 + C1 interaction (medium).** R2 says "trend strategies require `adx` or `hurst` regime gate." If `adx`/`hurst` belong to the `trend` family, a trend strategy would have two trend-family indicators (the directional + the gate), violating C1. The fixture registry resolves this by classifying `adx`/`hurst` as `volatility` family. The operator should decide whether (a) `adx`/`hurst` truly belong outside `trend`, or (b) §3.5 needs a clarification that trend-strength gates don't count for C1's family-collision rule.

2. **§3.5 P2 exit-DTE side (medium).** P2 specifies entry AND exit DTE windows per bucket (e.g., swing_short: entry 14-21, exit 5-7). The current Forge implementation only checks the entry side. Exit DTE lives in `theta_cliff_exit.params` (param name not pinned in §3.5). Decide: (a) pin a canonical exit-param name (`dte_threshold`?) and extend P2 to check it, or (b) accept P2 as entry-only for v1.

3. **§3.5 S5 "profit-taking forbidden" for tail_hedge (low).** S5 says `tail_hedge` forbids "profit-taking" — read narrowly as `hard_profit_target` (the only profit-taking exit in `KNOWN_EXIT_IDS`). If `tier_2_profit_take` or similar enters the vocabulary later, S5's forbidden list will need updating.

4. **§3.5 P1 strength (low).** P1 currently checks only that signal `params` keys appear in the union of the indicators' `params_schema` keys — full type+range validation against the JSON-Schema-shaped `params_schema` is deferred. A follow-up rule could strengthen P1 with `jsonschema` or similar.

5. **§3.5 R1 IV-rank threshold (low).** The threshold cap of ≤ 50 is baked in as `_R1_IV_RANK_MAX_THRESHOLD = 50.0`. The spec narrative says "only fire when IV is cheap" but doesn't pin 50. Operator should confirm the cap.

6. **Documentation inconsistencies** (carried forward from `PHASE_0_HANDOFF.md`):
   - §3.6 / §14 cite "25 rules"; literal count is 21 per D001.
   - §7.2 says YAML inbox; contracts ships JSON per D006.
   - §11 vs root `IMPLEMENTATION_DECISIONS.md` two-tier model.
   - §12 prose says "Five phases" then lists seven.
   - §3.5 E1 lists 3 mandatory exits; contracts pin 4 per D014. **(New)**
   - §3.5 R2 implies trend-strength gates outside `trend` family. **(New, see #1)**

---

## Source inventory

### `src/forge/grammar/` (8 modules)

| File | Purpose |
|---|---|
| `__init__.py` | Public API re-exports |
| `models.py` | Pydantic `Rule`, `Grammar`, 6 `*Predicate` variants, `PredicateResult`, exceptions |
| `path_resolver.py` | Dual-syntax field-path resolver (§3.4 sugar + JSONPath) |
| `predicates.py` | Pure-functional evaluators for the 6 predicate types + dispatch registry |
| `custom_predicates.py` | 16 §3.5 predicate functions + module-level tables (S5/C2/P2/P3/R1-R3/X1-X2) + `always_pass`/`always_fail` stubs |
| `validator.py` | `validate(config, grammar, registry) -> ValidationResult` |
| `loader.py` | YAML → `Grammar` + custom-predicate name check + archive consistency |
| `archive.py` | Hash + archive write/lookup helpers |

### `config/`

- `grammar.yaml` — 21 v1 rules.
- `grammar_archive/v1.yaml` — byte-identical archive entry.

### `docs/`

- `GRAMMAR.md` — narrative documentation (one section per rule).

### `scripts/`

- `check_grammar_version_bump.py` — pre-commit hook enforcing CLAUDE.md hard rule #10.
- `check_grammar_doc_sync.py` — pre-commit hook enforcing grammar↔doc id pairing.

### `tests/` (12 new files + 1 modified fixture)

| File | Count | Coverage |
|---|---|---|
| `tests/unit/test_grammar/test_models.py` | 31 | Predicate schema validation, discriminated-union parsing, Rule + Grammar |
| `tests/unit/test_grammar/test_path_resolver.py` | 17 | Both syntaxes, indexed access, list projection, error paths |
| `tests/unit/test_grammar/test_predicates_cardinality.py` | 10 | S1/S2/S3/C3 shapes + bounds + error reporting |
| `tests/unit/test_grammar/test_predicates_numerical_range.py` | 11 | P4 + scalar resolution + bool/string rejection |
| `tests/unit/test_grammar/test_predicates_requires_forbids.py` | 9 | Synthetic-rule coverage per D015 |
| `tests/unit/test_grammar/test_predicates_compatibility.py` | 7 | Synthetic-rule coverage per D018 |
| `tests/unit/test_grammar/test_predicates_custom_python.py` | 7 | Dispatch + registry + duplicate-name guard |
| `tests/unit/test_grammar/test_custom_predicates.py` | 46 | 16 §3.5 predicate functions (positive + negative each) |
| `tests/unit/test_grammar/test_validator.py` | 8 | Iteration, error format, inactive-rule skipping, no short-circuit |
| `tests/unit/test_grammar/test_loader.py` | 11 | YAML + schema + custom-name + archive checks |
| `tests/unit/test_grammar/test_archive.py` | 11 | Hash + lookup + write + idempotency + collision guard |
| `tests/integration/test_v1_grammar.py` | 10 | End-to-end load + validate on real grammar.yaml |
| `tests/integration/test_grammar_property.py` | 2 | 1000 valid + 1000 invalid per §12 |
| `tests/integration/test_grammar_perf.py` | 1 | < 10 ms per config |
| `tests/integration/test_hook_scripts.py` | 13 | Pre-commit hook scanners |
| `tests/invariants/test_phase1_invariants.py` | 5 | Hard rule #7 (no equity family) |
| `tests/fixtures/strategy_configs.py` | (fixture) | `minimal_strategy_config`, `grammar_valid_baseline`, `minimal_registry_snapshot` |
| `tests/fixtures/grammar_property_helpers.py` | (fixture) | Hypothesis templates + mutators |

Total new tests: **199**. Total Phase 0 + 1: **218**.

### Top-level state files

- `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`, `OPEN_QUESTIONS.md` — all updated.

---

## What close review should focus on

Per the resume prompt: "The operator's close review will involve hand-crafting a few `StrategyConfig`s (some intended to pass, some intended to fail specific rules) and running them through your validator. Be ready to explain any rule encoding choice that the operator questions."

The highest-leverage things to review, in priority order:

1. **`config/grammar.yaml`** — the operator-owned artifact. Each rule's predicate-type choice was confirmed in the pre-code message; D018 documents the one deviation (S4 → custom_python). Spot-check the predicate paths (e.g., `signals.role.directional` for S2/S3).

2. **`src/forge/grammar/custom_predicates.py` module-level tables** — `_S5_HYPOTHESIS_EXITS`, `_C2_HYPOTHESIS_FAMILIES`, `_P2_ENTRY_DTE`, `_P3_DELTA_BAND`, `_R1_IV_RANK_MAX_THRESHOLD`, `_R2_TREND_STRENGTH_INDICATORS`, `_R3_EVENT_PROXIMITY_INDICATORS`. These encode §3.5's prose verbatim. The most failure-prone path is S5's table (six hypothesis rows, each with required + forbidden lists).

3. **`docs/GRAMMAR.md`** — the rationale narrative. Each section's "Why" claim is auditable. The "Evidence to relax" entries are first-pass; operator may want to sharpen them.

4. **Open questions #1 (R2+C1) and #2 (P2 exit-DTE)** — these are real spec tensions surfaced by implementation; both deserve a sign-off before Phase 2 enumerator depends on them.

5. **`tests/fixtures/grammar_property_helpers.py` templates** — the 6 hypothesis templates encode "what a grammar-valid config of each hypothesis looks like." If the operator disagrees with a template, the property test is sampling from the wrong universe.

A quick smoke test the operator can run:

```bash
uv run python -c "
from pathlib import Path
from forge.grammar import load_grammar, validate
from tests.fixtures.strategy_configs import grammar_valid_baseline, minimal_registry_snapshot

grammar = load_grammar(Path('config/grammar.yaml'))
print(f'{len(grammar.rules)} rules loaded')
result = validate(grammar_valid_baseline(), grammar, minimal_registry_snapshot())
print(f'baseline valid={result.valid}, errors={result.errors}')
"
```

Should print `21 rules loaded` and `baseline valid=True, errors=()`.

---

## Recommendations for Phase 2 (Enumerator)

Phase 1 ships the *validator*; Phase 2 ships the *enumerator* that generates candidates the validator accepts. Key handoffs:

1. **The 6 templates in `grammar_property_helpers.py` are not the enumerator.** They are sampling fixtures for tests. The Phase 2 enumerator should be a CSP-style search over the grammar's allowed combinations, NOT an extension of these templates. Phase 2 will likely re-derive the per-hypothesis search shape from the registry + grammar rather than hard-coding templates.

2. **Determinism contract.** Hard rule #6 (deterministic enumeration) means `(grammar_version, registry_version, seed) → identical sequence`. Phase 2 must use `forge.core.seed.SeedHierarchy` (Phase 0 already wired) for any RNG; no naked `random.seed` (invariant test enforces).

3. **The grammar's validator is the post-enumeration gate.** Phase 2's enumerator should call `validate(cfg, grammar, registry)` on every generated candidate as the last step — both to confirm the enumerator respects the grammar and to surface enumerator bugs that produce invalid configs.

4. **Performance budget.** With validator < 10ms / config, the enumerator can afford to validate every candidate it considers without bottlenecking. No need for an enumeration-internal sub-grammar.

5. **The `custom_python` function-name registry will grow as new predicates land.** Phase 2 likely doesn't add new predicates, but Phase 3 (pre-filters) may. The `register()` helper in `custom_predicates.py` is the entry point.

---

## Awaiting

Phase 1 is **close-review** per the kickoff. **Awaiting operator review and explicit "proceed to Phase 2" sign-off.** Do not start Phase 2 (Enumerator) until the operator approves.

The operator's review will likely involve:

- Hand-crafting 2-3 grammar-valid `StrategyConfig`s and 2-3 intentionally-invalid ones; running them through `validate()`; confirming errors name the expected rule ids.
- Reviewing the open questions list (especially R2+C1 and P2 exit-DTE).
- Confirming D018's S4 reclassification reads correctly.

If anything fails review, the predicate function or `grammar.yaml` rule is the place to fix it — the dispatch + validator scaffolding shouldn't need touching.
