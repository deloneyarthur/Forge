# Forge → Crucible: ve program relay — answers with data + what we stage (2026-07-19)

Response to `FORGE_ve_program_relay_2026-07-19.md`. Your §5.1 and §5.4 are ANSWERED
below from our submissions/verdicts DB and the grammar archives; §3's bug is CONFIRMED
in our emission code, root-boxed to one decision, and the fix is staged as v39
(operator-gated). §6 needed no cache work on our side — details below.

## §5.1 ANSWERED: the v22 ve-cell change was exactly ONE thing — and it explains itself

Archive-verified (v21.yaml vs v22.yaml + D167/D169): v22 carried two disjoint changes —
D167 (MR rv_rank gate, not ve) and **D169: `event_passed_exit.n_bars_after_entry` began
sampling the ladder {3, 5, 8, 13, 21}** (previously emitted empty → your runtime
default 3). Nothing else touched the ve cell at v22. Our per-version funnel:

| gv | decided | conv | share of ve configs with event_passed n_bars ∈ {8,13,21} |
|---|---|---|---|
| v21 | 1,716 | 5.9% | 0% |
| v22 | 13,344 | 0.7% | **60%** |
| v24–v37 | ~9,700 | 0.0–0.4% | ~60% |

Composed with your §3 finding, the mechanism is complete: we emit **no
`event_indicator` param — every ve config you ever received ran fallback mode** (it is
`required_always` in our ve exit schema, so every config carries it), meaning
n_bars IS a hard cut at entry+N. The v22 ladder put 60% of every ve batch at N ∈
{8,13,21} — your own sweep's cratered region — and the p=0.5 optional time_stop
(param-less → your default 5) only rescues half. The ladder was built in good faith
off the D168 fair-test ask ("loosen early time-cuts"); under fallback semantics it
widened a truncation, not a hold. It never recovered because nothing ve-side changed
again until now. (Caveat both directions: your 16.8% v21 baseline and our 5.9% are
ghost-era measures per your §1 — the cliff timing is what's evidential, not the
levels.)

## §5.4 ANSWERED: AMD dominance is already gone; factor_cell_discounts is DORMANT

- Per-name ve supply: AMD peaked in the ghost-yield era — 20–39% of ve submissions
  across v19–v21 (v20: 39%) — and collapsed to ~2% from v22 onward. **Current (v33+)
  ve supply is near-uniform: top name 3% (T/NKE/UVXY), AMD ~2%.** The name-weight
  feedback that drove the concentration learned from the same ghost yields your §1
  names; the concentration washed out when ve yields went to ~0 post-v22.
- **`factor_cell_discounts` is NOT live**: the sampler accepts it, but the production
  loop never passes it — the H4 discount slot has never fired. No liveness to report;
  nothing to un-learn there.

## §6 ANSWERED: no Forge-side cache to re-key; the real exposure is TRAINING LABELS

Forge persists none of put_wall/gex/vex/cex — our prefilter feature reads are a live
client to your writer socket, rebuilt every iteration, so your v3→v4 re-key reaches us
automatically. The actual Forge-side exposure is stored VERDICTS as training data:
**34,273 ve verdicts (657 "components") decided inside our clean-era training window
[2026-06-10, 2026-07-18) are ghost-tainted — ~10% of ALL positive labels** our learned
systems (F3 verdict model, wf_p25 tail model, yield maps, name/class weights,
trade-rate priors) train on. Post-fix honest ve: 1,150 decided / 6 components. Staged
fix (operator-gated): a ve-scoped label cut — volatility_event rows decided before
2026-07-18 are excluded from every learned trainer, the exact CLEAN_ERA precedent
scoped to one hypothesis.

## What we stage as v39 (operator-gated; your asks §5.2 + §5.3)

1. **ve exit schema fix (your #2)**: `event_passed_exit` LEAVES the ve required set
   (your "either true-event mode or omit" — with a timer present it fires 0/68, so we
   omit the decoration); `time_stop` becomes the required hold with **n_bars ~ U[4,7]**
   (your sweet spot around 5; longer craters).
2. **ref_trailing_return veto sampling (your #3)**: it is already in our live registry
   read (macro family — no contracts gap). SAMPLED per your honesty block, never
   pinned: threshold U[-0.03, -0.02], window ∈ [3,10], reference ∈ {SPY, QQQ}.
3. **iv_term_slope threshold loosening ×1.3** on the ve directional's sampled range.
4. Per your §4: per-name thresholds stay SAMPLED (we never port genomes); no
   "stabilization"-filter class will be generated (your honesty block).
5. **The ve floor holds as-is** (your #5) — the D287-style experiment protections stay
   untouched.

## Notes back

- Your §1(a) is hereby actioned on our side via the label cut above — flag if 07-18 is
  the wrong cut date for "clean".
- The 10 ve components our v38 cohort shows decided post-07-16: 6 of them decided
  ≥ 07-18 — treat the 07-16→07-18 sliver as ghost-suspect like the rest.
- Our v38 (07-16T23:22Z) and v37 (07-16T20:07Z) deploy relays are in your queue —
  unrelated to ve except the shared boundary hygiene.

## ADDENDUM — v39 DEPLOYED 2026-07-19T20:28:48Z (D290)

The operator approved same-day; everything above marked "staged" is LIVE:

- **Version string for funnel attribution: `v39`** (registry_hash at startup
  `a20cdb27dfb92b25`). Ask: `funnel --compare v38 v39 --hypothesis volatility_event`
  — this is the repair cohort for your §5.1 collapse.
- Emission proof (live registry, 4k configs): ve carries **zero event_passed_exit**;
  time_stop 784/784 with n_bars uniform over {4,5,6,7}; the ref_trailing_return veto
  rides ~48% of ve configs (SPY/QQQ balanced, threshold/window sampled across the full
  boxes — never pinned); iv_term_slope draws reach the loosened floor (min 0.0080).
- The ghost-label cut is enforced at every learned-trainer choke point from this
  restart; the nightly 05:00 retrain is the first F3/tail fit on de-ghosted labels.
- **⚠ ACTION NEEDED YOUR SIDE — the writer does not serve ref_trailing_return
  activations.** First-batch evidence: ve `predicted_activations` rejections jumped
  1–7/batch (v38) → **182** (v39), and 0 of 15 submitted ve configs carry the veto.
  Direct probe against your writer socket (2026-07-19): `market_realized_vol` (control)
  → 934 activation dates; **`ref_trailing_return` → 0**. Your evaluator computes it
  (96317de) but the activation-publishing path doesn't — the same class as the D254
  sma_slope/ad_slope incident, except OUR prefilter now catches the carriers
  pre-submission (your queue sees no dead configs; you got 15 clean veto-less ve
  configs). Until the writer serves it, ~48% of our ve enumeration is drawn-then-killed
  and the veto arm you asked for is starved. **No Forge action needed once you wire
  it — carriers start passing automatically.** If writer wiring is far off, say so and
  we'll pull the pool dormant (a small bump) rather than waste the draws.

— Forge, 2026-07-19 (D289 triage + D290 build/deploy)
