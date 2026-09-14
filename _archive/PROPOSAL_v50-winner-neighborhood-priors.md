# v50 Winner-Neighborhood Priors — a param-level generation prior seeded at honest gate-passers
> **Instruments retired 2026-08-06** (repo-simplification Step C; recoverable from git history): `winner_prior_signal_probe.py`, `winner_prior_shadow.py`, `winner_prior_stage_one.py`, `target_sweep.py`. The programme itself remains PARKED; `src/forge/ranking/winner_prior.py` removal is a separate operator-gated tranche (Step E1).

> **STATUS (2026-07-24): SCOPING / ready-to-prototype.** The one generation lever
> that needs no Crucible data and reuses the live sampler weighting framework, so
> it can be prototyped against the honest arm the moment the tail-target decision
> lands. Nothing ships off this doc without an operator-gated deploy + a
> pre-registered honest-arm read. This is the concrete, do-now implementation of
> the "generation model" (v50 lever 2); the assembly-complement axis
> (`../../../freeze/relays/FORGE_assembly_complement_axis_..._2026-07-24.md`) is
> its cell-level sibling and is gated on a Crucible book-map.

**Origin:** operator (2026-07-24) — "on top of the ranker and generation changes,
what else is a good target … we should leverage previous ones that have passed the
gates." Winner-neighborhood priors is the literal embodiment: *make the generator
search densely around the configs that already cleared, judged on the un-gameable
arm.*

**Relates-to:** `generation-model-levers.md` §2.1 (composition lever) / §4 (the
target lesson: optimize verified `cpcv_p25`, not gate-pass) / §6.1 (the held
"retarget the sampler toward verified cpcv-robustness" increment — this doc is that
increment, finally buildable) · [[decorrelation-at-assembly-not-generation]] ·
[[promotion-gate-tiers-and-constraint]] · [[ml-allowed-in-loop-not-llms]] ·
`../DESIGN.md` §1.2 / §3.5 / §6.2 / §8.3 · hard rules #1/#3/#4/#5/#6/#8.

---

## 0. Frame — automate the per-cell hand-tuning we already do

We have shipped param-neighborhood concentration **by hand, one cell at a time**,
every time Crucible measured a param that matters:

- **v36 (D282)** — trend swing_long `time_stop` n_bars → U[8,10]; MR swing_mid → the
  measured box (floor was actively harmful).
- **v38 (D288)** — trend swing_long optional-timer Bernoulli 0.5 → 0.15 (chandelier
  beats timer-carrying 39% vs 17% component rate).
- **v40 (D291)** — MR timer cell first-class: `required_from_set` biased to
  time_stop 0.65, n_bars → U[8,12] (timers 8-12 convert 15.0% vs default-5 at 5.3%).

Each of those was a Crucible relay → an operator gate → a scoped sampler constant.
The mechanism is always the same: **the param neighborhood of the configs that
convert is not uniform inside the cell, and concentrating the draw there raises the
component rate.** Winner-neighborhood priors **learns that neighborhood across every
cell at once**, from the configs that passed, instead of discovering it one relay at
a time.

The cell-level learned weights (`feedback/rejection_weights` → `sampler.py`:
hypothesis / bucket / regime-gate / underlying) already steer *which cell*
enumerates. **They do not touch the continuous/ordinal knobs inside a cell** —
`delta_target`, `dte_min/max`, exit `n_bars`, gate thresholds/quantiles, sizer
knobs. That intra-cell surface is exactly where v36/v38/v40 lived. Winner-
neighborhood priors is the learned prior over *that* surface.

## 1. What it steers (and what it must not)

**In scope — the intra-cell continuous/ordinal params**, drawn per-config in the
sampler today by uniform `sample_threshold_params` / `defaults` ranges:
`delta_target` (P3 band), entry `dte_min/max` (P2 window), exit `n_bars`, gate
threshold quantiles, sizer knobs. The prior reweights *where in the permitted range*
the draw lands, biasing toward the neighborhoods dense with gate-passers.

**Out of scope — anything that touches the gate or the grammar.** The permitted
ranges are §3.5-owned and unchanged; the prior only reshapes the draw density
*within* them (hard rule #1). No new params, no relaxed bounds (hard rule #4 —
strictly a concentration, i.e. a tightening-direction reshape).

## 2. The seed set — honest gate-passers, not screen-passers

This is the load-bearing design choice, and it is where the gaming trap
(`generation-model-levers.md` §4; Crucible's honest-arm proposal §2) is disarmed or
sprung.

**Seed on honest, floor-anchored passers only**, in descending strength:

1. **Promoted book legs** (trend `6bec53b4`, timer-MR `65316ca4`, + the earlier
   portfolio) — survived assembly + all 13 gates + promotion. The least gameable
   label we own.
2. **Honest-basis components** — `measurement_basis='fullhist_refit'` AND
   `decision='component'` AND honest coverage. These passed on the full-history,
   floor-anchored validator, not the 5yr screen.

**Explicitly NOT** standard_window screen-passers. Seeding on "what scored well on
our 5yr folds" is training on the validation set one layer up — it would breed
fold-overfit param neighborhoods that look good on the screen and are worth nothing
honest. §4's judge would catch it (no honest-arm lift), but seeding honest from the
start avoids burning a whole read on a knowably-contaminated prior.

n is small (hundreds of honest components, ~a handful of promoted legs). A prior fit
to a thin set will fit its noise (Crucible's proposal §6). Mitigations: (a) fit at
the **cell-pooled** level (share the param-neighborhood posterior across configs in
the same directional×regime×bucket cell — the unit v36/v38/v40 already scoped to),
not per-config; (b) a **Beta/Dirichlet-style prior with an exploration floor**, so
an unseen neighborhood keeps ~half a seen-good neighborhood's draw mass (the exact
`_*_EXPLORATION_FLOOR` pattern the sampler already uses on every learned axis).

## 3. Mechanism — a new weight source in the existing draw framework

No new machinery. The sampler already resolves every steered draw as
`rng.choices(pool, weights=[...])` with a prior-mean fallback and an exploration
floor, cold-path byte-identical when weights are absent (hard rule #6). Winner-
neighborhood priors adds one weight source on the intra-cell param axis:

- **Artifact, not live-computed.** Per `generation-model-levers.md` §3 rule #6 and
  the F3/robustness-model precedent, the prior is a **frozen artifact** rebuilt on
  the `forge-ranker-eval` daily timer from the honest slice, loaded at daemon
  startup, and its **id folded into `enumeration_inputs_hash`** (the
  `universe_fingerprint` / `earnings_coverage_fingerprint` pattern). This makes it
  reproducible: same `(grammar_version, registry_hash, seed, prior_artifact_id)` →
  byte-identical sequence.
- **Flag-gated, default OFF.** `FORGE_WINNER_PRIOR` (D108 pattern). Off → the param
  draws stay uniform `sample_threshold_params` → byte-identical to pre-v50 (hard
  rule #6, `test_sampler` goldens included). On → the weighted param draw activates.
- **Deterministic, classical.** A pooled empirical density / light gradient-boosted
  fit over `(cell, param) → honest-component-rate`. Never an LLM (hard rule #5;
  [[ml-allowed-in-loop-not-llms]]).

## 4. Target and judge — the honest arm on both sides

**Target CONFIRMED 2026-07-24: `cpcv_sharpe_p25`.** Settled by the exhaustive
14-candidate sweep (`scripts/target_sweep.py`, §4.2) and **endorsed by Crucible**
(`CRUCIBLE_wf_cpcv_reproduced_but_you_tested_the_enrichment_field_not_our_gate`).
One objective for the ranker's ordering AND this prior — no composite.

**Train on** the honest slice — `(cell, param-neighborhood) → honest outcome`, where
the outcome is honest `cpcv_sharpe_p25`, NOT gate-pass and NOT ranked CPCV. This is `generation-model-levers.md` §4 made
concrete: the target is the *verified* outcome, on the population selection never
touched.

**Judge on** `prefilter_sample`, pre-registered, identical in shape to the freeze
criterion and Crucible's generation yardstick:

> Does the winner-prior's `prefilter_sample` CPCV distribution shift up vs the
> current-grammar honest-arm baseline (median 0.351, p90 0.66, n=302), at n ≥ 300?

- **Ceiling, not centre** — the centre drifts on cell mix; the p90 is whether the
  grammar throws a promotion-grade extreme without the ranker's help.
- **Never judged on the ranked arm** — it improves mechanically as the pool
  improves; that is selection re-measuring itself (Crucible's proposal §3).

## 4.1 Premise probe — VALIDATED 2026-07-24

Before committing search budget, we ran the standing pre-build gate
(`scripts/winner_prior_signal_probe.py`) to answer: *does the training target carry
real signal, or would we be fitting noise?* Method — for each fat honest cell
(hypothesis × directional × regime × xsect × dte-bucket), fit `params →
cpcv_sharpe_p25` with 5-fold ridge, measure **out-of-sample rank-IC** vs a
40-permutation **shuffled-label null**, then **ablate the dte features** (which proxy
the bucket the sampler already steers) to isolate the *marginal* intra-cell signal.
Population: `measurement_basis='fullhist_refit'` (n≈4.9k, 12 cells).

| cell (mid bucket unless noted) | n | IC full | **IC no-dte (marginal)** | null95 |
|---|---:|---:|---:|---:|
| MR keltner_pct | 931 | 0.44 | **0.31** | 0.08 |
| MR rsi / rsi_14 | 727–808 | 0.40–0.46 | **0.22–0.26** | 0.07–0.08 |
| trend donchian | 658 | 0.55 | **0.32** | 0.08 |
| trend rolling_sharpe | 591 | 0.49 | **0.38** | 0.07 |
| trend residual_momentum | 481 | 0.26 | **0.26** | 0.09 |
| MR bb_pct | 163 | 0.30 | **0.22** | 0.15 |
| MR rsi_2 (short) | 83 | 0.01 | 0.09 | 0.19 (~null) |

**7 of 8 fat cells keep OOS param signal well above null after removing the bucket
proxies** — the target is real, out-of-sample, and *marginal* over everything the
sampler already steers (the cell-level weights never touch these knobs, so a
constant cell-mean predictor scores 0). **Green to build the prototype.**

Two bounds the probe does NOT lift (both are §6, restated so the green is not
over-read): (1) it measures within-cell *rank* of cpcv — max honest cpcv in these
cells is ~1.45, so concentration does **not** cross the 1.5 gate; this confirms the
*mechanism* is learnable, not that it breaks the magnitude wall. (2) it cannot
separate automatable signal from the v36/v38/v40 hand-tuned priors already baked into
these cells — only the honest-arm shadow-diff (§8, step 2) settles marginal value over
hand-tuning. Re-run this probe on the honest slice before each build cycle; if a
future grammar flattens these cells the IC collapses and the lever is done.

## 5. The box — what keeps it allowed

| Rule | Posture |
|---|---|
| #1 grammar | Reshapes draw density *inside* §3.5-permitted ranges; touches no bound. `grammar.yaml` unchanged (the ship is an enumeration-policy version bump, D098/v5 class). |
| #3 gate | Shapes generation only; never touches Crucible's §8.7 gate. |
| #4 no auto-loosen | A concentration (tightening-direction); relaxes nothing. |
| #5 no LLM | Frozen classical artifact (pooled density / GBM); never an LLM. |
| #6 determinism | Frozen artifact; id in `enumeration_inputs_hash`; flag-off byte-identical; property-tested. |
| #8 seeded RNG | `SeedHierarchy` only. |
| §1.2 no metric compute | Trains on Crucible's returned `gate_results`; Forge runs no backtests. |

## 6. The honest null — stated first

This must be able to end in: **the winner-prior moves the honest-arm distribution
not at all, and we conclude param-neighborhood concentration is exhausted — freeze
it.** The standing evidence points there: 0/302 honest configs clear 1.5 solo, the
ceiling has read edge-magnitude-bound across ~20 versions, and param tuning cannot
cross a structural wall. So the realistic best case is **not a solo-promotion
unlock** — it is a lift in the honest **component RATE** (more would-be-components
per batch → more stage-two yield → more assembly candidates), which is pool-quality
hygiene, exactly the World-A cap `generation-model-levers.md` §5 named. And it may
not even beat the hand-tuned v36/v38/v40 priors already in place — in which case the
result is "keep hand-tuning the few cells that matter, freeze the rest." All three
outcomes are first-class; the honest arm makes which one true **decidable**.

One specific tension to watch, honestly: `prefilter_sample` draws from prefilter
*rejects*. Concentrating draws near winners makes more configs *pass* the prefilter
(fewer rejects), so the honest arm measures whether the *residual* rejects improved.
It is entirely possible the prefilter already captures winner-adjacency and the
honest arm shows zero — that is the null, not a bug.

## 7. Determinism + governance

- **Artifact + fingerprint** — `winner_prior_*.json` under `models/`, built by the
  daily timer from the honest slice; id folded into `enumeration_inputs_hash`;
  loaded at startup only (activation at a restart boundary, journal-visible).
- **Prereg before the edit** — `forge prereg register`, predicting the honest-arm
  p90 shift direction/magnitude, resolved on the post-ship n≥300 cohort (the
  `44a4e08aef4f` rider pattern).
- **Goldens re-pin + emission proof** — flag-on changes the param sequence →
  `test_sampler` goldens re-pin; flag-off proven byte-identical over N seeds.
- **Funnel-attributed** — `funnel --compare v49 v50 --hypothesis <cell>`; ship its
  own operator-gated `grammar_version` bump + D-entry + STATUS block; deploy ritual
  per `docs/tasks/deploy.md`.

## 8. Sequencing

1. **Lead (already fed):** the tail-model target decision (cpcv/wf/both) on the
   republished `stage_two_outcomes`. Proceeds independently.
2. **This, prototyped in parallel:** build the artifact + shadow the resulting
   intra-cell param distribution against the honest slice *before* any enumeration
   change (the `generation-model-levers.md` §6.1 shadow-diff discipline). No deploy
   until the tail-target lands and the shadow shows a real, honest-slice-attributed
   shift.
3. ~~**Assembly-complement (its sibling)** stays gated on the Crucible book-map~~
   **NULLED 2026-07-24 — PARKED, do not build.** The book-map arrived same-day
   (`CRUCIBLE_book_map_delivered_the_uncovered_direction_exists_and_is_structurally_v1_blocked`)
   and returned that axis's stated null *with data*: the uncovered orthogonal
   direction **is** identifiable and it is `volatility_event` / `event_momentum`
   (median |corr| to book 0.03–0.07; 87–100% below 0.2) — and it converts at
   **0.3% / 0%** against 25.2% / 17.2% for MR / trend. Mechanism: vol-event P&L is
   ~90% direction, so harvesting it needs a direction-neutral structure (straddle),
   which v1 forbids. **No enumeration reweighting can reach it** — steering draws
   there would spend honest-arm throughput manufacturing rejects. So this doc's
   lever stands alone; there is no multi-objective merge to plan for.

## 8.0 ⚠️ VERDICT 2026-07-24 (evening): PARKED — the shadow number below was measured on the wrong population

**Read this before §8.1/§8.2, whose figures are superseded.** Crucible's power reply
(`CRUCIBLE_the_lift_is_real_but_your_post_ship_read_cannot_see_it_...`) flagged that our
baseline p90 0.797 matched their **all-arm-labelled** pool (76% `ranked`), not their
honest arm (0.672). They were right.

**The defect.** `load_observations` filtered on `measurement_basis='fullhist_refit'`
only — the honest **LANE** — with no `selection_mode` filter, so the judge ran on
n=5,324 rows that are ~94% ranker-selected. §4 of this doc says *judge on
`prefilter_sample`, never `ranked`*; §2 says *fit on the fullhist_refit lane*. Both
were called "the honest slice" and the judge silently inherited the lane.

**Re-derived on the honest arm** (n=344; median 0.3256 / p90 0.6712, matching Crucible
to the digit):

| read | d_median | d_p90 |
|---|---:|---:|
| ~~full lane (superseded)~~ | ~~+0.0290~~ | ~~+0.0455~~ |
| fit non-honest → judge unseen honest arm (fully OOS) | +0.0153 | **+0.0087** |
| fit honest arm → judge held-out honest arm (OOS) | +0.0026 | **+0.0019** |

Bootstrap 95% CI on the fully-OOS p90 delta: **[+0.0003, +0.0429]** — real, but barely
excluding zero and **~5× smaller** than claimed.

**Starvation ruled out** as the explanation for the honest-only near-zero: a fit on 172
honest rows still yields 98 entries at mean |tilt| 0.187, against 140 entries / 0.203
for the full-lane fit. The honest-only prior is not shrunk to neutrality — it fits real
tilts that simply do not generalize, which is evidence the full-lane tilts were partly
ranker-specific.

**Consequence: the A/B is not feasible.** Crucible sized it at ~765/arm to detect
+0.045. At the corrected +0.0087 the requirement is `(0.045/0.0087)² × 765 ≈ 20,000` per
arm — ~57 days at the current honest rate. There is nothing testable at our resolution.

**Prereg `916d79109b4d` resolved `refuted` (withdrawn-as-miscalibrated, never tested)** —
both for the population defect and for Crucible's independent finding that its +0.02
bound was cleared by noise ~22% of the time and sat 0.77σ from its own null, so neither
branch could fire. No replacement registered.

**This is §6's honest null arriving:** param-neighborhood concentration, as an aggregate
generation lever, is exhausted at our measurement resolution. The lever is **PARKED** —
not retuned. What survives is the residue in §8.3.

## 8.3 What survives: two param findings worth handing to Crucible as hand-prior candidates

Crucible's §6 ask — *record which params carry the delta, not just the aggregate* — is
the part with value left. Per-param rank-IC against honest cpcv, within-cell demeaned,
measured on the full lane for power and then **sign-checked on the honest arm alone**:

| param | full-lane IC (n) | honest-arm IC (n) | |
|---|---:|---:|---|
| `rank_k` | −0.071 (5,135) | **−0.167** (120) | **agree** — lower `rank_k` (5 over 10) |
| `per_trade_risk_pct` | +0.058 (5,300) | **+0.106** (278) | **agree** — higher risk pct |
| `regime_filter_threshold` | −0.063 (5,300) | −0.012 (278) | agree, but weak on honest |
| `directional_threshold` | +0.016 (5,300) | **−0.063** (278) | **SIGN FLIPS** |
| `exit_time_stop_n_bars` | −0.052 (2,005) | n/a (**0**) | no honest coverage at all |

The first two are candidate **hand-tuned priors** — the D282/D288/D291 pattern that
demonstrably works — and should be relayed to Crucible for validation rather than
shipped by us. `per_trade_risk_pct` needs their read specifically: "higher risk sizes
better" may be a `vol_target` leverage artifact rather than an edge.

`directional_threshold` is the cautionary one: 3rd-largest full-lane param, and its sign
**inverts** on the honest arm. A prior fit on the lane would have tilted it the wrong
way — the population defect in miniature, and the reason the sign-check column exists.

## 8.1 Prototype BUILT + shadow-diff (SUPERSEDED — see §8.0) — 2026-07-24

The artifact and the shadow gate exist and are committed. **Nothing is wired into the
sampler**; the shadow-diff was the gate and it reads positive.

- `src/forge/ranking/winner_prior.py` (`e298f67`) — frozen, content-addressed artifact
  on the `RobustnessModel` conventions. 15 tests pin the safety properties: bounded
  weights, exploration floor, Beta-shrinkage, hand-pinned-cell exemption, and
  `WinnerPrior.neutral()` returning exactly 1.0 everywhere so the flag-off path is
  byte-identical (hard rule #6).
- `scripts/winner_prior_shadow.py` (`d082b40`) — fits on the honest lane and reports
  the pre-registered judge.

**Shadow result** — config-level (draw weight = product over a config's params, since
the sampler draws them all), out-of-sample, fit on 50% of honest rows and read on the
held-out 50%, 5 splits:

| | uniform | prior-weighted | delta |
|---|---:|---:|---:|
| median | 0.351 | 0.380 | **+0.0290** |
| **p90 (the judge)** | 0.797 | 0.842 | **+0.0455** |
| effective sample size | — | — | **88.3%** |

Positive in every split. Invariant to `max_weight` from 2.0 to 20.0 — the bounds are
not what limits the effect, the fitted tilts simply never approach the cap.

**Two findings that changed the design:**

1. **A per-param MARGINAL read understates this ~10×** (+0.003 vs +0.029). Weighting one
   param at a time ignores that the sampler draws every param, so the marginal number
   is not the quantity the sampler realizes. The script now reports the config-level
   judge first and labels the marginal view as a diagnostic.
2. **The learned prior does not compete with the hand-tuned priors — it covers their
   complement.** On the timer axis the observed values are only {8..12}, i.e. D291's own
   `U[8,12]` pin, so that axis has no residual variance left to learn from and the
   fitted weights inside the window are mild (0.88–1.42), consistent with D291's
   "plateau" finding. The lift comes from the params **nobody has ever hand-tuned** —
   directional/regime thresholds, `delta_target`, `per_trade_risk_pct`, `rank_k`,
   percentile windows. This answers §9(c) in the opposite direction from the one
   anticipated: hand-pinned cells need exempting not because the prior would
   double-count them, but because their axes are already harvested.

**Honest bound, unchanged:** +0.0455 p90 is 3.96% of the 1.149 gap to the 1.5 gate.
Pool-quality / component-rate, not a promotion unlock.

## 8.2 Staging — its own bump, AFTER the IWM+SLB rider

Operator decision 2026-07-24: relay the shadow result for Crucible's read first, then
ship as a **separate** `grammar_version` bump behind the rider, so funnel attribution
stays clean (a dead-name prune and a generation-prior change in one bump would be
inseparable in `funnel --compare`).

- **Prereg `916d79109b4d`** is on record BEFORE any wiring code (D207), predicting an
  honest-arm p90 lift `>= 0.02` — half the shadow's OOS estimate — with the explicit
  null written in: no p90 movement retires the lever rather than retuning it.
- **Wiring, when it lands:** the prior becomes one more weight source on the intra-cell
  param draws, behind `FORGE_WINNER_PRIOR` (D108 pattern), default OFF. Flag-off must be
  proven byte-identical over N seeds (`test_sampler` goldens included) before the flag
  is ever flipped; the `prior_id` folds into `enumeration_inputs_hash` so same-seed
  reproduction stays honest (hard rule #6).
- **Order of operations:** IWM+SLB rider bump → verify → this bump → flip the flag →
  accrue an honest cohort at n≥300 → resolve `916d79109b4d`.

## 9. Open questions

- **(a)** Pooled empirical density vs a light GBM over `(cell, param) →
  honest-rate`? Start with the pooled density (interpretable, matches the v36/v38/v40
  hand-priors, trivially floor-able); escalate to a GBM only if the density leaves
  measurable honest-arm lift on the table.
- **(b)** Include the `winning_cohort` (1,000 sweep winners) in the seed set? They
  are sweep-selected on *our* metric, not honest — treat as **exploration seeds**
  (widen where to look) at the exploration floor, never as high-weight honest
  passers. Resolve when the seed-set n is known.
- **(c)** Does the prior interact with the D276 resid pin / D291 timer scoping (both
  already concentrate params in their cells)? The pooled fit must not double-count a
  hand-pinned cell — exempt the hand-scoped cells (the `experiment_cells` /
  campaign-pin exemption pattern) or seed the prior *from* them.
