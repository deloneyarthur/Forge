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

---

## D081 — 2026-05-28 — Grammar-version weighting for the `expected_trades` trade-rate priors (WS1b)

**Spec section:** §5.3.4 / Q16 / D076; `feedback/trade_rate_priors.py`
**Decision:** `compute_trade_rate_priors` gains `current_grammar_version` + `prior_version_weight` (default 0.25). Gated runs submitted under a grammar version other than the current one (resolved via `submissions LEFT JOIN batch_summaries.grammar_version`) contribute to a bucket's Beta posterior at the reduced weight instead of 1.0. `_run_one_iteration` passes `grammar.grammar_version`. Raw counts (`n_total`/`n_pass`/`n_zero_trade`) stay unweighted — they feed the cold-start sample floor + telemetry; only the posterior is weighted. `current_grammar_version=None` reproduces pre-D081 behaviour exactly (all weights 1.0).

**Why weighting, not a hard version cut:** a config built under grammar vN should be judged by vN trade behaviour — D077-D079 are exactly the kind of grammar change that shifts trade rates, so the legacy (pre-v4) cohort's 61.6% zero-trade rate was unfairly suppressing buckets the fixes improved. But a HARD cut to v4-only would make the filter go inert on thin buckets: as of 2026-05-28 only 184 v4 runs have gated, 98% in two hypotheses, and **relative_value/mean_reversion/tail_hedge have ZERO v4 gated runs**. Cutting them to v4-only drops them below `min_bucket_samples` → cold-start activations heuristic (which Q16 showed passes ~everything) → Forge would re-rank and re-submit known-bad relative_value configs *before* having any v4 evidence that D079 fixed them. Down-weighting keeps the legacy signal alive (a bucket with only legacy zero-trade data still scores low) while letting current-version evidence dominate as it accumulates: a bucket with 100 legacy-zero + 10 v4 (6 pass) flips from ~0.03 to ~0.15 posterior.

**Interaction with throughput (Q22):** keeping the filter discriminating (not inert) matters because the §7.3 rate limiter caps *submission rate* but not *submission quality* — an inert filter would let more zero-trade configs rank into the top-200, wasting Crucible backtests. Weighting preserves quality while the v4 cohort fills out.

**Tested (TDD, red->green):** `tests/unit/test_feedback/test_trade_rate_priors.py` +3 tests: v4-scoping raises the posterior for an all-zero-legacy/passing-v4 bucket (exact 5/16.25 vs 5/20); lowers it for a good-legacy/bad-v4 bucket (3/15 vs 9/21); `version=None` matches the unweighted 4/21. Raw counts asserted unchanged. All 9 pre-D081 tests still green (LEFT JOIN + None default = no behaviour change). 23 CLI iteration tests green; ruff + mypy clean.

**Files modified:**
- `src/forge/feedback/trade_rate_priors.py` — `DEFAULT_PRIOR_VERSION_WEIGHT`; version-aware query + weighted posterior.
- `src/forge/cli/main.py` — `_load_trade_rate_priors(current_grammar_version=)` threaded from `_run_one_iteration`.
- `tests/unit/test_feedback/test_trade_rate_priors.py` — +3 tests, +2 helpers.

**Not done (deliberately):** `prior_version_weight` is a function default, not yet a `prefilter.yaml` calibration field — promote it to calibration only if the operator wants to tune it. The effect is small until the v4 cohort fills out (most buckets are still cold-start); its value compounds as throughput improves (Q22).

---

## D082 — 2026-05-28 — Fix `permutation_test._full_window` calendar/trading-day truncation (Q21)

**Spec section:** §5.3.7; `prefilters/permutation_test.py`
**Decision:** `_full_window(start, n_trading_days)` now spans `ceil(n_trading_days * 366/252)` CALENDAR days instead of `n_trading_days` calendar days. `data_history_days` is a trading-session count (~252/yr); treating it as calendar days truncated the permutation null pool. On the 2018 window exposed 2026-05-28 (`data_start_date=2018-01-02`, `data_history_days=2118`) the pool reached only 2023-10-20 — ~2.5 years short — so every config's p-value was computed against a null sampled only from 2018-2023, missing recent regimes. 366/252 over-covers (holidays + leap years); `feature_cache.returns()` drops the surplus dateless days, so over-coverage is free and the fix is a pure function of the registry (deterministic, hard rule #6 — no clock dependency).

**Behaviour change:** production `permutation_test` now samples its null from the full data calendar range, which will shift some p-values (the intended correction). No effect on the existing unit tests: their `_ReturnsCache` sizes returns over N calendar days and the longer window is a superset that `returns()` filters back to the same N.

**Tested (TDD, red->green):** `test_q21_full_window_spans_calendar_extent_of_trading_days` (window reaches >=2026 for a 2118-session span; red showed the 2023-10-20 truncation) + `test_q21_window_unchanged_for_pure_calendar_caller_dates` (superset regression guard). Full permutation suite 19/19, all 230 prefilter unit tests green; ruff + mypy clean.

**Files modified:**
- `src/forge/prefilters/permutation_test.py` — `_CALENDAR_DAYS_PER_TRADING_DAY`; `_full_window` calendar conversion.
- `tests/unit/test_prefilters/test_permutation_test.py` — +2 tests.

**Deploy:** committed; takes effect on the next `forge.service` restart (low severity — not worth interrupting an in-flight prefetch to force).

---

## D083 — 2026-05-29 — Restore §7.3 flow control: exclude D052 sentinels from the rate limit + wire the `inflight_threshold` knob (audit H-1, H-4)

**Spec section:** DESIGN §7.3; CLAUDE.md per-batch step 8
**Decision (operator-authorized via "do the recommended order"):** The 2026-05-29 audit found the §7.3 rate limiter structurally inert: (H-1) `check_rate_limit`'s local gated count included D052 sentinel-flushed rows (`status='gated'` + nil-UUID `crucible_run_id`), so the aging-out of stuck rows silently satisfied the ≥80% throttle — live, 91.6% of `gated` rows were sentinels and the loop never paused while submitting ~26× faster than Crucible decided; (H-4) `forge.yaml`'s `submission.inflight_threshold` parsed into `ForgeConfig` but was never passed to `check_rate_limit`, so the knob was dead and the threshold was only ever the hardcoded default.

This **changes the behaviour of a spec mechanism** (per the audit's instruction not to silently re-fix it). Fixes:
- `rate_limiter.py`: the oldest-batch query now also selects `crucible_run_id`; `local_gated_count` counts a `gated` row only when `crucible_run_id` is non-null AND != the nil sentinel `_SENTINEL_RUN_ID`. Real gates (normal reconcile, `consumer.py:131`, writes the real run id) count; sentinel flushes (`consumer.py:355`) do not. The export-overlap path was already real-only (Crucible's export contains only real decisions). D052's flush is unchanged — it still rolls genuinely-aged rows out of `submitted`; it just no longer masquerades as completion to the throttle.
- `cli/main.py`: `_resolve_run_defaults` now reads `cfg.submission.inflight_threshold` into `_ResolvedRunDefaults` (default `_RUN_DEFAULT_INFLIGHT_THRESHOLD=0.80` when no config); `cmd_run` threads it through `_run_one_iteration` into `check_rate_limit(threshold=...)`.

**Tested (TDD, red->green):** `test_rate_limiter.py` — sentinel-flushed gated rows excluded from `pct_gated` (5 rows, 1 real gate + 3 sentinels + 1 submitted -> pct 0.2, blocked, not 0.8/clear); drift guard asserting `rate_limiter._SENTINEL_RUN_ID == consumer._AGED_OUT_SENTINEL_RUN_ID`. `test_config_threading.py` — `inflight_threshold` resolves from forge.yaml (0.55) and to 0.80 with no config. 21 tests green; ruff + mypy clean.

**Files modified:** `src/forge/submission/rate_limiter.py`, `src/forge/cli/main.py`, `tests/unit/test_submission/test_rate_limiter.py`, `tests/unit/test_cli/test_config_threading.py`.

**Not addressed here (audit follow-ups):** M-7 (sentinel flush also dilutes `promotion_rate`, biasing auto-tune LOOSEN) and the option (b) rolling submission-vs-real-gate ratio remain open; this fix re-couples the throttle to real gates, which is the load-bearing change.

---

## D084 — 2026-05-29 — Revive the §2.1 feedback loop: analyze the most-completed batch, not the just-submitted one (audit H-2)

**Spec section:** DESIGN §2.1 steps 10-11, §8.2/§8.3; `cli/main.py`
**Decision:** In the `--loop` body, `_reconcile_pending_silently` discarded the `BatchFeedback`s from `reconcile_all_pending` (used only for a log line), and `_consume_feedback_after_submit` ran the analyze/propose/promoted-patterns/auto-tune chain on `result.batch_id` — the batch written to the inbox seconds earlier, which is 0-gated, so the join produced 0 matches and the entire learning layer (§2.1 steps 10-11) was inert in autonomous operation. Fix:
- `_reconcile_pending_silently` now returns the `tuple[BatchFeedback, ...]`.
- New pure helper `_select_feedback_target_batch(candidates: Sequence[(batch_id, gated_count)]) -> uuid | None` picks the batch with the MOST real gated outcomes (richest, most-completed signal), or None when none are gated.
- `_run_one_iteration` feeds `[(fb.batch_id, fb.gated_count) for fb in reconciled]` to the selector and passes the chosen batch (not `result.batch_id`) to `_consume_feedback_after_submit`, which now skips cleanly when the target is None.

**Why re-running is safe (no proposal flooding):** `proposal_writer` already has intent-dedup (`proposal_writer.py:198`, built specifically because the §8.4 trigger fires every batch) and `auto_tune` has the cumulative-tightening cap — so analyzing the most-complete batch across iterations until a newer one supersedes it does not flood OPEN_PROPOSALS.md or over-tighten.

**Tested (TDD, red->green):** `test_run_loop.py` — selector picks the most-gated batch; returns None when nothing is gated or the list is empty. 29 CLI/submission/resilience regression tests green; ruff + mypy clean.

**Files modified:** `src/forge/cli/main.py`, `tests/unit/test_cli/test_run_loop.py`.

**Scope note:** the chain still only runs on non-blocked iterations (after a successful submit), matching the pre-fix call site; running feedback on blocked polls too is a separate enhancement, not required by H-2. Target selection uses most-gated as the proxy for "most-recently-completed" (richest signal); exact completion-recency ordering is a future refinement.

---

## D085 — 2026-05-29 — Close cross-restart determinism gaps: fold auto-tightenings + universe into the batch identity (audit H-3, H-7, M-14)

**Spec section:** DESIGN §13.1; **hard rule #6** (deterministic enumeration)
**Decision:** Hard rule #6 requires `(grammar_version, registry_snapshot, seed)` to reproduce the same config sequence, but two external files also steer the sampler and were excluded from the recorded identity: `config/auto_tightened_thresholds.yaml` (D073, feeds `rng.uniform` ranges) and the universe export (D078, feeds `rng.choice` over the underlying pool). The audit proved divergence empirically (49/80 and 60/60 config-hash differences for the same triple). Because `mint_batch_id` hashed only the triple, a proposer rewriting the tightenings YAML (the point of D073) minted the SAME `batch_id` for a genuinely different population — and the SELECT-guarded `_insert_batch_summary` then no-op'd, leaving stale `batch_size`/`submitted_at` and blending two populations' `promotion_rate` (H-7). `batch_summaries` also recorded no `seed` and no input hashes, so batches weren't reproducible from state (M-14).

Fixes:
- `enumeration.auto_tightenings_fingerprint()` (hashes the *validated* tightenings, so YAML comment/formatting churn doesn't move it) + `enumeration.universe_fingerprint()` (hashes the resolved sorted pool) + combiner `enumeration.enumeration_inputs_hash()`.
- `mint_batch_id(..., extra_inputs="")` folds the combined fingerprint into the UUID payload; empty `extra_inputs` reproduces the pre-fix UUID exactly (back-compat — no batch_id churn for callers that don't supply it).
- `BatchContext.enumeration_inputs_hash` (default "") carries it; `batch_summaries` gains `seed BIGINT` + `enumeration_inputs_hash VARCHAR(16)` (idempotent ALTERs) and `_insert_batch_summary` persists both. `_run_one_iteration` computes the fingerprint once and threads it to both `mint_batch_id` and the context.

**Tested (TDD, red->green):** `test_batch.py` — `mint_batch_id` changes with `extra_inputs`, empty is back-compat, `BatchContext` records/defaults the hash. `test_determinism_inputs.py` (new) — toggling the auto-tightenings YAML and the universe export (each with `cache_clear`, simulating a fresh process) changes the respective fingerprint; combiner is deterministic. ruff + mypy clean.

**Files modified:** `src/forge/submission/batch.py`, `src/forge/enumeration/{indicator_thresholds,sampler,__init__}.py`, `src/forge/persistence/schemas.py`, `src/forge/submission/submitter.py`, `src/forge/cli/main.py`, `tests/unit/test_submission/test_batch.py`, `tests/unit/test_enumeration/test_determinism_inputs.py`.

**Note:** the `lru_cache` on both loaders still means a mid-run YAML/export change is only picked up on restart — but the fingerprint is now computed per batch from the cached value, so the recorded identity is correct for whatever the process actually used. Sourcing the universe from `RegistrySnapshot` (which would also resolve H-5 and let it ride `registry_hash`) remains the cleaner long-term path.

---

## D086 — 2026-05-29 — Crash-safe config writes: atomic prefilter.yaml + per-iteration loop guard (audit H-6, M-1)

**Spec section:** DESIGN §5.5, §13.2; `feedback/auto_tune.py`, `cli/main.py`
**Decision:** Two daemon-bricking paths, both fixed:
- **H-6:** `write_calibration_yaml` wrote the live `config/prefilter.yaml` with a plain `path.write_text(...)` — non-atomic. The auto-tuner runs every `--consume-feedback` iteration, and `_run_one_iteration` re-reads that file at the top of EVERY iteration via `load_calibration` (which raises on a truncated/missing-key file). A kill mid-write (OOM/SIGTERM/power loss) → next iteration's load raises → (pre-M-1) uncaught → systemd restart → raise again → permanent 30s crash-loop on the file the tuner tunes. Fix: write to a sibling `.tmp` then `os.replace` (POSIX-atomic same-filesystem), mirroring `proposal_writer._atomic_write`.
- **M-1:** the `--loop` body had no per-iteration exception guard, so any non-`KeyboardInterrupt` error crashed the process into the same systemd restart loop. Fix: wrap `_run_one_iteration` in `try/except` — re-raise `KeyboardInterrupt` (clean SIGINT stop) and `SchemaVersionMismatch` (§13.5 contracts hard-halt, must NOT be swallowed); for any other `Exception`, log loudly to stderr and continue to the next poll (`poll_interval` is the backoff; a persistent error becomes a repeating journal line, not a flapping service).

**Tested (TDD, red->green):** `test_auto_tune.py::test_write_calibration_yaml_is_atomic` — a monkeypatched `os.replace` failure leaves the destination's prior content fully intact (write staged in tmp). `test_run_loop.py` — a transient first-iteration error lets the loop continue and run the second iteration (exit 0, both ran); `SchemaVersionMismatch` propagates (non-zero exit, not swallowed). 34 tests green; ruff + mypy clean.

**Files modified:** `src/forge/feedback/auto_tune.py`, `src/forge/cli/main.py`, `tests/unit/test_feedback/test_auto_tune.py`, `tests/unit/test_cli/test_run_loop.py`.

---

## D087 — 2026-05-29 — Hard-rule-#2 universe read: make the deviation observable + surface the contracts gap (audit H-5)

**Spec section:** **hard rule #2** (all inter-system access via `crucible_contracts`); `enumeration/sampler.py`
**Decision:** `sampler._load_underlyings` (D078) reads `~/optbt_data/exports/universe_tickers.json` with a raw `json.loads`, but that file is not on `crucible_contracts.EXPORT_LAYOUT` — an inter-system read bypassing the contracts surface (hard-rule-#2 deviation), in the hot path of every config's underlying pick.

**Chosen resolution — the audit's sanctioned interim, NOT a revert.** Reverting to the D033 hardcoded list would discard D078's operator-requested dynamic-universe value, and the proper fix (a `crucible_contracts` loader) is a 3-system contract-surface change that belongs in its own coordinated release, not rushed inline. So: keep the dynamic read; make the deviation **observable** (`_logger.warning("universe_uncontracted_read", hard_rule="2", open_question="Q23")`, once per process via the lru_cache); **track** it in OPEN_QUESTIONS Q23; and **surface the contracts gap** via `Crucible/docs/handoffs/PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md` (add `load_universe_tickers_from_export` + an EXPORT_LAYOUT entry, or a `tier_tickers` field on `RegistrySnapshot` per the `universe_min_asof` precedent).

**Why not the full fix now:** the contracts route requires a `crucible_contracts` minor bump that QuantIQ + Crucible also consume; additive + backward-compatible, but a shared-surface change warrants its own focused change + operator awareness (the handoff is that vehicle). When it lands, Forge routes `_load_underlyings` through the helper, drops the warning, closes Q23 — and (Option B) can retire `universe_fingerprint()` since the pool would ride `registry_hash`.

**Tested:** logic is unchanged from D078 (still reads export, falls back to hardcoded) — the existing universe-loader tests (`test_sampler.py`, 132 green) cover it; the added structlog logging is observability, not behavior. ruff + mypy clean.

**Files modified:** `src/forge/enumeration/sampler.py`, `OPEN_QUESTIONS.md` (Q23); plus `Crucible/docs/handoffs/PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md` (Crucible repo).

---

## D088 — 2026-05-29 — Prefetch the full permutation-window returns (audit M-2; revives M-3/M-4)

**Spec section:** §5.3.7; `prefilters/crucible_feature_cache.py`
**Decision:** `permutation_test` builds its null pool from `ctx.feature_cache.returns(full_window)`, but `CrucibleFeatureCache.prefetch_*` only fetched returns for **activation dates** — so `returns(full_window)` (which silently drops unloaded dates) returned just the signal's own fire-day returns, not the market series. The permutation test was therefore comparing the real notional against a pool of ~the same activation returns → meaningless, and **D082 (full-window span) + D075 (forward-horizon) were prod no-ops** (M-3/M-4) because the dates they widened to had no loaded returns. Fix: on first touch of an underlying, prefetch returns for the FULL permutation window (`_permutation_window_dates`, mirroring `permutation_test._full_window`'s 366/252 calendar conversion), gated by the existing `_window_loaded_for` flag so re-prefetch stays io-light. Returns are per-underlying (one series), so the cost is one window fetch per underlying — bounded, not per-spec (modest vs Q22's ~10k activation computes).

**Tested (TDD, red->green):** `test_crucible_feature_cache.py` — prefetch's returns call now requests the full window (≥14 dates incl. the window start, not just the 1 activation date). All 231 prefilter tests green (incl. the 5 io-free/cache-sharing tests, kept passing via the `_window_loaded_for` gate); ruff + mypy clean.

**Files modified:** `src/forge/prefilters/crucible_feature_cache.py`, `tests/unit/test_prefilters/test_crucible_feature_cache.py`.

**Note:** this revives D082/D075 — `permutation_test` now compares against the real return series. It does add a per-underlying window-returns fetch to prefetch (bounded); watch alongside Q22.

---

## D089 — 2026-05-29 — Auto-tune correctness: exclude sentinels from promotion_rate + tighten the D076 primary knob (audit M-7, M-8)

**Spec section:** DESIGN §5.5, §8.2; `feedback/consumer.py`, `prefilters/calibration.py`
**Decision:**
- **M-7:** `_update_batch_summary` computed `promotion_rate = promoted / submitted_count`, where `submitted_count` includes D052 sentinel-flushed rows ('gated' + nil-UUID, but Crucible never decided them). Export-window loss (not candidate quality) thus depressed the rate and could trigger spurious auto-tune LOOSEN proposals. Fix: `consume_batch_results` counts sentinel rows for the batch and passes `promotion_basis = submitted_count - sentinel_count` as the rate denominator (parallels the D083 rate-limiter fix). `submitted_count` is unchanged for `BatchFeedback` (true batch size).
- **M-8:** `apply_tightening` shifted `min_trades`/Jaccard/regime/p-value but left `expected_trade_count.min_pass_probability` untouched — yet since D076/Q16 that posterior threshold is the PRIMARY expected-trades gate for warmed buckets (`min_trades` only governs the cold-start fallback), so a §5.5 tighten was a near-no-op for the filter rejecting ~3,250/5,000 per batch. Fix: tighten raises `min_pass_probability` by `step`, capped at 0.95 (so a tighten can't reject every warmed bucket outright).

**Tested (TDD, red->green):** `test_consumer.py` — sentinel rows excluded from promotion_rate denominator (1 promoted / (3-2 sentinels) = 1.0, not 0.33). `test_calibration.py` — tighten raises `min_pass_probability` and the 0.95 cap holds from near-1.0. 55 tests green (calibration + consumer + auto_tune); ruff + mypy clean.

**Files modified:** `src/forge/feedback/consumer.py`, `src/forge/prefilters/calibration.py`, `tests/unit/test_feedback/test_consumer.py`, `tests/unit/test_prefilters/test_calibration.py`.

---

## D090 — 2026-05-29 — Per-underlying degraded feature-cache response → explicit `data_unavailable` verdict + telemetry (audit M-5, M-6)

**Spec section:** §5.3.6/§5.3.7, §13 (observability); `prefilters/crucible_feature_cache.py`, `prefilters/battery.py`, `prefilters/types.py`
**Decision:** A valid `FeatureBatchResponse` may carry activations but an empty `features` window (thin Tier-2 underlying / transient writer state). Pre-fix, `returns()` returned `{}` and `regime_label()` defaulted **every** date to `"low_vol"`, so `regime_exposure` saw `max_share=1.0` → REJECT and `permutation_test` saw `effective_n=0` → `p=1.0` → REJECT — a *data-availability* failure indistinguishable from a *signal-quality* one (the D080 class, at per-underlying granularity, which D080's SPY-only `probe()` can't catch). The harm is false rejections polluting `pre_filter_logs` + the D076 priors.
- **M-5 detection + verdict:** `_fetch_window_for_dates` now counts populated returns/regimes; a non-empty request that yields zero of both marks the underlying in `_data_unavailable_for` and logs `feature_cache_window_empty` loudly (D080 stance, once per episode). `returns()`/`regime_label()` raise the new typed `FeatureDataUnavailable` for such underlyings; `active_underlying_data_unavailable()` lets the battery short-circuit *before* any filter runs to a `PreFilterReport(data_unavailable=True, passed=False)` (distinct from a signal-quality FAIL). The battery also wraps the filter loop in `except FeatureDataUnavailable` as a safety net.
- **M-6 observability:** `prefetch_for_batch` emits a `feature_cache_prefetch_batch` INFO line (per-underlying returns/regime coverage + which underlyings degraded); the empty-window WARNING plumbs `cache_hits`/`cache_misses`/`window_hash`. The module previously had zero logging.
- **Non-pollution:** `record_prefilter_rejections` buckets `data_unavailable` reports under a distinct `"data_unavailable"` key (not `"unknown"`); `record_pre_filter_logs_for_rejected` skips them entirely.

**Tested (TDD, red->green):** `test_crucible_feature_cache.py` (empty window → flagged + raises; populated window stays available), `test_battery.py` (proactive short-circuit runs no filters; mid-filter raise caught), `test_submitter.py` (distinct bucket, no `"unknown"`), `test_pre_filter_logger.py` (data_unavailable rows skipped). 307 prefilter+submission tests green; ruff + mypy clean.

**Files modified:** `src/forge/prefilters/{types,crucible_feature_cache,battery}.py`, `src/forge/submission/{submitter,pre_filter_logger}.py`, + the four test files.

---

## D091 — 2026-05-29 — Submit-path integrity + contracts-boundary hardening (audit M-10, M-11, M-12, M-13)

**Spec section:** §7.2/§13.4 + hard rule #9; §5.5 + hard rule #4; §13.5 + hard rule #2; D080
**Decision:** four independent integrity/boundary fixes bundled as Batch D.
- **M-10 (submit transaction):** `_submit_one` ran three autocommit statements — INSERT(`pending`) → `submit_candidate` (FS write) → UPDATE(`submitted`). A crash between INSERT and the final UPDATE committed a `pending` row that is **never reconciled** (write-only status; `reconcile_all_pending` selects `submitted`) and permanently held its unique `config_hash` → the candidate could never be resubmitted (`skipped_duplicate` forever) — a hard-rule-#9 break in the crash case. Fix: wrap the three in one explicit `BEGIN/COMMIT`; an uncommitted crash (incl. `KeyboardInterrupt`) hits `except BaseException: ROLLBACK; raise`, freeing the slot. The caught-error path (`submit_candidate` raises) still records the terminal `submission_failed` and COMMITs. The inbox write is idempotent (atomic tmp-then-rename keyed by config_hash) so committing it inside the txn is safe. (Corrects D046's stale "production never writes pending" note.)
- **M-11 (crash-ordering):** `_apply_tighten_and_persist` mutated `prefilter.yaml` *then* wrote the `grammar_versions` audit row. A crash between them left the calibration tightened on disk but unrecorded → the §5.5 cumulative-cap (sums recorded step_pcts) under-counts → silently permits tightening past 30%. Fix: write the audit row FIRST, then the (atomic, D086) YAML — so a crash can only *under*-apply (cap over-counts → conservative).
- **M-12 (contracts check):** `forge feedback` did Crucible I/O with no §13.5 startup `check_contracts_version()` (every other Crucible-touching command had it). Added at the top of `cmd_feedback` — a major mismatch now halts cleanly instead of failing late / mis-parsing.
- **M-13 (loud universe fallback):** `_load_underlyings`'s `except (...): pass` was silent — a present-but-unparseable universe export degraded the pool 152→24 tickers with zero observability (and the `lru_cache` froze it for the process). Fix: emit a `universe_export_unreadable` WARNING (and `universe_export_empty` for a parses-but-empty export), distinct from the expected `universe_fallback_hardcoded` info (file absent / offline). Mirrors D080's loud-fallback stance.

**Tested (TDD, red->green):** `test_submitter.py` (crash mid-write leaves no orphan row + hash resubmittable), `test_auto_tune.py` (audit row persisted before a failing YAML write; YAML untouched), `test_feedback_cmd.py` (mismatch halts before I/O), `test_sampler.py` (malformed export logs the drift WARNING — asserted via `capsys` since the module logger caches past `capture_logs()`). Submission + auto_tune + feedback_cmd + sampler suites green; 9 submit-path integration tests green; ruff + mypy clean.

**Files modified:** `src/forge/submission/submitter.py`, `src/forge/feedback/auto_tune.py`, `src/forge/cli/feedback_cmd.py`, `src/forge/enumeration/sampler.py`, + the four test files.

**Note:** M-10's rollback-on-crash also softens L-10 (transient `submission_failed` no longer the only outcome of a mid-write death), but L-10's explicit retry/reset of *caught* failures stays open for Batch E.

---

## D092 — 2026-05-29 — Batch E: grammar samplability + doc/spec sync + invariant-suite hardening (audit M-9, M-15, M-16, L-1/2/3, L-9, L-15/16, L-20)

**Spec section:** §3.5 R3/S5/C1 + hard rules #1/#10; §7.3 + hard rule #8; §13
**Decision:** a sweep of one Medium-trio + supporting Lows, no production-loop behavior change beyond M-9 and L-9.
- **M-9 (R3 samplability):** added `regime_range`/`op_regime` entries for `days_to_cpi`, `days_to_nfp`, `days_to_opex` to `_INDICATOR_THRESHOLD_TABLE` (mirroring `days_to_fomc`). T1.4/D039 widened R3's event-proximity pool to these macro indicators but never made them samplable — `is_threshold_skippable(ind, 'regime_filter')` returned True, so the ETF-usability widening was inert. New coverage test asserts every `_R3_EVENT_PROXIMITY_INDICATORS` entry is regime-samplable.
- **M-16 (K_MAX_OPTIONAL test):** the lone failure-mode test for the §3.5 S5 optional-exit cap (hard rule #1) `pytest.skip`ped unconditionally and asserted nothing (no shipped hypothesis has >2 optional_additions). Rewrote it to extend a hypothesis's optional pool via monkeypatch, attach 3 optional exits, and assert `_s5_exits_match_hypothesis` rejects with "too many optional_additions". The suite now has 0 skips (was 1).
- **M-15 + L-1/L-2/L-3 (doc sync):** rewrote `GRAMMAR.md` §S5 to the v3 `required_always`/`required_from_set`/`optional_additions`/`forbidden` schema (was stale v2 single-required prose) with a per-hypothesis table matching `_S5_HYPOTHESIS_EXITS`; refreshed §R3 (5 indicators + ETF rejection + `(v2, D039)` marker) and §C1 (11→12 families, `trend_strength`); added the D071-final amendment note to `DESIGN.md` §3.5 S5. Added a content-aware S5 doc-sync **pytest invariant** (asserts every source-table exit id + the v3 vocabulary appear in §S5) — implemented as a test rather than in the stdlib-only `check_grammar_doc_sync.py` hook, which can't import the Python table.
- **L-9 (loop guard):** `forge run --loop` now errors (exit 2) when `crucible_db` is None — the §7.3 rate limiter is the only submission backpressure and was silently skipped, so a no-Crucible-DB loop would submit unthrottled every poll interval. Mirrors the `--inbox` guard. Production (forge.yaml) is unaffected.
- **L-15/L-16 (invariant hardening):** broadened the hard-rule-#8 RNG scan from 2 literal forms to the full construction surface (`random.Random(`, `.seed(`, `np.random.RandomState/Generator/PCG64/SeedSequence`, `secrets.`) as a path-aware allow-list (only `seed.py` exempt); added a positive-control canary meta-test proving the clock/RNG regexes fire on known offenders (+ a negative control). No current violations.
- **L-20 (dead code):** deleted `src/forge/core/config.py` (`load_yaml` had zero production callers; every YAML consumer inlines `yaml.safe_load`) + fixed the `core/__init__` docstring.

**Tested (TDD, red->green where applicable):** new/updated tests in `test_no_empty_threshold_leak.py` (M-9), `test_custom_predicates.py` (M-16 + M-15 content-sync), `test_run_loop.py` (L-9), `test_phase0_invariants.py` (L-15/L-16). 287 grammar+enumeration+run_loop+invariant tests green; ruff clean; mypy clean on 74 src files (was 75 — confirms the deletion broke no imports).

**Files modified:** `src/forge/enumeration/indicator_thresholds.py`, `src/forge/cli/main.py`, `src/forge/core/__init__.py`, `docs/GRAMMAR.md`, `docs/DESIGN.md`; deleted `src/forge/core/config.py`; + the four test files.

**Deferred:** L-10 (explicit retry/reset of caught `submission_failed`), L-4..L-8/L-11..L-14/L-17..L-19, I-2/I-3 — lower-value latent/optional items left in `AUDIT.md` for a future pass.

---

## D093 — 2026-05-29 — Batch F: route the universe read through a blessed contracts helper (audit H-5 / Q23 close; contracts 1.13.0)

**Spec section:** hard rule #2 (all inter-system access via `crucible_contracts`); §13; D078
**Decision:** closed the last uncontracted inter-system read. Forge's enumerator picked every candidate's underlying from `~/optbt_data/exports/universe_tickers.json` via raw `json.loads` — a file not on the `EXPORT_LAYOUT` surface (H-5). D087 made the deviation observable (`universe_uncontracted_read`) and surfaced the gap (`PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md`); this batch lands the fix on both sides.
- **Contracts 1.13.0 (`crucible_contracts` commit `45f2ea0`):** added `load_universe_tickers_from_export(exports_dir) -> tuple[str, ...]` (unions/sorts/dedupes `tier_1`+`tier_2`; `()` when absent; `QueryError` on malformed JSON / non-object payload / malformed tiers — mirrors `load_recent_gated_runs_from_export`) and `universe_tickers*.json` on `EXPORT_LAYOUT.files`. Minor bump (additive, backward-compatible). 7 new loader tests; 100% coverage retained. (Drive-by in that commit: fixed the pre-existing-stale `test_known_exit_ids_size` 14→18 and two ruff lints in `feature_cache.py` so the contracts suite + `ruff check src/` are green.)
- **Forge:** `_load_underlyings` now calls the helper against `_UNIVERSE_EXPORT_DIR` (was `_UNIVERSE_EXPORT_PATH`); dropped the raw `json` read + the `universe_uncontracted_read`/`universe_export_empty` warnings (the read is contracted now). M-13 drift logging is preserved via the helper's `QueryError` → `universe_export_unreadable` + fallback. `FORGE_EXPECTED_CONTRACT_VERSION` 1.12.0→1.13.0; `uv.lock` regenerated. `universe_fingerprint()` (D085) retained (Option A keeps Forge's separate identity fold).

**Tested:** sampler + determinism-inputs (133) green with the 3 universe tests reworked to the dir-based loader; contracts-integration + feedback_cmd (10) green; `forge enumerate` end-to-end smoke passes the 1.13.0 startup check and falls back cleanly with the export absent. ruff + mypy clean. Q23 **CLOSED**.

**Files modified:** `src/forge/enumeration/sampler.py`, `src/forge/core/contracts_check.py`, `uv.lock`, `OPEN_QUESTIONS.md`, + `tests/unit/test_enumeration/{test_sampler,test_determinism_inputs}.py`. Contracts side committed separately in `../crucible_contracts` (`45f2ea0`).

---

## D094 — 2026-05-29 — Multi-class reward weighting: enumerator learns from trade-production + gate-progress, not just promotions (improvement-plan Phase 2)

**Spec section:** §8 feedback; hard rule #6 (deterministic enumeration); `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 2
**Decision:** the per-hypothesis sampling weight fed to the enumerator (`compute_hypothesis_weights`, D063/D067) learned ONLY from promotions: `(alpha + promoted)/(alpha + beta + total)`. With Forge in the designed-for sustained zero-promotion regime (§1.2; 0 promotions across 189 batches / 29,749 gated), every hypothesis collapses to the same trial-count decay `1/(11+total)` floored at 0.05 — i.e. ~uniform coverage with no gradient toward configs that even *trade*. Since the binding Crucible gate is `min_oos_trade_count` (~99.9% of decisions fail it; ~60% of real-decision runs trade zero times), the enumerator had no signal pulling it toward the one thing that must happen before edge can even be measured.

Added `compute_hypothesis_reward_weights` — a graded generalization. Each gated run contributes a reward in [0, 1] instead of a binary promoted flag, and the weight is the Beta-smoothed mean of that reward. Reward blends the two signals that actually vary across hypotheses pre-promotion:
- **trade production** — `run.trade_count >= TRADE_FLOOR` (default 1): "does this hypothesis fire at all" — the highest-information pre-promotion signal.
- **gate progress** — fraction of `gate_results` passed: a continuous "how far down the gauntlet" measure that → 1.0 for a promoted run (the contracts `PromotionDecision` validator guarantees promote ⟹ no failed gate), layering an edge gradient on top of bare trade production.

`reward = 0.6·traded + 0.4·gate_fraction`, with a promotion short-circuit to the 1.0 ceiling; the two weights sum to 1.0 so reward ∈ [0,1] and the smoothed weight stays in (0,1), leaving the D067 exploration floor's semantics unchanged. As promotions appear, gate_fraction → 1.0 for the promoting hypotheses and the signal transitions smoothly from "fires at all" toward "promotes". The shared submissions↔gated-runs join was factored into `_iter_hypothesis_outcomes` (used by both weighters); `compute_hypothesis_weights` is kept behavior-identical and still exported (its 13 tests unchanged). The single production call site (`_load_hypothesis_weights`, `cli/main.py`) now calls the reward weighter; everything downstream (D067 floor, cold-start fallback, journal line, sampler `rng.choices`) is untouched.

**Why this is not a hard-rule-#4 (loosening) or grammar concern:** the change only reallocates *sampling budget* across the canonical hypotheses. It touches no grammar, no gate, no validation, and cannot loosen anything — strictly an exploration-steering input. Reversible by reverting the one call site.

**Determinism (hard rule #6):** the reward weighter is a pure function of the `submissions` table + the `gated_runs` snapshot — same snapshot → same weights, identical to the promotion-only function's property (`rejection_weights.py` module docstring). `test_reward_weights_deterministic` pins it.

**Scope (deliberate, not yet complete):** the plan's `prefilter_killed` / `runner_failed` classes are NOT consumed — they never produce a GatedRun, and down-weighting a structurally-scarce-but-valid hypothesis (relative_value has a single pairs indicator; mean_reversion ~12 structural skeletons) for being prefilter-deduped would worsen the monoculture this is meant to relieve. The D067 floor still guarantees every hypothesis minimum budget. Consuming those classes (from `pre_filter_logs` / Crucible failure records) is a follow-up if the gated-cohort signal proves insufficient.

**Tested (TDD, red→green):** 9 new tests in `test_rejection_weights.py` — the core `test_reward_weights_trading_beats_zero_trading_at_zero_promotions` (a trading hypothesis outweighs a zero-trading one at 0 promotions, AND asserts the promotion-only weighter rates them equal — the contrast that motivates the change), plus promotion-ceiling, gate-progress gradient, unit-interval bound, tunable-knob, orphan-ignored, alpha/beta override, determinism, corrupt-config-skip. Full `test_rejection_weights.py` 22/22 green; ruff + mypy --strict clean on changed scope.

**Files modified:** `src/forge/feedback/rejection_weights.py`, `src/forge/cli/main.py`, `tests/unit/test_feedback/test_rejection_weights.py`.

**Deploy note:** behavior-changing for the live `--loop` sampler; requires a `forge.service` restart to pick up the new code path (weights are recomputed per iteration, but the running process holds the old function). No grammar bump, no contracts change, no migration. Verify-live: after restart, the `hypothesis_weights:` journal line should show non-uniform weights once a batch with traded gated runs is reconciled (regime_arbitrage / volatility_event above relative_value), vs the prior ~flat-at-floor distribution.

---

## D095 — 2026-05-29 — Re-grade the permutation_test ranker sub-score to use the full passing range (ranker-flatness; item 4)

**Spec section:** §6.2 composite scorer; §5.3.7 permutation test
**Decision:** the §6.2 composite was near-flat among submitted survivors — three of its five weighted inputs carried almost no variance (novelty std ~0.000, permutation std ~0.03, prior-promotion identically 0.0), so "top-N of survivors" was barely distinguishable from random. The fixable compression was the permutation factor: `PermutationTestFilter` scored `1 - p_value`, and since passers have `p ∈ [0, threshold=0.10]`, every passer's score landed in [0.90, 1.0] — the 0.15 §6.2 weight contributed a composite range of only ~0.015.

Replaced the sub-score with a threshold-relative map, `_significance_score(p, thr) = clamp(1 - p/thr, 0, 1)`, so the passing range spans the full [0, 1]: a highly-significant passer (p≈0) → ~1.0, a barely-significant one (p≈threshold) → ~0.0. Statistical significance now has real resolution in the ranker. **Pass/fail is unchanged** (`p_value <= p_threshold`); only the [0,1] quality score feeds §6.2. No weight change (so no §6.2 spec deviation) — this is a sub-score refinement.

**Deliberately NOT changed:**
- **novelty** score (`1 - max_temporal_overlap`) is saturated at 1.0 among survivors *by correctness* — the structural-fingerprint dedup (D069) removes exact duplicates first, so survivors genuinely have ~0 temporal overlap. No cheap richer novelty signal exists; forcing variance would fabricate it.
- **signal_density** is already log-graded (`log1p(n)/log1p(10·min)`); its top-saturation reflects most survivors firing well above the floor — real, not a bug.
- **prior_promotion_proximity** is identically 0 only because nothing has promoted; it self-heals when promotions appear (and D094 now steers generation toward trade-production meanwhile).
- **§6.2 weights** themselves: the 0.25 on novelty is effectively wasted in the current regime, but re-weighting is a §6.2 spec deviation; surfaced to the operator as an option rather than applied unilaterally.

**Tested (TDD):** the obsolete `test_score_is_one_minus_p_value` (which would now fail — behavior changed as intended) replaced by `test_score_is_threshold_relative` (integration: filter score == helper) + `test_significance_score_uses_full_passing_range` (unit: 0.0→1.0, threshold→0.0, mid→0.5, failing→clamp, degenerate-threshold→0). 130 prefilter + ranking + phase3/4-invariant tests green; ruff + mypy --strict clean on changed scope. (The `test_perf_rank_and_submit_30_candidates_under_5s` invariant failed at 8.9–14s, but it constructs a hardcoded `FilterResult(score=0.85)` and never invokes the permutation filter — proven independent of this change; the machine was under heavy load: load avg 11.6, ~195 MiB free RAM with forge.service + the suite running. Not a real regression; perf guard left intact rather than loosened to mask load.)

**Files modified:** `src/forge/prefilters/permutation_test.py`, `tests/unit/test_prefilters/test_permutation_test.py`.

**Deploy note:** behavior-changing for ranker ordering (which ~200 of ~277 survivors get submitted); requires a `forge.service` restart to take effect. No grammar/contracts/schema change.

---

## D096 — 2026-05-29 — Funnel instrumentation complement (Forge side): grammar-version slicing + pre-filter funnel export

**Spec section:** §9.1 (`batch_summaries` schema); §2.1 step 10 (analyzer); dispatch `FUNNEL_INSTRUMENTATION_FORGE.md` (Forge complement) aligning with the Crucible-side `FUNNEL_INSTRUMENTATION.md` (the combined pipeline funnel). Hard rules #2 (contracts boundary), #8 (blessed clock), #9 (config_hash idempotency).

**Why:** Crucible's funnel measures grammar iteration from `submitted` onward but is blind to what Forge discards *before* submission — and the pre-filter battery rejects the large majority of candidates (`expected_trades` ~69% in v4). A grammar change that gets its candidates killed at the pre-filter would show up in Crucible's funnel only as "fewer submissions this version," with no cause. This exposes Forge's two upstream funnel stages so the operator can distinguish "grammar produced worse candidates" from "pre-filter wrongly rejected this grammar's candidates," sliced by grammar version.

**Decision — two parts (operator chose "ship A now + propose B"; export to Forge's own dir):**

- **Part A (grammar-version slicing) — interim working path + durable proposal.** Forge cannot stamp `grammar_version` into the submission today: `crucible_contracts.submit_candidate` writes the bare `StrategyConfig` (`queries.py` — `model_dump_json`), and `StrategyConfig` is `extra="forbid"` with no `grammar_version` field (`models.py`). Crucible's funnel Stage 0 expects to read the version from submission metadata (`FUNNEL_INSTRUMENTATION.md` §Stage 0). **Interim:** Forge publishes a `config_hash → grammar_version` join-map (`forge_submission_versions.json`); Crucible joins `runs.config_hash` against it. Well-defined because hard rule #9 unique-indexes `config_hash` → each hash has exactly one batch → one grammar version. **Durable:** a contracts proposal (`CONTRACTS_GRAMMAR_VERSION_PROPOSAL.md`) to carry `grammar_version` in the submission payload *without* changing `config_hash` (exclude it from the hash), matching Crucible's Stage-0 spec as written. The join-map is the bridge until that lands.

- **Part B (pre-filter funnel export).** New `forge.funnel` subpackage aggregates `batch_summaries` per grammar version into the two Crucible `[Forge-opt]` stages — `enumerated` and `survived pre-filters` — plus `rejection_breakdown` (which filter killed the rest) and `enumerated_by_hypothesis` (which grammar branch). Written atomically to `~/forge_data/exports/forge_funnel.json` after each batch.

**Schema (idempotent ALTERs on `batch_summaries`, the D062/D076/D085 pattern):** `enumerated_count BIGINT`, `survived_count BIGINT`, `enumerated_by_hypothesis JSON`. `batch_size` already held the *post-diversifier submitted* count (a later, distinct stage); these add the two stages above it. `len(reports)` and `sum(r.passed)` are recorded by `submit_batch` from the run loop; pre-D096 batches keep NULL and are excluded from the export (with a `coverage` count so the exclusion is never silent), so the funnel invariant holds exactly.

**Load-bearing invariant:** `sum(rejection_breakdown) == enumerated − survived`, per grammar version. Holds by construction (`record_prefilter_rejections` buckets every non-passing report exactly once) and is locked at both the recording layer (`tests/invariants/test_funnel_invariants.py`) and the aggregated product (`test_aggregate.py`).

**Alignment with the Crucible funnel (operator-requested):** export keys match the dispatch JSON exactly (`enumerated`, `survived_prefilters`, `rejection_breakdown`, `enumerated_by_hypothesis`) so Crucible lines up its `[Forge-opt]` stages; primary axis is `per_grammar_version` (their Req 1); `schema_version` is self-describing so their funnel degrades gracefully (their hard rule #7); pure instrumentation, no threshold/grammar changes (their hard rule #5). The one divergence — Stage 0 via join-map rather than payload field — is documented in the handoff and resolved by the contracts proposal.

**Tested (TDD, red→green):** 2 submitter persistence tests + 6 aggregation + 7 export-writer + 1 recording-layer invariant + 1 full-run integration (the run loop actually emits the export, invariant holds on real data). Changed-scope + broad regression: 238 tests green (funnel/submission/invariants/cli/persistence); ruff + mypy --strict clean on changed scope.

**Files:** new `src/forge/funnel/{__init__,types,aggregate,export}.py`; modified `src/forge/persistence/schemas.py`, `src/forge/submission/submitter.py`, `src/forge/cli/main.py`; new tests under `tests/unit/test_funnel/`, `tests/invariants/test_funnel_invariants.py`, `tests/integration/test_funnel_export_integration.py`; handoffs `CRUCIBLE_FUNNEL_FORGE_HANDOFF.md`, `CONTRACTS_GRAMMAR_VERSION_PROPOSAL.md`.

**Deploy note:** the export is refreshed inside the per-batch submit block and is strictly non-fatal (a failure logs and the iteration proceeds; Crucible's funnel degrades gracefully without it). Requires a `forge.service` restart to begin emitting. No grammar bump, no contracts change yet (Part A interim is Forge-only; the contracts proposal is separate, awaiting operator + Crucible). DB picks up the three columns on next open (idempotent ALTER). Coordinate with the Crucible agent (handoff) so their funnel consumes both files.

## D097 — 2026-05-30 — Forward `grammar_version` stamping on submissions + contracts pin -> 1.14.0

**Spec section:** dispatch `FORGE_GRAMMAR_VERSION_STAMPING_PROMPT.md` (Tracks A + B); §7 submitter; hard rules #9/#10; §13.5.

**Decision:** Stamp the live grammar version onto every config the submitter writes to Crucible's inbox, and adopt `crucible_contracts` 1.14.0 (which carries the hash-excluded `grammar_version` field proposed in D096 / `CONTRACTS_GRAMMAR_VERSION_PROPOSAL.md`).

**Rationale:** Crucible's funnel slices runs by the grammar version that produced them. Forge had no way to carry the version on a submission (D096 noted the contracts gap). Contracts shipped the durable field (1.14.0, `StrategyConfig.grammar_version: str | None = None`, excluded from `config_hash`), so the clean forward fix is now available; the interim join-map (D096 Part A) becomes the historical-backfill complement rather than the only path.

**Action:**
- `src/forge/core/contracts_check.py`: `FORGE_EXPECTED_CONTRACT_VERSION` 1.13.0 -> 1.14.0; `uv.lock` regenerated; startup `check_contracts_version()` passes (same-major; the bump is honest pinning per D008/D016/D020/D022/D093).
- `src/forge/submission/submitter.py` (`_submit_one`): `config = config.model_copy(update={"grammar_version": batch.grammar_version})` before `submit_candidate` + `config.model_dump_json()`. Value = live grammar version via `BatchContext.grammar_version` (from `config/grammar.yaml`), so it changes exactly when the grammar does (hard rule #10). Both the inbox JSON and `submissions.config_json` carry it.
- Stamp is applied after the D066 overlay-only early-return (only submitted configs are stamped).

**Hard rule #9 safety:** `config_hash` excludes `grammar_version` (contracts), so the stamp leaves the inbox filename, the `submissions` unique index, and the join-map key byte-identical. Pinned by `test_grammar_version_stamp_preserves_config_hash` in `tests/invariants/test_funnel_invariants.py`.

**Track B note:** the historical join-map (`forge_submission_versions.json`, `build_version_map` + `write_funnel_export`) was already implemented under D096; D097 only adds the forward column. Crucible's resolver prefers per-run column -> join-map -> `pre-instrumentation`.

**Alternatives considered:** (a) post-process the written inbox JSON to inject the key — rejected (bypasses the contracts model / blessed API, fragile). (b) wrap the inbox file in an envelope `{config, grammar_version}` — rejected in the D096 proposal (changes the inbox file format / larger blast radius). The optional hash-excluded field is the minimal change.

**Tests/gates:** 2 forward-stamping unit tests (`test_submitter.py`) + 1 hash-preservation invariant; submission + funnel scope green; ruff + ruff format + mypy --strict clean on changed scope. Full uncontended suite + commit (D096 + D097) + `forge.service` restart are operator-directed (live service holds the DuckDB lock).

**References:** [[D096]] (interim join-map + proposal), hard rules #9/#10, §13.5.


## D098 — 2026-05-31 — v5 grammar: drop regime_arbitrage from enumeration + give relative_value its first fair test

**Context:** Crucible's pre-v5 investigation (DESIGN.md §20: `hypothesis-budget-triage`, `pairs-cross-tier-universe`, 2026-05-31) directed a clean v5 baseline that keeps iterating *within long-options scope* — no spreads/0DTE/scope-class change (hard rule #9 stands). The operator dispatch had six items; this entry covers items 1, 2, 4 (code). Item 3 (keep the productive three: volatility_event/trend_continuation/mean_reversion; tail_hedge stays dropped as an OverlaySpec per hard rule #7 / D066) is the status-quo no-op. Items 5/6 (grammar_version stamping; funnel publishing) needed no new code — D097/D096 already read the version dynamically, so v5 flows automatically. Each item was re-derived against Forge's own enumeration/pre-filter code before acting; the two non-obvious tensions were escalated to the operator via AskUserQuestion (see below).

Live-state confirmation before changing anything (`forge.service` iteration ~262, grammar v4): the journal showed `sampler_attempts: relative_value≈300/batch` but `prefilter_rejections_by_hypothesis: relative_value[expected_trades≈300]` and `ranked_top_n: relative_value=0` — relative_value was enumerated then **100% killed at `expected_trades`, 0 submitted, every batch**. `regime_arbitrage` was ~1148 attempts/batch → ~70 submitted, 90 gated / 0 promoted (~23% of the v4 enumeration budget per `forge_funnel.json`). So both items target empirically-confirmed live behaviour, not a hypothetical.

**Item 1 — drop `regime_arbitrage` from enumeration.** Low-yield *by construction*, not a wiring bug: it routes to the same ComposableLongOptions template as the productive hypotheses, but its mandatory `regime_filter` stacks contradictory regime concepts (momentum_252 trend + rsi_2 mean-reversion + iv_rank vol + expected_value_estimator) that rarely all align → 81% zero-trade, no edge thesis. Implemented as **Forge runtime policy mirroring the D066 `tail_hedge` precedent, NOT a grammar-rule edit** (hard rule #1 — the 21 rules are operator-owned and grammar.yaml S1 still lists all 6 canonical hypotheses; a hand-authored regime_arbitrage config still validates):
- `forge.enumeration.search_space`: new `DISABLED_HYPOTHESES = frozenset({"regime_arbitrage"})` + `NON_ENUMERABLE_HYPOTHESES = OVERLAY_ONLY_HYPOTHESES | DISABLED_HYPOTHESES`.
- The three enumeration-path filter sites now read `NON_ENUMERABLE_HYPOTHESES`: iterator D037 stratification floor (`iterator.py`), sampler `samplable_hypotheses` (`sampler.py`), CLI `_load_hypothesis_weights` floor set (`main.py`). regime_arbitrage now renders in the journal `hypothesis_weights:` line with the `*` prior marker (like tail_hedge), not a live weight. `_HYPOTHESES` / `space.hypotheses` (the canonical set mirroring the contracts `hypothesis` Literal) are unchanged.

**Item 2 — give `relative_value` its first FAIR test.** Two sub-changes, each escalated to the operator because each crossed a previously-shipped decision:
- **2a — underlying reverts to null (reverts D079).** D079 had assigned relative_value a concrete anchor ticker to work around the OLD PairsConvergence path. Crucible commit `4f5271f` now loads all 37 pair legs regardless of tier, retiring the anchor requirement; a single stamped underlying on a pairs config is misleading. `sampler._pick_underlying` returns `None` for `hypothesis == "relative_value"`. **Operator chose "revert → null."** Verified path-(a) holds: relative_value configs with `underlying=None` pass the validator (0 invalid at 5000-config scale).
- **2b — cold-start relative_value out of the stale `expected_trades` prior.** The load-bearing fix. relative_value's `(relative_value, *, pairs)` bucket carries thousands of pre-v5 ~100%-zero-trade gated runs from the now-fixed pairs-loading defect. D081 *down-weights* prior-version data (0.25×) but keeps the raw rows, so the bucket stays ≥ `min_bucket_samples` (20) in empirical-prior mode and its posterior stays far below `min_pass_probability` (0.10) → relative_value stays dead in v5. **Operator chose "cold-start relative_value in v5."** New `cold_start_hypotheses` param on `compute_trade_rate_priors`: for listed hypotheses, prior-version rows are **dropped entirely** (not down-weighted) so the bucket falls below the sample floor → filter cold-starts to the permissive activations heuristic → v5 configs flow, produce now-valid trades, and re-learn the prior honestly. Production policy constant `COLD_START_HYPOTHESES = frozenset({"relative_value"})` in `trade_rate_priors`, threaded via `main._load_trade_rate_priors`. No-op when `current_grammar_version is None` or empty set (pure D081 back-compat).

**Item 4 — grammar version bump v4 → v5.** The load-bearing step so Crucible can run `crucible funnel --compare v4 v5` and attribute the shift to exactly this cleanup. **First version bump with no `rules:` text change** — both item-1/item-2 changes are enumeration policy + pre-filter, not rule edits. `config/grammar.yaml` version field + header comment updated; `config/grammar_archive/v5.yaml` archived byte-identical (loader's archive-consistency check passes); v4.yaml unchanged (still matches HEAD — version-bump hook precondition). `docs/GRAMMAR.md` deliberately untouched: it documents the operator-owned *rules* (unchanged), and the tail_hedge/D066 precedent keeps runtime enumeration policy out of it; the doc-sync hook confirms no change required.

**Hard rules:** #1 preserved (21 rules untouched; regime_arbitrage drop is runtime policy mirroring D066, not a rule edit). #3/#4 N/A (no gate change, no loosening — this is enumeration *scope*). #6 preserved (enumeration deterministic for a fixed `(grammar_version, registry, seed)`; cold-start is a pure function of the gated-runs snapshot). #7 preserved (tail_hedge stays out as OverlaySpec). #9 preserved (no config_hash change). #10 satisfied (version bumped + prior archived + this entry; both grammar pre-commit hooks pass via `.venv/bin/python`).

**Bug caught by the lint gate (worth recording):** the first pass wired `cold_start_hypotheses=COLD_START_HYPOTHESES` at the `main._load_trade_rate_priors` call site but the symbol wasn't imported there (the docstring edit meant to also touch the import block silently failed to match). No test exercises that function's export-read branch, so the suite stayed green — only `ruff`/`mypy --strict` flagged the `F821`/`name-defined`. Fixed by adding `COLD_START_HYPOTHESES` to the local import. Reinforces: run the lint gate, not just pytest, before declaring green.

**Pre-existing test bug fixed in passing:** `tests/integration/test_hook_scripts.py` invoked the grammar hook scripts via `subprocess.run(["python", ...])`, but bare `python` is absent from this host's PATH (`/usr/bin/python3` only), so all 13 hook-script tests errored with `FileNotFoundError` — independent of D098 (proven by stashing every D098 change and re-running on pristine HEAD: still 13 failed). Switched to `sys.executable` (the running interpreter is guaranteed present; the hook scripts are stdlib-only). Bundled into D098 because it was blocking the clean full-suite gate this work needs.

**Verification:** **full uncontended suite 1229 passed / 0 failed** (service stopped to release the DuckDB write lock). 6 new D098 tests (3 sampler, 3 trade_rate_priors) + 2 new phase2 invariants; the 13 hook-script tests now pass via the `sys.executable` fix. ruff check + ruff format --check clean on changed scope; mypy --strict clean on the full 78-file `src/` tree. Both grammar pre-commit hooks pass on the staged v5 bump (run via `.venv/bin/python`; note the framework isn't installed as a git hook here and the hook `entry:` lines use bare `python`, so they're verified manually). E2E smoke on demo registry: 5000 configs across exactly 4 hypotheses (no regime_arbitrage, no tail_hedge), relative_value healthy ~24%, all relative_value `underlying=None` + all others non-None, 0 invalid. (NB this session had severe inline-stdout corruption; every gate was re-verified by capturing to files and reading them.)

**Files:** `config/grammar.yaml`, `config/grammar_archive/v5.yaml` (new), `src/forge/enumeration/search_space.py`, `src/forge/enumeration/iterator.py`, `src/forge/enumeration/sampler.py`, `src/forge/cli/main.py`, `src/forge/feedback/trade_rate_priors.py`, `tests/unit/test_enumeration/test_sampler.py`, `tests/unit/test_feedback/test_trade_rate_priors.py`, `tests/invariants/test_phase2_invariants.py`, `tests/integration/test_v1_grammar.py`, `tests/integration/test_hook_scripts.py` (sys.executable fix), `STATUS.md`.

**Pending (operator-directed gate, same as D094-D097):** stop `forge.service` → full suite uncontended → commit D098 → restart onto v5 (no contracts/schema-breaking change; DB unaffected). Then tell the Crucible agent the new grammar version string is **`v5`** so it can run the version-sliced `crucible funnel --compare v4 v5`. **Reality check (operator; do NOT tune toward recent windows):** v5 is a clean-baseline + relative_value test, NOT a promotion expectation — the gate is full-history-honest (only 3 of 20 current components survive era-stable, ceiling 0.884 « the 2.0 portfolio bar). A grammar change that lifts recent-window trade-rates but not full-history WF is the recency-fit trap.

**References:** [[D066]] (overlay-only precedent for runtime hypothesis exclusion), [[D079]] (reverted by 2a), [[D081]] (down-weighting that 2b extends to dropping), [[D094]] (multi-class reward weighting; floors regime_arbitrage at prior now), [[D096]]/[[D097]] (funnel + stamping that carry v5 automatically), hard rules #1/#6/#7/#9/#10.

## D099 — 2026-06-02 — Percentile-parameterized signal thresholds ("Grammar A"): direction + Crucible-first handoff (NO Forge code yet)

**Context.** Operator dispatch "Grammar A — percentile-parameterize signal thresholds." A 2026-06-02 firing decomposition (Crucible funnel) puts the binding constraint on discovery at signal **firing**, not the gate: ~70% of decided runs never trade. Family split — mean_reversion ~78% *directional*-never-fired (absolute `rsi_2` too tight); trend_continuation ~58% *regime*-gated (`adx`/`hurst` gate too restrictive); volatility_event fires ~every fold. Root cause is Forge-side: the sampler draws **absolute** thresholds via `rng.uniform` over once-on-SPY ranges (`indicator_thresholds.py:419` directional, `:425` regime) and applies them to every ticker, so an absolute threshold fires at an uncontrolled, name-dependent rate. The fix: for raw-unit indicators, emit a **percentile of the indicator's own trailing distribution** instead of an absolute value.

**Two dispatch premises checked before acting (one false, one I mis-scoped — both load-bearing):**
1. *"The percentile fields live in the spec dataclass."* They do **not**. `SignalSpec` (crucible_contracts 1.14.0, `models.py:142-164`) is `id, type, role, indicators, params: dict[str,Any]` — no `use_percentile`/`percentile_window`. Those fields live in a **different, unwired** Crucible class (`optbt/signals/threshold.py`, taking `long/short_threshold` + a `history` series) that is **not** on the SignalSpec path. Consequence: percentile params can only ride as opaque keys inside `params` (so **no contracts change needed**), and Crucible's strategy-path engine must *learn* to read them and fetch a trailing window it never pulls today.
2. *"DESIGN.md §5.2:613 already mandates this (`RSI below the 5th percentile of trailing 252d…`)."* **Crucible was right; I was mis-scoped.** That sentence is **verbatim in *Crucible's* `docs/DESIGN.md` §5.2** ("**Critical**: prefer percentile-based thresholds over absolute", with a `use_percentile` dataclass field beside it), and Crucible's *base* signal implemented it. The dispatch cited *Crucible's* §5.2; I checked *Forge's* `docs/DESIGN.md` — Forge's source of truth, where the concept genuinely is absent ("percentile" appears once, §5.3.7/L470, the permutation test) — and wrongly called the citation nonexistent. **Correct picture:** the percentile-threshold *concept* is a **pre-existing pipeline requirement** (Crucible §5.2 + base signal); what is new is (a) **Forge's enumeration layer** emitting it (it only ever drew absolute thresholds) and (b) the **SignalSpec/strategy-path wiring** — Crucible's base signal had percentile mode, but the strategy-path `ThresholdSignal` that consumes Forge configs did **not**, until Crucible commit `494cf96`. §5.3.3 is amended to point Forge's spec at that adoption, not to invent a new idea. (Lesson: "DESIGN.md" is ambiguous across the two repos; default-reading it as Forge's was the error.)

Also caught: Crucible's strategy-path `ThresholdSignal` does `indicator_params = {k:v ... if k not in ("threshold","op")}` (`optbt/strategy/signals/threshold.py:83-85`), so unknown percentile keys would be **misrouted into indicator construction**, not ignored — emitting them before Crucible handles them is actively harmful, not merely inert. This sharpens the "Crucible-first" requirement beyond the dispatch's framing.

**Three operator decisions (AskUserQuestion, 2026-06-02):**
- **Build order = Crucible-first handoff.** Forge writes the Crucible prompt, Crucible lands + verifies percentile-mode, *then* Forge builds + deploys the v6 emission. Forge does **not** edit Crucible (separate-agent / repo convention; mirrors the `PROMPT_CRUCIBLE_*.md` precedent). No Forge generation code this turn.
- **Scope = binding-constraint only.** Percentile-ize only the diagnosed failures: **mean_reversion directional pool** (§3.5 C2 families `mean_reversion ∪ dealer_positioning`, `custom_predicates.py:151`; the named culprit `rsi_2` lives here) and the **trend_continuation regime gate `adx` + `hurst`** (from `_R2_TREND_CONTINUATION_REGIME_INDICATORS = (adx, hurst, rv_rank)`, `:180` — `rv_rank` **excluded**, it is already a percentile rank by construction). Leave `days_to_*`, `vix_level`/`realized_vol`, `iv_rank`, `rv_rank`, and pairs untouched. This resolves the dispatch's internal contradiction (it listed `days_to_*` to-percentile yet marked volatility_event out of scope — but `days_to_*` ARE volatility_event's R3 gate; and it named `rv_rank` though rv_rank is already-rank).
- **Params contract = percentile in [0,1].** `params = {threshold: <0..1>, op, use_percentile: true, percentile_window: 252}`. Crucible ranks latest vs trailing-N → `[0,1]` via its existing `_percentile_rank` (`optbt/signals/threshold.py:65`, returns `below/n`) and compares with `op`. "rsi_2 in bottom 5%" → `{threshold:0.05, op:"<"}`; "adx in top 30%" → `{threshold:0.70, op:">"}`.

**Crucible feasibility (read-only pass, 2026-06-02) — modest/low-risk.** `IndicatorBase.compute(bars.lazy())` already returns a full polars Series; `_indicator_cache.build_indicator_series_over_period` already builds it then reduces to `dict[date,float]` (just retain the window); `_percentile_rank` already exists; `MarketSnapshot.underlying_bars()` exposes `<=asof` history (no lookahead). Handoff `PROMPT_CRUCIBLE_PERCENTILE_THRESHOLDS.md` written with the exact change path (Option A: don't discard the series in percentile mode), the param-exclusion fix, the insufficient-history guard (`< window//4` → safe default), backward-compat (no `use_percentile` ⇒ byte-identical raw path), and the no-op-until-Forge-emits property that makes it safe to deploy first.

**Deferred Forge build plan (executes only after Crucible confirms live; will be its own Decision + v6 bump):**
- `indicator_thresholds.py` + `sampler.py`: emit percentile params for the in-scope `(indicator, role)` draws; grammar `v5 → v6` (archive + hook + this-style entry; mirrors D098's "version bump, no `rules:` text change" since thresholds are enumeration-layer, not grammar.yaml rules). TDD; deterministic seeded sampling preserved (hard rule #6).
- **OPEN build-time design points to resolve then, NOT now:**
  - *Granularity.* `dealer_positioning` directional is shared with volatility_event (C2, `:157`) and `adx`/`hurst` regime can serve relative_value/tail_hedge (`_build_regime_pool` else-branch, `search_space.py:253`). To honor "don't touch volatility_event" strictly, percentile emission likely needs per-`(indicator, role, hypothesis)` gating (sampler currently passes only `(indicator, role)` to `sample_threshold_params`). Decide: thread hypothesis, or exclude `dealer_positioning` directional from the percentile set, or accept per-`(indicator,role)`.
  - *Auto-tightening reconciliation (D073).* `auto_tightened_thresholds.yaml` + `threshold_proposer` operate in **native units**; a percentile-emitting indicator can't take a native-unit tightening. The `_effective_range` / `_auto_tightenings` / `auto_tightenings_fingerprint` paths and the proposer need a percentile-aware branch or an explicit skip for in-scope indicators.
  - *Per-direction percentile target ranges.* Replace the native-unit `directional_range`/`regime_range` with percentile target ranges (e.g. directional rsi_2 ∈ [0.02, 0.10]; regime adx ∈ [0.60, 0.80]) — calibrated to intent, not SPY data. New `docs/INDICATOR_THRESHOLDS.md` provenance.
  - *Special-cases.* `pairs_zscore` (D068/D072 template params) is out of scope (pairs untouched); `rv_rank` (D077) stays raw. Verify the `_pairs`/`_rv_rank` param-merge paths are not in the percentile set.

**Hard rules.** #1 preserved (the 21 rules are untouched; this is enumeration-layer threshold *encoding* + a runtime/version-policy change, like D098 — grammar.yaml `rules:` text won't change at v6). #2 preserved (no Crucible imports; cross-system change goes via the contracts `params` dict + a handoff prompt, not direct edits). #3 preserved and central (this changes *whether a signal fires*, never the promotion gate). #5 preserved (deterministic Python; no LLM in the loop). #6 to be preserved at build (seeded sampling stays reproducible for a fixed `(grammar_version, registry, seed)`). #9/#10 N/A this turn (no config_hash change; v6 bump happens at Forge-build time with its archive + entry).

**State this turn.** Planning + handoff only — **no Forge production code, no grammar bump, service untouched on v5.** Blocked on the Crucible agent landing + confirming percentile-mode.

**Files (this turn):** `PROMPT_CRUCIBLE_PERCENTILE_THRESHOLDS.md` (new, the handoff), `IMPLEMENTATION_DECISIONS.md` (this entry), `docs/DESIGN.md` (§5.3.3 amendment), `STATUS.md`.

**References:** [[D098]] (the "version bump, no rules-text change" precedent v6 will follow; v5 is the A/B baseline), [[D073]] (auto-tightening machinery the percentile path must reconcile with), [[D068]]/[[D072]] (pairs template params — out of scope), [[D077]] (rv_rank already-rank — excluded), [[D062]] (dealer_positioning as mean_reversion directional — the shared-with-volatility_event subtlety), hard rules #1/#2/#3/#6.

**Crucible response (2026-06-02) — percentile-mode LANDED (commit `494cf96`).** Contract implemented **verbatim** as proposed: `{threshold: float∈[0,1], op: <|<=|>|>=|==|!=, use_percentile: true, percentile_window: int=252}`; `fired = _compare(percentile_rank(window_≤asof, latest), op, threshold)`. Both roles (directional → LONG_CALL/FLAT; regime_filter → allow/deny); warmup (`< percentile_window//4` clean values) → safe default (FLAT / allow=True), deterministic, no lookahead. No-op on raw traffic verified by construction + tests (the ~49k historical configs untouched); no contracts bump; no gate change. **Caveat: committed, not yet deployed** — goes live on the next crucible-runner restart (bundled with their firing-summary/007 deploy); Crucible will confirm "deployed + verified no-op on live raw traffic" after. **Forge deploy-gate (load-bearing):** Forge may BUILD the v6 emission now (contract is locked verbatim → zero rework risk) but must **not flip live emission** until Crucible confirms its runner is deployed on percentile-mode — otherwise the new keys misroute into indicator construction on the still-raw runner (the harm identified pre-handoff). Premise #2 above corrected per Crucible's valid framing point.

**Second cross-repo gate found (2026-06-02) — the feature-cache writer is a SECOND absolute path.** Forge's `signal_density`/`predicted_activations` pre-filters estimate firing via `CrucibleFeatureCache.activation_dates`, which ships the full `SignalSpec` to Crucible's **feature-cache writer** (`optbt/persistence/feature_cache.py`: `compute_activation_dates`→`_build_predicate`→`_threshold_predicate`) — a code path **separate** from the strategy-path `ThresholdSignal` that `494cf96` fixed, and still a raw absolute compare that **ignores `use_percentile`** (verified: `feature_cache.py` is not in `494cf96`'s changeset). So if Forge emitted percentile configs now, the writer would compare `0.05` as an absolute against `rsi_2∈[0,100]` → ≈0 activations → `signal_density` rejects **every** percentile config pre-submission → v6 strictly **worse** than v5. **Deploy is now DOUBLE-GATED**: needs both `494cf96` (strategy path, pending restart) AND a new feature-cache-writer percentile fix. Second handoff written: `PROMPT_CRUCIBLE_PERCENTILE_FEATURE_CACHE.md` (exact fix scoped: exclude `use_percentile`/`percentile_window` in `_strip_predicate_params`; add a windowed `percentile_rank` branch in `compute_activation_dates` reusing `optbt/signals/percentile.py`; warmup `< window//4` → no-fire). **Forge build scope grows:** Forge's own `SyntheticFeatureCache` (`prefilters/feature_cache.py`) must mirror the same percentile-awareness so the battery/integration tests model percentile firing faithfully (the `sample_threshold_params` unit tests don't need it; the battery tests do). Emission code may still be built now (contract locked) but stays undeployed until both Crucible changes are live.

**Operator decisions (2026-06-02, AskUserQuestion round 2):** (a) **build v6 now, deploy-gated**; (b) **scope = exclude dealer_positioning directional** — percentile-ize the `mean_reversion`-family directional indicators (`rsi_2`, `rsi_14`, and any same-family additions: `rsi`/`zscore_returns`/`bb_pct` if the live registry carries them as `mean_reversion`) + the `adx`/`hurst` trend regime gate; leave dealer_positioning directional, `rv_rank`/`iv_rank` (already-rank), and the whole `volatility_event` indicator set absolute. Registry fact grounding the safety: `mean_reversion`-family directional indicators are sampled only by the `mean_reversion` hypothesis (regime_arbitrage disabled), and `adx`/`hurst` are `trend_strength` family = regime-only (in no hypothesis's directional pool) and not in `volatility_event`'s R3 regime gate — so the `(indicator, role)` allowlist cannot leak into `volatility_event`, with **no** change to the seeded-sampling path (hard rule #6 intact).

**Forge v6 emission BUILT + verified (2026-06-02) — code complete, undeployed (deploy-gated on both Crucible changes), uncommitted (operator gate).** Landed as one coherent unit:
- `indicator_thresholds.py`: two optional fields on `IndicatorThresholdSpec` (`directional_percentile_range`, `regime_percentile_range`, both `(low, high)` in [0,1]); populated for `rsi_2`/`rsi_14`/`rsi`/`zscore_returns`/`bb_pct` directional `(0.05, 0.20)` op `<` and `adx` `(0.25, 0.50)` op `>` / `hurst` `(0.50, 0.75)` op `<` regime; new `_percentile_params` helper emits `{threshold∈[0,1], op, use_percentile: True, percentile_window: 252}` via the **same single `rng.uniform`** draw as the absolute path (RNG sequence unchanged — only the emitted value + 2 keys differ → v6 configs differ from v5 in exactly the threshold encoding, a clean A/B); new `is_percentile_emitting` helper; percentile branch **bypasses** `_effective_range` (D073 reconcile).
- Grammar `v5 → v6`: label-only, **no `rules:` text change** (D098 pattern — enumeration-layer, not a rule edit); `grammar_archive/v6.yaml` byte-identical; loader archive-consistency + the doc-sync hook both pass; the version-bump hook is satisfied (prior `v5.yaml` == HEAD).
- **No synthetic-cache or proposer change needed** (verified by reading): `SyntheticFeatureCache.activation_dates` is param-agnostic (per-`signal_id` synthetic density, never inspects threshold/op), so percentile configs are not spuriously rejected in tests; and the D073 loader's baseline check (`p_low >= native_low` → rejects a [0,1] proposal) plus the `_effective_range` bypass already keep native tightenings out of percentile space.

**Verification:** new `tests/unit/test_enumeration/test_percentile_thresholds.py` (12 cases incl. the `volatility_event`-never-percentile + `mean_reversion`-rsi-does sampler invariants, [0,1]-bound, determinism, op-preservation, threshold-key-present) RED (ImportError on `is_percentile_emitting`) → GREEN; **full unit suite 1090 passed**; the affected enumeration + invariants (incl. §13.1 byte-determinism / hard rule #6) + `test_v1_grammar` (now asserts `v6`) + feedback `trade_rate_priors` = 336 passed; ruff check + ruff format --check + mypy --strict clean on changed scope. (All gates captured to files + read — this session had the recurring inline-stdout corruption.)

**OQ filed:** Q26 — `hurst`'s regime gate op is `<` (allow when hurst low = mean-reverting), which looks backwards for `trend_continuation` and may itself feed the over-gating. v6 percentile-izes hurst **preserving the op** (still loosens the gate regardless of direction), so v6 does not depend on it; flipping the op is a separate operator-owned grammar decision, surfaced not silently changed (CLAUDE.md).

**Remaining to deploy:** (1) Crucible confirms BOTH percentile paths live (strategy `494cf96` + the feature-cache writer); (2) operator-directed full-suite-uncontended gate → commit D099 + v6 → `forge.service` restart onto v6 → `crucible funnel --compare v5 v6`.

**DEPLOYED + VERIFIED 2026-06-03 ~08:44 PDT.** Both Crucible paths confirmed live (`494cf96` strategy path; `3c57fb4` feature-cache writer — `use_percentile` read + `{use_percentile, percentile_window}` added to the `_strip_predicate_params` exclusion set; also `c2dd1b7` fixed a Crucible db-writer restart crash loop). Deploy: stopped `forge.service` → **full uncontended suite 1239 passed** → committed **`f5710b9`** to `main` (version-bump + doc-sync hooks pass on the staged v6) → `reset-failed` + restart onto v6. Verified live at loop iteration 317: `grammar_version=v6`, registry from export, `NRestarts=0`, `ExecMainStatus=0`, clean startup, reconciled 166 batches. Standalone emission proof on the deployed code (real registry, 4000 samples): 661 `mean_reversion` directional signals percentile-emitting (e.g. `rsi_14 → {threshold:0.0821, op:"<", use_percentile:True, percentile_window:252}`), **0 / 2843** `volatility_event` signals carry `use_percentile` (untouched-archetype invariant holds live). First *submitted* v6 batch lands after iteration 317's ~38-min prefetch; `crucible funnel --compare v5 v6` becomes meaningful once a v6 cohort gates. Follow-up docs commit per the D098 two-commit pattern.

## D100 — 2026-06-03 — v7 grammar: hurst regime-op fix (Q26) + mean_reversion expected_trades cold-start

**Context.** v6's first live batch (loop iteration 317) gave two clean read-outs. (a) The percentile firing fix WORKS: trend_continuation flowed at 98 submitted (up from its v5 struggle) and mean_reversion configs now PASS `signal_density`. (b) Two residual blocks surfaced, both fixed here and shipped together as **v7** — orthogonal by hypothesis (hurst→trend_continuation regime; cold-start→mean_reversion `expected_trades`), so `crucible funnel --compare v6 v7` still attributes each. No `rules:` text change (hard rule #1 intact) — enumeration-layer + feedback, like v5/v6. Operator greenlit the Sharpe-lever sequence + "ship as ready"; this is the first two ships (hurst was confirmed earlier; the cold-start was operator-confirmed this session).

**Part 1 — hurst regime-op fix (resolves Q26).** trend_continuation's `hurst` regime gate used the default `op_regime="<"` — it opened when hurst was LOW (mean-reverting), the opposite of the hypothesis's thesis (trend_continuation rides trends → wants HIGH hurst). A regime gate pointed at the wrong regime structurally suppresses co-firing with the trend directional signal (entry = directional ∩ regime), a plausible contributor to Crucible's "trend_continuation most-emitted, barely-survives" (their Artifact 1). Fix: `hurst` entry gets `op_regime=">"` (allow when TRENDING) + `regime_percentile_range=(0.25, 0.50)` (allow ~top 50-75%, mirroring `adx`). hurst's SEPARATE `mean_reversion` DIRECTIONAL use (`op_directional="<"`, fire when mean-reverting) is correct and untouched — only the regime op moved. Enumeration-table change in `indicator_thresholds.py`, not a §3.5 rule (R2 only pins which indicators may gate, never the op).

**Part 2 — mean_reversion `expected_trades` cold-start.** The same batch killed 100% of mean_reversion at `expected_trades` (923 rejected, 0 submitted) — and with **zero** `signal_density` rejections, so the percentile configs DO fire (≥30 activations); they died at the *empirical-prior* filter. mean_reversion's prior is poisoned by its pre-v6 absolute-threshold cohort (rarely fired → rarely traded → P(trades)≈0), and v6 changed the firing behavior out from under that prior — the identical poisoned-prior deadlock relative_value hit (D098). Fix: add `mean_reversion` to `COLD_START_HYPOTHESES` → its pre-v7 rows drop from the prior → bucket falls below `min_bucket_samples` → the filter cold-starts to the activations heuristic (live, percentile-aware firing) → v6/v7 mean_reversion configs flow → gate → re-populate the prior honestly. **Operator-confirmed** (same data-policy call as D098's relative_value, after a walkthrough of the mechanism). Low-risk per hard rule #3: removes only the stale Forge-side block; Crucible's gate + `signal_density` still catch genuinely-low-trade configs.

**Hard rules.** #1 preserved (21 rules untouched; both parts are enumeration-table / feedback-policy, like v5/v6). #3 preserved (neither lowers Crucible's gate — Part 1 changes WHICH regime a config trades; Part 2 changes whether FORGE submits, not whether Crucible promotes). #6 preserved (hurst op flip keeps the same single `rng.uniform` draw; cold-start is a pure function of the gated snapshot + current version). #10 satisfied (v6→v7 bump + `v7.yaml` archived byte-identical + this entry; loader + doc-sync + version-bump hooks all pass).

**Verification (TDD).** 2 new tests RED→GREEN: `test_hurst_regime_op_is_trending_but_directional_unchanged` (regime op flips to ">", directional stays "<" + absolute), `test_d100_mean_reversion_and_relative_value_are_cold_started`. Full uncontended suite **1241 passed / 0 failed** (service stopped to release the DB lock; +2 over v6's 1239 = the two new v7 tests). ruff + ruff format + mypy --strict clean on changed scope. `v7.yaml` byte-identical; loader + doc-sync + version-bump hooks pass.

**Files:** `src/forge/enumeration/indicator_thresholds.py` (hurst op), `src/forge/feedback/trade_rate_priors.py` (COLD_START_HYPOTHESES), `config/grammar.yaml` + `config/grammar_archive/v7.yaml` (v7 bump), `tests/unit/test_enumeration/test_percentile_thresholds.py`, `tests/unit/test_feedback/test_trade_rate_priors.py`, `tests/integration/test_v1_grammar.py` (v7 assert), `OPEN_QUESTIONS.md` (Q26 resolved), `STATUS.md`, `PROMPT_CRUCIBLE_SHARPE_LEVERS.md` (Crucible response handoff).

**References:** [[D099]] (v6 percentile — this completes its mean_reversion half + corrects its hurst-regime op), [[D098]] (the cold-start mechanism + relative_value precedent), [[D076]]/[[D081]] (expected_trades empirical prior + version-weighting), Q26 (resolved), hard rules #1/#3/#6/#10.

**DEPLOYED + VERIFIED 2026-06-03 ~11:12 PDT.** Stopped service → full uncontended suite **1241 passed** → committed **`814dad5`** to `main` (both grammar hooks pass) → reset-failed + restart onto v7. Verified live at loop iteration 318: `grammar_version=v7`, registry from export, `NRestarts=0`, `ExecMainStatus=0`, clean startup, reconciled 167 batches. Standalone emission proof on the deployed code: hurst regime `op=">"` + percentile (thr 0.4611 ∈ [0.25,0.50]); hurst directional unchanged (`op="<"`, absolute, no use_percentile); `COLD_START_HYPOTHESES = {mean_reversion, relative_value}`. **Watch on the first post-restart batch** (iteration 318, ~45-min prefetch): `ranked_top_n_by_hypothesis: mean_reversion` should rise from **0** (its v6 value — 100% killed at expected_trades) to **non-zero** — the empirical confirmation that the cold-start unblocked v6's mean_reversion firing fix. Next queued ship (greenlit, ship-as-ready): **#4 Sharpe-aware feedback**.

## D101 — 2026-06-03 — Sharpe-aware feedback reward (generation-objective realignment; Crucible Sharpe-lever #4)

**Context.** Crucible's v5 Sharpe diagnosis flagged "generation optimizes (return, max_drawdown), gate is WF-Sharpe-median" (their #4). Re-derivation **refuted the mechanism** — Forge has no optimizer/NSGA/sweeper (that was Crucible reading its own demo `sweeper.py`); Forge is enumerate→prefilter→rank→feedback. But the **gap is real**, reframed: Forge's per-hypothesis feedback reward (`compute_hypothesis_reward_weights`, D094) was **Sharpe-blind** — `0.6·traded + 0.4·(generic fraction of gates passed)` — and `walk_forward_sharpe_median` was already in the gated-run export + extracted by the analyzer (`HypothesisMetrics.avg_sharpe`) yet **never used**. So the gradient hill-climbed "fires + passes the easy Calmar/DD gates" and ignored the failing Sharpe axis (the Forge analog of Crucible's fingerprint). Operator greenlit, ship-as-ready. FEEDBACK change, not grammar — **no version bump** (D094 precedent); it shifts hypothesis sampling weights over time.

**Change.** `_run_reward` gains a Sharpe-proximity term: `reward = 0.5·traded + 0.2·gate_fraction + 0.3·sharpe_proximity` (promotion short-circuits to 1.0). `sharpe_proximity` = `walk_forward_sharpe_median` linearly ramped 0.0→2.0 (the §8.7 WF-Sharpe-median gate threshold) and clamped to [0,1]; **credited only for runs that traded** (a non-trading strategy's Sharpe is meaningless) and **0 when the metric is absent** (no crash, no inflation). The D094 split was reseated 0.6/0.4 → 0.5/0.2/0.3: gate_progress (a generic, Sharpe-blind pass-fraction) cut 0.4→0.2 to seat the 0.3 Sharpe term; trade-production 0.6→0.5 stays the dominant basic signal. Three weights sum to 1.0 → reward ∈ [0,1], `apply_exploration_floor` semantics unchanged. No contract change (data already in `gated_run.run.metrics`); CLI call site uses defaults so it auto-adopts on restart.

**Diversity guard.** The Sharpe tilt cannot starve a hypothesis: the D067 exploration floor (0.05) + the Beta prior (~0.091 for no-data) guarantee every canonical hypothesis a minimum budget. Critical right now — mean_reversion was just cold-started (D100/v7) and has ~no gated Sharpe data yet (sharpe term = 0), so the floor + trade-production term keep it sampled while its v7 configs gate and accrue Sharpe, after which #4 weights it on realized quality. Live confirmation: v7's first batch took mean_reversion 0 → 142/200 submitted, so the Sharpe data is now accruing.

**Hard rules.** #1 N/A (no grammar/rule change). #3 preserved — steers WHICH hypotheses Forge enumerates more (toward the gate-relevant Sharpe axis), never lowers Crucible's gate; anchoring normalization at the gate's 2.0 threshold is gradient-steering toward passing, not gate-tuning. #5 N/A (deterministic Python, no LLM). #6 preserved (pure function of the submissions + gated-runs snapshot, like D094).

**Verification (TDD).** 4 new tests RED→GREEN (`test_reward_weights_higher_sharpe_outweighs_lower`, `_sharpe_only_credited_when_traded`, `_missing_sharpe_metric_no_credit`, `_sharpe_clamped_to_unit`); 4 existing D094 value-assertions updated for the reseated split (inequalities unchanged); `_gated_run_graded` gains a `wf_sharpe` param. 26 reward tests pass; full uncontended suite **1245 passed / 0 failed** (+4 over v7's 1241 = the new Sharpe tests). ruff + ruff format + mypy --strict clean on changed scope.

**Files:** `src/forge/feedback/rejection_weights.py`, `tests/unit/test_feedback/test_rejection_weights.py`, `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`.

**References:** [[D094]] (the multi-class reward this generalizes), [[D067]] (the exploration floor = the diversity guard), [[D100]] (mean_reversion cold-start — #4 weights its accruing Sharpe data), [[D099]] (v6 percentile), `PROMPT_CRUCIBLE_SHARPE_LEVERS.md` (cross-system framing; #4's mechanism corrected there), hard rules #3/#6. Next queued: #1a mandatory stop on vol_event (§3.5 S5), #1b/#3 mandatory 2nd vol-regime gate.

**DEPLOYED + VERIFIED 2026-06-03 ~13:03 PDT.** Stopped service → full uncontended suite **1245 passed** → committed **`a5de187`** to `main` → reset-failed + restart. Verified live at loop iteration 320: `grammar_version=v7` (unchanged — #4 is feedback, not grammar), `NRestarts=0`, `ExecMainStatus=0`, clean startup, reconciled 169 batches. **#4 effect live in the `hypothesis_weights:` line:** shifted from the trade+gate-only signal (≈ trend 0.61 / vol_event 0.51 / mean_rev 0.54) to the Sharpe-aware reward — **trend_continuation=0.449, mean_reversion=0.395, relative_value=0.377, volatility_event=0.368** (vol_event now lowest of the active set, consistent with its mixed/low survivor Sharpe + the Calmar-passes/Sharpe-fails down-weighting). D067 floor + prior intact (regime_arbitrage/tail_hedge at 0.091*; all active hypotheses ≫ the 0.05 floor — no starvation). The full read on whether the tilt helps comes as the v7+#4 cohort gates (`crucible funnel`, and whether higher-Sharpe regions get more budget). Two-commit docs follow-up.

## D102 — 2026-06-04 — v8 grammar: horizon-matched DTE (Forge-owned signal-horizon table)

**Context.** Crucible's horizon-matched-DTE handoff (`FORGE_HANDOFF_dynamic_dte.md`, 2026-06-04) asked Forge to DERIVE each strategy's DTE from its signal horizon — `DTE_target = k · signal_horizon(config)`, snapped to a discrete bucket — instead of sampling DTE blind, with `k ∈ {2,3,4}` as the remaining knob. The handoff (Crucible-side, explicitly "re-derive the Forge mechanism from Forge code") assumed a per-signal horizon Forge could read. **Re-derivation against the live registry refuted that premise:** the snapshot the service loads (`registry_snapshot_2026-05-28T224247Z.json`) reports `IndicatorMetadata.lookback = 0` for **34 of 43 indicators**, and the 9 populated are not horizons (`rsi_2`→14, `ema_50`→200, `adx`/`hurst`/`macd`/`bb_pct`/`zscore_returns`→0). Worse, Forge's existing §3.5 S4 ("DTE matches the signal's lookback") read that same field, so S4 was already **degenerate in production** — `lookback ≤ 6 → swing_short`, so almost every directional was forced to `swing_short`, actively producing horizon-MISMATCHED configs (a MACD trend signal at 14-21 DTE). The directional signal's `params` carry only `{threshold, op}`; the period lives in the indicator *identity* (`rsi_2` vs `rsi_14`), which the registry doesn't expose numerically. This was not previously flagged (no OPEN_QUESTIONS / Decision Log entry). Surfaced to the operator before coding.

**Operator decisions (AskUserQuestion 2026-06-04).** (1) **Horizon source = Forge-owned table** — Forge owns the signal horizon the way it already owns per-indicator threshold ranges (`_INDICATOR_THRESHOLD_TABLE`), keyed by indicator id; the registry `lookback` is a Crucible data gap to flag, not block on (a populated value may mean warmup-bars, not horizon). (2) **Unify S4 on the horizon table** — the new table drives BOTH the S4 viability/validator AND the `k·horizon` bucket derivation, fixing the degenerate S4 (operator-owned rule's runtime behavior changes; no `rules:` text edit).

**Change.**
- **`src/forge/grammar/signal_horizon.py` (new).** `_SIGNAL_HORIZON_TABLE` (indicator_id → signal horizon in trading days), operator-reviewable with per-indicator rationale; `signal_horizon_days`, `horizon_class[_for_days]`, `buckets_for_horizon_class` (the old `_LOOKBACK_DTE_TABLE`), `nearest_bucket(allowed, target)` (snap a continuous target to the nearest §3.5 P2 window midpoint; ties → shorter bucket, deterministic #6). The horizon is a *signal horizon* (thesis time-scale), NOT a measurement window — they diverge for slow regime reads (`iv_rank`→30 not 252).
- **§3.5 S4 validator (`custom_predicates.py`).** `_lookback_class_for_indicators` now maxes `signal_horizon_days()` over the directional's indicators (registry *membership* still required); `_s4_…` uses `buckets_for_horizon_class`. Removed the registry-`lookback`-driven `_LOOKBACK_*` / `_LOOKBACK_DTE_TABLE`. The registered predicate name (`lookback_class_matches_dte_bucket`) and the `rules:` text are unchanged.
- **Sampler (`sampler.py`).** CSP reordered to **directional-first** (was bucket-first): pick the directional with a §3.5-S4-permitted bucket (chain-compat aware) AND a C1/C4/R-valid regime partner → derive the DTE target (`_dte_target`: `k·horizon` for mean_reversion/trend_continuation with `k ∈ {2,3,4}`; `entry_lead + 12 td` event-bracket for volatility_event with lead ∈ {5,10,20}; `None`→uniform for relative_value) → `nearest_bucket` → pick the regime (C1/C4/R only). The pre-v8 **regime-lookback-vs-bucket constraint is dropped** — S4 governs the directional horizon only (matching the validator), which also undoes the degenerate-registry artifact that forced trend regimes onto `rv_rank`. The X1/X2 chain indicator's horizon still constrains the bucket (preserved, via the table). relative_value keeps its uniform pick (its real DTE is a Crucible *runtime* choice off the live spread half-life — the handoff's runtime piece, NOT encoded in the grammar).
- **Grammar v7 → v8** (archive `grammar_archive/v8.yaml` byte-identical; header note; both pre-commit hooks satisfied). Enumeration-policy bump, NO `rules:` text change — the v5/v6/v7/D098/D099/D100 precedent. A/B via `crucible funnel --compare v7 v8`. **No contracts change** (`k` is an internal sampling knob; only the bucket + P2 window are emitted, as today).

**Hard rules.** #1 preserved — the 21 §3.5 rules are untouched; this is enumeration policy + a predicate's horizon *input*, like v5/v6/v7. #3 preserved — DTE-matching makes the search SMARTER (fewer DTE-mismatched configs), it never touches Crucible's promotion gate; the modest BS-sim edge (handoff) is efficiency + adaptivity, not gate-loosening. #6 preserved — all draws from the seeded rng in a fixed order (directional→target→bucket→regime); within-v8 determinism property tests green (the enumerated *sequence* changes vs v7 by design, as every version bump does). #8 preserved — `nearest_bucket` emits one of the 3 discrete buckets + the bucket's P2 window; never a continuous DTE.

**Verification (TDD).** New `test_signal_horizon.py` (39, RED→GREEN: table coverage of every threshold-eligible indicator, class boundaries, nearest-bucket math + tie-break, P2-midpoint drift guard, horizon→bucket thesis alignment) + new `test_horizon_matched_dte.py` (7: bucket ∈ directional's S4-permitted set across 400 seeds; vol_event→short/mid; rsi_2 pinned short; trend reaches swing_long; relative_value short/mid; determinism; k moves a boundary indicator). Existing S4 validator tests pass unchanged (the table is aligned to the fixture's semantic horizons; only production behavior changes). **`tests/unit` 1080 / 0 failed; `tests/invariants` + enumeration + grammar 539 / 0 failed**; ruff + ruff format + mypy --strict clean (full 79-file `src/`). **Real-registry emission proof** (4000 samples, 0 sampler errors): trend_continuation `{short 35, mid 878, long 102}` (was ~all short under the degenerate lookback — `macd`→swing_mid is the fix); mean_reversion `{short 440, mid 546}` (rsi_2→short, rsi_14/bb_pct/zscore→mid); volatility_event `{short 965, mid 52}`; relative_value `{short 513, mid 469}`.

**Crucible coordination (owed).** (a) Registry data gap: `IndicatorMetadata.lookback` is 0 for 34/43 — file so Crucible can populate real horizons (then a future Forge bump could migrate the table to the registry); also fixes whatever else reads `lookback`. (b) relative_value runtime: the handoff's per-pair `DTE = k × live spread half-life` is a **Crucible selector change** (`PairsConvergence` passes its measured half-life to the selector, snapping to a discrete bucket) — Forge's job is only to keep sampling `k`/the half-life gate, which it does. Both go in the v8 handoff reply.

**Files:** `src/forge/grammar/signal_horizon.py` (new), `src/forge/grammar/custom_predicates.py`, `src/forge/enumeration/sampler.py`, `config/grammar.yaml`, `config/grammar_archive/v8.yaml` (new), `docs/GRAMMAR.md` (S4 note), `tests/unit/test_grammar/test_signal_horizon.py` (new), `tests/unit/test_enumeration/test_horizon_matched_dte.py` (new), `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`.

**References:** [[D010]] (the operator-confirmed S4 lookback-class thresholds 6/89, reused; only the input moves), [[D098]] / [[D099]] / [[D100]] (version-bump-with-no-rules-text precedent), [[D077]] (chain-family regime exclusion, preserved), [[D074]] (within-bucket dte_min/dte_max sampling, unchanged), `FORGE_HANDOFF_dynamic_dte.md` (the Crucible handoff), hard rules #1/#3/#6/#8.

**DEPLOYED + VERIFIED 2026-06-04 ~23:33 PDT.** Stopped `forge.service` (SIGTERM exit 143, the normal `--loop` stop; `reset-failed` before restart) → **full uncontended suite 1291 passed / 0 failed** (the only change vs the build-time runs: one pre-existing `test_v1_grammar` hard-coded `grammar_version == "v7"` assertion bumped to `v8`) → committed **`ce0b768`** to `main` → restarted onto v8. **Verified live (loop iteration 361):** `grammar_version=v8`, `registry_loaded_from_export` (registry_hash=23092e5097f54a22), `grammar_versions: recorded manual_bump row for v8` (hard-rule-#10 audit row auto-written + resets the D035 stuck-state streak so the 42-batch zero-promotion history doesn't carry into v8 attribution), `NRestarts=0`, clean startup, no traceback / SchemaVersionMismatch, `hypothesis_weights` rendering normally (all active hypotheses ≫ the 0.05 floor). Operator passed `PROMPT_CRUCIBLE_HORIZON_DTE.md` to Crucible. **Watch** the first post-restart batch (after the ~33-min prefetch): trend_continuation should leave swing_short for swing_mid/long (the degenerate-S4 fix going live); the real read is `crucible funnel --compare v7 v8` once a v8 cohort gates.

**Cross-system loop closed (Crucible response `FORGE_horizon_dte_response.md`, 2026-06-05).** Both "YOURS" items resolved, no Forge code conflict. (1) **`lookback` semantics — definitively a warmup/measurement window, NOT a horizon** (the `compute()` contract masks NaN for the first `lookback` rows; both Crucible's warmup guards and Forge's `data_history_days` rejection use it as a history requirement). So Forge's `signal_horizon.py` table is the **permanent** end state — *do not migrate S4 back onto the registry field* (corrects this entry's earlier "wrong values/miscoded" framing: the populated values are correct warmups read wrong — `ema_50=200` EWM convergence, `rsi_2=14` RSI warmup; the 34 zeros are benign under-population where `compute()` self-masks the true param-dependent warmup, e.g. `macd` masks 104 / `adx` 28 — not a live bug, ~nil impact on the history-gate since v1 history ~2100 td ≫ any warmup ≤252). (2) **relative_value runtime DTE already shipped Crucible-side** (`384e3ec`): `selector.horizon_to_dte_window(k×measured_halflife)` snaps per-pair to a discrete §6.2 bucket (hard rule 8), lookahead-safe, `dte_override` replaces the emitted window only for pairs — so Forge's placeholder relative_value bucket is correct (gets overridden per-pair). (3) **`k`/`dte_halflife_mult` for relative_value — DEFER** (Crucible's vote + Forge agree, §29 filter-not-generator + measure-WF-benefit-first): keep `k=2.0` fixed; v8 already emits no `dte_halflife_mult`, and Crucible falls back to 2.0 — zero change either side, one-line enable later if data motivates. (4) **Funnel-compare caveat:** `--compare v7 v8` attributes mean_reversion / trend_continuation / volatility_event cleanly (grammar-gated), but the **relative_value column is confounded** — the runtime DTE (`384e3ec`) is live for ALL post-commit runs regardless of grammar_version, so both arms have it; clean relative_value attribution needs a code-level before/after on fixed grammar, not v7-vs-v8. **Owed:** relay the v8 deploy timestamp (2026-06-04 23:33 PDT, `ce0b768`) so Crucible runs the compare once a v8 cohort gates.

---

## D103 — 2026-06-05 — v9 grammar: relative_value quality-bias + dynamic regime curation + submission floor

**Context.** Crucible's orthogonal-components handoff (`FORGE_HANDOFF_orthogonal_components.md`, 2026-06-04) asked Forge to get **structurally-orthogonal, gate-passing** components into the pool — `relative_value` (market-neutral pairs convergence) the prime in-scope candidate — because the probe portfolio is a long-premium monoculture that can't lift portfolio Sharpe above its best single component. The handoff's premise was that relative_value "dies in the funnel" (zero in the v5-era probe pool). **Re-derivation against Forge's own code + the live runs DB refuted that premise** (the handoff explicitly warned its view of Forge internals may be stale, and it was):

- **relative_value firing is ALREADY fixed.** Joining Crucible's gated-runs export → `submissions.config_json` by `config_hash` and splitting by `grammar_version`: the aggregate "95% zero-trade" is a **stale-cohort artifact** — ~1,150 of 1,214 recent-window relative_value runs are pre-v5 (`grammar_version=None`) runs from the *known* pairs-loading bug (99% zero-trade), still being re-gated. **Current-grammar (v5/v7) relative_value fires ~77%** (20–24% zero-trade), comparable to the best hypotheses. [[D098]]'s fair-test + the percentile/cold-start work fixed firing; the handoff measured the stale cohort.
- **The live binding constraint is per-component SHARPE QUALITY, not firing.** Current-grammar traded relative_value: median single-run Sharpe **−0.085** (43% positive); rejects fail `walk_forward_sharpe_median` / `cpcv_sharpe_p25` / `deflated_sharpe` — *exactly* the gates the handoff cares about. Only 2/64 reach `decision='component'` (both ~0.70 Sharpe — proof quality is achievable). `min_oos_trade_count` is NOT the binder (21/62 rejects).
- **Two Forge-owned quality levers, evidence-grounded** (current-grammar gated relative_value, n=49 traded): `zscore_entry ≥ 1.0` → median Sharpe **+0.072** vs **−0.177** below; `pvalue_max ≤ 0.14` → **+0.023** vs **−0.086** above. And relative_value has **no §3.5 R-rule**, so the sampler draws its mandatory regime gate near-uniformly from the *whole registry* (`_build_regime_pool`); the two most-sampled gates (`rsi_2`, `rv_rank`) are among the *worst* performers — an incoherent gate just injects noise. The §6.2 ranker selects on firing-density/novelty (no Sharpe term) and the diversifier had no hypothesis floor, so a feedback oscillation (the post-[[D100]]/[[D101]] mean_reversion flood) starved relative_value to 0–2/batch for ~4h on 2026-06-04 before self-correcting to 23–59. Operator (AskUserQuestion 2026-06-05): **"Both"** quality-bias + submission floor, with the regime curation **dynamic/feedback-driven, not static** (avoids overfitting the thin n=49).

**Change (three parts; only part 1 is grammar-versioned).**
- **(1) Pairs template-param tightening — grammar v8 → v9** (enumeration policy, NO `rules:` text change — the [[D098]]/[[D099]]/[[D100]]/[[D102]] precedent; archive `grammar_archive/v9.yaml` byte-identical; both pre-commit hooks pass). `sampler._sample_pairs_template_params`: `pvalue_max` 0.10–0.25 → **0.02–0.12** (stronger cointegration), `zscore_entry` 0.5–1.5 → **1.0–2.0** (larger divergence entry). The converse trade of [[D072]]'s fire-chasing widening, made now that firing is solved. A/B via `crucible funnel --compare v8 v9`.
- **(2) Dynamic relative_value regime-gate curation — feedback, NO version bump** (the [[D101]] precedent). New `feedback.rejection_weights.compute_relative_value_regime_weights`: per-regime-indicator Beta(1,10)-smoothed reward, reusing the exact [[D101]] Sharpe-aware `_run_reward` (0.5·traded + 0.2·gate_fraction + 0.3·WF-Sharpe-proximity, promote=1.0), bucketed by the regime gate of each gated relative_value run (joined from `submissions.config_json`). Threaded `cli → enumerate_candidates → sample_config → _pick_regime`: relative_value's regime pick becomes `rng.choices(pool, weights=…)` floored at 0.05 (D067 analogue) with a Beta-prior fallback for unseen gates, so it *learns* toward gate-passing regimes while never starving exploration. The regime POOL is unchanged (hard rule #1). Scoped to relative_value only — every other hypothesis (R1/R2/R3-coherent pools) and the cold-start (empty weights) keep the byte-identical pre-D103 `rng.choice` pick (hard rule #6: weights are an added input, like `hypothesis_weights`).
- **(3) Per-hypothesis submission-diversity floor — ranking, NO version bump.** `diversifier.select_top_n(min_per_hypothesis=…)` + `rank_batch` + CLI wire `_PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS=15`. Two-phase greedy (floor per hypothesis in sorted order, then global fill) preserving the §6.3 diversity rule and determinism; guarantees each enumerable hypothesis ≥15 of the ~200 submitted slots (or all its survivors if fewer) so the orthogonal sleeve can't be starved by a feedback swing. `min_per_hypothesis=0` (default) is byte-identical to the legacy path.

**Hard rules.** #1 — the 21 §3.5 rules are untouched (part 1 = sampler param ranges, part 2 = regime *selection weight* not the pool, part 3 = ranking); #3/#4 — all three TIGHTEN/bias enumeration toward the gate-rewarded region, never loosen Crucible's gate (parts 2/3 are auto-tightening-class, ship without approval); #5 — parts 2/3 are deterministic Python feedback/ranking, no LLM; #6 — regime weights + the floor are deterministic given the gated snapshot, and the non-curated / cold-start paths are byte-identical (pinned by tests); #8 — clock/RNG via blessed sources (the reward read uses the file-based gated export, not `datetime.now`).

**Verification (TDD).** RED→GREEN throughout. `tests/unit/test_enumeration/test_sampler.py`: tightened `test_d068_pairs_template_params_ranges` + new `test_d103_pairs_quality_bias_*` + 4 `_pick_regime` tests (favor-high-weight, floor-keeps-zeroed-explorable, non-curated-byte-identical, cold-start-byte-identical). `tests/unit/test_feedback/test_rejection_weights.py`: 4 new (empty→{}, higher-reward-gate-outweighs, scoped-to-relative_value, deterministic+orphans-skipped). `tests/unit/test_ranking/test_diversifier.py`: 5 new (rescues-starved, degrades-when-few, zero-is-legacy-identical, never-exceeds-n, deterministic). **Changed-scope green:** invariants + enumeration + grammar + ranking + feedback **845 passed / 0 failed**; enumeration+feedback+cli **486 passed**; ranking+cli **151 passed**. ruff + ruff format + **mypy --strict clean on the full 79-file `src/`**. Both grammar pre-commit hooks pass on the staged v9 bump; loader accepts v9 (21 rules). **Real-registry emission proof** (4000 samples, seed 20260605, 0 errors): hypotheses `{relative_value 1035, trend_continuation 985, volatility_event 987, mean_reversion 993}`; relative_value pairs params live in-range (`pvalue_max [0.020, 0.120]`, `zscore_entry [1.000, 1.999]`); 35 distinct regime gates uniform at cold-start (no regression).

**Attribution caveat (mirrors [[D102]]#4).** Only part (1) is grammar-gated, so `crucible funnel --compare v8 v9` attributes the **pairs-param** effect cleanly; parts (2)/(3) are versionless (feedback/ranking) and active for ALL post-deploy runs regardless of grammar_version, so their effect is **confounded** in the v8-vs-v9 compare. Clean attribution of the regime-curation / floor needs a code-level before/after, not the version compare. All three ship together as the "relative_value quality + reliability" change.

**Files:** `src/forge/enumeration/sampler.py`, `src/forge/enumeration/iterator.py`, `src/forge/feedback/rejection_weights.py`, `src/forge/cli/main.py`, `src/forge/ranking/diversifier.py`, `src/forge/ranking/queue.py`, `config/grammar.yaml`, `config/grammar_archive/v9.yaml` (new), `tests/unit/test_enumeration/test_sampler.py`, `tests/unit/test_feedback/test_rejection_weights.py`, `tests/unit/test_ranking/test_diversifier.py`, `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`. (`docs/GRAMMAR.md` untouched — no `rules:` text change, doc-sync hook passes.)

**References:** [[D098]] (relative_value fair-test — the firing fix the handoff missed), [[D101]] (Sharpe-aware `_run_reward` reused for the regime weighter), [[D067]] (exploration floor, mirrored for regimes), [[D037]] (per-hypothesis *enumeration* floor — the submission floor is its missing submission-stage analogue), [[D072]] (the pairs param widening this reverses), [[D102]] (versionless-change attribution caveat), `FORGE_HANDOFF_orthogonal_components.md`, hard rules #1/#3/#4/#5/#6/#8.

**STATUS: BUILT + VERIFIED (unit/invariants + live emission); DEPLOY PENDING the operator gate** — Forge cannot run the full suite uncontended (the live `forge.service` holds the DuckDB write lock) and does not self-restart onto a grammar bump. Deploy ritual (operator): stop service → full uncontended suite → commit D103 + v9 → restart onto v9 → tell Crucible the version string is `v9` for `crucible funnel --compare v8 v9` (pairs-param arm only; see attribution caveat). **Deploy-timing recommendation:** v8 deployed only 2026-06-04 23:33 PDT, so let it soak a cohort before v9 so its horizon-DTE A/B is measurable — v8 (trend/vol DTE) and v9 (relative_value quality) target largely disjoint hypotheses, so the soak costs nothing here. **Owed once deployed:** relay the v9 timestamp + that relative_value firing was already fixed (the handoff's pool snapshot was the stale v4 cohort) so Crucible re-assembles on current-grammar relative_value components, not the pre-v5 pool.

**DEPLOYED 2026-06-07 03:21:44 UTC** (migration deploy on `aj-workstation`; commits `e4fc5a4`+`5d31f74`+`e126441`; suite 1305/0; see STATUS.md 2026-06-07 block) — **but see [[D104]]: the v9 CODE had already been live since 2026-06-06 06:48:49 UTC** via an unplanned reboot-deploy of the uncommitted working tree on the old box. The migration restart is NOT the v9 code boundary.

## D104 — 2026-06-07 — Reboot-deploy postmortem: the true v9 cutover is 2026-06-06T06:48:49Z; dirty-working-tree builds are a deploy hazard

**Context.** Crucible's response to our v9 time-cut handoff (`FORGE_v9_timecut_response.md`) verified every cohort count to the digit, implemented the read-time relabel, and caught one false claim in our prompt (`submitted_at` is NOT carried in the inbox JSON — the inbox file is a bare `StrategyConfig`; they cut on queue time, equivalent here because the migration gap is verified empty). It also reported a discovery: the pre-cutover v9-stamped window is **bounds-MIXED for relative_value** — new v9 pairs bounds appear from 2026-06-06 ~07:24Z, mid-window, ~20h before the migration deploy. Crucible attributed this to the per-batch YAML re-read "applied to the bounds." **Re-derivation refuted their mechanism and enlarged the finding:** the pairs bounds live in `sampler._sample_pairs_template_params` (CODE, loaded at process start), not in `grammar.yaml` — a YAML re-read can flip the stamp but never the bounds. A code flip requires a process restart.

**The actual event (verified, old-box journal over tailnet).** The old box (`aj-M5-Ultra`) took a **kernel-update reboot (6.17.0-29 → 6.17.0-35) at 2026-06-05 23:48 PDT = 2026-06-06 06:48:49 UTC**; linger auto-started `forge.service` (new systemd manager PID 1324) — **onto the uncommitted D103 working tree** (Forge is installed editable; the D103 build sat BUILT-but-DEPLOY-PENDING in the live tree since 06-05). All three D103 parts went live at that moment, byte-identical to what was later committed as `5d31f74`. Confirmed from `submissions ⋈ batch_summaries`, all three signatures flip at the first post-reboot batch (07:24:00Z) and never before: (1) pairs bounds pure-old → pure-new (326 vs 562 + overlap; matches Crucible's queue-side split to the batch); (2) **submission floor**: pre-reboot batches have rv = 0/2/7 (one batch has only 3 hypotheses — impossible under the floor), post-reboot rv never < 15 and pins at exactly 15 twice; (3) regime curation: rv regime gates uniform ~1/34 pre → `rsi_2`/`rv_rank` 7% post (the Beta(1,10)-reward shape). A 2.72h submission gap (04:40:38 → 07:24:00Z) brackets the reboot; the cut is clean.

**Corrected cohorts** (supersedes `PROMPT_CRUCIBLE_V9_LIVE_TIMECUT.md`; correction handed to Crucible as `PROMPT_CRUCIBLE_V9_TRUE_CUTOVER.md`): **v8 arm = 28 batches / 5,600 subs** (1 honest v8-stamp + 27 v9-stamped pre-reboot), window 06-05 07:10 → 06-06 04:40Z. **v9 arm = everything from 2026-06-06T06:48:49Z** (67 batches / 12,991 subs at write time, accruing) — the migration timestamp 2026-06-07T03:21:44Z is a box/TZ boundary, not a code boundary. Crucible's "silver lining" (a within-v8-code bounds-only rv A/B) is **void** — the post-reboot side carries the full D103 confound set; there is no bounds-only experiment in this data. Non-rv hypotheses sample byte-identically under v8/v9 code (pinned by D103 tests), so the v7↔v8 horizon-DTE read stays clean under the corrected cut; only submission composition shifts (the floor).

**The hygiene failure + corrective rule.** Two distinct mechanisms now documented: (a) the D099 wrinkle — `grammar.yaml` edits go live (stamp + any YAML-resident behavior) on the next batch re-read, before any deploy; (b) **NEW — the dirty-tree hazard: any BUILT-but-ungated code left in the live service's editable working tree deploys itself on the next process restart** (reboot, crash, OOM), silently bypassing the operator deploy gate. Hard rule #10's pre-commit hooks cannot catch it (nothing is committed). **Rule going forward: build sessions for grammar bumps / deploy-gated changes work in a separate git worktree (`git worktree add ../Forge-build`), and changes reach the service's tree only at the deploy gate (merge/checkout + immediate restart).** Equivalently: the live tree must always be clean (`git status` clean) whenever the operator is not actively mid-deploy. Proposed CLAUDE.md addition (operator to approve): one line under Phase discipline / deploy ritual. Also noted: `grammar_versions.changed_at` records first-load-post-bump observation (v9: 2026-06-05 07:16:08Z) — it is the STAMP flip time, never the deploy time; never source a cutover from it.

**Files:** `PROMPT_CRUCIBLE_V9_TRUE_CUTOVER.md` (new), `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`, `OPEN_QUESTIONS.md` (funnel re-bucket item), memory archive (`gated-export-stale-cohort.md`).

**References:** [[D103]] (the build that leaked; its attribution caveat now covers the whole post-reboot window), [[D102]] (deploy-ritual precedent), [[D099]] (the YAML-stamp wrinkle, mechanism (a)), `FORGE_v9_timecut_response.md` (Crucible's verification + the catch), hard rules #6/#10.

## D105 — 2026-06-07 — v10 grammar + component-rate feedback re-aim (Crucible yield-map handoff): reward tracks what Crucible ACCEPTS, plus hypothesis x dte_bucket and underlying-class granularity

**Context.** Crucible's handoff `FORGE_feedback_reward_yield_map.md` (2026-06-07 ~20:30Z, v9 cohort ~3,300 decided): two Crucible changes shifted Forge's reward landscape overnight — the rv lookback fix (`5fd485a`, 06-07 ~07:42Z) flipped `relative_value` from ~70-100% zero-trade to ~100% trading (avg 150-220 trades/run), and ~13x runner throughput (38/hr → ~488/hr) made the feedback window intraday. The [[D094]]/[[D101]] reward (0.5·traded + 0.2·gate_fraction + 0.3·sharpe) — correct for the zero-trade cold-start era it was designed in — became a **Goodhart proxy**: the live loop weighted rv **0.567** at **0.7-1.0%** component yield while volatility_event sat at **0.169** yielding **3.9-9.7%** (vol_event x swing_mid: 9.7% on 31 decided, starved ~20:1 vs the 0.0-0.3% mean_rev/trend x swing_mid cells). Every load-bearing claim was re-derived against live code/journal/export before acting (the handoff's validate-first note): weights rv=0.567 stable across iterations ✓; rv taking 84-136/200 slots and ~2,550/5,000 sampler draws with ~2,300/batch dying at `permutation_test` ✓; `lookback` 378 = the dead >280 band = exactly 25% of rv draws ✓; `_pick_underlying` uniform over the 124-ticker universe ✓. **Two facts the handoff didn't know:** (a) the gated export caps at **5,000 rows**, reaches back to 05-28, and carries **no grammar_version field** — so the 1,000-row hypothesis/regime weight loads had NO version scoping against the pre-v5 re-gate pollution [[D103]] documented; (b) the D103 rv-regime weights were **also** Goodharted — all 34 gates compressed into 0.33-0.40 once everything traded. Operator approved all four changes (AskUserQuestion 2026-06-07).

**Changes (only #4 is grammar-versioned → v10).**

1. **Component-rate reward family — feedback, versionless ([[D101]] precedent).** New shared engine `rejection_weights._component_rate_posteriors`: Beta-smoothed posterior of P(decision ∈ {component, promote}) per key, joined through `submissions LEFT JOIN batch_summaries` (the [[D081]] version resolution — current=1.0, prior=0.25, [[D098]] `COLD_START_HYPOTHESES` dropped entirely), with an epsilon tiebreak from gate-progress + sharpe-proximity. **A blend cannot fix the Goodhart** — worked example in the section comment: 0.7·component + 0.2·gate still ranks rv above vol_event on live numbers, because gate_fraction and traded are themselves trade-correlated. Scale design: `COMPONENT_BETA=50` (prior mean 1/51 ≈ the observed ~2% marginal component rate, so unobserved keys sample like average ones); `COMPONENT_TIEBREAK_WEIGHT=5e-5` sized so the window's max tiebreak mass (10,000-row limit x eps ≤ 0.5) stays below ONE component event — trading volume can never outrank a real component (invariant test). `compute_hypothesis_component_weights` fills every samplable hypothesis and **normalizes to max=1.0** so the untouched [[D067]] `apply_exploration_floor(0.05)` keeps its semantics (raw posteriors ~0.005-0.05 would all flatten at the floor); open-key-set maps (regime/bucket/class) stay RAW with draw-site prior/floor constants rescaled to the family's scale (1/51, 0.01 — same floor-to-prior ratio as D067). `compute_relative_value_regime_weights` re-aimed in place onto the engine ([[D103]]'s docstring already promised "gates that yield components"); sampler `_REGIME_WEIGHT_PRIOR_MEAN/_REGIME_EXPLORATION_FLOOR` rescaled in the same commit. CLI loaders widen 1,000 → `FEEDBACK_GATED_RUNS_LIMIT=10_000` (5x more component events per window; export caps at 5k anyway) and thread `grammar.grammar_version`. The old `compute_hypothesis_weights`/`compute_hypothesis_reward_weights` remain exported (diagnostics + history; CLI no longer calls them).

2. **hypothesis x dte_bucket weights — feedback+sampler, versionless.** `compute_hypothesis_bucket_weights` (same engine, keyed `(hypothesis, dte_bucket)`). Consumed by a **joint (directional, bucket) draw** in `_select_bucket_directional_regime`: with weights present, the pick runs over every (candidate, induced-bucket) pair — induced via the exact cold-path derivation (`k`·horizon / event-lead + 12td / S4-permitted set), WITH multiplicity so the learned weight composes with the structural prior. **The joint draw is load-bearing:** most directionals are bucket-locked across k (macd → all swing_mid, momentum_252 → all swing_long, rsi_14 → all swing_mid), so a k-only reweight could not move the bucket mix at all — the cell weight must steer WHICH directional anchors the config (e.g. trend x swing_long, 1.4% yield, is reachable only through momentum-class directionals). Cold start (None/{}) keeps the two-step draw **byte-identical** (hard rule #6; pinned). Emission proof also exposed a structural bottleneck logged as **Q28**: among vol_event directionals only `iv_rank` is medium-horizon-class, so ve x swing_mid (the 9.7% cell) caps at ~9% of ve draws under §3.5 S4 — widening would be a LOOSENING (OPEN_PROPOSALS path, not auto).

3. **Underlying-class prior — new table + feedback+sampler, versionless.** New `forge/enumeration/underlying_class.py` (Forge-owned curated table, [[D102]] signal_horizon precedent): two classes — `DIVERSIFIED` = curated ETF/index list (25 names incl. VIX); everything else `HIGH_IDIO_VOL`, deliberately including leveraged/thematic ETFs (TQQQ/SQQQ/SOXL/UVXY/ARKK — the handoff flags TQQQ/ARKK as undersampled high-beta); unknown future tickers default HIGH. Evidence: AAPL 27.9% / NVDA 22.2% / TSLA 12.8% component yield vs a wall of zeros on every diversified underlying with ≥30 decided (~390 total). `compute_underlying_class_weights` (same engine, keyed by class of `cfg.underlying`; rv's None skipped) → `_pick_underlying` draws per-ticker weight = class weight, floored; the T1.4 days_to_earnings ETF exclusion applies before weighting; cold start byte-identical. Per-name Bayesian smoothing deferred (handoff's own sequencing).

4. **rv `lookback` ≤ 280 → grammar v10.** `_sample_pairs_template_params` drops 378: post-rv-fix that band runs/trades properly and is **0-for-155 decided, best WF 0.19**, vs all 7 rv components at lookback ≤ 252 — one choice of four ≈ 25% of rv enumeration provably wasted. Tightening (hard rule #4); v9 → v10 bump + byte-identical archive per the v5-v9 enumeration-policy precedent; no `rules:` text change (hard rule #1). The handoff's GENERAL bounds-learning mechanism (param band with N ≥ ~100 decided and 0 components → auto-floor) is deferred to **Q29** — this ships the one decisive instance.

**Answer to the handoff's `trade_rate_priors` question.** It IS wired and binding — as the `expected_trades` PREFILTER (empirical mode: 713-737 trend + 448-516 mean_rev kills/batch at min_pass_p=0.1), not as a sampler input; the sampler keeps drawing into the dead region and burns battery compute, and vol_event's 75% zero-trade legitimately PASSES the filter (fat trading tail: avg 26 trades → P(≥50) > 0.1 — the yield map already prices the silence in). Re-aiming allocation (#1) shrinks the waste organically (mr/trend/rv draw share falls); threshold-DRAW adaptation is deferred to **Q29**.

**Expected live effect** (within ~1 day per the handoff's §5; the loop demonstrably reacts same-day): hypothesis_weights flip from rv=0.567/ve=0.169 to ve≈1.0 normalized (~60-67% of draws) / rv≈0.23 / trend≈0.15 / mr≈0.11; submission mix follows toward the yield table; component-mint rate per 1,000 decided is the outcome metric (current ~12-17/1,000). **Non-goal:** promote rate is NOT expected to move (WF≥2.0 ceiling is a strategy-space property); this buys more/cheaper components for §8.7 portfolio assembly. The [[D103]] submission floor (≥15/hypothesis) + [[D037]] stratification + D067 floor + the new bucket/class floors bound every starvation direction.

**Hard rules.** #1 — 21 rules untouched (v10 is sampler-param policy; the curated tables are enumeration policy); #3 — gates untouched, no loosening anywhere (the one loosening *candidate* found goes to Q28/OPEN_PROPOSALS); #4 — lookback cap is a tightening; #5 — deterministic Python throughout; #6 — all four weight families are added inputs; every cold path byte-identical (pinned by tests); #8 — no clock/RNG outside blessed sources; #9/#10 — bump + archive + this entry; both pre-commit hooks pass.

**Verification (TDD, RED→GREEN throughout).** New `tests/unit/test_feedback/test_component_rate_weights.py` (15: anti-Goodhart core regression asserting OLD ranks rv>ve while NEW ranks ve>rv on the same data; promote=component event; tiebreak gradient + the eps-bound invariant; prior-fill+normalization; D081 down-weight; D098 cold-start drop flips the ranking; bucket keying; class keying incl. rv-None skip; determinism/orphans/corrupt). `test_sampler.py` +8 (bucket-options locking pin documenting WHY joint; joint-draw steers directional choice; ve/mr bucket tilts + floors; cold-start byte-identical x2; underlying tilt + earnings-exclusion under weights; lookback ≤280). `test_underlying_class.py` (5). 2 D103 regime value tests re-pinned to the new estimand ([[D101]] precedent). **Gates:** unit+invariants+integration **1,290 passed / 0 failed** + integration 52/52 (run uncontended-equivalent: all tmp-path); ruff + ruff format + **mypy --strict clean (full 80-file src)**; both grammar hooks pass on the staged v10; `v10.yaml` byte-identical. **Real-registry emission proof** (4,000 cold + 4,000 weighted, 0 errors, all grammar-valid): cold byte-path mix uniform-ish {ve 1017, trend 1015, mr 986, rv 982} with rv lookbacks {126: 331, 189: 332, 252: 319} (378 GONE); weighted (yield-map-shaped synthetic weights) → {ve 2653, rv 600, trend 419, mr 328} = the designed allocation, diversified underlyings 19% → 4.5% (floored, not zero), ve x mid 5.1% → 9.2% (Q28 explains the cap).

**D104 hygiene rule — followed (first exercise).** Built initially in the live tree (error), then moved wholesale to the **`../Forge-build` worktree (branch `d105-yield-map-reaim`)** via stash before any batch could re-read the hot v10 `grammar.yaml` (the [[D099]] stamp wrinkle; live tree verified clean + back on v9 with the service untouched, well before the next re-read). All gates re-verified inside the worktree. **The live tree's `git status` is clean; nothing deploys on a reboot.**

**Files (all in `../Forge-build` until the deploy gate):** `src/forge/feedback/rejection_weights.py`, `src/forge/enumeration/sampler.py`, `src/forge/enumeration/iterator.py`, `src/forge/enumeration/underlying_class.py` (new), `src/forge/cli/main.py`, `config/grammar.yaml`, `config/grammar_archive/v10.yaml` (new), `tests/unit/test_feedback/test_component_rate_weights.py` (new), `tests/unit/test_feedback/test_rejection_weights.py`, `tests/unit/test_enumeration/test_sampler.py`, `tests/unit/test_enumeration/test_underlying_class.py` (new), `tests/integration/test_v1_grammar.py`, `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`, `OPEN_QUESTIONS.md` (Q28/Q29), `PROMPT_CRUCIBLE_YIELD_MAP_RESPONSE.md` (new).

**References:** [[D094]]/[[D101]] (the reward this re-aims; both retained as exported diagnostics), [[D103]] (regime weights re-aimed; submission floor relied on; the stale-cohort pollution this version-scopes against), [[D104]] (worktree hygiene rule, first exercise), [[D081]]/[[D098]] (version weighting semantics reused at the reward layer), [[D067]] (floor preserved via normalization), [[D102]] (signal-horizon table precedent for the underlying-class table; horizon-derived buckets the joint draw rides on), [[D072]] (the 504-drop precedent for lookback), `FORGE_feedback_reward_yield_map.md`, hard rules #1/#3/#4/#5/#6/#8/#9/#10.

**STATUS: BUILT + VERIFIED in `../Forge-build`; DEPLOY PENDING the operator gate.** Deploy ritual (operator): stop `forge.service` → in `../Forge-build` run the full uncontended suite → commit D105 + v10 (merge/fast-forward `d105-yield-map-reaim` to `main`) → checkout in the live tree → restart onto v10 → tell Crucible the version string is `v10` and relay the deploy timestamp. **Owed once deployed:** ask Crucible to re-pull the yield map after ≥1,500 newly-decided (~3h of queue) — their §5 validation protocol; watch `hypothesis_weights:` flip to the normalized scale (ve≈1.000) + the new `bucket_weights:`/`underlying_class_weights:` journal lines on the first post-restart iteration.

## D106 — 2026-06-08 — Hierarchical component-rate weights (underlying name <- class; directional x bucket triple <- pair), WF-source fix, contracts 1.15.0 adoption

**Context.** Post-D105 dimensional scan over the gated export ⋈ inbox configs (v9-stamped, 5,099 runs / ~100 components; pre-D105 sampling drew these dimensions uniformly, so the reads are quasi-randomized). Three findings: (1) **per-name yield is extreme INSIDE the high-idio class** — AMD 38.5% (10/26), AAPL 36.6% (37/101), NVDA 22.2%, NFLX 14.3%, TSLA 12.5% vs SHOP 0/85, SOXL 0/60, LUV 0/64 — the D105 two-class prior is leaky in both directions; (2) **directional structure is real and invisible to D105's families** — vol_event x iv_rank 17.9% (25/140) vs gamma_flip 0/147; mean_reversion x put_wall_distance_pct 7.7% (4/52) vs every classic oscillator at 0/~1,100 combined (the v6 percentile work targeted exactly the indicators that don't mint); trend x donchian 0/468; (3) a **delta-band gradient (0.5→3.5%, 0.4→1.5%, 0.3→0.6%, 0.2→0/94) turned out to be pure bucket-mix confound** — §3.5 P3's bands are bucket-determined (short [0.40,0.55] / mid [0.30,0.45] / long [0.20,0.35]) and the within-(ve, short) gradient vanishes (0.4-band 5.5% vs 0.5-band 5.1%) — so the planned delta-weight change was DROPPED before build. Methodology lesson recorded: cross-bucket dimension reads must be checked within-cell before acting; and post-D105/D106, scans must condition on the live weights (the quasi-randomization era is over). Operator approved building the Tier-1 list (2026-06-08).

**Changes (all versionless feedback/enumeration; no grammar change, no version bump).**

1. **Engine split + hierarchy.** `_component_rate_sums` (version-weighted `[total, reward_sum]` per key) split out of `_component_rate_posteriors`; new `_hierarchical_posteriors(fine_sums, coarse_of, *, prior_strength)` — empirical-Bayes shrinkage: coarse posterior from aggregated fine sums (identical to the flat weighter for the same key, by construction), each fine key gets `(S*coarse + fine_reward_sum)/(S + fine_n)` with `COMPONENT_HIER_PRIOR_STRENGTH = 50` (matches the COMPONENT_ALPHA+BETA scale: ~50 observations halve the anchor's pull). Zero fine evidence reproduces the coarse cell exactly → the draw-site fallback chains are scale-coherent.
2. **Per-name underlying weights.** `compute_underlying_name_weights` (name <- class anchor); `_pick_underlying` chain: name -> class -> prior, floored. Unseen names absent from the map fall to their class weight — AAPL-grade evidence concentrates draws without starving the unobserved remainder of its class.
3. **(hypothesis, directional, bucket) triple cells.** `compute_hypothesis_directional_bucket_weights` (triple <- (hypothesis, bucket) pair anchor); the D105 joint draw's option weight becomes triple -> pair -> prior. The triple key (rather than a flat directional weight multiplied into the pair cell) is load-bearing: iv_rank's edge is partly its swing_mid reach, which the pair cell already prices — a multiplicative composition would double-count correlated effects; the pair-anchored triple separates "this directional mints" from "this bucket mints".
4. **WF-source fix (D101/D105 correctness).** The live gated export carries `walk_forward_sharpe_median` ONLY in `gate_results[...].value` — `run.metrics` holds base backtest stats — so D101's metrics-only `_sharpe_reward` read has been silently scoring 0 on the current export shape (and the D105 tiebreak's sharpe half with it; gate_fraction carried the tiebreak, so D105's orderings stand). Gate value is now authoritative, metrics retained as fallback; zero-trade still uncredited.
5. **Contracts 1.15.0 adoption (forced mid-build).** Crucible shipped `9995f81` ("RunResult.grammar_version rides the gated export") at 2026-06-08 00:10:49Z — 32 minutes AFTER the v10 restart, in same-day response to the D105 reply's "export carries no version field" note. With `extra="forbid"` models, the RUNNING service's in-memory 1.14.0 reader would reject the new export rows at its first unblocked iteration → every weight loader degrades to `{}` (uniform sampling) until restarted. (Correction recorded during deploy: the §13.5 check is MAJOR-only by design — `validate_schema_version` tolerates minor bumps, and the editable install serves 1.15.0 code to any restarted process, which a brief probe restart confirmed by reconciling 4,533 newly-gated against the NEW export shape on the old pin. So the exposure was confined to the pre-00:10Z process, stopped at 01:39Z — no restart-halt existed. The pin bump remains correct adoption hygiene, not a fix.) Adopted per the D093/D097 pattern: `FORGE_EXPECTED_CONTRACT_VERSION` 1.14.0 → 1.15.0, `uv.lock` regenerated, and the synthetic Crucible DB fixture's `runs` table gains the (nullable) `grammar_version` column the 1.15.0 gated query selects. Coupling note for the record: this is exactly the §6-coupling class Crucible's own handoff asks to flag in advance — the pin caught it as designed, but it landed unannounced mid-session; relay in the next handoff. (Forge's own version scoping KEEPS the D081 submissions⋈batch_summaries join — Forge-authoritative, handles NULL-stamp legacy rows; reading the export's new field instead is a possible later simplification, not a correctness need.)

**Hard rules.** #1 — untouched; #3 — no loosening (the delta finding DIED on evidence; the Q28 widening still waits on data); #5 — deterministic Python; #6 — all new maps are added inputs; cold paths byte-identical (pinned); #8 — blessed sources only.

**Verification (TDD, RED→GREEN).** 4 new feedback tests (name escapes class / thin name pinned to class / triple shrinks toward pair with exact math / WF gate-value-first with metrics fallback + zero-trade guard) + 4 new sampler tests (name-over-class draw chain, cold byte-identical x2, triple-overrides-pair in the joint draw). Consumer suite restored by the fixture column (20 tests had broken on the unannounced 1.15.0 query change). **Full suite in the worktree: 1,341 passed / 0 failed** (1,333 + 8); ruff clean; **mypy --strict clean (80 files)**; ruff format clean on every file this branch touches (9 pre-existing drift candidates in untouched files left alone, per D105 precedent).

**Built in `../Forge-build` (branch `d106-frontier-weights`) per the D104 rule; live tree untouched.**

**Files:** `src/forge/feedback/rejection_weights.py`, `src/forge/enumeration/sampler.py`, `src/forge/enumeration/iterator.py`, `src/forge/cli/main.py`, `src/forge/core/contracts_check.py`, `uv.lock`, `tests/fixtures/synthetic_crucible_db.py`, `tests/unit/test_feedback/test_component_rate_weights.py`, `tests/unit/test_enumeration/test_sampler.py`, `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`.

**References:** [[D105]] (the engine + families this refines; the scan it enabled), [[D101]] (the WF read this fixes), [[D104]] (worktree rule), [[D097]]/[[D093]] (contracts adoption pattern), [[D081]]/[[D098]] (version semantics), Crucible `9995f81` (contracts 1.15.0), hard rules #1/#3/#5/#6/#8.

**STATUS: BUILT + VERIFIED; deployed same session (operator-approved)** — see STATUS.md for the deploy note. The urgency was real but narrower than first stated: only the long-running pre-00:10Z process was exposed to the export-shape change; any restart picks up 1.15.0 via the editable install regardless of the pin (major-only check).

## D107 — 2026-06-07 — H3 dealer-gamma regime switch (trend side): R2 admits `gamma_flip_distance_pct`; grammar v10 → v11

**Context.** First increment of the operator-approved new-hypotheses program (`NEW_HYPOTHESES_V11_PLAN.md`). Empirical basis: across 92,389 submissions / 10 grammar versions, **0 promotions ever** (WF≥2.0 is strategy-space, per Crucible's yield-map handoff); the currency is **components** (1.83% on the 2026-06-08 gated cohort, 183/10,000). The binding constraint is **breadth** — components trade median 146, rejects median 1; `min_oos_trade_count ≥ 100` kills 98% (Grinold IR = IC·√Breadth as a gate). vol_event mints 5.04% (5–8× the directional archetypes: trend 0.62%, mean_rev 0.86%, rel_value 0.98%) because events recur → breadth. H3 is the one program arm with **no upstream dependency** (H1 cross-sectional rank + H2 event-momentum are contracts-gated — handoff sent to Crucible 2026-06-07; H4 orthogonal-yield is versionless and follows). Web- + data-grounded thesis: trend pays in the **short-gamma / vol-amplifying** regime (SpotGamma/SqueezeMetrics: negative dealer gamma = trending). Gate trend_continuation to its productive regime → attack the weakest archetype.

**Change (grammar v10 → v11; the 21 `rules:` are textually unchanged — python-side predicate-constant expansion referenced by function name, exactly the v4/D077 pattern that added `rv_rank`; hard rule #1 intact).** `_R2_TREND_CONTINUATION_REGIME_INDICATORS` in `custom_predicates.py` adds `gamma_flip_distance_pct` (was `adx, hurst, rv_rank`). So R2's `trend_requires_trend_strength_gate` now accepts a dealer-gamma regime gate, and `_build_regime_pool` auto-includes it in the live trend pool (it's intersected with `registry_ids`; gamma_flip is live, 3,410 enumerated). **No sampler change:** `indicator_thresholds["gamma_flip_distance_pct"].op_regime` is already `">"` with `regime_range=(-0.05, 0.05)` — and ">" is the CORRECT direction ("Positive = flip above spot → dealers short gamma → vol amplifying" per the same table), so the gate fires in the trending regime with the existing threshold machinery. The D100/Q26 hurst-backwards failure mode is avoided because the direction is documented, not guessed.

**Honest risk / watch-item.** D106's dimensional scan found `gamma_flip 0/147` — but that was gamma_flip as a **directional** signal for vol_event. H3 uses it as a **regime gate** for trend (filters *when* trend fires; does not generate direction) — an untested, structurally different mechanism. The 0/147 tempers optimism about gamma_flip's signal content generally; if the v11 trend×gamma cohort also mints 0 over ≥100 decided, retire the gate (Forge Q-followup). Data first.

**Scope deliberately held to the trend side.** The mean_reversion side (long-gamma, op `"<"` — needs an R1 predicate OR-branch + a hypothesis-aware op flip in `_regime_signal_params` + the MR regime pool) and H4 (orthogonal-yield diversifier, versionless) ship as the next increment. Keeping v11 to one grammar-gated arm keeps `crucible funnel --compare v10 v11` a clean attribution (the v5–v10 discipline).

**Hard rules.** #1 — the 21 rules untouched (constant expansion, like D077). #3 — no gate change; this is enumeration scope, never validation strictness. #4 — this is a LOOSENING (more regime gates accepted), but **operator-directed**, not an auto-refiner proposal: hard rule #4 binds the *refiner code* (which writes to the machine-managed `OPEN_PROPOSALS.md` and waits); a supervised operator-approved edit takes the normal hard-rule-#10 path (version bump + archive + this Decision Log entry, which records the 2026-06-07 approval). Not written to `OPEN_PROPOSALS.md` — that file is the auto-tune channel with a UUID/marker approval flow, wrong for a hand-directed change. #6 — determinism preserved (the pool derivation is pure; the v11 sequence differs from v10, which is correct and expected). #8 — blessed sources only.

**Verification (TDD, RED→GREEN).** New predicate test `test_r2_trend_with_gamma_flip_passes` (RED: "requires one of ['adx','hurst','rv_rank']" → GREEN after the constant). New isolated `test_regime_pool_trend_continuation_includes_gamma_flip` covers the pool membership directly on `_build_regime_pool`, so the shared minimal fixture (and its golden d105/d106 sampler-sequence tests) stays stable. `test_v1_grammar_loads` + the search-space trend-pool assertion updated. **Full suite: 1,343 passed / 0 failed; ruff clean; mypy clean on changed scope.** `load_grammar` verified to accept v11 against the new `config/grammar_archive/v11.yaml` (archive-consistent, the restart-safety check).

**Built in the LIVE tree (deviation from the D104 worktree rule), small + fully verified, per the operator's "move forward + run suite + restart" directive.** Deploy: restart `forge.service` (user unit) onto v11; tree is dirty until committed — commit recommended to close the D104 silent-deploy window.

**Files:** `config/grammar.yaml` (v11 + version note), `config/grammar_archive/v11.yaml` (new), `src/forge/grammar/custom_predicates.py`, `docs/GRAMMAR.md` (R2 sync), `tests/unit/test_grammar/test_custom_predicates.py`, `tests/unit/test_enumeration/test_search_space.py`, `tests/integration/test_v1_grammar.py`, `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`. Program docs: `NEW_HYPOTHESES_V11_PLAN.md`, `PROMPT_CRUCIBLE_NEW_HYPOTHESES_V11.md`.

**References:** [[D077]] (the v4 rv_rank addition this mirrors exactly), [[D062]] (dealer_positioning as a first-class family — directional for MR/vol_event), [[D106]] (the gamma_flip 0/147 directional read this watch-items; the breadth/component framing), [[D100]] (the hurst-backwards regime-direction failure mode this avoids), [[D104]] (the worktree rule this deviates from), [[D098]] (version semantics), hard rules #1/#3/#4/#6/#8.

**Update (same session, 2026-06-08) — mean_reversion side folded into v11 (the complete H3 switch).** The trend side above was the first increment; the MR side is added to the SAME v11 because the §7.3 rate limiter held ALL v11 submissions (0 v11 cohort accrued — `forge.service` was queue-blocked from restart through this edit), so folding avoids a v12 bump with no attribution cost. **Change:** R1 (`mean_reversion_requires_iv_rank_gate`) now accepts `gamma_flip_distance_pct` as an alternative to the `iv_rank ≤ 50` gate; `_build_regime_pool`'s MR branch becomes `{iv_rank, gamma_flip_distance_pct} & registry_ids` (so MR's pool is now 2 members → ~50% gamma when sampled uniform); `_regime_signal_params` flips the gamma op to `"<"` for mean_reversion (the LONG-gamma / dampening / ranging side — the complement of trend's `">"` short-gamma side; documented direction, D100 failure mode avoided). **Why now / the 1/2 question (operator):** completing the MR side raises gamma's total enumeration footprint ~2.5%→~6.5% of draws *organically* (MR pool is 2-member → 50% gamma) without a static trend up-weight — declined hard-coding trend to 1/2 because (a) the rate limiter, not the gamma share, is the current read-speed bottleneck, and (b) a static prior front-runs the D105/D106 component-rate feedback; a feedback-driven boost is the principled path if a faster trend read is wanted post-first-data. **Promise (honest, operator asked):** modest — gamma_flip is 0-for-everything-so-far (D106 0/147 as directional; absent from all 183 component regime gates), the trend×gamma use is untried, and a regime gate is a QUALITY lever against a BREADTH-bound gate (`min_oos_trade_count ≥ 100`), so its ceiling is structurally low vs the breadth arms H1/H2. Worth running (near-free; existing trend/MR gates already mint poorly), not where the leverage is. **Verification:** 5 new TDD tests (R1 accepts gamma / R1 still fails without either gate / MR pool includes gamma isolated on `_build_regime_pool` / `_regime_signal_params` op is hypothesis-aware for gamma / op-flip scoped to gamma only — iv_rank byte-identical to the raw sampler). Full suite re-run + restart onto the both-sides v11 follow. **Files (added to the trend-side set):** `src/forge/enumeration/sampler.py`, `src/forge/enumeration/search_space.py` (+ `_R1_GAMMA_REGIME_INDICATOR` import), `src/forge/grammar/custom_predicates.py` (R1 + the new constant). **Next:** H4 orthogonal-yield (versionless); H1/H2 await Crucible.

## D108 — 2026-06-08 — H4 orthogonal-yield: marginal-value discount on the (hypothesis, directional, underlying-name) factor cell (versionless, A/B-flagged)

**Context.** The versionless arm of the new-hypotheses program (`NEW_HYPOTHESES_V11_PLAN.md` H4); follows [[D107]] (H3). D105 re-aimed the feedback reward to raw component-rate, which maximises components but over-concentrates sampling into *correlated* sleeves: on the 2026-06-08 live cohort the components pile into a handful of `volatility_event × {put_call_flow, iv_rank, put_wall} × high_idio_vol` cells, AAPL the top name (36 across directionals). The pod-shop uncorrelated-sleeve model (Millennium: 330+ *uncorrelated* sleeves, partitioned against alpha cannibalisation; Grinold 1989) says the marginal portfolio value of the 37th AAPL long-vol clone ≈ 0 — breadth the generator can't bank. H4 discounts each FACTOR CELL's underlying-draw weight by the Grinold marginal-value factor `(1 + m) ** -strength` (m = the cell's component count) so an over-mined cell yields draw probability to orthogonal candidates. No gate change (hard rule #3), no grammar change (versionless, like D101/D103/D105 components).

**Mechanism.** New `compute_orthogonal_yield_discounts(db, gated_runs, *, strength, min_discount, …)` in `rejection_weights.py` → `dict[(hyp, dir, name), float]`. Reuses the D105/D106 engine: `_component_rate_sums` with `tiebreak_weight=0.0` (H4 wants the pure component COUNT, not the ordering tiebreak the other weighters carry), version-scoped (D081: prior-version components weigh 0.25; cold-start hypotheses drop their prior rows). Discount = `max(min_discount, (1+m)**-strength)`; only cells with m>0 are returned (a 0-component cell is absent → the sampler defaults it to 1.0). Extracted a shared `_directional_indicator_of` helper (refactored out of D106's `compute_hypothesis_directional_bucket_weights`, identical logic). **Attachment:** the cell is only fully determined once the underlying (the name) is drawn, so the discount can only attach to `_pick_underlying`, conditioned on the already-chosen (hyp, dir). `sample_config` slices the triple map by the chosen (hyp, dir) → `{name: discount}` and passes it; `_pick_underlying` multiplies each ticker's existing D105/D106 weight by its name's discount BEFORE the exploration floor (so the floor stays the no-starvation guarantee). Threaded `enumerate_candidates` → CLI `_load_orthogonal_yield_discounts` + journal line + `_run_battery_for_seed`. **A/B flag:** `forge run --orthogonal-yield` (default OFF) — off skips the loader and passes `{}`, byte-identical to D105/D106 (hard rule #6).

**Emission-proof finding → name granularity (deviation from STATUS.md's "class", operator-approved via AskUserQuestion 2026-06-08).** STATUS.md scoped the cell as (hyp, dir, underlying-**class**). The required emission proof (live export ⋈ a read-only `forge.db` snapshot — the running service held the live DB lock, so analysis ran against a checkpointed copy) showed class granularity FAILS the goal: H4 attaches at the underlying draw, which only redistributes *within* a fixed (hyp, dir), and the only move at class granularity is high_idio→diversified — but diversified vol_event mints ~0.7% vs high_idio's 6.1%, so a class discount **dilutes raw yield rather than orthogonalising**. The real "36-on-AAPL" concentration is per-NAME inside high_idio. Switching the cell to (hyp, dir, **name**) lets the discount spread AAPL→NVDA/AMD (all minting peers): ~20% more name-concentration reduction per unit raw-yield cost, and the `(1+m)**-s` curve self-limits (only AAPL-grade cells bite; thin cells stay ~1.0, so name-level noise is contained by construction). This is the natural D105(class)→D106(name) progression. **Honest ceiling:** neither granularity can reach the dominant FACTOR (variance-risk-premium) concentration all high_idio vol_event components share — that needs hypothesis/directional diversification (H1/H2's domain), not the underlying draw. H4 is a QUALITY lever against a BREADTH-bound gate, so its ceiling is structurally modest (STATUS.md's own framing).

**Calibration (operator, AskUserQuestion 2026-06-08).** `DEFAULT_ORTHOGONAL_YIELD_STRENGTH = 0.15` (gentle: top live name cell AAPL m≈20 → 0.64 discount; steady-state first-order name-concentration -13% at raw-component-yield -17%, honouring "yield roughly flat" — and the pod-shop thesis says the discounted components are redundant clones, so portfolio-value yield is flatter still). `DEFAULT_ORTHOGONAL_YIELD_MIN_DISCOUNT = 0.25` (hard cap so a hugely over-mined cell can't be starved; the sampler's 0.01 underlying floor is a second, independent guard). Pure-sqrt (strength 0.5, STATUS.md's "1/√(1+37)") was confirmed too aggressive (~46% first-order raw-yield cut). Both are module constants, overridable; the flag is the experiment switch, the strength the dial.

**Hard rules.** #1 — no grammar/rule change (versionless). #3 — no gate change; this is enumeration scope. #4 — n/a (not a refiner proposal; an operator-directed feedback module like D101/D105). #5 — deterministic Python (pure function of submissions ⋈ gated snapshot). #6 — the discount is an ADDED sampler input; flag-OFF and empty-input paths are byte-identical, pinned by `test_h4_orthogonal_yield_flag_off_byte_identical` (invariants) + two sampler cold-start tests. #8 — blessed sources only (file-based gated export read + `db_connection`). #10 — n/a (no grammar bump).

**Anti-Goodhart (the D105-lineage regression).** The discount is computed off the COMPONENT count only (`tiebreak_weight=0.0`), so it is a pure function of components, never trades: a cell that trades heavily but mints zero components is ABSENT from the map (discount 1.0) — never inflated, never penalised for trading. Pinned by `test_zero_component_cell_is_absent_anti_goodhart`.

**Verification (TDD, RED→GREEN).** New `tests/unit/test_feedback/test_orthogonal_yield.py` (12: empty→{}, zero-component-cell-absent, exact Grinold math, monotone-in-count, cell separates directional+name, min_discount cap, strength=0 disables, default gentler than √, relative_value contributes no cell, prior-version downweight, cold-start drop, determinism). New sampler tests (cold-start byte-identical x2, tilts-away-from-crowded-name with mass preserved, exploration-floor-preserved, slices-by-hyp-dir-in-sample_config). New invariant `test_h4_orthogonal_yield_flag_off_byte_identical`. **Full unit suite 1,215 passed / 0; feedback+enumeration+cli+invariants 640/0; ruff + ruff format clean; mypy --strict clean (80 files).** Emission proof (`/tmp`, not committed) characterised the calibration against live data.

**Build location + deploy.** Built in the LIVE tree (like D107), but the flag-OFF-byte-identical property *is* the D104 guard here: the systemd unit command has no `--orthogonal-yield`, so a reboot restarting `forge.service` on the uncommitted code changes nothing (flag off → byte-identical). Deploy is a clean two-step the operator gates: (1) run the uncontended suite + commit + restart (still byte-identical, code landed); (2) add `--orthogonal-yield` to the unit + restart when ready to A/B. Forge cannot run the uncontended suite or self-restart — both the operator's.

**Files:** `src/forge/feedback/rejection_weights.py`, `src/forge/enumeration/sampler.py`, `src/forge/enumeration/iterator.py`, `src/forge/cli/main.py`, `tests/unit/test_feedback/test_orthogonal_yield.py` (new), `tests/unit/test_enumeration/test_sampler.py`, `tests/invariants/test_phase2_invariants.py`, `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`.

**References:** [[D105]] (the component-rate engine + class-level underlying weights this discounts; the over-concentration it caused), [[D106]] (the name-level granularity + `_directional_indicator_of` source this mirrors), [[D107]] (the H3 increment this follows; the breadth/component framing), [[D101]] (versionless feedback precedent), [[D081]]/[[D098]] (version scoping + cold-start), [[D067]] (exploration-floor diversity guard), [[D104]] (worktree rule — neutralised here by the flag), Grinold (1989) fundamental law, `NEW_HYPOTHESES_V11_PLAN.md` §4 H4, hard rules #3/#5/#6/#8.

**STATUS: BUILT + VERIFIED; flag defaults OFF (byte-identical); deploy + flag-flip operator-gated.**

---

## D109 — 2026-06-08 — H1 cross_sectional_rank combiner (breadth lever) + H2 event_momentum/PEAD hypothesis — bundled grammar v11 → v12

**Context.** The two contracts-gated arms of the new-hypotheses program (`NEW_HYPOTHESES_V11_PLAN.md` H1/H2; follows [[D107]] H3 + [[D108]] H4) — both unblocked when Crucible landed + verified the upstream on 2026-06-08: contracts **1.16.0** (`CombinerSpec.rank_k`/`rebalance_frequency`/`direction_mode`; `event_momentum` hypothesis literal; `post_event_drift` family literal), the `cross_sectional_rank_composable` runner (reads `combiner.rank_k`), `event_momentum` dispatch, the `days_since_earnings`→`calendar` reclassification, and Polygon EPS ingest (verified Forge-side against `../Crucible` + `../crucible_contracts`; confirmed by Crucible's `FORGE_days_since_earnings_family_response.md`). **Operator chose to BUNDLE H1+H2 into one v12 bump** (AskUserQuestion 2026-06-08) — the spec's lead path was H1=v12 / H2=v13 *once §2.1 resolved*, but §2.1 was already resolved upstream, so bundling is the spec's own sanctioned fallback. The binding constraint is **breadth**: `min_oos_trade_count ≥ 100` kills ~98% of candidates, 0 promotions ever, components are the currency (1.83%); vol_event mints ~5× the directional archetypes because events *recur* → breadth. H1 manufactures breadth structurally; H2 is a new directional thesis that rides the event calendar.

**The §2.1 resolution (load-bearing for H2).** `sue` AND `days_since_earnings` both lived under family `post_event_drift`, and C1 forbids two same-family indicators in one config — which would block the PEAD structure (sue directional + days_since_earnings timing gate). Crucible reclassified **`days_since_earnings` → `calendar`** (the backward twin of `days_to_earnings`) via the per-id override (`exports.py:207`, same mechanism + same C1 driver as `adx`/`hurst`→`trend_strength`). So `sue` (post_event_drift) + `days_since_earnings` (calendar) now coexist under C1. No config_hash impact (family is export-only metadata).

**H1 — cross_sectional_rank combiner (the breadth lever).** New `RANK_COMBINER_HYPOTHESES = {trend_continuation, mean_reversion, event_momentum}` (the breadth-starved DIRECTIONAL archetypes; vol_event already clears breadth via recurring events, relative_value is pairs). `sample_config` gains `rank_combiner_share: Mapping[str,float] | None`: for an eligible hypothesis it draws a `cross_sectional_rank` combiner with that probability (`rank_k∈{5,10,20}`, `rebalance_frequency∈{weekly,monthly}`, `direction_mode∈{long_only,long_short}`) and sets `underlying=None` (the runner ranks `universe.tickers(asof,tier)` — a single name is meaningless). The draw is the LAST decision and gated so the cold/`{}`/0.0-share paths consume ZERO rng and stay byte-identical (hard rule #6). Trade count becomes DETERMINISTIC (`~directions × rank_k × rebalances` ≫ the 100-trade floor) — the whole point. **The load-bearing correctness point:** `ExpectedTradesFilter` keyed a rank config on the stale SINGLE-NAME `(hypothesis, bucket, family)` prior (trend/mean_rev fire ~1 trade single-name → it would KILL the rank config, defeating the breadth win), so a structural branch (`_apply_structural_rank_estimate`) estimates `directions × rank_k × (window / rebalance_period)` instead. **Routing (verified, no Forge action):** Crucible's `_detect_strategy_name` (`runner.py:602-607`) routes a `forge_`-prefixed config with `combiner.type=="cross_sectional_rank"` to the composable rank runner *before* the legacy-name check — so the belt-and-braces `top_n`/`bottom_n` stamp the spec hedged on is NOT needed. config_hash: the rank fields are identity-bearing only for rank type (contracts drops them at sentinel otherwise), so rank configs dedup correctly and the additive bump never re-keys an existing config. **Rank emission is ON by default** at the ~1/3 exploration share (`_DEFAULT_RANK_COMBINER_SHARE`) — the point of v12, and "like every prior weight addition" per the spec (D105/D106 weights are always on in production; production passes the share, the sampler-core `None` default keeps tests/determinism byte-identical, #6). `forge run --no-cross-sectional-rank` is an operational KILL SWITCH (passes `{}` → every config confluence) for the first-time-new-runner path, not an opt-in gate. (Originally implemented flag-OFF mirroring H4; flipped to on-by-default on operator review — H4 was a quality lever needing calibration proof, H1 is the breadth lever and the whole point of the bump.) Share is flat ~1/3 across the three archetypes for now; feedback can rebalance (e.g. heavier on event_momentum, whose single-name form is sub-floor per §2.4).

**H2 — event_momentum / PEAD (new directional hypothesis).** Routes to `composable_long_options` (single-name, like trend/mean_rev/vol_event). Wiring, all Python-side enumeration policy (no new grammar.yaml rule): `_C2_HYPOTHESIS_FAMILIES["event_momentum"]=("post_event_drift",)` → directional = `sue`; `_build_regime_pool` pins the regime pool to `_EVENT_MOMENTUM_REGIME_INDICATORS=("days_since_earnings",)` (the post-event TIMING gate — folded into the pool builder like R1/R2/R3's pools, NOT a 22nd validator rule, hard rule #1); `_S5_HYPOTHESIS_EXITS["event_momentum"]` = drift-decay `time_stop` (required_from_set) + `trailing_atr`/`chandelier_exit` (optional momentum trailing) + `hard_profit_target` forbidden (convex payoff, like the winners). Thresholds: `sue` directional (op `">"`, 1–2σ strong surprise → upward drift → long calls), `days_since_earnings` regime (op `"<"`, {3..10} td — "fire within N td AFTER the print", the PEAD edge: sidesteps the pre-print IV crush the vol_event sleeves ride → structurally orthogonal). Signal horizon: `sue` 10 td (drift window) → medium_lookback → swing_short/mid; added to `_HORIZON_MATCHED_HYPOTHESES` so DTE = `k × 10` ∈ {20,30,40}. **Single-name by construction:** `days_since_earnings` sentinels on ETFs (no earnings) exactly like `days_to_earnings`, so the `_pick_underlying` ETF exclusion was extended to it (`_EARNINGS_CALENDAR_ETF_INCOMPATIBLE`) — only event_momentum draws it, so every pre-v12 hypothesis's underlying draw stays byte-identical. event_momentum is ALWAYS enumerable in v12 (not flag-gated). §2.4: PEAD on a single name ≈ 20 earnings/5y (sub-floor), so its productive form is cross-sectional → it is also rank-eligible (H1 supplies its breadth).

**Why v12 has NO `rules:` text change (hard rule #1).** S1 is a `cardinality` rule (`hypothesis count == 1`) — it does not enumerate hypothesis values; those live in the contracts `StrategyConfig.hypothesis` Literal (1.16.0 adds `event_momentum`). The combiner type lives in `CombinerSpec`. Neither is in the rules text, so both additions are pure Python-side enumeration policy — the v5–v11 pattern. The 21 operator-owned rules are textually untouched (`len(grammar.rules) == 21`).

**Hard rules.** #1 — no rules-text change (above); the event_momentum regime requirement is the pool builder, not a new rule. #2 — contracts-only; `FORGE_EXPECTED_CONTRACT_VERSION` 1.15.0→1.16.0 (minor/additive; §13.5 is MAJOR-only, so hygiene + suite-correctness, the editable install already serves 1.16.0). #3 — no gate change (breadth is enumeration scope, not validation strictness). #4 — these are enumeration-scope LOOSENINGS but operator-DIRECTED (the bundle decision), so the hard-rule-#10 supervised path (version bump + archive + this entry), not a refiner auto-proposal. #6 — the rank draw is an ADDED, gated sampler input (cold path byte-identical, pinned by `test_cold_path_byte_identical` + the existing golden sampler-sequence tests); event_momentum is a new hypothesis (no prior sequence to preserve), and its ETF-exclusion + regime-pool changes touch only the new hypothesis. #8 — blessed sources only. #10 — `grammar_version` v11→v12, `grammar_archive/v12.yaml` byte-identical (loader archive-consistency verified), this Decision Log entry; both grammar pre-commit hooks pass (no rule-ID change → doc-sync OK; bump + archive present → version-bump OK).

**Verification (TDD, RED→GREEN throughout).** New: `tests/unit/test_grammar/test_event_momentum_grammar.py` (10 — C1 coexist, C2 family, S5 exits, the per-hypothesis pools), `tests/unit/test_enumeration/test_event_momentum.py` (10 — sue/days_since_earnings thresholds + horizons, horizon-matched DTE, valid-config sampling, single-name-never-ETF, determinism), `tests/unit/test_enumeration/test_cross_sectional_rank.py` (9 — scope, forced-rank emission for trend/event_momentum, cold-path byte-identical, 0.0-share + ineligible no-perturbation, config_hash distinctness), 3 structural-rank tests in `test_expected_trades.py` (passes-despite-poisoned-single-name-prior — the load-bearing invariant — + scales-with-k/direction + weekly>monthly), 1 CLI flag test. Updated canonical-set assertions: `test_search_space` (hypotheses tuple), `test_sampler` (reaches-every-hypothesis), `test_run_loop` (D063/D065 ordering), `test_v1_grammar` (v11→v12, 21 rules). **Full suite 1,396 passed / 0 failed** (service live → contended; the operator's uncontended re-run is the deploy gate); ruff + ruff format clean; mypy --strict clean (80 source files); both grammar pre-commit hooks exit 0; `v12.yaml` byte-identical (loader archive-consistency verified live: `grammar_version=v12`, 21 rules).

**Build location + deploy.** Built in the LIVE tree (like D107/D108). **D104 caveat is live and salient:** rank is on-by-default and event_momentum is always-on, so the uncommitted v12 in the working tree is NOT reboot-safe — a reboot auto-starting `forge.service` on the dirty tree would silently deploy v12 with rank emission live, before the operator's ritual (exactly the D104 failure mode, now with the rank arm). The sampler-core no-share byte-identical property is a *determinism* guarantee (tests/reproducibility), not a reboot guard. → **commit promptly, or be aware of the window** (the operator could alternatively rebuild in `../Forge-build` per the strict D104 rule, but the work is already in the live tree). Deploy (operator-gated): stop `forge.service` → full uncontended suite → commit D109 + v12 → restart onto v12 — **rank goes live by default, no flag flip needed** (`--no-cross-sectional-rank` only if killing it). **Attribution:** `crucible funnel --compare v11 v12` is the headline; both arms self-identify in `config_json` (combiner.type / hypothesis), so the by-feature decision-rate join (forge.db ⋈ gated export) attributes each even bundled — expect rank configs' median n_trades ≫ 100 by construction, and event_momentum's component-rate read once a cohort gates. Forge cannot run the uncontended suite or self-restart onto a grammar bump — both the operator's.

**Files:** `config/grammar.yaml` (+ `config/grammar_archive/v12.yaml`), `src/forge/grammar/custom_predicates.py`, `src/forge/enumeration/search_space.py`, `src/forge/enumeration/sampler.py`, `src/forge/enumeration/indicator_thresholds.py`, `src/forge/grammar/signal_horizon.py`, `src/forge/enumeration/iterator.py`, `src/forge/prefilters/expected_trades.py`, `src/forge/cli/main.py`, `src/forge/core/contracts_check.py`, `docs/GRAMMAR.md`, `tests/fixtures/strategy_configs.py`, `tests/unit/test_grammar/test_event_momentum_grammar.py` (new), `tests/unit/test_enumeration/test_event_momentum.py` (new), `tests/unit/test_enumeration/test_cross_sectional_rank.py` (new), `tests/unit/test_prefilters/test_expected_trades.py`, `tests/unit/test_enumeration/test_search_space.py`, `tests/unit/test_enumeration/test_sampler.py`, `tests/unit/test_cli/test_run_loop.py`, `tests/integration/test_v1_grammar.py`, `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`.

**References:** [[D107]] (H3 — the new-hypotheses program's grammar-gated precedent + the breadth/component framing), [[D108]] (H4 — the `--orthogonal-yield` A/B-flag pattern `--cross-sectional-rank` mirrors), [[D105]]/[[D106]] (the weight-addition determinism-gating pattern the rank draw mirrors), [[D102]] (horizon-matched DTE + the Forge-owned signal_horizon table), [[D098]] (Python-side enumeration policy without a rules-text change; ETF/cold-start precedents), `H1_H2_V12_IMPLEMENTATION_SPEC.md`, Crucible `FORGE_days_since_earnings_family_response.md`, `NEW_HYPOTHESES_V11_PLAN.md` §4 H1/H2, hard rules #1/#2/#3/#4/#6/#10.

**STATUS: DEPLOYED + VERIFIED LIVE 2026-06-08 (commit `30d628d`, pushed to origin). `grammar_version=v12` healthy (NRestarts=0, no errors); clean cutover (0 submissions leaked in the hot-YAML window — §7.3-blocked). H1 rank emission ON by default (~1/3 share; `--no-cross-sectional-rank` kill switch) — emits on the first unblocked iteration; H2 event_momentum always-on. A/B via `crucible funnel --compare v11 v12` once a v12 cohort gates.**


## D110 — 2026-06-08 — Aged-out watermark recalibration (`min(decided_at)` → `max(decided_at) − STRANDED_AFTER`)

**Spec section:** §7.3 rate limiter; §8.2 feedback consumer; [[D052]] (aged-out flush), [[D046]] (oldest-batch policy), [[D061]] (the prior flush-no-op wedge).

**Context — production wedge.** `forge.service` generated **zero** candidates under v10/v11/v12: ~17h stalled, **758 consecutive blocked iterations** (06-08 00:01→15:37), every one logging `blocked: oldest in-flight batch ba92e7ee … 0.0% gated (0/200)`. The §7.3 limiter (D046 oldest-batch policy) was pinned on batch `ba92e7ee` (submitted 2026-05-29, 0/200 gated). Diagnosis of the live `forge.db` snapshot: **274 of 279 in-flight batches stranded** (48,198 `submitted` rows, May 29→Jun 07), none in Crucible's current export window. D052's `_flush_aged_out_submissions` — which exists precisely to clear such rows — was a silent no-op.

**Root cause.** D052's watermark is `min(decided_at)` over the export, valid only when the export is a shallow, time-contiguous window (it was top-1000 at D052). The gated-runs publisher now exports **top-10000**, and a **re-gate spike** on 2026-06-07 (~7,056 decisions in one day — 70% of the window) compressed the window's time-span from a normal ~40-60 days to ~13 days, dragging `min(decided_at)` UP to **2026-05-26** — *just below* the entire May-29+ stranded backlog. So `submitted_at < min(decided_at)` matched nothing and the backlog never flushed. Same wedge *symptom* as D061, different *mechanism*: D061 was an aware-vs-naive tzinfo coercion; this is watermark **calibration** under a window-shape the original heuristic didn't anticipate.

**Decision.** Recalibrate the watermark to `max(decided_at) − STRANDED_AFTER` (`STRANDED_AFTER = timedelta(days=8)`). It tracks Crucible's *newest* decision (its processing clock) minus a latency margin, and is immune to window-span compression. The D052 dual guard (`config_hash NOT IN export_hashes`) and the D061 naive-watermark conversion are retained.

**Why each choice:**
- **`max` not `min`:** `min` marks the window's *trailing* edge, which a re-gate spike moves arbitrarily; `max` marks Crucible's *leading* edge (processing frontier), which only advances with real progress.
- **Margin, not bare `max`:** bare `max` would flush rows Crucible simply hasn't decided yet — voiding §7.3 backpressure. The margin must exceed real submit→decide latency.
- **8 days:** above the observed p99 (~7.2d; itself biased *high* by window survivorship, so the true p99 is lower). Conservative — structurally cannot flush legitimately-pending work. **Tunable DOWN** once the true latency distribution is known (the paired Crucible-throughput investigation).
- **`max(decided_at)` not `utc_now()`:** if Crucible dies, `max(decided_at)` freezes and the flush stops advancing — pending rows are preserved (safe). `utc_now()` would keep flushing through an outage, eventually voiding the throttle. Also keeps the function clock-free (hard rule #8).

**Hard rules check:**
- #2 (no Crucible internals): contracts `GatedRun` only; no new imports.
- #6 (determinism): touches `submissions` rows only; no enumeration/seed dependency.
- #8 (blessed clock): watermark derived from contracts `decided_at`, not `datetime.now()`.
- #9 (submission idempotency): the sentinel UPDATE stays gated by `WHERE status = 'submitted'`; re-runs are no-ops.

**Alternatives considered:**
- **One-time manual SQL flush of the 48,198 rows, defer the code fix.** Rejected for the same reason as D061's parallel alt — the backlog regrows on the next window churn and the structural defect persists. (Operator may still apply it as a *convenience* for faster recovery; see below.)
- **Bare `max(decided_at)` (no margin).** Rejected — flushes still-pending batches, voids §7.3.
- **`utc_now() − margin`.** Rejected — keeps flushing during a Crucible outage; `max(decided_at)` freezes safely.
- **Inbox-disposition-aware flush** (mark configs in `inbox/errors/` terminal immediately). Deferred — larger scope, folded into the Crucible-throughput investigation; the watermark fix alone restores self-healing.

**Recovery profile (operator note).** The conservative 8d margin self-heals **gradually**: each stranded batch flushes as it ages past 8d behind `max(decided_at)`, so the May-29→Jun-07 backlog clears over ~1 week (sooner if Crucible gates the live backlog). After the dead head clears, the limiter correctly throttles on the *live* multi-day backlog — that is §7.3 working as designed, not a bug. v12 throughput remains bounded by Crucible's gating rate (the 67× produce-vs-gate mismatch of [[D070]]), which the paired investigation targets. For immediate full recovery the operator may one-time-flush the pre-`max−8d` `submitted` rows to the D052 sentinel.

**Verification:**
- 2 new unit tests in `tests/unit/test_feedback/test_consumer.py`: `test_d110_flushes_stranded_row_in_deep_export_window` (deep/compressed window — red on `min`, green on `max−margin`), `test_d110_does_not_flush_recent_row_within_stranded_margin` (margin safety boundary). Both confirmed red on the pre-fix watermark for the right reason.
- 2 existing D052 tests updated (`…_flushes_predates_export_window`, `…_aged_out_flush_idempotent`): stranded `submitted_at` widened to 2026-05-01, beyond the new margin. Helper `_insert_crucible_gated` gained an optional `decided_at`.
- 24/24 consumer tests; **517 passed** across `tests/{unit/test_feedback,unit/test_cli,unit/test_submission,integration,invariants}`. Ruff check + mypy strict clean on changed scope (test file format follows the repo's pre-existing hand-style; not reformatted — pre-commit format is bypassed tree-wide).

**Files:** `src/forge/feedback/consumer.py` (`STRANDED_AFTER` constant + watermark line + docstring), `tests/unit/test_feedback/test_consumer.py` (2 new + 2 updated tests, helper param), `IMPLEMENTATION_DECISIONS.md` (this entry).

**References:** [[D052]] (original aged-out flush + dual guard), [[D061]] (prior flush-no-op wedge; tzinfo), [[D046]] (oldest-batch limiter this protects), [[D070]] (67× produce-vs-gate mismatch — the throughput constraint), [[D083]] (sentinel exclusion from §7.3).

**STATUS: code complete + green; awaiting operator restart of `forge.service` to deploy (self-heals on the first reconcile pass). Paired Crucible gating-throughput investigation pending.**

## D112 — 2026-06-09 — Dealer indicators single-name only (no rank/universe pairing); grammar v12 → v13

**Spec section:** §3.5 R1/R2 (pools untouched for single-name), §5 enumeration policy; [[D062]] (dealer indicators admitted), [[D107]] (gamma regime switch), [[D109]] (H1 rank combiner). Origin: Crucible handoff `../Crucible/docs/handoffs/FORGE_dealer_indicator_sampling.md` (2026-06-09).

**Context.** Crucible asked Forge to restrict dealer indicators (`gamma_flip_distance_pct`, `gex`, `vex`, `cex`, `call_wall_distance_pct`, `put_wall_distance_pct`) to single-name templates: the dealer headline series is a per-bar greek grid costing ~100× a single-name headline when multiplied across the universe (5–14 min vs 1–3 s — the serial runner's throughput tail), while their decided "cross-sectional dealer" cohort (n=221) showed negative mean WF and zero §8.7-gate clears. Single-name dealer configs are the pool's promotion frontier (the only CPCV-p25 ≥ 1.5 clears) and stay at full weight.

**Premise verification (per `crucible-handoff.md` — partially corrected).** Joined the fresh export (06-09 19:02Z, 10k rows) to `submissions` on `config_hash`: every headline number reproduced byte-for-byte (n=221, comp 2.71%, mean WF −0.070, max 1.665, CPCV max 0.847; single-name: max WF 2.225, 2 CPCV clears max 1.537). **But the 221-row cohort is two populations Crucible conflated:** (a) **199 legacy v9-era `relative_value` universe-scans** (null underlying, confluence; dealer gate from rv's unconstrained regime pool) — comp 2.01%, mean WF **−0.129**, max 0.703: ALL the negative signal; (b) **22 v12 rank×dealer configs** — comp **9.09%** (2 components, both MR rank gated by `gamma_flip_distance_pct`, WF 1.264/1.665), mean WF **+0.464**: the best dealer subset in the window, though 0 CPCV clears (max 0.847). So "loses no promotion-relevant edge" is wrong as stated for the v12 arm — but nothing on the actual CPCV frontier is lost, and the **cost story is decisive**: rank×dealer was 36/200 of current emission (40% of rank draws) + 2/200 legacy-shape rv×dealer ≈ 19% of submissions consuming ~96% of runner headline compute, with Crucible decisions/day the pipeline's binding constraint ([[D110]], ~9.5/hr observed 06-09).

**Decision (operator-approved, AskUserQuestion 2026-06-09: "Full cut + decomposition report").** Dealer_positioning indicators become single-name only, both universe shapes:
1. **Rank branch skip (sampler):** a config that drew ANY dealer-family signal never takes the H1 `cross_sectional_rank` branch — checked before the rng draw, so the skip consumes no entropy and non-dealer draw sequences are unchanged. The dealer config keeps its signals + pinned underlying → single-name dealer emission **rises organically** (the handoff's "arguably increase it" parenthetical, without touching feedback weights — D105/D106/D108 already reward minting cells).
2. **rv pool exclusion (search_space):** `relative_value` (the always-universe pairs template, 15,741/15,741 null-underlying) loses the dealer family from its previously unconstrained regime pool.

Keyed on `IndicatorMetadata.family == "dealer_positioning"` (new `DEALER_POSITIONING_FAMILY` in `search_space.py`) — robust to Crucible adding dealer indicators. Tightening (hard rule #4 — allowed); enumeration-policy bump only, the 21 `rules:` textually unchanged (hard rule #1, the v5–v12 pattern); single-name pools untouched (D107 gamma gates, D062 MR/VE dealer directionals all keep full weight).

**Hard rules check:** #1 rules untouched (v13 header note only); #3 no gate change; #4 tightening; #6 cold/`{}`-share path byte-identical (rank block short-circuits before the dealer check; invariant suite green), versioned change for the warm path; #7 untouched; #10 bump + archive + this entry.

**Alternatives considered:** keep MR×gamma-regime rank at reduced share pending n≥100 (operator declined — leaves ~70% of the 5–14 min tail on a stalled runner); report-only (declined — runner keeps stalling); re-roll instead of skip on dealer rank draws (rejected — extra rng for an impossible outcome; the skip is the simplest deterministic shape and boosts the frontier cohort).

**Verification (TDD RED→GREEN):** new `test_rank_draw_skipped_for_dealer_signal_configs` (confirmed RED: dealer mr config emitted `cross_sectional_rank` pre-fix) + `test_regime_pool_relative_value_excludes_dealer_positioning` + phase-2 invariant `test_dealer_indicators_are_single_name_only` (universe-wide ⇒ no dealer; keep-side guard: single-name dealer still emitted). Deliberate re-pins: `test_rank_combiner_emitted_when_forced` (skips dealer draws), the two D107 `_build_regime_pool` direct calls (new `dealer_ids` kwarg), `test_regime_pool_unconstrained_hypothesis_uses_full_registry` (rv moved out), `test_v1_grammar_loads` (v13). **Emission proof (live registry, hash `a99e00d68567af59`, 3,000 samples, rank share 1/3):** 0 universe×dealer violations; single-name dealer 905 (30.2%); universe-clean 1,003; hypothesis mix healthy — incl. **event_momentum 610 (Q30 RESOLVED: Crucible republished 06-09 18:45:50Z, `days_since_earnings` → `calendar`)**. Scoped suites 669/0; full suite 1,415/1 (the 1: `test_cli_help` table flake, passes in isolation — contended run, live service up; uncontended re-run is the deploy gate); ruff + format(changed files) + mypy --strict (82 files) clean; both grammar hooks pass.

**Files:** `src/forge/enumeration/search_space.py` (constant + `_build_regime_pool` dealer_ids), `src/forge/enumeration/sampler.py` (`_uses_dealer_positioning` + rank-branch guard), `config/grammar.yaml` (v13 + header note), `config/grammar_archive/v13.yaml`, tests (3 files), `docs/tasks/grammar-change.md` (hook-invocation fix), `OPEN_QUESTIONS.md` (Q30 resolved), `PROMPT_CRUCIBLE_DEALER_SINGLE_NAME_RESTRICTION.md` (decomposition report — operator passes to Crucible), `STATUS.md`, this entry.

**References:** [[D062]] (dealer admission), [[D098]] (rv underlying=None), [[D107]] (gamma regime switch — single-name side kept), [[D109]] (H1 rank combiner), [[D110]] (Crucible capacity is the binding constraint). D111 is reserved by the pre-existing `d111-verdicts-expected-trades` branch (verdict-persistence / Q29 work, not started).

**STATUS: code complete + green in `../Forge-build` (branch `d112-dealer-single-name`); awaiting the D104 deploy ritual (stop service → uncontended suite → merge to main → restart → verify → relay v13 + timestamp to Crucible for `funnel --compare v12 v13`).**

---

## D111 — 2026-06-09 — Durable per-candidate verdicts table (+ backfill script)

**Spec section:** §8.2 feedback consumer (side-effect extension), §9.1 Forge DB; [[D052]]/[[D110]] (rolling-window flush — the data-loss mechanism this fixes). Origin: the 2026-06-09 data-driven pipeline review, recommendation 2 (operator-approved schema via AskUserQuestion). Numerically out of order in this log because D112 (begun by a parallel session the same afternoon) was committed first; chronological order preserved.

**Context.** Crucible's gated export is a rolling top-10k window; Forge persisted only batch aggregates (`promotion_rate`, `common_failures`) plus the submissions status flag. Consequences measured in the review: per-candidate verdicts recoverable for only **13.2%** of 92,389 closed submissions (80,163 D110-flushed rows have none, their batches' `common_failures` are `{}`); every feedback weight load is hostage to window composition (the 06-07 re-gate spike was 70% of the window — the D110 wedge's root enabler); per-version cohort analysis impossible beyond the window's reach.

**Decision.** New `verdicts` table — PK `crucible_run_id` (re-gates are new run_ids → append, never overwrite), `config_hash`, `decision`, `decided_at`, `trade_count`, `grammar_version`, `gate_results` JSON (full 11-gate values+thresholds), `recorded_at`. Written by new `forge.persistence.verdicts.record_verdicts`, called from `reconcile_all_pending` on every poll: sweeps the ENTIRE export against all known submission hashes (not just pending batches), so re-gates of completed batches are captured too. Idempotent via `INSERT OR IGNORE`. `decided_at`: aware → naive UTC; **naive passes through verbatim** — the export's PDT-naive skew (found in the same review; `PROMPT_CRUCIBLE_RUNNER_CAPACITY_STABILITY.md` asks for the fix) is not coerced client-side because a +7h shift would double-shift the moment Crucible emits aware UTC. One-time `scripts/backfill_verdicts.py` ingests an export snapshot through the same code path (deploy stop-window; verified against the saved 2026-06-09T185130Z snapshot: 10,000 rows, all matched).

**Alternatives considered:** columns on `submissions` (rejected: ALTER on the hot table, one verdict per config — re-gates overwrite history, flushed rows conflated); recording only in `consume_batch_results` (rejected: misses re-gates of completed batches; the manual `forge feedback` path is covered anyway since the loop's sweep is global).

**Verification (TDD RED→GREEN):** 9 tests in `tests/unit/test_feedback/test_verdicts.py` (schema, matched-insert, unknown-hash skip, idempotency, re-gate append, aware→naive-UTC, naive-verbatim, reconcile wiring, sentinel-flush exclusion) + 3 in `tests/integration/test_backfill_verdicts.py` (insert/idempotent/dry-run). Full suite 1,413/0 post-untangle on the branch; mypy --strict clean (82 files); ruff + format clean.

**Files:** `src/forge/persistence/schemas.py` (DDL + TABLE_NAMES), `src/forge/persistence/verdicts.py` (new), `src/forge/feedback/consumer.py` (one call + docstring), `scripts/backfill_verdicts.py` (new), tests (2 new files), `docs/MANPAGE.md` (table + script), `STATUS.md`, this entry.

---

## D113 — 2026-06-09 — expected_trades tightening REFUTED by measurement — no code change

**Spec section:** §5.3.4; [[Q29]](a), [[D076]]/[[Q16]] (the empirical-prior mode under test), [[D105]] (fat-tail pass-through note). Origin: the 2026-06-09 review, recommendation 3 — "~48% of Crucible's window decisions realized <10 trades; recalibrate the prefilter."

**Decision: ship nothing.** Every candidate tightening was tested counterfactually against the D111 verdicts ⋈ `pre_filter_logs` join (10,130 rows — realized trade counts vs what the filter saw at evaluation time) and failed:

1. **Raise `min_pass_probability` (0.10 → 0.25):** the posterior bands [0.15, 0.25) hold 63%/56% zero-trade waste AND 115 of the 140 empirical-mode components. The cut captures ~2,300 zero-trade configs at the cost of **82% of the component frontier**. The bucket posterior cannot separate waste from yield because vol_event's fat tail puts both in the same `(hyp, bucket, family)` cells — exactly D105's pass-through note, now quantified.
2. **New P(zero-trade) bucket knob** (Beta-smoothed `n_zero_trade/n_total`, already logged): equally poisoned — its natural cut band [0.5, 0.6) contains 104 components.
3. **Finer cells (+underlying):** safe by construction (cull only ≥80%-zero, 0-component, n≥20 cells) but captures just **14% of v9-era zero-trade waste** (539 configs, 24 cells — mr×swing_mid oscillator singles on ETFs, ve×dealer on low-vol names: shapes D105/D106 weights and the D112 dealer cut already starve).
4. **The decisive baseline: the waste already collapsed upstream.** v12-cohort verdicts: **1% zero-trade / 10% sub-10-trade** vs v9's 40%/49%. The review's 48% headline was a v9-mix artifact; the allocation re-aim + H1 rank (structural trade counts) + D112 fixed it at the sampler, where Q29(a) said the real fix lives.

**Monitoring (replaces the change):** per-version waste rate is now one query against `verdicts` — `SELECT grammar_version, AVG(CASE WHEN trade_count < 10 THEN 1.0 ELSE 0.0 END) FROM verdicts GROUP BY grammar_version`. Re-open Q29(a) if a post-v13 cohort (≥500 decided) shows sub-10-trade share back above ~25%; the verdicts table then supports the per-(indicator, role, band) attribution that a sampler-side threshold-draw fix needs.

**Files:** `OPEN_QUESTIONS.md` (Q29 updated), `STATUS.md`, this entry. No production code touched.

## D114 — 2026-06-09 — joint-quality term in the component-rate reward (versionless feedback change)

**Spec section:** §6.3/§8 (feedback weighting); [[D105]]/[[D106]] (the component-rate engine this amends), [[D111]] (the verdicts analysis that motivated it), [[Q32]] (the admission-rule change it is robust to). The D094 → D101 → D103 → D105 → D106 → D108 lineage's next re-aim.

**Problem.** The component-rate estimand learns from a binary event that is (a) rare — 2.4% all-time, so a cell needs ~50+ decided runs before its posterior escapes the prior — and (b) admission-rule-dependent: Q32 showed Crucible began enforcing `regime_coverage` ~2026-06-08 09:00 PDT, zeroing single-name component admission for *window-shape* reasons while the strategies' measured quality was untouched (66 otherwise-passing rejects in ~30h, including `d964e908` — WF 2.225/gate 2.0, CPCV-p25 1.537/gate 1.5, the only both-quality-gates pass in 10,089 archived decisions). Under the old reward the post-cut cohort teaches every weighter "single-name died"; the lesson is wrong.

**Decision.** A rejected run now earns `COMPONENT_QUALITY_WEIGHT × clamp(min(wf/thr_wf, cpcv/thr_cpcv), 0, 1)` in `_component_run_reward`, where the values AND thresholds come from the run's own `walk_forward_sharpe_median` / `cpcv_sharpe_p25` gate rows (robust to Crucible recalibration), eligible only when the run passed its own `min_oos_trade_count` gate. Component/promote events stay at exactly 1.0. The term threads through `_component_rate_sums` so every granularity inherits it (hypothesis, (hyp,bucket), triples, underlying class/name, rv-regime) with **zero sampler/CLI changes**; H4's discount passes `quality_weight=0.0` (its `m` stays a pure component count).

**Why a MATERIAL weight where D105 demoted continuous signals to epsilon:** the D105 Goodhart was trade-correlated signals (gate_fraction/traded). The joint quality score is different in kind: (a) trading volume cannot farm it — corr(trade_count, cpcv_p25) ≈ −0.14 on the live cohort, and the min_oos eligibility gate only zeroes sub-floor runs, never rewards volume; (b) admission-rule changes cannot move it (regime_coverage is deliberately not consulted — pinned by test); (c) it is the actual promotion objective, not a proxy. The D105 "no volume can outrank one component" bound now holds only for zero-quality volume — the departure is deliberate and test-documented (`test_sustained_quality_can_rival_a_sparse_component`).

**Calibration (live-data emission proof, export 10k ⋈ /tmp snapshot, v13-scoped):** `COMPONENT_QUALITY_WEIGHT = 0.25` — one component event ≡ 4 frontier-grade rejects (joint score 1.0). The signal is sparse by construction: 7.7% of 10,089 verdicts are quality-eligible; joint score median 0.037, p90 0.345, only 4 runs ≥ 0.75 (the all-time joint near-misses). Proof deltas at 0.25: hypothesis weights nearly unchanged (ve 0.911 → 0.928, ordering preserved); quality-rich cells gain relative mass — SOXL 0.0675 → 0.0725 (+7.4%), (ve, put_wall, swing_short) +6.7%, AAPL/AMD/NVDA +4-6% — junk cells flat. The differential GROWS as post-Q32 coverage-killed rejects accumulate: their quality values keep crediting the cells the binary event abandons. 0.5 tested and rejected (more aggressive, no ordering change — not worth the noise sensitivity of a single backtest's Sharpe).

**Verification (TDD RED→GREEN):** new `tests/unit/test_feedback/test_quality_term.py` (12: exact min/clamp math, own-trade-floor eligibility, missing-data-never-inflates ×4 shapes, component-still-ceiling, reward composition, **the Q32 pin** — regime_coverage cannot move the reward, junk-volume anti-Goodhart preserved, sustained-quality departure documented, H4 blind to quality, cold-start `{}` unchanged, determinism). Existing 245 feedback tests pass **without re-pins** (their fixtures carry synthetic gate names, so `_joint_quality` = 0 for all of them — the old numbers were already correct). Full worktree suite **1,431/0**; ruff + format clean on changed files; mypy --strict 0/82.

**Attribution:** versionless — invisible to `funnel --compare`. Read it in: (a) the journal weight lines' drift toward quality cells on the first post-deploy load; (b) per-cell weight-vs-realized-quality joins against `verdicts`. Success metric: when Q32 resolves (either branch), the weights did NOT crater the single-name quality cells in the interim.

**Deferred (logged here, not built):** switching the engine's data source from the rolling gated export to the durable `verdicts` table (kills the D111 window-composition sensitivity entirely; needs a GatedRun-equivalent reader + version-scoping rework — its own focused unit); an explicit Q32 era-split of the binary component evidence (the quality term reduces the urgency; revisit with Crucible's answer to the regime_coverage prompt).

**Files:** `src/forge/feedback/rejection_weights.py`, `tests/unit/test_feedback/test_quality_term.py`, this entry, `STATUS.md`.

---

## D115 — 2026-06-09 — Crucible confirms the rank-path dealer gate was inert/fixed-SPY (never per-name) — re-admission precondition rewritten; no code change

**Spec section:** none touched (docs-only); [[D112]] (the v13 cut this validates), [[D107]] (single-name gamma arm — unaffected, now the designated evidence source), [[D109]] (H1 rank combiner), [[Q32]] (sibling rank-path fail-open finding). Origin: incoming handoff `../Crucible/docs/handoffs/FORGE_dealer_rank_gate_cost_asymmetry.md` (2026-06-09, their response to `PROMPT_CRUCIBLE_DEALER_SINGLE_NAME_RESTRICTION.md`).

**What Crucible answered.** Ask #2 (does a regime-gate-only dealer rank config pay the full per-name headline?) confirmed **YES**: the rank template evaluates every `regime_filter` signal per-sym across the ranked universe, and the indicator cache keys on `(indicator, params, sym)` → each name builds its own series → its own full greek grid (~42k calls/bar on an SPY-sized chain). The ~100× headline is real as billed; D112's cost math stands. **Plus an unprompted correctness finding:** the dealer indicator's *chain* underlying is read from `params["underlying"]` (default `"SPY"`), decoupled from the per-name `sym` — `sym` selects only the spot bars and the cache key. So on the rank path every non-reference name computed SPY's gamma-flip against its own spot → strike-range mismatch → NaN → `_safe_default(regime_filter)` returns `allow=True`. Their probe (production gate code, 63 bars/name, 2025-09-02..11-28): SPY 100% real values; AAPL/AMD/AMZN **100% inert**; BAC 76% inert + 24% mismatched-chain garbage. Pinning `underlying=name` recovers a coherent signal (0.76–1.00 real) but is unreachable on the rank path (one signal object, many syms). Structural to the whole dealer family (`gex/vex/cex/walls/gamma_flip` share `_indicator_base`).

**Premise verification (per `crucible-handoff.md`; /tmp snapshot, fresh).** (a) Probe artifact re-read (`../Crucible/probe_results/dealer_rank_gate_inertness.json`): every quoted number matches. (b) **Producer-side structural confirmation:** all **183** v12 rank×dealer submissions (full `config_json` scan; their 22 decided are this population's decided subset) carry dealer signal params `{op, threshold}` ONLY — Forge has never emitted an `underlying` key in signal params, and top-level `underlying` is null on the rank shape by construction → **100% of the population rode the SPY default**, not just their probed names. (c) **Corollary they didn't probe: 52/183 used the dealer indicator as the rank *directional*** (131 as regime gate) — the same chain-source decoupling means those configs *ranked the universe* on NaN/mismatched-chain values. That mechanically explains the dealer-directional arm's 0/8 decided record cited in our prompt: it wasn't a weak hypothesis, it was noise-ranking. No dealer×rank variant has ever been evidence-tested in a coherent form.

**Decision: no code change; the §3 re-admission clause of the outgoing prompt is REWRITTEN.** The v12 MR×gamma rank arm's early-positive evidence (2 components, WF 1.264/1.665, comp 9.09% — D112's correction) is **void as evidence about MR×gamma**: the gate was inert for the bulk of the universe, so it was evidence about *effectively-ungated* MR rank — which v13 still emits as plain MR rank. New precondition for re-admitting dealer×rank in any form: (1) a correctly-implemented **reference-underlying macro-regime gate** exists Crucible-side (their proposed §20 change — not built; needs their explicit go) AND (2) fresh coherent-gate evidence, expected from the kept D107 single-name MR×gamma arm via `verdicts` (the gate is coherent there — underlying pinned; fires 23/63 on SPY per their probe). **Runner-capacity headroom alone no longer re-admits** (supersedes the old clause). Forge-side, re-admission remains a loosening → `OPEN_PROPOSALS.md` + operator gate (hard rule #4), now additionally paired with the Crucible template change.

**Position relayed (outgoing, operator passes): `PROMPT_CRUCIBLE_DEALER_REFERENCE_GATE_READMISSION.md`** — agree the reference-underlying gate is the only coherent vehicle; **decline to trigger their §20 scoping now** (the motivating evidence just evaporated; scoping ahead of evidence is what both phase gates exist to prevent); v13 stands. Plus a soft flag: this is the **second independent rank-path gate found failing OPEN in 24h** — `_safe_default(regime_filter) → allow=True` on no-data and Q32's `regime_coverage → coverage_unverified` pass-through are the same shape (per-name gate degradation is silent on the composable-rank path). A one-probe sweep of other regime families' per-name NaN rates is suggested, their call; a third instance would change how we read ALL rank-arm verdicts (incl. the 26-component rank cohort's quality ceiling).

**Files:** this entry, `PROMPT_CRUCIBLE_DEALER_REFERENCE_GATE_READMISSION.md` (new), `STATUS.md`. No production code, grammar, weights, or service touched. Their ask #1 (`funnel --compare v12 v13` at 2026-06-09T20:49:45Z) stays open on their side; the prompt/response pair stays at root until it closes.

---

## D116 — 2026-06-09 — Chain-reading indicators single-name only (iv_rank, put_call_flow join the D112 set); grammar v13 → v14

**Spec section:** §3.5 R1 (pool untouched — the tension is resolved at the combiner branch, not by editing the operator-owned rule), §5 enumeration policy; [[D112]] (the dealer cut this widens), [[D115]] (the inertness finding), [[Q33]] (the full evidence + options record). Origin: incoming handoff `../Crucible/docs/handoffs/FORGE_rank_gate_failopen_sweep.md` — their probe generalized the dealer decoupling to every chain-reading indicator (`params.get("underlying","SPY")` verified in their `iv_rank.py:73` / `put_call_flow.py:52`), in three modes: dealer greeks **inert** (NaN→allow), `iv_rank` **garbage_mismatch** (SPY chain IV at the name's spot — fires on noise, can spuriously pass), `put_call_flow` **hidden_uniform_reference** (SPY's value for every name); bar-only indicators coherent (their control).

**Exposure that forced the decision (fresh snapshot ⋈ verdicts, full numbers in Q33):** R1's MR pool is `{iv_rank, gamma_flip}`; D112 removed gamma from rank → every v13 MR rank config was iv_rank-gated (172/172 since the boundary) = 63% of rank emission = **17.2% of total emission** semantically void on the binding resource. All-time rank components 18/36 gate-confounded (10 noise + 8 ungated), splitting exactly on Crucible's mode boundary.

**Decision (operator-approved via AskUserQuestion 2026-06-09: "Tighten now — v14" over wait-for-Crucible and R1-widening).** New `CHAIN_READING_INDICATOR_IDS = {iv_rank, put_call_flow}` in `search_space.py`; both v13 enforcement points widened: (1) sampler rank-branch skip — `_uses_dealer_positioning` → `_uses_single_name_only_indicator` (dealer family OR chain id; still pre-rng, no entropy consumed, unaffected draw sequences unchanged); (2) `_build_regime_pool` kwarg `dealer_ids` → `single_name_only_ids` (dealer ∪ chain∩registry), rv pool excludes the set. **Consequence: mean_reversion structurally never ranks** until Crucible's reference-underlying gate exists (the Q33/D115 trigger — AGREED-DEFERRED their side); trend/em rank (bar-only/calendar gates) keep the breadth lever. Single-name pools untouched — iv_rank stays R1's MR gate, coherent where the chain pins to the traded name. Interim explicit id set; superseded by Crucible's indicator→mode map when delivered (`PROMPT_CRUCIBLE_RANK_GATE_CLASS_MAP.md` ask #1). Tightening (hard rule #4); enumeration-policy bump, the 21 rules textually unchanged (hard rule #1, the v5–v13 pattern).

**Hard rules check:** #1 rules untouched (v14 header note only); #3 no gate change; #4 tightening; #6 skip is pre-rng (invariant suite green; versioned change for affected draws); #7 untouched; #10 bump + `v14.yaml` archive + this entry.

**Alternatives considered (offered to operator, declined):** wait for Crucible's class-wide §20 fix (leaves 17.2% of emission noise-gated indefinitely); R1 pool widening with bar-only `rv_rank` (operator-owned rule edit + loosening → OPEN_PROPOSALS round-trip; slower, and untested thesis).

**Verification (TDD RED→GREEN):** 3 new tests, each confirmed RED for the policy reason first — `test_rank_draw_skipped_for_chain_reading_gate_configs` (MR forced at share 1.0: every draw stays single-name confluence; RED: iv_rank draws took rank), `test_regime_pool_relative_value_excludes_chain_reading` (RED: pool contained both ids), phase-2 invariant `test_chain_reading_indicators_are_single_name_only` (universe-wide ⇒ no chain id; keep-side: single-name iv_rank MR still emitted; RED on `forge_mean_reversion_swing_mid_7193b602`). Deliberate re-pins (documented in-test): `test_rank_combiner_emitted_when_forced` MR→trend_continuation (MR can no longer rank), `test_rank_draw_skipped_for_dealer_signal_configs` now asserts both skip mechanisms distinctly (all-MR-confluence + dealer/chain counters), the two `_build_regime_pool` direct calls (kwarg rename), `test_v1_grammar_loads` v14, D112's rv-pool equality assert moved to the new chain test. **Emission proof (live registry `a99e00d68567af59`, 3,000 samples, share 1/3): 0 universe×(dealer|chain) violations; rank = trend 148 + em 207, gates adx/hurst/rv_rank/days_since_earnings only; keep-side single-name iv_rank 564, single-name dealer 930; hypothesis mix healthy (579–622 each).** Full suite contended 1,434/0 AND uncontended (deploy gate) 1,434/0; ruff + format (changed files) clean; mypy --strict 0/82.

**Files:** `src/forge/enumeration/search_space.py`, `src/forge/enumeration/sampler.py`, `config/grammar.yaml` (v14 + header note), `config/grammar_archive/v14.yaml`, tests (4 files), `OPEN_QUESTIONS.md` (Q33 resolved), `STATUS.md`, this entry. Deploy per `deploy.md` in the same session (stop 23:08:07Z → suite → commit → restart; verification recorded in STATUS).

---

## D117 — 2026-06-09 — Crucible's capacity/stability response verified: restarts were deploys (no leak), per-run cost model recorded, decided_at fixed end-to-end → verdicts era repair built

**Spec section:** §8.2 (consumer read path), cross-system coordination per `crucible-handoff.md`; [[D110]] (the capacity-bound framing this confirms), [[D111]] (the verdicts table this repairs), [[Q32]] (the era-cut analyses the repair protects). Origin: `FORGE_runner_capacity_stability_response.md` — Crucible's answer to `PROMPT_CRUCIBLE_RUNNER_CAPACITY_STABILITY.md` (all four asks).

**Premise verification (per the handoff ritual, all Forge-side):** (1) decided_at fix LIVE — newest export (23:14Z) carries tz-aware UTC on 10,000/10,000 rows; their example row `7f5731b6` reads `2026-06-09T18:37:46.484550Z`, exactly the journal-derived truth this prompt's evidence used. (2) Verdicts damage quantified: 8,044 of 10,182 rows exactly +7.0h late (the pre-fix-ingested PDT-era values), 1,955 already correct, 183 rolled-off rows all old-box 05-28 era. (3) Their capacity model is consistent with every rate we've observed: 9.5/hr at the rank-heavy v12 tail, ~74/hr on the confluence-dominated 06-08 — both fall out of `3600/(s·635+(1−s)·16)`; no regression existed, the mix got 40× heavier per config.

**What their answer retires/corrects on our side:** the "runner instability" framing (my 2026-06-09 review + D110 flag) is RETIRED — both morning restarts were manual deploy restarts; the systemd "memory peak" lines count reclaimable page cache (anon heap ~9 GB of 123 GB, bounded); watch for `oom-kill` lines only (benign-signals list updated in `investigate-live.md`). The db-writer balloon is also mitigated their side (`MALLOC_ARENA_MAX=2`, WAL checkpointing: 472 KB vs the 653 MB we saw).

**Decision/actions:**
1. **`scripts/migrate_verdicts_decided_at.py`** (TDD, 2 integration tests): matched rows ← corrected export value (authoritative, journal-resolved); rolled-off rows +7h ONLY when equal to the pre-fix snapshot value (provably as-ingested → idempotent, cannot double-shift); everything else untouched + reported. Dry-run against the live DB copy: set-from-export=8,044, shifted=183, already-correct=1,955, **untouched=0** — full coverage. The pre-fix snapshot moved to durable `~/forge_data/` (was /tmp). **Execution OWED in the next stop-window** (the D114 restart this entry originally targeted was consumed by the D116/v14 deploy at 23:13:21Z before this script existed; the migration is a data-only repair — any brief operator-approved stop suffices, no code rides it). No consumer code change needed: `record_verdicts` already normalizes aware→naive-UTC, and the D110 watermark handles aware values (their +7h watermark note sits inside the 8d margin).
2. **Capacity model recorded for the rank-share decision (review rec 5):** decisions/hr ≈ `3600/(s·635+(1−s)·16)`; at the held s=1/3 → ~16/hr → ~10h per 200-batch to 80%. Their recommendation matches ours: keep rank (the yield arm), use share as the pipeline-clock knob, drop share (not batch size) for faster feedback cycles. No change now; revisit with the ≥300-decided re-eval (their rank-path perf work may move the 635s constant >20% — they'll update).
3. Playbook updates: decided_at era note flipped in `investigate-live.md` (aware-UTC after 2026-06-09T22:55Z; pre-fix files untrustworthy without +7h); memory-peak benign-signal added.

**Thread state:** all four asks answered; nothing further owed either side on this prompt — pair ready for `_archive/` once the migration has run.

---

## D119 — 2026-06-09 — rv-regime weight granularity FROZEN (versionless feedback change)

**Spec section:** §6.3/§8 feedback weighting; [[D103]]/[[D105]] (the engine this freezes), [[D114]] (the granularity list it amends), [[Q33]]→class-map thread. Origin: Crucible's class-map response (`../Crucible/docs/handoffs/FORGE_rank_gate_class_map.md` §3, 2026-06-09) — code-level proof that the `pairs_convergence` runner evaluates **NO regime filters**: `propose_actions` gates purely on cointegration pvalue/zscore/halflife, never calls `signal.evaluate(...)` (`pairs_convergence.py:89-168`). Operator approval: AskUserQuestion this session (option 1, "freeze rv-regime weights"; conditional "if no other agent is on it" — verified none; the concurrent session owns D118/v15, disjoint files).

**Problem.** Forge-side verification (fresh snapshot): **15,960/15,960 relative_value submissions are confluence combiners** → every one routed to `pairs_convergence` → **no rv regime gate has ever been evaluated, all-time** (including the 1,670 evi-gated configs — they were ungated pairs, not noise-gated; this also answers Crucible's open combiner-split offer). D103's founding premise ("rsi_2/rv_rank are the worst-performing rv gates") was therefore a sampling artifact — gate-id vs outcome correlations with no causal path — and the live engine was actively applying that noise (journal at 16:33 PDT: `regime_weights(relative_value): 5 gates learned`), tilting rv emission toward accidental winners.

**Decision.** `_RV_REGIME_WEIGHTS_FROZEN = True` in `rejection_weights.py`; `compute_relative_value_regime_weights` returns `{}` unconditionally. `{}` engages the documented cold-start contract end-to-end with zero other changes: the sampler's `_pick_regime` falls back to the uniform draw (identical to pre-D103) and the CLI's journal line is truthiness-gated (`cli/main.py:1551`) so it simply disappears — `cli/main.py` untouched (the D065/D105/D106 monkeypatch surface). Learning machinery kept dormant below the early return for reversibility; unfreeze = flip the flag + restore the D103 learning tests from git history at this commit, ONLY when Crucible threads regime gates into the pairs path. The rv regime POOL and emission shape are unchanged (gates still drawn/declared — the "should rv draw gates at all" question is deferred to the next Crucible round-trip; hard rule #1 untouched).

**Verification (TDD RED→GREEN):** `test_d119_regime_weights_frozen_returns_empty_despite_component_evidence` (the strongest fixture the old engine accepted — a component on one gate vs trading rejects on another — must move nothing; confirmed RED first: returned learned weights) + `test_d119_regime_weights_frozen_for_heterogeneous_inputs` (mixed rv rejects / cross-hypothesis promote / un-gated / orphan → `{}`, deterministic). Deliberate re-pins: the 3 D103 learning tests REMOVED (premise refuted; restoration path documented in the section comment), cold-start test kept. Feedback suite 256/0; **full worktree suite 1,435/0**; ruff + format clean (changed files); mypy --strict 0/82.

**Attribution:** versionless — invisible to `funnel --compare`. Read it in: the `regime_weights(relative_value)` journal line disappearing after the activating restart, and rv regime-gate draw frequencies flattening toward uniform in subsequent batches. Activates on the next service restart (built on branch `d119-rv-regime-freeze` in `../Forge-rvfreeze`; lands on main coordinated with the concurrent D118/v15 deploy).

**Files:** `src/forge/feedback/rejection_weights.py`, `tests/unit/test_feedback/test_rejection_weights.py`, this entry, `STATUS.md`.

---

## D118 — 2026-06-09 — Rank/universe exclusion re-keyed on Crucible's indicator→mode map (per-name event/DB ids join the single-name-only set); grammar v14 → v15; event_momentum structurally never ranks

**Spec section:** §3.5 (enumeration policy; the 21 `rules:` textually unchanged — the v5–v14 bump pattern), §1.2/§1.3 (producer discipline on the binding resource); [[D112]] (the dealer cut this generalizes), [[D116]] (the interim chain-reading set this re-keys), [[D115]]/[[Q33]] (the fail-open class), [[Q31]] (em data unblock, same evening). Origin: `../Crucible/docs/handoffs/FORGE_rank_gate_class_map.md` (2026-06-09 16:29 PDT) — their answer to `PROMPT_CRUCIBLE_RANK_GATE_CLASS_MAP.md` asks #1 (full map) + #2 (pairs-path parity). Operator approved "tighten now → v15" + "build + deploy now" (AskUserQuestion).

**The map (their ask-#1 answer, machine-readable `probe_results/rank_gate_class_map.json`, 45 indicators, completeness-asserted their side; verified Forge-side: registry ids ≡ map keys, 45=45 on the republished `90f05137067805db`):** 27 bar-only `coherent_per_name` (safe rank gates); 12 broken per-name = the exclusion class `decoupled_from_sym AND category != market_wide_by_design` — 6 dealer family (D112-covered) + iv_rank/put_call_flow (D116-covered) + **4 NEW: `expected_value_estimator` (runs-DB, `params["underlying"]`-keyed → the reference's EV for every name; hidden_uniform with inert fallback — NOT garbage-mode, their correction to our Q33 worst case) and `sue`/`days_since_earnings`/`days_to_earnings` (per-name events `params["symbol"]`-keyed; the rank path never threads symbol → inert fail-open; sue as a rank directional would rank the universe on NaN — the dealer-directional 0/8 pattern)**. The 5 `market_wide_by_design` ids (vix_level + 4 macro calendars) stay eligible — uniform-across-names is correct for a market gate. **Their ask-#2 answer (path parity):** three runner paths, only `cross_sectional_rank_composable` fans gates per-name; `pairs_convergence` (relative_value) evaluates **NO regime filters at all** — any rv regime gate is structurally ignored; `composable_long_options` evaluates on `config.underlying` (coherent for Forge's pinned single-name configs).

**Forge-side verification (fresh /tmp snapshot, 92,789 submissions):** (1) **rv cohort combiner split (their offered check, answered): 15,913/15,913 confluence — 100% took the pairs path → the historical rv cohort re-reads as "ungated pairs", NOT noise-gated**; the EV-gated subset is 1,667/1,667 confluence. (2) EV-as-regime-gate all-time: 1,902 uses (rv 1,667 + regime_arbitrage 151 + tail_hedge 84), all confluence; the ra/th subset rode the composable path where the gate WAS evaluated — as de facto SPY-reference EV (mislabeled-but-coherent, not noise). (3) **The v15 gap was fully latent: zero rank-combiner submissions ever carried the 4 ids as gate or directional** (4 v12 MR rank configs carried EV as the X2 kelly chain, role=confluence — flagged to Crucible to confirm the rank runner ignores confluence-role signals) **[corrected in [[D122]]: the split is 1×v12 + 3×v13, and the runner does NOT ignore confluence on rank — the leg is output-neutral there instead]**. (4) Socket probe: `sue`/`days_since_earnings` = 0 activations on SPY (ETF, no EPS) → em rank draws (underlying=None → SPY prefilter fallback) died at signal_density **by accident** — v15 makes the cut structural instead of fallback-dependent, just as Q31's fix would have started flowing em configs.

**Decision (the D112/D116 pattern, third application):** `SINGLE_NAME_ONLY_INDICATOR_IDS` = {iv_rank, put_call_flow, sue, days_since_earnings, days_to_earnings} (any role blocks the rank branch) + **`RANK_DECOUPLED_GATE_INDICATOR_IDS` = {expected_value_estimator}, role-scoped to directional/regime_filter** — the §3.5 X2 fractional_kelly sizer chain (role=confluence) is reference-keyed on EVERY path (single-name kelly configs also size off default-underlying EV with empty params), so EV-as-sizing must not block the rank branch (over-cutting guard, pinned by test). Same two enforcement points as v13/v14: sampler rank-branch skip (pre-rng, no entropy) + rv regime-pool exclusion. **Consequence: em never ranks (H2's whole signal set is per-name-event-keyed) — joins MR; trend keeps the rank arm on bar-only gates. em single-name emission untouched (sue+dse at full weight — coherent where the symbol is pinned).** Re-admission trigger = Crucible threads per-name symbols on the rank path (their map's `rank_per_name_coherent` key flips), not capacity. em's gates are sampler-side policy, not §3.5 rules — no operator-owned rule edit involved (unlike Q33's R1 tension). **Contracts gap surfaced (rule #2 discipline):** the registry should carry `rank_per_name_coherent` per indicator so future decoupled indicators auto-inherit the exclusion; until then the explicit set mirrors the map and the 45≡45 check guards drift.

**Verification (TDD RED→GREEN):** 4 tests confirmed RED for the policy reason first — `test_rank_combiner_emitted_for_event_momentum` re-pin (em forced at share 1.0 took rank; now: every draw single-name confluence + keep-side sue/dse counters non-vacuous), `test_regime_pool_relative_value_excludes_rank_decoupled` (pool contained all 4), the D116 rv-pool equality re-pin, phase-2 invariant `test_rank_decoupled_event_db_indicators_are_universe_excluded` (RED on a live rv×decoupled-gate draw `forge_relative_value_swing_short_c45ecfe7`; keep-side single-name gated configs still emitted). Plus the green-both-sides over-cutting guard `test_rank_draw_allowed_for_kelly_ev_sizer_chain` (kelly EV-chain trend configs still rank — 48/3,000 in the emission proof). Loader pin v15. **Full uncontended suite (deploy gate) 1,439/0; mypy --strict 0/82; ruff + format clean on changed files. Emission proof (live registry `90f05137067805db`, 3,000 @ share 1/3): rank = trend 123 ONLY (mr 0, em 0), rank gates rv_rank 29 / adx 49 / hurst 45 — all bar-only coherent; 0 universe×(dealer|decoupled) violations; keep-side single-name sue 589 / dse 589 / EV 755 / iv_rank 526 / dealer walls+gamma intact; mix healthy (589–619 per hypothesis).**

**Deploy (D104 ritual, same session):** stopped 2026-06-10T00:39:57Z (exit 143 clean SIGTERM) BEFORE the grammar edit (hot-reread guard) → v15 + `v15.yaml` archive byte-identical in the stop-window → full uncontended suite → commit `7a040dc` (grammar hooks via venv python on PATH; both passed) → reset-failed → restart **2026-06-10T00:44:37Z**. Verified: `grammar_version=v15`, `registry_hash=90f05137067805db` (Crucible's same-evening republish — id set unchanged, 45≡45), `manual_bump row for v15`, reconcile 14 batches / 377 newly gated, `rank_combiner_share` 0.33×3 logged (share config untouched — the skip is at draw time), NRestarts=0, zero traceback/GrammarVersionError/SchemaVersionMismatch. **Cohort note: v15 lands ~3.4h after the Q31 em-data unblock (17:18:21 PDT) and ~1.5h after v14's first batch — em emission begins INSIDE v15's window as single-name-only by construction; the v14 cohort (1 batch, 200 configs) is the only window where em rank could have submitted and didn't (the SPY-fallback accident held — verified 0 em in batch `20225de0`).**

**Files:** `src/forge/enumeration/search_space.py`, `src/forge/enumeration/sampler.py`, `config/grammar.yaml` (v15 + header note), `config/grammar_archive/v15.yaml`, tests (4 files), `PROMPT_CRUCIBLE_RANK_GATE_CLASS_MAP.md` (thread → response section), `OPEN_QUESTIONS.md` (Q33 map-residual closed), `STATUS.md`, this entry.

**Thread state / owed:** relay to Crucible (operator): v15 boundary 2026-06-10T00:44:37Z + the rv combiner split answer (100% pairs path — their "confirm which path" offer satisfied) + the 4 MR-rank×EV-confluence configs question + the `rank_per_name_coherent` registry-field ask. Deferred (unchanged from D114/Q33): the feedback-side gate-class tag for rank verdicts — now mechanically keyable on their map artifact. **Update 2026-06-09: both §4 asks answered in `FORGE_rank_confluence_and_registry_flag.md` → processed as [[D122]].**

## D120 — 2026-06-09 — demo-registry fallback is opt-in: production registry loads fail loudly

**Spec section:** §13.5 (contracts/startup discipline); registry read-side of `EXPORT_LAYOUT`. Origin: 2026-06-09 cross-system integration sweep (Crucible side), finding #3. The `registry_loader` module docstring always said production flips to fail-loud once Crucible's v3 export wiring ships — it shipped 2026-05-15 (Crucible Phase 9 v3); the flip never happened.

**Problem.** `load_registry(allow_demo_fallback=True)` was the default for every caller, production included (run-loop feedback, submission path, `forge feedback`). A missing/empty `~/optbt_data/exports/` would silently feed the enumerator the frozen Phase-2 (2026-05-13) demo registry: iv_rank v1/lookback-30 vs live v3/252, ema_50 lookback 50 vs 200 (S4 horizon misclassification), `sue`/`days_since_earnings` absent entirely (event_momentum enumeration crashes), ~26 newer indicators invisible. Latent, not live — exports exist on this box, so production never actually fell back; the risk was a silent month of stale enumeration after an export-publisher failure.

**Decision.** Default flipped to `allow_demo_fallback=False`; `load_registry` now raises `FileNotFoundError` when no snapshot exists. The two offline preview commands (`forge enumerate`, `forge prefilter`) opt in explicitly — their MANPAGE-documented fallback behavior is unchanged. `_demo_registry.py` re-documented as a deliberately FROZEN hermetic fixture: refreshing it to track the live registry would churn every test pinned to its contents for zero production benefit now that production can never see it; trust `registry_hash` for what enumeration ran against.

**Verification (TDD RED→GREEN):** `test_load_registry_default_is_fail_loud` (bare `load_registry()` on a missing dir must raise; confirmed RED first: returned the demo snapshot). Full suite 1,439/0; mypy --strict 0/82; ruff clean (changed files).

**Attribution:** versionless and behavior-invisible while exports exist. Activates at the next service restart (not bounced for this — no behavior change on the live box). Read it in: an exports outage now crashes the loop loudly instead of enumerating stale.

**Files:** `src/forge/persistence/registry_loader.py`, `src/forge/cli/main.py` (2 preview call sites), `src/forge/enumeration/_demo_registry.py` (docstring), `tests/unit/test_registry_loader.py`, this entry, `STATUS.md`.

## D121 — 2026-06-09 — contracts 1.17.0 adopted: universe-export freshness bound + registry-snapshot staleness warning

**Spec section:** §13.5 (contracts adoption); read-side of `EXPORT_LAYOUT`. Companion to [[D120]] — same 2026-06-09 integration-sweep finding family: every Crucible export Forge consumes is selected newest-by-mtime, which never expires, so a silently dead publisher meant operating on stale data with no signal anywhere.

**Changes.**
1. **contracts 1.17.0 adopted** (`FORGE_EXPECTED_CONTRACT_VERSION` 1.16.0 → 1.17.0): `load_universe_tickers_from_export` now raises `StaleExportError` (a `QueryError` subclass — existing catch sites already handle it) when the newest universe export exceeds `max_age_days=35` (one monthly publisher cycle + slack). The enumerator's call site (`sampler.py`) needs no change — fail-loud is the default. Age basis: payload `exported_at` (already stamped by Crucible's writer) with file-mtime fallback for pre-1.17.0 files.
2. **Registry staleness warning** (`registry_loader.py`): a parsed snapshot whose `snapshot_taken_at` is >14 days old logs `registry_snapshot_stale`. Warn-only by design — Crucible republishes at every deploy/boot, so 14 quiet days means the publisher is likely wedged, but an old snapshot is still VALID when registry content hasn't changed; `registry_hash` (not age) remains the integrity key. A hard bound here would brick enumeration on a healthy-but-quiet Crucible.

**Verification (TDD RED→GREEN):** Forge side — `test_load_registry_warns_when_snapshot_stale` (RED first: no warning emitted) + `test_load_registry_no_stale_warning_when_fresh`; contracts side (committed in `crucible_contracts` 64f1d0c) — 6 freshness tests incl. mtime fallback, naive-stamp normalization, `max_age_days=None` bypass, and `StaleExportError ⊂ QueryError`. Full suite 1,441/0; mypy --strict 0/82; ruff clean.

**Attribution:** versionless; activates at the next service restart. Read it in: `registry_snapshot_stale` lines if the publisher wedges; a `StaleExportError` crash if the universe publisher dies for >35 days (current export is 6 days old — safe margin).

**Files:** `src/forge/core/contracts_check.py`, `src/forge/persistence/registry_loader.py`, `tests/unit/test_registry_loader.py`, this entry, `STATUS.md`. Cross-repo: `crucible_contracts` 64f1d0c (v1.17.0), Crucible adopts the same version in its tree.

## D122 — 2026-06-09 — Crucible's rank-confluence response processed: confluence IS a rank-score input (premise corrected); the 4 rank×EV configs are 1×v12 + 3×v13 and need no flag; X2 cohorts re-read as entry-confluence + static kelly

**Spec section:** §3.5 X2 (how the kelly EV chain is actually consumed downstream); §1.2/§1.3 (cohort bookkeeping on the binding resource). Origin: `../Crucible/docs/handoffs/FORGE_rank_confluence_and_registry_flag.md` (2026-06-09 18:15 PDT) — their answer to `PROMPT_CRUCIBLE_RANK_GATE_CLASS_MAP.md` §4 asks #1/#2. The sequencing ACK + go-ahead went out the same night in `PROMPT_CRUCIBLE_FLAG_SEQUENCING_OOM_COVERAGE.md` (cd279a1); this entry lands the books corrections that prompt promised ("books correction also taken"). **Docs-only — no code, weights, grammar, or service change.**

**Ask #1, premise corrected (their own §3 routing summary was the source; their correction).** Rank-path roles partition as regime_filter vs *everything else* (`cross_sectional_rank_composable.py:145-151`): confluence-role signals feed the cross-sectional z-score composite alongside directionals (lines 212-214). On single-name composable paths, confluence is an entry vote into `combine_votes`. And the other half of the X2 model: **EV-as-sizing has no live wiring anywhere** — the sizer's EV gate exists (`sizer.py:165-176`) but zero call sites repo-wide pass `expected_value`; every `fractional_kelly` run on every path sizes at the static `kelly_fraction`. Books correction taken everywhere: **X2 cohorts = "EV entry-confluence + static `kelly_fraction` sizing", never EV-sized.** D118's over-cut-guard rationale ("EV-as-sizing must not block the rank branch") is premise-retired; the v15 behavior it pins is independently harmless (next paragraph), so `test_rank_draw_allowed_for_kelly_ev_sizer_chain` stays green-as-is until the v16 carve-out retires it.

**The 4 rank×EV configs: NO verdict flag, two independent reasons (theirs, accepted).** (a) Nothing to flag — all 4 are queued their side, never executed; when they decide, they decide in the post-cost-floor metric era (≥2026-06-09 ~23:09Z), unlike the pre-deploy pool. (b) The EV-confluence leg is provably output-neutral on rank while the reference cohort is warm: EV is `requires_symbol=False` and uniform across names → zero-variance factor → z-scores to all-zeros → identical ranking/top-K/trades vs the no-EV counterfactual. The two non-neutral failure modes are respectively impossible here (NaN-freeze needs a cold cohort; the cross-strategy SPY cohort has been warm since 2019-07-04 and the count is monotone) and dominated (EV's 61-bar guard is inside the rsi_2 percentile-252 directional's ~65-bar refusal). What the 4 DO carry is the exposure already tagged at D118: 3× `iv_rank` regime (garbage_mismatch) + 1× `gamma_flip` (inert_failopen) — noise-gated MR rank cohort, no new tag.

**Bookkeeping correction, verified on OUR books this session (fresh /tmp snapshot, 22:43 PDT):** the all-time rank×EV-confluence set is exactly 4 submissions = **1× v12-stamped (`15bbaab5`, submitted 2026-06-09 20:04:48Z) + 3× v13-stamped (`9fd2eaa8` 21:04:08Z, `21089ca1` 21:50:31Z, `6c747157` 22:31:51Z)** — straddling the 20:49:45Z v12→v13 cut and matching their queue times +15–36 s. D118's "4 v12" was a mis-grouping (entry annotated). All 4 still `status='submitted'`, `crucible_run_id` NULL our side (their run_ids: 9488bfc0/389432f5/a0abecf8/df8bbf5b).

**New reading instructions on file (drives the v16 candidate):** (1) a COLD EV confluence on rank freezes the config — uniform NaN → every name fails the all-factors-finite filter → empty scores → every rebalance bar no-ops. Masked today by the globally-warm SPY cohort; real in any thin-cohort context (fresh deployment/data_root, sparse non-SPY `underlying`). (2) On single-name paths the X2 leg is never entry-neutral: warm positive EV = a standing LONG_CALL vote (puts unreachable under `unanimous`); NaN/cold = a standing FLAT vote (`unanimous` structurally unsatisfiable, `majority` diluted). Both are now how kelly-chain cohorts get read; (1) is structurally removed when v16 keys rank eligibility on `rank_per_name_coherent` for ALL roles.

**Thread state:** ask #2 (registry flag) — design agreed; slice 1 shipped their side (`9da86f4`), registry publish deliberately held for our adoption; **waiting on contracts 1.18.0** (the 1.17.0 collision, our correction in cd279a1) → we adopt + bump pin + retire the 45≡45 invariant in the adoption commit → confirm → they republish (fingerprint rotation = contracts boundary, not drift). Ask #3 (re-admission evidence-triggered, never capacity) unchanged, on file both sides. The v16 candidate stays queued and operator-gated behind that chain. `PROMPT_CRUCIBLE_RANK_GATE_CLASS_MAP.md` is now fully answered — archive candidate once the flag chain completes.

**Files:** this entry, [[D118]] correction annotations, `STATUS.md`.

## D123 — 2026-06-09 — contracts 1.18.0 adopted: IndicatorMetadata rank-path flags — registry republish unblocked; pin-equality test closes the silent-minor-adoption hole

**Spec section:** §13.5 (contracts adoption). Origin: `crucible_contracts` 0b5f183 (2026-06-09 22:46 PDT — 36 minutes after our cd279a1 go-ahead landed; step 1 of the [[D122]] deploy order executed their side). Shipped surface verified against the agreed design: `rank_per_name_coherent` + `market_wide_by_design` on `IndicatorMetadata`, **fail-closed defaults** (False/False == rank-excluded; pre-1.18 snapshot files validate unchanged), `pyproject.toml` aligned to 1.18.0 (our version-drift nit taken), `_version.py` = 1.18.0.

**Changes Forge-side.**
1. **Pin bump** `FORGE_EXPECTED_CONTRACT_VERSION` 1.17.0 → 1.18.0 (`contracts_check.py`, with the adoption-ledger comment).
2. **New: pin-equality test** (`test_expected_contract_version_matches_installed`) — exact match, not just §13.5's major-only runtime check. Born RED on the real 1.17.0/1.18.0 gap this session: a contracts minor release could previously ship silently under a stale pin (the runtime check tolerates minors by design — unchanged). Mirrors the test Crucible added their side at 1.17.0; from now on every contracts minor bump fails our suite until explicitly adopted.
3. **New: fail-closed flags test** (`test_indicator_metadata_rank_path_flags_fail_closed`) — pins the absence-semantics the v16 policy will key on: an indicator whose snapshot entry omits the fields reads as NOT rank-eligible. This is the auto-inherit-exclusion property that motivated the registry-flag ask.
4. `uv.lock` refresh (editable dep metadata 1.16.0 → 1.18.0; the lock had silently lagged since their pyproject drifted).

**The D118 45≡45 invariant retires here** (as ACKed in cd279a1): the first new-field registry snapshot rotates `registry_hash` over the full canonical dump — read it as a contracts boundary, not indicator-set drift; same 45 ids expected. The manual registry-ids≡map-keys check was books-level practice (D118), not an executable test — nothing to delete; retired in prose.

**Verification:** pin test RED-confirmed (`'1.18.0' != '1.17.0'`) → pin bump → GREEN. **Full suite (contended) 1,443/0**; mypy --strict 0/82; ruff + format clean on changed files. Versionless and live-inert: the running daemon (03:23:18Z boot) keeps its loaded 1.17.0-era modules; the next restart loads contracts 1.18.0 against pin 1.18.0 — consistent either way (and the 22:46→now window where a restart would have paired 1.18.0 contracts with the 1.17.0 pin was safe regardless: §13.5 is major-only).

**Thread state:** our adoption confirm → `PROMPT_CRUCIBLE_CONTRACTS_1_18_ADOPTED.md` (operator: relay) → Crucible republishes the registry (publish deliberately held for this) → the **v16 candidate becomes actionable** (key rank-branch eligibility on `rank_per_name_coherent` for ALL roles incl. confluence — operator-gated grammar/policy bump, replaces v14's interim id set + v15's 4-id set; the [[D122]] cold-EV-freeze class dies with it).

**Files:** `src/forge/core/contracts_check.py`, `tests/integration/test_contracts_integration.py`, `uv.lock`, `PROMPT_CRUCIBLE_CONTRACTS_1_18_ADOPTED.md`, this entry, `STATUS.md`.

## D125 — 2026-06-10 — grammar v15 → v16: rank/universe exclusion keyed on registry flags (explicit id sets retired, confluence included) + P3 trend-scoped delta widening (operator-approved loosening)

**Spec section:** §3.5 P3 (first hypothesis-scoped band override), §3.5 X2 (kelly chain consequence), §1.2/§1.3 (producer discipline). Origin: operator directive this session — "merge this grammar with the hedge fund strategy changes running in parallel" — resolved via AskUserQuestion to **re-key + trend-only P3 widening, build + deploy now**. Two changes, one version boundary, deliberately co-attributed (both reshape emission; reads split cleanly: rank arm vs single-name trend cells, and `selector.delta_target` rides config_json).

**Change 1 — flag-keyed rank/universe exclusion (the [[D122]]/[[D123]] chain completing).** `rank_excluded_indicator_ids(registry)` = dealer family ∪ every `NOT rank_per_name_coherent AND NOT market_wide_by_design` id (the D118 key, now read per-indicator from the contracts-1.18.0 snapshot Crucible republished at `d701f07d4f23bd1f`). Retires `SINGLE_NAME_ONLY_INDICATOR_IDS` + `RANK_DECOUPLED_GATE_INDICATOR_IDS` (v13–v15's explicit mirrors). Three semantic deltas vs v15: (a) **confluence role now blocks the rank branch** — the v15 over-cut guard's premise died with D122 (EV-as-sizing has no live wiring; on rank, confluence is a score factor: output-neutral warm, cold-cohort freeze); consequence: **fractional_kelly configs never rank** (their X2 EV chain pins them single-name; kelly single-name emission untouched, X2 rule text unchanged). (b) **New indicators auto-inherit exclusion** (Crucible's fail-closed ClassVar defaults) — the dealer/iv_rank fail-open eras structurally cannot recur; re-admission = Crucible flips the flag (their agreed trigger). (c) **pairs_zscore joins the universe GATE exclusion** (it is in Crucible's 13 flag-excluded; v15's sets missed it) — it remains rv's pairs-path DIRECTIONAL, which the gate pools never governed. **Dealer family stays excluded independently of flags**: D115 re-admission needs reference-gate + single-name MRxgamma evidence; a flag flip alone is half the trigger (pinned by test).

**Change 2 — P3 trend-scoped delta widening (LOOSENING, operator-approved; OPEN_PROPOSALS `343e71fd`).** `_P3_DELTA_BAND_OVERRIDES = {trend_continuation: {swing_long: (0.20, 0.55), swing_mid: (0.30, 0.55)}}` — upper edges to the grammar-wide 0.55 cap (no Crucible position-builder change), lower edges keep the convexity rationale, all other hypotheses on base bands. **Evidence (this session's verdicts⋈submissions delta-tercile readout):** trend swing_long components 5/8/16 low→high tercile (rate 1.9%→6.0%, z≈2.4), swing_mid 9/9/12; every honest-coverage trend component in the upper two terciles of both bands; the legacy zero-slippage value bias favors LOW delta, so the read is conservative. P3's own "promotion at the edges" relax clause, fired. Literature prior agrees (Frazzini-Pedersen RAPS 2022 embedded-leverage drag — Q35). **Deliberately NOT widened:** MR (18/18/4 — inverted) and vol_event (60/54/46, honest 11/13/4 — drifts low); a global widening would have diluted both into their documented-worst zones. Q34 (R1 direction) and Q36 (missing conditioners) are NOT in v16 — Q34 is blocked on Crucible's MR net-premium answer (wrong-direction risk), Q36's indicators don't exist (contracts asks); both ride the outgoing prompt.

**Verification (TDD RED→GREEN, all RED-confirmed for the policy reason first):** `test_rank_draw_blocked_for_kelly_ev_sizer_chain` (inverts the v15 over-cut guard; non-vacuous both ways), `test_rank_exclusion_keys_on_registry_flags_not_identity` (adx flag-flip pulls its draws off rank — the auto-inherit property on a drawable id), `test_dealer_family_excluded_even_if_flagged_coherent` (green-both-sides guard), 3 P3 validator tests (trend widened, non-trend unchanged, swing_short floor intact), `test_p3_trend_sampler_explores_widened_band` (+ control), phase-2 invariant re-keyed on flags with rank-any-role vs pairs-gate-only split (the RED process caught my own over-reach: pairs_zscore as rv directional is pairs-path-coherent — the flag speaks to per-name fan-out, which only the rank template does), loader pin v16. Re-pins: forced-rank skip filter → production `rank_excluded_indicator_ids` (was a hand-rolled mirror), rv pool equality → flag-derived, `_P3_DELTA_BAND` sampler/space lookups → hypothesis-aware. Fixtures: demo registry + `minimal_registry_snapshot` carry the two flags mirroring the live republished values (21 + 19 ids — fixture-field addition, not a content refresh; frozen-fixture doctrine intact). **Enumeration/grammar/invariants 616/0; mypy --strict 0/82; ruff clean.** Determinism: the rank skip stays pre-rng; the selector override is the same single `rng.uniform` call — non-overridden draw sequences byte-identical (hard rule #6).

**Emission proof (live registry `d701f07d4f23bd1f`, 3,000 @ share 0.33×3):** rank = **trend 81 ONLY** (mr 0, em 0; vs v15's 123 — the delta is the 48-per-3k kelly-chain draws now staying single-name, plus seed noise); rank gates adx 36 / hurst 30 / rv_rank 15 — all flag-coherent; **0 rank×excluded violations, 0 EV-on-rank**; keep-side single-name intact (EV 985, sue/dse 617, iv_rank 524, pairs_zscore 584 as rv directional, dealer walls/gamma alive); trend deltas explore the widened bands (swing_long max 0.547, 33/62 above the old cap; swing_mid max 0.550), **0 non-trend deviations** from base bands; mix healthy (584–617/hypothesis).

**Files:** `src/forge/grammar/custom_predicates.py` (P3 overrides + `effective_delta_band`), `src/forge/enumeration/search_space.py` (`rank_excluded_indicator_ids`, SearchSpace fields), `src/forge/enumeration/sampler.py` (flag-keyed skip, hypothesis-aware selector), `src/forge/enumeration/_demo_registry.py` + `tests/fixtures/strategy_configs.py` (flag backfill), `config/grammar.yaml` (v16) + `config/grammar_archive/v16.yaml`, `docs/GRAMMAR.md` (P3 overrides section), tests (6 files), `OPEN_PROPOSALS.md` (343e71fd), this entry, `STATUS.md`.

**Deploy (D104 ritual):** stopped 2026-06-10T07:12:18Z (exit 143 clean) BEFORE the grammar edit (hot-reread guard) → v16 + byte-identical `v16.yaml` archive in the stop-window → **full uncontended suite 1,449/0** → commit `d84a71a` (grammar hooks via venv PATH, both passed; ruff-format hook reformatted 4 files, post-format slice re-verified 625/0) → reset-failed → restart **2026-06-10T14:43:20Z**. ⚠️ The stop window ran ~7.5 h (session idled overnight mid-window after the first commit attempt failed on hook PATH) — zero loss: submissions idempotent, Crucible kept gating, reconcile swept the backlog on restart (29 batches / 2,451 newly gated). **Verified:** `grammar_version=v16`, `manual_bump` row recorded, `registry_hash=d701f07d4f23bd1f` UNCHANGED (the policy is Forge-side; no registry move), hypothesis/bucket weights healthy, `rank_combiner_share` 0.33×3, NRestarts=0, zero traceback/extra_forbidden/SchemaVersionMismatch/GrammarVersionError. **Live boundaries: v16 = 2026-06-10T14:43:20Z; the 07:12–14:43Z gap is a no-emission window, not a behavior era.**

**Cross-session Q35 reconciliation (recorded post-deploy; the concurrent walkthrough session's readout, c983042, ran during this build's overnight idle).** Their deeper cut (single vs rank split, honesty marker, era split) agrees on the tilt (high-delta wins 6/8 usable value comparisons, incl. rank both buckets) but found a **counterexample my pooled terciles smoothed over: single-name swing_mid has 0 components above 0.40Δ in 576 rows — all 5 sit at 0.31–0.38Δ** (possible mid-band quality peak; theta/gamma at exit-DTE suspected at the high end). Why the widening still stands: (1) widening EXPLORES, it does not force — the sampler draws uniform in-band and Crucible's gate adjudicates; if swing_mid quality peaks mid-band, the >0.40Δ draws are bounded waste that the evidence then prices, exactly what the re-check measures; (2) the rank-arm and swing_long evidence is unambiguous; (3) the operator saw both readouts (walkthrough + this session's) before approving. **Adopted their re-check trigger as v16's watch item: at ≥300 decided post-cost-floor trend configs, re-run the within-band readout — if single swing_mid still peaks mid-band, propose re-narrowing the swing_mid override (v17 candidate, tightening, can ship without approval); if the tilt holds at weight, the widening is confirmed.** Their `PROMPT_CRUCIBLE_INDICATOR_GAPS.md` (Q34 premium-sign + Q36 indicator asks) is the canonical outgoing prompt — this session's duplicate was deleted and the v16 boundary folded in as its §4.

## D126 — 2026-06-10 — indicator-gaps response processed: Q34 CLOSED (R1 correct — MR is net-debit everywhere), all four indicators shipped their side, and a NEW era boundary incoming (single-name chain gates were SPY-decoupled; iv_rank v4 fix pending their deploy)

**Spec section:** §3.5 R1 (direction confirmed), §5/§13 read discipline (new era key). Origin: `../Crucible/docs/handoffs/FORGE_indicator_gaps_response.md` (2026-06-10) — their response to `PROMPT_CRUCIBLE_INDICATOR_GAPS.md`. **Docs-only: no code, grammar, weights, or service change** (the §3.5-adjacent integration is the v17 candidate below, blocked on their republish).

**Q34 CLOSED — R1 stands as written, no edit.** Net DEBIT at entry, every DTE bucket, structurally (long-only by type; `qty>=0`; spreads banned; DTE bucket never flips premium direction). Net-LONG premium wants IV cheap per the literature we cited → `iv_rank < threshold(≤50)` is the evidence-supported side. The walkthrough readout (n=2,376, "direction-suggestive, Fisher-fragile") is retired with prejudice — see next paragraph; it was thresholding noise.

**Their §2 finding — single-name chain gates were SPY-decoupled (their bug, our era key).** The composable single-name path never threaded the underlying into chain-reading indicator params: `iv_rank` read `params['underlying']` (default SPY) → every NON-SPY single-name config evaluated SPY's chain at the name's own spot — finite garbage (verified their side: AAPL 2024, 117/123 rows differ production-vs-correct, 0-vs-100 swings); `put_call_flow` same hole. This is the rank-path `garbage_mismatch` mechanism (D116/D118) discovered to ALSO be live on the single-name path — under R1's MR gate and every volatility_event iv_rank gate, all-time. **Fixed their side in `14f773a` (`iv_rank` v4 + `put_call_flow` v3, `requires_symbol=True`, resolution `symbol > legacy underlying > SPY`) — NOT yet deployed; rides their next runner restart.** Reading instructions adopted: (1) historical single-name iv_rank-gated verdicts re-read as noise-gated on the gate axis for non-SPY underlyings (SPY-underlying rows were correct — the cohort is not uniformly garbage); (2) **their deploy timestamp = a metric-era boundary for every iv_rank/put_call_flow-gated cohort** — joins the D124 era keys (cost-floor 22:52:57Z value-cut, honesty marker); re-run any R1-style readout on post-deploy decisions only; (3) the registry version bumps (v4/v3) invalidate their garbage cache rows and ride the same republish below. Dealer family shares the mechanism but is grammar-unreachable (v13 cut) — their fix deferred to the re-admission design, consistent with D115.

**Their §3 — all four indicators shipped as built** (registry republish pending; a 5th, per-name `iv_term_slope`, rides the same publish). Integration-relevant facts recorded for v17: `vix_term_slope` (macro, market-wide; vol points; median +2.1, 8.7% backwardation; regime cut `> 0` or threshold ~[−2,+3]; ingest one-shot 2018→now, nightly refresh flagged THEIR side — stale-NaN past last ingest until then), `iv_minus_rv` (iv_structure, single-name-only; annualized decimals, AAPL median +0.01 range −0.14…+0.25; net-debit gate direction `< threshold`), `market_state` (macro, market-wide; ±1, threshold `> 0` degenerate by design; ~18% down-state), `cs_dispersion` (macro, market-wide; median 0.095, ~0.05–0.25; tier-2-only full history; `min_names=5`; NOT a vol proxy — correlated crashes read LOW). **Verified in our code this session:** (a) the flag-vocabulary note is already satisfied — v16 eligibility is `rank_per_name_coherent OR market_wide_by_design` (`rank_excluded_indicator_ids` excludes only NOT-both; vix_level confirmed in rv's universe gate pool); (b) **their republish is SAFE with zero Forge changes** — ids absent from `_INDICATOR_THRESHOLD_TABLE` are `is_threshold_skippable → True` (defensive case 2, enforced by `test_no_empty_threshold_leak.py`), so the new ids stay invisible to threshold-style sampling until v17 deliberately adds entries. C1 note on file: all three market-wide ids are `family=macro` → C1 forbids pairing them in one config; per-id family override = an operator-gated ask their side, available when evidence wants the combination.

**v17 candidate (operator-gated, blocked on the republish):** the grammar-change.md new-indicator checklist for the four (+`iv_term_slope` if published): `_INDICATOR_THRESHOLD_TABLE` entries from the observed ranges above, `signal_horizon` entries, and the activation consequences made explicit for the operator: with thresholds present, `iv_minus_rv` auto-enters volatility_event's DIRECTIONAL pool (family=iv_structure, C2) and the macro trio auto-enters relative_value's universe GATE pool (R-rule-free; market-wide ids are rank/universe-eligible by flag); membership in R1/R2's pinned regime pools is a separate §3.5 rule edit (operator-owned) — recommend deciding that on post-republish evidence, not at activation. Registry expectations at republish: **≥49 ids (45 + 4 + possibly iv_term_slope), `iv_rank` v4 / `put_call_flow` v3, hash rotation = REAL id-set growth this time** (not a contracts boundary — expected, documented here).

**Files:** this entry, `OPEN_QUESTIONS.md` (Q34 resolved, Q36 shipped-awaiting-republish), `STATUS.md`.

## D127 — 2026-06-10 — Crucible's own evidence review processed: 2 more indicators on THEIR shelf (post-their-v10 sequencing), the §3 "expressible today" pre-earnings region is NOT fully expressible (1-gate structure), trend-lookback pool measured ~bimodal already

**Spec section:** §3.5 R3/C2 (what bounds the §3 region), S4 (the A2 medium-horizon-anchor condition), §1.2 (queue-capacity allocation). Origin: `../Crucible/docs/handoffs/FORGE_evidence_review_indicators_and_grammar_notes.md` (2026-06-10 — operator commissioned the same literature review Crucible-side). **Docs-only**; the operator decisions are logged as [[Q37]].

**§1–§2, two NEW indicators (their commits `804f491`/`c4cb3ff`), explicitly on THEIR shelf:** `iv_term_slope` (per-name Vasquez slope — distinct from our P1 `vix_term_slope`; gate `> threshold`; pair-with-`days_to_earnings` failure mode on file; the A2 condition stands — lifting Q28's ve×swing_mid cap needs BOTH it and `iv_minus_rv` classed medium-horizon in our S4 table) and `option_momentum` (Heston JF 2023 trailing 6m ATM-straddle return mean; gate `> threshold`; all published evidence GROSS — net-after-spreads is the hypothesis under test). Both `per_name_chain_unthreaded`/fail-closed — v16 consumes the flags correctly with zero changes. **Their sequencing rule governs adoption: nothing enters live grammar until their v10 corrected-data re-measure + portfolio battery land; classing + bounds are ours to propose at the first post-v10 grammar cut.** Registry republish expectation updated: **≥51 ids** (45 + P1–P4 + these 2); republish-safety unchanged (no threshold entries → invisible to sampling, D126).

**§3 pre-earnings IV-run-up region — their "expressible TODAY, no new vocabulary" is FALSE as stated; half-expressible.** Verified in code: the sampler emits exactly ONE directional + ONE regime gate; ve's gate slot is R3-pinned (event-proximity only) and `rv_rank` cannot be a ve directional (C2: iv_structure/flow/dealer). So the low-recent-RV conditioner — which their own text says "is what carries the documented effect" — has NO slot. The expressible half (ve × `days_to_earnings` threshold ≤10 × swing_short) was measured this session: days_to_earnings = 21% of ve regime draws (uniform over R3's 5), threshold ≤10 = 6.6% of those (the regime_range is (7,60)), **full expressible joint = 1.2% of ve emission (24/2,000 forced draws)** — "rarely lands" confirmed. Options scoped in [[Q37]]: (A) partial nudge (tighten/weight the days_to_earnings regime range toward [7,10] for ve — threshold-table policy, grammar bump, weak fidelity); (B) full fidelity via a **composed indicator their side** (`pre_earnings_setup` = days_to_earnings∈[5,10] AND rv_rank<q as ONE id — fits our 1-gate slot, no structural change; a contracts ask we can put in the next prompt); (C) two-gate config support (structural sampler/grammar change — the hard-to-reverse stop applies); (D) do nothing until their v10 re-measure. No action without operator.

**§4 trend-lookback bimodality — measured: our pool is already ~bimodal.** Forced-trend 2,000 draws, uniform across 7 directionals: short-node (literature ~20d) = donchian 20d / supertrend 10d / macd 26d ≈ 42%; long-node = momentum_252 / returns_12m_skip1 (252d) ≈ 29%; **dead-middle (their warning) = ema_cross 50d + rolling_sharpe 60d ≈ 28% of trend draws.** So the capacity burn is real but bounded — not a uniform ladder. A deliberate de-weighting of the two mid ids is a policy change (no per-directional learned weights exist; bucket weights only steer indirectly) — option logged in [[Q37]], evidence-first alternative: read the two ids' verdict record before tilting (they may already be self-evidencing).

**§5 Cao-Han constraint recorded for the future dispersion-lite class:** long-only dispersion must select names where the OPTION is cheap (low `iv_minus_rv`) with the index-vol regime as filter — never merely-volatile names (delta-hedged returns DECREASE in idio-vol; high-idio options are systematically overpriced). On file here for when the roadmap's idio-vol-concentration hypothesis gets designed; also consistent with our existing high_idio_vol underlying-class weighting being about UNDERLYING selection, not option-cheapness — the two must not be conflated in that design.

**Files:** this entry, `OPEN_QUESTIONS.md` (Q37 new; Q28 cross-ref), `STATUS.md`.

## D128 — 2026-06-10 — feedback era/honesty keys ENFORCED in the reward path (the D124-queued build): pre-cost-floor values earn nothing; dishonest-coverage "components" lose the binary event

**Spec section:** §7 (feedback inputs); enforces [[D124]]'s read standard (keys 1+2) in `_component_run_reward` — the single choke point every weight granularity inherits through `_component_rate_sums` (hypothesis / bucket / underlying-class / name / regime / H4). Origin: operator walked the decision queue this session and chose "build now." **Versionless feedback change (feedback-change.md ritual); activates at the next service restart.**

**Key 1 — cost-floor value era (`_values_readable`):** rows decided before `2026-06-09T22:52:57Z` (a literal constant, not a clock read — rule #8 untouched) earn NO quality term and NO Sharpe-proximity tiebreak half; the gate_fraction half survives (pass/fail booleans are not values). Naive timestamps read as UTC (era-uniform post-D117). Rationale: pre-cut WF/CPCV/Sharpe values are zero-slippage-optimistic; D114's quality term was consuming them.

**Key 2 — coverage honesty (`_honest_regime_coverage`):** the binary component reward (1.0) is granted only when the run's `regime_coverage` row passed AND its detail lacks `coverage_unverified` — byte-for-byte Crucible's `honest_regime_coverage` predicate (their pool filter ≡ refit trigger ≡ this read). Absent row (pre-Q32 legacy) = not honest, fail-closed. A dishonest "component" falls through to the reject path and earns what its READABLE values earn. Honest re-evaluations flow in organically via the fullhist-refit children (same config_hash — D124 key 3).

**Verification (TDD RED→GREEN):** 6 new tests in `test_quality_term.py`, 5 RED-confirmed (honest-component pin green-both-sides by design): unverified-detail / failed-row / absent-row components all lose the 1.0; pre-cut values earn only the gate_fraction tiebreak (post-cut twin earns full quality); naive-pre-cut read as UTC. Deliberate re-pins: component fixtures across `test_quality_term` / `test_orthogonal_yield` / `test_component_rate_weights` gain an honest `regime_coverage` row (the modern export shape — every live row carries one) — 5 call sites + 2 builders; zero semantic re-pins beyond that. **Full suite 1,455/0; mypy --strict 0/82; ruff + format clean on changed files.**

**Live-data effect proof (rolling 10k export ⋈ /tmp snapshot, production-faithful args incl. cold-start scoping, v16-stamped):** in-window 425 components, **185 honest (44% — the rolling window is healthier than the 94%-dishonest all-time figure, refit children replacing legacy)**; 26% of rows post-cut value-readable. Hypothesis weights OLD (journal 07:44) → NEW: **ve 1.000 → 0.526 (its component mass was the dishonest-legacy-inflated one — deflates ~2×), em 0.211 → 1.0 (all-honest-era evidence leads)**, tc 0.604 → 0.800, mr 0.379 → 0.942, rv 0.379 → 0.880 (mr/rv compress toward prior-driven values once ve's inflated max stops dominating the normalization). Caveats recorded: window-relative, and the old line was v15-stamped — directionally robust, exact numbers will differ at the activating restart. **Watch post-restart: the `hypothesis_weights:` journal line shifts per above; em's 1.0 rides tiny-n honest evidence and will move fast as its cohort decides.**

**Files:** `src/forge/feedback/rejection_weights.py`, `tests/unit/test_feedback/test_quality_term.py` (+6 tests, builder extension, 5 re-pins), `tests/unit/test_feedback/test_orthogonal_yield.py` + `test_component_rate_weights.py` (builder re-pins), this entry, `STATUS.md`.

**Deploy (D104 ritual, operator-directed same day):** stopped 2026-06-10T16:36:29Z (exit 143) → full uncontended suite **1,455/0** on committed main `f1d8359` → reset-failed → restart **2026-06-10T16:38:26Z** → verified: v16 unchanged, `registry_hash=d0b58c4b981dde4e` (the 51-id republish — already consumed in-process pre-restart, zero errors, new ids sampling-invisible as D126 predicted), reconcile 32/2,393, NRestarts=0, zero error lines, and **the `hypothesis_weights:` line shifted exactly per the live proof — em 1.000 / ve 0.524 / tc 0.813 / mr 0.794 / rv 0.750 (was em 0.211 / ve 1.000)**. D128 ACTIVE; boundary 16:38:26Z.

## D129 — 2026-06-10 — pre_earnings_setup response processed: SHIPPED with two spec corrections; THE BLOCKER — the forward earnings calendar never existed (days_to_earnings inert all-time; mandatory earnings_exit data-starved on every config)

**Spec section:** §3.5 R3/E1 (what the blocker touches), §5 (the prefilter that absorbed it), §7 read discipline. Origin: `../Crucible/docs/handoffs/FORGE_pre_earnings_setup_response.md` (their response to `PROMPT_CRUCIBLE_PRE_EARNINGS_SETUP.md`). **Docs-only.**

**Shipped as asked** (`b29822f`; class map now 52 ids; family=calendar per our C1-avoidance pick; fail-closed flags; params exposed; adoption rides the post-their-v10 lane). **Two corrections to OUR spec, accepted:** (1) `rv_rank` is [0,100] not [0,1] — rv_q default 50.0, sample in [0,100] (our spec'd 0.5 would have made the conditioner a dead id); (2) no-data = all-NaN → inert-failopen (our spec'd 0.0 would have made it a permanent never-admit); also `enter_min/max` are CALENDAR days — the literature's 5–10 trading-day window ≈ [7,14] calendar (our future threshold entries must use that range).

**The blocker (their live-box validation): `~/optbt_data/earnings.parquet` has never existed.** `days_to_earnings` returns far-value 999 on every bar, every name, all-time. Forge-side facts established this session: (1) our emitted ops are `<` (both roles) → every `days_to_earnings` gate NEVER ADMITS — structurally zero-trade, not "ungated"; (2) **exposure measured: 86 submissions all-time, ALL from one batch (2026-05-17), ZERO verdicts** — the §5 real-cache prefilter (zero activation dates) has absorbed the entire inert class before submission ever since: the pipeline contained their data bug at the cheap stage; (3) D127's "expressible half = 1.2% of ve emission" re-reads as a SAMPLING share — those draws die at the prefilter and never reach Crucible; the §3 region is fully data-inert today, both halves. (4) **The global note: E1's mandatory `earnings_exit` is data-starved too — every historical backtest, every config, HELD THROUGH EARNINGS.** Not a Forge bug, but a reading instruction: all verdict economics to date include earnings-gap risk the grammar believed was excluded; when the calendar lands and the exit starts firing, that is a **metric-era boundary for every single-name cohort** (ve/em most affected) and may materially change measured quality. Watch for their §20 entry + the `days_to_earnings` v1→v2 / `pre_earnings_setup` v2 bumps as the boundary markers.

**Their question — prioritize the calendar derivation ahead of other post-v10 work?** Recommendation YES, relayed via `PROMPT_CRUCIBLE_CALENDAR_PRIORITY_ACK.md`: it is the single prerequisite for the entire pre-earnings program AND restores the mandatory exit's designed semantics for every config; the PIT/knowability adjudication (§20, hindsight filing dates as scheduled) is theirs to own — the literature-standard assumption is acceptable to us if the §20 entry states it.

**Files:** this entry, `OPEN_QUESTIONS.md` (Q37 coda), `PROMPT_CRUCIBLE_CALENDAR_PRIORITY_ACK.md`, `STATUS.md`.

## D130 — 2026-06-10 — earnings calendar LIVE same-day (their §20 `earnings-calendar-derivation`): two-stage era boundary recorded; anchor quality quantified (~half protected, 32.5% late); v2 bumps incoming

**Spec section:** §7 read discipline (era keys), E1/R3 (what the data restores). Origin: `../Crucible/docs/handoffs/FORGE_earnings_calendar_live.md` — their same-day execution of the D129 priority call. **Docs-only.**

**The calendar exists:** 140 symbols, 4,221 dates, 2018-02-20 → 2026-06-03, derived from the D107 financials filing dates (deterministic, atomic; commit `1ca0361`). Their build also found the **second half of the starvation: the runner never passed the calendar into `Backtester`** — the mandatory exit's `earnings` parameter was unwired engine-side, independent of the missing parquet. Both halves fixed in `1ca0361`.

**Era keys adopted (recorded in `investigate-live.md`):**
1. **Indicator-side = 2026-06-10T17:05:01Z** (parquet write; `days_to_earnings`/`pre_earnings_setup` read it at compute time, no restart).
2. **Exit-side = their NEXT runner restart** (wiring + v2 cache keys ride deploy; they flag the timestamp when it lands — THE boundary for every single-name cohort: everything decided before it held through earnings).
3. **Version bumps incoming: `days_to_earnings` v1→v2, `pre_earnings_setup` v1→v2** — expect them (plus 51→52 ids if `pre_earnings_setup` joins the published snapshot) at the next registry republish; another hash rotation, expected.

**Anchor quality (their §20 probe, 3,469 events — the honest read of what the era flip buys):** median announcement-vs-filing offset −1 calendar day; ~40% within [−2,0]; **32.5% at ≤−6 (8-K well before the 10-Q) → `earnings_exit` is LATE for about a third of events** — post-boundary cohorts have ~half-restored protection, NOT full earnings-risk exclusion; never read the flip as binary. Re-anchoring to price spikes was rejected their side as lookahead (correct). For `pre_earnings_setup`, the same tail makes the gate post-announcement for those filings — our [7,14]-calendar enter-range sampling (D129 ack) is the agreed mitigation.

**Subtle window noted (no action):** with real activation dates, our §5 prefilter will START PASSING `days_to_earnings`-gated ve draws once their feature-cache writer recomputes against the parquet (next writer cycle) — if that precedes their runner restart, a few runs could compute v1-keyed real values in the gap. Real data either way; their v2 invalidation assumption holds in spirit; their restart is expected imminently. Not flagged back.

**Residuals on watch (theirs):** forward-edge staleness — the calendar ends at the last ingested filing (2026-06-03 today); names past their last known date read 999 until each financials refresh + builder re-run (nightly automation candidate; they flag if automated — matters for `pre_earnings_setup` adoption at the post-v10 cut). Anchor v2 (true announcement calendar) blocked on data tier. `earnings_exit` 2-day threshold deferred until the funnel shows the exit firing.

**Files:** this entry, `docs/tasks/investigate-live.md` (era keys), `STATUS.md`.

## D131 — 2026-06-10 — grammar v16 → v17: iv_minus_rv ACTIVATED (ve directional; ve×swing_mid reachable — partial Q28 lift) + R2 pool adds market_state (operator-approved rule edit); deployed 17:36:10Z

**Spec section:** §3.5 C2/S4 (the activation lane), §3.5 R2 (the rule edit — its own `evidence_to_relax` clause fired), §1.2. Origin: operator "push to v17" on the locked scope; R2 scope resolved via AskUserQuestion (market_state only — vix_term_slope deliberately excluded: Johnson 2017 validates it for VOL returns, not trend conditioning; its home is a future ve-gate/dispersion design). Loosening recorded: OPEN_PROPOSALS `2d0d68ca`.

**Change 1 — iv_minus_rv activation:** threshold entry `directional_range=(-0.05, 0.01)`, op `<` (Goyal-Saretto: enter when IV cheap vs the name's own realized — correct side for the net-debit book per Crucible's Q34 answer; provenance = their AAPL-2024 as-built stats, refine on funnel evidence) + signal-horizon entry 21 td (medium → S4 allows swing_short/swing_mid). Auto-enters volatility_event's DIRECTIONAL pool via C2 (iv_structure). **ve×swing_mid is reachable for the first time** (Q28's structural cap partially lifted; the full lift adds iv_term_slope at the post-Crucible-v10 cut, roadmap A2). Regime use deliberately NOT enabled — the R1-sibling gate question stays open (Q34 coda). market_state horizon entry 252 (gate-only; satisfies the thresholdable-coverage invariant, which RED-fired exactly as designed mid-build).

**Change 2 — R2 += market_state (§3.5 rule edit, operator-owned, approved):** Cooper/Gutierrez/Hameed JF 2004 — momentum pays after up-markets (+0.93%/mo), inverts after down; gate `{threshold: 0.0, op: ">"}` (degenerate by design — ±1 emission). Market-wide flag → also coherent on trend's RANK arm (the v16 flag key admitting a market gate, by design). The yaml `rules:` text is untouched (the pool is the python constant; R2's `evidence_to_relax` line is the clause that fired).

**Verification:** 3 RED-first sampler tests (ve draws iv_minus_rv with op/range + swing_mid reachability; trend draws market_state at exactly {0.0, ">"}; market_state-gated trend draws allowed on rank) + loader pin v17 + the horizon-coverage invariant RED→GREEN. **Full uncontended suite 1,458/0; mypy --strict 0/82; ruff clean. Emission proof (live 52-id registry, 3,000 @ share 0.33×3): iv_minus_rv = TOP ve directional (123/587, incl. 37 swing_mid — the lift live); market_state = 129 trend gates (~21%, even pool share) incl. 41 on rank draws; 0 rank×excluded violations (17 excluded ids incl. the 4 new shelf ids); mix healthy 586–616.**

**Deploy (D104 ritual):** stopped 2026-06-10T17:33:45Z (exit 143) → v17 + byte-identical archive in the stop window → **uncontended 1,458/0** → commit `5939fc4` → restart **17:36:10Z** → verified: `grammar_version=v17`, `manual_bump` row, reconcile 34/2,568, NRestarts=0, zero error lines. **Registry hash rotated to `a7ae9ccf843fd969` at this boot — the 17:23:39Z snapshot carries `days_to_earnings` v2 + `pre_earnings_setup` v2 (the expected calendar-fix republish), consumed cleanly.** Same-boot context: Crucible's exit-era runner restart was 17:17:13Z (D130's second boundary — now timestamped); v17's cohort is therefore also the first earnings-exit-live cohort.

**Files:** `src/forge/enumeration/indicator_thresholds.py`, `src/forge/grammar/signal_horizon.py`, `src/forge/grammar/custom_predicates.py` (R2 pool), `docs/GRAMMAR.md` (R2), `config/grammar.yaml` (v17) + archive, tests (2 files), `OPEN_PROPOSALS.md` (2d0d68ca), this entry, `STATUS.md`.

## D124 — 2026-06-09 — Crucible's v118/OOM/residuals response processed: OOM cure telemetry-backed (~60 decisions/hr), all four coverage residuals answered, d964e908's honest re-run craters the "best config ever" story — era keys + honesty marker adopted as the read standard (docs-only)

**Spec section:** §7 (feedback inputs), §20-adjacent (Crucible gates; read-side only). Origin: `../Crucible/docs/handoffs/FORGE_v118_oom_telemetry_and_residuals.md` (their response to `PROMPT_CRUCIBLE_FLAG_SEQUENCING_OOM_COVERAGE.md`). No code, weights, grammar, or service change — this entry fixes the *read standard* for every future feedback/analysis pass; the build that enforces it in the feedback engine is queued (see "Queued" below).

**Verified before recording (their numbers reproduce exactly):**
- **Contracts thread closed both sides:** their 0b5f183 = 1.18.0 with both flags (re-confirmed); our pin already 1.18.0 ([[D123]]). Registry republish still deliberately held for the operator relay of `PROMPT_CRUCIBLE_CONTRACTS_1_18_ADOPTED.md`.
- **OOM kill table corrected:** there was a **4th** runner kill we missed — pid 713927, 03:22:59Z, 101 MB anon (worker casualty; kernel-verified this session). Kill order: 484289 (22.2 GiB) → 713640 (3.1 GiB) → forge 437476 → 713927 → 714047 (27.5 GiB).
- **`b8b83495` (the d964e908 fullhist child):** present in the gated export AND already in our `verdicts` table alongside its reject parent `39961401` — same `config_hash`, new `run_id`, exactly the continuity they promised (their 94/94 claim spot-checked on `42f3a442`/`815be985` too: honest full-history coverage, 3,080d spans). decided 2026-06-10T00:42:34Z, `component`, regime_coverage honestly passed (3,072d span, start=0 sessions), **WF-median 0.280 / CPCV-p25 0.953** — byte-for-byte their numbers.

**Decisions adopted (the read standard):**
1. **Cost-floor value era: hard-cut `2026-06-09T22:52:57Z`** (their exact restart boundary; the "~23:09Z" STATUS note was the deploy-sequence tail — one decision in the churn window, ran post-floor, so this cut mislabels none). All WF/CPCV/Sharpe **values** decided before the cut are zero-slippage-optimistic; never learn from or compare values across it.
2. **Coverage honesty is a row marker, not a time-cut:** `gate_results["regime_coverage"].passed == true` AND `detail` NOT containing `'coverage_unverified'` — byte-for-byte their `honest_regime_coverage` predicate (pool filter ≡ refit trigger ≡ our reads; cannot drift). Parity boundaries for path-level reads: pairs floor live 2026-06-10T01:00:02Z (`4fd6ee2`), rank floor 01:28:03Z (`6f2fa2e`).
3. **Refit-children continuity: change nothing.** Same `config_hash`, new `run_id`; verdicts appends both; lineage at `universe_json.submission_metadata.fullhist_refit_of` if ever needed.
4. **Capacity model updated:** post-fix ~60 decisions/hr observed (109 in 1h49m; refit lane a third of it); per-class: confluence singles 2–30 s, fullhist rank-refit children 12–14 min; **current-window rank has no post-fix measurement** — the old 635 s number is dead but unreplaced; hold rank share 1/3 until they re-state it (their commitment) AND the ≥300-decided rank re-eval. New bounded-anon model: 28 workers × ~355 MB + parent ≈ 10–11 GB (the old "~9 GB" was the 4-worker box).
5. **The Q32 frontier story is rewritten by ground truth:** d964e908 — the only both-quality-gates pass ever — was promotion-grade only on its recency window; honest full-history reads it as a positive-but-weak component (WF 2.225→0.280). The v9 vol_event×dealer-flow×macro-calendar "beheaded frontier" narrative downgrades from "promote-grade frontier killed by a gate" to "recency-fit config correctly right-sized by honest evaluation." Weight implication flows in automatically via the verdicts row; no manual intervention.

**Q32 CLOSED** (entry coda written; all four asks answered — intent/windows/parity in code, ask-4 by the decided child). The three orphaned refit children stuck `status='running'` until their next runner restart are known/benign (single requeue then re-run; their canary).

**Queued (the now-fully-specified build, D114-sibling — versionless feedback change):** enforce keys 1+2 in the feedback engine — quality-term value-reads exclude pre-22:52:57Z rows; component-evidence reads prefer/flag honest-coverage rows (the binary P(component) signal currently counts 94%-dishonest legacy components). Exact timestamps and the marker predicate above make this mechanical; TDD per `docs/tasks/feedback-change.md`.

**Files:** `OPEN_QUESTIONS.md` (Q32 coda), `docs/tasks/investigate-live.md` (era keys), `PROMPT_CRUCIBLE_CONTRACTS_1_18_ADOPTED.md` (receipt addendum), this entry, `STATUS.md`.

## D132 — 2026-06-10 — Learned-ranker design PROPOSED: calibrated P(component | config features) as §6.2's prior_promotion_proximity term, shadow-first, coupled to a per-arm exploration floor (docs-only; three operator gates ahead)

**Spec section:** §6.2 (the `prior_promotion_proximity` "learning signal" slot — the one deviation: its computation generalizes from Jaccard-to-promoted to a fitted promotion-proximity; intent/name/slot/weight unchanged), §8.3 (sanctions outcome-driven ranker inputs), §10.3, §1.2/§1.3. Origin: operator brainstorm session — direction approved ("i like the idea. lets do the sketch out for it and design"); this entry records the DESIGN ONLY. Full document: `docs/proposals/learned-ranker.md`.

**Why now:** (a) §6.2's only learned term is non-discriminating — `promoted_patterns` is empty (0 promotions all-time), so 10% of the composite is dead weight; (b) the feedback weights are per-cell counters with no pooling across features, so newly activated arms start blind and get starved (baseline evidence: `iv_minus_rv` 2/600 submitted vs ~4% raw emission share, ~16 h after the v17 activation we paid for); (c) the clean era (composite boundary 2026-06-10T17:17:13Z) restarted the honest-label clock, and `submissions.config_json` + `verdicts` already hold everything — the entire honest era is retroactive training data, no new logging needed.

**Shape (three phases, each operator-gated):** F1 = `forge.ranking.features` (single extract codepath used at train and score time — skew-proof by construction; schema v1, ~35 dims, config-structural only, no market data) + dataset CLI. F2 = pure-Python Newton–IRLS L2 logistic regression (**zero new deps** — numpy/sklearn verified NOT installed; convex objective + zero-init + no RNG = deterministic, byte-identical artifact per DB snapshot, invariant-tested) + append-only JSON artifacts with coefficients by feature name (grammar_archive analog) + additive `shadow_scores` table that also persists the incumbent composite score (closing the "incumbent score never stored" telemetry gap) + checkpoint eval CLI (AUC / precision@K / Brier / calibration vs incumbent). F3 = scorer wiring behind staleness+era guards with Jaccard fallback (D076 two-mode precedent) + `batch_summaries.model_id` cohort key (D085 precedent) + **per-arm exploration floor in the diversifier (D103 floor precedent; young arm = (role, indicator_id) with <25 honest verdicts → ≤2 reserved slots/arm, ≤10% of batch). F3's wiring and the floor ship only together** — a live model without model-independent coverage trains on its own choices (closed-loop selection bias, the design's central risk).

**Honesty keys baked in:** labels reuse the D128 honesty predicate by import (never re-implemented); training rows hard-cut at `decided_at ≥ 2026-06-10T17:17:13Z` (deliberately stricter than the 22:52:57Z value-cut — labels must come from the earnings-exit-live + chain-fixed engine); any future declared era boundary auto-obsoletes models trained before it (era guard refuses → fallback); refit children kept as independent rows (D124 continuity decision). F3 promotion criterion (defaults, operator-tunable): ≥3 consecutive daily checkpoints, each ≥150 newly-decided honest verdicts across ≥5 batches, model AUC ≥ incumbent + 0.05 AND precision@K ≥ incumbent's.

**DECIDED (same session, in-session AskUserQuestion — all six recommended options approved):** (1) track shape as designed (manual trainer in F2 — auto-train offered, not chosen); (2) pure-Python Newton–IRLS, zero new deps; (3) upgrade `prior_promotion_proximity`, weight 0.10 unchanged, Jaccard = fallback; (4) F3 criterion defaults stand; (5) floor K=25 / 2 slots per young arm / ≤10% batch; (6) refit children keep all rows. **F1+F2 greenlit; F3 stays double-gated (criterion + its own go).** On F3 approval the §6.2 generalization becomes the first entry in `docs/DECISIONS.md` (the design-level log, currently empty). Hard-rule compliance table and the 7 RED-first invariant tests are specified in the proposal §5.

**Files:** `docs/proposals/learned-ranker.md` (new), this entry, `STATUS.md`.

## D133 — 2026-06-10 — F1 BUILT: learned-ranker feature extraction + honest-era dataset builder + `forge ranker-model dataset` (TDD, RED-first; service-inert until a ritual restart, zero behavior delta even then)

**Spec section:** §6.2/§8.3 via `docs/proposals/learned-ranker.md` §4 F1 (the [[D132]] track; all six §8 decisions operator-approved in-session). Versionless additive change — no grammar, no weights, no submission-path edits.

**Built (TDD: 33 tests written first, RED confirmed for the expected import reasons, then green):**
- **`forge.ranking.features`** — `FEATURE_SCHEMA_VERSION=1`, frozen `FeatureVector` (sorted name/value pairs), `extract_features(config, registry)`: the single codepath for train (config_json rehydration) and score (in-memory) time. ~35 dims, config-structural only: identity one-hots (hypothesis/bucket/underlying-class/combiner), rank-arm flag + rank_k, signal roles + directional id/family + regime multi-hot, **normalized-within-band selector features reading the grammar's own tables** (`effective_delta_band` incl. the v16 trend overrides, `_P2_ENTRY_DTE`, P4 risk band), directional threshold quantile vs the sampler table (percentile-emitting passthrough per D099; auto-tightenings deliberately ignored — stable semantic), non-mandatory exits multi-hot. Featurization never validates (a C2-violating config featurizes — pinned by test).
- **`forge.ranking.dataset`** — `build_dataset(conn, registry, era_cut=CLEAN_ERA_LABEL_CUT)`: verdicts ⋈ submissions (1:1 on the §13.4-unique config_hash), rows hard-cut at `decided_at ≥ 2026-06-10T17:17:13Z`, label = {component,promote} AND honest coverage, **keep-all refit rows** (D132 decision 6), deterministic order `(decided_at, crucible_run_id)`, wide polars frame (sorted feature columns, missing → 0.0).
- **Honesty single-sourcing refactor:** `rejection_weights.py` gains public `honest_regime_coverage_row(gate_results)`; `_honest_regime_coverage` now delegates — the reward path and the label builder read one predicate (parity pinned by invariant test). `CLEAN_ERA_LABEL_CUT` added beside `_COST_FLOOR_VALUE_CUT` with the era-key rationale.
- **CLI:** `forge ranker-model dataset --out … [--forge-db|--config] [--exports-dir] [--era-cut]` (`ranker_model_cmd.py`, one-file-per-command; `check_contracts_version()` at entry; registered additively in main.py — no restructure, D065/D105/D106 respected). `train`/`eval` are F2.
- **Invariants (`tests/invariants/test_learned_ranker_invariants.py`):** era constant byte-exact; cut inclusive at the boundary second (17:17:12 out / 17:17:13 in); honesty helper ≡ feedback predicate across all four coverage cases; dishonest component never labels positive; feature extraction round-trips config_json (train/serve skew-proof).

**Verification:** full suite **1,491/0** (was 1,458 at v17; +33 = 20 features + 6 dataset + 5 invariants + 2 CLI), `mypy --strict` 0/85, ruff clean (format scoped to changed files only). **Service-inert:** the running daemon never imports the new modules; the rejection_weights delegation is behavior-identical and loads at the next ritual restart with zero delta; `feedback` regression suite 262/0.

**Next (the F-track):** F2 (IRLS trainer + `shadow_scores` + eval CLI) builds next session-or-on-go; first real dataset pull off a `/tmp` snapshot can run any time (~339 decided post-boundary rows at the 18:53Z baseline and growing ~60/hr). F3 stays double-gated (criterion + operator go, ships only with the per-arm floor).

**Files:** `src/forge/ranking/features.py` + `dataset.py` (new), `src/forge/cli/ranker_model_cmd.py` (new), `src/forge/feedback/rejection_weights.py`, `src/forge/cli/main.py`, tests (4 new files), `docs/MANPAGE.md` (command entry), `docs/architecture.md` (ranking row), this entry, `STATUS.md`.

## D134 — 2026-06-10 — F2 BUILT: pure-Python IRLS verdict model + append-only artifacts + `shadow_scores` telemetry (post-submit daemon hook) + train/eval CLI — shadow activates at the NEXT ritual restart + first production train, both operator-controlled

**Spec section:** §6.2/§8.3 via `docs/proposals/learned-ranker.md` §4 F2 (the [[D132]] track, decisions 1–6). Versionless additive change; production ranking untouched (F3 stays double-gated). TDD: 32 tests RED-first; **full suite 1,523/0, mypy --strict 0/88, ruff clean.**

**Built:**
- **`forge.ranking.model`** — Newton-IRLS L2 logistic (zero new deps per D132 decision 2): zero-init, intercept unpenalized, standardized features, fixed tol/cap, NO RNG → **same frame = byte-identical artifact (invariant-tested)**. Rare id-level features (<10 nonzero rows) collapse into per-prefix `__other__` buckets; score-time unseen ids map onto the same bucket — the new-arm feature prior, pinned by test. Artifacts = canonical JSON w/ coefficients BY NAME, content-hashed `model_id`, append-only `models/` dir (grammar_archive analog); `load_latest_model` skips corrupt files.
- **`shadow_scores` table** (additive DDL) + **`forge.ranking.shadow.run_shadow_scoring`** — called in `_run_one_iteration` AFTER `submit_batch` (one additive hook, funnel-export never-crash precedent; internal catch-all → structlog warning + 0). Persists model_score AND the incumbent composite (closing the incumbent-never-stored telemetry gap). **Loop-level invariant:** same-seed `forge run` with artifact present vs absent → byte-identical submitted sets, shadow rows only with the artifact (battery loosened to the floor in the hermetic sandbox to push real submissions through — the synthetic cache is correctly rejected wholesale by production thresholds, the D076-era RCA).
- **`forge.ranking.evaluation` + CLI `train`/`eval`** — labels via the single `label_for` (dataset refactor; eval and training cannot disagree); per-model AUC (model vs incumbent), precision@K (K = realized positives), Brier, calibration deciles; eval prints the D132 criterion verdict (`criterion(+0.05)=PASS/FAIL`, INSUFFICIENT on single-class windows). `train` is manual (decision 1), refuses <50 rows / <5 positives, prints top-8 coefficients; `--models-dir` defaults from the CONFIG db_path (never the `--forge-db` snapshot's parent).
- **Smoke (live snapshot 23:55Z):** trains in **5.4 s** — 2,117 rows / 61 positive / 89 features, train_auc 0.927 (in-sample; the shadow eval is the honest test). Top coefficients read sane: `dir_id=put_wall_distance_pct` +0.59 (dealer-flow ve = the component-richest arm), `exit=target_exit` +0.44, `dir_id=rsi_2` +0.38. Artifact written to /tmp only — **production `~/forge_data/models/` deliberately left empty.**

**Activation semantics (nothing live yet):** shadow recording requires BOTH (a) a ritual restart onto this code (D104, operator-gated) and (b) a production train into `~/forge_data/models/`. Until then the daemon is byte-identical in behavior. First eval window opens one batch after activation; the F3 criterion clock (≥3 consecutive checkpoints) starts at the first eval with ≥150 fresh verdicts.

**Files:** `src/forge/ranking/model.py` + `shadow.py` + `evaluation.py` (new), `dataset.py` (label_for/parse_gate_results refactor), `src/forge/persistence/schemas.py` (shadow_scores DDL), `src/forge/cli/ranker_model_cmd.py` (train/eval), `src/forge/cli/main.py` (post-submit hook), tests (3 new files + 2 extended), `docs/MANPAGE.md` (train/eval + shadow_scores row), `docs/architecture.md`, this entry, `STATUS.md`.

**ACTIVATION CODA (2026-06-11, operator-approved):** D104 ritual — stopped 06:59:43Z (143) → uncontended 1,523/0 on `77addd5` → production train in the stop window (artifact `b7d260cb`, **same model_id as the /tmp smoke** — byte-identical determinism demonstrated on live data) → restart **07:02:07Z** → verified (v17/`a7ae9ccf` unchanged, reconcile 75/3,908, NRestarts=0, zero errors). **First shadow batch 07:11:12Z:** `e91e4ce2`, 200/200 scored, submitted 200/0/0. Shadow telemetry is live; production ranking untouched. Boundary note: the no-emission window 06:59:43–07:02:07Z is ~2.4 min, zero loss (idempotency). First-batch mix rode the swung weights (trend 169/200) — pre-existing rolling-window movement, logged as a watch in STATUS.

## D135 — 2026-06-11 — grammar v17 → v18: the adoption cut — iv_term_slope ACTIVATED (second medium-horizon ve anchor; A2 satisfied, Q28 cap fully lifted) + pre_earnings_setup joins R3; option_momentum HELD (probe-proven data starvation, Q39)

**Spec section:** §3.5 C2/S4 (activation lane), §3.5 R3 (pool widening — composed event-proximity gate), §1.2. Origin: operator "Let's cut to v18, proceed with all changes needed" + Crucible's GO doc (`../Crucible/docs/handoffs/FORGE_v18_adoption_go.md`: data-bar 3,753/1,500 v17 decided on corrected data; both sequencing preconditions landed; v17 new arms minting — iv_minus_rv 3 components, ve×swing_mid 2). Loosening recorded: OPEN_PROPOSALS `4c5d26ec`. Registry: the 52-id `registry_snapshot_2026-06-10T172339Z.json` (sha256 `f4f737401f298ccb…` — verified byte-exact, newest export, live since the D131 boot); all three ids' families/flags/versions verified against the GO doc table.

**Pre-build calibration probe (the new discipline — D031's audit, live):** neither shelf indicator had a published observed distribution (gap in their evidence-review doc; flagged in the relay). Ran a `FeatureCacheClient` activation-count sweep (read-only, Q31 pattern; 6–10 names × ~2,119 bars, `data_history_days=2400`):
- **iv_term_slope — clean.** Dense (non-NaN ≈ every bar, all names); median ≈ +0.005..+0.01; `> 0.01` fires ~44–49% of bars, `> 0.04` ~5–20%.
- **pre_earnings_setup — healthy.** At the GO-doc params ([7,14] calendar / rv_q 50): 114–152 firing days/name — comfortably above the §5.3.3 `min_activations=30` floor (the derived earnings calendar live since 2026-06-10T17:05:01Z).
- **option_momentum — data-starved.** 0 non-NaN bars over ~8.5y on MSFT/AMZN/GOOGL/META/NFLX/TSLA (control `rsi_2` healthy on the same names); AAPL 68 / AMD 22 / KO 146; cross-name scale incoherent (NVDA's 64 values ALL < −0.30; KO mostly > 0); percentile mode ≤ 26 activations. **No parameterization clears the activation floor on any probed name.**

**Change 1 — iv_term_slope activation:** threshold entry `directional_range=(0.01, 0.04)`, op `>` (Vasquez JFQA 2017: upward per-name term-structure slope predicts option returns; long-only book buys steep contango; range = probe-audited ~10–50% selectivity, the iv_minus_rv band) + signal-horizon entry 21 td (medium → S4 allows swing_short/swing_mid). Auto-enters volatility_event's DIRECTIONAL pool via C2 (iv_structure). **With iv_minus_rv (v17), BOTH medium-horizon ve anchors are live — the GO doc's A2 condition; Q28's ve×swing_mid structural cap is fully lifted** (three medium ve directionals now reach swing_mid via the lead-20 bracket). Regime use deliberately None (the R1-sibling question stays open, the iv_minus_rv precedent). Known failure mode noted in-table: imminent earnings fake a NEGATIVE slope → the `>` gate goes quiet pre-earnings (conservative miss, not false fire); corollary watch — iv_term_slope×pre_earnings_setup draws are thesis-contradictory and should die at expected_trades, not be special-cased.

**Change 2 — pre_earnings_setup adoption (R3-class):** python-side `_R3_EVENT_PROXIMITY_INDICATORS` += pre_earnings_setup (family calendar — the composed `days_to_earnings ∈ [enter_min, enter_max] AND rv_rank < rv_q` conditioner, D127/D129 lineage, full fidelity in the existing 1-gate slot). Both ETF-incompatible sets gain it (`_R3_ETF_INCOMPATIBLE_INDICATORS` + sampler `_EARNINGS_CALENDAR_ETF_INCOMPATIBLE`): it composes days_to_earnings → permanent-0.0 on ETFs (never admits; the T1.4 silent-zero-trade class). Threshold entry: regime `(0.5, 0.5)` op `>` (binary gate, degenerate by design — market_state precedent); the real knobs ride the same params via `_sample_pre_earnings_setup_params`: `enter_min ∈ {5..9}` / `enter_max ∈ {12..16}` **calendar** days (their Correction: literature's 5–10 *trading* days ≈ [7,14] calendar — choice sets center there, not on the shipped 5/10) + `rv_q = round(uniform(30, 60), 1)` on the rv_rank-native [0,100] scale (their Correction 1: a [0,1] draw would never fire). Horizon 5 (gate-only; coverage-invariant honesty).

**Change 3 — option_momentum HELD (the deliberate deviation from the GO doc's "adopt the three"):** no threshold entry → structurally unsamplable (test-pinned; the any-family regime_arbitrage/tail_hedge pools list it but are NON_ENUMERABLE). Activating a probe-proven-dead arm would put unreadable tiny-n noise in exactly the cohort v18 exists to make readable. Horizon shelf-classed (126 td → long — 6-month formation; Heston et al. JF 2023 persistence 6–36 mo) so activation is a one-line table add + bump. **Consequence: no C2 edit shipped** — the smart_money family question (GO doc item 4) is moot until re-activation, and `expected_value_estimator` (the other smart_money id, which has a live directional_range for the X2 chain) stays out of every directional pool. Q39 tracks; relay carries the probe numbers.

**Verification:** 6 RED-first sampler tests (iv_term_slope op/range/swing_mid reachability; pre_earnings_setup gate+params; ETF exclusion at the sampler; option_momentum unsamplable; flag-derived rank exclusion of all three) + 2 R3 predicate tests (pass on single-name; reject on ETF with detail) + horizon-class param pins + the thresholdable-coverage invariant + loader pin v18. **Full uncontended suite 1,533/0 (grammar commit) / 1,546/0 (with D136); mypy --strict 0/89; ruff clean. Emission proof (live 52-id registry, 3,000 @ rank share 0.33×3): mix healthy 573–638; iv_term_slope 77/580 ve directionals incl. 25 swing_mid (the Q28 lift live in emission); pre_earnings_setup 103/580 ve gates (~even 6-way pool share), ALL single-name, params exactly in the designed sets (enter_min {5..9} / enter_max {12..16} / rv_q [30.4, 59.8]); option_momentum 0 emissions; 0 grammar violations; 0 rank×v18-id leaks.**

**Deploy (D104 ritual):** stopped 2026-06-11T23:39:42Z (exit 143) → built v18 + archive + D136 floor in the stop window → commits `153531b` (grammar) + `ba420c4` (floor) → D134 daily-rhythm train in-window (artifact `f91e68777bc22957`, 4,180 rows / 128 positives, train_auc 0.921 — the post-flush window) + **first criterion-eligible eval: 356 fresh shadow-scored verdicts, model AUC 0.923 vs incumbent 0.925 → criterion(+0.05) FAIL — the F3 clock has started; consecutive-PASS count 0** → reset-failed → restart **2026-06-12T00:06:45Z** → verified: `grammar_version=v18` stamped, `manual_bump` row recorded, `registry_hash=a7ae9ccf843fd969` unchanged, reconcile 130 batches / 5,558 newly gated, NRestarts=0, zero error lines; weights loading v18-scoped. **First v18 batch verified end-to-end (`eb588e6f`, submitted 00:38:28Z):** enumerated 5,000 / passed 973 / ranked 200 / submitted 200/0/0 (the ~28-min battery = first-ever writer computation of the new indicator series — one-time cost); `arm_floor: mature_arms=49` live; new/young arms IN the submitted batch: iv_term_slope×2 (directional), pre_earnings_setup×3 (gate, params in the designed ranges), iv_minus_rv×2, market_state×1 — the floor delivering on batch one what v17's cold start took ~27 batches to produce; shadow scoring already riding the fresh artifact (`f91e6877`, 200/200). Relay: `PROMPT_CRUCIBLE_V18_CUT_COMPLETE.md` (live_at + the Q39 ask + heads-ups).

**Files:** `src/forge/enumeration/indicator_thresholds.py`, `src/forge/enumeration/sampler.py` (ETF set + param sampler), `src/forge/grammar/signal_horizon.py`, `src/forge/grammar/custom_predicates.py` (R3 pool + ETF set), `docs/GRAMMAR.md` (R3), `docs/INDICATOR_THRESHOLDS.md` (v18 section), `config/grammar.yaml` (v18) + archive, tests (3 files), `OPEN_PROPOSALS.md` (4c5d26ec), `OPEN_QUESTIONS.md` (Q28 resolved; Q39 opened), this entry, `STATUS.md`.

## D136 — 2026-06-11 — per-arm exploration floor SHIPPED standalone (the D132 §F3 floor half, pulled forward by the v18 GO doc item 5) — young (role, indicator_id) arms get ≤2 reserved diversifier slots, ≤10% of batch

**Spec section:** §6.3 (diversifier), D132 §F3 (floor half; §8 operator-approved parameters K=25 / 2 slots / ≤10%). Origin: Crucible's v18 GO doc item 5 — "the v17 cold start delivered new arms to Crucible at ~8x UNDER raw emission share (ranker-side starvation; arrivals were the denominator truth). With ~3 days of runway to Sunday, a forced-exploration quota is the difference between a readable v18 cohort and tiny-n on exactly the arms v18 exists to test." Versionless ranking change (D103 floor precedent); ships in the same stop window as the v18 cut, INERT until the restart.

**Coupling-rule check (the D132 design's one forbidden configuration):** F3 forbids the *wiring* shipping without the *floor* — not the floor alone. The floor is pure coverage (relaxes nothing, hard rule #4 clean); the learned-scorer wiring stays double-gated (≥3 consecutive PASS evals + operator go). Proposal doc updated in place.

**Mechanism:** **arm** = `(role, indicator_id)` for role ∈ {directional, regime_filter} (the X1/X2 confluence chain is sizing plumbing, not an arm). **Mature** = ≥25 verdicts with `decided_at` ≥ the D128 clean-era label cut (`CLEAN_ERA_LABEL_CUT`, imported — the same window the verdict model trains on, so "mature" ≡ "the learner has had a chance to see it"); counts VERDICT rows incl. refit children (D124 continuity), pooled across configs per arm. Everything else — including never-seen arms — is young. The diversifier gains a **phase-0 reservation**: young arms in sorted order, ≤2 slots each (counting candidates already selected via overlapping arms), capped at `int(n × 0.10)` total, each pick via the same §6.3 greedy rule (similarity penalties apply); then the D103 hypothesis floor and the greedy fill run unchanged. **The floor never invents candidates** — no young-arm survivor ⇒ no reservation ⇒ generation-side starvation stays visible in the funnel.

**Wiring:** `forge.ranking.arm_floor` (extraction + the verdicts⋈submissions count query) → `_load_mature_arms` in `cli/main.py` (sibling-loader pattern; `None` on :memory:/missing DB = floor off, the dry-run/test posture) → `rank_batch(mature_arms=…)` → `select_top_n(mature_arms=…)`. New journal line per iteration: `arm_floor: mature_arms=N (young arms reserved <=2 slots, cap 10% of batch)`. `mature_arms=None` keeps every legacy path byte-identical (test-pinned both at the diversifier and through `rank_batch`).

**Determinism:** sorted-arm iteration + the existing strict-`>` greedy tie-break; no RNG. Enumeration (hard rule #6) untouched — this is post-enumeration ranking, like D103.

**Verification (TDD, RED-first):** 6 arm_floor tests (role scoping incl. chain exclusion; multi-indicator signals; mature-at-exactly-K boundary; era-cut exclusion; cross-config accumulation; empty DB) + 6 diversifier tests (young-arm reservation despite 0.0 composite; the 10% cap binding; the 2-slot arm cap; `None` ≡ legacy; all-mature ≡ legacy / never-invents; composition with the hypothesis floor + determinism) + 1 rank_batch pass-through test. Full uncontended suite + deploy: rides the v18 restart (see D135's deploy paragraph).

**Files:** `src/forge/ranking/arm_floor.py` (new), `src/forge/ranking/diversifier.py`, `src/forge/ranking/queue.py`, `src/forge/cli/main.py` (`_load_mature_arms` + wiring + journal line), `docs/architecture.md` (module map), `docs/proposals/learned-ranker.md` (status note), tests (3 files), this entry, `STATUS.md`.

---

## D137 — 2026-06-13 — §7.3 stall guard SHIPPED (Q38 design built, all four §8 decisions as approved) — decision-clock staleness + work-pending predicate in `check_rate_limit`; service-inert until next ritual restart

**Spec section:** §7.3 (rate limiting), §8.2 (consumer read path). Origin: [[Q38]] / `docs/proposals/limiter-stall-guard.md` (APPROVED 2026-06-11). Implements the 2026-06-10 wedge fix: Crucible's gate stopped deciding for 18.08 h while its export stayed fresh-by-mtime; the §7.3 completion-fraction signal stayed clear the whole time (oldest in-flight batch `00dbf3b8` read 199/200 = 99.5% gated) and Forge poured ~13,000 configs into a dead gate. Second instance on record: 2026-05-30, 17.12 h / 10,000 configs.

**Decision (the four §8 options, all as approved):** (1) **signal** = decision-clock staleness + work-pending predicate (design §4): `stall_blocked ⇔ export readable ∧ ∃ submissions row status='submitted' ∧ submitted_at > max(decided_at) ∧ submitted_at ≤ utc_now() − T`. (2) **T = 3 h** (`submission.stall_after_seconds: 10800`, `0` disables). (3) **enforce directly** (no log-only stage — the §5 full-history backtest IS the shadow evidence), riding the next D104 ritual restart. (4) **placement** = extend `check_rate_limit` / `RateLimitStatus` (no third export parse, no second `main.py` seam).

**Why this predicate (the load-bearing properties):** **stateless** — recomputed from the export every check; a single fresh decision advances `max(decided_at)` past every witness and clears the block next poll. No counter, no hysteresis, nothing to reset on restart — the structural answer to the D110 "unrecoverable latch" lesson. **Deadlock-immune** — the `submitted_at > max(decided_at)` clause IS the inverse-wedge guard: a clock left stale by *Forge's own* quiet (our outage / the 06-07 migration window) has no submission postdating it, so the guard stays silent and the next batch flows. **Premise correction (Q38 as filed):** the originally-suggested `newly_gated_total` stagnation signal does not survive contact with the code — `consume_batch_results` re-derives outcomes for all batch rows every pass, so that line read ~199 (never 0) during the wedge; rejected for the semantics fix + cross-iteration state it would have required.

**Rollout posture (deliberate divergence from H-4):** the function default and the no-config fallback (`_RUN_DEFAULT_STALL_AFTER_SECONDS`) are **0 (off)**, NOT the production value — unlike H-4's `inflight_threshold` (which mirrors production at 0.80). Because the guard reads the wall clock, a stale-by-construction test/dev DB would false-trip it; defaulting off keeps the 14 existing rate-limiter tests + every `_run_one_iteration`/`cmd_run` test byte-identical, and makes "guard-off equivalence" the literal invariant. **Production opts in via `config/forge.yaml` (`stall_after_seconds: 10800`)** — the endorsed "production passes the value, core defaults to old behavior" pattern (main.py:1471 precedent). The Pydantic model field also defaults 0 (absent ⇒ disabled).

**Calibration (design §5, verdicts table full history):** healthy inter-decision gaps p50 7 s / p99 4.7 min / max 65 min. At T = 3 h (2.77× the worst healthy gap) the detector fires on both true stalls (05-30, 06-11) and stays silent on the healthy-slow 06-04 gap (2.02 h) and the Forge-quiet 06-07 migration gap (3.38 h, 0 submissions) — **2/2 true, 0/2 false**. Would have caught the 06-10 wedge at +3 h, avoiding ~10,800 of 13,000 dead submissions.

**tz note (test-only):** the synthetic crucible DB is not UTC-session-pinned like Forge's `db_connection`, so the DB-fallback fixtures store `decided_at` as naive-UTC for an identity round-trip through `get_recent_gated_runs`. Production reads the export's tz-aware UTC JSON (D117) — unaffected; the predicate normalizes naive→UTC per the D061 convention either way.

**Verification (TDD, RED-first):** 8 predicate truth-table + 4 §5 replay episodes (`tests/unit/test_submission/test_rate_limiter_stall_guard.py`); 3 invariants — deadlock-immunity (Hypothesis: `stall_blocked` iff a real witness exists), stateless-recovery (one fresh decision clears any blocked state), guard-off-equivalence (`stall_after_seconds=0` ⇒ pure completion-fraction) (`tests/invariants/test_stall_guard_invariants.py`); wiring (H-4 pattern) in `test_config_threading.py` + model default/validation in `test_forge_config.py`. **Full suite 1,563/0; mypy 0/89; ruff clean.** Service-inert (the running daemon won't reload code/config until a restart); activates at the next D104 ritual restart — no urgency, the runner just recovered; the next stall is what this buys down.

**Files:** `src/forge/submission/rate_limiter.py` (predicate + `_evaluate_stall_guard` + 3 new `RateLimitStatus` fields), `src/forge/config/forge_config.py` (`SubmissionConfig.stall_after_seconds` + `with_overrides`), `config/forge.yaml` (knob = 10800), `src/forge/cli/main.py` (`_RUN_DEFAULT_STALL_AFTER_SECONDS`, resolver + `_run_one_iteration` param + distinct journal line + both `cmd_run` call sites), `docs/MANPAGE.md`, `docs/HOW-TO.md`, `docs/tasks/investigate-live.md`, `docs/proposals/limiter-stall-guard.md` (status → BUILT), tests (4 files), this entry, `STATUS.md`.

---

## D138 — 2026-06-13 — grammar v18 → v19: option_momentum ACTIVATED (reverses the v18 hold; Q39 resolved) — smart_money pinned to trend_continuation's C2 directional families; PERCENTILE-ONLY (min_months=3); EV pinned out — BUILT in worktree, awaiting deploy

**Spec section:** §3.5 C2 (directional family ↔ hypothesis), §5.3.3 (signal_density), §3.5 S4 (horizon→bucket). Origin: [[Q39]] (v18 hold) + Crucible's coverage handoff `../Crucible/docs/handoffs/FORGE_option_momentum_coverage_response.md` (2026-06-12). Operator: effort-max session 2026-06-13 — "draft v19 activation now"; hypothesis pin chosen via AskUserQuestion.

**Q39 resolved (the premise correction):** the v18 probe read option_momentum as "data-starved — coverage" and held it. Crucible's reply: **NOT coverage.** Chains are fully present (~2,054–2,122 partitions/name, 2018→2026-06-11); the zeros are the shipped default **`min_months = months = 6`** (six *consecutive* clean reconstructed-straddle months) colliding with a ~40% honest per-month exit-match miss. KO=146/AMD=22 reproduce to the count. The Forge re-probe (`scripts/probe_option_momentum_min_months.py`, `probe_results/option_momentum_min_months_sweep.json`) confirmed: (a) **the writer reads `min_months` from per-config SignalSpec params** — `default == min_months=6 (~0 on liquid names) → mm=4 hundreds → mm=3 ~1000s` — so the unblock is fully Forge-side, NO Crucible republish; (b) at **min_months=3** the percentile range (0.80, 0.90) clears the §5.3.3 min_activations=30 floor on **all 10 probed names** (worst NVDA p>0.90 = 57); (c) rsi_2 control healthy 10/10. (See [[Q39]] for the resolution record.)

**Decision (3 Python-side changes + version bump; the 21 `rules:` text untouched, per every cut since v5):**
1. **C2 pin** (`custom_predicates._C2_HYPOTHESIS_FAMILIES`): `trend_continuation: ("trend",)` → `("trend", "smart_money")`. option_momentum (Heston-Jones-Khorram-Li JF 2023 — past option returns predict future option returns) is a momentum/persistence factor = a continuation thesis; horizon 126 td (long) → swing_mid/swing_long DTE. The D062 precedent (dealer_positioning → MR/ve) for extending the family map via a D-entry.
2. **EV pin-out** (`indicator_thresholds`): `expected_value_estimator.directional_range` → `None`. The C2 edit would otherwise admit EV (the other smart_money member) as a directional; EV is the X2 fractional-kelly sizer feature (runs-DB, reference-keyed) — never an honest per-name directional. Behavior-preserving on v18 (smart_money was in no C2 hypothesis). Its regime/gate use is untouched.
3. **option_momentum entry — PERCENTILE-ONLY** (`indicator_thresholds`): `directional_percentile_range=(0.80, 0.90)`, `op_directional=">"`, `directional_range=None`. Crucible §3: the as-built straddle return (front-expiry, ~34→4 DTE — near-total theta harvest) has a level that scales with the name's IV, so a fixed **absolute** `option_momentum > threshold` gate is a cross-sectional **inverse-IV sort** (a confound their gate would reject), not the momentum signal. Percentile over the name's own history normalizes that offset. To support a percentile-ONLY indicator, `is_threshold_skippable` / `sample_threshold_params` now treat "percentile range set, absolute range None" as samplable (percentile checked before the absolute-None guard; one rng.uniform either way, so dual-range indicators are byte-identical — #6). `_sample_option_momentum_params` adds `{min_months: 3, months: 6}` per config (the rv_rank/pre_earnings precedent).

**Why trend_continuation (the operator-pinned home), not the alternatives:** AskUserQuestion, recommended + chosen. volatility_event would group it with the other option/IV directionals but **leans into the very theta/IV-level confound** percentile mode normalizes away (its regimes/exits are vol-tuned) and snaps DTE to swing_mid; event_momentum is specifically PEAD (a non-earnings factor muddies it). regime_arbitrage (any-family, no C2 edit) is **disabled/non-enumerable** (`DISABLED_HYPOTHESES`) so it was never an option — which is also why EV was genuinely out of every *enumerated* pool pre-v19.

**Verification (TDD, RED-first; built in `../Forge-build` worktree — grammar.yaml hot-reread makes in-tree unsafe while the service runs):** new invariants `tests/invariants/test_option_momentum_activation.py` (always-percentile + min_months=3; pinned to trend_continuation only; EV never a directional; S4 bucket ∈ {swing_mid, swing_long}); unit additions in `test_percentile_thresholds.py` (percentile-only path + EV pin); deliberate re-pins — `test_search_space::test_directional_pool_trend_continuation` (EV joins the C2 build-pool, pinned out at sample time), `test_sampler::test_v18_option_momentum_not_emitted` → `test_v19_option_momentum_activated_under_trend_only`, `test_v1_grammar` version string. **Emission proof (v19, live registry, 4000 cold draws):** option_momentum **76/4000 = 1.90%**, all trend_continuation, all percentile + min_months=3 + op ">", EV directionals **0**; buckets swing_mid 39 / swing_long 37 (both S4-long; swing_mid when a chain signal narrows chain-compat DTE). C1 correctly blocks option_momentum + EV co-occurrence (same family). **Full suite 1,570/0; mypy 0/89; ruff clean; both grammar pre-commit hooks pass; range 0.80/0.85/0.90 live-audited at mm=3.**

**Caveat carried forward (the principled path):** even percentile-normalized, the underlying is the as-built theta-bleed straddle return — Crucible's words: *closer to* the thesis, not the Heston signal. The principled fix is their **constant-maturity** construction (Crucible §20, offered "on our word"). If/when the funnel says option_momentum is worth deepening, request that build and re-activate the absolute-threshold arm against it. The `smart_money` family stays as-is (Crucible: no objection; won't move it silently).

**Action:** worktree branch `v19-option-momentum` holds the full change + records (this entry, [[Q39]] resolution, OPEN_PROPOSALS `0c7e9d2f…`, GRAMMAR.md C2, STATUS). **Deploy is the separate operator-gated ritual** (`docs/tasks/deploy.md`: stop → uncontended suite → commit → restart → verify journal → relay v19 to Crucible). The probe script + JSON live untracked in the live tree (close the reproducibility gap Crucible flagged — commit alongside or before the deploy).

**Files (worktree):** `src/forge/grammar/custom_predicates.py` (C2 map), `src/forge/enumeration/indicator_thresholds.py` (option_momentum entry, EV pin, percentile-only support), `src/forge/enumeration/sampler.py` (`_sample_option_momentum_params` + hook), `config/grammar.yaml` (v19 + archive `config/grammar_archive/v19.yaml`), `docs/GRAMMAR.md` (C2 table), tests (1 new invariants file + 4 re-pinned), `OPEN_PROPOSALS.md`, `OPEN_QUESTIONS.md` (Q39), this entry, `STATUS.md`. Live tree: `scripts/probe_option_momentum_min_months.py`, `probe_results/option_momentum_min_months_sweep.json`.

## D139 — 2026-06-13 — `forge-ranker-eval` daily timer: automates the F-track checkpoint train+eval (telemetry-only; FRESH-window streak; atomic model publish) — OPS increment, no daemon / grammar / service touch

**Spec section:** §6.2 (the ranker the model shadows), [[D132]]/[[D134]] F-track. Origin: operator (this session) — *"set up the daily train+eval and make sure the script cleans up after itself"*, after asking how the learned model is progressing and confirming the F3 clock only advances when train/eval is run by hand at each checkpoint.

**What:** a systemd **user** timer `forge-ranker-eval.timer` (`OnCalendar=*-*-* 05:00:00`, `Persistent=true`) runs `scripts/daily_ranker_eval.sh`, automating the manual checkpoint rhythm ([[D134]]: `cp` snapshot → `ranker-model train` → `eval`). Units live in `deploy/systemd/`, symlinked into `~/.config/systemd/user/` (the `forge.service` pattern). Each run: snapshot the live DB to `/tmp` (intermittent RW lock — house convention) → `forge ranker-model train` into a **staging dir** → **atomic `mv`** the artifact into `~/forge_data/models/` → `forge ranker-model eval` → append one JSON row to `~/forge_data/ranker_eval/streak.jsonl` + journal the `N/3` streak. Deterministic, **no LLM** (hard rule #5).

**Two design calls:**
1. **Atomic publish, not the CLI's direct write.** `save_model` uses a plain `write_text`; the daemon calls `load_latest_model` every batch. Rather than inherit that torn-read window for a *scheduled* writer running next to the 24/7 daemon, the script trains into a same-filesystem staging dir and `mv`s the artifact in (atomic rename). (`load_latest_model` already skips corrupt files and falls back, so this only removes a benign warning — but the writer is now fully correct.)
2. **Streak judged on a FRESH per-checkpoint window** (verdicts decided since the prior run's `ts`), NOT the cumulative-since-clean-era window that manual `forge ranker-model eval` defaults to. The F3 criterion is "≥150 **fresh** verdicts on ≥3 consecutive checkpoints"; a cumulative window lets the same frozen verdicts climb the streak to 3/3 without new evidence. The journal prints BOTH views for continuity with the CLI; the JSONL records `window_since` + `fresh_decided` + the dominant model's verdict. "Dominant" = the model with the most decided verdicts in the fresh window (the one live then); a just-trained model has 0 decided and is correctly ignored.

**Scope / safety:** telemetry-only — never touches grammar/weights/config/ranking. The trained artifact only rolls the *shadow* model forward; F3 live wiring stays its own triple gate (3-PASS criterion AND operator go AND the still-unbuilt wiring increment + a ritual restart; only the per-arm floor half shipped, [[D136]]). A `trap … EXIT` removes the snapshot + staging on every path (verified: nothing left in `/tmp` or `~/forge_data` after two runs).

**Verification:** ran the service twice end-to-end (`Result=success`, `ExecMainStatus=0`); trained `df8933ba` (12,916 rows / 264 pos, train_auc 0.915), atomic-published, eval recorded the first streak entry — dominant `f91e6877` margin **+0.504 PASS → 1/3**. `bash -n` + `systemd-analyze --user verify` clean; timer `enabled`+`active`, next fire 05:00. No Python added to `src/` → suite/mypy unaffected (the inline eval imports `_AUC_MARGIN_CRITERION` from the CLI to single-source the criterion).

**Files:** `scripts/daily_ranker_eval.sh`, `deploy/systemd/forge-ranker-eval.{service,timer}` (new); `docs/MANPAGE.md` (ranker-model automation note + SCRIPTS entry + PIPELINE SERVICES timers), `docs/HOW-TO.md` (daily health check), `docs/architecture.md` (Forge timers), this entry, `STATUS.md`. (Memory: `ranker-eval-daily-timer.md`, outside the repo.)

---

## D140 — 2026-06-13 — tail-aware ranker T1 (offline): `cpcv_p25` regression head + dataset targets + `train-robustness` CLI — §8 walked (all recommended); analysis-side, shadow + T2 daemon-gated

**Spec section:** §6.2 (the ranker), §8.3 (metric distributions weight the ranker — the sanction), §1.2 (Forge computes no strategy metrics), [[D132]]–[[D134]] F-track. Design: `docs/proposals/tail-aware-ranker.md` (§8 DECIDED this session). Origin: the 06-13 Phase-2 pool read — the verified assembly pool fails the portfolio `cpcv_p25` bar (0/264 individually clear 1.5), so ranking by P(component) optimizes an abundant, ~goal-inverse quantity; retarget toward worst-quartile robustness.

**§8 decisions (in-session AskUserQuestion, all recommended):** (1) REGRESS `cpcv_p25.value`; (2) train on ALL-honest-era rows + a coverage-verified flag; (3) BLEND P(component) eligibility × tail-score preference at wiring; (4) T2 = asymmetric regime-complement floor on the regime-bet axis; (5) T3a (worst-quartile regime label) now, T3b deferred; (6) T1 wiring criterion mirrors F3 (3× / ≥150, margin set after shadow).

**Built (3 commits, TDD, offline/analysis-side only):** `163dfd2` — dataset gains continuous targets `target_{cpcv_p25,wf_median,regime_stress}` (read from `gate_results[...].value`, consume-not-compute per §1.2) + `coverage_verified` (= the D128 honesty predicate; fixed 1.0 at score time, §8.2); the P(component) logistic model EXCLUDES all four (targets are labels; coverage_verified is label-collinear) — byte-identical, pinned by a test. `481bfce` — `RobustnessModel` + `train_robustness_model`/`score_robustness`/save+load: deterministic pure-Python ridge (normal equations via the existing Gaussian solver, zero RNG, byte-identical artifact); standardization + rare-id-collapse extracted into a shared `_standardize_design`. `227e3f2` — `forge ranker-model train-robustness [--target] [--lambda]` (+ shared `_resolve_models_dir`).

**Verification:** full suite green (no daemon/loop touched; the existing logistic model + learned-ranker invariants unchanged). Live-snapshot smoke: 2,627 rows / 70 features, `train_r2`=0.169 (honest — config structure explains ~17% of `cpcv_p25` variance, not overfit); top coefs RECOVER the pool read — `mean_reversion` +0.036 vs `volatility_event` −0.039 on `cpcv_p25` (mr the most tail-robust family, the inverse of the P(component) ranking). mypy/ruff clean on all changed files; pre-commit hooks passed each commit.

**Deferred (daemon-gated, the next deliberate pass — NOT done here):** (a) persist the tail score in `_run_one_iteration` → a `shadow_scores.tail_score` column (live-DB schema migration); (b) tail eval wiring (Spearman rank-corr + top-K mean `cpcv_p25` on the new column); (c) T2 regime-complement supply-metric in the ranker. All touch the running service / live schema → the F2-style "build inert → operator ritual restart" treatment. T1 wiring + T2 enforcement stay gated (§8.6 criterion + the pending F3 go + complement supply). No grammar/gate/loosening touched (#1/#3/#4 clean).

**Files:** `src/forge/ranking/dataset.py`, `src/forge/ranking/model.py`, `src/forge/cli/ranker_model_cmd.py` + their tests; `docs/MANPAGE.md` (the new command), `docs/proposals/tail-aware-ranker.md` (§8 DECIDED), this entry, `STATUS.md`. Relay `PROMPT_CRUCIBLE_WORST_QUARTILE_REGIME_LABEL.md` (T3a) drafted + operator-relayed. (Memory: `promotion-gate-tiers-and-constraint.md`, outside the repo.)

---

## D141 — 2026-06-13 — tail-aware T1 shadow persistence (INERT): record the `cpcv_p25` prediction per batch in `shadow_scores` — daemon-touching, activates writes at the next ritual restart

**Spec section:** §6.2 / §8.3, [[D132]]/[[D134]] (F2 shadow telemetry — same hook), [[D140]] (the offline T1 model this scores). Design: `docs/proposals/tail-aware-ranker.md`. Origin: operator (this session) — *"build the shadow-persistence increment inert"*, the first of D140's deferred daemon-gated pieces.

**What:** `shadow_scores` gains two nullable columns — `tail_score DOUBLE` (the robustness model's predicted worst-quartile value) + `tail_model_id VARCHAR(64)` (which artifact produced it) — via idempotent `ADD COLUMN IF NOT EXISTS` ALTERs (the D062 prod-migration pattern; the live DB picks them up when `ensure_schema` runs at the next service open). `run_shadow_scoring` now also calls the new `load_latest_robustness_model` and records `score_robustness` for each submitted candidate next to the existing P(component) score; **NULL** when no robustness artifact exists yet (the whole pre-train history) or for pre-existing rows.

**Inert by construction (the F2/[[D137]] pattern):** the recorder still runs AFTER selection + submission and the loop NEVER reads `tail_score` (tail wiring is the separate, gated increment) → the submitted set is byte-identical (the shadow no-op invariant, unchanged). The **running daemon won't execute any of this until a restart** (Python loads at process start); an unplanned reboot (D104) is also safe — the migration is idempotent and the change is behavior-inert. So this is "committed now, writes activate on the operator's next ritual restart; behavior never changes until wiring."

**Verification:** targeted suites green — shadow/model/invariants (37), persistence schema incl. the updated column-set test (8), persistence + CLI-loop integration (66); **full uncontended suite green**; mypy --strict + ruff clean. **Migration smoke on a real 30,000-row `shadow_scores` copy:** both columns added, all 30k existing rows NULL, idempotent re-open. Two new shadow tests (tail populated when a robustness model is present; NULL when only the logistic model is).

**Files:** `src/forge/persistence/schemas.py` (2 ALTERs), `src/forge/ranking/model.py` (`load_latest_robustness_model`), `src/forge/ranking/shadow.py` (tail score in the insert) + `tests/unit/test_ranking/test_shadow.py`; `docs/MANPAGE.md` (the `shadow_scores` table row), this entry, `STATUS.md`. **Remaining T1/T2 (still daemon/eval-gated):** tail eval wiring (Spearman rank-corr + top-K mean `cpcv_p25` reading these columns) and the T2 regime-complement supply-metric; live tail WIRING stays behind the §8.6 criterion + the F3 go.

---

## D142 — 2026-06-13 — daily timer also trains the tail-aware robustness model — so D141's shadow hook has a daily-refreshed `cpcv_p25` artifact to score with

**Spec section:** [[D139]] (the timer this extends), [[D140]] (the tail model), [[D141]] (the shadow hook that scores with the artifact). Origin: operator (this session) — *"add the timer line so the tail model trains daily"*, the companion to D141 (without a robustness artifact in `~/forge_data/models/`, the inert shadow hook would record NULL forever even post-restart).

**What:** `scripts/daily_ranker_eval.sh` gains a `forge ranker-model train-robustness` step after the logistic train, with the SAME staging-dir → atomic-`mv` publish discipline (the 24/7 daemon never reads a half-written `robustness_model_*.json`). Independent of the logistic train — it can refuse (no cpcv rows / registry-load) without affecting it or the eval/streak. Telemetry-only; the production loop never reads the artifact (D141 is inert until a ritual restart).

**Verification:** `bash -n` clean; **ran end-to-end on the live box** — published `robustness_model_v1_20260613T183137Z_5174039c` (3,089 rows, 71 features, `train_r2`=0.182; top coefs `coverage_verified` +0.076 / `mean_reversion` +0.044 / `volatility_event` −0.042 — recovers the tail-robustness ordering). The logistic train + eval + streak were unaffected (note: the separate F3 *logistic* streak independently reached 3/3 on the fresh window this run — that's the D132 criterion clock, not the tail track; F3 live wiring stays its own gate). No `src/` change → suite/mypy unaffected.

**Side effects of the validation run (benign, = one extra timer cycle):** a fresh `verdict_model_*` + `robustness_model_*` published to the live `~/forge_data/models/` and one `streak.jsonl` row — exactly what the 05:00 timer does. The running (pre-D141) daemon ignores `robustness_model_*.json` (it globs `verdict_model_*`), so zero daemon impact; the robustness artifact simply pre-stages D141's activation.

**Files:** `scripts/daily_ranker_eval.sh` (the train-robustness step + header), this entry. (STATUS.md had concurrent uncommitted edits this session and was left untouched; Memory: `ranker-eval-daily-timer.md`, updated, outside the repo.)

---

## D143 — 2026-06-13 — tail-aware T1 eval wiring: `evaluate_tail_shadow` + `eval-robustness` CLI + daily readout — turns the accruing `tail_score` into a Spearman / top-K `cpcv_p25` measurement

**Spec section:** §6.2 / §8.3, `docs/proposals/tail-aware-ranker.md` §4 (T1 eval metrics) + §8.6 (the criterion). [[D140]] (the model), [[D141]] (the `tail_score` this reads), [[D142]] (daily tail train). Origin: operator (this session) — *"build the tail eval wiring increment"*, the readout that makes D141's accruing data legible.

**What:** `forge.ranking.evaluation` gains `evaluate_tail_shadow` (+ pure helpers `spearman_corr`, `_average_ranks`, `_top_k_mean`): per `tail_model_id`, over **verified-coverage** decided verdicts carrying a `cpcv_sharpe_p25` value, it computes **Spearman(tail_score, realized cpcv_p25)** and **top-K mean realized cpcv** for the tail model's top picks vs the incumbent composite's (K = top decile). New CLI `forge ranker-model eval-robustness [--since]` prints these per model; `daily_ranker_eval.sh` runs it each checkpoint (observation only). The verified-coverage filter makes it apples-to-apples with what the model predicts (the §8.2 score-time convention).

**No PASS/FAIL yet (deliberate, §8.6):** the criterion margin (on rank-corr / top-K) is set *after* the shadow distribution is visible — the readout prints metrics + "criterion: §8.6 margin not yet set". So this accrues the evidence to set the bar; it does not gate anything (live tail wiring stays behind the §8.6 criterion + the F3 go).

**Verification:** RED-first; 4 new eval tests (Spearman truth-table; top-K + overall; unverified/missing-cpcv exclusion; empty-on-no-tail-scores) + 2 CLI tests. Full ranking+CLI suite green (243); mypy --strict + ruff clean. **Smoke on the live snapshot:** graceful "no tail-scored verdicts decided … not yet accruing" — correct (every live `shadow_scores` row is NULL-`tail_score` until D141 is live post-restart).

**Files:** `src/forge/ranking/evaluation.py` (+`evaluate_tail_shadow`/`spearman_corr`), `src/forge/cli/ranker_model_cmd.py` (`eval-robustness`), `scripts/daily_ranker_eval.sh` (daily readout) + `tests/unit/test_ranking/test_evaluation.py` + `tests/unit/test_cli/test_ranker_model_cmd.py`; `docs/MANPAGE.md` (the command + timer note), this entry. **Tail-aware T1 is now end-to-end** (dataset → train → shadow-persist → eval); REMAINING: the §8.6 margin (set after observation), live tail WIRING (gated), and T2 (the regime-complement floor — now with T3a's measured bear/ranging target). (Memory: `ranker-eval-daily-timer.md` updated.)

---

## D144 — 2026-06-13 — T2 regime-complement supply metric (SHADOW): per-batch `regime_supply:` journal line — how much ranging/bear complement a future T2 floor could reserve, vs the passed pool

**Spec section:** §6.2 / §8.3, `docs/proposals/tail-aware-ranker.md` §4 T2 + §7 (the complement-supply coupling risk) + §8 dec-4 (T2 ships as a shadow supply-metric first). [[D136]] (the per-arm floor this sits beside), [[D140]]/[[D141]]/[[D143]] (the T1 track), [[promotion-gate-tiers-and-constraint]]. Implements the T3a measurement (worst quartile = BEAR 2.39× / RANGING 1.33×, regime_lift). Origin: operator (this session, AskUserQuestion) — *"build the T2 supply-metric (shadow)."*

**What:** new `forge.ranking.regime_supply` classifies each ranked survivor's **regime-bet** and rolls it up to whether it pays in the T3a-measured failure regimes: `trending_dominant` (trend_continuation — the 76% sleeve), `ranging_complement` (mean_reversion — the R1/D107 long-gamma/ranging payer), `bear_complement` (tail_hedge — the C2 `macro` crash payer), `other` (everything the grammar doesn't bind to a bear/ranging payoff — honestly un-classified, not force-fit). `_run_one_iteration` logs a `regime_supply:` line over BOTH the submitted batch and the pre-filter-passed pool it was drawn from (the reservable ceiling), leading with the ranging+bear complement share and calling out bear specifically. The finer (hypothesis × regime_gate × op) cell is carried on each `RegimeBet` and echoed in the per-cell breakdown, so the roll-up is re-bucketable from the journal without a re-run.

**The classifier is the structural judgment (flagged for review):** the roll-up keys on HYPOTHESIS, which C2 (hypothesis → directional family) + R1/R2/R3 + D107 (dealer-gamma regime switch) bind to a regime-bet. `mean_reversion`→ranging is well-grounded; `bear_complement`←`tail_hedge` is the defensible-but-soft half — the grammar has no general bearish/short directional stance (only the `long_short` rank mode), so bear-paying supply is structurally scarce, which this metric exists to surface. Because it is SHADOW-only telemetry (reversible, no behavior / no loosening impact — hard rule #4 untouched), an imperfect bear mapping is safe and re-bucketable: revise `_BET_CLASS_BY_HYPOTHESIS` after the live distribution is visible. **Not a new market-regime classifier** (none existed — recon-confirmed) so much as a documented, auditable roll-up of the grammar's own R1/R2/R3 regime-bet semantics.

**Inert by construction (the F2/[[D141]] pattern):** computed AFTER ranking, over already-selected configs, and threaded nowhere near submit → the submitted set is byte-identical (a pure config-only tally; determinism + non-mutation pinned). The running daemon won't emit the line until a restart (Python loads at process start); a D104 reboot is also safe (additive log line, behavior-inert). Service-inert until the next ritual restart.

**Verification:** RED-first; 14 new tests (classifier per hypothesis incl. the gate/op cell key; supply tally + complement share; pool-vs-selected; empty-batch 0.0% safety; the `regime_supply:` grep contract; purity / non-mutation). Ranking + main-loop + resilience + invariants suites green (241); the new file green (14); **full mypy --strict (90 files) + ruff clean**. No live-DB / feature-cache touch.

**Files:** `src/forge/ranking/regime_supply.py` (new), `src/forge/cli/main.py` (the additive `regime_supply:` line at the post-rank seam) + `tests/unit/test_ranking/test_regime_supply.py`; `docs/architecture.md` (the ranking-row telemetry note), `docs/proposals/tail-aware-ranker.md` (T2 supply-metric marked BUILT), `STATUS.md`, this entry. Lands alongside the T3a-answer integration (proposal §4 T2/T3a + STATUS + memory). **REMAINING for T2:** the enforcement floor (reserve Z% for the complement) stays gated on complement *supply* — which this metric measures — plus the §8.6 criterion + the F3 go; the next deliberate, daemon-touching increment.

## D145 — 2026-06-14 — `relative_value` exempted from the D103 per-hypothesis submission floor — reclaim its guaranteed ~7.5%/batch share (Q40: rv is structurally 0-yielding under options-only)

**Spec section:** §6.3 diversification floor ([[D103]] introduced it). Origin: operator (this session, Sunday 2026-06-14 review, AskUserQuestion) — *"exempt rv only"* from the floor, after the review surfaced that rv's persistent ~7.5% submitted share is the **D103 reservation**, not prefilter pass-through or its (already-crushed, 0.050) learned weight. Grounds: [[Q40]] — rv is **0/3639 honest-era** and structurally 0-yielding under options-only (long-premium, no spreads, hard rule 7), so the D103 floor — built explicitly to *protect* rv as the orthogonal sleeve — is now protecting a structurally-dead family. D145 reverses that protection for `relative_value` only, on the newer evidence.

**What:** `select_top_n` / `_select_top_n_floored` (`diversifier.py`) gain a `floor_exempt_hypotheses: AbstractSet[str] = frozenset()` param; Phase 1 (the D103 per-hypothesis reservation) `continue`s past any exempt hypothesis — it gets **no guaranteed slots** but still competes **on merit** in the Phase-2 greedy fill. `queue.rank_batch` threads it; `queue._PRODUCTION_FLOOR_EXEMPT_HYPOTHESES = frozenset({"relative_value"})` is the production policy, wired at the `main.py` `rank_batch` call beside `_PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS`. Effect: rv falls from a floored 15/200 (~7.5%) toward its merit share at weight 0.050 (≈<1%); the reclaimed ~6%/batch goes to the merit-ranked pool (trend/ve/mr). `em` is deliberately KEPT on the floor — it is data-sparse (`sue`-starved), not structurally dead, so its floor preserves the chance to learn if earnings-surprise data fills in.

**NOT an enumeration change (hard rule #6 intact):** this is a **ranking-stage** selection-policy change — the deterministic `enumerate` sequence (iterator/sampler, the byte-identity property) is untouched; only which survivors get submitted changes. `grammar.yaml` is not touched → no grammar version bump (hard rule #10 N/A), no Crucible relay (rv configs remain valid; Crucible simply receives fewer). Tightening-direction (fewer known-0% submissions) so hard rule #4 is satisfied — but it is a deterministic-output behavior change, so it ships via the [[D104]] ritual restart (service-inert until then), not hot.

**Verification:** RED-first — 3 new diversifier tests (exempt-not-rescued; exempt-still-competes-on-merit; empty-exempt byte-identical to D103) + 1 queue policy test (the production constant reaches the diversifier and starves rv; the same floor rescues it once the exemption is removed — proving the exemption is the cause, and locking the `{"relative_value"}` constant). Ranking + phase4/phase6 invariants green (209); the 163 cli.main/rank_batch-touching tests green; new queue/diversifier files green; **mypy --strict clean + ruff clean/format**.

**Files:** `src/forge/ranking/diversifier.py` (param + Phase-1 skip + docstring), `src/forge/ranking/queue.py` (`_PRODUCTION_FLOOR_EXEMPT_HYPOTHESES` constant + thread), `src/forge/cli/main.py` (wired at the `rank_batch` call), `tests/unit/test_ranking/test_diversifier.py` + `tests/unit/test_ranking/test_queue.py`, `STATUS.md`, OPEN_QUESTIONS (Q40 marked resolved-by-D145), this entry. **Service-inert until the next ritual restart** (ranking code loads at process start; a D104 reboot is safe — behavior-inert until then). Resolves the Sunday-review rv-de-emphasis lever; the reclaimed capacity awaits a better destination (Crucible OverlaySpec / ranging-supply growth — see `docs/proposals/worst-quartile-complement-supply.md`).

## D146 — 2026-06-14 — Crucible's worst-quartile design note INTEGRATED — the complement is breadth/drawdown control, NOT a CPCV-p25 unlock (the wall is edge MAGNITUDE); D144's classifier over-counts (credit the gate, not the hypothesis)

**Spec section:** §8 / `docs/proposals/tail-aware-ranker.md` T2/T3, [[D144]] (the `regime_supply` classifier this corrects), [[promotion-gate-tiers-and-constraint]]. Origin: operator relayed `../Crucible/docs/design_worst_quartile_regime_complement.md` (Crucible analysis note, 2026-06-14) — the *why* behind the T3a label + explicit guidance for Forge's T2 floor. DOCS-ONLY integration (no code this entry; the D144 classifier refinement is a separate, gated increment).

**The correction (hard rule 6 honesty, Crucible-requested):** Crucible's crater decomposition (`cpcv_crater_by_regime.json`) establishes the CPCV-p25 wall is **edge MAGNITUDE, not a regime gap** — every family is positive in its best regime but **none means ≥1.5 on any regime slice (best 1.10)**. The worst quartile over-populates **bear (2.39×) / ranging (1.33×)** because the balanced frontier is all `trend·cross_sectional_rank` gated to fire only in low-vol (`rv_rank<θ`) or trending (`hurst>θ`) — by construction it holds nothing useful when SPY sells off or chops (`trend_continuation` stress-path Sharpe **−0.13**). So a bear/ranging complement is a **breadth / drawdown-concentration lever** (cuts the worst-quartile concentration + the failing `cpcv_max_drawdown_p75` 0.396) — **NOT a promotion unlock.** A complement lifts the book's p25 only if itself net-positive at promotion-grade magnitude in bear/ranging, which the pool's bear/ranging-active family (mr, best-regime ~0.62–0.65) is NOT. **The promotion unlock is a higher-magnitude edge somewhere in the book — an edge-discovery / expressivity problem, not diversity.** (Caveat from §4: don't gate `volatility_event` to zero — its stress paths are net-positive 0.65, so gating it OUT would LOWER p25; the gate helps only net-negative-in-stress families like trend.)

**What it changes for Forge:** (1) T1 + T2 are reframed as **tail/breadth hygiene** (better pool quality, lower drawdown concentration), not a CPCV-p25 unlock — the proposal §4 limits 3/4, STATUS, and the supply work-up are corrected accordingly so the floor is never sold as a promotion lever. (2) **D144's `regime_supply` classifier over-counts:** it keys credit on HYPOTHESIS, but Crucible §5.1 says payoff is set by the regime **gate + direction** — a component gated `rv_rank<θ` / `hurst>θ` does not pay in bear/ranging regardless of hypothesis. The authoritative credit is Crucible's reference-calendar JOIN (`worst_quartile_regime_mix` × SPY `reference_regime_calendar`, re-pullable per book), which Forge cannot compute (§1.2) — so Forge's structural tally is a coarse proxy, to be refined gate-aware (a gated next increment) and ultimately replaced by the Crucible credit riding T3b (`PromotedPortfolio`). (3) **Roadmap impact:** the #1 lever ("grow + diversify the pool for worst-quartile robustness") splits — diversity = necessary tail hygiene, NOT the promotion path; the promotion path is edge-magnitude/expressivity. The T2 enforcement floor is **down-prioritized** (it is tail hygiene, near-redundant with D103/D136 on the selection side per D144's live numbers, and not a p25 unlock). (4) The OverlaySpec relay is narrowed to the **dispatch-path question** (is the §5.2 single-leg long put a `StrategyConfig` or `OverlaySpec`?) and de-claims "unlock."

**No code / no behavior change** (docs + memory + relay only). The D144 shadow classifier keeps running as-is (a documented coarse proxy) until a gate-aware refinement is greenlit. **Files:** `docs/proposals/tail-aware-ranker.md` (T2 limits 3/4), `docs/proposals/worst-quartile-complement-supply.md` (magnitude-cap update), `PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md` (narrowed), `STATUS.md`, memories ([[promotion-gate-tiers-and-constraint]], [[pipeline-vision-roadmap]], [[sunday-review-2026-06-14]]), this entry.

## D147 — 2026-06-14 — §8.6 tail-robustness streak tracker (T1 clock) — pooled across the daily-rolling tail models, appended by the daily timer; PROVISIONAL criterion, telemetry-only

**Spec section:** §8.6 (the T1 wiring criterion), [[D140]]/[[D141]]/[[D143]] (the tail track), [[D142]] (the daily timer this extends), [[ranker-eval-daily-timer]]. Origin: operator (this session) — *"build the robustness streak tracker."* Follows the T1 check that found the §8.6 gate as loosely specified ("≥150 fresh verified-coverage tail-scored verdicts × 3 checkpoints") is **unreachable per-model**: the daily timer rolls a fresh robustness model each run, so per-model decided counts plateau (5174039c=85, d40dca47=49) well below 150 under the sparse verified-coverage+cpcv population + multi-day decision latency.

**What:** mirrors the F3 verdict streak (`streak.jsonl`) for the tail model. New `evaluate_tail_shadow_pooled(conn, *, since)` (`evaluation.py`) pools ALL verified-coverage cpcv-bearing tail-scored verdicts in the window across every `tail_model_id` into one `TailEvaluation` (`tail_model_id="pooled"`); `evaluate_tail_shadow` refactored to share `_tail_triples_by_model` + `_build_tail_eval` (per-model behavior byte-identical — existing tests green). `daily_ranker_eval.sh` gains a streak block that judges the pooled stat on a FRESH per-checkpoint window (verdicts decided since the prior run's `ts`, like the verdict streak), appends a row to `~/forge_data/ranker_eval/robustness_streak.jsonl` (ts, window_since, fresh_decided, n_models_fresh, spearman, k, top-K means, criterion, verdict, qualifies), and prints the trailing consecutive-PASS streak. `_TAIL_SPEARMAN_CRITERION=0.30` + script `MIN_FRESH_TAIL=50` are the PASS/qualify thresholds.

**Why pooled (not per-model):** `tail_score` is a prediction of `cpcv_p25` in the SAME units across daily models, so pooling the (score, realized) pairs is the apples-to-apples methodology check — it validates the tail-scoring METHODOLOGY, not a single rolling artifact, and dodges the per-model sparsity. Live verification (snapshot, 2026-06-14): pooled **n=144, Spearman +0.456, 2 models, verdict PASS** — vs the per-model 85/49 that never reach a 150 bar.

**The criterion is PROVISIONAL (operator owns the §8.6 margin).** 0.30 is a modest bar (both live models ~+0.41/+0.45); `MIN_FRESH_TAIL=50` is far below F3's 150 because the verified-coverage+cpcv population is far sparser than the full verdict stream. The row records the RAW pooled Spearman + n every run, so the operator can re-judge at any threshold without a re-run, then finalize §8.6. Reaching 3/3 **wires nothing** — T1 live wiring stays its own operator gate (criterion + a separate go + a ritual restart), exactly like F3.

**Telemetry-only, no service restart.** The tracker is invoked by the `forge-ranker-eval` timer (05:00 daily), not `forge.service` — the next timer fire picks up the committed script + CLI (editable install); no D104 ritual needed. NEVER touches grammar/weights/config/ranking (hard rule #5: deterministic Python, no LLM). The first `robustness_streak.jsonl` row lands at the next 05:00 fire (window = clean era → a cumulative baseline, like the verdict streak's first row).

**Verification:** RED-first — 2 new tests (`evaluate_tail_shadow_pooled` pools across models with correct pooled n/Spearman/top-K; empty → None) + the 8 existing tail/verdict eval tests green (per-model unchanged); `test_ranker_model_cmd` green; **mypy --strict + ruff clean**; `bash -n` on the script; live end-to-end dry-run (n=144, +0.456, PASS). **Files:** `src/forge/ranking/evaluation.py`, `src/forge/cli/ranker_model_cmd.py` (`_TAIL_SPEARMAN_CRITERION`), `scripts/daily_ranker_eval.sh` (streak block + `MIN_FRESH_TAIL`/`ROBUSTNESS_STREAK_LOG` + header), `tests/unit/test_ranking/test_evaluation.py`, `STATUS.md`, `docs/MANPAGE.md`, [[ranker-eval-daily-timer]], this entry.

## D148 — 2026-06-14 — Crucible bear-complement adjudication + ranker-wiring greenlight: bear CLOSED (keep D066), F3 wiring + T2 ranging-only floor + mean_reversion supply growth GREENLIT (builds pending)

**Spec section:** §8 / `docs/proposals/tail-aware-ranker.md` T2, §5 wiring; [[D066]] (tail_hedge overlay-only, now affirmed), [[D146]] (the magnitude reframe), [[D147]] (the §8.6 clock). Source: operator relayed `../Crucible/docs/handoffs/FORGE_bear_complement_decision.md` + `FORGE_greenlight_ranker_wiring_and_ranging.md` (both Crucible-side, DECIDED + operator-approved 2026-06-14, validated on live data). DOCS-ONLY this entry; the greenlit builds are separate operator-gated increments.

**Bear is CLOSED for Forge (answers our `PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md` Q1/Q2).** Q1: only `tail_hedge` carries the PF/WF/CPCV gate exemption (`runner.py:757-825`), so a constant negative-carry put/long-vol hedge **cannot clear `deflated_sharpe`/`profit_factor` standalone** (confirms our engineering read); only a *timed* downside-directional bet could gate-pass. Q2: on 8,714 `long_short` rank runs / ~1.7M trades the short leg (long puts) is **net-negative in bear (−0.057)** and positive only in marginal ranging (+0.016) — single-name rank puts are a *relative* bet on weak names, not a market hedge (REFUTES the `edge-magnitude-levers.md` lever-1 hope that `long_short` already supplies bear). ⇒ **Do NOT add a §3.5 bearish-direction rule; keep D066.** Bear is the Crucible-owned **`tail_leg` overlay** (already 10%-OTM, §20 `tail-otm-deepening`; an era-C 0.10/0.12/0.15 depth A/B is running). Off Forge's plate.

**Three Forge moves GREENLIT (operator-approved, builds pending):**
1. **F3 (P(component) model → ranking) wiring** — criterion MET (verdict streak **4/4** qualifying PASS, AUC margin 0.21–0.50 ≫ +0.05). Production ranking is still pure Jaccard (`prior_promotion.py`); spec is `tail-aware-ranker.md` §5 (`prior_promotion_proximity := model P(component)`). Build + wire, deploy at a restart, **keep the Jaccard kill-switch + shadow-compare N batches**. Triple-gate now criterion ✓ / operator-go ✓ / build+restart (pending).
2. **T2 regime-complement floor — RANGING ONLY** (bear dropped, per above). Ship **with** move 3 (else it caps trend but has ~5 ranging configs to reserve). Deterministic D136-style insertion; D105 firewall + hard rules 3/6/7 untouched.
3. **Grow `mean_reversion` (ranging) supply** (operator-gated grammar) — ranging is the return-seeking, gate-passable half of the worst-quartile complement (mr ranging-active, thin: 49/342 era-C, 236/2661 last split). Bump weight/floor toward ranging-admitting regime gates so the T2 floor has something to reserve.

**Honest framing (hard rule 6) — none of this unlocks promotion.** World A holds: the wall is edge *magnitude*; ranging `mean_reversion`'s best-regime Sharpe (~0.62–0.65) is sub-promotion-grade. F3 wiring + T2 ranging floor + ranging supply are **selection quality + tail/breadth/DD hygiene** — pitch the floor as such, never as a p25 unlock. **The promotion unlock is a genuinely higher-magnitude adverse-regime edge — "regime-orthogonal arms"** (the open Forge research problem; the real producer #1 toward QuantIQ promotions, ahead of the diversity hygiene).

**Files (docs):** `PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md` (ANSWERED/CLOSED banner), `docs/proposals/edge-magnitude-levers.md` (levers 1+4 closed/refuted, recommendation updated), `docs/proposals/tail-aware-ranker.md` (T2 retarget banner — ranging only + F3 greenlit), `docs/proposals/worst-quartile-complement-supply.md` (bear closed, ranging is the Forge half), `STATUS.md`, memories ([[promotion-gate-tiers-and-constraint]], [[pipeline-vision-roadmap]], [[sunday-review-2026-06-14]]), this entry. **No code; the F3/T2/supply builds await operator sequencing.**

## D149 — 2026-06-14 — F3 wiring: `prior_promotion_proximity := P(component)` in production ranking (verdict_scorer + Jaccard kill-switch) — BUILT, service-inert

**Spec section:** §6.2 (the `prior_promotion_proximity` term), `docs/proposals/tail-aware-ranker.md` §5, [[D148]] (the operator-approved greenlight). Origin: operator — *"yes"* to building the F3 wiring. The F3 criterion is MET (verdict streak **4/4** qualifying PASS, AUC margin 0.21–0.50 ≫ +0.05); production ranking had stayed pure Jaccard (`prior_promotion.py`) because the wiring increment was never built.

**What:** `rank_batch` gains `verdict_scorer: Callable[[StrategyConfig], float] | None = None`. When provided, the per-candidate prior term is the learned **P(component)** score INSTEAD of `compute_prior_promotion_proximity` (Jaccard); `None` is the **Jaccard kill-switch** (legacy, byte-identical — proven by a test). `main.py` `_run_one_iteration` builds the scorer from `load_latest_model(models_dir)` + `extract_features(config, registry)` + `score_features` — the SAME path `shadow.py` runs every batch (so the glue is production-proven) — gated by the `FORGE_F3_RANKER` env kill-switch (default on; `off`/`0`/`false`/`no` → Jaccard). Logs `f3_ranker: P(component) prior ACTIVE (model=…)` or the Jaccard fallback reason each batch. P(component) thus fills the §6.2 `prior_promotion_proximity` slot (~10% weight; the term was dead weight at 0.0 with 0 promotions) — every other §6.2 term and weight is untouched.

**Determinism / hard rules:** ranking-stage change — the deterministic `enumerate` sequence is untouched (hard rule 6 N/A; linear model eval over deterministic features is itself deterministic). No `grammar.yaml` / gate / threshold / promotion-bar change (hard rules 3/6); no version bump, no Crucible relay. Tightening-direction is N/A (this reshapes selection, not volume) — it ships via the [[D104]] ritual restart with the kill-switch retained, NOT hot.

**Rollout posture (per the greenlight):** keep the Jaccard kill-switch + shadow-compare. NOTE the shadow-eval semantics shift post-wiring: the §6.2 composite now CONTAINS P(component) via the prior, so the F3 `eval` AUC "incumbent = composite" comparison becomes partly circular — reinterpret the eval as a monitor, not a fresh A/B, once live (telemetry-only; no behavior impact). The T1 tail-score blend (cpcv_p25) is the SEPARATE, still-§8.6-gated next layer (D147 clock accruing) — D149 wires P(component) only.

**Verification:** RED-first — 2 new `rank_batch` tests (verdict_scorer drives the prior + ranks the high-P(component) pick first; `verdict_scorer=None` reproduces the legacy Jaccard byte-for-byte) + the 11 existing queue tests; **353 ranking + all cli.main/rank_batch-touching tests green**; mypy --strict + ruff clean. **SERVICE-INERT until the next ritual restart** (ranking code loads at process start; a D104 reboot is safe — defaults to Jaccard when no model, P(component) when one exists). **Files:** `src/forge/ranking/queue.py` (`verdict_scorer` param + prior swap + docstring), `src/forge/cli/main.py` (scorer build + `FORGE_F3_RANKER` kill-switch + per-batch log + `Callable` TYPE_CHECKING import), `tests/unit/test_ranking/test_queue.py`, `STATUS.md`, this entry. **DEPLOY PENDING (operator-gated ritual restart).**

## D150 — 2026-06-14 — grammar v20: mean_reversion (ranging) supply growth — R1 `hurst` gate + regime-gate bias toward ranging; MR rank SUPPRESSED (Q33-gated)

**Spec section:** §3.5 R1, `docs/proposals/t2-ranging-floor-and-supply.md`, [[D148]] (Crucible greenlight Decision 2), [[D107]] (the gamma_flip widening this mirrors), [[D116]] (MR-never-ranks, which this preserves). Origin: operator-approved (this session) — Option 1 + Option 2, one v19→v20 bump. Operator-DIRECTED loosening (not auto), grammar-change ritual (`docs/tasks/grammar-change.md`).

**What (three Python-side changes; NO `rules:`-gate / threshold / promotion-bar change, hard rules 3/6):**
1. **R1 widened (Option 2):** `hurst` (op `"<"`, the mean-reverting H<0.5 side) joins `iv_rank` + `gamma_flip_distance_pct` as an accepted `mean_reversion` regime gate — the purest ranging signal. `custom_predicates._R1_HURST_REGIME_INDICATOR` + R1 acceptance; `search_space` MR regime pool += hurst; `sampler._regime_signal_params` sets op `"<"` for MR's hurst gate. Mirrors D107 (same indicator R2 uses for trend at op `">"`; C4 keeps it single-role).
2. **Regime-gate bias (Option 1):** `sampler._pick_regime` weights MR ~3:1 toward the ranging gates (`gamma_flip`, `hurst`) vs the prefilter-sparse `iv_rank` (stays explorable at 1.0). Grows *effective* ranging supply from the same MR enumeration share. Engages only with >1 gate present (single-gate registry stays byte-identical to `rng.choice`).
3. **MR rank SUPPRESSED (`sampler._RANK_INELIGIBLE_HYPOTHESES = {"mean_reversion"}`):** the new bar-based `hurst` gate is NOT single-name-only, so it would re-open the MR `cross_sectional_rank` branch D116 closed (empirically ~7% of MR at the 1/3 share — emission proof). MR is held SINGLE-NAME until Crucible confirms per-name hurst-rank coherence (Q33, `rank_per_name_coherent`) — relayed in `PROMPT_CRUCIBLE_MR_HURST_RANK_COHERENCE.md` (operator-sent 2026-06-14). Re-enabling is a one-line guard removal once Q33 is answered.

**Why:** the ranging half of the worst-quartile complement ([[D146]]/[[D148]]): ranging worst-quartile lift 1.33×, addressable by `mean_reversion` (the return-seeking, gate-passable ranging family, thin at 49/342). Pairs with the (greenlit, separately-built [[D149]]) F3 ranking wiring + D103's existing MR floor (which now binds on grown supply). **Honest cap (hard rule 6):** not a promotion unlock — ranging MR best-regime Sharpe ~0.62–0.65 is sub-grade; this is breadth/selection hygiene.

**Determinism / grammar:** enumeration-policy widening + bias → the deterministic stream changes (the bias re-weights MR's regime pick; the hurst gate adds configs), so `grammar_version` v19→**v20** for cohort attribution (archive `grammar_archive/v20.yaml` byte-identical; GRAMMAR.md R1 synced). The cold path (no >1 gate) stays `rng.choice`-identical. Relayed for `crucible funnel --compare v19 v20`.

**Verification:** RED-first — R1-accepts-hurst, MR-pool-includes-hurst, sampler hurst op `"<"`, `_pick_regime` ranging bias, and the MR-rank-suppression regression (hurst-gated MR stays confluence at share 1.0) + 2 deliberate re-pins (the minimal-fixture MR pool + the R1/R2/R3 regime-membership test). Emission proof: MR RANK=0 (suppressed), trend rank unaffected (234), MR ranging-gate share ~84%. **652 enumeration/grammar/invariants green; full suite + mypy --strict + ruff at deploy.** **Files:** `config/grammar.yaml` (v20 + header), `config/grammar_archive/v20.yaml`, `src/forge/grammar/custom_predicates.py`, `src/forge/enumeration/search_space.py`, `src/forge/enumeration/sampler.py`, `docs/GRAMMAR.md` (R1), tests (`test_custom_predicates`, `test_search_space`, `test_sampler`, `test_cross_sectional_rank`), `PROMPT_CRUCIBLE_MR_HURST_RANK_COHERENCE.md`, `docs/proposals/t2-ranging-floor-and-supply.md`, `STATUS.md`, this entry. Batched with [[D149]] (F3 wiring) in the v20 restart.

## D151 — 2026-06-14 — grammar v21: mean_reversion RANK ENABLED — Q33 answered YES (hurst per-name-coherent); the D150 hold removed, governance reverts to the published flag

**Spec section:** §3.5 R1 / H1 rank, [[D150]] (the conservative hold this removes), [[D116]] (the chain-reading skip, which stays correct), `PROMPT_CRUCIBLE_MR_HURST_RANK_COHERENCE.md`. Source: operator relayed `../Crucible/docs/handoffs/FORGE_q33_hurst_rank_coherence_response.md` (Q33 ANSWERED + operator-approved): **YES — `hurst.rank_per_name_coherent = True`**; enable it. Operator chose a clean v20→**v21** bump (not a fold into the just-deployed v20, which had 0 submissions but could produce a cohort any moment).

**Q33 answer (Crucible, structural + empirical proof):** on the `cross_sectional_rank` path the runner evaluates every signal **per ranked sym**; a `hurst` gate resolves to `Hurst.compute(sym_bars)` — pure per-name close-price autocorrelation, no chain, no reference underlying (`hurst.py`, `_indicator_cache.py` keyed `(id, params, underlying)`). Structurally unlike `iv_rank`/`gamma_flip`, which default their *chain* to SPY (the D116 incoherence). Corroborated by the fail-open sweep (`bar_only_all_coherent=true`) and the published registry flag (`hurst.rank_per_name_coherent=True`, added `9da86f4` 2026-06-09 — already in the live snapshot).

**What:** removed `sampler._RANK_INELIGIBLE_HYPOTHESES` (the D150 `{mean_reversion}` hold) + its guard clause. Governance reverts to the existing **flag-based** skip (`_uses_single_name_only_indicator(signals, space.rank_excluded_ids)`, keyed on the published `rank_per_name_coherent`): a **hurst-gated mr config RANKS**; **iv_rank/gamma_flip-gated mr stays single-name confluence** (D116 intact for the chain-readers). Crucible's recommendation — "key on the published flag, the same way chain-exclusion keys on False" — is satisfied exactly by removing the hypothesis hold. Emission proof: mr ranks ONLY via hurst (121/8000 at the 1/3 share); zero iv_rank/gamma_flip mr rank.

**Honest caveats (Crucible, hard rule 6):** (1) **coherence ≠ promotability** — the breadth lift (rank → trade count ≫ `min_oos_trade_count`) lifts the distribution CENTER, NOT the worst-quartile p25 (the binding portfolio wall); enable for legitimate ranging *supply/breadth*, do NOT budget promotions from it. (2) **short-history fail-open** — `hurst` needs ~101 sessions; below that → NaN → allow=True, so the effective ranging-filtered universe is names with ≥~101 sessions.

**Determinism / grammar:** removing the hold changes the mr enumeration stream (mr now ranks via hurst) → `grammar_version` v20→**v21** (clean cohort boundary; v20 had 0 submissions). NO `rules:`-gate / threshold / promotion-bar change (hard rules 3/6). Relayed for `crucible funnel --compare v20 v21`.

**Verification:** RED-first — the D150 suppression regression rewritten to the enable expectation (`test_mean_reversion_hurst_gate_ranks_chain_gate_does_not`: hurst-gated mr ranks, iv_rank-gated mr confluence) + 2 D116-era tests re-pinned (the skip is now gate-specific, not "all mr confluence"). Emission proof (mr ranks only via hurst); full suite + mypy --strict + ruff at deploy. **Files:** `src/forge/enumeration/sampler.py` (guard removed), `config/grammar.yaml` (v21 + header), `config/grammar_archive/v21.yaml`, `docs/GRAMMAR.md` (R1), `tests/unit/test_enumeration/test_cross_sectional_rank.py`, `tests/integration/test_v1_grammar.py` (version pin v21), `STATUS.md`, this entry. Q33 CLOSED.

## D152 — 2026-06-15 — Long-options exhaustion CRUCIBLE-CONFIRMED (4/4 empirical checks + independent 22-source sweep) → verdict PROVISIONAL → CONFIRMED; Path-C provability gate SATISFIED

**Spec section:** §1.2 (Forge computes no metrics — Crucible measures), §8.7 (the gate, unchanged), [[D146]] (the magnitude reframe this closes), [[D148]] (bear closed / regime-orthogonal pointer). Source: operator relayed `../Crucible/docs/handoffs/FORGE_long_options_exhaustion_consolidated.md` — Crucible's empirical + theoretical answer to `PROMPT_CRUCIBLE_LONG_OPTIONS_EXHAUSTION.md`. **DOCS-ONLY; no code, no grammar, no gate, nothing deployed.** Records a gating *decision* (the long-options frontier is closed; the Path-C scope question is unblocked), per the operator's "exhaust long-options before v2 spreads" directive ([[exhaust-long-options-before-v2-spreads]]).

**The ask was confirm-or-REFUTE; Crucible tried to refute and could not.** All four checks confirm on the live book:
- **M1 (decisive, gross-vs-net):** honest-era max **gross CPCV-p25 = 1.40 < 1.5**, cost ratio 1.00–1.10 → **IC-bound, not cost-bound**. Path B (execution-cost reduction) does not unlock adverse-regime magnitude — the raw edge isn't there. The only ≥1.5 "components" are `$0-slippage` WF-failing pre-cost-floor artifacts (filter `avg_slippage > 0`).
- **M2 (vol-target the convex book):** +0.07 to p25 (→ ~1.27), tail-shape; the real effect is drawdown (DD-p75 +0.27–0.33). The one residual lever (assessment nuance #1) is a **risk/shape lever, not a 1.5 path** — closed.
- **M3 (effective spread):** `bid==ask==mark`, no NBBO → true spread unmeasurable, but their §7.2 model is at Cao-Han's pessimistic end → net is *over*-costed; gross (1.40) is the clean read and best-execution can't lift net above gross.
- **M4 (deflation):** §8.7 DSR deflates by **selection-campaign size + PBO**, not raw enumeration → **Forge's enumeration method is vindicated** (assessment nuance #2 confirmed); the edge is absent, not hidden by overfitting.

**Plus their own independent 22-source literature sweep (23/25 claims adversarially verified) converges with our two deep-dives → QUAD-convergent:** long premium net-negative at source; conditioning on vol/jumps/tail marks the SELLER's edge, not a long rescue (Bakshi-Kapadia t=−4.39; Coval-Shumway crash-neutral straddle still −3%/wk); every documented high-Sharpe option signal is a short-leg/writing edge. **Inventory complete** — 52 indicators span the conditioner taxonomy; the 6 "untried" levers do NOT reopen the case (`iv_term_slope`/`vix_term_slope`/`iv_minus_rv` low-EV as long-only gates; **VOV/IVOL adverse → Crucible withdrew its "buy cheap-vol" long-trigger framing, reframed as exclusion filters**; constant-maturity creates no long-side edge).

**Verdict transition (operator's two conditions):** (a) "Crucible empirically agrees/refutes" = **MET (agrees)**; (b) "more decided items" = converted to a **defined standing monitor** — gross 1.40 is "not a comfortable margin," so **re-run M1/M2 as the decided-CPCV population grows; a creep to ≥1.5 is the sole reopener.** ⇒ **PROVISIONAL → CONFIRMED.**

**What this unlocks (operator decision, NOT auto-actioned):** the operator's Path-C provability gate ("only open v2 for spreads if long-options provably can't clear the bar") is **SATISFIED**. Path C is unblocked as a *decision* — still operator-gated, **debit-verticals-first** (net-debit, defined-risk, covered short — not naked premium-selling), and gated by the safety probe+test program in `regime-orthogonal-arms.md`. Crucible's sell-side VRP probe (`vrp_short_premium_by_regime.json`: short-vol positive every regime, strongest low-vol/calm) corroborates the direction; their sizing is in flight. **Remaining in-scope long-options actions are both very-low-EV** (enumerate the 3 published conditioners as gates = near-free confirmation; VOV/IVOL exclusion filters = hygiene) — neither is a promotion path. Hard rule 3 holds throughout (any future sleeve clears the same §8.7 bar).

**Files (docs/memory only):** `docs/proposals/long-options-exhaustion-assessment.md` (verdict → CONFIRMED; M1–M4 folded in; nuance #1 + the 3 cheap checks marked ANSWERED; VOV/IVOL exclusion reframe; Path-C gate satisfied), `docs/proposals/regime-orthogonal-arms.md` (confirmation banner), `PROMPT_CRUCIBLE_LONG_OPTIONS_EXHAUSTION.md` (ANSWERED banner), `STATUS.md`, memory [[exhaust-long-options-before-v2-spreads]], this entry. No production change.

---

## D153 — 2026-06-15 — Long-options exhaustion REOPENED on conditioning-completeness grounds → Path-A rich-conditioning sweep (3 threads, in-scope); the search/magnitude claim is PROVISIONAL pending the sweep; the structural/sign claim stands

**Spec section:** §1.2 (Forge computes no metrics — Crucible measures), §3.5 R1 (the `iv_rank` mean_reversion gate), §3.6 (the enumeration-space collapse single-gating buys), §8.7 (the gate, unchanged), hard rule #5 (clarified: bans LLMs, **not** ML), hard rule #9 (untouched — this is in-scope, no scope expansion), [[D152]] (the verdict this qualifies), [[D107]]/[[D150]] (the `gamma_flip`/`hurst` R1 proxies added *because* `iv_rank` is inert). Source: operator — "before we declare long options a failure, brainstorm." **DOCS-ONLY; no code, no grammar, no gate, nothing deployed.**

**What prompted it.** A code-grounded audit (sampler / grammar / indicators / ranker / prefilters) of *how Forge conditions a long-options bet* shows [[D152]]'s decisive read (M1: max **gross** CPCV-p25 = 1.40 < 1.5 → IC-bound) was measured over a **crudely-conditioned** population. Mapped to the operator's delta/theta/vega framing:
- **Delta (direction):** not optimized — fixed per bucket, sampled uniformly in a band (swing_short Δ 0.40–0.55 @ 14–21 DTE, etc.); not conditioned on state.
- **Theta (time decay):** **never computed** — implicit in the DTE band, never an explicit gate; nothing in the pipeline seeks low-bleed entries.
- **Vega / IV cost:** the weakest axis. The canonical "buy only when vol is cheap" gate `iv_rank` is a **NaN-only stub** (`docs/INDICATOR_THRESHOLDS.md:83,87,123`), which makes **§3.5 R1 "structurally unsatisfiable"** (`:131`) — so mean_reversion has gated on `gamma_flip` (D107) and `hurst` (D150) *regime-shape* proxies, **never on vol-cheapness**. The live IV conditioning (`iv_minus_rv` v17, `iv_term_slope` v18) is recent, thin, and directional, not a vol-cost gate.
- **Conditioning structure:** a config attaches **one** regime gate — it cannot express the joint Greek state (`Δ≈0.40 ∧ IV-rank<30 ∧ ¬pre-earnings ∧ bear`). Single-gating is what collapsed the enumeration space ~10^15→~10^6 (§3.6); the cost was joint-conditioning expressiveness on the long side.

**Decision — split the verdict, run the in-scope sweep before accepting failure.**
- **Structural/sign claim: NOT reopened.** Long premium is net-negative at source; the high-Sharpe edge is sell-side; conditioning changes *when/how much* VRP you pay, not the sign (Bakshi-Kapadia t=−4.39; Coval-Shumway crash-neutral straddle −3%/wk). [[D152]]'s structural finding stands.
- **Search/magnitude claim: REOPENED → PROVISIONAL pending the sweep.** 1.40 bounds *our grammar's long-side expressiveness*, not the asset class, because the vol-cost gate was inert and conditioning was marginal.
- **Launch the Path-A rich-conditioning sweep** (`docs/proposals/path-a-rich-conditioning.md`), risk/cost-ordered, all in-scope (single-leg net-debit long premium — **no hard-rule-9 touch**): **(1)** light up the vega axis — Crucible ships an ATM-IV cache → `iv_rank` live → §3.5 R1 satisfiable → re-enumerate mr (no grammar change; `iv_rank` is already the R1 gate). First action: `PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` (drafted, ready to relay). **(2)** joint-gate the entry — add theta/vega proxies + a bounded conjunction of conditioners (≤3 gates), prefilter-pruned; grammar change → operator-gated + version bump. **(3)** learn the conditioner — a deterministic, **non-LLM** learned model on the joint market state vs Crucible's conditioned-return labels, registered as a gated indicator.

**Hard rule #5 clarification (operator correction).** #5 bans **LLMs** in the production loop, **not ML.** A deterministic, non-LLM learned model is allowed in-loop (the ranker already is one). An earlier draft of this analysis mis-stated #5 as "no ML in loop"; corrected in the proposal and here.

**Calibrated EV (recorded so we don't over-promise).** The realistic prize is closing the thin **1.40→1.5 pocket**, NOT the 2.39× bear arm (sell-side, Path C). Crucible's "Inventory complete" prior rates IV conditioners low-EV for long-only — but that prior was formed on index literature + an inert vol-cost gate, never on our single-name net-debit book with the gate live. **Two clean outcomes:** a thread clears the pocket → cheap in-scope arm (Path C parked longer); OR all three fail → the *real* exhaustion on a properly-conditioned book (a **stronger** verdict than D152) → vindicates Path-C's parking.

**Relationship to Path C (parked, D152).** Does NOT un-park it; **reopens the exhaustion precondition** → D152's "Path-C provability gate SATISFIED" becomes "satisfied *pending* the rich-conditioning sweep"; Path-C resume pushed out behind the cheap in-scope sweep. The structural verdict is unchanged, so Path C stays the *likely* eventual unlock — just deferred. The standing M1/M2 monitor runs in parallel regardless.

**Alternatives considered:** (a) accept [[D152]] as final and proceed to Path-C sizing — rejected by operator ("before we declare a failure, brainstorm"); the exhaustion was demonstrably measured over a thinly-conditioned book. (b) Treat the sweep as the assessment's existing "very-low-EV residual actions" (enumerate 3 conditioners; VOV/IVOL exclusion) — insufficient: those are marginal `iv_term_slope`/`iv_minus_rv` gates, whereas the sharp gaps are the *stubbed vol-cost level gate* (`iv_rank` → R1 unsatisfiable), *joint* conditioning, and a *learned* conditioner — none in that residual list. (c) Jump straight to a learned conditioner (thread 3) — rejected as out-of-order; thread 1 is near-free and supplies the IV features threads 2–3 need.

**Action:** wrote `docs/proposals/path-a-rich-conditioning.md` (the active in-scope program) + `PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` (thread-1 relay, drafted); qualified `docs/proposals/long-options-exhaustion-assessment.md` (search-claim reopened banner) + `docs/proposals/path-c-scope-expansion.md` (precondition-reopened note); `STATUS.md` top block; memory [[exhaust-long-options-before-v2-spreads]] (reopening) + a new feedback memory on the rule-#5 clarification; this entry. No production change; nothing sent to Crucible (relay awaits operator). **[SUPERSEDED IN PART by [[D154]] — the load-bearing "`iv_rank` is a NaN stub" premise was a stale-doc error; thread 1 is falsified and the reopening is largely retracted. This entry is preserved as the append-only record of what was decided at the time.]**

---

## D154 — 2026-06-15 — D153 reopening LARGELY RETRACTED: `iv_rank` was never a stub (stale-doc error); the vega axis was live + its best near-miss craters on CPCV → exhaustion REINFORCED; reopening reduced to two low-EV threads

**Spec section:** §1.2, §3.5 R1 (the `iv_rank` mean_reversion gate — satisfiable, not "unsatisfiable"), [[D031]] (un-stubbed the five D030 stubs, 2026-05-15), [[D107]]/[[D150]] (the `gamma_flip`/`hurst` R1 proxies + the D150 `iv_rank` de-weighting), [[D116]] (rank-path exclusion), [[D152]] (the verdict, stands), [[D153]] (the reopening this corrects). Source: operator relayed `../Crucible/docs/handoffs/FORGE_iv_rank_already_live_coverage.md`. **DOCS-ONLY; no code, no grammar, nothing deployed.**

**The error.** [[D153]] reopened the long-options search/magnitude claim on the premise that the vega/IV-cost axis was dark — specifically that `iv_rank` is a "NaN-only stub" making §3.5 R1 "structurally unsatisfiable." **That premise was false.** It came from `docs/INDICATOR_THRESHOLDS.md` §9 — a **2026-05-14 pre-D031 audit** — which an audit agent read instead of the code. `indicator_thresholds.py:18-22` explicitly records that D030's "stub" framing was **obsoleted by D031 (2026-05-15)**, and `:236` gives `iv_rank` a live spec (`regime_range=(10,50)`, R1 ≤ 50 honored).

**Crucible's refutation (verified Forge-side against code).** `iv_rank` is live: non-NaN ~100% single-name across 2018→2026; v4 since 2026-06-10T15:52:04Z; **used as a regime gate in 3,998 runs / 77 components** and directionally in vol_event with hundreds of trades — structurally impossible for a NaN-only indicator (NaN → FLAT → 0 trades). Forge-side code confirms: `iv_rank` is not in `_SKIP_SPEC`; it is explorable for mean_reversion at weight 1.0 (never zeroed); it is correctly excluded from the `cross_sectional_rank` path ([[D116]], `rank_per_name_coherent=false`). The *only* current reason mr rarely gates on it is the [[D150]] **3:1 de-weighting** ("fires too sparsely to survive the prefilter") — a live sparseness reason, NOT a stub. (DuckDB CLI absent on the box → the runs-DB *counts* are deferred to Crucible, the authority; the liveness conclusion is decisive from code alone.)

**Why this REINFORCES the verdict.** The vega axis was live and used in the "gross 1.40" population, and its **strongest near-miss is itself vega-conditioned** — `iv_rank × days_to_opex` at WF 1.43 / **CPCV-p25 0.70** — a long config that conditions on vol-cheapness *and still craters on CPCV* (the binding wall). So conditioning on the vega axis does not lift long premium over the wall; it confirms the wall. The structural/sign claim ([[D152]]) was never in question.

**Corrected decision.**
- **Thread 1 (light up the vega axis): premise falsified → collapses to** (i) a **doc fix — DONE** (`docs/INDICATOR_THRESHOLDS.md` corrected: §9 stub table, skip-list, and §3.5-R1-"unsatisfiable" caveat all marked obsolete-per-D031) + (ii) an **optional, low-EV** mr experiment (lift `iv_rank`'s mr R1 weight, single-name path, re-enumerate — a sampler-weight/enumeration change, operator-gated; Crucible: cheap but low-EV). `PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` → **ANSWERED/moot, not sent** (nothing to ship).
- **Threads 2 (joint conditioning) + 3 (learned conditioner): survive as genuinely untried but LOW-EV.** They never depended on the stub — single-gate-per-entry is real (confirmed in `sampler.py`), and no market-aware learned conditioner exists. But EV is now judged low: the best single-gate vega config already craters on CPCV, and Crucible's prior rates IV conditioners low-EV for long-only.
- **One genuine gap (Crucible §4):** `skew / risk-reversal` is **absent** — the only unbuilt IV-surface conditioner. But it is a **seller** signal (wrong-signed for long premium per the assessment), so it is **Path-C-relevant, not a Path-A long conditioner** — do not request the build for Path A.
- **Verdict state restored:** the search/magnitude claim is **reinforced, not reopened**; **Path-C's provability gate ([[D152]]) stands SATISFIED** (D153's "pending the sweep" qualifier withdrawn); Path C stays **PARKED by operator choice.** The standing M1/M2 monitor is unaffected.

**Process lesson (recorded as a memory):** for indicator *liveness*, trust the code (`indicator_thresholds.py`) + the registry, NOT the narrative `docs/INDICATOR_THRESHOLDS.md` (a dated audit). An Explore agent surfaced the stale doc; I did not cross-check the code before building on it. See [[indicator-thresholds-doc-stale-pre-d031]].

**Alternatives considered:** (a) edit D153 in place — rejected; the log is append-only, so D153 is preserved and D154 records the correction. (b) Delete `path-a-rich-conditioning.md` + the relay — rejected; the relay is marked ANSWERED (history), and the doc is walked-back-but-retained because threads 2/3 are still the reference if the operator elects the low-EV probe. (c) Keep the reopening active — rejected; the evidence now leans toward exhaustion, and continuing to call it an "active reopening" would overstate the case.

**Action:** corrected `docs/INDICATOR_THRESHOLDS.md` (root cause), `docs/proposals/path-a-rich-conditioning.md` (walked back: banner + §0 + thread 1), `docs/proposals/long-options-exhaustion-assessment.md` + `docs/proposals/path-c-scope-expansion.md` (banners retracted), `PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` (ANSWERED), `STATUS.md` (top block), memory [[exhaust-long-options-before-v2-spreads]] (corrected) + new [[indicator-thresholds-doc-stale-pre-d031]]; this entry. No production change; nothing sent to Crucible.

## D155 — 2026-06-15 — Tail-aware (T1) robustness model STATIC AUDIT: validated on verified-coverage (tail_score↔cpcv_p25 Spearman +0.35 vs P(component) +0.12) but verified-only + weak; §1 "anti-correlated" premise SOFTENED; no leakage, non-redundant, underfit-not-overfit

**Spec section:** §8.3 (metric distributions weight the ranker — T1's sanction), §1.2 (Forge consumes Crucible's gate values, computes none), [[D140]]/[[D141]] (T1 head built + shadow-recording), [[D147]] (§8.6 pooled streak), `docs/proposals/tail-aware-ranker.md` §1/§8. Trigger: operator — "ensure the model is doing what we expected and doing it well." Read-only audit on a /tmp snapshot of the live DB. **NO code, grammar, or deploy.**

**Audited** the `RobustnessModel` (ridge on `cpcv_sharpe_p25`, `model.py:442`) — shadow-recording (`tail_score`/`tail_model_id`), NOT wired into ranking (T1 wiring gated). Also re-confirmed the live verdict model (F3): honest eval, real OOS skill (4/4 PASS, AUC ~0.9), keys on structure not the trend flag (Goodhart not realized) — a *selection* tool that cannot move promotions (still 0; magnitude-bound). Tail-model findings (honest-era):
- **No leakage** — 0/10,400 (`5174039c`) + 0/9,400 (`d40dca47`) tail-scored candidates had a verdict decided ≤ the scoring model's `trained_through` (frozen-at-submit, same posture as the verdict model).
- **Non-redundant** with P(component) — corr(tail_score, model_score) +0.14/+0.16.
- **Underfit, not overfit** (corrects a mid-audit worry) — trains on **4,194 rows** (the "144" is the *eval* slice), train **R²≈0.19**, coefficients stable across the two daily retrains (mr +0.044→+0.050; regime_id=iv_rank −0.042→−0.052; dir_id=donchian +0.050→+0.050).
- **Alignment validated — but verified-coverage-only.** Split on `honest_regime_coverage_row`: VERIFIED (n=371) tail_score↔realized cpcv_p25 Spearman **+0.350** vs P(component) **+0.119** (~3×); UNVERIFIED (n=1,270) TIE at +0.219. Ground truth concurs: verified mr 0.669 > ve 0.544 > trend 0.415 (doc premise holds); unverified inverts (trend 0.240 > ve 0.162 > mr 0.126). Verified ≈ **24%** of decided-with-cpcv (1,394 / 5,784).

**Decision.** Tail model PASSES the static audit and does retarget toward the binding constraint (~3× P(component)) on the slice it is built for. **`tail-aware-ranker.md` §1 corrected:** "P(component) anti-correlated (~180°)" → "weaker + family-tilted the wrong way" (measured weakly +0.119, not negative; the inversion is hypothesis-level — favors ve/trend, disfavors mr). Residual caveats (replacing the n=144 overfit worry): weak magnitude (R² 0.19, verified Spearman +0.35); value confined to the ~24% verified slice; §8.6 streak (+0.456 dry-run) thin + one point (pooled verified +0.350); cpcv individual ≠ portfolio contribution (T3b, open). **Wiring posture unchanged** — the static half justifies the planned BLEND (§8.3 decision 3) on verified candidates; the generalization verdict waits on the §8.6 streak.

**Tracking:** `scripts/tail_verified_alignment.py` reproduces the verified-split tail-vs-P(component) comparison + the verified-coverage population trend on a snapshot, runnable as the streak grows.

**Action:** this entry; `STATUS.md` top block; `docs/proposals/tail-aware-ranker.md` §1 correction; `scripts/tail_verified_alignment.py`; memory [[tail-model-verified-coverage-only]]. No production change; nothing sent to Crucible.

---

## D156 — 2026-06-15 — Path-A rich-conditioning sweep CLOSED after scoping: warm-up dominated, thread-2 held; long-options exhaustion stands REINFORCED; thread-2 state-conditioned-selection deferred to compose with the operator's learned conditioner

**Spec section:** §1.2, §3.5 C3 (max 4 signals — the joint-gate capability already exists in-grammar), §5 (prefilter battery / trade-count gates), §8.7 (CPCV trade-count penalty), [[D150]] (the `iv_rank` mr de-weighting + its sparseness rationale), [[D154]] (the iv_rank-live correction that reduced the reopening to threads 2/3), [[D155]] (the operator's parallel tail/conditioner model work). Source: operator chose, after scoping, "Hold thread 2; accept the reinforced exhaustion." **DOCS-ONLY; no code, no grammar, nothing deployed.** Closes the brainstorm → D153 reopen → D154 retract → "pursue the builds" arc.

**Scoping findings that drove the decision (Forge-side, verified against code):**
- **Warm-up (force `iv_rank` as mr's solo R1 gate) is DOMINATED.** Its viability question is already answered NEGATIVE by production evidence: D150 de-weighted `iv_rank` for mr because it "fires too sparsely to survive the prefilter (the v6 expected_trades history)"; Crucible saw 0 mr-rank components / thin single-name mr. The only ways to "re-test" are a demo-registry/synthetic-cache offline run (`forge enumerate`/`prefilter` both use `load_registry(allow_demo_fallback=True)` → ungrounded noise; the 2026-05-28 RCA) or an expensive production deploy that likely just re-confirms the sparseness. Not worth either.
- **Thread 2 (joint conditioning) is cheaper than feared structurally but hits a fundamental constraint.** The grammar ALREADY permits joint gates — **§3.5 C3 allows 4 signals** (1 directional + ≤3 supporting, AND-composed) — but the sampler only ever emits 2 (`sampler.py:519-534`). So the **AND-gate form is a sampler change, no grammar bump** (D150/D151 class). BUT every AND-gate makes a config **more selective → fewer trades**, which fights the trade-count prefilters AND CPCV's low-trade-count penalty — i.e. the **same failure mode as the warm-up.** "More conditioning = fewer trades" is a fundamental long-options tension and another face of the exhaustion.
- **The only trade-count-NEUTRAL joint conditioning is state-conditioned SELECTION** (adapt strike/DTE to the vol state instead of gating entries out). It is the durable, reusable capability and the natural home for a learned conditioner — but it is **CROSS-SYSTEM**: `SelectorSpec` is a `crucible_contracts` model and Crucible's backtester must interpret a state-conditioned selector. A Path-C-scale lift, low long-options EV.

**Decision:** **hold thread 2; the long-options exhaustion verdict ([[D152]], reinforced by [[D154]]) stands.** Neither residual form is a strong near-term long-options bet (AND-gate likely dominated; state-conditioned selection is a cross-system build with low long-options payoff). The valuable part — state-conditioned selection driven by a learned conditioner — is **deferred to be designed ONCE, around the operator's conditioner interface** (the thread-2 ↔ thread-3 integration seam) rather than now. Thread 3 (the learned model) remains the **operator's parallel workstream** ([[D155]] tail model + `generation-model-levers.md`, untouched here). The standing **M1/M2 monitor** remains the only active long-options watch.

**Division of labor (recorded):** operator → models (thread 3); this agent → enumeration/grammar (held). Integration seam: a learned conditioner registers as a gateable indicator / drives a future state-conditioned selector. D-numbering coordinated (operator took D155; this is D156).

**Alternatives considered:** (a) build the cheap AND-gate probe — rejected by operator (low-EV, fights trade-count/CPCV like the warm-up). (b) invest in state-conditioned selection now — rejected/deferred (cross-system, better designed around the in-flight conditioner). (c) run the offline `enumerate`/`prefilter` viability check — rejected mid-scope: it uses the demo registry + risks the synthetic-cache noise fallback, so it would be ungrounded; the production evidence (D150) already answers it.

**Action:** `docs/proposals/path-a-rich-conditioning.md` → status HELD (scoping findings recorded so thread 2 isn't re-derived); `STATUS.md` top block; memory [[exhaust-long-options-before-v2-spreads]]; this entry. Left untouched: the operator's untracked `docs/proposals/generation-model-levers.md` + all thread-3 work. No production change; nothing sent to Crucible.

---

## D158 — 2026-06-15 — Trend-book CHEAP-IV conditioning lever SCOPED under the [[D157]] reversal: trend R2 regime-pool widening, change surface mapped, staged T1/T2/T3; held relay for the 2-signal contracts gap (D-renumbered from D157 — operator concurrently claimed D157 for the D156 reversal; per the D155/D156 precedent their number stands)

**Spec section:** §3.5 R2 (trend regime-gate coherence — the rule that would widen), §3.6/§13 (hard rule #4 — pool widening is a *loosening* → `OPEN_PROPOSALS.md` + operator approval; hard rule #10 — version bump on ANY `grammar.yaml` byte; hard rule #2 — missing model is a contracts gap), §1.2 (producer/search-space framing), §8.7 (the CPCV bar this does NOT touch). Position: one of the untried in-scope levers un-held by [[D157]] (the operator's D156-hold reversal) — specifically the **trend-book** cheap-IV lever, distinct from D157's mr-focused AND-gate / Q41 cheap-vol / mr-warm-up levers. This is **enum/grammar-lane** work; per D157's coordination note the driver (this session vs the parallel enum/grammar session) is the operator's call. Source: operator answered the `FORGE_momentum_cheap_iv_conditioning.md` assessment with "**scope the trend-side build**", then concurrently broadened that to the full D157 reversal. **DOCS-ONLY; no `grammar.yaml`/`custom_predicates.py`/`indicator_thresholds.py`/`sampler.py` edit, no version bump, no `OPEN_PROPOSALS.md` record, no deploy, no relay sent.**

**Verification that drove the scope (read-only, code + /tmp DB snapshot + gated export):**
- **Forge-side ≠ the handoff's premise.** Of the 5 named cheap-IV signals, only `iv_rank` is gate-usable today (live R1 gate, `regime_range=(10,50)`, in **73/309 (~24%)** v21 components). `iv_minus_rv`/`iv_term_slope` are live but **directional-only** (`regime_range=None`, `indicator_thresholds.py:288-292,307-311`) — regime use deliberately deferred ([[D131]]/[[D135]], the Q34 "R1-sibling gate question"). `iv_vs_index` and `vix_term_slope` **do not exist Forge-side** (grep-clean in `src/`+`config/`); [[D131]] explicitly declined `vix_term_slope` for trend ("validated for vol returns, not trend conditioning"). "Three dormant conditioners" is inaccurate Forge-side.
- **Empirical context confirmed.** `trend_continuation` is the dominant arm (**202/309 = 65%**; ve 88, mr 19); the top CPCV-p25 component is exactly the target shape — `trend_continuation/swing_long/confluence`, **1.219, non-rank**.
- **EV prior is LOW — to be measured, not inferred** ([[D157]] keeps this an honest caveat, not a veto). Crucible's own consolidated handoff rates these "low-EV as long-only gates (edge is short-leg)"; [[D154]]'s best cheap-IV-conditioned long config (`iv_rank × days_to_opex`) is WF 1.43 / **CPCV-p25 0.70**; [[D156]]'s "more conditioning → fewer trades → fights CPCV" headwind applies; honest-era gross max is **1.40 < 1.5, IC-bound** ([[D152]]). The lever exists precisely to test whether the *trend* cell behaves differently.

**Change surface (mapped, line-cited):** R2 = `trend_requires_trend_strength_gate` (`grammar.yaml:604-614`); pool = `_R2_TREND_CONTINUATION_REGIME_INDICATORS` (`custom_predicates.py:246-257`, assembled `search_space.py:337`). Adding cheap-IV ids needs a grammar-coupled pool edit + version bump v21→v22 + archive + GRAMMAR.md#R2 sync; T2 also needs probe-audited `regime_range` for `iv_minus_rv`/`iv_term_slope`; `sampler.py` needs **no change** (it samples whatever the pool holds). **Self-limiting safety property:** all three IV signals are rank-excluded (`requires_symbol`/`rank_per_name_coherent=False`, `search_space.py:141-149`) → the widening can only emit *confluence* (single-name) genomes, exactly like the already-pooled rank-excluded `gamma_flip_distance_pct`; the rank arm is structurally untouched. C1 makes the three `iv_structure` gates mutually exclusive (≤1 cheap-IV gate per config).

**Staged tiers (risk/cost-ordered, each an independent operator gate):** **T1** `iv_rank` on trend (Forge-only, no threshold work, smallest reversal). **T2** `iv_minus_rv`+`iv_term_slope` as gates (Forge-only, reverses [[D131]]/[[D135]]; needs audited `regime_range`). **T3** `iv_vs_index`+`vix_term_slope` (cross-system; blocked on Crucible registry availability + a reversal of the D131 trend-decline — the held relay).

**Decision:** scope recorded as a **measurable increment under [[D157]]**; tiers stay operator-gated — the grammar bump is hard-rule-4/10 gated regardless of the un-hold. The genuinely-untried part (cheap-IV gates on the *trend* book) is the part that costs an operator-gated bump; the part answerable for free (the existing `iv_rank` cohort) is recommended as step 0. Two clean outcomes: no-lift closes the conditioning question on the dominant arm + firms Path-C ([[D152]]); surprise-lift is the first evidence our single-name net-debit book beats index-level long-side pessimism.

**Alternatives considered:** (a) read-only confirm + relay only — the recommended-but-not-chosen option; folded in as step 0 of the sequencing. (b) hold/acknowledge — rejected by operator (wants the empirical close). (c) hand-write the `OPEN_PROPOSALS.md` loosening record now — rejected: it is a machine-managed queue ("DO NOT edit status lines manually — use the approval flow"); the scope names it as a gated step instead.

**Action:** `docs/proposals/momentum-cheap-iv-conditioning.md` (new scope); `PROMPT_CRUCIBLE_MOMENTUM_CHEAP_IV_REGISTRY.md` (new held relay, T3 gate, **not sent**); `STATUS.md` top block; this entry. Reverses nothing yet — D131/D135 stand until a build is approved. No production change; nothing sent to Crucible.

## D157 — 2026-06-15 — D156 hold REVERSED (operator): grammar/enumeration work is NOT held → RUN the genuinely-untried in-scope levers before accepting exhaustion

**Spec section:** §3.5 C3 (joint gates already in-grammar — sampler emits 2 of ≤4), §5 (prefilter/trade-count battery), §8.7 (CPCV trade-count penalty), hard rules 1/4/10 (grammar operator-owned; auto-loosening→OPEN_PROPOSALS; version bumps). Reverses [[D156]]'s HOLD (+ its enum/grammar-lane "held" assertion). Relates [[D152]]/[[D154]] (exhaustion verdict — see the nuance), [[D155]] + `generation-model-levers.md` (thread-3 models), Q41 (the orphaned-vol cheapness gate), `PROMPT_CRUCIBLE_OPTIONS_PRIMARY_STANDALONE.md` (Q1 prioritizes these levers). Source: operator — "d156 should be reversed, we aren't holding on grammar changes; things are not exhausted yet." **DOCS-ONLY; no code/grammar/deploy in this entry.**

**Decision.** D156's HOLD is reversed. Grammar/enumeration work is **un-held** — the genuinely-untried in-scope long-options levers will be **run/measured**, not declined on a low-EV prior. Operator's position: you can't call long-options *exhausted* on levers you never ran. (D156's verdict that the *documented search frontier* is closed is not at issue; the untried in-scope *mechanisms* D154 itself conceded were untried are.)

**What this un-holds (all in-scope, single-leg long premium — no hard-rule-9 / Path-C touch):**
- **Joint / AND-gate conditioning (Thread 2)** — per D156's own finding, §3.5 C3 already permits ≤4 AND-composed signals; the sampler emits only 2 (`sampler.py:519-534`) → a **sampler change, no grammar version bump** (D150/D151 class), operator-gated ritual.
- **Realized-vol *cheapness* gate (Q41)** — wire the orphaned `volatility` family / `vol_regime` so mean_reversion gets a denser "buy-cheap-vol" gate than the sparse `iv_rank` (D150). Sampler/pool edit.
- **mr warm-up** (lift the D150 `iv_rank` 3:1 de-weight, single-name path) — D156 called it "dominated"; operator elects to **measure** it, not infer it.
- **Thread 3 (learned conditioner) + state-conditioned selection** stay the bigger, partly cross-system items (Crucible `SelectorSpec` / conditioned-return labels) — un-held as policy, sequenced after the cheap sampler-level levers.

**Honest caveat (D156's analysis still applies — this is an empirical test, not a refutation):** more conditioning → more selective → fewer trades → fights the trade-count prefilters + the §8.7 CPCV trade-count penalty. Each lever must be **measured** (does the added conditioning lift CPCV-p25 enough to beat the trade-count hit?), and the offline `enumerate`/`prefilter` path is ungrounded (demo-registry/synthetic-cache fallback, D156) → measurement must be production-grounded or shadow. **Grammar/sampler changes remain operator-gated** (hard rules 1/4/10; version bump + ritual for any `grammar.yaml` byte change). **Path C stays HELD** (operator, this session); the standalone-§8.7/1.5 criterion stands.

**Coordination:** D156 asserted "this agent → enumeration/grammar (held)"; reversing the hold reopens that lane — who drives it (this session vs the parallel enum/grammar session) is the operator's call. The just-revised standalone-primary relay Q1 asks Crucible to **prioritize** exactly these levers; its answer sequences which to run first.

**Action:** this entry; `STATUS.md` top block; memory [[exhaust-long-options-before-v2-spreads]]. `docs/proposals/path-a-rich-conditioning.md` (HELD → un-held) — sync **deferred to the enum/grammar lane** (their doc). No production change; nothing sent to Crucible.

---

## D159 — 2026-06-15 — The two cheapest D157 levers SCOPED (this session owns the enum/grammar lane): joint/AND-gate (sampler-only, no bump) + Q41 vol-cheapness gate for mr (needs an R1 rule edit — CORRECTS D157's "no bump"); both change surfaces mapped, sequenced B-first on the trade-count asymmetry

**Spec section:** §3.5 C3 (≤4 signals — the AND-gate headroom), §3.5 R1 (`mean_reversion_requires_iv_rank_gate` — the rule Q41 must edit), §5 (trade-count prefilters — the binding constraint), §8.7 (CPCV trade-count penalty + DSR effective-N deflation), hard rules 1/4/6/10 (operator-owned rule edits; loosening→OPEN_PROPOSALS; determinism re-pin; version bump). Source: operator — "this session keeps the lane — scope AND-gate + Q41 next" (the two cheapest levers un-held by [[D157]]; the 3rd, mr warm-up, is subsumed by Q41). Completes [[D157]]'s deferred sync of `path-a-rich-conditioning.md` (HELD → un-held). **DOCS-ONLY; no sampler/grammar/`indicator_thresholds.py` edit, no version bump, no `OPEN_PROPOSALS` record, no deploy.**

**Lever A — joint/AND-gate (verified change surface):** C3 already permits ≤4 signals (`grammar.yaml:469-481`, validator `predicates.py:65-105`); the sampler emits only 2(-3) — 1 directional + 1 regime (`sampler.py:519-534`) + optional X1/X2 chain (`:550-558`); combiner `confluence/k_of_n/k=1` (`sampler.py:609`). AND-composing a 2nd/3rd regime gate is a **sampler change, NO `grammar.yaml` byte** (pools are registry-derived, `search_space.py:200-210`; D150/D151 class) — confirming [[D157]]. The cost is **hard rule #6 re-pin**: it deliberately changes the enumeration sequence → re-baseline `tests/invariants/test_phase2_invariants.py:39-50` + ~7 sampler golden/cold-start tests + `test_batch_reproducibility` (rule #6 holds post-repin — same triple → same sequence). Build-time decision: stacked `regime_filter` signals vs raising combiner `k` (whichever the Crucible backtester reads as conjunction — verify against the contract). Dead intersections already pruned by `SignalCorrelation` (tier 7, `prefilters/signal_correlation.py`) + `ExpectedTrades` (`prefilters/expected_trades.py`, the binding filter).

**Lever B — Q41 vol-cheapness gate for mr (verified surface + a CORRECTION to D157):** `vol_regime` is live (`indicator_thresholds.py:180-183`, regime classifier 0/1/2, op `<`) but in NO enumeration pool (Q41: orphaned `volatility` family, 7/9 unreachable). **D157 called this a "sampler/pool edit, no bump" — that is only true for the *supplementary* form.** R1 (`custom_predicates.py:816-857`) already accepts any of {`iv_rank`≤50, `gamma_flip_distance_pct` (D107), `hurst` (D150)} — so a `vol_regime`-alone mr config FAILS R1 and never enumerates. Making `vol_regime` a **standalone, denser-than-`iv_rank` mr gate** (the actual intent) requires **adding it to R1** = operator-owned rule edit (hard rule #1) + bump v21→v22 (#10) + loosening → `OPEN_PROPOSALS` (#4) + `GRAMMAR.md#R1` sync + mr pool (`search_space.py:~338-351`) + sampler weighting (`_MR_RANGING_GATES`, `sampler.py:~107-114`). Indicator choice flagged for operator: `vol_regime` (D157-named, densest) vs `rv_rank` (tighter realized-vol-cheapness percentile, but already pinned to trend R2).

**The decisive asymmetry (drives sequencing):** the levers pull OPPOSITE ways on the [[D156]]-binding trade-count constraint. Lever A adds gates → **fewer** trades → fights it (a probe *of* the constraint: does a joint pocket survive the trade-count/DSR hit?). Lever B is a **denser** gate → **more** trades → relieves it (the breadth fix the thin 19-component mr arm needs; fixes the [[D150]] sparseness directly). **⇒ sequence Lever B first** (lower-risk, trade-count-positive, repairs a known defect); Lever A second (higher-variance probe).

**Decision:** both scoped as measurable increments under [[D157]]; **measurement is the deliverable** — each funnel-compare (`crucible funnel --compare`) must report prefilter pass-rate AND survivor CPCV-p25 vs baseline (the explicit test of whether added/denser conditioning beats the trade-count effect). Offline `enumerate`/`prefilter` is demo-ungrounded → measure production/shadow ([[D156]]). The two grammar-bumping levers in flight (Lever B's R1 + the trend R2 of [[D158]]) can batch into one v22 or ship v22/v23 sequentially (the [[D151]] clean-cohort precedent) — operator's call.

**Alternatives considered:** (a) Lever B as a pure sampler/pool edit (no R1 change) — rejected: that only stacks `vol_regime` as a supplementary AND-gate (= Lever A in disguise, adds selectivity), it does NOT give mr the denser standalone gate the lever is for. (b) fold both into `path-a-rich-conditioning.md` — rejected: that doc's "is the probe worth the build" framing contradicts D157's "run it"; cleaner to put the scoped builds in `conditioning-levers.md` and un-hold path-a with a pointer. (c) scope the mr warm-up separately — rejected: subsumed by Lever B (a denser gate is the better form).

**Action:** `docs/proposals/conditioning-levers.md` (new scope, both levers); `docs/proposals/path-a-rich-conditioning.md` banner un-held → points here; `STATUS.md` top block; memory [[exhaust-long-options-before-v2-spreads]]; this entry. No production change; nothing sent to Crucible.

---

## D160 — 2026-06-15 — Crucible's registry-availability answer FOLDED into the D158 trend lever: relay SENT+ANSWERED; T3 collapses to `iv_vs_index` only (was a stale export, now published); `vix_term_slope` conceded out (D131 upheld); T2 bands delivered (raw → percentile-wrap, converges with D159/Q41)

**Spec section:** §13 (registry snapshot / `registry_loaded_from_export`), hard rule #2 (contracts gap → surface, don't work around — the iv_vs_index path), §3.5 R2 (the trend pool the unblocked signal joins), [[D131]] (upheld), [[D158]] (the trend lever this updates), [[D159]] (the Q41 percentile-density convergence). Source: operator relayed the held `PROMPT_CRUCIBLE_MOMENTUM_CHEAP_IV_REGISTRY.md`; Crucible answered in `../Crucible/docs/handoffs/FORGE_momentum_cheap_iv_registry_response.md`; operator — "wrap it in and continue." **DOCS-ONLY; no registry adoption, no snapshot pull, no code/grammar/deploy.**

**What Crucible answered (the relay's three asks):**
- **Q1 — `iv_vs_index` was genuinely absent, now published.** My grep was correct: it was a **stale export**, not a missing indicator. Crucible's registry publisher (`crucible-registry-publisher.service`) is `Type=oneshot`-at-startup and hadn't restarted since 2026-06-10, so the 2026-06-15 dispersion-lite ship was registered in-process but never *published* (their earlier "registry now 58" conflated in-process registration with snapshot publication — they own the overclaim). Re-published: **`registry_snapshot_2026-06-15T180258Z.json`** (58 ids). Metadata: `family=iv_structure`, `requires_symbol=True`, `rank_per_name_coherent=False` → **rank-excluded → confluence-only**, range [0,100] percentile, **dir LOW** (<25–30 = cheap vs market), single-names-only (inert on the index).
- **Q2 — `vix_term_slope`: Crucible CONCEDES [[D131]].** It exists + has been in the snapshot since 2026-06-10 (if our tables show only `vix_level`, we're on a pre-06-10 load), but `market_wide_by_design=True` (a *when*-gate that can't select names) + no trend-conditioning evidence (their basis is Johnson JFQA 2017 = *vol returns*, D131's scope). **Keep D131; drop `vix_term_slope` from trend T3.** → **T3 collapses to a single signal, `iv_vs_index`.**
- **Q3 — `iv_minus_rv`/`iv_term_slope` regime bands delivered** (`probe_iv_regime_bands.py`, 20 Tier-2 names, full history; pooled + per-name p10/25/50/75/90 + selectivity→threshold map). **Caveat: raw-decimal** → one global band fires at name-dependent rates (2–4× spread, scaling with name vol). Two paths: per-name bands (immediate, from the JSON) or a **percentile-wrap** `iv_minus_rv_rank`/`iv_term_slope_rank` (cheap; reuses `iv_rank`'s engine). `iv_term_slope` foot-gun: pair with `days_to_earnings`.

**Net effect on [[D158]]:** T3 narrows from two signals to **`iv_vs_index` only, now UNBLOCKED**; its remaining gate is Forge-side — adopt the new snapshot (registry change → likely a ritual restart per [[D104]]; registry-load discipline [[registry-load-log-precedes-validation]]) + wire an `iv_vs_index` threshold spec + add to R2 → then a T1-class confluence-only build. The relay flips held→**sent+answered**. T2's threshold audit is now data-backed (Crucible's bands) rather than "to be probed."

**Cross-lever convergence (worth noting):** Crucible's "percentile-wrap raw IV signals for *gate* use" (Q3) is the **same principle** as the [[D159]]/Q41 finding (percentile gates `iv_rank`/`rv_rank` fire uniformly/densely; raw or sparse ones don't survive the prefilter). Both the trend lever's T2 ([[D158]]) and the mr cheap-vol lever ([[D159]]) point at **percentile-wrapped vol/IV gates** as the right regime-gate shape — a possible consolidation if we ask Crucible for the `*_rank` wraps once.

**Operational trap recorded (memory):** Crucible's registry publisher is oneshot-at-startup, so a Crucible-"shipped" indicator is **not in the snapshot Forge enumerates over until a republish/restart** — re-pull and confirm the id before enumerating. (Crucible has a pending process fix: publish on registry change.) New memory [[crucible-registry-publisher-oneshot]]; relates to [[gated-export-stale-cohort]].

**Action:** `PROMPT_CRUCIBLE_MOMENTUM_CHEAP_IV_REGISTRY.md` → SENT+ANSWERED banner; `docs/proposals/momentum-cheap-iv-conditioning.md` (§0/§1/§4 T2+T3/§6/§7 updated); `STATUS.md` top block; new memory [[crucible-registry-publisher-oneshot]] + index; this entry. No production change; nothing pulled or deployed.

---

## D161 — 2026-06-15 — Two Crucible EMPIRICAL reads folded in: trend cheap-IV REFUTED (no lift, mild inversion) → D158 T1/T2 SHELVED; mr wants cheap REALIZED vol (`rv_rank`, rank-coherent, a quality-knob not a promotion unlock) → D159 Lever B refined to `rv_rank`; AND-gate de-prioritized; the long-book residual lever is portfolio regime-placement

**Spec section:** §1.2 (producer/measurement framing), §8.7 (CPCV-p25 tail = the binding wall these reads do NOT move), §3.5 R1/R2 (the gate rules the levers would touch), hard rule #6 (measurement is the deliverable). Source: operator relayed two Crucible empirical handoffs (`../Crucible/docs/handoffs/FORGE_momentum_cheap_iv_empirical_read.md` + `FORGE_mr_realized_vol_conditioner.md`) — "make sure we are relaying everything right so we have all the right details." Causal trade-attribution on the live ledger (era-C, §13.16 causal entry values), not literature. **DOCS-ONLY.**

**Read 1 — trend cheap-IV does NOT lift (mild inversion):** causal attribution of era-C `trend_continuation` (163 comps / **126,133 trades**, 100% coverage) — `iv_rank` cheap−rich **−0.032** (edge in RICH IV), `iv_minus_rv` −0.020, `rv_rank` +0.013 (noise); every quintile ~0.08–0.11 (IC-bound). Cause: the directional net-debit book is **move**-dominated, not delta-hedged, so high-vol/trending regimes *help* it — Bakshi-Kapadia (the cheap-IV ask's basis) governs the pure-vol leg this book doesn't isolate. **⇒ [[D158]] T1 (`iv_rank`) + T2 (`iv_minus_rv`/`iv_term_slope`) on trend are SHELVED** — the "no-lift → firms Path-C" outcome the scope's §5 anticipated has arrived (Crucible's attribution is stronger than the funnel-compare we'd have run). **T3 `iv_vs_index` survives separately** (single-name SELECTION lens, not tested by entry-attribution). If one ever probes an IV gate on the directional trend book, the long-favorable direction is **rich IV** (converges with `volatility_event`), a quality tilt at best, still IC-bound.

**Read 2 — mr wants cheap REALIZED vol, `rv_rank`:** causal attribution of era-C `mean_reversion` (49 comps / 9,930 trades) — `rv_rank` cheap−rich **+0.095** (clean monotone ~2.5× per-trade Sharpe gradient); `iv_rank` weak (+0.041); `iv_minus_rv` inverted (raw-decimal artifact). **⇒ [[D159]] Lever B refined: the indicator is `rv_rank` (cheap *realized* vol), not `vol_regime` or cheap-IV** — resolving the open vol_regime-vs-rv_rank decision. Two corrections: **(i)** `rv_rank` is **rank-coherent** (`rank_per_name_coherent=True`, bar-only) → works on BOTH mr rank genomes AND confluence, **resolving the prior "pinned to trend R2" worry** (it's general-purpose, and a structural edge over the rank-EXCLUDED cheap-IV gates). **(ii)** Honest scope: every vol-quintile is net-profitable → `rv_rank`-gating adds **no standalone PnL**, it concentrates mr into ~2.5× higher-Sharpe entries = a per-trade-quality / cap-efficiency lift to the book **CENTER**, **not** the CPCV-p25 **tail** (the binding wall) — **a quality knob, not a promotion unlock.** The [[D159]] R1-edit requirement holds (`rv_rank` not in R1's accepted set). **Gate before build:** the **hurst-overlap test** (does `rv_rank` add beyond v21's existing hurst mr gate, [[D150]]? — Crucible offered) — drafted held relay `PROMPT_CRUCIBLE_MR_RV_RANK_HURST_OVERLAP.md`; build only if it adds.

**The symmetric pair (strategic):** MR ↔ cheap vol, momentum ↔ rich vol — opposite-regime hypotheses → natural portfolio **complements**, not co-combiners. Answers the operator's session-opening combine question: momentum + `volatility_event` = aligned (same high-vol regime, combine OK); momentum + mr = opposite regimes (complement at the **portfolio** level, not as co-gates). **⇒ Lever A (AND-gate) DE-PRIORITIZED** — the long-book residual lever is **portfolio regime-placement** (which hypothesis is on in which regime), not more per-name entry gates; stacking gates is the wrong direction.

**Net plan change:** my prior "v22 = Q41 + trend-T1 R2" recommendation ([[D159]]/STATUS) is **superseded** — trend-T1 is refuted/shelved. The only surviving enumeration lever is **`rv_rank`-on-mr**, gated on the hurst-overlap test, and it's a quality knob (won't move the promotion wall). AND-gate de-prioritized; `iv_vs_index` (D158-T3) stays a separate selection question (needs snapshot adoption + threshold spec). **Both my prior open build-questions are now resolved:** vol_regime-vs-rv_rank → `rv_rank`; trend-T2 per-name-bands-vs-percentile-wrap → moot (trend shelved). The strategic frontier moves to **portfolio regime-placement** (a Crucible/QuantIQ portfolio-architecture thread), consistent with the [[D152]] exhaustion verdict and the [[pts-quantiq-equity-arm]] overlay framing.

**Action:** result callouts on `docs/proposals/momentum-cheap-iv-conditioning.md` (T1/T2 shelved) + `docs/proposals/conditioning-levers.md` (Lever B → `rv_rank`, Lever A de-prioritized); new held relay `PROMPT_CRUCIBLE_MR_RV_RANK_HURST_OVERLAP.md` (**not sent**); `STATUS.md` top block; memory [[exhaust-long-options-before-v2-spreads]]; this entry. No production change; nothing pulled, built, or deployed.

---

## D162 — 2026-06-15 — Operator-requested outbound relay DRAFTED (held): ask Crucible for a concrete momentum-book recommendation (post cheap-IV refutation) + a sweep of any new Crucible data/design Forge should fold in

**Spec section:** §1.2 (producer ↔ Crucible coordination), hard rules #3/#6 (direction/inputs request — no §8.7 threshold change). Source: operator — "add the request on recommendation for momentum and any new data or design on the Crucible side that should be included." Follows [[D161]] (cheap-IV refuted; Crucible *gestured* at "rich-IV tilt / portfolio regime-placement" but left no actionable producer move). **DOCS-ONLY; relay HELD, not sent.**

**What it asks** (`PROMPT_CRUCIBLE_MOMENTUM_RECOMMENDATION_AND_INPUTS.md`): **(1) Momentum recommendation** — is there ANY in-scope Forge *enumeration* move for the trend book (the rich-IV/high-vol quality tilt — and which signal/threshold — or a non-IV conditioner), or is its enumeration frontier closed → only **portfolio regime-placement**; and if placement, what must Forge **emit** to feed it (regime-tagged candidates / a placement label / a `SelectorSpec` hook, naming the contract field). **(2) New data/design** — worst-quartile regime attribution, conditioned-return-by-regime, the faithful re-backtests; plus shipped/planned design (the percentile-wrap `*_rank` wraps, `SelectorSpec`/state-conditioned selection, regime plumbing, any indicator added since `registry_snapshot_2026-06-15T180258Z.json`) — **explicitly asking Crucible to flag anything shipped-but-unpublished** (the [[crucible-registry-publisher-oneshot]] gotcha, so we're not a snapshot behind a third time).

**Why:** the empirical reads ([[D161]]) closed the cheap-IV question but left "what next for momentum" as a gesture; this operationalizes the recommendation and pulls any missing Crucible inputs before Forge scopes the next increment. Pairs with the held `PROMPT_CRUCIBLE_MR_RV_RANK_HURST_OVERLAP.md` (the mr-side gate) — two held asks now await operator relay.

**Action:** new held relay `PROMPT_CRUCIBLE_MOMENTUM_RECOMMENDATION_AND_INPUTS.md` (**not sent**); `STATUS.md` top block; this entry. No production change; nothing sent to Crucible.

---

## D163 — 2026-06-15 — EXIT-PARAMETER sweeping SCOPED as the CPCV-p25 TAIL lever (operator Q: "regime filters or exit criteria?"): the answer is exits — entry gates are center-knobs (D161), exit-shaping is the unswept, trade-count-NEUTRAL, tail-aligned axis; sampler-only (no bump), probe-gated; held relay drafted

**Spec section:** §8.7 / CPCV-p25 (the worst-quartile binding wall, [[D146]]), §3.5 E1–E3 + S5 (the exit rules the sweep stays inside), hard rule #6 (sampler-only enumeration policy, golden-sequence re-pin), hard rule #3 (no §8.7-bar change). Source: operator — "what would help the CPCV-p25 tail on the Forge side? Should we have hypotheses with different regime filters or maybe different exit criteria? Can we probe and analyze to find better options?" **DOCS-ONLY; relay HELD, not sent.**

**The answer to the operator's fork — the two ideas are NOT symmetric.** *Regime filters* = entry-side = the [[D158]]/[[D159]]/[[D161]] program already run, and [[D161]] **empirically** showed (live-ledger causal attribution) entry conditioning is a **center** knob (`rv_rank` +0.095 per-trade Sharpe but *"NOT the CPCV-p25 tail"*), and each gate cuts trade count → fights the [[D156]] binding constraint. *Exit criteria* = the genuinely-**unswept**, tail-shaped lever.

**The Forge-side finding (code-verified):** the sampler enumerates *which* exits compose (`_build_exits`, `sampler.py:943-983`: E1 mandatory + S5 required + Bernoulli optionals) but leaves them **parametrically inert** — `_exit_params` (`sampler.py:1179-1183`) returns **`{}` for every exit except `trailing_atr`** (forced by E3). So stop tightness / profit-target / time-stop horizon / theta-cliff DTE — the knobs that reshape the trade-return distribution — run at Crucible's default across the whole population. The **sizer** already sweeps its analogue (D074: `vol_target_annual`, `kelly_fraction`) — exit-param sweeping is the precedent-following extension to the exit half of the risk-shape family. Logged as Q42 (Q41's tail-shaped sibling).

**Why exits move the tail when entry gates don't:** CPCV-p25 = worst-quartile OOS robustness → lifted by truncating the **left tail** of trade returns (a long option's worst outcome is theta-bleed-to-zero; an earlier time/premium/theta-cliff stop caps it). Decisively, exit-shaping is **trade-count-NEUTRAL** (same entries, earlier exits on losers) → **sidesteps the [[D156]] headwind** that makes entry gates center-knobs. Corroborated: the one tail-positive lever on file is Crucible's **M2 vol-target (+0.07 to p25**, [[D152]]) — same risk-shape family. S5 already encodes hypothesis-specificity (trend forbids `hard_profit_target`, wants the convex right tail; mr's natural knobs are `target_exit`/`zscore_reversion_exit`), so the sweep stays inside the permitted set per hypothesis.

**Honest EV (bounded, same calibration as [[D161]]):** the structural sign claim ([[D152]]/[[D154]]) still binds — no exit policy out-trades a regime where the long leg pays the VRP at entry. The worst-quartile *regime* fix (bear ~2.39× / ranging ~1.33×) is sell-side = Path C. So the realistic prize is the thin **1.40→1.5 pocket via dispersion-tightening**, a fraction of M2's +0.07 — a **robustness/hygiene gain, not a promotion unlock.** What earns it a scope: of the in-scope levers it is the only one (a) unswept, (b) tail-aligned, (c) trade-count-neutral.

**Change surface:** sampler-only — extend `_exit_params` with audited, S5-aware per-exit ranges; **no `grammar.yaml` byte change** (no exit ID added, no E1–E3/S5 edit), so **no version bump**; re-pins the golden sampler/determinism sequence deliberately (hard rule #6 preserved). **Decisive open risk:** exit params are emitted by Forge but executed by Crucible's backtester — the D068 (`pairs` template) / D138 (`option_momentum.min_months`) precedent shows some param dicts are read per-config and some use a runtime default; a swept param Crucible ignores is inert.

**Probe-first (the operator's "analyze"):** held relay `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md` (**not sent**) asks Crucible — same causal-attribution machinery as [[D161]]/[[D159]] — to (1) decompose the CPCV-p25 worst-fold trades by exit reason / hold / give-back: truncatable left-tail give-back (→ headroom; build) vs. adverse-regime structural bleed (→ no help; firms [[D152]]); and (2) enumerate which exit IDs honor per-config `ExitSpec.params`. Build only if (1) shows headroom and (2) confirms the params bite — discipline mirrors [[D158]] step-0 and the [[D161]] hurst-overlap gate.

**Action:** new proposal `docs/proposals/exit-tail-shaping.md`; new held relay `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md` (**not sent**); Q42 in `OPEN_QUESTIONS.md`; `STATUS.md` top block; this entry. No production change; nothing pulled, built, or deployed; nothing sent to Crucible.

---

## D164 — 2026-06-15 — Crucible answered the mr `rv_rank`×hurst gate (BUILD justified — `rv_rank` independent of + DOMINATES hurst) AND its L1/L2/L3 design doc REFUTES the exit-tail thesis's prior art (L2 book-level/exit-side de-gross dominated by uniform vol-target) → Lever B build operator-gated-only; D163 EV downgraded, probe now confirmatory

**Spec section:** §3.5 R1 (the mr regime-gate rule Lever B edits), §8.7 / CPCV-p25 (the tail wall both threads sit under), hard rule #6 (center-vs-tail honesty; "selection never moves maxDD"), #1/#10/#4 (the operator gates on the Lever B build). Source: operator relayed `../Crucible/docs/handoffs/FORGE_mr_rv_hurst_overlap_response.md`; its cited dependency `../Crucible/docs/design_regime_conditioned_construction.md` (the L1/L2/L3 architecture) read as context. **DOCS-ONLY** — folds two answers, builds nothing.

**Answer 1 — the mr `rv_rank`×hurst gate ([[D159]]/[[D161]] Lever B): CLEARED, build justified, stronger than asked.** Era-C mr (49 comps / 9,930 trades, 94.9% joint coverage): **(i) independent** — `Spearman(hurst, rv_rank) ≈ −0.036`; hurst-pass rate identical (16.5%) across `rv_rank` quintiles → not a re-expression of hurst; **(ii) gradient survives the hurst control** — cheap−rich per-trade Sharpe **+0.142** inside the hurst-passing subset vs +0.114 full-sleeve (`survives_ratio 1.25`); **(iii) `rv_rank` DOMINATES `hurst`** — strong `rv_rank` Sharpe gradient inside every hurst stratum (+0.094/+0.157/+0.096); `hurst` carries none inside any `rv_rank` stratum (−0.036/−0.035/−0.034). **⇒ Build the v22 `rv_rank`-LOW MR conditioner — the R1 edit is justified.** Build-design refinements: **(a) prefer/replace, don't stack** (hurst earns ~zero marginal mr quality once `rv_rank` is in → minimal form = add `rv_rank` to R1's accepted set; sampler-bias toward it is the go-forward economy call); **(b) on confluence** (mr's edge is there; rank caps at cpcv 0.729, "refuted on its own terms"). Two honest wrinkles, neither changes the verdict: the H<0.45 thin-slice inversion is small-sample noise (read off bias-robust terciles); causal 100-bar hurst is upward-biased (median 0.59 → literal H<0.5 passes only 17%), a second structural reason `rv_rank` (name-relative percentile) is the better-behaved conditioner. The Lever B build now has **no empirical gate left — operator-gated only** (R1 edit #1, v22 bump #10, loosening → `OPEN_PROPOSALS` #4). **Honest scope UNCHANGED: center/cap-efficiency, NOT the CPCV-p25 tail** (a quality knob, not a promotion unlock).

**Answer 2 — the L1/L2/L3 design doc REFUTES the [[D163]] exit-tail thesis's closest prior art.** The hurst-answer's cited dependency (`design_regime_conditioned_construction.md`) defines a 3-layer architecture: **L1** entry conditioners (Forge — the `rv_rank` mr gate above; *"may retain center/quality value"*), **L2** book-level *selective* regime de-gross (Crucible), **L3** portfolio regime-coverage/power-floor gates. **L2 is the exit-tail thesis's prior art** — §4 property 2 / §7.5 give it an *exit-side held-position trim* (partial-liquidation on adverse-regime transition) to reach hold-through damage. **§6 cap-interaction backtest REFUTED L2:** on the era-C 342-comp book, uniform vol-target **DOMINATES** selective de-gross on BOTH maxDD (−23.6% vs −40.1%) AND Sharpe (1.75 vs 1.42). **Mechanism (load-bearing for [[D163]]):** *"the book's drawdowns are NOT regime-confined — theta bleed in calm + vol spikes — which continuous book-vol-targeting catches and a targeted lever misses."* Theta-bleed-in-calm is the **exact** left-tail the exit-param sweep targets → the existing uniform vol-target already harvests it. Plus the settled framing this re-confirms: *"cap bounds the tail, selection never moves maxDD"*; the CPCV-p25 wall is **edge magnitude — a Forge generation problem** (World-A), not a regime/construction/exit gap.

**Net effect on [[D163]]:** EV downgraded from "calibrated-low" to **"likely dominated by the existing uniform vol-target."** NOT a full refutation — the exit-param sweep is *per-trade/per-config* timing (finer than L2's *sleeve-level, regime-conditioned* de-gross) and runs *inside* the vol-target; the narrowed open question is whether per-trade exit-timing adds CPCV-p25 *beyond* uniform vol-target. The exit-attribution probe (already SENT) still answers it but is now **confirmatory with an adverse prior** — expect "vol-target already caught it." If so → **fold D163 closed**, the magnitude wall confirmed on a third independent axis (entry [[D161]] · construction/exit [[D164]] · the pending probe). **Do not build the exit sweep ahead of the probe; the prior is now adverse.**

**Strategic synthesis (both answers point one way):** neither entry **selection** ([[D161]]) nor book **construction**/exit ([[D164]] L2) moves the CPCV-p25 tail — the wall is **edge magnitude**, a Forge **generation** problem (World-A). The only justified near-term *build* is Lever B (`rv_rank` mr), and it's an explicit **center/quality** knob, not a tail move. The tail lever that *works* (uniform vol-target) already exists Crucible-side. This converges the long-options exhaustion verdict ([[D152]]) from a third direction.

**Also landed, NOT yet folded (operator to relay):** the momentum relay's answer exists — `../Crucible/docs/handoffs/FORGE_momentum_recommendation_and_inputs.md` ([[D162]]) — but the operator relayed only the hurst response; flagged for the next fold, not processed here.

**Action:** relay `PROMPT_CRUCIBLE_MR_RV_RANK_HURST_OVERLAP.md` → **ANSWERED**; gate-cleared banner on `conditioning-levers.md` (Lever B); EV-downgrade banner on `exit-tail-shaping.md` ([[D163]]); `STATUS.md` top block; this entry. No production change; nothing built, bumped, or deployed.

---

## D165 — 2026-06-15 — Crucible answered the exit-tail attribution probe ([[D163]]): thesis CONFIRMED NON-TAIL — ~60% of the worst-quartile tail is structurally irreducible; the lever is real (params honored 7/8, trade-count-neutral) but a HYGIENE knob, not a wall-mover → D163 closed-as-wall-mover, kept as a cheap option to batch onto the Lever B v22 build

**Spec section:** §8.7 / CPCV-p25 (the worst-quartile wall the probe attributes), §3.5 E1–E3/S5 (the exit vocabulary the sweep would touch), hard rule #6 (center-vs-tail honesty; the magnitude wall). Source: operator relayed Crucible's answer (`../Crucible/docs/handoffs/FORGE_exit_tail_attribution_response.md`; probe `scripts/probe_exit_tail_attribution.py` → `probe_results/exit_tail_attribution.json`, commit 483386f). **DOCS-ONLY.** Closes the third and last of the three relays ([[D161]] mr-gate, [[D162]] momentum, [[D163]] exit) — the exit one.

**Ask 2 (param honoring) — NO inertness hazard.** The [[D163]] "decisive open risk" (D068/D138: would Crucible read per-config exit params?) is resolved favorably: Crucible's `build_exit()` factory reads `ExitSpec.params` via `params.get(key,default)` for **7 of 8** swept exits — once Forge emits them, Crucible honors them. **The inertness is purely Forge sampler-side** (`_exit_params` returns `{}`), exactly the gap [[D163]] identified. **One exception:** `hard_profit_target` is a no-op `DeferredExit` (`registry.py:219`; `should_exit` always None; §6.5.3-forbidden) → drop it; `target_exit` is the real profit-target lever. **And one addition Crucible flagged:** `event_passed_exit.n_bars_after_entry` is the **#1 wall-setter loser exit (55%)**, honored but off [[D163]]'s list → add it. Corrected swept set: `premium_stop_loss.stop_pct`, `atr_underlying_stop_loss.{n_atr,atr_period}`, `time_stop.n_bars`, `theta_cliff_exit.dte_threshold`, `target_exit.{target_pct|target_atr_multiplier}`, `convergence_exit.target_zscore`, `zscore_reversion_exit.{exit_zscore,lookback}`, `event_passed_exit.n_bars_after_entry`.

**Ask 1 (worst-fold attribution) — the tail is ~60% structurally irreducible; the give-back is OFF the wall.** On the 6 lowest-p25 long-options wall-setters (248 crater losers; MFE re-derived via the stored 45-path sharpes since MFE isn't persisted): **(i)** 56% of losers **never peaked positive** (58% of loss), median loser MFE-peak **= 0.0** — underwater from the first mark; ~60% structural, no exit recovers it. **(ii)** Losers are **early time-cuts** (event_passed 55% / time_stop 32% / theta_cliff 12%, low hold-fraction), **NOT slow theta-decay** — this **corrects [[D163]]'s §2 mechanism premise** ("theta-bleed-to-zero truncatable by an earlier stop"): the structural loss is *underwater-from-entry then time-cut*, an **entry/edge** problem, not an exit-timing one. **(iii)** Clean give-back (peaked ≥25%) is only **14% of loss** and lives in **higher-p25 MR (0.29–0.36) that doesn't set the wall** (MR losers round-trip — the MR-edge-is-entry finding); the wall-setters (trend/vol, p25 0.029–0.097) are **59–76% never-peaked, 1–8% give-back.** **(iv) Convexity tension:** oracle peak-exit recovers 1.31× the loss (perfect-foresight ceiling, convex round-trips) but crater **winners give back only 23% (they run)** → a target tight enough to catch loser round-trips also **caps the winners carrying the book.** And wall-setter genomes don't compose `premium_stop`/`target_exit`/`trailing_atr` at all — their only live knobs are `time_stop`/`theta_cliff`/`event_passed`, which the probe says can't reach the structural ~60%.

**Disposition — [[D163]] closed as a wall-mover, kept as a cheap hygiene option.** This is decisively the (b) branch [[D163]]/§5 anticipated ("structural bleed → no help; firms [[D152]]"). The lever is **viable hygiene** (Crucible: "build it if cheap" — params honored, trade-count-neutral, tightens dispersion on the off-wall MR) but **CONFIRMED non-tail**. **Recommendation: do NOT spend a standalone deploy** on a confirmed-non-tail lever; if built at all, **batch the corrected `_exit_params` sweep onto the Lever B v22 deploy** (both re-pin the golden sequence — near-free) or revisit as pool-hygiene later. No build this turn.

**Strategic close (all three axes now agree).** Neither entry **selection** ([[D161]]: center not tail), book **construction**/exit-side de-gross ([[D164]]: L2 dominated by uniform vol-target), nor per-trade **exit-timing** ([[D165]]: ~60% structural) moves the CPCV-p25 worst-quartile tail. The wall is **edge magnitude — a Forge GENERATION problem** (World-A), confirmed on three independent axes. The one justified near-term *build* is Lever B (`rv_rank` mr, [[D164]]), an explicit center/quality knob. The worst-quartile *regime* magnitude fix stays **sell-side / Path C**. This converges the [[D152]] exhaustion verdict from the exit direction — the long-options conditioning surface (entry + construction + exit) is now empirically swept and confirmed magnitude-bound.

**Still pending relay:** the momentum-recommendation answer (`../Crucible/docs/handoffs/FORGE_momentum_recommendation_and_inputs.md`, [[D162]]) has landed but is not yet relayed → next fold.

**Action:** relay `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md` → **ANSWERED**; probe-result banner + Status flip on `exit-tail-shaping.md` ([[D163]]); Q42 resolution note (`OPEN_QUESTIONS.md`); `STATUS.md` top block; this entry. No production change; nothing built, bumped, or deployed.

---

## D166 — 2026-06-15 — Crucible answered the momentum recommendation+inputs relay ([[D162]]): trend enumeration frontier ~CLOSED (high-vol/trending tilt at most, not worth a bump alone); regime-placement has NO Forge emit role (vol-target dominates it); registry current + publisher gotcha FIXED; `*_rank` wraps DECLINED → the last of the 3 relays; no in-scope momentum build

**Spec section:** §1.2 (producer↔Crucible coordination), §3.5 R2 (the trend regime-gate rule a tilt would touch), hard rules #3/#6 (direction+inputs request, no §8.7 change). Source: operator relayed `../Crucible/docs/handoffs/FORGE_momentum_recommendation_and_inputs.md`. **DOCS-ONLY.** Closes the third relay ([[D161]] mr-gate → [[D164]], [[D163]] exit → [[D165]], [[D162]] momentum → this).

**Q1 — momentum/trend enumeration frontier ~closed.** Per-6-regime attribution of the trend sleeve (126k trades, `trend_continuation_regime_attribution.json`), per-trade Sharpe by regime-at-entry: **trending +0.126 · high_vol +0.103 · low_vol +0.089 · bull +0.067 · ranging +0.011 · bear +0.008.** The edge concentrates in trending/high_vol; flat in bear/ranging. The only in-scope move is a **high-vol/trending regime quality tilt** (`momentum_252` + `vol_regime` HIGH / `market_state` trending, swing_mid/long). **But it's IC-bound (~0.07–0.13 everywhere) — a tilt, not a lift, "probably not worth a grammar bump on its own."** ⇒ recorded as a **declined low-EV option** (batchable onto a future v22 if ever wanted; not recommended standalone). The dominant arm's enumeration frontier is closed.

**Q2 — regime-placement: NO Forge emit role (the prior "residual lever" refuted).** Crucible tempered its own earlier framing: it built + tested the book-level selective regime de-gross (L2, [[D164]]) and **uniform vol-target dominates it** (Sharpe 1.75/maxDD −23.6% vs 1.42/−40.1%). ⇒ **do NOT scope regime-tagged candidates, a per-candidate regime/placement label, or a `SelectorSpec` regime hook** — building a contract surface for a lever that loses to `vol_target` is effort against a refuted hypothesis. Regime-aware sizing, if QuantIQ ever wants it, is a Crucible construction question and the book-vol-keyed vol-target is the better primitive — still no Forge emit.

**Q3 — new priors (per-(hypothesis,6-regime) Sharpe).** `trend_continuation` peaks trending +0.126; `volatility_event` bear **−0.105** / high_vol +0.138 / low_vol +0.160; `mean_reversion` bear **−0.27** / ranging +0.12 / low_vol +0.14 / high_vol +0.12 / trending 0.00. Three priors: each sleeve is regime-specialized (none has 6-regime-bear edge → bear is a `tail_leg` regime, not a sleeve regime); the **VIX-tercile stress sign ≠ the 6-regime-bear sign** (vol_event is +0.65 in a VIX spike but −0.105 in a bear grind — match the taxonomy to the use); worst-quartile bear 2.39×/ranging 1.33× is **magnitude, not a regime gap**. **Corroborates Lever B:** MR's −0.27 in bear vs positive in calm/ranging/low_vol means gating MR to cheap *realized* vol (`rv_rank` LOW = calm) concentrates it where it has edge — a center/quality alignment, consistent with the [[D164]] honest scope.

**Q4 — design/indicators.** `rv_rank`/`vol_regime` MR gate shipped + rank-coherent (hurst-overlap resolved, [[D164]]); momentum-side `rv_rank` is NOT the gate (momentum wants high-vol, the mirror). `iv_minus_rv_rank`/`iv_term_slope_rank` percentile-wraps **offered-not-built — momentum use-case gone → DECLINE** (leave unbuilt; flag only if another hypothesis needs a uniform-selectivity gate). The regime de-grosser is **Crucible engine-internal, NOT a Forge-enumerable indicator** — don't plan around it. Enumerable regime gates stay the published `vol_regime`/`market_state` (in the snapshot). **Registry is current and the publisher is now 6-hourly (the [[crucible-registry-publisher-oneshot]] startup-only gotcha is FIXED) — nothing shipped-but-unpublished.** ⇒ the "are we a snapshot behind" worry that motivated this relay is resolved.

**Net — all three relays answered; the picture is settled.** Build queue: **Lever B (`rv_rank` MR) is the one justified increment** ([[D164]], operator-gated). Everything else from this relay is declined/closed: momentum tilt (IC-bound, not worth a standalone bump), regime-placement emit (no Forge role), `*_rank` wraps (no use-case). The long book is IC-bound ([[D152]]) and these reads firm it from the momentum direction; the residual frontier is **edge magnitude = a Forge generation problem** (World-A), the consistent verdict across [[D161]]/[[D164]]/[[D165]]/this.

**Action:** relay `PROMPT_CRUCIBLE_MOMENTUM_RECOMMENDATION_AND_INPUTS.md` → **ANSWERED**; answer banner on `momentum-cheap-iv-conditioning.md`; `STATUS.md` top block; this entry. No production change; nothing built or deployed. **Next: scope the Lever B v22 build (operator-requested).**

---

## D167 — 2026-06-15 — Lever B v22 build SCOPED (operator-requested): add `rv_rank` (cheap realized vol) as a 4th `mean_reversion` R1 gate — ADD-not-replace + sampler-bias-to-prefer; operator-directed loosening (D107/D150 class, NOT OPEN_PROPOSALS); v22 = Lever B alone (clean funnel); TDD/file surface mapped; awaiting operator grammar-bump approval

**Spec section:** §3.5 R1 (the operator-owned rule this widens, hard rule #1), §3.6 (enumeration determinism, hard rule #6), hard rule #10 (version bump + archive), hard rule #3 (no §8.7-bar change). Source: operator — "fold the momentum answer first then let's scope it out." The build of the [[D164]]-cleared Lever B. **DOCS-ONLY; no code, no bump — operator-approval-pending.** Full plan: `docs/proposals/lever-b-rv-rank-v22-build.md`.

**The change:** add `rv_rank` (realized-vol percentile, op `<` = cheap; `indicator_thresholds.py:271-275`) as a **fourth accepted `mean_reversion` R1 regime gate** alongside `iv_rank`/`gamma_flip`/`hurst`. **Exact precedent: [[D107]]** (gamma→R1, v11) and **[[D150]]** (hurst→R1, v20) — same change class, same file surface (`custom_predicates.py` R1 constant+branch, `search_space.py` mr pool, `sampler.py` ranging-gate bias, `grammar.yaml` v21→v22 + archive, `GRAMMAR.md#R1` sync).

**Four build decisions, all with a recommended default (operator to confirm):**
1. **ADD, don't replace** — R1 is an OR (one gate per config), so removing `hurst` would orphan existing configs for no gain (Crucible's "hurst earns no marginal quality" is about *stacking*, which R1-as-OR never does). Express "prefer `rv_rank`" via the **sampler bias** (`_MR_RANGING_GATES += rv_rank`, inheriting the D150 3.0 weight), not the grammar. **Recommended.**
2. **Direction is free** — `rv_rank`'s spec op is already `<` (cheap), = mr's calm-vol edge, so (unlike D150's hurst) **no per-hypothesis op edit** — just a cross-hypothesis op-verify test (rv_rank is also in the *trend* R2 pool).
3. **LET it rank** — `rv_rank` is rank-coherent (Crucible-confirmed) + mr rank is enabled ([[D151]]), so `rv_rank`-gated mr can rank; mr's edge is **confluence** (rank caps at cpcv 0.729) so rank configs are **weak-but-harmless** — no new rank-exclusion machinery (and no D150-style suppress/re-enable dance, since there's no coherence question). **Recommended** (vs restrict-to-confluence).
4. **v22 = Lever B ALONE** — do NOT batch the exit-param sweep ([[D165]], confirmed non-tail, nothing to measure + would muddy attribution) or the trend tilt ([[D166]], IC-bound, declined); keep the funnel cohort clean ([[D151]] split precedent) so `funnel --compare v21 v22` reads the one measured hypothesis cleanly. **Recommended.**

**Classification correction (logged):** this is an **operator-directed loosening** (widens what passes R1) executed via the grammar-change ritual + this D-entry — **NOT** routed through `OPEN_PROPOSALS.md` (that queue is Forge's *auto-tune* loosening flow; [[D150]] — the direct precedent — was explicitly "operator-DIRECTED loosening (not auto)"). **This corrects the `conditioning-levers.md` §2/§3 note** that said the loosening goes "to `OPEN_PROPOSALS` via the approval flow."

**Honest scope (hard rule #6, unchanged):** a **center/quality** knob (concentrates mr into ~2.5× higher-Sharpe entries; +0.142 inside the hurst gate) — **NOT** a CPCV-p25 tail/promotion unlock (the tail is edge-magnitude-bound, [[D165]] three-axis close). Built because it's the one Crucible-validated, in-scope, positive-EV enumeration increment left — pool-quality hygiene on the thinnest arm.

**Gate to proceed:** operator approval of the R1 widening (hard rule #1) + confirm the four defaults. On approval → worktree build, red-first TDD (§4 of the scope), deploy ritual, `funnel --compare v21 v22`. **Nothing built or bumped this turn.**

**Action:** new build-scope `docs/proposals/lever-b-rv-rank-v22-build.md`; `STATUS.md` top block; this entry. No production change.

---

## D168 — 2026-06-15 — Exit-tail ADDENDUM ([[D165]] partially REOPENED): stripping `event_passed_exit` flips the 2 genomes that compose it from −$2.9k to +$31.9k worst-quartile (never-peaked 76%→44%) — a slice that read "structural" was cut-too-early-to-peak; the lever is LOOSENING early time-exits (not truncating), a hard-caveated suspect pending a fair OOS test; v22 stays Lever B alone

**Spec section:** §8.7 / CPCV-p25 (the worst-quartile wall), §3.5 S5/E-rules (the exit vocabulary), hard rule #6 (the magnitude wall, now softened on the exit axis). Source: operator relayed Crucible's addendum to the exit-tail relay (`../Crucible/docs/handoffs/FORGE_exit_tail_attribution_addendum.md`; `probe_exit_tail_attribution.py --strip-exit event_passed_exit` → `probe_results/exit_tail_no_eventpassed.json`, commit 81a4e15). Follows up Crucible's own design-note #1 ([[D165]]: `event_passed_exit` = #1 wall-setter exit, 55%, off the original sweep list). **DOCS-ONLY.**

**The counterfactual.** `event_passed_exit` is **per-genome** — only 2 of the 6 wall-setters compose it (AMD-vol, SOXL-vol; the rest use chandelier/trailing/`time_stop`), all keeping the mandatory backstops (`expiry`/`theta_cliff`/`earnings`/`liquidity`). Stripping it changes those two, on their worst-quartile blocks: **AMD-vol** 137→40 trades, crater net **−$137 → +$31,259**, never-peaked %loss **76%→44%**; **SOXL-vol** 86→60 trades, **−$2,727 → +$677**, **75%→63%**. 2-genome sum **−$2.9k → +$31.9k**.

**Mechanism — it CORRECTS the [[D165]] "~60% structural" read.** `event_passed_exit` chops positions a few bars after entry (~tripling trade count with short cuts). Remove it → positions hold to `theta_cliff`/`expiry` → losers' total loss shrinks AND winners grow (positions live long enough to develop favorable excursions). **Never-peaked loss share falls 76%→44%** — a real slice of what [[D165]] read as "structural, negative entry-to-any-exit" was actually **cut-too-early-to-peak**, and that slice **is exit-shapeable.** ⇒ [[D165]]'s "confirmed non-tail / ~60% irreducible" was **premature for the `event_passed`-composing genomes.**

**Direction FLIPS (corrects `exit-tail-shaping.md` §2 + the [[D165]] swept-knob note).** The headroom is in **LOOSENING early time-exit thresholds** (`event_passed_exit.n_bars_after_entry`, `time_stop.n_bars` — firing too tight, suppressing the convex upside), **NOT** tightening stops / adding profit-targets (still bounded by the structural floor + the winner-capping convexity tension). This fits the convex long-options payoff — the enemy is cutting early, not holding. `event_passed_exit.n_bars_after_entry` is **added to the swept set** (it honors `params`); it is the single most impactful exit knob found.

**Hard caveats — a SUSPECT, not a win.** (i) **In-sample optimism** — a post-hoc strip on the *same data the genome was Optuna-selected on* (entry/sizing tuned *with* this exit's churn) → the +$32k carries selection bias; (ii) **single-config**, not the joint book; (iii) for `event_passed` it is **explicitly NOT trade-count-neutral** (137→40), which **breaks the §2 trade-count-neutral premise** for the time-exit-loosening form. So: a **flagged suspect for a fair test**, not a confirmed "loosen it."

**Disposition.** The exit thread is **no longer cleanly closed** ([[D165]] partially reopened). **The fair test** (strips the in-sample optimism by construction): emit configs with **wider** `event_passed_exit.n_bars_after_entry` / `time_stop.n_bars`, let Crucible re-select/validate them **fresh** (OOS), read the worst-quartile / CPCV-p25 delta via `funnel --compare`. **Sequencing decision:** keep **v22 = Lever B alone** ([[D167]] unchanged — do NOT batch this exploratory, not-trade-count-neutral exit experiment into the clean Lever B cohort); run the time-exit-loosening fair test as the **NEXT exit experiment** — either a separate Forge v-cohort (wider `_exit_params` ranges → fresh OOS cohort) or a cheaper targeted **Crucible re-selection relay** on the 2 genomes first (probe-before-build discipline). **Operator's call on which, and whether before or after Lever B ships.**

**Honest-framing update.** The three-axis "magnitude wall" close ([[D165]]) is **softened on the exit axis**: entry ([[D161]]) and construction ([[D164]]) stand firm; the **exit axis now has a live-but-caveated suspect** (loosen early time-exits) that could touch the wall on ≥2 genomes if it survives a fair OOS test. The wall is still magnitude-bound to first order, but "exit can't help" is no longer a clean claim — credit to Crucible for chasing its own design-note #1.

**Action:** addendum banner + Status flip on `exit-tail-shaping.md` ([[D165]] → partially reopened); relay `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md` addendum note; Q42 update; `STATUS.md` top block; this entry. No production change; nothing built, bumped, or deployed.

---

## D169 — 2026-06-15 — Operator elected to TIE the [[D168]] exit time-cut fair test INTO v22 (alongside Lever B); fair-test relay DRAFTED (held): v22 = (A) `rv_rank` mr gate + (B) widen `event_passed_exit.n_bars_after_entry`; clean because the two act on DISJOINT hypothesis slices → sliced funnel; (B) gated on Crucible's range answer, fallback (B)→v23

**Spec section:** §3.5 R1 (A), §3.6 / hard rule #6 (enumeration determinism — both re-pin the sampler golden sequence), hard rule #3 (no §8.7 change), §8.7 / CPCV-p25 (the fair-test metric). Source: operator — "draft the relay, we should try and tie it into v22." Revises [[D167]]'s "v22 = Lever B alone." **DOCS-ONLY; relay HELD, not sent; no code/bump.**

**The decision:** v22 carries TWO changes — **(A) Lever B** (`rv_rank` as a `mean_reversion` entry R1 gate, [[D164]]/[[D167]]) **+ (B) the [[D168]] time-cut fair test** (widen `event_passed_exit.n_bars_after_entry`, the `volatility_event` exit on the AMD-vol/SOXL-vol wall-setters, so a fresh cohort tests the "loosen early time-exits" suspect OOS).

**Why the tie-in is clean, not muddy (reverses my [[D167]] "Lever B alone" caution):** (A) and (B) act on **disjoint hypothesis slices** — (A) on the **mr** *entry* gate, (B) on the **vol** *exit* param — so a **hypothesis-sliced** `funnel --compare v21 v22` reads each lever on its own slice; the [[D151]] clean-cohort concern is met by **slicing**, not by separating the deploys. Two conditions hold this: **(i)** widen **only** `event_passed_exit` (vol-scoped), **NOT** `time_stop.n_bars` (cross-hypothesis → would contaminate the mr slice; deferred, relay Ask 4); **(ii)** (B) is **sampler-only** (`_exit_params`) so it rides (A)'s v21→v22 bump for free — no second deploy.

**Why v22 IS the fair test (strips the [[D168]] in-sample optimism by construction):** the v22 wider-threshold configs are **new `config_hash`es**, gated/selected/CPCV'd **fresh** by Crucible — so the +$32k post-hoc-strip optimism does not carry over, and widening the whole population (not just the 2 cherry-picked genomes) tests **generalization**. This is a *stronger* test than a targeted 2-genome re-tune.

**The relay (`PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md`, drafted/held) gates (B), not (A).** Four asks: (1) recommend the wider `n_bars_after_entry` range + current default (Forge emits none today → Crucible's runtime default; **we need this before finalizing `_exit_params`**); (2) run the v21→v22 funnel **hypothesis-sliced**; (3) confirm fresh-cohort = the fair OOS test (+ flag any leakage); (4) `event_passed` alone vs also `time_stop` (we lean event_passed-only to keep the mr slice clean).

**Honest framing (unchanged):** (A) is a Crucible-validated **center/quality** knob ([[D164]]); (B) is a **caveated suspect** ([[D168]] — could evaporate OOS; not trade-count-neutral) — v22 is the fair test that resolves it, NOT a pre-commitment to a tail-mover. **Fallback (the "try"):** if Crucible's range is unworkable or the sliced attribution looks contaminated, drop to **v22 = (A) alone, (B) → v23**; (A) never blocks on (B).

**Build-scope updated** (`lever-b-rv-rank-v22-build.md`): new v22-carries-two banner, (B) row in the §2 surface, §4 TDD test for the `event_passed_exit` param emission, §6 batching REVISED (sliced-funnel attribution), §7 ritual (B-gate step 0), §8 decision #4.

**Action:** new held relay `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md` (**not sent**); build-scope `lever-b-rv-rank-v22-build.md` revised to the tied-in v22; `STATUS.md` top block; this entry. No production change; nothing sent, built, or bumped.

---

## D170 — 2026-06-15 — grammar v22 BUILT + DEPLOYED: (A) `rv_rank` mr R1 gate (D167) + (B) `event_passed_exit` time-cut ladder (D169, range answered); operator approved (A) + relayed/answered (B); worktree build, full suite 1623 passed, deployed to live service

**Spec section:** §3.5 R1 (A; operator-owned widening, hard rule #1), §3.6 / hard rule #6 (enumeration determinism), hard rule #10 (v22 bump + archive), hard rule #3 (no §8.7 change), hard rule #8 (seeded `_exit_params`). Source: operator "Approved" the Lever B build ([[D167]]) + relayed Crucible's `FORGE_v22_exit_timecut_fairtest_response.md` ([[D169]] (B) range) + "perform deploy ritual." **PRODUCTION CHANGE — v21→v22 deployed.**

**(B) range answer folded** (`FORGE_v22_exit_timecut_fairtest_response.md`): `event_passed_exit.n_bars_after_entry` default = **3** trading days; sweep ladder **{3, 5, 8, 13, 21}** (+ an "off/large" arm ≥ business_DTE−10, redundant past the mandatory `theta_cliff` cap — Forge can't compute per-genome DTE, so v22 ships the discrete ladder; 21 already reaches the theta_cliff envelope for the swing genomes). **Decisive masking finding (Ask 4):** widening event_passed past 5 is **inert for any genome composing `time_stop@≤5`** — AMD-vol (no time_stop) runs to theta_cliff and flips −$137→+$31,259; SOXL-vol (composes time_stop@5) is capped, only −$2,727→+$677. ⇒ the vol-slice lift will be **diluted** (read a muted result as partial masking, not a dead lever); **event_passed alone for v22** (vol-scoped, mr slice clean), `time_stop` deferred. **Fresh-cohort = fair OOS test CONFIRMED** at config level; 4 residual leaks flagged (policy-level lever-selection → needs whole-vol-population read; masking→false-null; recency; not-trade-count-neutral). **Funnel tooling gap:** `funnel.py` slices by version only → Crucible adds `--hypothesis`; read post-drain ≥1500 decided.

**Build (worktree `../Forge-v22`, branch `v22-rv-rank-mr-gate`, commit `4c4ce84`), red→green TDD:** **(A)** `custom_predicates._R1_RV_RANK_REGIME_INDICATOR` + R1 accept branch + detail; `search_space` MR pool += rv_rank; `sampler._MR_RANGING_GATES += rv_rank` (3.0 bias). **(B)** `sampler._EVENT_PASSED_NBARS_LADDER = (3,5,8,13,21)` + `_exit_params` event_passed branch. **grammar.yaml v21→v22** + header + R1 `evidence_to_relax` note; `grammar_archive/v22.yaml` byte-identical; `GRAMMAR.md#R1` synced. 6 new tests (4 (A) + 2 (B)) + 3 deliberate re-pins (mr-pool, R1-set, v22 version assert; rule count stays **21** — accepted set widened, no rule added). **Gates: full suite 1623 passed; mypy --strict 90 files clean; ruff clean; grammar version-bump + doc-sync hooks pass. Emission proof:** mr emits rv_rank 158/4000 (ranging-weighted; iv_rank 93 stays explorable), event_passed carries the full ladder.

**Determinism (hard rule #6):** the stream changes by design (new gate + bias; new exit param) → v22 bump for cohort attribution; `test_batch_reproducibility` green (reproducible). **Add-not-replace** (R1 stays an OR; hurst configs untouched). **LET-it-rank** (rv_rank rank-coherent; mr rank stays enabled — weak-but-harmless, no exclusion machinery). **No `OPEN_PROPOSALS`** — operator-DIRECTED loosening via the grammar-change ritual ([[D150]] precedent), not the auto-tune queue.

**Honest scope (hard rule #6):** (A) is a **center/quality** knob (mr ~2.5× higher-Sharpe entries), NOT a tail unlock; (B) is a **caveated suspect** (hygiene; could evaporate OOS; not trade-count-neutral). The CPCV-p25 wall stays edge-magnitude / sell-side (World-A). v22's measured value if (B) nulls = (A)'s mr center-lift, which ships regardless.

**Deploy (D104 ritual, `docs/tasks/deploy.md`):** built in worktree (service stayed up) → stop service → land `4c4ce84` to main → full suite (live tree) → restart → journal verify (`grammar_version=v22`). Deploy timestamp + journal evidence in `STATUS.md`. **Relay v21→v22 to Crucible** for the hypothesis-sliced `funnel --compare v21 v22` (mr slice = (A); vol slice = (B)).

**Action:** v22 deployed; relays `FORGE_mr_rv_hurst_overlap_response`/`FORGE_v22_exit_timecut_fairtest_response` ANSWERED+folded; `exit-tail-shaping.md` + `lever-b-rv-rank-v22-build.md` marked BUILT; `STATUS.md` + this entry. Crucible funnel-compare relay to follow.

---

## D171 — 2026-06-15 — INDICATOR-THRESHOLD axis AUDITED (operator probe): per-config CPCV-p25 is FLAT across threshold value for every indicator → the threshold axis is the THIRD confirmed-flat selection lever; D073 trade-count tightener is NOT Goodharting (no edge gradient to miss); nothing to pursue

**Spec section:** §8.7 / CPCV-p25 (the tail metric), §5 / D073 (the auto-tightening threshold proposer), hard rule #6 (center-vs-tail; the magnitude wall). Source: operator — "what about sweeping parameters/thresholds for indicators — anything to probe?" Cheap Forge-side read-only audit on `/tmp/forge_thresh_audit.db` (`investigate-live.md`). **DOCS-ONLY; no code.**

**Why this axis is different from entry/exit:** thresholds are NOT inert — they're the most-machined axis: swept per-config from audited ranges (`indicator_thresholds.py`, absolute + percentile modes), AND auto-LEARNED via the D073 `threshold_proposer` → `config/auto_tightened_thresholds.yaml` (16 live tightenings). The proposer optimizes toward **trade-count** (avoid zero-trade thresholds, ≥10-trade floor), not edge. The probe question: is it Goodharting — missing an edge gradient the tail cares about?

**Audit (10,004 component rows w/ non-null `cpcv_sharpe_p25.value`, 2,016 verified; threshold terciled per indicator, median CPCV-p25, split on `honest_regime_coverage_row` per [[D155]]):** the **verified-slice threshold-response is FLAT** for every indicator — momentum_252 +0.360/+0.358/+0.370, adx +0.344/+0.318/+0.329, hurst +0.468/+0.458/+0.454, rv_rank +0.493/+0.436/+0.434 (faint cheap-tilt ~0.06), iv_rank +0.613/**+0.717**/+0.650 (faint mid-hump ~0.10). Largest gradient ~0.10; most <0.06. **Per-config CPCV-p25 is insensitive to where in the audited range a threshold sits.**

**Conclusions:** **(1)** The D073 trade-count tightener is **NOT Goodharting** — there is no meaningful edge gradient for it to miss, so re-targeting it trade-count→cpcv buys ~nothing. **(2)** Where a faint gradient shows (rv_rank cheaper-best, hurst more-mean-reverting-best), it matches Crucible's per-TRADE direction but is **much smaller per-config** (rv_rank's per-trade **+0.095** ([[D161]]) → only ~+0.06 per-config cpcv) → a per-trade **CENTER** effect that barely reaches the tail. **(3)** The threshold axis is the **THIRD confirmed-flat selection lever** — entry-gate ([[D161]]) · exit-timing ([[D165]]/[[D168]]) · threshold-value (this) — all flat on the worst-quartile. The wall is **edge magnitude = a generation problem** (World-A).

**Caveat (honest):** this is per-config CPCV-p25, a coarser proxy than Crucible's per-trade causal attribution — so "flat on the tail" is clean, but small per-trade *center* gradients can still exist (rv_rank is proof one does). That only reinforces the verdict.

**Recommendation:** nothing to pursue on the threshold axis — don't re-target D073, don't relay a per-trade threshold probe (it would at most find a center effect, = the generation thread, not a tail unlock). Logged Q43. **The residual frontier stays the magnitude/generation problem** (Path C, or a learned generation conditioner — [[D155]]/`generation-model-levers.md`), not selection.

**Action:** this entry; Q43 in `OPEN_QUESTIONS.md`; `STATUS.md` top block. No production change.

---

## D172 — 2026-06-16 — Component-ADMISSION gates (not §8.7) throttle the ranging complement; `regime_coverage` is start-bound → options-derived signals structurally excluded; relay SENT

**Operator: "what knobs move CPCV + how does one typically move it" → "pull current pool composition + deep-probe the three ways to lift, using our data" → "trade count matters less, identify a better number" → "(a) size the coverage fix, (b) draft the relay" → "log + I relayed."** Read-only analysis on the `forge.db` snapshot (2026-06-16T04:21Z) + honest-era `verdicts` (`decided_at ≥ 2026-06-10T17:17:13Z`, `coverage_unverified` excluded). No code / grammar / bump. Probe scripts: `/tmp/p*.py`, `/tmp/q*.py`.

**Framing — the three ways to lift portfolio CPCV-p25** (worst-quartile across 45 purged paths, §8.3; §8.7 bar 1.5 at PORTFOLIO scope): **(1) raise the floor** (worst paths = BEAR/RANGING per [[D145]] T3a) by adding complement; **(2) cut dispersion** (de-monoculture / decorrelate); **(3) lift the whole distribution** (edge magnitude). Forge moves portfolio CPCV only INDIRECTLY — Crucible assembles + computes (§1.2); Forge changes the component population.

**Pool composition (submissions, last 7d):** trend **68%** (down from the 76% [[D145]] decided-cohort reading but plateaued — weekly trend-share 0→12→47→35→**69→65%**, never falling), ranging-complement (mr) 13%, **bear-complement (tail_hedge) 0%**, other 19%. Internal trend diversity is real (103 structures, gate-HHI 0.25) but **irrelevant** — same regime-bet → correlated in the paths that matter.

**Edge (lever 3) = empirically exhausted, quantified.** Of 7,566 honest single-config cpcv values, **0 reach 1.5** (max 1.495, p99 1.06); across **15 grammar iterations v9→v22 the ceiling is FLAT** (p90 ~0.68–0.74, p95 ~0.78–0.86, n≥1.5 always 0). Walk-forward clears 2.0 at **0.1%**. **No single config is promotion-grade** → promotion is necessarily a portfolio-assembly outcome → levers 1&2 (give the assembler decorrelated complement) are the only in-scope moves; lever 3 is Path C (parked). Confirms [[D152]]/[[D165]] from the population direction.

**The inversion (why "make more components" backfires).** Verified-coverage per-family cpcv-p25 median: **mr 0.638 > vol 0.547 > trend 0.410 > rel −0.011**; component-rate INVERTED: **trend 9.96% > vol 5.71% > mr 1.72% > rel 0%**. The best worst-quartile payer (mr/ranging) is accepted at ~1/6 trend's rate. Cause = two component-ADMISSION gates, NOT the §8.7 quality bar:

- **`min_oos_trade_count` (per-bucket 30/60/100, thinnest bucket).** mr lands in the swing_short 100-floor 66% of the time (median thinnest-bucket = 20 trades). But the floor does NOT buy cpcv reliability: cpcv-std is **flat** across trade counts (mr 0.41@20–39 vs 0.35@500+), and Spearman(trade_count, cpcv) = **trend −0.22 / mr −0.17** (only vol +0.25). Low-tc cpcv-p25 is downward-*biased* (45-path split → few trades/path → noise drags the worst paths down) → per-component cpcv-p25 is the wrong statistic for a low-frequency portfolio leg. The floor anti-selects the complement's robustness.

- **`regime_coverage` is a window-START gate (the headline + a CORRECTION of the prior-turn framing).** NOT per-regime-trades. Gate = start within 30 sessions of the data floor AND span ≥1460d. **27,662 of 29,924 honest-era configs (92.4%) fail — every one on the START condition; 0 fail on span.** Start is data-availability-driven (discrete buckets 0/363/866 sessions): **options-derived configs start at 866 sessions** (iv_rank/gamma_flip/put_call_flow/put_wall/days_to_*; cov-pass 4.5%) vs **price-only at 363** (7.1%) — inferred options/IV data floor ~866 sessions after the price floor. The ranging complement leans on exactly those signals (mr uses iv_rank 5763× / gamma_flip 4404× / rsi_2 3790×) → **2.9% coverage pass, structurally locked out**.

**Dispersion is SUPPLY-bound, not ranker-bound.** The `regime_supply:` journal shows the ranker selects complement ABOVE its pool share (ranging 39–61% selected from 25–34% pool; bear **0/0 always**). So the monoculture is upstream (admission gates + grammar), not the ranker — T1/T2 already favor complement.

**The prize (upper bound, pending honest re-gate):** relaxing the coverage start condition admits the ~27.7k start-only failures, **~932 at cpcv≥0.5** incl. **~175 mean_reversion** → roughly DOUBLES verified mr (207→~382; mr's verified cpcv-median 0.638 is the best of any family). Trade-floor→uniform ~30 adds ~51 more quality mr (cpcv≥0.5 & tc≥30: 160 vs tc≥60: 109). No grammar change, no §8.7 change. **Bear stays 0** — a grammar supply gap (tail_hedge ~0 decided all-era; no short stance in v1), separate thread (`PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md`).

**Alternatives REFUTED by the data:** (a) "re-scope coverage to in-target-regime" ([[D172]] prior-turn hypothesis) — moot: coverage is window-start, not per-regime-trades; (b) "lower the trade floor alone" — recovers only ~24 (coverage is the coupled lock, not trades); (c) "enumerate higher-frequency mr" — fights cpcv (the −0.17 correlation).

**Relay SENT — `PROMPT_CRUCIBLE_COMPONENT_ADMISSION_LEVERS.md` (RELAYED 2026-06-16, operator).** 3 independently-answerable asks: (1) is start-at-floor essential or can coverage verify on the available ~5y options-era window (which still holds the 2020/2022 bears)? (2) confirm the price-floor vs options-floor calendar (~866 sessions inferred); (3) lower the per-bucket trade floor toward uniform ~30 for non-event families. **Forge under each:** 1=relaxable → complement ~doubles, re-rank against the newly-verified pool, T2 floor gets real complement to reserve; 1=essential → ranging is hard-capped by options-data history (the gate, not the grammar, becomes binding → roadmap shifts to price-only complement + Path C); 3=yes → +~51 mr; 3=no → bias to higher-freq mr (worse trade).

**Honest scope:** both are component-ADMISSION gates, NOT the §8.7 thresholds (WF/CPCV/PBO/DSR/stress untouched — hard rule #3 intact); this is which raw material reaches assembly. Unlock cpcv is on currently-unverified coverage (upper bound until Crucible re-gates); per-component cpcv ≠ portfolio contribution (open [[D162]]/T3b — final robustness is the portfolio CPCV, Crucible's authority).

**Action:** relay RELAYED (awaiting Crucible's 3 answers → fold as D173); this entry; `STATUS.md` top block. No production change.

---

## D174 — 2026-06-16 — Meta-king A3 Phase 0 BUILT: oracle reader + featurizer + deterministic oracle-ranked search (generation-only dry-run); submission half BLOCKED on two contracts gaps (source tag + DSR n_trials), relay drafted

**Crucible relayed `docs/handoffs/FORGE_meta_king_a3_generator.md` (meta-king arm, A1 complete). Crucible owns the scorer (published as a plain-JSON durable-score oracle); Forge owns the A3 generator. Operator approved "Phase 0 + gaps relay." Built the generation core, verified it, surfaced the blockers. NEW CODE, NO production/daemon change.**

The arm attacks Forge's own established frontier: [[D165]]/[[D172]] both close with *"the CPCV-p25 wall is edge magnitude = a Forge GENERATION problem (World-A)"* — A3 is the generation-side attack (search the genome space to maximize the oracle's predicted durable `cpcv_sharpe_p25`, queue the top genomes as proposals into the **unchanged** §8.7 gauntlet, hard rule #3).

**Built — new `src/forge/king/` package (generation-only):**
- `oracle.py` — schema-pinned (`schema_version==1`), acceptance-gated, **no-cache** reader → frozen `DurableOracle`. Re-reads each run (the oracle refits daily; if `latest` stalls the gate is rejecting and the last good oracle stands).
- `featurize.py` — exact bit-for-bit mirror of Crucible's featurizer (A3 §2a); `score.py` — the ridge (impute→standardize→dot, §2b).
- `search.py` — **deterministic** (`SeedHierarchy`) oracle-ranked enumeration: reuse `enumerate_candidates` (valid-by-construction) → score each → dedup → top-K by predicted score (ties break on `config_hash`). Tracks `n_searched` = the DSR trial count `N`.
- `dedup.py` — gated-export tried-set, **lock-free** via the blessed `load_recent_gated_runs_from_export`.
- `cmd_king` (`forge king`) — **dry-run** preview; prints oracle meta + top-K + `N`/dedup stats + a "DRY RUN — NOT submitted" banner; optional `--out` JSON artifact carrying `dsr_trial_count_n`. **Writes nothing to the inbox.**

**Verified.** Scorer reproduces Crucible's three published reference hashes **EXACT to 1e-6** (`d31fa393…`=0.782095, `173f2db5…`=0.524689, `9a2f6fbf…`=−0.138255; genomes pulled from `forge.db` submissions) + the self-contained micro-artifact (6.5/3.5). Live dry-run on the real seam: oracle n_train=1693 / model_ic=0.3039 / 75 feat, N=2000, deduped vs 9518 gated hashes, top predicted **~0.74**. **Gates: full suite 1644 passed · mypy --strict clean (96 src) · ruff clean.** 21 king tests (golden scorer, oracle validation, search determinism/dedup/grammar-validity/order, CLI smoke+artifact) + 2 invariants (determinism hard rule #6; **structural no-submit** — fails if `submit_candidate` ever appears in `forge.king`).

**BLOCKERS — two `crucible_contracts` gaps (hard rule #2: surfaced, NOT worked around).** `StrategyConfig` is `frozen=True, extra="forbid"` (`models.py:306`) with no `source` and no `n_trials`/`trials`; `submit_candidate` writes exactly `model_dump_json` (`queries.py:208`). So: **(1)** the A4 success read (`source='meta_king'` reach-rate vs `forge`) is **unmeasurable** — `runs.source` can't distinguish the streams; **(2)** the **mandatory** DSR trial-laundering guard (A3 §4) is **unsatisfiable** — no channel carries the search multiplicity `N`, so the gate's DSR under-deflates and a king could pass by oracle-overfit, not edge. `grammar_version` (D096 — optional, hash-excluded provenance read by the inbox watcher) is the exact precedent fix for both. Relay `PROMPT_CRUCIBLE_META_KING_PROVENANCE_DSR.md` **DRAFTED (held)**: ask 1 = source mechanism (D096-style field vs dedicated inbox subdir); ask 2 = DSR discipline (report `N` via a channel vs Crucible oracle-blind holdout) + confirm `N` = genomes scored.

**Design decisions.** (a) **Oracle-rank enumeration, not free perturbation** — reusing `enumerate_candidates` guarantees grammar-validity (every king passes `validate()`) and a clean `N`; local-search refinement deferred. (b) **Seeded deterministic search** (rules #6/#8) — no Optuna dependency added. (c) **Phase 0 writes nothing outward**, structurally enforced. (d) Dry-run dedups vs the gated export (rolling 10k); authoritative `submissions.config_hash` dedup + the unique-index idempotency guard (rule #9) belong to the submission phase.

**Honest scope.** Component-grade, not promotion (oracle max ~0.78 « 1.5 wall) — consistent with [[D172]] ("no single config is promotion-grade; promotion is portfolio-assembly"). On-manifold by construction (enumerator samples the training corpus's space). Cross-validation: the unbiased oracle-argmax is **all `mean_reversion/swing_short`** — independently rediscovering Forge's best-durable family (mr verified cpcv-p25 0.638, [[D172]]); but that monoculture means the **submit phase needs per-cell diversity controls** before it can feed a decorrelated complement.

**Action:** package + 23 tests built & green; relay drafted (held); this entry; `STATUS.md` top block; `docs/MANPAGE.md` `forge king` section (doc-sync enforced). **No production change** — the arm is inert to the daemon (`forge run` never calls `forge king`; `forge --help` startup verified green), so no deploy/restart. Submission half waits on the two Crucible answers → fold as the A3-submission gate decision. (D173 reserved for the pending component-admission fold, [[D172]].)

---

## D175 — 2026-06-16 — Crucible ANSWERED the meta-king provenance/DSR relay: both granted (D096 hash-excluded pattern) → submit-half unblocked pending the contracts bump; per-cell diversity quota BUILT; confirmation drafted

**Operator relayed Crucible's answer (`FORGE_meta_king_provenance_dsr_response.md`) to the [[D174]] gaps relay. Folded; built the one unblocked Forge-side piece (diversity quota); drafted the confirmation. NO production change.**

**Crucible granted both asks, both as optional hash-excluded `StrategyConfig` fields (the `grammar_version`/D096 pattern — zero `config_hash` churn, no migration). Crucible owns + ships all three changes (contracts bump + 2 wiring sites) on Forge's confirmation:**
- **Gap 1 → (a) `source: str | None = None`.** Inbox watcher fills `runs.source = config.source or "forge"` (`optbt/data/inbox.py:193`). Forge stamps `source="meta_king"`; bare/forge configs default to `'forge'`. Chosen over the inbox-subdir (a first-class field beats a path side-channel; A4 keys on `runs.source`).
- **Gap 2 → (i) `search_n_trials: int | None = None`, REPLACE.** A submitted king is a single config with no in-gate sweep, so Crucible's runner uses `n_trials = config.search_n_trials or 1` at the single-config `deflated_sharpe` (`runner.py:2902`/`:1133`) — `N` *is* the only multiplicity (not added to an in-gate count). Forge configs without the field stay `n_trials=1` (unchanged).
- **`N` confirmed** = genomes scored against the oracle (`n_searched`), NOT pre-oracle sampler/validator rejections (they never competed on the deflated metric). Noted conservative-in-our-favor: the king maximizes the oracle *proxy* (IC ~0.31), so realized-cpcv multiplicity is `< N` → deflating by full `N` over-deflates (honest/safe).
- **Holdout (ii) DEFERRED to extrapolation mode only** (predicted >1.5, aiming to promote). Component-grade kings don't hit the promotion DSR gate, and A4 is population-self-correcting for oracle-overfit (a pure-overfit oracle's kings reach `component` no more than forge → A4 reports `no_difference`). Carving a `fullhist_refit` holdout pre-emptively would shrink the coverage-strained corpus; Crucible specs it when Forge flags its first extrapolation king. Until then Forge flags+holds extrapolation kings (honest-backtest, no submission) — matches the [[D174]] relay §4.

**BUILT — per-(hyp,dte) diversity quota (the one unblocked Forge-side piece, Crucible-endorsed).** `search_kings(per_cell_cap=K)` + `forge king --per-cell K`: at most `K` positively-scored kings per `(hypothesis, dte_bucket)` cell, capped at `top_k`, preserving global score order (`_select_diverse`). Additive — default (`None`/`0`) keeps the global top-K behavior, so [[D174]]'s tests are unchanged. **Breaks the monoculture:** unbiased argmax = all `mean_reversion/swing_short`; `--per-cell 2` dry-run now spans **6 cells** (mr / volatility_event / trend_continuation / event_momentum × swing_short/mid, scores 0.74→0.53) — the decorrelated complement [[D172]] needs. Crucible's A4 harness breaks reach-rate down by cell (de-confounds "better genomes" vs "easier cells") → Forge tunes `K` off that once a `meta_king` stream exists. **Gates: full suite 1646 passed · mypy --strict clean (96) · ruff clean · 23 king tests** (added per-cell cap + zero-guard).

**Confirmation DRAFTED (held) — `PROMPT_CRUCIBLE_META_KING_CONTRACT_BUMP_CONFIRM.md`:** ratifies (a)+(i), reports what Forge stamps, asks for the **target contracts version string** (to pin `FORGE_EXPECTED_CONTRACT_VERSION` in the adoption commit, avoiding a `SchemaVersionMismatch` window). A4 bar acknowledged: beat forge's **2.37%** component-reach (886/37456) via `scripts/probe_meta_king_yield_ab.py`.

**Still BLOCKED (correctly):** the submit-half build (stamp `source` + `search_n_trials`, wire the submit path with the diversity quota) needs the new fields, which don't exist until Crucible's contracts bump publishes. **Adoption step Forge owns post-bump:** pin `FORGE_EXPECTED_CONTRACT_VERSION` (`forge.core.contracts_check`) + **restart the daemon** (the bump changes the parsed `StrategyConfig`; a hot read would log `registry_loaded_from_export` and validate stale — restart per the adoption plan). Then the submit wiring is a separate operator-gated deploy.

**Action:** diversity quota + 2 tests built & green; Crucible answer folded; confirmation drafted (held); original relay flipped ANSWERED; this entry; `STATUS.md`; `docs/MANPAGE.md` `--per-cell`. No production change. **Next:** operator relays the confirmation → Crucible bumps → Forge adopts (version pin + restart) → submit-half build (operator-gated).

---

## D176 — 2026-06-16 — contracts 1.19.0 ADOPTED (pin 1.18.0→1.19.0, required); meta-king submit-half SCOPED + HELD on operator go (distinct submission path + outward-facing + feedback-source subtlety)

**Operator relayed `FORGE_meta_king_contract_1_19_0_shipped.md` — Crucible shipped `crucible_contracts` 1.19.0 (`30b8fa9`) with the two hash-excluded `StrategyConfig` fields (`source`, `search_n_trials`) + adopted/wired them (inbox stamps `runs.source`, runner folds `search_n_trials` into single-config DSR). Forge's one adoption step done (the version pin); the submit-half build surfaced as structural/outward → HELD for operator go. NO submission, NO daemon restart.**

**Contracts 1.19.0 adoption — REQUIRED, done.** Verified firsthand: installed `crucible_contracts.CONTRACT_VERSION == "1.19.0"` (editable `../crucible_contracts`), `StrategyConfig.model_fields` now carries `source` + `search_n_trials`. **Forge's pin was still `1.18.0` → every `forge` CLI startup was failing `check_contracts_version` (SchemaVersionMismatch), and a reboot would have taken the service down.** Pinned `FORGE_EXPECTED_CONTRACT_VERSION = "1.19.0"` (`forge.core.contracts_check`, §13.5). Post-pin: `forge king` dry-run works, 23 king tests green, 45 contracts/integration tests green; the `1.18.0` strings in tests are historical comments, not pin assertions. **Tree is now reboot-safe** (pin == installed). The running daemon still holds 1.18.0 in-memory (imported pre-bump) — fine, it submits bare configs the 1.19.0 watcher defaults to `source="forge"`; it adopts 1.19.0 in-memory at the next deliberate restart (operator deploy, low urgency now the tree is safe).

**Submit-half SCOPED — and deliberately HELD (hard-to-reverse structural choice + outward-facing, CLAUDE.md stop-rule).** Read `submitter.py` in full: `_submit_one` is coupled to a `RankedCandidate` carrying a **pre-filter battery report** (`record_pre_filter_logs`). Meta-king kings are **oracle-selected, not battery-selected** — they have no report — so the submit-half is a *distinct* submission path, not a reuse of `submit_batch`. Options: a self-contained `forge.king.submit` (additive, no risk to the monkeypatched `submitter.py`) vs. refactoring `_submit_one` to make pre-filter-logging optional. Plus two genuine decisions for the operator:
- **Architecture/cadence:** manual `forge king --submit` (v1; daemon untouched; controllable for A4's matched window) vs. a `forge-king-submit` systemd timer vs. folding into the `forge run` loop.
- **Feedback cross-contamination (subtle):** `RunResult` (the gated export Forge reads) has **no `source` field** — so once meta_king runs gate, Forge's learned-weight feedback can't distinguish them from forge runs (DESIGN.md §9.2's `WHERE r.source='forge'` applies to `runs.duckdb`, not the export). Keeping the arms independent (the oracle is meta_king's selector, not the forge ranker) may need Crucible to add `source` to `RunResult`/the gated export. Latent until the first meta_king run gates, but it shapes the design.

**Honest framing:** the meta-king arm now has a live contract channel; the generation half ([[D174]]/[[D175]]) is built + verified + dry-run-flowing with the diversity quota. The submit-half is the first time Forge would open a *new outward stream* to the live inbox — operator-gated by both the structural-choice rule and the outward-facing rule. Built nothing outward this turn.

**Action:** pin adopted (1.19.0); submit-half scoped + held; this entry; `STATUS.md`; awaiting operator go on cadence/architecture (+ a possible Crucible `RunResult.source` ask for clean feedback separation). **Next:** operator picks the submit-half cadence → Forge builds it inert (TDD, tmp-inbox tests) → operator authorizes the first live submission + a deploy to adopt 1.19.0 in-memory.

---

## D177 — 2026-06-16 — meta-king submit-half BUILT (`forge king --submit`, manual mode per operator): stamps source + search_n_trials, diversity quota, idempotent; verified to a tmp inbox; first LIVE submission + daemon deploy still operator-gated

**Operator (AskUserQuestion) chose "Manual `forge king --submit`" for the submit-half cadence ([[D176]]). Built it inert (opt-in; dry-run remains default), TDD, tmp-inbox-verified. NO live submission, NO daemon restart.**

**Built — `src/forge/king/submit.py` (a distinct submission path).** Kings are oracle-selected (no `PreFilterReport`), so this does NOT reuse `submit_batch`; `submit_kings` mirrors the §7 submitter's crash-safe `BEGIN → INSERT(pending) → submit_candidate → UPDATE(submitted) → COMMIT` transaction with `config_hash`-unique idempotency (hard rule #9), and reuses `_insert_batch_summary` (single source of truth for the `batch_summaries` schema; funnel/feedback joins stay valid). Each king is stamped `source="meta_king"` + `search_n_trials=N` + `grammar_version` via `model_copy` — **all three hash-excluded in 1.19.0, so `config_hash` (inbox filename, unique index, dedup key) is byte-identical** (verified: `bf696bdd00991018` unchanged before/after stamping). `N` = `n_searched` (same for every king in the batch — the oracle-search multiplicity).

**CLI — `forge king --submit`** (+ `--inbox`/`--forge-db`/`--config`; dry-run stays the default). Resolves inbox+db from explicit options or `forge.yaml`; errors (exit 2) if `--submit` can't resolve an inbox; warns if `--submit` without `--per-cell` (would queue the argmax monoculture). Mints a deterministic king batch_id (`mint_batch_id` with a `meta_king|n=…|k=…|pc=…` tag, so re-runs are idempotent no-ops and king batches never collide with forge batches).

**Verified — live `--submit` to a TMP inbox** (real oracle + registry; tmp inbox+db, NOT the live inbox): searched N=1500, `--per-cell 2` → 8 kings across 4 hypotheses (mr/vol_event/trend/event_momentum), **submitted 8**; inbox files keyed by the unchanged `config_hash`, each carrying `source=meta_king` / `search_n_trials=1500` / `grammar_version=v22`. **Gates: full suite 1652 passed · mypy --strict clean (97) · ruff clean · 29 king tests** (added `test_submit.py` provenance/idempotency/hash-stability/empty + 2 CLI submit tests). **Invariant updated** ([[D174]]'s "never submits" → **`submit_candidate` may appear ONLY in `submit.py`**; the generation/scoring core still never submits as a side effect).

**Design decisions.** (a) **Self-contained `forge.king.submit`** over refactoring the monkeypatched `submitter.py` — additive, zero risk to the ~10 D065/D105/D106 test files. (b) **Manual `--submit`** (operator/cron-invoked) over loop-integration — daemon untouched, controllable cadence for A4's matched window; a systemd timer is a trivial follow-on if it proves out. (c) **No pre-filter battery** for kings — the oracle IS meta_king's selection; running the forge battery would conflate the arms and muddy the A4 `meta_king`-vs-`forge` read (which compares selection mechanisms facing the same §8.7 gate).

**Still operator-gated (outward / deploy).** (1) The **first LIVE submission** — `forge king --submit --per-cell K --config config/forge.yaml` against the real inbox — opens the new `meta_king` stream; it's the operator's to fire. (2) The **daemon restart** to adopt 1.19.0 in-memory (low urgency; tree is reboot-safe). (3) **Feedback separation (latent):** `RunResult`/the gated export has no `source`, so once meta_king runs gate, Forge's learned-weight feedback can't exclude them — a Crucible `RunResult.source` ask would keep the arms independent (offered, not drafted).

**A4:** beat forge's **2.37%** component-reach (886/37456) via Crucible's `scripts/probe_meta_king_yield_ab.py`, by `runs.source`.

**Action:** submit-half built + tmp-verified; invariant updated; this entry; `STATUS.md`; `docs/MANPAGE.md` `--submit`/options. No live submission, no restart. **Next:** operator fires the first live `--submit` (when ready) + bundles the 1.19.0 daemon restart into a deploy; optionally I draft the `RunResult.source` relay.

---

## D178 — 2026-06-16 — FIRST LIVE meta_king submission FIRED: 15 kings → the live inbox (source=meta_king, search_n_trials=2500); routing corrected to a SEPARATE king DB (daemon lock + arms-independence)

**Operator: "Let's start the next steps to fire. I am asking the Crucible agent to do as well." Authorized the first live submission, coordinated with Crucible's A4 wiring. FIRED + verified; corrected the live-fire routing.**

**The stream is LIVE.** Fired `forge king --submit --inbox ~/optbt_data/inbox --forge-db ~/forge_data/king_submissions.db --search 2500 --top-k 15 --per-cell 3 --seed 1` → **15 kings submitted to the live Crucible inbox**, diverse across `mean_reversion`/`volatility_event`/`trend_continuation` (swing_short/mid), predicted 0.70→0.60. **Verified:** inbox files keyed by the unchanged `config_hash`, each stamped `source="meta_king"` / `search_n_trials=2500` / `grammar_version=v22`; king DB recorded 15/15 `submitted` + 1 `batch_summaries` row; **`forge.service` stayed active/healthy** (concurrent inbox writes don't collide — different hash filenames). Crucible's inbox watcher ingests them → `runs.source="meta_king"`, gating the A4 read.

**ROUTING CORRECTION (supersedes the [[D177]] `--config forge.yaml` go-live example, which was lock-unsafe).** The `forge.service` daemon holds an intermittent RW lock on the live `forge.db` ([[forge-db-readonly-snapshot]]), so a second writer there (`--forge-db ~/forge_data/forge.db`) would collide. The live fire routes `--forge-db` to a **separate** `~/forge_data/king_submissions.db`. Bonus: this keeps `meta_king` submissions OUT of the main `forge.db` that the forge feedback/reconcile reads → **the latent [[D176]] feedback-separation concern is solved by routing** (the arms stay independent without needing a Crucible `RunResult.source` change). Trade-off accepted: Forge doesn't locally reconcile meta_king `crucible_run_id` (the king DB isn't on the daemon's reconcile path) — fine, A4 is Crucible-side by `runs.source`. MANPAGE corrected.

**Oracle refreshed mid-session — no-cache design validated.** The dry-run/fire picked up a fresh oracle automatically: `published_at=2026-06-16T23:34:32` (was 21:53:46), `n_train=1819` (was 1693), `model_ic=0.3136` (was 0.3039), `features=77` (was 75) — Crucible's daily refit landed and the reader re-read `latest` with no caching ([[D174]]). Golden tests still pin the frozen `215346Z` fixture; runtime uses `latest`.

**Growing the stream:** re-fire with a **varied `--seed`** (same seed → same kings → idempotent skip via the king DB unique index); each fire adds ~15 fresh kings (deduped vs the gated export + the king DB). A `forge-king-submit` systemd timer (rotating seed) is the trivial automation if the operator wants the stream hands-off — offered, not built.

**Action:** first live fire done + verified; MANPAGE routing corrected; this entry; `STATUS.md`. **Still pending (operator):** the 1.19.0 daemon restart (low urgency, tree reboot-safe); the recurring-fire cadence (manual varied-seed vs a timer). The `RunResult.source` relay is now **moot for feedback separation** (routing handles it) — only needed if Forge later wants source-aware reads of the gated export.

---

## D179 — 2026-06-17 — meta-king oracle CUT OVER cpcv→P(component) (auto-adopted, one floor re-tune); VOLUME BOUND folded after the 2010-king flood starved forge + OOM-killed the writer → PAUSE, resume ≤20/day

**Two Crucible relays folded: `FORGE_meta_king_component_oracle_cutover.md` + `FORGE_meta_king_volume_bound.md`. The cpcv A4 came back 0/273 (wrong objective) and the volume was harmful. Re-tuned the one affected line; paused the stream. CODE (search floor) + DOCS; NO grammar/contract change.**

**Oracle cutover (cpcv → P(component)) — auto-adopted, verified.** The cpcv objective ranked `component` at **AUC 0.54 (~chance)**; the component objective hits **0.86** (Crucible's 5-axis adversarial probe). New live oracle: `target="p_component"`, n_train 3893, **85 features**, model_ic **0.6043** (was 0.30), published 2026-06-17T02:49:42Z. **Forge's reader auto-adopted it with ZERO code change** (schema-pinned + no-cache, [[D174]]) — verified: `load_oracle` loads it; the featurizer covers **all 85 features** (14 num: all known, no unknown-prefix cols → no scorer divergence from Crucible); the golden cpcv fixture still pins the (objective-agnostic) ridge math.

**The ONE re-tune — P(component) admission floor.** `search.py` per-cell selector dropped `predicted_score <= 0.0`; for a ~[0,1] probability that floor is inert. Replaced with a configurable `min_score` (default **0.5** = better-than-even; base rate ~0.39), CLI `--min-score`; **global top-K mode unchanged** (ranks by score). Live dry-run confirms it: the objective shift moved the argmax from cpcv's `mean_reversion/swing_short` to **`volatility_event/swing_short` (P=0.86)**; `--per-cell 3 --min-score 0.5` surfaced 12 diverse kings all ≥0.5.

**VOLUME BOUND — the hard correction (my 2010-king flood was harmful).** `meta_king` grades on an **absolute priority lane** (kings jump the queue). The flood (~2010 submitted) **starved the forge queue** (~7–17h with 84,768 forge runs queued behind it) and drove Crucible's **single-writer into an OOM-kill (106 GB / 9h, auto-recovered)** — the `skipped: real feature cache unavailable` journal line at the [[D176]] restart was a symptom of that OOM. **Self-correction:** I'd flagged the volume/backtest concern myself in the throttle discussion, but executed the operator's "push to 2000" without insisting on a bound first; the flood + OOM are the cost. The 2010 cohort was also the **wrong objective** (cpcv) → it will mostly `reject` as it drains.

**Crucible directive (folded as policy):** **PAUSE `forge king --submit` now**; let the existing full-history kings gate; Crucible reads A4 (*does any P(component) king reach `component` where cpcv got 0/273?*); then **resume bounded — ≤20 kings/cycle (`--per-cell 3 --top-k 20 --min-score 0.5`), ≤1 cycle/day** (aligned to the 07:00 PDT oracle republish), **keep `--search 2000`** (do NOT shrink — it's the DSR `n_trials` honesty), keep dedup-vs-gated on. Crucible adds a priority-lane **fair-share cap** their side (belt-and-suspenders).

**Disposition:** stream **PAUSED**. Bounded P(component) resume is the clean A4 read. Gates: **30 king tests · mypy --strict clean (97) · ruff clean**; MANPAGE updated (objective, `--min-score`, volume bound); STATUS. The operator's `FORGE_THROTTLE_BACKPRESSURE_PROPOSAL.md` (king-side throttle) would harden the spigot beyond the ad-hoc inbox wrapper ([[D178]]).

## D180 — 2026-06-17 — meta-king oracle flipped P(component)→M(component) (`min_margin`): auto-adopted; floor default re-tuned to the corpus median (relay's -0.8 was empirically a monoculture) + a fail-loud guard so a stale floor can never silently submit an empty batch; 20 M-kings FIRED pre-§20 on operator go (honest-gate cohort — component-reach still waits on §20)

**Crucible relay `FORGE_meta_king_min_margin_oracle.md` folded. Third objective flip. CODE (search floor default + a new empty-admission guard) + DOCS; NO grammar/contract change. 20 M-kings FIRED pre-§20 (seed 1002) on the operator's explicit go — they verified §20 is NOT yet resolved but directed firing anyway for the honest-gate / ΔM-assembly signal; component-reach still waits on §20 (below).**

**Oracle flip P(component) → M(component) — auto-adopted, verified live.** New objective `target="min_margin"`: the **standalone all-gate min-margin** — how close a single strategy comes to clearing the *whole* §8.7 gauntlet with its weakest gate binding (supersedes P(component)'s binary floor with a continuous "strong across EVERY gate" gradient). Crucible validation: 4,415-run corpus, lift 0.217, perm-null 0.052, IC 0.527. My live read of `meta_king_oracle_latest.json`: n_train **4497**, **85 features**, model_ic **0.5346**, published **2026-06-17T14:00:02Z** (07:00 PDT). Same featurize+ridge schema → **no contracts bump**; the schema-pinned no-cache reader ([[D174]]) auto-adopted it with zero code change (confirmed: `forge king` dry-run ranks it correctly).

**The score is now a MARGIN, mostly NEGATIVE.** `M ∈ ~[-4.2,-0.2]` on the corpus — **0% clear the gauntlet alone** (that's the whole point of the portfolio stage). Strongest = **least-negative** (highest). Global top-K ranks correctly as-is. The break was the **per-cell floor**: the D179 default `0.5` was tuned for P(component)'s ~[0,1] — under `min_margin` it **rejects every genome**, so per-cell mode silently surfaced **nothing** and `--submit` would have queued an empty batch.

**Re-tune #1 — floor default 0.5 → -1.0 (the corpus median), diverging from the relay on evidence.** The relay recommended `-0.8` (top-quartile). My live dry-run (n=2000, seed 1000) shows **-0.8 collapses to 3 kings in a single cell** (`volatility_event/swing_short`) — the monoculture per-cell mode exists to break — while **-1.0 (median) fills the diverse top-20 across 7 `(hypothesis,dte)` cells / 4 hypotheses** (volatility_event, trend_continuation, relative_value, mean_reversion). Adopted -1.0 as the default; flagged the discrepancy back to Crucible. The floor is **objective-relative** — always set from the live score range, never carried over.

**Re-tune #2 — the durable fix: fail-loud empty-admission guard.** Per-cell selection that admits **0 of N** scored genomes now **raises** with the live `oracle.target` + observed score range (e.g. *"admitted 0 of 198 … target='min_margin', scores ranged [-1.4793, -0.7908]"*) instead of silently returning empty. This survives the *next* objective flip — a stale floor can never again silently fire nothing. TDD: failure test (`test_per_cell_empty_admission_raises`) written red first. Global top-K mode is unchanged (ignores the floor).

**§20 / DSR dependency — fired pre-§20, knowingly.** An M-king still carries `search_n_trials=N`, so it hits the `deflated_sharpe` gate and **rejects at component-eligibility regardless of strength** until Crucible's §20 `king-component-dsr-scope` resolves. I verified its status (`docs/decisions/king_component_dsr_scope.md`, edited 2026-06-16T22:06): **"PROPOSED, conditional on the portfolio-OOS validation … NOT implemented" → "keep `n_trials=2500` at component (status quo)"** — i.e. the gate still binds. I surfaced that (it contradicted the operator's "should be resolved") and recommended holding; via AskUserQuestion the operator chose **"Fire now,"** then explicitly confirmed **§20 is not yet resolved but "it's fine to move forward."** So these M-kings **gate honestly but will reach `gated`, NOT `component`** — a 0-component A4 read is the DSR gate, **NOT the M-objective failing** (precisely the misread the relay warned against). Rationale for firing pre-§20: a bounded cohort confirms M-kings gate honestly and gives Crucible an M-strength set to measure ΔM portfolio-assembly on now, not after §20. **Kept `--search 2000`** (the relay's "2500" is illustrative — `search_n_trials` = the real `n_searched`; do not shrink, it's DSR honesty).

**Submit lock (relay §"lock-blocked") — already solved my side.** The relay flags `forge king --submit` conflicting with the daemon's `forge.db` write lock; Forge already routes king submission to a **separate `~/forge_data/king_submissions.db`** ([[D178]]) → no lock conflict (the relay author may not know). No change needed.

**Disposition:** code+docs **ADOPTED**; **20 M-kings FIRED** — `forge king --submit --search 2000 --top-k 20 --per-cell 3 --seed 1002` (default floor -1.0) → live inbox, **`submitted=20 skipped_dup=0 failed=0`** (batch `66330a2b`, 2026-06-17T15:09:11Z), `source=meta_king` / `search_n_trials=2000`. Diverse across **4 hypotheses** (volatility_event, mean_reversion, relative_value, trend_continuation) × 3 dte cells, **M -0.757 → -0.955**. Separate `king_submissions.db` (no `forge.db` lock); **daemon unperturbed** (active, NRestarts=0, same MainPID, normal §7.3 throttle). First fire of the min_margin cycle (07:00 PDT republish); the earlier p_component batches (seed 1000/1001) are superseded-objective and drain/gate. **Expect a 0-component A4 — that is the §20 DSR gate (acknowledged), not a failure of M.** Volume note: the king DB holds ~2240 lifetime (flood-dominated, [[D179]]); this fire added exactly 20. Gates: **32 king tests · full suite 1654 · mypy --strict · ruff clean**.

## D181 — 2026-06-17 — Crucible ANSWERED the min_margin-adopted relay (floor −1.0 CONFIRMED; the n=20 cohort gated HONESTLY = §20 DSR gate not M failing; §20/component-reach is ACCUMULATION-BOUND ~30–60 / weeks + gated on a held-out ΔM campaign that was NEGATIVE for the P-cohort; early read = magnitude wall not objective) → operator authorized a one-time 500-king override to compress the timeline, fired PACED + backpressured (NOT the D179 flood)

**`FORGE_meta_king_min_margin_adopted_response.md` folded. Both asks answered (no Forge change). Then the operator invoked the one-time larger-batch lever Crucible explicitly offered → 500-king paced fire.**

**Ask 1 — floor −1.0 CONFIRMED.** Correct for the assembler — ΔM = M(book+g) − M(book) extracts value from **diversity**; a −0.8 single-cell tip is "worthless to me." Crucible wants **more breadth, never less** ("don't pre-spread or pre-thin on your side"; a looser floor is fine, tighter is not). The −1.0 default + fail-loud guard endorsed; keep them objective-relative. **Winner's-curse note (not a change):** realized M on the 20 (median **−1.12**) lands *below* the −1.0 *predicted* floor (oracle predicted −0.76→−0.95; IC ~0.53) — admission optimistic by ~one floor-width in realized terms. Expected.

**The n=20 gating read (the honesty+ΔM read, not count).** All 20 **reject**, **honestly**: DSR fires on `n_trials` (the laundering fold works end-to-end) → the 0-component count is the **§20 gate, not `min_margin` failing** (confirmed, as warned). DSR-excised would-be-components **≈1/20** (~parity with the P-cohort's 3.66%; n=20 = noise). **The signal:** M-kings fail the *n_trials-independent* quality gates at the **same rate P did** — `sharpe_baseline` **19/20**, `regime_stress_p25` 12/20, `profit_factor` 10/20 — i.e. M-strength **isn't transferring to realized gate-clearance**; with the realized-M regression, the early (underpowered) read is **the binding wall is edge MAGNITUDE, not the selection objective** ([[exhaust-long-options-before-v2-spreads]]). Crucible flags it "not a refutation at n=20" — neither side should over-read a future "M-kings still 0 component."

**Ask 2 — §20 deploy ping: YES, but ACCUMULATION-BOUND.** §20 (`n_trials=1` at component scope) deploys **only if** a held-out §8.7 portfolio campaign on an **M-cohort** shows M-kings don't degrade the assembled book OOS — the **same adjudicator that came back NEGATIVE on the P-cohort** (both arms halved held-out WF + added gate failures; `probe_results/king_component_heldout_eval*.json`). It needs a usable would-be-component set (v1/v2 used **66**); the n=20 batch yields **≈1**. At ≤20/cycle × ≤1/day × ~5% DSR-excised → a comparable cohort is **WEEKS** out. Path: keep bounded daily fires (don't flood) → Crucible accumulates the set + folds the count into the daily EOD packet → at ~30–60 runs the held-out ΔM campaign (= the §20 adjudicator AND the ΔM read) → pass deploys §20 (ping, zero Forge change) / degrade keeps the King a research proposer, not a component source.

**Operator override — 500-king one-time push (to compress the weeks).** Crucible explicitly offered this: *"the operator can authorize a one-time larger seed batch to compress the timeline, but that's their call against volume discipline, not a default."* At ~5% DSR-excised, **500 kings → ~25 would-be-components** — a real down-payment toward the ~30–60 the §20 campaign needs. Operator authorized it. **Fired PACED, not flooded** (the D179 lesson): a background loop of `--search 2000 --top-k 20 --per-cell 3 --min-score -1.0` sub-batches (seeds 1003+), with **inbox backpressure (CAP=100 in-flight)** + a daemon-active gate + a 5-min stall-halt + a 40-batch cap — so in-flight stays bounded at ~120 (vs the flood's 2010), Crucible's fair-share cap paces its side, and the loop self-halts on any degradation. Pre-fire health clean (inbox 0, daemon active NRestarts=0). **Outcome: 519 submitted in 26 paced batches** (seeds 1003–1028, `submitted=20`/batch, **dup=0** — fully net-new; overshot 500 by one batch on the `<500` check), in-flight bounded **≤120** throughout, Crucible drained in ~60s periodic bursts, **daemon NRestarts=0 / MainPID stable** (fully isolated by the separate king DB); king DB **2240 → 2759**; completed 15:38:21Z (~5 min). **This is a deliberate one-time ≤1/day override (logged as such), not a policy change** — bounded ≤1/day resumes after.

**Disposition:** floor **−1.0 confirmed**; arm **flowing + gating honestly**; §20 **PROPOSED/NOT implemented**, weeks-out + campaign-gated. **No Forge code change.** Relay marked ✅ ANSWERED. The 500-cohort accelerates the M would-be-component accumulation Crucible needs for the §20 held-out campaign; watch the EOD packet's would-be-component count + the *n_trials-independent* hard-gate clearance rate (improvement there = M transferring; flat = the magnitude wall holds). A `forge-king-submit` timer (offered) would automate the post-override ≤1/day cadence bound-safe.

---

## D182 — 2026-06-17 — Cohort-yield axis (Crucible's 2026-06-17 yield-map refresh §3): the cohort draw (cross_sectional_rank vs confluence) becomes YIELD-DRIVEN instead of a fixed share — versionless feedback, A/B-flagged `--cohort-yield`, default OFF (byte-identical). BUILT + VERIFIED; deploy/flag-flip operator-gated.

**Spec section:** §6.3/§8 feedback weighting; the D094→D101→D103→D105→D106→D108 lineage (this extends D106's hierarchical triple one level). Origin: Crucible handoff `../Crucible/docs/handoffs/FORGE_structural_yield_map_refresh.md` (2026-06-17), §3 + §5.1. Operator: relayed the handoff at max effort, then *"What's the durable long term option let's just do that."*

**Validate-first (the handoff asked for it; it changed the plan).** Re-derived against current code + the LIVE registry (`registry_snapshot_2026-06-18T010003Z.json`):
- The "yield map" Crucible weights against = Forge's D105/D106 component-rate reward (`feedback/rejection_weights.py`) consumed by `enumeration/sampler.py`. Current keys: `(hyp, dte_bucket)` (D105) + `(hyp, directional, dte_bucket)` (D106) + underlying class/name + H4. **Cohort, rank_signal, regime_gate are NOT weighted today** — the handoff's "one granularity too coarse" is correct.
- **Stale-narrative correction (in the handoff's favour):** Forge's own D118/D125 log says *"mean_reversion never ranks."* The LIVE registry has since flipped mr's bar indicators (`bb_pct, rsi_14, rsi_2, rv_rank`) to `rank_per_name_coherent=True` → the handoff's mr-xsect-rv_rank recipe IS emittable; no Crucible flag flip needed (my first hypothesis, refuted by the registry — the trust-the-live-registry lesson, [[indicator-thresholds-doc-stale-pre-d031]]/[[crucible-registry-publisher-oneshot]]). Verified every recipe the handoff names respects the rank-exclusion flags (excluded `iv_rank`/`gamma_flip`/dealer/per-name-calendar are correctly kept single-name).

**Decision — cohort axis first (increment 1 of 3).** New `compute_cohort_yield_weights` → `dict[(hyp, directional, dte_bucket, cohort), float]`, cohort ∈ {`single`(confluence), `xsect`(cross_sectional_rank)} via `_cohort_of(combiner.type)`. Reuses the D105/D106 engine: `_component_rate_sums` (component-rate estimand, version-scoped D081) → `_hierarchical_posteriors` anchored on the **D106 triple** (`key[:3]`) — zero cohort-specific evidence reproduces the triple, so the fallback chain cohort→triple→share is scale-coherent. The sampler's final cohort draw (H1, D109) is made yield-driven by `_cohort_xsect_probability`: `p_xsect = w_xsect/(w_xsect+w_single)`, clamped to `[0.05, 0.95]` (`_COHORT_EXPLORATION_FLOOR`, the D067 principle on the cohort axis); falls back to the fixed `rank_combiner_share` when the cohort map is absent/empty or has no evidence for the recipe's triple.

**Why cohort first (sequencing).** §3 is *"the single most important reallocation"* — the largest within-stratum yield axis (xsect momentum 40.4% vs single-name 0.96%, a 40× flip the pair/triple can't express). It is also the structurally cleanest: the cohort draw is LAST in `sample_config`, so `(hyp, directional, bucket)` is fully determined when it fires → the yield weight attaches there with **zero draw-reordering** (the D108 attachment discipline). And it is monoculture-safe: a WITHIN-hypothesis reallocation (single↔xsect for a fixed hypothesis) that never shifts the cross-hypothesis mix — that axis lives in the hypothesis weights, which is where the [[promotion-gate-tiers-and-constraint]] T3a worst-quartile/regime work belongs. **Increments 2–3 (deferred):** (2) the regime_gate axis — needs the D119 causality check per cohort first, though the relevant gates live on rank/composable runner paths that DO evaluate them (unlike the frozen rv pairs path), so likely safe; (3) the cross-hypothesis regime-adjustment — gated on Crucible's worst-quartile regime label (the operator's in-flight `PROMPT_CRUCIBLE_REFIT_PRIORITY_AND_WORSTQ_REGIME.md`).

**Honest scope (unchanged from the handoff / D105 §5).** This buys more/cheaper COMPONENTS for portfolio assembly, NOT promotions — the WF/cpcv wall is a strategy-space property, not an allocation one. It re-routes wasted single-name compute on rank-eligible recipes to the minting cross-sectional cohort; it does NOT touch the (excluded-indicator) single-name component factory that produces most of Forge's components.

**Emission proof (live export 10,000 gated ⋈ `/tmp` `forge.db` snapshot, current-version v22-scoped; not committed).** 47 cohort cells learned, 15 with both cohorts present. The §3 headline reproduces on Forge's OWN data: `trend|momentum_252|swing_long` single **0 comp/839 decided** vs xsect **62/411** → weight **0.004 → 0.161** (p_xsect→0.95 clamped); `trend|returns_12m_skip1|swing_long` single **0/534** vs xsect **45/330**. Every comparable rank-eligible recipe tilts to xsect (single-name versions of these bar-signal recipes mint ~0). So flag-on redirects the ~800+-per-cell single-name backtest waste toward the ~15%-minting cross-sectional cohort, surgically (rank-eligible draws only).

**§6 of the handoff (meta-king oracle objective, min_margin→p_component) — HELD, no Forge change.** Crucible flags it as a deliberate reversal of the same-day [[D180]]/[[D181]] min_margin adoption. Decision: don't flip unilaterally; fold into the §20 ΔM-campaign outcome (which gates component-reach for EITHER objective — both kings are §20-DSR-blocked now, so the choice is moot until §20 deploys, and the 519 M-cohort fired today is mid-accumulation for exactly that campaign). The objective is a Crucible-side republish + a one-line Forge floor re-tune (the no-cache reader auto-adopts, [[D174]]); no urgency.

**Hard rules.** #1 untouched (no rule/grammar change). #3 — no gate change, enumeration scope only. #4 — n/a (operator-directed feedback module like D101/D105/D108, not a refiner loosening). #5 — deterministic Python (pure function of submissions ⋈ gated snapshot). #6 — the cohort map is an ADDED sampler input; flag-OFF and empty-input paths are byte-identical, pinned by a **golden hash sequence captured from the pre-refactor sampler** (`test_cohort_yield_cold_start_byte_identical`) + the `test_cohort_yield_flag_off_byte_identical` invariant. #8 — blessed sources only (file-based gated export + `db_connection`). #10 — n/a (no grammar bump).

**Anti-Goodhart (the D105-lineage regression).** Keyed on the component-rate estimand (components, never raw trades); `test_component_count_drives_weight_not_trades_anti_goodhart` pins that a busy-but-componentless cohort does not out-weigh a minting one.

**Verification (TDD, RED→GREEN).** `tests/unit/test_feedback/test_cohort_yield.py` (9: empty→{}, cohort separation, the 40× flip, hierarchical shrink toward triple, anti-Goodhart, D081 version downweight, cold-start drop, absent-cohort omission, determinism) + 5 sampler tests (`_cohort_xsect_probability` yield-driven+clamped / fixed-share fallback / zero for non-rank-hyp; cold-start golden byte-identical; end-to-end tilt both directions) + 1 invariant. **Feedback+enumeration+invariants 695/0; CLI 65/0; mypy --strict clean (changed files); ruff + format clean (changed files only, [[ruff-format-scope]]).**

**Build location + deploy.** Built in the LIVE tree (the flag-OFF-byte-identical property IS the D104 guard, per [[D108]]): the systemd unit has no `--cohort-yield`, so a reboot on the uncommitted code changes nothing (loader skipped → fixed share). Deploy is the operator's two-step: (1) uncontended suite + commit + restart (still byte-identical, code landed); (2) add `--cohort-yield` to the unit + restart to A/B. Forge cannot run the uncontended suite or self-restart — both the operator's.

**Files:** `src/forge/feedback/rejection_weights.py` (`_cohort_of`, `compute_cohort_yield_weights`), `src/forge/enumeration/sampler.py` (`_COHORT_EXPLORATION_FLOOR`, `_cohort_xsect_probability`, `cohort_yield_weights` param + draw refactor), `src/forge/enumeration/iterator.py`, `src/forge/cli/main.py` (`_load_cohort_yield_weights`, `_format_cohort_yield_weights_line`, `--cohort-yield` flag + loader block + threading), `tests/unit/test_feedback/test_cohort_yield.py` (new), `tests/unit/test_enumeration/test_sampler.py`, `tests/invariants/test_phase2_invariants.py`, `STATUS.md`, this entry.

**References:** [[D106]] (the hierarchical triple this extends + `_directional_indicator_of`), [[D108]] (the A/B-flag + attachment-discipline pattern this mirrors), [[D105]] (the component-rate engine), [[D109]] (the H1 cohort draw this makes yield-driven), [[D118]]/[[D125]] (the rank-exclusion flags + the stale "mr never ranks" narrative the live registry corrects), [[D119]] (the regime-gate freeze that scopes increment 2's causality check), [[D067]] (exploration floor), [[D104]] (live-tree/flag guard), [[promotion-gate-tiers-and-constraint]] (the cross-hypothesis monoculture axis this deliberately does NOT touch), Crucible `FORGE_structural_yield_map_refresh.md`, hard rules #1/#3/#5/#6/#8.

**STATUS: BUILT + VERIFIED; flag defaults OFF (byte-identical); deploy + flag-flip operator-gated. Increments 2–3 + the §6 oracle decision are follow-ups (the latter Crucible-side).**

---

## D183 — 2026-06-17 — Regime-gate-yield axis (Crucible's 2026-06-17 yield-map refresh §2/§4): the regime draw composes a learned (hyp,dir,bucket,regime) component-rate onto the D150/uniform base — down-weighting sink gates (gamma_flip), excluding relative_value (D119). Versionless feedback, A/B-flagged `--regime-gate-yield`, default OFF. BUILT + VERIFIED; deploy/flag-flip operator-gated.

**Spec section:** §6.3/§8 feedback weighting; the D105/D106/[[D182]] hierarchical lineage; [[D119]] (the freeze this scopes around) + [[D150]] (the mr ranging-bias this composes with). Origin: `../Crucible/docs/handoffs/FORGE_structural_yield_map_refresh.md` §2/§4. Increment 2 of 3 ([[D182]] = increment 1 cohort; increment 3 = cross-hypothesis regime-adjustment, gated on Crucible's worst-Q label). Operator: *"Let's start increment 2."*

**D119 causality gate FIRST (the precedent demanded it).** D119 froze relative_value regime weighting because the `pairs_convergence` runner evaluates NO gate → gate↔yield was a sampling artifact. So before building, re-derived the within-triple regime spread on a live `/tmp` `forge.db` snapshot ⋈ 10k gated export (v22-scoped, non-rv): **REAL but concentrated.** `trend|momentum_252|swing_long` mints hurst **8.1%** / adx 5.4% / rv_rank 4.9% / **gamma_flip 0.0% (0/260)** — an 8.1pp spread, the §4 "gamma_flip regime gate is a near-universal yield sink" replicating on Forge's own data. Most other triples are flat-at-zero (dead in every regime → no signal, correctly left alone). **Causality holds** because non-rv runners (composable_long_options / cross_sectional_rank, D118) DO evaluate the gate; rv stays excluded. **Complementary to [[D182]], not redundant:** gamma_flip is rank-excluded → its configs are ALWAYS single-name → the cohort axis can't touch them; only the regime axis can down-weight the gamma_flip trend-regime sink.

**Decision.** New `compute_regime_gate_yield_weights` → `dict[(hyp, directional, dte_bucket, regime_gate), float]` via `_regime_indicator_of`, anchored on the D106 triple (`key[:3]`), **excluding relative_value** (D119 — key_of returns None for rv). The sampler's regime draw (`_pick_regime`, reached from `_select_bucket_directional_regime` where dir+bucket are known — the H4 slice discipline) now COMPOSES the sliced `{regime: posterior}` onto the base: `weight[r] = base[r] * max(posterior[r], floor)` where `base` is the D150 ranging-bias for mean_reversion (>1 gate) else uniform 1.0.

**Why COMPOSE, not replace (the load-bearing design choice).** A dead triple's regime posteriors are ~equal → `base * posterior` stays proportional to `base` → the deliberate D150 ranging-bias (a diversity lever for the worst-quartile ranging complement) is **preserved, refined by evidence where it exists, never silently discarded**. A minting triple modulates `base` by component rate (down-weighting the sink). **Floor-placement bug caught in TDD:** flooring the *product* (`max(base*posterior, floor)`) clobbered the D150 ratio (base*rate < floor for component-rate-scale posteriors) → flattened mr to uniform. Fixed to floor the *posterior* (`base * max(posterior, floor)`, the D103 floor scale) — keeps a sink explorable (D067) without flattening base. Pinned by `test_pick_regime_learned_preserves_d150_on_dead_triple`.

**Scope boundary (honest).** Cohort is deliberately NOT in the regime key: the regime is drawn BEFORE the cohort in `sample_config` (cohort eligibility depends on ALL signals incl. the regime gate, so the order is forced), so the regime cannot be conditioned on the cohort — the quad is **cohort-blended**. Consequence: the handoff's mr-XSECT-rv_rank regime preference (§2, the decorrelating ranging payer) is NOT captured here (mr is single-dominated in the blend → near-flat) — that needs a cohort-conditioned regime, i.e. the cohort-reorder / increment-3 work. This increment captures the cohort-independent regime lift (the gamma_flip sink avoidance is the clear win) and the general "draw the minting regime gate" mechanism.

**Emission proof (live export 10k ⋈ `/tmp` snapshot, v22-scoped; not committed).** 116 regime cells learned; **0 relative_value cells** (D119 guard confirmed). The minting trend triple: hurst **0.0871** > rv_rank 0.0612 > adx 0.0596 > market_state 0.0490 > **gamma_flip 0.0088** (~10× below hurst). Composed in the sampler, gamma_flip's posterior (0.0088 < floor 0.01) floors to 0.01 → down-weighted ~9× vs hurst but kept explorable. So flag-on stops the sampler wasting trend-regime draws on the gamma_flip sink. Honest scope unchanged ([[D182]]): more/cheaper COMPONENTS, not promotions.

**Hard rules.** #1 — no rule/grammar change (weights re-draw WITHIN the §3.5 R-rule pool). #3 — no gate change. #5 — deterministic Python. #6 — added sampler input; flag-OFF and empty-input byte-identical, pinned by a **golden pre-refactor sequence** (`test_regime_gate_yield_cold_start_byte_identical`) + the `test_regime_gate_yield_flag_off_byte_identical` invariant. The `_pick_regime` refactor preserves the rng path when learned is empty (D150 → `rng.choices(base)`, uniform → `rng.choice`). #8 — blessed sources. #10 — n/a.

**Anti-Goodhart.** Component-rate estimand (components, never trades); `test_component_count_drives_weight_not_trades_anti_goodhart`.

**Verification (TDD, RED→GREEN).** `tests/unit/test_feedback/test_regime_gate_yield.py` (9: empty→{}, regime separation, gamma_flip-sink down-weight, **rv-excluded D119 guard**, hierarchical shrink, anti-Goodhart, D081 version downweight, cold-start drop, determinism) + 5 sampler/`_pick_regime` tests (sink down-weight, **D150-preserved-on-dead-triple**, rv-never-composed, cold-start golden, end-to-end tilt) + 1 invariant. **Feedback+enum+invariants+CLI 775/0; mypy --strict clean; ruff + format clean (changed files only).**

**Build location + deploy.** Live tree; flag-OFF-byte-identical is the D104 guard (the unit has no `--regime-gate-yield`). Operator's two-step deploy, same as [[D182]]: (1) uncontended suite + commit + restart (byte-identical), (2) add the flag to the unit + restart to A/B. Forge runs neither step.

**Files:** `src/forge/feedback/rejection_weights.py` (`compute_regime_gate_yield_weights`), `src/forge/enumeration/sampler.py` (`_pick_regime` compose + `regime_gate_yield_weights` thread + slice), `src/forge/enumeration/iterator.py`, `src/forge/cli/main.py` (`_load_regime_gate_yield_weights`, `_format_regime_gate_yield_weights_line`, `--regime-gate-yield` + loader block + threading), `tests/unit/test_feedback/test_regime_gate_yield.py` (new), `tests/unit/test_enumeration/test_sampler.py`, `tests/invariants/test_phase2_invariants.py`, `STATUS.md`, this entry.

**References:** [[D182]] (increment 1, the cohort axis + the pattern this mirrors), [[D119]] (the rv regime-freeze this scopes around — rv excluded), [[D150]] (the mr ranging-bias this composes with, not replaces), [[D106]] (the hierarchical triple anchor + `_regime_indicator_of`), [[D103]] (the regime-draw mechanism + `_REGIME_EXPLORATION_FLOOR`), [[D118]] (the runner-path map establishing non-rv gate causality), [[D067]] (exploration floor), [[promotion-gate-tiers-and-constraint]] (the worst-Q/ranging diversity D150 serves, which the compose-not-replace choice protects), Crucible `FORGE_structural_yield_map_refresh.md`, hard rules #1/#3/#5/#6/#8.

**STATUS: BUILT + VERIFIED; flag defaults OFF (byte-identical); deploy + flag-flip operator-gated. Increment 3 (cohort-conditioned / cross-hypothesis regime-adjustment, needs Crucible's worst-Q label) + the §6 oracle decision remain follow-ups.**

---

## D184 — 2026-06-17 — Yield-map refresh increment 3 INVESTIGATED → SKIPPED (Crucible concurs); cohort×regime interaction (3a) REFUTED on Forge's honest data, 3b (worst-Q decorrelation) not pursued → increments 1+2 are the final realization and were DEPLOYED. Investigation DOCS-ONLY; the deploy is [[D185]].

**Spec section:** §6.3/§8 feedback weighting; closes the [[D182]]/[[D183]] yield-map-refresh arc. Origin: operator *"Let's finish increment 3 so all three land in one deploy."* The validate-first probe (the D119/D171 discipline) refuted the buildable half before any code, so this is a DOCS-ONLY investigation + a deliberate hold.

**The probe (live `/tmp` `forge.db` snapshot ⋈ 10k gated export, v22, honest-coverage, non-rv).** Full `(hypothesis, cohort, regime)` component rates, asking whether the cohort×regime JOINT carries signal the increment-1 (cohort) + increment-2 (regime) marginals miss:
- **mean_reversion: 0/1901 honest components — zero in EVERY cohort×regime cell.** `mr-xsect-rv_rank = 0/328 = 0.0%`, NOT the handoff's 17–19%. That figure is a Crucible-DB number reflecting **dishonest-coverage components** (D124/D128 — the 94% unverified-admission noise) + the **D172 `regime_coverage` admission-gate lockout** of options-derived mr. It is a Crucible-side admission property, **not a Forge allocation lever** — Forge's sampler cannot mint what Crucible's gate rejects.
- **trend_continuation (the only minting hypothesis): the cells are ADDITIVE, not interactive.** single = 0.0% in every regime; xsect = hurst 8.6% > rv_rank 7.3% > adx 6.2%. That is exactly the cohort marginal ([[D182]]) plus the within-xsect regime tilt ([[D183]], whose emission proof already ranks trend hurst 0.087 > rv_rank 0.061 > adx 0.060). **No residual interaction.**

**3a (cohort-conditioned regime via draw-reorder) — REFUTED, NOT built.** Capturing a cohort×regime interaction needs the cohort drawn before the regime (the cohort-eligibility check reads the regime gate, so the order is otherwise forced) — a global draw-reorder, the single highest-risk change in the effort (breaks sampler determinism for every config, even flag-gated it's a parallel CSP). The probe shows **zero verified payoff** for it on Forge's honest data, and the only "prize" (mr-xsect-rv_rank) is dishonest-coverage we deliberately exclude. Building it would be the D119/D171 anti-pattern (chasing an artifact). **Shelved**; re-open trigger = Crucible relaxes the mr `regime_coverage` admission gate AND mr-xsect-rv_rank mints honest components on Forge.

**3b (cross-hypothesis worst-Q decorrelation) — the genuinely valuable increment 3, BLOCKED.** Increments 1+2 are WITHIN-hypothesis by construction; they deliberately do not touch the cross-hypothesis mix (the hypothesis weights), which is where the trend monoculture / worst-quartile (BEAR/RANGING) promotion threat lives ([[promotion-gate-tiers-and-constraint]] T3a). 3b would weight component-yield by its worst-quartile regime-decorrelation contribution so throughput tilts toward the decorrelating complement instead of raw count (which favours trend). It needs **Crucible's worst-Q regime label** — the operator's in-flight relays (`PROMPT_CRUCIBLE_WORST_QUARTILE_REGIME_LABEL.md` / `..._REFIT_PRIORITY_AND_WORSTQ_REGIME.md`), with **no response handoff and no label artifact** as of this entry. Its exact shape (per-component regime attribution vs a per-cell regime-lift score) waits on what the label provides.

**Disposition (operator + Crucible, 2026-06-17): SKIP increment 3, DEPLOY 1+2.** The initial AskUserQuestion answer was "hold for the worst-Q label," but Crucible then advised skipping increment 3 and the operator confirmed — *"Crucible suggests we skip it. let's deploy 1+2."* So 1+2 are the final, complete realization of the handoff and were deployed live ([[D185]]: flags `--cohort-yield` + `--regime-gate-yield` added to the unit; D104 ritual). **3a stays shelved** (re-open trigger: Crucible relaxes the mr `regime_coverage` admission gate AND mr-xsect-rv_rank mints honest on Forge). **3b is not abandoned but no longer gates this deploy** — it remains the natural next decorrelation lever if/when Crucible ships a worst-Q regime label, pursued separately.

**Handoff §5 coverage (for the record):** §5.1 axes all weighted — hypothesis (D105) · rank_signal/directional (D106) · cohort (D182) · regime_gate (D183); the joint cohort×regime interaction is the only uncaptured piece, and it has no Forge-side signal (this entry). §5.2 sinks floor-weighted — gamma_flip gate (D183) · single-name momentum→xsect (D182) · single-name rsi_2 mr (mr mints 0 → moot; D106 directional weighting covers the directional axis). So the handoff is fully realized by 1+2; 3b is the operator's decorrelation EXTENSION beyond it.

**Files:** `STATUS.md`, this entry. **No code, no test, no grammar change.**

**References:** [[D182]] (increment 1 cohort), [[D183]] (increment 2 regime_gate), [[D172]] (the mr `regime_coverage` admission-gate lockout this confirms), [[D124]]/[[D128]] (honest-coverage — why the handoff's mr 17–19% doesn't replicate), [[D119]]/[[D171]] (the validate-first / flat-axis precedents this follows), [[promotion-gate-tiers-and-constraint]] (the worst-Q decorrelation 3b serves), Crucible `FORGE_structural_yield_map_refresh.md` §2/§5.

**STATUS: increment 3 investigated → SKIPPED (Crucible concurs); 3a refuted+shelved, 3b deferred (not gating). Increments 1+2 = the final yield-map-refresh realization, DEPLOYED ([[D185]]).**

---

## D185 — 2026-06-17 — Yield-map refresh increments 1+2 DEPLOYED to the live service (D104 ritual): `--cohort-yield --regime-gate-yield` added to the unit; a loop-path wiring bug CAUGHT in journal verification + FIXED before the axes were truly live. Both axes now active in the journal. PRODUCTION CHANGE.

**Spec section:** §8 deploy / D104 ritual; lands [[D182]] (cohort) + [[D183]] (regime-gate), [[D184]] disposition (increment 3 skipped). Operator: *"Crucible suggests we skip it. let's deploy 1+2."*

**Deploy (deploy.md / D104).** Edited the version-controlled unit `deploy/systemd/forge.service` (symlinked into `~/.config/systemd/user/`) — added `--cohort-yield --regime-gate-yield` to ExecStart (default-OFF in code, so the unit flags are the A/B switch; removing either reverts that axis to byte-identical). Ritual: stop (`exit 143` = normal `--loop` SIGTERM) → full uncontended suite → commit → `daemon-reload` → `reset-failed` → start. Commit `9a1ca33` (feature + unit), suite **1684 passed**.

**The catch (why journal verification matters, not just restart health).** The first restart came up clean on every D104 signal — NRestarts=0, `grammar_version=v22`, `registry_loaded_from_export`, ExecStart carrying both flags, no traceback. But the journal showed `trade_rate_priors` emitting **2 s after `rank_combiner_share`** with **no `cohort_yield_weights:` / `regime_gate_yield_weights:` line between them** — too fast for two export-reading loaders to have run. Root cause: the two flags were wired only into the **single-iteration** `_run_one_iteration` call site (12-space indent); the **`--loop`** call site the daemon uses (20-space indent, inside `while`+`try`) was missed — `replace_all` matches identical whitespace, so "all occurrences" of the 12-space block was just the one. A missing kwarg **silently defaults to False** (byte-identical), so the daemon ran both axes INERT while the unit, the restart, the CLI tests, and mypy all looked green. **Fix** (`cf9b65c`): forward both flags in the loop-path call + a regression test (`test_loop_forwards_yield_map_flags_to_iteration` — asserts `--loop` forwards them True, and defaults False). Suite **1685 passed**; redeploy (stop → suite → commit → restart).

**Live verification (the real proof — D104 "first unblocked iteration").** New MainPID 2702548, **ActiveEnter 2026-06-18T03:23:33Z**, NRestarts=0, ExecMainStatus=0, no errors. Journal (03:24Z) now emits both axes on the live weight-load: `cohort_yield_weights: 48 cells learned; top trend_continuation×momentum_252×swing_long×xsect=0.157` (the 0/839→62/411 single→xsect reallocation, [[D182]]) and `regime_gate_yield_weights: 118 cells learned; top …×hurst=0.087 …×rv_rank=0.083` (gamma_flip down-weighted, [[D183]]), followed by `trade_rate_priors` (sequence complete). Both loaders return non-empty on live data, matching the emission proofs (47/116 cells).

**Lessons.** (1) `replace_all` is whitespace-exact — indentation-divergent duplicate call sites need per-site edits or a verifying grep (`grep -c` both sites). (2) A deploy is not verified by restart health alone — a flag can be set on the unit yet inert; confirm the FEATURE engages in the journal (the change-specific line), because a missing kwarg defaults silently and stays byte-identical. (3) The default-OFF/byte-identical design meant the bug was harmless (daemon ran the prior behavior), not a production incident — the A/B-flag discipline contained it.

**Honest scope (unchanged).** Buys more/cheaper COMPONENTS for assembly, not promotions (the WF/cpcv wall is strategy-space). Crucible watches the submission-mix convergence (handoff §7): trend-xsect + minting-regime share up, single-name-momentum + gamma_flip-gate share down; promote-rate NOT expected to move.

**Files:** `deploy/systemd/forge.service` (9a1ca33), `src/forge/cli/main.py` + `tests/unit/test_cli/test_run_loop.py` (cf9b65c), `STATUS.md`, this entry. Tree: my work committed; the operator's in-flight `PROMPT_CRUCIBLE_*` / `FORGE_THROTTLE_*` left uncommitted (theirs).

**References:** [[D182]]/[[D183]] (the axes deployed), [[D184]] (increment 3 skipped), [[D104]] (the ritual + the dirty-tree-reboot lesson), [[D108]] (the A/B-flag-off-byte-identical guard that contained the bug), Crucible `FORGE_structural_yield_map_refresh.md`.

**STATUS: increments 1+2 LIVE (cohort + regime-gate yield active in the journal); NRestarts=0, no errors. Increment 3 skipped. Yield-map-refresh arc COMPLETE + deployed.**

---

## D186 — 2026-06-18 — Decorrelation-proxy experiment → VERDICT: decorrelation belongs at ASSEMBLY (Crucible), not generation; the generation layer owns QUALITY + directional variety. Free structural proxy too weak; per-recipe map NOT warranted. RESEARCH + Crucible handoff — no production-loop change.

**Spec section:** Crucible `FORGE_generation_model_plan.md` §2 (quality×decorrelation objective), §3 (proposed per-recipe decorrelation map), §8.2 (joint-oracle question). Answers where the [[D184]] "3b worst-Q decorrelation lever (deferred, no Crucible label)" actually lives. Operator frame: *"how do we use an ML model for strategy generation."*

**The question.** The plan proposes a dual generation objective `quality × decorrelation`. Quality is already learned ([[D105]]/[[D106]]/[[D114]] component-rate posteriors); decorrelation is not — Forge has zero return/pairwise data (Crucible scores strategies independently, exports per-strategy scalars only). Two ways to feed a decorrelation signal into generation: (a) a FREE structural proxy Forge computes from the config alone, or (b) Crucible builds a per-recipe decorrelation map. Decide by testing whether the proxy predicts realized PnL correlation.

**Experiment (`scripts/decorrelation_proxy_alignment.py`, offline/read-only/deterministic).** X = pairwise structural distance = Jaccard over signal INDICATOR-ID sets, per role (params dropped — PREFLIGHT caught that `content_key` saturates at distance 1.0, zero variance). Y = Crucible's realized daily-PnL correlation, a one-off SAMPLE asked for in `PROMPT_CRUCIBLE_DECORRELATION_PROXY_SAMPLE.md` → delivered `~/optbt_data/exports/decorrelation_proxy_sample_20260618T235737Z.json` (1000 pairs / 70 configs, 810 broad×broad, 100% hash-resolved; standalone-PnL union-calendar flat=0 = generation-time-faithful; parity soft_joint standalone −0.069 vs joint −0.038, same conclusion).

**Findings (broad×broad n=810, by Crucible cohort tags; calm → stress[bear+high_vol]).**
- **Decorrelation is ABUNDANT in broad×broad:** mean |corr| 0.098 → 0.124. Good broad components already decorrelate from each other almost regardless of structure (the cross-sectional construction buys it). Decorrelated SUPPLY is not scarce.
- **The proxy is WEAK but correctly signed,** concentrated in ONE feature: directional-indicator distance Spearman −0.195 (calm) / **−0.228 (stress)**; all-indicator −0.114; **regime-gate distance is noise (−0.024)**. Strongest in the stress quarter the cpcv-p25 gate scores (good), but weak in magnitude.
- **Mild stress re-coupling:** mean |corr| +0.026 in stress (~63% of pairs higher; frac |corr|>0.3 ~12%→~15% on the first-pass subset), concentrated on same-directional pairs.
- **The residual decorrelation variance is PER-PAIR, not per-recipe** (realized name/beta overlap) — invisible to a generation-time proxy AND to a per-recipe map.
- **Cohort-definition divergence (side-finding):** 62/70 configs agree, but 8 `confluence`-combiner configs that Forge labels `single` (by `combiner.type`) Crucible tags `xsect` — Crucible's cohort = execution breadth, not combiner type. Verdict robust to the definition (the tool now segments by the sample's tags; numbers barely move). FLAG for [[D182]] (cohort-yield keys on combiner.type).

**Decision.** **Decorrelation is owned at ASSEMBLY (Crucible), not generation.** Crucible has the real pairwise correlations at assembly time — the per-pair signal that matters — so the §8.2 `quality × decorrelation` objective lives in assembly selection, NOT Forge's sampler.
- **No Forge-side decorrelation-yield sampler axis** (the would-be "Option A"): the generation-time signal is too weak and the wrong granularity (per-recipe can't capture per-pair).
- **Crucible's full per-recipe map is NOT warranted** — recommend a cheap directional-diversity guardrail at assembly (don't pair same-directional legs), measure assembled-book lift, revisit the map only if the ~12–16% correlated tail proves binding.
- **The generation layer = QUALITY + a varied menu:** (1) mint strong component-grade legs sharpened toward the binding WF-median CENTER gate — *this is where generation-layer ML belongs: a QUALITY model (P(component-grade)), not a decorrelation model*; (2) hold directional-indicator / hypothesis variety as a light floor so assembly has decorrelated-strong pairs to pick (already partly via [[D103]]/[[D136]] + the diversifier); (3) push the quality frontier into under-served hypotheses (strong MR/relval/vol_event) — a GRAMMAR problem (operator-gated rule edits), not ML.

**Alternatives considered.** (a) Build the decorrelation-yield axis now — rejected (weak proxy, wrong granularity, decorrelation already abundant). (b) Commission the full per-recipe map — deferred (per-recipe can't capture per-pair residual; near-saturated axis). (c) Heavy generative model conditioned on the pool — rejected (doesn't escape the grammar ceiling; determinism burden, hard rule #6/#8).

**Caveat.** n=70 configs (good broad components, v9–v22) — the right population for assembly but small; SIGNS and stress-strengthening are robust, magnitudes may be attenuated by a homogeneous set. "Abundant decorrelation" is a direct measurement, holds regardless.

**Files:** `scripts/decorrelation_proxy_alignment.py` + `tests/unit/test_decorrelation_proxy.py` (new; ruff clean, 10/10), `PROMPT_CRUCIBLE_DECORRELATION_PROXY_SAMPLE.md` (the ask), `STATUS.md`, this entry. NO `src/forge/` / grammar / feedback change → not a deploy, no production-loop impact. The operator's in-flight `PROMPT_CRUCIBLE_*` / `FORGE_THROTTLE_*` left uncommitted (theirs). Crucible writeback (verdict + §8.2 answer) pending operator go.

**References:** Crucible `FORGE_generation_model_plan.md` + `decorrelation_proxy_sample_20260618T235737Z.json`; [[D184]] (3b worst-Q decorrelation — this answers where it lives), [[D105]]/[[D106]]/[[D114]] (the quality machinery generation keeps), [[D182]]/[[D183]] (yield-map axes the rejected Option A would have mirrored; cohort-definition flag).

**STATUS: VERDICT recorded — decorrelation → assembly (Crucible); generation = quality + directional variety; no Forge decorrelation axis; per-recipe map not warranted. Tooling committed; Crucible writeback pending operator go.**

---

## D187 — 2026-06-18 — WF-quality probe → the generation-layer QUALITY model is VIABLE: rich king features predict honest WF (IC +0.27), coarse cells don't (~0). Greenlights folding King into the standard path (re-target M → WF) + a WF-p95 refit-label ask. RESEARCH; no production-loop change.

**Spec section:** Crucible `FORGE_generation_model_plan.md` — the *quality* half; companion to [[D186]] (which placed *decorrelation* at assembly). Operator: re-target the generation quality model to WF on broad targets; retire the King lane into the standard submission path.

**The question.** [[D186]] left QUALITY as the generation layer's job. Is it learnable at generation time — and does King's machinery transfer to a WF target (the prerequisite for folding King in)? A coarse-cell check first showed `(hypothesis, directional, dte)` ~zero-predicts honest WF-median (LOO Spearman −0.03) — WF quality is idiosyncratic at the recipe level.

**Probe (`scripts/wf_quality_probe.py`, offline/read-only).** Reuses `king/featurize.py` (rich features: param numerics, indicator/exit/signal-type one-hots, combiner categoricals), a pure-python ridge (no numpy in env) + 5-fold CV, out-of-fold Spearman = IC. Same harness, two targets on 1700 honest broad components / 36 features:
- **`cpcv_p25` = +0.44** (SANITY — beats the D155 tail model's +0.35, validates the pipeline).
- **`wf_median` = +0.27** (THE QUESTION — λ-robust across 1/10/100).

**Findings.**
- **Quality IS predictable at generation time — but only from RICH features.** Coarse recipe cells: −0.03 (dead). Rich king features: **+0.27** on honest WF-median. The signal lives in params/underlying/indicator structure, not the (hyp,dir,dte) cell.
- **The two probes now fully locate Crucible's `quality × decorrelation`:** decorrelation → ASSEMBLY ([[D186]], per-pair, Forge-blind), quality → GENERATION (this, rich-feature-predictable). Clean partition.
- **King-retirement de-risked.** King's featurizer+ridge transfer to a WF target → folding King into the standard path = re-targeting its machinery **M → WF on the broad cohort**, now evidence-backed.
- **WF-median is the *noisy* statistic** (+0.27 vs cpcv-p25's +0.44 on identical features) → a sharper WF statistic likely predicts better. Operator chose **WF-p95** (the ceiling) as the real target — fits the assembly *peak-tiling* logic (mint high-ceiling broad components; assembly stitches complementary peaks). p95 isn't in Forge's export (only `walk_forward_sharpe_median`) → requested from Crucible's refit lane (`PROMPT_CRUCIBLE_WF_P95_REFIT_LABEL.md`).

**Decision / next.**
- **Quality model = viable**, buildable on WF-median today (+0.27, no Crucible dep); upgrade the target to WF-p95 if `IC(p95) > IC(median)` (Crucible label requested).
- **Retire the King lane** into the standard submission path (operator directive) — its own operator-gated increment (separate oracle/search/DB/CLI, §20-blocked, paced fires; loop-touching → plan + deploy ritual + a [[meta-king-arm-status]] memory update). The folded-in lane = King's rich-feature ridge re-targeted to WF; do NOT fix the plug-in point (ranker prior à la [[D149]]/F3 vs replace-the-arm) until the target (median vs p95) is set.
- **Honest scope:** +0.27 is a *steering* lever (baseline prior ~+0.12, cpcv tail model +0.35), not a wall-breaker. No single broad component clears WF-median 2.0; the promotion path stays assembled-peaks.

**Alternatives considered.** (a) Coarse-cell / sampler-yield quality axis — rejected (−0.03; WF quality isn't a recipe property). (b) Conclude quality is unpredictable (as decorrelation was Forge-blind) — refuted (rich features +0.27). (c) Build on WF-median now vs wait for p95 — deferred to the King-fold increment once the target is set.

**Files:** `scripts/wf_quality_probe.py` + `tests/unit/test_wf_quality_probe.py` (new; ruff clean, 6/6), `PROMPT_CRUCIBLE_WF_P95_REFIT_LABEL.md` (the label ask, operator-relayed), `STATUS.md`, this entry. NO `src/forge/` / grammar / feedback change → not a deploy. Operator's in-flight `PROMPT_CRUCIBLE_*` / `FORGE_THROTTLE_*` left uncommitted (theirs).

**References:** [[D186]] (decorrelation → assembly; the companion half), [[D155]] (the cpcv-p25 tail model, +0.35, that the +0.44 sanity reproduces), `king/featurize.py` + `king/score.py` (the reused machinery), [[meta-king-arm-status]] (the arm being retired), `FORGE_generation_model_plan.md`, `PROMPT_CRUCIBLE_REFIT_PRIORITY_AND_WORSTQ_REGIME.md` (the refit lane the p95 label rides).

**STATUS: quality model VIABLE (rich features → honest WF +0.27); King-retirement greenlit (re-target M→WF, own increment); WF-p95 refit label drafted for operator relay. Tooling committed.**
