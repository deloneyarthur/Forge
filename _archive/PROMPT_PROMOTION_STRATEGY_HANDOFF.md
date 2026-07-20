# Forge Promotion-Strategy Handoff — Full Pipeline, Grammar, and Explored-Territory Brief

**Date:** 2026-07-06 · **Deployed grammar:** v22 · **Contracts:** crucible_contracts 1.24.0 · **Promotions to date: ZERO**

## 0. Your mission (read this first)

You are being handed the complete state of **Forge**, the candidate-strategy generator in the
Forge → Crucible → QuantIQ pipeline. Nothing has ever promoted through Crucible's gate. Your job:
propose **grammar changes, hypotheses, and generation strategy** that move us toward a first
promotion — WITHOUT re-treading the (large) explored territory catalogued in §6, and WITHOUT
violating the hard constraints in §7.

The current binding constraint (§3.4) is the **joint strong-AND-decorrelated frontier**: we can
now assemble books that clear the overfitting gate (PBO 0.178 « 0.40) OR books with high raw
magnitude, but not both — anti-overfit hygiene drops honest selected CPCV-p25 to ~1.0 against a
1.5 bar. The decorrelation half is essentially solved (single-name `volatility_event` is a
verified orthogonal second factor). **The open problem is edge MAGNITUDE on an honest basis.**

Every proposal you make should state: (a) the mechanism, (b) WHICH gate it moves and why,
(c) prior evidence, (d) build cost and what it's gated on, (e) a pre-registerable prediction.
Rank proposals by expected movement on the joint frontier per unit of effort/risk.

---

## 1. System overview

- **Forge** (this system): a *producer*. Enumerates grammar-valid options-strategy configs,
  cheaply pre-filters, ranks, and submits survivors to Crucible. Most submissions are rejected —
  that is correct behavior. Forge computes NO validation metrics; it succeeds when its stream
  becomes more likely to promote over time.
- **Crucible**: the *validator and sole authority on quality*. Runs backtests and the full gate
  stack (§3). Its promotion gate CANNOT be lowered — ever. Decorrelation/portfolio assembly is
  owned here (it has realized PnL correlations; Forge does not).
- **QuantIQ**: consumes promoted strategies. Its live equity arm (PraiseTheSun, paper-live via
  IBKR, combined-book Sharpe ~4.66) already works; Forge's long-options book is the intended
  options arm. **Operator ruling: the options arm is the PRIMARY vehicle and is judged
  STANDALONE — the "diversifying overlay valuable at Sharpe ~1.0" framing was explicitly
  declined. The 1.5 CPCV-p25 / 2.0 WF-median promotion bars stand.**
- Everything inter-system flows through **file exports** under `~/optbt_data/` via the
  `crucible_contracts` package (typed Pydantic models). No direct DB access across systems.

Stack: Python 3.12, Pydantic v2, Polars/DuckDB, deterministic (no LLMs in the loop — but
deterministic classical ML IS allowed and already used; see §7).

## 2. The generation pipeline, end to end

Per-batch order (batch size 200, one batch per iteration, ~10-min poll cadence):

1. **Load grammar** (`config/grammar.yaml`, version-checked + archived).
2. **Snapshot registry** — Crucible publishes a `RegistrySnapshot` (indicator ids, families,
   param ranges, rank-coherence flags) every ~6h; Forge fingerprints it.
3. **Enumerate** — a seeded CSP-style constraint solver (not brute force): pick hypothesis →
   compatible directional signal → DTE bucket → regime gate(s) → sample params → compose exits →
   compose sizer → yield config. **Deterministic: same (grammar_version, registry_hash, seed) →
   byte-identical sequence** (property-tested invariant). Learned feedback (§2.1) steers the
   *sampling distribution*, and any versionless change must be cold-start byte-identical.
4. **Pre-filter battery** — cost-ascending, short-circuit; rejects ~90%. Filters: structural
   redundancy (hash vs already-tested) → resource feasibility (lookback vs history) → signal
   density (≥30 activations/4y) → expected trades (≥50/4y) → novelty (Jaccard overlap of firing
   dates ≤0.80 vs prior configs) → regime exposure (≤0.80 in one regime) → permutation test
   (100 shuffles, p ≤ 0.10; since 2026-07-04 uses `cumulative_trading` forward-return mode) →
   signal-correlation (since 07-04 excludes the regime gate from the overlap — this alone cut
   volatility_event false-kills from ~58% to ~6%).
5. **Rank** — composite score:
   `0.30·signal_density + 0.25·novelty + 0.20·regime_diversity + 0.15·permutation + 0.50·prior`
   (prior weight raised 0.10→0.50 on 2026-06-30, D220, prereg CONFIRMED — weights renormalize).
   The **prior slot is a learned model**: `P(component)` from a pure-Python IRLS logistic
   (features from gated-run history), multiplied by a monotone transform of a ridge predicting
   `wf_sharpe_p25` (the "quality lane"). Then greedy diversification (Jaccard penalty), a
   per-hypothesis floor, a per-arm exploration floor, and an **orthogonal-family floor**
   (`volatility_event = 0.20` of each batch — live since 07-02).
6. **Submit** — atomic JSON per config to Crucible's inbox; `config_hash` (16-char SHA-256 of
   the config tree) is the cross-system identity and is unique-indexed (no double-submission).
7. **Backpressure** (§7.3): submission halts if ANY of: previous batch <80% gated · Crucible
   idle ≥3h · in-flight depth >600. Failed Crucible runs are reconciled via a `failed_runs`
   export so phantom in-flight rows can't pin the cap (two past incidents).
8. **Feedback** — Forge reads `gated_runs` exports: per run, a `metrics` dict + a
   `PromotionDecision` (`promote | component | reject`) + per-gate `GateResult`
   (name/passed/value/threshold) + coarse `failure_buckets`. Learned components consuming this:
   sampler rejection-weights (component-rate reward per (hypothesis × signal × bucket) arm),
   trade-rate priors, cohort-yield + regime-gate-yield reweighting (48 + 118 cells live),
   the P(component) model and quality-lane ridge (retrained daily by a 05:00 timer with a
   PASS-streak + drift/adoption gate), and a prefilter auto-tuner (tighten-only).

### 2.1 What a config looks like (the search space)

`StrategyConfig`: one `hypothesis` · one `dte_bucket` (swing_short 14–21 DTE / swing_mid 30–45 /
swing_long 60–90) · `underlying` (a ticker, or None = cross-sectional rank leg) · 1–4 `signals`
(exactly 1 `directional`, ≥1 `regime_filter`, optional confluence/filter; thresholds may be
percentile-parameterized against the indicator's own trailing distribution) · a `combiner`
(confluence / passthrough / cross_sectional_rank with rank_k + rebalance) · a `selector`
(delta target/tolerance per bucket, DTE window, liquidity floors) · a `sizer`
(fixed_risk_pct ≤0.02 per trade / vol_target / fractional_kelly) · `exits` (4 mandatory:
expiry, theta_cliff, earnings, liquidity + hypothesis-matched set, §4.3).

**Structures: single-leg LONG options only.** There is no multi-leg (`LegSpec`) in the grammar
or contracts today. Long calls/puts, defined direction from the signal. This is the
representational ceiling discussed in §5/§6 — a single long leg pays the full variance risk
premium (VRP), and the grammar-review conclusion is that only structure (debit spreads) can
raise the magnitude cap.

## 3. Crucible's gate stack — what a config must survive

Vocabulary: **component** = passed Crucible's component screen; accepted as a portfolio building
block (component rate is Forge's live currency, currently ~0.123). **promote** = passed the FULL
§8.7 gauntlet → exported to QuantIQ. No single config has ever cleared the promote-level bars
solo; promotion is expected to happen at the **book/portfolio level** (assembly is Crucible's).

### 3.1 Per-config gates (exact export field names in parentheses)

| Gate | What it measures | Promote-level bar |
|---|---|---|
| Hard gates | trade-count floor (`min_oos_trade_count`), real slippage >0, `regime_coverage` | binary |
| **WF** (`walk_forward_sharpe_median`, plus calmar/maxDD variants) | walk-forward OOS Sharpe, median across folds | **≥ 2.0** (1/365 honest configs clear solo) |
| **CPCV** (`cpcv_sharpe_p25`, `cpcv_max_drawdown_p75`) | combinatorially-purged CV Sharpe, 25th-percentile path — the downside/robustness floor | **≥ 1.5** (0/365 clear solo; THE magnitude bar) |
| **DSR** (`deflated_sharpe`) | Sharpe deflated by selection-campaign size + PBO (multiplicity control; charged via `search_n_trials`) | Harvey-style |
| Regime stress (`regime_stress_p25_return`) | bootstrap downside-tail filter | > 0 |
| **M / min_margin** | continuous all-gate minimum margin (distance to clearing the whole gauntlet, weakest gate binding) | ≥ 0 (live values mostly −4.2…−0.2) |

Informational-only fields (never gates): `wf_sharpe_p25`, `wf_sharpe_p10`, `selection_n_trials`.
`wf_sharpe_p25` is what Forge's quality lane regresses on.

### 3.2 Book-level gate

**PBO via CSCV** (`pbo`): probability of backtest overfitting, combinatorially-symmetric
cross-validation, computed on the assembled book. **Gate < 0.40; 0.50 = noise floor.** A book
property, not per-component. Also book-level: `mean_pairwise_correlation` (decorrelation gate).

Failure-bucket severity order (as published): `cpcv_p25_below_bar` → `walk_forward_below_bar`
→ `dsr_below_bar` → `pbo_too_high` → `regime_stress_fail` → `book_too_correlated` →
`insufficient_sample` → `robustness_fail` → `structural_incomplete`.

### 3.3 Honesty split — always condition on it

Only ~24% of decided-with-CPCV rows have verified `honest_regime_coverage`. Pooling verified and
unverified rows INVERTS conclusions (it flipped mr-vs-trend rankings once). Any analysis of
CPCV/WF numbers must split on this flag. All magnitude numbers in this doc are honest-slice.

### 3.4 The binding constraint — three framings, current one last

1. **Magnitude wall** (pre 06-25): 0/9,398 configs cleared CPCV-p25 1.5 solo; max GROSS
   cpcv-p25 in the long-options space measured at **1.40** — IC-bound, not cost-bound (D152).
2. **PBO wall** (D212, 06-25): assembly clears magnitude (books at WF 2.88 / cpcv-p25 1.79–1.95)
   but PBO 0.578 > 0.40, root-caused to effective dimensionality ~1.5 (trend + mr components
   ~0.78 correlated — an "mr/trend monoculture").
3. **CURRENT — joint frontier** (D216/07-01): anti-overfit hygiene (shrinkage, cluster-dedup)
   drives the best honest book's PBO to **0.067 (not binding)** — but that book is then rejected
   on MAGNITUDE: selected cpcv-p25 ≈ **1.0** vs the 1.5 bar. The high-magnitude D212 books were
   the overfit ones. **Supply cannot yet deliver strong AND decorrelated simultaneously.**

The one lever both systems agree on: **more strong, decorrelated supply.** Single-name
`volatility_event` supplies the decorrelated half (§5.2); the magnitude half is open — that is
your problem.

## 4. The grammar as deployed (v22)

Version history: v1 → v22 live (v23 built, not deployed — §6.4). The 21 rule *texts* are
operator-owned and unchanged since v2; all evolution v3→v22 is Python-side tables/enumeration
policy. 13 indicator families from the contracts registry: trend, trend_strength,
mean_reversion, volatility, iv_structure, dealer_positioning, flow, macro, calendar,
fundamental, smart_money, pairs, post_event_drift. (**No equity family — hard-forbidden.**)

### 4.1 The 21 rules (condensed)

- **S1** exactly one hypothesis · **S2** exactly one directional signal · **S3** ≥1 regime gate ·
  **S4** DTE bucket must match the directional signal's lookback class (Forge-owned horizon
  table; short ≤6d → swing_short; 7–89d → short/mid; ≥90d → mid/long) · **S5** exits match
  hypothesis (table §4.3).
- **C1** no two indicators from the same family · **C2** directional family must match
  hypothesis (map §4.2) · **C3** ≤4 signals · **C4** regime gate ≠ directional indicator.
- **P1** params within registry ranges · **P2** DTE windows fixed per bucket · **P3** delta
  bands (short 0.40–0.55, mid 0.30–0.45, long 0.20–0.35; trend×mid/long widened up to 0.55) ·
  **P4** per-trade risk ∈ [0.005, 0.02].
- **E1** 4 mandatory exits always present · **E2** ≤2 stop-loss exits · **E3** trailing stop
  needs activation threshold ≥ 0.30 gain.
- **R1** mean_reversion needs a gate from {iv_rank ≤50, gamma_flip_distance_pct <, hurst <,
  rv_rank <} · **R2** trend_continuation needs one of {adx, hurst >, rv_rank <,
  gamma_flip_distance_pct >, market_state >} · **R3** volatility_event needs an event-proximity
  gate from {days_to_earnings, days_to_fomc, days_to_cpi, days_to_nfp, days_to_opex,
  pre_earnings_setup} (ETFs can't pair with earnings gates).
- **X1** vol_target sizing needs realized_vol · **X2** fractional_kelly needs
  expected_value_estimator.

### 4.2 Hypotheses — live vs dead

| Hypothesis | Directional families (C2) | Status |
|---|---|---|
| `mean_reversion` | mean_reversion | LIVE — **81.4% of supply (monoculture; the over-produced redundant half)** |
| `trend_continuation` | trend, smart_money (option_momentum) | LIVE — 11.3% |
| `volatility_event` | iv_structure, flow, dealer_positioning | LIVE — 6.9%, 100% single-name; **the orthogonal factor; floor now forces 20%/batch** |
| `event_momentum` | post_event_drift (sue) | LIVE — 0.4% (thin) |
| `relative_value` | pairs | LIVE but ~0.0% flow; xsect form REFUTED (§6.2) |
| `regime_arbitrage` | any | DISABLED from enumeration (81% zero-trade, D098) |
| `tail_hedge` | macro | DISABLED (overlay-only) |

Cross-sectional-rank branch restrictions: dealer family single-name-only; chain-reading
indicators (iv_rank, put_call_flow) excluded from rank; per-name-decoupled ids excluded;
mean_reversion can rank only via hurst/rv_rank gates; event_momentum never ranks. Exclusions
keyed on registry flags (`rank_per_name_coherent`, `market_wide_by_design`), fail-closed.

### 4.3 Exit composition (S5) per hypothesis

trend: pick one of {trailing_atr, chandelier_exit, parabolic_sar_exit}, optional time_stop,
hard_profit_target forbidden · mean_reversion: pick one of {time_stop, target_exit,
zscore_reversion_exit}, optional iv_crush_exit · volatility_event: iv_crush_exit +
event_passed_exit required (exit-lag ladder {3,5,8,13,21} bars, sampled since v22) ·
relative_value: convergence/zscore exit · event_momentum: time_stop + optional trailing.

### 4.4 Notable signal activations (with dates)

iv_minus_rv (v17, ve directional, Goyal-Saretto) · iv_term_slope (v18, ve directional) ·
pre_earnings_setup (v18, R3 gate) · option_momentum (v19, trend directional, percentile-only) ·
hurst → R1 (v20) · MR ranks via hurst (v21) · rv_rank → R1 + event_passed_exit ladder (v22).

**Gotcha for proposals: registered ≠ enumerable.** A Crucible-registered indicator only becomes
enumerable after Forge adds it to `indicator_thresholds.py` (threshold/percentile spec) and the
signal-horizon table. Grammar bumps require: version bump on ANY byte change, archive, decision
ledger entry, operator sign-off.

## 5. Live state (2026-07-06)

- Daemon healthy, submitting; contracts 1.24.0 both sides (a 13h asymmetric-upgrade inbox
  stall was fixed today — clean measurement cohort restarts at 2026-07-06T15:54:09Z).
- **Component rate 0.1229** (6,732 components / 54,756 decided since the prior-weight cut;
  rising daily 0.117→0.128; baseline anchor was ~0.048). Component ≠ promote: component
  full-sample Sharpe ≈ 0.85.
- **Zero promotions ever.** The `component_contributions` export (would tell us realized
  marginal Sharpe + correlation-to-incumbent per component) is EMPTY until a first promotion —
  which data-blocks the "re-aim learned weights at marginal contribution" plan (held).
- Flags: orthogonal-family floor (ve=0.20) ON, prereg open · quality lane ON (KEEP verdict —
  helps ve +0.080 and trend +0.143 rank-skill, hurts mr −0.062) · gate-tail rank mode OFF but
  its flip gate is MET (SPRT logLR +41.66; teed up, operator-gated) · exploration holdout
  (≤10% random ranking-bypass for unbiased labels) built, OFF · both prefilter flips
  (cumulative_trading, exclude_regime_filter) DEPLOYED 07-04, preregs re-resolving on the
  post-incident clean cohort.

### 5.2 The closest thing to a promotable book (the current thesis)

Single-name `volatility_event` (n=611 honest components) **loads 0.10 on the trend/MR PC1**
(< 0.2 new-factor bar; 100% positive marginal Sharpe) — a genuine orthogonal second factor.
Mechanism: PC1 is market-wide dispersion; the single-name pre-event vol timer rides
idiosyncratic name vol. An 8-book mixed family sweep (0→67% ve) clears book PBO at
**0.178** (10-group/45-path CSCV; the earlier 0.107 was an 8-group preliminary — anchor on
0.178) vs pure trend/MR 0.556; the ve-heavy book won 36/45 paths. Degradation slope −0.598 →
magnitude haircuts OOS. **But**: this was a PBO-only read; the magnitude half (selected
cpcv-p25 ≈ 1.0 vs 1.5) remains short. Producer job in flight: ve supply quantity + durability
(floor + the two prefilter flips ≈ 2–3× ve survival). External research independently
confirmed: the event-vol edge is per-name, pre-print, long-vol selection harvested by breadth —
NOT a cross-sectional rank ("xsect is the wrong axis for the edge, the right axis for the
portfolio").

## 6. EXPLORED TERRITORY — do not re-tread

### 6.1 REFUTED (data killed it; don't re-propose without new evidence)

| Lever | Killing evidence |
|---|---|
| Strike/price-target forecaster (deep-researched 06-28) | predictability ceiling (OOS R² ≈0.3–0.4%); VRP headwind; adds dimensionality → raises PBO; re-ranks within-family = 0 gate movement |
| Cross-sectional volatility_event | xsect iv_minus_rv rank-IC −0.015 (t −0.86); 0/757 winners xsect; structurally double-locked |
| Cross-sectional relative_value supply | caps cpcv-p25 0.867; 0.88 MR-collinear |
| Sector-neutral/GICS relval decorrelation | corr-to-MR still 0.797 (ceiling 0.30); orthogonal residual IC ≈ 0 — same mechanism, different grouping |
| Trend cheap-IV entry gates (iv_rank/iv_minus_rv on trend) | cheap−rich −0.032: trend edge lives in RICH IV; every quintile ~equal → IC-bound |
| iv_rank × days_to_opex "near-miss" | WF 1.43 but cpcv-p25 0.70 — craters on CPCV |
| ve \|move\| permutation null (thought looser) | actually −62% stricter; Crucible read inverted the thesis: higher-\|move\| ve is MORE correlated (higher PC1) |
| regime_stress as a steering/selection target | hi-stress book WF 1.74 < 2.05 lo; it's a tail FILTER (assembly-owned), not a mover |
| Generation-side decorrelation proxies (structural Jaccard → PnL corr) | Spearman only −0.20; broad×broad decorrelation is already abundant (~0.10) — decorrelation is OWNED AT ASSEMBLY |
| parabolic_sar as trend exit | chandelier beats it +0.29 cpcv-p25 (pruned in v23) |
| Short-vol / credit structures (credit verticals, condors, flies, short strangles, ratios, risk reversals) | wrong risk factor — sells the vol Forge exists to be long; gives away bear convexity |
| Seller-side surface signals as directional edges (put-skew/RR, VRP timing, VVIX, dispersion); OPEX vanna/charm, max-pain, UOA folklore; accruals/pre-FOMC drift | evidence-negative or decayed (grammar review Dim-B "do not add") |

### 6.2 RETIRED / SHELVED / RETRACTED

- **Prefilter auto-tightening**: RETIRED (D206) — thresholds are a flat axis on the cpcv-p25
  tail; zero-trade waste already solved (89% of gated runs trade ≥10).
- **Meta-king arm** (parallel oracle-quality generator): RETIRED (D190) — subsumed by the
  standard quality lane; M-strength didn't transfer to realized hard-gate clearance.
- **AND-gate stacking** (≥2 regime gates): SHELVED — fewer trades fights the trade-count floor
  and CPCV penalty.
- **"iv_rank is a stub, vega axis unexplored" reopen**: RETRACTED same-day — stale-doc error;
  iv_rank live since 2026-05-15. The long-options **exhaustion verdict stands**: max gross
  cpcv-p25 in-paradigm = 1.40 < 1.5, cost-ratio ~1.0 → IC-bound. (Operator directive: exhaust
  in-scope long options before any v2 structure work; that gate is now SATISFIED but Path C is
  still deliberately HELD.)

### 6.3 LIVE but low-ceiling (steering, not wall-breaking)

Quality lane (wf_p25 ridge; blend measured ~no-op vs P(component) alone — Spearman 0.97
identical; per-family KEEP) · rv_rank mr gate (+0.095 cheap−rich per-trade gradient but lifts
the CENTER, not the cpcv-p25 tail — "quality knob, not a promotion unlock") · cohort-yield +
regime-gate-yield reweighting · learned sampler weights (component-rate reward) · P(component)
prior at 0.50 weight (CONFIRMED: component-rate 2.6× baseline). Consensus from the learned-
systems review: **none of the learned/selection machinery can break the magnitude ceiling —
only the grammar can.** 0 of ~7,566 honest single-config CPCV values reach 1.5, flat across 15
grammar iterations = representation wall.

### 6.4 BUILT, not deployed / teed up

- **v23 grammar** (branch, 2 commits): +sma_slope (best trend signal, rank-IC 0.078,
  dominates momentum_252; fair-backtest CPCV-p25 +18%) and +ad_slope percentile directionals;
  prunes redundant/anti-momentum trend directionals (returns_12m_skip1, macd, ema_cross,
  supertrend); chandelier default trend exit w/ atr_mult [2.0,3.0] (+0.155 cpcv-p25);
  days_to_fomc window 60→14d. Honest scope: selection-quality lift, does NOT move the
  single-name wall. Deploy queued behind flip-prereg resolution; operator-gated.
- **Gate-tail rank mode** (P gates eligibility, tail orders): flip criterion MET, waiting.
- **Exploration holdout** (unbiased-label lane): flag-OFF.
- 3 deferred builds from the Crucible design loop: failure-bucket-based reward migration,
  (family × data-era) freeze ledger, mechanism/regime vocab artifact.

### 6.5 Already-drafted roadmaps you should BUILD ON (not duplicate)

**Grammar review (Dimensions A/B/C)** — thesis: Forge's grammar core is best-practice; expand
only toward **net-long-vol, defined-risk** structures + decorrelating/regime-gating signals:

- **A / Path C (the ceiling-breaker, operator-HELD):** Tier 1 = debit vertical spreads
  (bull-call/bear-put) — same signals, defined-risk, cheaper, less VRP bleed; the
  representational unlock. Tier 2 = calendars (new forward-vol axis; pays in RANGING, the worst
  quartile 1.33×) — gated on term-structure signals. Requires contracts `LegSpec`, new rules
  S6/C5/P5–6/E4/R4, and a machine-checked **net-debit AND net-long-vega AND defined-risk**
  invariant. Straddles/backspreads: research-only (pay full VRP).
- **B (selectivity within the cap, ~50% McLean-Pontiff OOS haircut assumed):** ranked adds —
  (1) credit-spread/EBP regime gate (HY–IG OAS; best edge-per-complexity), (2) yield-curve
  slope gate, (3) options-native earnings-vol gate (implied-move vs realized + call/put IV
  spread; orthogonal to sue), (4) PCP-violation short-constraint proxy, (5) momentum-crash
  regime gate (Daniel-Moskowitz), (6) vix_term_slope ingest (already filed).
- **C (methodology PREREQUISITE):** cumulative effective-N **alpha budget** — ~1,000
  independent noise trials yield best-Sharpe ~1.5–2.0 with zero edge; Forge's 1.40 wall is
  uncomfortably near the null of a large search. Count ONC-clustered effective trials, deflate
  cumulatively; note `search_n_trials` is never set by the standard submitter (selection
  intensity currently unreported to DSR). Plus: rank-coherence as a grammar TYPE; sign/
  monotonicity shape constraints; expand only where the yield map shows BARREN vs
  under-sampled.
- **Learned-systems review (B1–B13):** calibration gating (Platt/ECE), principled two-part
  hurdle model, SPRT instead of streak counting (done), drift monitors (done), censored-loop
  fix via exploration holdout (built), uncertainty-aware cell allocation (Thompson/UCB),
  structural diversity as a search objective (attack the monoculture at source), MAP-Elites
  per-cell elite archive (gated on the alpha-budget item), ceiling-vs-coverage telemetry.
- **Higher-EV pivot flagged by the strike-forecasting research:** earnings event-PHASE split
  within volatility_event (pre-announce ramp vs post-announce drift as distinct sub-arms).

## 7. Hard constraints on any proposal

1. Crucible's promotion gate can NEVER be lowered; grammar can change, the gate cannot.
2. The 21 §3.5 rule texts are operator-owned; edits are operator-gated. Auto-TIGHTENING may
   ship; any LOOSENING requires operator approval (structurally enforced).
3. **No `equity` signal family, ever** (§13.6). Options-only. No short-vol/net-credit
   structures (refuted, and the planned v2 invariant will forbid them).
4. **No LLMs in the production loop** — but deterministic classical ML is explicitly fine
   (the ranker already is one). Binding constraints are determinism (same inputs →
   byte-identical enumeration) and seeded RNG, not "no learning."
5. Grammar changes: version bump on ANY byte change + archive + decision-ledger entry.
   Versionless (feedback-class) changes must be cold-start byte-identical.
6. Submission idempotency (config_hash unique); all inter-system access via
   `crucible_contracts` typed models — a missing model/field is a contracts gap to surface.
7. Operator directives in force: options arm judged STANDALONE (1.5/2.0 bars stand) · Path C
   deliberately HELD (re-pricing it is fair game; silently assuming it is not) · MR grammar
   expansion asks HELD · deploys/flips/bumps operator-gated, one lever at a time, each with a
   pre-registered prediction resolved on a later time-cut cohort.
8. Analysis hygiene: split all gate metrics on honest_regime_coverage; anchor book-PBO on
   0.178; component-rate ≠ promotion progress; expect ~50% OOS haircut on literature effects.

## 8. What we want from you

Given all of the above, produce a **ranked proposal set** for grammar + hypothesis + generation
strategy aimed at a first promotion. The frontier to move is **honest book magnitude at
already-cleared PBO** (cpcv-p25 ~1.0 → 1.5 selected, PBO ≤ 0.4 maintained). Directions we
already consider live (build on, critique, or re-rank them — with reasoning):

- Sequencing the teed-up levers (v23 deploy, gate-tail flip, exploration holdout) — is the
  current order right?
- The vol_event magnitude question: supply is being fixed (floor + flips); is there an
  UN-refuted selection/conditioning lever INSIDE single-name event-vol (e.g. the event-phase
  split, event-type interactions with the exit-lag ladder, term-structure conditioning via
  iv_term_slope) that lifts per-component honest magnitude?
- Path B signal adds: which of the six, in what order, and as gates vs directionals?
- Path C re-pricing: make the strongest honest case for/against unlocking Tier-1 debit
  verticals NOW vs after another supply cycle — including what evidence would justify asking
  the operator, and the alpha-budget prerequisite.
- Anything genuinely new that survives §6 and §7.

For EACH proposal: mechanism → which gate/frontier-half it moves → prior evidence (cite ours
above or literature with the haircut) → cost/complexity + what it's gated on → a concrete
pre-registerable prediction (metric, cohort, threshold, horizon) → failure modes/kill criteria.
Flag anything that increases effective search N and how you'd charge it to the alpha budget.
