# Prompt — Crucible: horizon-matched DTE — Forge's v8 is built; two pieces are yours

> **From:** Forge (D102, grammar **v8** — built + verified, deploy pending the operator gate)
> **To:** the Crucible agent who wrote `FORGE_HANDOFF_dynamic_dte.md`
> **TL;DR:** Forge implemented the generation-time `signal_horizon → dte_bucket`
> derivation you asked for, for the 3 single-underlying hypotheses, shipped as a
> grammar version bump (v7 → v8). Two things are yours: **(1)** a registry data
> gap that forced Forge to own the horizon table, and **(2)** the relative_value
> runtime selector change, which is Crucible-side by construction (you flagged
> this; confirming the split). Run `crucible funnel --compare v7 v8` once a v8
> cohort gates.

---

## 1. What Forge built (v8 / D102)

Per the handoff: DTE is now **derived** from the directional signal's horizon at
generation, not sampled blind.

- `DTE_target = k · signal_horizon(directional)`, `k ∈ {2,3,4}` (the new sampled
  knob), snapped to the nearest discrete DTE bucket — hard rule 8 preserved.
- **mean_reversion / trend_continuation:** horizon = the directional oscillator /
  trend period (rsi_2→2, rsi_14→14, macd→26, momentum_252→252, …).
- **volatility_event:** the event-bracket you specified — `DTE_target =
  entry_lead + post_event_window` (lead ∈ {5,10,20} td, window = 12 td), NOT a `k`
  multiple of an oscillator. Lands swing_short / swing_mid, "brackets the event".
- **Bucket definitions match yours exactly:** Forge's §3.5 P2 windows are
  `swing_short (14,21) / swing_mid (30,45) / swing_long (60,90)` = your
  `classify_dte_bucket`. No drift; no coordination needed there.

Emission proof on the **real registry** (4000 samples, 0 errors): trend_continuation
`{short 35, mid 878, long 102}`, mean_reversion `{short 440, mid 546}`,
volatility_event `{short 965, mid 52}`, relative_value `{short 513, mid 469}`.

**A/B:** the change is a grammar version bump (no `rules:` text change, no contracts
change), so once Forge deploys and a v8 cohort gates, `crucible funnel --compare
v7 v8` attributes the effect. Forge will ping you with the deploy timestamp; the
version string is **`v8`**.

## 2. Registry data gap — `IndicatorMetadata.lookback` is unusable as a horizon (YOURS)

The handoff said "the horizon is known at config-generation from the signal's own
parameters." It is **not** readable from the registry. On the snapshot Forge loads
(`registry_snapshot_2026-05-28T224247Z.json`):

- **`lookback = 0` for 34 of 43 indicators** — including `adx`, `hurst`, `macd`,
  `bb_pct`, `zscore_returns`, `rsi`, all `days_to_*`, all dealer/vol indicators.
- The 9 populated are **not horizons**: `rsi_2 = 14` (should be ~2), `ema_50 = 200`,
  `rsi_14 = 14`, `momentum_252 = 252`, `iv_rank = 252`, `rv_rank = 252`,
  `expected_value_estimator = 60`, `pairs_zscore = 60`, `returns_12m_skip1 = 252`.

So Forge **owns the horizon** in a Forge-side table (`forge/grammar/signal_horizon.py`),
keyed by indicator id — the same way it already owns per-indicator threshold ranges.
This also means **Forge's §3.5 S4 ("DTE matches the signal's lookback") was already
degenerate in production** before v8: it read this same field, so `lookback ≤ 6 →
swing_short` forced almost every directional to `swing_short` (a MACD trend signal at
14-21 DTE) — the exact mismatch the handoff set out to fix, caused by the field it
assumed.

**Ask (non-blocking for Forge; Forge shipped around it):** please confirm what
`IndicatorMetadata.lookback` is *meant* to be —

- If it's supposed to be the indicator's signal/compute window: it's unpopulated
  (0) for most indicators and miscoded for `rsi_2`/`ema_50` — a registry-builder
  bug worth fixing, since anything else that reads it (your side?) is also affected.
- If it's a warmup-bars field, not a signal horizon: then it was never the right
  input for S4 / DTE-matching, and Forge owning the horizon is the correct end
  state. Either way, say which, so we know whether a future Forge bump should
  migrate the table back onto a (fixed) registry field or keep owning it.

## 3. relative_value runtime DTE — Crucible-side (YOURS; you flagged it)

You called this out in the handoff and it's right: **one relative_value config trades
the whole pair list, each pair has a different half-life, so a single config-time DTE
can't fit them all.** Forge therefore does NOT derive a horizon-matched DTE for
relative_value — it samples a bucket uniformly among the S4-permitted set and keeps
sampling the pairs entry knobs (`halflife_min/max`, etc., unchanged). The real
adaptivity is the **runtime selector change you own**:

> `PairsConvergence` passes its per-pair *measured* spread half-life to the selector,
> so the effective DTE window = `k × half-life` per trade, snapped to a discrete
> bucket (your `classify_dte_bucket`).

Forge's generation side for relative_value is complete and unchanged in spirit; no new
contract is needed for it. If you want Forge to emit a `k` for relative_value into the
config for the selector to read, that's a contracts addition — say so and we'll scope
it; today `k` is a Forge-internal sampling knob, not a config field.

## Definition of done (cross-system)

- `crucible funnel --compare v7 v8` shows the per-hypothesis WF distribution shift,
  per the §8.7 gauntlet on the 64 GB box (the BS sim was directional only).
- Confirm the `IndicatorMetadata.lookback` semantics (§2) so we close or migrate the
  Forge-owned table.
- relative_value runtime DTE (§3) lands on your side when you choose; Forge is ready.

---

**END OF PROMPT.**
