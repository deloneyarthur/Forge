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

**Resolution 2026-05-28 — D082:** Fixed. `_full_window` now spans `ceil(n_trading_days × 366/252)` calendar days. Chose the calendar-conversion approach over the `utc_now()` anchor floated above — it keeps the window a pure function of the registry (deterministic per hard rule #6, no clock dependency) and over-covers safely (`returns()` drops surplus dateless days). TDD: +2 tests; full prefilter suite (230) green. Deploys on next `forge.service` restart.

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

## 2026-05-29 — Q23 — enumerator reads `universe_tickers.json` directly — hard-rule-#2 deviation pending a contracts helper — **MEDIUM SEVERITY**

**Question:** `sampler._load_underlyings` (D078) reads `~/optbt_data/exports/universe_tickers.json` via raw `json.loads(path.read_text())`. That file is NOT on the `crucible_contracts.EXPORT_LAYOUT` surface (verified: `EXPORT_LAYOUT.files == ('registry_snapshot_*.json', 'gated_runs_*.json', 'promoted_strategies_*.json', 'promoted/')`), so this is an inter-system data dependency that bypasses `crucible_contracts` — a hard-rule-#2 deviation. The contrast is explicit: `registry_loader` reads the contract-listed `registry_snapshot_*.json` through `RegistrySnapshot.model_validate_json` (the blessed pattern). Surfaced by the 2026-05-29 audit (H-5).

**What I did instead (D087):** did NOT revert D078 (its dynamic-universe value is real — the operator-requested ticker expansion). Per the audit's sanctioned interim, kept the dynamic read but made the deviation observable (`_logger.warning("universe_uncontracted_read", hard_rule="2", open_question="Q23")`, once per process) and surfaced the contracts gap via `Crucible/docs/handoffs/PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md`. The proper fix is a `crucible_contracts.load_universe_tickers_from_export` helper (or a `tier_tickers` field on `RegistrySnapshot`) — the Q19/`universe_min_asof` precedent — after which Forge routes the read through contracts and the warning is removed.

**Severity:** **medium** — every produced candidate's underlying is chosen via this uncontracted read (hot path), but there is no correctness break and the fallback to the D033 hardcoded list is safe. It is a contract-surface purity violation + a determinism input (now folded into the batch identity by D085), not a data bug.

**Tag:** `hard-rule-2`, `contracts-gap`, `universe`, `D078`, `relates-to-H5`, `relates-to-D085`

**RESOLVED 2026-05-29 (D093):** contracts **1.13.0** shipped `load_universe_tickers_from_export` + added `universe_tickers*.json` to `EXPORT_LAYOUT.files` (commit `45f2ea0`). Forge's `_load_underlyings` now routes through that blessed helper (`_UNIVERSE_EXPORT_DIR` + glob), `FORGE_EXPECTED_CONTRACT_VERSION` bumped to `1.13.0`, and the `universe_uncontracted_read` warning is removed — the read is on the contracts surface, so the hard-rule-#2 deviation is closed. The M-13 drift logging is preserved via the helper's `QueryError` (malformed export → `universe_export_unreadable` warning + fallback). `universe_fingerprint()` (D085) is retained (Option A keeps Forge's separate identity fold; only the unbuilt Option B `RegistrySnapshot.tier_tickers` would let it ride `registry_hash` and retire). **CLOSED.**

---

## 2026-05-29 — Q24 — Non-pairs template "hidden param contract" audit REFUTED; residual risk is the un-contracted pairs entry-key schema — **LOW SEVERITY (latent)**

**Hypothesis investigated:** the generator improvement plan (`FORGE_GENERATOR_IMPROVEMENT_PLAN.md:56`) flagged that `trend_rider` / `regime_mean_revert` / `cross_sectional_rank` "likely have analogous hidden [entry-param] contracts that Forge can't satisfy" — the same trap D068/D072 fixed for `pairs_convergence` — potentially silently zero-trading whole hypotheses (a candidate explanation for the ~60% zero-trade rate).

**What I found (read-only audit of Crucible `src/optbt/`):** **REFUTED.** Crucible's router `_detect_strategy_name` (`runner.py:459-515`) maps every `forge_*` config via `_HYPOTHESIS_TO_TEMPLATE` to exactly TWO templates: `composable_long_options` (mean_reversion / trend_continuation / regime_arbitrage / volatility_event) and `pairs_convergence` (relative_value). The three suspect templates only run for configs literally named after them (YAML/Optuna fixtures); Forge never reaches them. `composable_long_options` reads entries from the declarative `signals[].params` (`threshold`/`op`), which Forge always populates (+ the leak-guard assert at `sampler.py:301-309`). So there is no hidden-key trap on Forge's path; an analogous sampler fix would be dead code. The real zero-trade levers are entry-threshold *strictness* (D031/D073 calibration) and the relative_value pair-universe size (Crucible-side), not missing keys.

**Residual risk surfaced (the real finding):** the pairs entry-key names (`pvalue_max`, `zscore_entry`, `halflife_min/max`, `lookback`) are duplicated as bare string literals on BOTH sides — Crucible `pairs_convergence.py:91-96` and Forge `sampler.py:_sample_pairs_template_params` — with no shared schema in `crucible_contracts`. If Crucible renames or adds a required entry key, Forge silently regresses to template defaults and relative_value quietly returns to ~99% zero-trade, undetectable until a gauntlet diagnostic — exactly the D068 failure mode. Soft violation of hard-rule-#2's spirit (inter-system coupling via contracts).

**What I did instead of code:** logged it; no Forge bug to fix. Recommended (needs operator priority; both cross-repo): (a) promote the pairs entry-key schema (names + default-when-missing semantics) into `crucible_contracts` so both sides import one source of truth, + a contracts test that the template's `params.get(...)` keys match the schema; (b) a Crucible-side invariant test asserting `forge_*` configs only ever dispatch to `{composable_long_options, pairs_convergence}` — the routing table is the sole safety net today.

**Severity:** **low (latent)** — no current trade loss; it is a future-silent-regression guard. Both fixes are cross-repo (contracts + Crucible), not Forge.

**Tag:** `hard-rule-2`, `contracts-gap`, `pairs`, `zero-trade`, `crucible-coordination`, `relates-to-D068`, `relates-to-D072`

---

## 2026-05-29 — Q25 — `universe_fallback_hardcoded` is a Crucible publisher gap, not a Forge bug; 24 tickers IS the canonical Tier1+2 universe — **LOW/MEDIUM SEVERITY**

**Symptom:** the live service logs `universe_fallback_hardcoded n_tickers=24` every iteration, suggesting generation is degraded to a hardcoded 24-ticker pool instead of the full universe (D093's `load_universe_tickers_from_export` read path).

**Root cause (read-only investigation):** NOT a Forge or contracts bug — both work as designed and fall back correctly. Crucible never *publishes* `universe_tickers.json`: it has `build_universe_tickers()` / `write_universe_tickers()` (`Crucible/src/optbt/data/exports.py:752-803`) but NO `publish_universe_tickers()` and no `scripts/export_universe.py` / `crucible-universe-publisher.service` — unlike the three working exports (registry / gated_runs / promoted_strategies), each of which has a publisher script + enabled systemd unit. `write_universe_tickers` is referenced only by Crucible tests; in production the file has never been written (confirmed absent on disk; the other exports are fresh). D093 deliberately scoped only the READ side; the "Crucible export-side confirm" in `PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md` was assumed-satisfied but never wired.

**Important secondary finding:** even once published, the file would currently yield **24 tickers** — `build_universe_tickers()` reads `Crucible/config/universe.yaml` (tier_1=4 + tier_2=20) and deliberately excludes tier_3. Those 24 are identical to Forge's hardcoded fallback. So the symptom is cosmetic (a log line); the pool is not actually narrowed below canonical. The "~152" figure is the set Crucible has bar data for (tier_3 = dynamic ranks 25-100), NOT a configured universe.

**What I did instead:** logged; no Forge change (Forge is correct). Two separable follow-ups, both Crucible-side + operator scope: (a) wire a universe publisher so the read path is exercised + the log stops falling back (cosmetic; a one-shot `write_universe_tickers()` + `forge.service` restart unblocks it immediately — note Forge's `lru_cache` on `_load_underlyings` requires the restart); (b) the *real* lever — widening beyond 24 — is a deliberate `config/universe.yaml` tier_2/tier_3 expansion decision with downstream effects (more underlyings → more trade diversity, but also more bar-data + compute). Surfaced to the operator as a scope decision.

**Severity:** **low** for the cosmetic symptom; **medium** if the operator wants universe breadth as a zero-trade / diversity lever (then it is a real Crucible-side expansion, with a fresh handoff).

**Tag:** `universe`, `crucible-coordination`, `operator-decision`, `relates-to-D093`, `relates-to-Q23`

## 2026-06-02 — Q26 — `hurst` regime-gate `op` is `<` (allow when hurst LOW = mean-reverting), which looks backwards for `trend_continuation` — **RESOLVED 2026-06-03 (D100 / v7)**

**Symptom:** `trend_continuation`'s R2 regime gate may admit `hurst`, whose threshold-table entry uses the default `op_regime="<"` — i.e. the gate "allows" (is open) when hurst is *below* threshold. But low hurst (H < 0.5) is the **mean-reverting** regime; trend-continuation wants the **trending** regime (high hurst). So as written, the hurst gate appears to admit precisely the regime the hypothesis does *not* want — a plausible secondary contributor to the "trend_continuation ~58% regime-gated" firing decomposition that motivated D099.

**Status / why surfaced not fixed:** found while building D099 (percentile thresholds). D099 percentile-izes `hurst` regime **preserving the existing op** (`<`), which still *loosens* the gate per the diagnosis (a wider allow-rate regardless of direction), so v6 does not depend on resolving this. Flipping the op is a **semantic** change to the operator-owned grammar's intent, not a percentile-parameterization — out of D099's scope, and CLAUDE.md says log + surface rather than silently change rule semantics. (NB `adx` regime is correctly `op=">"` — allow when trend strong — so this is hurst-specific.)

**Resolve by:** operator confirms whether `trend_continuation`'s `hurst` regime gate should be `op=">"` (allow when trending). If yes, it is a small `_INDICATOR_THRESHOLD_TABLE` change (`op_regime=">"` on the `hurst` entry) + a percentile-range flip (allow ~top 50-75% → `regime_percentile_range` like adx's `(0.25, 0.50)`), shipped as its own decision/version bump. If the current direction is intentional (e.g. "fade exhausted trends"), document the rationale and close.

**Resolution (2026-06-03, D100/v7):** operator confirmed the trending-regime thesis — `hurst`'s `trend_continuation` regime gate should allow when TRENDING. Flipped `op_regime` to `>` + set `regime_percentile_range=(0.25, 0.50)` (allow ~top 50-75%, mirroring `adx`) on the `hurst` table entry. `hurst`'s separate `mean_reversion` **directional** use (`op_directional="<"`, fire when mean-reverting) is correct and untouched — only the regime op moved. Shipped in the v7 bump alongside the mean_reversion cold-start (orthogonal by hypothesis). Test: `test_hurst_regime_op_is_trending_but_directional_unchanged`.

**Tag:** `grammar`, `firing-rate`, `relates-to-D099`, `relates-to-D100`, `operator-decision`, `resolved`

## 2026-06-07 — Q27 — `forge_funnel.json` buckets by grammar-version STAMP, so the v9 bucket contains v8-code batches — re-bucket by the D104 cutover? — **LOW SEVERITY**

**Symptom:** `funnel/aggregate.build_funnel_export` groups `batch_summaries` purely on `grammar_version`, and `build_version_map` likewise labels each `config_hash` by stamp. Per D104, 27 v9-stamped batches (06-05 07:52 → 06-06 04:40Z) ran v8 code, so the export's v9 upstream stages (enumerated / survived / rejection breakdown) blend two code generations. Crucible flagged it (`FORGE_v9_timecut_response.md` §2, "optional ask") and currently annotates around it — their gating stages cohort correctly via their own `grammar_cutovers.yaml` relabel.

**Proposed fix (if/when wanted):** a Forge-side cutover config (mirroring Crucible's: `version`, `live_at`, `effective_prior`) consumed by `build_funnel_export`/`build_version_map` as a read-time relabel on `batch_summaries.submitted_at` — never rewriting stored stamps, always reporting the relabel count in `coverage`. Needs TDD (unit tests on the relabel + the never-silent count) + a schema_version note for the export consumers. ~Half-day.

**Why not now:** Crucible-side stages are the ones that gate, and they already cohort correctly; the D104 hygiene rule (clean live tree) makes recurrence unlikely. Revisit if a third labeling incident happens or if Crucible upgrades the ask from "optional."

**Tag:** `funnel`, `exports`, `relates-to-D104`, `relates-to-D096`, `low`

## 2026-06-07 — Q28 — vol_event x swing_mid (the 9.7%-yield cell) is structurally capped by §3.5 S4: only `iv_rank` among vol_event directionals is medium-horizon-class — **MEDIUM SEVERITY, LOOSENING-CLASS**

**Symptom:** the D105 emission proof showed the bucket-weighted sampler can only push vol_event's swing_mid share to ~9% (5.1% cold → 9.2% weighted) even with the cell weighted hot. Mechanically: the DTE bucket is derived from the DIRECTIONAL's horizon (D102), and every vol_event directional except `iv_rank` (horizon 30 → medium class) is short-class (put_call_flow 5, vix_level 1, dealer family 1, days_to_* 5 → S4 permits swing_short only), so all three event-lead options snap to swing_short. The highest-yield cell in Crucible's map (9.7% on 31 decided) is reachable only via `iv_rank` + lead-20 draws.

**Why surfaced not fixed:** any widening — e.g. re-classing an indicator's horizon, adding a medium-horizon vol_event directional to C2, or letting the event bracket extend (longer post-event window) — ENLARGES enumeration scope = a loosening. Hard rule #4: loosenings go to `OPEN_PROPOSALS.md` and wait; they cannot ship with D105. Also genuinely uncertain: the 9.7% may partly BE the iv_rank+long-lead structure rather than the bucket per se — more decided volume in the cell (which D105's allocation shift will produce) settles that before any grammar change is worth proposing.

**Resolve by:** let D105 run ≥1 yield-map refresh (≥1,500 newly-decided). If ve x swing_mid yield holds ≥2x ve x swing_short on materially more volume AND its share stays pinned ~9%, write the OPEN_PROPOSALS entry (options: extend `_VOL_EVENT_POST_WINDOW_TD` variants, or audit whether any existing vol-family indicator legitimately carries a 7-89d horizon). Otherwise close as working-as-intended.

**Tag:** `grammar`, `S4`, `dte-buckets`, `relates-to-D105`, `relates-to-D102`, `loosening-candidate`, `operator-decision`

## 2026-06-07 — Q29 — Deferred D105 mechanisms: (a) threshold-DRAW adaptation for the 75-83% zero-trade composables; (b) general parameter-band bounds-learning — **(a) PARTIALLY RESOLVED 2026-06-09 (D113): prefilter-tightening arm refuted by measurement; sampler-side arm deprioritized**

**Update 2026-06-09 (D113):** the prefilter-tightening half of (a) was investigated counterfactually against the new `verdicts` table ⋈ `pre_filter_logs` join (10,130 rows) and REFUTED — every candidate knob (raise `min_pass_probability`, a new bucket-P(zero) cut, finer +underlying cells) either kills most of the component frontier (the [0.15,0.25) posterior bands hold 115/140 empirical-mode components alongside the ~60% zero-trade waste — the fat-tail pass-through D105 noted, now quantified) or captures ≤14% of v9-era waste. Decisive: the v12-cohort waste rate is already 1% zero-trade / 10% sub-10-trade vs v9's 40%/49% — the allocation re-aim + H1 rank + D112 fixed this at the sampler. The sampler-side threshold-draw mechanism stays deferred; re-open if a ≥500-decided post-v13 cohort shows sub-10-trade share >~25% (one query against `verdicts`, recipe in D113). Original entry below.

**(a) Threshold-draw adaptation.** The yield-map handoff asked whether `trade_rate_priors` reaches the composable threshold draws. Answer (D105): it is wired and BINDING — as the `expected_trades` prefilter (713-737 trend + 448-516 mean_rev kills per batch in empirical mode), not as a sampler input. So the sampler keeps drawing thresholds in the dead region and burns battery compute, and the survivors still go ~75-83% zero-trade at gate (vol_event legitimately passes the prior via its fat trading tail). A real fix feeds zero-trade feedback into the PERCENTILE-RANGE draws (`indicator_thresholds`' directional/regime ranges) — per-(indicator, role, band) attribution, a substantially new mechanism. Deferred: D105's allocation re-aim shrinks the waste organically (mr/trend/rv draw share falls toward their yield), and the prefilter already blocks most dead submissions. Revisit if post-D105 zero-trade share stays >70% on the up-weighted classes.

**(b) General bounds-learning.** The handoff's proposed mechanism — any sampled parameter band with N ≥ ~100 decided and 0 components becomes a floor-weight/drop candidate — needs per-band outcome attribution over `submissions.config_json` params x gated outcomes, plus proposer integration (auto-tighten path for drops, OPEN_PROPOSALS for widenings). D105 ships only the one decisive instance by hand (rv lookback 378: 155/0). Build the general mechanism when a second instance shows up — one data point doesn't justify the machinery.

**Tag:** `feedback`, `prefilters`, `thresholds`, `relates-to-D105`, `relates-to-D076`, `relates-to-D099`, `deferred`

## 2026-06-09 — Q30 — v12's H2 arm emits ZERO event_momentum configs live: the published registry snapshot predates Crucible's `days_since_earnings` family reclassification — **RESOLVED 2026-06-09**

**RESOLVED (verified during the D112 emission proof):** Crucible republished the registry snapshot at 2026-06-09T18:45:50Z (`registry_snapshot_2026-06-09T184550Z.json`, hash `a99e00d68567af59`); `days_since_earnings` is now `family='calendar'`. A 3,000-sample emission proof on the new snapshot draws event_momentum 610 (vs 0 before) with a healthy 5-way mix. No Forge change was needed, as predicted — the run loop re-loads the registry each iteration. Original entry kept below for the mechanism record.

**Symptom:** a 3,000-config emission proof against the live export (seed 0, cold weights) yields 0 `event_momentum` configs; every draw is structurally rejected with `no directional indicator has a §3.5 S4-permitted DTE bucket with a C1/C4/R-valid regime partner`. Mix: trend_continuation 788 / volatility_event 747 / mean_reversion 742 / relative_value 723 / event_momentum 0.

**Mechanism:** the newest snapshot (`registry_snapshot_2026-06-08T132237Z.json`, hash `8f7e44d198bbc5e5` — the SAME hash recorded at the D109 deploy verify, so v12 has run on it since launch) still carries `days_since_earnings` with `family='post_event_drift'`. D109's design depends on Crucible's `days_since_earnings`→`calendar` reclassification (confirmed landed in `FORGE_days_since_earnings_family_response.md`), because §3.5 C1 requires the regime gate's family to differ from the directional's (`sampler._compatible_regimes`): with the stale family, `days_since_earnings` (event_momentum's ONLY permitted regime gate, `_EVENT_MOMENTUM_REGIME_INDICATORS`) shares `sue`'s `post_event_drift` family → no valid regime partner → `_directional_candidates` empty → 100% structural rejection. Forge's v12 tests pass because fixtures use the post-reclassification family. `crucible-registry-publisher` is oneshot-at-startup, so Crucible's code-side reclassification never reached the published export.

**What I did instead:** nothing Forge-side — correct per design (Forge defers to the export; hard rule #2 says a stale export is Crucible's to republish, not Forge's to patch around). Logged here + STATUS; emission-proof recipe added to `docs/tasks/grammar-change.md` (this finding came out of its doc-verification walkthrough).

**Resolve by:** operator asks Crucible to republish the registry snapshot (restart `crucible-registry-publisher` or equivalent). No Forge restart needed — the run loop calls `load_registry()` fresh every iteration (`cli/main.py`), so the next batch picks up the new snapshot (registry_hash changes; expected under #6). Verify with the emission-proof recipe (event_momentum > 0) and the journal submission mix. Note H1 is unaffected for trend/mean_reversion rank draws; the event_momentum rank-eligible arm is dead until this clears. Outgoing prompt ready: `PROMPT_CRUCIBLE_REGISTRY_SNAPSHOT_REPUBLISH.md`.

**Tag:** `crucible-coordination`, `registry`, `relates-to-D109`, `event_momentum`, `operator-action`

## 2026-06-09 — Q31 — event_momentum clears the grammar (post-Q30) but is 100% killed by the signal_density prefilter — **RESOLVED 2026-06-09: Crucible wiring bug, fixed in their `fd96707` + writer restart 17:18:21 PDT; post-restart probe matches their published ranges EXACTLY — H2/em unblocked, zero Forge changes**

**CLOSED (post-restart probe, 17:21 PDT, `/tmp/q31_probe_rerun.py`):** dse<7 = 92–165/name (their range 92–165), sue>1.0 = 60–505 (theirs 60–505), non-NaN dse 2,023–2,047 (~2,030 published; COIN 1,212 = 2021 IPO, legitimate), sue 527–1,413 (theirs 527–1,413) — **endpoint-exact agreement** with the distributions Crucible computed through the fixed path; control rsi_2<10 unchanged (324–434). One-liner relayed to Crucible via operator. **H2/event_momentum is data-unblocked as of 2026-06-09 17:18:21 PDT (2026-06-10 00:18:21Z) — the em-onset cohort boundary for all future em reads (mid-v14, writer-restart-keyed, NOT a grammar bump).** First live em emission will show as `ranked_top_n_by_hypothesis: event_momentum>0` at the next unblocked iteration; em rank draws stay dse-gated until the v15 re-key (class-map response, separate thread).

**Crucible response processed 2026-06-09 (~17:00 PDT, via operator relay):** (1) EPS ingest was fine — the writer's feature computations never received the symbol; fixed in Crucible commit `fd96707` (17:03:59 PDT), no Forge change needed. (2) **Hypothesis 1 CLOSED by their post-fix distribution numbers** (2126-day window, real bars): `days_since_earnings < 7` ≈ 92–165 activations/name; `sue > 1.0` ≈ 60–505 (SUE carries forward between prints — not print-count-bounded); non-NaN days dse ~2,030/name, sue 527–1,413 (NaN until ~11 quarters accrue; COIN's 2021 IPO → `sue > 1.5` = 0 is legitimate). All comfortably clear the §5.3.3 `min_activations=30` floor — **no event-cadence signal_density branch needed**; only deep-OTM combos (e.g. `sue > 2.0` on short-history names) die, correctly. (3) Their ask: after their writer restart, re-run the probe through the socket and relay the one-liner. **Probe re-run ~16:50 PDT (`/tmp/q31_probe_rerun.py`, existence + realistic specs + control): dse/sue still 0 on all 6 names, control rsi_2<10 healthy 324–434 — expected: the running writer (up since 16:09:35 PDT) predates `fd96707`. Re-run after their restart; if counts land in their published ranges, Q31 closes.** Cohort-hygiene note: when the fix goes live, H2/em starts passing signal_density MID-v14 — the em-onset boundary is the writer-restart timestamp, not a grammar bump. Original entry below.

**Update 2026-06-09 (probe executed):** ran the resolve-by probe against the live db-writer (`FeatureCacheClient`, registry `a99e00d68567af59`). Existence-level specs (`sue > −1000`, `days_since_earnings > −1` — any non-NaN day activates) return **0 activation dates on every name probed** (AAPL/NVDA/AMD/TSLA/NFLX/COIN) while the control `rsi_2 < 10` returns 324–434; the sentinel check (`days_since_earnings > 500`) is also 0. The series are entirely NaN/absent in the cache — **hypothesis 2**; signal_density is doing its job and no Forge change is warranted yet. Outgoing prompt: `PROMPT_CRUCIBLE_SUE_FEATURE_CACHE_COVERAGE.md` (asks: wire the EPS ingest to the feature computations; give us the real post-fix activation distribution — if it lands under the `min_activations=30` floor, the event-cadence signal_density branch (hypothesis 1) becomes a live operator-gated calibration decision SECOND). Original entry below.

**Symptom:** first post-v13 live iteration (batch `0e186240`, 2026-06-09 21:04Z): `sampler_attempts: event_momentum=783` (enumeration healthy after the Q30 registry republish) but `prefilter_rejections_by_hypothesis: event_momentum[signal_density=783]` — every em config rejected by §5.3.3, `ranked_top_n_by_hypothesis: event_momentum=0`. H2 has still never reached Crucible.

**Two hypotheses (decide with data before fixing):**
1. **`sue` activations are genuinely < 30 per name (likely).** PEAD is quarterly: ~20 earnings prints per single name in the data window, so a surprise-threshold directional structurally cannot reach `min_activations=30`. Same failure shape as the pre-D109 `expected_trades`-vs-rank mismatch — a prefilter calibrated on daily technical indicators mis-measures event strategies. The prefetch line `data_unavailable=[]` suggests the cache HAS the series (supports this hypothesis).
2. **`sue` series missing/empty in the db-writer feature cache** (Polygon EPS ingest is new; the writer restarted 2026-06-08). Then activations=0 and the fix is Crucible-side.

**Resolve by:** check `ctx.feature_cache.activation_dates("sig_directional")` counts for a sampled em config against the real cache (the daemon computes this every iteration — a small probe via the prefilter battery path answers it). If (1): propose an event-strategy branch for signal_density (e.g., density floor scaled by the regime gate's event cadence, or count post-event windows instead of raw activations) — prefilter calibration change, operator-gated, likely v14 or versionless per change taxonomy. If (2): outgoing Crucible prompt re: cache coverage for `sue`/`days_since_earnings`. Note em is also rank-eligible (H1) — but the rank draw happens at the sampler, and signal_density kills the config regardless of combiner, so the rank path is equally dead until this clears.

**Tag:** `prefilters`, `event_momentum`, `relates-to-D109`, `relates-to-Q30`, `signal-density`

## 2026-06-09 — Q32 — Crucible began ENFORCING `regime_coverage` (§20) ~2026-06-08 09:00 PDT: the single-name composable path now admits 0% of components, and the only config ever to pass BOTH promotion-quality gates was rejected on coverage alone — **RESOLVED 2026-06-10 (all four asks answered: coverage parity + fullhist-refit deploys + the v118 response; D124)**

**RESOLVED 2026-06-10 (processed as D124; full record there).** (1) Intent: intentional and doubled-down — rank got a real §20 floor (`6f2fa2e`, live 01:28:03Z) and pairs too (`4fd6ee2`, live 01:00:02Z); portfolio assembly filters to honestly-evaluated coverage (`28257e1` — only 19/295 all-time components were honest). (2) Windows: single-name DOES get full-history via the fullhist-refit two-stage lane (hourly, cap 20; the reject branch `coverage_blocked_component` reaches exactly the rejected-on-coverage-alone class) → **single-name confluence emission is NOT structurally dead; no emission change**. (3) Parity: shipped both paths. (4) **d964e908 re-gated and decided: child `b8b83495` (same config_hash) = component with honest coverage (3,072d span, start=0), but WF-median 2.225→0.280, CPCV-p25 1.537→0.953** — the only both-quality-gates pass ever was recency-fit; honest full-history reads it as positive-but-weak. Verified in the export + our verdicts table (both rows flow in automatically). Era-split keys for everything this entry warned about: cost-floor value-cut 2026-06-09T22:52:57Z + the `honest_regime_coverage` row marker — see D124 / `docs/tasks/investigate-live.md`. Original entry below for the record.

**Found during a read-only "what are we missing" analysis of the new `verdicts` table (10,089 rows, /tmp snapshot 2026-06-09 14:42 PDT).**

**Timeline (decided_at is PDT-naive per the documented trap):** components with `regime_coverage` FAIL were minted right up to 06-08 08:06 (29 that morning alone; 211 of the 241 all-time components have rc=FAIL — the gate was advisory). From 06-08 09:03 onward, **every** new component (30) passes rc only via the DEGRADED path (`coverage_unverified: no period/chain_floor supplied` — the rank/pairs runner paths); zero post-cut components have rc=FAIL.

**Post-cut decisions (06-08 09:00 → 06-09 14:42, n≈1,072):**
- Real-rc-evaluated path (single-name composable): **720 decisions → 0 components.** 716 fail rc; 4 pass rc but fail quality.
- Degraded path (rank + pairs): 352 → 30 components (8.5%).
- **66 rejects pass every gate except rc (+ at most the two promotion-quality gates)** — would-be components killed solely by coverage (49 on 06-08, 17 on 06-09; top directionals put_call_flow 20, returns_12m_skip1 15, put_wall_distance_pct 15; 3 of the 4 all-time joint near-misses are in this stream).
- **`d964e908f9aea66e`** (v9 volatility_event × SOXL, put_wall_distance_pct > −0.0061 × days_to_cpi < 9.5, swing_short, 123 trades, decided 06-08 11:07): passed **all ten other gates including WF-median 2.225 (gate 2.0) AND CPCV-p25 1.537 (gate 1.5)** — the only config in the table ever to pass both — rejected on rc alone. (Corrects the 06-09 review's "no config has ever passed both": that read predated the verdicts backfill.)

**Mechanism:** the gate demands window start ≤30 sessions after the data floor (2018-01-02) AND span ≥1460d. The dominant single-name runner window is 1825d starting **859 sessions (~3.4y) late** (~May 2021 → May 2026): 601/720 post-cut real evaluations show exactly 859. A handful of full-history runs (start=30) DO pass rc — so the runner can produce compliant windows but almost never does on this path. Meanwhile the composable-rank path supplies no period/chain_floor at all, so 100% of current component admission flows through an *unverified* gate.

**Why it matters:** (a) **~52% of current emission (last 5 batches: 522/1,000 single-name confluence) routes to a path with an observed 0% admission rate** while Crucible decisions are the binding resource (D110); (b) the D105/D106/H4 weight engines learn P(component) — the post-cut cohort will teach them "single-name died" when the truth is "the gate changed" (same cohort-trap class as D104; era-split at 2026-06-08 09:00 PDT needed for any weight load or analysis spanning the cut); (c) it beheads the only promote-grade frontier ever observed (v9 vol_event × dealer-flow × macro-calendar on SOXL/high-idio names).

**What I did instead:** read-only; logged here + STATUS; no code or weights change. **Needs a Crucible handoff** (operator-gated): (1) is rc enforcement on component admission intentional and permanent? (2) if yes, will single-name runs get full-history windows (the start=30 runs prove the data reaches the floor)? (3) should the rank/pairs path supply period/chain_floor so component admission isn't 100%-via-unverified-gate? **Forge contingency per answer:** intentional + windows stay 5y → emission to single-name confluence is dead weight; tightening it away is the auto-tighten path (hard rule #4 allows), or constrain to indicator sets with full-floor history; runner bug → no Forge change, but either way split cohorts at the enforcement boundary.

**Tag:** `crucible-coordination`, `gates`, `regime-coverage`, `verdicts`, `cohort-hygiene`, `relates-to-D111`, `operator-action`

## 2026-06-09 — Q33 — Crucible's fail-open sweep: EVERY chain-reading regime gate is broken per-name on the rank/pairs paths — §3.5 R1 makes the entire MR rank arm structurally noise-gated (17.2% of current emission) — **RESOLVED 2026-06-09: operator chose option 1 (tighten now), shipped as grammar v14 (D116)**

**Resolution (2026-06-09, same session):** operator picked option 1 via AskUserQuestion. Shipped as **D116 / grammar v14** — `CHAIN_READING_INDICATOR_IDS = {iv_rank, put_call_flow}` joins the dealer family as single-name-only at both D112 enforcement points (rank-branch skip + rv regime pool). MR structurally never ranks until Crucible's reference-underlying gate ships (the D115 trigger, AGREED-DEFERRED their side). Original entry below.

**Map residual CLOSED (2026-06-09 evening, D118/v15):** Crucible's map landed (`FORGE_rank_gate_class_map.md` + `rank_gate_class_map.json`, 45 indicators) and the interim set was re-keyed same session — `sue`/`days_since_earnings`/`days_to_earnings` (any role) + `expected_value_estimator` (gate/directional; the X2 kelly chain exempt) join the exclusion; **em joins MR as structurally never-ranking**; v15 deployed 2026-06-10T00:44:37Z. Their corrections: **EV is NOT garbage-mode** (runs-DB reference read, hidden-uniform w/ inert fallback) and **the pairs path evaluates NO regime filters at all** → the historical rv cohort (15,913/15,913 confluence, Forge-verified) re-reads as "ungated pairs," not noise-gated — the Q33 worst case ("garbage at scale on rv") did not occur. Still deferred: the feedback-side gate-class tag for rank verdicts (D114 sibling — now mechanically keyable on their map artifact); re-admission = their `rank_per_name_coherent` flip, not capacity.

**Origin:** incoming `../Crucible/docs/handoffs/FORGE_rank_gate_failopen_sweep.md` (2026-06-09, their answer to our D115 prompt's soft flag). Their probe (`probe_results/rank_gate_failopen_sweep.json`, same harness as the dealer probe) generalizes the D115 finding from one mode to **three**, classed by how the indicator uses spot — all stemming from the same `params.get("underlying","SPY")` decoupling (verified structurally in `iv_rank.py:73` and `put_call_flow.py:52`):

| mode | indicators (probed) | what the per-name rank gate actually computes | verdict-reading consequence |
|---|---|---|---|
| `inert_failopen` | dealer greeks (`gamma_flip` …) | NaN → `allow=True` no-op | arm was **ungated** (the D115/D112 case) |
| `garbage_mismatch` | `iv_rank` (any spot-dependent chain ind.) | SPY's chain IV interpolated at the NAME's spot | gate **fires on noise** — WF/CPCV confounded either direction; can spuriously *pass* configs |
| `hidden_uniform_reference` | `put_call_flow` (volume-only chain ind.) | SPY's value, identical for every name | a **market gate in disguise** — coherent but mislabeled |
| `coherent_per_name` (control) | `rv_rank` + all bar-only (rsi/adx/…) | the name's own bars | **fine** — read normally |

Modes are **structural/era-invariant** (code-level, window-independent) — no era-split needed for mechanism; era only matters for counting affected cohort rows.

**Forge-side exposure quantified (fresh /tmp snapshot, submissions ⋈ verdicts, 10,153 verdict rows):**
- **R1 tension (the HIGH part):** R1's MR regime pool is exactly `{iv_rank, gamma_flip_distance_pct}` (D107). D112/v13 removed gamma from rank eligibility → **every v13 MR rank config is iv_rank-gated: 172/172 — and on the rank path that gate fires on noise.** That is 63% of current rank emission and **17.2% of ALL v13-era emission (172/1,000)** routed to configs whose declared regime semantics do not compute. Trend rank is clean (R2 pool post-D112 = adx/hurst/rv_rank, all bar-only; 101/101 v13 trend rank coherent). No chain-reading rank *directionals* survive v13 either (the only one ever was gamma_flip ×52, killed by D112).
- **All-time rank components: 18/36 confounded** — 10 noise-gated (iv_rank MR rank), 8 ungated (gamma_flip; per D115). The 18 bar-gated (hurst/adx/rv_rank trend + none MR) are clean. Every weight-engine read of "rank mints" (v12's 21.4% headline, D110/D112 rank-share reasoning) includes this pollution; same mislearning class as Q32, now with a structural (not era) split key: regime-gate indicator class.
- **rv/pairs path: minor today** — v13-era 4/97 iv_rank-gated, 0 put_call_flow; legacy v9 rv components include 4 dealer-inert + 2 iv_rank + 1 put_call_flow of 31. **Open classification gap:** `expected_value_estimator` — the all-time top rv regime gate (1,824 uses) — is unclassified (chain-reading? spot-dependent?); fell out of the current rv mix but dominates historical rv cohorts. Asked Crucible for the full registry→mode map (they offered).

**Why surfaced, not fixed (the operator gates):** the minimal fix mirrors D112 exactly — chain-reading regime gates exclude the rank branch (and rv pool), keyed on the indicator *class* instead of the dealer family. But (a) under R1's operator-owned pool that **zeroes the MR rank arm entirely** (both pool members are now rank-broken) — a §3.5 rule in tension with reality, CLAUDE.md stop-and-ask trigger; (b) any alternative that keeps MR rank alive (e.g. admitting bar-only `rv_rank` as an R1 gate, conceptually the same vol-regime thesis) is an **edit to an operator-owned rule + a loosening** → `OPEN_PROPOSALS.md` + operator + arguably Crucible coordination; (c) a grammar bump (v14) is operator-gated regardless of direction. **Options queued for the operator:**
1. **Tighten (v14, D112 pattern):** chain-reading regime gates never take the rank branch → MR rank goes to zero until Crucible's reference-gate/hoist guard ships (same evidence trigger as the dealer re-admission, now class-wide). Trend rank (clean) keeps the breadth lever. Recommended: stops semantic lying + binding-resource waste + evidence pollution at the source.
2. **Status quo:** keep emitting noise-gated MR rank pending Crucible's §20 class-wide fix (their proposal doc now scopes the whole chain-reading family, still DEFERRED behind the single-name MR×gamma evidence trigger — i.e. indefinite). Costs 17.2% of emission on the binding resource.
3. **R1 pool widening (loosening + rule edit):** propose `rv_rank` (bar-only realized-vol percentile) as an R1-acceptable MR regime gate on the rank path only — keeps MR rank alive with coherent gating; needs `OPEN_PROPOSALS.md` + operator + likely a Crucible sanity-check that rv_rank-gated MR rank is worth decisions.
- (Feedback-side, any option: rank-cohort verdicts need the gate-class tag before weight loads — third sibling to D114's deferred era-split items; the verdicts table + config_json join above is the recipe.)

**Resolve by:** operator picks an option (AskUserQuestion pending this session). Response prompt to Crucible drafted regardless (accept the map offer; report our tagging numbers; flag `expected_value_estimator`).

**Tag:** `crucible-coordination`, `grammar`, `rank-path`, `R1-tension`, `verdicts`, `weight-pollution`, `operator-action`, `relates-to-D112`, `relates-to-D115`, `relates-to-Q32`

---

## 2026-06-09 — Q34 — R1's iv_rank gate direction vs the published single-name premium evidence: the rule's own "Why" argues both sides, and the literature's validated conditioner is the IV−RV *spread*, not the IV-rank *level* — **MEDIUM**

**Question:** R1 (GRAMMAR.md §R1) gates mean_reversion on `iv_rank` with `threshold ≤ 50, op "<"` — fire only when IV-rank is LOW. But the rule's own rationale text is internally two-sided: it opens "mean-reversion strategies make money by **selling rich premium** that mean-reverts" and "selling premium when IV is already low … is selling lottery tickets — there's no premium to capture," then concludes the gate forces firing "only when IV is **cheap**." Those argue opposite gate directions. Which direction the evidence supports depends on a fact Forge does not control: whether Crucible's MR position templates are net SHORT premium (credit spreads — then the documented edge wants IV **rich**) or net LONG premium (debit structures betting on underlying reversion — then cheap-IV entry is right).

**What the literature says (deep-research session, this date; sources verified):**
- Goyal & Saretto (JFE 2009): sorting single names on log(12-month realized vol / ATM IV) predicts option returns — long premium where IV is *cheap vs the name's own realized*, short where *rich*; long-short straddle deciles earned 21.9%/mo gross, ~4.1%/mo at quoted-spread costs (costs, not decay, are the binding constraint). The conditioner is the **IV-vs-own-realized spread**, not the IV level/percentile alone.
- Israelov & Nielsen (JPM 2015, "Still Not Cheap"): absolute IV level is explicitly NOT a valid timing signal — low IV typically accompanies even lower realized; the implied-minus-subsequent-realized spread is what prices.
- Bakshi & Kapadia (JoD 2003): single-name VRP is thin (~1.5%/yr vs ~3.3% index) and conditions on **market** vol level, not firm vol — short-premium MR earns more when market RV is high.
- Carr & Wu (RFS 2009): raw single-name variance premia insignificant for 32/35 names — unconditioned single-name premium selling has little documented edge; conditioning is everything.

**Why this is a Q-entry, not a fix:** R1 is operator-owned (§3.5, hard rule #1); any pool/direction change is a rule edit, and admitting a new conditioner is a loosening (OPEN_PROPOSALS path). R1's own "Evidence to relax" line already anticipates exactly this: "custom realized-vs-implied ratio."

**Asks:** (1) confirm with Crucible what the MR position templates' net premium sign actually is per DTE bucket (determines which side of the iv_rank gate the evidence supports); (2) contracts/indicator gap candidate for the next round-trip: an `iv_minus_rv`-class spread indicator (ATM IV minus trailing realized, per-name) — the single best-validated single-name premium conditioner in the literature; Crucible already computes both inputs (iv_rank needs ATM IV history; realized_vol ships).

**What I did instead:** logged; no grammar/code change. MR single-name emission continues under R1 as written.

**Tag:** `grammar`, `R1-tension`, `literature-priors`, `contracts-gap`, `operator-action`, `relates-to-Q33`

---

## 2026-06-09 — Q35 — P3's delta bands put trend's long-options expression in the literature's worst zone (embedded-leverage premium): swing_long trend = 0.20–0.35Δ, exactly the high-embedded-leverage region documented to carry negative alpha drag — **LOW**

**Question:** Frazzini & Pedersen (RAPS 2022, "Embedded Leverage"): options with high embedded leverage (low-delta/OTM, short-dated) earn LOWER risk-adjusted returns — long-low-leverage/short-high-leverage portfolios significant at t=8.6 (equity options) / t=6.3 (index options). Leverage-constrained buyers overpay for embedded leverage; a systematic long-OTM-options buyer pays that premium structurally. P3 maps trend_continuation's longest horizon (swing_long, 60–90 DTE) to delta 0.20–0.35 — the most embedded-leverage-rich band Forge emits — and caps all bands at 0.55, so no ITM/low-leverage expression exists for any hypothesis. The literature design rule for expressing a directional anomaly in options: prefer higher delta / longer date, or spread structures that sell the expensive leverage back (debit spreads), unless deliberately net-selling embedded leverage.

**Tension, not error:** P3's rationale (low gamma, room for trend, convexity) is real, and trend's convex-payoff design (no hard_profit_target, S5) deliberately wants tail payoff. The cost side (FP2022's drag) was just never priced into the band choice. Whether 0.20–0.35Δ trend longs are net-positive after the embedded-leverage premium is an empirical question Crucible's gate answers — but the prior says the high-delta edge of each band should outperform, and a band widening (e.g. trend swing_long up to ~0.50–0.55, or >0.55 if ever warranted) is an operator-gated grammar change + Crucible position-builder question.

**What I did instead:** logged as a literature prior; no proposal. Cheap evidence first: when enough trend verdicts accumulate, read promotion/quality vs sampled delta_target within-band (verdicts table + config_json) — if the high-delta edge dominates, that's the "Evidence to relax" for P3.

**Tag:** `grammar`, `P3`, `literature-priors`, `evidence-readout-recipe`, `relates-to-D114`

---

## 2026-06-09 — Q36 — Literature-validated regime conditioners Forge cannot currently express: IV−RV spread, VIX term-structure slope, market-state, cross-sectional dispersion (contracts/indicator gaps); ADX/Hurst (R2's pool) lack peer-reviewed OOS validation — **LOW**

**Question:** the deep-research pass ranked conditioning variables by replication strength. The top of the list is only partially expressible in the current 45-indicator registry:

| Conditioner | Evidence | Forge today |
|---|---|---|
| Strategy-specific trailing realized vol (scale/gate by own RV) | Barroso & Santa-Clara JFE 2015 (~2× momentum Sharpe, kills crash tail); Daniel & Moskowitz JFE 2016 | **HAVE** — `rv_rank` (R2 pool), `realized_vol` + X1 `vol_target` sizer; best-supported members of their pools |
| VIX term-structure slope (contango/backwardation) | Johnson JFQA 2017 (slope predicts variance-swap/VIX-futures/straddle returns at ALL maturities; the validated short-vol gate); Simon & Campasano JoD 2014 | **GAP** — `vix_level` is a stub; no VIX term-structure data at all |
| IV − trailing-RV spread (per name) | Goyal & Saretto JFE 2009 (see Q34) | **GAP** — `iv_rank` is IV-vs-own-IV-history, not IV-vs-RV |
| Market state (sign of trailing 12–36m INDEX return; bear-rebound flag) | Cooper/Gutierrez/Hameed JF 2004 (momentum +0.93%/mo after up-markets vs −0.37% after down); Daniel-Moskowitz crash indicator | **GAP** — indicators evaluate on the name's own bars; no market-level state gate exists for single-name configs (`vix_level` stub is the closest cousin) |
| Cross-sectional return dispersion | Stivers & Sun JFQA 2010 (high dispersion → cut momentum, favor reversal/pairs) | **GAP** — no universe-level dispersion indicator |
| Pair quality: OU half-life, formation zero-crossings, sector homogeneity | Avellaneda & Lee 2010; Do & Faff 2010/12 | **Crucible-side** (it selects pairs/half-life); relevant to the deferred "should rv draw regime gates at all" — literature answer is yes: turbulence/dispersion gates (Do-Faff: pairs work in prolonged turbulence; Zhu Yale 2024: +0.8%/mo per +1% BAA−AAA, robust to VIX substitution) |
| ADX / Hurst trend gates | **No peer-reviewed OOS validation found** (Hurst appears only in pairs-allocation literature; ADX practitioner-only) | R2's pool — they stay (operator-owned); prior says `rv_rank`/`gamma_flip` are the evidence-backed members |

Note all four GAP rows are `market_wide_by_design`-class (or per-name chain-derived for IV−RV) — the rank-coherence classification from Q33/D118 applies and should be declared at birth if any ship.

**What I did instead:** logged; gaps are contracts asks to queue for a future Crucible round-trip (not workarounds — hard rule #2); no emission change. Full research report delivered in-session (2026-06-09 deep-research: ~45 sources, claims adversarially verified, zero refutations on 27 votes).

**Tag:** `contracts-gap`, `literature-priors`, `regime-gates`, `crucible-coordination`, `relates-to-Q34`
