# Proposal: v50 — `rank_k=5` bias, scoped to `trend_continuation` (Crucible-validated)
> **SHIPPED 2026-07-25 in v50 (D336) and REVERTED SAME-NIGHT at v51 (D337): the validating evidence was collider bias, true sign reversed. Banner added at the 2026-08-06 archive sweep.**

Status: **STAGED — awaiting the operator's deploy word.** Prereg `b13b0f893a11` is on
record (cohort cut 2026-07-25T00:53:56Z) BEFORE any code.
Date: 2026-07-24. Source: Forge's winner-prior salvage, **validated on Crucible's
ledger** (`CRUCIBLE_rank_k_validated_trend_only_and_risk_pct_is_a_breadth_knob_not_an_edge_2026-07-24.md`).
Relates to: [[D276]] (the resid structural-pin precedent this copies), [[D282]]/[[D288]]/
[[D291]] (the hand-prior pattern), [[D207]] (prereg), hard rule #4 (tightening — a draw
bias, not a grammar relaxation), D067 (exploration floor).

## Origin — the residue of a parked lever

The learned winner-neighborhood prior was **parked** on 2026-07-24: correctly measured on
the honest ARM its aggregate effect is p90 +0.0087, needing ~20,000/arm to resolve
(`v50-winner-neighborhood-priors.md` §8.0). What survived was Crucible's §6 ask — *record
which params carry the delta*. Two candidates were relayed for their validation. **One
came back real and large; one came back refuted.** This proposal is the real one.

For scale: the effect below is **~29× the entire corrected generation-prior effect**, in
one param, in one hypothesis. Two scoped hand-priors were worth more than the learned
prior — which is the D282/D288/D291 pattern reasserting itself.

## Evidence (Crucible's ledger, honest arm n=341; ours agreed in sign and direction)

`cross_sectional_rank` configs, `rank_k ∈ {5, 10}`:

| rank_k | n | med CPCV | p90 CPCV | med maxDD | maxDD gate pass | med WF |
|---:|---:|---:|---:|---:|---:|---:|
| **5** | 230 | **+0.3977** | +0.6906 | **0.1462** | 97.4% | 0.7522 |
| 10 | 111 | +0.1474 | +0.5122 | 0.1571 | 97.3% | **0.8880** |

`IC(rank_k, cpcv) = −0.268` on their ledger (ours: −0.167 — same sign, they measured it
larger).

**It is free.** Drawdown is flat-to-better at k=5 and the maxDD gate pass rate is
identical. That is the test separating a real effect from a risk trade, and it passes —
unlike `per_trade_risk_pct`, which failed exactly there (§"Rejected" below).

**Controls it survives:** all three sizer modes (IC −0.286 / −0.229 / −0.162); every
`per_trade_risk_pct` quartile (gaps +0.266 / +0.145 / +0.356 / +0.168);
`IC(rank_k, risk_pct) = −0.146`, so these are largely independent axes rather than one
finding counted twice.

**Survivorship runs in our favour.** Per D004 a `rank_k=20` child cannot resolve the
breadth floor on full history and never enters the honest set. If that pressure partially
reaches k=10, the surviving k=10 configs are the *luckier* ones — biasing the comparison
**against** k=5. The +0.25 is conservative.

### It is trend-ONLY — the scoping is the proposal

| hypothesis | n(5) | n(10) | med CPCV k=5 | med CPCV k=10 | gap |
|---|---:|---:|---:|---:|---:|
| **trend_continuation** | 210 | 84 | +0.4056 | +0.1325 | **+0.2731** |
| mean_reversion | 20 | 27 | +0.3237 | +0.3208 | **+0.0029** |

**In mean_reversion the effect is zero.** A global bias would help trend and do nothing
for MR — the larger converting family (~25% of the component pool) — while advertising
itself as a whole change. Scope it or don't ship it.

### The trade to carry knowingly: rank_k moves CPCV and WF in OPPOSITE directions

k=5 raises CPCV and *lowers* walk-forward (0.7522 vs 0.8880). Both are binding gates, so
this needed checking. On the AND-shaped joint `min(cpcv/1.5, wf/2.0)`:

| group | n | med joint | p90 joint |
|---|---:|---:|---:|
| **trend k=5** | 210 | **0.2252** | **0.4229** |
| trend k=10 | 84 | 0.0864 | 0.2830 |
| MR k=5 / k=10 | 20 / 27 | 0.1769 / 0.1854 | — |

**k=5 wins the joint ~2.6× on trend**, because CPCV is by far the more binding gate
(0.0% admit vs 0.7%). We are trading WF for CPCV and the trade is favourable *only*
because of which gate binds — if that ever changes, this bias should be revisited. It is
also a clean instance of the wf⊥cpcv result both sides now hold: one param, opposite
directions, so they are not one axis.

## The change

`_rank_combiner` gains the `hypothesis` (already in scope at its single call site,
`sampler.py:1356`) and, for `trend_continuation` only, draws `rank_k` weighted toward 5
instead of `rng.choice((5, 10))`:

- **Bias, not a pin — `_TREND_RANK_K5_SHARE = 0.75`.** k=10 stays explorable at 25%,
  copying D276's `_RESID_LONG_ONLY_SHARE = 0.75` precedent verbatim ("the arm stays
  explorable"). A hard pin would end evidence flow on an axis measured at n=84, and D067
  says never starve a value to zero.
- **`residual_momentum` is untouched** — it already has its own D276 pin
  (`_RESID_RANK_K_CHOICES`) and its own structural evidence; this must not silently
  override an operator-approved pin.
- **`mean_reversion` keeps the uniform draw** — the measured effect there is +0.0029.
- Every non-trend, non-resid rank draw is **byte-identical** (hard rule #6).

## Rejected on the same evidence: `per_trade_risk_pct`

Relayed as the second candidate; Crucible **refuted** it and we accept in full. It is not
a `vol_target` artifact (the confound we suspected — `IC = −0.009`) but a **breadth knob**:
`max_concurrent_risk_pct` is fixed at 0.15 on all 344 honest configs, so per-trade risk
sets how many positions fit under a fixed budget (implied max positions 22.4 → 8.2 across
quartiles). Its +0.06 CPCV is bought with median maxDD **more than doubling**
(0.093 → 0.197) and maxDD gate pass falling **100% → 92.9%**; it is non-monotonic
(Q1 > Q2, Q3); it sits at **92% of the inviolable hard-rule-1 2% ceiling** so there is
~8% travel even if it were real; and sizing is **construction — Crucible's side**
(D186/D187). **Dropped.** Recorded here because a rejected candidate with a diagnosed
mechanism is worth as much as the accepted one.

## Mechanics at build time (the deploy window, not now)

1. `sampler.py` — pass `hypothesis` into `_rank_combiner`; add `_TREND_RANK_K5_SHARE`
   with a D-entry comment citing this proposal and Crucible's validation.
2. `config/grammar.yaml` bump + `config/grammar_archive/` + Decision Log (hard rule #10 —
   an emission-population change is versioned).
3. **Goldens re-pin** — the rank draw shifts for trend xsect, so `test_sampler` goldens
   move. Emission proof: the trend-xsect k=5 share moves ~50% → ~75% over a cold
   enumeration, and non-trend/resid draws are byte-identical.
4. Deploy ritual (`docs/tasks/deploy.md`): stop → full uncontended suite → READ it →
   commit → restart → verify journal.
5. `funnel --compare v49 vNN --hypothesis trend_continuation`; resolve prereg
   `b13b0f893a11` on the post-cut honest cohort.

## Bundling note (operator decision)

The staged IWM+SLB rider (`v50-iwm-slb-dead-name-rider.md`, prereg `8eaa7e4aca93`) and
this change touch **disjoint populations**: since v47 made trend/MR xsect-only, the
name exclusion can only affect *single-name* draws (i.e. `volatility_event`), while this
bias only affects *trend xsect*. They therefore cannot confound each other in
`funnel --compare`, and bundling them into one bump is defensible and saves a deploy
cycle. Separate bumps remain the more conservative option.

**DECIDED 2026-07-24 (operator: "definitely bundle"): ONE bundled v50 bump** carrying this
bias + the IWM/SLB rider, on the disjoint-population argument above.
