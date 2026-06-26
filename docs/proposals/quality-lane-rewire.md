# Quality-lane re-wire: gate-then-tail (two-part `E[wf_p25 | clears]`)

Status: **shadow-first build in progress** (operator-gated; flip deferred to a streak clear).
Supersedes the multiplicative wiring of the wf_p25 quality lane ([[tail-aware-ranker.md]],
D191–D193). Ranking-only; hard rules #1/#3/#5/#6 intact.

## Why re-wire

The deployed lane sets the §6.2 prior to `P(component) x tail_norm` (D193). An offline A/B
(2026-06-26, `scratchpad/ab_quality_lane.py`, `ab_rewire.py`; n=2,792 verified-coverage
decided verdicts, realized `wf_sharpe_p25`) found:

- **The deployed blend is a measured no-op.** Every top-K bootstrap CI spans 0;
  `Spearman(P, P×tail_norm) = 0.971` — the multiplier barely reorders anything because
  `tail_norm` is squeezed into a narrow band (0.27–0.85) and the product is dominated by `P`.
- **`P(component)` is ANTI-correlated with the WF floor** (pooled IC −0.10): it predicts
  *clearing the component gate*, a different objective. So any weight on `P` inside the
  ORDERING score drags it toward worse floors.
- **The tail model carries real, wasted signal.** Standalone IC pooled +0.06, and the recent
  daily models are strong (live `6b89fa04` +0.31, `7d62982b` +0.22). The multiplicative form
  throws it away (live model: tail-alone +0.31 → blend −0.17).

**Conclusion: `P` belongs as an eligibility GATE, not a score TERM** — the textbook two-part
`E[wf_p25 | clears]` decomposition. `P` decides *who is eligible*; the tail model decides
*the order*.

## The form

`gate_tail_rank_score(p_component, tail_pred, p_floor)` (`ranking/model.py`):
configs with `p_component ≥ p_floor` are ranked by `tail_pred`; configs below the floor are
demoted beneath every eligible one. Deterministic, ranking-only.

### A/B evidence (recent split = current-model regime, the forward-looking read)

Test window 06-24→06-26 (n=1,117), baseline `P` top-K = −0.681:

| variant | Δ vs `P` | 95% CI | P(Δ>0) |
|---|---|---|---|
| tail alone (ceiling, unsafe) | +0.226 | [+0.075, +0.367] | 1.00 |
| **gate50 → tail (this form)** | **+0.180** | [+0.060, +0.309] | **1.00** |
| add_ew `z(P)+z(tail)` (blend) | +0.091 | [−0.008, +0.169] | 0.96 |
| mult (deployed) | +0.028 | [−0.030, +0.091] | 0.85 |

On the **full pool** the same form is −0.07 (the older, weak tail models drag it down; naive
weight-tuning on the older half picks `w=0` = "use P alone"). The win is **recency-dependent**
— it rests on the tail models continuing to improve (D192's continuous path), which the daily
eval monitors.

## Two caveats (shape the design)

1. **Censoring.** The A/B re-ranks *already-submitted* (already-eligible) configs, so
   "tail alone" looks best only because `P` is pre-baked in. In production the lane scores the
   *full generation stream*, where dropping `P` would flood Crucible with non-clearing configs.
   The production form therefore KEEPS a `P` floor (gate-then-tail), never tail-alone.
2. **Floor calibration (DONE 2026-06-26).** The eligibility floor is the key knob, and the
   calibration (`scratchpad/floor_calibration.py`, reproducing enumerate→P with the live
   registry + F3 model) found the in-batch `keep_frac` mechanism **unsuitable**: production
   `P(component)` is extremely skewed (enumerated median **~0.0004**, p90 ~0.014, p99 ~0.15), so
   `keep_frac=0.5` puts the floor at ~0.0004 — **~311× below** the shadow's verified-coverage
   floor (0.136) and effectively a **no-op gate** (≈ the unsafe tail-alone form). Production
   therefore gates on an **absolute floor** `FORGE_REWIRE_P_FLOOR` (default **0.02** → keeps the
   top ~8% by P, ~100 of a ~1375 passed batch — the candidates that could plausibly clear
   component), and the shadow gates on the *same* floor.

## Rollout (shadow-first, flip on streak — like D193)

1. **Shadow eval (built).** `evaluate_rewire_shadow` (`ranking/evaluation.py`) +
   `forge ranker-model eval-rewire` compute gate-then-tail vs the `P`-baseline top-K realized
   `wf_sharpe_p25` over verified-coverage decided verdicts. Telemetry only — the production loop
   never reads it. Reuses the stored `model_score` (=P) + `tail_score`, so it needs no new
   scoring columns.
2. **Streak (built).** The daily timer (`scripts/daily_ranker_eval.sh`) appends a §8.6-style
   streak to `rewire_streak_wfp25.jsonl`; `forge status` surfaces it as the `re-wire gate-tail`
   clock. A checkpoint PASSes when the fresh-window Δ(gate-then-tail − P) clears the PROVISIONAL
   `_REWIRE_DELTA_CRITERION` (+0.05); the streak counts consecutive qualifying PASSes (target 3).
   Like the wf_p25 tail streak, the first record FAILs (the first fresh window spans the whole
   clean era = full-pool, Δ−0.07) and only climbs as recent per-checkpoint windows accrue — i.e.
   it tracks the recency-dependent win. Raw Δ recorded per row for re-judging.
3. **Floor calibration (DONE).** Switched production + shadow from the `keep_frac` quantile to
   an absolute floor (0.02). See caveat 2.
4. **Production scorer (built, flag-OFF).** Env `FORGE_QUALITY_RANK_MODE` selects the lane
   form; default `blend` = byte-identical. `gate-tail` makes the §6.2 prior
   `gate_tail_prior(P, tail_norm, p_floor)` — `tail_norm∈(0,1)` for configs at/above the floor,
   `0.0` below (stays on the `[0,1]` prior scale the F3/blend lanes use). The floor is the
   **absolute** `FORGE_REWIRE_P_FLOOR` (default 0.02); the shadow gates on the same floor, so
   the streak tracks the gate the live scorer runs. Operator flips by setting
   `FORGE_QUALITY_RANK_MODE=gate-tail` in the unit, on the streak clear, with a D-entry.

   **The censoring wall — why the flip is a WATCHED experiment.** Even with a matched absolute
   floor, the shadow only ever sees the *decided* (submitted) cohort — the passed configs the
   production gate newly surfaces/excludes have NO realized `wf_p25`. At floor 0.02 the decided
   cohort is ~all eligible (its P median 0.136 ≫ 0.02), so the shadow ≈ "does tail beat P on
   recent decided configs": a useful **recency monitor** (recent Δ **+0.19**, full-pool +0.03),
   but NOT a validation of the gate's exclusion of low-P passed configs. So the flip cannot be
   fully proven offline — flip → watch realized component/promotion rate → revert if it dips.

## Hard-rule posture

Ranking-only (#1 grammar / #3 gate untouched); deterministic, no RNG (#5/#6); flag-OFF
byte-identical (#6); reads Crucible's gate value, computes none (§1.2). A steering signal, not
a wall-breaker — promotion still happens at assembly.
