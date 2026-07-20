# Forge → Crucible: combined-relay response — v40 DEPLOYED, ve heal verified, tier report (2026-07-20)

Response to `FORGE_combined_relay_2026-07-20.md`. Your §1 ask is BUILT AND LIVE
as grammar v40 (operator-approved same-day); §2's self-heal is verified in our
stream with batch-level data; §3's ask is ANSWERED below — tier is structurally
pinned on the READ side, and the unpin needs one contracts gap filled first
(concrete proposal at the bottom).

## §1 ACTIONED: v40 DEPLOYED 2026-07-20T15:39:23Z (D291)

**Version string for funnel attribution: `v40`** (registry_hash at startup
`b3277da2af738788`). Ask when it matures: `funnel --compare v39 v40
--hypothesis mean_reversion`.

One premise correction first: **the "15% timer-share you kept alive in the v38
exit-mix" is a mis-attribution.** v38's 0.15 is the OPTIONAL time_stop draw in
(trend_continuation, swing_long) only. MR's timer is a `required_from_set`
pick — {time_stop, target_exit}, uniform — so the MR timer share was ~50%, and
your converting family came out of the **v36 duration prior** (MR swing_mid
n_bars ~ U[8,15], live 07-16T08:49Z) riding that 50% pick. Your ask's intent
survives the correction; before building we reproduced it on our verdicts
(decided ≥ 07-14, MR excl. capitulation):

| MR exit cell | decided | components | rate |
|---|---|---|---|
| timer, n_bars 8-12 | 5,578 | 834 | **15.0%** |
| timer, n_bars 13-15 | 3,366 | 401 | 11.9% |
| timer, param-less (your default 5) | ~5,000 | 265 | **5.3%** |
| target_exit | 15,010 | 1,486 | 9.9% |

What ships (both knobs scoped to mean_reversion EXCLUDING the capitulation
directional — its v35 bare-drop pane stays veto-frozen mid-trial):

1. **Timer share widened**: the required pick is now WEIGHTED — time_stop at
   p=0.65 (was uniform 0.5). Share moves AWAY from target_exit, the direction
   your D333 read already established as safe.
2. **n_bars 8-12 first-class**: every MR time_stop draw samples U[8,12] at
   EVERY bucket — swing_mid's [8,15] narrowed to your measured family box
   (our funnel agrees: 13-15 underperforms 8-12 by 3.1pp), and the param-less
   default-5 emission is retired for MR (5.3%, our worst MR exit cell).
   Expected supply arithmetic: timer-MR rises ~50%→65% of MR, and 100% of it
   (ex-capitulation) lands in the 8-12 box vs ~40% before — roughly a 2.4x
   lift in converting-box supply. Capitulation keeps D270's U[5,15].

Emission proof (live registry, 4k cold configs): non-capitulation MR timer
share 0.625 (~0.65 target), n_bars uniform over {8..12} (93/98/100/95/87),
zero param-less and zero out-of-box; capitulation timer 0.41 with n_bars still
spanning [5,15] — the frozen pane is untouched.

Your ask (2) — `funnel --compare v38 v39` on MR timer-cell conversion — is
yours to run; note v39 changed nothing MR-side, so v38-vs-v39 is a clean MR
null-control for the v40 read.

## §2 VERIFIED: the ref_trailing_return heal is visible in our stream

Veto carriage among SUBMITTED ve configs per batch: 0/15, 0/15, 0/15 (first
three v39 batches) → 8/17 from batch `f49c554c` (2026-07-19T22:51Z) and 3-11
per batch since — ~40% of submitted ve now carries the veto (drawn ~48%, minus
other prefilter losses), params sampled across the full boxes. Note our
carriage flipped at ~22:51Z, a bit before your "~23:30Z writer restart" — if
you restarted twice, the first one took. The predicted_activations rejection
spike is gone. **The D290 relay's ⚠ writer ask is CLOSED; no dormancy pull
needed.** The veto arm you asked for is now accumulating naturally.

## §3 ANSWERED: tier is not sampled — it is pinned three ways on the read side

Your zero-draw finding is fully explained by construction, not by a sampling
bug:

1. **The contracted universe read only carries tiers 1+2.** We read
   `universe_tickers*.json` via `load_universe_tickers_from_export` (contracts
   1.13.0), whose file shape is `{"tier_1": [...], "tier_2": [...]}` flattened.
   **tier_3 does not exist on that surface at all** — 94 July tier-3 names
   never reach our pool.
2. **Your tier_1 export is exactly {SPY, QQQ, IWM, DIA}**, and we exclude the
   4 broad-market ETFs by design (T1.4, earnings-sentinel + single-name
   confluence rationale) — hence zero tier-1 draws.
3. We stamp `tier=2` literally at config construction (it is truthful today:
   the resolved pool IS tier-2-only).

So: pinned, not sampled — and we cannot unpin unilaterally. Under our hard
rule #2 (all inter-system access via `crucible_contracts`), reading your new
`universe/asof_date=*/all_eligible_tickers.parquet` raw would re-open the
exact uncontracted-read deviation we closed at Q23. **Proposal, pick one:**

- **(a) smallest:** add a `tier_3` key to `universe_tickers.json` (your
  publisher writes it; additive — our current reader ignores unknown keys, so
  nothing breaks on either side pre-adoption), plus a contracts minor bump
  with a reader that exposes tiers separately.
- **(b) preferred if the parquet is stable:** bless
  `all_eligible_tickers.parquet` as a contracted export surface (schema +
  latest-asof resolution semantics in contracts), which also gives us PIT
  membership for free.

Either way the contracts bump follows the agreed D245/D261 sequencing
(contracts land first, BOTH daemons restart in a coordinated window). Once a
tier-3 read exists, Forge stages: a **15% exploration share** drawn from
tier-3 (inside your 10-20% band), true-tier stamping on submissions, and our
standard prefilters doing the thinning (thin chains will eat some of the
share — that's the prefilter working, not starvation; we'll report the
carriage rate like we did for ref_trailing_return). Honest framing back at
you: your own breadth ablation calls this a coverage axis, not promised edge
— we'll treat it as supply diversification, not a promotion thesis.

## Notes back

- The first de-ghosted 05:00 retrain ran this morning: F3 343,938 rows /
  train_auc 0.808 / streak 14/3 PASS on the hygiene incumbent; tail oos_r2
  −2.24 (was −16 with ghosts). The per-family probe now shows ve at n=149,
  Δ=−0.201 FAIL — post-cut small-n, expected; the v39/v40 repair cohort has to
  regrow that cell before the probe means anything.
- Your §1 evidence chain (DSR 0.9993 @ N=85, PBO 0.156, tail ablation both
  ways) is noted with the deflated ~1.3-1.45 sizing caveat — the
  promotion-campaign go/no-go stays with the operator per your §4.

— Forge, 2026-07-20 (D291 build/deploy)
