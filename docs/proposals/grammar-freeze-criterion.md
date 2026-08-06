# Grammar Freeze Criterion

> **⚠️ RE-BASED 2026-07-22 (D330) — read this box before using anything below.**
>
> Conditions (A) and (B) below, and the baseline table, are computed from Forge's
> `verdicts` ledger — which is **94% Crucible stage-one screen rows**
> (`measurement_basis = 'standard_window'`). That lane yields coverage-honest labels at
> **0.064%** and *structurally cannot* produce a component; the honest population is the
> **stage-two `fullhist_refit`** lane (80.8% honest, 5.9% of the feed). So metric B
> (2.11%) and the whole dead-mass ledger are **stage-one artifacts**, and the
> `converting` / `dead_unprotected` classification is measured on the wrong basis.
>
> **Three corrections, all landed in the joint program (`~/proj/freeze`):**
> 1. **Basis.** Grammar quality is measured on `measurement_basis = 'fullhist_refit'`,
>    never stage-one (joint charter §2, signed).
> 2. **Metric.** Component **admission is not a quality metric** — 593/593 stage-two rows
>    fail `cpcv_sharpe_p25` while 80.8% are admitted. Admission is a pool bar. The quality
>    axis is the **CPCV distribution**, and `GateResult.value` puts it within Forge's
>    reach today (100% `config_hash` join to stage-two rows, no contract change).
> 3. **Vocabulary.** `unverified` (could not evaluate) / `failed` (evaluated, failed) /
>    `honest` (evaluated, passed) — never a two-way split. Conflating the first two
>    inverted a conclusion on 2026-07-22 and set a bar ~250× too loose.
>
> **A new condition (C) is added below and is now the binding one.** Conditions A and B
> survive as *surface/throughput* conditions and must be re-derived on the stage-two
> basis before they mean anything.

**Status: SUPERSEDED IN PART — the measurable definition of "the grammar is done."**
Operator directive 2026-07-21: "optimize and maximize the grammar as much as possible … the
search_n_trials and freeze criterion (without opening Path C)." Establishes when Forge stops
bumping `grammar_version` and commits the search budget to the converting core. No code path,
grammar, or determinism touched by this document.

Relates to: [[promotion-gate-tiers-and-constraint]], [[grammar-review-expansion]],
[[exhaust-long-options-before-v2-spreads]]; hard rules #1/#4/#6/#10; §12 phases. Instrument:
`scripts/search_multiplicity_census.py` (D1). Precedent for the enumeration-policy bump class:
D098/v5 (rules text unchanged, version bump for funnel attribution).

## Why a freeze, and why now

Prior analysis (STATUS 2026-07-21; the memory ledgers) established that grammar **expansion**
cannot raise the promotion cap — that is structural (Path C, parked) — and the signal surface is
exhausted (23/72 registered indicators dark, none correctly-signed for a net-long-vol book). The
remaining lever is **convergence**: retire dead/refuted enumeration cells so the frozen grammar
is minimal and defensible, and the stream spends its budget on cells that convert.

**Honest scope (state it plainly):** the DSR hurdle is *slot-scoped*
(`search_multiplicity.slot_key` = hypothesis × dte_bucket × xsect/named), and the converting
slots carry ~0 within-slot dead mass. So pruning **cannot lower the converters' DSR hurdle** —
that hurdle is honest search breadth. Freezing buys a **minimal, auditable surface + reclaimed
throughput + a clear line under the v1 producer program**, not a promotion. Promotion stays the
structural question this document deliberately does not open.

## Baseline (census, forge.db snapshot 2026-07-21T21:24Z; 526,789 distinct configs)

| Class | Share of all-time multiplicity | Meaning |
|---|---|---|
| converting | 51.5% | produced a component/promote in the recent window |
| protected | 11.2% | matches a `farming` campaign (`mr-timer-duration`, `ve-exit-repair`) |
| already_pruned | 7.9% | emission-excluded (v31/v33/v34); recent rows are the aging tail |
| disabled_legacy | 2.9% | `regime_arbitrage` (D098) + `tail_hedge` (D066) — not enumerated |
| legacy_inactive | 12.5% | 0 recent submissions — old versions, already gone |
| **dead_unprotected** | **4.1%** | **still emitted, still ~0 conversion — the prune backlog** |
| thin | 10.0% | too few recent submissions to judge |

**Freeze metric (B), current flow:** of the last 14 days of submissions, **2.80%** land in
dead-unprotected cells. The backlog is 13 cells, dominated by the single-name (`named`) trend/MR
gated axis (deferred — see below) plus `event_momentum` `named` (same class: its productive
cross-sectional form is not generated). `relative_value` is already dormant (0 recent flow).

## Definition of "frozen"

The grammar is **frozen** when `grammar_version` stops bumping, `enumeration_inputs_hash`
stabilizes, and the search/throughput budget is committed to the converting core. Post-freeze,
new alpha work is Crucible-selection-side (assembly, gating), not Forge-generation-side. Freeze
is a **checkpoint, not a terminus** — the reopeners below are first-class.

## The two freeze conditions (both read off the census)

**(A) Coverage.** Every cell carrying material current flow is classified
`{converting | refuted-and-pruned | protected-with-an-open-read}`. No cell carries material flow
with *unmeasured* promotion potential. Operationally: the census `dead_unprotected` ledger is
empty of any cell that has not been either (i) pruned via a version bump, or (ii) explicitly
deferred with a named open decision (a Crucible relay or a farming campaign).

**(B) Multiplicity efficiency — RE-BASED 2026-07-22 (D331 item 2); the pre-re-base series is
NOT comparable.** The census now requires an **honest** component before calling a cell
`converting`, and adds an `unevaluated` class for cells with flow but zero honest
evaluations (never a prune target — a new cell is in that state by construction, and
pruning it is the v17 cold-start mistake). **Metric B moved 2.11% → 0.85% on the same
snapshot. That is a definitional change, not progress:** the drop is `unevaluated` mass
no longer being counted as dead. The operator threshold must be re-set against the new
baseline, and the 2.80% / 2.11% readings belong to the old basis. **A third number is now
visible and is arguably the more actionable one: 11.0% of all-time multiplicity sits in
cells that have never had a fair hearing.**

The dead-unprotected share of current flow (metric B) is below
an **operator-set threshold** and **stable over N census runs**.

**THE BAR IS SET (operator, 2026-07-31): metric B ≤ 1.00% of current flow, stable over 7
consecutive census runs.** Recorded series first, as the pattern requires — the 12 runs since
the D331 re-base (`metric_b_flow`, the flow metric; note the JSONL's
`dead_unprotected_share` is the *all-time* share and is a different, smaller number):

```
2.27  0.69  0.69  0.63  0.58  0.74  0.74  0.37  0.29  0.34  0.40  0.42
 ^v47 prune lands here                          ^ last 5 runs: 0.29-0.42
```

**Why 1.00% and not tighter.** The observed post-prune range is 0.29–0.74% and the last five
runs sit in 0.29–0.42%, so 1.00% clears the realised range with ~2.4× headroom over the recent
band. That headroom is deliberate and is NOT slack: a genuinely NEW cell enters the census as
`unevaluated`, and the moment it accrues its first honest evaluations without a component it
becomes `dead_unprotected` for as long as it takes to prune or defer it. A bar set at the
recent band would fire on healthy exploration — the v17 cold-start mistake wearing a different
hat. 1.00% is loose enough to tolerate one new cell being measured and tight enough that the
2.27% pre-prune state would have failed it.

**Expected post-prune value: ~0.05%.** Every remaining unit of dead-unprotected flow is one
cell (the v35 capitulation bare-drop); retiring it takes metric B to approximately zero, at
which point the bar is a regression tripwire rather than a target.

**(C) Quality ceiling — RE-SPECIFIED ON THE HONEST ARM 2026-07-31 (D339 cont.). The
stage-two version below is SUPERSEDED and must not be used to declare exhaustion.**

### Why the original (C) is void

It measured CPCV on `measurement_basis = 'fullhist_refit'` — **stage two**. It was written
2026-07-22; three days later [[D337]] and [[D338]] established that stage-two admission **is
the refit trigger**, a function of config quality, so conditioning on it is a collider that can
*sign-flip* an estimate (`rank_k=5`: +0.0776 stage two vs −0.1712 stage one — shipped in v50,
reverted in v51 the next night). (C) was never revisited after that rule landed.

It is not a theoretical worry here. Re-measured 2026-07-31 at n ≥ 300 per version, the two
bases **disagree in sign**:

| basis | median | p90 |
|---|---|---|
| stage two (`fullhist_refit`), v39 → v51 | 0.2945 → **0.4287** (+0.13) | 0.7260 → **0.8965** (+0.17) |
| stage one (all decided), v18 → v51 | 0.2877 → 0.2297 (−0.06), via a deep U | 0.7352 → 0.6964 |

The original text read "*best figures are the oldest*" off the stage-two series. That is not
what stage two says today, and stage one's endpoint decline is an artifact of comparing across
a trough (median bottoms at −0.026 in v28 and recovers to 0.2297 by v51).

**And stage one is not the fix either.** "All decided configs" is still ranker-selected — the
ranker picks what gets submitted, so its preferences are baked into the population. Neither
basis answers "what can the *grammar* produce".

### The re-specified (C)

**Basis: the D335 honest arm (`selection_mode = 'prefilter_sample'`)** — a uniform random draw
from prefilter-REJECTED configs, the only population unselected by *both* the prefilter and the
ranker. Note precisely what it is: a draw from the **rejected** pool, so it is a **lower bound**
on the grammar's surface, which is the conservative direction for an exhaustion claim.

The grammar is exhausted when **both** hold on that arm:

1. **Centre converged** — median CPCV stable as n grows. *Necessary, NOT sufficient.*
2. **Tail exhausted** — the max and the count clearing the **1.5 promotion gate** stop moving
   as n grows. **This is the binding half**, because promotion is a tail event (4 in ~428k) and
   a converged median carries no information about tail production: on stage-one cells
   spearman(cell mean, cell std) = −0.148 while spearman(cell P(≥1.0), cell std) = +0.500.

**A median-convergence argument alone can never establish exhaustion.** That was the defect in
the original criterion beyond its basis, and it is the same mean-⊥-tail lesson the two-leg
ranked lane was built on.

### Where the re-specified (C) stands — NOT MET (2026-07-31)

The recorded convergence claim was **n = 937, median 0.3521, max-ever 1.3125, 0.00% clearing
the 1.5 gate**, concluding *"a 3.1× sample changed the answer by 0.001, so more n cannot move
it — only a different GENERATION SURFACE can."* At **n = 7,484**, an 8× sample:

| reading | recorded (n=937) | now (n=7,484) |
|---|---|---|
| max CPCV | 1.3125 | **1.6629** |
| configs clearing 1.5 | **0** | **2** |
| pooled median | 0.3521 | 0.1990 *(basis unreconciled — see below)* |

Both clearers are real, cross-sectional, non-degenerate, with healthy trade counts:

```
d004043d  v49  reject     cpcv 1.6326  227 trades  trend/swing_long  sma_slope x rv_rank
36c8aab4  v51  component  cpcv 1.6629  425 trades  MR/swing_mid      rsi x market_rv x ivol
```

**⇒ The centre converged; the TAIL did not.** The claim "only a different generation surface
can move it" is falsified for the tail: the *same* surface produced a 1.6629 component once the
sample was large enough to reach it. **(C) is NOT satisfied and the grammar is not exhausted on
the reading that matters.**

**Honest caveat:** the pooled honest-arm median (0.1990) does not reconcile with the recorded
0.3521, and the original script is not available to diagnose the difference. Neither figure is
treated as authoritative here. The gate-clearer counts are directly checkable and are what this
section rests on.

**Second-order finding, tracked separately:** `36c8aab4b0f6a360` reached CPCV 1.6629 **as a
component** after our own prefilter rejected it. A prefilter false-negative at the top of the
distribution is a different problem from grammar exhaustion and does not belong in this
criterion, but it should not be lost.

### ⚠️ CORRECTION 2026-08-02 — the "2 clearers" above is a BASIS ERROR, and (C) is measured on a statistic that cannot resolve

Two independent defects in the reading immediately above. Both were found by re-running it at
a grown sample; neither changes the *criterion*, both change what it currently says.

**(1) One of the two clearers was pooled across the basis boundary this document forbids.**
`36c8aab4b0f6a360` carries two verdict rows:

```
measurement_basis   decision    cpcv
fullhist_refit      component   1.6629   <- the number quoted above (STAGE TWO)
standard_window     reject      1.1703   <- its actual STAGE-ONE reading
```

The 1.6629 is its **stage-two refit** value. On the stage-one honest arm — the declared basis
of (C) — that config reads **1.1703 and does not clear 1.5**. This is the D337/D338 error the
section's own basis paragraph warns against, committed inside the measurement meant to enforce
it. **The corrected stage-one honest-arm count is 1, not 2** (only `d004043d`, 1.6326), and it
was 1 at the time of writing too.

**(2) The corrected series cannot discriminate, and D341 already proved it.** Re-read at
n = 11,932 (a 1.6× larger sample than the 7,484 above):

| reading | at n=7,484 | at n=11,932 |
|---|--:|--:|
| stage-one honest-arm configs clearing 1.5 | **1** (corrected) | **1** |
| max CPCV | 1.6326 | 1.6326 |
| clearing 1.25 | — | 4 (0.034%) |
| clearing 1.0 | — | 51 (0.427%) |
| median / p90 / p99 | — | 0.1428 / 0.5944 / 0.9104 |

A count that goes 1 → 1 while n grows 1.6× is equally consistent with "the tail is exhausted"
and "the tail produces at a constant 0.008% rate". It has essentially no power — and **[[D341]],
dated the same day as this section, measured exactly that**: detecting a doubling of
P(cpcv ≥ 1.5) needs ~183 days per arm, which is why the A/B was specified on p90 instead.
**(C) is therefore specified on the one statistic the programme had already shown cannot be a
decision metric.**

**⇒ Neither "the tail did not converge" (the reading above) nor "the tail is exhausted" is
supported.** (C) is *unevaluable as specified*, not unmet — a different claim, and the honest
one. Reading a stall off a count of 1 is the same error we corrected Crucible on 2026-08-02
(three zero-counts at a per-name expectation below 1).

**What would make (C) decidable:** re-specify the tail half onto a bar with observable event
counts on this arm — P(cpcv ≥ 1.0) carries 51 events at 0.427%, and p90 (0.5944) moves on a
~3-day horizon per D341 — then set the exhaustion bar there. Operator-gated: it changes what
the freeze programme turns on. Instrument: `scripts/threshold_resolution_value.py` shares the
basis discipline; the counts above are reproducible from any `forge.db` snapshot.

### ⚠️ THE p90 SPEC BELOW IS SUPERSEDED — prereg `90caf0cd877f` resolved `insufficient`, never read; see the corrected spec at the end of this section (prereg `f507e5da0677`)

### (C) TAIL HALF, RE-SPECIFIED 2026-08-02 (operator: "move forward with that") — prereg `90caf0cd877f` (SUPERSEDED)

**The repair is narrow: keep the corrected basis, restore the ORIGINAL statistic.** The
original (C) already used **p90** and was voided for its *basis*, not its statistic; the
re-specification correctly moved the basis to the stage-one honest arm but also swapped p90
for the 1.5-gate count, and nothing in D337/D338 required that second change. It is what made
(C) undecidable.

**Specification.** p90 of `cpcv_sharpe_p25`, honest arm (`selection_mode='prefilter_sample'`),
stage one only, over **consecutive non-overlapping windows of n = 1,200** in submission order.

**The bar is measured, not assumed** (`scripts/freeze_tail_reading.py`). Window-to-window
variance decomposes as `sd² = a²/n + b²`:

| window n | k windows | mean p90 | sd | 2sd |
|--:|--:|--:|--:|--:|
| 400 | 29 | 0.5946 | 0.0376 | 0.0752 |
| 800 | 14 | 0.5921 | 0.0324 | 0.0648 |
| 1,200 | 9 | 0.5875 | 0.0253 | 0.0506 |

⇒ sampling **a = 0.681** (shrinks as 1/√n) and **irreducible drift b = 0.0159** (does not).
**A p90 move counts only if it exceeds 2b = 0.0319.**

**This is the enabling finding.** Crucible's "version-over-version deltas below ~0.15–0.20 are
beyond resolution at ANY n" is about a different quantity; on *this* statistic the floor is
**0.016**, an order of magnitude smaller. p90 is a usable decision metric here — which is
exactly what the 1.5-count is not.

**Reading rule.** The tail is EXHAUSTED when `best(p90) over the trailing K windows` does not
exceed `best(p90) over the preceding K windows` by more than **0.0319**. NOT-exhausted on any
excess above it. K = 6, fixed in advance; a single read, no peeking-to-threshold.

**Current reading — flat, and this is the first EVALUABLE reading of the tail half:**
9 consecutive windows spanning v49 → v54 read
`0.574 0.532 0.613 0.580 0.616 0.600 0.587 0.612 0.572`; newest vs best-prior **−0.0437**,
inside the floor. Six grammar versions produced no attributable p90 movement.

**Three caveats, on the record before anyone reads exhaustion into that:**
1. **10 days is short** for a claim about a grammar's ceiling, and the windows span a period
   with no deliberate expansion — mostly prunes. Absence of movement from prunes is weak
   evidence about what expansion could do.
2. **The honest-arm RATE changed** at the v54 deploy (`FORGE_PREFILTER_SAMPLE_N` 150 → 40, so
   ~1,851/day → ~718/day). The draw is still uniform over prefilter rejects, so the
   *distribution* should be unchanged and only the clock slows — but a distributional shift
   here would masquerade as a tail reading, and the first post-v54 windows should be checked
   against the pre-v54 ones before they are pooled.
3. **A flat p90 is necessary, not sufficient.** It is the ceiling of the *sampled* surface; a
   grammar change that opens genuinely new structure would show up first as new cells, not as
   a p90 move within existing ones. Condition (A) still carries that half.

### (C) TAIL HALF — CORRECTED SPEC, 2026-08-02, prereg `f507e5da0677` (THIS IS THE LIVE ONE)

A four-agent review found **two defects in the spec above, before it was ever read.** Both are
fixed here; `90caf0cd877f` is resolved `insufficient` (a specification defect, not an
unfavourable result — its clock had not elapsed, so no peeking is involved).

**Defect 1 — the bar was contaminated by COMPOSITION.** The pooled statistic confounds quality
with mix. Measured: `swing_long`'s share of the honest arm moved **48.4% → 61.9%** across the
ten windows, while its pooled p90 (**0.6447**) sits **0.149** above `swing_mid`'s (**0.4955**).
Mix shift alone therefore moves pooled p90 by **~0.020 — 63% of the registered 0.0319 bar** —
with no quality change at all. The traced cause is *our own* chain-inception filter
([[D351]]/[[D352]]) adding and removing swing_long-only names at the window-9 boundary. And the
old `b = 0.0159` was **fit on that drifting series**, so part of what was called irreducible
noise was composition: the bar was wrong in both directions simultaneously.

**Fix: post-stratification.** Each observation is weighted `p_c / q_c` — `p_c` the cell's share
of the full reference sample, `q_c` its share of the window — so every window is read as if it
carried the reference mix. Cells are `(hypothesis, dte_bucket)`, the granularity D341 measured
as **signal** (z=+2.02) rather than noise (per-cell z=+0.29).

**Defect 2 — the statistic was not the best available.** The **tail-conditional mean of the top
decile** (mean of everything at/above the window's own weighted p90) uses the whole tail instead
of one order statistic.

| series | mean | sd@1200 | b | b_upper | **bar 2·b_up** |
|---|--:|--:|--:|--:|--:|
| p90 raw (pooled) | 0.5903 | 0.0255 | 0.0199 | 0.0211 | 0.0422 |
| p90 standardised | 0.5939 | 0.0171 | 0.0085 | 0.0123 | 0.0245 |
| TCM raw (pooled) | 0.7360 | 0.0187 | 0.0151 | 0.0208 | 0.0416 |
| **TCM standardised** | **0.7371** | **0.0147** | **0.0019** | 0.0121 | **0.0242** |

`p95`/`p99` were rejected **on evidence**: their small apparent floors are artifacts of thin
tail density (the sampling term inflates 0.64 → 1.05 as per-window tail observations fall to
~60 and ~12), and p90 is the only quantile where *both* variance components resolve. Median and
mean were rejected for drift floors of **43%** and **52% of their own level**.

**The bar is deliberately conservative.** `sd² = a²/n + b²` is fitted by OLS across five widths
(300/400/600/800/1200), and the bar is **2·b_upper = 0.0242**, from a leave-one-width-out upper
bound — *not* 2·b_point (0.004). An earlier two-width fit returned `b = 0.0000` exactly, which
is not "no drift" but "cannot resolve drift" wearing a decisive-looking number. Direction
justifies the choice: **too small a bar delays a freeze; too large a bar freezes a grammar that
is still improving. Only the first is recoverable.**

**Current reading:** `0.7206 0.7241 0.7448 0.7417 0.7512 0.7548 0.7209 0.7453 0.7141 0.7535`;
newest vs best-prior **−0.0013**, inside the floor. Coverage 1.000/window, max weight 2.18.

**Companions — reported, never the trigger.** (a) `P(cpcv ≥ 1.0)` per window (3 3 5 5 6 7 4 8 5
5): TCM sits at rank ~120-from-top while promotion-grade events sit at rank ~0.4–5, so **a
top-1%-only lift is arithmetically invisible to the trigger** — a case that falls between (A),
which covers only *new* cells, and (C). (b) `P(cpcv|submitted)`: trend **73.1%**, MR 68.3%,
`volatility_event` **20.6%**, driven by Crucible's per-bucket min-trade floors (100/60/30). A
shift here changes the measured population with zero grammar action, and Crucible has a known
live trigger (the `ref_trailing_return` writer gap) that would do exactly that.

**Two corrections to claims made in the superseded spec:** "six grammar versions produced no
attributable movement" is really **v51+v52 (>80% of the arm) flat plus four underpowered
slivers**; and **the honest arm does not exist before v49** (the D335 campaign began
2026-07-23), so **v43 and v47 — this programme's two headline prunes — cannot be validated on
this basis at all.**

**Still open, and NOT settled by any of this:** whether a *quality* statistic is the right
target. Crucible measured `IC(cpcv, corr_to_book) = +0.547` — better components are more
redundant — and located the binding constraint at assembly, not supply. A rising TCM could mean
Forge is efficiently producing exactly the redundancy they asked us to reduce. Every
Forge-native redundancy proxy tried has failed (threshold geometry R²=0.0018; the most- and
least-orthogonal promoted legs share a label), so that leg must come from a relay. **(C) as
specified is a supply-ceiling condition and should not be read as a promotion-likelihood one.**

Instrument: `scripts/freeze_tail_reading.py` (standardised + raw, both statistics, companions).

### (C) LEG 2 — THE REDUNDANCY LEG, 2026-08-02, prereg `13e4d2cece3f`

The "still open" paragraph above is now closed, and **not by a relay**. It was scoped as
relay-dependent on the assumption that only Crucible could see corr-to-book. Wrong: their
`corr_to_book_*.json` already publishes **116,329 per-run rows keyed by `config_hash`**, and our
honest arm joins to it. We asked them to build a periodic export before checking whether the
data was already on disk; it was, and we told them to stand down.

**Statistic:** composition-standardised **TCM-corr** — the post-stratification-weighted mean
`|corr to book|` among configs at/above the window's own weighted p90 of `cpcv_sharpe_p25`.
Deliberately the *same* population, window, threshold and weights as leg 1, because the question
is not "is our average config redundant" but **"is the supply that would actually be USED
becoming redundant."** Crucible's entanglement finding reproduces here: top-decile `|corr|`
**0.3837** against **0.3171** for the rest. **RISING IS WORSE**, so the comparison reference is
the prior **maximum**. Bar `max(2·b_up, 2·sd) = 0.0173`; the fallback is load-bearing, not
decorative, because the a/b split degenerates for this statistic (sd shrinks almost exactly
1/√n, leaving `2·b_up = 0.0034` against a series whose own spread is 0.0087 — a bar three times
tighter than the noise is not conservatism, it is a leg that always fails).

**Crucible's two conditions are binding:** it is a *supply* statistic and must never become a
generation target ("report it, do not tune against it"), and it is cohort-scoped — honoured by
the same `(hypothesis, dte_bucket)` post-stratification as leg 1, since a pooled read would
reintroduce the very composition drift that contaminated leg 1's original bar.

#### The reference book is pinned to `frozen_b36f49a4` and does NOT track the designation

Recorded because it is the leg's most reversible-looking decision and the one most likely to be
"helpfully" changed later. `frozen_b36f49a4` is the minted series of the **second promotion**
(2026-07-20) — the book the operator **retired on 2026-08-01** in favour of `f52a05c8968bdc7a`
(QuantIQ D306: the old champion was infeasible at 11.48% NAV drawdown against an 8% ceiling).
The flip therefore landed **before** this leg's prereg cut (2026-08-02T17:26Z), so the entire
registered series was already read against one fixed reference and **nothing needs re-basing**.

It stays pinned, on Crucible's recommendation and our own measurement. On the 2,497 configs
carrying correlations to both books:

| | value | note |
|---|--:|---|
| per-config agreement, pearson | **+0.9582** | the choice costs ~no ordering power |
| per-config agreement, spearman | **+0.9531** | |
| leg-2 level vs `frozen_b36f49a4` | **0.4228** | the registered reference |
| leg-2 level vs `f52a05c8968bdc7a` | **0.3770** | the designated book |
| **level gap** | **−0.0458** | **2.6× the leg's own 0.0173 bar** |

The two books rank our configs almost identically but sit at materially different **levels**. So
a silent switch would have printed a large unearned **improvement** — biasing the freeze toward
being declared MET on a reference change rather than a supply change. **That is the
unrecoverable direction.** A coverage-chosen yardstick that chased the designation would also
inherit a re-base on every future flip, and there will be more. If coverage on the designated
book ever overtakes (it is climbing: 2,497 and rising against 13,480), re-point **at a boundary
with the series split**, never mid-window.

**The yardstick is self-checking, not promise-checked.** Crucible undertook to flag changes to
`corr_to_book`'s window or `min_overlap` before shipping them. A promise depends on someone
remembering, and this week produced a defect of exactly that shape on each side. So the
instrument fingerprints the reference book's identity fields (`spec_note`, `window`, `n_days`,
`weights`, `traded_unit`, `minted_at`), pins the hash (`ae47a4749c9d`, stable across every
export on disk), and **refuses to run leg 2 on any mismatch** — same principle as the existing
50%-join refusal. A re-mint can move the level either way, so an unnoticed one could manufacture
a false PASS.

**The registered read must not set its own bar.** Left alone the instrument re-fits `a`/`b` on
every run — *including the windows under judgement* — so the threshold moves with the data it
judges. That is peeking wearing a formula: leg 2's bar read 0.0173 at registration and 0.0210
one window later, purely from refitting. `--leg1-bar` / `--leg2-bar` pass the registered values
and label the output `REGISTERED`; without them the run is labelled **EXPLORATORY — NOT the
registered read**. Resolve against the prereg's literal baseline (0.4411), not the recomputed
one: post-stratification re-weights past windows as the sample grows, moving them ~0.0002 (1.2%
of the bar).

**Reading rule (fixed in advance):** a single read once **6 new n=1200 windows** accrue after the
cut, best-of-new-6 against the prior max. **The freeze decision requires BOTH legs** and is taken
at the *later* of the two reads. Backdating leg 2's cut to align with leg 1's would mean
registering a prediction against data already seen.

**Current status — EXPLORATORY, not the read:** leg 1 **−0.0174** vs 0.0183; leg 2 **−0.0420**
vs 0.0173. Both inside their floors, neither is a freeze decision, and **both legs remain
arithmetically blind to a top-1%-only lift** by the same rank argument as above.

---

**SUPERSEDED — the original stage-two (C), retained for the record:**
The grammar is exhausted when, on `measurement_basis = 'fullhist_refit'` at n ≥ 300 per
version: (1) admitted **median** CPCV shows no improvement over N trailing versions,
**and** (2) **p90** CPCV does not move — the ceiling, not the centre, since the centre
drifts on cell mix alone — **and** (3) no newly-added component clears a pre-set
within-cell lift bar on *both* admission and CPCV.

**Where the SUPERSEDED (C) stood, measured (2026-07-22):**

| reading | value | source |
|---|---|---|
| admitted median CPCV, v18 → v42 | 0.5881 → **0.4340** (declined; best figures are the oldest) | `freeze/analysis/forge_convergence_read_2026-07-22.txt` |
| admitted p90 across 20 versions | **0.6695–0.8646, no trend** | same |
| stage-two rows ever clearing CPCV 1.5 | **8 of 16,873** (0.047%) | `freeze/data/crucible/stage2_quality_by_version_2026-07-22.json` |
| best / worst measurable cell (medCPCV) | `bb_pct` 0.5619 / `residual_momentum` 0.2406 | `freeze/data/forge/forge_cell_cpcv_scorecard_2026-07-22.json` |
| stage-two coverage of v43–v48 | **zero** | Crucible per-version artifact |

Read strictly, **(C)(1) and (C)(2) are already satisfied on the historical series** — the
ceiling has not moved in 20 grammar versions and ~481k stage-one runs, and the entire
cell range sits below *half* the promotion gate. Forge deliberately does **not** claim
this, because the five versions carrying our largest structural changes (v43–v48) have
zero stage-two rows. Declaring exhaustion on a series ending at v42 is the basis trap.

> **2026-07-31 postscript on the block above.** Refusing to claim exhaustion off that series
> turned out to be right for a *second*, larger reason than the one given: the series is not
> merely truncated at v42, it is measured on the collider basis, and its central claim
> ("best figures are the oldest") reverses on today's stage-two data. The instinct to
> withhold the claim on coverage grounds happened to protect us from a basis error nobody
> had identified yet. Withholding a conclusion you cannot fully justify is worth more than
> the specific reason you withhold it.

**The blocking constraint is the stage-two FEED, not throughput and not optimization.**
(Corrected 2026-07-22 — an earlier version of this paragraph proposed a stage-one intake
cut on a "divergence, not a backlog" argument. That was **wrong**: Crucible's scanner is
`ORDER BY pd.decided_at DESC`, re-derived every pass, so new work never queues behind old
work and cutting intake would not have improved v47/v48 coverage. Operator refused it on
exactly that ground.)

The real mechanism: `_triggers_rederive` admits a stage-one row into stage two via
`reject → coverage_blocked_component` or `component → not-honest-coverage`. **The reject
path has contributed ZERO all along** — `deflated_sharpe` fails ~100% of forge rows and is
absent from `_COMPONENT_ELIGIBLE_GATE_FAILURES`, failing the subset test. So *every*
version's stage-two feed came from the component path: the `rank_k=20` unverified bypass.
**v48 closed that bypass, so v48 feeds ZERO rows into stage two** (v46 508, v47 509,
**v48 0**). Crucible's DESIGN.md §20 `dsr-record-not-binding-forge-minimal` already ruled
DSR must not bind here; the exemption landed in `_verdict_from_gates` but never reached
`fullhist_refit.coverage_blocked_component`. Honoring it (source-scoped, `wf>0`/`cpcv>0`
untouched, so **not** a gate relaxation) would take v48 from 0 to 368 eligible rows in our
window sample. **Until that lands, condition (C) cannot be evaluated on v48 at any n.**

Freeze is declared when **(A), (B) and (C) hold**, A and B re-derived on the stage-two
basis, and (C) evaluated on a set that includes **v47 and v48**.

## The freeze ledger (how progress is tracked)

Two standing records, both already in the tree:
- **The refutation registry** — `enumeration/refutations.py` consumer + Crucible's
  `refutations.yaml` (D313/D320): what has been ruled dead and is being routed off.
- **The census JSONL** — `scripts/search_multiplicity_census.py`, productionized into the daily
  timer (`search_multiplicity_census.jsonl`) + a `forge healthcheck` reader (D1 Step 1b): the
  running metric-B series and the live dead-mass ledger.

## Reopeners (freeze is reversible)

Any of these reopens a `grammar_version` bump after a freeze, each operator-gated:
1. **A Crucible refutation retraction** — a cell ruled dead is re-validated (the ghost-era class).
2. **A new registry family with a net-long-vega mechanism argument** — a genuinely orthogonal,
   correctly-signed signal (not the currently-dark seller-side surface set).
3. **A Path-C structural decision** — the operator un-parks defined-risk structure. This raises
   the cap and necessarily reopens the grammar (`exhaust-long-options-before-v2-spreads`).

## Governance (every prune, before and after freeze)

Each retirement is its own operator-gated increment:
- **Class:** enumeration-policy bump (rules text unchanged — D098/v5), or an emission-exclusion
  edit in `search_space.py` (the `_DIRECTIONAL_POOL_EXCLUDED_IDS` / `DISABLED_HYPOTHESES` /
  `_REGIME_GATE_GLOBALLY_EXCLUDED_IDS` pattern). Auto-*tightening* needs no approval (hard rule
  #4); the deploy/restart is operator-gated (CLAUDE.md).
- **Version + archive + Decision Log** (hard rule #10), goldens re-pinned (removing draws shifts
  the sequence — v43 precedent), emission proof (0 draws of the retired cell).
- **Prereg first** (D207): register the predicted post-cut conversion ≈ 0 on the pruned cells with
  a cohort cut *before* the edit (mirror the v43 rider prereg `44a4e08aef4f`); resolve on post-cut
  evidence via `forge prereg resolve`.
- **Funnel attribution** (`funnel --compare vN vN+1`), STATUS block + D-entry.

## Backlog (census-derived, 2026-07-21)

| Item | Flow share | Disposition |
|---|---|---|
| `relative_value` (dormant) | ~0% (surface only) | **Clean prune** — refuted (D215/D276), retire to shrink the surface + prove the machinery (v47, `_archive/PROPOSAL_v47-dead-hypothesis-retirement.md`). |
| Single-name (`named`) trend/MR gated axis | bulk of the 2.8% | **Deferred** — single-name components are Crucible's assembly-diversity source (~15.9% of the honest pool, D215/D186); needs a Crucible "do books consume these?" read before retiring. Draft the relay. |
| `event_momentum` `named` | ~0.4% | **Deferred** — dead in its `named` form, productive cross-sectional form not generated; joins the single-name-axis read (not a standalone clean prune). |
| Single-name `volatility_event` | (protected today) | **On probation** — `ve-exit-repair` farming campaign; re-anchors on the v38-vs-v39 ve funnel, not a prune target until then. |
