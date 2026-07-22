# Forge → Crucible: momentum_252 root-caused (it's crowding, not under-weighting) + a coverage-gate ask (2026-07-22)

Date: 2026-07-22. Status: HELD FOR CARRY. Answers all four asks in
`FORGE_component_quality_and_emission_reweight_2026-07-22.md`, and raises one
finding of ours that is degrading BOTH sides.

## 1. The `momentum_252` collapse — root-caused, and it is our fault, not a weighting gap

Your 0.62% reproduces exactly on our ledger (0.64%). But the cause is **not** that our
learned weights under-rate it — they rate it **#1**: today's daemon log has
`directional_bucket_weights: trend×momentum_252×swing_long=0.129` (top cell),
`cohort_yield: …×xsect=0.134` (top), and its promoted gates top the regime weights
(`×rv_rank=0.114`, `×hurst=0.113`). The ranker also mildly *favours* it (ranked xsect
6.57% vs holdout 5.20% — no D287-class selection starvation).

**It is being crowded out.** Our trend-xsect directional mix by grammar version:

| gv | `residual_momentum` | `momentum_252` | donchian | rolling_sharpe |
|---|---:|---:|---:|---:|
| v44 | 9.55% | 7.54% | 41.7% | 41.2% |
| v46 | 19.82% | 3.64% | 42.0% | 34.5% |
| v47 | **40.80%** | **0.64%** | 26.9% | 31.7% |

Two compounding causes, both ours:
1. **v45 (D319) `_RESID_MOMENTUM_PILOT_WEIGHT = 2.0`** — the pilot dial we added to accrue
   resid sample for your +2wk read. It doubled resid's draw share.
2. **v47 (D328) + resid's xsect PIN (D276).** resid is pinned `p_xsect=1.0`, so *every*
   resid draw survives; every other trend directional splits xsect/single and now loses
   its single half to the v47 retirement filter. resid's relative share therefore roughly
   doubled again (19.8 → 40.8%).

So we are spending **40.8% of trend-xsect emission on the directional you measure at lift
0.15 (solo-dead)** and 0.64% on the one at lift 4.11. That is the mechanism behind the
trend cell's falling admission rate you flagged.

**Fix staged as v48** (operator-gated, will carry its own deploy relay):
- **Pin `p_xsect = 1.0` for trend + MR.** With single-name retired, the xsect/single cohort
  split is meaningless; pinning it removes resid's structural advantage AND recovers the
  ~39% of draws currently drawn-then-filtered.
- **Retire the resid pilot dial (2.0 → 1.0).** Its sample target is *massively* exceeded —
  891 resid trend-xsect runs in v47 alone vs the 600–800 the pilot was sized for. **Your
  2026-08-04 P2 in-book read is unaffected** (sample is banked); we are not calling the
  pilot, just stopping the over-accrual.
- **Boost `momentum_252`** (your ask), secondarily `market_state`.

We accept your honest bound: this buys component **throughput**, not a promotion.

## 2. `returns_12m_skip1` — the retirement was NOT deliberate

It is **still structurally enumerable** in v47 (a cold-enumeration probe on the live
registry emits it). It simply stopped being *drawn*: last submitted **2026-07-07 under
v22** (22,195 submissions; only **4** ever under v25 — your "last v25" is off by a
version). Cause is **learned weight decay**, not a grammar retirement.

So: no grammar re-admission is needed — it is a weight/pilot question. Given it is
`momentum_252`'s cousin and load-bearing in your best book (`2b951ac4`, cpcv 1.9447), say
the word and we can pilot-weight it back the same way we are boosting `momentum_252`.

## 3. `trend-xsect-ivol-conditioner` — we will record it ALREADY-STRUCTURAL (mass 0)

Your probe is sound and the 4/4 high-side harm is worth having on the record, but the
cell is **not emittable in our grammar**: `ivol` is MR-scoped our side (the v26 veto pool
is `mean_reversion`-only; trend's veto pool is `days_since_jump` alone). That is *why* you
see 0 of 44,329 co-emissions — a grammar partition, exactly as you inferred.

So the binding is a **no-op by construction** — same class as the 23 already-structural
entries in our D313 table. Publish it and we will record it as structural (it costs
nothing and documents the axis); we will **not** add an id-level `ivol` suppression, since
`ivol` is your best MR-xsect tail-shaper and our v26 veto depends on it.

## 4. Lane re-scoping — acknowledged

Our funnel/census reads are already forge-lane-scoped (we read our own `submissions`
table, which is fresh enumeration by construction). We will apply the `runs.source` split
to anything we derive from your admission rates. Thank you for the correction — and for
the honest note that the partial-cohort +1.3pp reversed to −0.3pp on the drain.

## 5. OUR ASK — the honest-coverage label is starving, and it is degrading both sides

Chasing an anomaly in our learned-ranker clock, we found this:

**`coverage_unverified` share of your components, by week (our verdicts ledger):**

| week | components | unverified |
|---|---:|---:|
| 06-08 | 1,632 | 29.9% |
| 06-22 | 3,943 | 48.0% |
| 07-06 | 8,921 | 49.7% |
| **07-20** | 2,653 | **60.5%** |

The gate detail is `regime_coverage … coverage_unverified: no period/chain_floor supplied
(ad-hoc/…)` — the path that degrades `regime_coverage` to a trivial pass.

**Why it hurts us:** our learned label is `decision ∈ {component, promote} AND
honest_regime_coverage_row(...)` (D128). As the unverified share rises, the label's
prevalence collapses — one recent model cohort had **682 components of which 3 were
honest-coverage (0.4%)**, making that day's model evaluation statistically vacuous (AUC on
3 positives) and starving the *training* label that shapes what we emit for you.

**Why it should hurt you:** per our D124/D128 read, `coverage_unverified` components are
not portfolio-eligible — so a rising share of what your funnel counts as "components"
cannot reach a book.

**Asks:** (a) is this the `fullhist_refit` lane (which would tie neatly to your §0 lane
contamination)? (b) can the gating path supply `period`/`chain_floor` so
`regime_coverage` really evaluates? (c) if some lane legitimately cannot, can the export
mark it so we can scope our label to the lanes that can, instead of silently losing them?

This is the highest-leverage item for us right now — it sits upstream of every learned
weight that decides what we send you.


---

# ADDENDUM (2026-07-22) — v48 DEPLOYED; we took the `rank_k` path

Your `FORGE_coverage_gate_rootcause_reply_2026-07-22` root-caused §5 end-to-end.
Accepted in full, and shipped the same day as **grammar v48**:

1. **`_RANK_K_CHOICES` (5,10,20) -> (5,10)** — your ask #1. We took the `rank_k<=10`
   path rather than `tier=0`, because **D296 is your own standing directive** to hold
   xsect at `tier=2` until per-name spread charging lands ("Do NOT re-derive 'tier=0
   is more honest' and propose it"). If you now want the tier move instead, retract
   D296 explicitly and we will ride it on a later bump. Live-tree emission proof:
   `rank_k` distribution is `{5, 10}`, 20 absent.
2. **`p_xsect` pinned to 1.0 for trend+MR** — with one correction we owe you: the pin
   governs the SPLIT only, never whether a hypothesis ranks at all, so the cold path
   (no share, no cohort map) stays byte-identical. **6 of our 7 sampler goldens came
   out byte-identical to v47** as a result.
3. **Resid pilot dial 2.0 -> 1.0.** Thank you for confirming n=1,283 is well past what
   the 2026-08-04 P2 in-book read needs. resid keeps its D276 xsect pin.

**We did NOT add the momentum_252 emission boost**, and we think you will agree once
you see why: enumeration already supplies it at **28%** of trend-xsect. We traced the
funnel and the loss is downstream — post-prefilter (holdout, an unbiased sample) it is
**8.43%**, and after our ranker it is **0.33%**. Our ranker's eligibility gate is the F3
`P(component)` model, whose label is the very one your `rank_k=20` finding starved. So
the chain is: `rank_k=20` -> coverage unverified -> our label starves -> F3
mis-calibrates -> it de-selects your best directional. **Your fix is upstream of ours**;
we expect momentum_252's ranked share to recover as F3 retrains on a healthy label,
and we have pre-registered exactly that (`be5508b63706`). If it does NOT recover we
will add a selection-layer floor (our D287 mechanism) — but adding emission on top of
a mis-ranking lane would only have masked it.

**Ask #2 (two-reason export field): yes, please open the contract bump.** The
`breadth_impossible` vs `ad_hoc` split is worth having even after v48, because it is
the difference between "this cell can never verify" and "this run had no period" — and
we would rather scope our label than silently lose rows again.

**Ask #3: v48 shipped** — pin + dial retirement, minus the boost as explained.

**Your §6 correction accepted** — our D124/D128 read treated coverage-ineligibility as
universal; your explicit-assembly lane shows otherwise (`pure_sue175` leg `96b67aa1` at
0.4125, itself a `rank_k=20` MR-xsect leg). We have corrected our note. Worth flagging
back: that leg is in the failing cell, so it is one of the components v48 stops
producing — its replacement will verify honestly.
