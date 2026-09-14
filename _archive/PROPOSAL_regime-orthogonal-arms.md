# Proposal / scoping: edge-magnitude — regime-orthogonal arms (the promotion unlock)

> **CORRECTION (2026-07-15, [[D273]]):** the "worst quartile = bear (2.39×) / ranging (1.33×)" input
> below is corrected to **bear-only (2.08×; ranging 0.90 = hull-CPCV artifact)** on per-block math
> (`FORGE_worst_quartile_regime_label_correction_2026-07-15.md`). The ranging-arm case (premium-selling
> in chop, Path C) must now stand on its own edge magnitude — it is no longer a worst-quartile-crater
> fill; the bear-crater half of the framing is unchanged.

> **STATUS (2026-06-24):** SCOPING — research framing, no code shipped off this doc. The ranging-supply increments shipped separately ([[D150]]/[[D151]] grew mr supply; v22 added the `rv_rank` mr gate); bear was CLOSED for Forge (`worst-quartile-complement-supply.md`). The deeper "regime-orthogonal unlock" lands in Path C, which remains HELD. Historical record below.

Status: **SCOPING (research framing) — no code; defines the problem, the paths, and the first
experiments.** Date: 2026-06-14. Relates to: [[D146]] (the magnitude reframe), [[D148]] (Crucible
greenlight + the "regime-orthogonal arms" pointer), `edge-magnitude-levers.md` (the expressivity
inventory), `worst-quartile-complement-supply.md`. Backing data (Crucible-side):
`probe_results/cpcv_crater_by_regime.json`, `regime_durability.json`, `worst_quartile_regime_eraC.json`.

> **UPDATE 2026-06-15 — the long-options exhaustion is CRUCIBLE-CONFIRMED** (`long-options-exhaustion-assessment.md`,
> `../Crucible/docs/handoffs/FORGE_long_options_exhaustion_consolidated.md`): all four empirical checks confirm
> (gross max 1.40 < 1.5, IC-bound), inventory complete, theory quad-convergent. **The operator's Path-C
> provability gate ("only open v2 if long-options provably can't clear the bar") is now SATISFIED.** Path C
> below is unblocked as a *decision* — still operator-gated, **debit-verticals-first**, safety-program-gated.
> Crucible's sell-side VRP probe (`vrp_short_premium_by_regime.json`: short-vol positive every regime) and
> their sizing-in-flight corroborate the direction. Standing reopener: re-run M1/M2 as the population grows.

## Why this exists — the one lever that can actually move promotions

Everything shipped so far (T1 ranker, T2 ranging supply D150/D151, rv de-emphasis D145) is
**selection / breadth / tail hygiene** — Crucible was explicit and we verified it: it improves *what
the pool holds* but does **not** cross the binding wall. That wall is **edge MAGNITUDE**: every family
is positive in its best regime but **none means a CPCV Sharpe ≥1.5 on any regime slice (pool best
1.10)**; the worst quartile is **bear (2.39×) / ranging (1.33×)**. So the promotion unlock is a single
thing: **an arm with promotion-grade per-regime magnitude in an adverse regime, orthogonal to the
trend/vol-event factors that dominate the pool.** This scopes how Forge — a producer that computes no
metrics (§1.2), options-only, **net-debit single-leg long-premium, spreads banned** — could produce one.

## The structural frame (the hard truth, grounded)

Forge's grammar is **net-debit long-premium** (`Direction={LONG_CALL,LONG_PUT,FLAT}`, `qty≥0`, spreads
banned; D-confirmed, `FORGE_indicator_gaps_response.md` §1). Two consequences set the magnitude ceiling:

1. **The VRP headwind.** Long premium *pays* the variance risk premium on average — you are buying the
   thing that is, unconditionally, rich. Carr-Wu (RFS 2009): unconditioned single-name premium has
   little edge; **conditioning is everything.** Goyal-Saretto (JFE 2009): the documented edge is
   *conditional* long-premium (long where IV is cheap vs the name's own realized — shipped as
   `iv_minus_rv`), and the gross decile spread (~22%/mo) collapses to ~4%/mo **at quoted-spread costs
   — costs, not decay, are the binding constraint.** So within long-premium, magnitude is gated by
   (a) conditioner IC and (b) execution cost, and the headline edges barely survive costs.

2. **The high-magnitude adverse-regime edges are OUT OF v1 SCOPE.** The natural high-Sharpe play in
   **ranging/chop is premium SELLING** (theta harvest — short strangles/iron condors): structurally
   forbidden (short premium + spreads banned). The natural **bear** play is short/put-spread or a
   portfolio **tail overlay**: the overlay is Crucible-owned (`tail_leg`, D148), spreads are banned.
   Long puts *are* expressible (`LONG_PUT`), but a standalone long-put bleeds the VRP (Crucible: the
   `long_short` short leg is net-negative in bear). **So the two regimes the wall lives in are exactly
   where v1's long-premium-only constraint is weakest.**

**Bottom line:** the unlock is unlikely to come from "enumerate harder." It comes from one of three
paths — a higher-IC conditioner, lower execution cost, or a scope expansion — and two of the three are
Crucible/operator-gated. That reframes "regime-orthogonal arms" from a search problem to a
**signal-quality / cost / scope** problem.

## Three paths to magnitude

### Path A — a higher-IC conditioner/signal within long-premium [Crucible-publishes-indicator]
Lift the predictor, not the payoff. The pool's conditioners are IV-level/percentile, `iv_minus_rv`
(Goyal-Saretto), `iv_term_slope`, trend/momentum, dealer-gamma. Candidates with literature support for
*adverse-regime* option returns: **skew / risk-reversal** (crash-risk pricing), **variance-term-structure
slope** (VRP timing), **order-flow / dealer-positioning at higher fidelity** (gamma/charm/vanna),
**cross-asset / macro stress** (credit, rates, FX vol). Reach: each needs Crucible to publish the
indicator (registry) — contract-gated. **Honest:** Goyal-Saretto shows even a *good* conditioner is
cost-bound; a new conditioner must clear costs AND have adverse-regime IC, which is uncertain.

### Path B — execution-cost reduction (convert gross edge to net) [Crucible-gated, partly offered]
Goyal-Saretto says costs are the binding constraint, so *the same signal at lower cost* lifts realized
magnitude. Levers: **constant-maturity construction** (§20, Crucible-offered — removes the theta-bleed
confound, cleaner option_momentum/straddle returns), **liquid-universe / wider-DTE selection** (lower
bid-ask drag), **rebalance discipline**. Reach: §20 is offered (held); the rest is selector/grammar
tuning (Forge-side) + Crucible cost modeling. Lower risk than A, bounded upside.

### Path C — scope expansion beyond long-premium [hard-rule-9 / v1-scope; operator + Crucible]
The structural fix for the adverse-regime magnitude gap: **defined-risk spreads / conditional
premium-selling** (verticals, condors, calendars). This unlocks the *natural* ranging theta edge and a
bounded-risk bear structure — the high-magnitude plays v1 forbids. But it's a major decision: Crucible's
runner, gates (§8.7), and risk model must support multi-leg/defined-risk, and it re-opens hard rule 9
(single-leg long-premium). Biggest upside, biggest lift, fully operator+Crucible-gated.

## Candidate arms (regime × path)

| Arm (thesis) | Regime | Edge basis | Path | Reach |
|---|---|---|---|---|
| Skew / risk-reversal conditioner | bear | crash-risk mispricing predicts put returns | A | Crucible indicator |
| Variance-term-structure timing | high_vol/bear | VRP slope predicts long-vol payoff | A | Crucible indicator |
| Higher-fidelity dealer flow (vanna/charm) | bear/ranging | dealer hedging drives the gamma regime | A | Crucible indicator |
| Constant-maturity straddle | bull/trending | removes theta-bleed cost confound (§20) | B | Crucible (offered) |
| Defined-risk short strangle / condor | **ranging** | theta harvest in chop (the natural ranging edge) | C | scope expansion |
| Put/bear vertical | **bear** | bounded-risk downside, lower VRP bleed than naked puts | C | scope expansion |

## What to ask Crucible (the cheapest, highest-value first move)

Forge can't measure magnitude (§1.2) — Crucible can. Before any build, get the **per-family ×
per-regime magnitude + cost decomposition** (extend `cpcv_crater_by_regime.json` / `regime_durability.json`):
1. **Where is the headroom?** Which (family, regime) cells are closest to 1.5, and is the gap signal-IC
   or execution-cost? (Goyal-Saretto says cost — confirm per cell.)
2. **Would a named new conditioner** (skew, var-term-slope, dealer-vanna) plausibly lift an adverse-regime
   cell, per their data? (Directs Path A.)
3. **What would defined-risk-spread support take** on the runner/gates/contract? (Sizes Path C.)

## Recommended sequencing

1. **Relay the magnitude/cost-decomposition ask to Crucible** (above) — cheapest, and it tells us
   whether the binding gap is IC (→ Path A) or cost (→ Path B) per cell. Do this first; it directs
   everything else.
2. **Literature deep-research scan** — "single-leg long-premium option strategies / conditioners with
   documented risk-adjusted edge in bear & ranging regimes, net of costs" — to harden the Path-A
   candidate list beyond Goyal-Saretto/Carr-Wu. (Offered as the `deep-research` skill.)
3. **Decide §20 constant-maturity (Path B)** — the one cost lever already on the table.
4. **Scope-expansion feasibility (Path C)** — only if Crucible's decomposition says ranging/bear
   magnitude is structurally unreachable in long-premium (likely) AND the operator wants to re-open
   hard rule 9. The biggest, slowest, highest-upside path.

## Deep-research findings (2026-06-14, adversarially verified — 26 sources, 25 claims, 5 killed)

A literature deep-dive (the `deep-research` workflow; full report in the run transcript) returned a
**decisive, sobering verdict** that confirms this scoping's structural hypothesis with external evidence:

- **Path A has NO documented net-of-cost, bear/ranging-conditional, single-leg long-premium edge near
  1.5 Sharpe.** Every in-scope candidate fails ≥1 of {net-of-cost, regime-conditional, EOD-computable,
  single-name (not index)}. The premise is *confirmed* (3-0): unconditioned long premium is structurally
  net-**negative** (SPX variance assets incl. straddles, ann. Sharpe −0.25 to −1.44, Johnson JFQA 2017),
  and the VRP is **dominated by left-jump-tail / "fear" compensation** (59.8% of the VRP from left tails,
  Bollerslev-Todorov JF 2011) — which accrues to the **seller**, the wrong side for this book.
- **Costs are first-order / binding** (3-0): term-structure-slope straddles 27.1%→12.3% net (~55%
  erosion, Vasquez JFQA 2017); the IVOL strategy 1.40%→0.17% (statistically dead at 50% of quoted
  spread, Cao-Han JFE 2013); single-name quoted spreads ~19-20%. So net single-leg magnitude is
  **unestablished, not merely small**.
- **RANGING is the worst-supported regime** — every regime-conditional signal found (CDS-slope,
  order-flow) concentrates in **bear/high-vol** and is **absent in ranging**. The honest read: *the
  ranging arm is fundamentally a short-premium (Path C) problem*, not a long-premium one.

**Path-A shortlist (direction only — pursue a candidate ONLY if Crucible's decomposition says its
adverse cell is IC-bound AND EOD-computable; all are gross/index-level/cost-fragile):**
1. **IV term-structure SLOPE** as a long-premium *timing* gate (buy when slope low/inverted) — the
   strongest direct long-premium-return evidence, but index-level + gross (the *single-name* cross-section
   was refuted 1-2). EOD: VIX/VIX3M spread or per-name IV term slope.
2. **Left-jump-tail / "fear" (VRP = IV²−RV; far-OTM-put risk-neutral jump intensity / LJV analog)** — the
   active predictive ingredient. EOD-computable.
3. **Inverse VOV + inverse IVOL underlying screens** (favor LOW-vol-of-vol, LOW-idio-vol names — high-VOV/
   IVOL buyers systematically lose) — but established on *delta-hedged* returns → partial conditioner only.
4. **Order-flow / put-call-flow imbalance** (price impact ~doubles in crisis → bear-amplifying) — but
   transient, cost-fragile, wants intraday flow (2-1 vote).
5. **Cross-sectional option momentum** as a ranking tilt — full-sample, not regime-specific (weakest).

**Path C verdict (3-0):** the magnitude advantage of premium-selling / defined-risk spreads is real and
is the **structurally correct (seller) side** of the dominant left-tail/VRP compensation — *"the single
change most likely to unlock a promotion-grade bear/ranging arm."* It is the only documented route to a
high-Sharpe **ranging** arm. **Caveat:** the specific net-of-cost per-regime Sharpe of short strangle /
iron condor / put-spread / collar was **not independently quantified** → size it first (the Crucible
relay's part 3 / open question #1).

**Net implication:** within v1's long-premium-only scope, the literature gives **direction, not a
validated edge** — and the highest-leverage producer move is likely the **Path-C scope expansion**
(hard rule 9, operator + Crucible), now backed by verified evidence, *contingent on Crucible sizing the
net-of-cost per-regime magnitude first.* (5 overclaims were killed by adversarial verification — incl.
the single-name IV-term-slope cross-section and "order-flow is the single strongest predictor" — so the
shortlist above is what survived skeptical voting.)

## Priority order (operator decision, 2026-06-14): EXHAUST long-options (A+B) first; Path C is the LAST RESORT

The deep-dive says Path C is the most *likely* unlock — but it's the most *expensive and dangerous*
(cross-system build + correlated short-vol tail risk). So the order is: **fully exhaust the in-scope,
safe long-premium levers (Path A + B) before opening v2 for spreads.** A+B are cheap to rule out and
carry no short-vol-blowup risk; Path C's cost is only warranted once we've *proven* long-options can't
clear the bar. Path C stays scoped (below) but **deferred to "v2," last resort.**

### The long-options exhaustion inventory (work through these before v2)

**Already shipped — confirm each is pulling its weight per-regime** (the Crucible IC-vs-cost read tells us):
`iv_rank` (IV cheap), `iv_minus_rv` (Goyal-Saretto IV−RV), `iv_term_slope`, `option_momentum` (Heston),
trend/momentum (`momentum_252`, …), `hurst`, `adx`, dealer `gamma_flip`, mr oscillators (`rsi`/`bb_pct`/`zscore`).

**Path A — conditioners NOT yet tried (the deep-dive shortlist), by reach:**
1. **IV term-structure SLOPE as a long-premium TIMING gate** (buy when slope low/inverted) — we have
   `iv_term_slope` as a *directional*; the deep-dive's strongest evidence is the *timing-gate* use. **Likely
   Forge-side** (re-apply the existing indicator as a regime gate) — cheapest, do first.
2. **Left-jump-tail / skew conditioner** (far-OTM-put risk-neutral jump intensity; VRP = IV²−RV) — the
   active VRP ingredient. `iv_minus_rv` is VRP-adjacent; a true SKEW/left-tail measure is **Crucible
   indicator**.
3. **Inverse VOV / inverse IVOL underlying screen** (favor low-vol-of-vol, low-idio-vol names) — **Crucible
   indicator** (VOV) / possibly Forge-side (IVOL from EOD returns).
4. **Put-call-flow imbalance** as a single-name conditioner — `put_call_flow` exists (chain-reader caveats);
   **Forge-side** to test.
5. **Cross-asset / macro stress** (credit spreads, MOVE, VIX term) as a regime gate — **Crucible indicator**
   (macro data); bear-concentrated per the deep-dive.

**Path B — execution-cost reduction (a magnitude lever in itself, costs bind):**
1. **§20 constant-maturity straddle** (Crucible-offered, held) — request it; cleans the option_momentum/vol
   edge of theta-bleed cost confound.
2. **Liquid-universe / wider-DTE selection** tuning — Forge-side (selector), lowers bid-ask drag.

**Director:** the Crucible **IC-vs-cost decomposition** (relay parts 1-2, now the priority) says, per
adverse cell, whether the gap is IC (→ add the right Path-A conditioner) or cost (→ Path B). Work the
inventory guided by it. **Only when this is exhausted with no cell clearing the bar do we open v2 (Path C).**

## Path C (LAST RESORT — v2; only after A+B is exhausted) — the probe + test program

A scope expansion to **defined-risk spreads / premium-selling** is NOT a grammar flag — it's a
cross-system program, and the binding question is **safety**, not just viability. Sequence it as
hard gates, cheapest first; do NOT build any machinery until the edge is proven.

**Gate 0 — Viability sizing (cheap, Crucible-side, FIRST).** The relay's Part 3: net-of-cost
per-regime Sharpe of candidate defined-risk structures (put/call vertical, iron condor, collar,
put-ratio) on the era-C book. **If it doesn't clear the bar → STOP** (the wall is just hard; no
expansion). Everything below is gated on this passing. Hard rule 3 holds: the spread sleeve must
clear the SAME §8.7 portfolio bar — the expansion adds expressivity, it never lowers the gate.

**Track 1 — Viability deepening (Crucible).** Full §8.7 + CPCV battery on a hand-authored spread
sleeve, regime-attributed. Does it actually lift the portfolio worst-quartile p25 (the binding wall),
or just the center?

**Track 2 — SAFETY / risk (the hard part; the massive probe).**
- **Correlated book-level tail.** Defined-risk caps loss *per trade* but NOT the book: many capped
  losses fire *simultaneously* in a vol spike → a large aggregate drawdown (Feb-2018 / "volmageddon"
  short-vol crash). The portfolio risk model + CPCV worst-quartile + `max_drawdown_ceiling` must
  capture this — it's the single failure mode that kills a viable-but-unsafe short-premium book.
- **Mechanics under stress.** Assignment / early-exercise / pin risk; whether the "defined" risk
  actually holds through gaps and realistic multi-leg fills (the net debit/credit at true fills —
  the cost question, worse for multi-leg). Probe a candidate sleeve through 2018 / 2020 / 2022.
- **Sizing.** The fractional-Kelly / vol-target sizer assumes long-premium payoffs; capped-loss
  short-premium needs a different risk-of-ruin model.

**Track 3 — Cross-system plumbing (only if Tracks 1-2 pass).** Each is substantial: a **multi-leg
`StrategyConfig`** in `crucible_contracts` (contract gap, hard rule 2); a **multi-leg backtest runner**
(per-leg fills, greeks, assignment) Crucible-side; **§8.7 gates calibrated for spread payoffs**; new
**§3.5 grammar** (leg structure, width, ratio) + a spread-aware sizer/selector Forge-side; **QuantIQ**
multi-leg live execution + margin. This is a multi-quarter, all-three-systems lift — which is exactly
why **Gate 0 must come first**: never build this machinery on an unproven edge.

**Discipline:** the program is *gated and abortable at every step*. The cheap measurement (Gate 0)
decides whether it's worth opening at all; the safety probe (Track 2) can kill it even if viable. Bring
the operator a go/no-go at Gate 0, and a separate go/no-go after the safety probe — not one big commit.

## Honest cap (hard rule 6)
This is the genuinely hard, uncertain frontier — and it may not be fully solvable inside v1's
long-premium scope. Forge cannot manufacture magnitude; it can express archetypes, lean enumeration,
and surface candidates for Crucible to measure. Expect this to be a *multi-step, Crucible-coupled
research program*, not a single increment — and be honest that the answer might be "the high-magnitude
adverse-regime edges require a scope expansion (Path C), not more search."
