# Forge → Crucible: sector-ETF cross-sectional pre-check — measure before we build

> **⏳ STAGED 2026-07-12 — ONE cheap ask (§1). Awaiting operator relay**
> (`docs/tasks/crucible-handoff.md`).
>
> **From:** Forge — a measure-first stone, in the lineage of the GICS-relval "No"
> (`FORGE_gics_relval_inv1_2026-06-28.md`) and the held fundamental-value pre-check
> (`PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md`).
> **To:** the Crucible agent.
> **TL;DR.** An operator prompt ("sector ETFs like SOXL — is there a play?") surfaced sector axes we
> had never *isolated* as their own residual-IC experiment. A decorrelation-first literature sweep
> (see `SECTOR_VOL_MECHANISM_RESEARCH.md`) came back **NEGATIVE** on the sector-*volatility* axis —
> every candidate is VIX-collinear, off-mandate short-vol, already-refuted (D214), or
> momentum-adjacent — so no sector-vol pre-check is worth your time (§2). That leaves **one** cheap,
> never-isolated, low-prior stone worth a single measurement: sector-ETF cross-sectional **trend**
> (§1). Ingest/measurement on your side — **no Forge build, no bar moves** (hard rules 3/4/6/7
> intact). Mirrors `probe_sector_relval_decorr.py` verbatim; the IC pre-check is the gate, as for
> `iv_minus_rv` (D214), sector-relval (D215), and the earnings-yield stone.

## 0. Why this is worth one measurement (and why we are honest about the prior)

Sector ETFs (XLB/E/F/I/K/P/U/V/Y, SMH, SOXX, XBI — plus leveraged SOXL/TQQQ) are **already
enumerable underlyings** today; nothing about *trading* them is new. What has never been isolated
is whether a **sector-scoped** signal carries residual predictive power *after* the single-name
trend + mean-reversion core. The load-bearing lesson from D215 governs: **orthogonality needs a
different *mechanism*, not a re-grouping.** We split the two candidates on exactly that test:

- **§1 sector-ETF cross-sectional trend — LOW prior, cheap to settle.** This is a *re-grouping* of
  trend onto a sector-aggregate universe. Moskowitz-Grinblatt (1999) found industry momentum
  largely *subsumes* single-name momentum → we expect it to be **trend-collinear** (like
  sector-relval was MR-collinear). We ask anyway because it is the one structurally-enumerable
  sector axis we have never measured in isolation, and a clean "residual-IC ≈ 0" **definitively
  closes** the directional-sector door on data, not assertion.
- **§2 a sector-volatility mechanism — investigated, NEGATIVE, no ask.** For a buy-premium-only book
  the interesting sector signal would be volatility dynamics (spillover/lead-lag, sector-vol term
  structure, event-density) — a *different mechanism* from price trend/MR. A decorrelation-first
  literature sweep (`SECTOR_VOL_MECHANISM_RESEARCH.md`) found no candidate clears
  orthogonal-AND-long-vega-AND-cost-surviving: sector-ETF vol is VIX-dominated (already ours), the
  harvestable side of every vol-mispricing is short-vol (off-mandate), the one long-leg signal is
  the already-refuted `iv_minus_rv` family (D214), and lead-lag is momentum-adjacent + concentrated
  in illiquid names. So we send you **no** sector-vol pre-check — the axis is barren, not
  under-sampled.

## 1. The cheap pre-check (ready now; reuse the sector-relval harness verbatim)

Signal: **sector-ETF cross-sectional trend** — rank the sector/industry ETF sub-universe
(XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, SMH, SOXX, XBI) by `sma200_slope` (and, as a second
cut, `momentum_252`), same monthly non-overlapping 2018–2026 panel, same trend=`sma200_slope` /
MR=`rev_21` cores as `probe_sector_relval_decorr.py`. Report the same triple:

- **corr-to-trend, corr-to-MR, and residual-IC after trend+MR (t).**

Decision rule (the D215 "No" branch precedent):
- **residual-IC ≈ 0 / trend-collinear** (corr-to-trend ≫ the 0.30 ceiling, as we expect) → the
  directional-sector axis is genuinely exhausted on data; we record it and never revisit. No build.
- **residual-IC meaningfully nonzero + right-signed AND corr-to-core well under 0.30** → a surprise
  worth §2's shape gate. (We are not betting on this branch.)

We cannot pre-measure this ourselves: Forge has no return/correlation data at generation (D186) —
it is owned at assembly, your side. A sector-ETF-only rank *universe* would also be a Forge grammar
item (operator-gated v31), so we will not build it unless this measurement earns it.

## 2. The sector-volatility axis — investigated, no ask (see `SECTOR_VOL_MECHANISM_RESEARCH.md`)

We scoped the sector-*volatility* axis specifically to find a signal whose economic driver differs
from price trend/MR, survives VRP + single-name/ETF option costs for a buy-premium-only book, and is
expressible on a sector aggregate/reference (not short-correlation structure). The
decorrelation-first sweep (24 primary sources, 25 claims verified 3-vote) returns a **well-supported
negative** — the full verdict + citations are in `SECTOR_VOL_MECHANISM_RESEARCH.md`. In brief, every
candidate falls into a disqualifying bucket:

- **Cross-sector vol spillover** → sector-ETF vol is VIX-dominated (Bouri et al. 2021) — not
  orthogonal to `vix_level` / `vix_term_slope` / `market_realized_vol` you already serve.
- **Sector IV overreaction/reversal** (JoD 2017) → real IV-space mechanism, but the harvestable side
  is *short* vol; the long-vega leg is 0.11%/day at 10% sig, midpoint-priced (no costs), 1-day
  rebalance — dead net of ETF option spreads.
- **IV−RV / vol-surface** (Goyal-Saretto 2009) → this is the `iv_minus_rv` / `rv_rank` family you
  already measured and refuted (D214; `rv_rank` direction was backwards). Not new supply.
- **Sector lead-lag** → directional/momentum-adjacent (would collapse toward trend), intra-industry,
  concentrated in small/neglected illiquid names — absent in the liquid sector ETFs we'd trade.

Two angles (credit-implied vol, VRP term structure) were cut off by a session limit before
adversarial verification; their extracted evidence is already discouraging (CIV level is 81%
VIX-correlated; both premia accrue to the *seller*). Resume-to-close is available if you want it, but
the prior confirms the negative. **No sector-vol residual-IC ask follows — measured, not asserted.**

## 3. Scope — what this does NOT touch

- **No bar moves, no grammar loosening, no v2/Path-C, no spreads.** Measurement/ingest only.
- If §2 is positive, any Forge-side consumption (a registered, rank-coherent sector-vol indicator;
  a sector-ETF rank universe) is a **v31 grammar item, operator-gated**, and — because it would
  widen a rule's indicator pool — routes through `OPEN_PROPOSALS.md` (hard rule #4). Nothing here.
- **Hard rule #7 intact.** A sector-aggregate signal registered under `macro` (cf. `cs_dispersion`,
  `market_realized_vol`) is not an `equity` signal family; and a sector indicator *selecting option
  underlyings* is not equity exposure (cf. `days_to_earnings`). This ask asserts neither.

## Forge-side state for reference
- `grammar_version` **v30**; registry adopted from your latest snapshot. `cross_sectional_rank` is
  live over `trend_continuation` / `mean_reversion` / `event_momentum` (~73% of the stream), but has
  never been restricted to a sector-ETF-only universe — hence "never isolated."
- Prior in-v1 fronts, all closed on data: plain xsect relval (refuted, prereg `9b88966c446a`);
  sector-neutral GICS relval (No — residual-IC ≈ 0, D215); xsect `volatility_event` (fail-closed,
  directionally dead, D214). This pre-check adds the two sector axes those rounds never isolated.
- Standing operator directive `[[exhaust-long-options-before-v2-spreads]]`: we exhaust in-v1
  measure-first fronts before opening v2/Path-C. This is one such front.
- If §1 or §2 turns positive, Forge pre-registers the confirming claim (`forge prereg`, D208) on a
  post-cut cohort before any build, and charges it against the alpha budget (`forge alpha-budget`,
  D207) — every added primitive raises the null-max hurdle; the current standalone bar is honest
  cpcv-p25 ≥ 1.5 AND WF ≥ 2.0 AND sharpe_baseline ≥ ~1.25-and-rising.

*Relay status: §1 drafted 2026-07-12, §2 research-gated, awaiting operator relay. Lineage:
`FORGE_gics_relval_inv1_2026-06-28.md` → `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md` → this.*
