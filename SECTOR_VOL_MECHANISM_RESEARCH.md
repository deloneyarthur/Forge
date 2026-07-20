# Sector-signal research verdict — DON'T-BUILD (a sector *grouping* is not a new mechanism)

> **Verdict (2026-07-12): NEGATIVE.** No sector-specific signal clears the bar of
> *orthogonal-to-trend/MR* **AND** *long-vega-expressible* **AND** *survives VRP + option costs*.
> Sector ETFs are already tradeable underlyings (SOXL + 12/14 sector ETFs live); the question was
> whether a **sector-aware signal** adds an orthogonal driver. It does not. Every candidate the
> literature offers falls into one of four disqualifying buckets (§2). This reinforces the D215
> doctrine verbatim: **a re-grouping of an existing driver adds no dimension — orthogonality needs a
> different *mechanism*, and the genuinely-different mechanisms in vol-space are structurally
> short-vol, which a buy-premium-only book cannot harvest.**
>
> Trigger: operator prompt ("after seeing SOXL, is a sector-ETF play worth testing?"). Method: a
> decorrelation-first deep-research sweep (6 angles, 24 primary sources, 25 claims adversarially
> verified 3-vote) + the internal prior-art record (D214/D215, GRAMMAR_REVIEW §4.2). This is a
> research verdict, not a build and not a bar move (hard rules 3/4/6/7 intact).

## 0. What the question actually was

Not "can we trade sector ETFs" (we already do — they're Crucible-universe underlyings). The real
question: does a **sector-scoped signal** — sector momentum, sector-vol spillover, sector-IV term
structure, sector event-density, etc. — carry residual predictive power *after* the single-name
trend + mean-reversion core, in a form a **long-vega, defined-risk, buy-premium-only** book can
express? The gate is the same measure-first residual-IC pattern that closed sector-relval (D215)
and `iv_minus_rv` (D214).

## 1. Candidates evaluated (each mapped to the mandate)

| Mechanism | Genuinely different from trend/MR? | Long-vega-expressible? | Survives cost/VRP? | Verdict |
|---|---|---|---|---|
| Sector cross-sectional **trend** (§ pre-check) | No — industry momentum *subsumes* single-name momentum (Moskowitz-Grinblatt 1999) → trend-collinear | directional, not vega | — | **re-grouping** — expected residual-IC ≈ 0 |
| Sector **IV overreaction / reversal** (JoD 2017) | Yes — an IV-space mechanism, not price | harvestable side is **short**-vol; long leg weak | No — see below | **off-mandate** |
| Cross-sector **vol spillover / contagion** | No — dominated by the market/VIX factor | — | — | **already owned** (vix_level, vix_term_slope, market_realized_vol) |
| Sector rotation **lead-lag** | Directional/momentum-adjacent; intra-industry | directional, not vega | weak in liquid names | **momentum-adjacent + wrong universe** |
| IV−RV / vol-surface cross-sectional (Goyal-Saretto 2009) | vol-mispricing, not price | long leg separable | already-refuted internally | **already tested** (= `iv_minus_rv`, D214) |
| **Credit-implied vol** (CIV, FAJ 2025) | partially — CDS tail info | harvestable side is short-vol | level is VIX-collinear | **thin residual only** (unverified — §3) |

## 2. The four disqualifying buckets (why the whole axis is barren, not under-sampled)

1. **Already owned by Forge.** Sector-ETF volatility is dominated by a common market-vol factor.
   *"The 30-day forward looking expectations of US stock market volatility (VIX) has the strongest
   effect on US sector equity ETFs in both short and long runs"* (sciencedirect S0140988321001833,
   3-0). Forge already carries this via `vix_level`, `vix_term_slope`, `market_realized_vol`,
   `market_state`. A sector-vol level/spillover signal is not orthogonal to what we have.

2. **Off-mandate (structurally short-vol).** The harvestable side of every vol-mispricing sector
   mechanism is *selling* vol. Sector IVs overreact and **reverse** → the profitable side is fading
   the spike (JoD 2017, jod.pm-research.com/content/25/2/22, 3-0). The long-vega side is weak:
   *"Long DH Straddle return… 0.11%\* per one-day holding"* (10% sig) vs the short side *"0.29%\*\*"*
   (5% sig) (aaltodoc replication, 3-0). Same shape for the credit-vol premium (accrues to the
   protection *seller*) and the VRP itself (negative for ~19/20 asset classes → a buyer pays it).

3. **Already tested internally and refuted.** The one longer-horizon vol-surface signal with a real
   long leg — Goyal-Saretto IV−RV mean-reversion (the long leg is *"9.7%"* of a *"19.1%"* 47-day
   return, UCLA `cross_options.pdf`, 2-1) — is the `iv_minus_rv` / `rv_rank` / `iv_term_slope`
   family Crucible already measured and largely refuted (D214; `rv_rank` straddle direction was
   *backwards*). Not new orthogonal supply, and not sector-specific.

4. **Momentum-adjacent + wrong universe.** Sector lead-lag is a *directional* return-predictability
   effect (gradual information diffusion — Hong-Torous-Valkanov), not a vol signal, so it would
   collapse toward the trend factor. And it is *"predominantly an intra-industry phenomenon"* (RFS
   20(4), 3-0), *"concentrated in small, less competitive and neglected industries"* (2-0) — i.e.
   weak/absent in the large, liquid, options-eligible sector ETFs the book would actually trade.

**Cost overlay (applies to buckets 2-4).** Every headline result is computed at bid-ask *midpoints*
with no spreads deducted (aaltodoc, 3-0); a 0.11%/day edge at a 1-day rebalance does not survive
real sector-ETF option spreads. Post-publication decay compounds it (~58% haircut, McLean-Pontiff,
jofi.12365). One tailwind worth noting: the historical VRP that penalized option *buyers* has
decayed toward zero since ~2012 (Chicago Fed 2025) — but that lowers the *cost of being long vol*
generally; it is not a sector edge.

## 3. The thin residual threads (honest incompleteness)

The sweep hit a session limit before the **credit-implied-vol (CIV)** and **VRP-term-structure**
angles finished adversarial verification (8 claims errored, unverified; the synthesis step was
skipped). Their own extracted evidence is already discouraging, so the verdict is unlikely to flip:
- **CIV (Kelly-Manzo-Palhares, FAJ 2025, ssrn 2576292).** Genuinely distinct source (CDS-implied
  tail info not in equity options) — but the *level* factor is *81.2% correlated with VIX* (not
  orthogonal), and the tradeable premium *accrues to the protection seller* (short-vol). Only the
  residual CIV *shape* factors could be orthogonal — thin, and not obviously long-vega-harvestable.
- **VRP term structure / dealer-inventory driver** — the mechanism is distinct (dealer positioning,
  not price) but it is a premium a long-vol buyer *pays*, not earns.

If the operator wants belt-and-suspenders, resume the workflow after the limit resets to close
these two (`resumeFromRunId` — cached agents replay free). Prior: confirms the negative.

## 4. Recommendation

- **Do not build a sector-vol indicator.** The axis is barren for a long-vega book, not
  under-sampled — the GRAMMAR_REVIEW §5 "expand only when illumination shows BARREN not
  UNDER-SAMPLED" test says stop here. Adding one would only raise the alpha-budget null hurdle
  (D207) for no orthogonal supply.
- **Optionally send the one cheap unmeasured stone:** sector-ETF cross-sectional *trend* residual-IC
  (`PROMPT_CRUCIBLE_SECTOR_ETF_XSECT_PRECHECK.md` §1). Low-prior (expected trend-collinear) but it
  *definitively closes* the last never-isolated sector door on data — the D215 discipline. No build,
  measurement on Crucible's side.
- **The un-refuted door remains the same one as before:** a genuinely *different mechanism* (e.g.
  fundamental value, `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md`) — not a sector grouping. Sector
  granularity is a *reference/grouping*, and grouping ≠ mechanism (D215). `[[exhaust-long-options-before-v2-spreads]]` unchanged.

## Sources (primary, peer-reviewed unless noted)
- Sector Option IV Dynamics & Predictability, *J. of Derivatives* 25(2) 2017 — jod.pm-research.com/content/25/2/22 (3-0)
- Replication w/ straddle decomposition — aaltodoc.aalto.fi/items/2e49399d-6342-40fb-84e6-1e2f9a23ea3d (3-0)
- Goyal & Saretto, *Cross-section of option returns and volatility*, JFE 2009 — anderson.ucla.edu/documents/areas/fac/finance/cross_options.pdf (2-1 on the split)
- VIX dominates sector-ETF connectedness — sciencedirect.com/science/article/abs/pii/S0140988321001833 (3-0)
- Lead-lag is intra-industry / neglected-industry — academic.oup.com/rfs/article-abstract/20/4/1113 (3-0 / 2-0)
- Credit-Implied Volatility, *FAJ* 2025 — papers.ssrn.com/sol3/papers.cfm?abstract_id=2576292 (unverified — session limit)
- VRP negative across asset classes — afajof.org (unverified — session limit)
- McLean & Pontiff, *JF* 2016 (decay) — onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365
- Chicago Fed 2025 (buyer-VRP decayed to ~0 since 2012) — chicagofed.org/…/wp2025-17

*Status: research verdict, 2026-07-12. Staged, not a decision — operator rules on relay/record.
Companion ask: `PROMPT_CRUCIBLE_SECTOR_ETF_XSECT_PRECHECK.md`. Lineage: D214 / D215 /
GRAMMAR_REVIEW §4.2 / [[exhaust-long-options-before-v2-spreads]].*
