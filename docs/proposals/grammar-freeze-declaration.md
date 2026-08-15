# Grammar freeze — DECLARATION (**SIGNED 2026-08-14**)

**Status: ✅ SIGNED — operator, 2026-08-14, on the re-founded evidence below.** The grammar is
frozen at **v55**. `grammar_version` stops bumping, `enumeration_inputs_hash` stabilizes, and the
search/throughput budget is committed to the converting core. New alpha work is Crucible-side
(assembly, gating), not Forge-side generation. **§6 governance is in force from this date**, and the
§5 reopeners are live and operator-gated.

**WHAT THE SIGNATURE ASSERTS — and it is the narrower of the two available claims.** That the
**bulk of the supply distribution has stopped improving** and the budget is better spent on the
converting core. It does **NOT** assert that no better strategy exists, that the grammar cannot be
improved, or that a ceiling has been proven. Two measurements point the other way and were read
before signing (§4, §8): the ranked lane is still setting running-maximum records at exactly the
unbounded-search rate, and the joint frontier is still advancing (z=+3.60, p=0.003).

**THE STRONGEST OBJECTION, ON THE RECORD AT SIGNATURE.** §4: *"the window spans mostly prunes, not
expansion — absence of movement is weak evidence about what expansion could do."* That objection is
**not answered by this evidence and is not claimed to be.** It is the reason §5's reopeners are
first-class rather than adversarial: reopener (2) (a new registry family with a net-long-vega
mechanism argument) and reopener (3) (a Path-C structural decision) are precisely the untested
expansion cases, and either reopens a version bump on the operator's signature alone.

**WHY SIGN NOW RATHER THAN MEASURE MORE.** §8 Step 1: **14 of 23 configs clearing both binding gates
were never refit**, with a stage-one profile identical to the 9 that were, and refit latency p99=2h
proving they were passed over rather than queued. The binding constraint on component production is
**refit triage on Crucible's side, not generation on ours.** No amount of additional grammar search
addresses that, which is what makes committing the budget the correct move on measured grounds
rather than on exhaustion.

**Prior status, retained for the record:** ⚠️ NOT SIGNED — ready for signature for the first time;
the re-baselining this document demanded of itself has been done and read. The 08-06 blocker was that (C) certified flatness at a
~0.75 plateau the stream had since left by +0.1532. This draft's own remedy was "a fresh (C)
registered against the post-break level, with its drift floor refit on post-break windows only."
That is **`3b0cbca7ae17`**, registered 2026-08-10 (D388) and read once 2026-08-14 (D389):

```
LEG 1  quality      best-of-new 0.8971  vs baseline 0.9193  =  -0.0222   bar 0.0536   CONFIRMED
LEG 2  redundancy   best-of-new 0.4392  vs baseline 0.4484  =  -0.0092   bar 0.0135   CONFIRMED
```

**Both legs came in BELOW baseline, so neither confirmation leans on its bar** — and leg 1's
−0.0222 would also have cleared the *original* (C)'s narrower 0.0242 bar, which is what makes the
wider-bar caveat (§2C) survivable rather than fatal.

**What changed in the interim, and it strengthens the claim rather than patching it.** The 08-03
break was not a grammar effect at all: it was Crucible's monthly tier-3 universe re-rank arriving
through our own 4h15m cache lag — a **generation-basis** change (D385→D387, our competing
ranking-time explanation refuted on our own data and withdrawn). So the re-baselining became a
**replication inside a single fixed basis** (`e1adced727678c8f`), which is stronger evidence than
the original: the generator now draws from a *different universe* and (C) still holds. The original
(C) legs were themselves basis-clean — windows 1–18 are all `877b1eddde9864eb` — and **they stand.**

**⚠️ READ §4 AND §8 BEFORE SIGNING. THEY ARE NOT HEDGES AND THEY ARE NOT SETTLED BY D389.**
(C) tests the **bulk tail** and says so itself. Two measurements point the other way and are
recorded here rather than in a footnote: the **ranked lane is still setting running-maximum records
at exactly the unbounded-search rate** (z=+0.13, trail climbing to +1.7397 on 08-03), and the
**joint frontier is still advancing** (z=+3.60, p=0.003). Signing asserts "the bulk of the supply
distribution has stopped improving and the search budget is better spent on the converting core" —
it does **not** assert "no better strategy exists," and §8 Step 1 found the binding constraint on
component production is **Crucible-side refit triage, not Forge generation.** That finding is the
strongest practical argument *for* freezing, and it is not an argument that the ceiling is absolute.

**Programme:** D328 → D389. **Grammar at declaration:** v55. **Preregistration registry: 31
registered, 31 resolved, none open.**
**Relates to:** `docs/proposals/grammar-freeze-criterion.md` (the criterion this reads against),
`IMPLEMENTATION_DECISIONS.md` D328–D389, `INDEX_forge_answered.md` (Crucible-side agreements).

Everything below stands as the record, with §2C re-founded and §7 refreshed.

---

## 1. What is being declared

Per the registered definition: the grammar is **frozen** when `grammar_version` stops bumping,
`enumeration_inputs_hash` stabilizes, and the search/throughput budget is committed to the
converting core. Post-freeze, new alpha work is **Crucible-selection-side** (assembly, gating),
not Forge-generation-side.

**Freeze is a checkpoint, not a terminus.** The reopeners in §5 are first-class and each is
operator-gated, not adversarial.

## 2. The three conditions, with evidence

### (A) Coverage — MET 2026-08-06

Every cell carrying material current flow is classified `{converting | refuted-and-pruned |
protected-with-an-open-read}`. Operationally: the census `dead_unprotected` ledger is **empty**.

```
census 2026-08-06T12:08:45   dead cells: 0   dead flow: 0 / 148,322
```

The last cell standing was `mean_reversion / swing_mid / named / momentum / (nogate)` — the
capitulation cell, retired at v52 (D340). It left the ledger by its 14-day flow ageing below the
`_MIN_SUBMITTED_FOR_DEAD = 200` threshold, on the date predicted (D363). **No action was taken to
clear (A); it cleared arithmetically**, which is the correct outcome — the cell was already
pruned and the ledger was showing residue, not a live decision.

### (B) Multiplicity efficiency — MET

Dead-unprotected share of current live flow, against the operator bar of **≤1.00%, stable over 7
consecutive census runs** (set 2026-07-31, before the readings that would satisfy it):

```
metric B: 0.00%          consecutive runs ≤1.00%: 18   (bar: 7)
```

Basis note: metric B was **re-based** at D331 and the pre-re-base series (2.80% / 2.11%) is not
comparable — the census now requires an *honest* component before calling a cell converting, and
adds an `unevaluated` class that is never a prune target.

### (C) Supply ceiling — MET, and RE-FOUNDED within a single generation basis 2026-08-14

**The reading that carries the condition (D389, prereg `3b0cbca7ae17`).** Basis-scoped to
`e1adced727678c8f` — the universe basis created when our `_load_universe_tiers_cached` picked up
Crucible's 2026-08-03T13:00:07Z tier-3 re-rank 4h15m late, at 17:15:54Z. Rows filtered to the basis
**first** and gridded **second**, so no window straddles the seam (18 basis-local windows, zero
straddles, coverage 0.996–1.000, corr join 84.2%, reference fingerprint `ae47a4749c9d` verified).

| leg | windows | best-of-new | baseline | delta | bar | falsify above | verdict |
|---|---|--:|--:|--:|--:|--:|---|
| 1 — quality (standardised TCM) | 12–17 | 0.8971 | 0.9193 | **−0.0222** | 0.0536 | 0.9729 | **CONFIRMED** |
| 2 — redundancy (standardised TCM-corr) | 12–17 | 0.4392 | 0.4484 | **−0.0092** | 0.0135 | 0.4619 | **CONFIRMED** |

Both falsifiers were one-sided **upward**, for opposite reasons: rising quality would mean the
ceiling is still moving, rising correlation would mean the good supply has become more redundant.
Both came in **below** baseline.

**⚠️ THE ONE WAY THIS READ IS WEAKER THAN THE ORIGINAL, stated at registration rather than found
later.** Leg 1's bar is 0.0536 — **2.2× the original's 0.0242** — because the drift fit finally
*resolved* (`b=0.0235`, `b_up=0.0268`) instead of degenerating to `b=0.0000` as it had three times
before, which forced a `2·sd` fallback. A wider bar makes "flat" easier to confirm, so this
confirmation is **weaker per-unit** than the original's. The rule was held fixed rather than the
number, which is the only defensible choice. **Mitigation, measured:** the observed −0.0222 clears
the original's narrower bar too, so the verdict does not depend on the extra room.

**Second self-check recorded.** The recomputed prior maxima had drifted to 0.9204 / 0.4485 against
the registered literals 0.9193 / 0.4484 as post-stratification re-weighted history with the growing
sample. The read used the **literals**, as the prereg required — marginally *harder*, not easier.

**The original (C) STANDS as history, not as the live basis.** Read 2026-08-03 on preregs
`f507e5da0677` (leg 1, windows 11–16, +0.0041 vs 0.0242) and `13e4d2cece3f` (leg 2, windows 12–17,
−0.0033 vs 0.0173), both also clearing a 3.3×-tighter post-ramp re-derived bar (0.0074 / 0.0130,
D358). **Both were basis-clean** — global windows 1–18 are all `877b1eddde9864eb`, so neither
crossed the 08-03 boundary (D387/D388). What the break invalidated was the *level* they certified,
not the reads themselves. This is why D389 is a **replication**, not a repair.

**Not carried forward:** leg A of `74dbbaee89c7` (+0.0798 "durable level shift") is **discounted** —
its 0.7877 threshold was old-basis while its windows were new-basis, so it measured the universe
change, not persistence. Leg B (rise REFUTED, −0.0438) was basis-clean and stands; it is the result
that keeps a freeze coherent, since the grammar is not on a rising trajectory.

**§4 qualifies what (C) means. It should not be read without it.**

## 3. What the programme actually did

| | |
|---|---|
| grammar versions | v42 → **v55** (14 bumps) |
| submissions all-time | 692,631 |
| honest arm (D335, unselected by prefilter *and* ranker) | 28,126 with a cpcv |
| retirements | `relative_value`, `event_momentum`, single-name trend/MR (v47); capitulation (v52); Q46 vix conditioner (v55); 30 dead names (v43); D216 ve floor (D367) |
| prereg registry at declaration | 17 confirmed · 6 refuted · 5 insufficient · 1 open |

**Metric B fell 2.80% → 0.00%.** That is the programme's headline number and it is a *supply
hygiene* result: the enumerable surface no longer carries material flow into cells with no
measured promotion potential.

## 4. WHAT THIS DOES NOT CLAIM

This section is load-bearing. Every item is a measured limit, not a hedge.

**~~(C) was read during a capacity squeeze~~ — THIS CAVEAT WAS WRONG AND IS WITHDRAWN (2026-08-06).**
We wrote, and Crucible endorsed, that (C) was read at 25% eligible stage-two coverage and that
*"the grammar stopped improving"* versus *"we could not measure a grammar improvement"* were
entangled. **Neither side checked whether (C)'s basis touches stage two. It does not.** Both legs
read **stage-one** cpcv distributions on the honest arm; the capacity raise, the two-lane refit
split and the promote-stamp validator are all **stage two**. Measured: `P(cpcv|submitted)` on the
honest arm runs 63.7 / 62.9 / 65.2 / 65.5 / 64.1 / **72.6 / 73.0 / 71.5** across 07-30→08-06 — the
one step is at **08-04, our own ve-floor retirement**, not at 08-06 where their fixes landed. A
caveat agreed in writing by both sides, unchecked by both, and withdrawn here rather than left
standing.

**Both (C) legs are arithmetically blind to a top-1%-only lift.** They sit at rank ~120-from-top
in a 1,200-row window; promotion-grade events sit at rank ~0.4–5. `P(cpcv ≥ 1.0)` is carried as a
companion for exactly this blind spot and never triggers the decision.

**The honest arm does not exist before v49.** The D335 campaign began 2026-07-23, so **v43 and
v47 — this programme's two headline prunes — cannot be validated on that basis at all.**

**The window spans mostly prunes, not expansion.** Absence of movement is weak evidence about
what expansion could do.

**Supply composition is not currently an actionable lever on the promotion axis (D361).** Neither
Forge nor Crucible holds a statistic that ranks buckets or families on that axis. This was learned
expensively: `swing_long` is bad on every solo metric and sits in **7 of 7 promoted books** as the
exclusive trend carrier.

**THE EXTREME TAIL IS STILL SETTING RECORDS — (C) measures the bulk tail and says so itself.**
Added 2026-08-06 after the operator asked whether "flat" means "we hit the ceiling." Those are
different claims and only the first is tested by (C). The distribution-free record test
(`scripts/ceiling_record_test.py`): in *n* i.i.d. draws, running-maximum records arrive at rate
1/n, so the expected count is `H_n ≈ ln(n) + γ` regardless of the underlying shape. A deficit is
the signature of a bounded distribution being approached.

```
RANKED LANE   n=163,901   records 13   expected 12.58 (sd 3.31)   z = +0.13
              last record at draw 154,576 of 163,901 — 5.7% of the sample ago
HONEST ARM    n= 28,126   records  5   expected 10.82 (sd 3.03)   z = -1.92
              last record at draw 784 — but only 5 records, so almost no power
```

The ranked lane is setting records at **exactly** the unbounded-search rate, and the trail is
still climbing through the promotion gate: 1.4738 → 1.5325 → 1.5501 → 1.6006 → **+1.7397 on
2026-08-03**. This direction cannot be explained by our ranker improving: **better selection
reaches a ceiling faster, it cannot exceed one.** The honest arm's apparent deficit is a sampling
artifact — it draws prefilter-*rejected* configs, so its maximum is a lucky early draw from the
reject pile.

(C) reads the top-*decile* mean, rank ~120-from-top; records live at rank 1. So the observed state
is exactly the blind spot (C) names in its own text: **the bulk tail has stopped moving, the
extreme tail has not.** This does not invalidate the freeze — but it forecloses reading it as
"the grammar cannot produce a better component," and the +1.7397 is the concrete refutation.

**AND WE HAVE BEEN MEASURING THE WRONG COORDINATE.** Promotion is a JOINT requirement, and
stage-one pass rates show which gates actually bind:

```
wf_sharpe_p25 / wf_sharpe_p10   100.00%   <- the non-binding enrichment labels
walk_forward_sharpe_median        0.49%   <- a DIFFERENT gate, second-most binding
cpcv_sharpe_p25                   0.00%   (11 of 198,360)
```

Of the 11 stage-one configs that have **ever** cleared cpcv ≥ 1.5, **7 failed
`walk_forward_sharpe_median`**; the single one that promoted failed nothing at all. WF-median pass
rate does rise with cpcv rank (0.7% overall → 38% in the top 100), so the two are positively
correlated — but it still rejects 62–80% of our best cpcv configs.

**Condition (C), the freeze legs, and the record test all measure cpcv alone.** None of them sees
the binding joint surface. That is not an error in (C) — it measures what it was specified to
measure — but it means the question *"can the ceiling go higher"* has never actually been asked on
the surface promotion requires. (Note the three WF-family gates are easy to conflate: the v50
retarget rationale correctly described `wf_sharpe_p25` as admitting 100%; `walk_forward_sharpe_median`
is a different gate and binds hard.)

**AND THE JOINT FRONTIER SAYS THE BINDING CONSTRAINT IS NOT GENERATION AT ALL.** Measured
2026-08-06 (`scripts/joint_frontier.py`). A config is a *frontier advance* if nothing earlier beat
it on **both** axes; the null is a PERMUTATION of arrival order over the fixed point set, which
preserves the cpcv/WF dependence — the closed-form `(ln n)²/2` assumes independence and would have
manufactured a saturation finding.

```
RANKED LANE   73 advances vs permutation null 37.0 (sd 10.0)   z = +3.60, p = 0.003  STILL ADVANCING
HONEST ARM    28 advances vs null 32.9                          z = -0.50, p = 0.708  STATIONARY
```

Our best effort is still pushing the joint frontier outward faster than chance; the unselected
supply is stationary, consistent with leg 1 reading flat. **But the frontier is not where the loss
is.** Restricting to the window where `measurement_basis` is 100% populated (decided ≥ 2026-07-27):

```
  stage-one configs clearing BOTH binding gates (cpcv >= 1.5 AND WF-median >= 2.0):  23
     all 23 IDENTICAL at stage one: decision=reject, failed [deflated_sharpe, regime_coverage]
      9 refit into fullhist_refit  ->  9 became components
     14 never refit
```

Refit latency is **median 0h, p99 2h, max 3h** over 36,061 pairs, and 13 of the 14 are 1–5 days
past their stage-one decision — so they were **passed over, not queued**. Same eligibility, same
failure set, different outcome: the difference is which rows the newest-first scanner reached.
**61% of our best-ever supply never entered the only lane that can produce a component.**

Not claimed: that the 14 are better than what was refit (9/9 is consistent with the lane's ~80%
base rate, p=0.13). Claimed only: they were identically eligible. Relayed to Crucible 2026-08-06.

**This is the single most important qualifier in this document.** Adding grammar surface while
losing 61% of what already clears both binding gates would be solving the wrong problem — and it
is further evidence that freezing *generation policy* is the correct call.

**PER-LANE: ALL THE REMAINING CEILING IS IN `swing_mid`, AND NO LANE IS SATURATING.** Joint
frontier by bucket (ranked, stage one), with a per-lane permutation null:

```
bucket           n       advances   null      z       max cpcv @ WF>=2.0
swing_mid    139,730        68      35.8   +3.71      +1.601
swing_long    18,611        34      35.6   -0.19      +1.084   never reached cpcv 1.5
swing_short    5,560        26      26.3   -0.05      +0.714
```

`swing_mid` is the only lane still advancing, the only one that has ever cleared both binding
gates, and it holds every record. **But `swing_long`/`swing_short` are STATIONARY, not exhausted** —
a distinction we initially got wrong and corrected the same day. Advances per *doubling* of
cumulative search is the saturation metric, and it declines only when a bound is being reached:

```
swing_mid    2 3 2 2 2 2 3 3 6 4 4 3 5 6 5 7 10     <- RISING; improving, not saturating
swing_long   1 2 2 3 1 3 2 0 2 3 3 3 4 1  5         <- FLAT; stationary, still advancing
```

Neither shows the declining signature. What is true of `swing_long` is that its frontier sits far
**below** the promotion gate — a low ceiling, not a reached one.

**And the lane with ceiling left is the capacity-bound one.** `swing_long` converts at STAGE ONE
(29.1%, so it needs no refit and is immune to Crucible's queue); `swing_mid`/`swing_short` convert
0.0% at stage one and depend entirely on refit. Our mix is 80.7% swing_mid. **So the ceiling cannot
be bought by shifting toward the unthrottled lane — that lane's ceiling is below the gate.**

The saturation experiment that would settle exhaustion is designed and **HELD** at
`ceiling-saturation-experiment.md`, blocked on the refit-ordering answer; its honest cost is ~33
days per doubling, ~3 months for the full falsifier.

**AND OUR "ZERO PROMOTES" WAS A MEASUREMENT SHADOW (D370).** Crucible reproduced our 23/9/14
exactly, then found that validating it exposed a validator crash: §20 (2026-07-22) made
`deflated_sharpe` recorded-but-non-binding while their `PromotionDecision` validator still required
a promote to carry zero failed gates — and §20 keeps the exempt DSR *recorded as failed*. **Every
stage-two child good enough to promote since has crashed at the stamp: 31 configs, 67 children, 12
permanently blacklisted, 9 first crashing 08-05/08-06 and accelerating with v55 quality.** Failed
runs never export, so this was structurally invisible to us. Verified on our ledger: **4 promote
verdicts ever, all pre-§20, ZERO since 2026-07-23.**

Two of our "14 never refit" were in fact refit within seconds and destroyed at the stamp, so 61%
decomposes as **52% passed over + 9% destroyed at the finish line**.

**(C) and the frontier/record tests are UNAFFECTED** — all read stage-one distributions, and the
crash is at the stage-two stamp. What is shadowed is any claim resting on recent promote counts.
**The freeze premise holds with MORE force**, as Crucible put it: the binding constraint sits even
further downstream of generation than we had measured.

**Coverage is not the same as having tested the surface.** An indicator audit (2026-08-06) found
**19 of 72 registered indicators completely dark** — 5 by recorded decision, 11 by accident, and
one (`yz_rank`) structurally identical to `rv_rank`, which carries 17% of all configs. It also
found `rv_rank`-primaried trend configs — **77,416 all-time, the single largest trend cell** —
have **never once** carried a second regime gate, blocked by a C1 family collision rather than by
evidence. **(A) is satisfied and that surface is still untested.** These are coverage findings,
not alpha findings, and none of them is a reason to delay the freeze — but none of them should be
described as settled either.

## 5. Reopeners (unchanged from the criterion)

Each reopens a `grammar_version` bump, operator-gated:

1. **A Crucible refutation retraction** — a cell ruled dead is re-validated (the ghost-era class).
2. **A new registry family with a net-long-vega mechanism argument** — genuinely orthogonal and
   correctly-signed, not the currently-dark seller-side surface set.
3. **A Path-C structural decision** — the operator un-parks defined-risk structure. This raises the
   promotion cap and necessarily reopens the grammar.

**Two candidate reopeners already exist and are named here rather than discovered later:** the
`rv_rank` second-gate blind zone (§4), and the accidental dark-indicator set. Both fall under (2)
if pursued; neither is a refutation of the freeze.

## 6. Governance after freeze

Unchanged from the criterion, and it is what makes a freeze meaningful rather than decorative.
Any post-freeze change is a full increment: prereg **before** the edit with its **required n
stated at registration** (D363/D364), version bump + archive + Decision Log (hard rule #10),
goldens re-pinned, **emission proof**, funnel attribution, STATUS block.

Standing obligations to Crucible carry forward (`INDEX_forge_answered.md`): report drift from
their eligible-vs-drain ratio in either direction — **under-supply is now the failure mode that
costs components** — flag honest-arm rate changes that move a registered basis, and never tune
generation against `IC(cpcv, corr_to_book)`.

## 7. Open at declaration

- **No preregistration is open.** The registry stands at **31 registered, 31 resolved** (20
  confirmed, 6 refuted, 5 insufficient). `6e81bfaa3907` (adx regime-gate
  replication), listed here as "not due" at declaration time, **read CONFIRMED 2026-08-08** at
  n=1,727 against its registered n≥1,500, with the collider check re-run as part of the read. It was
  never a freeze condition and did not gate this declaration.
- **✅ CLOSED 2026-08-14 (D392) — the overdue-read gap (D389).** The defect as found: `STATUS.md`
  described a watcher as armed with no systemd unit and no cron entry behind it, and the read tool
  printed its verdict without writing the registry, so `3b0cbca7ae17`'s resolution had to be entered
  by hand after its clock (7,490 rows against 7,200 required) had already passed.
  **Fixed:** `forge-prereg-watch.timer` armed daily (reports DUE / waiting / **UNWATCHABLE**, with
  no `SuccessExitStatus` so every condition surfaces), and `freeze_registered_read.py --resolve`
  writes the outcome through the repo's own resolver. 16 tests, TDD.
- **`scripts/second_gate_contrast.py` pools across `measurement_basis`** — the D360 defect, in a
  committed instrument. Worth fixing before it is used to judge any future second gate.
- **`young_explore` REMOVED outright** (D367 kept it OFF; D378 deleted the never-enabled lane,
  operator 2026-08-06): 87% of its budget would fund `volatility_event`, the
  family whose floor was just retired.

---

## 8. Next steps — can the ceiling go higher?

The §4 findings change this from a rhetorical question to a measurable one. Ordered by what has
to be true before the next thing is worth doing.

**Step 1 — DONE 2026-08-06, and it reordered everything below.** `scripts/joint_frontier.py`.
The joint frontier is still advancing (z=+3.60, p=0.003) — so no ceiling — but the measurement
found the real constraint one step further down: **14 of 23 configs clearing both binding gates
were never refit**, with an identical stage-one profile to the 9 that were, and refit latency of
p99 = 2h proving they were passed over rather than queued. **The binding constraint on component
production is refit triage, not generation.**

**Step 2 — ✅ ANSWERED AND CLOSED 2026-08-14 (D393).** The ask (relayed 2026-08-06): is
newest-first refit ordering deliberate under the doubled capacity? **It was an artifact, and
Crucible fixed it on 2026-08-06 — the day after the relay, before answering in words.** A quality
sub-lane now reserves budget for the best margin over both binding bars. Measured over 44h:
**2.5% of volume → 84% of the promotes (6.30% vs 0.03%, a 206× ratio).**

**And the lane is finished rather than under-funded.** They raised its share 20% → 80%, measured
no effect, and reverted the same day — it finds 0–3 eligible candidates per pass. *"Refit our best
2,000"* was already executed: 1,736 above-floor rows are components, 1,460 more have children, and
un-consumed above-floor supply is **three rows**.

**Consequence for this document: both candidate answers to "what binds component production" are
now closed — not generation (Step 1's finding), and not refit triage (Step 2's).**

**Step 3 — ~~re-read (C) under the restored capacity~~ STRUCK 2026-08-14. Its premise is
withdrawn earlier in this same document.** It read: *"(C) was read at 25% eligible stage-two
coverage; Crucible has since doubled the drain."* **§4's first entry withdrew that caveat as
wrong** — both (C) legs read **stage-one** cpcv distributions on the honest arm, and the capacity
raise is entirely stage-two, so drain coverage never touched (C)'s basis. A step written to remove
"the largest caveat in this document" survived the caveat's own retraction by three days and was
never re-checked against it.

Recorded rather than deleted, because a struck step and an absent one carry different information:
this one shows the document disagreeing with itself for eight days while signed-adjacent. Separately
and for a different reason, (C) **has** been re-read — `3b0cbca7ae17`, within-basis, both legs
confirmed (D389) — which is the replication Crucible's generation-basis finding made necessary, not
the capacity re-read proposed here.

**Step 4 — probe the untested surface — DEPRIORITISED, and the reason is Step 1.** Adding grammar
surface while 61% of what already clears both binding gates never reaches stage two is solving the
wrong problem. Retained here because the targets are real and named, not because they are next.
Two concrete targets, both discovered 2026-08-06 and neither yet acted on:
- the `rv_rank`-primaried trend cell — **77,416 configs, the single largest, has never once
  carried a second regime gate**, blocked by a C1 family collision rather than by evidence.
  C1-legal candidates: `market_state` (macro) or `adx`/`hurst` (trend_strength).
- `yz_rank` — structurally identical to `rv_rank` (volatility, lookback 252, rank-coherent), which
  appears in 17% of all configs and in the most recent record-setter. It has no threshold spec and
  has never been discussed anywhere.

**If Step 4 is ever taken, score it on the joint frontier, not on cpcv.** The dsj precedent is the
warning: dsj produced a real stage-one cpcv effect (z=+5.44) and, through our own generator, **zero
promoted components in 6,707 tries.** Probing new surface and grading it on cpcv would repeat that
exactly. Each probe is a full increment under §6 — prereg first, required n stated, emission proof,
funnel attribution.

**Step 5 — housekeeping that blocks clean measurement.** `scripts/second_gate_contrast.py` pools
across `measurement_basis` (the D360 defect) and is the instrument we would naturally reach for
when judging any new second gate. Fix before Step 4.

**Not proposed:** re-opening the grammar for expansion, or acting on any of the 11 accidental dark
indicators as a group. Those are coverage findings; nothing yet says they carry alpha, and D361's
standing result is that supply composition is not currently an actionable lever on the promotion
axis.

---

**Recommendation.** Declare the freeze, with §4 attached and non-optional. The conditions are met
as written and the writing was honest. The single most likely misuse of this document is someone
quoting "(C) MET" as evidence that the grammar cannot produce a better component — it is not that,
it was never that, and §4 exists so the record says so before anyone needs it to.

**And declare it as a supply-hygiene result, not an exhaustion result.** The evidence in §4 is that
the extreme tail is still moving and that the binding axis has never been measured. Freezing
generation *policy* while those remain open is coherent — Step 1 is analysis, and Steps 2–3 are
reopener-class work the criterion already anticipates. Declaring exhaustion would not be.
