# Grammar freeze — DECLARATION (DRAFT, awaiting operator)

**Status:** DRAFT. All three conditions of `grammar-freeze-criterion.md` are MET as of
2026-08-06. Declaring the freeze is the operator's act, not this document's.
**Programme:** D328 → D367. **Grammar at declaration:** v55.
**Relates to:** `docs/proposals/grammar-freeze-criterion.md` (the criterion this reads against),
`IMPLEMENTATION_DECISIONS.md` D328–D367, `INDEX_forge_answered.md` (Crucible-side agreements).

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

### (C) Supply ceiling — MET 2026-08-03, and read under conditions that have since changed

Both legs read **once**, at their registered window counts, against bars fixed in advance:

| leg | prereg | windows | best-of-new | baseline | excess | bar | verdict |
|---|---|---|--:|--:|--:|--:|---|
| 1 — quality (standardised TCM) | `f507e5da0677` | 11–16 | 0.7589 | 0.7548 | **+0.0041** | 0.0242 | CONFIRMED |
| 2 — redundancy (TCM-corr) | `13e4d2cece3f` | 12–17 | 0.4378 | 0.4411 | **−0.0033** | 0.0173 | CONFIRMED |

Both also clear a bar **re-derived on post-ramp data that is 3.3× tighter** (0.0074 / 0.0130), so
the result is not an artifact of a loose threshold — the one direction that could not have been
walked back (D358).

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

**(C) was read during a capacity squeeze that has since been fixed.** Stage two was covering
**25% of eligible supply** at read time, against ~110% pre-flood. Crucible has since raised
`scan_and_queue --limit` 20 → 40, roughly doubling the drain to ~5,760 refits/day. Both sides
agreed in writing that (C) **must not be cited as exhaustion**. The condition is met exactly as
specified, and the specification was honest — but the ceiling was measured under conditions that
no longer apply, and *"the grammar stopped improving"* versus *"we could not measure a grammar
improvement"* were genuinely entangled in that window.

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

- **Prereg `6e81bfaa3907`** (adx regime-gate replication) — **not due**: n=1,021 against a
  registered n≥1,500. Its observed ρ=−0.1004 *would* clear its MDE, which is precisely why it is
  not being read early. ~1.5 days at the observed rate. **It is not a freeze condition** and does
  not gate this declaration.
- **`scripts/second_gate_contrast.py` pools across `measurement_basis`** — the D360 defect, in a
  committed instrument. Worth fixing before it is used to judge any future second gate.
- **`young_explore` remains OFF** (D367): 87% of its budget would fund `volatility_event`, the
  family whose floor was just retired.

---

**Recommendation.** Declare the freeze, with §4 attached and non-optional. The conditions are met
as written and the writing was honest. The single most likely misuse of this document is someone
quoting "(C) MET" as evidence that the grammar cannot produce a better component — it is not that,
it was never that, and §4 exists so the record says so before anyone needs it to.
