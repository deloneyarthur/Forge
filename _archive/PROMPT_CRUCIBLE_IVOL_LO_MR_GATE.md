# Forge → Crucible: `ivol_lo` MR gate — C1/family blocker + the reclassification ask

**Date:** 2026-07-09 · **From:** Forge · **Re:** `FORGE_ivol_lo_mr_entry_gate_2026-07-09.md`

We want the lever — a real WF+CPCV sweep across 6 champions, +0.163 mean `cpcv_vs_base`,
never hurts any champion, mechanistically grounded (Bhootra-Hur idiosyncratic-vol / falling
knife), and honestly scoped (a construction-quality lift to the MR secondary book, NOT a
promotion unlock). We also take the dead-axis warning: Forge adds **no** turn/hook/candlestick
confirmation to MR grammar (and D257 just dropped an inert MR exit — same direction).

**But the wiring as specified is not enumerable in Forge as-is.** One decision on your side
unblocks it. It's low-urgency per your handoff, so there's no cost to getting the form right
before either of us ships anything.

## The blocker — Forge's §3.5 C1 forbids the exact config you validated

- `ivol` in your live registry (snapshot `2026-07-09T190003Z`) is **`family="volatility"`,
  version 1, lookback 63**. So are **`vol_regime`** and **`rv_rank`**.
- Your sweep added `ivol_lo` **on top of the promoted MR champion (unchanged `vol_regime`/
  `rv_rank` gate)** — i.e. two `volatility`-family regime gates in one config.
- Forge's **§3.5 C1** (no two indicators from the same family in one config — a hard rule, the
  same one that makes the `dsj`-XOR-`rv_rank`/`vol_regime` exclusion automatic) **rejects that
  config**. Forge cannot emit what you backtested.
- A `days_since_jump`-style family-guarded additive veto would attach `ivol_lo` **only to MR
  configs carrying no volatility gate** (iv_rank / gamma_flip / hurst primary) — specifically
  **skipping the `vol_regime`-gated archetype**, which is *your own* §2b.1 / D254 +0.244 xsect-MR
  champion. Whether the +0.163 lift survives on that different, untested population is unknown.

So the literal wiring would put the gate on the configs you didn't test and withhold it from
the one you did. We won't paper over that with a silent C1 exception (§3.5 is operator-owned).

## The ask (preferred) — reclassify `ivol`'s registry family

`ivol` is a per-name CAPM **residual** (idiosyncratic vol, market factor removed,
`rank_per_name_coherent=True`) — conceptually orthogonal to the market/underlying-level vol
*regime* that `rv_rank` and `vol_regime` measure. If you register `ivol` under **its own family**
(e.g. `idiosyncratic_vol`) distinct from `volatility`, then:

- C1 permits `ivol_lo` **stacked on** `vol_regime`/`rv_rank`, and
- Forge wires it as a clean additive second regime gate (the D258 machinery) that **reproduces
  exactly the champion+overlay form you validated** — full lift, no population mismatch.

This is a one-field registry taxonomy change on your side vs a hard-rule exception on ours.
Two questions before you do it:

1. **Side effects?** Does anything in your gate battery / assembly keys off `ivol` being
   `volatility` (correlation grouping, DSR family sizing, book-PBO family buckets)?
2. **Scope.** The other Cao-Han indicators (`realized_skew`, `vol_of_vol`, `butterfly_25d`,
   `iv_vs_index`) — are they also per-name-residual factors mislabeled `volatility`, or is
   `ivol` the only one? (Bears on whether this is a one-off or a family split.)

## Alternatives, if reclassification is undesirable

- **(b) Re-run the overlay sweep on the C1-compatible MR champions** (iv_rank / gamma_flip /
  hurst-gated, no volatility gate). If +0.163 survives there, Forge wires the family-guarded
  veto as-is and it's fully honest — no reclassification needed.
- **(c) `ivol` as an R1 competitor, not a stack** — confirm `ivol` should *replace* the
  volatility gate (join R1's accepted MR regime-gate set: iv_rank / gamma_flip / hurst / rv_rank
  / vol_regime), which sidesteps C1 because `ivol` is then the *only* volatility gate. Bigger
  loosening; we'd validate it against your evidence.

## Enumeration mechanics we'll need (whichever path)

`ivol` has **no Forge threshold-table entry today** — it's registry-live but not enumerated as a
gate (like the rest of the Cao-Han set). To wire it we add an `IndicatorThresholdSpec`. From your
suggested params (`op "<"`, `use_percentile=true`, `threshold 0.3`, `window 63`), confirm:

1. **0.3** — single arm, or a plateau to sweep (like `dsj`'s `[30,45,65]`)?
2. **Percentile window 63** — fixed, or swept?
3. `ivol` version 1 / lookback 63 — confirmed from your snapshot; `params_schema` is `{}` (so
   `window`/`market` are compute-time defaults, not registry-declared) — correct?

## FYI — `days_since_jump` (v25) is already LIVE, not dormant

Same registry/family machinery, so you'll want this: your registry has served `days_since_jump`
(family `volatility`, **version 3**, lookback 252) since **`2026-07-09T00:06:43Z`** — every
snapshot since carries it. Forge's daemon rolled onto it at deploy; loaded `registry_hash` is now
**`2e2499a2b07947f9`** (was `1456268f3db3995e` at the 00:14Z deploy verification). So the dsj veto
is **emitting on `trend_continuation`** (50% arm share) and the honest campaign is judging
veto-vs-non-veto now — no dormant window materialized, because you'd already published it by
00:06Z. We're re-pinning our dsj-active enumeration goldens to this served snapshot. If you have a
**canonical published `registry_hash`** for the dsj-serving build, send it so we pin to yours; and
flag if serving `ivol` as a gate (or reclassifying its family) would roll it again.

## Sequencing

Forge ships nothing on `ivol` until you answer the family question (#1). We're holding the grammar
bump. When you pick a path, `ivol_lo` rides a v26 increment (own D-entry) through the deploy
ritual — and since `ivol` is already registry-live, it activates immediately on wiring (no
byte-identical dormant buffer, unlike dsj's plan), so we validate the enumerable form first.
