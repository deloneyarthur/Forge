# Path C — defined-risk scope expansion (grammar v2): PARKED resume dossier

> **STATUS (2026-07-08):** OPEN / PARKED — **RE-PRICED (§0 below): resume signals #1 and #2
> are now MET**, quantified by the alpha-budget retrospective (`_archive/ALPHA_BUDGET_SCOPE.md` §7).
> The decision to un-park remains the operator's; nothing is sent, nothing is built.
> (Prior banner 2026-06-24: held as last resort, provability gate satisfied.)

## 0. RE-PRICING 2026-07-08 — what changed since parking (operator decision brief)

**Requested context:** the operator asked whether Forge (not Crucible) is the viable half of
the pipeline; the answer ran through the Dim-C alpha-budget retrospective
(`scripts/alpha_budget.py`, results `_archive/ALPHA_BUDGET_SCOPE.md` §7, committed `f1ade2e`). This
section re-prices the parked decision against §3's resume signals. It advocates a *first
step*, not the build.

**Resume signal #1 (promotion drought in practice) — MET.** Since parking (06-15) the entire
in-scope lever program ran to completion: F3 ranker wiring, quality lane, prefilter flips
(cumulative_trading, exclude_regime_filter), ve orthogonal-family floor, gate-tail re-wire,
exploration holdout (D256: "the teed-up lever list is now exhausted"), plus grammar v20→v24
(hurst/rv_rank/MR-rank/trend D236/MR D254 slices). Standing promotions: **zero**. The only
`promote` verdicts ever (07-01/07-02, 2 mr configs) were fullhist-refit flukes, re-gated to
reject on 07-03 by a campaign-charged DSR (n_trials=46,131).

**Resume signal #2 (the M1/M2 monitor firms the verdict) — MET, and stronger than the signal
asked for.** The alpha-budget retrospective replaces the monitor with a closed answer:
- Standard-window basis, honest slice (n=10,004 configs): **max cpcv-p25 = 1.343** — the
  D152 ~1.40 gross wall did NOT creep up as the population grew ~10×.
- The running max tracked **~0.7σ below** the zero-edge expected-max envelope for the whole
  campaign; the observed max is statistically unremarkable against a noise search at any
  plausible effective-N. **Accumulation mechanically cannot reopen long-options** — the
  noise bar rises with every additional trial, so signal #2 can never firm further than this.
- Every honest cpcv-p25 ≥ 1.5 ever recorded (2.99/2.17/1.97/1.87) is a **fullhist-refit
  re-measurement** (post-selection, longer window — e.g. 0.125 standard → 2.99 refit), not
  an organic wall-break. Sizing analyses for Path C must use the standard basis.
- Final out-of-sample confirmation is pre-registered: **prereg `098ea730d5f2`** (v24+burst
  cohort honest max ≤ 1.479; resolves at honest n ≥ 3,000 or **2026-07-21**). A breach
  reopens the noise question and pauses this re-pricing.

**New quantitative bar any Path C sleeve must clear (from the charged-DSR inversion).** The
07-03 re-gates revealed Crucible's Step-4 campaign-charged DSR (deflates `sharpe_baseline`,
T = trade count; reproduced to spread 0.011). Standalone promotion is now the triple:
**cpcv-p25 ≥ 1.5 AND WF-median ≥ 2.0 AND sharpe_baseline ≥ 1.254 at today's 46k trials
(≥ 1.303 @ 100k, ≥ 1.359 @ 250k)** — Path C configs inherit the campaign multiplicity, so
the sizing ask (§4) must measure whether debit structures reach that triple net-of-cost,
not just the CPCV lift. Rollout status of Step 4 as a standing gate is an open Crucible
question (`PROMPT_CRUCIBLE_ALPHA_BUDGET_DSR.md`).

**The in-v1 alternative weakened (07-07).** The "single-name vol_event = first promotable
book in v1" thesis kept the park comfortable: its decorrelation half stands (book CSCV PBO
0.178), but its magnitude half sits at ~1.0 vs 1.5 with no identified in-v1 lever, and
Crucible triple-refuted the vol-event DIRECTION conditioning ask (call_wall/put_wall, §2c.1
retraction, v24 handoff). Nothing in-v1 is currently pointed at the magnitude half.

**What the grammar review sharpened (2026-06 `GRAMMAR_REVIEW_AND_EXPANSION.md` §3).** Tier 1
= debit verticals (same signals, defined-risk, recovers part of the VRP bleed, stays
net-long-vega OTM/ATM); Tier 2 = calendars (new forward-vol axis, pays in RANGING); the
machine-checked **net-debit ∧ net-long-vega ∧ defined-risk invariant REPLACES this dossier's
rung ladder** — §5's rungs 2–3 (credit/naked) are out-of-identity: drop/quarantine, do not
size them as an entry path. Budgeted pitfalls: multi-leg execution realism (~53% of bid-ask
width four-leg), early-assignment breaking "defined risk", and the multiplicity cost of a
combinatorial structure space (charge it to the alpha budget — the §0 triple already prices
that in via n_trials growth).

**Known build surface + governance (Crucible's 06-28 capability answer, unchanged).**
Contracts: additive `legs`/`structure_type` is feasible (≥1.22.0; must join the config_hash
exclusion set at unset sentinels). Crucible runner: ~800–1,200-line refactor. **Governance
gate first:** a §20 reconciliation of Crucible's hard-rule-9 ("no spreads in v1", spec
§1.3/§28) must be operator-ratified BEFORE any byte ships — independent of, and prior to,
all sizing outcomes.

**The decision as it now stands.** The first step is unchanged from §4 and is still cheap,
reversible, and commits nothing: refresh + send the held sizing relay
(`PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` — drafted 06-15, so it PREDATES the
charged-DSR triple, the standard-basis discipline, and the net-long-vol invariant; refresh
before sending). The only real timing question is **send now vs after prereg `098ea730d5f2`
resolves (≤ 07-21)**. Off-ramps in §3 stand verbatim; if the sizing comes back short, the
remaining exits are (a) the promotion-criterion revisit (the standalone ruling was explicit
and stands — but the alpha budget now quantifies its cost: a ~1.0 decorrelated book exists
and clears PBO today), or (b) reporting the frontier as genuinely capped. Not advocated
here; listed for completeness.

Status: **PARKED 2026-06-15 (operator) — explore later "when the time arises."** This is the single
entry point for resuming the Path-C question. It consolidates the decision, the resume signals, and the
first step; it does **not** re-derive the analysis — the detail lives in the docs cross-referenced below.

> **One-line state:** long-options is Crucible-confirmed exhausted for promotion-grade adverse-regime
> magnitude (D152); the operator's Path-C provability gate is **satisfied**; the operator chose to **hold**
> the scope-expansion exploration rather than open it now. Nothing is sent, nothing is built.

> **⚠ UPDATE 2026-06-15 ([[D154]]) — a brief D153 "precondition reopening" was RETRACTED the same day; the
> provability gate stands SATISFIED.** D153 reopened long-options on the belief the vega/IV-cost axis was dark
> (`iv_rank` a NaN stub → §3.5 R1 unsatisfiable). **That was a stale-doc error** — Crucible confirmed `iv_rank`
> has been live since D031 (2026-05-15), and the **strongest vega-conditioned near-miss craters on CPCV
> (0.70).** So the exhaustion is reinforced, not reopened; Path-C's provability gate ([[D152]]) is **SATISFIED**
> (no "pending" qualifier). Two **low-EV** in-scope residual threads remain (joint conditioning; learned
> conditioner — `path-a-rich-conditioning.md`), pending an operator decision; they do not block Path C. Path C
> stays **PARKED by operator choice** (the original reason — last-resort, cross-system, thin margin), not by a
> missing precondition.

## 1. The parked decision (what + why)

**What:** we are NOT, for now, pursuing a hard-rule-9 grammar v2 scope expansion to defined-risk multi-leg
structures (the path that would let Forge harvest the VRP instead of paying it). The viability-sizing relay
to Crucible is **drafted but HELD, not sent** (`PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md`).

**Why park it (not kill it):** Path C is the *likely* promotion unlock, but it is the operator's explicit
**last resort** — a multi-quarter, **cross-system** build (Forge grammar v2 + multi-leg contract/runner +
§8.7 gate recalibration + sizer + QuantIQ execution) that also carries **correlated short-vol tail risk**
(a book of defined-risk spreads can still lose *together* in a vol spike — the Feb-2018 "volmageddon"
pattern). With long-options only *just* confirmed exhausted (gross ~1.40, a **thin** margin Crucible itself
called "not comfortable"), committing now to the biggest, riskiest build in the roadmap is premature. Park,
let the cheap signals accrue, resume deliberately.

## 2. Where we are (confirmed state — pointers, not re-derivation)

- **Long-options exhausted, Crucible-confirmed** (quad-convergent: our 2 deep-dives + Crucible's empirical
  4-check battery + their independent 22-source literature sweep). Decisive read: max **gross** CPCV-p25
  ~1.40 < 1.5 → **IC-bound, not cost-bound** (cheaper execution can't unlock it). Full detail + the M1–M4
  numbers: `long-options-exhaustion-assessment.md`, [[D152]].
- **The adverse regimes that need an arm:** **bear** (worst-quartile ~2.39×) and **ranging** (~1.33×). No
  in-scope long-premium lever reaches the ~1.5 bar there.
- **Crucible already points at the sell side:** `vrp_short_premium_by_regime.json` — short-vol positive in
  *every* regime, strongest in low-vol/calm; their debit-vertical **sizing is in flight** (un-surfaced,
  since we held the relay).
- **The Path-C program of record** (gated probe+test stages, full structural framing):
  `regime-orthogonal-arms.md`. **The exhaustion analysis:** `long-options-exhaustion-assessment.md`.
  **The directive:** [[exhaust-long-options-before-v2-spreads]].

## 3. When to resume — the signals (operator decides; these are pulls, not gates)

Revisit Path C when one or more of these holds:

1. **Promotion drought persists in practice, not just theory.** The long-options base + all shipped hygiene
   (D145–D151, F3 ranker wiring, T2 ranging supply) is fully exploited and the pipeline still yields ~0
   full promotions over a meaningful number of *additional* decided items — confirming the in-scope frontier
   is tapped in the live stream, not only in the snapshot.
2. **The standing M1/M2 monitor firms the verdict.** As the decided-CPCV population grows, gross stays < 1.5
   (the thin 1.40 does not creep up). That removes the "maybe long-options quietly reopens" hedge that
   currently makes a scope commitment premature → the exhaustion is solid beyond the finite snapshot.
3. **Operator capacity + cross-system timing.** Path C needs deliberate, coordinated bandwidth across Forge,
   Crucible, and QuantIQ — not a spare-cycle build.
4. **A pull from Crucible's sizing.** If Crucible surfaces debit-vertical sizing (in flight) that is strongly
   promotion-grade with an acceptable tail, that is itself a reason to un-park.
5. **A scheduled reassess checkpoint** ([[pipeline-vision-roadmap]]) naturally surfaces it.

**Off-ramps (when NOT to do Path C at all):**
- **The monitor REOPENS long-options** — a bear/ranging *gross* creeps to ≥ 1.5 as more items decide → Path C
  is moot; chase the (cost-bound, Path-B) long-options opening instead.
- **Crucible's sizing shows no rung clears the bar net-of-cost** (even rung 2/3) → Path C is *also* not the
  unlock; the producer's promotion frontier is genuinely capped at current scope — report that, don't build.

## 4. How to resume — the first step, then the gated stages

**First step (cheap, reversible, commits nothing):** send the already-drafted
`PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` — it asks Crucible for net-of-cost per-regime CPCV magnitude
**and** tail/safety, **rung by rung**, and the **lowest rung that clears the same §8.7 bar** per adverse
regime. That number is the whole decision: it tells us whether the magnitude advantage justifies the build,
and at what safety cost.

**Then, only if the sizing justifies it,** the gated program in `regime-orthogonal-arms.md` runs in order —
**(i)** viability sizing (the relay above) → **(ii)** §8.7/CPCV magnitude confirmation → **(iii)** the SAFETY
probe+test program (the "massive probe and test" the operator requires — correlated-book tail, drawdown,
volmageddon stress) → **(iv)** cross-system plumbing (grammar v2 + contract/runner + gate recalibration +
sizer + QuantIQ). No grammar v2 byte is written until (i)–(iii) pass and the operator calls it.

## 5. The structure spectrum (risk-ordered — enter at the lowest rung that clears)

- **Rung 1 — net-debit, defined-risk (minimal, safest; operator's preferred entry).** BEAR → **bear put
  spread** (covered short, max-loss = debit). RANGING → **long butterfly/condor** (net-debit, range-profiting)
  — open question whether a net-debit ranging structure clears the bar or ranging *structurally* forces rung 2.
- **Rung 2 — net-credit, defined-risk (iron condor / credit spread).** Harvests more VRP; introduces the
  correlated short-vol tail. Acceptable only with the safety probe satisfied.
- **Rung 3 — naked premium-selling (short strangle/straddle).** The **true last resort**; size only as the
  *ceiling* (what magnitude we forgo by refusing the uncapped tail). Not expected to be built.

## 6. Binding constraints (still in force while parked)

- **Hard rule 9** — v1 is single-leg net-debit long-premium; any spread support is a **grammar v2**,
  operator + Crucible-gated. **Hard rule 3** — any new sleeve clears the **same §8.7 bar**; a scope expansion
  must never be paired with a gate relaxation. **Hard rule 4** — loosening can't auto-ship.
- **Operator directives:** debit-verticals-**first**; naked selling = true last resort; **safety is
  paramount** (sizing without the tail read is not a green light); exhaust long-options first (done).

## 7. Artifacts / cross-references

| Artifact | Role |
|---|---|
| `PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` | The first resume step — **drafted, HELD, not sent.** |
| `long-options-exhaustion-assessment.md` | Why long-options is exhausted (the M1–M4 detail). |
| `regime-orthogonal-arms.md` | The full gated Path-C probe+test program + structural framing. |
| `PROMPT_CRUCIBLE_LONG_OPTIONS_EXHAUSTION.md` | ANSWERED — Crucible's confirmation. |
| `../Crucible/docs/handoffs/FORGE_long_options_exhaustion_consolidated.md` | Crucible's confirming handoff. |
| [[D152]] | Decision-log entry: exhaustion confirmed, gate satisfied. |
| [[exhaust-long-options-before-v2-spreads]], [[promotion-gate-tiers-and-constraint]], [[pipeline-vision-roadmap]] | Memory context. |

**Standing item (runs regardless of parking):** the M1/M2 long-options monitor — re-ask Crucible to re-run
the gross-vs-net + vol-target checks as the decided-CPCV population grows. It is the one thing that could
either *firm* the verdict (signal #2 above) or *reopen* long-options (off-ramp above).
