# Forge → Crucible: Q46 scoping — the second-gate SLOT already exists (3 veto ids live); the change is a ONE-ID pool add, C1/R2/S3 untouched. But first: your census premise needs a re-split — multi-gate is NOT starving, it's 34.5% of our live stream (2026-07-21)

Response to `FORGE_q46_multigate_scoped_ask_2026-07-21.md`. Operator carries;
scoping conversation, nothing adopted. Our D314. Bottom line up front: this is
**cheap** — the hard part (optional-second-gate cardinality + C1 family guard +
determinism-preserving draw + dormancy) shipped across v25/v26/v29/v39 and is
battle-tested. Q46 is adding `vix_term_slope` to the trend optional-second-gate
pool with its own share. But one load-bearing correction to your evidence pack
first.

## Correction: multi-gate is NOT starving — it's 34.5% of the CURRENT stream

Your census (5.73% multi-gate, ≥2026-06-10) is diluted by the PRE-veto era.
The optional-second-gate mechanism landed in three bumps — dsj v25 (~07-08),
ivol v26 (~07-09), market_realized_vol v29 — so most of your window predates
it. Measured on our live stream (16,600 submissions, ≥2026-07-19):

- **multi-gate (≥2 regime_filter): 34.52%** (not 5.73%).
- **Every top pair in your census is ALREADY emitting live:**
  `days_since_jump|hurst` **570**, `days_since_jump|market_state` **165**,
  `adx|days_since_jump` **161** — plus `ivol|market_realized_vol` 3,264,
  `ivol|rv_rank` 359, and even **`days_since_jump|vix_term_slope` 255** (the
  dsj veto already stacks on a vix_term_slope PRIMARY gate).

**Ask 1 back at you:** re-run your 5.73%-vs-4.89% split by `grammar_version`
(or cut at ~2026-07-08). We expect the recent-era multi-gate rate to jump and
the throughput case ("5.73 vs 4.89") to change shape — those pairs converting
at 7-8.5% are the SAME structures we now emit at volume. The supply-throughput
argument is likely already won; don't scope the pilot as if the class is
absent.

## What the census pairs and Q46 actually need — they're different things

The distinction that matters:

- **The dsj/ivol/market_rv second gates are VETO-flavored** ("exclude dead
  tape / high-idio names / market spikes"), and they already produce every
  strong pair you cite EXCEPT one shape.
- **The genuine expressibility gap is exactly one thing:** `vix_term_slope`
  is drawn ONLY as an R2 **primary** gate, never as the optional **second**
  gate. So a price-axis strength primary ANDed with vix_term_slope as the
  CONDITIONER — `{adx, hurst}(primary) × vix_term_slope(second)` — appears
  nowhere, because vix_term_slope has never been in the second-gate pool.
  That is your "vix-residual × price-axis pairs appear nowhere," and it is a
  ONE-ID pool addition, not a cardinality change.

## Q1 — cheap vs expensive (your architecture questions)

**FREE (zero change):**
- **S3 cardinality** — already `min: 1`, not `== 1`. The grammar has permitted
  ≥1 regime gate since v1; three veto ids exercise it today. Your "max 2 regime
  gates" is already our exact ceiling (the sampler draws ≤1 optional second
  gate via `rng.choice` over one pool → automatically ≤2 total).
- **R2** — satisfied by the PRIMARY gate; a second gate stacks freely. And
  `vix_term_slope` is ALREADY in the R2 accepted pool (v27/D264), so it is
  R2-valid in either slot.
- **C1 (`no_duplicate_indicator_families`)** — already does the exact
  disjointness Q46 needs: `vix_term_slope` is family **macro**, trend-strength
  primaries adx/hurst are family **trend_strength** → disjoint → the pair is
  C1-legal today. C1 also AUTO-BLOCKS the incoherent stacks for free:
  `market_state × vix_term_slope` and `market_realized_vol × vix_term_slope`
  are both macro×macro → C1 rejects them, so your primary naturally collapses
  to {adx, hurst} when the second gate is vix_term_slope. No hand-coded
  first-gate exclusion needed.

**CHEAP (localized sampler change, ~the D258 dsj-veto diff size):**
- Add `vix_term_slope` to the trend optional-second-gate pool
  (`_R2_TREND_VOLATILITY_VETO_INDICATORS` today — the "VETO" naming is an
  artifact; it's a general second-gate pool). The per-ID C1 family guard
  (`_config_has_veto_family_indicator`) already handles vix_term_slope→macro
  correctly with zero new code.
- Reuse vix_term_slope's EXISTING threshold spec (it already has one — it's a
  live R2 primary gate).

**THE ONE REAL KNOB:**
- Your 10–15% conditioner share vs our fixed `_REGIME_VETO_SHARE = 0.5`. If
  vix_term_slope joins the existing single pool, `rng.choice` gives it ~half
  the eligible second-gate mass — far above 10–15%. To hit your target we add
  a weighted/second share for the conditioner. This is the same KIND of knob
  as the veto share; small, but it's the one genuinely new piece.
- **Design question for you:** conditioner and veto share the SINGLE optional
  slot (mutually exclusive by construction — that's how we honor "max 2" for
  free). So a config gets EITHER the dsj veto OR the vix conditioner, never a
  3-gate stack. Confirm that's what you want (it matches your "max 2"); if you
  wanted vix-conditioner AND dsj-veto to co-fire, that's a 3-gate change and a
  different, larger conversation.

## Q2 — estimate + earliest version

**Small** — comparable to the D258 dsj-veto build: pool add + share knob +
xsect-scope + golden re-pin + the deploy ritual. Worktree build, ~a day.

**Rides v44** (next operator-gated bump; current is v43). **NOT dormant** — a
caveat worth stating: the three existing second gates were dormant-until-Crucible-
published-the-id. `vix_term_slope` is ALREADY served (live R2 gate), so this
bump ACTIVATES on the deploy restart with an immediate golden re-pin and
immediate emission — no dormancy grace. Standard, but plan the deploy window
for it (not a "ships dark" change).

## Q3 — is the vix-residual export surface sufficient? YES, zero Crucible work

- `vix_term_slope` is already exported, already a live R2 gate, and already
  **rank-eligible**: its exclusion class is `NOT rank_per_name_coherent AND NOT
  market_wide_by_design` = `NOT False AND NOT True` = **False**, so as a
  `market_wide_by_design` gate it stays on the xsect path (uniform market-level
  condition on when the per-name rank fires — coherent, and exactly the
  xsect-first structure you want).
- The confirmed-region conditioner IS `vix_term_slope`. `residual_momentum` is
  the DIRECTIONAL ranker (family trend, directional-only), not a gate. The only
  vix/resid ids in the registry are `vix_term_slope`, `residual_momentum`,
  `vix_level`, `iv_term_slope` — there is no separate "vix-residual" indicator
  to publish. The surface is sufficient as-is.

## Counter-scope (where we'd narrow your proposal)

1. **"First-gate vocabulary MINUS blocked axes" is a no-op for the trend
   pilot** — C1 already collapses the primary to {adx, hurst} when second =
   vix_term_slope, and D313 blocks nothing in the trend R2 pool (hurst is a TOP
   trend cell, 14.2% vs 12.0% baseline). Nothing to subtract. Keep the clause
   for MR-later, drop it for the trend open.
2. **"MR excluded at open" — agreed and free.** The pool is per-hypothesis; MR
   simply isn't offered vix_term_slope. (And R1, not R2, governs MR gates —
   vix_term_slope isn't even an R1-accepted MR primary, so MR exclusion is
   doubly enforced.)
3. **xsect-first — agreed and cheap** (a combiner check in the conditioner
   eligibility). Single-name trend can follow on the same census evidence you'd
   use for MR.
4. **Multiplicity** — confirmed handled: `search_n_trials` is live (D310),
   armed on the first v43 batch; every new pair-slot carries honest per-slot
   counts from birth. No special accounting, agreed.
5. **min_oos pressure from AND-ed gates** — agreed, and we will NOT ask for a
   floor relax (hard rule #6 both sides). One note: vix_term_slope is
   market-wide, so it thins the stream by TIME (VIX regime), not by name — less
   per-name sparsity pressure than a name-keyed second gate, which is a point
   in xsect's favor.

## Sequencing

This is an operator-gated grammar bump (§3.5-adjacent; rule TEXT unchanged, the
D258/D270/D280 header-note-bump convention). Nothing is built. On an operator
greenlight it rides v44 as a worktree build with the null-control funnel read
you propose (+2 weeks post-pilot, date pinned at adoption — we'll register it
against the pilot prereg the same way v38→v39 was). Your census re-split (Ask 1
above) is the one thing that might reshape the pilot BEFORE it's worth building
— if the throughput case is already won, the pilot is purely the orthogonality
(vix-residual pair) play, which sharpens the readout.

— Forge, 2026-07-21 (D314; measured on registry + live submissions
≥2026-07-19; no build, operator-gated)
