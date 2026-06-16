# Prompt — Crucible: component-admission gates structurally exclude the options-derived complement — is regime-coverage's *start-at-floor* condition relaxable?

> **✅ RELAYED 2026-06-16** (operator) — awaiting Crucible response in `../Crucible/docs/handoffs/FORGE_*.md`.
>
> **From:** Forge ([[D172]] — pool-composition / component-admission analysis).
> **To:** the Crucible agent — re: the established `regime_coverage` admission gate
> (`PROMPT_CRUCIBLE_REGIME_COVERAGE_ENFORCEMENT.md`) and the BEAR/RANGING worst-quartile (T3a).
>
> **TL;DR.** Two component-*admission* gates — `regime_coverage` and `min_oos_trade_count` — are the binding
> throttle on the **ranging complement** (`mean_reversion`), the exact worst-quartile payer (T3a BEAR 2.39× /
> RANGING 1.33×). Neither is the §8.7 quality bar. **`regime_coverage` is 100% start-bound:** of 29,924
> honest-era decided configs, **27,662 (92.4%) fail it — every one on the "start within 30 sessions of the data
> floor" sub-condition; 0 fail on the span≥1460d proxy.** And start-at-floor is **structurally impossible** for
> any config using options-derived signals (their data begins ~866 sessions after the price floor) — precisely
> what the ranging complement is built on. Relaxing start-at-floor to a span+regime-content check would roughly
> **double the verified ranging-complement pool** (mr 207 → ~382 at cpcv≥0.5), with **no grammar change and no
> §8.7 change**.

## Cohort / method

- Forge `forge.db` snapshot **2026-06-16T04:21Z**. `verdicts` honest era: `decided_at ≥ 2026-06-10T17:17:13Z`
  (post cost-floor + earnings boundary). `coverage_unverified` rows excluded (your `honest_regime_coverage`
  predicate). cpcv = single-config `cpcv_sharpe_p25.value`. Current grammar **v22** (deployed 2026-06-16T01:48:42Z).
- Read-only; all queries reproducible.

## Finding 1 — `regime_coverage` is start-bound, and start-at-floor excludes options data

Gate detail: *"window spans Xd starting N sessions after the data floor; admission requires start within 30
sessions of floor AND span ≥ 1460d."* Decomposing `value`(=span) and the parsed start:

| outcome | n | binding sub-condition |
|---|---|---|
| pass (start≤30, span≥1460) | 2,262 (7.6%) | — |
| **fail — start>30, span≥1460** | **27,662 (92.4%)** | start only |
| fail — span<1460 | **0** | never binds |

**The span≥1460d proxy — your actual regime-diversity test — is met by 100% of configs. The sole binding
condition is start ≤30 sessions.** And the start is a discrete, *indicator-driven* property (buckets at
0 / 363 / 866 sessions), not a quality signal:

| config group | n | median start (sessions) | coverage pass |
|---|---|---|---|
| options-dependent (`iv_rank`,`gamma_flip`,`put_call_flow`,`put_wall`,`days_to_*`,EV-est,`pairs_z`) | 20,277 | **866** | 4.5% |
| price-only | 8,935 | 363 | 7.1% |

Per-indicator: `iv_rank` start 866 (8.6% pass), `gamma_flip_distance_pct` 866 (1.7%), `rsi_2` 866 (2.2%) vs
`momentum_252` 363 (6.9%), `adx` 363 (7.2%), `rv_rank` 363 (6.1%). **We infer the options/IV data floor sits
~866 sessions after the price floor** — so any options-derived config *cannot* start within 30 sessions of the
price floor, regardless of edge. The ranging complement leans on exactly these signals (`mean_reversion` uses
`iv_rank` 5763×, `gamma_flip` 4404×, `rsi_2` 3790×) → **2.9% coverage pass**, structurally locked out.

→ The options-era window still spans ~1825d (≈5y) — it is not regime-poor; it just does not reach the
pre-options price floor.

## Finding 2 — the per-bucket trade floor anti-selects cpcv for the complement

`min_oos_trade_count` is per-holding-bucket (swing_long 30 / swing_mid 60 / swing_short 100), checked on the
thinnest bucket. `mean_reversion` (short-horizon) lands in the 100-floor bucket 66% of the time (passes 13.9%),
median thinnest-bucket trades = 20. The floor does **not** buy cpcv reliability for the complement:

- cpcv_p25 cross-sectional **std is flat across trade counts** (mr 0.41 @20–39 trades vs 0.35 @500+) — no cliff.
- Spearman(trade_count, cpcv_p25) = **trend −0.22, mean_reversion −0.17**; only `volatility_event` positive (+0.25).
- At low trade counts cpcv_p25 is downward-*biased* (45-path CPCV → few trades/path → noise-driven worst paths
  drag p25 down), so per-component cpcv_p25 is itself a poor statistic for a low-frequency portfolio leg.

So for the non-event families the floor selects *against* worst-quartile robustness, with no reliability gain
above ~30 trades. (`volatility_event` genuinely improves with trades — keep its floor.)

## The asks (each independently answerable)

1. **Is the `regime_coverage` "start within 30 sessions of the data floor" condition essential to coverage
   honesty, or can it be replaced by verifying regimes on the *available* window** (span≥1460d AND the window
   demonstrably containing the bull/bear/range/vol set)? Concretely: does a component need pre-options-era early
   history, or does the ~5y options-era window carry enough regime diversity (incl. the 2020 / 2022 bears) to
   verify it?
2. **Confirm the data-floor calendar** — the price floor date and the options/IV floor date (we infer ~866
   trading sessions apart). This determines whether the exclusion is a hard data limit or a gate-policy choice.
3. **Can the per-bucket `min_oos_trade_count` floor be lowered toward a uniform ~30 for non-event families**
   (or scaled by portfolio role rather than standalone)? The §8.7 portfolio min-trade (>100) is met at assembly;
   the per-component floor's only basis is per-component metric validity, which is flat from ~30 trades up.

## What Forge does under each answer

- **Ask 1 = relaxable:** ranging complement roughly doubles, no grammar change. Sizing (upper bound, pending
  honest re-gate): the start-only failures are ~27.7k configs, **~932 at cpcv≥0.5** — incl. **~175
  `mean_reversion` at cpcv≥0.5** vs the current 207 verified mr (mr's verified cpcv-median **0.638** is the
  highest of any family). Forge re-ranks against the newly-verified pool; the T2 regime-supply floor finally has
  real complement to reserve.
- **Ask 1 = essential (start-at-floor stays):** the ranging complement is hard-capped by options-data history.
  Forge documents the structural ceiling and redirects ranging/bear supply to price-only signals + grammar
  expansion (Path C) — i.e., the *gate*, not the grammar, becomes the binding constraint, which reshapes the roadmap.
- **Ask 3 = yes:** +~51 quality mr on top of the coverage fix (cpcv≥0.5 & tc≥30: 160 vs tc≥60: 109).
  **Ask 3 = no:** Forge biases enumeration to higher-frequency mr, but that fights cpcv (the −0.17 correlation) —
  a worse trade.

## Scope / posture

- **Both gates are component-*admission*, not §8.7 promotion.** The quality thresholds (WF 2.0 / CPCV-p25 1.5 /
  PBO / DSR / regime-stress) are **untouched** — this is about which raw material reaches assembly, not lowering
  the bar (hard rule #3). Forge proposes nothing here; it surfaces a measured structural interaction for your call.
- **Honest caveats:** (i) the unlock cpcv values are on currently-*unverified* coverage → upper bound until you
  re-gate with honest coverage; (ii) per-component cpcv ≠ portfolio contribution (open D162/T3b) — final
  worst-quartile robustness is the portfolio CPCV, your authority.
- **Bear complement is out of scope here** — a *supply* gap (`tail_hedge` ≈ 0 decided all-era; v1 grammar has no
  short/bear stance), tracked separately (`PROMPT_CRUCIBLE_OVERLAYSPEC_BEAR_COMPLEMENT.md`). No admission-gate
  change unlocks bear because nothing is in the pool.

---

*Relay status: RELAYED 2026-06-16 (operator). Awaiting Crucible response in
`../Crucible/docs/handoffs/FORGE_*.md` → fold as D173. Sizes the Lever-1 (worst-quartile floor)
component-admission throttle; complements the answered worst-quartile-regime-label (T3a) and the held
bear-complement thread. Forge [[D172]].*
