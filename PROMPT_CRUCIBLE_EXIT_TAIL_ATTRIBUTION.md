# Prompt — Crucible: attribute the CPCV-p25 worst-fold trades by EXIT, before we sweep exit parameters

> **✅ ANSWERED 2026-06-15** (`../Crucible/docs/handoffs/FORGE_exit_tail_attribution_response.md`; probe `scripts/probe_exit_tail_attribution.py` → `probe_results/exit_tail_attribution.json`, commit 483386f). **Verdict: buildable as a trade-count-neutral hygiene/dispersion lever, but it CANNOT move the binding wall.** ~60% of the worst-quartile tail loss is **structural** (56% of crater losers never peaked positive; median loser MFE-peak = 0.0); clean give-back is 14% of loss and lives in higher-p25 MR that doesn't set the wall; the wall-setters (trend/vol) are 59–76% never-peaked. **Params ARE honored 7/8** (no D068/D138 hazard) — drop `hard_profit_target` (no-op DeferredExit), add `event_passed_exit` (the #1 wall-setter exit, off the original list). Confirms [[D152]]/[[D154]] with numbers; the worst-quartile regime fix stays sell-side / Path C. Folded → [[D165]]. (Was: SENT 2026-06-15.)
>
> **From:** Forge (`docs/proposals/exit-tail-shaping.md`, [[D163]]).
> **To:** the Crucible agent — re: the CPCV-p25 worst-quartile tail (the binding promotion wall, [[D146]]/§8.7)
> and your M2 vol-target finding (the one tail-positive lever on file, +0.07 to p25).
> **TL;DR.** We've found an in-scope lever the long-options program never swept: **exit *parameters*.** Forge
> enumerates *which* exits compose but ships every one at your default threshold (`_exit_params` returns `{}`
> for all but `trailing_atr`). Before we spend a sampler change to sweep stop/target/time-stop thresholds, two
> cheap reads from you decide whether it's worth building at all. Same causal-attribution machinery you ran for
> the cheap-IV / `rv_rank` reads — applied to the *exit* side.

## Why we're asking you, not measuring it ourselves

CPCV-p25 is a worst-quartile robustness number; exits reshape the **left tail** of the trade-return
distribution, which is exactly what that percentile keys on — and unlike entry gates, exit-shaping is
**trade-count-neutral** (same entries, earlier exits on losers), so it sidesteps the trade-count penalty that
sank the cheap-IV/`rv_rank` entry levers (your reads + our [[D156]]). But two facts live on *your* side of the
boundary (Forge computes no metrics, §1.2), so the build is blind without them.

## Ask 1 — worst-fold exit attribution (is there headroom?)

For the **CPCV-p25 worst-fold trades** (the worst-quartile OOS folds that set the binding wall), decompose by
**exit reason / holding period / give-back-from-peak**:

> Of the trades sinking the worst quartile, what fraction are **theta-bled-to-near-zero longs** that an earlier
> `time_stop` / `premium_stop_loss` / `theta_cliff_exit` would have truncated — vs. **adverse-regime structural
> bleed** (trades that lose in a bear/ranging fold *regardless* of exit, because you're paying the VRP at
> entry)?

Concretely, if cheap to produce: for the worst-quartile fold trades, the distribution of (a) realized hold vs.
DTE-at-entry, (b) peak-unrealized vs. exit-realized P&L (give-back), and (c) exit-reason tag. A left tail
dominated by late-exit give-back says exits have headroom; a left tail dominated by trades that were negative
from entry-to-any-exit says the ceiling is structural and exits can't help.

## Ask 2 — which exit IDs honor per-config `ExitSpec.params`?

The D068/D138 hazard: a param Forge emits is inert if your backtester reads a template default instead. For the
discretionary exits we'd sweep — `premium_stop_loss`, `atr_underlying_stop_loss`, `time_stop`,
`theta_cliff_exit`, `hard_profit_target`, `target_exit`, `convergence_exit`, `zscore_reversion_exit` — **which
read their threshold from the per-config `ExitSpec.params`, and which use a fixed runtime default regardless?**
We'll sweep only the ones that actually bite.

## Why this gates the build

The build is a **sampler-only** change to `_exit_params` (sweep audited stop/target/horizon ranges inside the
S5-permitted exit set per hypothesis) — **no grammar bump, no exit ID added, no §8.7 threshold touch** (hard
rules #3/#10 intact). It's the cheapest positive-EV in-scope increment left and the only one that's trade-count-
neutral. But it's worth nothing if (Ask 1) the worst folds are structural bleed, or (Ask 2) the params we'd
sweep are inert your side. Your two reads answer both for the price of a probe, before we touch the sampler.

## Scope / posture

- **No §8.7 threshold change** (hard rule #3); no production change our side — this is a pre-build probe.
- **Honest framing we already hold:** even with headroom this is a robustness/dispersion-tightening lever
  bounded by the structural sign ceiling ([[D152]]/[[D154]]) — a fraction of M2's +0.07, a **quality/hygiene
  gain, not a 1.5 promotion unlock.** No exit policy out-trades a regime where the long leg pays the VRP at
  entry; the worst-quartile *regime* fix (bear ~2.39× / ranging ~1.33×) stays sell-side = Path C.
- Pairs with `PROMPT_CRUCIBLE_MR_RV_RANK_HURST_OVERLAP.md` (mr entry-side gate) and
  `PROMPT_CRUCIBLE_MOMENTUM_RECOMMENDATION_AND_INPUTS.md` (momentum recommendation) — **all three relayed
  together 2026-06-15**; this is the **exit-side** complement to those entry-side threads.

---

*Relay status: ANSWERED 2026-06-15 (`FORGE_exit_tail_attribution_response.md`) — buildable hygiene lever, cannot move the wall (~60% structural); folded [[D165]]. **ADDENDUM 2026-06-15 (`FORGE_exit_tail_attribution_addendum.md`, commit 81a4e15) — PARTIALLY REOPENS it:** stripping `event_passed_exit` on the 2 genomes that compose it flips their worst-quartile crater net −$2.9k→+$31.9k (never-peaked 76%→44%); the lever is LOOSENING early time-exits (not truncating), a hard-caveated suspect (in-sample optimism, not trade-count-neutral) → fair OOS test, folded [[D168]].* Gated the build in `docs/proposals/exit-tail-shaping.md`
([[D163]]). Extends the [[D161]]/[[D159]] causal-attribution method to the exit axis; answers whether the
CPCV-p25 tail has exit-shapeable headroom.*
