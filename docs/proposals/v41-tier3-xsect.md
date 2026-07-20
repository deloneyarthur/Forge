# v41 proposal — tier unpin: contracts 1.32.0 adoption + true-tier stamping + xsect tier-3 exploration share (STAGED, operator-gated)

Source: Crucible `FORGE_tier_unpin_and_promote_2026-07-20.md` (their D291 reply;
contracts 1.32.0 shipped their side, fold held until our adoption confirm).
Triage: D292. Status: **staged, awaiting operator go** (grammar bump + contracts
pin bump + restart — one deploy window covers all of it).

## What their reply established (all verified, D292)

- Tier-3 names ARE in our pool (folded `tier_2` export key since ca51d35);
  single-name tier-3 coverage exists and is largely structurally dead.
- The real pin is the literal `tier=2` STAMP. Cross-sectional cost: their
  engine resolves the xsect ranking pool from the stamp against PIT
  membership, so every xsect config we ever emitted ranks the TRUE 20-name
  curated tier-2 pool — rank_k=20 rank-then-takes the entire pool (zero
  selectivity), and the 94-name tier-3 xsect pool has never been sampled.
- Their census: rank_k=20 is the best band in both trend and MR swing_mid
  (~26%) — on a pool where it currently selects nothing. The tier-3 xsect
  pool is where that band gets real selectivity.
- Honest framing (both sides agree): supply diversification / coverage axis,
  not a promotion thesis. The xsect-pool point is the one place it could be
  more.

## The change set

1. **Contracts pin 1.31.0 → 1.32.0** (pin-only class, D267 precedent — minor
   gap does not hard-fail, so this is hygiene riding the same window).
2. **Reader switch:** `_load_underlyings` moves to
   `load_universe_tiers_from_export`; the sampling pool stays the IDENTICAL
   118-name union (verified: both readers agree on the live export), so the
   pool itself is a no-op. The loader now also exposes true tier membership
   to the sampler. D033 fallback unchanged.
3. **True-tier stamping (single-name):** a single-name config stamps the
   underlying's true tier (2 or 3) instead of the literal 2. Attribution fix;
   no engine-behavior change for single-name (their note). This changes
   config bytes → config_hash for tier-3-name genomes (funnel discontinuity
   at the v40/v41 boundary — flagged in the relay; grammar_version splits it).
4. **Xsect tier-3 exploration share:** 15% of cross-sectional draws stamp
   `tier=3` (inside their 10–20% band) — the engine then ranks the 94-name
   tier-3 PIT pool (their step: engine already resolves tier-3 membership
   today). The other 85% keep tier=2 (the true 20-name curated pool, as
   today). Xsect-first per their suggestion; single-name draw shares are NOT
   changed (coverage exists; the learned weights already price those names).
5. **Rider — ASML + COST join `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS`**
   (auto-tightening class): our funnel — ASML 641 decided / 0 components,
   COST 1,544 / 1 (0.06%) — the same dead-cell class as the v37 six.
   Flagged for Crucible's row-45 cross-check in the relay; drop the rider if
   their preflight disagrees.

## Determinism / test surface

- Version bump v41 mandatory (stamping + new draw change bytes and the rng
  stream at xsect cells). Goldens: expect re-pin via the environment-matched
  harness; divergence onset = first xsect draw (or first tier-3-name
  single-name config via the stamp). The universe fixture pin
  (`UNIVERSE_SNAPSHOT_2026_07_16`) is tier-blind — tests need a tiered
  fixture extension mirroring the 4/20/94 shape.
- New tests: xsect tier-3 share ~0.15; single-name stamps true tier; pool
  union unchanged vs old reader; exclusion rider; capitulation/ve/trend cells
  untouched (control).

## Sequencing (one deploy window)

preflight → stop → pin bump + v41 bump + archive in the down-window →
uncontended suite → commit → start → verify journal (contracts 1.32.0 line,
v41 stamp, first-batch xsect tier mix ~15/85, tier-3 single-name stamps) →
**relay adoption confirmation so Crucible retires the fold** (their old-reader
shrink hazard disappears once we're on the new reader).

## Watches after deploy

- First-batch audit: xsect tier=3 share, true-tier single-name stamps,
  prefilter carriage on tier-3 xsect (report the rate like ref_trailing_return).
- Their `funnel --compare v40 v41` once mature; the v39→v40 MR read
  (~07-22/23) is unaffected (MR exit changes predate this).
