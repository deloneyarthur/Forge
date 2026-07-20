# Crucible ← Forge: grammar v22 → **v24** DEPLOYED (trend + MR slices). Ready to relay.

**Status: DEPLOYED 2026-07-07T15:05:50Z.** The whole `FORGE_signal_quality_champions_2026-07-03.md`
grammar upgrade shipped in one bump — the trend slice (D236, which had never shipped as a standalone
v23) plus the MR slice (D254) land together as `v22 → v24`. Relay per `docs/tasks/crucible-handoff.md`.

## What changed

**Trend (D236 — `rules:` text untouched, enumeration-policy):**
- **§2.1/§2.5** — `sma_slope` + `ad_slope` added as **percentile-only** trend directionals (our
  `option_momentum` pattern — top-decile of the trailing window; neither has a published value
  distribution our side, so no fabricated absolute range). `momentum_252` retained (learned weight
  ranks `sma_slope` against it — no hard swap).
- **§2.2** — pruned `returns_12m_skip1` (rank-corr 1.0 with `momentum_252`). **§2.3** — pruned
  `macd`/`ema_cross`(12/26)/`supertrend` as trend directionals.
- **§2.7** — `chandelier_exit` is now the default discretionary trend exit (dropped `parabolic_sar_exit`);
  it samples `atr_multiplier ∈ [2.0, 3.0]`.
- **§2d** — `days_to_fomc` event-proximity window tightened `(7,60) → (7,14)` (median firing ~10d, was ~31d).

**MR (D254 — the one `rules:` change, R1 loosening, operator-approved):**
- **§2b.1 R1** — admitted **`vol_regime`** as a fifth accepted `mean_reversion` regime gate, gated
  **`< 2`** (exclude the high-vol tercile), RAW discrete tercile (never `use_percentile`). Sampler now
  boosts `vol_regime`/`rv_rank`/`gamma_flip` and **biases away from `hurst`** (kept in the R1 OR at
  baseline weight — your null-to-negative MR-gate finding). `zscore_returns` retained (your §2b.1 #2
  by backtest — we did **not** apply the single-name §2b "drop"). `bb_pct` ranker preference is left to
  our learned directional weight.

**§2c.1 (2026-07-07)** — acknowledged; **no grammar change** (we never built a VE-direction lever). We
corrected an internal comment so the `days_to_fomc` tightening is attributed to the magnitude timer you
affirm, not the retracted call-wall direction.

## The ask

1. Once the **v24** stream accrues, run `crucible funnel --compare v22 v24` and report the cohort deltas
   for **both** `trend_continuation` and `mean_reversion` — **WF-median** and **CPCV-p25**.
   - **Trend:** your corrected §0 says `sma_slope` (as the ranker) **wins CPCV-p25 +18%** — we want to
     confirm the tail lifts (or at least does not drag) on the live cohort.
   - **MR:** your §2b.1 says `vol_regime<2` beats the `rv_rank` cost gate **+0.244 CPCV-p25** — confirm on
     the live `mean_reversion` cohort (and whether `vol_regime`-gated configs out-clear `hurst`-gated).
2. Honest expectation on our side (your §0/§4 + our [[promotion-gate-tiers-and-constraint]]): component
   selection/WF/tail should improve; the **portfolio promote rate** is bounded by the bear-hedge (trend)
   and correlated-core (MR) problems — we are not expecting the deploy alone to lift promotions.
3. If you'd rather we sample `sma_slope`/`ad_slope` on an **absolute** range than a trailing percentile,
   publish their value distributions and we'll recalibrate under a later bump.

**Deploy timestamp (v22 → v24):** `2026-07-07T15:05:50Z` — new daemon PID 1280850, `grammar_version=v24`,
`manual_bump` row recorded, `forge healthcheck` OVERALL=OK, contracts 1.26.0.
