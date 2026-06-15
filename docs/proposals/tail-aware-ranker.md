# Tail-Aware Ranking — Design Proposal (F-track successor)

**Status: §8 DECIDED 2026-06-13 (in-session AskUserQuestion — all six decisions, all
recommended options). T1 offline head BUILT (D140, 3 commits); the tail-score shadow-wiring
increment shipped INERT as D141 (`fc1e985`). T1 wiring +
T2 enforcement stay gated (decision-6 criterion + the pending F3 go). T3a ANSWERED 2026-06-13
(Crucible relay, §4 below): the assembled book's worst CPCV quartile is disproportionately
BEAR (2.39× regime_lift) and RANGING (1.33×) — the T2 complement is now a MEASURED target,
no longer a structural guess.**
**Origin:** the 2026-06-13 Phase-2 pool read (this session). Extends — does not replace —
`docs/proposals/learned-ranker.md` (F1/F2/F3), the D136 per-arm floor, and the D103
diversifier.
**Spec anchors:** §6.2 (composite score; the `prior_promotion_proximity` learning slot),
**§8.3** ("metric distributions … used to weight the ranker" — the sanction for this),
**§1.2** (Forge computes NO strategy metrics — the central design constraint), §1.3.
**Cross-system fact:** the promotion criterion is the full §8.7 battery at **portfolio**
scope (`../Crucible/docs/handoffs/FORGE_portfolio_promotion_wiring_status.md`).
**Decision-log home:** a `docs/DECISIONS.md` entry on approval; each shipped part its own D.

---

## 1. Problem — the ranker optimizes the abundant thing, not the binding thing

Verified against data this session:

1. **P(component) is no longer scarce — and it is *anti-correlated* with the goal.** Honest-era
   component rate is ~3.3% (in §1.3's band); the verified-coverage assembly pool is ~200–260
   components. F2 predicts P(component) — but components are abundant *and* the objective points
   the wrong way: per-family individual `cpcv_p25` median (06-13, v17–19 verified pool) is **mr
   0.74 > ve 0.61 > trend 0.505**, while component-rate is the inverse (trend 6.65%, ve 0.84%,
   mr 0.47%, rv/em 0). So a P(component)-max ranker floods the **least** tail-robust,
   fully-redundant sleeve (trend) and **starves** the most tail-robust regime-complement (mr).
   It isn't merely saturating an abundant quantity — it is pointed ~180° from the binding lever.

   > **CORRECTION ([[D155]], 2026-06-15 — measured on the live snapshot, split on `honest_regime_coverage_row`).**
   > "~180° / anti-correlated" is **too strong.** On VERIFIED-coverage rows P(component) is *weakly POSITIVE* vs
   > realized `cpcv_p25` (Spearman **+0.119**), not negative; `tail_score` reaches **+0.350** there (~3× better) —
   > so the tail head IS the right corrective, but the honest framing is "P(component) is a much weaker,
   > family-tilted predictor," not "180° wrong." The inversion is at the HYPOTHESIS level (P(component) favors
   > ve/trend, disfavors mr): on verified rows mr 0.669 > ve 0.544 > trend 0.415 holds, but on the UNVERIFIED
   > majority (~76% of decided-with-cpcv) the ordering COLLAPSES and tail ≈ P(component) (both +0.219). So T1's
   > value is real but **confined to the ~24% verified slice** and weak in magnitude (train R² ≈ 0.19). Full
   > audit + leakage/redundancy/stability checks: [[D155]].

2. **The binding constraint is downstream and tail-shaped.** Promotion = the full §8.7
   battery at **portfolio** scope. The assembled honest pool fails it on
   `cpcv_sharpe_p25` / worst-quartile (+ DD) OOS; WF-median ~holds. Pool read: individual
   `cpcv_p25` **median 0.53, max 1.15, 0/264 clear the 1.5 portfolio threshold**, and the
   pool is **64% trend / 61% market-wide / 5 (family,dte) cells**. The constraint is
   **dual** — (a) *quality*: no individually tail-strong raw material; (b) *diversity*:
   worst-quartiles co-move (avg corr 0.024 is low, but average corr misses tail
   co-movement).

So the ranker should steer toward **worst-quartile robustness**, the thing that gates
promotion — not P(component), an abundant quantity it already saturates.

## 2. The hard constraint: Forge computes no strategy metrics (§1.2)

Forge cannot run a portfolio backtest, so it **cannot directly optimize portfolio
`cpcv_p25`** — the true objective (a candidate's *marginal contribution* to the assembled
book's worst quartile) is Crucible-side. What Forge *can* use, without violating §1.2:

- **Per-component metric values already in `verdicts.gate_results`** — `cpcv_sharpe_p25.value`,
  `walk_forward_sharpe_median.value`, `regime_stress_p25_return.value` are present on every
  decided row (confirmed 06-13). Forge **consumes** Crucible's computed values; it computes
  nothing. §8.3 explicitly sanctions "metric distributions … used to weight the ranker."

This forces a three-part design: **(T1)** learn the per-component worst-quartile proxy
(unilateral), **(T2)** decorrelate tails structurally (unilateral heuristic), **(T3)** get
the *correct* signal from Crucible (coordinated, optional).

## 3. What this is NOT

- **Not a gate change** (#3) — ranking only; Crucible's gate is untouched.
- **Not a grammar change** (#1) — `grammar.yaml`/enumeration untouched.
- **Not an LLM, not stochastic** (#5) — same deterministic pure-Python solver family as F2.
- **Not Forge computing metrics** (§1.2) — it reads Crucible's already-computed gate values,
  the same way feedback reads gate outcomes today.
- **Not abandoning P(component)** — we still must submit configs that pass the gate *at all*.
  Tail-awareness is a *second* objective layered on top.

## 4. Design — three parts

### T1 — Retarget the learned signal to worst-quartile robustness (extends F1 + F2)

- **F1 dataset gains continuous targets** from `gate_results`: `cpcv_sharpe_p25.value`
  (primary), `walk_forward_sharpe_median.value`, `regime_stress_p25_return.value`. Same
  single-codepath discipline as features; skew-pinned.
- **New model head** predicting worst-quartile robustness. Two target forms (operator
  decision §8.1): (a) **regress** `cpcv_p25.value`; (b) **classify** `P(cpcv_p25 ≥ τ)`.
  Same pure-Python, zero-RNG, deterministic solver family as F2 (ridge / IRLS); same
  append-only JSON artifact with coefficients by feature name.
- **Training-row filter (§8.2):** `cpcv_p25` is trustworthy only on **verified-coverage**
  rows — `coverage_unverified` is the ad-hoc/CLI backtest path (degraded window). Verified-
  only is clean but component-heavy (~264); including verified *rejects* adds low-end range
  (rv sits at ~0.0–0.3). Decide: verified-only vs all-honest-era + a coverage-verified
  feature flag.
- **Shadow-first**, identical posture to F2: score in shadow, no behavior change. **New eval
  metrics** beside AUC: Spearman rank-corr of model score vs realized `cpcv_p25`, and
  **top-K mean `cpcv_p25`** (does ranking by the model surface more tail-robust configs than
  the incumbent / the P(component) model?).

### T2 — Regime-complement batch composition (extends D136 floor / D103 diversifier)

> **RETARGET 2026-06-14 (Crucible adjudication, operator-approved —
> `FORGE_greenlight_ranker_wiring_and_ranging.md` Decision 1):** the T2 floor targets **RANGING
> (`mean_reversion`) ONLY — bear is dropped.** Bear is not component-suppliable (a constant hedge is
> negative-carry / gate-exempt only for `tail_hedge`; `long_short`'s short leg is net-negative in
> bear, −0.057) → it's the Crucible `tail_leg` overlay, not a Forge reservation target. Reserving for
> "bear-paying" configs would reserve for something that cannot exist. **F3 (P(component)→ranking)
> wiring + this RANGING floor are GREENLIT** (criterion met, streak 4/4) — build with the Jaccard
> kill-switch + shadow-compare, ship the floor *with* the `mean_reversion` supply growth (Decision 2;
> else the floor caps trend but has ~5 ranging configs to reserve). So everywhere below reads
> "bear/ranging" → **ranging only**; "bear-paying supply growth" → handled Crucible-side.

Forge can't measure correlation, so it decorrelates tails **structurally**. The first sketch
proposed *symmetric* concentration caps (no family > X%, market-wide ≤ Y%, a floor on
(family,dte) cells). The 06-13 measurement says that is the wrong axis **and** the wrong shape:

- **Wrong axis — orthogonality lives in the regime a strategy BETS ON, not its family or
  underlying.** The trend bulk is one long-momentum factor spelled many ways: the 159 trend
  components span momentum_252 / returns_12m_skip1 / donchian / rolling_sharpe / macd —
  "diverse" by directional family yet tail-identical (all pay iff the market trends). A
  family-% or underlying-% cap passes them as diverse. Key the axis instead on the
  **regime-bet** = `(hypothesis × regime-gate indicator × op-direction)`. Worked example: trend
  `gamma_flip_distance_pct >` (short-gamma / move-amplifying) and mr `gamma_flip_distance_pct <`
  (long-gamma / dampening) are the **same indicator, opposite regime bet** (R1/R2, D107) — that
  pair is the orthogonality unit, not the family label.
- **Wrong shape — reserve the complement, don't just cap the dominant.** Per-family individual
  `cpcv_p25` median (06-13, verified pool) is **mr 0.74 > ve 0.61 > trend 0.505**, while
  component-rate is the inverse (trend 6.65%, ve 0.84%, mr 0.47%, rv/em 0). The P(component)
  feedback — and F2/F3 — therefore *starve* the regime-complement that the worst quartile most
  needs and that is itself the most tail-robust. A symmetric cap is far too weak against a ~14×
  rate gap; T2 must **actively reserve** batch slots for the complement, not merely throttle the
  leader.

**Mechanism (deterministic, D136-style) — a "regime-complement floor".** After ranking:
(1) identify the **target complement** = the regime-bet that pays in the regime where the book's
worst quartile actually lives. T3a now measures that regime (BEAR primarily, RANGING secondarily
— §4 T3a); until that label is a per-batch contract field it is a config constant from the relay,
with the structural fallback (complement of the dominant verified-coverage regime-bet cell,
recomputed per batch) when no measured label is available. (2) reserve up to **Z%** of the batch
for ranked survivors whose regime-bet pays in that target regime, drawn in score order. Same
insertion point, sorted-order determinism, and never-invents discipline as the per-arm floor —
it reshapes only among configs that already passed the gate-eligibility term.

**Two honest limits, both pointing past T2 alone:**
1. **Still a proxy — but the target regime is now measured.** Regime-bet is a *better*
   tail-decorrelation proxy than family/underlying, but it is structural, not a measured
   correlation — T3b (`portfolio_contribution`) validates (and can eventually replace) it. The old
   assumption "complement of the dominant regime-bet ≈ complement of the regime the book's p25
   fails in" is now **closed by T3a's measurement**: the book fails in BEAR/RANGING, which is *not*
   the naive complement of trend-long-momentum — so reserve toward bear/ranging-paying regime-bets
   directly, not toward "anything not-trend." Crucible's caveat carries into the design: target the
   **regime_lift** signal (bear 2.39×, ranging 1.33×), NOT the raw-dominant worst-quartile regime
   (low_vol, lift 1.00 — a base-rate artifact).
2. **Bounded by what enumerates.** T2 reshapes survivors — it cannot create the complement, and
   the complement families barely exist: `relative_value` 0/1651 (Crucible pairs runner ignores
   regime filters, D119; `pairs_zscore` ~stub, Q17), `event_momentum` 0/56 (unrankable,
   D115/D116), mr thin. So T2 is **necessary-not-sufficient** and is coupled to *growing* the
   complement (a producer / grammar / Crucible-handoff workstream outside this ranker proposal).
   Without that pairing, T2 only caps trend; it does not add orthogonality. Flag the coupling
   explicitly so T2 is never read as the whole fix. **T3a sharpens the growth target:** the
   measured complement is *bear/ranging-paying* supply — short-direction / long-gamma / defensive
   bets (bear) and mean-reversion / range / premium-capture bets (ranging) — which is exactly the
   thin-or-broken part of today's inventory (mr thin, rv 0/1651). The complement-growth workstream
   now has a measured direction, not just "grow not-trend."
   **Live-confirmed (D144, first `regime_supply:` line 07:33:28Z) — supply IS the bind, and the
   existing floors already work the selection side.** The reservable ceiling measured **88.7% trend
   / 1.8% ranging / 0% bear** (pool of 1,105), yet the submitted batch *over*-represents the
   complement (ranging 7.5% > pool 1.8%) because D103 `min_per_hypothesis` + D136 already pull ~15
   of the 20 available ranging configs in. A T2 enforcement floor therefore has **~5 configs of
   ranging headroom and *nil* for bear** — the selection-side gap is already near-closed by the
   existing floors; what is missing is *supply*. This strengthens "necessary-not-sufficient" toward
   **"largely redundant with D103/D136 on the selection side"**: the dominant lever is the
   complement-*growth* workstream, and the T2 enforcement floor (the gated next step) should be
   re-justified against it — possibly down-prioritized — before building.
3. **World-A magnitude cap — the complement is breadth/drawdown control, NOT a promotion unlock
   (Crucible design note, 2026-06-14, `../Crucible/docs/design_worst_quartile_regime_complement.md`).**
   Crucible's crater decomposition (`cpcv_crater_by_regime.json`) finds the CPCV-p25 wall is **edge
   MAGNITUDE, not a regime gap**: every family is positive in its best regime but **none means ≥1.5
   on any regime slice (best 1.10)**. A bear/ranging complement diversifies regime exposure and cuts
   the worst-quartile concentration + the failing `cpcv_max_drawdown_p75` (0.396) — real and worth
   doing — but it lifts the book's p25 only if the complement component is *itself* net-positive at
   promotion-grade magnitude in bear/ranging, which today's bear/ranging-active family (mr,
   best-regime ~0.62–0.65) is NOT. **So T1+T2 are tail/breadth hygiene; the promotion unlock is a
   higher-magnitude edge somewhere in the book — an expressivity / edge-discovery problem, not
   diversity.** Pitch the floor accordingly (hard rule 6): sold as a p25 unlock while the book still
   fails p25 (it will, until a higher-magnitude edge appears), it reads as a gate regression rather
   than the correct World-A outcome.
4. **Credit the regime GATE, not the hypothesis (corrects D144's `regime_supply` classifier).**
   Crucible §5.1: a component's complement payoff is set by its regime **gate + direction**, not its
   hypothesis label — a component gated `rv_rank < θ` (low-vol-only) or `hurst > θ` (trending-only)
   does **not** pay in bear/ranging *regardless of hypothesis* (it is gated out of them; the entire
   balanced frontier is trend·`cross_sectional_rank` gated exactly this way). D144's hypothesis-keyed
   tally therefore **over-counts** the complement. The authoritative credit is Crucible's
   reference-calendar JOIN (`worst_quartile_regime_mix` × SPY `reference_regime_calendar`, re-pullable
   per book in seconds), which Forge cannot compute (§1.2). Forge's structural tally is at best a
   coarse proxy — to be refined gate-aware and ultimately replaced by the Crucible credit riding T3b
   (`PromotedPortfolio`). See [[D146]].

### T3 — The correct signal from Crucible (coordination) — two-step, smallest first

Forge is blind to per-fold returns and to the regime identity of each CPCV fold, so T2 can only
*guess* which complement decorrelates the tail. Two asks, cheapest first:

- **T3a — "which regime is the worst quartile?" — ANSWERED 2026-06-13 (Crucible relay).**
  Taxonomy: the 6-regime §5.3.6 composite (bull · bear · low_vol · high_vol · trending · ranging),
  SPY market-wide reference. Result (era-C 342-component book; `probe_results/worst_quartile_regime_eraC.json`,
  Crucible-side): the worst CPCV quartile is disproportionately **BEAR (2.39× regime_lift)** and
  secondarily **RANGING (1.33×)**; every vol/trend/bull regime sits at-or-below base rate. **Use
  regime_lift, not the raw dominant** — the raw worst-quartile is low_vol (lift 1.00), a base-rate
  artifact, not a signal. The tail is a **directional-drawdown (bear) problem**, consistent with the
  maxDD −63% vol-targeting finding — not a calm-market or vol-clustering one. (Disjoint-block and
  convex-hull labelings agree, so the convex-hull blur didn't bite this book.) This converts T2's
  complement from a structural assumption ("not-the-dominant-cell") into a **measured** target
  ("regime-bets that pay in bear/ranging") — §1.2 clean, Forge consumes the label, computes nothing.
  Per-component labeling + `portfolio_contribution` ride the `PromotedPortfolio` contract (T3b),
  as scoped.
- **T3b — `portfolio_contribution` (the full signal).** Each candidate's marginal contribution
  to the assembled book's `cpcv_p25`, exported via `crucible_contracts`, lets T1 train on the
  **right** target instead of the individual-`cpcv_p25` proxy. Contract-ahead-of-need (parallels
  the `PromotedPortfolio` work).

Raise both as convergence points; do **not** block T1/T2 on either. **T3a is the cheaper, sooner
win** and directly converts T2 from heuristic to measured — sequence it ahead of T3b.

## 5. How it wires (relative to F3)

F3's pending wiring sets `prior_promotion_proximity := P(component)`. This proposal makes the
learning slot a **two-objective blend**: **P(component)** as the gate-pass eligibility term
(submit only things that clear the gate at all) × the **tail-aware score** as the preference
term among gate-passers; **T2** applied at batch composition (post-rank, like the floor).
Operator decides replace-vs-blend and weights (§8.3). Sequencing: **T1 shadows** under the
existing F2 machinery (zero behavior change) and earns wiring on its own criterion + the
still-pending F3 go; **T2** could ship earlier as pure coverage policy (the D136 precedent)
**iff** it only reshapes within ranked survivors and relaxes nothing — operator call.

## 6. Hard-rule & invariant compliance

| Rule | Posture |
|---|---|
| #1 grammar | Untouched — ranker policy + learned weighting only. |
| #2 contracts-only | Reads `verdicts.gate_results` (already populated via contracts). T3 would add a contracts field, never a Crucible-internal import. |
| #3 gate untouched | Ranks/orders; never rejects; the §8.7 gate is unchanged. |
| #4 no auto-loosening | T2 adds coverage/diversity; relaxes nothing. T1 is shadow until gated. |
| #5 no LLM / deterministic | Convex fit, zero-init, no RNG; T2 deterministic (sorted order). |
| #6 deterministic enumeration | Enumeration untouched; ranking already depends on learned state, cohort-keyed via `model_id`. |
| §1.2 no metric compute | Consumes Crucible's computed gate values; computes none. |

New invariants (RED-first): continuous-target round-trip skew-proof; verified-coverage row
filter pins out `coverage_unverified`; T1 shadow no-op (submitted set identical with/without
the tail model); T2 reshapes only within survivors (never invents); determinism (same
snapshot → byte-identical artifact).

## 7. Risks

- **Proxy gap (the central one):** individual `cpcv_p25` ≠ portfolio contribution; a set of
  individually-robust-but-correlated components can still assemble weak. Mitigation: T2
  (structural decorrelation) + T3 (the real signal).
- **Goodhart:** optimizing toward Crucible's `cpcv_p25` estimator. But `cpcv_p25` is *closer*
  to the true objective than P(component) is — net Goodhart **reduction** vs the status quo;
  shadow-first + regularization + coefficients-by-name auditing stand.
- **Small / biased training set:** verified-coverage rows are component-heavy and tiny-n;
  `coverage_unverified` `cpcv` values may be optimistic. Mitigation: §8.2 decision, strong λ,
  shadow-until-criterion.
- **Diversity heuristic over-suppresses** a genuinely strong concentrated batch. Mitigation:
  loose caps, shadow T2's effect on realized component/robustness mix before enforcing.
- **Closed-loop selection bias** — same as F3; the per-arm floor (D136, live) is the
  mitigation, plus T1's shadow baseline window.
- **T2 starves for lack of inventory (the coupling risk):** the regime-complement T2 should
  reserve barely enumerates today (rv/em ~0, mr thin) — T2 reshapes survivors, it cannot create
  them. A complement floor over an empty complement just under-fills the batch. Mitigation: pair
  T2 with a complement-growth workstream (unblock rv's regime eval / em ranking upstream; an
  enumeration or grammar lever to raise complement supply) — outside this proposal, but T2's
  value is contingent on it. Track complement *supply* (survivors available to reserve) as a T2
  shadow metric so under-fill is visible before enforcement — **BUILT + live (D144).** First
  reading (07:33:28Z): pool ceiling **1.8% ranging / 0% bear**, and D103/D136 already over-select
  it (submitted 7.5% > pool 1.8%) — so the under-fill is a *supply* problem, not a ranking one,
  and a T2 enforcement floor has minimal headroom over the existing floors.

## 8. Operator decisions — DECIDED 2026-06-13 (in-session AskUserQuestion; all recommended)

1. **Target form: REGRESS `cpcv_p25.value`** — continuous worst-quartile prediction, ranked
   directly; no arbitrary individual τ (the 1.5 bar is portfolio-scope). Winsorize/standardize
   for heavy tails.
2. **Training rows: ALL-honest-era + a coverage-verified feature flag** — full high/low range
   for a discriminating ranker; the flag lets the model discount the noisier
   `coverage_unverified` (CLI-path) cpcv values rather than dropping them.
3. **Wiring: BLEND** — `prior_promotion_proximity := P(component)` (gate-pass eligibility) ×
   tail score (preference among gate-passers). Blend weights set later; the slot weight stays
   0.10 until separately raised.
4. **T2: REGIME-COMPLEMENT FLOOR** — asymmetric reservation on the regime-bet axis
   `(hypothesis × regime-gate × op-direction)`, not symmetric family/underlying caps. Reserve
   fraction **Z** + dominant-regime lookback are build-time defaults; **ships as a shadow
   supply-metric first** — the §7 coupling risk stands: enforcement is contingent on complement
   supply, which barely enumerates today (rv/em ~0, mr thin). **Supply-metric BUILT (D144)** —
   `forge.ranking.regime_supply` + the per-batch `regime_supply:` journal line (shadow, daemon-inert).
   The enforcement floor stays gated — and the first live reading (§4 T2 / §7) now shows it has
   minimal headroom over D103/D136 (supply is the bind), so re-justify it against the
   complement-growth workstream before building, rather than treating it as the automatic next step.
5. **T3: T3a NOW (ANSWERED), T3b DEFERRED** — the worst-quartile-regime-label ask was relayed and
   **answered 2026-06-13**: the book fails in BEAR (2.39× lift) / RANGING (1.33×), so T2 reserves
   toward bear/ranging-paying regime-bets (measured, regime_lift-based — see §4 T3a). Hold
   `portfolio_contribution` (T3b) until T1 has shadowed; per-component labeling rides the
   `PromotedPortfolio` contract with it.
6. **T1 wiring criterion: MIRROR F3's STRUCTURE** — ≥3 consecutive checkpoints, each ≥150
   honest verdicts spanning ≥5 batches; the rank-corr / top-K-mean-`cpcv_p25` margin is fixed
   once the shadow distribution is visible (not guessed a priori).
   **OPERATIONALIZED 2026-06-14 (D147), with a correction:** the per-model ≥150 is *unreachable*
   (the daily timer rolls a fresh robustness model each run → per-model decided plateaus ~85/49).
   The §8.6 streak therefore **pools across the daily tail models** (`evaluate_tail_shadow_pooled`;
   valid because `tail_score` is a `cpcv_p25` prediction in the same units) and uses a PROVISIONAL
   `_TAIL_SPEARMAN_CRITERION=0.30` + a far-lower `MIN_FRESH_TAIL=50` (the verified-coverage+cpcv
   population is far sparser than the full verdict stream). The daily timer appends a fresh-window
   row to `robustness_streak.jsonl` recording the raw pooled spearman + n; the operator finalizes
   the margin from that log. Live: pooled n=144, spearman +0.456, PASS.

**Effect:** T1 (regress head on the F1/F2 machinery, all-honest+flag rows) and T2's shadow
supply-metric are greenlit to BUILD as shadow-only increments — zero behavior change, each its
own TDD pass + D-entry. **T2 enforcement and T1 wiring stay gated** (wiring on the decision-6
criterion plus the still-pending F3 go; enforcement on complement supply). **T3a is ANSWERED**
(§4 — bear/ranging measured); T1's offline head shipped (D140) and the tail-score shadow
persistence shipped inert (D141). No grammar/gate/loosening touched (§6). The headline change —
**rank toward worst-quartile robustness, the thing that actually gates promotion** — is the
producer-side answer to the binding constraint in [[promotion-gate-tiers-and-constraint]].
