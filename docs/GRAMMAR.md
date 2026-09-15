# Forge — Hypothesis Grammar Narrative

Every rule in `config/grammar.yaml` has a section here, paired by id; the pre-commit hook
(`scripts/check_grammar_doc_sync.py`) enforces the pairing, and each rule's `rationale_ref` points
here (`GRAMMAR.md#{id}`). The grammar is **FROZEN at v55** (D390): any change needs an open
preregistration first (`docs/tasks/grammar-change.md`), and no code writes `grammar.yaml` at
runtime (hard rule #4) — loosenings are operator commits, never applied by machinery.

Per rule: **What** (the LIVE rule — the predicate code in `src/forge/grammar/custom_predicates.py`
is the source of truth), **Why**, **Cost** (low / medium / high, read like `cost_estimate` in the
YAML), **Evidence to relax**. Where a rule body was amended after v1, the admission is one line
carrying its D-entry; the measurement narrative lives in `IMPLEMENTATION_DECISIONS.md`, not here.
`DESIGN.md` §3.5 holds the v1 statements verbatim (its drift banner names which bodies moved);
encoding notes are D009–D018.

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

**What.** At least one signal has `role: regime_filter`. Two amendments, both at the predicate
surface with the YAML untouched:

- **Exempt (v35, D280; shared with R1):** a `mean_reversion` config whose directional is the
  capitulation `momentum` id (the C2 per-id carve-out) needs no gate — the operator-approved
  bare-drop arm (`_R1_GATE_EXEMPT_DIRECTIONALS`, keyed on the directional's exact indicator tuple).
- **`min: 1` permits an optional SECOND gate:** the sampler fills one mutually-exclusive
  second-gate slot (max 2 total) from the veto pools listed under R1 and R2. The v44 hurst×vix
  conditioner draw (D317/D319) was retired at v55 (D366). C1 keeps the second gate a different
  family from the primary.

**Why.** A strategy without a regime gate fires in every market state, including states where its hypothesis is structurally wrong. Mean-reversion fires when momentum is at its strongest; trend-continuation fires when the market is range-bound; volatility-event fires when no event is near. Each fire in the wrong regime is dead-weight risk. Requiring an explicit regime gate forces the strategy to declare when it should *not* fire.

**Cost.** Low. Excludes unfiltered candidates — a clean prune. Some otherwise-promoted candidates might be unfiltered; this rule biases against them.

**Evidence to relax.** Four or more batches in a row where unfiltered candidates promote at the same rate as regime-filtered ones for the same hypothesis.

### S4: DTE bucket matches the directional signal's lookback class

**What.** The directional signal's lookback class (computed by taking the max *signal horizon* across its indicators and bucketing into `short_lookback` ≤ 6 days, `medium_lookback` 7-89, `long_lookback` ≥ 90) must be compatible with `dte_bucket` per the table:
- `short_lookback`: `swing_short` only
- `medium_lookback`: `swing_short` or `swing_mid`
- `long_lookback`: `swing_mid` or `swing_long`

The horizon is the Forge-owned table in `forge.grammar.signal_horizon`, **not**
`IndicatorMetadata.lookback` (v8, D102 — the live registry reports `lookback=0` for most
indicators, which had collapsed the rule to "almost everything → `swing_short`"); v8 also derives
the bucket from the directional horizon at generation (`DTE_target = k·horizon`, snapped to the
nearest permitted bucket) and stops the regime gate from constraining it. Intent and text unchanged.

**Why.** A signal's lookback is its hypothesis about the time scale at which information matters. A 2-day RSI is making a 2-day claim; a 252-day momentum is making a multi-month claim. Pairing a 252-day signal with a 14-21 DTE position means the trade closes long before the signal's underlying thesis can play out. The match enforces that signal time-scale and position time-scale agree.

**Cost.** Medium. Excludes many lookback/DTE mismatches — most plausibly novel candidates are still within the table; the rule mostly trims confused pairings.

**Evidence to relax.** Promoted long-lookback signals operating at short DTE buckets (or vice versa) with theoretical backing for why the mismatch works (e.g., "trend signal sets up early; we exit before the trend matures, capturing only the initial repricing").

### S5: Exit framework consistent with hypothesis

Schema: v3 (D071-final) replaced "one required exit per hypothesis" with a four-part composition so
a hypothesis can offer a *choice* of equivalent exits. The source-of-truth table is
`_S5_HYPOTHESIS_EXITS` in `src/forge/grammar/custom_predicates.py`; DESIGN §3.5 keeps the v1
single-required wording, bannered.

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
| `volatility_event` (v39, D290) | `iv_crush_exit`, `time_stop` | — | — | `event_passed_exit` |
| `tail_hedge` | `roll_on_schedule_exit` | — | — | `hard_profit_target` |
| `event_momentum` (v12, D109) | — | `time_stop` | `trailing_atr` / `chandelier_exit` | `hard_profit_target` |

Lineage of the table: `tail_hedge` is overlay-only and filtered at the sampler (D066
`OVERLAY_ONLY_HYPOTHESES`; row kept for parity); `hard_profit_target` is the canonical
"profit-taking" exit §3.5 forbids (D015/D018); `parabolic_sar_exit` left the trend pool (v23, D236 —
`chandelier_exit` beat it on both the CPCV-p25 tail and WF; chandelier samples an `atr_multiplier`
∈ [2.0, 3.0] trail); `event_passed_exit` moved from required to FORBIDDEN on `volatility_event`
(v39, D290 — Forge never emitted an `event_indicator`, so it only ever ran Crucible's fallback hard
cut that truncated every ve hold; `time_stop` ~ U[4,7] is the required hold instead); the
`mean_reversion` pick is WEIGHTED toward `time_stop` (p=0.65) and MR timer draws sample `n_bars`
~ U[8,12] (v40, D291 — sampler policy; the sets themselves are unchanged).

**Why.** Each hypothesis has a built-in answer to "when is the trade over." Trend strategies are right until the trend breaks — a trailing/chandelier stop captures that; hard profit targets cap upside on the very moves the strategy is trying to ride. Mean-reversion is right within a known time horizon — a time stop or target exit bounds exposure. Volatility-event strategies have a discrete event in mind — exits reference the IV collapse (`iv_crush_exit`) plus a short required hold (`time_stop`). `event_momentum` (v12, D109) rides the post-earnings drift, which decays over ~5–20 td: a `time_stop` is the primary exit (the drift window closing), momentum trailing (`trailing_atr`/`chandelier_exit`) optionally lets a strong drift run, and `hard_profit_target` is forbidden — the payoff is convex/positive-skew (long optionality on the drift), the same profile as the vol_event winners. The `required_from_set` choice lets Forge enumerate equivalent exit framings without contradicting the hypothesis; the `K_MAX_OPTIONAL` cap keeps the optional tail from bloating the stack.

**Cost.** Medium. Excludes most internally-inconsistent exit stacks; the surviving candidates have well-shaped exits.

**Evidence to relax.** A promoted strategy whose exit stack violates §3.5 S5 for its hypothesis — would prompt a per-row review of the table.

---

## Composition rules

### C1: No two indicators from the same family

**What.** Across all signals in the strategy, no two indicators share the same
`IndicatorMetadata.family`. The check reads the family dynamically; the canonical list is
`crucible_contracts._INDICATOR_FAMILIES` (13 as of v12: `trend`, `trend_strength` (D019),
`mean_reversion`, `volatility`, `iv_structure`, `dealer_positioning`, `flow`, `macro`, `calendar`,
`fundamental`, `smart_money`, `pairs`, `post_event_drift` (D109) — the count here is informational).
H2 depends on one fact of that list: `sue` is `post_event_drift` and `days_since_earnings` is
`calendar`, so the PEAD pair (surprise directional + post-event timing gate) is C1-legal in one config.

**Why.** Two same-family indicators correlate by construction — they're measuring the same latent variable through different statistics. RSI(2) and RSI(14) are both mean-reversion family; using both is redundancy that inflates apparent confluence. The rule forces signal diversity: confluence comes from independent information sources, not parameter variations.

**Cost.** Medium. Blocks plausible combinations like "RSI + ROC for mean-reversion confluence" — a real cost. We accept it because redundancy is a real failure mode.

**Evidence to relax.** Promoted strategies that meaningfully combine two same-family indicators with distinguishable param choices (e.g., RSI(2) for entry timing + RSI(14) for trend qualification with measurably independent signal).

### C2: Directional signal family matches hypothesis

**What.** The directional signal's indicator family must match the hypothesis per the table:
- `trend_continuation` → `trend`, `smart_money` (v19, D138 — `option_momentum`; retired from
  EMISSION at v33, D276 — 100% structurally dead in the funnel — the family admission stands)
- `mean_reversion` → `mean_reversion`, `dealer_positioning` (D062 — walls/gamma-flip as MR
  magnets); plus the per-id carve-out `momentum` (v31, D270 — below)
- `regime_arbitrage` → any family
- `relative_value` → `pairs`
- `volatility_event` → `iv_structure`, `flow`, or `dealer_positioning` (D062)
- `tail_hedge` → `macro`
- `event_momentum` → `post_event_drift` (v12, D109 — the directional is `sue`, the standardized
  earnings surprise driving the drift)

**Per-id carve-outs (v31, D270; `_C2_HYPOTHESIS_EXTRA_IDS`).** An indicator id listed for a
hypothesis passes C2 although its registry FAMILY is not in the table. One entry exists: the
parameterized `momentum` id under `mean_reversion` — the capitulation-bounce family (a trailing
3–10-day drop trigger `momentum < θ`, θ ∈ [−0.083, −0.041] log, in ELEVATED realized vol — buy the
panic print with a long call). The kernel's family is `trend`; the thesis is contrarian REVERSION
whose validated chassis is MR's time-stop exit schema (S5). Admitting the whole `trend` family would
flood MR with continuation directionals, so the carve-out is one id, and `momentum` is symmetrically
pin-excluded from `trend_continuation`'s directional pool (its `<`-side trigger under a continuation
thesis would be label-dishonest — exactly what C2 prevents) and from the cross-sectional rank path
(the rank combiner sorts DESCENDING; top-N by raw momentum is the inverse mechanism).
Operator-approved loosening, OPEN_PROPOSALS `e9d74318`.

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

### R1: Mean-reversion requires a reversion-regime gate

Lineage: v1 D013 → v11 D107 → v20 D150 → v22 D167 → v24 D254 → v28 D265 → v29 D266 → v35 D280
(each admission is one line below).

**What.** When `hypothesis == "mean_reversion"`, at least one `regime_filter` signal must reference
one of: `iv_rank` with `params.threshold ≤ 50`; `gamma_flip_distance_pct`; `hurst`; `rv_rank`;
`vol_regime`; `realized_vol`; `market_realized_vol`. The non-`iv_rank` members are accepted
**op-agnostically** — the predicate checks id presence and the sampler sets the side (the D107
"same gate, opposite side" convention). D013 collapsed the v1 second clause about
directional-family alignment (redundant given C2). Exempt: the capitulation `momentum` directional
(v35, D280 — the bare-drop arm; see S3).

**Why.** Mean-reversion makes money on premium that reverts; the gate forces "fire only in a
reversion-friendly regime." Per member — mechanism and admission:
- `iv_rank ≤ 50` (v1, D013) — fire only when premium is cheap enough for reversion to have room.
- `gamma_flip_distance_pct`, op `"<"` (v11, D107) — dealer LONG-gamma / dampening regime, the
  complement of R2's trend-side gamma gate; single-name confluence only (`space.rank_excluded_ids`).
- `hurst < 0.5` (v20, D150) — anti-persistence, the ranging signature; R2's indicator on the
  opposite side (C4 keeps it single-role); measured null-to-negative as an MR gate at D254, so the
  sampler biases away from it — it stays in the OR.
- `rv_rank < θ` (v22, D167) — cheap realized vol; the densest conditioner, dominant over hurst.
  (Q49: the "rank" kernels are min-max range positions, not statistical percentiles.)
- `vol_regime < 2` (v24, D254) — discrete Int8 vol tercile, RAW threshold only; the
  cross-sectional-MR champion in Crucible's WF+CPCV sweep.
- `realized_vol < θ`, θ ∈ [0.15, 0.30] annualized (v28, D265) — ABSOLUTE spike gate: binds in
  regime-WIDE spikes where percentile gates normalize; C1 makes it REPLACE the percentile gate in
  the vol-family slot, never both.
- `market_realized_vol < θ` (v29, D266) — the market-level variant (SPY-reference rv21); family
  `macro` BY DESIGN so it stacks with vol-family primaries and doubles as a veto-pool member.

**The elevated side (v31, D270).** The capitulation-bounce family deliberately emits `rv_rank > θ`,
θ ∈ [50, 80]: its thesis IS the (panic drop × elevated realized vol) pair — the corner the champion
MR family vetoes — which is what makes its supply structurally decorrelated. The gate is PINNED for
that directional (a calm gate ANDed onto a panic-print trigger would never co-fire), the calm-side
veto slot is skipped, and the pin composes with C1's chain guard (no `vol_target` sizer).

**The optional MR veto slot (v26 D263, v29 D266).** A `mean_reversion` config may carry ONE optional
second `regime_filter`: `ivol` (per-name CAPM-residual idiosyncratic vol, family `idiosyncratic_vol`,
`op: "<"`, percentile plateau [0.2, 0.4], window 63 — excludes the high-idio-vol "falling knives"
whose reversion fails) or `market_realized_vol` (family `macro`), one drawn per config, each eligible
iff no indicator of its own family is already present. Neither satisfies R1 on its own; `ivol` is
emitted only when the registry serves the id.

**Cost.** Medium. Excludes mean-reversion strategies that don't explicitly gate on one of the accepted ranging proxies (`iv_rank`, `gamma_flip_distance_pct`, `hurst`, `rv_rank`, `vol_regime`, `realized_vol`, `market_realized_vol`).

**Evidence to relax.** Promoted mean-reversion strategies that use a regime proxy outside the accepted set `{iv_rank, gamma_flip_distance_pct, hurst, rv_rank, vol_regime, realized_vol, market_realized_vol}` (e.g., `iv_zscore`, a custom realized-vs-implied ratio, or a new percentile-rank conditioner). (Fired twice: the v24/D254 `vol_regime` and the v28/D265 `realized_vol` admissions — Crucible's champion post-mortem as the outside-the-pool evidence.)

### R2: Trend strategies require a trend-regime gate

Lineage: v1 → v2 D077 → v11 D107 → v17 D131 → v27 D264 (v55 D366 retired the separate conditioner draw).

**What.** When `hypothesis == "trend_continuation"`, at least one `regime_filter` signal must reference indicator `adx`, `hurst`, `rv_rank`, `gamma_flip_distance_pct`, `market_state`, or `vix_term_slope`.

**Why.** Trend-continuation presumes a trend exists; firing range-bound is dead-weight risk.
Per member — mechanism and admission:
- `adx` (trend strength) and `hurst > 0.5` (persistence) — v1.
- `rv_rank < θ` (v2, D077) — cheap realized vol, the PTS thesis for trend long calls.
- `gamma_flip_distance_pct > θ` (v11, D107) — dealers SHORT gamma amplify moves (GEX literature);
  the complement of R1's MR-side gamma gate.
- `market_state > 0` (v17, D131 — first firing of the relax clause) — momentum pays after
  up-markets and inverts after down-markets (Cooper/Gutierrez/Hameed JF 2004); market-wide by
  design → coherent on trend's rank arm.
- `vix_term_slope > θ`, θ ∈ [0, 2] (v27, D264 — second firing, via OPEN_PROPOSALS `0a4d8da8`) —
  contango = calm; admitted on Crucible's campaign-grade probe (the first walk-forward-gate pass in
  program history, with `residual_momentum`), reversing the v17 exclusion; the tighter sampled range
  reflects their measured failure mode (stays in contango too long at bear onsets). The separate
  hurst×vix conditioner draw was retired at v55 (D366) after Q46 closed refuted; vix as a primary
  gate is unaffected.

**The optional volatility veto (v25, D258).** A `trend_continuation` config may carry ONE optional
second `regime_filter`: `days_since_jump` (family `volatility`, `op: "<"`, threshold on the 30–65
trading-day plateau) — vetoes "dead tape", names with no ≥5% move for N+ days, where the trend
champion's theta-bleed losses cluster. Because it is `volatility` family, C1 makes it mutually
exclusive with the level gates (`rv_rank` / `vol_regime`): a config picks the frequency veto OR a
level gate, never both. It does not satisfy R2 on its own and is emitted only when the registry
serves the id (dormant otherwise).

**Cost.** Medium. Excludes trend strategies without an explicit regime filter from the accepted set.

**Evidence to relax.** Promoted trend strategies that use a regime gate outside `{adx, hurst, rv_rank, gamma_flip_distance_pct, market_state, vix_term_slope}`. (Fired twice: the v17 `market_state` admission, and the v27 `vix_term_slope` admission — where the outside-the-pool evidence arrived as Crucible's campaign-grade probe rather than a post-promotion observation.)

### R3: Volatility-event strategies require event-proximity gate

Lineage: v1 (2 gates) → v2 D039 + M-9 (5, plus the ETF incompatibility) → v18 D135 (6: `pre_earnings_setup`).

**What.** When `hypothesis == "volatility_event"`, at least one `regime_filter` signal must reference one of the six event-proximity indicators: `days_to_earnings`, `days_to_fomc`, `days_to_cpi`, `days_to_nfp`, `days_to_opex`, `pre_earnings_setup` (all `calendar` family). **ETF exception:** ETF underlyings (`SPY`, `QQQ`, `IWM`, `DIA`) have no earnings, so `days_to_earnings` returns the sentinel/far value and never fires — the (ETF underlying, `days_to_earnings`) combination is rejected at validation time (T1.4/D039). `pre_earnings_setup` composes `days_to_earnings`, so it carries the same ETF rejection (D135). On ETFs the gate must use a macro-calendar indicator instead.

**Why.** Volatility-event strategies depend on a discrete event happening (earnings, FOMC, CPI,
NFP, OPEX) — firing far from any event means the setup hasn't materialized; the gate forces
declaring the anchor event. The macro-calendar members (D039 + M-9 threshold entries) make the
hypothesis usable on ETFs, which have no single-name earnings. `pre_earnings_setup` (v18, D135)
composes `days_to_earnings ∈ [enter, exit]` AND `rv_rank < q` — the pre-earnings IV-run-up
region — and was retired from EMISSION at v33 (D276: every pairing measured 91–100%
structurally dead) while this predicate still accepts it, so the submitted lineage stays valid.

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
