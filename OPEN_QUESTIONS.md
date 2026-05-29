# Forge — Open Questions

Append-only. Each entry: date, question, what I did instead, severity (low / medium / high).
Operator reviews at every phase boundary.

> **Note (D059 / P3-4 2026-05-18):** Some entries reference Crucible coordination prompts (`CRUCIBLE_*_AGENT_PROMPT.md` at repo root) that were deleted in commit `e85f0d4` after their work shipped. The references are preserved as historical narrative; the prompt files are recoverable via `git show e85f0d4^:<filename>`. See the matching D059 entry in `IMPLEMENTATION_DECISIONS.md` for the deleted-file list.

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

**Closure update 2026-05-13 (Phase 9 v2 shipped):** Crucible Phase 9 v2 closed Gaps 3, 4, 5 above (commits `5623d85` exit-vocab parity, `d1322f5` from-config dispatcher, `7c7cd5d` Gap 3 stub, `e45a90e` Gap 3 minimal evaluator). First v2 re-process of the 2 stranded forge-source runs surfaced a **fourth layer** of mismatch, logged below as Q12.

---

## 2026-05-13 — Q12 — Indicator-vocabulary divergence between Forge demo registry and Crucible runtime — **HIGH SEVERITY**

**Question:** After Phase 9 v2 re-processed the 2 stranded Forge configs, both failed with `Unknown indicator: 'iv_rank'` (mean_reversion run) and `Unknown indicator: 'expected_value_estimator'` (regime_arbitrage run). Forge's enumerator is sourcing from an in-Forge stub registry (`forge.enumeration._demo_registry`) that advertises indicators Crucible's runtime doesn't implement. How does the system reach indicator-vocabulary parity for v1 go-live?

**Scope of the divergence:**

| Side | Count | Notes |
|---|---:|---|
| Forge `_demo_registry` (Phase 2 stub — "ships ahead of the Phase 4 Crucible-registry wiring") | 14 | adx, days_to_earnings, days_to_fomc, ema_50, **expected_value_estimator** (X2-required), hurst, **iv_rank** (R1-required), momentum_252, pairs_zscore, put_call_flow, realized_vol, rsi_2, rsi_14, vix_level |
| Crucible runtime (`features/` registry) | 23 | adx, amihud, atr, atr_pct, bb_pct, donchian, ema, ema_cross, garman_klass_vol, hurst, keltner_pct, macd, parkinson_vol, realized_vol, returns_12m_skip1, rolling_sharpe, rsi, rsi_2, sma, supertrend, vol_regime, yang_zhang_vol, zscore_returns |
| **Intersection** | **4** | adx, hurst, realized_vol, rsi_2 |

§3.5 R1 requires `iv_rank` for mean_reversion regime gates; §3.5 X2 requires `expected_value_estimator` for fractional Kelly sizing. Both are operator-owned grammar rules (CLAUDE.md hard rule #1) and cannot be relaxed Forge-side.

**Architectural root cause:** Crucible's `EXPORT_LAYOUT.registry_snapshot_*.json` was never wired. Forge has been enumerating against a fictional registry the whole time. Phase 2 D6 + Phase 4 D5 + Phase 5 D9 all acknowledged this in passing (carrying `_demo_registry` forward) but the wiring was never built.

**Severity:** **high** — first v1 go-live attempt is blocked here exactly the same way Q11 blocked it. The pipeline can't honestly produce candidates Crucible can backtest until the registry alignment lands.

**Resolution 2026-05-13 (operator choice):** **Path A — Crucible implements all 10 missing indicators + publishes RegistrySnapshot per EXPORT_LAYOUT.** Driven via separate Crucible-side agent following `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md` at Forge repo root. Forge side pre-stages `forge.persistence.registry_loader` with graceful demo-registry fallback so Forge picks up the real snapshot automatically when it lands.

Alternatives rejected:
- **Path B** (shrink Forge grammar to Crucible's 23 known indicators) — would amputate §3.5 R1 + X2 + several hypothesis families; violates hard rule #1.
- **Path C** (Crucible implements only load-bearing iv_rank + expected_value_estimator + aliases) — operator preferred completeness over band-aid; some of the deferred indicators (vix_level, days_to_earnings) are non-trivially load-bearing for hypotheses Forge can't dodge.

**Action items:**
1. Crucible side (per `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`):
   - Implement 10 new registered indicators (most have existing math/scaffolding to wrap)
   - Publish `~/optbt_data/exports/registry_snapshot_<timestamp>.json`
   - Verify the 2 stranded runs re-process cleanly under v3
2. Forge side (this session):
   - `forge.persistence.registry_loader` shipped with 8 unit tests
   - 5 CLI sites threaded (4 in main.py + 1 in feedback_cmd.py) — fallback to demo on miss
   - When Crucible publishes, no Forge code changes needed
3. Operator restart `forge.service` after Crucible v3 ships; observe end-to-end loop close.

**Tag:** `crucible-v3-prerequisite`, `v1-go-live`

**Closure update 2026-05-14 (v1 go-live operational):** Crucible Phase 9 v3 shipped 10 new indicators + EXPORT_LAYOUT publishing (Crucible commit `phase9v3`). Plus a runtime architectural gap surfaced — DuckDB's writer holds an exclusive lock blocking Forge's direct read-only opens. Closed by `crucible_contracts` v1.8.0 (`load_recent_gated_runs_from_export`) + Crucible's `crucible-gated-runs-publisher.service` writing `gated_runs_*.json` snapshots + Forge's rate limiter & feedback consumer switching to file-based reads. Q11 + Q12 considered closed; new survival-rate concern logged below as Q13.

---

## 2026-05-14 — Q13 — 100% pre-filter rejection at permutation_test under real Crucible registry — **MEDIUM SEVERITY**

**Question:** First v1 go-live iteration after the registry/publisher work landed: enumerate 5000 candidates → 0 survivors. Diagnostic via `uv run forge prefilter --seed 42 --max 200 --summary` showed `permutation_test: 200 rejections` (the only rejecting filter; the other 6 in the cost-ascending battery passed every candidate). Auto-tune (Phase 5 D5) is designed to handle this over time, but the immediate effect is zero promotions per batch. Is the current pre-filter calibration honest under the real registry?

**Root cause:** `SyntheticFeatureCache` (Phase 3 D1 stopgap) deterministically stubs feature values from config_hash. Under the demo registry (14 indicators) most candidates had p-values in a range that produced ~5-20% survival; under the real registry (33 indicators) the config_hash distribution shifts and the synthetic cache yields uniformly low signal-strength → uniform permutation_test failure.

**This is `SyntheticFeatureCache` fidelity meeting calibration tuning** — both are known stopgaps:
- Q10 (already deferred): the real Crucible-backed FeatureCache requires a contracts surface that hasn't shipped.
- §5.5 auto-tune mechanism (Phase 5 D5): on 95%+ rejections by a single filter, auto-tighten/loosen proposes a calibration adjustment. Phase 5 ships the trigger; it requires a few batches of evidence before it fires.

**What I did instead:** confirmed the pipeline is structurally correct (Forge submits 0, Crucible has nothing to backtest, Forge's feedback consumer cleanly reports 0 — no crash). Let `forge.service` continue to run; auto-tune will accumulate evidence over batches.

**Severity:** **medium** — the loop closes end-to-end without errors; the 0-survivor signal is the auto-tune's intended trigger. Long-term: real feature cache is the right fix. Short-term: operator may manually relax `config/prefilter.yaml` `permutation_test.p_value_threshold` to bootstrap survival until auto-tune fires.

**Resolution 2026-05-14:** Logged + watching auto-tune behavior across iterations. Not blocking v1 go-live operability.

**Tag:** `auto-tune-candidate`, `synthetic-cache-fidelity`

---

## 2026-05-14 — Q14 — Threshold semantics + stub-indicator implications

**Question:** Real Crucible feature cache (commit `b447597`) revealed two coupled issues:

1. **Threshold semantics mismatch:** Forge enumerator emitted threshold-style SignalSpecs with empty `params` (`indicators=(id,)` only). Crucible's `ThresholdSignal._compare` requires `params.get("threshold")`; absent → predicate `lambda _v: False` → 0 activations. Same for `params.get("op", "<")`. Most directional signals never fire under real cache.

2. **Stub indicators:** 5 of the 10 indicators registered in Crucible's v3 work return NaN on real data (`iv_rank`, `expected_value_estimator`, `vix_level`, `pairs_zscore`, `put_call_flow`). Their value distribution from audit (`docs/INDICATOR_THRESHOLDS.md`, 2026-05-14) is all-NaN. Forge's grammar §3.5 R1 (mean_reversion → iv_rank) and §3.5 X2 (fractional Kelly → expected_value_estimator) become structurally unsatisfiable.

**What I did instead:** Two-track fix:

- **Forge-side (this session):** Added `forge.enumeration.indicator_thresholds` module with audited per-indicator threshold ranges. Sampler now emits `params={"threshold": <audited>, "op": <"<" or ">">}` for every threshold-style signal. P1 grammar updated to whitelist `threshold` + `op` as signal-type predicate params (not indicator params). Price-scale indicators (`ema`, `ema_50`, `sma`) skipped from directional/regime threshold roles via `is_threshold_skippable` filter in `_pick_directional_regime_pair`. Stubs included in enumeration with educated defaults (will fire 0 until Crucible v4 implements them).

- **Crucible-side (separate workstream):** Authored `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md` for a Crucible agent to implement the 5 stubs properly. Operator-decided "long-term hold" approach (option 2) — include stubs in enumeration honestly while waiting for upstream fix.

**Severity:** **medium-high** — pipeline closure works but is structurally honest about most candidates failing until stubs are real. §3.5 R1 + X2 grammar rules effectively disabled until upstream fix.

**Resolution 2026-05-14:** Logged + Forge-side thresholds fixed; awaiting Crucible stub-impl follow-up. See **D030**.

**Tag:** `crucible-v4-prerequisite`, `threshold-semantics`

---

## 2026-05-19 — Q15 — `trend_continuation` blocked by registry family mismatch on `adx`/`hurst` — **HIGH SEVERITY**

**Question:** Why does the `trend_continuation` hypothesis produce zero sampler attempts in production despite D067's 5% exploration floor and D037's 2% stratified rotation? Iter 36 telemetry (D064 `prefilter_rejections_by_hypothesis:`):

```
sampler_attempts: trend_continuation=0, mean_reversion=1520, regime_arbitrage=1102, relative_value=1142, volatility_event=1236, tail_hedge=0
```

**Diagnosis.** The production registry (`registry_snapshot_2026-05-18T033529Z.json`) assigns `family="trend"` to **both** `adx` and `hurst`, the §3.5 R2 regime indicators for `trend_continuation`. Forge's grammar requires:

- §3.5 C2[`trend_continuation`] = `("trend",)` — directional must be `trend` family.
- §3.5 R2 = literal IDs `("adx", "hurst")` — regime must be one of these.
- §3.5 C1 — directional family ≠ regime family.

When the sampler picks `trend_continuation`, it draws a directional from `trend` family (e.g., `momentum_252`). Then for the regime it picks `adx` or `hurst` — but both have `family="trend"` in the production registry. C1 fires → `SamplerError`. After 20 forced-rotation retries hit the `_FORCED_FAILURE_CAP`, `trend_continuation` is blacklisted for the batch. The weighted-sample path also fails on every pick, producing **zero successful samples** in the entire 5,000-candidate batch.

Forge has historically expected `adx`/`hurst` to live in a separate `trend_strength` family. Evidence:

- `tests/unit/test_enumeration/test_search_space.py:116-119` asserts `indicators_by_family["trend_strength"] == ("adx", "hurst")` and references the move as "post-contracts-v1.4.0, adx + hurst live in the `trend_strength` family rather than `volatility` (D019)."
- `tests/fixtures/strategy_configs.py::minimal_registry_snapshot()` ships `adx` and `hurst` with `family="trend_strength"`.
- D019 in `IMPLEMENTATION_DECISIONS.md` formalized the split.

**The production registry has them as `family="trend"` — same family as the directional pool.** This is a regression from D019's contract.

**What I did instead:** Logged this question. Did not modify the grammar (hard rule #1). Did not change `_R2_TREND_STRENGTH_INDICATORS` (Forge would silently break the cross-system contract and the test suite). Did draft `CRUCIBLE_TREND_STRENGTH_FAMILY_AGENT_PROMPT.md` at the repo root for the operator to hand off to a Crucible agent — it specifies moving `adx` and `hurst` from `family="trend"` to `family="trend_strength"` (with no other changes), citing this Q15 entry and D019.

**Severity:** **high** — fully blocks the `trend_continuation` hypothesis from ever being sampled. Crucible's post-mortem cohort (3,829 configs) shows `trend_continuation` at 0/3,829 = 0.0%; consistent with this finding being persistent rather than transient.

**Tag:** `crucible-registry-regression`, `trend-strength-family`, `cross-system-contract`

**Resolution 2026-05-19:** Crucible shipped `e298138 fix(exports): split adx + hurst into trend_strength family per D019`. Verified live in `registry_snapshot_2026-05-19T211742Z.json` — `adx` and `hurst` now have `family="trend_strength"`. Forge's first iter to load the new registry (iter 37, `registry_hash=fc0dd3bd55a35177`) immediately produced ~1,500 sampler attempts for `trend_continuation` per batch (was 0). Those configs now die at `permutation_test` (~85% of kills) — a separate signal-quality issue addressed by Phase 3 (D073) and not blocking. **Q15 closed.**

---

## 2026-05-20 — Q16 — `expected_trades` pre-filter measures indicator activations, not trades — **HIGH SEVERITY**

**Question:** Why does the `expected_trades` filter (`src/forge/prefilters/expected_trades.py`) reject 0 / 16,253 configs while 77% of submitted configs produce 0 trades in Crucible? Diagnostic across 1,213 distinct gated runs (decided 2026-05-15 → 2026-05-20):

```
Trade count distribution (n=1213):
       0:   934 (77.0%)
     1-9:   211 (17.4%)
   10-49:    39 (3.2%)
   50-99:    19 (1.6%)
    100+:    10 (0.8%)
```

`pre_filter_logs` (Forge DB) corroborates the filter is structurally a no-op for its intended purpose — **every one of 16,253 attempts passed**, with median `estimated_trades` well above the `min_trades=50` floor (samples show 60, 367, 367, 73, ...).

**Root cause.** `ExpectedTradesFilter.apply()` computes:

```python
n_activations = len(ctx.feature_cache.activation_dates(directional.id))
capacity = 5 * (ctx.registry.data_history_days / hold_days)   # ≈ 418 for swing_short
estimated = min(n_activations, int(capacity))
passed = estimated >= ctx.calibration.expected_trade_count.min_trades  # default 50
```

This counts how many times the directional signal's indicator crosses its threshold over the 5-year cache window. Under realistic thresholds (e.g., `pairs_zscore < -1.26`, `vix_level > 18`), threshold crossings happen many times per year so `n_activations >> 50` almost always — even when zero actual trades will open downstream.

What the filter does NOT check:
- Whether the **selector** can find a matching option contract on activation dates.
- Whether the **sizer** would skip the trade (risk budget, position cap, fractional-Kelly EV miss).
- Whether the **exit rules** would close at zero P&L.
- Whether the **regime_filter** signals would veto the directional signal at runtime.

The mental model conflates "indicator-would-fire times" with "trades the strategy would execute." Threshold-distribution medians for 0-trade vs trading configs are nearly identical (`pairs_zscore`: -1.26 vs -1.07; `expected_value_estimator`: 0.0046 vs 0.0046) — so threshold strictness isn't the lever; the filter cannot discriminate.

**Possible directions (operator decision needed before any rewrite):**

1. **Empirical-prior filter (recommended).** Replace activations-based estimate with a learned trade-rate prior per `(hypothesis, dte_bucket, directional_signal_family)`. Feedback consumer maintains rolling `gated_trade_count / submitted_config`; filter rejects if predicted < `min_trades`. Builds on Q10's deferred FeatureCache work. Self-corrects from real data; no Crucible API change required.
2. **Crucible-side dry-run estimator.** Crucible exposes a fast no-execution endpoint returning "would-have-opened N trades" given a config (skip option-chain pricing, just signal-fire × selector-feasibility). Cleaner semantics; new `crucible_contracts` surface required.
3. **Tighten activations threshold heuristically.** Raise `min_trades` from 50 toward `capacity` (~400). Catches lowest-activation 0-traders but won't catch most of them (96.75% zero-trade `pairs_zscore` configs already show plenty of activations).

**What I did instead:** Logged. Did NOT modify the filter — the §5.3.4 motivation cites Crucible's 100-OOS-trade floor without prescribing the activations heuristic, so there is freedom to redesign, but the redesign needs operator review (likely a Decision Log entry).

**Related observation (filed inline, not as separate Q):** As of 2026-05-20, **all 9 pre-filters pass every config — 0 rejections across the entire battery.** Q15's 2026-05-19 closure noted `permutation_test` was killing ~85% of `trend_continuation` configs. Either auto-tune (D053-era) has loosened `permutation_test` to pass everything, or another regression. If the pre-filter battery is universally pass-through, Forge is effectively submitting raw-grammar output to Crucible — the rate limiter (Q19-area / spec §7.3) is the only remaining flow control, and it isn't engaging either.

**Severity:** **high** — `expected_trades` is the spec's intended structural mitigation against the 0-trade flood (§5.3.4). With it inert, every downstream computation (Crucible queue time, gauntlet compute, gated-runs storage) burns on configs that will never trade.

**Tag:** `prefilter-semantic-gap`, `zero-trade-root-cause`, `phase-7-candidate`

**Resolution 2026-05-20:** Closed by **D076** — empirical-prior `expected_trades` filter learns per-`(hypothesis, dte_bucket, directional_family)` posterior P(n_trades ≥ min_trades) from the gated_runs cohort, rejects buckets with ≥20 samples + posterior < 0.10, falls back to legacy activations heuristic for cold-start buckets. Bundled with the `pre_filter_logs` audit-gap fix (rejected configs now logged with `config_hash` + `forge_batch_id` columns). **Q16's sidenote correction:** the battery was NOT a no-op — `batch_summaries.prefilter_rejections` showed ~50% rejection per batch all along; `pre_filter_logs` only ever held survivor rows, the audit gap masked the truth. Real per-filter rejection telemetry: see D062 + D064. Restart required to activate.

---

## 2026-05-20 — Q17 — `pairs_zscore` and `expected_value_estimator` show >93% zero-trade rate — Q14 follow-up status — **HIGH SEVERITY**

**Question:** Q14 (2026-05-14) flagged 5 Crucible-registered indicators as stubs returning NaN: `iv_rank`, `expected_value_estimator`, `vix_level`, `pairs_zscore`, `put_call_flow`. Resolution authored `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md` and adopted "long-term hold" — include stubs in enumeration honestly while waiting for upstream. Six days later, gated-runs evidence shows the stubs have not been replaced (or were replaced with implementations that produce ~zero trades):

**Per-indicator 0-trade rate in 1,213-run gated cohort (2026-05-15 → 2026-05-20):**

| indicator | 0-trade | trading | 0-rate |
|---|---:|---:|---:|
| `pairs_zscore` | 596 | 20 | **96.75%** |
| `expected_value_estimator` | 378 | 26 | **93.56%** |
| `rsi_14` | 66 | 12 | 84.62% |
| `hurst` | 21 | 4 | 84.00% |
| `rsi` | 31 | 6 | 83.78% |
| `momentum_252` | 65 | 18 | 78.31% |
| `rsi_2` | 66 | 19 | 77.65% |
| `iv_rank` | 108 | 42 | 72.00% |
| `realized_vol` | 200 | 111 | 64.31% |
| `vix_level` | 170 | 167 | 50.45% |

**Hypothesis × DTE 0-trade rate** (most affected — driven by `pairs_zscore`):

```
relative_value × swing_short:  370/375  (98.7%)
relative_value × swing_mid:    202/205  (98.5%)
volatility_event × swing_short: 105/147 (71.4%)
regime_arbitrage × swing_long:  43/67   (64.2%)
```

`relative_value` is effectively non-functional. 580 of 596 zero-trade `pairs_zscore` configs come from `relative_value` × `swing_short`/`swing_mid`.

**Severity:** **high** — Forge is filling Crucible's gauntlet queue with structurally hopeless candidates from the `relative_value` hypothesis, and to a lesser extent `volatility_event`/`regime_arbitrage` via the other stubs. Compounds Q16 (filter doesn't catch them) and the Crucible queue latency (separate, ~5d).

**What I did instead:** Logged. Did NOT modify grammar or filter (hard rule #1; Q14 chose long-term hold). Did NOT verify whether the prompt file `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md` is still at repo root or in `e85f0d4`-history.

**Open sub-questions:**
1. Have the 5 stub indicators shipped real implementations? If yes, why does the cohort still show NaN-like behavior? If no, what's the ETA?
2. Should Forge temporarily down-weight `relative_value` enumeration until `pairs_zscore` is real, to reduce queue contamination?
3. Should Forge's sampler treat known-stub indicators with a per-indicator suppression weight derived from rolling gated trade-rate (auto-discovery rather than a hard-coded list)?

**Tag:** `crucible-stub-followup`, `zero-trade-root-cause`, `relates-to-Q14`

---

## 2026-05-20 — Q18 — Grammar R3 (ETF + `days_to_earnings`) documented in `grammar.yaml` but inbox/errors shows it isn't fully enforced — **MEDIUM SEVERITY**

**Question:** `config/grammar.yaml` R3 (v2, D039) documents that ETF underlyings paired with `days_to_earnings` must be rejected ("sentinel-value silent-failure case from translation corpus"). However, two pieces of evidence indicate the rule is not being enforced for at least some emitted configs:

1. **`inbox/errors/` contains 10 Forge submissions** that failed Crucible's preflight. Sample rejection reason:

> `queue_run failed: queue-time preflight: hypothesis='volatility_event' + underlying='SPY' (Tier-1 ETF) + regime indicator(s) ['days_to_earnings'] that require single-name earnings — days_to_earnings returns the 999 sentinel for ETFs so the gate never fires.`

Both `SPY` and `QQQ` (the Tier-1 ETFs) appear in the error sample. This is exactly the case R3 was authored to prevent — Crucible's preflight is acting as a downstream safety net for a Forge-side rule that should have caught it.

2. **123 configs in the 1,213-run gated cohort use `days_to_earnings`** and produce 0 trades each (100% zero-rate). Some of these may be Tier-2/3 single-name configs where `days_to_earnings` is technically valid but never reaches a useful window — but at least the 10 ETF cases are clear R3 violations that shipped.

**Possible explanations:**
1. R3 exists in `grammar.yaml` only as documentation, not in the validator.
2. R3 is wired but bypassed by a specific enumeration path (e.g., sampler emits before validator runs, or a tier check is off).
3. R3 catches Tier-1 but not Tier-2 ETFs (or vice versa).

**What I did NOT verify:** whether R3 is enforced in `src/forge/grammar/predicates.py` or `validator.py`. Defer that to whoever resolves this — the question itself is the deliverable.

**Severity:** **medium** — 10 confirmed preflight rejects on the Forge side (we sent invalid configs Crucible caught) plus unknown share of the 123 zero-trade `days_to_earnings` cohort. The blast radius is small, but per hard rule #1 grammar rules are operator-owned and silent under-enforcement is a contract violation worth surfacing.

**Next step:** grep `predicates.py` / `validator.py` for R3 / `days_to_earnings` enforcement; either confirm it works and the 10 errors are an unrelated edge case (e.g., universe/registry drift), or fix the validator.

**Tag:** `grammar-enforcement-gap`, `zero-trade-root-cause`, `inbox-errors`

---

## 2026-05-20 — Q19 — `RegistrySnapshot` exposes `data_start_date` but not `universe_min_asof` — contracts gap — **MEDIUM SEVERITY**

**Question:** On 2026-05-15, 125 Crucible runs failed with `No universe snapshot at or before 2021-01-04` after D031 widened backtest windows to 5y/7y. The universe table only covered 2024–2025 at the time. Forge had no defensive clip because the only date floor `RegistrySnapshot` exposes today is `crucible_contracts.RegistrySnapshot.data_start_date` — the feature-cache anchor, not the universe-coverage floor. The fix that actually landed was Crucible-side: `scripts/ingest_universe.py` back-extended snapshots to 2019-01-02 (Forge commit `a4e5d2f` documents the recovery). The two floors are independent and can drift again whenever Crucible's feature cache and universe table are widened on different cadences.

**What I did instead:** wrote up the diagnosis in the reply to Crucible's `PROMPT_FORGE_POST_D066_FINDINGS.md` (see `/home/aj/proj/Crucible/docs/handoffs/REPLY_FORGE_POST_D066_FINDINGS.md`). No code change Forge-side yet — per hard rule #2, Forge cannot read universe coverage by importing Crucible internals; the surface has to come through `crucible_contracts`.

**Severity:** **medium** — wasted ~20 min runner throughput last time it fired (125 slots × ~10s reject). Self-healed when Crucible's universe backfill landed, no recurrence in the 5 days since. But the structural gap is durable: any future widening of cache vs universe on different cadences re-opens the bug.

**Options:**

1. **Extend `crucible_contracts`** — add `universe_min_asof: date | None` to `RegistrySnapshot` (next to `data_start_date`). Forge then clips submissions against `max(data_start_date, universe_min_asof)` at submitter or pre-filter time. Minor version bump (additive). This is the option that matches the precedent set by Q7/Q8/Q12 contracts-gap resolutions.
2. **Treat as operational** — accept "Crucible's universe coverage is the source of truth; if it's behind, runs fail and Crucible patches the universe table." No Forge-side guard. Cheaper but the same bug will recur whenever cache and universe drift.
3. **Forge-side `OPTBT_HOME/universe/` peek** — Forge could read the universe table directly via DuckDB. Violates hard rule #2 (Crucible internals).

**Recommendation:** option 1. Same precedent as Q7 / Q8 / Q12 — contracts gap surfaced from Forge, fixed by additive contracts bump. Waiting on operator agreement to file the contracts ticket.

**Tag:** `contracts-gap`, `universe-coverage`, `defensive-clip`

---

## 2026-05-20 — Q20 — `volatility_event` is the edge-density leader at 2.1% cohort share — re-weight under D067 / re-tune under D073 once round-robin is live — **LOW SEVERITY**

**Question:** Crucible's 2026-05-20 post-D066 analysis (see `PROMPT_FORGE_POST_D066_FINDINGS.md` §"Forward-looking observation") shows 9 of the top 10 traded configs by n_trades are `volatility_event` (max 171 trades, Sharpe 0.91) while the hypothesis is only 2.1% of post-D066 cohort. Forge is sampling under its empirical edge density. Three downstream levers exist: (i) D067 stratification weights can bias toward higher-density hypotheses; (ii) D073 per-(indicator, role) priors can tighten `volatility_event` thresholds more aggressively now that the bucket has signal; (iii) the signal-poverty diagnosis from `PROMPT_FORGE_GENERATOR_GAPS.md` §1 can be revisited per-hypothesis (maybe `volatility_event`'s exit set is fine; the gap is concentrated in `relative_value` / `regime_arbitrage`).

**What I did instead:** flagged as a future action; no code change. Gated on the Crucible round-robin scheduler being live ~24h so the gated-runs cohort is hypothesis-representative — otherwise rebalancing now just amplifies sampling noise from the current `relative_value`-flooded queue. To be clear (and per the handoff), this is not a "raise weight to promote" ask — Crucible's gate doesn't move (hard rule #3). It's a "your strongest edge-density hypothesis is your second-rarest" observation worth acting on once the feedback signal is clean.

**Severity:** **low** — observational. No production breakage. Pure enumeration-shape question.

**Next step:** revisit when (a) Crucible round-robin commit lands and gated_runs shows 5%+ floor per hypothesis, AND (b) ≥24h of gated runs have accumulated under the new scheduler. At that point: re-run the per-hypothesis trade-density analysis Forge-side, propose a D067 weight update (auto-tightening goes through `OPEN_PROPOSALS.md` per hard rule #4 if it relaxes anything; pure re-weighting toward higher-density hypotheses is the auto-tighten side).

**Tag:** `edge-density`, `enumeration-weights`, `D067`, `D073`, `awaiting-crucible-roundrobin`

## 2026-05-28 — Q21 — `permutation_test._full_window` treats a trading-day count as calendar days — **LOW SEVERITY (latent)**

**Question:** `permutation_test.py:_full_window(data_start_date, data_history_days)` builds the null-distribution window as `data_history_days` *calendar* days from `data_start_date`. But `data_history_days` is a *trading*-day count (~252/yr). On the long window exposed 2026-05-28 (`data_start_date=2018-01-02`, `data_history_days=2118`), the generated window only reaches **2023-10-20** instead of ~2026 — so the permutation null pool silently excludes ~2.5 years of the most recent returns.

**Why it surfaced:** Diagnosing the post-reboot stall (D080). The window doubled when the registry-publisher re-exported Crucible's 2018 Polygon backfill (`data_start_date` 2022→2018, `data_history_days` 1109→2118). Direct instrumentation on real-cache configs showed `permutation_test` still passes a healthy fraction (~454/5000 at the service level), so this is **not** an outage — it was a red herring during the D080 RCA. But the null pool being truncated by ~2.5y biases every config's p-value.

**What I did instead:** Did NOT fix under the outage pressure (the outage was D080's synthetic fallback, not this). Logged for a clean TDD fix. Fix is small: span `data_start_date` → `utc_now()` (blessed clock, hard rule #8) by calendar days, or convert `data_history_days` to a calendar span (×365/252). A regression test must assert the pool's last date is near "today", not `start + data_history_days` calendar days.

**Severity:** **low** — latent correctness wart; biases permutation p-values but does not block submission. Pre-2026-05-28 it was masked because the 3-year window happened to cover the activation domain.

**Tag:** `permutation-test`, `calendar-vs-trading-day`, `latent`, `relates-to-D080`

## 2026-05-28 — Q22 — prefetch is 17-38 min/batch — dominated by unique-spec count + writer load, not window size — **MEDIUM SEVERITY**

**Question:** `phase_timings` shows `prefetch` (the `CrucibleFeatureCache.prefetch_for_batch` socket round-trips) costs 17-38 min/batch, dwarfing every other phase (battery 5-30s, submit 2-4min). At 1 batch / ~25-40 min plus the §7.3 ≥80%-gated wait, Forge throughput is heavily bottlenecked. Can Forge mitigate?

**Investigation (2026-05-28):** Pulled the prefetch time-series. It was ALREADY 1000-2200s (17-36 min) on the OLD 3-year window (May 23-27, `data_history_days=1109`), and grew ~16× over May 21→25 (134s → 2181s) on a roughly fixed window. Today's window doubling (1109→2118) added only ~36% (pre-change avg ~1357s → post ~1852s), **sub-linear** — so window size is a MINOR lever. Large intraday variance (136s-682s on May 22 alone) points to **writer contention with the runner** (single-writer socket). Root cost: the sampler mints fresh thresholds per spec, so ~10k unique specs/batch are near-100% cache-miss every batch → ~10k indicator computations over the socket, no cross-batch amortization.

**What I did instead:** characterized only; did NOT change enumeration behavior or batch size (operator-owned tuning / cross-system design per CLAUDE.md "stop and ask"). Candidate levers, each needing operator/Crucible decision:
1. **Threshold quantization** (Forge-side): round sampled thresholds so specs repeat across batches → `signal_content_key` cache hits → fewer computations. Cost: reduces enumeration diversity.
2. **Persistent feature cache** (Crucible-side): memoize activations by `content_key` across batches / a cheaper bulk estimation endpoint. Biggest win; their side.
3. **Reduce `max_candidates`** (5000→smaller): fewer specs → faster prefetch; trades coverage for throughput.
4. Narrowing Forge's analysis window: only ~36% win (window is not the driver) — low priority, but composes with Q21's fix.

**Severity:** **medium** — no correctness break, but throughput is degraded enough to matter for the feedback-loop cadence (fewer batches gated/day = slower threshold learning).

**Tag:** `prefetch-perf`, `feature-cache`, `writer-contention`, `throughput`, `relates-to-D080`
