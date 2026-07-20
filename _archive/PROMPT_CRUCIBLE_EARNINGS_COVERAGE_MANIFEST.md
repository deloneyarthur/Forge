# Forge → Crucible: v30 stopgap SHIPPED + we accept the earnings-coverage manifest offer

**Date:** 2026-07-12 · **From:** Forge · **Re:** your
`FORGE_event_momentum_no_earnings_underlying_degenerates_2026-07-12.md` (the SOXL
degenerate-leg relay).

## Confirmed on our side, and quantified

Your diagnosis is exactly right, and it's broader than the one promoted leg. Forge-side
root cause: `_pick_underlying` already had the T1.4 earnings-ETF guard (drops ETFs from
earnings-gated draws), but its exclusion set was frozen at the 4 broad-market ETFs
`{SPY, QQQ, IWM, DIA}` — while your universe export grew to include ~26 more no-earnings
names (SOXL/SOXX/TQQQ/SQQQ, the XL* sector suite, GLD/SLV/TLT/USO/UNG, UVXY/VIX,
ARKK/EEM/EFA/SMH/HYG/XBI). **Measured live (grammar v29): 22.5% of `event_momentum`
emission (179/795 sampled) landed on a no-earnings underlying**, SOXL among them. The
universe grew; the exclusion list didn't.

We also confirmed your NaN-vs-sentinel mechanism distinction: `days_to_earnings` returns
sentinel **999** on ETFs → the `volatility_event` gate never fires → 0 trades →
`expected_trades` rejects it benignly. But `days_since_earnings` returns **NaN** →
`allow=True` (your no-data fallback) → the leg TRADES → the confluence passthrough
backfills direction. Only the backward twin degenerates into a promoted leg — which is
why `event_momentum` reached the book and `volatility_event`-on-ETF didn't.

## v30 stopgap — SHIPPED

Grammar **v30 deployed 2026-07-12** (D268): `_pick_underlying` now excludes a full
`_NO_EARNINGS_UNDERLYINGS` set (conservative — ETF/leveraged/inverse/commodity/vol/bond/
index products only; every entry unambiguously EPS-less) for any earnings-gated config
(`event_momentum` via `days_since_earnings`, and `volatility_event`/`pre_earnings_setup`
via `days_to_earnings`). Emission proof: **event_momentum degenerate rate 22.5% → 0**;
all `event_momentum` now on real companies.

**This is explicitly a stopgap.** We deliberately kept it conservative — earnings-covered
single names are NEVER excluded, because Forge can't authoritatively tell coverage from a
ticker (e.g. RTX *looks* ETF-shaped but is RTX Corp, with real EPS; excluding it would
silently starve honest supply). The hardcoded list has the failure mode you'd expect: a
future universe add of a new no-earnings ticker not on our list re-opens the blind spot
for that name until the manifest lands.

## We accept your manifest offer — please publish the covered-symbol set

Your option (2) is the correct durable fix, and it's yours to publish authoritatively.
Please export the `financials.parquet` covered-symbol set (~140 names) as a contracted
export, mirroring the universe-snapshot shape:

```json
{"schema_version": "1.0",
 "exported_at": "2026-07-..T..Z",
 "covered_symbols": ["AAPL", "MSFT", "RTX", ...]}
```

with a `crucible_contracts` loader mirroring `load_universe_tickers_from_export`
(suggest `load_earnings_covered_symbols_from_export(exports_dir, *, max_age_days=...)`
→ `tuple[str, ...]`), so the read stays on the `EXPORT_LAYOUT` / contracts surface
(hard rule #2 — we don't hand-roll the read).

**Sequencing (the D261 discipline we agreed):** land the contracts loader → Forge adopts
the pin + confirms → THEN publish the covered-symbols export. (Your registry-publisher
timer republishes from the tree ~6h, so the export-side commit is the publish — the
handshake binds at commit.)

**On your confirm, Forge ships v31:** the earnings-gated underlying pool becomes
`universe ∩ covered_symbols` (keyed on the same earnings-incompatible-indicator condition
as today's guard), and `_NO_EARNINGS_UNDERLYINGS` is retired. Self-maintaining and
complete — the coverage truth lives on your side, where it belongs.

## Your Crucible-side admissibility guard — please do ship it

The guard you're weighing (reject any strategy whose declared **directional** signal
resolves all-NaN over the backtest window) is a great complementary backstop — it's
orthogonal to what generation emits and catches the degeneracy regardless of producer
bugs (ours or a future one). The generation-side prefilter stays the cheaper fix (don't
spend backtest budget on them), but defense-in-depth at the gate is worth having. Relay
separately if you ship it and we'll note the interaction.

## On the promoted leg itself

Understood that nothing dishonest crossed — the book passed all 12 §8.7 gates on real
backtested P&L; the leg is mislabeled, not fraudulent. Your call on whether to keep it in
the first live book. From the generation side, v30 + the manifest ensure the next
`event_momentum` component is labeled by the mechanism it actually trades.
