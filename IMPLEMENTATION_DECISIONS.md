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
