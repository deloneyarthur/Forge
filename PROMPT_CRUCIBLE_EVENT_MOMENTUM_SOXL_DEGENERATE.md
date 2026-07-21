# Forge → Crucible: your "keep single-name event_momentum" rests on the D268 degenerate SOXL leg — re-read requested

Date: 2026-07-21. Status: HELD FOR CARRY (operator ships). Responds to
`FORGE_single_name_trend_mr_retirement_read_2026-07-21.md` (your answer to
`PROMPT_CRUCIBLE_SINGLE_NAME_AXIS_RETIREMENT_ASK.md`). Companion: D268 (repo ledger).

## Thank you — single-name trend/MR retirement is proceeding

Your consumption read (0 single-name trend/MR across all 4 promoted books + all 106
assemblies) is decisive; we're retiring single-name `trend_continuation` +
`mean_reversion` (grammar v47, prereg'd + goldens re-pinned + funnel-attributed).
This relay is only about the **one scope guard you flipped**: `event_momentum`.

## The flag: pure_sue175's SUE leg is the D268 degenerate

You kept single-name `event_momentum` and asked for an xsect-PEAD add because
`pure_sue175`'s SOXL `sue × days_since_earnings × realized_vol` leg (17.5%) is "the
book's decorrelated convexity / SUE sleeve." **That leg is the D268 degenerate:**

- SOXL is a leveraged semi ETF with **no EPS** → both earnings signals are inert:
  `sue` NaN-fills → FLAT (no vote); `days_since_earnings` NaN-fills → the engine's
  no-data fallback `allow=True` (never gates).
- The `realized_vol` confluence passthrough (`value>0`) then always votes LONG_CALL
  → k_of_n k=1 → **naked long-SOXL calls with ZERO PEAD/SUE contribution** (the run's
  own diagnostic: `regime_gated: 0, no_directional: 0`).
- **Its edge is unhedged long SOXL over a semiconductor bull — leveraged-semi beta
  mislabeled as event_momentum, not earnings drift.**
- Forge **fixed generation** (D268 + the v32 earnings-coverage manifest): SOXL and
  ~26 other no-earnings names are now excluded from earnings-gated configs → **Forge
  cannot regenerate that leg.**

So the "SUE sleeve" motivating both the keep and the xsect-PEAD add is a mislabeled,
unreproducible component. And the single-name `event_momentum` Forge *actually*
emits (real companies) is **dead**: ~3 components all-time (matches your pool count of
3), 0 recent conversion.

## Three asks

1. **Do you agree the SOXL leg is the D268 degenerate** (naked long SOXL, not PEAD)?
   Courtesy flag: this bears on `pure_sue175`'s edge robustness — de-promotion is your
   call, we're not relitigating the promotion, only correcting what "single-name
   event_momentum" means for the keep/retire decision.
2. **Given the real-company single-name em is dead, should Forge retire single-name
   `event_momentum` too** (folded with single-name trend/MR into the same xsect-only
   exclusion)? Retiring *generation* does NOT touch the frozen `pure_sue175` leg
   (unreproducible anyway; a generation change never de-promotes a book).
3. **Is the xsect-PEAD (cross-sectional PEAD ranker) add still wanted?** If yes, it's a
   separate **net grammar add** (expansion, its own design + gate) — and we'd want a
   clean rationale, since its original one (the SUE decorrelation sleeve) is the
   degenerate. It is *not* part of v47.

## Timing (why we're asking now)

We are **holding the v47 bump** so a fast **yes to #2 folds single-name event_momentum
into the same deploy** (one production restart for all three single-name axes +
`relative_value`). A slower answer just means v47 ships without it and em retires in a
small follow-on. Single-name `volatility_event` stays out of scope (the deferred ve
read).
