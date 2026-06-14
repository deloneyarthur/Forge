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

### 1. ~~Lean into `long_short` cross-sectional rank — the in-reach bear-adjacent edge~~ — REFUTED 2026-06-14
> **REFUTED by Crucible's Q2 probe** (`FORGE_bear_complement_decision.md`,
> `longshort_shortleg_regime_edge.json`): on 8,714 `long_short` runs / ~1.7M trades the short leg
> (long puts) is net-**negative in bear (−0.057)** and positive only in marginal ranging (+0.016).
> Single-name rank puts are a *relative* bet on weak names, not a market hedge — in a slow bear they
> bleed theta and weak names don't fall hardest. **So `long_short` does NOT supply a bear leg, and
> raising its share would not add one.** Bear is closed for Forge (Crucible `tail_leg` overlay; keep
> D066). The lever below stands on its own merits (breadth), not as a bear play. Original text kept
> for the record:

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

### 4. ~~Bear via tail_hedge / single-leg long puts~~ — DECIDED 2026-06-14: NOT a Forge lever
Crucible adjudicated (`FORGE_bear_complement_decision.md`, operator-approved): a *constant* bear
hedge is negative-carry and only `tail_hedge` carries the gate exemption, so it can't gate-pass as
an ordinary `StrategyConfig`; bear is handled by the **Crucible `tail_leg` overlay** (10%-OTM, §20),
not Forge supply. **Keep D066; no §3.5 bearish-direction rule.** Bear is off Forge's plate.

### 5. New higher-Sharpe signal families / indicators [Crucible-gated / data-blocked]
The largest magnitude reservoir (a genuinely new edge) but mostly out of reach: needs Crucible to
publish new indicators/families (the v11/v12 program: event_momentum/PEAD is thin on `sue`,
0/117; the rank-per-name reference gate blocks mean_reversion + event_momentum from the H1 rank
path) or paid/intraday data (OPRA-tick option greeks, intraday dealer gamma). Track via the
Crucible handoff backlog; not actionable unilaterally. **Regime: varies.**

## Recommendation / sequencing (UPDATED 2026-06-14 after Crucible's bear adjudication)

Levers 1 and 4 are CLOSED (bear is not a Forge supply item — Crucible `tail_leg` overlay; keep
D066). The promotion unlock Crucible names is a **genuinely higher-magnitude adverse-regime edge —
"regime-orthogonal arms"** (the open Forge research problem). What remains actionable:
1. **`mean_reversion` (ranging) supply growth** — NEW, greenlit (`FORGE_greenlight_ranker_wiring_and_ranging.md`):
   ranging is the half of the worst-quartile complement that IS a return-seeking, gate-passable
   Forge family (mr, ranging-active, thin: 49/342). Operator-gated grammar; ships *with* the T2
   ranging floor. This is the near-term producer move (hygiene, not a p25 unlock).
2. **Decide the §20 constant-maturity request (lever 2)** — the one edge-*quality* deepening on the
   table (deepens option_momentum); request if its arm earns funnel signal.
3. **Hold lever 3 (gamma-gate tuning)** — waits on the T3b magnitude-by-cell credit. **Lever 5
   (new families/indicators)** is the real magnitude reservoir but Crucible-v10/data-blocked — and
   is where the "regime-orthogonal arms" unlock would come from.

## What this does NOT propose
No grammar/enumeration change shipped. Levers 1 and 3 become enumeration-share changes only
*after* a Crucible read confirms the target cells carry magnitude (else Forge would lean into a
sub-1.5 archetype on a structural guess — the exact error [[D146]] warns against). The honest
near-term truth: **most edge-magnitude reservoir is Crucible-gated or data-blocked; Forge's
unilateral move is to lean enumeration toward whatever Crucible's per-regime read says carries
magnitude — starting with `long_short` rank.**
