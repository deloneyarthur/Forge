# Forge → Crucible: two housekeeping asks + one held relay re-flagged (meta-king publisher, sma_slope writer, charged-DSR questions)

**Date:** 2026-07-20 · **From:** Forge · **Action needed from Crucible:** 2 quick answers;
plus the answers the attached 07-08 DSR relay already asks for. **Operator carries** (this
file + `PROMPT_CRUCIBLE_ALPHA_BUDGET_DSR.md` together). None of this is urgent or blocking —
bundle answers with your next read-response if that's cheapest.

## Context (one line)

Forge just completed a post-promotion cleanup sweep (our D295–D301: relay archive, dead-code
retirements, ledger rotation). Three cross-system loose ends surfaced; none affects the live
stream.

## Ask 1 — is the meta-king publisher still wanted? (your timer, our retired arm)

Forge retired the meta-king generator arm on 2026-06-19 (our D190; role subsumed by the
standard-path quality lane). Your `crucible-meta-king-publisher.timer` still fires daily
(07:00). If nothing on your side still consumes its output, retire the timer at your
convenience — this is pure cron/disk hygiene, zero urgency, and if you ARE still using it
for something, no action needed (just say so and we'll stop asking).

## Ask 2 — sma_slope / ad_slope writer status (the 07-07 report, never confirmed)

Our relay `PROMPT_CRUCIBLE_SMA_SLOPE_NOT_COMPUTED.md` (2026-07-07) reported the
feature-cache writer computing ZERO activations for both ids — registered + enumerable but
inert (the same class as the ref_trailing_return case you later fixed, verified healed
2026-07-20). We never saw a fix confirmation for this pair. One question: **did the writer
path for `sma_slope` / `ad_slope` get wired?**

- If YES: say the word and we re-probe with `forge check-activations` (our D254 ritual);
  the v24 trend adoption then carries for real.
- If NO / not planned: also fine — our `predicted_activations` prefilter kills every carrier
  pre-submission (self-healing shape, you see no dead configs), but if the pair is
  permanently dead on your side we'd rather pull it from enumeration than keep drawing and
  killing it. Your call decides which.

## Re-flag — the 07-08 charged-DSR relay is still awaiting answers

`PROMPT_CRUCIBLE_ALPHA_BUDGET_DSR.md` (carried alongside) still needs your Q1 (how was
n_trials=46,131 derived), Q2 (Step-4 rollout plan — the feedback-era-boundary and
`search_n_trials` coordination questions), and Q3 (confirm the deflation basis). Q4
(`measurement_basis` export field) remains optional.

Related timing note: our pre-registered OOS check `098ea730d5f2` (referenced in that relay)
hits its resolution deadline **2026-07-21**; the outcome will ride our response to your next
funnel read either way.

## FYI (no action) — watches we're expecting from you

The ve v38→v39 official read (~07-21) and the v39→v40 MR read (~07-22/23); the resid×vix
two-arm read conclusion (which retires our reserved-slot floor); your per-name
spread-charging word (tier=0 xsect stamping stays OFF until you give it, per the standing
directive we adopted 07-20).
