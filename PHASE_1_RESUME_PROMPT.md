# Forge — Phase 1 Resume Prompt

> **For the operator:** paste this as the first message of a fresh Forge agent session, with the working directory set to `/home/aj/proj/Forge/`. The agent should also have read access to `~/proj/PIPELINE.md`, `~/proj/crucible_contracts/`, and `~/proj/Crucible/CLAUDE.md`. **Prerequisite:** the `crucible_contracts` v1.2.0 release has been merged (commit SHA from the contracts-agent's report).
>
> The agent will read `docs/DESIGN.md`, `CLAUDE.md`, `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`, `OPEN_QUESTIONS.md`, `PHASE_0_HANDOFF.md`, and `CONTRACTS_V1_2_AGENT_PROMPT.md` on its own to recover state. No prior conversation history is needed.

---

You are resuming Forge at **Phase 1 (Grammar engine)**, which was paused at kickoff on 2026-05-13 pending a `crucible_contracts` upgrade. That upgrade is now complete: `crucible_contracts` has shipped **v1.2.0** adding `StrategyConfig.hypothesis`, `SignalSpec.role`, and reconciling the `IndicatorMetadata.family` enum to the spec's 11-family canonical list. Forge can now proceed.

`docs/DESIGN.md` is the authoritative spec. `CLAUDE.md` is your operating discipline doc. Read both before writing any code.

---

## Operating mode (unchanged from Phase 0)

Graduated autonomy. You work autonomously within Phase 1; you pause at the phase boundary for explicit operator sign-off before starting Phase 2. **Phase 1 is a close-review phase** per the original kickoff: the grammar is the conceptual core of Forge and a bug in any predicate type or rule binding corrupts every subsequent enumeration.

Specifically:
- You do **not** proceed past the Phase 1 boundary without writing `PHASE_1_HANDOFF.md` and getting explicit operator sign-off ("proceed to Phase 2").
- For ambiguities that would commit you to a hard-to-reverse path (predicate field paths, rule encoding choices, validator semantics), stop and ask immediately.
- For ambiguities that don't commit you, log to `OPEN_QUESTIONS.md` (with severity) and proceed with your best interpretation.

Persistent state files you maintain (already exist from Phase 0; append):
- `STATUS.md` — update after every module
- `IMPLEMENTATION_DECISIONS.md` — append-only; new decisions get fresh `D{NNN}` ids
- `OPEN_QUESTIONS.md` — append-only; mark resolutions in place
- `PHASE_1_HANDOFF.md` — written at end of Phase 1

End sessions before ~50K cumulative-token context. Re-read files via the file-read tool rather than relying on recall.

---

## First-session actions (before any production code)

Do these in order. The first response must be confirmation, not code.

### 1. Recover state

Read in this order (skim, don't memorize verbatim):
- `CLAUDE.md` — full
- `STATUS.md` — full
- `IMPLEMENTATION_DECISIONS.md` — full (D001 through D007 at minimum; D008+ if added by prior sessions)
- `OPEN_QUESTIONS.md` — full
- `PHASE_0_HANDOFF.md` — full (the four spec inconsistencies surfaced there are still open as doc-only items)
- `CONTRACTS_V1_2_AGENT_PROMPT.md` — full (informs you what the contracts agent was supposed to deliver; if you find drift, surface it)
- `docs/DESIGN.md` §3 (grammar — full, every subsection) and §11 (file layout)
- `~/proj/crucible_contracts/src/crucible_contracts/models.py` — full (you need the post-v1.2.0 surface, not your training-data version)
- `~/proj/crucible_contracts/src/crucible_contracts/_version.py` — verify `CONTRACT_VERSION = "1.2.0"`

### 2. Verify contracts v1.2.0 is what D007 specified

In a Python REPL (or a one-off script):
```python
from crucible_contracts import CONTRACT_VERSION, StrategyConfig, SignalSpec, IndicatorMetadata
import typing

assert CONTRACT_VERSION == "1.2.0"

# StrategyConfig must now have a required `hypothesis` field
sc_fields = StrategyConfig.model_fields
assert "hypothesis" in sc_fields
assert sc_fields["hypothesis"].is_required()

# SignalSpec must have a required `role` field
ss_fields = SignalSpec.model_fields
assert "role" in ss_fields
assert ss_fields["role"].is_required()

# IndicatorMetadata.family must be the 11-family canonical list
im_fields = IndicatorMetadata.model_fields
family_annot = im_fields["family"].annotation
assert typing.get_origin(family_annot) is typing.Literal
families = set(typing.get_args(family_annot))
expected = {
    "trend", "mean_reversion", "volatility", "iv_structure",
    "dealer_positioning", "flow", "macro", "calendar",
    "fundamental", "smart_money", "pairs",
}
assert families == expected, f"family enum mismatch: got {families}, expected {expected}"
```

If any assertion fails: **stop, do not proceed**, surface to the operator with what you found vs. what D007 required.

### 3. Bump Forge's expected contracts version

Edit `src/forge/core/contracts_check.py`:
```python
FORGE_EXPECTED_CONTRACT_VERSION: str = "1.2.0"
```

Run `pytest tests/integration/test_contracts_integration.py -v` — should pass.

Run the full suite: `pytest`. **Expected outcome**: Phase 0 tests may now fail if any of them constructed `StrategyConfig` or `SignalSpec` without the new required fields. Phase 0 didn't construct either (the only `StrategyConfig` reference is in `tests/integration/test_contracts_integration.py:test_contracts_models_importable`, which only checks the symbol exists), so likely zero failures. If any do fail, fix the fixtures by adding the new required fields with sensible defaults — log as `D{NNN}` if non-obvious.

### 4. Update state

- Append `D008` to `IMPLEMENTATION_DECISIONS.md` with the contracts v1.2.0 bump (link to the contracts commit SHA the operator provides).
- Update `STATUS.md`: phase 1 resumed; first deliverable started.

### 5. Confirm understanding

Before writing any production code, post a single confirmation message to the operator covering:
- The 6 deliverables for Phase 1 (§12).
- The 6 predicate types you'll implement (§3.4) and one sentence each about how the predicate evaluates against a `StrategyConfig`.
- The 21 grammar rules from §3.5 grouped by category, with the predicate type each will use (your proposed encoding).
- The work order you'll follow (one predicate at a time, TDD, etc.).
- Any new open questions you've discovered while reading §3.

**Wait for operator acknowledgment before writing any code.** The operator may correct your proposed predicate encodings.

---

## Phase 1 deliverables (FORGE_DESIGN.md §12)

1. **`grammar.yaml` parser and validator.** Loads `config/grammar.yaml` into a Pydantic-validated `Grammar` object.
2. **All 6 predicate types** (§3.4): `cardinality`, `requires`, `forbids`, `compatibility`, `numerical_range`, `custom_python`. Each is a distinct Pydantic discriminated-union variant; each has an `evaluate(config: StrategyConfig, registry: RegistrySnapshot) -> bool` method (or equivalent functional form).
3. **Rule loader with version archive.** When loading `grammar.yaml`, check that the `grammar_version` field matches the on-disk archive: any non-archived version refuses to load.
4. **Validator: `validate(config, grammar, registry) -> ValidationResult`** returning `valid: bool` and `errors: tuple[str, ...]`. Each error names the rule id and the field/value that violated it.
5. **`config/grammar.yaml`** populated with **all 21 v1 rules** from §3.5 (S1-S5, C1-C4, P1-P4, E1-E3, R1-R3, X1-X2). The rules are operator-owned: implement as written; do not silently restate. See D001 — count is 21, not 25.
6. **`docs/GRAMMAR.md`** with one paragraph per rule explaining: what it does in words, why it exists, what the cost is (how much of the search space it eliminates), what evidence would justify relaxing it.

**Acceptance criteria for the deliverable** (§12 Phase 1):
- Any `StrategyConfig` can be validated against the v1 grammar in **< 10ms**.
- Property test: 1000 random *grammar-valid* configs all pass validation; 1000 random *grammar-invalid* configs all fail with at least one named error.

---

## Recommended work order (TDD throughout)

Each predicate type follows red → green → refactor with a test in `tests/unit/test_grammar/` first.

1. **Design phase** (no code; just thinking)
   - Sketch the Pydantic `Rule` model (id, category, version, active, rationale_ref, predicate, cost_estimate, evidence_to_relax — see §3.3).
   - Sketch the predicate discriminated union: each variant has a `type` field that picks the implementation.
   - Decide how `compatibility` predicates with named lookback tiers (§3.4 example) resolve a signal's "lookback class" — likely via a registry lookup against `IndicatorMetadata.lookback`.
   - Decide how `custom_python` predicates resolve function names — registry pattern (a dict mapping name → callable in `forge.grammar.custom_predicates`), never `exec()` / `eval()` against the YAML.
   - Write this up in `IMPLEMENTATION_DECISIONS.md` as a single `D{NNN}` entry before implementation.

2. **Schema files** (`src/forge/grammar/models.py`)
   - Pydantic `Rule`, `Grammar`, and the six predicate variants. Discriminated union via `Annotated[Union[...], Field(discriminator="type")]`.

3. **Per-predicate implementations** (`src/forge/grammar/predicates.py`)
   In this order, each with its own unit-test file:
   - `cardinality` — simplest; test against fields like `hypothesis` (single value), `signals` (count), `signals[?(@.role=="directional")]` (count of matches).
   - `numerical_range` — second-simplest; test against `params.rsi_period`, `sizer.per_trade_risk_pct`.
   - `requires` — test against S5 (hypothesis → exits inclusion).
   - `forbids` — test against S5 (trend_continuation forbids hard_profit_target).
   - `compatibility` — test against S4 (lookback × dte_bucket compatibility table).
   - `custom_python` — test with a stub predicate (`always_pass`, `always_fail`); the predicate-registry pattern is the load-bearing piece.

4. **Validator** (`src/forge/grammar/validator.py`)
   - Iterates the grammar's rules, evaluates each predicate, accumulates errors.
   - Short-circuits on the first rule that's marked `cost_estimate: high` if perf demands it (decide via test); otherwise evaluate all rules so errors are exhaustive.

5. **Loader** (`src/forge/grammar/loader.py`)
   - Parses `config/grammar.yaml` → `Grammar`. Pydantic validates the shape.
   - Validates that every rule's `rationale_ref` resolves to a section header in `docs/GRAMMAR.md` — this is a soft check at load time; a pre-commit hook does the strict check.

6. **Archive helpers** (`src/forge/grammar/archive.py`)
   - On `grammar.yaml` load, hash the file; compare to the latest archived version's hash; if different *and* `grammar_version` hasn't bumped, refuse to load (a `GrammarVersionError`).
   - On version bump, copy prior version to `config/grammar_archive/v{N}.yaml`.

7. **The 21 rules** (`config/grammar.yaml`)
   - Write all 21. Use the §3.4 predicate type that best expresses each rule. Several will need careful predicate-path construction (e.g., S2 cardinality on `signals[?(@.role=="directional")]`).
   - For predicates that need the registry to evaluate (e.g., C1's "no two indicators from the same family" requires looking up each indicator's family in `IndicatorMetadata`), document the dependency in the rule's body and ensure your validator passes a `RegistrySnapshot`.

8. **`docs/GRAMMAR.md`** — one section header per rule id, matching the YAML's `id` field exactly. Pre-commit hook (next step) enforces sync.

9. **Pre-commit hooks** (`.pre-commit-config.yaml`)
   - **Version-bump scanner**: if `config/grammar.yaml` is staged, ensure either (a) the file is byte-identical to HEAD or (b) `grammar_version` is bumped *and* the prior version is staged into `config/grammar_archive/`. Implement as a small Python script in `scripts/check_grammar_version_bump.py`.
   - **Grammar ↔ GRAMMAR.md sync**: if either is staged, ensure every rule id in `grammar.yaml` has a matching `## {id}:` heading in `docs/GRAMMAR.md`. Implement as a small Python script in `scripts/check_grammar_doc_sync.py`.
   - Wire both hooks into `.pre-commit-config.yaml`.

10. **Property tests** (`tests/statistical/test_grammar_property.py` or `tests/unit/test_grammar/test_property.py`)
    - **Valid config generator**: a Hypothesis strategy that constructs grammar-valid `StrategyConfig`s by sampling within the constraints. Hard to write correctly; iterate.
    - **Invalid config generator**: take a valid config and mutate exactly one field to break exactly one rule; record which rule was broken; assert the validator reports that rule.
    - 1000 valid → all pass. 1000 invalid → all fail with the expected rule id.

11. **Performance test** (`tests/integration/test_grammar_perf.py`)
    - Validate 100 configs; assert mean < 10ms (per §12 Phase 1 deliverable).

12. **`PHASE_1_HANDOFF.md`** following the template in the original kickoff prompt.

---

## Hard rules (carried forward from the original kickoff)

The same 10 hard rules from `CLAUDE.md`. The ones most relevant to Phase 1:

1. **The 21 v1 grammar rules in §3.5 are operator-owned.** Implement as written. If a rule looks wrong, log to `OPEN_QUESTIONS.md` and surface at the phase boundary — never silently change.
2. **No imports from Crucible internals.** All inter-system access via `crucible_contracts`. The grammar validator references `crucible_contracts.StrategyConfig`, `SignalSpec`, `IndicatorMetadata`, `RegistrySnapshot` — never Crucible's internal types.
5. **No LLM in the production loop.** The grammar validator is deterministic Python.
7. **The grammar must not permit `equity` as a signal family** (§13.6). Validator rejects configs with `equity` family. Add an invariant test in `tests/invariants/`.
8. **No `datetime.now()`, no naked `random.seed()`** outside the blessed modules. Invariant tests already enforce.
10. **Version bumps required on `grammar.yaml` changes.** Pre-commit hook enforces (step 9 above).

---

## When to stop and ask immediately during Phase 1

- A `§3.5` rule appears in tension with itself or with another rule, or with the post-v1.2.0 contracts surface.
- A predicate type from `§3.4` cannot cleanly express a `§3.5` rule (you'd need a custom_python or a contracts gap to encode it).
- The `custom_python` predicate's function-resolution pattern hits a security or correctness concern.
- A property test reveals a rule that fires in unexpected ways.
- Performance falls below the 10ms target and you can't see why within an hour.
- The contracts v1.2.0 release doesn't match what D007 / the contracts prompt specified.
- You discover the §3.5 rule list is missing context the operator should have given (e.g., a parameter range that needs a value).

---

## Phase boundary: close review

When you reach Phase 1 completion:

1. All Phase 1 deliverables shipped.
2. All tests green; coverage non-trivial on `src/forge/grammar/`.
3. `ruff check`, `mypy --strict` clean.
4. The 21 rules are present in `grammar.yaml`; matching paragraphs in `GRAMMAR.md`.
5. Pre-commit hooks fire on test changes (run `pre-commit run --all-files`).
6. Write `PHASE_1_HANDOFF.md` using the same template as `PHASE_0_HANDOFF.md`.
7. Update `STATUS.md`: Phase 1 complete; awaiting close review.
8. Post a tight ~200-word summary to the operator.
9. **Stop. Do not start Phase 2.** Phase 1's close review is where the grammar gets validated; bugs caught here save the next 8 weeks.

The operator's close review will involve hand-crafting a few `StrategyConfig`s (some intended to pass, some intended to fail specific rules) and running them through your validator. Be ready to explain any rule encoding choice that the operator questions.

---

## Repo state at handoff (your starting point)

Two commits exist on `main`:
- `74f0ffa` phase 0: bootstrap
- `1af97dd` phase 1 paused at kickoff: contracts gap (Q7) → D007 → contracts v1.2.0 prompt

Working tree should be clean. If it isn't, investigate before doing anything else.

The next commit you author should be either:
- `phase 1: contracts v1.2.0 bump + grammar models scaffolding` (after step 3-4 above and the schema-files step), or
- `phase 1: cardinality predicate + tests` (if you bundled the schema with the first predicate's test)

Commit per module per the kickoff's working pattern; don't bundle the entire phase into one commit.

---

**End of resume prompt.**
