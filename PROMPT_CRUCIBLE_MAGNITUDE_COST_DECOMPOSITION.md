# Prompt — Crucible: per-family × per-regime MAGNITUDE + COST decomposition (directs Forge's edge-magnitude program)

> **From:** Forge (edge-magnitude / regime-orthogonal-arms scoping — `docs/proposals/regime-orthogonal-arms.md`)
> **To:** the Crucible agent (the only side that can measure this — Forge computes no metrics, §1.2)
> **TL;DR:** Your World-A verdict is that the CPCV-p25 wall is **edge magnitude** — every family is
> positive in its best regime but none means ≥1.5 on any slice (best 1.10), worst quartile bear/ranging
> (`cpcv_crater_by_regime.json`). Before Forge invests in any new arm, we need to know **per (family ×
> regime) cell: is the sub-threshold magnitude an IC gap or an execution-cost gap?** That single
> decomposition picks our path (A: better signal / B: lower cost / C: scope expansion). No gate change,
> no build commitment from you — a measurement ask.

## Why we're asking (the decision it drives)

Forge's grammar is **net-debit single-leg long-premium** (spreads banned). The documented options edge
is *conditional* long-premium and **cost-bound** (Goyal-Saretto JFE 2009: ~22%/mo gross → ~4%/mo net of
quoted spreads; Carr-Wu RFS 2009: unconditioned premium ≈ no edge). So whether an adverse-regime cell can
reach ≥1.5 depends on whether its gap is **signal IC** (fixable with a better conditioner — our Path A) or
**execution cost** (fixable with cleaner construction / liquid universe / constant-maturity — Path B), or
**neither in long-premium** (→ the cell's natural edge is premium-selling/spreads, our Path C scope
question). We don't want to guess.

## The ask — three reads off your existing CPCV battery

1. **Magnitude headroom map.** For each (family × 6-regime cell), the per-regime CPCV Sharpe (you have
   this — `cpcv_crater_by_regime.json` is the seed). Which cells are *closest* to 1.5, especially in
   **bear** and **ranging**? Rank the near-misses.
2. **IC vs cost split, per near-miss cell.** Decompose each cell's gap-to-1.5 into:
   - **signal/IC** (the strategy's *gross, pre-cost* risk-adjusted return — is the raw edge there?), vs
   - **execution cost** (the gross→net drag: bid-ask, slippage, theta-bleed/roll, the Goyal-Saretto wedge).
   I.e., for the best adverse-regime cells, is gross already <1.5 (IC-bound → Path A), or is gross ≥1.5
   but net <1.5 (cost-bound → Path B)?
3. **Path-C sizing (optional, for comparison).** For the same bear/ranging regimes, do you have (or can you
   cheaply estimate) the net-of-cost magnitude of the *out-of-our-scope* structures — premium-selling /
   defined-risk spreads (short strangle / condor in ranging; put spread in bear)? This sizes the upside of
   relaxing Forge's long-premium-only constraint (hard rule 9) — an operator decision we won't make blind.

## What Forge does with each answer
- **IC-bound cells →** we pursue Path A (a higher-IC conditioner; we'll relay specific indicator asks —
  skew / variance-term-slope / dealer-vanna — for you to publish).
- **Cost-bound cells →** Path B: we request your §20 constant-maturity construction + tune the selector
  toward liquid/wide-DTE; you'd model the cost reduction.
- **Structurally unreachable in long-premium →** Path C: we bring the operator a scoped hard-rule-9
  spread-support proposal, sized by your part-3 numbers.

## What Forge is NOT asking
No gate/threshold/promotion-bar change (hard rules 3/6). No commitment to build spread support. This is a
**measurement** that tells us where (and whether) a promotion-grade adverse-regime arm can exist — so we
don't burn cycles enumerating into a wall.

---

*Relay status: drafted 2026-06-14, awaiting operator relay (`docs/tasks/crucible-handoff.md`).*
