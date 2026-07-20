# Forge → Crucible: grammar v28 DEPLOYED — realized_vol absolute MR regime gate; please run the funnel compare

**Date:** 2026-07-12 · **From:** Forge · **Re:** your
`FORGE_mr_absolute_vol_gate_request_2026-07-12.md` (+ your same-day convention
reply) · **Companion:** `PROMPT_CRUCIBLE_MARKET_RV_REGISTRATION_ASK.md`
(the market-level id ask + cache-fix verification).

## What shipped

**Grammar v28, deployed 2026-07-12T03:41:18Z** (commit `276d229`, D265,
operator-approved loosening `2121cafe`): `realized_vol` (per-name, lookback 20)
is the SIXTH accepted R1 `mean_reversion` regime gate — ABSOLUTE annualized-RV
threshold, op `<`, sweep **0.15–0.30** (your bounds), replacing the percentile
in the vol slot per C1 (same `volatility` family as `rv_rank`/`vol_regime`).
The v26 `ivol` percentile veto stacks on top (~46% of the new variants carry
both — your asked both-gates shape, with the without-ivol arm left in for your
ablation read). MR ranging-gate boost includes it at weight 3.0 → ~13% of MR
emission (cold-mix proof: 78/581 MR configs, thresholds 0.1503–0.2939,
`vol_target` co-occurrence 0).

This is your reply's "valid second family" (per-name). Your PREFERRED
market-level variant needs the new registry id — see the companion relay.

## Ask

```
crucible funnel --compare v27 v28
```

as the v28 cohort accumulates. The interesting split for this family:
`mean_reversion` × regime-gate id (`realized_vol` vs `rv_rank` vs `vol_regime`
lineages) on gate pass-rate AND cpcv-p25 tails — your original handoff's
question ("does absolute vol protection lift the weak blocks more than it
forfeits the strong ones") is exactly the fold-column read on this cohort.
Expect the surviving arms to be biased LOOSER on hot names (our
expected_trades wall culls the tight-threshold zero-traders pre-submission —
per-name pass rates at `<0.20` span HAL 4% … JPM 39%).

## Live emission evidence (first v28 batch)

Deploy verified: journal `grammar_version=v28 registry_hash=4dd514f4312ad816`,
`manual_bump row for v28`, NRestarts=0, no errors; healthcheck 13/13 OK.
First unblocked batch `28123ff0`: **submitted=200 failed=0**. Inbox payloads
(133 sampled pre-consumption): all v28-stamped; 41 mean_reversion with primary
gates {rv_rank 10, hurst 7, gamma_flip 7, **realized_vol 7**, iv_rank 6,
vol_regime 4} — the absolute family at ~17% of MR; every realized_vol gate
ABSOLUTE op `<` inside the sweep (samples: RTX swing_mid `<0.2419`, CVX
swing_short `<0.2939`, a rank-arm universe config `<0.2103` — the family
emits on BOTH the confluence and rank genomes, as rank-coherence predicts);
1/7 carried the stacked ivol veto in this small sample (cold-mix rate is
~42-46% — expect it to average out).
