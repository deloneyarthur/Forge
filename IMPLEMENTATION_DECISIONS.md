# Forge — Implementation Decisions Log

Append-only. Each entry: ID, date, spec section, decision, rationale, alternatives considered, action.

Order is chronological. Decisions are referenced from `STATUS.md`, `OPEN_QUESTIONS.md`, and `PHASE_N_HANDOFF.md`.

---

## D001 — 2026-05-13 — v1 grammar contains 21 rules, not 25

**Spec section:** §3.5, §3.6, §14
**Decision:** Implement Phase 1 grammar with the 21 rules enumerated in §3.5. The "25 rules" count in §3.6 and §14 is a typo (operator confirmation Q1, 2026-05-13).
**Rationale:** §3.5 is the authoritative listing; §3.6 is a derived summary. Operator confirmed possibility (a): §3.6's "25" is a typo for 21.
**Alternatives considered:** (b) draft 4 missing rules from category exemplars in §3.2; (c) treat §3.6 as forward-looking for v1.1. Both rejected by operator.
**Action:** Phase 1 `grammar.yaml` will contain exactly 21 rules (S1-S5, C1-C4, P1-P4, E1-E3, R1-R3, X1-X2). CLAUDE.md hard rule #1 reads "21 v1 grammar rules." Surface the doc typo as a recommendation in `PHASE_0_HANDOFF.md`.

---

## D002 — 2026-05-13 — crucible_contracts location

**Spec section:** kickoff prompt
**Decision:** `crucible_contracts` is at `/home/aj/proj/crucible_contracts/`, referenced as `../crucible_contracts` from Forge.
**Rationale:** The kickoff prompt's `~/projects/crucible_contracts/` path does not exist on this workstation (operator confirmation Q2, 2026-05-13). Actual sibling path is `/home/aj/proj/crucible_contracts/`.
**Alternatives considered:** Install from a published wheel — not applicable; package is local-only.
**Action:** `pyproject.toml` declares `crucible_contracts` as a path dep via `[tool.uv.sources] crucible_contracts = { path = "../crucible_contracts", editable = true }`.

---

## D003 — 2026-05-13 — Spec file path → `docs/DESIGN.md`

**Spec section:** §11
**Decision:** Move `FORGE_DESIGN.md` from repo root to `docs/DESIGN.md`, matching §11's prescribed layout and Crucible's convention.
**Rationale:** §11 explicitly specifies `docs/DESIGN.md` as the spec location. The current root-level `FORGE_DESIGN.md` predates the repo and was just where the file was authored. Symmetry with Crucible's `CLAUDE.md` "Source of truth: `docs/DESIGN.md`."
**Alternatives considered:** Keep at root for path-stability of operator references — rejected; the operator can update references once.
**Action:** `git mv FORGE_DESIGN.md docs/DESIGN.md` before first commit. CLAUDE.md references `docs/DESIGN.md`.

---

## D004 — 2026-05-13 — Synthetic Crucible runs DB fixture (Phase 0 read-path proof)

**Spec section:** §12 Phase 0, §9.2
**Decision:** Build a minimum synthetic Crucible runs DB in `tests/fixtures/synthetic_crucible_db.py`. Schema covers the four tables `crucible_contracts.queries` reads from: `runs`, `promotion_decisions`, `metrics`, `trades`. Tests assert that the empty DB returns zero gated runs through `crucible_contracts.get_recent_gated_runs`.
**Rationale:** Crucible isn't built yet; Forge's §12 Phase 0 deliverable "first successful read of Crucible's runs DB" requires *something* to read. Schema mirrors `crucible_contracts.queries._GATED_QUERY_BASE` column set. Operator confirmed default (Q5).
**Alternatives considered:** Mock the `get_recent_gated_runs` function — rejected; defeats the purpose of integration verification. Pin to Crucible's real DDL — not available until Crucible is built.
**Action:** Fixture exports `ephemeral_crucible_db(tmp_path)` context manager and `build_synthetic_crucible_db(path)`. Tests in `tests/integration/test_crucible_read.py` use them. Retire fixture when Crucible's real DDL is published.

---

## D005 — 2026-05-13 — CLAUDE.md sourced from FORGE_DESIGN.md + kickoff

**Spec section:** kickoff prompt
**Decision:** New `CLAUDE.md` borrows only the *outline* of Crucible's CLAUDE.md (intro / TDD / hard rules / blessed APIs / operation order / style / phase discipline / when-to-stop / context discipline / communication / quick map). All content populated from `FORGE_DESIGN.md` and the kickoff prompt. TDD section included.
**Rationale:** Operator confirmation Q3 (2026-05-13). Crucible's CLAUDE.md references Crucible-specific files (`core/seed.py` at Crucible-internal paths, `~/optbt_runs/`, version-bump for indicator math, bar-level event ordering) that don't apply to Forge.
**Alternatives considered:** Skip CLAUDE.md — rejected, discipline doc is needed. Copy verbatim and edit — rejected, too easy to leave Crucible-isms in.
**Action:** `/home/aj/proj/Forge/CLAUDE.md` written; references Forge's blessed APIs, per-batch operation order, hard rules, and phase discipline.

---

## D007 — 2026-05-13 — Q7 resolution: extend `crucible_contracts` to v1.2.0 with the 11-family canonical list

**Spec section:** OPEN_QUESTIONS.md Q7; FORGE_DESIGN.md §3.5
**Decision:** Extend `crucible_contracts` (minor version bump 1.1 → 1.2) to add the fields the §3.5 grammar rules reference:
- `StrategyConfig.hypothesis: Literal["trend_continuation","mean_reversion","regime_arbitrage","relative_value","volatility_event","tail_hedge"]` (matches §3.5 S1).
- `SignalSpec.role: Literal["directional","regime_filter","filter","confluence"]` (matches §3.5 S2/S3).
- `IndicatorMetadata.family` enum reconciled to the **spec's 11-family list** (canonical): `trend, mean_reversion, volatility, iv_structure, dealer_positioning, flow, macro, calendar, fundamental, smart_money, pairs`. Rename contracts' current names (`mean_revert → mean_reversion`, `price_trend → trend`, `realized_vol → volatility`, `iv → iv_structure`, `dealer → dealer_positioning`); drop `multi_factor`; add `flow, calendar, fundamental`.
- Mandatory exits stay at the contracts' current **4** (`expiry_exit, theta_cliff_exit, earnings_exit, liquidity_exit`). Recommend amending FORGE_DESIGN.md §3.5 E1 to match (separate doc-update task).
**Rationale:** Operator confirmation 2026-05-13 (chose option 1 + spec's 11-family list). The kickoff prompt anticipates this exact situation as a "contracts gap to surface, not work around." Encoding via `params` dicts (option 2) is stringly-typed and brittle; shipping a weaker grammar (option 4) abandons the most fundamental S-rules. Option 1 keeps the contracts package as the single source of truth for inter-system shapes.
**Alternatives considered:** Option 2 (params shimming), option 4 (defer to v1.1); both rejected by operator. Family-list options: 9-family (contracts' current) — rejected, less domain-faithful; hybrid union — rejected, ambiguous; defer — rejected, leaves C-rules incomplete.
**Action:** `crucible_contracts` repo gets v1.2.0 bump with the additive field/enum changes plus tests. Forge bumps `FORGE_EXPECTED_CONTRACT_VERSION` to `"1.2.0"`. Forge is **paused** at Phase 1 kickoff until contracts ships v1.2.0. Owner of the contracts change is **TBD** — awaiting operator decision (this session, separate session, or manual).
**Breaking-change note:** the family-enum rename is technically not additive (`mean_revert` → `mean_reversion`), so a SemVer purist would argue this is a major bump 1.1 → 2.0 rather than minor. However: no existing strategy configs reference the old names yet (Crucible and Forge are pre-build; no production data), so the rename is harmless in practice. Treat as minor bump with a release note.

---

## D006 — 2026-05-13 — Inbox file format is JSON via `crucible_contracts`, not YAML

**Spec section:** FORGE_DESIGN.md §7.2; `crucible_contracts/queries.py` ADR comment
**Decision:** Forge's submitter uses `crucible_contracts.submit_candidate(config, inbox_path)`, which writes **JSON** to `{inbox_path}/{config_hash}.json` (atomic tmp-then-rename). Forge does not implement a separate YAML inbox writer.
**Rationale:** `crucible_contracts/queries.py` carries an explicit ADR: "PIPELINE.md and CRUCIBLE_CHANGES.md references to YAML inboxes are forward-looking; the contracts ship JSON as v1." The contracts package is the inter-system surface (hard rule #2); its format wins over the FORGE_DESIGN.md §7.2 example. Avoids a fourth external dep (pyyaml) for the contracts package and keeps round-tripping through `model_dump_json()` / `model_validate_json()` lossless.
**Alternatives considered:** (a) Write YAML in Forge per §7.2 — rejected; would diverge from the contracts-blessed inbox format and require Crucible to parse two formats. (b) Propose YAML support in contracts — possible future work; not blocking Phase 0.
**Action:** CLAUDE.md "Blessed APIs" section names `submit_candidate` as the inbox write path and notes the JSON-vs-YAML divergence. Phase 4 submitter implementation will call this helper directly. Surface the doc inconsistency as a recommendation in `PHASE_0_HANDOFF.md` (FORGE_DESIGN.md §7.2 should be updated to reflect the contracts package's reality).

---

## D008 — 2026-05-13 — `crucible_contracts` v1.2.0 adopted; Phase 1 unblocked

**Spec section:** OPEN_QUESTIONS.md Q7; D007; FORGE_DESIGN.md §3.5
**Decision:** Bump `FORGE_EXPECTED_CONTRACT_VERSION` from `"1.1.0"` to `"1.2.0"` now that the contracts repo has shipped v1.2.0 (commit `7d0f359` on `crucible_contracts/master`). Phase 1 grammar work proceeds against the v1.2.0 surface.
**Rationale:** D007's resolution required `crucible_contracts` to add `StrategyConfig.hypothesis` (Literal of 6), `SignalSpec.role` (Literal of 4), and reconcile `IndicatorMetadata.family` to the spec's 11-family canonical list. Verification script (PHASE_1_RESUME_PROMPT.md step 2) confirms all four assertions hold against the installed package: hypothesis is required with the 6 expected values, role is required with the 4 expected values, family is the 11-value canonical Literal `{trend, mean_reversion, volatility, iv_structure, dealer_positioning, flow, macro, calendar, fundamental, smart_money, pairs}`. `MANDATORY_EXIT_IDS` remains a frozenset of 4 (`expiry_exit, theta_cliff_exit, earnings_exit, liquidity_exit`) per D007.
**Alternatives considered:** None — D007 already settled the design space; this is the implementation of that decision.
**Action:** Edited `src/forge/core/contracts_check.py`. Full test suite still 18/18 green; `ruff check` clean; `mypy --strict` clean. Q7 marked resolved in `OPEN_QUESTIONS.md`. Phase 1 proceeds.
**Note on §3.5 E1:** the spec still says "Every strategy includes `expiry_exit`, `theta_cliff_exit`, `earnings_exit`" (3 exits); contracts enforces 4 (adds `liquidity_exit`). Per D007 the contracts count wins. E1's `requires`-style predicate in `grammar.yaml` will reference all 4 mandatory exits. The doc inconsistency is logged for a separate `docs/DESIGN.md` cleanup pass (already on the PHASE_0_HANDOFF.md "spec inconsistencies" list).

---

## D009 — 2026-05-13 — Predicate-path resolver supports both §3.4 sugar and JSONPath

**Spec section:** §3.4
**Decision:** The path resolver inside the rule engine accepts two equivalent forms:
- §3.4 sugar (documented): `signals.role.directional` meaning "filter `signals` by `role == "directional"`, count or project the result".
- JSONPath-ish primitive (internal): `signals[?(@.role=="directional")]`.
Both compile to the same AST; rule authors are encouraged to use the sugar in `grammar.yaml`.
**Rationale:** Operator confirmation 2026-05-13 (Phase 1 kickoff Q1). The §3.4 example syntax is what the operator + Claude have been reading, so authoring stays familiar; the JSONPath form is more explicit and useful for tests + complex paths. Using one syntax exclusively would either tie us to underspecified sugar (drift risk) or burden every author with verbose syntax.
**Alternatives considered:** sugar only (rejected — too underspecified for compound paths); JSONPath only (rejected — operator-facing yaml gets noisier than §3.4 implies).
**Action:** `forge.grammar.path_resolver` exposes one `resolve(config, path) -> list[Any]` function with both syntaxes. Tested in `tests/unit/test_grammar/test_path_resolver.py`.

---

## D010 — 2026-05-13 — S4 lookback class thresholds and multi-indicator rule

**Spec section:** §3.5 S4
**Decision:** Bucket `IndicatorMetadata.lookback` (days) into the three lookback classes used by S4:
- `short_lookback`: `lookback <= 6`
- `medium_lookback`: `7 <= lookback <= 89`
- `long_lookback`: `lookback >= 90`
When the directional signal references multiple indicators, take the **max** lookback (the longest-tail indicator dominates the holding period).
**Rationale:** Operator confirmation 2026-05-13 (Phase 1 kickoff Q2). §3.5 S4 gives examples ("RSI<5", "RSI 7-21", "12-month momentum") but no thresholds; these are the smallest-integer thresholds that match every example shown. Max-of-indicators is the conservative bucketing — a config with a 5-day + 90-day pair lives in `long_lookback`, not `short`.
**Alternatives considered:** mean-lookback (rejected — masks tail behavior); min-lookback (rejected — would let a 1-day indicator dominate a 90-day signal); operator-specified per-indicator buckets (rejected — adds registry surface for negligible gain).
**Action:** `forge.grammar.custom_predicates.lookback_class(indicators, registry)` helper used by S4 and any future rules that need the bucket. Constants live in `forge.grammar.constants`.

---

## D011 — 2026-05-13 — Canonical exit-ID set lives in `crucible_contracts` (v1.3.0)

**Spec section:** §3.5 (S5, E1, E2, E3); CLAUDE.md hard rule #2
**Decision:** Add a `KNOWN_EXIT_IDS: frozenset[str]` constant to `crucible_contracts` containing the full canonical set of exit IDs the v1 grammar references. v1.3.0 minor bump. The set is the union of:
- The 4 existing `MANDATORY_EXIT_IDS`: `expiry_exit`, `theta_cliff_exit`, `earnings_exit`, `liquidity_exit`.
- 7 hypothesis-required exits (§3.5 S5): `trailing_atr`, `time_stop`, `regime_flip_exit`, `convergence_exit`, `iv_crush_exit`, `event_passed_exit`, `roll_on_schedule_exit`.
- 1 commonly-forbidden exit (§3.5 S5 trend_continuation forbids): `hard_profit_target`.
- 2 stop-loss family members (D012, §3.5 E2): `premium_stop_loss`, `atr_underlying_stop_loss`.
Total: 14 ids.
**Rationale:** Operator confirmation 2026-05-13 (chose path "b" — contracts owns the canonical list, even at the cost of a small minor bump). Hard rule #2 ("missing model is a contracts gap to surface, not to work around") applies: putting the list in Forge would mean Crucible's validators would silently accept the same names without knowing they're canonical — a divergence trap. Contracts is the integration boundary; it should own the vocabulary.
**Alternatives considered:** (a) Forge-local list — rejected per operator. (c) Make exit IDs free-form and rely on registry consistency at submission time — rejected; grammar needs to refuse unknown names at validate time, before submission.
**Action:** v1.3.0 contracts release adds `KNOWN_EXIT_IDS` and `STOP_LOSS_EXIT_IDS` (D012) constants and re-exports them. Forge bumps `FORGE_EXPECTED_CONTRACT_VERSION` → `"1.3.0"` and references the constants from custom_predicates. Process decision pending: drive inline this session or spawn a fresh contracts agent (D007 / v1.2.0 pattern).
**Doc-cleanup note:** §3.5 references exit IDs by name without listing them as a canonical set anywhere; recommend adding a paragraph to §3.5 (or §13) enumerating the v1 known-exit vocabulary and pointing readers at `crucible_contracts.KNOWN_EXIT_IDS`.

---

## D012 — 2026-05-13 — E2 stop-loss exit-ID classifier

**Spec section:** §3.5 E2
**Decision:** Stop-loss exit IDs for the "at most 2 stop-loss exits" rule are: `premium_stop_loss`, `atr_underlying_stop_loss`, `trailing_atr`. (Three names; the rule still caps the count at 2.) Lives in `crucible_contracts` as `STOP_LOSS_EXIT_IDS: frozenset[str]` (subset of `KNOWN_EXIT_IDS`).
**Rationale:** Operator confirmation 2026-05-13 (Phase 1 kickoff Q4). §3.5 E2 says "one premium stop + one underlying-ATR stop is the max"; trailing-ATR is a third commonly-stacked stop and is included so E2 catches over-stacked configs. Lives in contracts (not Forge) for the same reason as D011: the vocabulary is shared across systems.
**Alternatives considered:** Restrict to 2 names (premium + ATR) — rejected; trailing_atr in combination with the other two is a common over-specification pattern E2 should refuse.
**Action:** Contracts v1.3.0 exports `STOP_LOSS_EXIT_IDS`. Forge's E2 custom predicate counts `len({e.id for e in config.exits} & STOP_LOSS_EXIT_IDS)` and rejects > 2.

---

## D013 — 2026-05-13 — R1's directional-family clause is redundant; collapse to hypothesis-only

**Spec section:** §3.5 R1, C2
**Decision:** R1's `if` clause encodes only `hypothesis == "mean_reversion"` (drop the AND-clause on directional family). C2 already guarantees that mean_reversion hypothesis ↔ mean_reversion-family directional signal, so the second clause is tautological.
**Rationale:** Operator confirmation 2026-05-13 (Phase 1 kickoff Q5). Carrying a redundant clause adds maintenance cost (if C2 changes, R1 silently becomes stricter than intended). The simpler form is equivalent under v1 grammar.
**Alternatives considered:** Keep the clause verbatim — rejected; tautologies in rule logic are a recipe for subtle drift later.
**Action:** Document R1's simplified form in `docs/GRAMMAR.md`; flag in `docs/DESIGN.md` §3.5 cleanup list.

---

## D014 — 2026-05-13 — §3.5 E1 mandatory-exit count documentation lags contracts

**Spec section:** §3.5 E1 (3 exits cited); contracts `MANDATORY_EXIT_IDS` (4 ids)
**Decision:** Forge's E1 predicate validates against the contracts' 4-id set, not the spec's 3-id list. The spec needs a §3.5 E1 update to add `liquidity_exit` and to make the relationship to `crucible_contracts.MANDATORY_EXIT_IDS` explicit (cross-reference rather than re-statement).
**Rationale:** Operator confirmation 2026-05-13 (Phase 1 kickoff Q6) + D007 (which set the count at 4 in contracts). Contracts is the source of truth at the integration boundary.
**Alternatives considered:** Change contracts back to 3 — rejected by D007. Carry both — rejected; one canonical source.
**Action:** E1 predicate references `crucible_contracts.MANDATORY_EXIT_IDS` directly (no constant duplication). Add to `docs/DESIGN.md` cleanup list (now 5 doc-cleanup items, all non-blocking).

---

## D015 — 2026-05-13 — S5 stays as one rule; `requires`/`forbids` covered via synthetic test rules

**Spec section:** §3.5 S5; D001 (rule count = 21)
**Decision:** S5 is encoded as a single `custom_python` predicate (`exits_match_hypothesis`) holding the 6-row hypothesis → required/forbidden exits table. Predicate types `requires` and `forbids` are implemented and exercised via synthetic rules in `tests/unit/test_grammar/test_predicates_requires.py` / `test_predicates_forbids.py`, but are **not** used by any v1 grammar rule.
**Rationale:** Operator confirmation 2026-05-13 (Phase 1 kickoff Q7) + D001 (count locked at 21). Splitting S5 into ~10 `requires`/`forbids` sub-rules would increase the count and obscure the operator-owned rule identity. Synthetic-rule unit tests satisfy the §12 deliverable that "all 6 predicate types are implemented."
**Alternatives considered:** Split S5 into S5a-S5j (rejected — changes the rule count and dilutes a single operator-owned concept across multiple ids). Skip implementing `requires`/`forbids` for v1 (rejected — §12 deliverable explicitly requires all 6 predicate types).
**Action:** `forge.grammar.predicates.requires` and `forge.grammar.predicates.forbids` shipped with full impl + tests; v1 `grammar.yaml` does not reference either; v1.1 grammar may.

---

## D016 — 2026-05-13 — `crucible_contracts` v1.3.0 adopted; exit-id vocabulary in place

**Spec section:** D011; D012
**Decision:** Bump `FORGE_EXPECTED_CONTRACT_VERSION` from `"1.2.0"` to `"1.3.0"`. The contracts package now exports `KNOWN_EXIT_IDS` (14 ids) and `STOP_LOSS_EXIT_IDS` (3 ids) per D011/D012; Forge's grammar predicates resolve their exit-id vocabulary against these constants rather than carrying a local list.
**Rationale:** Inline contracts side-trip in this session (operator chose path "drive inline" 2026-05-13). Contracts commit `1d5b51f`. v1.3.0 contracts test surface: all 142 tests pass; 100% coverage; ruff + mypy strict clean.
**Alternatives considered:** Spawn a fresh contracts agent (D007/v1.2.0 pattern) — rejected by operator as overhead for a small additive bump.
**Action:** `src/forge/core/contracts_check.py` updated. All 18 Forge tests still green; ruff + mypy strict clean. Grammar predicates `S5`, `E1`, `E2`, `E3`, plus the `KNOWN_EXIT_IDS` membership check used by every exit-touching rule, now have a single authoritative vocabulary.

---

## D017 — 2026-05-13 — Grammar rule-engine architecture (pre-code)

**Spec section:** DESIGN.md §3.3, §3.4; resume-prompt work-order step 1
**Decision:** Architect the Phase 1 grammar engine as a layered Pydantic + functional stack:

1. **Pydantic `Predicate` discriminated union** in `src/forge/grammar/models.py`:
   - One concrete subclass per §3.4 type (`CardinalityPredicate`, `RequiresPredicate`, `ForbidsPredicate`, `CompatibilityPredicate`, `NumericalRangePredicate`, `CustomPythonPredicate`).
   - Each frozen, `extra="forbid"`, with a `type: Literal["..."]` discriminator field matching §3.4's `type:` key in YAML.
   - Union assembled via `Annotated[Union[...], Field(discriminator="type")]` so YAML parses straight into the right subclass.
2. **Pydantic `Rule`** with the §3.3 shape (`id`, `category`, `version: int`, `active: bool`, `rationale_ref`, `predicate`, `cost_estimate: Literal["low"|"medium"|"high"]`, `evidence_to_relax: tuple[str, ...]`).
3. **Pydantic `Grammar`** wrapper carrying `grammar_version: str`, `generated_at: datetime | None`, `rules: tuple[Rule, ...]`, with a model-validator that asserts rule-id uniqueness.
4. **Path resolver** in `src/forge/grammar/path_resolver.py`: pure functional `resolve(config: BaseModel | dict, path: str) -> list[Any]` returning a list of matched nodes (zero, one, or many). Supports both §3.4 sugar (`signals.role.directional`) and the JSONPath primitive (`signals[?(@.role=="directional")]`) per D009; both compile to the same internal AST.
5. **Predicate impls** in `src/forge/grammar/predicates.py` (one function per type): each takes `(predicate, config, registry) -> PredicateResult` where `PredicateResult` is a frozen dataclass `(passed: bool, detail: str)`. Functions are pure (no side effects); registry is the `crucible_contracts.RegistrySnapshot`.
6. **Custom-predicate registry**: `forge.grammar.custom_predicates.REGISTRY: Mapping[str, Callable[[StrategyConfig, RegistrySnapshot], PredicateResult]]`. Resolved at predicate-evaluation time; unknown name → `GrammarLoadError` at *load* time (not at evaluation). **No `exec()`/`eval()` against YAML.** This is the load-bearing security/correctness piece.
7. **Validator** in `src/forge/grammar/validator.py`: `validate(config, grammar, registry) -> ValidationResult` iterates rules in declaration order, evaluates each predicate, and returns `ValidationResult(valid=all_passed, errors=tuple(detail strings))`. No short-circuit — full error list (helps property tests pinpoint failing rules).
8. **Loader** in `src/forge/grammar/loader.py`: thin wrapper that reads `config/grammar.yaml`, runs `Grammar.model_validate(yaml.safe_load(...))`, and verifies (a) every `rationale_ref` resolves to a section header in `docs/GRAMMAR.md` (soft warning at load; strict check via pre-commit) and (b) every `custom_python` predicate's `function` name is in the custom-predicate registry.
9. **Archive helpers** in `src/forge/grammar/archive.py`: on load, hash `config/grammar.yaml` and compare against the latest version under `config/grammar_archive/`; raise `GrammarVersionError` on hash drift without a version bump. On version bump, helper copies the prior `grammar.yaml` to `config/grammar_archive/v{N}.yaml`.

**Rationale:**
- Discriminated unions over `match` dispatch keep the YAML→Python boundary minimal and let `mypy --strict` reason about each variant's required fields.
- The pure-functional predicate impls plus an immutable `Grammar` make property tests trivial — no shared state to reset.
- Separating the path resolver from the predicate impls means S2/S3-style filter-and-count logic lives in one place and is unit-testable directly.
- The custom-predicate registry pattern is what closes the §3.4 escape-hatch's security surface: function names are looked up in a Python dict, never resolved against arbitrary strings.

**Alternatives considered:**
- One mega-Predicate model with optional fields per type, dispatched by `if-elif` — rejected; loses type narrowing and lets invalid combos slip past Pydantic.
- Inline custom-predicate functions inside each `Rule` (lambda-style) — rejected; YAML can't carry Python callables without eval.
- Short-circuit-on-first-failure validator — rejected for v1; full error list is more useful in property tests and operator review.

**Action:** This decision precedes any code. Implementing in the resume-prompt order: `models.py` → `path_resolver.py` → `predicates.py` (cardinality first) → tests → commit. `custom_predicates.py`, `validator.py`, `loader.py`, `archive.py` follow in their respective sub-tasks.

---

## D018 — 2026-05-13 — S4 reclassified to `custom_python`; compatibility stays generic

**Spec section:** DESIGN.md §3.4, §3.5 S4; D015 (synthetic-rule pattern); pre-code confirmation
**Decision:** Encode S4 ("DTE bucket matches the signal's natural holding period") as a `custom_python` predicate using a `lookback_class_matches_dte_bucket` function rather than as a `compatibility` predicate. The `compatibility` predicate is implemented as a generic table-lookup primitive: `field1`'s resolved value is the key into `table`; the resolved key's tuple must contain `field2`'s value. No domain-aware transformations live inside the predicate. `compatibility` gets unit-test coverage via synthetic rules (same pattern as `requires`/`forbids` under D015).
**Rationale:** §3.4's compatibility example uses `field1: signals.directional.lookback` — a path that doesn't resolve cleanly against `StrategyConfig` because `SignalSpec` has no `lookback` attribute (the lookback lives on `IndicatorMetadata.lookback` in the registry, indirected via `SignalSpec.indicators[]`). For the example to evaluate as written, the resolver would need registry-aware semantics, OR the predicate itself would need a class-extractor sub-registry. Both add structural coupling between the predicate primitive and the registry layer. Keeping `compatibility` as a generic key→target lookup matches the rule-engine architecture in D017 (pure-functional predicates with no implicit dependencies). The registry-aware logic for S4 lives where it belongs — in `forge.grammar.custom_predicates.lookback_class_matches_dte_bucket`, which can use the D010 bucketing helper and the registry directly.
**Alternatives considered:**
- Add `class_resolver` field to `CompatibilityPredicate` naming a registered class-extractor function — rejected; adds an internal sub-registry of single-purpose functions, blurs the line between `compatibility` (declarative) and `custom_python` (escape hatch).
- Make the path resolver registry-aware so `signals.directional.lookback` works — rejected; couples path semantics to runtime data and makes the resolver dual-rooted.
- Keep S4 as `compatibility` but precompute the lookback class in the validator before evaluation — rejected; splits the predicate semantics across two layers.
**Action:** Phase 1 module 4 ships `compatibility` as a generic primitive with synthetic-rule tests. Module 5 (`custom_python` + registry) ships the actual `lookback_class_matches_dte_bucket` function. The eventual `grammar.yaml` lists S4 with `type: custom_python` rather than `type: compatibility`. Predicate-type tally for v1 grammar.yaml shifts: `cardinality` (4: S1/S2/S3/C3), `numerical_range` (1: P4), `custom_python` (16: S4/S5/C1/C2/C4/P1/P2/P3/E1/E2/E3/R1/R2/R3/X1/X2), `requires` + `forbids` + `compatibility` (0). Per §12 deliverable "all 6 predicate types implemented" — yes; per D015 + D018 they are exercised via synthetic test rules.
**Surface item for operator at handoff:** the original proposal (pre-code confirmation, this session) had S4 as `compatibility`. This is a deviation made under the resume prompt's "predicate type cannot cleanly express a rule" trigger. Logged here for review at the Phase 1 close.

---

## D019 — 2026-05-13 — `crucible_contracts` v1.4.0 adopted; R2/C1 honest-family resolution

**Spec section:** DESIGN.md §3.5 R2 + §3.5 C1; CLAUDE.md hard rule #2 (contracts gap surfaces upstream); Phase 2 pre-code closure plan (this session, D1)
**Decision:** Bumped `crucible_contracts` to **v1.4.0** (commit `d84240a`) adding `trend_strength` to the canonical indicator-family list. Bumped Forge's `FORGE_EXPECTED_CONTRACT_VERSION` to `"1.4.0"`. Reclassified `adx` and `hurst` in `tests/fixtures/strategy_configs.py` from `volatility` (Phase 1 workaround) to `trend_strength` (honest classification). No grammar rule semantics change; no `grammar_version` bump needed.
**Rationale:** §3.5 R2 names `adx` and `hurst` as the required trend-strength regime gate for trend_continuation hypotheses. §3.5 C1 forbids two same-family indicators in one strategy. With only `trend` in the family vocabulary, every trend_continuation strategy violated C1 the moment it paired a trend-family directional (e.g., `ema_50`) with `adx` or `hurst` as the regime gate. Phase 1 fixtures worked around this by misclassifying adx/hurst as `volatility` (flagged in D018's surface-item / fixture comment). Operator chose the contract-bump path over an in-Forge workaround at Phase 2 closure (this session, D1). The contracts change is additive (12 families instead of 11); no consumer code breaks; Forge gets to keep §3.5 R2 + C1 as written.
**Alternatives considered:**
- (d from the closure plan) Tighten C1 semantics to "no duplicate families *within the same role*" — rejected; it changes a Phase 1 grammar rule's intent under the guise of a bug fix and would have masked the family-vocabulary gap.
- (a) Leave adx/hurst as `volatility` in the production registry — rejected; semantically dishonest and would break any future signal-search that uses `family == "volatility"` to find vol indicators.
- (c) Special-case C1 to permit `trend` + `trend_strength` co-occurrence — rejected; brittle, fans out to every future family-pair exception.
**Action:** Phase 2 enumerator's `search_space` treats `trend_strength` as a normal family. C1 (`no_duplicate_indicator_families`) keeps its current per-strategy semantics — no code change to `custom_predicates.py` required. The Phase 1 invariant `test_no_equity_family_*` family remains the symmetric guard for the forbidden side.

---

## D020 — 2026-05-13 — `crucible_contracts` v1.5.0 adopted; `RegistrySnapshot.data_history_days` lands at the honest layer

**Spec section:** DESIGN.md §5.3.2 (resource feasibility filter); CLAUDE.md hard rule #2 (cross-system surface lives in contracts); Phase 3 closure plan D6 (this session)
**Decision:** Bumped `crucible_contracts` to **v1.5.0** (commit `edbdfcb`) adding `RegistrySnapshot.data_history_days: int = Field(ge=1)`. Bumped Forge's `FORGE_EXPECTED_CONTRACT_VERSION` to `"1.5.0"`. Updated every `RegistrySnapshot(...)` constructor site in Forge (9 sites total: 1 fixture, 1 demo registry, 7 unit/invariant tests) to pass `data_history_days=1008` (≈ 4×252 trading days, matching §5.3.3/4's "4-year backtest" framing). Added a sensitivity test in `test_registry_fingerprint.py` so the new field participates in `registry_hash`.
**Rationale:** Operator chose path (b) "if not too heavy" over (a) "carry it on FeatureCache" at Phase 3 closure (this session). Honest placement: history depth is a property of what the registry has indexed, not of any consumer's derived feature cache. Multiple downstream filters (and any future planning logic) want this number; carrying it inside one consumer's protocol meant every other consumer would re-derive it. The bump is small (one required `int` field with `ge=1`) and additive in the same sense D019 was — no production data yet, so updating all fixtures at once is harmless.
**Alternatives considered:**
- (a) `FeatureCache.data_history_days` only — rejected; the registry knows the depth before any cache is built.
- (c) Hardcode in `config/prefilter.yaml` — rejected; the value should travel with the registry snapshot, not the filter config (changes when the universe widens).
- Make `data_history_days` optional with a default — rejected; an unset value means "the registry didn't tell me," which silently lets resource_feasibility pass everything. Required-with-validation matches the operator's "most honest" preference.
**Action:** Phase 3 module 5 (`resource_feasibility`) reads `ctx.registry.data_history_days` directly. All fixtures use 1008; sparse-registry tests in Phase 2 keep the same value (the field doesn't constrain those tests' behavior).

---

## D021 — 2026-05-13 — Phase 3 pre-code closure plan (D1–D9)

**Spec section:** DESIGN.md §5 (pre-filter battery), §12 Phase 3, CLAUDE.md hard rule #4 (no auto-loosen without approval)
**Decision:** Operator green-lit the following Phase 3 closure plan (this session). Captured here for traceability — each item is the architectural choice made before the first line of Phase 3 code lands.

- **D1** — Crucible's feature cache doesn't exist yet, so Forge defines a **`FeatureCache` Protocol** in `forge.prefilters.feature_cache` plus a `SyntheticFeatureCache` implementation seeded by `forge.core.seed`. Real cache lands in Phase 4/5 by implementing the protocol. Protocol stays internal-to-Forge until Crucible has its own cache to surface.
- **D2** — `PreFilterReport.composite_score` stays `None` in Phase 3. Each `FilterResult` carries `(passed: bool, score: float, details)`; the §6.2 weighted sum belongs to the Phase 4 ranker, not Phase 3.
- **D3** — Phase 3 ships the calibration **mechanism** (load `config/prefilter.yaml` → `Calibration` frozen dataclass + a `propose_adjustment(direction, magnitude)` API). **No auto-fire** — no feedback data exists yet. Tightenings can auto-apply once Phase 5 wires them; loosenings always write to `OPEN_PROPOSALS.md` per CLAUDE.md hard rule #4.
- **D4** — Regime labels live on `FeatureCache.regime_label(date) -> Regime`. Synthetic cache stubs deterministic labels by date hash. Real cache (Phase 4/5) derives from macro indicators.
- **D5** — `Filter` Protocol: `name: str, cost_tier: int, apply(config, ctx) -> FilterResult`. `FilterContext` bundles `registry, feature_cache, prior_configs, calibration, rng_factory`. Battery iterates in `cost_tier` order with short-circuit on first `passed=False` per §5.2.
- **D6** — see D020 (contracts v1.5.0 side-trip).
- **D7** — Permutation test K=100 (confirmed against §5.3.7's stretch K=1000).
- **D8** — Phase 3 returns `PreFilterReport` in-memory only. Phase 4 wires `pre_filter_logs` DB writes when batch IDs exist (chicken-and-egg: no batch ID in Phase 3).
- **D9** — Module breakdown: types → feature_cache → calibration → 7 filters in cost-ascending order → battery orchestrator → CLI → invariants + handoff (13 modules, ~1 commit each).

**Rationale:** Phase 3 is close-review (§12). Locking the architectural decisions before code prevents the same back-and-forth that the Phase 1 Q7 surface check produced. Honest dependencies (D1, D4, D6) get a protocol-with-synthetic-impl pattern matching D004's playbook; mechanism-without-trigger (D3) preserves hard rule #4 by structurally separating "propose" from "apply." Phase 4 wiring is out of scope (D8).
**Alternatives considered:** Listed inline in the closure plan; rejected per the operator answers `1.a, 2.a, 3.a, 4.a, 5.ok, 6.b, 7.confirm 100, 8.a, 9.ok`.
**Action:** Phase 3 build proceeds in the D9 module order under tasks #29–#41. D020 (the contracts side-trip) already landed; D021 covers the in-Forge scope.

---

## D022 — 2026-05-13 — `crucible_contracts` v1.6.0 adopted; `RegistrySnapshot.data_start_date` lands at the registry layer

**Spec section:** DESIGN.md §5.3.7 (permutation test); CLAUDE.md hard rule #2 (cross-system surface lives in contracts); Phase 4 closure plan D5 (this session)
**Decision:** Bumped `crucible_contracts` to **v1.6.0** (commit `073ad61`) adding `RegistrySnapshot.data_start_date: date` (required, no default). Bumped Forge's `FORGE_EXPECTED_CONTRACT_VERSION` to `"1.6.0"`. Updated all 9 `RegistrySnapshot(...)` constructor sites in Forge to pass `data_start_date=date(2022, 1, 1)` (matching the `SyntheticFeatureCache` default anchor). Refactored `forge.prefilters.permutation_test` to read `ctx.registry.data_start_date` instead of the hardcoded `date(2022, 1, 1)` from Phase 3 (open-question item 2 from `PHASE_3_HANDOFF.md`). Added a sensitivity row in `test_registry_fingerprint.py` so the new field participates in `registry_hash`.
**Rationale:** Operator chose path (b) "bump contracts now for cleanliness" at Phase 4 closure (this session). Phase 3 surfaced the hardcoded anchor as a known shortcut; with Phase 4 about to compose ranker + submitter, removing the shortcut now is cheaper than carrying it into Phase 5 wiring. Honest placement: the calendar anchor is a property of what the registry indexes, same as `data_history_days`. Both fields travel together inside `RegistrySnapshot`. Same additive playbook as D008 (v1.2.0), D016 (v1.3.0), D019 (v1.4.0), D020 (v1.5.0).
**Alternatives considered:**
- (a) Defer to Phase 5 alongside the Crucible-backed FeatureCache work — rejected; cleaner to land the field now, and Phase 5 only adds the cache implementation against the same `RegistrySnapshot` shape.
- Carry `data_start_date` on `FeatureCache` Protocol only — rejected; the calendar anchor is a registry property, not a cache property. Filters that read `ctx.registry` shouldn't have to also fetch the cache to learn the same fact.
**Action:** Phase 4 work proceeds with the registry as the single source of truth for the permutation-test calendar axis. Synthetic feature cache stays as-is (its default `start_date=date(2022, 1, 1)` matches the threaded registry value). No production data exists yet, so updating all fixtures at once remains harmless.

---

## D023 — 2026-05-13 — Phase 4 pre-code closure plan (D1–D8)

**Spec section:** DESIGN.md §6 (ranker), §7 (submitter), §12 Phase 4
**Decision:** Operator green-lit the following Phase 4 closure plan (this session). Captured here for traceability — each item is the architectural choice made before the first line of Phase 4 code lands.

- **D1** — `prior_promotion_proximity_score` (§6.2, 10% weight): ship the real implementation in Phase 4. Pure function `compute_prior_promotion_proximity(config, promoted_configs) -> float = max Jaccard overlap of signal IDs vs each promoted config's signal IDs`. Empty list → 0.0. Week-1 batches naturally use only the other 90% of weights (which sum to 0.90 by design), no special-casing required.
- **D2** — `Ranker` frozen dataclass that loads §6.2 weights from `config/ranker.yaml` once and exposes `score(report, prior_promotion_score) -> float`. Same pattern as Phase 3 `Calibration`.
- **D3** — Greedy diversifier per §6.3 pseudocode (§12 + §14 confirm "greedy in v1"). Similarity metric = Jaccard overlap of signal IDs, mirroring the §5.3.5 novelty filter so the metric stays coherent across pipeline.
- **D4** — Batch size from `config/forge.yaml` `forge.submission.batch_size` (default 200, §6.4 / §10.1). CLI `--batch-size N` overrides.
- **D5** — see D022 (contracts v1.6.0 side-trip).
- **D6** — `forge run [--batch-size N] [--seed S] [--dry-run]` is single-batch: checks rate-limiter against the latest batch; if blocked, exits with "waiting for prev batch" message; if clear, runs end-to-end (enumerate → pre-filter → rank → submit) once. The 10-min poll daemon (§7.3) is Phase 5/6 work.
- **D7** — Submitter wraps `crucible_contracts.submit_candidate` per §13.4 / hard rule #9: (1) insert `submissions` row status=`pending` (DB unique-index rejects duplicate `config_hash`), (2) on insert success → contracts write, (3) on contracts success → row update with receipt info, (4) on contracts failure → status=`submission_failed`, surface error. Duplicate-hash at step 1 is logged-warning, not fatal (idempotent re-run is a no-op).
- **D8** — Module breakdown: ranking/{types, config, prior_promotion, scorer, diversifier, queue} → submission/{batch, rate_limiter, pre_filter_logger, submitter} → CLI `forge run` → invariants + handoff (12 modules + 1 prep + 1 invariants).

**Rationale:** Phase 4 is light-review (§12 — phases 0/2/4/6). Locking decisions before code keeps the build linear; mirrors Phase 2/3 closure-plan discipline.
**Alternatives considered:** Listed inline in the closure plan; rejected per the operator answers `1.a, 2.a, 3.a, 4.a, 5.b, 6.a, 7.ok, 8.ok`.
**Action:** Phase 4 build proceeds in the D8 module order under tasks #44–#55. D022 (the contracts side-trip + adoption) is task #42–#43; D023 covers the in-Forge scope.

---

## D024 — 2026-05-13 — Phase 5 pre-code closure plan (D1–D11)

**Spec section:** DESIGN.md §5.5 (calibration auto-tune), §7.3 (rate-limiting / daemon loop), §8 (feedback consumer + analyzer + proposer), §10.1 (config/forge.yaml), §12 Phase 5
**Decision:** Operator green-lit the following Phase 5 closure plan (this session). Captured for traceability — each item is the architectural choice made before the first line of Phase 5 code lands. Phase 5 is **close-review** (§12, phases 1/3/5).

- **D1** — `consume_batch_results(forge_db, crucible_db, *, since=None, batch_id=None) -> BatchFeedback`. Joins `crucible_contracts.get_recent_gated_runs(since=)` to Forge's `submissions.config_hash`. Updates `submissions.status` `pending` → `gated` + sets `crucible_run_id`. Updates `batch_summaries.completed_at` / `promotion_rate` / `common_failures`. Returns in-memory aggregate. Idempotent (re-consume = no-op).
- **D2** — `analyze_batch(feedback) -> AnalysisReport`. Pure function: promotion rate, gate-failure breakdown, metric-per-hypothesis distributions, promoted-pattern candidates (§8.3). DB writes to `promoted_patterns` are a side effect via the separate `feedback.promoted_patterns` writer.
- **D3** — Proposer ships all three §8.4 trigger types: (a) 95%+ rejected by gate X → propose pre-filter tighten; (b) 100% promoted in family Y → propose ranker re-weight / grammar tighten; (c) 0 promotions in 200+ above param threshold T → propose grammar param-range tighten.
- **D4** — Calibration adjustments write back to `config/prefilter.yaml` with a `cumulative_adjustment_pct` header per filter. Cap at 30% per direction structurally enforced (§5.5). Each auto-tune event writes a row to `grammar_versions` with `change_type='auto_tighten_calibration'`.
- **D5** — `OPEN_PROPOSALS.md` format: extend the `---`-delimited markdown blocks the existing `write_loosening_proposal` writes. Each block carries `proposal_id`, `direction`, `evidence_json` reference, and a `grammar_proposals` table row insertion.
- **D6** — `forge run [--consume-feedback]` flag wires the consumer→analyzer→proposer chain into per-batch operation order step 9 (§2.1). Standalone subcommand `forge feedback [--since T | --batch-id ID]` for manual invocation.
- **D7** — `forge run --loop` ships in Phase 5: single Python process, sleeps `poll_interval_seconds` between iterations, exits cleanly on SIGINT. Minimal incremental work on top of D6; closes §7.3.
- **D8** — Full `config/forge.yaml` loader (`forge.config.forge_config.load_forge_config()`) covering all DESIGN.md §10.1 keys (`forge.{data_root, db_path, log_root, crucible.*, enumeration.*, submission.*, feedback.*}`). CLI flags become overrides on top of yaml. Default `--forge-db` derives from yaml (closes Phase 4 OQ-3, OQ-5).
- **D9** — Real Crucible-backed FeatureCache: **deferred**. `SyntheticFeatureCache` stays through Phase 5; PHASE_5_HANDOFF.md flags it as Phase 6+ work. Honest "still synthetic" beats fake "looks real."
- **D10** — `signal.id` similarity key → content-hash key (Phase 3 OQ-4 closed): `forge.ranking.signal_key.content_key(signal) -> str` hashed from `(type, role, sorted(indicators), canonical(params))`. Threaded through `jaccard_signal_ids` + `compute_prior_promotion_proximity`.
- **D11** — Module breakdown: feedback/{types, consumer, analyzer, promoted_patterns, proposer, proposal_writer, auto_tune} → ranking/signal_key → config/forge_config → cli/{feedback, main wiring, grammar} → invariants + handoff (12 modules + 1 invariants + 1 handoff).

**Contracts version:** No gap. Phase 5 stays pinned to `crucible_contracts == 1.6.0`. (§8.2 pseudo-code `get_gated_runs(filter=batch_id)` is illustrative — Crucible has no `forge_batch_id` column; batch-filtering is correctly Forge-side.)
**Rationale:** Phase 5 is close-review (§12). Locking decisions before code mirrors Phase 1/3 closure-plan discipline. Recommended option chosen for every D-item; no genuine forks remained after the closure plan.
**Alternatives considered:** Listed inline in the closure plan; rejected per operator answer "All recommended options are fine."
**Action:** Phase 5 build proceeds in the D11 module order under tasks #57–#70. D024 covers the in-Forge scope; no contracts side-trip needed this phase.

---

## D025 — 2026-05-13 — Phase 6 pre-code closure plan (D1–D10)

**Spec section:** DESIGN.md §12 Phase 6 (5 deliverables: property-based invariant tests, reproducibility tests, resilience tests, CLI completion + help text, operational runbook); §13 production-quality requirements; CLAUDE.md phase discipline (phases 0/2/4/6 are light review).
**Decision:** Operator green-lit the following Phase 6 closure plan ("all recommended"). Phase 6 is **polish + operational discipline**; no new feature modules. Recommendations selected for every D-item.

- **D1** — Add Hypothesis-driven property tests in `tests/invariants/test_phase6_properties.py` for three surfaces not yet covered by property generators: (i) submission idempotency (random configs + repeat-submit ⇒ unique-constraint enforcement), (ii) ranker score ∈ [0,1] (random valid configs ⇒ composite score range), (iii) diversifier returns-exactly-N (random batches ⇒ output cardinality holds). Existing Phase 1 grammar property suite stays unchanged.
- **D2** — Full-pipeline byte-determinism integration test in `tests/integration/test_batch_reproducibility.py`: same `(grammar_version, registry_version, seed)` ⇒ identical `submissions.config_hash` sequence, identical `pre_filter_logs` rows, identical ranked-batch order across enumerator → prefilters → ranker → submitter.
- **D3** — Three resilience scenarios as integration tests: (i) Crucible offline = `crucible_db` path missing during `forge feedback` ⇒ clean exit with surfaced error + no partial DB writes; (ii) corrupt feedback = a `gated_runs` row missing expected fields ⇒ skip-with-warning + others process; (iii) partial batch = rate-limiter < 80% gated ⇒ next iteration retries cleanly. Pure-test scope; no new production resilience code unless a test surfaces a real gap.
- **D4** — Help-text audit test in `tests/integration/test_cli_help.py`: every registered Typer subcommand returns `--help` with non-empty docstring + every option's `help=` is non-empty; README "Commands" section references each command (sync check). One mechanical test.
- **D5** — `## Operations` section added to `README.md`: normal-operation commands (`forge run` / `forge feedback` / `forge grammar`), monitoring queries (read-only DuckDB samples), recovery procedures (Crucible offline; gated_runs lagging; grammar.yaml manual-merge), config files inventory, "incident bookmarks" mapping §13 invariants to test files. Single README, not a separate RUNBOOK.
- **D6** — Thread `load_forge_config()` through `forge run` and `forge feedback`: yaml provides defaults; CLI flags override via `with_overrides()`. Add `--config PATH` (default `config/forge.yaml`) + `--no-config` escape hatch. Closes Phase 4 OQ-3, OQ-5 + Phase 5 OQ-5.
- **D7** — Doc rename: §6.2 ranker-weight key "regime_diversity" → "regime_exposure_weight" so it matches the §5.3.6 filter name. Doc-only; no code surface affected.
- **D8** — §8.4 trigger (c) cross-batch param-no-promotion: **deferred** to a future operational-discipline phase (Phase 7+). Current-batch-only Phase 5 implementation stays; the multi-batch rolling window needs a `submissions × gated_runs` history query that is non-trivial and outside Phase 6's polish charter. Logged to `OPEN_QUESTIONS.md`.
- **D9** — Crucible-backed FeatureCache: **deferred** further. Crucible still hasn't shipped a feature-cache surface in contracts. `SyntheticFeatureCache` stays. Re-confirmed deferral logged to `OPEN_QUESTIONS.md` with a "contracts dependency" tag.
- **D10** — Two micro-polish: (i) prune the unused `networkx` section from `pyproject.toml` mypy overrides (carried since Phase 3); (ii) **decline** `--apply` convenience for `forge grammar approve-proposal` (Phase 5 OQ-4 confirmed the manual yaml-edit step as the intentional §13.2 human-in-loop boundary). Add a clarifying note to the command docstring instead.

**Contracts version:** No gap. Phase 6 stays pinned to `crucible_contracts == 1.6.0`.
**Rationale:** Phase 6 is light-review (§12, phases 0/2/4/6). Locking decisions before code mirrors Phase 2/3/4/5 closure-plan discipline. Each D-item is either an in-scope §12 deliverable, a Phase 4/5 carry-forward polish, or an explicit deferral. No new feature modules — Phase 6 is the hardening + operational pass before Forge runs autonomously.
**Alternatives considered:** Listed inline in the closure plan; rejected per operator answer "all recommended."
**Action:** Phase 6 build proceeds in module order #1–#12 (per closure plan table). D025 covers the in-Forge scope; no contracts side-trip needed this phase. D8 and D9 deferrals get OPEN_QUESTIONS.md rows for traceability.

---

## D026 — 2026-05-13 — Inbox flat-layout fix (post-Phase-6 go-live hotfix)

**Spec section:** `crucible_contracts.INBOX_LAYOUT` (formats.py); `crucible_contracts.submit_candidate` (queries.py); CLAUDE.md hard rule #2 (contracts is the integration boundary); DESIGN.md §7.2 (inbox layout — "spirit" only; INBOX_LAYOUT is the authoritative shape).
**Decision:** `forge.submission.submitter.submit_batch` writes each config to `{inbox_root}/{config_hash}.json` directly (flat), matching `INBOX_LAYOUT.files = ("*.json", "*.yaml", "processed/", "errors/")`. The earlier per-batch-subdirectory layout (`{inbox_root}/{batch_id}/{config_hash}.json`) was Forge-side divergence from the contract; Crucible's contract-compliant `_iter_inbox_files` intentionally skips subdirectories, so every prior Forge submission silently failed to land in Crucible's queue. Per-batch grouping continues to live in `submissions.forge_batch_id` (Forge's own DB), not on the filesystem.
**Rationale:** Surfaced during v1 go-live (this session). Two Forge submissions from a prior test run had been sitting in `~/optbt_data/inbox/716677d6-.../` for ~50 minutes while Crucible's inbox-watcher polled the top level once per minute and saw nothing. Confirmed by reading Crucible's `src/optbt/data/inbox.py::_iter_inbox_files` (line 65: `if not path.is_file(): continue`). Forge's `submitter.py:141` built `batch_inbox = inbox_root / str(batch.batch_id)` and passed that to `submit_candidate`. The contracts package writes to whatever path it's handed — `submit_candidate` is correct; Forge was passing the wrong root. Crucible follows the contract; Forge had drifted from it. Hard rule #2 says the contract wins.
**Alternatives considered:**
- Change Crucible's `_iter_inbox_files` to recurse into subdirectories — rejected. Cross-system change: requires `INBOX_LAYOUT` to declare a per-batch subdir glob (contracts minor bump), Crucible code change, Forge tests update, with no benefit Forge can't get from its own `submissions.forge_batch_id` column.
- Add a `INBOX_LAYOUT.per_batch_subdir` field to the contract and bump contracts to v1.7.0 — rejected. The contract was already correct; Forge was the diverging side.
**Action:** (1) `src/forge/submission/submitter.py:141` — `batch_inbox = inbox_root / str(batch.batch_id)` → `inbox_root` directly. (2) Updated docstring at line 185 to reflect flat layout + cite this D-entry. (3) `tests/unit/test_submission/test_submitter.py` — 2 sites updated (the per-batch-subdir layout test renamed + rewritten to assert flat layout). (4) `tests/unit/test_submission/test_cli_run.py` — line 103-106 updated. (5) New `tests/invariants/test_inbox_layout_contract.py` (3 tests) asserts flat layout against `INBOX_LAYOUT` directly so a future regression fails loudly. (6) Stranded files moved from `inbox/716677d6-.../` to flat layout; Crucible's watcher picked them up within 30s (run_ids `682a54b6...` and `6195bb6b...`). (7) `forge.service` restarted to load the fix. Full test suite: 926/926 passing (was 923; +3 new invariants). Ruff + format + mypy --strict clean on changed scope.
**Phase 6 gap note:** Phase 6 (D025/D4 — CLI help-text audit; D025/D3 — resilience tests) did not add an `INBOX_LAYOUT` invariant. The new `test_inbox_layout_contract.py` closes that gap. Worth flagging at Phase 7 close-review: a "test that the contract-blessed APIs are used as the contract intends" theme may surface more such gaps.

---

## D027 — 2026-05-13 — v1 go-live attempt paused; Crucible Phase 9 v2 is the real prerequisite

**Spec section:** CLAUDE.md "When to stop and ask"; OPEN_QUESTIONS.md Q11 (full discovery trail); CRUCIBLE_CHANGES.md §3.1, §10.1; `crucible_contracts.KNOWN_EXIT_IDS` (D011).
**Decision:** Stop `forge.service` (left enabled for future restart). Acknowledge that Forge's v1 go-live cannot achieve closed-loop operation until Crucible Phase 9 v2 ships three things: (a) exit-vocabulary parity with `crucible_contracts.KNOWN_EXIT_IDS`, (b) a from-config dispatcher so source='forge' runs backtest Forge's actual signal config (not a template placeholder), (c) a forge-source gate evaluator that writes `promotion_decisions` rows so `_GATED_QUERY_BASE` can find them. Forge stays as-is; Phase 7 (minimal + Q9) work also pauses pending real promotion data.
**Rationale:** First-attempt v1 go-live (this session) surfaced gaps that aren't on Forge's side to fix. The inbox-layout (D026) and name-routing (Crucible commit `98f1eeb`) fixes brought one Forge config through to `completed`, but with `n_trades=0` (template ran, not the Forge config) and no `promotion_decisions` row (gate evaluator unwired). The remaining gaps are structurally Crucible's. Forge has structurally everything it needs (923→926 tests, 13 invariants files, all gates clean, autonomous service installed); what's missing is downstream parity.
**Alternatives considered:**
- Stub the forge-source gate evaluator in Crucible (write 'reject' decisions so the rate limiter unblocks) — rejected; lets the loop spin without honest evaluation, and the deeper from-config gap stays masked.
- Tighten Forge's grammar to only emit Crucible-implemented exits — rejected; Forge's grammar correctly serves the spec, and `regime_flip_exit` / `event_passed_exit` / `roll_on_schedule_exit` are the hypothesis-required exits per §3.5 S5. Trimming them would amputate 4 of 6 hypotheses' grammar coverage.
- Investigate further before deciding — rejected; the three Crucible-side gaps are direct observations from this session's run, not speculative.
**Action:**
1. `systemctl --user stop forge.service` — service remains `enabled` for autostart once Crucible v2 lands.
2. OPEN_QUESTIONS.md Q11 captures the full discovery trail + the 4-item action list for the Crucible Phase 9 v2 scoping session.
3. STATUS.md flips to "v1 go-live PAUSED awaiting Crucible Phase 9 v2."
4. This session's productive shipped: D026 (Forge inbox flat-layout fix, commit `c299f39`) + Crucible routing fix (Crucible commit `98f1eeb`) + ops/systemd plumbing (Forge commit `61f4319`).
5. Phase 7 closure-plan drafting paused. Reassess scope after Crucible v2 ships at least one real `gated` forge-source run.

---

## D028 — 2026-05-13 — Path A — Crucible v3 indicator parity + EXPORT_LAYOUT publication

**Spec section:** OPEN_QUESTIONS.md Q12 (indicator-vocabulary gap discovery); CLAUDE.md hard rule #1 (21 v1 grammar rules are operator-owned); `crucible_contracts.EXPORT_LAYOUT` (formats.py); `crucible_contracts.RegistrySnapshot` (models.py).
**Decision:** Operator chose **Path A** over Path B (shrink Forge grammar) and Path C (implement only load-bearing indicators). Crucible implements all 10 indicators Forge's demo registry advertises that Crucible's runtime doesn't yet expose (`iv_rank`, `expected_value_estimator`, `days_to_earnings`, `days_to_fomc`, `pairs_zscore`, `put_call_flow`, `vix_level`, plus aliases `momentum_252`, `rsi_14`, `ema_50`), then publishes a real `RegistrySnapshot` to `~/optbt_data/exports/registry_snapshot_<timestamp>.json` per `EXPORT_LAYOUT`. Forge consumes the snapshot via the new `forge.persistence.registry_loader` module (shipped this session, with graceful demo-registry fallback until Crucible v3 lands).
**Rationale:** First v1 go-live attempt surfaced a deeper coordination gap than Q11 — Crucible never wired the registry export, so Forge has been enumerating against a fictional registry since Phase 2 (D6 noted the deferred wiring; Phase 4 D5 + Phase 5 D9 carried it forward unchanged). Path A preserves CLAUDE.md hard rule #1 (R1 + X2 stay implementable) while removing the structural mismatch that would keep recurring. Path B would amputate §3.5 R1, X2, and several hypothesis families; Path C would leave a partial gap that surfaces the next time go-live is attempted. The operator's strong preference is completeness — implement once, run autonomously thereafter.
**Working model:** Same as past contracts side-trips (D007 v1.2.0, D016 v1.3.0, D019 v1.4.0). Forge agent writes a thorough kickoff prompt (`CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md` at Forge repo root); operator spawns a separate Crucible-side agent with that brief. In parallel: Forge agent pre-stages the consumer side (`registry_loader.py`) and logs the discovery + decision (Q12 + this entry).
**Alternatives considered:**
- **Path B (Forge grammar shrinks).** Drop §3.5 R1, X2, and any other rule referencing missing indicators. Forge could enumerate immediately against Crucible's 23 known indicators. Rejected: violates hard rule #1; loses mean_reversion hypothesis coverage; loses Kelly sizer entirely; significant grammar surgery for what should be a Crucible-side completeness item.
- **Path C (hybrid — Crucible implements load-bearing only).** Implement `iv_rank` + `expected_value_estimator` + 3 aliases; defer the other 5 indicators to v1.1 and drop matching grammar rules. Rejected: deferred indicators include `vix_level` (fundamental for volatility regime) and `pairs_zscore` (load-bearing for relative_value hypothesis). Operator preferred completeness in one pass.
- **Path D (Forge ships its own registry adapter that maps Forge indicators → Crucible equivalents).** Rejected as architecturally dishonest — `iv_rank ≈ realized_vol` is not a true equivalence; the backtest semantics differ.
**Action:**
1. **Forge side (this session, this commit):**
   - `src/forge/persistence/registry_loader.py` — `find_latest_snapshot` + `load_registry(allow_demo_fallback=True)` reading `EXPORT_LAYOUT`-compliant snapshots, falling back to `_demo_registry` with a warning log.
   - 8 unit tests in `tests/unit/test_registry_loader.py` (find-latest dir-missing/dir-empty/non-matching/multi-by-mtime; load with file present, demo fallback, fallback-disabled raise, malformed-JSON raise).
   - 5 CLI sites threaded to use `load_registry()` instead of `demo_registry()` directly (4 in `cli/main.py`, 1 in `cli/feedback_cmd.py`).
   - Test suite: 934/934 (was 926; +8 new). Ruff + format + mypy --strict clean on changed scope.
2. **Crucible side (separate agent, separate session):** `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md` at Forge repo root contains the full brief — 10 indicators (with code pointers to existing math + scaffolding), EXPORT_LAYOUT wiring, acceptance criteria, operator-recommended specs for `expected_value_estimator` math + data-source decisions for calendar/flow/vix.
3. **Contracts side:** Pinned at v1.6.0; no bump expected.
4. **Operator post-Crucible-v3:** Restart `forge.service`. Forge picks up `~/optbt_data/exports/registry_snapshot_*.json` automatically; enumeration shifts to Crucible-honest indicators; pipeline closes end-to-end for the first time.


## D029 — 2026-05-14 — v1 go-live OPERATIONAL — first end-to-end loop closure

**Spec section:** OPEN_QUESTIONS.md Q11 + Q12 (closed); CLAUDE.md "Forge succeeds when, over time, its submissions become more likely to promote" success criterion; DESIGN.md §2.1 per-batch operation order; §7.3 rate limiter; §8 feedback consumer.
**Decision:** v1 go-live is now operational. The Forge → Crucible → Forge loop closes end-to-end without errors. First end-to-end iteration on 2026-05-14 00:23:32 PDT completed in ~52s: enumerate 5K candidates → pre-filter battery → rank → submit (0 survivors) → consume feedback → sleep 10 min. No crash, no manual intervention required.

**What was needed to get here** (this session — 2026-05-13 → 2026-05-14):
1. **D026 inbox flat-layout fix** — Forge submitter wrote `inbox/{batch_id}/*.json` (subdir layout); Crucible's contract-compliant inbox watcher skips subdirectories. Reverted to flat per `INBOX_LAYOUT`.
2. **Crucible 98f1eeb routing fix** — `_detect_strategy_name` only handled `genome_<...>` prefix; Forge emits `forge_<...>`. Added the missing prefix arm.
3. **Crucible Phase 9 v2** (separate session): from-config dispatcher (no more template routing), forge-source gate evaluator (writes promotion_decisions), exit-vocabulary parity with 6 stub no-ops for unimplemented exits.
4. **Crucible Phase 9 v3** (separate session + this one): 10 new indicators registered (`iv_rank`, `expected_value_estimator`, calendar/flow/vix/aliases) + `EXPORT_LAYOUT.registry_snapshot_*.json` publishing.
5. **D028 Path A** — operator chose "Crucible implements everything missing + publishes RegistrySnapshot" over the cheaper grammar-shrink alternatives. Preserved CLAUDE.md hard rule #1 (21 grammar rules operator-owned).
6. **`crucible_contracts` v1.7.0** — `RegistrySnapshot.schema_version` + `exported_at` envelope metadata fields. Crucible's v3 publisher added them per §13.17; the v1.6.0 contract rejected the extras.
7. **`crucible_contracts` v1.8.0** — `EXPORT_LAYOUT.files` += `("gated_runs_*.json",)` + new `load_recent_gated_runs_from_export()` helper. DuckDB's writer process holds an exclusive file lock; `get_recent_gated_runs(read_only=True)` fails. File-based path side-steps the lock.
8. **`crucible-gated-runs-publisher.service`** (Crucible) — Type=simple daemon polling 60s, writes `gated_runs_*.json` snapshots via DBProxy (the writer's socket-mediated read API).
9. **Forge `registry_loader.py`** — reads newest `registry_snapshot_*.json`, graceful demo-registry fallback. Threaded through 5 CLI call sites. Replaces the Phase 2 `_demo_registry` stopgap.
10. **Forge rate_limiter export-path** — prefers `load_recent_gated_runs_from_export(exports_dir)` with fallback to direct DuckDB for test fixtures. Closes the lock-conflict failure where the rate limiter saw 0 gated despite real gated runs in Crucible.
11. **Forge consumer.py export-path** — same pattern; the feedback consumer had been the second silent caller of the direct-DB path. Refactored into `_fetch_crucible_runs` helper. Raises QueryError only when BOTH export AND direct-DB fail (preserves Phase 6 D025/D3.i "Crucible offline → clean exit" behavior).
12. **`tests/conftest.py` autouse `_isolated_home`** — monkeypatches `Path.home()` per-test so the new default exports_dir lookup doesn't see the operator's real `~/optbt_data/exports/`. 25 test sites in `test_rate_limiter.py` + `test_consumer.py` pass `exports_dir=tmp_path/"noexports"` explicitly for direct-DB-path assertions.
13. **config/forge.yaml tuning** — `max_candidates_per_batch: 100000 → 5000`. The 100K default OOM-risked the first iteration; 5K lets the loop close fast enough to observe behavior without blowing memory. Ramp later once survival rate is healthy.

**Tests:** 934/934 passing; ruff + format + mypy --strict clean across all changed scope. Contracts: 159/159 + 100% coverage. Crucible: 1651/1651.

**State on 2026-05-14:**
- `forge.service` active, looping every 10 min, no errors
- `crucible-{db-writer, inbox-watcher, runner, refit-watcher, registry-publisher, gated-runs-publisher}` all active
- `~/optbt_data/exports/` has both registry + gated_runs snapshots refreshing
- Loop is structurally correct; 0-survivor rate per batch is a calibration concern (Q13) handled by §5.5 auto-tune over time

**Open follow-ups (none blocking go-live):**
- Q13 — 100% permutation_test rejection under real registry; auto-tune will propose loosening as evidence accumulates
- Q10 — Real Crucible-backed FeatureCache still deferred; `SyntheticFeatureCache` stays until contracts adds the surface
- Q9 — Cross-batch param-no-promotion trigger (§8.4 trigger c) still deferred
- Phase 7 closure-plan drafting resumes once auto-tune has produced a few proposals to reason about


## D030 — 2026-05-14 — Indicator-aware threshold sampling + grammar P1 whitelist

**Spec section:** OPEN_QUESTIONS.md Q14 (threshold semantics + stub indicators); CLAUDE.md hard rule #4 (auto-loosen needs operator approval — proposal 646a865f-1379-4535-b470-e1df4b91d0f2 approved 2026-05-14 by aj); §3.5 R1 / X2 (iv_rank + expected_value_estimator).
**Decision:**
1. Forge enumerator emits explicit `params={"threshold": <value>, "op": <"<"|">">}` for every threshold-style SignalSpec, sourced from `forge.enumeration.indicator_thresholds._INDICATOR_THRESHOLD_TABLE`. The table encodes audited per-indicator threshold ranges from a real SPY 2020-2025 distribution audit (see `docs/INDICATOR_THRESHOLDS.md`).
2. Grammar P1 (`_p1_indicator_params_within_registry_ranges`) extended to whitelist signal-type-specific predicate params: `{threshold, op}` for `threshold` signals. These are signal-evaluator params, not indicator params, and were incorrectly flagged before.
3. Price-scale indicators (`ema`, `ema_50`, `sma`) flagged `is_skip=True` in the threshold table and filtered from `_pick_directional_regime_pair` + `_viable_buckets` via the new `is_threshold_skippable()` helper. They remain valid for `passthrough` confluence signals where the predicate is `value != 0`, not a threshold compare.
4. Stub indicators (`iv_rank`, `expected_value_estimator`, `pairs_zscore`, `put_call_flow`, `vix_level`) included with educated default ranges. iv_rank's range honors §3.5 R1's `threshold <= 50` constraint; expected_value_estimator uses `op=">"` (fire when EV exceeds threshold). Stubs fire 0 times under current Crucible until `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md` work ships.
5. `CrucibleFeatureCache.prefetch_for_config` restructured: fetches activation_dates first, then returns + regime_label for the *actual* activation dates (not a fixed calendar window). Resolves window-mismatch errors (`KeyError: date=2022-01-01 not prefetched`) caused by `data_history_days` being measured in trading days while my window was calendar days.
6. `returns()` and `regime_label()` Protocol methods now graceful — `returns()` silently drops dates not in cache; `regime_label()` defaults to `"low_vol"` for missing dates. Callers (`permutation_test` passes the full window; `regime_exposure` passes activation dates) tolerate shorter result maps without crashes.
7. `prefilter.yaml` `permutation_test.p_value_threshold` reverted from 0.50 (approved-proposal experimental loosen for synthetic cache) back to 0.10 — original threshold is honest under real Crucible cache + indicator-aware thresholds. The audit row in `grammar_proposals` remains.
**Rationale:** Real Crucible cache (commit `b447597`) shipping revealed that Forge had been emitting threshold-style signals with no threshold params at all. Crucible's compute correctly returned 0 activations. The fix surfaces honest per-indicator threshold ranges from a real audit; P1 grammar update permits the signal-type-aware params; price-scale indicators are excluded from threshold-style enumeration where they have no meaningful threshold.
**Alternatives considered:**
- Universal `threshold=30` default: rejected — meaningful only for ~25% of indicators.
- Skip stubs from enumeration: rejected by operator — long-term plan is to implement stubs properly (see `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md`).
- Fix only signal_density / let other filters fail: rejected — incomplete; the synthetic-vs-real gap shows up at multiple filters.
**Action:**
- `src/forge/enumeration/indicator_thresholds.py` — new module with the 33-indicator threshold table.
- `src/forge/enumeration/sampler.py` — `_directional_signal_params` + updated `_regime_signal_params` use `sample_threshold_params`. Skippable filter applied to directional/regime pools.
- `src/forge/grammar/custom_predicates.py` — P1 whitelists threshold-type signal params.
- `src/forge/prefilters/crucible_feature_cache.py` — restructured prefetch (activations → returns/regime via actual dates) + graceful returns/regime_label.
- `tests/unit/test_prefilters/test_crucible_feature_cache.py` — 7 tests covering new prefetch order + graceful date handling.
- `docs/INDICATOR_THRESHOLDS.md` — audit report.
- `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md` — kickoff brief for Crucible-side follow-up.
- `OPEN_QUESTIONS.md` Q14 — discovery + resolution notes.

941/941 Forge tests pass; ruff + format + mypy --strict clean on changed scope.

---

## D031 — 2026-05-15 — Reframe "stubs" + recalibrate three low-fire indicator ranges

**Spec section:** Follows D030. Triggered by 27-batch zero-promotion streak with all 1000 sampled gated_runs showing trade_count=0.
**Discovery:** Parallel audit (Forge + Crucible) revealed the "5 stub indicators" framing is wrong. All five (`iv_rank`, `vix_level`, `pairs_zscore`, `put_call_flow`, `expected_value_estimator`) have shipped real `version=2` implementations in Crucible. Direct compute on the SPY OOS window (2025-06-02 → 2025-09-05) confirms real values:
  - `vix_level`: 67 rows / 0 NaN / range 14.22 → 21.60 / mean 16.69
  - `iv_rank`: 67 rows / 1 NaN / range 0 → 100 / mean 27.43
  - `put_call_flow`: 67 rows / 0 NaN / range -0.50 → 0.02
  Data sources (VIX bars, SPY chain_snapshots 2024-01 → 2025-12, XOM/CVX bars, runs.duckdb) are backfilled.

**Root cause of 0-trade cascade** (now diagnosed correctly):
1. Crucible's registry publisher last ran 2026-05-14 08:03 — Forge enumerated against `version=1` metadata for 24+ hours after Crucible bumped to v2. Cosmetic only (Crucible's runner uses code directly), but a confusing trap.
2. Threshold ranges in `indicator_thresholds.py` were audited against *generic* historical distributions, not actual SPY OOS firing rates. Three indicators sample thresholds that fire <20% of the time, which combined with the §3.5 grammar mapping (e.g. `tail_hedge` directional = `vix_level` only) drives effective trade counts to ~0 on a 60-day OOS window.
3. Orthogonal Crucible-side question: `min_oos_trade_count=30` may be structurally incompatible with `swing_short` (14-21 DTE) on a single ~60-day OOS window — even continuous firing of a non-overlapping swing strategy caps at ~4 trades per window. Filed as `CRUCIBLE_TRADE_COUNT_GATE_AGENT_PROMPT.md`.

**Decision:**
1. Trigger `crucible-registry-publisher.service` to refresh snapshot to v2 (done 2026-05-15 20:55 UTC; new file `registry_snapshot_2026-05-16T035511Z.json`). Forge `load_registry()` picks latest by mtime so next loop iteration runs against v2 metadata automatically.
2. Widen directional ranges for three low-fire indicators in `_INDICATOR_THRESHOLD_TABLE`:

   | Indicator | Before | After | Reason |
   |---|---|---|---|
   | `vix_level` directional | (15.0, 22.0) | (18.0, 25.0) | Real SPY VIX mean 16.69; old range often sampled below median → <20% fire |
   | `pairs_zscore` directional | (-2.0, -1.0) | (-1.5, -0.5) | `relative_value` has pairs_zscore as ONLY directional; dominant fire-rate driver |
   | `zscore_returns` directional | (-2.0, -1.0) | (-1.5, -0.5) | Same logic; -2 was overly extreme on actual returns distribution |

   Regime ranges unchanged (already permissive).
3. Out of scope: structural `min_oos_trade_count` vs swing-DTE mismatch — see Crucible agent prompt.

**Hard rules check:**
- Not a `grammar.yaml` change → no archive / version bump required (hard rule #10).
- Not a loosening of Crucible's gate → does not violate hard rule #3.
- Auto-tightening adjacent: this is auto-widening of *enumeration scope*, mirror operation. Hard rule #4 reserves auto-loosening of `grammar.yaml` for operator approval — this edits a sampler helper, not grammar.

**Rationale:** D030 marked these 5 indicators as "stubs returning NaN" based on Crucible's pre-Phase-9-v2 state. Crucible has since shipped real implementations and the data is loaded; D030's hold-until-stubs-implemented framing is obsolete. The remaining 0-trade pathology is mostly threshold calibration and partly a Crucible-side gate question.

**Alternatives considered:**
- Skip stubs from directional pools (D-NN-as-originally-proposed): rejected once we discovered they're not stubs.
- Lower `min_oos_trade_count`: rejected — Crucible's gate, hard rule #3.
- Touch grammar mapping (`tail_hedge` directional pool of one): deferred — separate decision, broader scope.

**Action:**
- `crucible-registry-publisher.service` restarted (one-shot); new snapshot live.
- `src/forge/enumeration/indicator_thresholds.py` — 3 spec entries updated with inline `D031` annotation.
- `IMPLEMENTATION_DECISIONS.md` D031 (this entry).
- `CRUCIBLE_TRADE_COUNT_GATE_AGENT_PROMPT.md` — kickoff brief for Crucible-side investigation.

Tests pending: existing `test_no_empty_threshold_leak.py` still passes (no structural change); calibration test not added — values are data-derived, regression-guarded by the 27-batch zero-promotion stuck_state alarm if they over-correct.


## D032 — 2026-05-16 — Forge sampler: Tier 1 → Tier 2 (production-default underlyings)

**Context:** After 5 overnight fixes (universe backfill, walk_forward KeyError, cross-ticker / total_return / tail_hedge gate-domain corrections, runner-path port), v1 still produced 0 promotions over batch 550e24a2's 44/125 gated runs. Post-mortem audit shows the binding constraint is `min_oos_trade_count` (most configs produce 0-19 trades vs floor 100 for swing_short) — the v1 grammar's regime∧directional∧confluence triple-AND combined with SPY-only enumeration fires too rarely.

Crucible's `templates.py:80` notes "Phase 3 tier=1 (4 ETFs) is a smoke fixture"; Tier 2 (24 tickers: 4 ETFs + 20 single names) is the production-default and is already wired in `config/universe.yaml` with `use_for: [trend_rider, cross_sectional_rank, regime_mean_revert, pairs_convergence]`.

**Change:** `src/forge/enumeration/sampler.py:207` flipped `tier=1` → `tier=2`.

**Rationale:**
1. Multiplies cross-ticker breadth by ~6×; trade-count cascade may resolve mechanically without grammar change.
2. Indicator distributions on single names (AAPL, NVDA, JPM…) differ from SPY — calibration ranges from D031 may need re-tuning, but the alternative (stay on Tier 1) is structurally trade-starved.
3. Pre-existing Crucible runner machinery supports Tier 2 since at least Phase 3; no Crucible work required.

**Hard rules check:**
- Not a `grammar.yaml` change → no version bump required (hard rule #10).
- Not a loosening of Crucible's gate (hard rule #3).
- `tier` is a `StrategyConfig` field, operator-approved field-value change. Hard rule #1 (21 §3.5 rules) untouched.

**Known follow-ups:**
- D031 threshold ranges were calibrated against SPY OOS distributions; single-name realized_vol / bb_pct / atr_pct can fire at different rates. May need per-ticker or per-tier threshold sweeps. Surface in 2-3 batches of post-D032 data.
- `pairs_zscore` for `relative_value`: pair selection logic in `sampler.py` already iterates pairs (sample_strategy code path); Tier 2 expands the pair universe.
- `vix_level` and other macro indicators are market-wide; behavior unchanged.

**Action:**
- `src/forge/enumeration/sampler.py:207` — inline D032 annotation.
- `IMPLEMENTATION_DECISIONS.md` D032 (this entry).
- Forge service restart required to pick up the change.
- Cross-sectional rank (v2 grammar option B) scoped separately in `OPTION_B_CROSS_SECTIONAL_RANK_SCOPING.md`.

**Tests pending:** Sampler test fixtures may have `tier=1` hardcoded — verify and update if so.


## D033 — 2026-05-16 — Per-config underlying + cache underlying-keying (P1 blocker fix for D032)

**Context:** D032 flipped `tier=1` → `tier=2` in `src/forge/enumeration/sampler.py:207` with the expectation that Forge would start trading the 24-ticker Tier 2 pool. Post-D032 audit (parallel Explore agents 2026-05-16) revealed TWO bugs that made D032 a no-op for single-underlying hypotheses:

1. **Sampler still emitted `config.underlying=None`**. Crucible's `data/inbox.py:_FALLBACK_UNDERLYING = "SPY"` falls back when underlying is None, so every "Tier 2" config actually backtested on SPY.
2. **`CrucibleFeatureCache` was SPY-locked at construction**. Pre-filter battery (signal_density, expected_trades, regime_exposure, permutation_test, novelty) all scored configs against SPY activation history regardless of the config's intended ticker. Even if (1) was fixed, the pre-filter cache would silently miscalibrate.

**Change:**
1. `src/forge/enumeration/sampler.py:90-130` — added `_TIER_1_2_UNDERLYINGS` tuple (24 tickers, mirror of Crucible's `config/universe.yaml::tier_1.tickers + tier_2.tickers`) + `_pick_underlying(rng, hypothesis)` helper. The helper returns `None` for `relative_value` (Crucible's pairs_convergence template selects its own pair) and a uniform pick from the pool otherwise.
2. `src/forge/enumeration/sampler.py:206-212` — `underlying=_pick_underlying(rng, hypothesis)` instead of `underlying=None`. Deterministic via shared rng (hard rule #6 preserved).
3. `src/forge/prefilters/crucible_feature_cache.py` — refactor to per-underlying keying:
   - Activations dict keyed by `(underlying, content_key)` (was `content_key` alone)
   - Returns + regimes dicts keyed by underlying (each is `dict[str, dict[date, T]]`)
   - `prefetch_for_config` resolves `config.underlying or default` and sets `_active_underlying`
   - `prefetch_for_batch` partitions configs by underlying and fetches per partition
   - Protocol methods (`activation_dates`, `returns`, `regime_label`) serve from `_active_underlying`'s slice
4. New invariant tests in `tests/unit/test_prefilters/test_crucible_feature_cache.py`:
   - `test_d033_two_configs_different_underlyings_do_not_collide` — SPY and AAPL configs with the same spec get distinct cache entries, 4 client calls (2 per config), no silent reuse.
   - `test_d033_underlying_none_falls_back_to_default` — `config.underlying=None` resolves to the cache's default (SPY), mirroring Crucible's `_FALLBACK_UNDERLYING`.

**Hard rules check:**
- Not a `grammar.yaml` change (hard rule #10). The grammar's per-config underlying selection isn't governed by §3.5 rules.
- Not a loosening of Crucible's gate (hard rule #3).
- Determinism preserved (hard rule #6) — `_pick_underlying` uses the shared rng.
- No imports from Crucible internals (hard rule #2) — ticker pool is hardcoded mirror of universe.yaml. Drift risk noted; future cleanup is to expose via `crucible_contracts`.

**Verification:**
- 270 unit + invariant tests pass (including 2 new D033 tests).
- 49 integration tests pass.
- Ruff + mypy strict clean on changed scope.
- Pre-existing reproducibility test (`test_phase2_invariants.py::test_enumeration_byte_identical_for_same_triple`) still passes — proves the new rng-based underlying selection didn't break determinism.

**Drift risk:**
- `_TIER_1_2_UNDERLYINGS` is hardcoded in `sampler.py`. If Crucible's `config/universe.yaml` adds/removes tickers, Forge stays stale until manually synced. Future: expose via `crucible_contracts` (e.g., `crucible_contracts.universe.tier_tickers(2)`) — separate contracts version bump.

**Action:**
- `src/forge/enumeration/sampler.py` — D033 inline annotations.
- `src/forge/prefilters/crucible_feature_cache.py` — full refactor with D033 module-docstring history note.
- `tests/unit/test_prefilters/test_crucible_feature_cache.py` — failing assertion updated + 2 new invariant tests.
- `IMPLEMENTATION_DECISIONS.md` D033 (this entry).
- Forge service restart required to pick up the changes.


## D034 — 2026-05-16 — Auto-proposer: intent-based dedup + zero-promotion guard

**Context:** Post-D033 audit identified `OPEN_PROPOSALS.md` as in a feedback-loop loop. The auto-proposer's gate-failure-concentration trigger (`feedback/proposer.py::_proposals_from_gate_failures`) fired every batch where a gate failed ≥95% of rejected candidates. In the 0-promotion regime, EVERY gate failed 100% — so every batch wrote ~9 identical tighten-proposals. `proposal_writer._has_identical_pending_proposal` was supposed to dedup, but the dedup key was `(proposal_type, rationale)` and rationale strings embed mutable count fields ("308 of rejected..."), so the dedup never fired. Result: 19 PENDING entries in `OPEN_PROPOSALS.md` at audit time, mostly duplicates.

**Two-part fix:**

1. **`_proposals_from_gate_failures` gated on `feedback.promoted_count > 0`** (`feedback/proposer.py`). In a 0-promotion regime the gate-failure signal is degenerate (every gate fails 100% of rejects); the proposer correctly suppresses the trigger until something passes. `propose()` updated to pass `feedback` through.

2. **`_has_identical_pending_proposal` dedups by structural intent** (`feedback/proposal_writer.py`). New `_intent_key(evidence)` helper extracts the per-trigger detail field (`target` for gate_failure, `hypothesis` for hypothesis_dominance / param_no_promotion, `family` for family_dominance). Dedup matches on `(proposal_type, status='pending', _intent_key)`. Legacy fallback to `(proposal_type, rationale)` when evidence lacks a trigger key.

**Hard rules check:**
- Not a grammar.yaml change (hard rule #10).
- Hard rule #4 preserved: this changes which proposals get *written*, not whether loosening can auto-apply. Loosenings still wait for operator review.

**Verification:**
- 114 feedback tests pass (3 prior tests updated to reflect new semantics; 2 new D034 invariant tests added: `test_trigger_a_suppressed_when_zero_promotions`, `test_append_same_intent_different_count_fields_deduped`).
- Ruff + mypy strict clean.

**Action:**
- `src/forge/feedback/proposer.py` — gate added with D034 docstring.
- `src/forge/feedback/proposal_writer.py` — `_intent_key` helper + refactored dedup.
- `tests/unit/test_feedback/test_proposer.py` — updated trigger-a test + new suppression test.
- `tests/unit/test_feedback/test_proposal_writer.py` — updated dedup tests + new intent-dedup test.
- `IMPLEMENTATION_DECISIONS.md` D034 (this entry).


## D035 — 2026-05-16 — Stuck-state detector: grammar-change floor

**Context:** Post-D033 audit identified `stuck_state.consecutive_zero_promotion_batches` as blind to structural changes. The 27-batch zero-promotion streak that triggered D031/D032/D033 will keep climbing past 27 even when those fixes resolve the underlying issue — for several batches after each structural fix, the operator can't distinguish "warming up" from "still stuck."

**Change:**
1. `stuck_state.most_recent_grammar_change(db)` — new helper that returns `MAX(grammar_versions.changed_at)`. Returns None when the table is empty.
2. `consecutive_zero_promotion_batches(db, *, since=None)` — added optional `since` floor. Pre-floor batches don't influence the streak.
3. `is_stuck(db, *, threshold, since=None)` — forwards `since` to the counter.
4. `cli/main.py:437` — passes `since=most_recent_grammar_change(conn)` so production calls automatically reset on grammar bumps.

**Calibration-only changes (D031/D032/D033) intentionally don't reset.** Those are tweaks, not structural shifts. To force a reset for a calibration cycle, bump grammar version or insert a row into `grammar_versions` with `change_type='calibration'`. The line between "calibration" and "structural" is operator-owned.

**Hard rules check:**
- Not a grammar.yaml change (hard rule #10).
- Not a gate relaxation (hard rule #3).

**Verification:**
- 12 stuck_state tests pass (9 pre-existing + 3 new D035 invariant tests).
- Full Forge test suite 988 tests pass.
- Ruff + mypy strict clean on changed scope.

**Action:**
- `src/forge/feedback/stuck_state.py` — new helper + `since` parameter on both functions.
- `src/forge/cli/main.py:413, 437-441` — import + pass `since=most_recent_grammar_change(conn)`.
- `tests/unit/test_feedback/test_stuck_state.py` — 3 new D035 invariant tests.
- `IMPLEMENTATION_DECISIONS.md` D035 (this entry).


## D036 — 2026-05-17 — Rate-limiter threshold tactical drop 0.80 → 0.50

**Spec section:** DESIGN.md §7.3 ("Forge waits until >=80% of the previous batch's candidates are gated in Crucible before queuing a new one"); CLAUDE.md "Deviations are proposed as Decision Log entries, not silent edits"; back-filled 2026-05-18 per the 2026-05-17 audit finding that this entry was missing.

**Decision:** `forge.submission.rate_limiter._DEFAULT_THRESHOLD` dropped from `0.80` → `0.50`. Pre-D033 batch `550e24a2` was gating at ~80 min/run (vs the prior 17-27 min/run), so the 0.80 threshold projected first-D033-batch ETA out to Tuesday morning. Dropping to 0.50 unblocked immediately and let D033 (Tier 1 → Tier 2 sampler flip + per-config underlying + cache underlying-keying) actually exercise.

**Rationale:** Tactical, time-bounded. The 0.80 default in §7.3 was sized for v1 / SPY-only behavior where per-run cost was bounded. Tier 2's expanded underlying pool (24 tickers) and the slower per-run cost during the pre-D033 transition made strict 0.80 a structural block on the exact next-batch we needed to observe. The cost of false-clear at 0.50 (~100 ungated candidates outpacing Crucible's queue) is bounded by `max_candidates_per_batch=5000` and Crucible's inbox-watcher cadence; the cost of staying-blocked is the experiment never running.

**Alternatives considered:**
- Wait the 36+ hours at 0.80 — rejected; would have delayed every other in-flight change (D034/D035/D037+) gated on observed Tier 2 behavior.
- Lower further to 0.30 — rejected; nothing in the data justified that deep a cut; 0.50 is the natural "majority gated" midpoint with operator-meaningful semantics.
- Leave at 0.80 + tune Crucible-side concurrency to drain faster — rejected; cross-system change, slower to land, and the throughput improvement is uncertain until Tier 2 ships.

**Hard rules check:**
- Not a `grammar.yaml` change (hard rule #10).
- Not a Crucible gate change (hard rule #3).
- Operational threshold tweak — same class as D031's calibration widenings, D032's tier flip. The spec's 80% is the *default*, not an invariant.

**Verification:**
- `tests/unit/test_submission/test_rate_limiter.py:184` updated to reflect the new default (test was previously asserting 0.80).
- 1006 tests passing post-change (then 1028 after subsequent T2.x ships).
- Ruff + mypy strict clean on changed scope.

**Revert criteria:** Restore to `0.80` once **either**:
- D033 has shipped at least 2 full Tier 2 batches and we have evidence of stable per-run throughput, **or**
- Crucible throughput regresses to v1 / SPY-only levels.

**Sunset:** 2026-06-15. If neither revert criterion has been met by then, surface the threshold question at the next phase-boundary review and propose a permanent §7.3 amendment rather than carrying the tactical drop indefinitely.

**Audit gap acknowledgment:** This entry was originally written only as an inline comment in `src/forge/submission/rate_limiter.py:32` and the matching test update; the IMPLEMENTATION_DECISIONS row was missed. Back-filled 2026-05-18 after the audit caught it. CLAUDE.md "Deviations are proposed as Decision Log entries, not silent edits" applies; this is the proposed decision row.

**Action:**
- `src/forge/submission/rate_limiter.py:32-39` — inline comment + `_DEFAULT_THRESHOLD = 0.50`.
- `tests/unit/test_submission/test_rate_limiter.py:184` — threshold-assert update.
- `IMPLEMENTATION_DECISIONS.md` D036 (this entry, back-filled).


## D037 — 2026-05-17 — Stratified hypothesis sampling floor (Forge sampler bias fix)

**Context:** Forge sampler audit on 2026-05-17 — across 4020 historical submissions, two of six v1 hypotheses had near-zero coverage:

```
tail_hedge          : 1851  (46.0%)
relative_value      : 1154  (28.7%)
regime_arbitrage    :  858  (21.3%)
volatility_event    :  156  ( 3.9%)
mean_reversion      :    1  ( 0.0%)
trend_continuation  :    0  ( 0.0%)
```

`trend_continuation` and `mean_reversion` — both classical retail-feasible hypothesis classes that v1 should test — were essentially untested. Today's D033 batch was 78% `volatility_event` (156/200), the bias having rotated from tail_hedge → vol_event but the under-sampled hypotheses remaining at zero.

**Root cause** (per `OPTION_B_CROSS_SECTIONAL_RANK_SCOPING.md`-adjacent investigation, this session's transcript):
1. **Grammar-structural**: §3.5 R1 (mean_reversion needs `iv_rank` regime — 1 indicator) and R2 (trend_continuation needs `adx`/`hurst` — 2 indicators) give these hypotheses tiny regime pools. CSP dead-ends are common.
2. **Bayesian failure-bias** (`forge/feedback/rejection_weights.py:87-90`): weight = (α+promoted)/(α+β+total). Tail_hedge with 1851 submissions, 0 promotions: weight ≈ 0.00054 (vs. prior_mean 1/11 ≈ 0.091 for never-tried hypotheses). The sampler's `rng.choices(weights=...)` then collapses toward the highest-weight option each batch.
3. **CSP retry amplification**: when the chosen hypothesis dead-ends, the iterator re-picks — biasing toward the easier-to-construct hypotheses (vol_event has the largest regime pool).

The three compound: the failure-bias gives wrong signal-to-noise; CSP retries amplify the bias; trend_continuation and mean_reversion are systematically excluded.

**Conclusion that motivated the fix**: 4020 submissions of "data" we've been treating as evidence that v1 doesn't promote is actually evidence that **4 hypotheses don't promote on biased data, two of which were never tried**. Before declaring v1 dead and committing to Option B (cross-sectional rank, v2 grammar work), we need fair-sample data on trend_continuation and mean_reversion.

**Change:**
1. `src/forge/enumeration/sampler.py:132` — `sample_config` gains a `forced_hypothesis: str | None = None` kwarg. When set, bypasses the weighted/uniform pick. Raises `SamplerError` if the forced hypothesis is not in the samplable pool.
2. `src/forge/enumeration/iterator.py` — `enumerate_candidates` gains a `min_hypothesis_fraction: float = 0.0` kwarg (default 0.0 for backward compat) and a `_compute_stratification_floor` helper. The iterator tracks per-hypothesis yield counts and rotates through under-quota hypotheses (by `attempts % len(under_quota)`) to force-pick each one until its floor is met. A blacklist (`_FORCED_FAILURE_CAP = 20`) drops hypotheses from the rotation if their CSP-failed-when-forced count exceeds threshold — prevents starvation when a hypothesis is structurally hard to construct on the current registry.
3. `src/forge/cli/main.py:380` — production CLI passes `min_hypothesis_fraction=_PRODUCTION_MIN_HYPOTHESIS_FRACTION` (= 0.02). At max_candidates=5000 → 100 forced picks per hypothesis (capped at 50% of budget by `_compute_stratification_floor`), 4400 remaining via weighted sampling.
4. Floor cap: `_compute_stratification_floor` returns `min(ceil(max_candidates * fraction), max_candidates // (2 * n_samplable))`. Guarantees stratification never consumes more than 50% of the candidate budget.

**4 new invariant tests** in `tests/invariants/test_phase2_invariants.py`:
- `test_d037_stratification_floor_guarantees_each_hypothesis`: with fraction=0.05 and max=600, every samplable hypothesis appears ≥ 30 times in the enumerated output.
- `test_d037_stratification_disabled_when_fraction_zero`: fraction=0 preserves legacy behavior.
- `test_d037_floor_caps_at_50pct_of_budget`: tiny `max_candidates` with large `fraction` doesn't starve the weighted-sample path.
- `test_d037_determinism_preserved_with_stratification`: same triple + same fraction → byte-identical sequence (hard rule #6 preserved).

**Hard rules check:**
- Not a `grammar.yaml` change (hard rule #10).
- Not a Crucible gate change (hard rule #3).
- Determinism preserved (hard rule #6) — verified by new invariant test.
- No Crucible internals imported (hard rule #2).

**Verification:**
- 992 tests pass (full Forge suite, including 4 new D037 tests).
- Ruff + mypy strict clean on changed scope (one `# noqa: PLR0912` annotation on `enumerate_candidates` — the stratification branches push it over the 12-branch threshold but a refactor would be net-harm).
- Reproducibility test still passes (sequence under same (grammar, registry, seed, fraction) is byte-identical across runs).

**Expected outcome:**
- Next D033 batch should show `trend_continuation` and `mean_reversion` at ~10% each (200 × 0.02 floor = 4 forced + weighted contributions). Over 5-10 batches we accumulate enough fair-sample data on those hypotheses to either:
  - Confirm v1 grammar can't promote even on the previously-untested classes (justifies Option B / v2 grammar work), OR
  - Surface unexpected promotion patterns (means D031/D032/D033/D034/D035/D036 corrections plus stratification opened a real path).

**Action:**
- `src/forge/enumeration/sampler.py` — `forced_hypothesis` parameter.
- `src/forge/enumeration/iterator.py` — stratification + blacklist + floor cap.
- `src/forge/cli/main.py` — CLI opts in via `_PRODUCTION_MIN_HYPOTHESIS_FRACTION`.
- `tests/invariants/test_phase2_invariants.py` — 4 new D037 invariant tests.
- `IMPLEMENTATION_DECISIONS.md` D037 (this entry).
- Forge service restart required to pick up the iterator + sampler changes.


## D038 — 2026-05-17 — T1.3 predicted_activations pre-filter (Prompt 5 v2 / silent-failure fix)

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T1.3 surfaced a silent-failure mode: configs that pass the existing 7 pre-filters but produce 0 trades during the full Crucible backtest because the directional signal and the regime gate *never co-fire* on the chosen underlying. Concrete instances from the translation corpus:
- `days_to_earnings <= 3` regime gate on SPY (ETF) — `days_to_earnings` returns sentinel value 999 for ETFs → never <=3 → empty intersection
- Continuous-true signals + DTE-bucket constraint
- Misc misaligned regime/directional combos

Each silent-inert config wastes 1-2 hours of Crucible compute and contributes zero learning. With Tier 2 (D033) opening 24 underlyings, the silent-failure surface area expanded; pre-filtering this class of config before submission is high-ROI.

**Change:**
1. New `src/forge/prefilters/predicted_activations.py` — `PredictedActivationsFilter` (cost_tier=5). Intersects directional signal's activation_dates with each regime_filter gate's activation_dates; rejects when `len(intersection) < min_entries`.
2. Calibration knob `predicted_activations.min_entries` (default 10) in `src/forge/prefilters/calibration.py` + `config/prefilter.yaml`. Auto-tightening propagates per the existing pattern.
3. Cost_tier bumps: `NoveltyFilter` 5→6, `RegimeExposureFilter` 6→7, `PermutationTestFilter` 7→8. Position 5 reserved for the new filter; battery `default_filters()` now returns 8 filters in cost order.
4. `write_calibration_yaml` (`src/forge/feedback/auto_tune.py:46`) updated to emit the new section.
5. 9 new unit tests in `tests/unit/test_prefilters/test_predicted_activations.py` covering: intersection mechanics (pass / reject / empty / disjoint / partial overlap), the days_to_earnings-on-SPY silent-failure case explicitly, multiple regime gates intersected together, defensive guard on missing directional signal.

**T1.1 / T1.2 forward-compatibility note:**
- T1.1 (bidirectional inference via SignalSpec `direction` field) and T1.2 (entry_cadence field) are gated on contracts schema changes + Crucible-side template updates and aren't shipping yet. T1.3 ships now with phase-1 semantics: assumes all signals are on-each-bar (conservative over-count direction; fewer false-rejects). When T1.2 lands, T1.3 will be updated to distinguish on_edge vs on_each_bar entry cadence.
- T1.3 transparently handles `op="<"` configs because `activation_dates` already incorporates the threshold predicate — no special LONG_PUT handling needed at filter time.

**Hard rules check:**
- Not a `grammar.yaml` change (hard rule #10).
- Not a Crucible gate change (hard rule #3). Pre-filter is upstream of all Crucible gates.
- Auto-tightening of this knob is allowed (hard rule #4 — tightening is auto-apply-able); loosening writes to OPEN_PROPOSALS.md as usual.
- No Crucible internals imported (hard rule #2).

**Verification:**
- 1001 tests pass (full Forge suite, including 9 new T1.3 tests).
- Ruff + mypy strict clean on all changed scope.
- Live Forge service crashed and recovered cleanly mid-edit when `prefilter.yaml` and `calibration.py` were briefly out of sync; surfaced the importance of YAML-and-code-change ordering for any future calibration schema change.

**Operational notes:**
- Existing in-flight batch e2658f76 (the D033 first Tier 2 batch) is gated *without* this filter — it shipped pre-D038. Next batch shipped post-restart will include the new filter in the pre-filter battery.
- Default `min_entries=10` is conservative. Auto-tightening can raise it; loosening requires operator review per hard rule #4.

**Action:**
- `src/forge/prefilters/predicted_activations.py` (new)
- `src/forge/prefilters/calibration.py` (new dataclass + loader)
- `src/forge/prefilters/battery.py` (wire in)
- `src/forge/prefilters/{novelty,regime_exposure,permutation_test}.py` (cost_tier bumps)
- `src/forge/feedback/auto_tune.py` (yaml writer)
- `config/prefilter.yaml` (new section)
- 6 test files updated (3 cost_tier pins, 4 calibration fixtures, 1 new test file)
- `IMPLEMENTATION_DECISIONS.md` D038 (this entry)
- Forge service restart required.


## D039 — 2026-05-17 — T1.4 ETF-aware event regime gates + grammar v1→v2 bump

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T1.4 surfaced the third silent-failure mode from the translation corpus: `days_to_earnings` returns sentinel value 999 on ETF underlyings (SPY/QQQ/IWM/DIA — no earnings). A volatility_event config with `days_to_earnings <= 3` regime gate on an ETF underlying never fires, produces 0 trades, and silently rejects on `min_oos_trade_count`. D033 (Tier 2) made this worse because the sampler now produces per-config Tier 2 underlyings that may be ETFs.

Crucible Prompt 6 shipped 3 new macro-event indicators on 2026-05-17:
- `days_to_cpi` — distance to next CPI release
- `days_to_nfp` — distance to next Nonfarm Payrolls release
- `days_to_opex` — distance to next monthly options expiration

These are ETF-compatible (the events apply to the market, not the company).

**Change:**
1. **R3 expansion** (`src/forge/grammar/custom_predicates.py:118`): `_R3_EVENT_PROXIMITY_INDICATORS` grew from `(days_to_earnings, days_to_fomc)` to 5 indicators, adding the 3 new macro ones. New constants `_R3_ETF_INCOMPATIBLE_INDICATORS = {days_to_earnings}` and `_R3_ETF_UNDERLYINGS = {SPY, QQQ, IWM, DIA}`.
2. **R3 predicate logic** (`_r3_volatility_event_requires_event_proximity_gate`): now also rejects (vol_event, ETF underlying, days_to_earnings regime) combinations at validation time with a specific error message naming the ETF-compatible alternatives.
3. **Sampler ETF-awareness** (`src/forge/enumeration/sampler.py`): `_pick_underlying` now accepts `regime_indicators: tuple[str, ...]`. When any indicator is ETF-incompatible (currently just `days_to_earnings`), the underlying pool is restricted to single-names (excludes Tier 1 ETFs). Preserves R3 v2 at sample time so the validator doesn't have to reject downstream.
4. **Grammar version bump** v1 → v2 (`config/grammar.yaml`): `grammar_version: v2`, R3 rule's `version: 1 → 2`, evidence_to_relax updated. v1.yaml retained in `config/grammar_archive/`; v2.yaml added as the new canonical archive.
5. **Registry refresh**: triggered `crucible-registry-publisher.service` (one-shot) to re-export the registry snapshot. Now includes all 5 event indicators (`registry_snapshot_2026-05-18T033529Z.json`).

**3 new invariant tests** in `tests/unit/test_grammar/test_custom_predicates.py`:
- `test_r3_volatility_event_with_days_to_earnings_passes` — updated to use underlying="AAPL" (single-name); pre-D039 used "SPY" by default which now rejects.
- `test_r3_volatility_event_with_days_to_earnings_on_etf_rejects` — D039's headline case: vol_event + SPY + days_to_earnings rejects with an ETF-specific error message.
- `test_r3_volatility_event_with_days_to_fomc_passes_on_etf` — confirms macro-event indicators (FOMC/CPI/NFP/OPEX) are valid on ETFs.

**Updated fixtures**:
- `tests/integration/test_v1_grammar.py::test_v1_grammar_loads` — version assertion bumped "v1" → "v2".
- `tests/fixtures/grammar_property_helpers.py` — `volatility_event` template's regime_indicator switched from `days_to_earnings` to `days_to_fomc` (ETF-compatible; matches the fixture's hardcoded underlying="SPY").

**Hard rules check:**
- Hard rule #1: §3.5 21 rules count unchanged. R3 expanded internally — rule count remains 21.
- Hard rule #2: no Crucible internals imported. Crucible Prompt 6's new indicators reach Forge via the published registry (the contracts path).
- Hard rule #3: not a Crucible gate change.
- Hard rule #10: grammar version bumped v1 → v2, v1.yaml archived, v2.yaml archived, D039 logged.
- D037 stuck-state detector will reset on grammar version bump — `most_recent_grammar_change()` now returns the v2 changed_at timestamp.

**Verification:**
- 1003 tests pass (full Forge suite, 3 new T1.4 tests).
- Ruff + mypy strict clean on changed scope.
- Registry export verified to contain all 5 event indicators.

**Expected outcome:**
- All future vol_event configs on ETF underlyings use ETF-compatible event indicators (FOMC/CPI/NFP/OPEX).
- Sampler no longer produces (vol_event, ETF, days_to_earnings) combinations.
- T1.3 (predicted_activations) was previously catching the silent-failure case at pre-filter time via empty intersection; T1.4 now catches it at validation time, eliminating the wasted pre-filter compute on doomed configs.
- D035 stuck-state counter resets to 0 on the next batch (grammar bump triggers the floor).

**Coordination note**: Per the prompt's §T1.4, Crucible also needed a queue-time preflight in `runs_repository.queue_run` to reject incompatible combinations. Whether that's shipped is Prompt 6's scope; Forge's R3 v2 + sampler ETF-awareness is the upstream guard.

**Action:**
- `src/forge/grammar/custom_predicates.py` — R3 v2 predicate.
- `src/forge/enumeration/sampler.py` — `_pick_underlying` regime-aware.
- `config/grammar.yaml` — v1→v2 bump, R3 v2 metadata.
- `config/grammar_archive/v2.yaml` — new archive.
- 3 test updates + 1 fixture update.
- Registry re-published.
- `IMPLEMENTATION_DECISIONS.md` D039 (this entry).
- Forge service restart required.


## D040 — 2026-05-17 — T2.2 `forge grammar revert` CLI (reversibility for auto-tightening)

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.2 / Draft Enhancement 7 — every auto-tightening change needs a one-command revert path. Pre-D040 grammar version bumps wrote to `config/grammar_archive/` but had no operator tool to reverse a bad tightening; the operator would have to hand-edit `grammar.yaml` back to the prior content and bump the version manually, risking archive inconsistency.

**Change:** new CLI subcommand `forge grammar revert --to-version <prior_version> --initials <op>` in `src/forge/cli/grammar_cmd.py`.

Mechanics:
1. Locate `<archive_dir>/<to_version>.yaml`; fail loudly if missing.
2. Validate it loads cleanly via `load_grammar(...)` — rejects malformed archive entries.
3. Compute new version = max(existing v{N}) + 1 (refuses no-op if `to_version` would equal `new_version`).
4. Substitute the `grammar_version:` field in the prior content with the new version string, prepend a REVERT header comment, write to `grammar.yaml`.
5. Archive the new version via `archive_grammar(...)`.
6. Append a `grammar_versions` row to `forge.db` with `change_type='revert'` (reuses `_write_grammar_versions_row` from auto_tune.py).
7. Print a reminder to the operator to log the revert rationale in `IMPLEMENTATION_DECISIONS.md`.

**Why "promote forward" instead of overwrite**: hard rule #10's archive contract says every `grammar_version` maps to a fixed file. Overwriting `v2.yaml` with v1's content would corrupt the audit trail. Bumping to v3 (= v1's content with the v3 label) keeps history complete and the corrupted v2 recoverable for forensics. Same pattern as a clean-room "fresh fork from history."

**3 new unit tests** in `tests/unit/test_cli/test_grammar_cmd.py`:
- `test_revert_promotes_prior_version_forward` — happy path: revert v2 → v3-with-v1-content; v1.yaml and v2.yaml in archive untouched; grammar_versions audit row written.
- `test_revert_rejects_missing_version` — error if `to_version` isn't in the archive.
- `test_revert_rejects_empty_initials` — typer-style bad-input exit.

**Hard rules check:**
- Hard rule #4: this is operator-triggered (`--initials` required), not auto-revert. Preserves the "operator-in-the-loop" discipline for any change-of-direction.
- Hard rule #10: the new version IS archived; the archive contract holds.
- Not a grammar.yaml direct edit by Claude (operator runs this manually); not a Crucible change.

**Verification:**
- 1006 tests pass (full Forge suite, 3 new T2.2 tests).
- Ruff + mypy strict clean.
- README updated with the new subcommand row.

**Operational notes:**
- This is operator-triggered tooling — no autonomous trigger fires it.
- Forge service does NOT need restart for this; the CLI is a separate process. If grammar.yaml IS reverted, the next Forge iteration loads the new version automatically.
- Pattern established: any future "revert" semantics for other config files (prefilter.yaml, etc.) should follow this promote-forward-with-history convention.

**Action:**
- `src/forge/cli/grammar_cmd.py` — new `cmd_revert` command.
- `tests/unit/test_cli/test_grammar_cmd.py` — 3 new tests + helper `_write_grammar_yaml`.
- `README.md` — new row in the CLI table.
- `IMPLEMENTATION_DECISIONS.md` D040 (this entry).
- No Forge service restart required.


## D041 — 2026-05-17 — T2.1 confidence-weighted grammar proposals

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.1 / Draft Enhancement 6 — proposer-generated proposals carry a confidence score derived from their evidence sample size. Lets the operator (and any future auto-apply path, see T2.3) distinguish "this is based on 5 samples" from "this is based on 500 samples."

**Change:**
1. `src/forge/feedback/types.py`: `GrammarProposal` dataclass gains `sample_size: int = 0` and `confidence: float = 0.0` fields (defaults preserve back-compat).
2. `src/forge/feedback/proposer.py`: new `compute_confidence(sample_size)` step function — `<20 → 0.1`, linear ramp `20→100 → 0.3→0.7`, linear ramp `100→500 → 0.7→1.0`.
3. Each proposal-creation site (`_proposal_from_gate_failure`, `_proposal_from_hypothesis_pattern`, `_proposal_from_family_pattern`, `_proposals_from_param_history`) sets both fields and also stores them in `evidence_json` so downstream consumers (CLI, dashboards) see them without needing the dataclass.

**Hard rules check:** not a grammar change; not a Crucible gate change; auto-tightening behavior unchanged (T2.3 will gate it). Hard rule #4 stands.

**Verification:** 1028 tests pass (3 new T2.1 tests: step function, negative-rejection, end-to-end proposal carries fields). Ruff + mypy strict clean.


## D042 — 2026-05-17 — T2.6 signal correlation pre-filter

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.6 / Draft Enhancement 2 — §3.5 C1 blocks two indicators from the *same family*, but cross-family indicators can still be empirically redundant (e.g., RSI mean-rev family vs Stochastic-K momentum family — different families per registry, near-identical firing). New pre-filter complements C1's structural rule with an empirical check.

**Change:**
1. New `src/forge/prefilters/signal_correlation.py` — `SignalCorrelationFilter` (cost_tier=7). Computes pairwise Jaccard overlap of activation_dates across the config's signals; rejects when max pair exceeds `calibration.signal_correlation.max_jaccard_overlap` (default 0.85).
2. Calibration: `SignalCorrelationCalibration` dataclass + YAML loader + auto-tightening propagation in `apply_tightening`.
3. Battery: inserted at cost_tier=7; `RegimeExposureFilter` bumped 7→8; `PermutationTestFilter` bumped 8→9. Total filters now 9.
4. 7 new unit tests covering: pass/fail at threshold, identical signals, disjoint signals, partial overlap, single-signal trivial-pass, empty-set defensive.

**Hard rules check:** new pre-filter is upstream of Crucible gates (hard rule #3 stands). Auto-tightening of the new knob obeys hard rule #4 pattern.

**Verification:** 1028 tests pass. Ruff + mypy strict clean.


## D043 — 2026-05-17 — T2.7 structural fingerprint extension to novelty filter

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.7 / Draft Enhancement 3 — the existing `NoveltyFilter` checks *temporal* Jaccard overlap of activation dates. T2.7 adds a *structural* check: hash of (hypothesis, signal indicator IDs by role, exit IDs, dte_bucket, sizer_mode). Two configs with the same fingerprint encode the same structural idea (Optuna's job to explore parameters within); Forge shouldn't redundantly enumerate parameter variations.

**Change:**
1. `src/forge/prefilters/novelty.py` — new `compute_structural_fingerprint(config)` helper. Returns a 16-hex-char SHA-256 prefix of the canonical JSON of the config's structural components. Excludes thresholds, deltas, selector params (Optuna's territory).
2. `NoveltyFilter.apply` checks fingerprint match BEFORE temporal Jaccard (cheaper, exact); rejects with `details["reject_reason"]="structural_fingerprint_match"` if matched.
3. `FilterContext.prior_structural_fingerprints: frozenset[str]` added (defaults to empty frozenset). Production population is a future ship (load from `submissions.config_json` history); the framework lands now.
4. 3 new tests: fingerprint stable across param changes, distinguishes indicator swaps, rejection on fingerprint match.

**Hard rules check:** novelty is upstream of Crucible gates. Hard rule #3 / #4 stand.

**Verification:** 1028 tests pass. Ruff + mypy strict clean.


## D044 — 2026-05-17 — T2.3 counterfactual evaluation framework

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.3 / Draft Enhancement 8 — before any future auto-apply of a proposer-generated proposal, check whether the proposed change would regress any recently promoted strategy. Auto-tightening that would harm a working config gets escalated to operator review.

**Scope clarification:** the existing `auto_tune.py` calibration adjustment (rolling-rate-driven) is a SEPARATE path from proposer-generated proposals. The draft's counterfactual logic targets the latter (which carries `sample_size + confidence` per T2.1). Today no caller auto-applies proposer-generated proposals (operator runs `forge grammar apply-proposal`); T2.3 is the framework a future auto-apply path will consume.

**Change:**
1. `src/forge/feedback/proposer.py`: new `CounterfactualResult` dataclass + `evaluate_counterfactual(proposal, recent_promoted_count)` (phase-1: coarse — 0 promoted → safe; >0 promoted → conservative worst-case 1.0 rejection_rate).
2. `should_auto_apply_proposal(proposal, counterfactual, min_confidence=0.7)` decision function: escalates on either non-zero rejection_rate OR confidence below threshold.
3. Phase-1 doesn't replace per-strategy re-validation; replace `evaluate_counterfactual`'s body once `submissions.config_json` history queries are wired to compute exact rejection sets.

**Hard rules check:** hardens the auto-apply path (when wired) — strictly more conservative than current behavior. Hard rule #4 (loosenings stay manual) unchanged.

**Verification:** 1028 tests pass (5 new T2.3 tests: safe-no-promotions, conservative-with-promotions, escalation-on-counterfactual, escalation-on-low-confidence, happy-path-auto-apply). Ruff + mypy strict clean.


## D045 — 2026-05-17 — T2.4 persistent proposal detection

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.4 / Draft Enhancement 9 — when the same proposal theme recurs across 3+ batches without being applied, escalate it with a `[PERSISTENT]` flag. Helps operators distinguish "noisy false-positive" from "the data keeps insisting on this; either re-evaluate the rejection or fix the proposer's noise source."

**Change:**
1. `src/forge/feedback/proposer.py`: new `PersistentProposal` dataclass + `detect_persistent_proposals(proposals, min_occurrences=3)` function.
2. Theme = `(evidence.trigger, evidence.target | hypothesis | family)` — same dedup key as D034's `_intent_key`. Two proposals sharing a theme convey "same intent appeared again."
3. Returns list of `PersistentProposal` sorted by occurrence_count descending.

**Wiring note:** the detection function lives in `proposer.py` but no caller consumes it yet. Future wiring: CLI `forge grammar list-proposals` reads the proposal-table window and surfaces persistent ones with the `[PERSISTENT]` tag (per the draft). This ship lands the detection mechanism; the surfacing is a small follow-up CLI change.

**Hard rules check:** detection-only; no auto-action. Hard rule #4 unchanged.

**Verification:** 1028 tests pass (3 new T2.4 tests: 3-occurrence threshold, below-threshold quiet, theme distinction). Ruff + mypy strict clean.


## D046 — 2026-05-18 — Feedback loop multi-batch reconciler + oldest-unfinished rate-limit semantics

**Spec section:** DESIGN.md §7.3 (rate limiter), §8.2 (feedback consumer); CLAUDE.md "Forge succeeds when, over time, its submissions become more likely to promote"; 2026-05-17 audit P0 finding "feedback writeback gap."

**Context:** The 2026-05-17 audit found that the Forge → Crucible → Forge loop has been silently broken since 2026-05-14: 4,020 submissions ever, 308 gated (all from one batch on 2026-05-14), 2026-05-15 burst of 3,110 submissions never reconciled, 2026-05-16 produced zero batches, 2026-05-17 produced one batch (e2658f76) that has been rate-limit-blocked at 0/200 for 8+ hours. The diagnostic agent traced this to two coupled regressions:

1. **Consumer is single-batch** (`forge.feedback.consumer.consume_batch_results` + the two CLI driver paths `cli/main.py:630` and `cli/feedback_cmd.py:104`). Each invocation reconciles exactly one batch (the just-submitted one by default). Once Crucible's per-run latency exceeded one Forge poll cycle, older batches accumulated stranded `status='submitted'` rows the latest-batch-only consumer never reached. By 2026-05-17 the system had 11 stranded batches and 3,712 un-reconciled candidates.
2. **Rate-limiter picks the latest batch** (`forge.submission.rate_limiter.check_rate_limit` — `ORDER BY submitted_at DESC LIMIT 1`). With the latest batch always at the back of Crucible's queue (still 0% gated) and older batches stranded behind the consumer bug, the rate-limit check stayed permanently blocked.

The contracts and Crucible publisher are correct; export schema parses cleanly through `crucible_contracts.queries.load_recent_gated_runs_from_export`. The bug is entirely in Forge's consumer-driver and rate-limit selection.

**Decision:**

1. **Multi-batch reconciler** — new `forge.feedback.consumer.reconcile_all_pending(forge_db, crucible_db, *, exports_dir=None) -> tuple[BatchFeedback, ...]`. Reads the gated-runs export once, then per-batch reconciles every `forge_batch_id` that still has `status='submitted'` rows. Each per-batch call is itself idempotent. `consume_batch_results` gained an optional `crucible_runs` argument so the reconciler can pass the pre-fetched snapshot to every per-batch invocation rather than refetching.
2. **Oldest-unfinished rate-limit semantics** — `check_rate_limit` now finds the OLDEST batch with `status='submitted'` rows (not the latest). The oldest is the actual queue front; the latest is the back. Once the oldest drains, the next-oldest takes over. In steady state (no stranded batches) the oldest IS the latest and behavior matches the prior path. `RateLimitStatus` gained a `threshold` field so the CLI's "blocked" message can report the actual threshold value instead of a hardcoded `>=80%` string (which had been stale since D036's drop to 0.50).
3. **Pre-rate-limit reconcile** — `_run_one_cycle` in `cli/main.py` now calls a new `_reconcile_pending_silently` helper before `check_rate_limit`, so the rate-limit check operates on fresh local-DB state. The reconcile call absorbs `QueryError` (Crucible offline) and logs a `reconciled: batches=N newly_gated_total=M` line when there's something to report.

**Hard rules check:**
- Hard rule #2 (no Crucible internals) — unchanged; reconciler still goes through `crucible_contracts.load_recent_gated_runs_from_export` / `get_recent_gated_runs`.
- Hard rule #3 (Crucible gate untouched) — unchanged.
- Hard rule #6 (determinism) — unchanged; the reconciler iterates batches in stable `MIN(submitted_at) ASC, forge_batch_id ASC` order.
- Hard rule #10 (grammar archive) — N/A.

**Alternatives considered:**
- **Bump Crucible's gated-runs export limit (`_DEFAULT_LIMIT=1000`)** to ~10,000 so historical rows stay visible while Forge catches up. Cross-system change; rejected as the primary fix because the Forge-side single-batch consumer would still leave older `submitted` rows stranded even with a larger export window. Recommended as a complementary Crucible-side improvement.
- **Track in-flight queue depth instead of per-batch percent gated.** Simpler in some ways ("don't submit if total `submitted` rows exceed 2× batch size") but loses §7.3's per-batch semantics; deferred.
- **Skip reconcile when `--consume-feedback` is off.** Rejected: the reconcile is what makes the rate-limit accurate; coupling them to the same flag is the regression we just fixed.

**Verification:**
- 29 targeted tests pass: 12 in `test_rate_limiter.py` (including 3 D046-specific: `test_uses_oldest_unfinished_batch`, `test_oldest_batch_with_local_gated_rows_clears_to_next`, `test_no_submitted_rows_clears_completely`) and 17 in `test_consumer.py` (including 3 D046-specific: `test_reconcile_all_pending_processes_every_in_flight_batch`, `test_reconcile_all_pending_is_idempotent`, `test_reconcile_all_pending_returns_empty_when_no_submitted_rows`).
- Full Forge suite: 1043/1043 passing. Ruff + mypy strict clean.
- The `_insert_submission` test helper in `test_rate_limiter.py` was updated to default to `status='submitted'` (matches production submitter at `forge.submission.submitter.py:169`). Earlier tests had used `status='pending'`, which production never writes — fixing the helper alongside the rate-limit-semantic change preserves all pre-existing test intents.

**Recovery for stranded data:**
On forge.service restart, the new `_reconcile_pending_silently` call will sweep every `submitted` row in `forge.db.submissions` against the latest `gated_runs_*.json` export. Crucible's current export contains ~1,000 rows that ARE Forge-submitted hashes, spanning ~10 of the 11 stranded batches. Those will flip to `status='gated'` on the first iteration. The remaining ~2,712 candidates not yet in Crucible's export will continue to drain as Crucible processes them and the export window advances. No DB surgery required.

**Operational sequence:**
1. Tests green (Forge suite, this session).
2. Operator restarts `forge.service`.
3. First iteration: `_reconcile_pending_silently` flips ~1,000 rows; rate-limit oldest-batch logic now points at the oldest still-`submitted` batch (likely a 2026-05-15 batch with partial export overlap).
4. Loop unblocks once that batch's local+export gated count reaches 50% (D036 threshold).
5. `forge.service` resumes normal cadence.

**Action:**
- `src/forge/feedback/consumer.py` — `reconcile_all_pending` added; `consume_batch_results` gained optional `crucible_runs` param.
- `src/forge/submission/rate_limiter.py` — oldest-batch SQL + `threshold` field on `RateLimitStatus`.
- `src/forge/cli/main.py` — `_reconcile_pending_silently` helper + pre-rate-limit call; updated "blocked" message uses `rate.threshold`.
- `tests/unit/test_submission/test_rate_limiter.py` — helper default → `'submitted'`; 3 new D046 tests; old `test_uses_most_recent_batch` rewritten as `test_uses_oldest_unfinished_batch`.
- `tests/unit/test_feedback/test_consumer.py` — 3 new D046 reconciler tests.
- `IMPLEMENTATION_DECISIONS.md` D046 (this entry).
- Forge service restart required to pick up the fix.


## D047 — 2026-05-18 — T2.5 trade-concentration post-batch analyzer

**Context:** `PROMPT_5_FORGE_V1_1_REVISED.md` §T2.5 / Draft Enhancement 1 originally specified a *pre-filter* rejecting configs whose top-3 trades constituted >40% of P&L. That required `context.simulated_trades` at pre-filter time — Forge's pre-filters operate on activation_dates from Crucible's feature cache and don't have per-trade ledgers (hard rule #2 bars accessing Crucible's runs DB directly).

**Scope transformation per operator decision (2026-05-18):** ship the same intent as a **post-batch analyzer** instead. Lives in `forge/feedback/` alongside the proposer; reads gated runs from Crucible's published exports.

**Change:**
1. New `src/forge/feedback/trade_concentration.py`:
   - `compute_concentration_proxy(profit_factor, n_trades, win_rate) -> float` — coarse proxy from aggregated metrics (the export carries no per-trade ledger).
   - `analyze_promotion_concentration(gated_runs, *, threshold=0.05) -> list[ConcentrationFlag]` — scans promoted runs, flags suspects sorted by proxy descending.
2. `ConcentrationFlag` dataclass carries `run_id`, `config_hash`, `proxy_score`, `profit_factor`, `n_trades`, `win_rate`, `threshold` for operator review.
3. 8 new unit tests covering proxy correctness, ignore-rejected runs, sort order, threshold configurability.

**Proxy formula:** `profit_factor / (n_trades × max(win_rate, 0.01))`. High proxy → likely concentrated (few outsized wins drive a high PF on a small trade count). Calibrated against typical broad-distribution strategies (PF=1.5, n=200, wr=0.5 → proxy=0.015) vs concentrated ones (PF=8, n=40, wr=0.2 → proxy=1.0). Default threshold=0.05 sits between.

**Limitation acknowledged in module docstring:** the exact "top-3 trade share" check from the draft needs trade-ledger access. Two future paths to sharpen:
- Crucible adds `top_3_trade_pnl_share` to the export metrics (small Crucible-side addition).
- Crucible exposes a per-run trade-ledger query that Forge consumes via `crucible_contracts`.
Either way, the framework lands here; sharpening swaps the proxy with the real metric.

**Wiring note:** the analyzer is callable but no caller invokes it yet. Future wiring: `forge feedback` CLI runs `analyze_promotion_concentration` over the latest export and writes flagged runs as `[CONCENTRATION_SUSPECT]` proposals to `OPEN_PROPOSALS.md` for operator review. Small follow-up CLI integration.

**Hard rules check:**
- Hard rule #2: no Crucible internals imported; reads gated_runs via the contracts-blessed export path.
- Hard rule #3: not a Crucible gate change. Post-batch analyzer surfaces operator-actionable signals only.
- Hard rule #4: any concentration-driven tightening writes to OPEN_PROPOSALS.md (when wiring lands), never auto-applies.

**Verification:** 1043 tests pass. Ruff + mypy strict clean on new module.


## D048 — 2026-05-18 — `scripts/requeue_high_value_configs.py` — selective historical re-queue

**Context:** Most of Forge's 4020 historical submissions were emitted while one or more silent-failure bugs were active:
- Pre-D033 (2026-05-16): per-config underlying not set; feature cache SPY-locked.
- Pre-D037 (2026-05-17): Bayesian failure-bias sampler collapsed onto 1-2 hypotheses per batch.
- Pre-D038/D039 (2026-05-17): silently-inert configs (e.g., days_to_earnings on ETFs) reached Crucible and ate compute.

The infrastructure is now fixed. Some historical configs that were rejected by silent failures might pass v1.1 evaluation. Mass re-run of all 4020 is infeasible (~55 days of Crucible compute). Operator approved a **targeted re-queue** of high-value subsets.

**Change:** new `scripts/requeue_high_value_configs.py`.

Mechanics (mirrors the proven `processed/ → inbox/` recovery pattern from the 2026-05-15 batch 550e24a2 incident):
1. Query Forge's `submissions` DB for three selection sets:
   - **Top N by recency** (default N=50): most-recent submissions, likeliest to reflect post-D033 universe.
   - **All `tail_hedge`** (1851 configs): D039's runner-side PF/CPCV/WF exemptions + T1.4's ETF event indicators all relevant; pre-D039 they were uniformly reject-by-gate-domain-mismatch.
   - **All `relative_value`** (1154 configs): D033's pairs handling + T1.4 macro events relevant.
2. For each selected `config_hash`, copy `~/optbt_data/inbox/processed/{hash}.json` → `~/optbt_data/inbox/{hash}.json` atomically (tmp + rename).
3. Crucible's inbox-watcher picks the JSON up, allocates a fresh `run_id`, runs it through Crucible v1.1's gates.
4. Dedup across categories — a top-N tail_hedge config doesn't get copied twice.

**Hard rules check:**
- Hard rule #9 (submissions idempotency) preserved: this script bypasses Forge's submitter and writes directly to Crucible's inbox. Forge's `submissions` table is unchanged. Crucible allocates a fresh `run_id`, so no FK collision.
- Hard rule #2: no Crucible internals imported. Only writes to the well-known inbox-watcher contract path.

**Usage:**
```
uv run python scripts/requeue_high_value_configs.py \
    --forge-db ~/forge_data/forge.db \
    --inbox-dir ~/optbt_data/inbox \
    --processed-dir ~/optbt_data/inbox/processed \
    --top-n 50 [--dry-run]
```

`--dry-run` prints what would be re-queued without writing. Operator can iterate on selection criteria before committing.

**Verification:** ruff + mypy clean (no test for this script — operational tooling, exercised by manual runs in the recovery cycles).


## D049 — 2026-05-18 — Grammar version audit row self-healing

**Spec section:** CLAUDE.md hard rule #10 (grammar archive + decision-log audit on every yaml change); D035 (stuck-state floor reads `MAX(grammar_versions.changed_at)`); DESIGN.md §13.3 (no silent grammar changes); 2026-05-17 audit P1 finding "empty `grammar_versions` table despite v2 active."

**Context:** Hard rule #10 requires version bumps + archive + decision-log entries on every `grammar.yaml` change, and the `grammar_versions` table exists as the structural audit-trail companion. Pre-D049 the table was written by only three code paths — `auto_tune.apply_tightening`, `grammar_cmd.cmd_apply_proposal`, and `grammar_cmd.cmd_revert`. Manual operator yaml bumps (e.g., D039's v1→v2 R3 expansion) had no code path that recorded an audit row, so the table was empty on the operator's `~/forge_data/forge.db` despite the active grammar being v2. D035's stuck-state grammar-floor logic depends on this table to reset on grammar changes; an empty table silently defeats that mechanism.

**Decision:** Add `ensure_grammar_version_recorded(db, *, grammar, yaml_path, at)` to `forge.feedback.auto_tune`. Self-healing: when called, the helper checks whether a `grammar_versions` row exists for `grammar.grammar_version`; if missing, it inserts one with `change_type='manual_bump'`, the yaml's SHA-256, and the rule count, with `operator_initials=None` (manual edits don't carry initials the way `apply-proposal` does). Idempotent — the second call is a SELECT-only no-op.

The CLI's `_run_one_iteration` calls a thin wrapper (`_ensure_grammar_version_recorded_silently`) once per iteration after `load_grammar` and before the rate-limit reconcile. The wrapper absorbs unexpected errors so the audit-row path can never crash the production loop. Diagnostic commands (`forge enumerate`, `forge prefilter`) intentionally don't call it — they have no DB and shouldn't write side effects.

**Hard rules check:**
- Hard rule #10 — this decision IS the structural piece hard rule #10 has been depending on. Decision-log audit (this file) + archive (`config/grammar_archive/`) + DB audit (`grammar_versions`) now all converge on every grammar change.
- Hard rule #6 (determinism) — `changed_at` is `forge.core.clock.utc_now()` which is the blessed clock; not seed-dependent.
- Not a §3.5 rule change.

**Alternatives considered:**
- **Pre-commit hook writes the row at commit time.** Rejected; the row needs to land in the operator's `~/forge_data/forge.db`, not the repo. Pre-commit can't reach there.
- **`forge grammar record-bump` CLI command** (operator-explicit, parallel to `apply-proposal` / `revert`). Considered as complementary, deferred. Self-healing is the minimal-friction safety net; if/when the operator wants explicit initials on a manual bump, the CLI subcommand can be added in a follow-up.
- **Side-effect inside `load_grammar`.** Rejected — the loader is called from tests and read-only diagnostics; coupling a DB write to a parsing function is bad layering.

**Verification:**
- 3 new unit tests in `tests/unit/test_feedback/test_auto_tune.py`: writes row when missing, idempotent on second call, never overwrites a pre-existing row from a different code path.
- 2 new invariant tests in `tests/invariants/test_phase5_invariants.py`: end-to-end self-heal against the production grammar (`config/grammar.yaml`), and structural check that `_run_one_iteration` still calls the helper (so a future refactor can't silently un-wire it).
- 12 auto_tune unit tests + 17 Phase 5 invariants all pass. Full Forge suite remains 1043+ green.

**Recovery for the operator's existing DB:**
The first post-restart iteration will write the missing `v2` row via the self-heal. The historical `v1` row is lost (it was never written; this fix is forward-looking, not retroactive). That is acceptable per the audit-row's intent — D035 reads `MAX(changed_at)` to floor the stuck-state counter, so the v2 row alone establishes the correct floor going forward.

**Action:**
- `src/forge/feedback/auto_tune.py` — `ensure_grammar_version_recorded` helper.
- `src/forge/cli/main.py` — `_ensure_grammar_version_recorded_silently` wrapper + call from `_run_one_iteration`.
- `tests/unit/test_feedback/test_auto_tune.py` — 3 new D049 unit tests.
- `tests/invariants/test_phase5_invariants.py` — 2 new D049 invariant tests.
- `IMPLEMENTATION_DECISIONS.md` D049 (this entry).
- Forge service restart required to pick up the helper (rolls in with the D046 fix).


## D049 — 2026-05-18 — T2.3/T2.4/T2.5/T2.7 framework wiring + re-queue execution

**Context:** D041-D045 + D047 shipped the framework helpers for T2.3 (counterfactual), T2.4 (persistent detection), T2.5 (trade-concentration analyzer), and T2.7 (structural-fingerprint novelty) but didn't wire them into any production caller. D049 ships the wiring.

**Change:**

1. **T2.7 — structural-fingerprint dedup against history** (`src/forge/cli/main.py`):
   - New `_load_prior_structural_fingerprints(forge_db_path)` helper: scans `submissions.config_json`, computes fingerprint per config, returns the union. Empty frozenset when DB is `:memory:` or missing.
   - `_run_battery_for_seed` gains `forge_db_path: Path | None = None` kwarg; populates `FilterContext.prior_structural_fingerprints` from the loader. NoveltyFilter's D043 check now actually fires in production — rejects new candidates whose structural skeleton matches any historical submission.
   - Production `forge run` call site at the bottom of `_run_loop_iteration` threads `forge_db_path` into `_run_battery_for_seed`.

2. **T2.3 — counterfactual annotation on every proposal** (`src/forge/cli/main.py::_consume_feedback_after_submit`):
   - After `propose(...)` returns, for each proposal compute `evaluate_counterfactual(proposal, recent_promoted_count=feedback.promoted_count)`.
   - Inject `counterfactual_rejection_rate` and `counterfactual_promoted_count` into `evidence_json` and write the annotated proposal via `append_proposal`. Operator review (`forge grammar list-proposals` / dashboards) sees the safe/escalate signal alongside the rationale.
   - Stops short of auto-application: today operator still runs `apply-proposal` manually. A future auto-apply path consumes `should_auto_apply_proposal` from the same module.

3. **T2.5 — post-batch trade-concentration analyzer** (`src/forge/cli/main.py::_consume_feedback_after_submit`):
   - After proposer runs, scan `feedback.outcomes` for concentration suspects via `analyze_promotion_concentration`.
   - Each `ConcentrationFlag` is emitted as a tighten-grammar proposal with `trigger="promotion_concentration_suspect"` so D034's intent-dedup naturally handles repeats and D045's persistent-detection picks them up if they recur.
   - rationale string is operator-readable ("Promoted run X has concentration proxy 0.42 > threshold 0.05 (PF=8, n=40, wr=0.2)").

4. **T2.4 — persistent-theme tag in `forge grammar list-proposals`** (`src/forge/cli/grammar_cmd.py`):
   - `cmd_list_proposals` now reconstructs minimal `GrammarProposal` objects from the DB rows, runs `detect_persistent_proposals` over the pending set, and prints a `[PERSISTENT]` tag next to any proposal whose theme has 3+ pending occurrences.
   - Appends a "persistent themes" footer summarizing the recurring `(trigger, detail)` tuples.
   - Operator sees: "this proposal keeps coming back — either fix the proposer's noise source or re-evaluate your prior rejections."

**Re-queue execution:** `scripts/requeue_high_value_configs.py` invoked at 2026-05-18 (after the D048 ship). Selection: top-50-by-recency + all tail_hedge (1851) + all relative_value (1154). Total: **3047 configs re-queued** (with 8 cross-category duplicates correctly deduped). Inbox now holds 3047 JSONs; Crucible's inbox-watcher consumes them at the runner's pace.

**Crucible coordination:** operator separately tasked the Crucible agent with identifying speed-up opportunities. Current runner pace (~17-27 min/run baseline, occasional 80-min spikes) implies the 3047 backlog at ~36-57 days; speedup work shrinks that meaningfully.

**Hard rules check:**
- Hard rule #2: T2.7 wiring reads only Forge's own DB; no Crucible internals imported.
- Hard rule #4: T2.5 / T2.3 wirings write to `OPEN_PROPOSALS.md` for operator review; never auto-apply.
- Hard rule #9: re-queue script bypasses Forge's submitter via `processed/ → inbox/` copy; `submissions` table unchanged; new run_ids on Crucible side.

**Verification:** 1050 tests pass (2 list-proposals tests adjusted to handle tz-aware datetime on DB-roundtrip). Ruff + mypy strict clean on changed scope.

**Action:**
- `src/forge/cli/main.py` — `_load_prior_structural_fingerprints` + `_run_battery_for_seed` plumbing + T2.3/T2.5 wiring in `_consume_feedback_after_submit`.
- `src/forge/cli/grammar_cmd.py` — T2.4 persistent-tag in `cmd_list_proposals`.
- `IMPLEMENTATION_DECISIONS.md` D049 (this entry).
- 3047 historical configs re-queued.
