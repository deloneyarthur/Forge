# Path A — rich-conditioning sweep of long options (in-scope): light up the vega axis, joint-gate the entry, learn the conditioner

Status: **UN-HELD 2026-06-15 ([[D157]]) — D156's hold reversed; operator chose to RUN/measure the untried
levers. Thread 2 (joint/AND-gate) is now SCOPED for build in `conditioning-levers.md` ([[D159]]).** Arc:
launched ([[D153]]) → thread-1 premise falsified, walked back ([[D154]]) → "pursue the builds" → held
([[D156]]) → un-held ([[D157]]). **The §0 "is the probe worth the build?" question below is now ANSWERED
(run it) — read the threads as historical context; the actionable change surfaces live in
`conditioning-levers.md`.**

> **⏸ SCOPING OUTCOME ([[D156]]) — recorded so thread 2 isn't re-derived if revisited:**
> - **Warm-up (force `iv_rank` as mr's solo gate): DOMINATED.** Already answered NEGATIVE by production
>   evidence (D150: `iv_rank` "fires too sparsely to survive the prefilter"; Crucible: 0 mr-rank components).
>   Offline re-test is ungrounded (`forge enumerate`/`prefilter` use the demo registry + risk the
>   synthetic-cache noise fallback). Not built.
> - **Thread 2 — AND-gate form: a SAMPLER change, NO grammar bump.** §3.5 **C3 already permits 4 signals**
>   (1 directional + ≤3 supporting, AND-composed); the sampler only emits 2 (`sampler.py:519-534`). But each
>   AND-gate → more selective → fewer trades → fights the trade-count prefilters + CPCV (the warm-up's failure
>   mode). Likely dominated. Not built.
> - **Thread 2 — state-conditioned SELECTION: the only trade-count-neutral joint conditioning** (adapt
>   strike/DTE to vol state instead of gating entries out). Durable infra + the home for a learned conditioner,
>   but **cross-system** (`crucible_contracts.SelectorSpec` + Crucible backtester) — a Path-C-scale lift, low
>   long-options EV. **Deferred** to be designed once, around the operator's conditioner interface (the
>   thread-2 ↔ thread-3 seam).
> - **Thread 3 (learned conditioner): the operator's parallel workstream** ([[D155]] tail model;
>   `generation-model-levers.md`). Its (2.2) "conditioning = path-a threads 2-3, LOW-EV for long premium"
>   independently converges with this scoping.
>
> **Decision: held.** Neither residual form is a strong near-term long-options bet. The exhaustion verdict
> ([[D152]] + [[D154]]) stands reinforced; Path C stays parked by operator choice; the **M1/M2 monitor** is the
> only active long-options watch. Revisit thread 2 (state-conditioned selection) only when the learned
> conditioner's interface is defined, so it's designed once.

> **⚠ CORRECTION ([[D154]], `../Crucible/docs/handoffs/FORGE_iv_rank_already_live_coverage.md`).** This
> program was launched on the belief that the vega / IV-cost axis was **dark** — that `iv_rank` is a NaN stub
> making §3.5 R1 "structurally unsatisfiable." **That was wrong.** It came from a **stale 2026-05-14 doc**
> (`docs/INDICATOR_THRESHOLDS.md`, now corrected); the *code* has treated `iv_rank` as live since **D031
> (2026-05-15)**, and Crucible confirms it computes **non-NaN ~100%** single-name and was **used in 3,998 runs
> / 77 components**. So the vega axis was **live and used** during the "gross 1.40" population — and its
> **strongest near-miss is a vega-conditioned config** (`iv_rank × days_to_opex`, WF 1.43 / **CPCV-p25 0.70**)
> that **craters on CPCV.** That *reinforces* the exhaustion verdict on this axis, it does not reopen it.
> **Net effect on the three threads:** thread 1's premise is gone (→ a doc fix [done] + an optional *low-EV*
> mr experiment); threads 2 (joint conditioning) and 3 (learned conditioner) survive as **genuinely untried
> but low-EV** (they never depended on `iv_rank` being a stub — single-gate-per-entry is real). The verdict
> leans **back toward exhausted**; the residual decision is whether the low-EV joint/learned threads are worth
> the build. **Read §0–§1 with this correction in force.**

The in-scope counterpart to the parked Path-C dossier (`path-c-scope-expansion.md`). Where Path C *expands
scope* (grammar v2, hard rule 9, defined-risk multi-leg), Path A stays **entirely within v1's single-leg
net-debit long-premium grammar.**

> **One-line state (corrected):** the exhaustion verdict ([[D152]]) was measured over a population that
> conditioned on the vega/IV-cost axis **for vol_event** (`iv_rank` live, directional + gate) but **not for
> mean_reversion** (the sampler de-weights `iv_rank` 3:1 vs `gamma_flip`/`hurst` because it fires too sparsely
> — D150, a *current* reason, not the stale "stub" belief), does **not** compute theta/delta as conditioners
> (`iv_rank`/`iv_term_slope`/`iv_minus_rv` ARE live IV-cost features), lacks **skew/risk-reversal** (genuine
> gap, but a seller signal), and conditions **marginally** (one regime gate per entry — confirmed in code,
> `sampler.py`). The only un-swept territory is *joint* and *learned* conditioning — both low-EV given that the
> best single-gate vega config already craters on CPCV.

## 0. What is and is NOT reopened (read this first — honesty up top)

The exhaustion verdict has two separable claims. Only one is reopened.

- **The structural / sign claim — NOT reopened, still confirmed.** Long premium is net-negative *at source*
  (you pay the variance-risk-premium); every documented high-Sharpe option signal is a **short**-leg edge
  (Bakshi-Kapadia t=−4.39; Coval-Shumway crash-neutral straddle still −3%/wk). **Conditioning changes *when*
  and *how much* VRP you pay — it cannot flip the sign.** No amount of clever conditioning or ML turns a
  long-premium book into the seller's edge. The big adverse-regime magnitude (bear worst-quartile ~2.39×) is
  sell-side and structurally out of long-only reach. This half stands exactly as [[D152]] recorded it.
- **The search / magnitude claim — ~~reopened~~ → mostly intact ([[D154]] correction).** I originally argued
  "1.40 was measured over a population that never had a working vol-cost gate." **That is false:** `iv_rank`
  was live and `vol_event` used it; the strongest near-miss (`iv_rank × days_to_opex`) *is* vega-conditioned
  and craters on CPCV (0.70). So the vega axis does **not** reopen the search claim — it reinforces it. The
  *only* genuinely un-swept dimensions are **joint conditioning** (one regime gate per entry — real, confirmed
  in `sampler.py`) and a **learned market-aware conditioner** (none exists). Those remain technically untried,
  so the search claim is not *closed* — but the evidence now leans toward "exhausted," not away from it.

**Calibrated EV — now LOW, and honest about it.** The realistic prize was only ever **closing the thin
1.40 → 1.5 pocket**, never the 2.39× arm (sell-side, Path C). With the correction, even that is unlikely:
Crucible's literature prior already rates IV conditioners **low-EV for long-only**, and we now know the
*best* vega-conditioned config in the live book craters on CPCV. So the residual threads (2 joint, 3 learned)
are **low-EV bets on a thin pocket**, against evidence that the pocket isn't there. **Two clean outcomes:**
1. A thread finds a clearing conditional pocket → a **cheap, in-scope** arm; Path C stays parked longer. *(now
   judged unlikely.)*
2. They come back negative → the **real** exhaustion, on a properly-conditioned book — a **stronger** verdict
   than [[D152]] — and Path C's parking is vindicated. *(now judged the likely outcome.)*

**So the live question for the operator is no longer "run the sweep" but "is a low-EV joint/learned probe
worth the build cost, or do we accept the reinforced exhaustion and re-park?"** (See §0-decision at the end.)

This is **in-scope** (no hard-rule-9 touch — still single-leg net-debit long premium), **cheap and safe**
relative to Path C, and it *is* the operator's "exhaust long-options before v2 spreads" discipline
([[exhaust-long-options-before-v2-spreads]]) — done **richly** this time, not crudely.

## 1. The three threads (risk / cost-ordered)

### Thread 1 — ~~light up the vega axis~~ — **PREMISE FALSIFIED ([[D154]]); collapses to a doc fix + an optional low-EV experiment.**

**What I claimed (WRONG):** that `iv_rank` is a NaN stub → §3.5 R1 "structurally unsatisfiable" → the vega
axis is dark. **Reality:** `iv_rank` is **live since D031 (2026-05-15)** (Crucible v4 2026-06-10), non-NaN
~100% single-name, with a real spec (`regime_range=(10,50)`, R1 ≤ 50 honored — `indicator_thresholds.py:236`).
The "stub" came from a **stale 2026-05-14 doc** (now corrected). R1 is **satisfiable.** The vega axis was
**live and used** in the "gross 1.40" population — `vol_event` conditioned on `iv_rank` directionally *and* as
a gate (3,998 runs / 77 components), and the **strongest near-miss in the whole pool is `iv_rank × days_to_opex`
at WF 1.43 / CPCV-p25 0.70** — a vega-conditioned long config that **craters on CPCV.**

**The one current, non-stale nuance:** `mean_reversion` *specifically* rarely gates on `iv_rank` — not because
it's a stub, but because the sampler **de-weights it 3:1** vs `gamma_flip`/`hurst` (D150: `iv_rank` "fires too
sparsely to survive the prefilter"). It stays explorable (weight 1.0, never zeroed) and is correctly excluded
from the `cross_sectional_rank` path (D116). mr is the **weakest family** (0 mr-rank components; thin
single-name mr).

**What remains (small):** (i) **doc fix — DONE** (`docs/INDICATOR_THRESHOLDS.md` corrected; the root cause of
the error). (ii) **Optional, low-EV:** temporarily lift `iv_rank`'s mr R1 weight (override the D150 3:1
de-weighting) on the single-name path and re-enumerate, to measure mr-gated-on-vol-cheapness. Crucible agrees
it is "worth running — cheap, in-scope" **but low-EV** (mr is weakest; the de-weighting exists for a real
sparseness reason, so the cohort may just be prefilter-rejected; and the best `iv_rank` config — in vol_event —
already craters on CPCV). **Gating:** a sampler-weight change → enumeration change → operator-gated.
**No Crucible relay needed** (`PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` is ANSWERED/moot).

### Thread 2 — joint-gate the entry (in-scope grammar enrichment). Operator-gated.

**The gap (grounded):** a config cannot express the operator's "best set of {delta, theta, vega} for this
stock at this time." Delta and DTE are **fixed selector params** sampled uniformly inside a bucket band
(swing_short Δ 0.40–0.55 @ 14–21 DTE, etc.) — not conditioned on state. **Theta is never computed** — it is
implicit in the DTE band and is never a gate. And a config attaches **one** regime gate, so it cannot say
*"long call when Δ≈0.40 AND IV-rank<30 AND not-pre-earnings AND bear-regime."* (The one composed gate,
`pre_earnings_setup` = days_to_earnings ∧ rv_rank, is baked into Crucible's indicator, not Forge's grammar.)

**The plan:** (a) add **theta-burn and vega/IV-level proxies** to the conditionable feature set (theta from
DTE+IV; vega/IV-level from the thread-1 IV cache); (b) allow a **bounded conjunction** of conditioners on one
entry — e.g. ≤3 stacked gates (directional + vol-cost + regime). The existing prefilters already make this
safe: `PredictedActivations` (tier 5, directional ∩ regime ≥ 10) and `SignalCorrelation` (tier 7) prune the
dead and redundant intersections.

**Gating:** grammar change → operator + version bump + archive + D-entry (hard rule #1, rule #10).
**Honest cost:** single-gating is what collapsed the enumeration space ~10^15 → ~10^6 (DESIGN §3.6).
Reintroducing conjunction must be **bounded and prefilter-pruned** to stay tractable, and more gates = larger
effective N → Crucible's §8.7 DSR deflates harder (correct behavior, M4) — so the bar to clear *rises* with
conditioning richness. Thread 2 only pays off if a joint pocket has enough true IC to survive that deflation.

### Thread 3 — learn the conditioner (ML in-loop, **deterministic, non-LLM**). Research + operator-gated.

**Rule correction (operator, 2026-06-15):** hard rule #5 bans **LLMs** in the production loop, **not ML**. A
deterministic, non-LLM learned model is *allowed in-loop* — the ranker already is one (L2 logistic
regression). So the learned conditioner can be **in** the loop, not offline-only. (An earlier draft of this
analysis mis-stated #5 as "no ML in loop"; corrected here.)

**The gap (grounded):** "our other model" (the ranker) is **structure-only** — it predicts P(a config passes
Crucible's gate) from the config's *shape* (hypothesis, bucket, which signals it cites) and deliberately sees
**no market data**. It is a librarian ranking configs, not a trader picking entries. We have **no
market-aware learned bet-signal** anywhere.

**The plan:** train a deterministic learned model (logistic / gradient-boosted trees — **not** an LLM) on the
**joint market state** (IV rank, skew, term slope, regime, days-to-event, realized vol, the directional
trigger) against Crucible's **conditioned option-return labels**, to find the non-linear pockets where a
long call/put pays **net of cost** in bear/ranging. Register its output as an **indicator the grammar gates
on** (or crystallize the learned structure into deterministic threshold predicates). This is the "creative
experimental tooling" the operator asked about — done in-bounds.

**Compliance:** deterministic inference (rule #6 — frozen weights → byte-identical re-enumeration); seeded
training (rule #8 — `SeedHierarchy`, no naked RNG); non-LLM (rule #5); and the training **labels are
Crucible's conditioned-return data** (§1.2 — Forge computes no metrics, so this is a Crucible coordination).
**Gating:** needs Crucible's conditioned-return labels + operator go for the grammar/registry change.

## 2. Sequencing & gates

1. **Thread 1 first** — cheapest, no grammar change, just a Crucible data ask + re-enumeration. It also
   *supplies the IV features* threads 2 and 3 need, so it is the natural front of the line.
2. **Thread 2 next** — grammar enrichment for joint gates, built on thread 1's IV features.
3. **Thread 3 last** — richest; needs the conditioned-return labels and builds on the thread-2 feature work.

Nothing ships off this doc. Each thread is independently gated (Crucible data / operator grammar approval).
The **standing M1/M2 long-options monitor** runs in parallel regardless ([[D152]]).

## 3. Relationship to the parked Path C

This does **not** un-park Path C. It **reopens the exhaustion precondition** that satisfied Path-C's
provability gate: [[D152]]'s "Path-C provability gate SATISFIED" becomes **"satisfied pending the
rich-conditioning sweep."** Path-C resume is pushed out until this sweep returns negative (the off-ramp in
`path-c-scope-expansion.md` §3: "no in-scope lever clears → frontier capped" now requires *this* sweep, not
just the crude one, to come back empty). If a thread clears the pocket, Path C stays parked longer; if all
three fail, Path C's parking is vindicated on a stronger verdict.

## 4. Artifacts / cross-references

| Artifact | Role |
|---|---|
| `PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` | Thread-1 first action — **drafted, ready for operator to relay.** |
| `long-options-exhaustion-assessment.md` | The verdict this qualifies (search-claim reopened; structural-claim intact). |
| `path-c-scope-expansion.md` | The parked scope-expansion path this defers. |
| `regime-orthogonal-arms.md` | The full structural framing (Path A/B/C). |
| [[D152]] | Exhaustion CONFIRMED → now *qualified* by this sweep. [[D153]] records the reopening. |
| [[exhaust-long-options-before-v2-spreads]] | The directive this fulfills — richly. |

**Standing item (runs regardless):** the M1/M2 long-options monitor — re-ask Crucible to re-run the
gross-vs-net + vol-target checks as the decided-CPCV population grows ([[D152]]).
