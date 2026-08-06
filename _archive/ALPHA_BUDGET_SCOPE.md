# Alpha-Budget / Effective-N Analysis — Scope for `scripts/alpha_budget.py`

**Status:** BUILT + FIRST RUN 2026-07-07 (late) — `scripts/alpha_budget.py`; results in §7
(which CORRECTS two §0/§2 claims, marked ⚠️ below). Read-only research analysis — no daemon
interaction, no grammar/production change, no D-entry until results drive an operator ask.
**Origin:** grammar-review Dim C prerequisite (`GRAMMAR_REVIEW_AND_EXPANSION.md`), promoted to
"run now" by the 2026-07-03 discovery in §0. Feeds the Path C re-pricing case
(`PROMPT_PROMOTION_STRATEGY_HANDOFF.md` §8).

---

## 0. What changed — verified in a forge.db snapshot taken 2026-07-08T02:10Z

All facts below were verified directly against the snapshot (233,232 `verdicts` rows,
2026-05-28 → 2026-07-08); nothing here is inferred from docs.

1. **The `verdicts` table retains full per-run gate VALUES for the whole campaign.** Every row
   carries `gate_results` JSON with `passed/value/threshold/detail` for: `cpcv_sharpe_p25`,
   `walk_forward_sharpe_median`, `deflated_sharpe`, `pbo`, `sharpe_baseline`,
   `regime_coverage`, `regime_stress_p25_return`, `min_oos_trade_count`,
   `max_drawdown_ceiling`, `profit_factor`, `ablation_arm`. `cpcv_sharpe_p25.value` is non-null
   on 233,232/233,232 rows. **The analysis needs NO new accumulation and NO Crucible data pull.**

2. **Transient promotes (2026-07-01 → 07-03).** Three `decision='promote'` rows exist for TWO
   configs (both `mean_reversion` × `swing_mid`, single-name, v22):
   - `7d07c259297e99de` — honest WF 3.088 / cpcv-p25 1.965, 615 trades, promoted 07-01T02:35Z.
   - `3d6ed2afbfe4837e` — honest WF 2.497 / cpcv-p25 2.988, 403 trades, promoted 07-02T02:37Z
     (plus a refit-child promote row 07-03T01:17Z, `trade_count=0`, identical metric values).
   Both were **re-gated 2026-07-03T06:15/06:17Z with DSR deflated by `n_trials=46131`**
   ("max of Forge search_n_trials and the measured selection multiplicity" per the gate detail)
   → DSR collapsed 0.9955/0.9995 → **0.0118 / 0.0726** → REJECT. `promoted_patterns` = 0 rows;
   `component_contributions_*.json` exports publish `"contributions": {}` on a ~2-min cadence
   (since ~2026-07-08T00:54Z). **"Zero standing promotions" remains true.**

3. **The charged DSR is NOT the standing gate.** It was applied to exactly those 2 re-gate rows
   and never again — 0 of 25,997 rows decided after 07-05 are charged; all carry
   `n_trials=1` ("Multiple-comparison deflation across sweep trials lands in Step 4").
   Crucible's Step 4 exists in code and fired once, reactively.

4. ⚠️ **CORRECTED BY THE BUILD RUN (§7): "noise-creep to 2.99" was a basis conflation.**
   Every honest value ≥ 1.5 (2.99 / 2.17 / 1.97 / 1.87) is a **fullhist-refit
   re-measurement** — a post-selection re-gate of an already-interesting config on a LONGER
   window (e.g. 3101d vs the standard ~1825d; 3d6ed's standard-window cpcv was **0.125**, its
   refit 2.99). On the single standard-window basis the honest max is **1.343** — i.e. the
   handoff §3.4 "flat ~1.40 wall" was CORRECT. Refit rows must be paneled separately, never
   pooled into max statistics.

⚠️ Also corrected: raw honest ROW counts (23,954) pool re-gates; the deduped
standard-window honest cohort is **10,004 configs** (98.6% trend_continuation — the
verified-coverage lane is essentially the cross-sectional trend path; ve=100, mr=29).

## 1. Questions the script answers

- **Q1 — retrospective null (the verdict matrix):** Is the observed honest max cpcv-p25
  consistent with a zero-edge search of the campaign's effective size? Answered per cell of an
  N_eff bracket (§3-B) × null-center variant, as exceedance probabilities.
- **Q2 — creep diagnostic:** Does the running honest max track the noise envelope
  σ·√(2·ln N(t)) as N accumulates (noise signature), or plateau below it (ceiling signature)?
- **Q3 — the de-facto standalone bar (DSR inversion):** What Sharpe must a single config show
  to keep DSR ≥ 0.95 when charged with campaign-level n_trials (46,131 today; project growth)?
  **This is the number the Path C re-pricing needs** — it quantifies what "standalone
  promotable" actually requires once multiplicity is honestly charged.
- **Q4 — prereg emitter:** Emit the pre-registered v24+burst-cohort prediction (§3-F) so the
  incoming data becomes an out-of-sample check instead of an accumulation excuse.

## 2. Data sources + exact predicates (all verified against the snapshot)

- **Snapshot:** `cp ~/forge_data/forge.db <scratch>/forge_snapshot.db` (lock trap —
  `docs/tasks/investigate-live.md`). Read-only connect.
- **verdicts** (233,232): `crucible_run_id` PK, `config_hash`, `decision`
  (promote/component/reject), `decided_at` (naive UTC post-06-09), `trade_count`,
  `grammar_version`, `gate_results` JSON.
- **Honest predicate (byte-for-byte D124):**
  `CAST(json_extract(gate_results,'$.regime_coverage.passed') AS BOOLEAN)
   AND detail NOT LIKE '%coverage_unverified%'`.
- **Hygiene cuts:**
  - `decided_at > TIMESTAMP '2026-06-09 22:52:57'` (cost-floor era — never pool values across).
  - Exclude `grammar_version IS NULL` (pre-v5 re-gate pollution).
  - Dedupe per `config_hash` to the **standard-window basis**: keep the earliest post-cut
    row's values (the LATEST row for `decision`). ⚠️ Corrected by the build run: refit
    re-gates do NOT copy values — they re-measure on longer windows (different estimator,
    post-selection population) and are reported as a separate panel.
  - Exclude the 2 charged-DSR rows from any DSR pooling (era outliers) — they are Stage-E
    calibration anchors instead.
- **Config metadata join:** `submissions.config_json` → `hypothesis`, `dte_bucket`,
  `underlying`, signals. NB verified key shape: signals are
  `{id, indicators, params, role, type}` — indicator ids live under **`indicators`** (a list),
  not `indicator_id`.
- **Orphan check:** verdict hashes absent from `submissions` (king-arm/external cohorts) —
  count them, include as trials (they are part of the search), tag separately.
- **Burst cohort tag:** `~/forge_data/winning_cohort/cohort_hashes.txt` (1,000 hashes;
  research cohort, in-campaign trials).

## 3. Stages

- **A — Cohort + empirical distribution.** Honest slice primary, unverified slice as a
  secondary panel (never pooled — D124). Robust center/spread (median, IQR/1.349) pooled and
  per hypothesis. Composition check: family mix honest-vs-all, and what drove the 06-29-week
  honest spike (coverage-verification broadening would be an era artifact worth a caveat line).
- **B — N_eff bracket** (the whole verdict is reported per cell; no single N_eff is defended):
  1. clusters at hypothesis × directional-indicator × dte_bucket (lower bound);
  2. clusters at hypothesis × family × dte_bucket (coarser lower bound);
  3. correlation-adjusted N/(1+(n̄−1)ρ) for ρ ∈ {0.5, 0.78} (0.78 = measured mr/trend
     monoculture pairwise corr);
  4. raw honest N (~24k);
  5. Crucible's measured 46,131 (campaign incl. unverified);
  6. total submissions 363,589 (upper bound; also covers selection-before-gating, §4).
- **C — Null expected-max.** Gumbel/EVT analytic:
  `E[max_N] ≈ μ0 + σ·a_N`, `a_N = √(2 ln N) − (ln ln N + ln 4π)/(2√(2 ln N))`, plus the
  exceedance probability of the observed max under the fitted Gumbel. Two μ0 variants:
  `μ0 = 0` (favorable-to-signal) and `μ0 = empirical median` (bulk≈null assumption). Output =
  the Q1 verdict matrix (bracket cell × μ0 → exceedance p).
- **D — Creep diagnostic.** Running honest max vs cumulative honest N by day, overlaid on the
  σ·√(2 ln N) envelope; classify track-vs-plateau. (Known data points it must reproduce:
  ~1.40 at ~7.5k, 2.99 at ~24k.)
- **E — DSR inversion + calibration gate.** First REPRODUCE Crucible's two charged DSRs
  (0.0726, 0.0118) from the stored per-run fields + `n_trials=46131` using the Bailey–López de
  Prado DSR closed form — this also settles empirically WHICH Sharpe field they deflate
  (likely `sharpe_baseline`, not cpcv-p25). **The inversion is not trusted until calibration
  matches.** Then invert: SR* such that DSR ≥ 0.95 at n_trials ∈ {46,131; 100k; 250k}, using
  campaign-median T; report SR* plus its cpcv-p25-equivalent via the empirical
  sharpe↔cpcv-p25 mapping on the honest slice.
- **F — Prereg emitter.** JSON prereg: cohort = honest-predicate rows with
  `decided_at ≥ 2026-07-07T15:05:50Z` (v24 deploy) OR hash ∈ burst manifest; prediction =
  cohort honest max cpcv-p25 ≤ the Stage-C bound at the MOST signal-favorable bracket cell;
  resolve at honest n ≥ 3,000 or 2026-07-21, whichever first. Include the Q3 bar in the same
  artifact so the prediction and the standalone-bar claim are timestamped together.

## 4. Statistical caveats the script must encode (not just the writeup)

- **cpcv-p25 is a p25-of-paths statistic**, not a mean Sharpe — its null center is < 0 and its
  null dispersion is not the plain SR standard error. The empirical-body calibration (Stage A/C)
  sidesteps modeling CPCV internals. Directionality of the contamination bias must be stated:
  if the bulk contains real modest edge, empirical σ overstates null σ → null max overstated →
  the test is conservative AGAINST declaring signal. Hence the honest framing of Q1's verdict:
  "the observed max cannot evidence edge above the search null" — it cannot distinguish
  "everything has modest edge" from "nothing does."
- **Selection-before-gating:** the prefilter permutation test (p ≤ 0.10) right-shifts the
  submitted population relative to raw enumeration, so trial-count = submissions understates
  effective search pressure per survivor. Bracket cell 6 (363,589) bounds this; footnote only.
- **Refit-identical values:** re-gates copy metric values verbatim (verified) — dedupe per §2
  or the tail double-counts.
- **Relay questions for Crucible** (append to the next handoff/funnel relay, not blockers):
  1. How was `n_trials=46131` derived ("measured selection multiplicity" — what was counted)?
  2. Is Step 4 (charged DSR) planned to become the standing per-run gate, and on what
     schedule? (It changes decision semantics under Forge's feedback loop — the P(component)
     model trains on `decision`, so a flip is a feedback era boundary Forge must timestamp.)
  3. Which Sharpe field does the DSR deflate? (Stage-E calibration will infer it; confirm.)

## 5. Outputs & conventions

- **File:** `scripts/alpha_budget.py`, conventions per `scripts/tail_verified_alignment.py`
  (D155 pattern: standalone research script, stdlib + duckdb, typed, ruff/mypy-clean).
- **No Crucible imports** (hard rule #2 — everything needed is already in `verdicts`); no
  clock/RNG use (pure retrospective math; if Monte Carlo is ever added, `SeedHierarchy`).
- **CLI:** `--db PATH` (snapshot), `--out DIR` (default `~/forge_data/alpha_budget/`),
  `--json`. Console verdict summary + `report_<stamp>.json` + `prereg_<stamp>.json`.
- **Validation gate before results are cited:** Stage-E calibration reproduces Crucible's two
  charged DSR values within tolerance.
- **Effort:** ~1 day build + validate. Versionless, read-only; STATUS.md block on completion;
  D-entry only when results back an operator ask (expected: the Path C re-pricing).

## 6. Explicitly out of scope

- **No accumulation wait.** More v1 trials mechanically RAISE the noise bar (E[max] grows with
  N); the retrospective is strongest now, and the v24/burst inflow is consumed as the Q4
  prereg out-of-sample check instead.
- **No ONC / realized-PnL correlation pull.** Only if the Q1 verdict FLIPS across the §3-B
  bracket does pinning N_eff matter — then it becomes a `crucible_contracts` ask (realized
  per-config return correlations), not a Forge workaround.
- **No production/feedback changes**, no consumption of results by any live component.

## 7. RESULTS — first run, snapshot max decided_at 2026-07-08T01:01:59Z

Artifacts: `~/forge_data/alpha_budget/report_20260708T010159Z.json` +
`prereg_20260708T010159Z.json`. Console = the script's Summary block. Key numbers:

- **Cohort (standard-window basis):** honest n=10,004 (98.6% trend), median +0.222,
  σ_robust 0.357, **max 1.343** (`52d25dc465a9d165`, 07-05). Unverified panel n=84,943,
  max 1.808. **Refit panel n=8,947 rows (all honest), max 2.99** — the four ≥1.5 outliers
  incl. both transient promotes all live here (§0.4 correction).
- **Q1 (noise-null):** verdict FLIPS across the bracket — the null survives (p>0.05) for
  N_eff ≥ **607** at μ0=0, ≥ **61** at μ0=median. Structural cluster cells (11–35) reject;
  raw/charged cells (10k/46k) don't. With D215's measured within-supply ρ=0.158 → N_eff≈113:
  rejects at μ0=0 (p≈0.01), survives at μ0=median (p≈0.09). **Not decisive alone**: the test
  cannot distinguish "modest-edge bulk" from "selection-shifted null" (the μ0 choice IS that
  question — prefilter permutation p≤0.10 right-shifts the body; a true zero-edge cpcv-p25
  null is centred BELOW zero). Honest framing: nothing in the standard basis approaches 1.5,
  and the max is unremarkable against the body extrapolated to any plausible N_eff.
- **Q2 (creep):** running max grew 1.152→1.343 as honest N grew 158→10,004, sitting −0.1σ →
  −0.72σ vs the null envelope the whole way. No break-out; consistent with noise/modest-edge.
- **Q3 (the de-facto standalone bar) — calibration CONSISTENT (spread 0.011):** Crucible's
  charged DSR deflates **`sharpe_baseline`** with **T = trade count** (cpcv combos are wildly
  inconsistent, spread ~1.0 → relay Q3 answered empirically). SR*(46,131)=1.173, implied
  trial-σ 0.278. **Required sharpe_baseline for DSR ≥ 0.95: 1.254 @ 46k · 1.303 @ 100k ·
  1.359 @ 250k trials** (typical honest T=724 trades). The transient promotes had 1.064/1.076
  → correctly killed. Context: campaign max honest sharpe_baseline = 1.648, so charged DSR
  alone is clearable — **the binding promote gates remain cpcv-p25 ≥ 1.5 (standard-basis max
  1.343) and WF ≥ 2.0**; the charged DSR adds a ~1.25-and-rising sharpe floor that hard-kills
  refit-lane flukes.
- **Q4 (prereg, emitted):** v24+burst cohort honest max cpcv-p25 ≤ **1.479** (null-max 95th
  pct for 3,000 draws, most signal-favorable μ0); resolve at honest n ≥ 3,000 or 2026-07-21.
  A breach rejects the noise-null; resolution needs the burst hashes read from Crucible's
  gated exports (they are not in forge.db).

**Net read for the Path C case:** the campaign's standard-basis ceiling (~1.34, flat) sits
0.15 below the 1.5 bar and the only ≥1.5 sightings are post-selection re-measurements that a
properly-charged DSR kills; accumulation cannot change either fact (the noise bar only rises
with N). What standalone promotion now requires is simultaneously: honest cpcv-p25 ≥ 1.5
(never observed on a consistent basis), WF ≥ 2.0, AND sharpe_baseline ≥ ~1.25-and-growing.
That triple is the quantified ask to price Path C (or a promotion-criterion discussion)
against.
