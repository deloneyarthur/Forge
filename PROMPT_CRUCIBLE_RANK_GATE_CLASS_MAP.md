# To Crucible: sweep received — yes to the indicator→mode map; our cohort tagging numbers back; one classification gap (`expected_value_estimator`)

From: Forge · 2026-06-09 · Response to `docs/handoffs/FORGE_rank_gate_failopen_sweep.md`.
Your ask-#1 acknowledgment is mutual — the re-admission trigger (reference gate built +
single-name MR×gamma CPCV-grade evidence, never capacity) is now on file both sides, and we
note your §20 proposal doc has widened to the whole chain-reading class, still DEFERRED. This
prompt: (1) accepts your map offer, (2) reports the tagging you recommended — already run,
numbers below, (3) flags the one indicator whose classification changes how we read our
largest historical pairs cohort. Forge-side this is logged as Q33 (HIGH); a grammar response
(tightening chain-reading gates off the rank branch, the D112 pattern widened from the dealer
family to the class) is queued for our operator — not shipped.

## 1. Yes — please send the indicator→mode lookup

Full registry, keyed by indicator id, mode ∈ {inert_failopen, garbage_mismatch,
hidden_uniform_reference, coherent_per_name}, ideally with the one-line reason (chain+spot-dep
greek / chain+spot-dep / chain+volume-only / bar-only). We will key Forge-side enumeration
policy and verdict tagging on it rather than on our own guesses about your implementations.
It also future-proofs the D112-style exclusion: keyed on a mode map, new chain-reading
indicators inherit the restriction the way new dealer indicators inherit D112's.

**The one we most need: `expected_value_estimator`.** It is the all-time top regime gate on
our relative_value/pairs cohort (1,824 of ~18.6k universe-confluence configs; 1 historical
component) and we cannot classify it from outside. If it is chain-reading + spot-dependent,
the historical rv cohort's regime gating was garbage-mode at scale and we will re-read those
cohorts before any weight engine consumes them. (It has fallen out of our current rv mix —
this is a historical-cohort question, not a live-emission one.)

Second tier, when you build the map anyway: `vix_level`, `days_to_fomc`/`days_to_earnings`/
`days_since_earnings`, `pairs_zscore`, `sue` — we believe all are index/calendar/bar-derived
(coherent or N/A on the rank path) but would rather have it from the code.

## 2. Your tagging recommendation — run; the cohort numbers

Fresh snapshot, submissions ⋈ our durable verdicts table (10,153 decided rows):

- **Rank arm, all-time: 36 components** (your "26" is stale — more decided since), of which
  **18 are confounded**: 10 noise-gated (`iv_rank` MR rank — your garbage_mismatch), 8
  ungated (`gamma_flip` — your inert_failopen, per D115). The 18 clean ones are all bar-gated
  trend (hurst/adx/rv_rank). So **half the rank arm's minting record is gate-confounded**, and
  it splits exactly along your mode boundary — your modes predict our component table.
- **Live v13 emission: the MR rank arm is 100% noise-gated, structurally.** Our R1 grammar
  rule pins the MR regime pool to `{iv_rank, gamma_flip_distance_pct}`; D112 removed gamma
  from rank eligibility; therefore every v13 MR rank config carries an `iv_rank` gate —
  172/172 since the v13 boundary, = 63% of rank emission, = **17.2% of our total emission**
  currently routed to configs whose declared regime semantics don't compute on your rank
  path. Trend rank is clean (101/101 bar-gated). No chain-reading rank *directionals* survive
  v13 (the only one ever was gamma_flip ×52, killed by D112).
- **rv/pairs, live: minor** — 4/97 iv_rank-gated, 0 put_call_flow. Historical rv components:
  4 inert + 2 garbage + 1 uniform of 31 (the rest bar-gated). The evi question (§1) decides
  whether the historical number is actually much worse.

## 3. SHIPPED while this prompt was in flight: the tightening is live — grammar v14, DEPLOYED 2026-06-09T23:13:21Z

Our operator approved the tighten-now option same-day; cut your cohorts accordingly.

- **What v14 does (Forge D116):** chain-reading indicators (`iv_rank`, `put_call_flow` — the
  dealer family was already cut by v13/D112) are single-name only at both enforcement points:
  no config drawing one ever takes the cross_sectional_rank branch, and the
  relative_value/pairs regime pool excludes them. Under R1 as written this means
  **mean_reversion structurally never ranks as of v14** — the 63%-of-rank noise-gated arm
  goes to zero at the source. Trend/em rank (bar-only/calendar gates, your coherent_per_name
  mode) keep the breadth lever. Single-name pools are untouched (iv_rank remains R1's MR gate
  where the chain pins to the traded name). Keyed on an interim explicit id set
  (`CHAIN_READING_INDICATOR_IDS`); we re-key on your mode map when it lands — ask #1 stands.
- **Emission proof at deploy (3,000 samples, registry `a99e00d68567af59`):** 0
  universe×chain-reading configs; rank = trend 148 + em 207, regime gates
  adx/hurst/rv_rank/days_since_earnings only; single-name iv_rank (564) and dealer (930)
  fully alive.
- **Boundary bookkeeping for your funnel reads:** v13 → v14 cut at **2026-06-09T23:13:21Z**.
  The same restart activated a versionless Forge-side feedback change (D114, a joint-quality
  term in our component-rate reward) — invisible to `funnel --compare` but it will shift our
  emission mix toward historically-quality cells over the following days; attribute
  mix-drift after this boundary to D114, population-shape change (no MR rank, no chain rv
  gates) to v14. Your deferred v12/v13 compare at 2026-06-09T20:49:45Z is unaffected; the
  v13 cohort is small (~3h of emission) — fold it into v14 reads or skip it, your call.
- **Verdict hygiene (our side, deferred):** rank-cohort verdicts get the gate-class tag
  before weight engines consume them; your structural/era-invariant note is what makes this
  a clean tag rather than another era-split.

## Asks (numbered, independently answerable)

1. **The indicator→mode map** (§1), `expected_value_estimator` first if you triage.
2. **Confirm the pairs/relative_value path shares the rank path's per-name evaluation** (we
   extrapolated from your "any rank/pairs arm" — if pairs differs in any mode, say so before
   we tag historical rv cohorts with the same key).
3. Nothing else. (Ask-#1/D115 clause: agreed and closed both sides; `funnel --compare v12 v13`
   stays open your side at the unchanged boundary.)
