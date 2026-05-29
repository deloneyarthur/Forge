# Forge — Implementation Decisions Log

Append-only. Each entry: ID, date, spec section, decision, rationale, alternatives considered, action.

Order is chronological. Decisions are referenced from `STATUS.md`, `OPEN_QUESTIONS.md`, and `PHASE_N_HANDOFF.md`.

> **Note (D059 / P3-4 2026-05-18):** Older entries reference Crucible coordination prompts (`CRUCIBLE_*_AGENT_PROMPT.md` at repo root) that were deleted in commit `e85f0d4` ("docs: archive paired Crucible coordination docs + drop completed unpaired prompts") after their work shipped. The references are preserved in the historical narrative below; the prompt files themselves are recoverable via `git show e85f0d4^:CRUCIBLE_*_AGENT_PROMPT.md`. The 7 deleted prompts: `CRUCIBLE_FEATURE_CACHE_AGENT_PROMPT.md`, `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`, `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md`, `CRUCIBLE_EV_DEADLOCK_AGENT_PROMPT.md`, `CRUCIBLE_EMPTY_THRESHOLD_AGENT_PROMPT.md`, `CRUCIBLE_DB_CHECKPOINT_ON_BATCH_AGENT_PROMPT.md`, `CRUCIBLE_TRADE_CONCENTRATION_METRIC_AGENT_PROMPT.md`.

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


## D051 — 2026-05-18 — Grammar version audit row self-healing

(Originally written as D049; renumbered to D051 because the parallel-agent
commit `6db2be5` also took D049 for "T2.3/T2.4/T2.5/T2.7 framework wiring +
re-queue execution." This entry chronologically precedes that one but the
parallel agent's commit was on disk first, so the natural resolution is to
push the later doc-only entry forward to the next free number.)

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


## D050 — 2026-05-18 — T2.5 swap: heuristic proxy → real `top_3_trade_pnl_share` metric

**Context:** D047 shipped T2.5's post-batch trade-concentration analyzer with a heuristic proxy (`profit_factor / (n_trades × win_rate)`) because Forge had no access to per-trade P&L. D049's wiring made the analyzer fire on every batch. Crucible commit `6a57ee5` (2026-05-18) shipped the real metric `top_3_trade_pnl_share = sum(|pnl| of top-3 trades) / sum(|pnl| of all)` directly in the gated_runs export per the Forge-side prompt `CRUCIBLE_TRADE_CONCENTRATION_METRIC_AGENT_PROMPT.md`.

**Change:** `src/forge/feedback/trade_concentration.py` now prefers the real metric over the proxy:
1. `_extract_metric(metrics)` reads `top_3_trade_pnl_share` from the metrics dict; if present, returns `(value, "top_3_share", 0.40)`. If absent (pre-Crucible-6a57ee5 runs in the export), falls back to `compute_concentration_proxy(...)` and returns `(proxy, "fallback_proxy", 0.05)`.
2. `ConcentrationFlag` schema updated: `proxy_score` → `score` with `metric_type: Literal["top_3_share", "fallback_proxy"]`. Downstream consumers (the OPEN_PROPOSALS flag in `cli/main.py::_consume_feedback_after_submit`) updated to use the new field names.
3. Default thresholds calibrated per-scale: `top_3_share_threshold=0.40` (the draft Enhancement 1's headline value), `fallback_proxy_threshold=0.05` (existing).

**Why graceful fallback**: the gated_runs export is a rolling window; on the day of the Crucible deploy it contains a mix of pre-deploy rows (no `top_3_trade_pnl_share` key) and post-deploy rows (key present). The dual-path analyzer handles both correctly without operator intervention. Once the export window fully rolls past the deploy time, all rows carry the real metric and the fallback path becomes dead code (safe to remove in a future cleanup).

**Hard rules check:**
- Hard rule #2: no Crucible internals imported; reads only the contracts-blessed export.
- Hard rule #3: not a Crucible gate change; analyzer surfaces operator-actionable signals only.
- Hard rule #4: any concentration-driven proposal writes to OPEN_PROPOSALS for operator review (D049 wiring already in place); never auto-applies.

**Verification:**
- 15 unit tests covering: real-metric path (4 cases: passing balance, flagged concentration, exact-threshold boundary, just-above-threshold), fallback proxy path (2 cases), mixed-export transition (1 case), shared behaviors (ignore-rejected, sort-descending, diagnostic fields, threshold overrides).
- 1055 tests pass (full Forge suite, including 5 net-new T2.5 tests on top of D047's 10).
- Ruff + mypy strict clean.

**Verified live:** Crucible commit `6a57ee5` shipped in the active runner; the latest gated_runs export at `~/optbt_data/exports/gated_runs_2026-05-18T173931Z.json` contains the new key (though current post-deploy runs all have `n_trades=0` so the field is `None` until a non-zero-trade run completes).

**Action:**
- `src/forge/feedback/trade_concentration.py` — dual-path metric extraction.
- `src/forge/cli/main.py::_consume_feedback_after_submit` — rationale/evidence_json updated for new fields.
- `tests/unit/test_feedback/test_trade_concentration.py` — rewritten for both paths.
- `IMPLEMENTATION_DECISIONS.md` D050 (this entry).


## D052 — 2026-05-18 — Reconciler export-window low-watermark fallback

**Spec section:** §7.3 rate limiter; §8.2 feedback consumer; D046 (oldest-batch rate-limit policy); CLAUDE.md per-batch operation order step 8.

**Context:** D046 shipped oldest-batch rate-limit semantics on 2026-05-18 — Forge now waits for the OLDEST in-flight batch to reach the gating threshold before submitting a new batch. The 2026-05-18 11:36 PDT post-restart audit surfaced the corollary failure mode: Crucible's gated-runs export is a rolling top-1000 window (`Crucible/scripts/export_gated_runs.py:44`). Forge's reconciler reads only what's currently in that window. A `submitted` row whose decision rolled off the window — concretely batch `716677d6-7fee-401e-8ff7-59f6e050a20d`, 2 configs submitted 2026-05-13 20:40, decisions rendered 2026-05-13 23:44 and last visible in the export at `gated_runs_2026-05-15T091106Z.json` — has no path back to `gated` status. Per D046, that batch pins the loop forever.

**Decision:** Add `_flush_aged_out_submissions(forge_db, runs)` in `forge.feedback.consumer`. Before each per-batch reconcile pass, compute `watermark = min(decided_at)` over the current export's `GatedRun`s and the set of `config_hash`es in the export. Any `submitted` row whose `submitted_at < watermark` AND whose `config_hash` is not in the export is "aged out": Crucible's decision for it (if any was made) has rolled off the window and is unreachable. Transition such rows to `status='gated'` with `crucible_run_id = '00000000-0000-0000-0000-000000000000'` (RFC-4122 nil UUID sentinel — distinguishable from any real run_id in audit queries). Empty `runs` (Crucible-offline) is a no-op: flushing in that condition would mask a Crucible outage.

**Why the dual guard** (`submitted_at < watermark` AND `config_hash NOT IN export_hashes`):
- Watermark alone false-flushes rows that ARE in the export but whose `submitted_at` happens to precede their own decision time (e.g., row submitted at noon, Crucible decides at 2pm — watermark is the 2pm decision, noon falls below it). Those rows must reconcile via the normal join, not the sentinel path.
- Hash-not-in-export alone false-flushes recent submissions Crucible hasn't yet processed (still in pending queue). The watermark guarantees enough time has passed for a decision to have been rendered.

**Hard rules check:**
- Hard rule #2 (no Crucible internals): contracts-blessed `GatedRun` only. No new imports outside `crucible_contracts`.
- Hard rule #6 (determinism): the flush touches `submissions` rows only; no enumeration state, no seed dependency.
- Hard rule #8 (clock/seed): no `datetime.now()`; the watermark is derived from contracts data.
- Hard rule #9 (submission idempotency): the sentinel update is gated by `WHERE status = 'submitted'`, so re-running over an already-flushed row is a no-op.

**Alternatives considered:**
- **Increase Crucible's export window size to "unlimited".** Rejected — that's a Crucible-side change, doesn't address the structural Forge dependency on export-window-size, and would unbounded-grow the export file. Forge should not depend on the window being any particular size.
- **Reconcile against `runs.duckdb` directly when the export misses.** Rejected — Crucible's `db_writer` service holds an exclusive lock on the writer file; this is the original reason for the export-based path (see `rate_limiter.py:160-167`). Forge would need a separate read replica or a contracts query helper that doesn't yet exist.
- **Mark with a distinct status (`gated_via_timeout`) rather than `gated`+sentinel.** Rejected — every downstream query (`SELECT ... WHERE status='gated'`, `WHERE status IN ('submitted','gated')`) would need updating. Many call sites; one would be missed. The sentinel `crucible_run_id` is queryable for distinction when needed (`WHERE crucible_run_id = '00000000-...-000000000000'`) and invisible everywhere else.
- **Skip the watermark; use only `config_hash NOT IN export_hashes`.** Rejected — would flush a row submitted 10 seconds ago whose decision Crucible hasn't yet rendered (still in the writer queue). The watermark provides the "enough time has passed" guarantee.

**Verification:**
- 4 new unit tests in `tests/unit/test_feedback/test_consumer.py`:
  - `test_reconcile_all_pending_flushes_predates_export_window` — stranded row gets sentinel; visible row reconciles via join.
  - `test_reconcile_all_pending_does_not_flush_rows_inside_export_window` — row younger than watermark stays `submitted` (no false-positive flush).
  - `test_reconcile_all_pending_aged_out_flush_idempotent` — second pass over already-flushed row is a no-op.
  - `test_reconcile_all_pending_no_flush_when_export_empty` — Crucible-offline condition: no false flushes.
- 2 new invariant tests in `tests/invariants/test_phase5_invariants.py`:
  - `test_aged_out_sentinel_is_nil_uuid` — sentinel value pinned to RFC-4122 nil UUID.
  - `test_reconcile_all_pending_calls_aged_out_flush` — structural call-site check (no silent un-wire).
- Full Forge suite: 1059 passing. Ruff + mypy strict clean.

**Operator unstick action for the existing 2 stranded rows:**
The 2 zombie rows from batch `716677d6` predate the structural fix. On the next `forge.service` restart with this change live, the first iteration's reconciler pass will flush them via the new path: their `submitted_at = 2026-05-13 20:40` is well below any plausible current watermark and their `config_hash`es are no longer in the export window. No manual SQL needed. (For faster unblock, the operator may still apply the one-time UPDATE in the brief — but with this fix in place it's a convenience, not a requirement.)

**Action:**
- `src/forge/feedback/consumer.py` — `_flush_aged_out_submissions` helper + `reconcile_all_pending` call site + module-level `_AGED_OUT_SENTINEL_RUN_ID`.
- `tests/unit/test_feedback/test_consumer.py` — 4 new D052 unit tests.
- `tests/invariants/test_phase5_invariants.py` — 2 new D052 invariants.
- `IMPLEMENTATION_DECISIONS.md` D052 (this entry).
- Service restart required to pick up the helper.


## D053 — 2026-05-18 — Counterfactual phase labeling (P1-1 honesty fix)

**Spec section:** T2.3 (counterfactual evaluation framework, D044); P1-1 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** T2.3's `evaluate_counterfactual` in `forge.feedback.proposer` is a phase-1 binary safety floor — `del proposal; if recent_promoted_count > 0: rejection_rate = 1.0 else 0.0`. The function's docstring is honest about that; the call site in `cli/main.py` was not. Every proposal got `counterfactual_rejection_rate=1.0` stamped into `evidence_json` whenever the prior batch had any promotion, so operators reading OPEN_PROPOSALS.md saw "1.0 rejection rate" and interpreted it as "every promoted strategy would be rejected" — a real per-strategy measurement that the system does not yet make.

The follow-up brief offered two options: (a) label the phase explicitly so the operator can filter the noise, or (b) implement real per-strategy re-validation (draft Enhancement 8 phase 2). Option (a) is the immediate honesty fix; (b) is deferred because `submissions.config_json` history queries + a pre-filter-battery harness against historical configs are substantial scope.

**Decision:** Make the data self-describing at its source. Add a `phase: str` field to `CounterfactualResult` (default `PHASE_1_BINARY = "1_binary_safety_floor"`). `evaluate_counterfactual` returns `phase=PHASE_1_BINARY`. Expose a module-level `COUNTERFACTUAL_PHASE_1_NOTE` constant with the human-readable disclaimer ("phase-1 binary safety floor: rejection_rate is a worst-case assumption..."). The call site (and any downstream caller) stamps both `counterfactual_phase` and `counterfactual_note` alongside the existing numeric fields, so the operator reading raw `evidence_json` sees the disclaimer without having to read source. When phase 2 lands, only `evaluate_counterfactual` changes its return body to `PHASE_2_PER_STRATEGY`; consumers' code stays identical, and the operator can tell post-fact whether a given proposal was annotated under the binary floor or the real measurement.

**Hard rules check:**
- Hard rule #4 (no auto-loosening): UNCHANGED. `should_auto_apply_proposal` still has zero production callers — even with a labeled phase, no path auto-applies a proposer-emitted proposal. The fix is operator-facing honesty, not safety.
- Hard rule #6: no determinism impact.
- Hard rule #8: no clock/seed touch.

**Alternatives considered:**
- **Don't stamp the rejection_rate field at all under phase-1.** Rejected — downstream tooling and the dashboard reasonably expect a consistent field set; quietly omitting it under a phase is its own surprise.
- **Rename `counterfactual_rejection_rate` to `counterfactual_safety_signal`.** Considered. Rejected — broader API rename, every consumer needs updating, doesn't help operators who already have the old name in muscle memory. Phase label + note achieves the honesty goal with a smaller blast radius.
- **Skip the constant and just inline the disclaimer string at the call site.** Rejected — drifts. The constant + module-level export keeps the disclaimer in one place; phase 2's flip flows naturally.

**Verification:**
- 2 new unit tests in `tests/unit/test_feedback/test_proposer.py`:
  - `test_d053_counterfactual_result_carries_phase_field` — dataclass default.
  - `test_d053_evaluate_counterfactual_marks_phase_1` — function return value.
- The D053 invariant test was rewritten in D054 (see below) to point at the shared enrichment helper.
- Ruff + mypy strict clean across the modified files.

**Action:**
- `src/forge/feedback/proposer.py` — `PHASE_1_BINARY`, `PHASE_2_PER_STRATEGY`, `COUNTERFACTUAL_PHASE_1_NOTE` constants; `CounterfactualResult.phase`; updated docstring.
- `src/forge/cli/main.py::_consume_feedback_after_submit` — stamps `counterfactual_phase` and `counterfactual_note` (later moved into the shared helper by D054).
- `tests/unit/test_feedback/test_proposer.py` — 2 new D053 unit tests.
- `IMPLEMENTATION_DECISIONS.md` D053 (this entry).


## D054 — 2026-05-18 — Shared T2.3 + T2.5 enrichment helper (P1-2)

**Spec section:** T2.3 (counterfactual), T2.5 (trade-concentration analyzer), D049 wiring; P1-2 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** D049 wired T2.3 + T2.5 into the autonomous loop's `_consume_feedback_after_submit` in `cli/main.py`. The manual `forge feedback` command (`cli/feedback_cmd.py:125-126`) was not updated — it iterated proposals and called `append_proposal` directly, silently bypassing both the counterfactual annotation AND the concentration analyzer. Two call sites consuming the same upstream state (Crucible's gated runs) produced different `OPEN_PROPOSALS.md` content. An operator running a manual diagnostic batch via `forge feedback --batch-id X` saw fewer proposals + missing evidence_json fields than the loop's autonomous output for the same batch.

**Decision:** Factor the enrichment block into `forge.feedback.proposal_writer.enrich_and_append_proposals(proposals, *, feedback, open_proposals_path, db, at)`. The helper applies T2.3 enrichment (counterfactual + D053 phase label + note) to each proposer-emitted proposal, then runs `analyze_promotion_concentration` over `feedback.outcomes` and emits a tighten-grammar proposal per flagged run. Both `_consume_feedback_after_submit` and `cmd_feedback` import and call this helper. Structurally they CAN'T diverge — there's no inline enrichment in either call site.

**Hard rules check:**
- Hard rule #2: imports stay within `forge.feedback.*` and `crucible_contracts`. No Crucible-internal imports introduced.
- Hard rule #4: no loosening path added; the helper writes via `append_proposal`, which already enforces the dedup + grammar_proposals discipline.
- Hard rule #6: no determinism impact.

**Alternatives considered:**
- **Inline duplication.** Keeps each call site self-contained but is exactly the divergence trap we just fell into. Rejected.
- **A new `forge.feedback.enrichment` module.** Considered. Rejected because `proposal_writer.py` is already the "write the proposal somewhere" module and `enrich_and_append_proposals` is just the enriched analog of `append_proposal`. Splitting it across modules adds an import without adding clarity.

**Verification:**
- 1 new unit test in `tests/unit/test_cli/test_feedback_cmd.py`:
  - `test_d054_feedback_cmd_stamps_counterfactual_phase_into_proposals` — manual `forge feedback` invocation produces proposals with the full enrichment fields in OPEN_PROPOSALS.md.
- 2 new invariant tests in `tests/invariants/test_phase5_invariants.py` (D053 + D054 family):
  - `test_enrich_and_append_proposals_writes_counterfactual_phase` — the helper still stamps the phase + note.
  - `test_forge_run_and_forge_feedback_share_enrichment_helper` — both call sites must call `enrich_and_append_proposals`.
- Full Forge suite: 1064 passing post-P1-2. Ruff + mypy strict clean.

**Side benefit:** the `_consume_feedback_after_submit` PLR0915 noqa is now obsolete — extracting the inline block dropped the function back under the statement-count limit.

**Action:**
- `src/forge/feedback/proposal_writer.py` — `enrich_and_append_proposals` + top-level imports of `proposer.COUNTERFACTUAL_PHASE_1_NOTE`, `proposer.evaluate_counterfactual`, `trade_concentration.analyze_promotion_concentration`, `types.GrammarProposal`.
- `src/forge/cli/main.py::_consume_feedback_after_submit` — replace the inline enrichment block with a call to the helper.
- `src/forge/cli/feedback_cmd.py::cmd_feedback` — switch from direct `append_proposal` loop to the helper.
- `tests/unit/test_cli/test_feedback_cmd.py` — 1 new D054 unit test.
- `tests/invariants/test_phase5_invariants.py` — 2 D053+D054 invariants (the earlier D053 invariant was redirected to point at the helper).
- `IMPLEMENTATION_DECISIONS.md` D054 (this entry).


## D055 — 2026-05-18 — Re-queue script grammar_version filter (P1-3)

**Spec section:** P1-3 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** `scripts/requeue_high_value_configs.py` selectively re-queues historically-tested configs from `inbox/processed/` back into Crucible's inbox. Pre-D055 the script did not check the originating batch's grammar version — it shipped v1-era configs into a v2-active Crucible. v1-only signals (e.g., the pre-D039 R3 indicator set, or pre-D033 SPY-locked configs) silently reject on Crucible's side: the config validates against StrategyConfig's pydantic shape (still parses) but fails Crucible's signal-content validation. The rejection produces no gated_runs entry, so Forge's reconciler sees nothing, and the re-queued configs effectively vanish.

A dry-run against the operator's current `~/forge_data/forge.db` showed **3,010 configs** would have been re-queued under v1 grammar (every batch_summary row is `grammar_version='v1'`). With v2 active, every one of those re-queues would have been wasted compute.

**Decision:** Add `filter_to_current_grammar_version(forge_db, candidate_hashes, current_grammar_version) -> (matching, skipped_by_version)`. The filter joins `submissions.forge_batch_id` → `batch_summaries.forge_batch_id` → `batch_summaries.grammar_version`, partitions the candidate set, and returns:
- `matching`: hashes whose originating batch matches the active grammar.
- `skipped_by_version`: counts by version (plus `(unknown)` bucket for hashes not present in `submissions`).

The script's `main()` invokes the filter by default. The CLI gains two flags:
- `--grammar-yaml PATH` (default: `config/grammar.yaml`) — used to derive `current_grammar_version` via a stdlib-only `_read_grammar_version` regex parser (no Forge module dep — keeps the script's stdlib-only cold-start path intact).
- `--skip-grammar-filter` (default: false) — operator override for the rare case where re-queueing stale-version configs is desired (e.g., archival testing or a grammar-version downgrade).

The summary output prints `grammar_filter: active (current=vN)` and a per-version skip table so the operator immediately sees the rejection picture.

**Hard rules check:**
- Hard rule #2 (no Crucible internals): unchanged. The script only reads Forge's DB.
- Hard rule #10 (grammar archive + audit): unchanged. The filter consumes the active grammar; doesn't touch the archive.

**Alternatives considered:**
- **(b) Re-write each config's grammar_version to current after validating signal compat.** Rejected — verifying signal compatibility requires running the full grammar validator against each config, which is what Crucible's inbox-watcher does. Duplicating that logic in the re-queue script is bad layering and risks divergence. The skip path is the conservative correct move.
- **(c) Log per-version counts but don't filter.** Rejected as too weak — the script still ships doomed configs, just with a friendlier console summary.
- **Drop the entire script.** Considered (it's a one-off recovery tool). Rejected because the operator may want it again after future grammar bumps; making it correct is more durable than removing it.

**Verification:**
- 3 new unit tests in `tests/integration/test_requeue_high_value_configs.py` (loaded via `importlib` since `scripts/` isn't on `pythonpath`):
  - `test_d055_filter_keeps_only_current_grammar_version` — happy path: v1-era skipped, v2-era passes.
  - `test_d055_filter_handles_unknown_hashes` — hashes not in submissions get the `(unknown)` bucket.
  - `test_d055_filter_no_skips_when_all_match` — identity case.
- End-to-end dry-run against the operator's real Forge DB: shows `grammar_filter: active (current=v2)` and `skipped by grammar_version: v1: 3010`. Total would-copy = 0 (no v2 batches exist yet — the active grammar is v2 but only v1 batches are recorded).
- Ruff + mypy strict clean.

**Action:**
- `scripts/requeue_high_value_configs.py` — `filter_to_current_grammar_version` helper, `_read_grammar_version` parser, CLI flags `--grammar-yaml` and `--skip-grammar-filter`, summary output extended.
- `tests/integration/test_requeue_high_value_configs.py` — 3 new D055 unit tests.
- `IMPLEMENTATION_DECISIONS.md` D055 (this entry).


## D056 — 2026-05-18 — Hard rule #3 direct invariant via contracts risk caps (P3-1)

**Spec section:** CLAUDE.md hard rule #3 ("never propose grammar relaxations that lower Crucible's promotion gate"); `crucible_contracts.ABSOLUTE_MAX_PER_TRADE_RISK_PCT` (0.02), `ABSOLUTE_MAX_CONCURRENT_RISK_PCT` (0.15); P3-1 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** Hard rule #3 had no dedicated `tests/invariants/` check. The protection leaned indirectly on rule #4's `apply_loosening` ban: no code path can auto-raise a calibration threshold, so by transitivity no auto path can lower the gate. That argument covers automated changes but not manual operator edits to `config/grammar.yaml`. A future operator (or a future LLM session) could in principle bump P4's `sizer.per_trade_risk_pct.max` above 0.02 — contracts validation would catch it on submission, but the rule-#3 spirit asks for the floor at the grammar layer too. Pre-D056 we had no structural check that the grammar's static bounds respect the contracts ceiling.

**Decision:** Two complementary invariants in `tests/invariants/test_phase5_invariants.py`:

1. `test_grammar_p4_per_trade_risk_max_within_contracts_ceiling` — parse `config/grammar.yaml`, find rule P4, assert `predicate.max ≤ ABSOLUTE_MAX_PER_TRADE_RISK_PCT`. Catches a stale grammar.yaml bound regardless of code paths.

2. `test_enumerated_configs_respect_absolute_risk_caps` — load active grammar + registry, enumerate 50 configs, assert every `cfg.sizer.per_trade_risk_pct ≤ 0.02` and `cfg.sizer.max_concurrent_risk_pct ≤ 0.15`. Roundtrip property: even if the grammar or sampler changed shape, the output respects the gates.

**Hard rules check:**
- Hard rule #3: this entry IS the structural piece rule #3 has been depending on implicitly.
- Hard rule #6: enumeration uses a fixed seed (0xD056) so the property check is deterministic across runs.

**Alternatives considered:**
- **Single integration test that runs every reasonable seed**. Rejected — would slow the invariants suite and the property holds for any seed; 50 configs at one seed exercises the sampler's full path.
- **Hypothesis-based property test (`@given`).** Considered. Rejected for now — the existing test suite doesn't lean on Hypothesis; adding it for one invariant raises maintenance cost without proportional confidence gain. Revisit if the grammar grows enough range-style rules that fixed-seed sampling becomes thin.

**Verification:** 2 new invariants pass under the current v2 grammar (P4.max=0.02, sampler emits per_trade_risk_pct ∈ [0.005, 0.02], max_concurrent_risk_pct defaults to 0.15).

**Action:**
- `tests/invariants/test_phase5_invariants.py` — 2 new D056 invariants.
- `IMPLEMENTATION_DECISIONS.md` D056 (this entry).


## D057 — 2026-05-18 — Relocate hard rule #1 count invariant to invariants/ (P3-2)

**Spec section:** CLAUDE.md hard rule #1 (21 v1 grammar rules); D001; P3-2 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** `tests/integration/test_v1_grammar.py::test_v1_grammar_rule_count_per_category` enforced the §3.5 / D001 invariant of 5/4/4/3/3/2=21 rules per category. Wrong directory: invariants live in `tests/invariants/`, integration tests are for end-to-end workflows. A reviewer auditing rule-#1 protection by reading `tests/invariants/test_phase1_invariants.py` would have concluded the invariant didn't exist.

**Decision:** Move the test to `tests/invariants/test_phase1_invariants.py` (rule #1 is grammar-scoped → phase 1). Replace the original with a NOTE-comment pointing at the new location, so anyone grep-ing for `test_v1_grammar_rule_count_per_category` lands on a breadcrumb rather than a dead reference. Loading the grammar fresh in the relocated test (rather than depending on the integration suite's `grammar` fixture) keeps the invariant self-contained.

**Hard rules check:**
- Hard rule #1: same test, stronger location.
- No spec change.

**Alternatives considered:**
- **Keep the test in both places (integration + invariants).** Rejected — duplicates the assertion; one failure becomes two and they can drift.
- **Move other `test_v1_grammar_*` tests too.** Considered. The other tests in that file genuinely are end-to-end integration (load+validate+cross-reference docs); they belong where they are. Only the count-per-category test was misclassified.

**Verification:**
- `tests/invariants/test_phase1_invariants.py::test_v1_grammar_rule_count_per_category` passes (counts and total agree with §3.5).
- `tests/integration/test_v1_grammar.py` still passes after the relocation; its line count dropped by 15 lines.

**Action:**
- `tests/invariants/test_phase1_invariants.py` — relocated test.
- `tests/integration/test_v1_grammar.py` — NOTE-comment breadcrumb.
- `IMPLEMENTATION_DECISIONS.md` D057 (this entry).


## D058 — 2026-05-18 — D051 self-heal idempotency under writer race (P3-3)

**Spec section:** D051 (grammar_versions audit-row self-healing); P3-3 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** D051's `ensure_grammar_version_recorded` uses a SELECT-then-INSERT pattern: check whether a row for `grammar.grammar_version` exists, and INSERT if not. In a single-process world that's idempotent. The brief flagged a hypothetical race: the autonomous loop's `_ensure_grammar_version_recorded_silently` and an operator-driven `cmd_apply_proposal` / `cmd_revert` could in principle both observe an empty `grammar_versions` table at the same instant, then both INSERT — producing two rows for the same version. The `version VARCHAR(20) PRIMARY KEY` constraint catches the loser's INSERT, but no test pinned the contract that exactly one row lands either way.

**Decision:** Add `test_d058_ensure_grammar_version_no_duplicate_under_concurrent_writers` to `tests/unit/test_feedback/test_auto_tune.py`. The test uses `threading.Barrier(2)` to release two worker threads simultaneously; each opens its own DuckDB connection on the same file and calls `ensure_grammar_version_recorded`. Asserts:

1. **Outcome correctness:** exactly one `grammar_versions` row exists for the active version.
2. **At-least-one writer succeeded:** one thread reports `wrote=True` (or in the lucky case where the SELECT-then-INSERT serializes, both succeed at the contract level — one writes, one returns `False`).
3. **Loser path observed:** either a returns-False worker (later writer sees the row exists) OR a `ConstraintException` (race on INSERT) — the test accepts both because both preserve the invariant.

The test catches a future refactor that switches the idempotency mechanism (e.g., to INSERT-OR-IGNORE without the SELECT preflight) where the contract could silently break.

**Hard rules check:**
- Hard rule #10 (grammar archive + audit): the test pins the audit-row uniqueness directly, strengthening rule #10's enforcement in concurrent-writer conditions.

**Alternatives considered:**
- **`multiprocessing`-based race test.** Considered for closer prod fidelity (forge.service and CLI are separate processes). Rejected because `threading` with separate DuckDB connections on the same file exercises the OS-level file-lock the same way; multiprocessing adds fork/spawn overhead without changing what's being tested.
- **Wrap the SELECT-then-INSERT in an explicit `BEGIN/COMMIT`.** Considered. Rejected as gold-plating — DuckDB statement auto-commit + PRIMARY KEY enforces the invariant; an explicit transaction doesn't add safety.

**Verification:**
- New unit test passes deterministically (5 consecutive runs).
- Existing 2 D051 idempotency tests still green.
- Ruff + mypy strict clean.

**Action:**
- `tests/unit/test_feedback/test_auto_tune.py` — 1 new D058 race test.
- `IMPLEMENTATION_DECISIONS.md` D058 (this entry).


## D059 — 2026-05-18 — Breadcrumb annotations for deleted Crucible prompts (P3-4)

**Spec section:** P3-4 from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** Commit `e85f0d4` deleted 7 Crucible coordination prompts after the corresponding work shipped:
- `CRUCIBLE_FEATURE_CACHE_AGENT_PROMPT.md`
- `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`
- `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md`
- `CRUCIBLE_EV_DEADLOCK_AGENT_PROMPT.md`
- `CRUCIBLE_EMPTY_THRESHOLD_AGENT_PROMPT.md`
- `CRUCIBLE_DB_CHECKPOINT_ON_BATCH_AGENT_PROMPT.md`
- `CRUCIBLE_TRADE_CONCENTRATION_METRIC_AGENT_PROMPT.md`

`STATUS.md`, `IMPLEMENTATION_DECISIONS.md`, and `OPEN_QUESTIONS.md` still carried 10 bare textual references to these (e.g., D028's entry cites `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md` as "see operator-recommended specs"). A new contributor following one of those references would land on a dead path.

**Decision:** Add a single breadcrumb at the top of each of the three state docs pointing at `e85f0d4` and listing the deleted files. Per-reference inline edits were considered but the count (10) and pattern (uniform — "see prompt X" inside historical narrative) made the global note cleaner: one read at the top of any document tells the reader what happened to every `CRUCIBLE_*_AGENT_PROMPT.md` reference in that document.

The prompt files remain recoverable via `git show e85f0d4^:<filename>` for any reader who wants the original content.

**Hard rules check:**
- None impacted. Pure documentation hygiene.

**Alternatives considered:**
- **Per-reference `(deleted in e85f0d4)` annotations.** Lower-noise per-paragraph but higher-noise globally; 10 surgical edits. Rejected as harder to maintain (future doc edits could orphan the breadcrumb).
- **Move historical content to a `docs/deleted-prompt-references-2026-05-18.md` appendix.** Too aggressive — the references are integral to the surrounding narrative, not stand-alone content.
- **Restore the prompts.** Rejected — they document workstreams that already shipped; restoring them adds noise without value.

**Verification:**
- Breadcrumb visible at top of each of the 3 files.
- `grep -n "CRUCIBLE_*_AGENT_PROMPT" ...` still finds the references; readers landing there can scroll up to the breadcrumb or `git show` the original.

**Action:**
- `STATUS.md` — D059 breadcrumb at top.
- `IMPLEMENTATION_DECISIONS.md` — D059 breadcrumb at top + this entry.
- `OPEN_QUESTIONS.md` — D059 breadcrumb at top.


## D060 — 2026-05-18 — Ranker contract docstring + NoveltyFilter dedup warning (P2-4 + P2-5)

**Spec section:** §6.2 ranker (P2-4); T2.7 / D049 structural-fingerprint dedup (P2-5); both from FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md.

**Context:** Two small hardening items batched into one decision log entry because both touch the same audit-trail surface (operator-visible behavior contracts that were implicit pre-D060).

**P2-4 — Ranker contract:** `Ranker.score` in `src/forge/ranking/scorer.py` lists 4 required filter keys; missing any raises `ValueError`. Today the production caller `rank_batch` iterates only `passed=True` reports so the precondition holds, but it isn't documented. A future caller that passes a short-circuited report would hit `ValueError` with no clear "you violated the contract" signal.

**P2-5 — NoveltyFilter dedup:** `_run_battery_for_seed(forge_db_path=None)` falls through to `prior_structural_fingerprints=frozenset()`, which silently disables T2.7 structural-fingerprint dedup. The demo `forge prefilter` CLI legitimately invokes this without a DB; the autonomous loop should never. Pre-D060 there was no signal distinguishing the two paths, so a future caller could regress T2.7 without noticing.

**Decision:**
- P2-4: add a "Precondition" paragraph in `Ranker.score`'s docstring pinning the `report.passed == True` requirement. Names the production caller (`rank_batch`) so future contributors know where to look.
- P2-5: add a module-level `_NOVELTY_DEDUP_WARNED` flag and a `_warn_once_novelty_dedup_disabled` helper that writes to stderr the first time `_run_battery_for_seed` is called without a DB path. Idempotent (warn-once); never raises; pure observability.

**Hard rules check:**
- None impacted.
- Hard rule #6 (determinism): P2-5's warning is stderr-only and does not affect enumeration output.

**Alternatives considered:**
- **P2-4: change `_REQUIRED_FILTER_KEYS` to a method-time class attribute.** Considered. Rejected — the docstring is the right place for a behavioral contract; class structure is the right place for what's enforced, not why.
- **P2-5: raise `ValueError` on no-DB path.** Rejected — the demo `forge prefilter` path is intentional. A warning is the right severity: surfaces the degraded state without breaking valid demo use.
- **P2-5: use `warnings.warn(...)`.** Considered. Rejected because `warnings.warn` has a default filter discipline that can suppress repeated warnings differently across environments; stderr write-once with a module flag is predictable.

**Verification:**
- 1 new unit test in `tests/unit/test_cli/test_run_loop.py`: `test_d060_novelty_dedup_disabled_warning_fires_when_db_is_none` — first call writes to stderr, second call is silent (warn-once), flag reset on exit so the test is order-independent.
- Ruff + mypy strict clean.

**Action:**
- `src/forge/ranking/scorer.py` — Precondition docstring on `Ranker.score`.
- `src/forge/cli/main.py` — `_NOVELTY_DEDUP_WARNED` flag, `_warn_once_novelty_dedup_disabled` helper, call site at `_run_battery_for_seed` top.
- `tests/unit/test_cli/test_run_loop.py` — 1 new D060 test.
- `IMPLEMENTATION_DECISIONS.md` D060 (this entry).


## D061 — 2026-05-18 — Pin DuckDB session timezone to UTC at connection open

**Spec section:** Hard rule #8 (blessed clock); §13.4 (submission idempotency, indirectly).

**Context:** D052's aged-out flush (`_flush_aged_out_submissions` in `src/forge/feedback/consumer.py`) silently no-op'd in production. Forge.service iterations 54→167 (~110 min) all logged `blocked: oldest in-flight batch 196dc597 is 0.0% gated (0/110); waiting for >=50%` while 1,182 stuck `submitted` rows accumulated. Investigation:

1. `forge.core.clock.utc_now()` (hard rule #8) returns aware-UTC datetimes. The flush builds `watermark = min(decided_ats)` with `tzinfo=UTC` and binds it to `WHERE submitted_at < ?` against a naive `TIMESTAMP submitted_at` column.
2. DuckDB's default session TZ on this host is `America/Los_Angeles` (PDT = UTC-7 in May). On aware-vs-naive comparison, DuckDB coerces the naive column via the session TZ → every `submitted_at` shifts +7h forward (08:26 naive → 15:26 UTC).
3. Watermark is 15:10:57 UTC. Production rows shift past the watermark and the WHERE clause matches 0 rows. The flush never executed since deploy.

Existing D052 unit test (`test_reconcile_all_pending_flushes_predates_export_window`) passed because its `submitted_at` (2026-05-10) and watermark (2026-05-13 14:00) were 3+ days apart — the 7-hour shift didn't flip the inequality. Production datetimes cluster within hours, so the shift does flip it.

**Decision:**
- **Primary fix:** Pin DuckDB session TZ to UTC inside `open_db` (`src/forge/persistence/db.py`) via `conn.execute("SET TimeZone='UTC'")`. Encodes the project's actual contract — all timestamps flow through `utc_now()` (hard rule #8), so on-disk naive `TIMESTAMP` values are implicit-UTC wall clocks; the session TZ should match.
- **Defense-in-depth:** Convert the watermark in `_flush_aged_out_submissions` to naive UTC (`min(decided_ats).astimezone(UTC).replace(tzinfo=None)`) to match the naive column convention. Survives any future caller that opens a connection outside `db_connection`.
- **Structural guard:** New invariant test `test_db_connection_pins_session_timezone_to_utc` in `tests/invariants/test_phase0_invariants.py` asserts every `db_connection` opens with TZ=UTC. Prevents regression.

**Hard rules check:**
- Hard rule #8 (blessed clock): reinforced. This is the read-side complement to the write-side `utc_now()` discipline.
- Hard rule #6 (deterministic enumeration): unaffected — session TZ does not influence enumeration output.
- Hard rule #9 (submission idempotency): unaffected — config_hash uniqueness is the structural guard; D061 only fixes the read-time comparison that the D052 aged-out flush depends on.

**Alternatives considered:**
- **Migrate all timestamp columns to TIMESTAMPTZ.** Schema-level proper fix. Rejected for now — touches 8 columns across 6 tables, requires data migration on the production DB (~4,000 rows), every reader, every test fixture. DuckDB strips tzinfo cleanly on write to TIMESTAMP, so stored values are already correct UTC; the bug is exclusively in coercion-on-read. Pinning session TZ is the surgical match for the actual defect. Migration remains available as a future option if the implicit-UTC convention proves fragile.
- **Strip tzinfo from watermark only (no session-TZ pin).** Fixes D052 in isolation but leaves the latent bug for every other aware-vs-naive comparison in the codebase (current and future). Rejected — same class of bug, different call site.
- **Set TZ via env var (`DUCKDB_SETTINGS`).** Not a DuckDB feature; the `SET TimeZone` statement is the canonical mechanism.
- **One-shot SQL flush of the 1,015 aged-out rows in production, defer the code fix.** Unblocks tonight but the bug persists; the same backlog regrows. Rejected once the proper fix proved trivial.

**Verification:**
- Dry-run against `/home/aj/forge_data/forge.db` (read-only): default session TZ matches 0 stuck rows; `SET TimeZone='UTC'` matches 963 of 1,182; naive watermark matches the same 963 — confirms next iteration after restart will flush ~963 rows and unblock the loop. The remaining 219 are inside the export window and reconcile via the normal join.
- All 28 tests in `tests/invariants/test_phase0_invariants.py` + `tests/unit/test_feedback/test_consumer.py` pass.
- Ruff + mypy strict clean on changed scope (`src/forge/persistence/db.py`, `src/forge/feedback/consumer.py`).

**Action:**
- `src/forge/persistence/db.py` — `SET TimeZone='UTC'` at connection open in `open_db`.
- `src/forge/feedback/consumer.py` — naive watermark in `_flush_aged_out_submissions`.
- `tests/invariants/test_phase0_invariants.py` — new `test_db_connection_pins_session_timezone_to_utc` invariant.
- Operator restart of `forge.service` required to pick up the change (no schema migration; existing data unaffected).


## D062 — 2026-05-18 — Wire `dealer_positioning` family into C2 hypothesis allowlist + per-batch prefilter rejection counter

**Spec section:** §3.5 C2 (directional family ↔ hypothesis pairing); §11 (file layout / observability).

**Context, part 1 — dealer indicator wiring:** Crucible commit `5af63ad` (2026-05-18 20:17 PDT) added 6 dealer indicators (`gex`, `vex`, `cex`, `call_wall_distance_pct`, `put_wall_distance_pct`, `gamma_flip_distance_pct`) tagged with `family="dealer_positioning"` via `Crucible/src/optbt/data/exports.py:169` (module-path-to-family map). Forge's `_C2_HYPOTHESIS_FAMILIES` dispatch table in `src/forge/grammar/custom_predicates.py:91` did NOT include `dealer_positioning` under any hypothesis. Effect pre-D062: when Crucible re-exports the registry, dealer indicators are usable as regime-gate signals (no C2 constraint) but rejected as the *directional* thesis for every hypothesis — silently shrinking the strategy class available for enumeration.

**Context, part 2 — observability gap:** Iteration 31 (the first complete iteration post-D061) logged `enumerated=5000 passed_prefilter=7` — a 0.14% survival rate. `pre_filter_logs` only records *survivors* (7 rows × 9 filters × passed=True only). `batch_summaries.common_failures` is reserved for Crucible-side gate failures (populated by `feedback/consumer.py:_common_failures` post-feedback). No surface in the DB recorded *which* pre-filter killed each candidate, so the operator could not diagnose the 99.86% attrition without re-running the battery.

**Decision:**
- **C2 mapping (Option A, operator-chosen):** Add `dealer_positioning` to both `volatility_event` (alongside `iv_structure`, `flow`) and `mean_reversion` (alongside the native `mean_reversion` family). Rationale: GEX/VEX/CEX/gamma-flip drive vol-regime intent; call/put walls and the gamma-flip line are documented mean-reversion magnets. Splitting across both buckets captures both intents without introducing a new hypothesis. A future `dealer_flow` hypothesis remains available if telemetry shows the buckets compete.
- **Rejection counter:** New `prefilter_rejections JSON` column on `batch_summaries` (idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Populated by a new `record_prefilter_rejections` helper in `forge.submission.submitter` after each successful `submit_batch`. For every rejected `PreFilterReport`, increments the counter at the first-failing filter (matching the `forge prefilter --summary` semantics). Counter is also echoed to the journal as `prefilter_rejections: filter=N, ...` so operators can grep without DB access.
- **Diagnostic flag:** New `--synthetic-cache` flag on `forge prefilter` to force `SyntheticFeatureCache`. Without this, high-`--max` diagnostic runs were unusable when Crucible's feature_cache was slow (one round-trip per config × 5000 configs). Documented in the help text that cache-dependent filters (`permutation_test`, `predicted_activations`) are over-represented under synthetic and the cache-independent filters (`structural_redundancy`, `signal_density`, etc.) are the load-bearing diagnostic.

**Hard rules check:**
- Hard rule #1 (21 v1 grammar rules operator-owned): grammar.yaml unchanged; only the Python dispatch table extended. The rule's *implementation* widens its allowlist; the rule itself (`directional_family_matches_hypothesis`) is untouched. Operator explicitly requested this in conversation.
- Hard rule #2 (no Crucible internals): unaffected — we only consume `family="dealer_positioning"` as it appears in the contracts-tagged registry snapshot.
- Hard rule #4 (auto-tightening only): this is operator-approved human loosening, not auto-loosening. The proposer auto-tune path is not involved.
- Hard rule #10 (grammar.yaml version bump): grammar.yaml content unchanged, so no bump.

**Alternatives considered:**
- **New `dealer_flow` hypothesis bucket.** Cleanest separation but larger surface (grammar.yaml + sampler weights + analyzer thresholds + auto-tune state). Rejected for now; operator chose A and the buckets can be split later if signal warrants.
- **Reuse `common_failures` for prefilter rejections with namespaced keys (`prefilter:structural_redundancy`).** Considered. Rejected because the column is overwritten in `feedback/consumer.py` when Crucible feedback arrives — Forge-side rejections would be clobbered. Separate column is the simpler correctness story.
- **Log prefilter rejection breakdown to a sidecar JSON file under `~/forge_data/`.** Considered. Rejected — the DB is the canonical operator-visible state; a sidecar file would diverge from `batch_summaries` and require a second query surface.
- **Add per-rejected-candidate rows to `pre_filter_logs`.** Considered. Rejected — would multiply storage by ~5000× per batch with mostly-redundant detail; an aggregate counter is the right granularity for the "why are we rejecting so much" question.

**Verification:**
- 3 new C2 tests in `tests/unit/test_grammar/test_custom_predicates.py`: dealer_positioning accepted under `volatility_event`, dealer_positioning accepted under `mean_reversion`, dealer_positioning rejected under `trend_continuation`.
- 2 new submitter tests in `tests/unit/test_submission/test_submitter.py`: rejection counter writes JSON to `batch_summaries.prefilter_rejections`; no-op when all reports pass.
- Test fixture `minimal_registry_snapshot()` extended with 2 dealer_positioning indicators (`gex`, `call_wall_distance_pct`) so existing tests can reference them.
- `forge prefilter --seed 1350668565 --max 5000 --summary --synthetic-cache` reproduces the production-seed enumeration for diagnostic purposes (the production-side seed that produced `passed_prefilter=7`).

**Action:**
- `src/forge/grammar/custom_predicates.py` — `_C2_HYPOTHESIS_FAMILIES` extended for `volatility_event` and `mean_reversion`.
- `src/forge/persistence/schemas.py` — `ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS prefilter_rejections JSON`.
- `src/forge/submission/submitter.py` — `record_prefilter_rejections` helper.
- `src/forge/cli/main.py` — wire `record_prefilter_rejections` into `_run_one_iteration` after `submit_batch`; add `--synthetic-cache` flag to `cmd_prefilter`.
- `tests/fixtures/strategy_configs.py` — 2 dealer_positioning indicators added to fixture registry.
- `tests/unit/test_grammar/test_custom_predicates.py` — 3 new D062 C2 tests.
- `tests/unit/test_submission/test_submitter.py` — 2 new D062 rejection counter tests.
- `IMPLEMENTATION_DECISIONS.md` D062 (this entry).


## D063 — 2026-05-18 — Surface prior-filled hypotheses in the `hypothesis_weights:` journal line

**Spec section:** §6.2 ranker / sampler observability; hard rule #6 (deterministic enumeration nuance).

**Context:** Production journal at iteration 31/32 logged:
```
hypothesis_weights: regime_arbitrage=0.004, relative_value=0.003, tail_hedge=0.002, volatility_event=0.050
```
`mean_reversion` and `trend_continuation` were absent. Operator's read: "the adaptive weighter has pruned them." Actual behavior: `compute_hypothesis_weights` only returns dict entries for hypotheses with ≥1 row in the `submissions ⋈ gated_runs` join; the sampler then falls back to `prior_mean()` (Beta(1,10).mean = 0.0909) for missing keys via `hypothesis_weights.get(h, _HYPOTHESIS_WEIGHT_PRIOR_MEAN)` in `sampler.py:201`. Plus D037's stratified floor (`_PRODUCTION_MIN_HYPOTHESIS_FRACTION ≥ 2%`) hard-guarantees nothing is pruned.

So the **sampler was fine** — `mean_reversion` and `trend_continuation` actually got ~38% probability each (prior 0.0909 normalized against the smaller observed weights 0.002–0.050). The **journal line was lying by omission**, making it look like a sampler bug when it wasn't. Live data confirmed:

| Hypothesis | submitted | gated |
|---|---:|---:|
| mean_reversion | 1 | 1 |
| trend_continuation | 0 | 0 |
| regime_arbitrage | 865 | 835 |
| relative_value | 1,154 | 1,134 |
| tail_hedge | 1,851 | 1,824 |
| volatility_event | 156 | 9 |

Only one mean_reversion submission ever, zero trend_continuation — but the bottleneck is downstream of the sampler (pre-filter battery rejecting them at ~100%), not the weight selector. D062's `prefilter_rejections` counter will surface which filter does the killing on the next production batch.

**Decision:** Replace the dict-dump log line with `_format_hypothesis_weights_line(weights)`, which renders all six canonical hypotheses in `_HYPOTHESES` order, fills `prior_mean()` for unobserved entries, and marks them with `*`. Suffix `(*=prior, no data)` makes the convention self-documenting.

**Example new line:**
```
hypothesis_weights: trend_continuation=0.091*, mean_reversion=0.091*, regime_arbitrage=0.004, relative_value=0.003, volatility_event=0.050, tail_hedge=0.002 (*=prior, no data)
```

**Hard rules check:**
- Hard rule #6 (deterministic enumeration): unaffected — this is an observability change to the journal line; sampler behavior is unchanged.
- No other hard rules touched.

**Alternatives considered:**
- **Log only the dict, add a separate "missing:" line.** Two-line variant. Rejected — single line is greppable; one is more diff-friendly than two.
- **Log raw weights without `*` marker.** Rejected — operator would still need to know `0.091` is the prior magic number to disambiguate; the marker is one character and self-explanatory.
- **Fix `compute_hypothesis_weights` to always return all six keys with prior fallback.** Considered. Rejected — the function's contract is "posterior dict; empty means uniform"; padding it with priors would invert the "empty=uniform" semantics. The presentation layer (cli/main.py) is the right seam for this. The sampler keeps its `dict.get(h, prior_mean)` fallback as the source of truth for actual weights.

**Verification:**
- 2 new tests in `tests/unit/test_cli/test_run_loop.py`: prior-filled marker fires for absent keys; canonical hypothesis order is preserved.
- Ruff + mypy strict clean on `src/forge/cli/main.py`.

**Action:**
- `src/forge/cli/main.py` — new `_format_hypothesis_weights_line(weights)` helper; `_run_one_iteration` calls it instead of the inline `", ".join(...)`. Inline removed (was 2 statements, helper is 1 call — also resolves a PLR0915 nudge on `_run_one_iteration`).
- `tests/unit/test_cli/test_run_loop.py` — 2 new D063 tests.
- `IMPLEMENTATION_DECISIONS.md` D063 (this entry).


## D064 — 2026-05-18 — Per-hypothesis pre-filter rejection breakdown

**Spec section:** §11 observability; follow-on to D062.

**Context:** D062 surfaced production rejection breakdown for iteration 32:
```
prefilter_rejections: permutation_test=2085, novelty=1399, predicted_activations=1063,
                     expected_trades=290, signal_density=145, signal_correlation=4,
                     regime_exposure=2
```

Cross-referenced against per-hypothesis structural fingerprints in `submissions`:

| Hypothesis | submitted | unique fingerprints |
|---|---:|---:|
| mean_reversion | 1 | 1 |
| trend_continuation | 0 | 0 |
| regime_arbitrage | 877 | 214 |
| relative_value | 1,154 | 81 |
| tail_hedge | 1,851 | 70 |
| volatility_event | 156 | 6 |

`mean_reversion` and `trend_continuation` aren't dying at `novelty` — they have effectively zero historical fingerprints, so they can't be the source of novelty rejections. They must be killed by an earlier filter in the §5.2 battery before reaching novelty. D062's aggregate column can't tell us *which* — we need the same counter partitioned by `config.hypothesis`.

**Decision:** Add `prefilter_rejections_by_hypothesis JSON` column to `batch_summaries`. Extend `record_prefilter_rejections` to populate both columns in one pass. Return a `PrefilterRejectionSummary` dataclass (`total`, `by_hypothesis`) so callers can log either or both. CLI's `_run_one_iteration` echoes both lines to the journal:

```
prefilter_rejections: filter=N, ...                              # D062 aggregate
prefilter_rejections_by_hypothesis: hyp[filter=N, ...]; ...      # D064 breakdown
```

**Hard rules check:**
- None impacted. Observability layer only; no enumeration semantics change.
- ALTER TABLE is `IF NOT EXISTS`-idempotent, so existing prod DBs pick up the column on next `db_connection` open without manual migration.

**Alternatives considered:**
- **Nest the per-hypothesis breakdown inside the existing `prefilter_rejections` column.** Considered. Rejected because the existing column already has analyzed history (one batch from iteration 32 just landed under the flat-dict schema). Adding a new column preserves backwards-compatibility — old analytic queries against `prefilter_rejections` keep working.
- **One row per `(batch_id, hypothesis)` in a new normalized table.** Considered. Rejected — overkill for what's effectively a per-batch summary; the JSON column matches the granularity of the existing `common_failures` and `prefilter_rejections` columns.
- **Skip the per-hypothesis breakdown and add per-hypothesis `forge prefilter --summary` instead.** Considered. Rejected because the autonomous loop is the only path that runs the production feature cache — the CLI runs synthetic by default (and synthetic was 100% permutation_test, useless for this question). Production telemetry has to come from production runs.

**Verification:**
- New unit test `test_d064_record_prefilter_rejections_partitions_by_hypothesis` in `tests/unit/test_submission/test_submitter.py` covers the partition logic and DB persistence.
- Existing D062 tests updated for the new return type (`PrefilterRejectionSummary` instead of raw dict).
- Ruff + mypy strict clean on changed files.

**Action:**
- `src/forge/persistence/schemas.py` — `ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS prefilter_rejections_by_hypothesis JSON`.
- `src/forge/submission/submitter.py` — `PrefilterRejectionSummary` dataclass + extended `record_prefilter_rejections` populates both columns.
- `src/forge/cli/main.py` — new `_log_prefilter_rejections(summary)` helper; `_run_one_iteration` calls it instead of the inline join. Echoes both aggregate and per-hypothesis lines.
- `tests/unit/test_submission/test_submitter.py` — new D064 test + D062 tests adapted for the summary return type.
- `IMPLEMENTATION_DECISIONS.md` D064 (this entry).


## D065 — 2026-05-18 — Per-iteration pipeline telemetry: timings + funnel distributions

**Spec section:** §11 observability; follow-on to D062/D063/D064.

**Context:** Through D052→D064, we built rejection-bucket visibility piece by piece. Three remaining gaps were load-bearing for understanding pipeline performance:

1. **No timing data.** Iteration 31's 3h22m feature_cache prefetch was *invisible* — we only inferred it from the gap between `--- loop iteration X ---` and `enumerated=N`. The systemd-level "Consumed Xmin CPU time" line was the only timing signal, and it only fired on service stop. Any phase pathology required CPU-profile-and-deduce instead of grep-and-see.

2. **No sampler attempt counts per hypothesis.** D064 partitioned the *rejection* bucket by hypothesis. But the funnel-top — *what the sampler actually produced* — was invisible. Couldn't distinguish "sampler proposed 1,900 mean_reversion configs, all died" from "sampler proposed 10, all died."

3. **No ranked-survivor counts per hypothesis.** Symmetric gap at the funnel-bottom. `ranked_top_n=12` told us *how many* candidates we submitted but not *which hypotheses* they came from. With D064 in the middle showing per-hypothesis attrition, the missing endpoints made the funnel un-narratable.

**Decision:** Three new journal lines per iteration, plus a `timings` plumbing parameter through `_run_battery_for_seed`:

```
phase_timings: reconcile=3.00s, enumeration=8.00s, prefetch=12345.00s, battery=8.00s, rank=0.20s, submit=0.05s
sampler_attempts: trend_continuation=N, mean_reversion=N, regime_arbitrage=N, relative_value=N, volatility_event=N, tail_hedge=N
ranked_top_n_by_hypothesis: trend_continuation=N, mean_reversion=N, regime_arbitrage=N, relative_value=N, volatility_event=N, tail_hedge=N
```

Together with D064's `prefilter_rejections_by_hypothesis: hyp[filter=N, ...]; ...` in the middle, the journal now carries a **complete per-hypothesis funnel** in three lines plus a timing breakdown:

```
sampler_attempts → prefilter_rejections_by_hypothesis → ranked_top_n_by_hypothesis
        ↑                       ↑                              ↑
    (D065 top)             (D064 middle)                  (D065 bottom)
                  phase_timings (D065 timing axis)
```

**Implementation choices:**
- `_run_battery_for_seed` accepts an optional `timings: dict | None` parameter; when provided, populates `enumeration`, `prefetch`, `battery` keys with monotonic deltas. Default `None` keeps existing callers (the demo `cmd_prefilter`, tests) signature-compatible.
- `_format_phase_timings_line` renders in canonical pipeline order (reconcile → ... → submit), skipping absent keys so a `blocked`-short-circuit iteration produces an honest partial view.
- `_format_hypothesis_distribution_line` renders in canonical `_HYPOTHESES` order with `=0` for absent hypotheses — D063's lesson: silent omission is misleading.
- Both helpers extracted from `_run_one_iteration` to keep the function within reason. `_run_one_iteration` carries a single `# noqa: PLR0915` with a comment explaining the function is observability-heavy by design now.

**Hard rules check:**
- None impacted. Pure observability layer; no enumeration semantics, no Crucible-side coupling, no schema changes (this iteration stays in the journal — the DB-persisted breakdowns from D062/D064 cover the analytics axis).

**Alternatives considered:**
- **Add `phase_timings`/`sampler_attempts`/`ranked_by_hypothesis` columns to `batch_summaries`.** Considered. Rejected for now — the journal is the right surface for transient performance data (operator grep, dashboard tail); `batch_summaries` is the right surface for *outcome* analytics (promotion rates, rejection buckets). Adding more columns muddies that split. If a rolling-window timing view becomes valuable, a separate `iteration_timings` table is the cleaner home.
- **Use a stdlib `time.perf_counter()` context manager helper for each phase.** Considered. The `_t_X = monotonic(); ...; timings[X] = monotonic() - _t_X` pattern is 3 lines vs a 4-line `with` block + helper definition; for 3 phases the savings don't pay back the helper.
- **Surface `prefetch` progress mid-flight (chunks=X/Y).** Considered. Rejected — the long-term fix for slow-prefetch invisibility is the contracts-side recv timeout (proposed earlier), not more in-flight logging. Per-chunk progress would also be much more verbose.
- **Add per-filter elapsed timing to `prefilter_rejections`.** Considered. Rejected — premature; we'd need a representative production batch first to see if the cost is actually filter-distributed or dominated by one phase (likely the feature-data-dependent ones).

**Verification:**
- 4 new tests in `tests/unit/test_cli/test_run_loop.py`:
  - `test_d065_phase_timings_line_renders_in_pipeline_order` — canonical order + 2-decimal seconds format.
  - `test_d065_phase_timings_line_skips_missing_phases` — partial view honesty.
  - `test_d065_hypothesis_distribution_line_uses_canonical_order` — canonical `_HYPOTHESES` order + `=0` for absent.
  - `test_d065_run_battery_for_seed_populates_timings` — opt-in dict populated with the three internal phases.
- Ruff + mypy strict clean on `src/forge/cli/main.py`.

**Action:**
- `src/forge/cli/main.py`:
  - `_run_battery_for_seed` — new `timings: dict | None = None` parameter; populates `enumeration`, `prefetch`, `battery`.
  - `_run_one_iteration` — new `timings` local; wires outer phases (`reconcile`, `rank`, `submit`); emits new log lines.
  - New helpers: `_format_phase_timings_line`, `_format_hypothesis_distribution_line`, `_log_hypothesis_distributions`, `_echo_dry_run_preview` (extracted from inline dry-run preview).
  - `_run_one_iteration` carries a `# noqa: PLR0915` for the observability-heavy statement count.
- `tests/unit/test_cli/test_run_loop.py` — 4 new D065 tests.
- `IMPLEMENTATION_DECISIONS.md` D065 (this entry).

---

## D066 — Tail-hedge dropped from StrategySpec enumeration (overlay-only)

**Date:** 2026-05-18

**Context.** Forge has been emitting `hypothesis="tail_hedge"` configs as `StrategyConfig`s and submitting them via the inbox. Crucible's runner (`src/optbt/data/runner.py:397`) rejects every one at dispatch with `RunnerError` because `tail_hedge` belongs to `OverlaySpec` semantics, not `StrategySpec`. Every such submission is pure wasted compute: round-trip to Crucible's queue, picked up, errors immediately, run marked failed, no backtest work happens.

Concrete cost from this iteration of monitoring:

- **1,851 of 4,039 processed inbox configs (45.8%)** are `tail_hedge`.
- **~422 of the latest 1,000 gated_runs** are `tail_hedge`, all `RunnerError`.
- Forge's adaptive sampler at iteration 32 placed `tail_hedge` at ~50% of effective submissions despite all of them erroring at dispatch — the failure-bias weights are downstream of *Crucible-gate* outcomes, not of *Crucible-dispatch* outcomes, so they never registered the runner rejections as a signal to down-weight the hypothesis.

**Root cause.** The grammar lists `tail_hedge` as a valid hypothesis (§3.5 — operator-owned), and Forge had no enumerator-side or submitter-side filter to keep tail_hedge configs out of the production loop. Crucible's runner-side defense was firing correctly but on the wrong side of an expensive boundary (post-queue, post-dispatch).

**Decision.** Two-layer defense:

1. **Sampler-side prevention.** A new module-level frozenset `OVERLAY_ONLY_HYPOTHESES = frozenset({"tail_hedge"})` in `forge.enumeration.search_space` is the single source of truth. The sampler (`sample_config`) and the iterator (`enumerate_candidates` D037 stratification) both filter `OVERLAY_ONLY_HYPOTHESES` out of the `samplable_hypotheses` pool BEFORE any other selection happens — no enumeration work is wasted on these hypotheses.
2. **Submitter-side defense-in-depth.** `submitter._submit_one` checks `config.hypothesis in OVERLAY_ONLY_HYPOTHESES` and short-circuits: no DB insert, no inbox write, returns a `SubmissionRecord(status="dropped_overlay_only")`. `submit_batch` aggregates these into a new `BatchSubmissionResult.dropped_overlay_count` field and emits a `logger.warning` if any fire — so a future regression that bypasses the sampler filter surfaces loudly instead of silently round-tripping to Crucible.

**Why not just delete `tail_hedge` from grammar.yaml?** Hard rule #1: the §3.5 grammar rules are operator-owned. Hard rule #10 also requires a version bump + archive + Decision-Log entry on any grammar change. The semantic claim — "tail_hedge is a valid *hypothesis*, but Forge should not enumerate it as a *standalone strategy*" — belongs in the enumeration-policy layer, not the grammar. When `crucible_contracts` grows an `OverlaySpec` model (currently a contracts gap, surfaced 2026-05-18), an overlay-aware enumeration path can re-admit `tail_hedge` as a portfolio overlay and the `OVERLAY_ONLY_HYPOTHESES` set can shrink — without re-bumping the grammar.

**Why not silence Crucible's runner-side RunnerError?** Defense-in-depth. Crucible's authority over what is a `StrategyConfig` should not depend on Forge's producer discipline. The runner check stays; Forge's filter just stops feeding it work to reject.

**Hard rules check:**

- **#1 (21 v1 grammar rules operator-owned):** grammar.yaml unchanged. The §3.5 `tail_hedge` hypothesis stays listed. Filter lives in Forge runtime policy.
- **#2 (no imports from Crucible internals):** no Crucible imports touched. The runner-side defense is acknowledged by reference only.
- **#3 (never lower Crucible's gate):** N/A — this is enumeration scope, not gate strictness. Forge submits *less*, not Crucible gating *more loosely*.
- **#6 (deterministic enumeration):** preserved. The filter is a deterministic predicate against a frozen set; `(grammar_version, registry_hash, seed)` still produces a byte-identical sequence within the now-smaller hypothesis pool. The Phase 2 determinism property test (`test_enumeration_byte_identical_for_same_triple`) still passes.
- **#7 (no equity family):** N/A.

**Alternatives considered:**

- **Submitter-only filter (no sampler change).** Considered. Rejected: leaves the enumeration / scoring / ranking layers doing pointless work on candidates we know cannot ship, and the journal's `sampler_attempts` line would mislead.
- **Sampler-only filter (no submitter defense).** Considered. Rejected: a future regression — e.g., a CLI path that constructs candidates outside the sampler, or a stale rerun script — could silently re-introduce tail_hedge submissions. The submitter-side guard is cheap and converts silent failure into a loud warning.
- **Mark `tail_hedge` as `active: false` in grammar.yaml.** Considered. Rejected for now: it's a grammar edit (hard rule #10 audit cost) and conflates "Forge does not enumerate this" with "the operator disabled this hypothesis." The runtime filter is the more honest framing.
- **Sample `tail_hedge` at low weight (e.g., 0.001) and accept the waste.** Considered. Rejected — 0.001 of 5000 candidates/iteration ≈ 5 wasted Crucible round-trips per iteration; at iteration cadence that's still 100s/day of compute on guaranteed failures.

**Verification:**

- 2 new tests in `tests/invariants/test_phase2_invariants.py`:
  - `test_d066_no_overlay_only_hypothesis_in_any_yielded_config` — sweeps 5 seeds × 100 candidates = 500 configs; none has `hypothesis="tail_hedge"`.
  - `test_d066_overlay_only_hypothesis_blocked_when_forced` — a direct `sample_config(..., forced_hypothesis="tail_hedge")` raises `SamplerError`.
- 2 new tests in `tests/unit/test_submission/test_submitter.py`:
  - `test_d066_submitter_drops_overlay_only_hypothesis` — a tail_hedge candidate is dropped: no `submissions` row, no inbox file, status `"dropped_overlay_only"`, `dropped_overlay_count == 1`.
  - `test_d066_batch_submission_result_default_dropped_overlay_is_zero` — sanity that healthy batches report `0`.
- 1 existing test updated:
  - `tests/unit/test_enumeration/test_sampler.py::test_sampler_reaches_every_hypothesis` — expected set no longer includes `tail_hedge`.

**Action:**

- `src/forge/enumeration/search_space.py` — new `OVERLAY_ONLY_HYPOTHESES` frozenset.
- `src/forge/enumeration/sampler.py` — import + filter in `sample_config`.
- `src/forge/enumeration/iterator.py` — import + filter in `enumerate_candidates` D037 stratification path.
- `src/forge/submission/submitter.py` — `SubmissionStatus` gains `"dropped_overlay_only"`; `BatchSubmissionResult` gains `dropped_overlay_count: int = 0`; `_submit_one` short-circuits on overlay-only hypothesis; `submit_batch` aggregates the counter and emits a `logger.warning` per batch with any drops.
- `tests/invariants/test_phase2_invariants.py` — 2 new D066 tests.
- `tests/unit/test_submission/test_submitter.py` — 2 new D066 tests.
- `tests/unit/test_enumeration/test_sampler.py` — `test_sampler_reaches_every_hypothesis` expected set updated.
- `IMPLEMENTATION_DECISIONS.md` D066 (this entry).

---

## D067 — Exploration floor on hypothesis weights (cold-start death-spiral guard)

**Date:** 2026-05-18

**Context.** Forge's adaptive hypothesis weighter (`forge.feedback.rejection_weights.compute_hypothesis_weights`) produces a Beta-smoothed posterior promotion rate per hypothesis. Hypotheses with zero gated history return the Beta(1, 10) prior mean (~0.091); hypotheses with observed-but-failing history get a much lower posterior (e.g., 0.003-0.05). Over 4,039 submissions, two of the six v1 hypotheses had collapsed:

- **trend_continuation:** 0 / 4,039 submissions (0.000%).
- **mean_reversion:** 1 / 4,039 submissions (0.025%).

This is the classic cold-start death spiral: a hypothesis with very-low posterior weight rarely gets sampled, so it never accumulates corrective evidence, so its weight stays low, so it's rarely sampled, ad infinitum. D037 (2% stratified floor on the iterator's forced rotation) was meant to backstop this, but the forced-failure cap (20 retries) means that hypotheses whose CSP keeps dead-ending get blacklisted for the rest of the batch and the Bayesian sampler takes back over for the remaining ~98% of the budget. D063 made the absent hypotheses visible in the journal (prior-filled with `*`), but didn't change their effective sampling weight.

**Decision.** Apply a `DEFAULT_EXPLORATION_FLOOR = 0.05` across all canonical sampling hypotheses BEFORE the weights reach the sampler.

A new helper `apply_exploration_floor(weights, *, hypotheses, floor, fallback)` in `forge.feedback.rejection_weights` returns a dict that ALWAYS contains every name in `hypotheses` with weight at least `floor`:

- **Present in `weights`:** `max(weights[h], floor)`.
- **Absent + `fallback` set:** `max(fallback, floor)` — used to keep cold-start hypotheses on the Beta prior (which is already above the floor at ~0.091).
- **Absent + `fallback=None`:** the floor directly.

The CLI's `_load_hypothesis_weights` chains this after `compute_hypothesis_weights`, passing `hypotheses=_HYPOTHESES \\ OVERLAY_ONLY_HYPOTHESES` (D066) and `fallback=prior_mean()`. Every cold-start / degraded-export / no-overlap path also returns floored weights, so the sampler never sees a sparse dict for canonical hypotheses again.

**Math after the floor.** With 5 active sampling hypotheses (tail_hedge excluded by D066) and a floor of 0.05:

```
pre-D067 effective weights (from production journal iter 32):
  trend_continuation = 0.091  (prior, missing from weights map)
  mean_reversion     = 0.091  (prior, missing from weights map)
  regime_arbitrage   = 0.004  (observed, posterior)
  relative_value     = 0.003  (observed, posterior)
  volatility_event   = 0.048  (observed, posterior)
  → sample shares:    38.4% / 38.4% / 1.7% / 1.3% / 20.3%

post-D067 effective weights:
  trend_continuation = 0.091  (prior, unchanged — already above floor)
  mean_reversion     = 0.091  (prior, unchanged — already above floor)
  regime_arbitrage   = 0.050  (floored)
  relative_value     = 0.050  (floored)
  volatility_event   = 0.050  (floored — natural 0.048 just below floor)
  → sample shares:    27.4% / 27.4% / 15.1% / 15.1% / 15.1%
```

Every hypothesis now gets at least 15% of the budget — enough for ~38 candidates per 250-candidate iteration to start accumulating corrective evidence. Once a hypothesis's posterior climbs above the floor on its own merit (~50 promoted runs), it dominates naturally.

**Hard rules check:**

- **#1 (grammar operator-owned):** untouched. The §3.5 hypothesis list is unchanged; this is a runtime sampling policy.
- **#6 (deterministic enumeration):** preserved. The floor is a deterministic transform on the weight map. Same `(grammar_version, registry_hash, seed, gated_runs_snapshot)` still produces a byte-identical enumeration sequence.
- **#4 (auto-loosening forbidden):** N/A — this is sampling-distribution policy, not grammar relaxation. The pre-filter battery and Crucible's gate are unchanged; this only changes which hypotheses get scored.

**Alternatives considered:**

- **Apply floor inside `compute_hypothesis_weights`.** Considered. Rejected: that function is also called by analytics paths and integration tests that expect the raw Beta posterior. Keeping the floor in a separate function preserves analytic clarity and lets the CLI explicitly opt in.
- **Raise the Beta prior alpha (e.g., from 1 to 5).** Considered. Rejected: the prior controls how strongly the posterior shifts toward observed data; raising alpha would slow learning for hypotheses that genuinely deserve down-weighting. The floor is a sharper instrument — it's about exploration guarantees, not posterior shape.
- **Adaptive floor (e.g., higher floor when sample count is small, decay as data accumulates).** Considered. Rejected for v1 simplicity: a fixed floor at 0.05 lets ~15% per hypothesis through; once any hypothesis stably clears 0.05 on natural posterior the floor is inactive for it. An adaptive schedule adds tuning surface without obvious benefit at current sample sizes.
- **Stratified floor at the iterator (raise D037 from 2% to 10%).** Considered. Rejected: D037's `_FORCED_FAILURE_CAP=20` rate-limits the forced rotation when CSP dead-ends. Raising the floor wouldn't help if the actual blocker is the CSP. The weighted-sample path is the right surface.

**Verification:**

- 5 new tests in `tests/unit/test_feedback/test_rejection_weights.py`:
  - `test_d067_floor_bumps_observed_below_floor` — observed-low hypotheses (0.003, 0.004, 0.048) get clamped to 0.05.
  - `test_d067_floor_preserves_observed_above_floor` — natural high posterior passes through.
  - `test_d067_unobserved_uses_fallback_then_floor` — `fallback=prior_mean()` keeps cold-start at prior (above floor); `fallback=None` uses floor directly.
  - `test_d067_all_canonical_hypotheses_always_present` — sparse input → all 5 keys in output.
  - `test_d067_custom_floor_threshold` — sensitivity at floor=0.10.
- Ruff + mypy strict clean on `src/forge/feedback/rejection_weights.py` + `src/forge/cli/main.py`.

**Action:**

- `src/forge/feedback/rejection_weights.py` — new `DEFAULT_EXPLORATION_FLOOR=0.05` constant; new `apply_exploration_floor(...)` helper.
- `src/forge/cli/main.py` — `_load_hypothesis_weights` chains `apply_exploration_floor` after every compute path (cold-start, degraded-export, no-overlap, normal). The journal `hypothesis_weights:` line now reflects floored values directly.
- `tests/unit/test_feedback/test_rejection_weights.py` — 5 new D067 tests.
- `IMPLEMENTATION_DECISIONS.md` D067 (this entry).

**Expected operator-observable behavior.** After restart, the `hypothesis_weights:` line in the journal will show all 5 sampling hypotheses with weights at or above 0.05. `sampler_attempts:` should track ~15-27% per hypothesis within the first iteration. Within 5-10 iterations, both `mean_reversion` and `trend_continuation` should produce gated runs that move their posteriors off the prior.

---

## D068 — Populate pairs_convergence template params (relative_value zero-trades fix)

**Date:** 2026-05-19

**Context.** Across 4,039 historical submissions, 1,154 (28.6%) were `relative_value` configs. Every single one produced n_trades=0 on Crucible's backtester — 345/345 gated runs had zero trades. This is the second-largest source of wasted compute behind the D066 tail_hedge issue.

**Diagnosis.** Two compounding problems, surfaced by an instrumented funnel walk across 62 sessions x 15 pairs (930 (asof, pair) evaluations):

1. **Contract mismatch.** Crucible's `pairs_convergence` template (`src/optbt/strategy/templates/pairs_convergence.py:84-96`) reads its CSP-style entry rule (`lookback`, `pvalue_max`, `zscore_entry`, `halflife_min`, `halflife_max`) from `signals[0].params.get(key, default)`. Forge's sampler currently emits `{"threshold": -1.18, "op": "<"}` — the *generic* threshold-predicate keys Crucible uses for activation-date detection. The template's keys are absent, so all 1,154 relative_value configs ran with template defaults: `lookback=252`, `pvalue<0.05`, `|z|>2.0`, `hl ∈ (5, 30)`.

2. **Strict default thresholds.** With template defaults, only **3 of 930 (0.32%)** evaluations were entry-eligible across the 90-day window. Failure breakdown:
   - 818/930 = 88.0% fail `pvalue<0.05` (median cointegration pvalue = 0.59).
   - 96 of 112 pvalue-passers = 85.7% fail `|z|>2.0` (median |z| = 1.06).
   - 13 of 16 zscore-passers = 81.3% fail `5<halflife<30` (median halflife = 3.32 — below the floor).

   Two pairs carry essentially all the surviving signal (PG-CL and GOOG-GOOGL); the other 13 pairs of the 15-pair list fail cointegration on every sampled session. Even when an entry IS eligible, the dedup rule (one position per underlying per strategy_id) clusters all viable PG-CL entries into a single position — yielding 0-1 trades total per backtest.

   Widening sensitivity (same 930 evaluations):
   - default `pval<0.05, |z|>2.0, hl ∈ (5,30)`: **0.3% eligible** (baseline).
   - widened-low `pval<0.10, |z|>1.5, hl ∈ (3,45)`: **3.9% eligible** (13x).
   - widened-mid `pval<0.15, |z|>1.0, hl ∈ (2,45)`: **7.7% eligible** (26x).
   - widened-aggressive `pval<0.20, |z|>0.8, hl ∈ (2,60)`: **9.1% eligible** (30x).

**Decision.** Populate `signals[0].params` with the template-expected keys when the directional indicator is `pairs_zscore`. This is a Forge-side fix because (a) Crucible's template is already a `.get(key, default)` lookup — no Crucible change needed; (b) per CLAUDE.md hard rule #2, no Crucible internals modifications; (c) the contract that Forge's `signals[0].params` should carry strategy-template params is naturally Forge's side of the boundary.

New helper `_sample_pairs_template_params(rng)` in `forge.enumeration.sampler`:

```python
lookback:      rng.choice((126, 189, 252, 378, 504))
pvalue_max:    uniform(0.05, 0.20)
zscore_entry:  uniform(0.8, 2.0)
halflife_min:  rng.choice((2, 3, 5, 8))
halflife_max:  rng.choice((15, 30, 45, 60))
```

`_directional_signal_params` merges these into the threshold-params dict ONLY when `indicator_id == "pairs_zscore"`. Other indicators are untouched. The disjoint discrete ranges for `halflife_min` (2..8) and `halflife_max` (15..60) guarantee `halflife_min < halflife_max` by construction.

**Hard rules check:**

- **#1 (grammar operator-owned):** untouched. Pairs-template params live in the sampler, not the grammar. If the operator decides to add a §3.5 P-rule constraining these ranges, the sampler will narrow inside the grammar-prescribed bounds — same pattern as P2/P3/P4 today.
- **#2 (no Crucible internals):** preserved. We do not import from Crucible. We adapt to its public `signals[0].params` contract.
- **#3 (never lower Crucible's gate):** N/A. This is enumeration variation, not gate strictness. Backtests with widened thresholds still pass through Crucible's full gate.
- **#6 (deterministic enumeration):** preserved. `_sample_pairs_template_params(rng)` is a pure function of the RNG state at call time. Same `(grammar_version, registry_hash, seed)` still produces byte-identical configs.
- **#7 (no equity):** N/A.

**Alternatives considered:**

- **Add §3.5 P-rules for the pairs params.** Considered. Rejected for now: hard rule #1 makes that a careful operator-review item; the urgent fix is to stop wasting 28.6% of inbox compute on identical no-trade backtests. The sampler ranges can later be tightened by a grammar P-rule without breaking this commit.
- **Widen `pvalue_max` only.** Considered. Rejected: the funnel analysis shows pvalue is the dominant filter (88% failure rate), but |zscore| and halflife each also block ~80% of the remaining survivors. Widening just one knob leaves the other two as the bottleneck.
- **Modify Crucible's template defaults.** Considered. Rejected per the operator's prompt boundary ("fix lands in the correct repo — Forge if it's grammar ranges"). The template's defaults are fine for a conservative single-config invocation; the variation belongs in the enumeration layer.
- **Down-weight relative_value at the sampler.** Considered. Rejected: that masks the symptom without fixing the underlying contract mismatch. Eventually we want relative_value submissions to vary AND fire trades; mere down-weighting yields neither.
- **Skip the pairs-strategy hypothesis until OverlaySpec / proper template variation lands.** Considered (same shape as D066). Rejected because, unlike `tail_hedge`, `relative_value` is a return-seeking strategy with a real Crucible gate — the variation knobs exist and are easy to populate. Better to enumerate properly than to defer.

**Verification:**

- Funnel-walk diagnostic at `/tmp/diag_relative_value.py` (kept for re-running on new pair lists).
- Sensitivity diagnostic at `/tmp/diag_widen.py` (confirms 13-30x entry-rate improvement across the proposed ranges).
- 4 new tests in `tests/unit/test_enumeration/test_sampler.py`:
  - `test_d068_pairs_zscore_directional_emits_template_params` — keys present.
  - `test_d068_pairs_template_params_ranges` — values in documented ranges across N=50 seeds; `halflife_min < halflife_max` invariant holds.
  - `test_d068_pairs_template_params_deterministic_under_same_rng` — same seed → same params.
  - `test_d068_non_pairs_indicator_does_not_get_template_params` — other directional indicators unaffected.
- Full pytest suite (1,086 tests) green.
- Ruff + mypy strict clean on changed scope.

**Expected operator-observable behavior.** After restart, new `relative_value` submissions will carry `lookback`/`pvalue_max`/`zscore_entry`/`halflife_min`/`halflife_max` in `signals[0].params`. Within ~5 iterations, the `gated_runs` export should start showing relative_value runs with `n_trades > 0` — at least ~10% per sensitivity analysis. The adaptive weighter will then have real data to refine the posterior beyond the D067 exploration floor.

**Action:**

- `src/forge/enumeration/sampler.py` — `_directional_signal_params` merges in `_sample_pairs_template_params(rng)` for `pairs_zscore`; new helper exposes the 5 sampled keys.
- `tests/unit/test_enumeration/test_sampler.py` — 4 new D068 tests.
- `IMPLEMENTATION_DECISIONS.md` D068 (this entry).

---

## D069 — Param-aware structural fingerprint (Phase 1 of FORGE_GENERATOR_IMPROVEMENT_PLAN)

**Date:** 2026-05-19

**Context.** After D066 + D067 + D068 shipped, four consecutive Forge iterations (33-36) produced **100% regime_arbitrage survivors** across different seeds: 31 / 20 / 14 / 19 of 5,000 candidates each. The other four sampling hypotheses (trend_continuation, mean_reversion, relative_value, volatility_event) got zero past the pre-filter battery. The dominant rejection bucket was `novelty` at ~41.8% across all four iterations.

Per `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 1 analysis (Forge-side surface of Crucible 2026-05-19 3,829-cohort handoff), the structural cause is:

1. D067 evenly distributed sampling across 5 active hypotheses, dropping ~1,000 candidates each into `mean_reversion`, `trend_continuation`, `volatility_event`, `relative_value`.
2. The §3.5 grammar constrains these four hypotheses to narrow C2 family x R-rule combos: ~6 (directional, regime) pairs for `mean_reversion`, ~18 for `trend_continuation`, ~25 for `volatility_event`, ~50 for `relative_value`. The fifth (`regime_arbitrage`, any-family) has ~2,500 combos.
3. The T2.7 structural fingerprint (D043 / D049 / D060) hashed `(hypothesis, indicator_ids, exit_ids, dte_bucket, sizer_mode)` and EXPLICITLY excluded numeric params (delta_target, threshold values, sizer params, D068 pairs keys). Original D043 rationale: "anything Optuna would tune within a fixed structural shape" — but Optuna is not in the production loop, and each different-param config produces a different Crucible backtest with different gated metrics.
4. Result: a batch with 1,000 `mean_reversion` candidates collapsed to ~6 unique fingerprints. The novelty filter correctly killed 99.4% of them as intra-batch duplicates. `regime_arbitrage` survived because its any-family pool produced ~2,500 unique fingerprints, well above the batch size.

**Decision.** Extend `compute_structural_fingerprint` to include bucketed numeric params.

New hash inputs (additive to the pre-D069 structural skeleton):

- **Per-signal params:** sorted by `signal.id`, each param keyed and bucketed.
- **Per-exit params:** sorted by `exit.id`, each param keyed and bucketed.
- **Selector:** `delta_target` (bucketed), `dte_min` (exact int), `dte_max` (exact int).
- **Sizer params:** `per_trade_risk_pct` (bucketed), `kelly_fraction` (bucketed), `vol_target_annual` (bucketed).

**Bucketing rule.** All floats round to a per-key decimal precision (default 2dp). `per_trade_risk_pct` overrides to 3dp because its native range is 0.005-0.020 — 2dp would collapse to ~4 buckets and erase Phase 5 variation. Ints / strs / None pass through unchanged.

**Math after the change.** For `mean_reversion` with 6 (directional, regime) combos x ~36 delta_target buckets x ~16 risk_pct buckets x ~15 directional-threshold buckets x ~9 regime-threshold buckets x 3 dte_buckets = ~1.4M structural variants. A 1,000-candidate batch now hits a vastly larger discrimination space; intra-batch novelty collisions drop from 99.4% to a trivial fraction.

**Backwards compatibility.** Existing `submissions` rows store the raw `config_json`; fingerprints are computed on demand by `_load_prior_structural_fingerprints`. Switching the algorithm re-derives the historical fingerprint set with the new richer schema — no DB migration. The set size grows (more unique fingerprints), but new candidates are also more likely to be unique, so the net effect is MORE configs admitted, not fewer.

**Hard rules check:**

- **#1 (grammar operator-owned):** untouched. Pure pre-filter dedup change. No §3.5 modification.
- **#2 (no Crucible internals):** preserved. Pure Forge-side change in `forge.prefilters.novelty`.
- **#3 (never lower Crucible's gate):** N/A. Affects which configs reach Crucible, not which Crucible promotes.
- **#6 (deterministic enumeration):** preserved. The fingerprint is deterministic over the bucketed config — same (`grammar_version`, `registry_hash`, `seed`) still produces the same enumeration sequence, and the same config always hashes the same.

**Alternatives considered:**

- **Include raw (unbucketed) floats.** Considered. Rejected: would defeat the dedup almost entirely — `delta_target=0.394` and `delta_target=0.401` would have different fingerprints even though they pick the same option contract on most days. The dedup's purpose is to collapse truly-equivalent configs without enumerating their continuous param tail.
- **Round to 4 decimal places.** Considered. Rejected: matches the sampler's native emission precision, so EVERY sampled config would have a unique fingerprint and the dedup becomes a no-op.
- **Single-precision rule (round all floats to 2dp).** Considered. Rejected: per_trade_risk_pct's 0.005-0.020 range collapses to 4 buckets at 2dp — would erase Phase 5's planned sampler variation. Per-key precision avoids this without much complexity.
- **Asymmetric novelty filter (looser threshold for under-sampled hypotheses).** Considered as Phase 1 alternative. Rejected: more complex, requires per-iteration state, and treats the symptom (hypothesis imbalance) rather than the cause (param-blind dedup).
- **Shrink max_candidates from 5000 to 1000.** Considered. Rejected: surface-level mitigation that limits exploration of the regime_arbitrage tail and doesn't address the structural cause — the constrained hypotheses would still hit the same novelty wall at scale 1000.

**Verification:**

- 6 new tests in `tests/unit/test_prefilters/test_novelty.py`:
  - `test_d069_structural_fingerprint_distinguishes_material_threshold_change` — replaces the pre-D069 `test_t27_structural_fingerprint_is_stable_across_param_changes`; threshold=20 vs threshold=30 now produces different fingerprints.
  - `test_d069_structural_fingerprint_collapses_within_bucket` — threshold=30.001 / 30.002 still collapse to the same bucket; delta_target=0.451 / 0.452 collapse.
  - `test_d069_structural_fingerprint_distinguishes_delta_target` — different delta picks different option contract → different fingerprints.
  - `test_d069_structural_fingerprint_distinguishes_risk_pct` — 0.005 vs 0.020 risk produces different fingerprints (3dp precision).
  - `test_d069_structural_fingerprint_distinguishes_d068_pairs_params` — D068 pairs-template variation (zscore_entry, halflife_min) enters the hash so D068's widening isn't deduped away.
  - `test_d069_structural_fingerprint_is_deterministic` — same config twice → same fingerprint (hard rule #6).
- Existing T2.7 tests (`test_t27_structural_fingerprint_distinguishes_indicator_swap`, `test_t27_novelty_rejects_matching_structural_fingerprint`) still pass — indicator-swap discrimination unchanged; fingerprint-match still rejected by NoveltyFilter.
- Full pytest suite: 1,091 tests green (5 new D069 + 1086 baseline).
- Ruff + mypy strict clean on changed scope.

**Expected operator-observable behavior.** Next iteration (37+) should show non-zero `ranked_top_n_by_hypothesis` counts for the constrained hypotheses (`trend_continuation`, `mean_reversion`, `volatility_event`, `relative_value`) — not necessarily even, but the 100% regime_arbitrage monoculture should break. `prefilter_rejections.novelty` will likely drop from the ~41.8% it has been holding at across iters 33-36.

**Action:**

- `src/forge/prefilters/novelty.py` — `compute_structural_fingerprint` extended with `signal_params` / `exit_params` / `selector` / `sizer_params` bucketed contributions; new `_bucket_value` + `_canonical_params` helpers; `_FINGERPRINT_FLOAT_PRECISION_*` constants.
- `tests/unit/test_prefilters/test_novelty.py` — 6 new D069 tests; existing T2.7 stability test replaced (was asserting param-blind behavior).
- `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` — Phase 1 row marked complete with D069 reference (separate commit).
- `IMPLEMENTATION_DECISIONS.md` D069 (this entry).

---

## D070 — Rate-limit threshold restored to 0.80 (D036 was tactical)

**Date:** 2026-05-19

**Context.** D036 dropped the §7.3 rate-limiter threshold from 0.80 → 0.50 on 2026-05-17 to unblock Forge while D033 Tier-2 throughput was bedding in. That tactical drop has now outlived its purpose:

- D033 Tier-2 batches are flowing.
- Crucible-side iv_rank + dealer/flow vectorization (Crucible-prompt-driven, shipped 2026-05-19) have collapsed the per-chunk feature_cache compute from hours to seconds.
- Forge's D069 param-aware fingerprint has unlocked the constrained hypotheses, taking ranked_top_n from 14-31 (iters 33-36) to 200 (iters 37-40).

The post-D069 throughput numbers from iters 37-40:

- Forge submission rate: ~200 configs/iter at ~7 min/iter = **~1,600 configs/hour**.
- Crucible gauntlet rate (one config in flight at a time, parallelized 4-way across CPCV folds internally, ~150-160s/config): **~24 configs/hour**.

That's a **67x mismatch**. The 0.50 threshold lets Forge keep iterating before Crucible has gated even half of the prior batch, so the inbox grows unboundedly. The §7.3 design-time choice of 0.80 ("wait until ≥80% of prev batch is gated") is the exact safeguard for this situation: it forces Forge to pause when the gauntlet falls behind, matching its submission cadence to gauntlet throughput.

**Decision.** Restore `_DEFAULT_THRESHOLD = 0.80` in `forge.submission.rate_limiter`. D036 stays as a historical comment; the new comment block explains the restoration with the throughput numbers above.

**Hard rules check:**

- **#1 / #4 (grammar / auto-loosening):** N/A. This is operational tuning of a rate-limit knob, not a grammar change.
- **#6 (deterministic enumeration):** preserved. The rate limiter does not enter the seed/sample paths.

**Alternatives considered:**

- **Leave at 0.50.** Considered. Rejected: lets the inbox grow ~1,576 configs/hour faster than the gauntlet can drain. Eventually overwhelms Crucible's queue or hits memory pressure.
- **Set to 1.0.** Considered. Rejected: pathological — would require EVERY config of the prior batch to gate before the next can start, eliminating overlap entirely. 0.80 is the spec value (§7.3) and was extensively reasoned about pre-v1.
- **Make it dynamic / adaptive.** Considered. Rejected for now: the 0.80 spec value is well-grounded; a dynamic schedule would need its own tuning surface without obvious benefit at current scale. Revisit if gauntlet throughput materially changes.

**Verification:**

- `tests/unit/test_submission/test_rate_limiter.py` — 12 tests pass; fixtures use explicit thresholds and are unaffected by the default change.
- Ruff clean on the changed file.
- Operator-observable: forge.service journal should now show occasional rate-limit pauses ("waiting" messages) once the next iter's ≥80% threshold isn't met. That's the design.

**Action:**

- `src/forge/submission/rate_limiter.py:51` — `_DEFAULT_THRESHOLD: 0.50 → 0.80`. Old D036 comment retained for history; new D070 block explains the restoration.
- `IMPLEMENTATION_DECISIONS.md` D070 (this entry).

---

## D072 — More aggressive `_sample_pairs_template_params` ranges (Phase 3.5 Forge-side)

**Date:** 2026-05-19

**Context.** D068 (2026-05-18) populated the pairs_convergence template's expected keys in `signals[0].params` and chose initial ranges that bridged template defaults to the "widened-aggressive" end of the sensitivity sweep:

```
# D068
lookback:      choice(126, 189, 252, 378, 504)
pvalue_max:    uniform(0.05, 0.20)
zscore_entry:  uniform(0.8, 2.0)
halflife_min:  choice(2, 3, 5, 8)
halflife_max:  choice(15, 30, 45, 60)
```

The 2026-05-19 cohort cross-tab (1,000 gated_runs × Forge submissions) revealed `relative_value` is still **97.5% zero-trade**:

| Hypothesis | 0 trades | 1-9 | 10-99 | 100+ | Total | % zero |
|---|---:|---:|---:|---:|---:|---:|
| `relative_value` | **309** | 8 | 0 | 0 | 317 | **97.5%** |

**Zero configs reach the 10-trade bucket.** The D068 widening helped — pre-D068 it was ~99% zero-trade — but uniform random sampling within (0.05, 0.20) concentrates picks around the midpoint (0.125), well below the diagnostic's "widened-aggressive" pvalue<0.20 setting that yielded 9.1% (asof, pair) eligibility.

**Decision.** Shift the ranges toward the more permissive end while preserving the conservative tail. New ranges:

```
# D072
lookback:      choice(126, 189, 252, 378)         # dropped 504 (longest)
pvalue_max:    uniform(0.10, 0.25)                  # shifted up
zscore_entry:  uniform(0.5, 1.5)                    # shifted down
halflife_min:  choice(1, 2, 3, 5)                   # admits fastest reverters
halflife_max:  choice(20, 45, 60, 90)               # admits slowest reverters
```

Reasoning by knob:
- **`pvalue_max` 0.05-0.20 → 0.10-0.25.** D068's diagnostic showed `pvalue<0.20` yields 9.1% eligibility. Sampling 0.10-0.25 puts most picks in the "moderately permissive" band that should yield 5-10% per-day eligibility.
- **`zscore_entry` 0.8-2.0 → 0.5-1.5.** The diagnostic's median |z| among pvalue-passers was 1.06, so 0.5-1.5 puts most picks BELOW that median — strategies fire on the visible portion of the distribution, not just the extreme tail.
- **`halflife_min` (2, 3, 5, 8) → (1, 2, 3, 5).** Median observed halflife was 3.32; previous floor of 2 was already permissive but the 8 option excluded too many fast reverters. New floor of 1 admits intraday-fast mean reversion.
- **`halflife_max` (15, 30, 45, 60) → (20, 45, 60, 90).** Original cap of 60 excluded slow reverters; some pairs have halflives in the 60-90 range.
- **`lookback` (126, 189, 252, 378, 504) → (126, 189, 252, 378).** Dropped 504 because in a 90-day backtest a 504-day lookback means the cointegration recompute window slides very slowly; fewer effective recomputes → fewer entry opportunities.

**Hard rules check:**
- **#1 (grammar operator-owned):** untouched. Sampler-side parameter ranges, not §3.5 rules.
- **#3 (never lower Crucible's gate):** preserved. Crucible's gauntlet (Sharpe, profit_factor, etc.) is the same. We just submit configs that more often produce SOMETHING for the gauntlet to evaluate.
- **#6 (deterministic enumeration):** preserved. Pure rng-state function.

**Alternatives considered:**

- **Even more aggressive (pvalue<0.30, zscore<0.4, etc.).** Considered. Rejected: at extreme permissiveness, cointegration-test pvalue stops being informative and zscore < 0.5 means we're trading on near-mean-spread. Both produce trades but with deteriorating signal-to-noise. The new ranges sit at the "shoulder" of the diagnostic's sensitivity curve.
- **Bias the existing D068 ranges via non-uniform sampling (e.g., beta distribution concentrated at the permissive end).** Considered. Rejected: simpler to shift the range than introduce a new sampling distribution.
- **Keep D068 and rely on Phase 3 (threshold auto-tightening) to learn.** Considered. Rejected: Phase 3 needs gated outcomes with non-zero trade counts to learn from; the current 97.5% zero-trade rate gives Phase 3 nothing to bias toward. D072 buys Phase 3 actual training signal.

**Companion work:**
- **Crucible-side pair-universe expansion** — separate hand-off prompt `CRUCIBLE_PAIR_CANDIDATES_EXPANSION_AGENT_PROMPT.md`. The 15-pair list is still narrow (only 2 viable per D068 diagnostic on 2025-Q2 data); even with D072's aggressive sampling, configs are bounded by what pairs exist. Pair-universe expansion is the second lever.

**Verification:**
- `tests/unit/test_enumeration/test_sampler.py::test_d068_pairs_template_params_ranges` updated to assert the new D072 ranges across 50 seeds.
- `halflife_min < halflife_max` invariant preserved by disjoint discrete sets (max(halflife_min)=5 < min(halflife_max)=20).
- Ruff + mypy strict clean on `src/forge/enumeration/sampler.py`.
- Full `test_sampler` + `test_phase2_invariants` (140 tests) pass.

**Expected operator-observable behavior.** Next iter's submissions will carry the new ranges. Within ~3-5 iters, gauntlet outcomes for `relative_value` should start showing configs in the 1-9 trade bucket (currently 8/317 = 2.5%) and possibly the 10-99 bucket for the first time. If still ≥90% zero-trade after 1,000 new submissions, the issue is the pair-universe (Crucible-side), not Forge's param ranges.

**Action:**
- `src/forge/enumeration/sampler.py::_sample_pairs_template_params` — 5 sampling ranges shifted/widened per the table above.
- `tests/unit/test_enumeration/test_sampler.py::test_d068_pairs_template_params_ranges` — assertions updated for new ranges.
- `IMPLEMENTATION_DECISIONS.md` D072 (this entry).
- `CRUCIBLE_PAIR_CANDIDATES_EXPANSION_AGENT_PROMPT.md` (separate commit) — Crucible-side coordination.

---

## D073 — Phase 3: per-(indicator, role) threshold-tightening proposer from gated_runs

**Date:** 2026-05-19

**Context.** Crucible's 3,829-cohort gap analysis (`../Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md` Fix #2) flagged the D031 audited threshold table (`forge.enumeration.indicator_thresholds._INDICATOR_THRESHOLD_TABLE`, 2026-05-14) as never re-trained on actual gated outcomes. The 3,411 zero-trade configs in that cohort encode "this threshold range produces nothing on real data"; the 64 high-trade configs (≥10 trades) encode "this range fires usefully." That signal was being discarded.

Forge's own observation reinforced the case: per-iter `prefilter_rejections_by_hypothesis` (D064) shows ~85% of `trend_continuation` and `mean_reversion` candidates are killed by `permutation_test` — a signal-quality filter that tighter thresholds could let pass.

**Decision.** Ship a Phase 3 proposer that:

1. Cross-references the latest `gated_runs` export with Forge's `submissions` table to extract, per (indicator_id, role), the threshold values used by configs with `n_trades ≥ high_trade_floor` (default 10).
2. For each (indicator, role) with ≥ `min_high_trade_samples` (default 5) high-trade configs, proposes a tightened range as the [5th, 95th] percentile envelope of those thresholds.
3. Compares the proposed range to the D031 baseline. If the proposed range FITS inside the baseline → `direction="tighten"` (auto-applicable). If it extends OUTSIDE → `direction="loosen"` (requires operator review, hard rule #4).
4. Writes tightenings to `config/auto_tightened_thresholds.yaml` (shadows D031). Appends loosenings to `OPEN_PROPOSALS.md`.
5. The sampler (`forge.enumeration.indicator_thresholds.sample_threshold_params`) loads the YAML on first call (lru_cache), validates each entry is strictly tighter than D031 (defensive guard against malformed YAML), and prefers the tightened range when present.

**First pass = operator-driven, not in the production loop.** The operator runs `scripts/propose_threshold_tightenings.py` manually after a meaningful gated cohort accumulates, then restarts forge.service. Auto-firing on every iter is a Phase 3.x follow-up — first need to validate the proposer's output quality against the audited D031 baseline.

**Hard rules check:**

- **#1 (grammar operator-owned):** untouched. D031's table is sampler-side calibration, not §3.5 grammar. The YAML shadow is also sampler-side.
- **#3 (never lower Crucible's gate):** N/A — sampler tightening can only restrict the candidate space, not relax Crucible's gauntlet.
- **#4 (auto-tightening can ship; auto-loosening cannot):** preserved BY DESIGN. Proposer writes ONLY tightenings to the auto-apply YAML; loosenings go to `OPEN_PROPOSALS.md` and wait. The sampler-side loader is also defensive — silently skips any YAML entry that would loosen the D031 baseline.
- **#6 (deterministic enumeration):** preserved. Same `(grammar_version, registry_hash, seed, auto_tightenings_yaml_hash)` produces the same enumeration. The YAML enters the determinism contract — operators need to know that running the proposer changes future enumeration, which is the whole point.

**Alternatives considered:**

- **Auto-fire in the production loop on every iter.** Considered. Rejected for first pass: the cohort needs time to accumulate trade-rich samples; running every iter on the same 24-config gauntlet rate would propose noise. Operator-driven is the right cadence until the system is producing dozens of high-trade configs per day.
- **Bayesian shrinkage toward D031 instead of raw percentile.** Considered. Rejected for simplicity in v1 — the 5th/95th-percentile-of-high-trade is conservative enough that we don't need a formal prior. Worth revisiting if D073 produces noisy tightenings.
- **Mutate `_INDICATOR_THRESHOLD_TABLE` in-place at import.** Considered. Rejected: the D031 dict is an operator-audited artifact. Touching it would obscure which ranges came from where. The shadow-file approach (loader prefers shadow when present, falls back to D031) keeps the audit trail clean.
- **Per-hypothesis tightenings as well as per-(indicator, role).** Considered. Rejected for v1: per-(indicator, role) is already coarser than the gauntlet outcomes (the same indicator may have different optimal ranges for different hypotheses). Worth revisiting once v1 produces enough high-trade samples per hypothesis to support the cross-cut.

**Verification:**

- 6 new tests in `tests/unit/test_feedback/test_threshold_proposer.py`:
  - `test_proposes_tightening_when_high_trade_configs_cluster` — 6 high-trade rsi_2 configs at thresholds 8-12 produce a tightening fit inside D031's (5.0, 15.0); zero-trade configs at extreme thresholds (5.5, 14.5) DON't bias the proposal.
  - `test_min_samples_floor_skips_low_evidence` — fewer than min_samples high-trade configs → no proposal (avoids noise).
  - `test_loosening_detected_when_high_trade_outside_baseline` — high-trade configs cluster OUTSIDE the baseline → `direction="loosen"`.
  - `test_yaml_writer_only_includes_tightenings` — tightenings in YAML, loosenings excluded.
  - `test_loosening_writer_appends_to_open_proposals` — loosenings appended to OPEN_PROPOSALS.md with cohort context.
  - `test_empty_gated_runs_returns_no_proposals` — cold-start safety.
- Full pytest suite: **1,097 tests pass** (6 new D073 + 1091 baseline).
- Ruff + mypy strict clean on changed scope.

**Expected operator workflow:**

```
scripts/propose_threshold_tightenings.py
# review the printed tightenings + any loosening proposals in OPEN_PROPOSALS.md
systemctl --user restart forge.service
# next iter uses the new tightened ranges
```

After ≥1 high-trade-rich cohort runs through the gauntlet, expected impact:
- `trend_continuation` + `mean_reversion`: the dominant `permutation_test` killer (~85% of their rejections) should drop as tighter sampling produces more statistically-significant signals.
- `volatility_event` + `regime_arbitrage`: marginal — they already produce most of the high-trade configs, so the percentile envelope shouldn't shift much.
- `relative_value`: minimal — its threshold sampling is overridden by D068/D072 template params, which are separately tracked.

**Action:**

- `src/forge/feedback/threshold_proposer.py` — new module: `ThresholdProposal`, `propose_threshold_tightenings`, `write_tightenings_to_yaml`, `write_loosening_proposals_to_open_proposals`.
- `src/forge/enumeration/indicator_thresholds.py` — `_auto_tightenings` lru_cached loader + `_effective_range` helper; `sample_threshold_params` prefers auto-tightened range when present.
- `scripts/propose_threshold_tightenings.py` — CLI entrypoint (operator-driven first pass).
- `tests/unit/test_feedback/test_threshold_proposer.py` — 6 new D073 tests.
- `pyproject.toml` — `scripts/**` ruff per-file-ignore widened to include `PLC0415` (lazy imports for sys.path patterns).
- `IMPLEMENTATION_DECISIONS.md` D073 (this entry).
- `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 3 row will be marked completed in a follow-up commit.

---

## D071 — Phase 4 multi-exit schema rewrite (Forge-side code, pre-v3-bump)

**Date:** 2026-05-19

**Context.** Per `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 4 and Crucible's 3,829-cohort recommendation (Fix #1), §3.5 S5 is rewritten from "exactly one required exit per hypothesis" to "required-from-set + optional-additions". Operator approved **Option A** (PHASE_4_MULTI_EXIT_DRAFT.md): ship 4 new ExitRule implementations Crucible-side AND the grammar rewrite Forge-side.

This commit is the **Forge-side schema rewrite**, landing AHEAD of the grammar.yaml v2 → v3 bump. The new schema is in place and active; the v3-only exit IDs (`chandelier_exit`, `parabolic_sar_exit`, `target_exit`, `zscore_reversion_exit`) are NOT yet referenced — they'll be added once `crucible_contracts` ships the contracts version bump (`CRUCIBLE_NEW_EXITS_AGENT_PROMPT.md` 9871745).

**Decision.** Restructure `_S5_HYPOTHESIS_EXITS` from `{"required": (...), "forbidden": (...)}` to `{"required_always": (...), "required_from_set": (...), "optional_additions": (...), "forbidden": (...)}`, and update sampler + validator + SearchSpace to match.

New schema per hypothesis (post-D071, pre-v3-bump — uses only existing KNOWN_EXIT_IDS):

| Hypothesis | required_always | required_from_set (sampler picks 1) | optional_additions (0..K) | forbidden |
|---|---|---|---|---|
| trend_continuation | () | (trailing_atr,) [+chandelier, parabolic_sar on v3 bump] | (time_stop,) [+theta_cliff via E1] | (hard_profit_target,) |
| mean_reversion | () | (time_stop,) [+target_exit, zscore_reversion on v3 bump] | () [+iv_crush_exit on v3 bump] | () |
| regime_arbitrage | () | (regime_flip_exit,) | (time_stop,) | () |
| relative_value | () | (convergence_exit,) [+zscore_reversion on v3 bump] | (time_stop,) | () |
| volatility_event | (iv_crush_exit, event_passed_exit) | () | (time_stop,) | () |
| tail_hedge (D066 filtered) | (roll_on_schedule_exit,) | () | () | (hard_profit_target,) |

`K_MAX_OPTIONAL = 2` — sampler picks each optional independently with p=0.5, truncated to 2.

**Sampler `_build_exits` (new):**
1. E1 mandatory (always).
2. `required_always` (always).
3. Exactly one rng pick from `required_from_set` (if non-empty).
4. Bernoulli p=0.5 per optional addition, truncated to K_MAX_OPTIONAL.
5. Dedup (E1 / required_always / optional may overlap).

**Validator `_s5_exits_match_hypothesis` (new):**
1. All `required_always` present.
2. Exactly one of `required_from_set` (or required_from_set is empty).
3. Any exits beyond E1 + required_always + chosen_required must be in `optional_additions`.
4. Optional-additions count ≤ K_MAX_OPTIONAL.
5. No `forbidden`.

**SearchSpace exposes the new derived fields** plus a `s5_required_by_hypothesis` legacy convenience (= required_always + first element of required_from_set) so existing callers / tests during the transition don't break.

**Hard rules check:**

- **#1 (grammar operator-owned):** `config/grammar.yaml` UNCHANGED in this commit. The grammar.yaml bump v2 → v3 (D071 final) waits for Crucible's contracts. The python dict `_S5_HYPOTHESIS_EXITS` IS the cross-hypothesis exit table; it's sampler+validator-side code, not the §3.5 textual grammar.
- **#3 (never lower Crucible's gate):** N/A.
- **#6 (deterministic enumeration):** preserved. Sampler's new random choices (`rng.choice(required_from_set)` + Bernoulli for optional) flow through the same SeedHierarchy. Same `(grammar_version, registry_hash, seed)` produces byte-identical exits.
- **#10 (grammar version bump):** N/A in this commit — `grammar.yaml` is untouched. The version bump v2 → v3 ships in a separate commit alongside `_S5_HYPOTHESIS_EXITS` additions for new exit IDs once Crucible's contracts ship.

**Alternatives considered:**

- **Wait for Crucible's contracts to ship before any Forge-side change.** Considered. Rejected: the schema rewrite + sampler + validator + tests are substantial; landing them in isolation gives a clean rollback boundary if anything goes wrong. The pre-bump schema only references existing exits, so behavior is unchanged from v2 except for the cleaner internal shape.
- **Land the v3 grammar.yaml bump now AND reference the new exit IDs.** Considered. Rejected: configs would attempt to submit `chandelier_exit` etc. which `KNOWN_EXIT_IDS` rejects → Forge validator failures.
- **Mixed-type `required_from_set` (tuples for AND-bundles).** Considered (option discussed in Phase 4 draft Q4). Rejected: operator chose explicit `required_always` field for cleaner schema.

**Verification:**

- 4 new D071 tests in `tests/unit/test_grammar/test_custom_predicates.py`:
  - `test_d071_volatility_event_missing_required_always_fails` — both elements of the 2-element AND must be present.
  - `test_d071_foreign_exit_fails` — exits outside E1+required+optional are rejected.
  - `test_d071_too_many_optional_additions_fails` — K cap (currently skipped — activates once v3 grammar adds wider optional pools).
  - `test_d071_sampler_optional_additions_can_fire_over_seeds` — Bernoulli p=0.5 picks aren't accidentally pinned to never-fire (120 seeds).
- Existing S5 tests updated:
  - `test_s5_mean_reversion_without_time_stop_fails` — assertion updated to match the new `required_from_set: none of [time_stop] present` detail string.
  - `test_s5_required_exits_present_and_forbidden_absent` — sampler-side assertion updated to walk `required_always` + `required_from_set` separately.
- Full pytest suite: **1,100 pass, 1 skipped (intentional, awaits v3 bump)**, 13 deselected (env-broken hook scripts unrelated).
- Ruff + mypy strict clean on all changed scope.

**Action:**

- `src/forge/grammar/custom_predicates.py` — `_S5_HYPOTHESIS_EXITS` schema rewrite + `K_MAX_OPTIONAL=2` constant + `_s5_exits_match_hypothesis` predicate updated.
- `src/forge/enumeration/search_space.py` — `SearchSpace` gains `s5_required_always_by_hypothesis` / `s5_required_from_set_by_hypothesis` / `s5_optional_additions_by_hypothesis`; legacy `s5_required_by_hypothesis` retained for transition.
- `src/forge/enumeration/sampler.py` — `_build_exits` does the rng-driven pick from `required_from_set` + Bernoulli optional additions.
- `tests/unit/test_grammar/test_custom_predicates.py` — 4 new D071 tests + 1 existing S5 assertion updated.
- `tests/unit/test_enumeration/test_sampler.py` — 1 existing S5 assertion updated to walk the new schema.
- `IMPLEMENTATION_DECISIONS.md` D071 (this entry).

**Next steps (separate commits):**
1. Crucible ships the 4 new ExitRule classes + adds them to `KNOWN_EXIT_IDS` + bumps `crucible_contracts` version (`CRUCIBLE_NEW_EXITS_AGENT_PROMPT.md`).
2. Forge bumps `FORGE_EXPECTED_CONTRACT_VERSION`, adds the 4 new exit IDs to `_S5_HYPOTHESIS_EXITS` per the Phase 4 draft mapping, archives `grammar_archive/v2.yaml`, writes new `grammar.yaml` with `grammar_version: v3`, restarts forge.service. **That commit closes Phase 4 / D071-final.**

---

## D071-final — Phase 4 multi-exit grammar v3 bump (closes Phase 4)

**Date:** 2026-05-19

**Context.** D071 (`f79b27a`) shipped the Forge-side schema rewrite (required_always + required_from_set + optional_additions + forbidden) but held the grammar.yaml v3 bump until Crucible's `CRUCIBLE_NEW_EXITS_AGENT_PROMPT.md` shipped. Crucible delivered all four pieces:

- `crucible_contracts efa2d17`: bumped to 1.11.0; KNOWN_EXIT_IDS adds 4 new IDs (total 18).
- `Crucible e2d5869`: 4 new ExitRule classes (ChandelierExit, ParabolicSarExit, TargetExit, ZScoreReversionExit) in `src/optbt/strategy/exits/` + registry wire-up via `build_exit` dispatch.
- ExitRule semantics per the prompt (Wilder SAR, N×ATR chandelier trail, ATR-multiple or pct target, z-score reversion threshold).

This commit closes Phase 4.

**Decision.** Three Forge-side changes:

1. **`config/grammar.yaml` v2 → v3.** Header + `grammar_version` field bumped. The §3.5 rule TEXT is unchanged (S5 schema lives in `forge.grammar.custom_predicates._S5_HYPOTHESIS_EXITS` python-side). Archived `config/grammar_archive/v3.yaml` as a content-match snapshot of the live YAML (loader's `_verify_archive_consistency` validates this).
2. **`FORGE_EXPECTED_CONTRACT_VERSION` 1.9.0 → 1.11.0** in `forge.core.contracts_check`. The CLI startup check (`check_contracts_version`) will now require the contracts package to be at exactly 1.11.x.
3. **`_S5_HYPOTHESIS_EXITS` expanded** with the 4 new exit IDs per the Phase 4 draft mapping:
   - `trend_continuation.required_from_set`: `(trailing_atr,)` → `(trailing_atr, chandelier_exit, parabolic_sar_exit)` — 3-way choice across trend exits.
   - `mean_reversion.required_from_set`: `(time_stop,)` → `(time_stop, target_exit, zscore_reversion_exit)` — 3-way choice across MR exits.
   - `mean_reversion.optional_additions`: `()` → `(iv_crush_exit,)` — MR strategies firing in high-IV regimes get an extra exit option.
   - `relative_value.required_from_set`: `(convergence_exit,)` → `(convergence_exit, zscore_reversion_exit)` — RV configs can now use tunable z-score reversion instead of Crucible's internal convergence logic.
   - regime_arbitrage / volatility_event / tail_hedge unchanged (no new exits applicable to those hypotheses per the Phase 4 design).

**Hard rules check:**

- **#1 (grammar operator-owned):** YES — grammar.yaml CHANGED. Operator approved Phase 4 + Option A in writing earlier this session. v2 → v3 bump is the documented change.
- **#10 (grammar version bump):** preserved. `grammar_version: v2` → `v3` in YAML; v3.yaml archived; pre-commit hook will enforce on subsequent edits.
- **#6 (deterministic enumeration):** preserved. Same triple still produces byte-identical sequence; the new sampler chooses from the wider required_from_set deterministically via rng.

**Alternatives considered:**

- **Postpone the v3 bump until a fresh production run validates the new exits.** Considered. Rejected: the schema rewrite is already live (D071 `f79b27a`), the new ExitRule classes are in Crucible's runner, the contracts package is bumped, the KNOWN_EXIT_IDS validation has the new IDs. Holding back the v3 bump would leave Phase 4 in a half-shipped state with no observable benefit while the operator is online.
- **Reorder: add the optional iv_crush_exit to MR before bumping required_from_set.** Considered. Rejected: the schema design (Phase 4 draft Q3) already accommodates both with K_MAX_OPTIONAL=2; deferring the iv_crush addition wouldn't change the rollout sequence.

**Verification:**

- `crucible_contracts` version: confirmed `CONTRACT_VERSION = "1.11.0"` in `_version.py`.
- `KNOWN_EXIT_IDS`: 18 entries; includes all 4 new IDs.
- ExitRule registry: `chandelier_exit`, `parabolic_sar_exit`, `target_exit`, `zscore_reversion_exit` all imported + registered in `registry.py::build_exit` dispatch.
- Forge: `tests/integration/test_v1_grammar.py::test_v1_grammar_loads` assertion updated v2 → v3.
- Full pytest suite: **1,100 pass, 1 skipped (K_MAX_OPTIONAL cap test — still inactive, max optional_additions per hypothesis = 1 after D071-final, so the cap of 2 still isn't reached).** Ruff + mypy strict clean on all changed scope.
- Grammar archive: `config/grammar_archive/v3.yaml` snapshot matches live `config/grammar.yaml`; `_verify_archive_consistency` will pass at startup.

**Operator-observable behavior post-restart:**

- Sampler outputs configs with **varied `exits` lists** across configs of the same hypothesis. Example trend_continuation distribution across N=1000 configs: ~33% pick `trailing_atr`, ~33% `chandelier_exit`, ~33% `parabolic_sar_exit`; each gets `time_stop` as an optional addition with p≈0.5.
- Crucible gauntlet: configs flowing through pick `build_exit(spec.id, ...)` with new IDs that resolve to ChandelierExit / ParabolicSarExit / TargetExit / ZScoreReversionExit instances; no RunnerError.
- Expected gauntlet effect: trade-count distribution should diversify within each hypothesis. Pre-D071, every trend strategy had the same exit timing; post-D071, three different exit philosophies produce different trade-count and edge profiles. Crucible's 3,829-cohort identified this as the #1 cause of the 89.1% zero-trade rate; we should see that ratio shift over the next 24 hours of gauntlet processing.

**Phase 4 status:** ✅ **CLOSED.**

**Action:**

- `config/grammar.yaml`: header + `grammar_version: v2 → v3`; rule text unchanged.
- `config/grammar_archive/v3.yaml`: snapshot of the live v3 yaml.
- `src/forge/core/contracts_check.py::FORGE_EXPECTED_CONTRACT_VERSION`: `"1.9.0" → "1.11.0"`.
- `src/forge/grammar/custom_predicates.py::_S5_HYPOTHESIS_EXITS`: 4 new exit IDs added to trend_continuation / mean_reversion / relative_value entries.
- `tests/integration/test_v1_grammar.py::test_v1_grammar_loads`: assertion `v2 → v3` updated.
- `IMPLEMENTATION_DECISIONS.md` D071-final (this entry).

**Restart required:** `systemctl --user restart forge.service` to activate v3 grammar + new contract version + expanded sampler.

---

## D074 — Phase 5: sample sizer-mode params + DTE within bucket

**Date:** 2026-05-19

**Context.** Per `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 5 + Crucible's gap analysis #2 (sizer-mode parameter vacuum). Pre-D074:

- `dte_min` always pinned to the §3.5 P2 window's `window_low`; `dte_max` always to `window_high`. Every swing_short config emitted `dte_min=14, dte_max=21` regardless of how many such configs went out per batch.
- `kelly_fraction` and `vol_target_annual` hardcoded to defaults (0.25 and 0.20) in `forge.enumeration.defaults`. Every fractional_kelly config used identical Kelly sizing; every vol_target config used identical vol-target sizing.

Result: configs with otherwise different structural shape collapsed to identical selector / sizer params, defeating D069's param-aware fingerprint when the only varying parameter was the threshold.

**Decision.** Sampler-side variation, no grammar bump:

1. **DTE within bucket** — `_build_selector` samples `dte_min` uniformly from the low half of the §3.5 P2 window and `dte_max` from the high half. The disjoint halves (split at the midpoint) guarantee `dte_min < dte_max` by construction. For swing_short (14, 21), midpoint=17 → dte_min ∈ [14, 17], dte_max ∈ [18, 21]; analogous for swing_mid and swing_long.

2. **Sizer-mode params** — `_build_sizer` conditionally samples mode-specific knobs:
   - `fractional_kelly` mode: `kelly_fraction ~ uniform(0.10, 0.50)` (quarter to half Kelly typical; 0.25 was the legacy default).
   - `vol_target` mode: `vol_target_annual ~ uniform(0.10, 0.30)` (10-30% annualized target; 0.20 was the legacy default).
   - `fixed_risk_pct` mode: both stay at defaults (mode doesn't read them).

`per_trade_risk_pct` already sampled per §3.5 P4 — unchanged.

**Hard rules check:**

- **#1 (grammar operator-owned):** untouched. `grammar.yaml` unchanged. Sampler-side variation only.
- **#3 (never lower Crucible's gate):** N/A — gauntlet gates unchanged; widening sampler diversity, not gate strictness.
- **#6 (deterministic enumeration):** preserved. All new rng calls flow through `SeedHierarchy`. Same triple still produces byte-identical sequence including the new selector / sizer variation.

**Alternatives considered:**

- **Sample dte_min and dte_max independently from the full window with a `dte_min < dte_max` guard + retry.** Considered. Rejected: the disjoint-halves design is cheaper (no retry) and produces a more even distribution across the window.
- **Use the full Kelly range (0.0, 1.0).** Considered. Rejected: full Kelly is widely understood to be over-aggressive on real returns; the [0.10, 0.50] range covers conventional fractional-Kelly variants used in practice.
- **Tie kelly_fraction / vol_target_annual to grammar P-rules.** Considered. Rejected for v3: these are sampler-side knobs that don't need grammar enforcement; the grammar v3 bump (D071-final) is the right moment to add P-rules constraining them if the operator decides to later. Punt to v4 / Phase 7 follow-up.

**Verification:**

- 5 new tests in `tests/unit/test_enumeration/test_sampler.py`:
  - `test_d074_dte_min_strictly_less_than_dte_max` — 100 seeds, the disjoint-halves design holds.
  - `test_d074_dte_window_uses_both_halves` — across 300 seeds with swing_short, dte_min covers ≥3 distinct values in [14, 17] and dte_max covers ≥3 in [18, 21].
  - `test_d074_kelly_fraction_sampled_for_fractional_kelly_mode` — 300 seeds; values within [0.10, 0.50]; ≥5 distinct values.
  - `test_d074_vol_target_sampled_for_vol_target_mode` — 300 seeds; values within [0.10, 0.30]; ≥5 distinct values.
  - `test_d074_fixed_risk_pct_keeps_default_kelly_and_vol_target` — fixed_risk_pct configs unchanged (defaults preserved).
- Full pytest suite: **1,105 pass, 1 skipped, 13 deselected**. Ruff + mypy strict clean on changed scope.

**Expected operator-observable behavior post-restart:**

- Configs of the same hypothesis × dte_bucket × required_from_set choice will now differ in their `dte_min` / `dte_max` (was identical) AND in their mode-specific sizer knobs. Combined with D071 multi-exit, the structural fingerprint (D069) sees significantly more variation per batch.
- `passed_prefilter` should rise modestly as fewer configs hit intra-batch novelty collisions on selector / sizer params.
- Gauntlet `n_trades` distribution should diversify within hypothesis bins — different DTE windows pick different option contracts; different Kelly fractions size differently; different vol_target annualizations vary position size.

**Action:**

- `src/forge/enumeration/sampler.py::_build_selector` — disjoint-halves DTE sampling.
- `src/forge/enumeration/sampler.py::_build_sizer` — mode-conditional kelly_fraction / vol_target_annual sampling.
- `tests/unit/test_enumeration/test_sampler.py` — 5 new D074 tests.
- `IMPLEMENTATION_DECISIONS.md` D074 (this entry).
- `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 5 row marked ✅ (follow-up commit).

**Restart required:** `systemctl --user restart forge.service` to activate.

---

## D075 — permutation_test forward-horizon return comparison

**Date:** 2026-05-19

**Context.** Overnight diagnostic (this session) cross-referenced `pre_filter_logs` × `submissions.config_json -> hypothesis` and found that across all 9,308 historical Forge submissions, **zero `trend_continuation` configs have ever passed `permutation_test`**. Per-iter pattern post-D074: 1,500 trend_cont configs enumerated, ~1,250 rejected by `permutation_test`, 0 reach ranked_top_n. Closes Crucible's `PROMPT_FORGE_GENERATOR_GAPS.md` Ask #1 part b (eb19fea).

**Root cause.** The pre-D075 `permutation_test.apply()` summed underlying returns at **T+0** of the directional-signal activation dates and compared to the permuted distribution. The §3.5 C2 `trend` family contains 10 indicators (donchian, ema, ema_50, ema_cross, macd, momentum_252, returns_12m_skip1, rolling_sharpe, sma, supertrend) — all leading / regime-state indicators whose activation days don't correlate with unusually-high T+0 returns. The test gives them zero credit for the *forward drift* they actually predict.

Mean_reversion's family (bb_pct, keltner_pct, rsi*, zscore_returns) is largely concurrent — fires *because* today's return was extreme — and therefore passes the legacy test naturally. The asymmetry is structural, not a calibration issue.

**Decision.** Three changes:

1. **New calibration field `forward_horizon_days: 5` in `config/prefilter.yaml`.** Loader requires it (no silent default); `_validate_int` enforces `minimum=0`. The 5-day default is one trading week — matches the typical swing_short trade thesis (DTE 14-21, follow-through over ~1 week). 0 preserves legacy behavior.

2. **`PermutationTestCalibration` gains `forward_horizon_days: int`.** Frozen dataclass; `apply_tightening` doesn't touch this field (it's about *what* we test, not strictness).

3. **`permutation_test.apply()` rewritten** to shift activation dates by `horizon` days before reading returns. Dates that land past the data window's end are silently dropped by `feature_cache.returns()` (CrucibleFeatureCache contract). `effective_n` (the in-window post-shift count) is used as the permutation sample size — preserves apples-to-apples comparison. Two new detail keys exposed: `effective_n` and `forward_horizon_days`.

**Hard rules check:**

- **#1 (grammar operator-owned):** untouched. `grammar.yaml` unchanged.
- **#3 (never lower Crucible's gate):** preserved. Pre-filter behavior, not gauntlet gate.
- **#4 (auto-tightening can ship; auto-loosening cannot):** N/A — calibration is neither a tightening nor a loosening in the grammar sense; it's a re-grounding of the test target. Operator-approved this change explicitly before ship (this session).
- **#6 (deterministic enumeration):** preserved. No new RNG calls; date arithmetic is pure.
- **#8 (blessed clock / RNG):** preserved.

**Alternatives considered:**

- **Use a single horizon vs. sweep multiple horizons.** Considered. Rejected for v1 implementation: a single horizon keeps the calibration surface narrow. If the trend pass-rate looks healthy at horizon=5 but mean_reversion regresses, can revisit with per-family horizons later.
- **DTE-bucket-specific horizon (swing_short→5, swing_mid→10, swing_long→21).** Considered. Rejected for first ship: adds calibration complexity before we know the simpler version's effect. Worth a D076 follow-up if the trade-count distribution within trend_continuation skews to one DTE bucket.
- **Compare aggregated [T+1..T+k] returns instead of just T+k.** Considered. The drift over a 5-day window is materially less noisy than a single T+5 return. Decided against for v1 — same-noise comparison is fine because the permutation pool would shift to T+k random samples too, preserving the relative comparison. Worth revisiting if pass-rate at horizon=5 is overly noisy.
- **Replace permutation_test with a fully P&L-aware test (executes the strategy).** Considered. Rejected for v1: that's a substantial rewrite (selector + sizer + exits simulation) and changes the filter's cost from O(K×N) to O(N×trade_simulation). Forward-horizon return is the cheap, defensible compromise.

**Verification:**

- 3 new tests in `tests/unit/test_prefilters/test_permutation_test.py`:
  - `test_d075_details_record_horizon_and_effective_n` — new detail keys present in result.details with expected values.
  - `test_d075_leading_indicator_passes_only_with_horizon` — synthetic signal whose activations predict T+5 returns. With horizon=0 the filter rejects; with horizon=5 it passes. Same data, same seed, two calibrations.
  - `test_d075_dates_past_window_drop_from_effective_n` — boundary handling: activations near window end shift past the data boundary; effective_n reflects the in-window count.
- 1 new assertion in `tests/unit/test_prefilters/test_calibration.py::test_calibration_nested_shape_matches_yaml` — verifies `forward_horizon_days == 5` is loaded from production YAML.
- 1 production code change to `_ReturnsCache.returns()` test stub — silently drops missing dates to mirror CrucibleFeatureCache contract.
- 2 PermutationTestCalibration constructors updated in `tests/invariants/test_phase5_invariants.py` to include `forward_horizon_days=0` (preserves legacy semantics in those reproducibility tests).
- 1 PermutationTestCalibration constructor in `tests/integration/test_batch_reproducibility.py` updated similarly.
- Test sweep on changed scope: **316 pass** (tests/unit/test_prefilters + tests/integration/test_batch_reproducibility.py + tests/invariants). Ruff + mypy strict clean.

**Expected operator-observable behavior post-restart:**

- `prefilter_rejections_by_hypothesis[trend_continuation][permutation_test]` should drop materially below the current ~1,250-per-iter level.
- `ranked_top_n_by_hypothesis[trend_continuation]` should become non-zero on first post-restart iter (likely modest — 10-50 candidates depending on signal quality, not the 100+ that volatility_event sees).
- `passed_prefilter` may decline slightly because the new test is grounded on a more meaningful comparison (forward drift), so noisy-trend configs that happened to land on lucky T+0 days will now fail.
- New telemetry: per-config `details["effective_n"]` and `details["forward_horizon_days"]` available in `pre_filter_logs` for configs that survive to submission.

**Action:**

- `config/prefilter.yaml` — add `permutation_test.forward_horizon_days: 5`.
- `src/forge/prefilters/calibration.py::PermutationTestCalibration` — new int field + loader validation.
- `src/forge/prefilters/permutation_test.py::PermutationTestFilter.apply` — shift target_dates by horizon; use effective_n for sample size; expose new detail keys.
- `src/forge/cli/main.py::_run_one_iteration` — honor the `prefilter_yaml` parameter (was hardcoded to `config_root / "prefilter.yaml"`, silently ignoring `--prefilter-yaml`). Surfaced during D075 test diagnosis; the CLI flag now actually controls calibration.
- `tests/unit/test_prefilters/test_permutation_test.py::_ReturnsCache.returns` — silent drop on missing dates (matches CrucibleFeatureCache contract).
- `tests/unit/test_prefilters/test_permutation_test.py` — 3 new D075 tests.
- `tests/unit/test_prefilters/test_calibration.py::test_calibration_nested_shape_matches_yaml` — assert forward_horizon_days == 5.
- `tests/integration/test_batch_reproducibility.py` — PermutationTestCalibration constructor gains `forward_horizon_days=0`.
- `tests/invariants/test_phase5_invariants.py` — same 2 constructor updates.
- `tests/unit/test_feedback/test_auto_tune.py::_default_calibration` — same.
- `tests/unit/test_cli/test_grammar_cmd.py` — inline YAML fixture gains `forward_horizon_days: 0`.
- `tests/unit/test_submission/test_cli_run.py` — `_permissive_prefilter` fixture (p_value_threshold=1.0 + forward_horizon_days=0) for the one test that requires ≥1 config to flow end-to-end (synthetic feature cache produces ~uniform p-values around 0.5 so production threshold rarely admits anything).
- `IMPLEMENTATION_DECISIONS.md` D075 (this entry).
- `D075_PERMUTATION_TEST_FORWARD_RETURNS_DRAFT.md` — draft proposal that anchored this decision; retained as historical artifact.

**Restart required:** `systemctl --user restart forge.service` to activate.

---

## D076 — 2026-05-20 — Empirical-prior `expected_trades` filter + `pre_filter_logs` audit-gap fix

**Closes Q16. Adjacent to Q17 (does not fully resolve it).**

**Problem.** Q16 diagnostic across 1,213 gated runs (decided 2026-05-15 → 2026-05-20): 77% of submitted configs produce 0 trades in Crucible. The `expected_trades` pre-filter — the §5.3.4 mitigation against the 0-trade flood — rejected only 0 / 16,253 in `pre_filter_logs` (Q16's original headline) and 126-164 / 5000 per batch in `batch_summaries.prefilter_rejections` (corrected during recon). Either reading, the filter caught <3% per batch while ~77% of survivors went on to produce zero trades. Root cause: it measured *indicator activation counts* over the cached window, not actual trades. Threshold-distribution medians for 0-trade vs trading configs were nearly identical (Q16), so threshold strictness wasn't the lever — the filter structurally could not discriminate. Per-hypothesis bias made it worse: it caught 9% of `mean_reversion` (healthy) but 0% of `relative_value` (96.75% zero-trade per Q17).

**Adjacent finding (corrected during recon).** Q16's sidenote claimed "all 9 pre-filters pass every config" based on `pre_filter_logs`. That table only contained survivor rows — `record_pre_filter_logs` was called from `submitter.py` AFTER a successful submission, never from the battery for rejected configs. Real rejection counts have always lived in `batch_summaries.prefilter_rejections` (D062) and `prefilter_rejections_by_hypothesis` (D064). The audit gap is real; the sidenote interpretation was wrong. Closed in this commit alongside the filter rewrite per operator decision (single-PR bundle).

**Decision.** Replace the activations-based estimate with a learned per-`(hypothesis, dte_bucket, directional_family)` posterior P(n_trades ≥ min_trades), Beta-smoothed via the same Beta(1, 10) prior `rejection_weights` uses. Reject when the bucket has ≥ `min_bucket_samples` gated observations AND the posterior is below `min_pass_probability`. Buckets under the sample floor fall back to the legacy activations heuristic so cold-start exploration is preserved. Additionally: extend `pre_filter_logs` with `config_hash` + `forge_batch_id` columns and add a `record_pre_filter_logs_for_rejected` writer so the table truly reflects every config the battery sees.

**Defaults:** `min_pass_probability=0.10`, `min_bucket_samples=20`. The 20-sample floor matches the smallest bucket size where Q17 noticed >90% zero-trade rates; 0.10 rejects buckets whose smoothed pass-rate is below ~10%.

**Why this and not the other Q16 paths:**
- **Q16 path 2 (Crucible-side dry-run endpoint).** Cleaner semantics, but requires a new contracts surface + Crucible-side work + Forge wait. The empirical prior reuses data we already have (gated_runs via `EXPORT_LAYOUT`) and ships entirely in Forge. Path 2 stays viable as a follow-up if the empirical prior misses edge cases the dry-run would catch.
- **Q16 path 3 (heuristic threshold tightening).** Operator-rejected during the closure question — Q16's own analysis showed threshold strictness isn't the discriminant.

**CLAUDE.md hard-rule impact:**
- **#1 (grammar operator-owned):** untouched. `grammar.yaml` unchanged.
- **#3 (never lower Crucible's gate):** preserved. Pre-filter behavior, not gauntlet gate.
- **#4 (auto-tightening can ship; auto-loosening cannot):** the new filter is strictly *more* selective for observed buckets and preserves the old behavior for cold-start, so the worst-case effect on observed buckets is stricter rejection. Auto-tune does NOT yet tighten the new knobs — they're config-only. Auto-tune extension is a follow-up if observed in practice.
- **#6 (deterministic enumeration):** preserved. `compute_trade_rate_priors` is a pure function over `(gated_runs, submissions, registry, min_trades)`.
- **#8 (blessed clock / RNG):** preserved. No new RNG calls; no clock reads.
- **#9 (submission idempotency):** preserved. `pre_filter_logs` PK `(forge_candidate_id, filter_name)` unchanged; rejected-row UUIDs are minted fresh per write so no collision.

**Alternatives considered:**
- **Bucket key `(hypothesis, dte_bucket)`.** Coarser; reaches min_samples faster but blends doomed `relative_value × pairs` with healthy `relative_value × pairs` (none today, but a hypothetical pair-template improvement would be invisible). Rejected.
- **Bucket key `(hypothesis, dte_bucket, directional_indicator_id)`.** Finest; sparse → many cold-start fallbacks. Rejected for v1; revisit if family-level posteriors are too coarse in practice.
- **Reuse `forge.feedback.threshold_proposer` directly.** Different output shape (per-indicator threshold ranges vs per-bucket pass-rate). Same gated-runs source, different consumer. Documented as such.
- **Skip the audit-gap fix in this PR.** Operator chose to bundle so post-deploy Q16 validation has per-config visibility (was the recommended option).

**Verification:**
- 9 new tests in `tests/unit/test_feedback/test_trade_rate_priors.py` — empty cohort, bucket key shape, posterior arithmetic, unknown indicator, corrupt JSON, orphan gated_run, bucket isolation, determinism, frozen dataclass.
- 6 new tests in `tests/unit/test_prefilters/test_expected_trades.py` — empirical-prior rejection, empirical-prior pass, below-sample-floor fallback, no-bucket-data fallback, `relative_value × pairs` Q16 smoke, unknown indicator fallback. Existing 15 tests retained — they exercise the cold-start activations path and pass unmodified.
- 8 new tests in `tests/unit/test_submission/test_pre_filter_logger.py` — survivor populates new columns, survivor back-compat without batch_id, rejected writer skips passed, rejected writer mints unique UUIDs per report, rejected writer populates new columns, empty iterable no-op, all-pass no-op, naive datetime raises.
- Full suite: 1144 passed, 1 pre-existing skip. Ruff + format + mypy --strict clean on changed scope.

**Predicted operator-observable behavior post-restart:**
- New journal line per iteration: `trade_rate_priors: buckets=N below_sample_floor=M min_pass_p=0.10 min_samples=20`.
- `pre_filter_logs` row counts increase materially (rejected configs now logged); existing audits keyed on `forge_candidate_id JOIN submissions` continue to work because survivor rows are unchanged. New audits can use `config_hash` + `forge_batch_id` to slice rejected vs surviving.
- `prefilter_rejections_by_hypothesis[relative_value][expected_trades]` should rise from ~0 / batch to a material fraction (the empirical prior identifies relative_value × swing_short × pairs as a 96.75% zero-trade bucket).
- `expected_trades` rejection counts for `mean_reversion` and `regime_arbitrage` may *fall* (those buckets have healthy posteriors); the filter stops mis-targeting them.
- Downstream: gauntlet queue pressure on `relative_value` configs drops; Crucible's compute and gated-runs storage on hopeless configs both decline. Q17's zero-trade pollution mitigated structurally (does NOT replace Q14's stub-indicator follow-up, which is upstream of this).

**Action:**
- `src/forge/feedback/trade_rate_priors.py` — new module: `BucketKey`, `BucketStats`, `compute_trade_rate_priors`.
- `src/forge/prefilters/calibration.py::ExpectedTradeCountCalibration` — new optional fields `min_pass_probability` + `min_bucket_samples` (defaults 0.10 / 20); loader uses `.get()` so pre-D076 yamls keep loading.
- `src/forge/prefilters/types.py::FilterContext` — new `trade_rate_priors` field with empty default for back-compat.
- `src/forge/prefilters/expected_trades.py` — empirical-prior + activations-fallback `apply()`; new `_bucket_key_for_config` + `_apply_activations_heuristic` helpers; new `mode` / `bucket_key` / `fallback_reason` / `posterior_p_pass` keys in `result.details`.
- `src/forge/cli/main.py` — new `_load_trade_rate_priors` mirroring `_load_hypothesis_weights`; `_run_battery_for_seed` and `_run_one_iteration` thread the priors through; new journal line + `record_pre_filter_logs_for_rejected` call inside the submitter transaction.
- `src/forge/submission/pre_filter_logger.py` — new `record_pre_filter_logs_for_rejected`; survivor-path `record_pre_filter_logs` gains optional `batch_id` kwarg and writes `config_hash` + `forge_batch_id`.
- `src/forge/submission/submitter.py` — survivor call passes `batch_id`.
- `src/forge/submission/__init__.py` — re-export new symbol.
- `src/forge/persistence/schemas.py` — idempotent ALTERs add `config_hash` + `forge_batch_id` to `pre_filter_logs`.
- `config/prefilter.yaml` — `expected_trade_count.min_pass_probability: 0.10` + `min_bucket_samples: 20`.
- `tests/unit/test_feedback/test_trade_rate_priors.py` — new test file (9 tests).
- `tests/unit/test_prefilters/test_expected_trades.py` — 6 new tests for empirical-prior path; `_ctx` gains `trade_rate_priors` kwarg.
- `tests/unit/test_submission/test_pre_filter_logger.py` — 8 new tests for survivor + rejected paths.
- `IMPLEMENTATION_DECISIONS.md` D076 (this entry).
- `OPEN_QUESTIONS.md` Q16 — appended `**Resolution 2026-05-20:** Closed by D076.`
- `STATUS.md` — appended session log entry.

**Restart required:** `systemctl --user restart forge.service` to activate. Forge picks up the new prefilter.yaml + the new module on next iteration; the priors take effect on the next gated_runs-bearing iteration (~1 cycle once exports are read).

---

## D077 — 2026-05-27 — Wire `rv_rank` as regime_filter for `trend_continuation`

**Spec section:** §3.5 R2 (regime gate for trend_continuation)
**Decision:** Expand R2 from `(adx, hurst)` to `(adx, hurst, rv_rank)`. Bump grammar v3 → v4.
**Rationale:** PTS thesis import — "enter trend-following long calls when realized vol is cheap relative to history." Crucible registered `rv_rank` (percentile rank of 21-day realized vol within trailing 252-day window, [0, 100] scale, `volatility` family). The handoff (`Crucible/docs/handoffs/PROMPT_FORGE_RV_RANK_WIRING.md`, 2026-05-27) directs wiring as regime_filter only, not directional.
**Alternatives considered:** (a) Keep R2 restricted to trend_strength indicators only — rejected; operator directive to expand. (b) Create a separate R2b rule for rv_rank — rejected; adds rule count without benefit since R2's predicate function already accepts an extensible set.
**Action:**
- `_R2_TREND_STRENGTH_INDICATORS` renamed to `_R2_TREND_CONTINUATION_REGIME_INDICATORS`, expanded with `rv_rank`.
- `_INDICATOR_THRESHOLD_TABLE` gains `rv_rank` entry: `regime_range=(25.0, 75.0)`, `op_regime="<"` (fire when vol is LOW/cheap), `directional_range=None` (regime-only per handoff §5).
- `is_threshold_skippable` made role-aware: indicators with `directional_range=None` are skipped for directional signals but remain valid for regime_filter. Prevents rv_rank leaking into directional pools for unrestricted hypotheses.
- `_pick_directional_regime_pair` and `_viable_buckets` now exclude regime indicators whose family matches the sizer chain indicator's family (prevents rv_rank + realized_vol C1 collision when vol_target sizer is active).
- `_regime_signal_params` adds `rv_window` and `window` sampling for rv_rank per PTS calibration: `rv_window ∈ {10, 21}`, `window ∈ {126, 252}`.
- Demo registry and test fixture registry gain rv_rank IndicatorMetadata (`family="volatility"`, `lookback=252`).
- Grammar v3 → v4, R2 rule version 1 → 2, v4 archived.

**Files modified:**
- `src/forge/grammar/custom_predicates.py` — constant rename + expansion.
- `src/forge/enumeration/indicator_thresholds.py` — rv_rank threshold entry + role-aware `is_threshold_skippable`.
- `src/forge/enumeration/sampler.py` — role-aware threshold skip, chain-family C1 guard, rv_rank params sampling.
- `src/forge/enumeration/search_space.py` — constant rename import.
- `src/forge/enumeration/_demo_registry.py` — rv_rank IndicatorMetadata.
- `tests/fixtures/strategy_configs.py` — rv_rank in test registry.
- `tests/unit/test_grammar/test_custom_predicates.py` — `test_r2_trend_with_rv_rank_passes`.
- `tests/unit/test_enumeration/test_search_space.py` — updated R2 pool assertion.
- `tests/unit/test_enumeration/test_no_empty_threshold_leak.py` — rv_rank role-skip test + lambda fix.
- `tests/unit/test_enumeration/test_sampler.py` — constant rename import.
- `tests/integration/test_v1_grammar.py` — version assertion v3 → v4.
- `config/grammar.yaml` — v4 header + version + R2 update.
- `config/grammar_archive/v4.yaml` — archive.

---

## D078 — 2026-05-27 — Dynamic universe loader + threshold feedback activation

**Spec section:** sampler `_pick_underlying` (ticker pool); D073 threshold feedback loop
**Decision:** (a) Replace hardcoded 24-ticker `_TIER_1_2_UNDERLYINGS` with `_load_underlyings()` that reads Crucible's `universe_tickers.json` export, falling back to the D033 list when absent. (b) Run `scripts/propose_threshold_tightenings.py` against the latest 1000-run gated cohort.
**Rationale:** (a) Handoff `PROMPT_FORGE_TICKER_EXPANSION.md` — Crucible has bar+chain data for 152 tickers; Forge limits to 24 via hardcoded list. Dynamic loading eliminates drift risk and enables expansion via Crucible's `universe.yaml`. (b) Handoff `PROMPT_FORGE_ACTIVATE_THRESHOLD_FEEDBACK.md` — all D073 preconditions met (round-robin scheduler live 7+ days, gated runs export publishing, export limit raised to 5000).
**Alternatives considered:** (a) Expand hardcoded list to 40+ tickers manually — rejected; creates ongoing maintenance. Read data directory listing — rejected; universe definition should be canonical. (b) Wait for larger export (5000 runs) — unnecessary; 1000 runs sufficient for initial tightening.
**Action:**
- `_load_underlyings()`: reads `~/optbt_data/exports/universe_tickers.json` (Tier 1 + Tier 2), cached for process lifetime, falls back to D033 hardcoded list. Restart to pick up changes.
- `_pick_underlying()` calls `_load_underlyings()` instead of the constant.
- Threshold proposer run: 14 tighten proposals (0 loosen) written to `config/auto_tightened_thresholds.yaml` from a 1000-run cohort.
- 2 new tests for universe loader (fallback + export reading).

**Files modified:**
- `src/forge/enumeration/sampler.py` — `_load_underlyings()`, updated `_pick_underlying()`, imports.
- `tests/unit/test_enumeration/test_sampler.py` — 2 universe loader tests.
- `config/auto_tightened_thresholds.yaml` — 14 tightening entries from proposer run.

**Restart required:** `systemctl --user restart forge.service` to activate both changes.

---

## D079 — 2026-05-27 — Fix `relative_value` zero-trade structural bug (underlying=None)

**Spec section:** sampler `_pick_underlying`
**Decision:** Remove the `if hypothesis == "relative_value": return None` early return. All hypotheses now get a concrete ticker from the Tier 1+2 pool.
**Rationale:** Handoff `PROMPT_FORGE_ZERO_TRADE_STRUCTURAL_BUGS.md` — analysis of 6,407 gated runs shows 8,069 `relative_value` submissions all had `underlying=None`, producing 99% zero-trade. Crucible's `pairs_convergence` template needs a concrete primary ticker to search for pair partners. The original None return was based on the assumption that the template ignores `config.underlying` — the data disproves this.
**Other bugs from the handoff:**
- Bug 1 (tail_hedge): D066 overlay guard already prevents new submissions. The 1,833 legacy configs are historical. No code change needed.
- Bug 3 (regime_arbitrage): D033 `_pick_underlying` already assigns real tickers. The 850 `underlying=None` configs are pre-D033 legacy. No code change needed.
**Action:** Removed `relative_value` early return from `_pick_underlying()`. Updated docstring and construction comment.

**Files modified:**
- `src/forge/enumeration/sampler.py` — removed `relative_value` early return + comment updates.

---

## D080 — 2026-05-28 — Production runs must not silently degrade to the synthetic feature cache

**Spec section:** §5.2 battery / §13 production-quality; `cli/main.py` `_build_feature_cache`
**Decision:** Add a `--require-real-cache` flag to `forge run` (default **off**). When set and Crucible's real feature cache is unreachable, `_build_feature_cache` raises `FeatureCacheUnavailableError` and `_run_one_iteration` returns `"skipped"` (logged loudly) instead of degrading to `SyntheticFeatureCache`. The systemd service (`deploy/systemd/forge.service`) sets the flag. The fallback now logs LOUDLY in every mode, even when degradation is allowed.

**RCA (verified):** After the PC rebooted on 2026-05-28, the service's first iteration logged `prefetch=0.00s, battery=63.58s, passed_prefilter=0`. `prefetch=0.00s` is an unambiguous fingerprint of `SyntheticFeatureCache` (it has no `prefetch_for_batch` hook), and a 63s battery is impossible for the real cache (which takes 17-38 min on the socket). The Crucible writer socket was not yet up during the cold start, so `_build_feature_cache`'s `except FeatureCacheUnavailableError: pass` silently fell back to synthetic. Synthetic returns are pure Gaussian noise uncorrelated with activations, so `permutation_test` rejected ~100% of what `expected_trades` passed -> 0 submissions. The same silent path could equally PASS garbage and submit it. Historical journal scan: 7 such synthetic-fallback iterations clustered on 2026-05-21/22 (matching the "writer socket broken" errors) plus this reboot — i.e. the gap fires on every writer-unavailable event.

**Rationale:** Hard-rule spirit / §13 production quality: Forge must never filter or submit a batch against a cache it knows is meaningless. Default-off preserves offline dev/test flows (no writer socket -> synthetic) and every existing test; production opts in via the service unit. The fallback path is now observable (loud `warning:` to stderr/journal) regardless of the flag.

**Tested (TDD, red->green):** `tests/unit/test_cli/test_feature_cache_fallback.py` (4 tests): `require_real=True` raises when the socket is absent (hermetic via injectable `data_root`); `require_real=False` falls back to synthetic; a production `forge run --require-real-cache` with the cache unavailable SKIPS (exit 0, no inbox files, no `submissions` rows); the default path still submits on synthetic (back-compat guard).

**Files modified:**
- `src/forge/cli/main.py` — `_build_feature_cache(require_real=, data_root=)` (raise-or-warn, no more silent `pass`); `_run_battery_for_seed(require_real_cache=)`; `_run_one_iteration` try/except -> `"skipped"`; `cmd_run` `--require-real-cache` flag threaded to both call sites.
- `tests/unit/test_cli/test_feature_cache_fallback.py` — new.
- `deploy/systemd/forge.service` — ExecStart adds `--require-real-cache`.

**Deployed:** unit edited, `systemctl --user daemon-reload` + restart; flag confirmed active in `ExecStart`.

**Follow-ups (see OPEN_QUESTIONS Q21, Q22):** latent `permutation_test._full_window` calendar/trading-day bug (exposed by the window doubling, not the outage cause); prefetch perf (17-38 min/batch, dominated by ~10k unique-spec computations over the socket, not the window size).

