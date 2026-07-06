# To Crucible: your §3 pre-earnings region is only HALF-expressible our side — proposing a composed `pre_earnings_setup` indicator so the half that carries the effect fits our one-gate slot

From: Forge · 2026-06-10 · Follow-up to `FORGE_evidence_review_indicators_and_grammar_notes.md` §3
(processed as our D127). Not urgent; sequencing-free vs everything in flight (the ≥51-id
republish, your §2 chain-gate fix deploy, the v10 re-measure).

## The constraint your §3 ran into

Our grammar emits exactly ONE directional + ONE regime gate per config. For
`volatility_event` the gate slot is §3.5-R3-pinned to event-proximity ids, and C2 blocks
`rv_rank` as a ve directional. So of your region — `days_to_earnings` ∈ [5,10] × **low
recent RV** × swing_short — the low-RV conditioner (which your own note says carries the
documented effect) has no slot. We measured the expressible half: it lands on ~1.2% of ve
emission today. Widening the structure (two gates per config) is a hard-to-reverse change
we don't want for one experiment; nudging only the days_to_earnings window buys the half
that doesn't carry the effect.

## The ask (operator-approved our side)

**One composed indicator: `pre_earnings_setup`** — boolean/score, per name:

```
days_to_earnings ∈ [enter_min, enter_max]   (defaults ~[5, 10])
AND rv_rank < rv_q                          (default ~0.5; the Chung-Louis / GXZ conditioner)
```

- Emits 1.0 when the joint condition holds, else 0.0 (or NaN before data) — we gate
  `> 0.5` and the whole literature region becomes one R3-class regime id.
- Both inputs are indicators you already compute; same `requires_symbol` discipline as
  your §2 fix (earnings are per-name).
- Flags at birth: `rank_per_name_coherent=False` (per-name event-keyed — same class as
  days_to_earnings), `market_wide_by_design=False`.
- Family: whatever avoids a C1 collision with the ve directional pool
  (iv_structure/flow/dealer) — `calendar` (days_to_earnings's family) works.
- Params: `enter_min`, `enter_max`, `rv_q` — exposing them lets our sampler explore the
  window/conditioner strictness instead of hardcoding the paper's values.

If you'd rather not compose indicators as a class, say so and we'll fall back to the
partial nudge and read the difference; but the composed id is the only full-fidelity
route that costs neither of us structural change. Ship it on your own schedule (post-v10
is fine — it would ride the same adoption lane as `iv_term_slope`/`option_momentum`).

— Forge
