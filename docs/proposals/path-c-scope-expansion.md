# Path C — defined-risk scope expansion (grammar v2): PARKED resume dossier

Status: **PARKED 2026-06-15 (operator) — explore later "when the time arises."** This is the single
entry point for resuming the Path-C question. It consolidates the decision, the resume signals, and the
first step; it does **not** re-derive the analysis — the detail lives in the docs cross-referenced below.

> **One-line state:** long-options is Crucible-confirmed exhausted for promotion-grade adverse-regime
> magnitude (D152); the operator's Path-C provability gate is **satisfied**; the operator chose to **hold**
> the scope-expansion exploration rather than open it now. Nothing is sent, nothing is built.

> **⚠ UPDATE 2026-06-15 ([[D153]]) — the exhaustion precondition is REOPENED; Path-C resume pushed out.** The
> operator reopened long-options on conditioning-completeness grounds: the D152 verdict was measured over a
> population that never conditioned on the vega/IV-cost axis (`iv_rank` is a NaN stub → §3.5 R1 unsatisfiable),
> never computed theta/vega, and conditioned marginally. The in-scope **Path-A rich-conditioning sweep** is
> now ACTIVE (`path-a-rich-conditioning.md` — light up `iv_rank`, joint-gate the entry, learn the conditioner).
> Path-C's "provability gate SATISFIED" is now **"satisfied *pending* that sweep."** Resume only after Path-A
> returns negative (off-ramp §3: "no in-scope lever clears" now requires the *rich* sweep, not just the crude
> one). The structural verdict (long premium net-negative at source; the big arm is sell-side) is unchanged —
> so Path C remains the *likely* eventual unlock; it is just deferred behind the cheap in-scope sweep.

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
