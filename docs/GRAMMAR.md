# Forge — Hypothesis Grammar Narrative

Every rule in `config/grammar.yaml` has a section in this document, paired by id. The pre-commit hook (`scripts/check_grammar_doc_sync.py`) enforces the pairing. The rule's `rationale_ref` points here (`GRAMMAR.md#{id}`).

For each rule, four things:
- **What.** Plain-language statement of the rule.
- **Why.** The hypothesis the rule encodes — what failure mode it prevents.
- **Cost.** How much of the strategy search space it eliminates (low / medium / high), interpreted the same way as `cost_estimate` in the YAML.
- **Evidence to relax.** What we'd need to observe to justify loosening or removing the rule. Loosenings go through the `OPEN_PROPOSALS.md` review path (Phase 5); never silently to `grammar.yaml`.

See `DESIGN.md` §3 for grammar structure and §3.5 for the original ruleset. Encoding notes (predicate-type choices, table values) live in `IMPLEMENTATION_DECISIONS.md` (D009-D018).

---

## Structural rules

### S1: One hypothesis per strategy

**What.** Each strategy declares exactly one `hypothesis` from the canonical 6: `trend_continuation`, `mean_reversion`, `regime_arbitrage`, `relative_value`, `volatility_event`, `tail_hedge`.

**Why.** A strategy that bets on multiple hypotheses simultaneously is two strategies pretending to be one. Portfolio-level diversification belongs to QuantIQ; within Crucible, each candidate is evaluated on one hypothesis at a time so we can attribute promotion/rejection to that hypothesis's true edge. Combining hypotheses muddies attribution.

**Cost.** Low. The contracts package's `StrategyConfig.hypothesis: Literal[...]` already enforces this at the type level. The grammar rule reports it as a clean pass for completeness — useful when a hand-authored YAML somehow bypasses the type system.

**Evidence to relax.** Three or more promoted strategies that explicitly model multi-hypothesis combinations (e.g., "if regime=trending fire X else fire Y") and outperform single-hypothesis variants on the same underlying.

### S2: One directional signal source per strategy

**What.** Exactly one signal has `role: directional`. Other signals must be `regime_filter`, `filter`, or `confluence`.

**Why.** Two directional signals is two strategies wearing a coat: their direction votes have to be combined somehow, and the combination logic is itself a sub-strategy that should be evaluated separately. The combiner pattern (k_of_n / unanimous / majority) is for confluence on the *non-directional* signals.

**Cost.** Low. Most natural strategies have one direction-naming signal anyway; rejecting two-directional configs prunes a small slice of grossly over-specified candidates.

**Evidence to relax.** Promoted strategies that systematically use two competing directional signals with an explicit arbitration rule (e.g., always prefer A unless B disagrees by N σ).

### S3: At least one regime gate per strategy

**What.** At least one signal has `role: regime_filter`.

**Why.** A strategy without a regime gate fires in every market state, including states where its hypothesis is structurally wrong. Mean-reversion fires when momentum is at its strongest; trend-continuation fires when the market is range-bound; volatility-event fires when no event is near. Each fire in the wrong regime is dead-weight risk. Requiring an explicit regime gate forces the strategy to declare when it should *not* fire.

**Cost.** Low. Excludes unfiltered candidates — a clean prune. Some otherwise-promoted candidates might be unfiltered; this rule biases against them.

**Evidence to relax.** Four or more batches in a row where unfiltered candidates promote at the same rate as regime-filtered ones for the same hypothesis.

### S4: DTE bucket matches the directional signal's lookback class

**What.** The directional signal's lookback class (computed by taking the max *signal horizon* across its indicators and bucketing into `short_lookback` ≤ 6 days, `medium_lookback` 7-89, `long_lookback` ≥ 90) must be compatible with `dte_bucket` per the table:
- `short_lookback`: `swing_short` only
- `medium_lookback`: `swing_short` or `swing_mid`
- `long_lookback`: `swing_mid` or `swing_long`

> **v8 (D102, 2026-06-04).** The horizon is read from the Forge-owned table in
> `forge.grammar.signal_horizon`, **not** `IndicatorMetadata.lookback`. The live
> Crucible registry reports `lookback=0` for 34 of 43 indicators (and wrong
> values for most of the rest — `rsi_2`→14, `adx`/`hurst`/`macd`→0), which had
> collapsed this rule to "almost everything → `swing_short`" and produced
> horizon-*mismatched* configs. v8 also makes the bucket *derived* from the
> directional horizon at generation (`DTE_target = k·horizon`, snapped to the
> nearest permitted bucket) rather than sampled blind, and stops the regime gate
> from constraining the bucket (S4 was always about the directional signal). No
> change to this rule's *intent* or text — only its horizon input and the
> generation-time selection that honors it. See `IMPLEMENTATION_DECISIONS.md`
> D102.

**Why.** A signal's lookback is its hypothesis about the time scale at which information matters. A 2-day RSI is making a 2-day claim; a 252-day momentum is making a multi-month claim. Pairing a 252-day signal with a 14-21 DTE position means the trade closes long before the signal's underlying thesis can play out. The match enforces that signal time-scale and position time-scale agree.

**Cost.** Medium. Excludes many lookback/DTE mismatches — most plausibly novel candidates are still within the table; the rule mostly trims confused pairings.

**Evidence to relax.** Promoted long-lookback signals operating at short DTE buckets (or vice versa) with theoretical backing for why the mismatch works (e.g., "trend signal sets up early; we exit before the trend matures, capturing only the initial repricing").

### S5: Exit framework consistent with hypothesis

> **(v3, D071-final)** — schema bump. The original v1/v2 model named a single
> required exit per hypothesis ("must include `trailing_atr`"). v3 replaces that
> with a four-part composition (`required_always` / `required_from_set` /
> `optional_additions` / `forbidden`) so a hypothesis can offer a *choice* of
> equivalent exits. Operator-approved; see `IMPLEMENTATION_DECISIONS.md`
> D071-final and the source-of-truth table `_S5_HYPOTHESIS_EXITS` in
> `src/forge/grammar/custom_predicates.py`. The §3.5 DESIGN text still uses the
> single-required wording — see the L-3 amendment note in DESIGN §3.5 S5.

**What.** Every config carries the four E1 mandatory exits
(`expiry_exit`, `theta_cliff_exit`, `earnings_exit`, `liquidity_exit`, per
contracts `MANDATORY_EXIT_IDS`). On top of those, each hypothesis composes its
exit stack from four sets:

- `required_always` — all must be present.
- `required_from_set` — exactly **one** must be present (the "choose one of N"
  slot). Empty when `required_always` already exhausts the requirement.
- `optional_additions` — 0..`K_MAX_OPTIONAL` (=2) may be added.
- `forbidden` — none may be present.

Any exit beyond `E1 ∪ required_always ∪ chosen_from_set ∪ optional_additions`
is a "foreign" exit and rejects.

| Hypothesis | required_always | required_from_set (pick 1) | optional_additions | forbidden |
|---|---|---|---|---|
| `trend_continuation` | — | `trailing_atr` / `chandelier_exit` | `time_stop` | `hard_profit_target` |
| `mean_reversion` | — | `time_stop` / `target_exit` | `iv_crush_exit` | — |
| `regime_arbitrage` | — | `regime_flip_exit` | `time_stop` | — |
| `relative_value` | — | `convergence_exit` / `zscore_reversion_exit` | `time_stop` | — |
| `volatility_event` | `iv_crush_exit`, `event_passed_exit` | — | `time_stop` | — |
| `tail_hedge` | `roll_on_schedule_exit` | — | — | `hard_profit_target` |
| `event_momentum` (v12, D109) | — | `time_stop` | `trailing_atr` / `chandelier_exit` | `hard_profit_target` |

(`tail_hedge` is overlay-only and filtered at the sampler via D066's
`OVERLAY_ONLY_HYPOTHESES`; its row is retained for parity. `hard_profit_target`
is the canonical "profit-taking" exit forbidden per §3.5 — see D015 / D018.
D236 (v23): `parabolic_sar_exit` was dropped from the `trend_continuation`
pool — Crucible's exit sweep found `chandelier_exit` beats it on both the
CPCV-p25 tail and WF; `chandelier_exit` also samples an `atr_multiplier`
∈ [2.0, 3.0] tuned trail.)

**Why.** Each hypothesis has a built-in answer to "when is the trade over." Trend strategies are right until the trend breaks — a trailing/chandelier stop captures that; hard profit targets cap upside on the very moves the strategy is trying to ride. Mean-reversion is right within a known time horizon — a time stop or target/zscore exit bounds exposure. Volatility-event strategies have a discrete event in mind — exits must reference it (`event_passed_exit`) and the IV collapse (`iv_crush_exit`). `event_momentum` (v12, D109) rides the post-earnings drift, which decays over ~5–20 td: a `time_stop` is the primary exit (the drift window closing), momentum trailing (`trailing_atr`/`chandelier_exit`) optionally lets a strong drift run, and `hard_profit_target` is forbidden — the payoff is convex/positive-skew (long optionality on the drift), the same profile as the vol_event winners. The `required_from_set` choice lets Forge enumerate equivalent exit framings without contradicting the hypothesis; the `K_MAX_OPTIONAL` cap keeps the optional tail from bloating the stack.

**Cost.** Medium. Excludes most internally-inconsistent exit stacks; the surviving candidates have well-shaped exits.

**Evidence to relax.** A promoted strategy whose exit stack violates §3.5 S5 for its hypothesis — would prompt a per-row review of the table.

---

## Composition rules

### C1: No two indicators from the same family

**What.** Across all signals in the strategy, no two indicators share the same `IndicatorMetadata.family` (the 13 canonical families: `trend`, `trend_strength`, `mean_reversion`, `volatility`, `iv_structure`, `dealer_positioning`, `flow`, `macro`, `calendar`, `fundamental`, `smart_money`, `pairs`, `post_event_drift`). The check reads `IndicatorMetadata.family` dynamically — the canonical list is `crucible_contracts._INDICATOR_FAMILIES` (13 since v12/D109 added `post_event_drift` for H2 event_momentum; `trend_strength` was added by D019); this prose count is informational only. **This is the §2.1 fact H2 depends on:** `sue` is `post_event_drift` and `days_since_earnings` is `calendar` (Crucible reclassified it from `post_event_drift`), so the PEAD pair — surprise directional + post-event timing gate — is C1-legal in one config.

**Why.** Two same-family indicators correlate by construction — they're measuring the same latent variable through different statistics. RSI(2) and RSI(14) are both mean-reversion family; using both is redundancy that inflates apparent confluence. The rule forces signal diversity: confluence comes from independent information sources, not parameter variations.

**Cost.** Medium. Blocks plausible combinations like "RSI + ROC for mean-reversion confluence" — a real cost. We accept it because redundancy is a real failure mode.

**Evidence to relax.** Promoted strategies that meaningfully combine two same-family indicators with distinguishable param choices (e.g., RSI(2) for entry timing + RSI(14) for trend qualification with measurably independent signal).

### C2: Directional signal family matches hypothesis

**What.** The directional signal's indicator family must match the hypothesis per the table:
- `trend_continuation` → `trend`, `smart_money` (v19, D138 — `option_momentum`, the Heston-et-al. option-momentum continuation factor; the sibling `expected_value_estimator` is pinned out of the directional path)
- `mean_reversion` → `mean_reversion`
- `regime_arbitrage` → any family
- `relative_value` → `pairs`
- `volatility_event` → `iv_structure`, `flow`, or `dealer_positioning` (D062)
- `tail_hedge` → `macro`
- `event_momentum` → `post_event_drift` (v12, D109 — the directional is `sue`, the standardized earnings surprise driving the drift)

**Why.** A trend-continuation strategy that takes direction from a `pairs` indicator is taking direction from a relationship test, not from a trend signal — the hypothesis label and the signal disagree. Forcing the match keeps hypothesis labels honest. `regime_arbitrage` is the deliberate exception: by definition the strategy switches regimes, so any family that drives the switch is admissible.

**Cost.** High. Eliminates most cross-family pairings — a large fraction of the raw enumeration space.

**Evidence to relax.** Promoted strategy that combines hypothesis X with directional family Y where the table disallows the pairing AND the pairing has theoretical backing.

### C3: Maximum 4 signals per strategy

**What.** Total signal count ≤ 4 (one directional + at most three supporting).

**Why.** More than four signals is almost always overfit. The signal space has a small number of orthogonal axes; piling on more signals adds noise correlated with the existing ones. The hard cap is a curve-fitting brake, not a deeply principled number.

**Cost.** Low. The cap is generous enough that few useful candidates bump against it.

**Evidence to relax.** Promoted strategy uses 5+ signals with each measurably contributing orthogonal information.

### C4: Regime gate cannot use the same indicator as the directional signal

**What.** No indicator id appears in both the directional signal's `indicators` tuple and any `regime_filter` signal's `indicators` tuple.

**Why.** A directional signal saying "buy when RSI < 30" plus a regime gate saying "only when RSI < 50" is circular — the gate restates the directional condition with looser bounds. The directional logic must be filtered by *different* evidence, not its own evidence rewindowed.

**Cost.** Low. Same-indicator overlap is structurally rare; the rule mostly catches careless reuse.

**Evidence to relax.** Promoted strategy reuses the directional indicator as a regime gate with a different threshold AND the threshold combination encodes a genuinely separate condition.

---

## Parameter coherence rules

### P1: Indicator parameters within published ranges

**What.** Every signal's `params` keys must appear in the union of its indicators' `params_schema` keys (Phase 1 reading; see D-log). Full type+range validation against `params_schema` is deferred.

**Why.** The registry pins the parameter shape an indicator accepts. A signal that passes `params: {bogus_key: 1}` to RSI is configuring a parameter the indicator doesn't expose — silently no-op at runtime, but the grammar should refuse before Crucible has to.

**Cost.** Low (in the v1 reading). The full type+range validation will be stricter when implemented in a later phase.

**Evidence to relax.** N/A — this is a correctness check, not a hypothesis. The follow-up is to *strengthen* P1 with full schema validation, not relax it.

### P2: DTE window matches bucket (entry side)

**What.** `selector.dte_min` and `selector.dte_max` must fall within the entry-DTE window for `dte_bucket`:
- `swing_short`: 14-21 DTE
- `swing_mid`: 30-45 DTE
- `swing_long`: 60-90 DTE

(Exit-DTE thresholds live in `theta_cliff_exit.params` and are not pinned in §3.5; P2 v1 checks the entry-side window only. Surfaced as an open question in `OPEN_QUESTIONS.md`.)

**Why.** Each bucket has a domain meaning: `swing_short` is 2-4 week positions, `swing_mid` is 1-2 month, `swing_long` is 2-3 month. Letting `selector.dte_min` drift outside the bucket's named window dilutes the bucket label.

**Cost.** Medium. Excludes most non-coherent DTE/bucket pairings.

**Evidence to relax.** Promoted strategies whose `dte_min`/`dte_max` sit just outside the bucket's window suggest the window should widen — a calibration rather than a relaxation.

### P3: Delta target within DTE-appropriate band

**What.** `selector.delta_target` falls within the band for `dte_bucket`:
- `swing_short`: 0.40-0.55 (ATM-ish)
- `swing_mid`: 0.30-0.45
- `swing_long`: 0.20-0.35

Hypothesis-scoped overrides (v16, D125 — P3's first; bands above remain the base):
- `trend_continuation` × `swing_long`: 0.20-0.55
- `trend_continuation` × `swing_mid`: 0.30-0.55

**Why.** Short-DTE positions live in a high-theta, high-gamma regime — ATM-ish deltas dominate; OTM puts/calls decay before any movement matters. Long-DTE positions can afford lower deltas because there's time for the position to develop into the money. The bands match each bucket's natural delta range.

The trend overrides widen the UPPER edge only: systematically buying low-delta/OTM options pays the embedded-leverage premium (Frazzini-Pedersen RAPS 2022), and the within-band evidence agreed — trend component rate rises monotonically toward the upper band edge (the relax clause below, triggered), with every honest-coverage trend component in the upper two terciles. MR and vol_event show the OPPOSITE gradient (components concentrate low-delta), so only trend widens; lower edges keep the convexity rationale. Operator-approved loosening: OPEN_PROPOSALS `343e71fd`, D125.

**Cost.** Medium. Excludes off-band deltas that would mostly be premium-collection or far-OTM lottery tickets.

**Evidence to relax.** Promoted strategies whose `delta_target` sits at the band edges suggest widening — again a calibration. (Fired once: the v16 trend overrides above.)

### P4: Sizer per-trade risk percentage in [0.005, 0.02]

**What.** `sizer.per_trade_risk_pct` must be in `[0.005, 0.02]`. The upper bound is also enforced by contracts' `SizerSpec` validator (the absolute cap from `ABSOLUTE_MAX_PER_TRADE_RISK_PCT`).

**Why.** The upper bound is a hard risk-management cap — promoted strategies cannot leak risk into the 3%+ range. The lower bound prevents accidental zero-sized positions: a 0.001% per-trade risk allocates near-nothing, which means the strategy "exists" without being able to move the portfolio. Real strategies size to be felt.

**Cost.** Low. Most natural sizings sit comfortably within the band.

**Evidence to relax.** Lower bound: a documented micro-hedging strategy that genuinely wants to allocate 0.1-0.5% per trade. Upper bound: cannot be relaxed at the grammar level; the contracts package owns that ceiling.

---

## Exit logic rules

### E1: Mandatory exits always present

**What.** Every strategy includes the four mandatory exits from `crucible_contracts.MANDATORY_EXIT_IDS`: `expiry_exit`, `theta_cliff_exit`, `earnings_exit`, `liquidity_exit`. (Note: §3.5 lists three; contracts pins four per D007/D014. The contracts count wins.)

**Why.** These four exits encode failure modes the strategy doesn't get to opt out of: option expiration is a hard date; theta cliff is a known decay regime; earnings is a known-unknown event; liquidity collapse turns paper P&L into stuck positions. Skipping any of them is taking risk the framework doesn't know how to bound.

**Cost.** Low. Most candidates include the mandatory exits by construction.

**Evidence to relax.** Cannot relax at the grammar level; the contracts package's `StrategyConfig` validator enforces it. The grammar rule is defense in depth.

### E2: At most 2 stop-loss exits

**What.** Counting exits whose id is in `STOP_LOSS_EXIT_IDS` (`premium_stop_loss`, `atr_underlying_stop_loss`, `trailing_atr`), the count must be ≤ 2.

**Why.** A strategy with three stop-loss types is over-specified — the multiple stops will trigger at slightly different times and the strategy ends up exiting on whichever fires first, regardless of which threshold the strategy author intended to be primary. The cap (one premium stop + one ATR stop, per §3.5 narrative) is enough to express most defensible stop logic.

**Cost.** Low. Three-stop configs are rare.

**Evidence to relax.** Promoted strategy uses three distinct stop-loss exits with non-redundant trigger conditions and the third stop measurably contributes to outcome.

### E3: Trailing stop requires activation threshold

**What.** If any exit has `id: trailing_atr`, its `params.activate_after_gain_pct` must be ≥ 0.30.

**Why.** A trailing stop that activates from zero gain locks in losses: any retracement past the noise floor exits the position. The activation threshold (gain must reach 30%+ before the trailing logic engages) ensures the trailing stop captures *profit* rather than amplifying loss. The 0.30 floor is a reasonable conservative default.

**Cost.** Low. Most trailing-stop usages have an activation threshold anyway.

**Evidence to relax.** Promoted trend strategy uses `trailing_atr` with activate_after_gain_pct < 0.30 systematically — would suggest the threshold should adapt to volatility regime.

---

## Regime coherence rules

### R1: Mean-reversion requires IV-rank gate (v1, D013; v11, D107; v20, D150; v22, D167; v24, D254; v28, D265)

**What.** When `hypothesis == "mean_reversion"`, at least one `regime_filter` signal must reference `iv_rank` with `params.threshold ≤ 50`, **or** `gamma_flip_distance_pct` (v11, D107 — the dealer-gamma regime switch, MR side), **or** `hurst` (v20, D150 — the mean-reverting H<0.5 side, op `"<"`), **or** `rv_rank` (v22, D167 — cheap realized vol, op `"<"` = LOW/calm), **or** `vol_regime` (v24, D254 — the discrete vol tercile, `< 2` = exclude the high-vol tercile), **or** `realized_vol` (v28, D265 — ABSOLUTE annualized 21d realized vol, op `"<"`, sweep 0.15-0.30). (D013 collapsed the second clause about directional-family alignment — redundant given C2.)

**Why.** Mean-reversion strategies make money by selling rich premium that mean-reverts. Selling premium when IV is already low (cheap premium) is selling lottery tickets — there's no premium to capture, and any IV expansion hurts. The `iv_rank` gate forces "fire only when IV is cheap enough that the reversion has room to work." `gamma_flip_distance_pct` (v11, D107) is the alternative dealer-gamma regime gate: MR pays in the **long-gamma / dampening / ranging** regime (flip below spot → dealers long gamma → mean-reverting price action), the op `"<"` side set by the sampler — the complement of R2's trend-side gamma gate (op `">"`, short-gamma). `hurst` (v20, D150) is the third and purest ranging gate: `hurst < 0.5` is the mathematical signature of a mean-reverting (anti-persistent) series, so it fires only when the regime is itself mean-reverting — the op `"<"` side set by the sampler, the complement of R2's trend-side `hurst` gate (op `">"`, persistent). Same indicator, opposite side per hypothesis: the regime "switch." (C4 keeps `hurst` single-role.) **D150/D151 note:** the bar-based `hurst` gate is per-name-coherent on the rank path — Crucible answered Q33 YES (`hurst.rank_per_name_coherent = True`, D151/v21), so a **hurst-gated MR config now RANKS** (the breadth lever), while the chain-reading `iv_rank` / `gamma_flip` gates stay single-name confluence via the published-flag skip (`space.rank_excluded_ids`). D116 stays correct for the chain-readers; the D150 conservative hold (`_RANK_INELIGIBLE_HYPOTHESES`) is removed. `rv_rank` (v22, D167) is the fourth and densest ranging gate: cheap **realized** vol (`rv_rank < threshold`, op `"<"` = the calm, reversion-friendly regime). Crucible's causal trade-attribution (`FORGE_mr_rv_hurst_overlap_response`) found `rv_rank` **independent of** the `hurst` gate (Spearman ≈ −0.036) and **dominant** over it (carries the per-trade-Sharpe gradient inside every hurst stratum; hurst carries none inside any rv_rank stratum), and — being a name-relative percentile with no absolute-threshold fragility — the better-behaved conditioner. Added **alongside** the existing three (R1 stays an OR; existing hurst configs untouched), with the sampler biasing the pick toward it over the prefilter-sparse `iv_rank`. Like `hurst` it is rank-coherent (`rank_per_name_coherent = True`), so an `rv_rank`-gated MR config also ranks — though MR's edge is on confluence. Honest cap (hard rule 6): a per-trade-quality / cap-efficiency lift to the book **center**, NOT a worst-quartile p25 unlock. `vol_regime` (v24, D254) is the fifth accepted gate and the **cross-sectional-MR champion**: unlike trend (where `rv_rank` is the KING *cost* gate), MR wants a *regime* gate — Crucible's real WF+CPCV sweep found `vol_regime < 2` (exclude the top vol tercile) beats the `rv_rank` cost gate by **+0.244 CPCV-p25 in all 6 components** (§2b.1). It is a **discrete Int8 tercile** → gated with a RAW threshold `< 2`, never `use_percentile` (degenerate on a 3-value series); `< 1` (strict calm) starves the book. Admitted per the D107/D150/D167 widening pattern (operator-approved loosening; R1 stays an OR). Corollary from the same sweep: `hurst` is null-to-negative as an MR gate (−0.27 vs `rv_rank`, 0/6 folds), so it stays in the R1 OR but the **sampler biases away from it** toward `rv_rank`/`vol_regime`. `realized_vol` (v28, D265) is the sixth accepted gate and the **systematic-spike complement**: the champion post-mortem (Crucible `FORGE_mr_absolute_vol_gate_request_2026-07-12`) showed the `rv_rank` PERCENTILE normalizes in regime-WIDE vol spikes — every name is volatile, so ranks stay mid-distribution and the gate passes exactly when it should bind (probe-verified 2026-07-12: `rv_rank<62` open 21/21 days on all five knife-catch names in 2022-12 while absolute rv held ≥ 0.25). The ABSOLUTE threshold (`realized_vol < θ`, θ ∈ [0.15, 0.30] annualized, op `"<"`) binds regardless of the cross-section. PER-NAME semantics (registry `market_wide_by_design=False`): pass rates are strongly name-heterogeneous (`<0.20` passes HAL 4% … JPM 39% of bars), so tight arms zero-trade hot names — the `expected_trades` wall culls them and the sweep's top half keeps hot names live; Crucible's preferred MARKET-level variant (reference-underlying RV) needs a new market-wide registry id (relayed, future bump). C1: `realized_vol` shares family `volatility` with `rv_rank`/`vol_regime`, so the absolute gate REPLACES the percentile in the vol slot (never both in one config), and C1's chain guard keeps it out of any `vol_target`-sized config (the X1 chain is the same indicator); the v26 `ivol` veto (family `idiosyncratic_vol`) still stacks on top — the asked both-gates shape. Honest scope: Crucible's own removal counterfactual is P&L-NEGATIVE overall and only gate-positive (weak blocks decide cpcv_p25) — no gated config has been measured; generating the family IS the probe, the gate decides.

**Cost.** Medium. Excludes mean-reversion strategies that don't explicitly gate on one of the accepted ranging proxies (`iv_rank`, `gamma_flip_distance_pct`, `hurst`, `rv_rank`, `vol_regime`, `realized_vol`).

**Evidence to relax.** Promoted mean-reversion strategies that use a regime proxy outside the accepted set `{iv_rank, gamma_flip_distance_pct, hurst, rv_rank, vol_regime, realized_vol}` (e.g., `iv_zscore`, a custom realized-vs-implied ratio, or a new percentile-rank conditioner). (Fired: the v24/D254 `vol_regime` admission, and the v28/D265 `realized_vol` admission — Crucible's champion post-mortem as the outside-the-pool evidence.)

**v26 (D263) — optional idiosyncratic-vol veto (`ivol`), a name-selection refinement.** In addition to the mandatory MR regime gate above, a `mean_reversion` config may carry an OPTIONAL SECOND `regime_filter` gate: `ivol` (per-name CAPM-residual idiosyncratic vol, family `idiosyncratic_vol`, `op: "<"`, percentile plateau [0.2,0.4], window 63). It EXCLUDES the high-idio-vol oversold names — the "falling knives" whose reversion fails (Bhootra-Hur 2015; Crucible `FORGE_ivol_lo_mr_entry_gate_2026-07-09`, +0.163 cpcv, 6/6). §3.5 S3 permits more than one regime gate, so R1 stays satisfied by the primary gate. UNLIKE the R2 `days_since_jump` veto (`volatility` family, mutually exclusive with the level gates), `ivol` is `idiosyncratic_vol` — a DISTINCT C1 family — so it STACKS **on top of** the `rv_rank` / `vol_regime` gate (the validated form; the reason contracts 1.28.0 split the family). It is **not** a member of R1's accepted set (it does not satisfy R1 on its own), and it is emitted only when the registry serves the id.

### R2: Trend strategies require regime gate (v2, D077; v11, D107; v17, D131; v27, D264)

**What.** When `hypothesis == "trend_continuation"`, at least one `regime_filter` signal must reference indicator `adx`, `hurst`, `rv_rank`, `gamma_flip_distance_pct`, `market_state`, or `vix_term_slope`.

**Why.** Trend-continuation strategies presume there *is* a trend to continue. Firing in range-bound markets is dead-weight risk. `adx` gates on trend strength, `hurst` on trend persistence. `rv_rank` (v2, D077) gates on realized-vol regime — PTS thesis: "enter trend-following long calls when realized vol is cheap" (`rv_rank < threshold`, `op: "<"`). `gamma_flip_distance_pct` (v11, D107 — the dealer-gamma regime switch, H3) gates on the dealer-gamma regime: trend pays when dealers are SHORT gamma and amplifying moves (flip above spot → `gamma_flip_distance_pct > threshold`, `op: ">"`), per the GEX literature (SpotGamma/SqueezeMetrics: negative-gamma = trending) and Forge's own gated cohort (trend is the weakest archetype; gating it to its productive regime is the lever). `market_state` (v17, D131 — the relax clause below fired, operator-approved) gates on the market state: sign of the reference's trailing 252-session return, `market_state > 0` = up-market — momentum pays after up-markets and inverts after down-markets (Cooper/Gutierrez/Hameed JF 2004; Daniel-Moskowitz crash regime = down-state). Market-wide by design, so it is also a coherent gate on trend's rank arm. `vix_term_slope` (v27, D264 — the relax clause's second firing, operator-approved via OPEN_PROPOSALS `0a4d8da8`) gates on the vol term structure: `vix_term_slope > threshold` (threshold ∈ [0, 2], `op: ">"`) = contango = calm market. REVERSES the v17/D131 deliberate exclusion ("validated for vol returns, not trend conditioning"): Crucible's `probe_resid_vix_swing_mid` measured exactly this use at campaign grade and produced the **first walk-forward-gate pass in program history** (WF median 2.0611 vs gate 2.0, paired with the `residual_momentum` directional; `FORGE_resid_vix_generation_request_2026-07-11`). Their measured failure mode — the gate stays in contango too long at bear onsets (2022-02/05) — is why the sampled range explores tighter thresholds (>0.5..1.0), not just >0. Market-wide by design, so also coherent on trend's rank arm (the `market_state` precedent).

**Cost.** Medium. Excludes trend strategies without an explicit regime filter from the accepted set.

**Evidence to relax.** Promoted trend strategies that use a regime gate outside `{adx, hurst, rv_rank, gamma_flip_distance_pct, market_state, vix_term_slope}`. (Fired twice: the v17 `market_state` admission, and the v27 `vix_term_slope` admission — where the outside-the-pool evidence arrived as Crucible's campaign-grade probe rather than a post-promotion observation.)

**v25 (D258) — optional volatility veto (`days_since_jump`).** In addition to the mandatory trend-strength gate above, a `trend_continuation` config may carry an OPTIONAL SECOND `regime_filter` gate: `days_since_jump` (family `volatility`, `op: "<"`, threshold on the 30–65 trading-day plateau). It vetoes "dead tape" — names with no ≥5% move for N+ days, where the trend champion's theta-bleed losses cluster (Crucible `FORGE_days_since_jump_indicator_2026-07-08`). §3.5 S3 permits more than one regime gate, so R2 stays satisfied by the primary gate; and because it is `volatility` family, C1 keeps `days_since_jump` mutually exclusive with the volatility-level gates (`rv_rank` / `vol_regime`) — a config picks the frequency veto OR a level gate, never both. It is **not** a member of R2's accepted set (it does not satisfy R2 on its own), and it is emitted only when the registry serves the id (dormant otherwise).

### R3: Volatility-event strategies require event-proximity gate

> **(v2, D039 + M-9)** — pool widened from 2 to 5 event-proximity indicators
> and ETF-incompatibility added. **(v18, D135)** — pool widened to 6:
> `pre_earnings_setup` (operator-approved adoption cut).

**What.** When `hypothesis == "volatility_event"`, at least one `regime_filter` signal must reference one of the six event-proximity indicators: `days_to_earnings`, `days_to_fomc`, `days_to_cpi`, `days_to_nfp`, `days_to_opex`, `pre_earnings_setup` (all `calendar` family). **ETF exception:** ETF underlyings (`SPY`, `QQQ`, `IWM`, `DIA`) have no earnings, so `days_to_earnings` returns the sentinel/far value and never fires — the (ETF underlying, `days_to_earnings`) combination is rejected at validation time (T1.4/D039). `pre_earnings_setup` composes `days_to_earnings`, so it carries the same ETF rejection (D135). On ETFs the gate must use a macro-calendar indicator instead.

**Why.** Volatility-event strategies depend on a discrete event happening (earnings, FOMC, CPI, NFP, OPEX) — firing far from any event means the volatility setup hasn't materialized. The gate forces declaration of the event the strategy is anchoring to. The macro-calendar additions (D039) make the hypothesis usable on ETFs, which have no single-name earnings. (All are sampled as regime gates per `_INDICATOR_THRESHOLD_TABLE` — M-9 added the threshold entries for the three macro indicators that D039 introduced but left unsamplable.) `pre_earnings_setup` (v18, D135) is the composed pre-earnings IV-run-up conditioner — `days_to_earnings ∈ [enter_min, enter_max]` (calendar days, sampled centered on [7, 14]) AND `rv_rank < rv_q` — expressing the Chung-Louis / Gao-Xing-Zhang region at full fidelity in the existing one-gate slot; Crucible's mandatory `earnings_exit` forces the pre-announcement exit, which is exactly the variant that dodged the post-2013 decay.

**Cost.** Medium. Excludes volatility-event strategies without an explicit event reference.

**Evidence to relax.** Promoted volatility-event strategies that use a non-calendar event proxy (e.g., "iv_spike_above_threshold" as a generic event indicator). (Fired once, in composed form: the v18 `pre_earnings_setup` admission — still calendar-anchored.)

---

## Risk coherence rules

### X1: Vol-target sizing requires realized_vol indicator

**What.** When `sizer.mode == "vol_target"`, at least one signal must reference indicator `realized_vol`.

**Why.** Vol-target sizing scales position by realized volatility — but the sizer reads its volatility estimate from somewhere. Forcing the strategy to declare `realized_vol` as an explicit indicator ensures the input is computed from the registered indicator pipeline rather than improvised inside the sizer.

**Cost.** Medium. Excludes vol-target sizings that lack the explicit indicator declaration.

**Evidence to relax.** A registered alternative realized-vol proxy with the same downstream API — would amend the predicate's expected indicator id (or add the alias).

### X2: Fractional Kelly requires expected_value_estimator

**What.** When `sizer.mode == "fractional_kelly"`, at least one signal must reference indicator `expected_value_estimator`.

**Why.** Fractional Kelly sizing scales position by edge-relative-to-variance: needs an EV estimate. The registered `expected_value_estimator` is a Crucible-provided helper that computes EV from win-rate and average win/loss. Forcing the strategy to declare it ensures the Kelly fraction is computed from a known estimator rather than improvised.

**Cost.** Medium. Excludes fractional-Kelly sizings that lack the explicit EV indicator.

**Evidence to relax.** An alternative EV estimator becomes a Crucible helper with the same downstream API — would also need an alias on the `expected_value_estimator` name.
