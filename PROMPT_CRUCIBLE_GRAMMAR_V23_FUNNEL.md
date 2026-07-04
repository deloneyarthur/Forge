# Crucible ← Forge: grammar v22→v23 (trend directional pool). SEND AFTER DEPLOY.

**Status: DRAFT — do not send until v23 is deployed and the stream is accruing v23 configs.**
Fill the deploy timestamp below, then relay per `docs/tasks/crucible-handoff.md`.

## What changed (enumeration-policy bump; `rules:` text untouched)

Implements your `FORGE_signal_quality_champions_2026-07-03.md` asks on the `trend_continuation`
directional pool (Forge D236):

- **§2.1/§2.5** — added `sma_slope` + `ad_slope` as trend directionals. They are **percentile-only**
  (our `option_momentum` pattern: fire when the slope ranks in the top decile of its trailing
  window), because neither has a published value distribution on our side — so we did **not**
  fabricate an absolute threshold range.
- **§2.2** — pruned `returns_12m_skip1` from the directional pool (rank-corr 1.0 with `momentum_252`).
- **§2.3** — pruned `macd` / `ema_cross`(12/26) / `supertrend` as trend directionals.
- `momentum_252` **retained** — our learned directional weight ranks `sma_slope` against it on live
  evidence rather than a hard swap.

Cold-start emission (seed 0): trend directional mix is now `donchian / momentum_252 / sma_slope /
ad_slope / rolling_sharpe / option_momentum`, roughly uniform until the learned weight adapts.

## The ask

1. Once the v23 stream has accrued, run `crucible funnel --compare v22 v23` and report the
   **`trend_continuation` cohort** deltas — specifically **WF-median** and **CPCV-p25**. Your §0
   predicted WF-median +2.5% but CPCV-p25 flat-to-−3.6%; we want to confirm the tail did not drag
   (this is the one number that would make us reconsider — we deployed it as hygiene, not a lever).
2. If you'd rather we sample `sma_slope`/`ad_slope` on an **absolute** range than a trailing
   percentile, publish their value distributions (as you did for `iv_term_slope` in
   `INDICATOR_THRESHOLDS.md`) and we'll recalibrate under a v24 bump.

**Deploy timestamp (v23):** `<FILL ON DEPLOY>`
