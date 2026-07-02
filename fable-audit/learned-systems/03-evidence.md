# 03 — Evidence appendix: raw numbers, provenance, reproduction commands

All live reads taken 2026-07-01 ~14:30–15:00 UTC unless noted. DB-derived numbers came from a
throwaway snapshot of `~/forge_data/forge.db` (copied, queried, deleted) — **never open the
live DB directly** (RW lock; `docs/tasks/investigate-live.md`).

## Reproduction commands

```bash
# Streaks (JSONL, append-only; one record per checkpoint)
tail -n 15 ~/forge_data/ranker_eval/streak.jsonl                    # F3 P(component)
tail -n 15 ~/forge_data/ranker_eval/robustness_streak_wfp25.jsonl   # wf_p25 lane (§8.6)
tail -n 15 ~/forge_data/ranker_eval/rewire_streak_wfp25.jsonl       # gate-then-tail shadow

# Model artifacts (daily pairs: verdict + robustness)
ls -lt ~/forge_data/models/ | head -30

# Ops summaries (read-only CLI)
uv run forge status
uv run forge healthcheck

# Live service config + loop liveness
systemctl --user cat forge.service          # check ExecStart flags + Environment= lines
journalctl --user -u forge.service --since "48 hours ago" --no-pager \
  | grep -Ei "quality_rank|f3_ranker|hypothesis_weight|rank_mode|orthogonal"

# DB snapshot for per-model evals (~4.5 GB; check free space first)
cp ~/forge_data/forge.db /tmp/<scratch>/forge_snap.db
uv run forge eval-robustness --gate wf_sharpe_p25 --db /tmp/<scratch>/forge_snap.db   # per-model wf_p25 IC
uv run forge ranker-model eval        --db /tmp/<scratch>/forge_snap.db               # per-model F3 AUC
uv run forge ranker-model eval-rewire --db /tmp/<scratch>/forge_snap.db               # pooled gate-tail vs P
# (flag names may drift — verify with --help; delete the snapshot after)

# Offline A/B records (already-run experiments; scripts preserved)
sed -n '1,60p' docs/proposals/quality-lane-rewire.md
ls scratchpad/ab_quality_lane.py scratchpad/ab_rewire.py
```

## E-1. F3 verdict ranker

- Streak: **17 consecutive PASS** through 2026-07-01. Latest: AUC margin **+0.409**
  (model 0.862 vs incumbent-composite 0.454). Last 8 margins:
  +0.34, +0.30, +0.50, +0.23, +0.26, +0.33, +0.27, +0.41. No FAIL since ≤06-13.
- Per-model recompute (07-01 snapshot, `ranker-model eval`): all substantial models PASS,
  margin +0.20…+0.52. Examples: `a51c83c1` AUC 0.864 vs 0.451 (n=10,575); `c33e2875` 0.872 vs
  0.422 (n=17,945). Sole FAIL `b7d260cb` (−0.171) on a degenerate window (n=483, 6 positives,
  incumbent AUC 0.931) — noise, not signal.
- **Calibration defect** (from eval reliability tables): recent model `a51c83c1` —
  bin [0.3,0.4): predicted mean 0.341 vs realized rate **0.127**;
  bin [0.4,0.5): 0.441 vs **0.099**; bin [0.5,…): 0.542 vs **0.091** (≈3–5× over-predicted).
  Older `c33e2875` was well-calibrated/slightly under-predicting → drift across artifacts,
  not a stable bias.
- Live model 07-01: verdict `589bb6da` (journal `f3_ranker: P(component) prior ACTIVE`).

## E-2. wf_p25 quality lane

- §8.6 streak: **FAIL 0/3**; all 9 recent checkpoints FAIL vs criterion 0.30. Last 8 Spearman:
  −0.05, −0.11, +0.27, +0.06, +0.04, +0.08, +0.05, **+0.2986** (07-01).
- Per-model Spearman IC vs realized wf_p25 (07-01 snapshot, `eval-robustness --gate
  wf_sharpe_p25`; note the output mislabels realized values "cpcv_p25" — cosmetic bug):

| model | trained | n decided | Spearman | top-K realized tail vs incumbent |
|---|---|---|---|---|
| `69019c92` | 07-01 (live) | 857 | **+0.280** | −0.746 vs −1.022 (better) |
| `85cf4762` | 06-30 | 583 | **+0.315** | −0.555 vs −0.534 (~tie) |
| `6b89fa04` | 06-26 | 1,350 | **+0.052** | −0.558 vs −0.434 (worse) |
| `c66e56af` | ~06-21 | 488 | −0.003 | ~tie |
| `15a9d38c` | — | 536 | +0.075 | better |
| `7d62982b` | — | 508 | +0.220 | worse |
| others | n<200 | — | +0.04…+0.20 | mixed |

- **Decay-at-n pattern, two occurrences:** `c66e56af` +0.403 @ n=58 (06-21 read) → −0.003 @
  n=488 (06-26 read); `6b89fa04` +0.307 @ n=98 (06-26 read) → +0.052 @ n=1,350 (07-01 read).
  The two newest models (+0.28/+0.315) match the early-model shape that decayed both times —
  treat them as unproven until n grows.
- Journal liveness: `quality_rank: wf_p25 BLEND ACTIVE (model=69019c92…)` every iteration.

## E-3. Gate-then-tail (offline A/B + shadow)

- Offline A/B (06-26, `scratchpad/ab_quality_lane.py` / `ab_rewire.py`, n=2,792; recorded in
  `docs/proposals/quality-lane-rewire.md:8-24` + `gate_tail_rank_score` docstring):
  - Spearman(P, P×tail_norm) = **0.971** (blend ≈ P-alone; tail_norm squeezed to 0.27–0.85);
  - P pooled IC vs realized wf_p25 = **−0.10** (anti-correlated); tail-alone +0.06 pooled /
    +0.31 on the then-live model;
  - deployed-blend uplift vs P-alone: Δ +0.028, **CI spans 0**;
  - gate-then-tail (hard-gate form), recent window: Δ **+0.180**, CI **[+0.060, +0.309]**;
    full-pop d = −0.074 (the recent-window/full-pop split is why fresh windows matter).
- Rewire shadow streak (`rewire_streak_wfp25.jsonl`, criterion Δ ≥ 0.05, 3-consecutive):
  - 2026-06-30: FAIL, Δ +0.007, n=4,003 — **full-pool window since 2026-06-10, marked
    `qualifies: true`** (contaminated first look; counted toward streak arithmetic);
  - 2026-07-01: PASS, Δ **+0.333**, n=586, k=58 (fresh window). Streak 1/3.
- Pooled recompute (07-01 snapshot, `eval-rewire`): n=5,484; top-548 realized wf_p25:
  gate-then-tail **−0.803** vs P-baseline **−0.865** (Δ +0.062, PASS-level) — but population
  mean is **−0.694**: BOTH selections underperform the average config on the realized WF
  floor. Gate-then-tail mitigates, does not cure, the P-inversion.
- Production state: `forge.service` ExecStart carries `--quality-rank` only; **no
  `Environment=` lines** → `FORGE_QUALITY_RANK_MODE` unset (mode=blend live),
  `FORGE_ORTHOGONAL_FAMILY_FLOOR` unset (D216 floor OFF). Zero journal hits for
  rank_mode/gate-then-tail in 48h.

## E-4. Hypothesis weights / family mix

- Journal (07-01, every iteration): `trend_continuation=1.000`, `mean_reversion≈0.16–0.19`,
  `volatility_event=0.050–0.068` (mostly exactly **0.050 = the D067 floor**),
  `relative_value≈0.17–0.20`, `event_momentum≈0.20`, `regime_arbitrage`/`tail_hedge`=0.091
  (prior — never enumerated).
- Realized submission mix (snapshot):
  - last 7d, n=54,200: **mr 72.7% / trend 20.1% / vol_event 6.5% / em 0.5% / relval 0.1%**;
  - last 2d, n=22,000: **mr 59.8% / trend 32.8% / vol_event 6.5%**.
- Oscillation timeline (all from STATUS/D-entries + this read): 06-25 ~85% mr → 06-29 81.4% mr
  (vol_event 6.9%) → 07-01 trend weight 1.000, trend share rising through 33%. vol_event flat
  at ~6.5% throughout = floor-sustained, zero organic growth.
- D216 floor experiment (from the D216 record): `volatility_event=0.20` (relative-to-max) lifts
  vol_event *sampling share* 2.9% → 10.7% at the 07-01 weight vector; trend 58% → 54%.

## E-5. Healthcheck / ops (07-01)

- `forge healthcheck`: **OVERALL=OK** (9 ok / 0 warn / 0 crit). Notables: model fresh (9.6h);
  contracts pin == 1.21.0; `component_contributions: present (0.6h old)` — but the export is
  **n=0** (promotion-gated; populates only when a book promotes); drift lines:
  `F3 ranker drift ok (latest +0.409)`, `wf_p25 drift ok (latest +0.299)`.
- Model rotation: newest pair 07-01 05:08 (`589bb6da` verdict + `69019c92` robustness). Holes:
  **06-16 and 06-27→29 missing** (a single 06-30 pair covered 4 days; its F3 window had
  fresh_decided 22,486). Streak checkpoints skip the same days. Cause not investigated
  (timer vs box downtime) — plan item P5.4.
- Known-benign (do not "fix"): `blocked: prev batch N% gated` (§7.3 limiter working);
  `crucible-ingest-daily` "failed" (rfr-only).

## E-6. Static/code facts (working tree @ `ceeefa4` + uncommitted D216)

- Composite weights: `config/ranker.yaml:8` (`prior_promotion_proximity: 0.10`),
  `src/forge/ranking/scorer.py:74-80` (0.30/0.25/0.20/0.15/0.10). Incumbent composite AUC vs
  realized components per streak records: **0.45–0.53**.
- Blend vs gate-tail wiring: `src/forge/cli/main.py:1988-2012` (mode dispatch + floor env at
  `:2000`, unguarded `float()`), `:2015-2019` (blend default). Pure functions:
  `src/forge/ranking/model.py:622-637` (`gate_tail_rank_score`), `:653-662` (`gate_tail_prior`),
  `:609` (tail_norm sigmoid, docstring still "provisional"), `:579` (blend). Shadow hard-gate:
  `src/forge/ranking/evaluation.py:351`.
- Streak criteria: `src/forge/cli/ranker_model_cmd.py:44` (§8.6 `0.30`, PROVISIONAL), `:52`
  (rewire Δ ≥ 0.05); pooling across artifacts `evaluation.py:213`; F3 PASS criterion
  `:229-241`; calibration printed-not-gated `:249-253` + `evaluation.py:70-86`; ridge
  train-R²-only at `:466`.
- Estimand: `src/forge/feedback/rejection_weights.py:456-486` (reward), `:489-542` (sums),
  `:578-581` (posterior mean), `:632-668` (normalize to max=1), `:309-310` (Beta(1,50)),
  `:1290-1322` (D067 floor 0.05), `:1325-1361` (D216 `apply_orthogonal_family_floor`,
  uncommitted). Parser `main.py:511-544`; call site `main.py:1770-1778`; loader + warn-once
  global `main.py:546-640`. Sampler consumption `src/forge/enumeration/sampler.py:549-555`;
  rank gating `sampler.py:694-704` + `search_space.py:111,142`.
- D216 tests: `tests/unit/test_feedback/test_rejection_weights.py:301-352` (5),
  `tests/unit/test_cli/test_run_loop.py:302-333` (3),
  `tests/invariants/test_orthogonal_family_floor_invariants.py` (2 — **untracked file**).
- B8: `search_n_trials` defined only at `crucible_contracts/models.py:374` (hash-excluded);
  zero assignments in `src/forge`; `src/forge/cli/alpha_budget_cmd.py:64` prints "Crucible
  currently charges n_trials=1 (search_n_trials unset) → deflation 0.00".
  `confirm_promotion_claim` (`src/forge/feedback/preregistration.py`): no production callers.
- Prereg `9b88966c446a` (relval ceiling): resolved REFUTED 2026-06-28 with a disclosed
  **metric substitution** (Crucible rank-IC probe instead of the pre-registered
  `cpcv_sharpe_p25_max` census; operator accepted) — see `config/preregistrations.jsonl`.
- Dead code (no production callers): `compute_hypothesis_weights`,
  `compute_hypothesis_reward_weights` (+ `_sharpe_reward`, `_run_reward`), legacy Beta(1,10)
  at `rejection_weights.py:49-50`.
- Process: commits `edb03e6`/`fdeed29`/`92e9061`/`ceeefa4` (06-26) — `edb03e6` commit message
  ends "D-entry deferred (concurrent edits in IMPLEMENTATION_DECISIONS.md)"; no D-entry or
  STATUS block exists for gate-then-tail as of 07-01. D212–D216 uncommitted.

## Method note

Produced by three parallel read-only audit passes on 2026-07-01: (1) ranking-stack code audit
(B1–B6 + the 06-26 commits), (2) feedback/enumeration code audit (B7–B12 + D216), (3) live
evidence sweep (streaks, per-model evals on a DB snapshot, journal, healthcheck, service
config), synthesized against `LEARNED_SYSTEMS_AND_GENERATION_REVIEW.md`, `STATUS.md`
(06-25→07-01 blocks) and D-entries D193–D216. The audit itself changed nothing outside
`fable-audit/learned-systems/`.
