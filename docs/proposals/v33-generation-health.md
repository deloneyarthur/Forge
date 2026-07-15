# Proposal: v33 — generation-health change set (resid_vix concentration + dead-cell reclamation)

Status: **SCOPING — operator-gated grammar bump; nothing here ships off this doc.**
Date: 2026-07-15. Author: triage of `FORGE_generation_health_capitulation_addendum_2026-07-15.md`
plus the three late-published relays it shipped with (`FORGE_resid_vix_region_followup_2026-07-13.md`,
`FORGE_days_to_nfp_cpi_threshold_prior_2026-07-14.md`, `FORGE_capitulation_v31_followup_2026-07-13.md`).
Receipt/contradiction response: `PROMPT_CRUCIBLE_GENERATION_HEALTH_RECEIPT.md` (held for carry).
Relates to: [[D270]] (v31 capitulation), [[D264]] (v27 resid_vix activation), [[D272]] (v32),
Q49 (rv_rank range-position), Q45 (dark supply), `orthogonal-family-supply-for-pbo.md`.

## Why one bump

Crucible's 7-day audit: ~1,000 configs/week burn in cells that are structurally dead (>=90%
WF=0.0, median OOS trades <=6 — below the trade floor by construction), while the highest-value
confirmed ask (resid_vix region sweep) has zero supply because the relay was never received.
Every item below changes deterministic enumeration → one version bump, one golden re-pin, one
deploy. Items are independent; the operator can strike any line.

## The change set (priority order)

1. **resid_vix concentrated sweep — the headline (HIGH; their 07-13 followup).** Three
   pipeline-native residual_momentum configs PASS the WF gate in-book (blend WF 2.119 / 2.103 /
   2.031 vs probe 2.0611); best cpcv carrier 1.4099 (closest-ever to the 1.5 gate); no config
   carries both axes yet — the sweep target. Concentrate: window 70-160, skip 7-21, percentile
   threshold 0.65-0.85 (percentile_window 252); gates BOTH arms — `vix_term_slope > 0.1..0.7`
   (single + days_since_jump-veto dual) AND `hurst > p40..p50`; structure pinned by evidence:
   combiner `cross_sectional_rank`, monthly rebalance, rank_k 5-10, long_only preferred,
   swing_mid delta ~0.31-0.42. Density target: tens of samples per neighborhood (today: ~1 per
   cell over a 5-dim box). Solo-reject is EXPECTED for this family (host-dependent; all three
   WF passes are solo rejects) — do not let solo verdicts feed back as kill signals.
2. **`days_to_nfp`/`days_to_cpi` regime_range (7,60) → (7,30)** (`indicator_thresholds.py`
   `_INDICATOR_THRESHOLD_TABLE`). Ceilings are 35/34 (monthly countdowns); ~42% of sampled
   gates sit above the ceiling = inert no-ops. Mirrors the already-safe `days_to_opex` (5,30).
   Guardrail noted for any future op-generalization: op `>` near the ceiling flips the failure
   mode from inert to always-false — pair with a ceiling-aware clamp if ops ever open up here.
3. **capitulation rv_rank gate: drop (or re-place) — pending one adjudication.** Their 07-13
   sweep: the gate is unhelpful-to-harmful on clean data at every threshold 50-70, and our
   [50,80] band was calibrated on the pre-Q49 percentile reading (clean drop-day median ~50 in
   kernel units → the gate strangles co-fire; 69/69 decided dead, median 4 OOS trades).
   Dropping the gate ALSO moots their gate-off-split ask (their own words: the bare-drop arm IS
   the gate-off cohort). **Blocked on Crucible reconciling the addendum's "reweight toward
   index" ask with their 07-13 honest-pricing verdict that the index arm is NEGATIVE
   (survivor = single-name high_vol)** — see the receipt relay. swing_short-next-to-swing_mid
   rides the same decision.
4. **`pre_earnings_setup` × vol_event: retire the pairing** (or widen its window if Crucible
   sends a measured parameter). ~450 configs/wk at 91-100% dead; vol_event conversion 0.1%
   (11/10,008). vol_event reverts to its other regime gates.
5. **trend double-gate cap: drop the `days_since_jump`+`gamma_flip_distance_pct` AND-pairing**
   (~300/wk at 93-98% dead; single-gated versions of the same directionals convert at trend's
   healthy 9.7%).
6. **Retire `option_momentum` from the directional pool** (47/wk, 100% dead, median 5 OOS
   trades; the v19 percentile/min_months fix has had a month with ~0 conversions). Tightening.
7. **Remove `gamma_flip` as a MEAN_REVERSION directional** (~100/wk, 94-97% dead in every gate
   combination). Tightening; gamma_flip stays as a regime gate everywhere it is one today.

## Budget arithmetic (their framing, accepted)

Items 4-7 reclaim ~900-1,000 configs/week of structurally-dead emission; item 1 is where it
goes. This is a reallocation, not a throughput change — §7.3 pacing untouched.

## Ritual

Single v32→v33 bump: grammar.yaml header note + archive + D-entry; golden re-pins licensed by
the bump (hard rule #6); items 6-7 are tightenings, items 1-5 are enumeration-policy /
threshold-table changes — ALL ride the one operator-approved bump; full deploy ritual per
`docs/tasks/deploy.md`. Pre-build verification per `docs/tasks/grammar-change.md`: registry
liveness for every touched id from CODE + current snapshot (never INDICATOR_THRESHOLDS.md).
