# Proposal: v48 — trend-xsect emission re-weight (un-crowd `momentum_252`)

**Status: DEPLOYED 2026-07-22 (D328) — operator "deploy".** SCOPE CHANGED vs the staged version: the headline change became Crucible's root cause (`rank_k<=10`, their `FORGE_coverage_gate_rootcause_reply`), and the `momentum_252` emission boost was DROPPED — the funnel showed enumeration already supplies 28% and the loss is at the ranker (holdout 8.43% -> ranked 0.33%), which the label fix addresses upstream. prereg `be5508b63706`. Superseded staging notes below.

**Status (history): STAGED (operator-gated) — 2026-07-22.** Answers Crucible's ask #1 in
`FORGE_component_quality_and_emission_reweight_2026-07-22.md`. Relay:
`PROMPT_CRUCIBLE_EMISSION_REWEIGHT_AND_COVERAGE_GATE.md`. Class: emission-policy
(rules text unchanged, D098/v5 pattern) + a sampler change → goldens re-pin.

## The problem (root-caused, ours)

`momentum_252` is Crucible's best trend component (cell-controlled lift **4.11**, 21.2%
all-time admission vs 12.9% base, no losing version across 25 revisions) and its emission
collapsed to **0.64%** of trend-xsect (their 0.62% reproduces on our ledger).

It is **not** under-weighted — our learned weights rank it #1
(`directional_bucket trend×momentum_252×swing_long = 0.129`, cohort-xsect 0.134, and its
promoted gates top the regime weights). The ranker mildly favours it (ranked 6.57% vs
holdout 5.20% — no D287 selection starvation). **It is crowded out:**

| gv | `residual_momentum` | `momentum_252` | donchian | rolling_sharpe |
|---|---:|---:|---:|---:|
| v44 | 9.55% | 7.54% | 41.7% | 41.2% |
| v46 | 19.82% | 3.64% | 42.0% | 34.5% |
| v47 | **40.80%** | **0.64%** | 26.9% | 31.7% |

Two compounding causes, both ours:
1. **v45 (D319) `_RESID_MOMENTUM_PILOT_WEIGHT = 2.0`** — the pilot dial doubled resid's draw.
2. **v47 (D328) × resid's xsect PIN (D276)** — resid is pinned `p_xsect=1.0` so every draw
   survives, while every other trend directional loses its single-name half to the v47
   filter. resid's relative share doubled again (19.8 → 40.8%).

Net: **40.8% of trend-xsect emission goes to the directional Crucible measures at lift
0.15 (solo-dead, n=1,283, median CPCV 0.027, zero top-200 appearances)**; 0.64% to the one
at lift 4.11. This is the mechanism behind the trend cell's falling admission rate
(8.44% → 6.34%).

## The change

1. **Pin `p_xsect = 1.0` for `trend_continuation` + `mean_reversion`**
   (`_cohort_xsect_probability`, the D276 pattern extended from one directional to the two
   hypotheses). With single-name retired (v47) the xsect/single cohort split is
   meaningless: it (a) removes resid's structural advantage over directionals that lose
   their single half, and (b) recovers the ~39% of trend/MR draws currently drawn-then-
   filtered. **This alone is expected to restore most of the mix.**
2. **Retire the resid pilot dial: `_RESID_MOMENTUM_PILOT_WEIGHT` 2.0 → 1.0.** Its sample
   target is massively exceeded (891 resid trend-xsect runs in v47 alone vs the 600–800 the
   pilot was sized for). Crucible's 2026-08-04 P2 in-book read is **unaffected** — the
   sample is banked; we are not calling the pilot, only stopping over-accrual. resid keeps
   its D276 xsect pin.
3. **Boost `momentum_252`** (Crucible's explicit ask) via a directional weight multiplier
   mirroring the v45 dial pattern; secondarily `market_state` (their 1.8–1.9× second-best).

Bound honestly (hard rule #6): this buys component **throughput**, not a promotion — the
family's CPCV ceiling sits under the 1.5 gate (best 1.470 v46 / 1.401 v47).

## Determinism & test surface

Changes the weighted draw → **sampler goldens re-pin** (the v47 method: recompute off the
pinned-universe fixture, re-verify flag-off invariants BEFORE re-pinning, document the
relational splits per test). Emission proof required: trend-xsect mix before/after showing
`momentum_252` share restored and resid share normalized; xsect/single ratio = 100% xsect
for trend/MR; capitulation (momentum, single-name) still emitted.

## Sequencing

Prereg first (predicted: `momentum_252` share of trend-xsect ≥ ~5% post-cut and the trend
cell's admission rate stops falling) → build in `../Forge-build` → goldens re-pin → full
suite → emission proof → deploy ritual → `funnel --compare v47 v48`.

## NOT in v48

The coverage-gate starvation (relay §5) is Crucible-side and upstream of every learned
weight — it is the higher-leverage item but not ours to fix.
