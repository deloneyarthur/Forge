# Proposal / work-up: worst-quartile complement supply (bear + ranging)

Status: **WORK-UP (analysis only) — no grammar/code change proposed for direct ship.**
Date: 2026-06-14 (Sunday review). Author: ranking/grammar investigation.
Relates to: `tail-aware-ranker.md` (T2/T3a), D144 (`regime_supply`), [[promotion-gate-tiers-and-constraint]].

## Why this exists

The Sunday 2026-06-14 review paired two live instruments and found the binding
constraint on promotions is **not** ranking quality:

- **T1 tail shadow works** — dominant model `5174039c` decided=85, spearman(pred, realized
  cpcv_p25) **+0.451**, top-8 realized cpcv_p25 **0.727 (tail) vs 0.467 (incumbent)**.
  Ranking on tail-robustness would pick materially better worst-quartile components.
- **But D144 `regime_supply:` logs `bear 0/0` every iteration**, and the ranging pool is
  only ~2% of the passed pool (the ranker already *over*-selects it, ~7.5% of the batch).
  T3a measured the worst CPCV quartile as **BEAR 2.39× / RANGING 1.33×** (regime_lift).

**Conclusion: the worst-quartile gap is a grammar-expressivity / supply gap, not a ranking
gap.** A perfect T1 ranker + a T2 reservation floor cannot assemble a complement the
enumerated pool does not contain. This work-up answers "what would it take to supply it?"

## What blocks bear-paying exposure today (grounded)

Forge is options-only (hard rule 7 / §13.6), single-leg long-premium (net debit, qty≥0),
spreads banned. Direction is **delegated to Crucible**: Forge emits no signed direction and
no call/put choice — `selector.delta_target` is unsigned/positive (`sampler.py:863`,
`GRAMMAR.md` P3 bands all positive), and the directional family (C2,
`custom_predicates.py:156–187`) only constrains *which* indicator sets direction, not its
sign. In practice every enumerated directional signal is bullish-by-convention, so Crucible
only ever buys calls. There is no §3.5 rule sampling a bearish stance.

The one hypothesis that is structurally defensive/bearish — **`tail_hedge`** (directional
family = `macro`, i.e. VIX/term-structure; long-vol / long-puts) — is **disabled**
(`search_space.py:80`, `OVERLAY_ONLY_HYPOTHESES`). It was dropped by **D066** not for lack
of edge but because Crucible's runner rejects a standalone `tail_hedge` `StrategyConfig` at
dispatch (`RunnerError`, `runner.py:397`) — it belongs to `OverlaySpec` semantics, not
`StrategySpec`. **`OverlaySpec` does not yet exist in `crucible_contracts`** (verified
2026-06-14: `[n for n in dir(crucible_contracts) if 'overlay' in n.lower()] == []`).

`regime_arbitrage` is separately disabled (`DISABLED_HYPOTHESES`, D098 — low-yield by
construction).

## The three supply paths

### A. tail_hedge → BEAR (highest leverage, **Crucible-owned, blocked on contracts**)
The principled bear/defensive supplier. Re-admitting it is **not a Forge change we can make**
— per hard rule 2, the missing `OverlaySpec` model is a contracts gap to *surface*, not work
around. Until Crucible ships `OverlaySpec` (overlay-aware enumeration can then re-admit
tail_hedge as a portfolio overlay, per the `search_space.py:69–79` plan), bear supply stays
zero. **→ Relayed to Crucible** (`PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md`) with the
new T3a + `regime_supply` evidence so it can be prioritised against the now-measured need.

### B. Bearish-side enumeration → BEAR (weak, **Forge grammar, operator-gated**)
Some enabled directional indicators have a bearish reading Crucible could map to puts — e.g.
negative SUE (event_momentum: positive surprise → long calls, negative → puts, per the D-entry
mapping), or bearish macro/dealer thresholds. Today the grammar only samples the bullish
thresholds. Enumerating the bearish side would be a §3.5 grammar change (operator-owned) and
requires Crucible to confirm it interprets the signal sign → puts for a single-leg long-put.
**Caveat:** event_momentum is data-starved (`sue` sparse, 0/117 honest-era), so this is a
thin, unreliable bear supplier even if enabled. Low priority vs. (A).

### C. R1 widening → RANGING (modest, **Forge grammar, operator-gated loosening**)
`mean_reversion`'s regime gate (R1, `_r1_mean_reversion_requires_iv_rank_gate`) accepts only
`iv_rank` (threshold ≤ 50) **or** `gamma_flip_distance_pct` (`search_space.py:341`). `iv_rank`
fires sparsely, so the pre-filter rejects many MR candidates on firing density → the ~2%
ranging pool. Widening R1's permitted regime indicators (or relaxing the iv_rank threshold)
would grow ranging supply. This is a grammar **loosening** → hard rule 4: it cannot ship
auto; it is *proposed* here and waits for the operator (do NOT write to `grammar.yaml`).
**Ceiling caveat:** even widened, ranging pays only 1.33× the tail vs bear's 2.39× — this is
the smaller half of the worst-quartile problem.

## Recommended sequencing

1. **Relay (A) to Crucible now** — bear is 2.39× the worst quartile and is *un-suppliable in
   Forge*; the `OverlaySpec` contract is the unlock. Highest leverage, zero Forge risk.
2. **Hold (B)** — low value until `sue`/event_momentum has data; revisit if a bearish-signal
   funnel opens.
3. **Decide (C) with the operator** — a bounded ranging-supply loosening (R1) is the only
   complement Forge can grow unilaterally; modest ceiling. Pair with the rv-de-emphasis
   capacity reclaim (rv 0/3639 frees ~7% of the stream that could carry more MR draws).

## What this does NOT propose
No grammar edit, no gate change, no loosening shipped. T2's enforcement floor stays gated:
reserving a bear quota is pointless while bear supply is 0; the floor becomes meaningful only
once (A) lands or (C) grows ranging supply enough to reserve against.
