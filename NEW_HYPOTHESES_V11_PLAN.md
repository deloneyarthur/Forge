# New-hypotheses program — consolidated plan (one `v11` grammar bump for four changes)

**Status:** Design / proposal. NOT a green-light to edit `grammar.yaml`, contracts, or ship code.
**Date:** 2026-06-07.
**Author:** Forge session (operator-requested: "explore new hypotheses to improve strategy generation; do all four; update the grammar a single time").
**Umbrella Decision Log entry:** D107 (confirm next free number in `IMPLEMENTATION_DECISIONS.md` before applying).
**Grammar:** v10 (live, deployed 2026-06-07 23:38:39 UTC) → **v11** (this program).

---

## 0. TL;DR — the shape that honors "one grammar update"

A literal single bump for all four is impossible *today* because two of them (H1, H2)
cannot be **traded** until Crucible's runner + registry land — hard rule #2 (Forge invents
neither combiners nor indicators) and `validate_config_against_registry` rejects them at
submission. But we can still make **one `v11` grammar edit** carry all the scaffolding,
using the established `NON_ENUMERABLE_HYPOTHESES` pattern (D066/D098) and the versionless
enumeration-rollout precedent (v5–v10):

- **`v11` grammar bump** adds *all* structure: the cross-sectional combiner (H1), an
  `event_momentum` hypothesis + post-event family (H2), and gamma/vol regime gates (H3).
- **H3 enumerates live immediately** (its indicators already exist — see §1).
- **H1 + H2 ship grammar-present but enumeration-disabled** via `NON_ENUMERABLE_HYPOTHESES`
  / a disabled-combiner set; they **flip on versionlessly** (no new grammar version, like
  v5→v10) the day Crucible's runner + registry land. No D104-style mixed-window risk.
- **H4 is not a grammar change at all** — versionless §6.3 diversifier/feedback (ships like
  D101/D103/D105 components), alongside `v11`.
- The only prerequisite for the bump itself is an **additive contracts change** (§5):
  reserve the new `hypothesis` / `CombinerSpec.type` / `family` literals so the disabled
  scaffolding still *constructs* and *validates*. No runner needed for the additive bump.

**Attribution stays clean without serializing into 3 versions:** every new structure is
self-identifying in `config_json` (combiner `type`, `hypothesis`, regime indicator id), so
the by-feature decision-rate join (forge.db `submissions` ⋈ Crucible gated export) attributes
each arm — this is exactly the join used to derive §1's numbers. `crucible funnel --compare
v10 v11` attributes H3 (the only live grammar-gated arm); H1/H2 attribute on their flip-on
date via the same join.

---

## 1. Empirical basis (self-contained; re-derive before acting)

Source: forge.db `submissions` (92,389) ⋈ Crucible gated export
`gated_runs_2026-06-08T052422Z.json` (10,000 most-recent decided), joined on `config_hash`.

- **0 promotions, ever** — across all 92,389 submissions / 10 grammar versions
  (`batch_summaries.promotion_rate` max = 0.0; `promoted_strategies` export empty). The
  WF-Sharpe ≥ 2.0 promote gate is strategy-space-limited and "not expected to move" (Crucible
  yield-map handoff, 2026-06-07). **The currency is components** (`decision == "component"`),
  running at **1.83%** (183 / 10,000).
- **The binding constraint is breadth (trade count), not signal quality:**

  | metric (median) | components (n=183) | rejects (n=9,817) |
  |---|---|---|
  | n_trades | **146** | **1** |
  | sharpe | 0.88 | 0.00 |
  | win_rate | 0.47 | 0.00 |
  | profit_factor | 1.57 | 0.00 |

  98% die at `min_oos_trade_count ≥ 100`. This is Grinold's law as a gate: IR = IC·√Breadth.
- **Component rate by hypothesis** — vol_event dominates 5–8×:

  | hypothesis | decided | component% |
  |---|---|---|
  | volatility_event | 2,422 | **5.04%** |
  | relative_value | 2,138 | 0.98% |
  | mean_reversion | 2,455 | 0.86% |
  | trend_continuation | 2,893 | 0.62% |

  vol_event wins because events *recur* (earnings + FOMC/NFP/CPI/OPEX → 60+ bets/5y on one
  name → clears the floor). Directional archetypes fire rarely on a single name → median 1
  trade → rejected before their IC is tested.
- **Winning vol_event recipe** (122 components): directional `put_call_flow` (70) /
  `iv_rank` (31) / `put_wall_distance_pct` (21); event gate `days_to_fomc/nfp/cpi/opex`;
  exits `iv_crush` + `event_passed`; high-idio-vol single names (AAPL ×36, AMD, NVDA, TSLA…),
  swing_short. Win rate <50% but PF 1.57 → convex/positive-skew (long optionality into catalysts).
- **Concentration risk:** the 122 vol_event components are *not* uncorrelated — same
  variance-risk-premium factor, same macro calendar, 36 on AAPL alone. Pod-shop practice
  (Millennium: 330+ *uncorrelated* sleeves, partitioned to prevent "alpha cannibalization")
  says the marginal portfolio value of the 37th AAPL long-vol clone ≈ 0. → motivates H4.
- **Registry already contains H3's signals:** `gamma_flip_distance_pct` (3,410 enumerated;
  dealer GEX gamma-flip level), `vol_regime` (685), full `dealer_positioning` family;
  contracts ships a `Regime` classifier (`trending`/`ranging`/`low_vol`/`high_vol`). H3 needs
  **no new indicators** — only a grammar loosening + enumeration policy.

External grounding: cross-sectional momentum ~3× Sharpe (Poh/Lim/Zohren/Roberts 2020;
`OPTION_B_CROSS_SECTIONAL_RANK_SCOPING.md`); PEAD durable anomaly (~72% 5-day drift after
10%+ beats, Alpha Architect/Quantpedia); GEX regime switch (SpotGamma/SqueezeMetrics);
Grinold (1989) fundamental law; pod-shop uncorrelated-sleeve model (Millennium/Citadel).

---

## 2. Feasibility matrix

| | thesis | grammar delta | contracts delta | Crucible delta | new indicators? | ownable now |
|---|---|---|---|---|---|---|
| **H1** cross-sectional rank | manufacture breadth | new combiner rule | `CombinerSpec.type += cross_sectional_rank` (+ K/rebalance params) | **rank-top-K runner** | no | ❌ upstream |
| **H2** event-momentum / PEAD | port event-breadth to directional | `event_momentum` hypothesis + family + C2/R3/S5 | `hypothesis +=`, `family +=` | **post-event entry window** | **yes** (`days_since_earnings`, SUE) | ❌ upstream |
| **H3** gamma regime switch | match tool to regime | R1/R2 loosen (allow gamma/vol_regime gate) | none | none | no (exist) | ✅ **Forge** |
| **H4** orthogonal-yield | reward decorrelated components | **none** (versionless) | none | none | no | ✅ **Forge** |

---

## 3. The single `v11` grammar bump — exact contents

One edit to `config/grammar.yaml` (+ archive `config/grammar_archive/v10.yaml`, + D107 Decision
Log entry, hard rule #10). Per hard rule #1 the 21 operator-owned rules' *intent* is preserved;
these are additive option-expansions (loosenings → §7 OPEN_PROPOSALS first, hard rule #4).

1. **H1 combiner (scaffold, disabled):** add `cross_sectional_rank` as a permitted
   `combiner.type` with a P-style rule bounding `K` and `rebalance_frequency`. Gated OFF via a
   new `DISABLED_COMBINERS` set in `search_space.py` until the runner lands.
2. **H2 hypothesis (scaffold, disabled):** add `event_momentum` to S1's hypothesis set; C2
   maps it to a new `post_event_drift` directional family; a new regime rule requires a
   post-event-proximity gate; S5 defines its exit set (drift-decay time stop + momentum
   trailing). Added to `NON_ENUMERABLE_HYPOTHESES` until `days_since_earnings`/SUE register.
3. **H3 regime gates (LIVE):** loosen **R1** (mean_reversion may use a positive-gamma /
   low-`vol_regime` gate in addition to `iv_rank ≤ 50`) and **R2** (trend_continuation may use a
   negative-gamma gate via `gamma_flip_distance_pct`, in addition to adx/hurst/rv_rank).
   Enumeration policy pairs them (positive-gamma→MR template, negative-gamma→trend template).
   S1-legal: each is a single-hypothesis strategy with the gamma gate as its **regime filter**;
   the trend↔MR "switch" emerges at the QuantIQ portfolio layer (DESIGN's stated philosophy).

H4 is **not** in this list (versionless).

---

## 4. Per-hypothesis spec

### H1 — Cross-sectional rank combiner (breadth, the master lever)
- **Thesis:** replace per-name Boolean firing with score→rank→trade-top-K→rebalance. Trade
  count becomes deterministic (K × rebalances) → the 100-trade floor stops binding. ~3× Sharpe
  (Poh et al. 2020). Already scoped in `OPTION_B_CROSS_SECTIONAL_RANK_SCOPING.md`; Crucible's
  `universe.yaml` already names `cross_sectional_rank`.
- **Forge side:** new combiner in grammar (§3.1); enumerate K ∈ {5,10,20}, rebalance ∈
  {weekly, monthly}, long-only vs long-short; sampler emits a universe-scoped config (not
  single-underlying). Disabled until runner lands.
- **Upstream (critical path):** contracts `CombinerSpec.type += "cross_sectional_rank"` + params
  (§5); **Crucible rank-top-K backtest runner** (§6, the long pole).
- **Test:** on flip-on, by-feature join — expect `cross_sectional_rank` configs' median n_trades
  ≫ 100 by construction; target trend/mean_rev component% from 0.6–0.9% toward vol_event's 5%.

### H2 — Event-momentum / PEAD (the vol-event × trend mix)
- **Thesis:** a *directional* strategy on the event calendar. Enter **after** the print
  (sidesteps the IV crush our vol_event sleeves ride → structurally orthogonal to existing
  winners), ride 5–20-day drift. Every earnings event is a bet → breadth like vol_event.
- **Forge side:** `event_momentum` hypothesis; `post_event_drift` directional family; regime
  rule requires a post-event window gate; S5 exits = drift-decay time stop + momentum trailing
  (no hard target — same convex profile as the winners). Disabled until indicators register.
- **Upstream:** contracts `hypothesis += "event_momentum"`, `family += "post_event_drift"` (§5);
  **Crucible registers** `days_since_earnings` (backward window — note registry has only the
  forward `days_to_earnings`) and an earnings-surprise/SUE indicator; **runner** post-event
  entry semantics (§6).
- **Breadth note:** PEAD on a *single* name ≈ 20 earnings bets/5y — **below 100**. So H2 only
  clears the floor when paired with H1 (cross-section) **or** multi-event stacking. Sequence H2
  after H1, or scope H2's first cut as cross-sectional from day one.

### H3 — Gamma / vol regime switch (the mean-rev × trend mix, LIVE in v11)
- **Thesis:** "match the tool to the regime." Positive dealer gamma → vol compressed,
  range-bound → mean_reversion pays; negative gamma → moves amplify → trend pays. Indicators
  **already in the registry** (`gamma_flip_distance_pct`, `vol_regime`, dealer family).
- **Forge side (fully ownable):** R1/R2 loosening (§3.3) + enumeration policy that pairs the
  positive-gamma gate with mean_reversion templates and the negative-gamma gate with trend
  templates. Two S1-legal single-hypothesis templates; switch emerges at QuantIQ.
- **Upstream:** none.
- **Test:** `crucible funnel --compare v10 v11` (H3 is the only live grammar-gated arm) +
  by-feature join — expect MR/trend configs *carrying a gamma gate* to lift component% vs
  their iv_rank/adx-gated peers; watch n_trades doesn't collapse (regime gates cut firing).

### H4 — Orthogonal component yield (versionless, ships now)
- **Thesis:** D105 re-aimed reward to raw component-rate → over-concentration into correlated
  vol_event sleeves (§1). Reward the **marginal orthogonal** component, per the pod-shop
  uncorrelated-sleeve model.
- **Forge side (fully ownable, no grammar):** extend the §6.3 diversifier penalty (and/or the
  feedback reward) to score a candidate against the **realized component population's**
  factor/correlation structure (hypothesis × underlying-class × event-type × directional-family
  cells), not just within-batch novelty. Keep the exploration floor (don't zero any cell).
- **Test:** measure realized-component **factor concentration** (Herfindahl over the cells)
  pre/post; expect concentration ↓ with component-rate roughly flat — i.e. same yield, more
  orthogonal. This is the success metric, not raw component count.

---

## 5. Contracts ask (additive, non-breaking — draft as `CONTRACTS_V*_*.md`)
Single additive bump so the disabled scaffolding constructs + validates:
- `CombinerSpec.type`: `Literal[..., "cross_sectional_rank"]` + optional `k: int`,
  `rebalance_frequency`, `direction_mode` fields (defaulted; back-compatible).
- `StrategyConfig.hypothesis`: `Literal[..., "event_momentum"]`.
- `IndicatorMetadata.family`: `Literal[..., "post_event_drift"]`.
- (Indicators themselves register on Crucible's side, §6 — not a contracts literal.)
No behavior change; existing configs validate byte-identically (additive literals only).

## 6. Crucible handoffs (the critical path — draft as `PROMPT_CRUCIBLE_*.md`)
- **H1:** rank-top-K backtest runner (score all universe names each bar, hold top-K, rebalance,
  per-leg fills/greeks). The long pole; everything breadth-related waits on it.
- **H2:** register `days_since_earnings` + earnings-surprise/SUE; runner post-event entry window.
- Flag both as cross-system per the §6-coupling lesson: Forge flips enumeration on within hours
  of these landing.

## 7. OPEN_PROPOSALS.md loosenings (hard rule #4 — cannot auto-ship)
H1/H2/H3 expand enumeration scope (loosenings) → each gets an `OPEN_PROPOSALS.md` entry and
waits for operator sign-off before the `v11` apply. (H3 is the one that goes live on approval;
H1/H2 entries also note their upstream gating.) None lowers the promotion gate (hard rule #3).

## 8. Attribution & A/B plan
- `crucible funnel --compare v10 v11` → H3 (only live grammar-gated arm).
- By-feature decision-rate join (forge.db ⋈ gated export) → per-arm component% for all four, on
  their respective live dates. Self-identifying configs make this exact.
- H4 success = realized-component factor-concentration ↓ at flat component-rate (not raw count).
- Window caveat (2026-05-29 lesson): allocation/orthogonality conclusions only until full-history
  WF + portfolio battery settle.

## 9. Sequencing & TDD (phase-disciplined; tests-first per CLAUDE.md)
1. **Now, Forge-only:** H4 (versionless feedback module, red→green) + H3 grammar loosening
   (OPEN_PROPOSALS → operator approval → `v11` apply + archive + D107 + invariant tests).
   Every hard-rule/structural mitigation gets its `tests/invariants/` check first.
2. **In parallel:** contracts additive proposal (§5) + Crucible handoffs (§6).
3. **On upstream land:** flip H1 then H2 enumeration on (versionless), each with its by-feature
   A/B readout. Sequence H2 after H1 (breadth dependency, §4).

## 10. Open decisions for the operator
1. **Approve the one-bump shape (§0)?** vs. staged (v11 = H3 now, v12 = H1/H2 later). One-bump
   needs the additive contracts change ahead of the runner.
2. **Approve the §7 loosenings** (R1/R2 gamma gates live; H1/H2 scaffolded-disabled)?
3. **Green-light the §5 contracts ask + §6 Crucible handoffs** (the critical path)?
4. **H2 first cut:** single-name (simpler, but sub-floor breadth) or cross-sectional from day
   one (needs H1 first)?
