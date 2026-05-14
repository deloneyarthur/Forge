# Forge — Open Questions

Append-only. Each entry: date, question, what I did instead, severity (low / medium / high).
Operator reviews at every phase boundary.

---

## 2026-05-13 — Q7 — Grammar fields missing from `crucible_contracts.StrategyConfig` — **HIGH SEVERITY, BLOCKING PHASE 1**

**Question:** The §3.5 grammar rules reference fields that do not exist on `crucible_contracts.StrategyConfig` / `SignalSpec`. How should these be carried?

**What's missing (cross-referenced spec rule → contracts field):**

| Spec rule cites | Spec field name | Contracts has? |
|---|---|---|
| S1 ("one hypothesis per strategy") | `hypothesis` ∈ {trend_continuation, mean_reversion, regime_arbitrage, relative_value, volatility_event, tail_hedge} | **NO** — no `hypothesis` field on `StrategyConfig` |
| S2 ("one directional signal") | `signals[*].role` ∈ {directional, regime_filter, filter, confluence} | **NO** — `SignalSpec` has only `id`, `type`, `indicators`, `params` |
| S3 ("at least one regime gate") | `signals[*].role == regime_filter` | **NO** (same as S2) |
| C1, C2 (family rules) | `signals[*].family` ∈ {trend, mean_reversion, volatility, iv_structure, dealer_positioning, flow, macro, calendar, fundamental, smart_money, pairs} | **PARTIAL** — `IndicatorMetadata.family` exists but uses a different 9-value enum: `mean_revert, price_trend, realized_vol, iv, macro, pairs, smart_money, multi_factor, dealer`. Spec lists 11 families; 3 don't exist in contracts (`flow, calendar, fundamental`); 1 contracts-only (`multi_factor`). Renaming conventions also differ (`mean_revert` vs `mean_reversion`, `price_trend` vs `trend`, etc.). |
| E1 (mandatory exits) | "Every strategy includes `expiry_exit`, `theta_cliff_exit`, `earnings_exit`" — **3 exits** | Contracts `MANDATORY_EXIT_IDS` has **4**: `expiry_exit, theta_cliff_exit, earnings_exit, **liquidity_exit**`. |

**What I did instead:** halted before any code lands. Phase 1 cannot proceed because:
- I can't write a `cardinality` predicate for `field: hypothesis` if `hypothesis` doesn't exist on the model.
- I can't write a `cardinality` predicate for `field: signals.role.directional` if `role` doesn't exist on `SignalSpec`.
- I can't write a `forbids` predicate referencing `signals.family` without a lookup convention.

**Severity:** **high** — structural blocker for Phase 1. Picking silently means either (a) inventing fields on a model the contracts package owns (violates hard rule #2), (b) shimming with `signals[*].params["role"]` strings (loose typing, will break refactors), or (c) deriving fields via lookups that the spec doesn't define.

**Options for the operator (numbered for reference in reply):**

1. **Extend `crucible_contracts`** (cleanest; treats this as the gap the kickoff anticipated):
   - Add `hypothesis: Literal[...]` to `StrategyConfig`.
   - Add `role: Literal["directional","regime_filter","filter","confluence"]` to `SignalSpec`.
   - Reconcile `IndicatorMetadata.family` enum with the §3.5 C1 family list (decide: 9, 11, or some merged set; pick canonical spellings).
   - Resolve E1 mandatory-exit count (3 vs 4; recommend accepting contracts' 4 since the contracts validator enforces it).
   - Bump `crucible_contracts` to **1.2.0** (additive: minor). Forge's `FORGE_EXPECTED_CONTRACT_VERSION` follows.

2. **Encode in `SignalSpec.params`** (no contracts change):
   - `hypothesis` lives on `StrategyConfig.signals[0].params["hypothesis"]` (or a separate top-level convention).
   - `role` lives on `signal.params["role"]`.
   - `family` is derived: `signal.indicators[0]` → `RegistrySnapshot.indicators` lookup → `IndicatorMetadata.family`.
   - Forge encodes/decodes via helpers; the grammar predicates use dotted paths into `params`.
   - Stringly-typed; refactors brittle; no validation that the params dict carries the expected keys.

3. **Forge-side annotation field** (least clean):
   - Forge submits configs with an extra `forge_metadata: dict` field that Crucible ignores. Hypothesis/role live there.
   - Violates the "no extra fields" extra="forbid" pydantic config on `StrategyConfig` — would require a contracts change too. So this collapses into option 1.

4. **Defer Phase 1 grammar to v1.1; ship a simpler grammar for v1.0** that only validates fields actually present on contracts (`dte_bucket`, `sizer.mode`, `signals[*].type`, `exits[*].id`, etc.). Loses S1, S2, S3, parts of C1, C2 — about 1/3 of the spec rules. The grammar becomes structurally weaker but immediately implementable.

**Recommendation:** option 1. The contracts package is explicitly named in PIPELINE.md §7 as "the integration boundary" and the kickoff anticipates "missing model or field — surface as a contracts gap." This is precisely that case. Minor version bump (1.1 → 1.2) is additive and won't break Crucible / QuantIQ.

**Note on family-list mismatch (sub-question if option 1 chosen):** the spec's `flow`, `calendar`, `fundamental` families aren't in contracts; contracts' `multi_factor` isn't in the spec. Pick the canonical list and align both sides. My read: spec list (11) is more domain-faithful; contracts is missing common categories. But this is a domain question.

**Surfaced 2026-05-13 by agent.** Awaiting operator decision before any Phase 1 code.

**Resolution 2026-05-13:** Operator chose **option 1** (extend `crucible_contracts` to v1.2.0) and **11-family canonical list** (spec's). See `IMPLEMENTATION_DECISIONS.md` D007 for the full resolution. Forge remains paused at Phase 1 kickoff until contracts v1.2.0 ships. Owner of the contracts change still TBD.

**Closure 2026-05-13:** `crucible_contracts` v1.2.0 shipped (`crucible_contracts/master` commit `7d0f359`). Forge bumped `FORGE_EXPECTED_CONTRACT_VERSION` to `"1.2.0"` (see D008). All v1.2.0 surface assertions pass against the installed package. Q7 closed; Phase 1 resumed.

---

## 2026-05-13 — Q8 — §3.5 R2 + C1 are jointly unsatisfiable under v1 family vocabulary — **HIGH SEVERITY, BLOCKING PHASE 2**

**Question:** §3.5 R2 ("trend_continuation strategies must include `adx` or `hurst` as a regime gate") combined with §3.5 C1 ("no duplicate indicator families in one strategy") and the contracts v1.1–1.3 family list (no `trend_strength`) creates a contradiction: any trend_continuation strategy with a trend-family directional plus adx/hurst as regime gate violates C1, because adx/hurst would also need to be `trend` family. The Phase 1 fixture (`tests/fixtures/strategy_configs.py`) worked around this by classifying adx/hurst as `volatility`, which is semantically false and was flagged inline + in D018's surface-item.

**What I did instead:** Phase 1 shipped with the misclassification in fixtures only (production grammar engine is registry-driven, so the production behavior depends on what the *real* registry says). The Phase 2 enumerator picks indicators directly from the registry and will hit this on day one — cannot be deferred further.

**Severity:** **high** — structural blocker for Phase 2 enumerator. Picking silently means continuing to claim adx is a vol indicator, which will be wrong the moment Crucible's actual registry ships.

**Options:** (a) keep the lie in production, (b) add `trend_strength` to contracts, (c) special-case C1, (d) tighten C1's semantics to per-role. (See Phase 2 closure plan D1 in this session's conversation log.)

**Resolution 2026-05-13:** Operator chose **(b) — add `trend_strength` to contracts**. Most honest; smallest blast radius outside the immediate fix. See `IMPLEMENTATION_DECISIONS.md` D019.

**Closure 2026-05-13:** `crucible_contracts` v1.4.0 shipped (`crucible_contracts/master` commit `d84240a`) adding `trend_strength` to the canonical 12-family list. Forge bumped `FORGE_EXPECTED_CONTRACT_VERSION` to `"1.4.0"`; fixture reclassified. Q8 closed; Phase 2 unblocked.

---

## 2026-05-13 — Q9 — §8.4 trigger (c) cross-batch param-no-promotion — DEFERRED to Phase 7+

**Question:** §8.4's third trigger example ("0 promotions in 200+ submissions with parameter X above threshold T") requires a multi-batch rolling window. Phase 5 shipped current-batch-only — the trigger only fires on batches that themselves contain 200+ submissions. The spec example reads as a cross-batch aggregate over recent history.

**What's needed:** extend `forge.feedback.proposer.propose(report, feedback, *, at)` with a `forge_db` argument (or pre-computed `history: ParamPromotionHistory` object), then issue a query joining `submissions` × `gated_runs` over the last N batches grouped by `(hypothesis, dte_bucket, signal-param-bucket)`. The 200-submission threshold then aggregates across that history.

**Severity:** **low** — current-batch behaviour is a strict subset of the spec; it under-fires rather than mis-fires. No grammar safety issue (hard rule #3 untouched).

**Resolution 2026-05-13 (Phase 6 closure):** **D025/D8 — deferred**. Phase 6's charter is polish + operational discipline (§12). Cross-batch wiring needs a new history-query module and is closer to Phase 7 / future-operational-phase work than polish. Filing here for traceability; revisit when Crucible has > 1 batch of real promotion data and the operator wants the trigger to fire on the longer baseline.

**Tag:** `phase-7-candidate`

---

## 2026-05-13 — Q10 — Crucible-backed FeatureCache — DEFERRED to contracts dependency

**Question:** Phase 3 D1 introduced `forge.prefilters.feature_cache.FeatureCache` Protocol + `SyntheticFeatureCache` implementation. The synthetic cache deterministically stubs `expected_trades_per_year`, `signal_density`, `regime_label`, etc. The real Crucible-backed cache was deferred at Phase 3 (D021), again at Phase 5 (D024/D9), and again at Phase 6 (D025/D9). Each deferral has been honest about the upstream blocker.

**Blocker:** `crucible_contracts` v1.6.0 does not expose a feature-cache surface (no `get_feature_cache()` helper, no FeatureCache Pydantic model with statistics rows, no realized-trade-count read-path). Until Crucible exposes such a surface, Forge cannot build the real implementation — the Protocol is in place, but there's nothing to adapt against.

**Severity:** **medium** — synthetic-cache numbers are deterministic but not data-grounded. Pre-filter scores are correct relative to themselves (good for ranking) but absolute thresholds (e.g., "≥ 20 trades/year") cannot be validated against real Crucible feature behaviour. As soon as the first batch of real Crucible runs lands, the gap shows in the gated-run promotion rate vs Forge's expected_trades estimates.

**Resolution 2026-05-13 (Phase 6 closure):** **D025/D9 — deferred**. Re-confirmed at every phase boundary; the contracts gap is upstream and outside Forge's scope to resolve. Phase 6 ships with synthetic cache. Next action: when Crucible/contracts adds a feature-cache surface, swap `forge.prefilters.feature_cache.SyntheticFeatureCache` to the real adapter behind the same Protocol — call sites need no changes.

**Tag:** `contracts-dependency`

---

## 2026-05-13 — Q11 — v1 go-live paused; Crucible Phase 9 v2 is the real prerequisite — **HIGH SEVERITY**

**Question:** First v1 go-live attempt (this session) surfaced three stacked gaps between Forge's emitted configs and Crucible's current runtime, with no honest path forward until Crucible's Phase 9 v2 lands. How does v1 go-live actually achieve closed-loop operation?

**What we discovered during go-live:**

1. **Inbox layout mismatch** (resolved as D026, this session) — Forge wrote `inbox/{batch_id}/{config_hash}.json`; Crucible's contract-compliant inbox watcher skips subdirectories. Fixed by writing flat per `INBOX_LAYOUT`. Crucible queued the 2 stranded submissions within 30s of the move.

2. **Name-prefix routing gap** (resolved in Crucible commit `98f1eeb`, this session) — Crucible's `_detect_strategy_name` only routed `genome_<...>` configs; Forge emits `forge_<hypothesis>_<bucket>_<hash>`. Stale convention. Added `forge_` arm matching the existing scaffold comment. One run then completed; the second hit gap #3 below.

3. **Exit-vocabulary divergence (NEW, unresolved):** `crucible_contracts.KNOWN_EXIT_IDS` (per D011) lists 14 exit IDs; Crucible's backtest engine implements 10. The intersection misses 6 contract-only exits:
   - `atr_underlying_stop_loss` (per D012 stop-loss family)
   - `event_passed_exit` (tail_hedge hypothesis-required exit per S5)
   - `hard_profit_target` (trend_continuation forbids; harmless if unimplemented)
   - `premium_stop_loss` (per D012 — Crucible has `premium_stop` instead; likely an unsynced rename)
   - `regime_flip_exit` (regime_arbitrage hypothesis-required exit per S5; surfaced as Run 2's failure)
   - `roll_on_schedule_exit` (calendar hypothesis-required exit)
   Plus 2 Crucible-only ids missing from the contract: `blow_out_exit`, `premium_stop`.

4. **From-config dispatcher gap (NEW, unresolved):** Even Run 1 (mean_reversion) "completed" with all-zeros metrics (`n_trades=0`, `final_equity=100000=initial`). Per `Crucible/src/optbt/data/runner.py:199` comment: *"v2: a proper 'from-config' dispatcher."* Crucible currently routes Forge configs to the `regime_mean_revert` template — it ignores Forge's actual signal config and runs the template. Honest backtests of Forge configs require Phase 9 v2.

5. **Promotion gate gap (NEW, unresolved):** `promotion_decisions` table is empty across the test runs. Crucible's gate evaluator for `source='forge'` runs isn't wired (refit-source has a stub via `_make_refit_evaluator_stub`; forge-source has nothing). `_GATED_QUERY_BASE` is an INNER JOIN with `promotion_decisions`, so even successfully-completed runs never appear gated. **Forge's rate limiter (§7.3, ≥80% gated) blocks indefinitely** in current state.

**What I did instead:** Stopped `forge.service` (left enabled). Documented the three new gaps and the v1 go-live status here.

**Severity:** **high** — v1 go-live is the boundary between "code is structurally complete" and "system actually produces strategy candidates." Forge cannot achieve the latter alone; Crucible v2 must (a) sync exit vocabulary with the contract, (b) implement from-config dispatch so Forge configs backtest honestly, (c) wire a forge-source gate evaluator that writes `promotion_decisions`.

**Resolution 2026-05-13 (operator choice):** **Pause v1 go-live, scope Crucible Phase 9 v2 in a separate session.** Forge's Phase 7 (minimal + Q9) work loses its testing ground until real promotion data exists; reassess Phase 7 scope after Crucible v2 ships at least one real `gated` row.

**Action items for the Crucible Phase 9 v2 scoping session:**
- Reconcile `crucible_contracts.KNOWN_EXIT_IDS` with the runtime exit table. Determine which side renames (`premium_stop` ↔ `premium_stop_loss`?), which exits Crucible must implement vs deferred, and whether `blow_out_exit` should be added to the contract.
- Implement a from-config dispatcher in `runner.py` so source='forge' runs evaluate Forge's actual signal config (not a placeholder template).
- Wire a forge-source gate evaluator that writes `promotion_decisions` after each completed forge-source run (decision can be reject for v1, mirroring the refit stub — what matters is the row exists for `_GATED_QUERY_BASE`).
- Validate end-to-end: Forge submits → Crucible queues → backtests with Forge's signals → writes promotion_decisions → Forge consumes feedback + rate-limiter unblocks → submits batch 2.

**Tag:** `crucible-v2-prerequisite`, `v1-go-live`
