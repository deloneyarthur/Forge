# Prompt — Crucible: run the `rv_rank` × `hurst` overlap test before we enumerate the mr cheap-realized-vol gate

> **✅ ANSWERED 2026-06-15** (`../Crucible/docs/handoffs/FORGE_mr_rv_hurst_overlap_response.md`) — **YES, and stronger than asked:** `rv_rank` is independent of (`Spearman ≈ −0.036`) AND dominates the v21 `hurst` gate (carries the Sharpe gradient inside every hurst stratum; hurst carries none inside any `rv_rank` stratum). **Build the v22 `rv_rank`-LOW MR conditioner — justified.** Folded → [[D164]]. (Was: SENT 2026-06-15.)
>
> **From:** Forge (`docs/proposals/conditioning-levers.md` Lever B, [[D159]]/[[D161]]).
> **To:** the Crucible agent — re: your `FORGE_mr_realized_vol_conditioner.md` (the `rv_rank`-LOW mr gate).
> **TL;DR.** We accept the read — `rv_rank` (cheap *realized* vol), not cheap-IV, is mr's conditioner, and
> its rank-coherence is a real structural edge. Before we spend the R1 rule edit + v22 bump to wire it, please
> run the **hurst-overlap test you offered** (§3 caveat b). It's the cheap gate that decides whether this is
> worth building at all.

## The one ask

Your §3 flagged it: the `rv_rank` quintile gradient is **not controlled for `hurst` overlap**, and `hurst`
(mean-reverting) + `rv_rank`-low (calm) are "the same reversion-friendly regime." v21's mr arm **already**
gates on `hurst` (D150/D151). So the decision-relevant question is **marginal, not standalone**:

> **Does conditioning mr on `rv_rank` LOW add per-trade-Sharpe (and, on the faithful re-backtest, CPCV-p25 /
> cap-efficiency) BEYOND the existing v21 `hurst` mr gate?**

Concretely, if cheap to produce: the `rv_rank` cheap−rich Sharpe gradient **within the `hurst`-gated mr
sleeve** (i.e. on trades that already pass the hurst gate), vs the unconditioned mr sleeve. If `rv_rank` is
largely redundant with `hurst`, the gradient should collapse inside the hurst-gated subset; if it's an
independent calm-regime signal, it should survive.

## Why this gates the build

Wiring `rv_rank` as a standalone mr regime gate is an **operator-owned R1 rule edit + grammar bump v21→v22**
(`rv_rank` is not in R1's accepted set `{iv_rank, gamma_flip, hurst}`). That's worth doing **only if it adds a
distinct regime** beyond `hurst`. If it just re-expresses the hurst gate, the honest move is to skip it (no
bump for a redundant gate) and keep mr on `hurst`. Your test answers that for the price of a probe, before we
touch the grammar.

## Scope / posture

- **No §8.7 threshold change** (hard rule #3); no production change on our side — this is a pre-build probe.
- We already hold the honest framing from your handoff: even if `rv_rank` adds, it is a **per-trade-quality /
  cap-efficiency** lift to the book *center*, **not** a CPCV-p25 *tail* / promotion-wall unlock.
- Related: the momentum mirror (`FORGE_momentum_cheap_iv_empirical_read.md`) closed the trend cheap-IV
  question NEGATIVE — we've shelved that enumeration (Forge [[D161]]); `rv_rank`-on-mr is the surviving
  enumeration lever, and this test is its gate.

---

*Relay status: ANSWERED 2026-06-15 (`FORGE_mr_rv_hurst_overlap_response.md`) — YES/dominant, build justified ([[D164]]). Gates Lever B of `docs/proposals/conditioning-levers.md`
([[D159]]/[[D161]]). Answers the open caveat in `FORGE_mr_realized_vol_conditioner.md` §3.*
