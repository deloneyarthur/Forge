# 01 — Scorecard: each learned system, its implementation, and what the live data says

Snapshot 2026-07-01 (HEAD `ceeefa4` + uncommitted D216). Line numbers verified at audit time;
re-grep before editing. Raw numbers + reproduction commands: `03-evidence.md`.

---

## §1. F3 verdict ranker — `P(component)` logistic prior. VERDICT: HEALTHY; one real defect (calibration).

**What/where.** Newton-IRLS logistic with L2, ~85–90 structural features, target =
"clears component gate ∧ honest coverage". Model: `src/forge/ranking/model.py:64,258`;
features via the single shared path `_standardize_design` (`model.py:220-255`; the logistic
drops only `coverage_verified` + targets, `model.py:52`). Wired into the §6.2 prior since D149;
journal prints `f3_ranker: P(component) prior ACTIVE` every iteration. Daily retrain via
`forge-ranker-eval.timer` → `scripts/daily_ranker_eval.sh`; artifacts content-addressed in
`~/forge_data/models/`; newest-wins loader.

**Live performance (07-01, strong).**
- Streak (`~/forge_data/ranker_eval/streak.jsonl`): **17 consecutive PASS**, latest AUC margin
  **+0.409** (model 0.862 vs incumbent-composite 0.454). Last 8 margins all ≥ +0.23.
- Per-model recompute on a fresh DB snapshot (`forge ranker-model eval`): every substantial
  model PASSes, margins +0.20…+0.52 (e.g. `a51c83c1` AUC 0.864 vs 0.451 at n=10,575). The one
  FAIL (`b7d260cb`, −0.171) is a degenerate window (n=483, 6 positives) — noise.

**Defect: miscalibration at high p, now load-bearing (B3).** Recent models over-predict badly
above p≈0.3: bin [0.3) predicts mean 0.341 vs realized 0.127; [0.4) 0.441 vs 0.099; [0.5)
0.542 vs 0.091 (~3–5× inflated). Older `c33e2875` was well-calibrated → this is a *drift*, not
a constant. It matters because P no longer only sorts:
- the live D193 blend **multiplies** P (a product is invariant only to affine transforms —
  miscalibration leaks into the ordering);
- gate-then-tail gates on an **absolute** P floor 0.02 (`src/forge/cli/main.py:2000`) against
  an enumerated-population median P of ~0.0004 (`docs/proposals/quality-lane-rewire.md`
  caveat 2) — calibration drift silently moves the effective keep-fraction, and nothing
  monitors the eligible fraction.
No Platt/isotonic step exists anywhere (grep clean); calibration is computed-and-printed only
(`src/forge/ranking/evaluation.py:70-86`, `src/forge/cli/ranker_model_cmd.py:249-253`); the F3
PASS criterion is AUC-margin + precision@K only (`ranker_model_cmd.py:229-241`).

---

## §2. wf_p25 quality lane — ridge + D193 blend. VERDICT: LIVE BUT A MEASURED NO-OP IN ITS LIVE FORM; skill still unproven.

**What/where.** Ridge (L2) on the SAME feature vector (ridge keeps `coverage_verified`,
`model.py:439`), target `target_wf_p25` (WF-Sharpe 25th-pct floor). Live form (since D193,
commit `df455e6`, flag `--quality-rank`): `prior := P(component) × sigmoid(ridge)` —
`tail_norm` sigmoid at `model.py:579`, production wiring `main.py:2015-2019`. Note
`model.py:609` still describes the sigmoid scale as **"provisional — tune from the shadow
distribution before the wiring flag is flipped"** — it was never tuned and has been live
since 06-20.

**The 06-26 A/B measured the live blend as a no-op** (`scratchpad/ab_quality_lane.py`,
`ab_rewire.py`, n=2,792; recorded in `docs/proposals/quality-lane-rewire.md:8-24` and the
`gate_tail_rank_score` docstring `model.py:631-635`):
- Spearman(P, P×tail_norm) = **0.971** — the product is dominated by P (tail_norm is squeezed
  into 0.27–0.85 by the untuned sigmoid);
- P itself is pooled **anti-correlated** with realized wf_p25 (IC −0.10); tail-alone is +0.06
  pooled / +0.31 on the then-live model;
- deployed-blend uplift vs P-alone: Δ +0.028, CI spans 0.
07-01 pooled recompute sharpens it: ranking by P surfaces top-K with realized wf_p25 **−0.865
vs population mean −0.694** — actively worse than average (see §3 for the gate-tail partial fix).

**Live skill still unproven.**
- §8.6 streak (`robustness_streak_wfp25.jsonl`): **FAIL 0/3**; 9 recent checkpoints all FAIL
  vs the 0.30 bar; last value +0.2986 (a hair under).
- Per-model IC (decision-grade recheck, 07-01 snapshot, `forge eval-robustness --gate
  wf_sharpe_p25`): the **decay-at-n pattern recurred a second time** — `6b89fa04` cleared the
  bar at +0.307 (n=98) on 06-26 and decayed to **+0.052 at n=1,350** by 07-01, exactly as
  `c66e56af` did before it (+0.403 @ n=58 on 06-21 → −0.003 @ n=488 on 06-26). Only the two
  newest models are near/above the bar (+0.280 n=857; +0.315 n=583) — the same early-model
  shape that has twice failed to survive data. Full table in `03-evidence.md` §2.
- The lane is operationally green (daily rotation, journal `quality_rank: wf_p25 BLEND
  ACTIVE`), i.e. live + not-harmful — but the "improving skill" pillar has now failed twice.

---

## §3. Gate-then-tail rewire (06-26, flag-OFF). VERDICT: THE RIGHT FIX (B4), NOT YET TRUSTWORTHY TO FLIP.

**What/where.** The two-part/hurdle form the June review's B4 recommended: P *gates*
eligibility, the ridge's native-scale prediction *orders* survivors. `gate_tail_rank_score`
(`model.py:622-637`; ineligible → 1e9 demotion constant near `model.py:619`), `gate_tail_prior`
(`model.py:653-662`). Production wiring behind `FORGE_QUALITY_RANK_MODE=gate-tail` +
`FORGE_REWIRE_P_FLOOR` (default 0.02) at `main.py:1988-2012`. Shipped over 4 commits 06-26:
`edb03e6` (shadow eval + `forge ranker-model eval-rewire`), `fdeed29` (daily rewire streak +
`forge status` clock), `92e9061` (production scorer, flag-OFF), `ceeefa4` (absolute floor 0.02
replacing the in-batch keep-frac quantile, which collapsed to ~0.0004 ≈ no-op on the skewed
production P distribution).

**Evidence for it (positive, early).** Offline A/B recent-window Δ **+0.180**, CI
[+0.060, +0.309] vs P-baseline. Shadow streak (`rewire_streak_wfp25.jsonl`): 1/3 — 06-30 FAIL
(Δ +0.007, but that record is a contaminated full-pool window since 06-10 marked
`qualifies: true`), 07-01 fresh-window **PASS Δ +0.333** (n=586, k=58). Pooled 07-01: top-548
gate-tail −0.803 vs P-baseline −0.865 (Δ +0.062) — a real improvement, though both remain
below the population mean −0.694 (gate-tail only *partially* cures §2's inversion).

**Why it can't be flipped on this evidence — four defects:**
1. **Shadow-vs-production fidelity gap (most important).** The shadow/streak ranks by
   `gate_tail_rank_score` — a **hard** gate (ineligible configs demoted by 1e9;
   `evaluation.py:351`). Production `gate_tail_prior` fills the **0.10-weight**
   `prior_promotion_proximity` slot of the composite (`src/forge/ranking/scorer.py:74-80`) — a
   **soft** gate: a below-floor config loses at most 0.10 of composite and can still outrank
   eligible configs on the other 0.90 hygiene weight. The streak therefore validates a
   *stronger intervention than the flag delivers*. Interacts directly with B2 (§5).
2. **The 0.02 floor sits on the uncalibrated P of §1** — no eligible-fraction monitor exists;
   calibration drift silently changes what the floor keeps.
3. **Unguarded env parse can crash the production loop**:
   `float(os.environ.get("FORGE_REWIRE_P_FLOOR", "0.02"))` at `main.py:2000` raises on a
   malformed value — inconsistent with the degrade-never-crash `_orthogonal_family_floors`
   parser in the same file (`main.py:511-544`).
4. **No test exercises the `FORGE_QUALITY_RANK_MODE` dispatch branch in `main.py`** (unit
   coverage exists for the pure functions only), and the whole 06-26 change has **no D-entry /
   no STATUS block** — invisible to the decision log.

**Live state:** NOT live. `systemctl --user cat forge.service` shows `--quality-rank` only, no
`Environment=` lines → mode=blend. Zero journal hits for gate-then-tail in 48h.

---

## §4. Yield map / hypothesis weights (component-rate estimand) + D216 floor. VERDICT: MISALIGNMENT CONFIRMED LIVE; THE BUILT FIX IS CORRECT BUT HAS 3 GAPS.

**What/where.** Per-cell Beta-smoothed component-rate posteriors re-weight sampling.
Reward: `_component_run_reward` = 1.0 iff component/promote ∧ honest coverage, else a
quality+ε tiebreak (`src/forge/feedback/rejection_weights.py:456-486`); sums joined from
Crucible's gated export against `submissions` (`:489-542`); posterior **mean**
`(α+r)/(α+β+n)` (`:578-581`) with Beta(1,50) (`:309-310`); normalized to max=1.0
(`compute_hypothesis_component_weights`, `:632-668`); D067 exploration floor 0.05
(`apply_exploration_floor`, `:1290-1322`). Cells: hyp / hyp×bucket / hyp×directional×bucket
(`main.py:752` via `_load_hypothesis_weights` `:546-640`), cohort D182 (`:1015`), regime-gate
D183 (`:1069`), underlying class/name D106 with empirical-Bayes shrinkage (`:584-616`).
Consumed by `rng.choices` in `src/forge/enumeration/sampler.py:549-555`; the rank branch is
gated by `space.rank_excluded_ids` + `RANK_COMBINER_HYPOTHESES`
(`src/forge/enumeration/search_space.py:111,142`; `sampler.py:694-704`).

**The misalignment, live (07-01).** The estimand rewards "more of what already clears" — the
homogeneity the PBO gate penalizes. Journal: `trend_continuation=1.000` all day, mr 0.16–0.19,
`volatility_event` mostly at **exactly 0.050 = the D067 floor**. Realized mix last 7d
(n=54,200): **mr 72.7% / trend 20.1% / vol_event 6.5%**; last 2d (n=22,000): mr 59.8% /
trend 32.8% — vs 81.4% mr on 06-29. The monoculture **oscillates trend↔mr** (the two halves of
the 0.78-corr core) while vol_event — the family in Crucible's first PBO-clearing book — is
floor-sustained with zero organic growth. Any one-day mix read misleads; measure over ≥1 week.

**D216 Layer-2 fix (uncommitted, flag-OFF): correct.** `apply_orthogonal_family_floor`
(`rejection_weights.py:1325-1361`): copy + `max(weights[f], floor)`; ignores families absent
from the map. Env parser `_orthogonal_family_floors` (`main.py:511-544`): unset/empty → `{}`;
malformed tokens and floors ∉ (0,1] silently dropped (never raises). Call site
(`main.py:1770-1778`) applies AFTER `_load_hypothesis_weights` → after normalization and after
the D067 floor. Ordering verified safe: max-only lift can't lower anything (D067 preserved);
`rng.choices` normalizes ratios internally (sum≠1 harmless); `{}` → block skipped (byte-identity
doubly guarded). 10 new tests (5 unit `tests/unit/test_feedback/test_rejection_weights.py:301-352`,
3 parser `tests/unit/test_cli/test_run_loop.py:302-333`, 2 invariants in
`tests/invariants/test_orthogonal_family_floor_invariants.py`).

**D216 gaps:**
1. **No integration test of the call-site splice** — nothing runs `_run_one_iteration` with the
   env set and asserts lifted weights reach the sampler / the journal line prints. The D185
   incident was exactly an inert call site that passed unit tests.
2. **Floor semantics are relative-to-max, not sampling share.** `volatility_event=0.20` means
   "≥20% of the *top family's* weight" → realized share was 2.9%→10.7% in the D216 experiment,
   and since the top family oscillates (§ above), the delivered share for a fixed env value
   drifts iteration-to-iteration. Docstrings never state the unit — an operator could read
   0.20 as 20% share.
3. The invariants test file is **untracked** (would be lost to `git clean` / lost on checkout),
   and duplicate family tokens in the env take last-wins silently (untested, trivial).

**Track A (the principled fix) is correctly blocked.** Re-aiming the estimand to marginal
portfolio contribution needs Crucible's `component_contributions` export
(`~/optbt_data/exports/component_contributions_<iso>.json`, schema v1) — shipped 07-01 but
**empty (n=0; populates only as books promote)** and with **no contracts loader** (rule #2 →
relay `PROMPT_CRUCIBLE_CONTRIB_LOADER_IN_CONTRACTS.md`, HELD at audit time). A soft healthcheck
line watches the export (`check_component_contributions_export`, uncommitted in
`healthcheck_cmd.py`). Do not build the re-aim until the loader lands AND the export has real
data — you cannot validate a flip against a null signal.

**Related dead code** (also flagged by the parent audit): `compute_hypothesis_weights`
(D067-era) and `compute_hypothesis_reward_weights` (+ `_sharpe_reward`/`_run_reward`,
D094/D101) have zero production callers but are still exported/maintained in
`rejection_weights.py`. Legacy Beta(1,10) constants at `:49-50`.

---

## §5. The composite sort — the structural constant nobody revisited (B2). VERDICT: 90% OF THE SORT IS MEASURABLY PROMOTION-BLIND.

`config/ranker.yaml:8` + `scorer.py:74-80`:
`score = 0.30·signal_density + 0.25·novelty + 0.20·regime_diversity + 0.15·permutation_test
+ 0.10·prior_promotion_proximity`. The learned prior (F3, or blend/gate-tail under the flags)
occupies only the 0.10 slot; the other 0.90 re-scores hygiene filters every candidate already
passed as hard gates. New since the June review: this is no longer just an argument — the
streak files *measure* the incumbent composite at **AUC 0.45–0.53** vs realized components
(coin flip) while the F3 model measures 0.80–0.86. Every improvement to the models in §§1–3 is
capped by this 0.10 lever arm, and it is why the §3 soft-gate flip may underperform its shadow.
No weight A/B has ever been run.

---

## §6. Promotion / MLOps discipline. VERDICT: TELEMETRY GOOD, GATES STILL AD-HOC.

- **Streak gates (B5 — open, pattern replicated).** §8.6 tail: absolute pooled
  `Spearman ≥ 0.30`, marked PROVISIONAL (`ranker_model_cmd.py:44`), pooled across daily models
  (`evaluation.py:213`). The new rewire streak inherits the same shape: absolute Δ ≥ 0.05, no
  pairing/significance (`ranker_model_cmd.py:52`), 3-consecutive convention (null
  false-promotion 12.5%; the D193 flip already overrode a 0/3 once). Its first record (06-30)
  is a contaminated full-pool window counted as a valid look.
- **Drift monitor (B6 — partial, D209).** `check_learning_drift`
  (`healthcheck_cmd.py:260-300`): CRITICAL at anti-predictive floors (F3 −0.05 / tail −0.10,
  `:254-257`), WARN on weak or a ≥0.15 drop vs trailing median-of-3. Outcome-IC only — no
  feature drift (PSI/JS), no label-shift check — and artifact adoption is blind newest-wins
  (the monitor alerts; nothing gates rotation).
- **Alpha budget / prereg (D207/D208 — good manual telemetry, nothing automatic).**
  `forge alpha-budget` (`src/forge/feedback/alpha_budget.py`,
  `cli/alpha_budget_cmd.py`) brackets honest trials (Σ batch_size floor / Σ enumerated_count
  ceiling) + Bailey-LdP E[max] hurdle; it prints the honest state: *"Crucible currently charges
  n_trials=1 (search_n_trials unset) → deflation 0.00"* (`alpha_budget_cmd.py:64`).
  `search_n_trials` is **never set** by the standard submitter (field exists only at
  `crucible_contracts/models.py:374`, hash-excluded) → B8 remains a Crucible coordination gap.
  `forge prereg` works; `confirm_promotion_claim` (post-cut anti-bias guard) has **no
  production callers**. Prereg `9b88966c446a` was resolved REFUTED with a *disclosed metric
  substitution* (resolved on Crucible's rank-IC probe, not the pre-registered census metric;
  operator accepted) — fine once, but the guard-rail should not make a habit of it.
- **Censored feedback (B7 — open).** No propensity weighting, no randomized exploration
  holdout anywhere in `src/forge` (grep clean). Mitigation is floors-only. Both heads and the
  estimand train exclusively on Forge-selected submissions.
- **Silent-degrade path:** `_load_hypothesis_weights` warn-once global
  (`_HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED`, `main.py:546-640`) — a mid-life export corruption
  degrades sampling to uniform silently after the first warning; not surfaced in healthcheck.
- **Ops nits:** daily model rotation has holes (06-16, 06-27→29 — one 06-30 pair spanned 4
  days, fresh_decided 22,486; timer/box downtime not investigated). `forge eval-robustness`
  prints "cpcv_p25" labels even under `--gate wf_sharpe_p25` (cosmetic).

---

## §7. June-review item status (B1–B13)

| Item | Status @ 07-01 | Evidence |
|---|---|---|
| B1 blend earns its keep? | **DONE — answer: NO** (offline A/B 06-26; blend ≈ P-alone, P anti-correlated with target) | §2; `quality-lane-rewire.md:8-24` |
| B2 revisit 0.10 prior weight | **NOT DONE** — now sharpened by live AUC 0.45–0.53 of the other 0.90 | §5 |
| B3 calibrate P, make it gate | **NOT DONE** — and now load-bearing twice (blend product + 0.02 floor); live 3–5× overprediction | §1 |
| B4 two-part/hurdle combination | **PARTIAL** — gate-then-tail built + production-wired, flag-OFF; live path still the blend | §3 |
| B5 significance-based streak gate | **NOT DONE** — pattern replicated in the new rewire streak | §6 |
| B6 drift monitoring | **PARTIAL** (D209) — outcome-IC only; adoption still blind newest-wins | §6 |
| B7 censored feedback | **NOT DONE** | §6 |
| B8 trial counting | **PARTIAL** — D207 ledger (telemetry); `search_n_trials` still never reported; deflation 0.00 | §6 |
| B9 Thompson/UCB allocation | **NOT DONE** — posterior mean only; Beta variance discarded | §4 |
| B10 diversity as objective | **NOT DONE** — floors + greedy-Jaccard only (D216 floor is still a floor) | §4 |
| B11 elite archive (MAP-Elites) | **NOT DONE** (correctly gated on B8) | §4 |
| B12 ceiling-vs-coverage telemetry | **NOT DONE** | §4 |
| B13 re-price the Path-C hold | **OBE/EVOLVED** — the PBO worldview shift (D212) + the 06-29 vol_event result superseded the framing; v2 currently NOT indicated (STATUS 06-29) | README §context |

---

## §8. Verified healthy — do NOT "fix"

- F3's model, features, and eval harness (beyond the §1 calibration defect).
- Determinism / train-serve parity (single featurize path, round-trip pinned), content-addressed
  artifacts, seeded RNG discipline.
- The shadow machinery is a genuine no-op (post-submission, fails safe to 0 rows) and every
  learned lane has a byte-identical revert (drop the flag).
- Decorrelation stays at assembly (D186/D187) — do not build per-recipe return-corr maps.
- D067 exploration floors (they are currently the only thing keeping vol_event alive).
- The wf_p25 *target choice* (downside floor percentile) — endorsed by the literature; the
  problem is the lane's blend form and unproven skill, not the target. Do not switch to wf_p10
  (fragile at the fold counts in play).
- `alpha-budget`/`prereg` mechanics — they work; they need *adoption*, not rework.
- Known-benign ops signals: "blocked: prev batch N% gated" (§7.3 limiter), `crucible-ingest-daily`
  "failed" (rfr-only).
