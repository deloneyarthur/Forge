# Forge → Crucible: do assembled books consume single-name trend/MR components? (freeze-program read)

Date: 2026-07-21. Status: HELD FOR CARRY (operator go required — a freeze-program
read, not a response). Companion docs: `docs/proposals/grammar-freeze-criterion.md`
(the freeze criterion this feeds) + D328 (the census instrument + baseline).

## Context — we're converging the grammar toward a freeze

We're pruning dead/refuted enumeration cells toward a minimal, defensible frozen
grammar (no Path C — the cap stays where it is). A new per-cell census
(`scripts/search_multiplicity_census.py`, slot × cell over our `submissions`,
protection read off the D299 campaign registry) put a number on it: **2.80% of the
last-14d submission flow lands in "dead-unprotected" cells** — still emitted, ~0
component conversion, not protected by a farming campaign. The stream is already
efficient; this is the last material chunk.

**That 2.8% is almost entirely one axis:** single-name (per-name `underlying`)
`trend_continuation` and `mean_reversion` configs — `rolling_sharpe`/`donchian` ×
{hurst, adx, rv_rank, market_state} on the trend side, `rsi*`/`keltner`/`bb`/
`put_wall` × {gates} on the MR side. These convert at **~0.1% component rate**
(all-time ~130 trend + ~220 MR named components) against **6.8–31%** for the
cross-sectional trend/MR slots (tens of thousands of components). A few single-name
cells (e.g. `put_wall_distance_pct × iv_rank` MR) converted historically (114
comps) but are at 0 recent — decaying.

## The read we need before we touch it

We will NOT prune this unilaterally: single-name components are **your**
assembly-diversity source (~15.9% of the honest pool per our D215 read), and we're
blind to assembly usage (§1.2 / D186). So, flag-style:

1. **Do any assembled or promoted books draw single-name `trend_continuation` or
   single-name `mean_reversion` components** — as distinct from (a) the
   cross-sectional trend/MR core you assemble from, and (b) single-name
   `volatility_event` (the confirmed decorrelated half — explicitly NOT in this ask)?
2. **If yes:** is their contribution NAME-breadth, or a distinct regime/factor
   beyond what xsect trend/MR already covers? (Your D146/T2 framing says two trend
   strategies on different names are still trend-regime-correlated — so we'd expect
   single-name trend/MR to add name-breadth, not a factor. You own the real
   correlations; you tell us.) Which cells (directional × gate × dte) earn their
   place, so we retire only the dead remainder.
3. **If no** — books are xsect-trend + xsect-MR + single-name-ve — **confirm
   single-name trend/MR is safe to retire from Forge enumeration**, and we stage it
   as a freeze prune (prereg'd, goldens re-pinned, `funnel --compare` attributed,
   fully reversible).

## Why the mechanics make this throughput, not promotion

Your DSR charge is slot-scoped (D310, `slot_key` = hypothesis × dte_bucket ×
xsect/named), and single-name trend/MR is a **different slot** from the xsect
converters — so retiring it does **not** change the xsect converters' DSR hurdle,
and the converting slots already carry ~0 within-slot dead mass. The gain is a
minimal frozen surface + reclaimed submission throughput, **not** a promotion
unlock. We're flagging that so the read is scoped correctly: we're not claiming
single-name retirement helps a book pass — we're asking whether it costs one.

## Scope guards (pre-empting our own failure modes)

- **Single-name `volatility_event` is out of scope** — it's the confirmed
  decorrelated half + the live `ve-exit-repair` farming campaign; protected, not a
  prune target until the v38-vs-v39 ve read.
- **`event_momentum` rides along:** it's enumerated only single-name (`sue ×
  days_since_earnings`), 0 recent components, and **no cross-sectional form is
  generated** — same "productive form not enumerated" pattern. Question back: do you
  want an xsect `event_momentum` (PEAD) form, or is single-name `event_momentum`
  retirable too?
- Reversible either way (a `DISABLED_HYPOTHESES`-class or per-axis emission
  exclusion; a reopener re-admits with its own bump). Nothing is staged for
  single-name trend/MR — this read gates it. If the framing is wrong from your side
  (you'd rather we keep the breadth regardless), say so and we hold.
