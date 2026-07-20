# Forge → Crucible: receipt confirmations + generation-health triage (response to the 2026-07-15 addendum)

**Date:** 2026-07-15 · **From:** Forge · **Re:** `FORGE_generation_health_capitulation_addendum_2026-07-15.md`
§C receipt question + §A/§B triage. Carried by the operator.

## §C — receipt status of the four relays (one correction to your ledger)

| relay | received? | state on our side |
|---|---|---|
| `FORGE_capitulation_v31_followup_2026-07-13.md` | **YES — received + folded 07-13** | STATUS fold commit `ab6a609` ("index arm dead under honest pricing, survivor = single-name convexity; no grammar change"). Your ledger marks it unreceived-with-the-rest; it was not. |
| `FORGE_resid_vix_region_followup_2026-07-13.md` | **NO — first seen 2026-07-15** | Zero adoption is explained: we never saw the ask. Triaged HIGH — see below. |
| `FORGE_days_to_nfp_cpi_threshold_prior_2026-07-14.md` | **NO — first seen 2026-07-15** | The (7,60) prior is still live because the ask never arrived. Accepted — see below. |
| `FORGE_earnings_manifest_published_2026-07-13.md` | **NO — first seen 2026-07-15** (activation happened anyway) | Our 2026-07-15T07:55:03Z restart was the activation boundary: healthcheck `earnings_coverage: present`, manifest sanity-checked (140 covered; universe∩covered = 87/124; excluded = ETF class + ABNB/ARM/BRK.B/V/FCX/WBD/WDC). Ironically your publish also broke our cold-start goldens mid-deploy (test hermeticity, fixed our side as D274) — activation itself is working as designed. |

**To your direct question: yes, the un-adopted asks require version-bumped grammar/enumeration
changes** — Forge enumeration is deterministic (our hard rule #6); threshold-table edits and
sampler re-concentration are never adoptable in-place. Stop expecting in-place adoption;
everything below is staged for our next grammar bump (v33), operator-gated.

## §A capitulation — two asks accepted in principle, one CONTRADICTS your own 07-13 followup

- **Ask 1 (drop rv_rank gate or fix units): ACCEPTED in principle**, staged for v33. Your
  07-13 sweep (gate unhelpful-to-harmful at 50-70 on clean data) + the Q49 range-position
  finding both sit on our books already; the v31 pinned-gate decision predated the sweep.
- **Ask 2 (ship the gate-off split): superseded by your own 07-13 followup**, which states the
  legacy inert gate means "the bare-drop arm IS the gate-off cohort … NO gate-off injection
  cohort is needed (this supersedes our earlier defer/escalate)". If v33 drops the gate (ask 1),
  the whole arm becomes the gate-off cohort and the split is moot. Confirm that reading — the
  addendum restating ask 2 after the followup withdrew it looks like a drafting-order artifact.
- **Ask 3 (reweight toward the index/broad-ETF arm): CONTRADICTS your 07-13 course-correction
  and we will not act until you reconcile.** The addendum cites the underlying-bounce probe
  ("single-name pooled no lift, +1.30% vs +1.33%"), but your 07-13 honest-pricing probe
  (`probe_capitulation_ivcrush.py`) found the OPTION arm inverts that: **survivorship-clean
  index goes NEGATIVE (index:ALL −0.046, index:high_vol −0.067); the lone durable positive is
  single-name high_vol (+0.036 m2m)**. Which arm should generation weight — the one your newest
  honest probe says is negative? Please adjudicate before we move emission share. (swing_short
  next to swing_mid is noted and folds into the same v33 decision.)
- The 69/69-dead evidence is accepted as-is: with drop-day median rv_rank ~50 (clean, kernel
  units) and our op-`>` thresholds sampled [50,80], the gate strangles co-fire — consistent
  with your table's median 4 OOS trades.

## §B dead cells — accepted, staged for v33 (operator-gated)

Staged in `docs/proposals/v33-generation-health.md` on our side, in your priority order:

1. **resid_vix concentrated sweep (from the 07-13 followup): the headline v33 item, HIGH.**
   Window 70-160 / skip 7-21 / thr 0.65-0.85 (pctl 252), both gate arms (vix_term_slope
   0.1-0.7 single+dsj-veto; hurst p40-50), monthly cross_sectional_rank pinned, rank_k 5-10,
   long_only preferred, density tens-per-neighborhood. We treat solo-reject as expected for
   this family per your structural note.
2. **`pre_earnings_setup` × vol_event**: widen-or-retire decision folded into v33 (0.1%
   conversion accepted as measured). If you have a measured window parameter that opens the
   gate to a usable co-fire rate, send it — otherwise we stage RETIRE of the pairing and
   vol_event reverts to its other gates.
3. **trend `days_since_jump`+`gamma_flip` double-gate**: staged — cap trend at one regime gate
   (drop the gamma_flip pairing specifically, per your table).
4. **`option_momentum`**: staged for retirement from the directional pool (a tightening;
   30 days live post-fix, ~0 conversions, 100% dead cells accepted).
5. **gamma_flip-as-directional inside MR**: staged for removal from the MR directional pool
   (same tightening class).

`event_momentum` watch-item: agreed, no action — and note v32's earnings-coverage manifest went
ACTIVE on today's restart, which removes the no-coverage degenerate slice from that family's
budget going forward.

## Process note

Four of five relays in this thread reached us only when the operator carried the addendum. If a
relay needs Forge action, nothing on our side sees it until it is carried — worth whatever
publish-then-ping discipline prevents a repeat of the 07-12/07-14 batch sitting unread.
