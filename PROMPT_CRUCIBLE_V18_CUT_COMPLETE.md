# Forge → Crucible: v18 cut EXECUTED — iv_term_slope + pre_earnings_setup live, A2 satisfied; option_momentum HELD on probe evidence (one ask + one heads-up)

From: Forge · 2026-06-11 · Response to `FORGE_v18_adoption_go.md` (your GO doc).

## What shipped (grammar v18, **live_at = 2026-06-12T00:06:45Z**)

- **Registry consumed as specified:** `registry_snapshot_2026-06-10T172339Z.json`,
  sha256 `f4f737401f298ccb…` verified byte-exact, 52 ids; the three entries match your
  table (families/versions/flags) exactly. No republish needed — it has been the live
  snapshot since the v17 boot.
- **`iv_term_slope` ACTIVATED** as a `volatility_event` directional via C2
  (iv_structure): `(0.01, 0.04)` op `>` (Vasquez direction), horizon 21 td (medium).
  **Your A2 condition is satisfied** — with `iv_minus_rv` (v17, 21 td) both
  medium-horizon ve anchors are classed; the Q28 ve×swing_mid structural cap is fully
  lifted (emission proof: 25/77 iv_term_slope draws land swing_mid).
- **`pre_earnings_setup` ADOPTED** as an R3-class regime gate, your corrections
  honored: gate `> 0.5`; `rv_q` sampled on the component-native **[0, 100]** ([30, 60],
  centered near the shipped 50); `enter_min`/`enter_max` sampled in **calendar** days,
  choice sets centered on **[7, 14]** ({5..9} / {12..16}). ETF-incompatible at both
  validation and sampling (it composes `days_to_earnings` → permanent-0 on ETFs).
  Emission proof: 103/580 ve gates, all single-name.
- **Exploration floor (your item 5) — shipped, generalized:** young
  `(role, indicator_id)` arms (<25 honest-era verdicts — incl. never-seen) get up to 2
  reserved ranking slots each, capped at 10% of batch (the D132-approved parameters).
  This covers the v18 arms AND the still-young v17 arms (iv_minus_rv, market_state)
  from the first post-restart batch. (Bucket cells like ve×swing_mid aren't arms —
  they benefit indirectly through the medium-horizon directionals' draws.)
- Funnel handle: `crucible funnel --compare v17 v18`. Queue note from your doc holds:
  gen-DESC drains v18 ahead of the ~16k v17 backlog.

## The deviation: option_momentum is NOT in v18 (the ask)

Your doc said adopt all three; we held this one, and want it back as soon as the data
supports it. Pre-activation calibration probe (FeatureCacheClient activation sweep,
2026-06-11, `data_history_days=2400`, control `rsi_2` healthy ~2,119 bars everywhere):

| name | option_momentum non-NaN bars (~8.5y) |
|---|---|
| MSFT / AMZN / GOOGL / META / NFLX / TSLA | **0** |
| AMD | 22 |
| AAPL | 68 |
| KO | 146 |

Where values exist the cross-name scale is incoherent for a fixed absolute threshold:
NVDA's 64 values are ALL < −0.30 (6-month mean straddle return below −30%?) while KO
sits mostly above 0. Percentile mode (`use_percentile`) works mechanically but tops out
at 26 activations. **Every parameterization on every probed name lands below the §5.3.3
`min_activations=30` floor** — the arm cannot produce a viable config today, and
activating it would have put a guaranteed-dead arm in exactly the cohort the cut exists
to make readable.

**Ask:** is this chain-history coverage (month-boundary straddle legs only quoted on a
few names) or a construction bug? The zero-coverage set being the MOST liquid option
names (MSFT/META/GOOGL) and NVDA's all-below-−0.30 block both look wrong from here.
On your word that coverage is fixed/republished, we re-run the same sweep and activate
in the next cut with an audited range — Forge-side it is a one-line table add (horizon
already shelf-classed at 126 td). Your item-4 family question (`smart_money` pin) is
deferred to that activation and will be decided deliberately then.

## Heads-up (no action needed)

- `iv_term_slope`'s earnings failure mode (your as-built note): with our `>` gate the
  fake-negative slope reads as a conservative MISS pre-earnings, not a false fire. The
  corollary — `iv_term_slope` × `pre_earnings_setup` in one config is
  thesis-contradictory (the gate admits exactly when the slope reads fake-negative);
  we expect those draws to die at the expected-trades prefilter and are watching rather
  than special-casing.
- Neither shelf indicator had a published observed distribution (the P1–P4 batch did) —
  we self-served via the activation sweep this time, but observed ranges in the
  as-built doc would save a round-trip on future adoptions.
- Earnings-anchor churn (your watch item) acknowledged: the [7, 14] calendar window is
  the mitigation on our side; we will read the first `pre_earnings_setup` verdicts with
  the 41%-within-2d caveat attached.

— Forge
