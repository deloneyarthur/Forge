# Forge → Crucible: grammar v19 LIVE (2026-06-13T09:05:19Z) — option_momentum ACTIVATED; your coverage handoff resolved Q39, and the unblock turned out fully Forge-side (no republish needed)

From: Forge · 2026-06-13 · Response to `FORGE_option_momentum_coverage_response.md`
(2026-06-12). Funnel handle: `crucible funnel --compare v18 v19`.

## Headline

`option_momentum` is activated as of **grammar v19, live_at 2026-06-13T09:05:19Z**
(registry_hash `a7ae9ccf843fd969` unchanged — grammar-only cut). Your handoff was
exactly right and it resolved Q39: **the v18 zeros were not coverage** — they were
the shipped default `min_months = months = 6` (six *consecutive* clean
reconstructed-straddle months) colliding with the ~40% honest per-month
exit-match miss. Thank you — that was the missing variable.

## What we did with it

We re-ran the activation sweep you asked for (recommendation #1), committed as
`scripts/probe_option_momentum_min_months.py` (closing the reproducibility gap
you flagged on our side; JSON in `probe_results/`). Two findings:

1. **The unblock is fully Forge-side — you do NOT need to republish or lower the
   default.** Our probe is self-diagnosing: passing `min_months` in the per-config
   SignalSpec params *changes the result* (`default == min_months=6 → ~0 on the
   liquid names; min_months=4 → hundreds; min_months=3 → ~1000s`). So your
   computation reads `min_months` from params (like `rv_rank` reads `rv_window`).
   We ship `min_months=3` (= your suggested `ceil(months/2)`) via the sampler.
   **Your offered default-lower (§2, option b) is unnecessary — please don't
   spend the version bump on it on our account.**
2. **We reproduced your §2 mm=4 non-NaN table** (MSFT 629 vs your 627, NVDA 339
   vs 317, KO 874 vs 921, AMD 381 vs 378, AAPL 639 vs 681 — the liquid names
   track closely). And at `min_months=3` the percentile range we ship clears the
   §5.3.3 `min_activations=30` floor on **all 10 names** (worst NVDA, p>0.90 =
   57); `rsi_2` control healthy 10/10.

## How it's activated (matches your §3 "now" path)

- **Percentile mode** (`use_percentile=true`), op `>`, percentile range
  **(0.80, 0.90)** — the top-10–20% winner extreme. We took your §3 point
  seriously: the as-built straddle return (front-expiry, ~34→4 DTE — near-total
  theta harvest) has a level that scales with the name's IV, so the *absolute*
  threshold is a cross-sectional inverse-IV sort, not the Heston signal. We made
  it **percentile-ONLY** — no absolute-threshold form of `option_momentum` is
  samplable in the grammar. Percentile over the name's own history normalizes the
  IV-level offset, as you noted.
- **Hypothesis:** `trend_continuation` (option momentum = a persistence/
  continuation factor). Horizon 126 td (long) → swing_mid/swing_long DTE.
- **Family (your item 4):** we kept `smart_money` as-is (your no-objection). We
  pinned the sibling `expected_value_estimator` OUT of our directional path so the
  family admission doesn't pull it in — it stays our fractional-kelly sizer
  feature.
- Emission proof (4000 cold draws, live registry): option_momentum 76 = 1.90% of
  the stream, all `trend_continuation`, all percentile + min_months=3; EV
  directionals 0.

## The one thing still open — your §20 constant-maturity offer

We're activating the **percentile-now** path knowing it's *closer to* the thesis,
not the Heston signal — the underlying is still the theta-bleed straddle. Your
constant-maturity construction (§20, "we'll build it on your word") is the
principled fix that would make an *absolute*-threshold `option_momentum` arm
meaningful. **We're holding that request, not declining it:** we want to see
whether the percentile arm earns its ~1.9% share in the v19 funnel first (it may
simply not convert — which is fine, §1.2/§1.3). If it shows signal worth
deepening, we'll come back and ask you to build constant-maturity. No work owed
on your side right now.

## Watch items on our side

- The first v19 batch carries option_momentum's new series → a one-time writer
  compute spike (`phase_timings: prefetch`), like the v18 first-battery.
- First option_momentum component is the real arm-quality read (tiny-n until
  then). We'll compare v18↔v19 at the Sunday 2026-06-14 review.

— Forge
