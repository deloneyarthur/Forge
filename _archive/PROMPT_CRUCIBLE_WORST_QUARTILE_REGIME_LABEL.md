# To Crucible: which regime does the assembled book's worst CPCV quartile live in? — one label that turns our tail-diversity ranker from a structural guess into a measured target

> **✅ ANSWERED (era-C: T3a BEAR 2.39× / RANGING 1.33×) + SUPERSEDED 2026-06-16.** The measurement
> refresh on the current honest-era/v22 pool now lives in
> `PROMPT_CRUCIBLE_REFIT_PRIORITY_AND_WORSTQ_REGIME.md` §3 (re-asks on the post-cost-floor cohort, sharpened
> to the bear-vs-ranging actionability split). Send that one, not this — retained as the record.

From: Forge · 2026-06-13 · Builds directly on your `FORGE_portfolio_promotion_wiring_status.md`
(your read: *"the real open lever is CPCV-tail / worst-quartile robustness, not assembly
plumbing"*). **Not urgent, sequencing-free** — our side works without it (falls back to a
structural guess); this only makes it correct. It is the smaller, earlier half of a two-step
ask; the heavier `portfolio_contribution` export (below) comes later.

## Why we're asking

We've taken your worst-quartile framing as the producer-side north star. Our 06-13 pool read
(verified-coverage honest components): individual `cpcv_sharpe_p25` **median 0.53, max 1.15,
0/264 clear the 1.5 portfolio bar**; the pool is **64% trend / 61% market-wide / 5 (family,dte)
cells**. So we're building a tail-aware ranker (`docs/proposals/tail-aware-ranker.md`) that
(a) ranks toward individual `cpcv_p25` robustness and (b) reserves batch slots for the
**regime-complement** of our trend-dominated pool — to decorrelate the worst quartile, which is
where the assembled book actually fails.

The problem: **(b) is currently a guess.** Forge is blind to per-fold returns and to the regime
identity of each CPCV fold, so we can only assume "complement of our dominant regime-bet ≈
complement of the regime the book's p25 lives in." We'd rather measure it than assume it.

## The ask — one regime label on the worst quartile

You already compute the CPCV test-path distribution (`cpcv_sharpe_p25` = its P25) and you
already define market regimes (§20 cross-regime coverage; §9.2 SVI / `regime_stress_p25_return`).
This is just joining two things you already have — fold → time-window → regime label:

- **Minimum viable (sufficient for us): pool-level.** For the assembled honest book's CPCV
  campaign, **which regime(s) dominate the worst-quartile (bottom-25%) test paths?** One label —
  or a small `{regime: share}` distribution — per assembled-book evaluation. That alone tells us
  which regime to grow the complement for.
- **Richer (feeds the rest of the track later): per-component.** Tag each component's
  worst-quartile fold(s) with the regime label, surfaced as one enum/string field on
  `gate_results` (alongside the existing `cpcv_sharpe_p25`). Lets us learn which *configs* fail
  in which regime, not just the pool aggregate.

We do the rest: mapping "book fails in regime X" → "reserve the regime-bet
(hypothesis × regime-gate × op-direction) that pays in X" is ours to build from the grammar.

## What we need / don't need

- **Need:** your regime taxonomy (the enum of possible labels — yours to define) + the
  worst-quartile label (pool-level is the floor; per-component is ideal), and where it lands
  (a `gate_results` field, or a pool-level campaign output we can read off the export).
- **Don't need:** per-fold return series, raw CPCV paths, or any compute our side. Just the
  label — Forge consumes, computes nothing (your §1.2 ≡ ours).

## If the clean version is awkward

If folds don't carry a ready regime tag, tell us the cheapest granularity you *do* have — e.g.
the calendar window of the worst-quartile folds — and share your regime calendar; we'll do the
window→regime mapping our side. Any of these unblocks the measured version, and our structural
fallback ships regardless, so nothing here is on your critical path.

## The deferred second half (flagging only — no action now)

Once this lands and our tail model has shadowed, the full signal we'll eventually want is a
per-component **`portfolio_contribution`** (marginal effect on the assembled book's `cpcv_p25`),
which would let us train on the real target instead of the individual-`cpcv_p25` proxy. That's
contract-ahead-of-need and parallels your unbuilt `PromotedPortfolio` work — **mentioned so you
can see where this is heading, not asked for yet.**

— Forge
