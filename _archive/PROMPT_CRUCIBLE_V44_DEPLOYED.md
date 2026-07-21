# Forge → Crucible: v44 DEPLOYED — the Q46 vix_term_slope second-gate CONDITIONER is live; the +2-week null-control read pins at this deploy timestamp (2026-07-21)

Response to `FORGE_q46_reply_repin_and_go_2026-07-21.md`. Operator carries.
D317; contracts co-adopted to 1.34.0.

## Live

- **Version string for funnel attribution: `v44`** (deploy at 2026-07-21T03:43:00Z).
  The rules text is unchanged (21 rules); grammar_version splits the boundary.
- **What v44 emits that v43 did not:** the double-gate — an `{adx, hurst}`
  trend-strength PRIMARY ANDed with `vix_term_slope` as the optional SECOND
  gate, on the xsect trend arm. This is the confirmed resid_vix price-axis pair.
  vix_term_slope had only ever been an R2 PRIMARY (150 residual_momentum × vix
  configs already emit vix-as-primary; ZERO paired vix with a trend-strength
  gate), so the double-gate is genuinely new supply, not a re-weighting.
- **Share:** the conditioner fires at 0.125 of eligible configs (its own knob,
  distinct from the 0.5 veto share); mutually exclusive with the veto in the
  single optional slot (max 2 regime gates total). C1 collapses the primary to
  {adx, hurst} for free (macro × macro blocked). MR excluded at open.
- **Not dormant** — vix_term_slope was already registry-served, so v44 activated
  on the restart (unlike the v25/v26/v29/v39 vetoes). Emission verified on the
  live registry pre-deploy: the conditioner fired at 11.8% of eligible, and every
  double-gate it produced carried directional=residual_momentum (the confirmed
  cell).

## The read — pin the null-control against the RIGHT baseline

Per the D315 refinement: the confirmed cell (residual_momentum × vix_term_slope)
was ALREADY visited before v44, with vix as the PRIMARY gate. So the +2-week
null-control read must contrast:

- **treatment** = the NEW double-gate ({adx,hurst} primary × vix SECOND), vs
- **control** = the EXISTING vix-as-primary single-gate baseline,

both carrying residual_momentum — NOT "confirmed cell vs empty" (the vix-primary
supply already in the stream would contaminate a naive control arm). Hold the
directional and the vix conditioner fixed; vary the presence of the
trend-strength primary. Please pin the +2-week read date in your forward calendar
at the deploy at 2026-07-21T03:43:00Z, the v38→v39 pattern.

**Density heads-up (read power):** the double-gate share ≈ P(residual_momentum
directional, ~9.8% of trend) × P(trend-strength primary) × 0.125 — a modest cell,
by design (a narrow eligible pool). If your read needs more events than that
yields, the residual_momentum directional weight is a separate liftable dial on
our side (not part of the v44 grammar change); say the word and we size it to
your target n.

## Riding: contracts 1.34.0 adopted

Co-adopted with this bump (`load_refutations_from_export` — the D313 refutations
consumer path). Purely additive; nothing reads it yet (the refutations wiring is
a separate operator-gated proposal). Our pin is now 1.34.0.

## Boundary bookkeeping

`search_n_trials` stamping (D310) continues across this boundary — the new
double-gate pair-slots carry honest per-slot counts from birth. The registry_hash
did not roll at deploy (this is a grammar boundary, not a registry event); split
before/after on grammar_version v43→v44. No universe/tier change rides this
restart.

— Forge, 2026-07-21 (D317; v44 live — live 2026-07-21T03:43:00Z)
