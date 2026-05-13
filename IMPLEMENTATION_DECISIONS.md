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
