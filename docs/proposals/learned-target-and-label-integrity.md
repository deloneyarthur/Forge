# Proposal: learned-target upgrade + label integrity as a standing system (Theme 2)

Status: **2b BUILT flag-OFF (D307, 2026-07-20)** — `forge.ranking.cell_floor`
+ diversifier phase 0c behind `FORGE_YOUNG_CELL_FLOOR` (default off,
byte-identical, reboot-safe); activation = an operator deploy window (flip
the service env + restart + first-batch audit). 2a / 2c / 2d remain drafts —
operator-gated; nothing else ships off this doc.
Date: 2026-07-20. Source: post-promotion process-improvement review (the 2-leg
promotion retro + the first de-ghosted retrain read).
Relates to: [[D287]] (selection starvation), [[D290]] (ghost-label cut), [[D284]]
(hygiene comparator / tail-model KEEP verdict), [[D136]] (arm floor), [[D119]]
(learned weights must not bias experimental draws), D128 (clean-era label cut
precedent), docs/proposals/tail-aware-ranker.md, quality-lane-rewire.md.

## Motivating evidence (all verified in STATUS/D-entries)

- **Promotion is not a learnable target.** n=2 promotions ever. F3 learns
  P(component); the actual objective is the joint strong-AND-decorrelated
  frontier. The frontier metrics (cpcv_p25, WF median, OOS trade count) are
  graded, abundant, and sit in `verdicts.gate_results` — unused as targets.
- **The tail model's regression framing is broken on its own terms**: first
  de-ghosted retrain oos_r2 = −2.24 (was −16 ghosted) — still deeply negative —
  while its RANK information is real (abs tail IC 0.31–0.54; re-wire clock
  +0.44…+0.68; SPRT promote +22.4, the D284 audit). The value is ordinal; the
  loss is not.
- **The ranker gates its own future training data.** D287: the F3 P-gate held
  vix-resid to 16% eligibility vs hurst's 87% because history was hurst-carried;
  the D136 arm floor could not scope to the pair (arm key = (role, indicator_id);
  vix_term_slope matured within days). The 5% exploration holdout is the only
  unbiased sample.
- **Labels can be fictional at scale.** The ve ghost episode: 34,273 verdicts /
  657 fictional components ≈ 10% of all positive labels for five weeks. The v39
  cut was reactive archaeology; nothing structurally prevents a recurrence.

## Proposed increments (each independently shippable, own D-entry)

### 2a. Ordinal gate-tail targets (learning-to-rank on distance-to-frontier)
Replace/augment the binary component label with an ordinal target derived from
`gate_results` (e.g. bucketed cpcv_p25 / WF-median bands). The tail model moves
to a ranking or quantile loss; judged ONLY on rank metrics (IC/AUC-style),
never r2 — the D284 finding formalized. Prereg the comparison (D207) against
the current stack on the same holdout-cohort protocol used for F3.

### 2b. Cold-start floor generalization (retire the hand-pin class)
Generalize the D136 arm-floor keying so any *cell* (configurable key, incl.
(directional, regime) pairs) younger than N days of decided verdicts gets
model-independent floor slots automatically — the D287 pin becomes the manual
override, not the mechanism. Interacts with the campaign registry (D297):
a new campaign's cell should be floored on registration day without a bespoke
code change. Selection-side, versionless (D193/D252 precedent), but NOT
byte-identical → needs its own deploy window + emission audit.

### 2c. Label provenance + integrity tripwires (the anti-ghost system)
- Stamp label rows with provenance (source export, cache era, writer version
  where available) so future cuts are a filter flip, not archaeology.
- Standing activation-probe audit: the exact probe that caught
  ref_trailing_return inert (0 activations vs control market_rv=934) run on a
  timer over every indicator our carriers depend on; WARN on zero-activation
  ids with live carriage.
- Staleness tripwire on stored-cpcv component inputs feeding labels (the
  put_wall/gex/vex/cex class), to the extent visible from our side; where not
  visible, a standing ask in the next relay for a cache-era stamp on gated
  exports (contracts gap — surface, don't work around, hard rule #2).

### 2d. Young-cell holdout weighting (selection-bias hygiene)
Raise the exploration-holdout share *for young cells specifically* (or add an
uncertainty bonus to the prior blend) so novel cells accrue unbiased labels
faster than the flat 5% provides. Off-policy correctness beats raw volume:
the holdout is the estimand's only clean window (P3.3 design intent).

## Explicitly NOT proposed
- Training on promotion outcomes directly (n=2; would overfit to one book).
- Any change to Crucible's gate or our submission volume.
- LLMs anywhere in the loop (hard rule #5; classical ML only, per operator).

## Sequencing suggestion
2c first (cheap, pure telemetry, de-risks everything downstream), then 2b
(unblocks campaign velocity), then 2a (the model change, biggest lift), 2d
alongside 2a. Each gets a prereg line before its comparison read.
