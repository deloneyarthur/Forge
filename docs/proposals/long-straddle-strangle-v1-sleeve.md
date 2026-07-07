# Proposal: long straddle/strangle — the v1-compatible non-directional long-vol sleeve

**Status:** **DEAD — do NOT build; REFUTED 2026-06-28** by Crucible's pre-check (§0: −27%/−98.6% maxDD at
zero cost, sign not robust, dies at cost). Both in-v1 orthogonal fronts closed on data. §1–9 retained as the
scoping record and as the template if a future long-multileg thesis resurfaces. (Was: SCOPING 2026-06-28.)
**Origin:** operator redirect — after cross-sectional vol_event closed (Crucible `iv_minus_rv` pre-check,
rank-IC −0.015) and plain relval refuted, the remaining *vol-side* in-v1 orthogonal sleeve. Sibling to the
GICS-relval sleeve (D215). Gating ask: `PROMPT_CRUCIBLE_LONG_MULTILEG_CAPABILITY.md`.

## 0. Recommendation — DEAD (do NOT build), per Crucible's pre-check
**REFUTED 2026-06-28** (`../Crucible/docs/handoffs/FORGE_long_multileg_capability_2026-06-28.md`). Crucible had
already run the faithful cheap-vol-conditional long-straddle backtest on 2026-06-25 (real both-leg chain marks,
hold-to-expiry, cost sweep, 88 months, **our exact signal `iv_minus_rv` = `naive_vrp`**) and it fails three
independent ways: (1) cheapest quintile **compounds to −27% / −98.6% maxDD at ZERO cost** (the +4.28% mean is a
lottery artifact); (2) **sign not robust** — `residual_iv_gap` (a better-constructed cheapness measure) gives
the *opposite* ranking (rich > cheap) → noise/overfit; (3) **dies at cost** (−99/−100% by 5%; two-leg ≥5%,
selector-independent). Pre-earnings straddle independently dead (break-even gross, −4% net). So the "pre-check
dead → concede, no build" branch fires: **do NOT build the `LegSpec`/`structure_type` contract change or the
runner refactor.** Both in-v1 orthogonal fronts (this + GICS-relval) are now closed on data. **The §1–9 design
below is retained as the record of what was scoped and why it was conceded** — and as the template if a *future*
long-multileg thesis ever resurfaces (which would first need the §20 hard-rule-9 reconciliation, below).

> **Governance (gates any future multileg):** the spec still reads "no spreads in v1" (§1.3 / §28 / hard
> rule 9, "cannot be relaxed"). Any long-multileg pursuit needs a **§20 Decision Log reconciliation of
> hard-rule-9, operator-ratified, BEFORE shipping** — independent of this dead sleeve.

## 0b. (original scoping recommendation — SUPERSEDED by §0)
Pursue a **long straddle/strangle** as a second in-v1 orthogonal sleeve (the first being GICS-relval). It is
the only v1 structure that supplies a **non-directional long-vol** risk driver — the one orthogonal axis
nothing in v1 currently touches, and the binding constraint (PBO 0.733, the quality×diversity frontier) is
starved for orthogonal drivers. **Prior: uncertain but not refuted** — the double-VRP headwind is real, but the
*cheap-vol-conditional* form is untested and is not touched by the directional refutation. The build is
**heavier than GICS-relval** (multi-leg contract + runner + grammar) and is **gated on Crucible's runner**
(Forge can't price options), so the next step is the capability ask, ideally short-circuited by a Crucible
edge pre-check.

## 1. Why — the orthogonal driver v1 is missing
The binding wall is the quality×diversity frontier at effective dimensionality ~1.5: the strong pool is
trend + mr, ~0.78-correlated. Every in-v1 *directional* orthogonal lever has now closed — relval (0.88
MR-collinear), cross-sectional vol_event (`iv_minus_rv` directional IC −0.015). What remains untouched is
**non-directional long-vol**: a bet on realized vol *exceeding* the implied vol paid, with no view on
direction. That is a genuinely different risk factor from trend/mr, and `iv_minus_rv`'s real content (per
Crucible) is exactly this — "monetizable solely via straddles."

## 2. The v1/v2 boundary is the SHORT LEG, not leg count
A long straddle/strangle is **all-long**: you buy both legs, max loss = premium, net-long-vega, net-debit. It
carries **no short leg → no short-vol tail, no early-assignment hazard, no gate impact**. So by the operative
risk boundary it is **v1-compatible**, even though it is multi-leg. This is *more* conservative than the
grammar review's "debit verticals first" — a debit vertical has a short leg, so by this boundary it is the
real v2. We do all-long structures before anything with a short leg.

## 3. The structure
- **Long straddle:** long call + long put, same strike (ATM) + same expiry. Pure convexity; profits if the
  underlying moves more than the combined premium either way.
- **Long strangle:** long OTM call + long OTM put. Cheaper, wider breakevens; more convex per dollar.
- Invariant (machine-checked, mirrors the grammar review's v2 invariant scoped to all-long):
  **net-debit ∧ net-long-vega ∧ defined-risk**, all legs `side=LONG` (holds by construction).

## 4. The entry — cheap-vol-conditional, NON-directional
This is the structural shift from the current grammar: a straddle config has **no directional signal**. Its
entry trigger is a **vol-cheapness** gate — `iv_minus_rv` / `iv_rank` / `rv_rank` high (RV > IV ⇒ you buy vol
*below* fair). The Goyal-Saretto cheap-vol edge is the thesis: unconditional long vol bleeds (−3%/wk), but
*conditional on cheap implied vol* it can be net-positive. The cross-sectional form ranks the universe by
vol-cheapness and holds straddles on the cheapest-vol names.

## 5. Grammar fit + the gating contracts/runner gap
New surface (as the grammar review documents, §3.4): a `LegSpec`/`legs` model + `structure_type` in
`crucible_contracts` (today `StrategyConfig` is single-leg — `models.py:316`, one option via `SelectorSpec`);
new grammar rules (S6 structure, C5 combiner, P5–6 leg/strike selection, E4 exits, R4 vol-cheap regime);
a `composable_spreads`-style enumeration + a **Crucible multi-leg runner path**. The runner is the gate:
**Forge cannot price options**, so the edge cannot be measured here. `PROMPT_CRUCIBLE_LONG_MULTILEG_CAPABILITY.md`
asks whether the contract/runner already support this, what the additive `LegSpec` shape is, and — decisively —
whether Crucible can pre-check the edge on existing data before any build.

## 6. The two tensions (and why the thesis survives)
- **Double VRP.** Two long legs pay the VRP twice; a crash-neutral straddle loses −3.24%/wk unconditionally
  (Coval-Shumway 2001). The grammar review therefore parked long straddles as "research-only." **Survives
  because:** our entry is cheap-vol-*conditional*, a different bet — and the open question (does cheap-vol
  clear double-VRP + double-cost?) is empirical, answerable by Crucible's runner/pre-check, not by that
  unconditional result.
- **Infra-heavy.** The multi-leg machinery (contract + runner + grammar) is "v2-scale" even though the *risk*
  is v1. **Mitigant:** straddles-first is the lowest-risk way to *build* that capability (all-long,
  defined-risk, zero assignment risk), after which verticals/calendars are incremental. It is smart
  sequencing of an inevitable build, not a free move.

## 7. Test plan (same discipline as relval/vol_event)
Once enumerable: a gated `forced_structure="straddle"` release to Crucible's gate (deterministic seed,
inbox-only, idempotent), **pre-registered** via `forge prereg` (predicted: cheap-vol straddle component
cpcv-p25 / the relevant strong-band metric), evaluated under CPCV (purge ≥ max DTE) / PBO / DSR, charged to
`forge alpha-budget`, later-cohort-confirmed. **Better:** if Crucible's §4 pre-check is feasible, it settles
the sleeve with no build at all.

## 8. Sequencing vs GICS-relval, and honest prior
GICS-relval is the **lighter** sleeve (data ingest, single-leg, in-paradigm) and should not wait on this.
Straddles are the **heavier** bet but the only one that adds the **vol** driver (vs GICS-relval's
**sector-value** driver) — complementary, not either/or. **Honest prior: low-to-moderate** — the double-VRP
headwind is the real risk; the cheap-vol conditioning is the only reason it is worth measuring, and the
measurement is cheap if Crucible can pre-check.

## 9. What kills it
- Crucible's edge pre-check (§4) shows cheap-vol does not predict RV > IV net of double-cost → concede the vol
  sleeve, no build.
- The multi-leg runner doesn't exist and is too costly to build for one structure → defer; revisit if the
  GICS-relval sleeve also stalls and v2 structure becomes the operator's call.
- Execution realism (two-leg slippage on illiquid OTM legs) eats the thin conditional edge → the runner's
  honest cost model will surface this in the gated test.
