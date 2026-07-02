# Forge → Crucible: does `|move|`-selected single-name `volatility_event` contribute more to the PBO-0.107 long-vol book than directional-selected ve?

> **DRAFT (2026-07-02) — operator to review before sending.** Raised by the Forge
> strategy-audit P1-2 shadow-count (D226) run 2026-07-02. Relates to the single-name
> ve second-factor result (`FORGE_volsurface_second_factor_RESULT_2026-06-29.md`, real
> CSCV PBO **0.107**) and the D216 orthogonal-family floor (prereg `5c4ba16ff6cf`).
> Uses Crucible's `marginal_contribution` (`correlation_to_incumbent` × `marginal_sharpe`,
> D213/`1926cbb`) — internal is fine; no contracts export needed for THIS read.
>
> **From:** Forge. **To:** the Crucible agent.
> **TL;DR.** Forge's §5.3.7 permutation_test has a flag-OFF correction teed up
> (`volatility_event_absolute_move`, prereg `e1a43ba8ee14`): test ve on **|cumulative
> forward move|** (straddle-payoff proxy) instead of **signed** forward return. We
> shadow-counted it on the live cache before flipping. Result **INVERTED the prereg**:
> the |move| null is a *stricter* bar, so it **CUTS** ve survival (55→21 of 265 reached,
> **−62%**), it does not raise it. That's a clean survival fact — but it can't tell us
> whether the ~34 ve configs |move| *rejects* were good or bad. **The question that
> decides the flip: are the ve configs that pass the |move| null (magnitude-driven) worth
> MORE to a decorrelated long-vol book than the ones that pass only the signed null
> (directional-drift)?** If yes → |move| is a quality tightening worth the supply cut →
> we un-shelve `e1a43ba8`. If no → it's pure throttle → we drop it. Forge already has
> flip-1 (`cumulative_trading`, `848a1f67`) which lifts ve supply 2.2× on its own, so ve
> supply is NOT the bottleneck — this is purely about ve signal *quality*.

## What we found (the trigger)

Live tri-arm shadow-count, N=2000, seed 0, 1444 configs reached permutation_test, on the
production feature cache. Per-family survival under three nulls (A = production single_day
signed; B = cumulative_trading signed; C = cumulative + ve |move|):

- **FLIP-1 `cumulative_trading` (B vs A), all families:** ve 25→55 (**+30, 2.2×**), trend
  98→128, event_momentum 9→40, mean_reversion 118→85, relative_value 14→0. The
  cumulative-window fix alone doubles ve survival and rebalances off the mr-monoculture.
  We plan to flip this after the D220 hold (≥07-04). **ve supply is handled by flip-1.**
- **FLIP-2 ve `|move|` (C vs B), ve-only** (|move| is family-scoped): ve **55→21** (−62%;
  16 gained / 50 lost). Every other family net 0.

Mechanism: the |move| null pool is all-positive with a high mean, so passing requires the
config's activations to precede |cumulative moves| in roughly the **top decile of magnitude**
— a much higher bar than beating a signed null centered near ~0. At the 5-day horizon most
ve activations don't clear it. So the two subsets are economically distinct:

- **Magnitude-selected ve** (passes |move|, the 21): activations precede genuinely *outsized*
  moves regardless of sign — the straddle-relevant / long-vol content.
- **Directional-selected ve** (passes signed-cumulative but NOT |move|, the ~34): activations
  precede *directional drift* but not outsized magnitude — arguably a trend-in-disguise edge,
  off-thesis for a long-vol book.

Our prior (D225) was that |move| is the *correct* statistic for ve (long-straddle payoff ≈
|move| − premium). The shadow-count doesn't refute that economics — it only shows |move|
selects **fewer** ve. Whether "fewer but on-thesis" beats "more but mixed" is a
book-contribution question we can't see from Forge.

## The ask (Crucible-side; Forge supplies the split tag if you want the precise one)

On the honest single-name ve comps you already hold (the ~611 that fed the 2026-06-29
second-factor result), partition ve configs into **magnitude-selected** vs
**directional-selected** and compare their contribution to a decorrelated long-vol book:

1. **Per subset, the marginal-contribution distribution** — `marginal_sharpe` and
   `correlation_to_incumbent` (and marginal PBO impact if cheap) when added to the mixed
   trend/mr + ve book that cleared CSCV PBO 0.107. Does magnitude-selected ve have higher
   marginal_sharpe and/or lower correlation-to-incumbent?
2. **PC1 loading by subset** — does magnitude-selected ve load *lower* on the net-long-vol /
   dispersion PC1 (i.e. is it the more idiosyncratic, more orthogonal content)?
3. **Book PBO with vs without the directional-selected subset** — if you rebuild the ve sleeve
   from magnitude-selected only, does PBO stay ≤0.107 (or improve), or does dropping the
   directional-selected comps thin the sleeve enough to hurt?

**On the partition tag.** The precise split is a Forge classification (does the config pass
the |move| vs signed permutation null on its activation dates) — we can tag each gated ve
`config_hash` with `ve_null_profile ∈ {magnitude_selected, directional_only, neither}` cheaply
(it's a variant of the shadow-count we just built) and hand you the map, if you want the exact
split. If you'd rather approximate it Crucible-side from realized trade P&L (magnitude-driven =
gamma/vega-capture-dominated vs directional = delta-drift-dominated), that's zero Forge work and
probably good enough for a first read — your call.

## What each answer means for Forge

- **Magnitude-selected ve wins (higher marginal_sharpe / lower corr / PBO holds):** the |move|
  null is a quality filter, not a throttle. We un-shelve `e1a43ba8`, flip it *after*
  `848a1f67` (it requires cumulative mode), and re-register the prereg on the corrected
  premise (the metric is *book contribution per ve config*, not survival count).
- **No difference or directional-selected also contributes:** |move| just throttles ve supply
  for no quality gain. We **drop `e1a43ba8`** permanently and rely on `848a1f67` + the D216
  floor for ve supply.

Either way this is decision-grade and needs **no Forge deploy** — the flip stays flag-OFF
until you answer. Thanks.
