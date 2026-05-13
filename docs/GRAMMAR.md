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

**What.** The directional signal's lookback class (computed by taking the max `IndicatorMetadata.lookback` across its indicators and bucketing into `short_lookback` ≤ 6 days, `medium_lookback` 7-89, `long_lookback` ≥ 90) must be compatible with `dte_bucket` per the table:
- `short_lookback`: `swing_short` only
- `medium_lookback`: `swing_short` or `swing_mid`
- `long_lookback`: `swing_mid` or `swing_long`

**Why.** A signal's lookback is its hypothesis about the time scale at which information matters. A 2-day RSI is making a 2-day claim; a 252-day momentum is making a multi-month claim. Pairing a 252-day signal with a 14-21 DTE position means the trade closes long before the signal's underlying thesis can play out. The match enforces that signal time-scale and position time-scale agree.

**Cost.** Medium. Excludes many lookback/DTE mismatches — most plausibly novel candidates are still within the table; the rule mostly trims confused pairings.

**Evidence to relax.** Promoted long-lookback signals operating at short DTE buckets (or vice versa) with theoretical backing for why the mismatch works (e.g., "trend signal sets up early; we exit before the trend matures, capturing only the initial repricing").

### S5: Exit framework consistent with hypothesis

**What.** Each hypothesis names its required and forbidden exit ids:
- `trend_continuation`: must include `trailing_atr`; must NOT include `hard_profit_target`.
- `mean_reversion`: must include `time_stop`.
- `regime_arbitrage`: must include `regime_flip_exit`.
- `relative_value`: must include `convergence_exit`.
- `volatility_event`: must include `iv_crush_exit` and `event_passed_exit`.
- `tail_hedge`: must include `roll_on_schedule_exit`; must NOT include `hard_profit_target` (the canonical "profit-taking" exit per §3.5 narrative — see D015 / D018).

**Why.** Each hypothesis has a built-in answer to "when is the trade over." Trend strategies are right until the trend breaks — trailing stops capture that; hard profit targets cap upside on the very moves the strategy is trying to ride. Mean-reversion is right within a known time horizon — time stops bound exposure. Volatility-event strategies have a discrete event in mind — exits must reference it. The required/forbidden lists keep exit logic from contradicting the hypothesis.

**Cost.** Medium. Excludes most internally-inconsistent exit stacks; the surviving candidates have well-shaped exits.

**Evidence to relax.** A promoted strategy whose exit stack violates §3.5 S5 for its hypothesis — would prompt a per-row review of the table.

---

## Composition rules

### C1: No two indicators from the same family

**What.** Across all signals in the strategy, no two indicators share the same `IndicatorMetadata.family` (the 11 canonical families: `trend`, `mean_reversion`, `volatility`, `iv_structure`, `dealer_positioning`, `flow`, `macro`, `calendar`, `fundamental`, `smart_money`, `pairs`).

**Why.** Two same-family indicators correlate by construction — they're measuring the same latent variable through different statistics. RSI(2) and RSI(14) are both mean-reversion family; using both is redundancy that inflates apparent confluence. The rule forces signal diversity: confluence comes from independent information sources, not parameter variations.

**Cost.** Medium. Blocks plausible combinations like "RSI + ROC for mean-reversion confluence" — a real cost. We accept it because redundancy is a real failure mode.

**Evidence to relax.** Promoted strategies that meaningfully combine two same-family indicators with distinguishable param choices (e.g., RSI(2) for entry timing + RSI(14) for trend qualification with measurably independent signal).

### C2: Directional signal family matches hypothesis

**What.** The directional signal's indicator family must match the hypothesis per the table:
- `trend_continuation` → `trend`
- `mean_reversion` → `mean_reversion`
- `regime_arbitrage` → any family
- `relative_value` → `pairs`
- `volatility_event` → `iv_structure` or `flow`
- `tail_hedge` → `macro`

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

**Why.** Short-DTE positions live in a high-theta, high-gamma regime — ATM-ish deltas dominate; OTM puts/calls decay before any movement matters. Long-DTE positions can afford lower deltas because there's time for the position to develop into the money. The bands match each bucket's natural delta range.

**Cost.** Medium. Excludes off-band deltas that would mostly be premium-collection or far-OTM lottery tickets.

**Evidence to relax.** Promoted strategies whose `delta_target` sits at the band edges suggest widening — again a calibration.

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

### R1: Mean-reversion requires IV-rank gate

**What.** When `hypothesis == "mean_reversion"`, at least one `regime_filter` signal must reference indicator `iv_rank` with `params.threshold ≤ 50`. (D013 collapsed the second clause about directional-family alignment — redundant given C2.)

**Why.** Mean-reversion strategies make money by selling rich premium that mean-reverts. Selling premium when IV is already low (cheap premium) is selling lottery tickets — there's no premium to capture, and any IV expansion hurts. The gate forces strategies to declare "fire only when IV is cheap enough that the reversion has room to work."

**Cost.** Medium. Excludes mean-reversion strategies that don't explicitly gate on IV.

**Evidence to relax.** Promoted mean-reversion strategies that use a non-`iv_rank` IV-percentile proxy (e.g., `iv_zscore`, custom realized-vs-implied ratio).

### R2: Trend strategies require trend-strength gate

**What.** When `hypothesis == "trend_continuation"`, at least one `regime_filter` signal must reference indicator `adx` or `hurst`.

**Why.** Trend-continuation strategies presume there *is* a trend to continue. Firing in range-bound markets is dead-weight risk. The named indicators (`adx` for trend strength, `hurst` for trend persistence) are the canonical Phase-1 proxies; the gate forces the strategy to declare a trend-strength condition.

**Cost.** Medium. Excludes trend strategies without an explicit trend-strength filter.

**Evidence to relax.** Promoted trend strategies that use a non-`adx`/`hurst` trend-strength proxy.

### R3: Volatility-event strategies require event-proximity gate

**What.** When `hypothesis == "volatility_event"`, at least one `regime_filter` signal must reference indicator `days_to_earnings` or `days_to_fomc`.

**Why.** Volatility-event strategies depend on a discrete event happening (earnings, FOMC) — firing far from any event means the volatility setup hasn't materialized. The gate forces declaration of the event the strategy is anchoring to.

**Cost.** Medium. Excludes volatility-event strategies without an explicit event reference.

**Evidence to relax.** Promoted volatility-event strategies that use a non-calendar event proxy (e.g., "iv_spike_above_threshold" as a generic event indicator).

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
