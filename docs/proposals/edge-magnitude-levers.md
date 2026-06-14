# Proposal / scoping: edge-magnitude (expressivity) levers

Status: **SCOPING (analysis only) — ranked inventory, no code/grammar change proposed for direct ship.**
Date: 2026-06-14 (Sunday review follow-up). Relates to: [[D146]] (the magnitude reframe),
`worst-quartile-complement-supply.md`, `tail-aware-ranker.md`, [[pipeline-vision-roadmap]] Phase 3.

## Why this exists

Crucible's 2026-06-14 design note established the promotion wall is **edge MAGNITUDE**: no
component means a CPCV Sharpe ≥1.5 on any regime slice (pool best ~1.10). Diversity/ranking
(T1/T2) only re-orders a sub-1.5 pool — hygiene, not an unlock. So the producer's real #1 lever
toward QuantIQ promotions is **a higher-magnitude per-regime edge.** This scopes what Forge can
actually do about that.

## The honest constraint (read this first)

**Forge cannot raise a strategy's Sharpe directly — it computes no metrics (§1.2) and is a pure
expressivity + search engine.** Edge magnitude is a property of the *signal × construction ×
regime*, measured by Crucible. So "edge-magnitude levers" for Forge are **expressivity levers**:
making the grammar able to enumerate an archetype that *could* clear a higher per-regime bar.
Three families, by reach: enable a **higher-quality construction** of an existing signal, enable
a **structurally new archetype** (esp. bear-active), or **lean enumeration** toward the
archetype/regime cells most likely to carry magnitude. None of these *guarantees* a ≥1.5 edge —
they expand the search so one *can* exist. Frame accordingly (hard rule 6).

## Ranked levers

### 1. Lean into `long_short` cross-sectional rank — the in-reach bear-adjacent edge [Forge-side, already ON]
`cross_sectional_rank` (H1/D109) carries `direction_mode ∈ {long_only, long_short}`
(`sampler.py` `_RANK_DIRECTION_MODES`), and **`long_short` is already enumerated** — Crucible's
own balanced-frontier config `7a5a782` (WF 1.60 / cpcv-p25 1.21) is `long_short` swing_long.
**This partially corrects the `worst-quartile-complement-supply.md` claim that bear is
un-suppliable:** the short leg of a `long_short` rank book *is* downside exposure (short the
bottom-ranked names), so bear-adjacent edge is expressible **today, without `OverlaySpec`** — it
is simply not enumerated as a dedicated bear bet, and D144's hypothesis-keyed classifier misses
it (the short leg pays in bear but the config is labelled trend). **Lever:** examine the
per-regime edge of `long_short` vs `long_only` rank (Crucible-side read), and if `long_short`
carries the bear leg with magnitude, raise its enumeration share for the rank-eligible
hypotheses. Lowest-risk, highest-reach edge-magnitude move; needs a Crucible read to confirm the
short leg pays before leaning in. **Regime: bear/ranging.**

### 2. Constant-maturity straddle for option_momentum (Crucible §20) [Crucible-gated, OFFERED + deferred]
`option_momentum` (v19/D138) ships **percentile-only** because the as-built front-expiry straddle
is theta-bleed-confounded (return scales with name IV). Crucible offered a **constant-maturity
construction** (§20, "we'll build it on your word") that decouples return from IV level and would
unlock the **absolute-threshold** form — a genuine edge-*quality* deepening of an existing arm,
not just breadth. Currently held pending a v19 percentile-arm signal. **Lever:** if the v19
percentile arm earns any funnel signal, request the §20 build. **Regime: bull/trending.**
**Decision input:** option_momentum is 0/128 honest-era so far (young) — wait for n before
requesting, or request now to deepen proactively. (Operator call; relates to the relay batch.)

### 3. Gamma/vol regime gates (H3/D107) — lean the enumeration [Forge-side, LIVE]
The gamma-flip regime switch (positive-gamma↔mean_reversion, negative-gamma↔trend) is live and
fully Forge-owned. It is "match the tool to the regime" — the closest thing to a magnitude lever
Forge owns, because a regime-coherent entry has higher per-regime Sharpe than a regime-blind one.
**Lever:** once the regime_supply / T3b credit shows which regime cells carry magnitude, lean
enumeration share toward the coherent (gate × direction) cells. Tuning, not new capability.
**Regime: ranging/trending.**

### 4. Bear via tail_hedge / single-leg long puts [Crucible-gated — the relay's open question]
A *dedicated* bear bet (long puts / `tail_hedge`) is the structurally cleanest bear-magnitude
expression (bear is where the whole pool is net-negative, so the most room to differentiate). But
it is blocked on the dispatch question now in `PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md`
(StrategyConfig vs `OverlaySpec`). **Subsumes** lever 1's partial bear leg with a purer
expression *if* Crucible accepts single-leg long puts as a StrategyConfig. **Regime: bear.**

### 5. New higher-Sharpe signal families / indicators [Crucible-gated / data-blocked]
The largest magnitude reservoir (a genuinely new edge) but mostly out of reach: needs Crucible to
publish new indicators/families (the v11/v12 program: event_momentum/PEAD is thin on `sue`,
0/117; the rank-per-name reference gate blocks mean_reversion + event_momentum from the H1 rank
path) or paid/intraday data (OPRA-tick option greeks, intraday dealer gamma). Track via the
Crucible handoff backlog; not actionable unilaterally. **Regime: varies.**

## Recommendation / sequencing

1. **Read `long_short` rank's per-regime edge (lever 1)** — cheapest, and it may already supply
   the bear leg the worst-quartile note wants. A Crucible-side read on `long_short` vs `long_only`
   CPCV-by-regime answers whether to (a) lean enumeration into it (Forge-side, no contract) and
   (b) how much the OverlaySpec long-put path (lever 4) would add on top. **Fold this into the
   bear-dispatch relay** so Crucible answers both in one pass.
2. **Decide the §20 constant-maturity request (lever 2)** with the relay — it's the one edge-
   *quality* deepening already on the table.
3. **Hold levers 3/5** — 3 is tuning that waits on the T3b magnitude-by-cell credit; 5 is the
   Crucible/data backlog.

## What this does NOT propose
No grammar/enumeration change shipped. Levers 1 and 3 become enumeration-share changes only
*after* a Crucible read confirms the target cells carry magnitude (else Forge would lean into a
sub-1.5 archetype on a structural guess — the exact error [[D146]] warns against). The honest
near-term truth: **most edge-magnitude reservoir is Crucible-gated or data-blocked; Forge's
unilateral move is to lean enumeration toward whatever Crucible's per-regime read says carries
magnitude — starting with `long_short` rank.**
