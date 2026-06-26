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
2. **Floor calibration.** The eligibility floor is the key knob. The shadow uses an in-cohort
   `keep_frac` (default 0.5). The *production* floor must be an absolute `P` threshold
   calibrated to the component-clear rate on the generation stream — a separate shadow that the
   submitted-only data cannot supply. Over-gating costs WF floor (full-pool `q=0.25` → −0.097),
   so calibrate conservatively (drop only clearly-ineligible configs).

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
3. **Floor calibration (next).** One-time generation-stream shadow to set the absolute `P`
   floor.
4. **Production scorer (next, flag-OFF).** A `--quality-rank-mode={blend,gate-tail}` (or a
   replacement) on the lane; `gate-tail` makes the §6.2 prior use `gate_tail_rank_score`.
   OFF/blend default = byte-identical. Operator flips on the streak clear, with a D-entry.

## Hard-rule posture

Ranking-only (#1 grammar / #3 gate untouched); deterministic, no RNG (#5/#6); flag-OFF
byte-identical (#6); reads Crucible's gate value, computes none (§1.2). A steering signal, not
a wall-breaker — promotion still happens at assembly.
