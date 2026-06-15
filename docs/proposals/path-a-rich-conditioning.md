# Path A — rich-conditioning sweep of long options (in-scope): light up the vega axis, joint-gate the entry, learn the conditioner

Status: **ACTIVE — operator-launched 2026-06-15.** The in-scope, active counterpart to the parked
Path-C dossier (`path-c-scope-expansion.md`). Where Path C *expands scope* (grammar v2, hard rule 9,
defined-risk multi-leg), Path A stays **entirely within v1's single-leg net-debit long-premium grammar**
and asks the question the exhaustion verdict skipped: *did we condition long options well, or did we declare
them exhausted over a crudely-conditioned population?*

> **One-line state:** the long-options exhaustion verdict ([[D152]]) was measured over an enumerated
> population that (a) could **not** condition on the vega / IV-cost axis — the canonical gate `iv_rank` is a
> **NaN-only stub**, which makes §3.5 R1 *"structurally unsatisfiable"* (`docs/INDICATOR_THRESHOLDS.md:131`)
> — (b) does **not compute theta / vega / delta** as conditionable features at all, and (c) conditions
> **marginally** (one regime gate per entry), never on the *joint* Greek state. Before accepting the failure
> we run the rich-conditioning sweep we skipped.

## 0. What is and is NOT reopened (read this first — honesty up top)

The exhaustion verdict has two separable claims. Only one is reopened.

- **The structural / sign claim — NOT reopened, still confirmed.** Long premium is net-negative *at source*
  (you pay the variance-risk-premium); every documented high-Sharpe option signal is a **short**-leg edge
  (Bakshi-Kapadia t=−4.39; Coval-Shumway crash-neutral straddle still −3%/wk). **Conditioning changes *when*
  and *how much* VRP you pay — it cannot flip the sign.** No amount of clever conditioning or ML turns a
  long-premium book into the seller's edge. The big adverse-regime magnitude (bear worst-quartile ~2.39×) is
  sell-side and structurally out of long-only reach. This half stands exactly as [[D152]] recorded it.
- **The search / magnitude claim — reopened.** "Max **gross** CPCV-p25 = 1.40 < 1.5" is a fact about a
  *crudely-conditioned* book, not yet about a *richly-conditioned* one. The population behind 1.40 never had
  a working vol-cost gate, never computed theta/vega, and never conjoined conditioners. So 1.40 bounds *our
  current grammar's expressiveness on the long side*, not the asset class. That is the gap this sweep closes.

**Calibrated EV — do not over-promise.** The realistic prize is **closing the thin 1.40 → 1.5 pocket in a
narrow conditional region**, not finding the 2.39× arm. Crucible's own literature prior is that IV
conditioners are **low-EV for long-only** (assessment "Inventory complete": `iv_term_slope` / `iv_minus_rv`
edges live on the L/S straddle's *short* leg). But that prior was formed (i) from index-level literature, not
from measuring *our* single-name net-debit book, and (ii) over a book whose vol-cost gate was **inert**. So
the sweep is worth running — cheaply, in-scope — rather than conceding on a prior. **Two clean outcomes, both
decision-useful:**
1. A thread finds a clearing conditional pocket → we got a **cheap, in-scope** arm; Path C stays parked longer.
2. All three come back negative → that is the **real** exhaustion, measured on a *properly-conditioned* book
   — a **stronger** verdict than [[D152]] — and Path C's parking is vindicated, not undermined.

This is **in-scope** (no hard-rule-9 touch — still single-leg net-debit long premium), **cheap and safe**
relative to Path C, and it *is* the operator's "exhaust long-options before v2 spreads" discipline
([[exhaust-long-options-before-v2-spreads]]) — done **richly** this time, not crudely.

## 1. The three threads (risk / cost-ordered)

### Thread 1 — light up the vega axis (IV-cost conditioning). Cheapest; needs **no grammar change**.

**The gap (grounded):** the operator's "long options cost most with volatility" axis is the one we condition
on least. The canonical "only buy when vol is cheap" gate, `iv_rank`, is a **NaN-only stub** in our registry
(`docs/INDICATOR_THRESHOLDS.md:83,87,123` — "skip in enumeration until Crucible ships real IV cache"). §3.5
R1 *mandates* `iv_rank` as the mean_reversion regime gate, so with it stubbed **R1 is structurally
unsatisfiable** (`:131`) — which is exactly why D107 (v11) added `gamma_flip_distance_pct` and D150 (v20)
added `hurst` as *alternative* R1 gates. Net: mean_reversion has been gating on **dealer-gamma and Hurst
persistence (regime *shape*)**, never on **vol-cheapness**. The IV conditioning that *is* live — `iv_minus_rv`
(v17, directional) and `iv_term_slope` (v18) — is recent, thin (`iv_minus_rv` was 2/600 in one snapshot), and
runs as a directional trigger, not a vol-cost gate.

**The plan:** Crucible ships a computable ATM-IV history (the data dependency) → `iv_rank` goes non-NaN →
§3.5 R1 becomes satisfiable → **re-enumerate mean_reversion with a real "buy-vol-cheap" gate** and
funnel-compare against the proxy-gated cohort. **No grammar change is needed** — `iv_rank` is *already* the
R1 canonical gate; it is merely inert. The re-enumeration *is* the test.

**First action:** `PROMPT_CRUCIBLE_IV_CACHE_DEPENDENCY.md` (drafted — ready for operator to relay).
**Gating:** Crucible data dependency (§1.2 — they compute the indicator). **EV:** Crucible's prior is
low-EV for long-only IV conditioners, but we have **never** measured our single-name net-debit book with the
vol-cost gate *live* — this makes that measurement possible for the first time.

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
