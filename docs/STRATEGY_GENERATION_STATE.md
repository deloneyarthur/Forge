# Forge — Strategy Generation: State of the System

> **STALE — historical snapshot (banner added 2026-06-09).** Written at grammar **v4** /
> contracts 1.13.0; the system is now at v12 / 1.16.0 with a substantially re-aimed feedback
> loop (D098–D110). The mechanics narrative (how enumeration/pre-filtering/ranking work) remains
> broadly accurate; **all numbers, weights, search-space counts, and gap analyses are
> superseded.** Current state: `STATUS.md` top block + `IMPLEMENTATION_DECISIONS.md` D095+.

**Date:** 2026-05-29
**Status:** Living discussion document — describes how Forge generates strategies *today* (grammar v4, contracts 1.13.0, post-D095).
**Purpose:** A single place to judge whether Forge's generation approach is **strong and correct**. It is deliberately verbose: it covers the grammar, the enumeration mechanics, the path from candidate to submission, the feedback loop, what gives Forge its edge, the recent changes, and — most importantly — what the live data shows and where the gaps are.
**Source of truth:** `docs/DESIGN.md` always wins on intent. Where this doc and DESIGN.md disagree, it is flagged inline (DESIGN.md has several known stale spots; see §11). All numbers were verified against live code, the live registry export (`registry_snapshot_2026-05-28`, 43 indicators), and Forge's own DB on 2026-05-29.

---

## 0. TL;DR — is generation strong and correct?

**Correct: yes, with high confidence.** Forge produces only grammar-valid configs, deterministically and reproducibly, and defers all quality judgment to Crucible's gate. The machinery (enumerate → pre-filter → rank → submit → reconcile → learn) is sound, tested (1201 tests green), and running.

**Strong: partially, and improving — but honestly not yet.** Forge's job (§1.2) is for its submissions to become *more likely to promote over time*. Today that rate is **0 promotions across 29,749 gated runs**, and the binding reason is upstream of quality: **~60% of the runs Crucible actually decides trade zero times** (`min_oos_trade_count` is the dominant gate failure). Until configs reliably *fire*, the edge gates (Sharpe, PBO, regime-stress) are barely exercised.

The two structural weaknesses, and where each stands:
1. **The enumerator had no gradient toward edge.** Its only learned signal was promotion rate = always 0, so it explored ~uniformly. **Fixed this session (D094):** it now learns from trade-production + gate-progress and is already steering (verified live: hypothesis weights went from flat 0.05 to a real 0.52–0.66 spread).
2. **Constrained hypotheses have tiny structural spaces** the grammar+registry can't currently expand (relative_value has exactly **1** directional indicator; mean_reversion has **2** valid skeletons). Generation effort there produces near-duplicates that zero-trade. **Being addressed:** universe widening (in flight, Crucible-side) + threshold calibration; the deepest fix (more registry indicators) is Crucible-owned.

So: the *method* is correct; the *yield* is not yet strong, the binding constraint is understood (zero-trade, not bad-edge), and the highest-leverage lever (closed-loop steering toward trade-production) just went live. The rest of this doc is the evidence.

---

## 1. What Forge is (and is not)

Forge is the **producer** in the **Forge → Crucible → QuantIQ** pipeline. It enumerates grammar-valid option-strategy configurations, cheaply pre-filters them, ranks the survivors, and submits the best to Crucible's inbox. Crucible runs the expensive walk-forward / CPCV gauntlet and is the **sole authority on promotion**.

Three principles shape everything:

- **Producer, not validator (§1.2, §1.3).** Most candidates Forge submits *will* be rejected. That is correct behavior. Forge does not try to be right about individual candidates; it tries to make its *stream* of submissions progressively more promotable.
- **Defer to Crucible.** Forge never lowers Crucible's gate. Grammar can change (what gets enumerated); the gate cannot (what counts as good). Auto-*tightening* can ship autonomously; auto-*loosening* always waits for an operator (hard rule #4).
- **Deterministic, no LLM in the loop.** Given `(grammar_version, registry_version, seed)`, enumeration is byte-reproducible. The enumerator, pre-filters, ranker, submitter, and feedback are all deterministic Python (hard rules #5, #6). Claude/operator grammar-refinement happens *outside* the running system.

**Where the "edge" actually comes from.** Forge cannot manufacture alpha — Crucible decides. Forge's edge is four things, in order of leverage:
1. **A constrained, expressive grammar** that only emits *plausible* strategies (no nonsense configs waste Crucible's compute).
2. **Cheap pre-filtering** that kills configs which can't trade or show no signal *before* they cost a backtest.
3. **A feedback loop** that learns which regions of the space produce trade-firing, gate-progressing configs and steers future enumeration there (this is the part that makes the submission stream improve over time — and the part most recently strengthened).
4. **Determinism + reproducibility** so every result is attributable to an exact `(grammar, registry, seed)` and learning is auditable.

---

## 2. The pipeline at a glance (§2.1)

Each batch runs this fixed order; cross-batch state lives only in Forge's DuckDB (`~/forge_data/forge.db`), never in process memory.

```
 1. Load grammar (config/grammar.yaml)  ── verify version + archive
 2. Snapshot registry (crucible_contracts.RegistrySnapshot, from Crucible's export)
 3. ENUMERATOR        → grammar-valid StrategyConfigs (lazy, seeded, hypothesis-first)
 4. PRE-FILTER BATTERY → 9 filters, cost-ascending, short-circuit on first failure
 5. RANKER            → §6.2 composite score
 6. DIVERSIFIER       → greedy top-N with diversity penalty
 7. SUBMITTER         → atomic write to Crucible inbox + submissions row (idempotent)
 8. RATE LIMITER      → wait until ≥80% of the oldest in-flight batch is really gated
 9. FEEDBACK CONSUMER → read Crucible's gated_runs export, join on config_hash
10. ANALYZER          → batch_summaries, pre_filter_logs, promoted_patterns
11. PROPOSER          → auto-apply tightenings; write loosenings to OPEN_PROPOSALS.md
```

Steps 9–11 feed back into steps 3–4 of *future* batches via two learned inputs:
`hypothesis_weights` (steers what gets enumerated) and `trade_rate_priors` (steers what survives the `expected_trades` filter). This loop was silently broken for ~5 days mid-May and revived 2026-05-29 (D084); it is now active every iteration.

---

## 3. The Grammar — the heart of Forge (current: v4)

The grammar is what makes Forge's output *plausible by construction*. It is operator-owned (hard rule #1): the 21 rules are implemented as written; changes require a version bump + archive + Decision Log (hard rule #10).

### 3.1 Hypotheses (the top-level "thesis" of a strategy)

Every config carries exactly one `hypothesis` (rule S1). Six exist; five are sampled:

| Hypothesis | Sampled? | Note |
|---|---|---|
| `trend_continuation` | yes | |
| `mean_reversion` | yes | |
| `regime_arbitrage` | yes | the "any-family-directional" catch-all — by far the largest space |
| `relative_value` | yes | pairs-only; structurally tiny (see §4.4) |
| `volatility_event` | yes | event-proximity gated |
| `tail_hedge` | **no — excluded (D066)** | Crucible's runner rejects standalone tail_hedge at dispatch; it belongs to overlay semantics. Kept in grammar.yaml (operator-owned) but excluded at *runtime* via `OVERLAY_ONLY_HYPOTHESES`. Pre-D066 it was ~46% of wasted submissions. |

The hypothesis is chosen **first** in sampling, and (since D094) **weighted** by learned reward — but the choice is independent of how many downstream configs each hypothesis can produce. So a tiny structural space does *not* make a hypothesis rare; it makes its configs *near-duplicates* (which the novelty filter then kills). This distinction matters a lot (see §4.4, §9).

### 3.2 The 21 rules (§3.5)

Grouped by concern. Predicate type in brackets. "Amended" marks where the live behavior extends the literal v1 text (all tracked via version bumps + Decision Log).

**Structural (S1–S5):**
- **S1** [cardinality] — exactly one `hypothesis`.
- **S2** [cardinality] — exactly one `directional` signal.
- **S3** [cardinality] — at least one `regime_filter` signal.
- **S4** [custom] — DTE bucket must match the directional signal's lookback class (short ≤6 / medium 7–89 / long ≥90 days → bucket).
- **S5** [custom] — exit framework consistent with hypothesis. **Amended (v3/D071):** rewritten from "one required exit" to a 4-part composition per hypothesis — `required_always` + pick-exactly-one `required_from_set` + 0..2 `optional_additions` + `forbidden`. The entire schema lives in `_S5_HYPOTHESIS_EXITS` (Python); the YAML body was unchanged.

**Composition (C1–C4):**
- **C1** [custom] — no two indicators share a `family` (forces signal diversity). 12 families.
- **C2** [custom] — the directional signal's family must match the hypothesis. **Amended (D062):** mean_reversion also accepts `dealer_positioning`; volatility_event also accepts `dealer_positioning`. (`regime_arbitrage` = any family.)
- **C3** [cardinality] — at most 4 signals.
- **C4** [custom] — the regime gate cannot reuse the directional indicator's id.

**Parameter coherence (P1–P4):**
- **P1** [custom] — signal `params` keys ⊆ the indicators' registry `params_schema`.
- **P2** [custom] — entry-DTE window per bucket: swing_short (14,21) / swing_mid (30,45) / swing_long (60,90).
- **P3** [custom] — delta-target band per bucket: (0.40,0.55) / (0.30,0.45) / (0.20,0.35).
- **P4** [numerical_range] — `sizer.per_trade_risk_pct` ∈ [0.005, 0.02]. *(The only rule using `numerical_range`; upper bound also pinned by contracts `ABSOLUTE_MAX_PER_TRADE_RISK_PCT`.)*

**Exit logic (E1–E3):**
- **E1** [custom] — the 4 mandatory exits present: `expiry_exit`, `theta_cliff_exit`, `earnings_exit`, `liquidity_exit`. *(DESIGN.md §3.5 says 3; contracts pins 4 — contracts wins, D007/D014.)*
- **E2** [custom] — at most 2 stop-loss exits.
- **E3** [custom] — a `trailing_atr` exit requires `activate_after_gain_pct ≥ 0.30`.

**Regime coherence (R1–R3):**
- **R1** [custom] — mean_reversion requires an `iv_rank` regime gate with `threshold ≤ 50`.
- **R2** [custom] — trend_continuation requires a regime gate in **{adx, hurst, rv_rank}**. **Amended (v4/D077):** added `rv_rank` ("enter trend longs when realized vol is cheap").
- **R3** [custom] — volatility_event requires an event-proximity gate in **{days_to_earnings, days_to_fomc, days_to_cpi, days_to_nfp, days_to_opex}**. **Amended (v2/D039):** expanded from 2 to 5; also rejects ETF underlyings paired with `days_to_earnings`. *(Follow-on M-9 made cpi/nfp/opex actually samplable — the widening was inert until 2026-05-29.)*

**Risk coherence (X1–X2):**
- **X1** [custom] — `sizer.mode == vol_target` requires a `realized_vol` signal.
- **X2** [custom] — `sizer.mode == fractional_kelly` requires an `expected_value_estimator` signal.

### 3.3 Signal families (12)

`trend`, `trend_strength`, `mean_reversion`, `volatility`, `iv_structure`, `dealer_positioning`, `flow`, `macro`, `calendar`, `fundamental`, `smart_money`, `pairs`. *(DESIGN.md §3.5 lists 11 — stale; `trend_strength` added D019. `fundamental` has no live indicator yet.)* Live registry family counts: trend 10, volatility 9, mean_reversion 6, dealer_positioning 6, calendar 5, trend_strength 2, and flow/iv_structure/macro/pairs/smart_money 1 each.

The C2 directional-family pins (the heart of why hypotheses differ in expressiveness):

| Hypothesis | Allowed directional families |
|---|---|
| trend_continuation | `trend` |
| mean_reversion | `mean_reversion`, `dealer_positioning` |
| regime_arbitrage | **any** |
| relative_value | `pairs` |
| volatility_event | `iv_structure`, `flow`, `dealer_positioning` |
| tail_hedge | `macro` (excluded at runtime) |

### 3.4 Predicate types (§3.4)

Six exist; the live grammar uses three. `cardinality` (S1/S2/S3/C3), `numerical_range` (P4), `custom_python` (the other 16 rules). `requires`, `forbids`, and `compatibility` are implemented and tested but no v1 rule references them (the cases that would use them — e.g. S4's lookback→DTE table — were implemented as `custom_python` instead, D018).

### 3.5 What the grammar guarantees

Because S1–X2 are enforced both at sampling time (valid-by-construction) and re-validated on every emitted config, **every config Forge submits is grammar-valid**. The grammar also bakes in upstream guards: e.g. it cannot emit `equity` as a signal family (hard rule #7 — Crucible is options-only). The grammar is the contract that lets the rest of the pipeline assume well-formed input.

### 3.6 Version history (v1 → v4)

| Version | Date | Change | YAML diff |
|---|---|---|---|
| v1 | 2026-05-13 | initial 21-rule grammar | — |
| v2 | 2026-05-17 (D039) | R3 → 5 event indicators + ETF-incompatibility | only R3 `version: 1→2` |
| v3 | 2026-05-19 (D071) | S5 → multi-exit composition + 4 new exit classes | **none** (schema is Python-side) |
| v4 | 2026-05-27 (D077) | R2 accepts `rv_rank` | only R2 `version: 1→2` |

A striking property: **the real grammar semantics live in `custom_predicates.py` constants, not the YAML.** Two of three bumps changed a single `version:` field; one changed no rule body at all. This is by design (the YAML declares structure; `custom_python` holds domain logic) but is worth knowing when reading the grammar — `config/grammar.yaml` alone does not tell you what the grammar does.

---

## 4. How generation works (§4)

### 4.1 The flow

```
build_search_space(grammar, registry)   # pure: pre-resolve the CSP coordinate space once/batch
        │  per-hypothesis directional pools (C2-filtered), regime pools (R-rule-filtered),
        │  samplable sizer modes (X-rule-satisfied), DTE/delta/risk tables, S5 exit maps
        ▼
sample_config(space, registry, rng, hypothesis_weights)   # hypothesis-first stratified sampler
        │  (1) hypothesis  [weighted by D094]  → (2) sizer mode → (3) DTE bucket
        │  (4) directional indicator → (5) regime indicator [C1/C4-disjoint, S4-ok]
        │  (6) selector params → (7) sizer params → (8) exits → (9) X-chain confluence if needed
        ▼
defaults  # fixed fields the v1 grammar doesn't constrain (selector OI/volume/spread, kelly/vol defaults)
        ▼
iterator.enumerate_candidates(...)   # lazy generator; re-validate() each config; retry budget; D037 floor
```

### 4.2 Valid-by-construction, not generate-and-reject

The sampler is a **hand-rolled stratified rejection sampler** that builds each config in dependency order so it satisfies the grammar by construction; the final `validate()` is a safety net, not the primary mechanism. *(DESIGN.md §4.2 says the enumerator uses `networkx` + `python-constraint`; it does not — that's a stale spec note. The hand-rolled approach is faster and was chosen deliberately; networkx was later pruned.)* The retry budget is `max_candidates × 100`; exhaustion raises `EnumerationCapped`.

### 4.3 Determinism + the seed

The reproducibility triple is **`(grammar_version, registry_hash, seed)`**; identical triples produce byte-identical candidate sequences (hard rule #6, property-tested). All randomness flows through `SeedHierarchy` (blake2b-derived sub-seeds) — no naked `random`/`numpy` RNG anywhere outside `core/seed.py` (hard rule #8, invariant-scanned).

The **seed advances per batch**: `effective_seed(root, iteration) = SeedHierarchy(root).derive(f"batch_{iteration:08d}")`, where `iteration = 1 + COUNT(DISTINCT forge_batch_id)`. So each batch explores a different region, and restarts *resume* rather than re-enumerate from zero. Two enumeration-shadowing inputs outside the triple (auto-tightened thresholds, the universe fingerprint) are folded into the recorded batch identity (`enumeration_inputs_hash`) so determinism is still attributable.

### 4.4 The structural space per hypothesis (live registry)

This is the single most important table for judging generation breadth. "Valid (dir, reg) pairs" = distinct structural skeletons (directional × regime indicator pairs that satisfy C1/C4/S4) before parameter sampling:

| Hypothesis | directional pool | regime pool | **valid (dir, reg) skeletons** |
|---|---|---|---|
| regime_arbitrage | 35 | 36 | **907** |
| relative_value | **1** (`pairs_zscore`) | 36 | **35** |
| volatility_event | 5 | 5 | **20** |
| trend_continuation | 7 | 3 | **12** |
| mean_reversion | 9 | **1** (`iv_rank`) | **2** |

`regime_arbitrage` has a ~450× larger structural space than `mean_reversion`. Because the hypothesis is picked first (and the structural count does not bias that pick), the constrained hypotheses repeatedly draw the *same handful of skeletons* with different numeric params — which the param-aware novelty fingerprint (D069) then dedups, so they mostly fail to reach submission. **This is the structural root of the "monoculture" tendency and of relative_value's ~97.5% zero-trade rate** (one directional indicator can only express so much). The grammar+registry, not the sampler, is the limiter here.

### 4.5 Selector / sizer / DTE / exits (what gets filled in)

- **DTE buckets:** swing_short / swing_mid / swing_long, with the P2 entry windows and P3 delta bands above.
- **Sizer modes:** `fixed_risk_pct`, `vol_target` (needs realized_vol), `fractional_kelly` (needs expected_value_estimator). `per_trade_risk_pct` is sampled in [0.005, 0.02]; `kelly_fraction` in [0.10, 0.50] and `vol_target_annual` in [0.10, 0.30] are sampled *only* when their mode is active (D074), else fixed defaults.
- **Selector:** `delta_target` sampled within the P3 band; `dte_min`/`dte_max` sampled within the bucket window. **Fixed (never sampled):** `min_open_interest=100`, `min_volume=10`, `max_bid_ask_spread_pct=0.10`, `delta_tolerance=0.05`, `prefer_monthly_expiry=False` — these liquidity gates are constant across all configs.
- **Exits:** the 4 mandatory + the S5 per-hypothesis composition (e.g. trend_continuation picks one of trailing_atr/chandelier/parabolic, optionally adds time_stop, forbids hard_profit_target).

### 4.6 The stratification floor (D037)

To stop the Bayesian weighter from starving a hypothesis to zero, a `_PRODUCTION_MIN_HYPOTHESIS_FRACTION = 0.02` floor forces a per-hypothesis minimum via round-robin `forced_hypothesis`, capped at 50% of the budget. A hypothesis whose CSP keeps dead-ending gets blacklisted for the rest of the batch (`_FORCED_FAILURE_CAP=20`). This complements the D067 exploration floor on the *weights* (≈0.05).

---

## 5. From candidates to submissions (§5–§6)

### 5.1 The pre-filter battery — 9 filters, cost-ascending, short-circuit

Filters run cheapest-first and short-circuit on the first failure (so an expensive filter never runs on a config a cheap one already killed). The 9 (DESIGN §5.2 lists 7; D038 `predicted_activations` and D042 `signal_correlation` are additive extensions):

| Tier | Filter | Rejects when… | Calibrated from data? |
|---|---|---|---|
| 1 | structural_redundancy | config hash seen in a prior batch | n/a (exact) |
| 2 | resource_feasibility | infeasible resource profile | n/a (rare) |
| 3 | signal_density | directional signal fires < 30 times historically | hand-set floor |
| 4 | predicted_activations | predicted entries < 10 | hand-set |
| 5 | **expected_trades** | bucket's empirical P(n_trades ≥ 50) < 0.10 | **yes — from real gated trade counts** (D076) |
| 6 | novelty | structural fingerprint duplicate, OR temporal firing overlap > 0.80 | hand-set |
| 7 | signal_correlation | signal-set Jaccard overlap > 0.85 | hand-set |
| 8 | regime_exposure | single-regime concentration > 0.80 | hand-set |
| 9 | **permutation_test** | real notional p-value > 0.10 vs a forward-return permuted null | hand-set threshold |

**The binding constraint, by grammar version (from `batch_summaries`):**

| Filter | v2 | v3 | **v4 (current)** |
|---|---|---|---|
| permutation_test | 63% | 50% | **12%** |
| **expected_trades** | 3% | 18% | **69%** |
| predicted_activations | 15% | 16% | 8% |
| signal_density | 8% | 11% | 8% |

In v4, **`expected_trades` is the dominant rejector (69%)**, having displaced the permutation test. This is healthy in principle — it means Forge is increasingly rejecting configs predicted to under-trade *before* spending a backtest. The caveat (§9): the empirical mode needs ≥20 real gated samples per `(hypothesis, dte_bucket, family)` bucket; under that floor it falls back to a weak activations heuristic — and the starved hypotheses (relative_value, mean_reversion) have ~0 v4 gated data, so it can't yet judge exactly the configs that zero-trade most.

Two important truths about the filters:
- **They run on REAL market features.** Production runs `--require-real-cache`: if Crucible's feature-cache writer is unavailable, the iteration is skipped rather than silently falling back to synthetic (Gaussian-noise) features. A degraded per-underlying window yields a typed `data_unavailable` verdict, distinct from a signal-quality FAIL (D090). So filter verdicts are trustworthy.
- **The permutation test is sound only recently.** Until 2026-05-29 (D088) it built its null pool from only the signal's own activation-day returns (a degenerate self-comparison); historical permutation rejections (v2/v3) are not statistically trustworthy. It is correct now (forward-horizon returns vs a full-window null), which is partly why its v4 rejection share dropped — it is no longer over-rejecting against a broken null.

### 5.2 The ranker (§6.2) and diversifier (§6.3)

Survivors are scored by a fixed composite:

```
score = 0.30·signal_density + 0.25·novelty + 0.20·regime_exposure + 0.15·permutation + 0.10·prior_promotion_proximity
```

then the diversifier greedily picks the top-N (200) with a diversity penalty so near-twin signal-sets don't crowd the batch.

**Honest assessment of the ranker (this is a real finding):** among submitted survivors, the composite is nearly flat. `novelty` is ~always 1.0 (survivors are novel *by definition* after dedup), `prior_promotion` is identically 0 (nothing has promoted), and `permutation` *was* squashed into [0.90, 1.0]. So ~0.50 of the weight carried little variance, making "top-200 of ~277 survivors" close to random. **D095 (this session)** re-graded the permutation sub-score to use its full passing range, restoring real resolution there. `novelty` (saturated by correctness) and `density` (already log-graded) are left as-is; a §6.2 re-weight to reclaim novelty's dead 0.25 was considered and **deliberately not taken** (it's a spec deviation; deferred). The diversifier's de-duplication, not the weighted ordering, is currently the more valuable half of this stage.

### 5.3 Submission + rate limiting

The submitter writes each config atomically (tmp-then-rename) to Crucible's inbox and records a `submissions` row; the `config_hash` is unique-indexed so the same config can never be submitted twice (hard rule #9, crash-safe transaction per D091). The rate limiter then blocks until ≥80% of the *oldest in-flight* batch has a **real** Crucible decision (D083 — it no longer counts the timeout-sentinel rows that used to make ~91% of "gated" rows fake, which had silently voided the throttle).

---

## 6. The feedback loop (§8–§9)

This is what makes the submission stream *improve* — the difference between a random generator and a learning one.

**Active, autonomous, every iteration:**
- **`hypothesis_weights` → enumeration.** Per-hypothesis weights bias the sampler's first choice. **As of D094 (this session)** these are computed from a *multi-class reward* — `0.6·trade-production + 0.4·gate-progress`, promotion = ceiling — Beta-smoothed and floored. Previously they learned only from promotions (always 0) and were flat. *Verified live 2026-05-29:* weights moved from a flat 0.05 to a 0.52–0.66 spread ordered by which hypotheses actually trade.
- **`trade_rate_priors` → pre-filtering.** Per-bucket P(trades ≥ min) posteriors feed the binding `expected_trades` filter, recomputed each iteration from gated runs (with v4-current-grammar weighting, D081).

**Active but report-only (operator-gated; hard rule #4):**
- **Analyzer** writes `batch_summaries`, `pre_filter_logs`, `promoted_patterns`.
- **Proposer** fires §8.4 triggers; **tightenings** can auto-apply (calibration only, capped at 30% cumulative, §5.5) but in practice almost never fire (they require a rolling promotion rate > 5%, which never happens); **loosenings** always write to `OPEN_PROPOSALS.md` and wait for the operator.
- **Threshold auto-tightening** (`config/auto_tightened_thresholds.yaml`) narrows per-indicator sampling bands to the high-trade percentile range — but it is a **manual script**, not loop-wired, and is tighten-only (running it repeatedly only narrows the space).
- **Stuck-state detector** counts consecutive zero-promotion batches (currently ~39) and emits a WARN — it observes but does not act.

**A key operating insight:** in the current regime, *tightening is the wrong lever.* Forge does not have a "too much junk passes the filters" problem (the filters reject ~95% already); it has a "what passes doesn't trade" problem. More tightening shrinks an already-narrow space. The lever that matters is making generation produce trade-firing configs — which is exactly what D094 + the universe widening target.

---

## 7. Recent changes (the trajectory)

The improvement program (`FORGE_GENERATOR_IMPROVEMENT_PLAN.md`) has been steadily attacking the zero-trade problem. Landed:

- **D066** — exclude tail_hedge (killed ~46% wasted submissions).
- **D067** — exploration floor on hypothesis weights (anti-starvation).
- **D068/D072** — populate the pairs template's hidden entry-key contract (pairs were silently zero-trading).
- **D069** — param-aware structural fingerprint (broke the 100%-regime_arbitrage monoculture).
- **D071** — multi-exit grammar (v3): exits drive trade count more than entries.
- **D073/D074** — threshold-range calibration + DTE/sizer-knob sampling.
- **D075/D088** — permutation test moved to forward-horizon returns, then fixed to use a real null pool.
- **D076** — empirical-prior `expected_trades` filter (the binding v4 filter).
- **D077** — R2 accepts rv_rank (v4).
- **D083–D093** — full audit remediation (rate-limiter honesty, feedback-loop revival, crash-safety, contracts-boundary purity, universe read via contracts).

**This session (2026-05-29), deployed + verified:**
- **D094 — multi-class feedback weighting.** The enumerator now learns from trade-production + gate-progress, not just promotions. *This is the single highest-leverage generation change* — it gives the loop a gradient in the zero-promotion regime. (improvement-plan Phase 2.)
- **D095 — permutation ranker re-grade.** Restores resolution to the ranker's significance signal.

**Investigation outcomes this session (no code, but important):**
- **Q24** — the suspected "hidden template-param contract" in the non-pairs templates is **refuted**: Forge configs only ever reach `composable_long_options` / `pairs_convergence`, both of which Forge satisfies. The residual is a latent cross-repo risk (the pairs entry-keys are un-contracted) — recommended contracts hardening.
- **Q25** — the `universe_fallback_hardcoded` log is a Crucible publisher gap, not a Forge bug; and 24 *is* the canonical Tier 1+2 universe. Widening to ~152 is approved and handed off (`PROMPT_CRUCIBLE_UNIVERSE_EXPANSION.md`).

---

## 8. What the live data shows (the honest scoreboard)

From Forge's DB + Crucible's export, 2026-05-29:

- **Submissions:** 37,373 total; 29,749 reached `gated`; 7,424 in flight; ~38 batches/day.
- **Real decisions vs sentinels:** ~**91% of "gated" rows are timeout sentinels** (aged out of Crucible's rolling export before a real decision). Only **~2,608** carry a real Crucible verdict. *This is why every empirical signal is data-starved.*
- **Promotions: 0.** Across all 29,749. (Crucible's export shows only `reject`/`component`, never `promote`.) A 39-batch zero-promotion streak the system is warning about.
- **Zero-trade rate:** ~**60%** of real-decision runs trade zero times (v3+v4 window); the v4-only cohort is ~30% but on small n. **Median trade_count = 0.**
- **Binding gate:** `min_oos_trade_count` fails ~99.9% of decisions; the Sharpe/PBO/regime gates are barely exercised because so few configs trade enough to reach them.
- **Throughput:** prefetch-bound (~1800–2540 s/iteration; ~83% of wall-clock). Not enumeration- or gate-bound.

**Reading of the scoreboard:** 0 promotions is *expected* per §1.2 and is not itself alarming. What's actionable is that the failure is concentrated at the *first* gate (does it trade), which is upstream of edge — so the levers are (a) generate configs that fire, and (b) get more real decisions (the sentinel problem) so the empirical filters/weights have data. Both are now being worked.

---

## 9. Gaps & recommendations (prioritized)

**P1 — Confirm D094 moves the needle, then extend it.** The enumerator now steers on trade-production (verified non-flat). Over the next ~1–2 weeks of v4 data, watch whether the zero-trade rate falls and whether trade-producing hypotheses gain submission share. If the gated-cohort signal proves too sparse, extend the reward to consume `prefilter_killed` / `runner_failed` outcomes (improvement-plan, deliberately deferred here to avoid punishing structurally-scarce hypotheses).

**P2 — Widen the universe (in flight).** 24 underlyings is canonical Tier 1+2 but caps trade diversity; ~152 names have bar data. Handoff drafted (`PROMPT_CRUCIBLE_UNIVERSE_EXPANSION.md`). *Caution:* prefetch is already the throughput bottleneck and scales with universe size — stage the widening and watch `phase_timings`.

**P3 — Attack the sentinel problem (real-gated coverage).** ~91% of "gated" rows never got a real decision. The empirical filters and the D094 weights are only as good as the real-decision cohort (~2,608). Coordinate with Crucible on throughput / export-window retention so more submissions get real verdicts before aging out. This compounds the value of every learning mechanism.

**P4 — Relieve structural scarcity in constrained hypotheses.** relative_value (1 indicator) and mean_reversion (2 skeletons) cannot help producing near-duplicates. The real fix is more registry indicators (Crucible-owned: pairs-family breadth, the deferred Crucible pair-universe expansion) and/or operator-approved grammar widening of C2/R-rule pins. Until then, D094 correctly down-weights these (with the floor preserving exploration), which is the right interim behavior.

**P5 — Harden the pairs template contract (Q24).** The pairs entry-keys (`pvalue_max`, `zscore_entry`, …) are duplicated as bare strings on both sides with no shared contract. A Crucible rename would silently regress pairs to ~99% zero-trade. Promote the schema into `crucible_contracts` + add a Crucible routing invariant test.

**P6 — Reconsider the ranker holistically (lower priority).** D095 fixed the permutation compression. Two residual items: `novelty`'s 0.25 weight is dead-by-correctness among survivors (a §6.2 re-weight could reclaim it — a spec deviation, currently declined), and `prior_promotion` self-heals once anything promotes. Ranking is secondary to generation while ~60% of survivors don't trade, so this can wait.

**P7 — Fix the spec drift in DESIGN.md.** Several stale spots mislead readers (see §11). A doc-only PR would help future reasoning.

---

## 10. So — is generation strong and correct?

**Correct: yes.** Valid-by-construction enumeration, deterministic + reproducible, defers to Crucible, no LLM in the loop, 1201 tests green, all hard rules structurally enforced. The machine does exactly what the spec says, and does it reliably.

**Strong: trending toward yes, not there yet, and now for understood reasons.** The honest blocker is zero-trade, not bad-edge — most submissions don't fire, so Crucible's quality gates never get a real look. The two structural causes (no edge-gradient in the loop; tiny constrained-hypothesis spaces) are both being addressed: the first was just fixed and verified live (D094); the second is in flight (universe widening) and partly Crucible-owned (registry breadth). The right metric to watch is not "promotions tomorrow" but **"does the zero-trade rate fall and the real-decision cohort grow over the next few weeks of v4"** — if those move, the §1.2 success criterion (rising promotability over time) is being met, and the generation approach is validated. If they don't, the next lever is multi-class feedback extension + registry breadth, not more tightening.

---

## 11. Known DESIGN.md drift (read alongside the spec)

| DESIGN.md says | Reality | Ref |
|---|---|---|
| §3.6 "25 rules" | 21 rules enumerated | D001 |
| §4.2 enumerator uses networkx + python-constraint | hand-rolled stratified rejection sampler | §4.2 |
| §3.5 C1 lists 11 families | 12 (trend_strength added) | D019 |
| §3.5 E1 lists 3 mandatory exits | 4 (liquidity_exit added) | D007/D014 |
| §3.5 C2 family sets | mean_reversion/volatility_event also accept dealer_positioning | D062 |
| §3.5 S5 single-required-exit | 4-part composition | D071 (amendment note present) |

---

## 12. Quick file map

- Grammar: `config/grammar.yaml` (+ `config/grammar_archive/v{1..4}.yaml`), `docs/GRAMMAR.md`, `src/forge/grammar/{custom_predicates,predicates,validator,loader}.py`
- Enumeration: `src/forge/enumeration/{search_space,sampler,defaults,iterator,registry_fingerprint}.py`
- Pre-filters: `src/forge/prefilters/{battery,expected_trades,permutation_test,novelty,signal_density,...}.py` + `config/prefilter.yaml`
- Ranking: `src/forge/ranking/{scorer,diversifier,queue}.py` + `config/ranker.yaml`
- Feedback: `src/forge/feedback/{rejection_weights,trade_rate_priors,consumer,analyzer,proposer,auto_tune}.py`
- Submission: `src/forge/submission/{submitter,rate_limiter}.py`
- State: `~/forge_data/forge.db`; Crucible export (read-only): `~/optbt_data/exports/`
- Process docs: `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`, `OPEN_QUESTIONS.md`, `OPEN_PROPOSALS.md`, `FORGE_GENERATOR_IMPROVEMENT_PLAN.md`
