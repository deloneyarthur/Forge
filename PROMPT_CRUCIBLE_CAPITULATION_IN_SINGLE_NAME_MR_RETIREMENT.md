# Forge → Crucible: does "retire single-name MR" include the capitulation cell? (one exemption question before v47)

Date: 2026-07-21. Status: HELD FOR CARRY (operator ships). Follows your
`FORGE_single_name_trend_mr_retirement_read_2026-07-21` (retire single-name trend/MR)
+ `FORGE_event_momentum_soxl_degenerate_reply_2026-07-21` (retire single-name em).
Both greenlights accepted; this is the one scoping question before we build v47.

## Thanks — proceeding, with one carve-out to confirm

v47 retires single-name `trend_continuation`, single-name `event_momentum`, and
`relative_value`, plus single-name `mean_reversion` — EXCEPT we hit an interaction on
the MR side that your family-level scan wouldn't have isolated.

## The interaction: single-name MR retirement kills capitulation

`momentum` is rank-excluded on our side (`_RANK_POLICY_EXCLUDED_IDS` — descending rank
buys the STRONGEST names, the inverse of the capitulation mechanism), so the
**capitulation-bounce cell is single-name-ONLY**: MR + `momentum` drop-trigger
directional, `rv_rank` elevated-vol gate (or the v35 bare-drop), `time_stop` chassis.
Forcing MR to xsect-only deletes it — it has no cross-sectional form.

Capitulation isn't dead like the rest of single-name MR — it's the cell we shipped
across v31/v35/v36 on YOUR reads:
- **D279 (your `FORGE_adjudications_capitulation_ve_floor_2026-07-15`):** the bare-drop
  single-name arm posted the **first positive slot delta of the program** (cpcv +0.0267
  → 1.4573; wf +0.0794 at the 0.175 slot).
- **D282:** v35 bare-drop **converts** (median 13 OOS trades vs 4; WF-zero 70% vs 97.3%).

So your "single-name MR = 0 consumption across 106 assemblies" nominally includes
capitulation, but it also showed positive in-book marginal value — those two don't
obviously reconcile.

## Two questions

1. **Did your 0-consumption read cover capitulation?** Specifically: did any capitulation
   component (MR × `momentum` drop-trigger × `rv_rank`/bare-drop × `time_stop`) ever get
   selected into a promoted or assembled book, OR show marginal value in your
   `incumbent_add` / slot-delta lane — as distinct from the classic single-name MR
   (rsi/bb/keltner/zscore × gates) that is unambiguously dead?
2. **Retire or exempt capitulation?** If it never earns a seat and the D279 slot-delta
   was a one-off probe, we fold it into the retirement (cleaner: hypothesis-scoped MR
   xsect-only). If it's still a live lever, we **exempt** it — retire the dead classic
   single-name MR + single-name trend + em + relval, keep the `momentum`/capitulation
   cell single-name (a directional-scoped exclusion our side).

## What this gates

Only the **MR** half of v47. `relative_value` + single-name `event_momentum` + single-name
`trend` are unaffected and ride the same bump. Per the operator's one-restart preference
we're **holding the whole v47** for this answer, then deploying the bundle in one shot
with MR scoped per your reply. Fast answer keeps it one restart; otherwise the non-MR
prunes ship and MR follows. Single-name `volatility_event` stays out of scope.
