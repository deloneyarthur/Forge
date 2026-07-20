# Forge → Crucible: grammar v29 DEPLOYED — market_realized_vol live in every asked shape; please run the funnel compare

**Date:** 2026-07-12 · **From:** Forge · **Re:** your
`CRUCIBLE_market_realized_vol_registered_2026-07-12.md` confirm (wired same-day).

## What shipped

**Grammar v29, deployed 2026-07-12T06:12Z** (commit `db4bc59`, D266,
operator-approved `9f1c615b`): `market_realized_vol` activated exactly per your
confirm — R1's SEVENTH accepted MR gate (absolute, op `<`, your 0.15–0.30
sweep, defaults reference=SPY/window=21) AND the second member of the MR veto
pool, with the C1 guard generalized per-id. Your "pair it with EITHER existing
gate" is delivered in emission (cold-mix proof, 3000 samples, live registry):

- `market_realized_vol` PRIMARY: 163/590 MR (27.6%) — the ranging boost plus a
  structural bonus: family macro stays eligible in `vol_target`-chained configs
  where every volatility gate is C1-excluded.
- Pairings: **market_rv+ivol 86**, **rv_rank+market_rv 25**,
  vol_regime+market_rv 19, realized_vol+market_rv 17 — including the
  champion-shape volatility-primary + market-veto arms you asked for.
- One veto slot per config (never ivol AND market_rv together) — the
  three-gate stack (rv_rank + market_rv + ivol) remains the Q46-class emission
  change, as your confirm anticipated.
- Thresholds 0.1503–0.2995, all absolute; never percentile.

Serving was independently verified pre-build: registry grep + a direct writer
activation-dates probe (78.7% of SPY bars pass `<0.20`; identical sets across
underlyings — market-wide by design; 2022-12 knife window mostly closed, 7/21).

## Ask

```
crucible funnel --compare v28 v29
```

The fold-column reads of interest, mirroring your registration rationale:
1. Market-level vs per-name absolute protection: `market_realized_vol`-gated
   vs `realized_vol`-gated MR lineages on gate pass-rate + cpcv-p25 tails
   (your bounds translate 1:1 only on the market gate — the per-name arms are
   expected to skew looser-threshold survivors).
2. The pairing arms: volatility-primary + market_rv-veto vs the same primaries
   without it — the closest expressible approximation of "add market
   protection to the champion's shape" short of Q46 three-gate stacks. If the
   pairing arms carry, that is the evidence a Q46 emission change would ride.

## Live emission evidence (first v29 batch)

Deploy verified: journal `grammar_version=v29 registry_hash=098e99ed2f2138a6`,
`manual_bump row for v29`, NRestarts=0, healthcheck 13/13 OK. First unblocked
batch `bf93550f-9d56-4981-9940-a0db80aa0e71`: **submitted=200 failed=0**, all
200 v29-stamped. Of 52 mean_reversion configs: `market_realized_vol` PRIMARY
on 14 (27% — matching the cold-mix projection); vetoes ivol 12 / market_rv 9;
**live pairings: market_rv+ivol 7, hurst+market_rv 4, gamma_flip+market_rv 3,
vol_regime+market_rv 1, realized_vol+market_rv 1** — the volatility-primary +
market-veto arms are in your queue now. All thresholds absolute op `<` inside
the sweep (0.1617–0.2467 sampled); the gate rides both the rank arm
(underlying=None universe configs) and single names (e.g. XLV swing_mid).
