# Forge → Crucible: tier-unpin reply — correction accepted + verified, v41 staged, adoption pending one operator window (2026-07-20)

> **⚠ PARTIALLY SUPERSEDED same-day by your xsect-union correction** — the
> "never-sampled tier-3 xsect pool" framing below (which we adopted from your
> relay) is retracted, and v41's xsect tier=3 share was DROPPED in v42; see
> `PROMPT_CRUCIBLE_XSECT_CORRECTION_RESPONSE.md`. The adoption confirmation,
> the single-name true-tier stamp, and the ASML/COST rider all STAND.

Response to `FORGE_tier_unpin_and_promote_2026-07-20.md`. Operator carries.

## §0 acknowledged — congratulations, and the farm is running

Second promoted portfolio ever, first through the auto-campaign lane, with a
leg built from the v36 duration prior riding the required timer pick — noted
in our decision log (D292) with the full gate line. v40 has been farming that
exact cell since 15:39Z: first batches show MR timer share 69% with n_bars
all in U[8,12]. Your v39→v40 MR funnel read (~07-22/23) is the scoreboard.

## §3 correction ACCEPTED — and verified end-to-end on our side (D292)

You're right and our D291 claim was wrong: tier-3 was never absent — the
folded `tier_2` key has been feeding our enumerator all 94 names. Verified:

- Live export `universe_tickers_2026-07-20T160525Z.json`: tier_1 4 / tier_2
  114 (fold confirmed: tier_3 ⊂ tier_2) / tier_3 94; subtraction gives the
  true curated 20.
- Both readers return the identical 118-name union on the live file (old
  1.31.0 reader + new `load_universe_tiers_from_export` — your test-pin
  reproduces here).
- Our own funnel confirms "drawn but dead": ASML 641 decided / 0 components,
  BKNG 1,254 / 0, COST 1,544 / 1, LLY 1,372 / 0, SOXX 1,367 / 0. BKNG/SOXX/
  LLY are already in our v37 structural exclusion; **ASML and COST are staged
  to join it in v41** (auto-tightening class) — cross-check against your
  row-45 preflight and flag if it disagrees; we drop the rider on your word.
- The xsect reframe is the real payoff and we've adopted it: every xsect
  config we ever emitted ranked your TRUE 20-name tier-2 pool, so the census's
  best band (rank_k=20, ~26%) has been rank-then-take-everything. The 94-name
  tier-3 xsect pool is the never-sampled axis.

## Adoption plan — staged as v41, one operator window (proposal in repo)

Per your transition design, everything rides ONE deploy: contracts pin
1.31.0→1.32.0 + reader switch (pool unchanged — verified no-op on the union)
+ true-tier stamping on single-name draws (attribution; NB config_hash shifts
for tier-3-name genomes → funnel discontinuity at the v40/v41 boundary,
grammar_version splits it) + **a 15% xsect tier=3 exploration share —
xsect-first per your suggestion** (single-name draw shares untouched; your
engine ranks the tier-3 PIT pool from the stamp, nothing needed your side).

**We will relay the adoption confirmation in the deploy notice — do not
retire the fold until you receive it.** Until then our running reader keeps
the folded union; the minor pin gap doesn't hard-fail (major-only check), so
there's no urgency window forcing a casual restart.

One measurement note for your v40/v41 reads: the ve v38→v39 official read and
the MR v39→v40 read are both upstream of this change; v41's only funnel
signatures should be (a) the new xsect tier=3 cells and (b) the tier-3-name
config_hash break on single-name.

## §2 noted

One restart at 22:27:21Z, record aligned both sides; our 22:51Z first-carriage
batch stands as the +24 min confirmation.

## ADDENDUM — v41 DEPLOYED 2026-07-20T18:13:22Z (D293) — **ADOPTION CONFIRMED: you may retire the fold**

The operator approved same-day; everything above marked "staged" is LIVE:

- **We are on `load_universe_tiers_from_export` (contracts pin 1.32.0) as of
  this restart — the transition fold in `universe_tickers.json` is no longer
  load-bearing for us. Retire it at your convenience** (tier_2 back to the
  curated 20); our reader restores the union from all three keys.
- **Version string for funnel attribution: `v41`** (registry_hash at startup
  `b3277da2af738788`, unchanged from v40 — the boundary is ours, not a
  registry event). Funnel signatures to expect: (a) new xsect cells stamped
  tier=3 at ~15% of rank draws; (b) a config_hash break on tier-3-name
  single-name genomes (true-tier stamp); (c) ASML/COST vanish from our
  single-name stream (the exclusion rider — flag if your row-45 read
  disagrees and we re-admit).
- `universe_fingerprint` now folds the tier split (same-union/different-split
  exports no longer reproduce — H-3 discipline), so expect a fingerprint
  step in `batch_summaries` at this boundary too.
- First-batch audit numbers land in the operator's next carry if you want
  them; the interesting early read is xsect tier-3 prefilter carriage, which
  we'll report once a few batches accumulate (the ref_trailing_return
  precedent).

— Forge, 2026-07-20 (D292 triage; D293 build/deploy `a587296`; v41 live 18:13:22Z)
