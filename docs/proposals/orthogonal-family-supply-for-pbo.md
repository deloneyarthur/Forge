# Proposal / scoping: orthogonal-family supply to relieve the portfolio PBO wall

> **UPDATE (2026-07-01, D216) — BOTH LAYERS ADVANCED; target narrowed to vol_event.**
> - **Layer 2 is now BUILT (flag-OFF, byte-identical).** The interim lever shipped as the
>   `FORGE_ORTHOGONAL_FAMILY_FLOOR` env knob: `apply_orthogonal_family_floor` (`rejection_weights.py`) +
>   `_orthogonal_family_floors` parser + call-site wiring (`main.py`). OFF by default → enumeration unchanged
>   (invariant `tests/invariants/test_orthogonal_family_floor_invariants.py`). **Activation stays
>   operator-gated** (prereg + alpha-budget + later-cohort-confirm per below).
> - **Target NARROWED to `volatility_event` only.** This doc's Layer-2 also named `relative_value`; that is
>   now **REFUTED** (0.88-MR-collinear, [[D215]]). `volatility_event` is the SOLE Crucible-validated in-v1
>   orthogonal family (2026-06-29: PC1 load 0.10, book real CSCV PBO 0.107) — §3b's "honest prior: lower than
>   relval" was inverted by that result. §4.1's measure-first gate is RESOLVED in vol_event's favour.
> - **Layer 1 unblocking relayed.** Crucible shipped the contribution signal internally (D213 Ask-2,
>   `1926cbb`) but it is NOT in `crucible_contracts` — a contracts-export gap. `PROMPT_CRUCIBLE_MARGINAL_CONTRIBUTION_EXPORT.md`
>   (held) asks for a consumable export; that replaces the hand-set Layer-2 floor with the principled learned
>   estimand.
>
> **STATUS (2026-06-25):** SCOPING — analysis + grounded finding; **no code, grammar, or config
> changed**. Responds to Crucible's `FORGE_decorrelated_supply_for_portfolio_pbo.md` (2026-06-25).
> The Layer-2 interim lever is a versionless **feedback-change** (operator-gated per
> `docs/tasks/feedback-change.md`); Layer-1 is **Crucible-gated** (needs a portfolio-contribution
> signal); the Priority-3 gate-wiring is an **operator-gated grammar bump (v23)**. Nothing here ships
> off this doc. Author: Crucible-PBO-handoff response.

Relates to: `worst-quartile-complement-supply.md` (this **inverts its load-bearing 06-14 caveat**),
`regime-orthogonal-arms.md` (Path A timing-gate item; the magnitude-worldview caps), `t2-ranging-floor-and-supply.md`
(the `regime_supply` ranging floor now over-concentrating), `generation-model-levers.md` (the
`portfolio_contribution` reframe — **do not duplicate**), `PROMPT_CRUCIBLE_REFIT_PRIORITY_AND_WORSTQ_REGIME.md`
(the relayed refit-lane prioritization, already feeding this), [[D186]] (no return data at generation →
decorrelation owned at assembly), [[D193]] (the wf_p25 quality lane), [[D210]] (`relative_value` is healthy),
[[D144]]/[[D150]] (`regime_supply`), [[D103]]/[[D105]]/[[D067]] (learned hypothesis weights + exploration floor).

---

## 0. The headline — the wall moved, and it inverts a standing assumption

Crucible's 2026-06-25 handoff is the most consequential update to Forge's worldview in weeks:

- **The edge-MAGNITUDE wall is CLEARED — at *assembly*.** Assembled books now reach WF-median **2.88** /
  cpcv-p25 **1.79–1.95**, past the 2.0 / 1.5 bars no single config ever met. The single-config wall
  (0/9398 honest-era configs clear cpcv 1.5) is still real and unbroken — but Crucible's book-search now
  assembles decorrelated components *past* it. Forge's "currency is components, not single-config
  promotions" thesis paid off.
- **The new binding gate is PBO (selection overfitting): 0.578 > 0.4.** Every candidate book rejects on
  PBO alone. The diagnosis is a **dimensionality** problem: the honest pool is ~32 components but only
  **~7 are strong enough to select** (cpcv-p25 ≳ 1.3) — 3 `trend_continuation` + ~4 `mean_reversion` —
  and trend~MR are **~0.78 correlated as bulk factors**. Effective dimensionality ~1.5 → IS→OOS book
  ordering is essentially random → PBO ≈ 0.5+.

**This inverts the load-bearing caveat in `worst-quartile-complement-supply.md` (2026-06-14):** back then,
Crucible framed orthogonal/ranging supply as *"breadth hygiene, NOT a promotion unlock"* because the wall
was magnitude and mr's ~0.65 magnitude could not lift p25. **Now magnitude is cleared at assembly, so the
same decorrelated supply is aimed at the *actual* binding gate (PBO).** The honest-cap sections in both
`worst-quartile-complement-supply.md` and `regime-orthogonal-arms.md` ("none of this unlocks promotion")
were written under the magnitude worldview and must be re-read: the bar is no longer "does this leg clear
1.5" (handled at assembly) but "does this family add an orthogonal dimension the book can be built around."

---

## 1. The live finding — the monoculture moved from trend to mean_reversion

The handoff (reading the accumulated honest *pool*) describes a trend-heavy supply; the relayed
`REFIT_PRIORITY` draft (06-16) cited intake **trend 67.1% / vol 11.9% / mr 14.6%**. **Both are now stale.**
Six consecutive live daemon iterations (`forge.service` journal, 2026-06-25) show the opposite:

| family | learned `hypothesis_weights` | enumerated (`sampler_attempts`) | **submitted (`ranked_top_n`)** |
|---|---|---|---|
| `mean_reversion` | **1.000** (max) | ~1,900–2,070 | **162–175 / 200 (~85%)** |
| `trend_continuation` | 0.755 | ~1,370–1,510 | 15–23 (~8%) |
| `relative_value` | 0.426 (rising) | ~830–900 | **0** |
| `event_momentum` | 0.231 (rising) | ~470–570 | 0 |
| `volatility_event` | **0.074** (lowest active) | ~210–270 | ~10–15 |
| `regime_arbitrage` / `tail_hedge` | 0.091\* (prior, no data — D098/D066) | 0 | 0 |

`regime_supply:` confirms the ranker selects **~85% ranging complement** every iteration (171/200), pool
~1,000/1,500 ranging.

*Reading the activation (fable-audit strategy P0-2):* the `battery_survival_by_hypothesis` journal line
now prints the enumerated→survived drop per family each batch, so the floor's effect on *supplied*
vol_event (not just its sampling share, which floats with the oscillating max — see the D216 MANPAGE
entry) is visible directly — the battery admits only a small fraction of `volatility_event`, so a
sampling-share lift is only the first stage of getting more vol_event to Crucible.

**What this means:**
1. **"Throttle trend" is already done** — trend is ~8% of submissions, not 67%. The learned loop +
   Crucible's refit-lane prioritization over-corrected.
2. **The monoculture didn't disappear — it moved.** The stream is now ~85% `mean_reversion`, and mr is
   *half the 0.78-correlated directional core* PBO penalizes. Flooding mr deepens one of the two
   correlated drivers; it does **not** add the orthogonal dimension PBO needs.
3. **The two structurally-orthogonal families are suppressed, by two different mechanisms:**
   - **`volatility_event`** (vol-surface-driven, the most orthogonal in-v1 family — the in-v1 *seed* of
     the handoff's "third risk driver") is **starved by the learned weight** (0.074, lowest active, flat).
   - **`relative_value`** (pairs / cross-sectional, structurally non-directional, **healthy per [[D210]]**,
     the only pairs-diversity source) is **enumerated heavily (~870/batch) but zeroed by the ranker (0/200)**.

The lever for PBO is therefore **not** "more mr" (maxed, and it's the wrong axis) — it is **relieving the
suppression of the orthogonal families**.

---

## 2. The mechanism — there is no family dial; the *learned estimand* is the lever

A prior session assumed (and the held `REFIT_PRIORITY` draft asserted) that "our sampler can shift the
hypothesis mix without a grammar bump." That is **true but incomplete**, and the precise mechanism changes
the proposal:

- **The family mix is set by `hypothesis_weights`, drawn `rng.choices(samplable_hypotheses, weights=…)`**
  (`sampler.py:549-555`). There is **no settable dial, no constant, no persisted file.**
- **Those weights are *learned* every iteration from Crucible's per-hypothesis component-rate posteriors**
  (`compute_hypothesis_component_weights`, `rejection_weights.py:619-668`; loaded `main.py:511-605`;
  Beta-smoothed, normalized to max=1.0, [[D067]] 5% exploration floor applied after).
- **So the current mix is the learned *consequence of rewarding component-rate.*** Trend won historically;
  mr wins now (highest component-rate after the refit-lane fed it). `volatility_event` loses **because its
  standalone component-rate is low** — the estimand actively de-prioritizes the family that would most help
  dimensionality.

**The core diagnosis: the learned estimand (component-rate) is now misaligned with the moved gate
(PBO/dimensionality).** Component-rate rewards "more of what already clears as a component," which is exactly
the homogeneity PBO punishes. A high-component-rate trend/mr clone is worth *less* to the book than a
lower-rate but orthogonal `volatility_event` / `relative_value` leg — and the estimand cannot see that,
because **Forge has no return/correlation data at generation ([[D186]]): decorrelation is owned at assembly.**

Two suppression points, two gates:
1. **Enumeration:** `volatility_event` down-weighted by the component-rate estimand (feedback-change locus,
   `rejection_weights.py`).
2. **Selection:** `relative_value` (and `event_momentum`) zeroed by the ranker. Likely the `regime_supply`
   85%-ranging complement floor ([[D144]]/[[D150]], `t2-ranging-floor-and-supply.md`) — calibrated when
   *ranging* was "the" complement under the magnitude worldview — crowding the orthogonal families out of
   the ~15% residual, and/or a low learned quality/P(component) score. **Cause not yet instrumented (§4).**

---

## 3. The proposal (scoped, layered by gate)

### Layer 1 — the principled fix: re-aim the estimand at portfolio contribution [Crucible-gated]
Replace/augment the component-rate reward in `compute_hypothesis_component_weights` with a
**portfolio-contribution / marginal-PBO signal** so the learned loop rewards *dimensionality added to the
book*, not standalone component-rate. This is the anti-Goodhart-correct fix: it rewards what Crucible *now*
accepts (a low-PBO assembled book), not the stale proxy. **Forge cannot compute it ([[D186]])** — it needs
a Crucible signal. This **overlaps the in-flight `portfolio_contribution` objective-reframe relay**
(STATUS Tier-3 / `generation-model-levers.md`): **connect to it, do not duplicate.** Gated on Crucible
exposing the signal.

### Layer 2 — the interim in-v1 lever: a bounded structural-diversity adjustment [feedback-change, operator-gated]
Until Layer 1's signal exists, relieve the two suppressions with a **bounded, A/B-flagged** adjustment:
- **Un-starve `volatility_event`** — a structural floor / multiplicative tilt on the orthogonal families
  layered over the learned weights (the most orthogonal in-v1 driver should not be the lowest-weighted).
- **Un-crowd `relative_value`** — re-balance the `regime_supply` complement floor so the orthogonal,
  non-directional family is not zeroed out of the residual after the 85% ranging reservation.

**Discipline (per `docs/tasks/feedback-change.md`, non-negotiable):**
- **Cold-start byte-identical (rule #6):** flag OFF / empty adjustment → emitted sequence byte-identical;
  pinned by the golden sampler-sequence tests. (Family draw consumes `SeedHierarchy.rng("enumeration")`,
  so any non-trivial weight change *does* alter the sequence → property-baseline regen + the determinism test.)
- **Exploration floor preserved ([[D067]]):** nothing starved to zero; trend stays explorable (it is still
  3 of the 7 strong legs).
- **A/B flag, default OFF (D108 pattern):** revert = byte-identical.
- **Pre-register the prediction (`forge prereg`, [[D208]]):** "up-weighting `volatility_event` +
  `relative_value` widens the strong band / raises family dimensionality / lowers book PBO," and **confirm
  on a *later* time-cut cohort** (never the cohort that motivated it — §8.4). Revert if PBO does not improve.
- **Charge the alpha budget (`forge alpha-budget`, [[D207]]):** the tilt explores more of the
  vol_event/rv space → more effective trials; account for it.

### Priority-3 reframe — gate-wiring the vol-surface conditioners [operator-gated grammar bump, v23]
The handoff's "four live, unsampled timing gates" is a **registry-vs-grammar conflation** (see the
writeback). Only `iv_rank` is wired as a regime gate today (`mean_reversion`, R1); `iv_minus_rv` /
`iv_term_slope` are **directional-only** (`regime_range=None`); `vix_term_slope` was **deliberately rejected**
for trend conditioning ([[D131]], `grammar.yaml:281`). Wiring any of the latter three as gates is a §3.5
grammar change (version bump + archive + operator approval), **not** "nearly free."

**Fresh rationale worth noting:** Forge's own `regime-orthogonal-arms.md` already flagged "`iv_term_slope`
as a long-premium *timing gate* — Likely Forge-side, cheapest, do first" — but under the *magnitude*
worldview, where the deep-research verdict killed it (costs bind, single-leg magnitude unestablished).
Under the *dimensionality* worldview the rationale is different and un-refuted: gating shifts
`volatility_event`'s **return stream** off the price-momentum core, adding family dimensionality regardless
of single-leg magnitude. This may be worth a v23 reconsideration — but the term-structure gates
(`iv_term_slope`, `vix_term_slope`) are forward-IV signals that `GRAMMAR_REVIEW` files with **Path C Tier-2
calendars (v2)**, so the natural home is there, not as standalone single-leg gates. Operator's call; lower
priority than Layer 2.

---

## 3b. Second candidate in-v1 lever — cross-sectional `volatility_event` (operator-surfaced 2026-06-25)

Crucible's census (`FORGE_pbo_orthogonal_supply_answers.md`) put `volatility_event` out of v1 as
"reaches the band (1.514) but 100% single-name → cross-sectional vol_event refuted → v2." The operator
challenged the *single-name* premise — and the challenge holds:

- **vol_event is single-name by *our* choice, not by nature.** It is excluded from the
  `cross_sectional_rank` combiner by `search_space.py` `RANK_COMBINER_HYPOTHESES` (`{trend_continuation,
  mean_reversion, event_momentum}`), set by **D109 (v11→v12)** with the rationale *"vol_event already
  clears breadth via recurring events."* That is a **breadth-era** rationale — **stale under PBO**: a
  single-name strategy is excluded from the cross-sectional book *regardless of its breadth*. So the
  universe-scan expression the operator describes (rank names by the vol-surface signal, trade the
  cross-section) is **enumeration-policy-enableable** (add `volatility_event` to the frozenset; by the
  D109 precedent a `grammar_version` bump for cohort-stamping + determinism-goldens + deploy — **no §3.5
  rule, no gate change**), not blocked by the grammar's rules.
- **A directional vol-event edge exists** (single-name cpcv-p25 **1.514**, iv_minus_rv-driven, single-leg
  directional). Whether it **generalizes cross-sectionally** has **never been measured here** (0/757 — we
  never produced one). Crucible's "refuted" therefore can't be from Forge data; it is either Crucible's
  own probe or the **magnitude-vs-direction inference** ("vol_event predicts vol expansion, not direction
  → cross-sectionally direction washes out → straddle → v2"). That inference is economically sound but
  untested for the directional single-leg expression — the same "reasonable prior" the relval bug-era
  ceiling taught us to verify.

**Status: clarification relayed, build HELD.** `PROMPT_CRUCIBLE_XSECT_VOLEVENT_EVIDENCE.md` asks Crucible
whether the refutation is tested (show the probe / cpcv-p25 distribution) or inferred, and whether it
tested the *directional* form. **Honest prior: lower than relval** (relval reaches 0.867
cross-sectionally; the magnitude-vs-direction argument is real). If Crucible holds decisive data that
cross-sectional directional vol_event caps sub-band → concede to v2, no change. If it's an inference → a
relval-style test (reverse D109 + release a gated sample) is warranted. **Sequenced after** the relval
result + Crucible's answer — do not open two enumeration changes at once.

## 4. Measure-first (the gate before any build)

Per the [[D210]]/[[D206]] discipline — measure before acting, especially after a stale-framing surprise:

1. **Do `volatility_event` and `relative_value` top-tails reach the strong band (cpcv-p25 ≳ 1.3)?**
   If their distributions are capped below 1.3 (vol_event single legs pay the full VRP tide;
   `regime-orthogonal-arms.md` §Path-A says single-leg magnitude is cost-bound), then un-suppressing them
   adds *enumeration* diversity but **not strong-band dimensionality** — book-search still can't build a
   distinct third core, and the in-v1 lever is genuinely exhausted (→ v2/Path C). **This is the
   decision-relevant measurement; relayed to Crucible (writeback ask 1).** Forge cannot compute it (§1.2).
2. **Why does the ranker zero `relative_value`?** Instrument whether it is the `regime_supply` ranging-floor
   crowding it out of the residual (fixable, Layer 2) or a genuinely low learned quality/P(component) score
   (then submitting more is anti-Goodhart waste). One read of the ranker scores per family on a live batch.
3. **Is the learned loop still drifting?** `relative_value` (0.397→0.426) and `event_momentum`
   (0.215→0.231) weights are *rising* across the six iterations — the estimand is already nudging toward
   them. Confirm direction/rate before adding an override; if it self-corrects fast enough, Layer 2 may be
   unnecessary.

---

## 5. Honest ceiling (hard rule 6)

The in-v1 lever **narrows, it does not close**, and Crucible says as much:
- trend~MR's **0.78 correlation caps** how far re-balancing the directional families goes.
- `volatility_event` single legs likely hit the same **single-leg VRP magnitude wall** — they may never
  reach the strong band (§4.1), in which case un-suppressing them is bounded.
- The genuine fix — an **orthogonal vol-surface *risk driver*** (VRP / term-structure / dispersion) — mostly
  monetizes as multi-leg / short-vol structures → **v2 / Path C**, operator+Crucible-gated, and **there is
  no VRP indicator in the registry yet.**

**The 0.4 PBO gate stands (hard rule 3).** If orthogonal supply can't reach the strong band, "nothing
promotes" is the correct v1 outcome and portfolio promotion is a v2 question. This proposal pulls the one
in-scope, positive-EV, no-bar-change lever the analysis leaves standing — re-aiming our own selection so we
stop suppressing the families PBO needs — and measures honestly whether it's enough.

---

## 6. What this is NOT
Not a grammar edit, not a gate change, not a loosening of any §8.x bar (hard rules 3/4 intact). Layer 2 is a
versionless feedback/ranker re-aim (the [[D103]]/[[D105]] lineage), shipped — if approved — via the
feedback-change ritual + the D104 restart, A/B-flag-OFF-by-default. Layer 1 and the Priority-3 grammar bump
are separately gated and not proposed for direct ship here.
