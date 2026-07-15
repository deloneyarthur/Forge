# Proposal: v34 — census dead-dimension retirements (two items; three census asks resolve without a build)

Status: **SCOPING — operator-gated grammar bump; nothing ships off this doc.**
Date: 2026-07-15. Source: `FORGE_grammar_census_dead_dimensions_2026-07-15.md` (companion to
the generation-health addendum → [[D275]]/[[D276]]). Census: 228,021 configs decided
07-01→07-15; healthy-gate baseline 8-14% component rate.
Response relay: `PROMPT_CRUCIBLE_CENSUS_RESPONSE.md` (held for carry).
Relates to: [[D276]] (v33 — the pairing-level subset of ask 3), [[D257]] (ask 2 already
shipped), [[D107]] (the gamma_flip gate's admission lineage), [[D216]]/`orthogonal-family-
supply-for-pbo.md` (the ve floor ask 5 collides with).

## Build items (the v34 bump, if approved)

1. **Exclude BKNG + BRK.B from single-name sampling** (census §1: 100% WF=0.0 at n=703/431 —
   per-contract volume never clears the v1 selector liquidity floor; ~$4-5k underlyings also
   blow the 2%-of-equity per-trade budget on a single contract). Both are live tier_2 names
   in our pool today. Mechanism: a `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` exclusion in
   `_pick_underlying`'s pool build (the `_NO_EARNINGS_UNDERLYINGS` pattern — a frozen list is
   acceptable here because the mechanism is Crucible-measured per-name, not classifiable from
   the ticker; revisit when their queue-time liquidity preflight ships, which is the durable
   fix and makes the list retirable). "Until we say otherwise" honored — re-admission on their
   relay. NOTE: this cannot stop cross_sectional_rank baskets from touching these names
   (underlying=None; the universe is theirs) — flagged in the response.
2. **Retire `gamma_flip_distance_pct` as a regime gate from EMISSION, globally** (census §3:
   12,088 uses, 0.1% component rate, 79% WF=0.0 — ~1/100th of healthy gates, everywhere, not
   just the v33-flagged pairings). Removes it from the MR R1 pool (D107 admission), the trend
   R2 pool, and the any-id pools (tail_hedge / regime_arbitrage). Predicates untouched
   (emission-side, the D276 pattern — submitted lineage stays valid); the R1/R2 rule TEXT is
   untouched (the pools are code-side). The capitulation family is unaffected (gate pinned
   rv_rank); MR keeps 6 gates, trend keeps 5. gamma_flip stays enumerable as a VOL_EVENT
   DIRECTIONAL only if the ve arm survives ask 5 (see below) — its MR-directional use died in
   v33. Supersedes the v33 assumption that single-gated gamma_flip cells were alive (they are
   not in the census; D276's test comment gets a correction note in the build).

## Census asks that resolve WITHOUT a build

- **Ask 2 (`zscore_reversion_exit`): ALREADY SHIPPED — D257/v25 (2026-07-08)** dropped it from
  mean_reversion; it remains only on `relative_value`, the actual pair template — exactly the
  "fence it to a pair template" option. The census's 13,947 declares are the pre-v25 queue
  backlog draining through decisions (the window counts DECIDED, not submitted). Verification
  offered to Crucible: split the census by `grammar_version >= v25` → ~0.
- **ASML (ask 1, third name): NOT IN OUR UNIVERSE** (tier lists checked 07-15) — our
  single-name draws cannot produce it; their ASML configs are rank-basket exposure or stale
  cohort. Nothing to exclude; their queue-time preflight is the only lever.
- **Ask 4 (shrink the event-proximity gate family): DEFERRED ON THEIR OWN CONDITION.** The ask
  is "pending the nfp/cpi prior fix; revisit only if the fixed-prior cohort shows life" — v33
  (deployed today) IS that fix. Sequencing: read the v33-cohort funnel first. Structurally the
  family is also inseparable from vol_event (R3's pool is exclusively event-proximity gates),
  so most of this ask collapses into ask 5.
- **Ask 5 (shrink vol_event's share): BLOCKED on a Crucible-internal contradiction + an
  operator call.** The **D216 orthogonal-family floor is ACTIVE (`volatility_event >= 0.20`)**
  — installed because Crucible's PBO relay named single-name ve the SOLE validated
  PBO-orthogonal family (book real CSCV PBO 0.107). The census now reads the same arm as
  EDGE-ABSENT (0.1-0.3% across all directionals). Both positions are theirs; the floor cannot
  be lowered on one relay while the other stands (and dropping it is a de-facto loosening of
  the decorrelated-supply commitment). Adjudication requested in the response relay; the
  operator owns the floor either way.

## Budget

Items 1+2 free ~1,370 configs/2wk (dead names) + ~12k gate draws/2wk — reallocated by the
learned weights (no manual concentration, per their "deliberately NOT asked" note).

## Ritual

One v33→v34 bump; both items are emission-side (`rules:` text unchanged); goldens re-pin
licensed; full deploy ritual. Item 2 flips one v33 test's premise
(`test_v33_gamma_flip_still_an_r1_regime_gate`) — re-pinned as part of the build, with the
census cited.
