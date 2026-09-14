# Forge — Implementation Decisions Log

Append-only. Each entry: ID, date, spec section, decision, rationale, alternatives considered, action.

Order is chronological. Decisions are referenced from `STATUS.md`, `OPEN_QUESTIONS.md`, and `PHASE_N_HANDOFF.md`.

> **Note (D059 / P3-4 2026-05-18):** Older entries reference Crucible coordination prompts (`CRUCIBLE_*_AGENT_PROMPT.md` at repo root) that were deleted in commit `e85f0d4` ("docs: archive paired Crucible coordination docs + drop completed unpaired prompts") after their work shipped. The references are preserved in the historical narrative below; the prompt files themselves are recoverable via `git show e85f0d4^:CRUCIBLE_*_AGENT_PROMPT.md`. The 7 deleted prompts: `CRUCIBLE_FEATURE_CACHE_AGENT_PROMPT.md`, `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`, `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md`, `CRUCIBLE_EV_DEADLOCK_AGENT_PROMPT.md`, `CRUCIBLE_EMPTY_THRESHOLD_AGENT_PROMPT.md`, `CRUCIBLE_DB_CHECKPOINT_ON_BATCH_AGENT_PROMPT.md`, `CRUCIBLE_TRADE_CONCENTRATION_METRIC_AGENT_PROMPT.md`.

---

> **Rotation (D242, 2026-07-05; extended 2026-08-06, Step A3):** earlier entries live
> verbatim in `_archive/IMPLEMENTATION_DECISIONS_D001-D200.md` and
> `_archive/IMPLEMENTATION_DECISIONS_D201-D300.md`, and (2026-09-13, Batch 1)
> `_archive/IMPLEMENTATION_DECISIONS_D301-D350.md`. Code/docs cite D-numbers, not
> paths — grep the archives for `## D0`/`## D1`/`## D2`/`## D300` entries. This file
> continues from D301.

> **Relay pile removed (2026-09-13, Batch 1 / D407):** the 150 `_archive/PROMPT_*` and
> `_archive/CRUCIBLE_*` relay files (the retired root-channel record) were `git rm`'d; recover any
> one with `git show fd9cba4:_archive/<filename>`. The live relay channel is `~/proj/freeze/relays/`.

## D351 — 2026-08-02 — v52 → **v53**: chain-inception floors (enumeration-policy bump), bundled with the generation-A/B teardown and the honest-arm ramp revert

**Spec section:** §3 (enumeration policy), §7.3 (submission budget); hard rules #4 (tightening — may ship), #6 (determinism), #10 (version bump on any `grammar.yaml` byte change). Class: **enumeration-policy bump** (D098/v5 class) — `rules:` text UNTOUCHED. Operator-directed ("let's deploy").

**Decision.** The underlying pool for each config excludes names whose first option-chain snapshot post-dates that config's backtest-window start, read per batch from Crucible's `chain_inception_floors_*.json`. `forge/enumeration/chain_inception.py` + sampler/iterator/CLI wiring.

**Why.** Those configs are refused `pre_inception` **permanently for the window** — pre-IPO chains cannot be backfilled — so each burns a submission slot and a runner cycle for a verdict that can only ever be a refusal. Measured ~22/day. Crucible's own `pre_inception` failure category already unpinned our §7.3 limiter (all 11 such rows retire via the D240 flush), so the residue is throughput only: ~16 failing configs/day against ~4,200/day = **~0.4%**. That did not justify a restart on its own, which is why the bump was **HELD from 2026-08-01** and rode this window instead — the standing plan recorded in relay `64088e2`, executed.

**THE WINDOW IS PER-BUCKET, AND THE FIRST VERSION WAS WRONG.** Crucible queues each `dte_bucket` at the history its §8.7 min-trade floor needs: **1,825d swing_short/swing_mid, 2,555d swing_long**, 1,825d default, sliding from `polygon_data_asof`. We had inferred a flat 5 years and verified it **5-of-5** on the boundary names — a check that *could not have failed*, because all 49 recorded `pre_inception` failures are 5y-lane runs and the 7y trap has never fired. 18% of decided volume rides the 7y window and that cohort is **100% trend_continuation/swing_long**. Refusing to ship on an inferred semantic (the D342 lesson) is the only reason this was caught before deploy rather than months later; the flat-5y filter would have looked like it was working the entire time.

**Design — refresh, never pin.** Unlike the D278/D286 untradeable list, the exclusion set is recomputed from the newest export every batch: floors move EARLIER on backfill (never later) and the window slides, so a frozen list would both starve names that became legal again and miss names that just became illegal. Both directions are pinned by tests. `ChainInceptionExclusions` (frozen, `slots=True`) replaces a bare `frozenset` through sampler/iterator/CLI, and `for_bucket()` is its only reader — a bare mapping would let a call site index it with a missing bucket key and silently re-introduce the flat-window bug. A **183-day fail-safe margin** drops a name shortly BEFORE it starts failing rather than after; it also absorbs the `polygon_data_asof`-vs-calendar skew. Fail-open on absent/unreadable/malformed export → empty set → emission byte-identical (#6).

**Emission proof (v53, live registry, seed 20260802, 4,000 configs).** Bucket-aware: **221 → 0** configs on excluded names, single-name supply **3,573 → 3,547** (−0.7%, draw redistribution). Live exclusion sets at deploy: **14** for the 5y buckets, **22** for swing_long; the 8 swing_long-only names are ABNB DASH LYFT PLTR RTX SQQQ UBER UVXY — six of which we had filed as permanently dormant. Crucible counts 20 for swing_long; our extra two are LYFT (2019-04-04) and UBER (2019-05-16), inside the margin band and not failing yet — the fail-safe working, confirmed as intended by them ("keep 183 uniform").

**Bundled in the same restart (each independently settled, none needing its own window):**
1. **`FORGE_PREFILTER_SAMPLE_N` 150 → 40** — the D341 ramp obligation. Time-boxed to the generation A/B, which resolved today; at 150 we forgo ~31% of ranked production/day.
2. **`FORGE_GENERATION_ARM_B_SHARE` 0.5 → 0** — the registered falsifier action for prereg `4e369b779ca9`, REFUTED (D350): honest-arm p90 delta −0.0039, bootstrap P(delta≤0)=0.5210, and the secondary agrees. Revert to a single map.
3. **`forge grammar reject-proposal --id f59812c7`** — the operator audit row for the declined cell-prune (D349), which needs a DB write and therefore the stopped window (Q60).

**Deliberately NOT bundled:** the `young_explore` lane (D316 2d). Its configs stamp `selection_arm=None`, so they are invisible to the freeze criterion's honest-arm analysis; flipping it in the same restart that changes the submission mix twice over would make its effect unattributable. It gets its own window.

**Files:** `src/forge/enumeration/chain_inception.py`, `sampler.py`, `iterator.py`, `src/forge/cli/main.py`, `tests/unit/test_enumeration/test_chain_inception.py`, `config/grammar.yaml`, `config/grammar_archive/v53.yaml`, `deploy/systemd/forge.service`, `STATUS.md`.

## D352 — 2026-08-02 — v53 → **v54**: the chain-inception filter was NEVER LIVE — one missing keyword argument, and every gate we ran was blind to it

**Spec section:** §3 (enumeration policy); hard rules #6 (determinism/emission identity), #10. Class: **enumeration-policy bump** (D098/v5); `rules:` text untouched. Operator-directed.

**The defect.** `_run_one_iteration` computed `below_inception = underlyings_below_inception(...)` per batch, echoed it to the journal, and **never passed it** to `_run_battery_for_seed`. The parameter took its `None` default and enumeration ran unfiltered. One keyword argument, absent from one call site, from `fa00daf` through the entire v53 deploy.

**WHY IT SURVIVED A FULL DEPLOY RITUAL — the part worth keeping.** Nothing we ran could have caught it:
- The 13 unit tests exercise `underlyings_below_inception` **directly**, so they prove the predicate and never the call graph.
- The **emission proof passed `below_inception` explicitly into a test harness** — it proved the FUNCTION works, not that production reaches it. This is the exact shape of the mistake: a proof constructed around the path production does not take.
- The **journal line was the trap**: `chain_inception: excluding 22 underlying(s) (ABNB, ARM, …)` printed the resolved set faithfully, every batch, while nothing was excluded. [[D185]] says verify the FEATURE in the journal, not just restart health — this is its inverse, and the sharper rule is: **verify a filter by its EMISSION through the production path; a log line is not evidence.**
- Crucible's independent first-look "verified" it too, and their verification was underpowered rather than wrong-headed — see below.

**Measured contamination.** v53 cohort at discovery: **960 submissions, 96 single-name, 10 on excluded names** (LCID ×4, UVXY ×3, SQQQ, RTX, COIN). Nothing was actually burning cycles — the 7y-class names (UVXY/SQQQ/RTX) appeared in `swing_short` where they are legal, and LCID/COIN sit inside the 183-day margin zone, both clean today. **The only thing lost was the feature.**

**v53 IS A VOID COHORT FOR THIS FEATURE.** It is stamped as the chain-inception version and emits like v52. `funnel --compare v52 v53` is not a floors comparison; the floors comparison is **v53-vs-v54**, and v53's 960 rows belong with v52 for that purpose. Relayed.

**Why a bump and not a versionless fix.** Emission changes here, so hard rule #6 (versionless changes must be cold-start byte-identical) forbids shipping it unversioned, and doing so would split the v53 cohort at an unrecorded timestamp. The grammar-change taxonomy is explicit that a Python-side change altering the emitted population "still bumps `grammar_version` for cohort attribution."

**The durable guard.** `tests/invariants/test_enumeration_inputs_reach_the_battery.py` — any local in `_run_one_iteration` whose name matches a `_run_battery_for_seed` keyword must be forwarded under that name. Static (`ast`) rather than behavioural, because the defect is a **missing edge in the call graph** and an emission test would need the whole daemon path (DB, registry, cache) to observe what parsing proves in milliseconds. Verified **red against the exact defect, then green**, and its class sweep reports only this one name — no false positives. It guards every future enumeration input, not just this one.

**Crucible's first-look, corrected (their `aac80d7`).** They read RIVN 38→0, CEG 19→0, ARM 27→0 as the loop closing. At their own stated sample — ~820 arrivals, ~9% single-name ≈ 74 configs over a ~118-name universe — the per-name expectation is **under 1**, so three zeros are noise, not evidence. **LCID ×3 against an expectation of ~0.6 was the real signal, and it pointed the other way.** The names they filed as a harmless curiosity were the tell; the names they used as proof could not have discriminated. Their instinct to flag COIN/LCID was right and their §1 conclusion was premature.

**Files:** `src/forge/cli/main.py` (the one line), `tests/invariants/test_enumeration_inputs_reach_the_battery.py`, `config/grammar.yaml`, `config/grammar_archive/v54.yaml`, `tests/integration/test_v1_grammar.py`, `STATUS.md`.

## D353 — 2026-08-02 — freeze condition (C) is UNEVALUABLE, not unmet; and the threshold-resolution probe refutes its own proposal

**Spec section:** `docs/proposals/grammar-freeze-criterion.md`. **(1) (C)'s recorded reading contained a BASIS VIOLATION inside the measurement meant to enforce the basis:** one of its two 1.5-clearers was quoted at 1.6629, which is its `fullhist_refit` **stage-two** value; its stage-one row reads 1.1703 and is a reject. Corrected stage-one count is **1, not 2**. **(2) The corrected series has no power** — 1 → 1 across a 1.6× sample, and [[D341]] (same day) priced detecting a doubling of P(cpcv ≥ 1.5) at ~183 days/arm. So neither "the tail did not converge" nor "the tail is exhausted" is supported. **(3) The threshold-resolution probe:** directional threshold resolution buys nothing (well-powered null, 0/21 cells clear their own MDE) — **but the action it was meant to justify is refuted by its own feasibility check**: coarsening the directional threshold to 1dp collapses 1 config of 95,376, and coarsening every continuous parameter still leaves 74.8% distinct. The n_trials treadmill is structural composition, not parameter resolution. **(4) The regime gate is the real find, and the collider check made it usable:** `adx` is clean (observation rate flat, 5.1pp spread) at rho −0.226/−0.190 across two independent cells; `vix_term_slope` is CONFOUNDED (rate of getting a cpcv falls 75.9% → 50.7% across its range) and must not be read causally.

## D354 — 2026-08-02 — `/tmp` is a 62 GB tmpfs and the live DB is 6.7 GB: the house snapshot ritual was eating RAM

**Spec section:** ops; `docs/tasks/investigate-live.md`. **The ritual said `cp ~/forge_data/forge.db /tmp/forge_snapshot.db`.** Nine investigation snapshots in one session filled tmpfs and **took the shell down twice** — every command, including `true` and `/bin/echo`, returning **exit 1 with no output**, because the harness could not write its own output capture. It presents as broken tooling, not disk-full, which is what makes it expensive. **It had billed production before:** `MANPAGE:553` records the 2026-07-09 stall where the daily ranker-eval's `cp` failed on a full /tmp, F3 and wf_p25 silently staled, and the `model` check CRIT'd ~2 days later. **[[D259]] responded with a DETECTOR (`tmp_headroom`) and left the cause in place, in six documents, for three weeks.** **Fixed at the source:** `scripts/live_db_snapshot.sh` (one reusable real-disk snapshot, refuses tmpfs/ramfs, checks free space, reuses <15 min, `--clean`); `daily_ranker_eval.sh` moved off tmpfs; all eight stale instances swept. **Transferable:** a hazard documented in a detector's rationale is still a live hazard — when an incident note explains a cause, fix the cause in the same change.

## D355 — 2026-08-02 — honest-arm rate re-ramped 40 → 150 to run the freeze clock, with the revert written into the unit file

**Spec section:** §7.3; D335 honest arm. `FORGE_PREFILTER_SAMPLE_N` was cut 150 → 40 in [[D351]] once the generation A/B was resolved, because a 150/batch uniform draw from prefilter-**rejected** configs is a real throughput tax with no live experiment to fund. Freeze condition (C) then needed windows: both legs read consecutive n=1200 windows of the honest arm, and at 40/batch the clock runs ~3.75× slower. Re-ramped to **150** to make the read land in days rather than weeks. **The cost is stated, not hidden:** ~110 extra submissions/batch of known-rejected configs, and the rate change is itself a caveat on both preregs — windows now span ~0.65 d instead of ~1.7 d, so true drift *within* a window is smaller than the `b` fitted on the slower series, which makes "flat" **easier** to declare. That is the unrecoverable direction, so both preregs carry an explicit obligation to **re-derive the a/b fit on post-change data before either read is final**. **⚠️ REVERT TO 40 once `f507e5da0677` and `13e4d2cece3f` are read** — recorded in `deploy/systemd/forge.service` next to the variable rather than only here, because a standing obligation kept solely in a ledger is one nobody reads at the moment it binds. **Transferable:** when you change a sampling rate that a registered measurement depends on, the rate change is part of the measurement's basis — write the revert where the operator will see it, and say which direction the bias runs.

## D356 — 2026-08-02 — freeze condition (C) gets its second leg, and it is Forge-computable after all

**Spec section:** `docs/proposals/grammar-freeze-criterion.md`; prereg `13e4d2cece3f`. Leg 1 asks whether the grammar's quality ceiling has stopped rising; it is **silent on assembly value, and that silence is dangerous rather than merely incomplete.** Crucible measured `IC(cpcv_p25, corr_to_book) = +0.547` (confirmed 2026-08-02 as computed on the **zero-fill-equivalent** basis, so the convention error that forced retraction of the earlier +0.336 does not apply): better components **are** the more correlated ones. A quality-only freeze could therefore certify "done" at exactly the moment the stream is most efficiently producing the redundant supply Crucible asked us to stop producing. **We scoped the leg as relay-dependent and were wrong** — their `corr_to_book_*.json` already publishes **116,329 per-run rows keyed by `config_hash`**, and our honest arm joins to it. We asked them to build a periodic export **before checking whether the data was already on disk**; it was, and we told them to stand down. **The statistic:** composition-standardised **TCM-corr** — the post-stratification-weighted mean `|corr to book|` among configs at/above the window's own weighted p90 of cpcv, deliberately the same population/window/threshold/weights as leg 1, because the question is "is the supply that would actually be **used** becoming redundant." Their entanglement finding reproduces (top-decile `|corr|` 0.3837 vs 0.3171). **RISING IS WORSE**, so the reference is the prior **maximum** — the first implementation compared against the prior *minimum*, a max-drawup that any noisy series clears, and printed a false `WORSENED +0.0214` where the correct reading is −0.0082. Bar `max(2·b_up, 2·sd) = 0.0173`, the fallback load-bearing because the a/b split degenerates here (sd shrinks almost exactly 1/√n, leaving 2·b_up = 0.0034 against a series spread of 0.0087). Crucible's two conditions are bound into the falsifier: **supply statistic, never a generation target**, and **cohort-scoped**. **Transferable:** before asking another system to compute something for you, check what it already publishes — the ask cost them a design conversation and the answer was on disk the whole time.

## D357 — 2026-08-02 — the designation flipped mid-programme; the leg's reference stays pinned, and the yardstick is now self-checking

**Spec section:** `docs/proposals/grammar-freeze-criterion.md`; prereg `13e4d2cece3f`. The operator retired `aa31532489613849` for `f52a05c8968bdc7a` on **2026-08-01** (QuantIQ D306: the old champion was infeasible at 11.48% NAV drawdown against an 8% ceiling). Leg 2's reference `frozen_b36f49a4` is the **retired** book's minted series. The flip landed **before** the leg's prereg cut (08-02T17:26Z), so the whole registered series was already read against one fixed reference and **nothing needs re-basing**. **It stays pinned, and the decision is priced rather than argued.** On the 2,497 configs carrying both: per-config agreement **pearson +0.9582 / spearman +0.9531** — the choice costs essentially no ordering power — but the leg-2 **level** reads **0.4228** against the retired book and **0.3770** against the designated one, a gap of **−0.0458 = 2.6× the leg's own 0.0173 bar**, pointing **down**. A silent switch would have printed a large unearned *improvement* and biased the freeze toward MET on a reference change rather than a supply change: the unrecoverable direction. A coverage-chosen yardstick that chased the designation would also inherit a re-base on every future flip. **Two guards added, both converting a promise into a check.** (1) The instrument fingerprints the reference book's identity fields and **refuses leg 2 on any mismatch** (`ae47a4749c9d`, stable across every export on disk) — Crucible undertook to flag basis changes before shipping them, but a promise depends on someone remembering and this week produced a defect of exactly that shape on each side (our computed-but-never-passed keyword, their computed-but-never-persisted ablation value); a re-mint can move the level either way, so an unnoticed one could manufacture a false PASS. (2) `--leg1-bar`/`--leg2-bar` make the registered read use a bar **fixed before the data it judges** — left alone the script re-fits a/b on every run *including the windows under judgement*, and leg 2's bar moved 0.0173 → 0.0210 in one window purely from refitting. **That is peeking wearing a formula.** Runs without the flags are labelled `EXPLORATORY — NOT the registered read`. Also documented: post-stratification re-weights past windows as the sample grows (~0.0002, 1.2% of the bar), so resolution uses the prereg's **literal** baseline (0.4411), not the recomputed one. **Transferable:** an instrument that computes its own threshold from the data it is judging is not a test — pin the threshold and the baseline in advance, and make the tool refuse to pretend otherwise.

## D358 — 2026-08-03 — freeze condition (C) is **MET**: both legs read once, on their registered slices, and both survive a 3.3×-tighter bar

**Spec section:** `docs/proposals/grammar-freeze-criterion.md`; preregs `f507e5da0677` (leg 1) + `13e4d2cece3f` (leg 2), both resolved **confirmed**. **THE READS.** Leg 1 (quality, standardised TCM of the top decile): windows 11–16 = `0.7483 0.7589 0.7478 0.7552 0.7426 0.7457`, best-of-new **0.7589** against registered baseline **0.7548** = **+0.0041**, bar **0.0242** → **CONFIRMED, the ceiling has not resumed rising**. Leg 2 (redundancy, standardised TCM-corr over the same top decile): windows 12–17 = `0.4298 0.4202 0.4378 0.4345 0.4310 0.4368`, max-of-new **0.4378** against baseline **0.4411** = **−0.0033**, bar **0.0173** → **CONFIRMED, the good supply has not become more redundant.** Corr coverage **100% on all 17 windows**; reference basis fingerprint verified against the pin *before* reading. **THE BAR OBLIGATION COULD NOT BE MET AS WRITTEN, AND SAYING SO IS THE POINT.** Both preregs required re-deriving the a/b fit on post-`SAMPLE_N`-ramp data before the read was final. The ramp landed 08-02T09:00Z — essentially **at** leg 1's cut (08:24Z) — so there is **no post-ramp, pre-cut data to fit on**: the post-ramp data *is* the judged data, and fitting there is precisely the defect [[D357]]'s registered-bar flag exists to prevent. Resolved by reading on the **registered** bar (a prereg forbids extension) and re-deriving on the post-ramp era as a **disclosed sensitivity, never the decision**: `b_up` 0.0121 → 0.0037, so a post-ramp bar would be **0.0074 — 3.3× tighter**. **The read passes anyway** (+0.0041 < 0.0074), and also passes the `max(2·b_up, 2·sd)` variant (0.0176); leg 2 passes its own tightened bar (0.0130) trivially, having moved the safe direction. **So the result is not an artifact of a loose bar — the one direction that would have been unrecoverable.** Honest limit on the sensitivity itself: the post-ramp slice is 9,292 rows = 7 windows and its `b` point estimate is exactly 0.0000 — the "cannot resolve drift" signature — so 0.0074 is a **bound, not a measurement**. **NEW INSTRUMENT** `scripts/freeze_registered_read.py`, deliberately separate from the exploratory one: it hard-codes what the preregs fixed and **computes none of it**, reads *exactly* the registered windows (leg 1 takes 11–16 even though a 17th exists — reading it would be an extension chosen after seeing data), and **refuses** on a short or NaN-holed slice rather than rendering a partial verdict, because an early read that happens to pass is indistinguishable from peeking-to-threshold. Tests assert the hard-coded constants against the prereg registry itself, so script and record cannot drift. **WHAT THIS IS NOT:** (C) is a **supply-ceiling** result. Both legs sit at rank ~120-from-top while promotion-grade events sit at rank ~0.4–5, so **a top-1%-only lift is arithmetically invisible to them** — "flat" must never be read as "the grammar cannot produce a better component". The freeze still requires **(A)**, whose entire remaining surface is one cell (the capitulation cell, `mean_reversion/swing_mid/named/momentum/(nogate)`, 312 in 14d flow); **(B) is met** at metric B 0.28% against a 1.00% bar, 14 consecutive runs. **Transferable:** when a prereg's own caveat becomes unsatisfiable, do not quietly drop it and do not silently reinterpret it — read on the registered terms and publish the unmet obligation as a sensitivity, with the direction of the bias named.

## D359 — 2026-08-03 — honest-arm rate reverted 150 → 40: the ramp's question closed, so the ramp closed with it

**Spec section:** §7.3; D335 honest arm. `FORGE_PREFILTER_SAMPLE_N` was ramped 40 → 150 in [[D355]] for one purpose — to run the freeze clock, because at 40 the six n=1200 windows take ~10 days against ~4 at 150. **Both legs are now read and resolved `confirmed` ([[D358]]), so the clock has stopped and the ~31% ranked-production cost buys nothing.** Reverted the same day. **This is the second consecutive ramp returned in the window its question closed** (the first was [[D351]], on the generation A/B), and both times the trigger was the ⚠️ note written next to the variable rather than in a ledger — a standing obligation kept where the operator will see it at the moment it binds. **WHAT THE RAMP ACTUALLY BOUGHT, stated so the next one is priced honestly:** the reads landed 08-03 instead of ~08-09, at the cost of ~110 extra known-rejected submissions per batch for a day. **AND WHAT IT COST THAT WAS NOT ANTICIPATED:** the ramp landed at 08-02T09:00Z, essentially **at** leg 1's cohort cut (08:24Z), which made both preregs' "re-derive the a/b fit on post-change data before the read is final" caveat **unsatisfiable** — there is no post-ramp *pre-cut* data to fit on, so the post-ramp data is the judged data and fitting there is the defect [[D357]]'s registered-bar flag exists to prevent. Resolved in D358 by reading on the registered bar and publishing the tightened one (0.0074, 3.3× tighter — both legs still pass) as a disclosed sensitivity. **Transferable, and now written into the unit file:** a sampling-rate change made for a clocked prereg must land **before the cohort cut**, or the prereg's own re-derivation caveat cannot be honoured. D355 timed the switch to land at 0.3% of the post-cut rows *to keep the cohort homogeneous* — which was right for the cohort and precisely wrong for the variance fit. Deploy: preflight suite **2151 passed / 1 skipped**, unit-file change so `daemon-reload` mandatory before `start`.

## D360 — 2026-08-03 — the "MR conversion collapse" was MY POOLING ERROR; prereg `0a5ddc861aae` resolved `confirmed` and the v52 retirement STANDS

**Spec section:** D330 basis rules; prereg `0a5ddc861aae`. **Investigating why the capitulation cell stopped emitting, I measured pooled MR component conversion falling 27.19% → 11.01% across the v52 cut and called it a probable prereg falsification.** That prereg's registered action on a material conversion fall is **REVERT THE RETIREMENT**. It would have been an error. **THE READING WAS A MEASUREMENT-BASIS ARTIFACT.** Component admission comes only from the `fullhist_refit` lane; the `standard_window` 5-yr screen converts at **0.0% BY CONSTRUCTION** ([[D330]]) — `regime_coverage` requires the evaluation window to start within 30 sessions of the data floor, and a 1825d rolling window starts ~900 sessions after it. Verified as an **identity**: the gate's pass rate equals the share starting ≤30 sessions, exactly, in every version. **Conditional on reaching stage two, MR conversion is FLAT — 79.9% (v51) → 78.9% (v52) → 78.9% (v54).** Only the stage-two SHARE moved (37.1% → 14.7% → 11.5%), which is the known D330 stage-two-feed constraint, Crucible-side machinery, not a property of our supply. **Pooling a 0%-by-construction screen with a 79% refit lane makes the pooled statistic a function of lane mix** — precisely the D337/D338 collider discipline I spent the same day enforcing on the freeze legs, applied to conversion and missed. **FOUR CONTROLS, all exonerating the retirement:** (1) our MR supply quality ROSE across the boundary — cpcv_p25 median +0.298 → +0.327, WF +0.847 → +0.853, sharpe_baseline +0.846 → +0.886; (2) the retired cell converted at **0.00%** over 122 ranked configs and was ≤2.1% of MR flow, so removing it cannot move the other 98%; (3) the control hypothesis `trend_continuation` HELD (26.69% → 22.45%, above its own v48–v50 baseline of 13–17%); (4) gate mix flat within 1pp with every gate cell moving together, reject-reason mix unchanged. **PREREG RESOLVED `confirmed`:** emission leg confirmed (0 momentum-MR post-deploy; the three post-cut rows are v51-stamped and pre-restart, plus a 20,000-draw v54 probe returning 0), conversion leg confirmed once measured on the correct basis, metric-B leg **explicitly recorded as not-yet-readable** (the census's 14-day flow window still holds 312 v51-era rows until ~2026-08-14) and counted as evidence for neither side. **A SECOND CORRECTION IN THE SAME THREAD:** I had also reported the capitulation cell as an OPEN operator decision blocking freeze condition (A). It was not — [[D340]] retired it on 2026-07-31 with Crucible confirming the close-out. (A) is not blocked by a decision; it is blocked by that same 14-day window artifact, and resolves itself. The census-protection fix I proposed would have re-protected an exemption that no longer exists. **Transferable, and it is the same lesson twice:** a prereg falsifier that names a mechanism must be checked **against that mechanism** before its registered action fires — the observation leg tripped while the attribution it assumed was false, and acting on the trigger alone would have undone a correct prune on a basis error. Before reporting any rate as having moved, decompose it by `measurement_basis` first, not after.

## D361 — 2026-08-03 — solo cpcv cannot rank buckets: swing_long is in 7/7 promoted books, and the deciding export was already on our disk

**Spec section:** §1.2; [[D186]]/[[D187]] decorrelation-at-assembly. Crucible corrected our stage-one "0.0% by construction" identity — true for the 1825d buckets, **false for `swing_long`, which runs a 2555d window, starts near the data floor, and converts at 28.1% (5,726/20,402) directly at stage one**. Verified on our ledger; we had derived the identity from `mean_reversion`, which is ~96% swing_mid, and promoted a bucket-specific arithmetic fact to a structural claim — *after* Crucible had corrected us on the per-bucket 5y/7y windows two days earlier, a correction that lives in our own chain-inception code. **We then made the larger error.** Against their "cut the 1825d buckets, keep swing_long" we argued swing_long was a component factory but not a promotion source, on a **same-basis** comparison: stage-two components reaching cpcv ≥1.0 at **0.61% vs swing_mid's 5.62%** (expected ~165, observed 13), and **0 of 8,221 swing_long components ever clearing 1.5** against all 12 from swing_mid. **The measurement is correct and the conclusion is wrong.** `promoted_portfolios_2026-08-03T230326Z.json` — in `~/optbt_data/exports/`, which we had been reading all week — shows **7 of 7 promoted books carry a swing_long leg and all 8 of those legs are `trend_continuation`**; both books QuantIQ has traded are swing_long-anchored. swing_long is the **decorrelating** leg: its long window and slow cadence are why its solo cpcv is mediocre *and* why it is what the MR sleeve is measured against under §8.7, where `mean_pairwise_correlation` and the drawdown family dominate. Ranking it by solo cpcv asks it to be a good MR component, which it is not and need not be. **This is D186/D187 — decorrelation is owned at ASSEMBLY — which is already a standing rule on our side, written after a previous version of this mistake.** Crucible's `write-probe-script.md` preflight independently uses swing_long as its worked example of the same error; both principles pre-existed and both sides still needed the other to catch this instance. **BOTH bucket recommendations withdrawn, theirs and ours. No supply-composition change; staying at ~34,300/day** — supply composition is not currently an actionable lever, which is more useful than the recommendation we nearly acted on. **SECOND FINDING, procedural:** this is the second time in one day we reasoned from a derived statistic while the deciding data sat in something we already held (the first: asking Crucible to build a periodic corr-to-book export that had been publishing 116,329 rows). **Transferable, and it is the sharper form of the rule we already had:** a correct measurement of the wrong quantity is *worse* than a wrong measurement, because it looks decisive — so before a solo/supply statistic is allowed to decide anything, name the axis the decision actually runs on and check whether an artifact already answers it directly.

## D362 — 2026-08-03 — the "unsent relay queue" was a fiction; both sides now keep an index

**Spec section:** ops; `docs/tasks/crucible-handoff.md`. Forge tracked outbound relays as a running "N unsent" list and reported the count to the operator every turn. **Every relay on it had already been answered by Crucible, several the same day** — the shared `freeze` repo is how relays move, so committing *is* delivering, and our queue was a private fiction that produced an operator to-do list with nothing on it. Surfaced by Crucible shipping `relays/INDEX_crucible_answered.md` (their side: 137 files, append-only, unindexed) with a table showing all six of our "unsent" relays closed. **Reciprocated with `INDEX_forge_answered.md`** — same convention, our side only, recording which Crucible relays we have handled, the D-number or reply that closed each, and the standing obligations in **both** directions (ours: report drift from their eligible-vs-drain ratio, flag honest-arm rate changes, never tune generation against `IC(cpcv, corr_to_book)`; theirs: flag `corr_to_book` basis changes, keep publishing `designation_history`, report if the stage-two backlog stops draining). **Not every relay needs a reply** — one with no ask that we simply act on is closed by its D-entry, and the index says so explicitly to stop reply-for-its-own-sake. **Transferable:** a queue only one party can see and neither reconciles is worse than no queue — it manufactures work that does not exist and hides work that does. If two systems exchange artifacts, the ledger belongs in the shared artifact store, not in either side's head.

## D363 — 2026-08-03 — backlog close-out: two preregs resolved `insufficient` for the same defect, and v52→v54 measures FLAT everywhere

**Spec section:** D207 prereg discipline; `docs/proposals/grammar-freeze-criterion.md`. **Both resolutions are specification defects, not unfavourable results, and both are the same defect: a prediction registered against a quantity nobody had checked was measurable.** (1) **`44a4e08aef4f`** predicted a post-cut conversion rate ≤0.001 on the 30 yield-audit dead names — while the registered action, v43, **excluded those names from enumeration**. Post-cut flow is **17 submissions / 0 components**; the observed 0.000 satisfies the prediction arithmetically, but at n=17 the one-sided upper bound is ~0.16, so the read cannot distinguish 0.001 from 0.16. Resolving it `confirmed` would claim a pass from a test with no power — the D361 failure mode. The exclusion itself **STANDS** on its pre-cut basis (each name ≥500 decided / 0 conversions, ghost-cut applied, plus Crucible's independent row-45 cross-check), but pre-cut evidence is exactly what a prereg exists not to rely on. **Rule:** never preregister a post-cut rate on a population the registered action removes; predict on *surviving* flow, as `2c3d5ab6cc5a` (v47) and `0a5ddc861aae` (v52) both did. (2) **`5c4ba16ff6cf`** predicted `book_cscv_pbo ≤ 0.40 AND vol_event marginal_sharpe > 0` — **neither term is Forge-computable.** `component_contributions` is populated now (12 entries, the D216 "export is empty" hold lapsed) and **zero are `volatility_event`**; cross-checked against `promoted_portfolios`, **7 books / 20 legs / no ve leg ever**. No book-level PBO export exists on our side at all. And the window is ghost-era contaminated (the 07-19 close-out made pre-07-18 ve verdicts unrankable). **Rule:** check the reader exists before registering the claim. **THE LIVE QUESTION IS RECORDED, NOT BURIED:** ve ran **13,650 submissions → 47 components (0.34%)** over 14 days against MR 22.51% / trend 22.45%, while the D216 floor reserves ~20% of enumeration for it — **and the assembly check, which is the axis D361 says actually decides, is also negative: ve is absent from every promoted book and every contribution row.** Not acted on; the v39 exit-repair programme is still accruing and this is an operator call. **FUNNEL v52→v54** (v53 skipped — void cohort, D352): prefilter survival **34.2% → 33.8%**, submitted/enumerated **6.9% → 6.6%**, rejection mix within 1pp; basis-split downstream, stage-two conversion **83.9% → 83.5%** and stage-one **7.1% → 6.6%**. **Chain-inception is neutral on every measurable axis** — which is the honest result for a change deployed to fix a filter that had never been live. Stage-two *share* fell 12.0% → 10.3%, which is Crucible capacity (D360), not grammar. The ≥1.5 tail reads 2-of-2,851 (v52) against 0-of-4,464 (v54); at v52's rate ~3.1 were expected, so this is the underpowered rare-event regime D341 warned about — **a watch, not a finding.**

## D364 — 2026-08-04 — Q46 CLOSED by Crucible: the double-gate is MORE correlated, and we reproduced it before accepting

**Spec section:** D317 (v44) / D319 (v45), the Q46 `vix_term_slope`-as-conditioner pilot. Crucible closed Q46 on two grounds. **(a) The pinned metric was structurally unmeasurable** — reaching ONE expected honest-pool entry needed ~1,768 double-gate components at 1.1/day = **1,506 days**, and an expectation of 1 is an anecdote; a real marginal-contribution read needs 10–30 entries. The zero-in-pool observation they nearly reported as negative is uninformative: `P(zero | base rate) = 0.96`. **Their stated lesson is one we should adopt symmetrically: a load-bearing read must state its required n AT REGISTRATION, not discover it at resolution** — which is precisely how `44a4e08aef4f` and `5c4ba16ff6cf` failed in D363, independently, the same day. **(b) The hypothesis is refuted on its own axis.** The double-gate was proposed as a *decorrelation* mechanism, which needs no pool entry because `corr_to_book` is stamped on every run. **VERIFIED INDEPENDENTLY ON OUR LEDGER before accepting:** median `|corr to frozen_b36f49a4|` for hurst×vix configs **0.3682 (n=1,172)** against **0.3520 (n=109,384)** for all other v45+ — **+0.0161, MORE correlated**, same sign and conclusion as their +0.0219 at n=1,335 vs 118,189 (the gap is window/coverage). Supporting on their side: component cpcv median 0.2715 vs 0.4177. Emission verified correct — `hurst×vix` present, **`adx×vix` absent**, so our v44→v45 refinement held exactly as specified. **CONSEQUENCE:** ~20 configs/day of enumeration share to reclaim by retiring the conditioner, and the vix-term-slope half of the July `resid_vix` both-axes ask is retired with it (the hurst arm is untouched and not implicated). **STAGED, NOT DEPLOYED** — retiring a drawn optional gate shifts the enumeration sequence, so this is a grammar-version bump with goldens re-pin, prereg-before-edit, emission proof and the full D104 ritual. Operator-gated. **Caveat carried from their §3:** the correlation is to ONE reference, the retired champion pinned for coverage; a mechanism could in principle decorrelate against a different book, and the measurement is cheap to repeat against `f52a05c8` once coverage catches up. At +0.0161 against 109k controls we treat that as a thin hope, not a live hypothesis.

## D365 — 2026-08-03 — the v50 retarget is VINDICATED, eleven days after it shipped: cpcv-targeting orders realised CPCV 5.3× better than its own detection floor

**Spec section:** prereg `7f675a79ca57`; `docs/tasks/feedback-change.md`. **The action shipped before the prediction was ever tested.** The production quality lane was re-targeted to `target_cpcv_p25` at v50 on 2026-07-24 — **one day after this prereg's cohort cut** — and the prereg was then left open for eleven days. **This is the second instance found today of the same pattern** (the first: the v52 capitulation retirement, D360): an action landing makes the question feel settled, so nobody returns to the prediction. **NOW MEASURED, and it holds decisively.** New instrument `scripts/tail_target_rank_ic.py`, on the trainer's own temporal holdout: OOS rank IC against **realised** `target_cpcv_p25` reads **+0.3773** for the cpcv-targeted ridge against **+0.2472** for the wf-targeted one — delta **+0.1300** at n_test=12,910, against an MDE of 0.0246, so it clears its own detection floor by **5.3×** and is **4.4× larger than the +0.0294 measured at registration** (which had n_test=5,283 of a common n=26,416; this read has a common n=64,551). **PREREG DISCIPLINE VERIFIED RATHER THAN ASSUMED:** the test split spans 2026-08-01T11:20 → 2026-08-03T23:13 and **12,910 of 12,910 rows post-date the 07-23T07:50 cut**, so the read is post-cut-only; the fit is on the older train split (06-19 → 08-01), which is the correct direction. **TWO DESIGN CHOICES THAT MAKE IT A FAIR TEST, both load-bearing:** (1) **two models, ONE yardstick** — both ridges are scored against the same realised `target_cpcv_p25` on the same test rows, because the wf model is not being asked to predict wf but to predict CPCV, which is the question the lane actually needs answered; scoring each against its own target would compare two different quantities and could not rank them. (2) **common population** — restricted to rows carrying BOTH targets (64,551 of 67,554 cpcv / 72,917 wf), so the models see identical train and test sets; without it the comparison reads differing coverage footprints as predictive skill. Rank IC rather than R² because the lane **ranks** and never consumes the predicted level. **WHAT IT DOES NOT ESTABLISH, and the limit is the day's recurring one:** ordering realised CPCV better is not evidence of more promotions. CPCV is a gate; promotion is an **assembly** property ([[D361]]), and no rank-IC result bridges that. The lane's value on the axis that matters remains unmeasured. **Minor finding logged, not chased:** `build_dataset` emits `reader behind contract: pruned unknown field(s) ['prefilter_sample'] while re-reading StrategyConfig`. The frame builds correctly (64,551 rows, 114 features) so it is not blocking, but a field-set disagreement between our process and our own stored payloads is worth a look before it becomes load-bearing. **Also registered this pass:** prereg **`6e81bfaa3907`**, the `adx` regime-gate replication — and it is the first in this programme written to the D363/D364 rule, **stating its required n at registration**: MDE = 2.8/√n, |ρ|=0.10 needs n=784, measured accrual 922 qualifying rows/day, single read at n≥1,500 (~1.6 days), **with the collider check re-run as part of the read** rather than inherited, and explicitly authorising *nothing* — a replicated association is not a licence to steer.

## D366 — 2026-08-03 — v54 → **v55**: the Q46 `vix_term_slope` conditioner is retired (share zeroed, not deleted) — and the hot-grammar-read hazard fired a SECOND time

**Spec section:** §3.5 S3 (rules text unchanged — emission-policy); D317 (v44) / D319 (v45); prereg `c14fa12cd4da`. **THE EVIDENCE, from both sides.** Crucible closed Q46 on 2026-08-03: the hurst×vix double-gate was proposed as a **decorrelation** mechanism and measures **more** correlated to the champion book — median `|corr|` **0.3782 vs 0.3564** at n=1,335 against 118,189 controls. **We reproduced it on our own ledger before accepting: 0.3682 (n=1,172) vs 0.3520 (n=109,384), +0.0161, same sign.** Their pinned pool-entry metric was separately shown structurally unmeasurable (~1,768 components for ONE expected entry = **1,506 days**), so decorrelation was the only axis that could ever have decided it, and it decided against. **THE CHANGE IS ONE CONSTANT: `_VIX_CONDITIONER_SHARE` 0.125 → 0.0**, and zeroing rather than deleting is load-bearing twice over. *Determinism:* the draw site reads `_vix_conditioner_eligible(...) and rng.random() < SHARE` and Python short-circuits, so keeping the predicate keeps the `rng.random()` call exactly where it was; deleting the predicate would remove that consumption and churn the sequence far more. *Reversibility:* their reading is correlation to **one** reference (the retired champion, pinned for coverage) — they wrote that the door is not nailed shut and the measurement is cheap to repeat against `f52a05c8`. A constant is a one-line revert; a deleted path is not. **The reclaimed ~20 configs/day are REDISTRIBUTED, not subtracted:** with `added_second_gate` now always False on that arm, the regime-**veto** branch becomes reachable for configs that previously took the conditioner. **NO GOLDENS RE-PIN WAS NEEDED, and that was verified rather than assumed:** all 210 sampler goldens pass untouched because their `minimal_registry_snapshot()` fixture never served `vix_term_slope` as a trend gate, so the predicate short-circuits and the cold path stays byte-identical (hard rule #6) — exactly what the v44 design comment predicted. **EMISSION PROOF on the LIVE registry, 3 seeds × 8,000 configs:** 0 `sig_vix_conditioner` signals, 0 hurst×vix double-gates, **1,231 vix-as-PRIMARY draws still emitted** — the retirement is scoped to the conditioner, not the indicator, and that scope guard is a test. **TESTS INVERTED, NOT DELETED** (v52 precedent — a deleted test cannot catch silent re-admission): three v44 emission assertions now assert unreachability, and the share-rate test's *eligibility denominator* assertion becomes the load-bearing half, proving the zero is a real non-firing rate rather than an empty denominator quietly passing (the Q57 lesson that fixed that same test once before). **A TEST OF MINE WAS WRONG AND THE SUITE CAUGHT IT:** the first emission guard keyed on the *indicator* id, which banned `vix_term_slope` outright and contradicted my own scope guard; re-keyed onto the conditioner's **signal id** (`sig_vix_conditioner`), which is the only thing v55 removes. **⚠️ THE HOT-GRAMMAR-READ HAZARD FIRED A SECOND TIME.** CLAUDE.md forbids editing `config/grammar.yaml` in the live tree while the service runs; I did, and the daemon re-read it hot — **6 journal iterations stamped `grammar_version=v55` while the running process still held the v54 sampler.** Any batch shipping in that window would have been stamped v55 but enumerated under v54 semantics: corrupt provenance no later analysis could untangle, the [[D340]] incident exactly. **ZERO CONTAMINATION — 0 v55-stamped rows all-time** — because §7.3 backpressure held the stream at 72.9% gated (175/240, needing ≥80%) throughout. **That is luck, not design, and it is the same luck that saved D340.** The durable fix is unchanged and was not followed: for `grammar.yaml` the tree **is** the live config, so the edit must land on a branch or the stop must come first. **Deploy:** preflight suite **2,155 passed / 1 skipped** (the `test_v1_grammar` version pin is a deliberate tripwire and was updated with rationale), stop → commit → restart. **NOT a promotion unlock** — an enumeration-policy retirement of a refuted cell worth ~20 configs/day; the standing finding that supply composition is not an actionable lever on the promotion axis ([[D361]]) is unchanged.

## D367 — 2026-08-03 — the D216 ve orthogonal-family floor is RETIRED: its founding evidence was retracted and the repair it waited for did not work

**Spec section:** D216 Layer-2 orthogonal-family supply; prereg `d4b1efd26bb3`. **THE FLOOR'S FOUNDING EVIDENCE WAS WITHDRAWN.** D216 installed `FORGE_ORTHOGONAL_FAMILY_FLOOR=volatility_event=0.20` because Crucible validated single-name ve on 2026-06-29 as **the second factor** — PC1 load 0.10, a mixed book clearing real CSCV PBO 0.107. Their **07-19 ve close-out retracted exactly that**: 23 of 25 stored-cpcv ve components were re-derived as **ghosts** (put_wall/gex/vex/cex staleness, fixed their v3→v4), and clean-cache mixed-book PBO came back **0.40** — "real-but-MARGINAL, no solo promotion case." **THE REPAIR IT WAS HELD OPEN FOR DID NOT WORK, and that is the new fact.** ve conversion by grammar version runs 2–10% at median cpcv **+0.20…+0.33** through v21 — *the ghost era, i.e. the retracted evidence itself* — then collapses from v22 onward to 0–1% at median **−0.23…−0.53** and stays there straight through the v39 exit repair: **v39 0.40% / −0.439, v54 0.10% / −0.413**, indistinguishable from pre-repair v38 (0.64% / −0.396). **THE ASSEMBLY AXIS WAS CHECKED, NOT ASSUMED**, because [[D361]] establishes that a solo statistic cannot condemn a family — value can be assembly-side and invisible, which is precisely the error we made on `swing_long` the same week (bad solo cpcv, 0.61% vs 5.62% at ≥1.0, while sitting in **7 of 7** promoted books). For ve that check is empty: **0 ve legs across 7 books and 20 component legs, 0 ve rows among the 12 `component_contributions`.** swing_long is bad-solo/7-of-7; ve is bad-solo/**0**-of-7, and that contrast is the entire argument. **UN-PROPPING, NOT PRUNING.** The floor is a max-**normalized** weight, not a target share, delivering ~10–12% (v54 12.1%, v55 9.9%). Removing it returns ve to its learned weight plus the D067 **5% exploration floor** — the family stays samplable, and the per-cell question stays open on purpose, because each ve cell carries only **3–24** honest-coverage verdicts, the census's `_UNEVALUATED` state we refuse to prune on. Reversible by re-adding one env line. **THE FALSIFIER TESTS D216'S ACTUAL CONCERN.** Conversion would be the wrong falsifier — reallocating share from a 0.34% family to 22.5% families *must* raise aggregate conversion, so predicting it would be predicting arithmetic. D216's real argument was **homogeneity**: the learned component-rate estimand rewards "more of what already clears," which PBO penalizes. That is now directly measurable with the freeze **leg-2** instrument, so the prereg predicts the standardised **TCM-corr** does not rise more than **0.0173 above its pre-cut max of 0.4457** — reusing the bar registered and read for `13e4d2cece3f` rather than refitting one, because refitting a bar on the data it judges is the [[D357]] defect. Required n stated at registration per [[D363]]/[[D364]]: 3 new n=1200 windows ≈ 0.6 days of accrual plus ~1 export of corr lag, so ~2 days. **COUPLED DECISION RECORDED: `young_explore` (D316 2d) stays OFF.** Measured while deciding this: of 42 young cells, **22 are ve and 87% of young-cell flow is ve** — they stay young because ve's P(cpcv|submitted) is ~21% against trend's ~73%. Flipping the explore lane would have spent ~576 configs/day funding targeted exploration of the family we just declined to over-supply. The two levers point opposite ways and doing both would have been incoherent; the alternative (keep the floor AND flip the lane, under a dated prereg) was the coherent pro-ve option and was not chosen. **NOT A PROMOTION CLAIM** — a cost decision reclaiming ~5–7% of enumeration share; D361's finding that supply composition is not an actionable lever on the promotion axis is unchanged.

## D368 — 2026-08-06 — the ceiling is NOT reached, and the binding constraint is refit TRIAGE, not generation

**Spec section:** `docs/proposals/grammar-freeze-declaration.md` §4/§8. Operator asked whether "the ceiling is flat" means "we hit the ceiling." **They are different claims and only the first is what (C) tests.** Two new instruments answer the second. **(1) RECORD PROGRESSION** (`scripts/ceiling_record_test.py`) — distribution-free: in n i.i.d. draws, running-maximum records arrive at rate 1/n, so the expected count is `H_n ≈ ln(n)+γ` whatever the shape. Ranked lane: **13 records vs 12.58 expected, z=+0.13** — exactly the unbounded-search rate — with the trail still climbing through the promotion gate (1.4738 → 1.5325 → 1.5501 → 1.6006 → **+1.7397 on 08-03**). This cannot be explained by our ranker improving: **better selection reaches a ceiling faster, it cannot exceed one.** (C) reads the top-*decile* mean at rank ~120-from-top; records live at rank 1 — so the observed state is exactly the blind spot (C) names in its own text: **the bulk tail stopped moving, the extreme tail did not.** **(2) THE JOINT FRONTIER** (`scripts/joint_frontier.py`) — every ceiling instrument we own reads cpcv alone, but promotion needs cpcv **and** `walk_forward_sharpe_median`; stage-one pass rates are cpcv 0.00%, WF-median 0.49%, while `wf_sharpe_p25`/`p10` admit 100% (three WF-family gates, easily conflated — the v50 retarget rationale correctly described the *non-binding* one). The null is a **permutation of arrival order over the fixed point set**, which preserves the cpcv/WF dependence; the closed-form `(ln n)²/2` assumes independence and would have manufactured a saturation finding. Result: ranked lane **73 advances vs 37.0 null, z=+3.60, p=0.003 — STILL ADVANCING**; honest arm stationary (z=−0.50), consistent with leg 1 flat. **(3) THE ACTUAL FINDING, one step past the frontier.** On the window where `measurement_basis` is 100% populated: **23 stage-one configs cleared BOTH binding gates, all 23 with an IDENTICAL verdict and failure set** (`reject`, failing `deflated_sharpe` + `regime_coverage`). **9 were refit → 9 became components. 14 were never refit.** Refit latency is **median 0h, p99 2h, max 3h** over 36,061 pairs and 13 of the 14 sit 1–5 days past their stage-one decision, so they were **passed over, not queued** — the difference is which rows the newest-first scanner reached. **61% of our best-ever supply never entered the only lane that can produce a component.** NOT claimed: that those 14 are better (9/9 is consistent with the lane's ~80% base rate, p=0.13); claimed only that they were identically eligible. **A CORRECTION TO OUR OWN FIRST PASS, caught before relaying:** we first counted 24-of-33, which was unverifiable — `measurement_basis` is **0% populated before the week of 07-20**, so a refit of any older config carries NULL basis and is invisible to us as stage two. Same class as the D360 pooled-conversion artifact: a field that means one thing going forward and another historically. **CONSEQUENCE FOR THE PROGRAMME:** probing untested grammar surface (the `rv_rank` second-gate blind zone, the 19 dark indicators) is **DEPRIORITISED** — adding surface while losing 61% of what already clears both binding gates is solving the wrong problem. The highest-value next item is Crucible-side and already relayed (2026-08-06): is newest-first refit ordering deliberate under the doubled capacity, given stage one has already computed cpcv and WF before the scanner chooses? **This strengthens the freeze rather than complicating it** — it is further evidence the binding constraint is not generation.

## D369 — 2026-08-06 — no lane is saturating; the remaining ceiling is in `swing_mid`, which is the capacity-bound one

**Spec section:** `docs/proposals/ceiling-saturation-experiment.md` (design, HELD); declaration §4. **Per-lane joint frontier** (ranked, stage one, per-lane permutation null): `swing_mid` n=139,730, **68 advances vs 35.8 null, z=+3.71** — the only lane still advancing, the only one ever to clear both binding gates (max cpcv **1.601** at WF≥2.0), and holder of every record. `swing_long` z=−0.19, `swing_short` z=−0.05. **AN ERROR MADE AND CORRECTED THE SAME DAY:** those two z-scores were first described as the lanes being "already exhausted." **Wrong — and it is the exact confusion `joint_frontier.py`'s own docstring warns about** ("stationary is not ceiling-reached"), committed one turn after writing that caution. The saturation metric is **advances per DOUBLING of cumulative search**, which is constant under a fixed distribution and declines only when a bound is approached: `swing_mid` reads `2 3 2 2 2 2 3 3 6 4 4 3 5 6 5 7 10` — **rising**, most in the last full doubling — and `swing_long` reads `1 2 2 3 1 3 2 0 2 3 3 3 4 1 5` — **flat at 2–3**. **Neither shows the declining signature; no lane is saturating.** What is true of `swing_long` is different and still useful: its frontier sits **below the promotion gate** (max cpcv 1.084 among WF≥2.0 rows; never reached 1.5) — a low ceiling, not a reached one. **THE STRUCTURAL ASYMMETRY THAT MAKES THIS AWKWARD:** `swing_long` converts at **stage one** (29.1% — its 2555d window passes `regime_coverage`, so it needs no refit and is immune to Crucible's queue), while `swing_mid`/`swing_short` convert **0.0%** at stage one and depend wholly on refit. Our mix is **80.7% swing_mid / 12.6% swing_long**. **So the ceiling cannot be bought by shifting supply toward the unthrottled lane — that lane's ceiling is beneath the gate — and the only lane with headroom is the one throttled by someone else's capacity.** **EXPERIMENT DESIGNED AND HELD.** Metric: advances per doubling; falsifier requires **two consecutive** declining doublings, because advance counts are small integers (sd on ~7 is ~2.6) and a single low doubling is noise. Required n stated in advance per [[D363]]/[[D364]]: one doubling of `swing_mid` = **+139,730 ranked stage-one rows ≈ 33 days**, and mix concentration buys only ~1.24× because swing_mid is already 80.7% of supply — the full falsifier is a ~3-month commitment. **HELD, not registered**, because 61% of swing_mid's gate-clearing output never reaches stage two ([[D368]]): a ceiling measured while a recency-ordered queue discards most qualifying output is a property of the queue, and if ordering becomes quality-aware mid-experiment the series is uninterpretable — the same defect that voided the first (C). Unblocks on Crucible's refit-ordering answer **either way**; what cannot be tolerated is running it across an unannounced change.

## D370 — 2026-08-06 — our "zero promotes" is a MEASUREMENT SHADOW: 31 configs destroyed at Crucible's verdict stamp since 07-23

**Spec section:** relay `7611258` → Crucible's reply, same day. **Our 23/9/14 reproduced EXACTLY on their ledger** (`promotion_decisions` + `runs`, not our mirror): 23 dual-gate clearers, all with the identical `reject` / `[deflated_sharpe, regime_coverage]` profile, 9 refit → 9 components. Latency reproduced too (their n=36,399 vs our 36,061 — snapshot drift). They also confirmed our §3 self-correction was right on their data: one additional dual-gate clearer sits just outside our trustworthy window, so discarding the pre-07-27 count was correct. **THE CORRECTION: our "14 never refit" is really 12 + 2.** Two were refit *fast* — children queued 3 minutes and 38 seconds after the stage-one decision — ran their full-history backtests, and **crashed at the verdict stamp**. A failed run gets no `promotion_decisions` row and never reaches any verdict-based export, so they were structurally invisible to us. 61% decomposes as **52% passed over + 9% destroyed at the finish line**. **THE FINDING THEIR VALIDATION UNCOVERED, and it is much larger than our relay:** §20 of 2026-07-22 made `deflated_sharpe` recorded-but-non-binding at the single-run verdict layer, but the `PromotionDecision` contract validator still enforced the pre-07-22 rule that a promote must carry **zero** failed gates — and §20 deliberately keeps the exempt DSR **recorded as failed**. So the first stage-two child good enough to promote after 07-22 crashed the stamp, and **every one since: 31 configs, 67 children, 12 now permanently blacklisted (`refit_attempts_exhausted`), 9 first crashing on 08-05/08-06 — accelerating with v55 quality.** **VERIFIED ON OUR SIDE:** we hold exactly **4 promote verdicts ever** (07-01, 07-02, 07-03, 07-18 — all pre-§20) and **ZERO since 2026-07-23**. Our last promote predates §20 by four days. **Every "0 promotes" reading in our records since 07-23 measures a crashing validator, not supply quality.** **WHAT THIS INVALIDATES AND WHAT IT DOES NOT:** freeze condition (C) is **unaffected** — both legs read stage-one cpcv distributions on the honest arm, and the crash is at the stage-two stamp. The record and joint-frontier tests are **unaffected** for the same reason. What *is* shadowed is any claim resting on recent promote counts, including part of the [[D361]]-adjacent dsj reading ("6,707 dsj components, zero reached a promoted book") — the dsj window opens ~07-08 so it is only partly affected, but the zero is no longer clean evidence. **IT STRENGTHENS THE FREEZE PREMISE RATHER THAN WEAKENING IT**, and Crucible said so explicitly: the binding constraint sits even further downstream of generation than D368 measured — our best supply is lost at refit triage **and** at the stamp. **ORDERING ANSWER: `ORDER BY pd.decided_at DESC` is an ARTIFACT, not a policy** — no design rationale exists anywhere in their scanner, and the limitation was noticed and hand-bypassed the day the lane shipped. The policy call goes to their operator with our relay as the trigger. Their measured payload for our intuition: among *reached* dual-gate clearers, **2 of 11 produced promote-grade children against a ~0.06% lane base rate (31 of 48,323) — ~280× enrichment.** Their stated cost is methodological and correct: quality-ordering conditions the stage-two cohort on stage-one metrics, so the version-delta yardstick — **the instrument that produced our v55 read** — acquires a dated policy boundary; a two-lane split (reserved quality sub-budget, remainder newest-first) would preserve a like-conditioned majority cohort. **ACTION: none from us.** Fix, requeue of all 31, and the ordering decision are theirs; the contracts bump reaches us through the normal channel and lands **before** any promote row can reach our readers. **WATCH:** the requeue will inject up to 31 promote verdicts as a burst — a basis boundary of exactly the class we split on elsewhere. Record the timestamp when it lands and split any series that spans it.

## D371 — 2026-08-06 — repo-simplification Steps 0–C EXECUTED (operator: "let's attack the plan"): 11 commits of record/doc/scripts hygiene, zero daemon/config/behavior change

**Spec:** `docs/proposals/repo-simplification-2026-08.md` (the plan; D368-adjacent audit basis).
**What landed, by tranche (commits e56cff1 → 88c7df0):**
- **Step 0** — strays: the stranded QuantIQ training-signals relay filed to `freeze/relays/` +
  tracked as **Q62** (unhandled inbound, six streams, triage = ranker design work, still owed);
  4 answered ACF relays committed with corrected banners (`joint_frontier.py` was committed by
  the concurrent D368 session).
- **A1/A2** — 20 answered/dead-channel relays + `RELAYS.md` → `_archive/` (D202/D241 criterion;
  corr-to-book verified answered in both INDEX ledgers); `docs/tasks/crucible-handoff.md`
  rewritten to the D362 `freeze/relays/` channel — the doc that was regenerating root clutter.
  Root `.md`: 34 → 9 (only `PATHC_DEBIT_VERTICAL_SIZING` stays, operator-parked D152).
- **A3** — ledger rotations (D242/D295 precedents): STATUS 2026-07 blocks (180) →
  `_archive/STATUS_2026-07.md`; **D201–D300 (99 entries — D236 was never written, D-number
  race, noted in the slice header)** → `_archive/IMPLEMENTATION_DECISIONS_D201-D300.md`;
  31 resolved Qs → `_archive/OPEN_QUESTIONS_RESOLVED.md` (Q46 heading got its missing
  RESOLVED marker, D364/D366, before rotating). Session read-path 1.42 MB → ~450 KB.
- **A4/A6/A7** — `AUDIT.md`, `SECTOR_VOL_MECHANISM_RESEARCH.md`, `ALPHA_BUDGET_SCOPE.md`
  (2 refs repointed), `STRATEGY_GENERATION_STATE.md` archived; **19 terminal proposals →
  `_archive/PROPOSAL_*.md`** — 4 carried stale-in-reality STAGED headers corrected at archive
  time (v43 rider SHIPPED D309; v50 IWM/SLB + rank_k SHIPPED D336, rank_k REVERTED D337;
  corr-to-book EXECUTED); `docs/proposals/` 39 → 20 (12 code-cited + open/active). Root-file
  taxonomy restored in `architecture.md`; `docs/proposals/` routing rows added to
  CLAUDE.md/README.
- **B** — truth repair: DESIGN.md as-built reconciliation (D201 pattern; fictional §11 tree,
  §9.1 DDL, §10 config pastes removed in favor of owners; **§9.2 corrected — file exports,
  never Crucible's DB**; §4.2 CSP/networkx fiction corrected; §3.6 "25 rules" → 21) + the
  **§3.5 DRIFT BANNER (commit 9afe042, flagged for operator review** — rule text untouched
  per hard rule #1; discloses the six drifted bodies with verified lineages, GRAMMAR.md wins
  on conflict). GRAMMAR.md monster paragraphs → per-gate bullets (sync hook green).
  MANPAGE env-knob essays compressed + 3 stale facts fixed (D287 pin EMPTY per D305; arm-B
  REFUTED D351; ve floor RETIRED D367). INDICATOR_THRESHOLDS shed its shipped-plan +
  struck-through sections. glossary.md merged into `architecture.md` §Terms; the two
  unreadable module-map cells split into breakdowns. quality-gates.md stopped teaching the
  pre-D351 broken hook; NEW_BOX_TRANSFER de-pinned from v22; empty docs/DECISIONS.md deleted.
  Two doc-needle tests updated (Q10 archive-aware; §6.2 symbolic formula).
- **C** — 22 one-off research scripts retired with MANPAGE ledger rows + a full scripts
  inventory + the standing rule (*one-off scripts die with their D-entry*); the 137-line
  version-changelog comment deleted from `test_v1_grammar.py`; mypy strict-implied flags
  dropped; pytest floor 8 → 9; orphan `.pyc` purged.
**Verification:** doc-needle + hook-script + grammar-sync + cli-help suites green (40/40);
`tests/unit/test_scripts` + `tests/integration` green except
`test_expected_contract_version_matches_installed` — **pre-existing**: contracts **1.43.0**
shipped in the sibling repo mid-session; the 1.42.0 pin adoption is its own operator-gated
tranche (D244/D245 restart sequencing), deliberately NOT smuggled in here (`uv.lock` kept at
1.42.0; commits made under `UV_FROZEN=1`).
**NOT done (by design):** Steps D (unit-file comment move), E (src dead code — `winner_prior.py`
et al.), F (post-freeze retirement per `fable-audit/code-complete-retirement/REPORT.md`) —
operator-gated. Q62 triage owed. Regrowth rule #3 (STATUS blocks ≤ ~10 lines, narrative in the
D-entry) is a PROPOSAL awaiting the operator; this entry ironically demonstrates the need.

**↳ 2026-08-06 (later) — D236 BACKFILLED (operator: "write the D that's free").** The
rotation's "never written" conclusion was WRONG: D236 was written on the `v23-trend-grammar`
branch (`ade3344`/`7813595`), reserved by D237's own note, and silently lost when the branch's
second ledger-conflict re-merge (`2f2748f`) resolved to main's side — a merge-conflict loss,
not a numbering race. Restored VERBATIM (entry + its 07-06 addendum) into
`_archive/IMPLEMENTATION_DECISIONS_D201-D300.md` in chronological position with a provenance
blockquote; the slice header now reads 100 entries. Lesson for the D-number-race family: a
ledger conflict resolved "theirs" can silently drop an entry — after any ledger-conflict
merge, grep the merged file for the entry you just inserted.

## D372 — 2026-08-06 — E1: `winner_prior.py` DELETED (the v50 winner-neighborhood prototype) — repo-simplification Step E, operator "Let's do 1-4"

**Spec section:** none (never reached the spec). Classification: dead-code removal; no behavior
change (nothing imported it — its gating flag `FORGE_WINNER_PRIOR` was never created).
**Evidence of death:** single-commit history (`e298f67`, "PROTOTYPE — offline only"); prereg
`916d79109b4d` resolved **refuted** ("WITHDRAWN-AS-MISCALIBRATED, not tested");
`docs/proposals/v50-winner-neighborhood-priors.md` records the programme PARKED; its three
driver scripts were already retired in Step C. **Removed:** `src/forge/ranking/winner_prior.py`
(352 LOC) + `tests/unit/test_ranking/test_winner_prior.py`. The proposal doc stays (code-cited
design record) and notes the instruments' retirement. Revert = `git revert`; re-parking the
programme later starts from the proposal, not from dead code in the tree.
**Verification:** `tests/unit/test_ranking` green post-delete; `forge.cli.main` imports clean.
Restart NOT required (dead code); rides the pending contracts restart window.

## D373 — 2026-08-06 — E2: the alpha-budget feature RETIRED (`forge alpha-budget` + module + script) — its question is answered and cannot re-open

**Spec section:** Tier-1a honesty ledger (D207). Classification: dead-feature removal, no
behavior change (read-only telemetry the production loop never read).
**Why it is spent, precisely:** (1) its prereg `098ea730d5f2` resolved **confirmed** 2026-07-21;
(2) the long-options exhaustion monitor it existed to close is CLOSED — the Path-C dossier §0
re-priced on its output 07-08 and accumulation cannot reopen the monitor; (3) charged DSR fired
once (07-03) and was made not-standing by Crucible's `dffbb83` answers; (4) the STANDING half of
search-multiplicity honesty is `submission/search_multiplicity.py` (D310, self-gated stamping) —
separate code, untouched. The operator named alpha-budget as the archetype of the debt class.
**Removed:** `feedback/alpha_budget.py` (162), `cli/alpha_budget_cmd.py` (105) + the two
`main.py` wiring lines, `scripts/alpha_budget.py` (743), both test files (157). **Kept:** the
preregistration machinery (shares nothing but a docstring, repointed); `_archive/ALPHA_BUDGET_SCOPE.md`
(the spec + §7 results record); `config/preregistrations.jsonl` untouched.
**Docs same-commit:** MANPAGE command section removed + retirement-ledger row; architecture cli
row + honesty-ledgers bullet updated.
**Verification:** `test_cli` + `test_feedback` + `test_cli_help` (the every-command-in-MANPAGE
contract) — 419 green. Restart not required; rides the pending contracts restart window.

## D374 — 2026-08-06 — contracts 1.42.0 → **1.44.0** adopted (pin-only): the promote-stamp fix and the lane tag we asked for

**Spec section:** §13.5 contracts pin; [[D370]]. Crucible shipped the D370 chain in the order they proposed, and the last gate was ours — our reader had to restart on ≥1.44.0 before any promote row could reach it. **1.43.0 (`284558a`) — THE STAMP FIX.** `PromotionDecision` now accepts `promote` iff the failed gates lie within the §20 recorded-not-binding set (`{'deflated_sharpe'}`); any **other** failed gate still raises, and the error now names the offenders. Verified additive-for-us by reading the diff rather than trusting the note: it is a **relaxation of a validator we only READ**, so strictly more rows parse and nothing we emit changes. This ends the D370 shadow — the pre-07-22 zero-failed-gates rule destroyed **67 stage-two would-be promotes** between 07-23 and 08-06, which is exactly why our ledger showed 4 promotes ever and **zero since 07-23**. **1.44.0 (`bcb8290`) — THE LANE TAG.** `RunResult.refit_selection: str | None = None`: `None` marks the unconditioned newest-first drain (the like-conditioned cohort marker), `'quality_margin'` the new quality sub-budget. This is our D370 §5 ask answered as a first-class field, and **they made it a FREE STRING rather than a Literal, citing the 1.24.0 vocabulary-growth lesson** — which is precisely the [[D261]]/[[D342]] hazard: `parse_forward_compatible` does **not** cover enum values, so a new Literal member would have hard-failed our registry reader on arrival. Optional with a `None` default, so pre-1.44 rows still validate. **THE TWO-LANE SPLIT IS LIVE ON THEIR SIDE:** quality sub-budget of `limit // 5` (8 of 40) ranked by margin over **both** promotion bars with a −0.3 floor set from the measured crashed-parent range; the remainder stays newest-first and **unstamped**, so the absence of the tag is the like-conditioned cohort marker — which preserves the version-delta yardstick that produced our v55 read, the methodological cost they correctly raised and we would have missed. **THE LANE ALREADY PROVED THE FINDING:** their 17:10 timer tick beat the hold drop-in by 43 seconds and ran one quality pass under the old runner code. Its 8 picks were **precisely the passed-over elite dual-clearers** our D368 relay identified; **7 gated as honest components immediately** and 1 computed promote and crashed at the old stamp — a **12.5% elite promote rate**, consistent with their 2-of-11 estimate and ~280× the 0.06% lane base rate. Damage bounded to one burned attempt, recovered by the requeue driver. **Deploy:** preflight **2,155 passed / 1 skipped**, stop → commit → restart, then ack by relay (they are monitoring the relay directory). **WATCH, carried from D370:** the requeue of the crash cohort will arrive as a **burst of promote verdicts** — a basis boundary of the same class as the tail-OFF unit change and the designation flip. Their requeue driver prints the exact queue-time bounds and they will relay them; record that timestamp and split any version-delta or learned-weight series that spans it.

## D375 — 2026-08-06 — persist `refit_selection`: the lane tag we asked for was arriving and our writer was dropping it

**Spec section:** §13.4 persistence; [[D370]] §5; contracts 1.44.0. **We asked Crucible for a refit-lane tag, they built it as a first-class contracts field, it arrives on every exported row — and our writer discarded it.** Verified before fixing: `refit_selection` appeared nowhere in `src/forge` outside a comment, and `verdicts` had no column for it, so `RunResult.refit_selection` parsed cleanly (optional, `None` default) and was silently dropped at the INSERT. Nothing broke, which is exactly why it would have gone unnoticed — we would simply have found ourselves unable to filter, and fallen back to reconstructing the split from timestamps, **which is the thing the tag exists to replace.** **WHY IT MATTERS AND IS NOT COSMETIC:** from 2026-08-06 17:10 PDT Crucible's stage-two scanner reserves a quality sub-budget (`limit // 5`, ranked by margin over **both** promotion bars) alongside the newest-first drain. A quality-ordered cohort is **conditioned on stage-one metrics**, so pooling it with the drain would silently break the like-conditioned version-delta yardstick — the instrument that produced our v55 read. **The absence of the tag is the cohort marker**, which only works if absence is recorded rather than indistinguishable from "we never stored it." **Wire vocabulary:** `NULL` = unconditioned newest-first drain, `'quality_margin'` = the reserved sub-lane, `'promote_stamp_recovery'` = the 31-config requeue of the D370 stamp-crash cohort. Crucible made it a **free string, not a Literal**, citing the 1.24.0 vocabulary-growth lesson — the [[D261]]/[[D342]] hazard exactly, since `parse_forward_compatible` does not cover enum values and a new Literal member would have hard-failed our registry reader on arrival. **CHANGE:** one idempotent `ALTER TABLE verdicts ADD COLUMN IF NOT EXISTS refit_selection VARCHAR` following the `measurement_basis`/`fullhist_refit_of` precedent, plus the writer field and a widened row-tuple type. **TDD:** the test asserts all three vocabulary values round-trip AND that the untagged row stays `NULL` — the last assertion is the load-bearing one, since a writer that defaulted absence to a string would destroy the cohort marker. The exact-column-set guard in `test_verdicts_table_created_by_ensure_schema` was updated deliberately rather than loosened. **Migration verified against a copy of the live 617,782-row table**: column added, all legacy rows preserved and `NULL`. **Suite 2,122 passed / 1 skipped; mypy --strict clean.** **Backfill is NOT possible and that is fine** — the tag exists only from the 1.44.0 export onward, so every pre-2026-08-07 row is legitimately `NULL`, which is also the correct value for them (they all came from the newest-first drain, the only lane that existed).

## D376 — 2026-08-06 — E3: the D287 experiment-cell hand-pin reservation REMOVED (provably a no-op since D305); `config_cell` moves home to the campaign registry

**Spec section:** §6.3 diversifier. Classification: dead-machinery removal, **behavior-identical
by construction** — `EXPERIMENT_CELLS` has derived `frozenset()` since the resid×vix campaign
retired (D305), so phase 0b reserved nothing, the young-capacity pinned-exemption excluded
nothing, and the `experiment_cell_floor:` journal line printed an empty dict.
**Removed:** `ranking/experiment_cells.py` (the derive shim); `diversifier._reserve_experiment_cells`
+ phase 0b + the `experiment_cells`/`experiment_cell_slots` parameter threading
(diversifier/queue ×3 signatures); `sample_young_cell_explore`'s `pinned_cells` exemption;
`main.py`'s kwarg + journal block; the 6 D287 reservation tests + the pinned-skip/pinned-excluded
tests (they test deleted machinery — unlike grammar retirement guards, there is no silent
re-admission path for a deleted function).
**Moved, not deleted:** `config_cell` (the model-based cell extractor) → `ranking/campaigns.py`,
beside its dict-shaped twin `config_cell_from_json`; the mirror-equality test stays (both now in
one module — the D305-noted duplication resolved). `campaigns.py`, `campaign_audit.py`,
`cell_floor.py` and the young-cell floor are UNTOUCHED; `active_selection_cells` remains the
wiring point if a future farming campaign needs a selection floor again (own D-entry).
**Docs same-commit:** MANPAGE knob block + campaigns-list note; architecture ranking breakdown.
**Verification:** ruff + `mypy --strict` clean; `test_ranking` + `test_cli` + `tests/invariants`
green (505 + 601-suite runs; the 4 initial failures were the young-explore tests passing the
removed kwarg — rewired). Restart not required; rides the pending contracts restart window.

## D377 — 2026-08-06 — E4 DECLINED: the "retired tail-clock display plumbing" is a WAITING instrument, not dead code

**The proposed cut** (repo-simplification Step E4 / audit item): `_TAIL_SPEARMAN_DELTA_CRITERION`
+ the paired-delta display path in `ranker_model_cmd.py`, flagged "RETIRED (D285), DISPLAY-only."
**Why it survives review:** D285 retired the §8.6 STREAK and its SPRT flip gate because the
paired incumbent column became self-referential after the gate-tail flip — but the same D285
note (and `status_cmd.py`'s header) says the paired read resumes **once D284 hygiene-incumbent
rows accrue**, and D284 recording went live 2026-07-16 (200/200 non-NULL from the first batch).
Deleting the paired-delta path now would destroy the instrument D284 exists to feed, days
before it becomes readable. `sequential_test.py` likewise serves the LIVE rewire clock
(`status_cmd.rewire_flip_gate`), not only the retired tail streak. **This is the D361 class —
a plausible cut whose axis check fails — caught before the cut this time.** Re-propose only
after the hygiene-incumbent read is taken and judged.

## D378 — 2026-08-06 — the dsj re-read: the shadow lifted and the finding STANDS, on better evidence than before

> (Renumbered D376 → D378 at the E6 commit: D376 was already claimed by the committed E3 entry above — the third same-day number race; commit `8116235`'s message says D376.)

**Spec section:** [[D370]] (the shadow), the 2026-08-06 indicator audit, [[D361]]. D370 flagged our dsj claim — *"6,707 components through our own generator, zero reached a promoted book"* — as **shadowed**, because Crucible's validator had been destroying stage-two promote verdicts since 07-23. With the stamp fixed and the recovery batch recorded, the claim is now measurable. **IT SURVIVES, and the confound is eliminated rather than assumed away.** **THE RECOVERY COHORT IS SILENT ON dsj BY CONSTRUCTION.** 23 distinct promote verdicts landed (our ledger went 4 → 27), and **all 23 were generated by us** — a genuinely good result in its own right, and the first stage-two promotes our own sampler has ever had recorded. But **all 23 are `mean_reversion/swing_mid`**, and dsj is a **trend-only** optional second gate ([[D258]]), so none of them could carry it. Crucible re-derived the 31-config crash cohort **live from their DB rather than from the pinned probe**, so the cohort is complete — which means **no dsj config was ever in it.** The stamp bug hid MR-swing_mid promotes, not trend/dsj ones. Raising the caveat in D370 was right; it turns out not to bite. **THE RE-READ, on unshadowed data:** 29,887 distinct dsj configs generated → **7,901** ever gated `component` → **359** ever clearing the 0.9439 book-usability floor → **0** ever gated `promote` → **0** legs in any promoted book. All **six** dsj legs across the 8 promoted books remain the single hand-tuned `dsj_veto45` (v22) reused six times, and it is **still not ours** — Crucible's 2026-07-08 direct-to-inbox research exemplar, the config that *motivated* the feature rather than a product of it. **THE LESSON SURVIVES INTACT AND IS NOW BETTER-FOUNDED:** dsj's stage-one effect is real and well-powered (z=+5.44 on the honest arm, book-floor rate 0.055% → 0.579%), and its assembly record through our generator is **zero** — demonstrably, not merely apparently. It is the cleanest example we have that **a strong solo-metric effect is not evidence of assembly value** ([[D361]]), and it now rests on a promote stream that records. **OPERATIONAL CAVEAT, recorded so it is not misread later:** the 23 recovery rows landed **untagged**. They were ingested at 00:33 — before [[D375]] deployed — and `INSERT OR IGNORE` does not backfill, so `refit_selection` is NULL on them. **For these 23 rows specifically, NULL means "arrived before we could store the tag", NOT "came from the newest-first drain."** They are identifiable by the `decided_at` window (2026-08-07 00:32:40–00:33:12) and by `fullhist_refit_of`; Crucible's queue-time bounds are 00:28:10.808842–00:28:26.563081. The tag applies from the next reconcile forward. **Transferable:** when a caveat is raised on a claim, re-read the claim rather than quietly keeping the caveat — half the time the confound is structurally impossible and saying so is worth more than the hedge.

## D379 — 2026-08-06 — E6: the `young_explore` lane REMOVED (operator: "We should deprecate E6 for sure")

**Spec section:** D316 Theme 2d. Classification: dead-lane removal, behavior-identical — the
lane was built flag-off (D307-floor-dependent), `FORGE_YOUNG_CELL_EXPLORE_SLOTS` was never set
on any unit or live environment (verified against the unit file AND `/proc/<pid>/environ`),
and zero `young_explore`-tagged rows have ever existed. D367 reaffirmed OFF (87% of the budget
would have funded the ve family being un-propped); the freeze declaration's only mention was
the standing-decision line recording OFF — the freeze work never consumed it (verified:
declaration/criterion cite no lane data; the open prereg `6e81bfaa3907` is adx replication).
**Removed:** `queue.sample_young_cell_explore` + the young params/draw/capacity math in
`rank_batch_with_exploration` (returns 3-tuple now; holdout + objective lanes unchanged);
`main._resolve_young_explore_slots` + threading + journal line; the submitter's
`young_explore_hashes` param + tag + selection_arm map entry; the campaign-audit skip branch;
`tests/test_young_explore.py` (162 lines; its engine-property coverage lives on in
`test_tail_lane.py`, which adapted to the 3-tuple) + the young tests in
submitter/campaign-audit. **KEPT, emphatically:** the D307/D312 young-cell FLOOR
(`FORGE_YOUNG_CELL_FLOOR=on`, live) — a different mechanism; only the biased explore QUOTA died.
**Docs same-commit:** MANPAGE knob block → removal note; architecture lane set; the freeze
declaration's standing-decision line; the Theme-2d proposal status.
**Verification:** ruff + mypy --strict clean; 599 green across
ranking/submission/run_loop/invariants. NOTE the deploy race: the service restarted
17:46:49 PDT (the 1.44.0 window) possibly onto this change mid-application — journal verified
post-commit; see STATUS.

## D380 — 2026-08-06 — (C) IS FALSIFIED BY ITS OWN INSTRUMENT: the quality ceiling broke upward three days after the freeze read, and the §4 capacity caveat was wrong

**Spec section:** `docs/proposals/grammar-freeze-declaration.md`; prereg `74dbbaee89c7`; supersedes the freeze-ready state of [[D358]]. **Operator asked to re-read (C). It should not be signed.** Freeze condition (C) leg 1 was read once on 2026-08-03 at its registered window count and CONFIRMED flat (+0.0041 vs a 0.0242 bar). **Within three days the composition-standardised TCM broke out of its plateau:** windows 14–17 read `0.7563 0.7434 0.7445 0.7625`, windows 18–23 read `0.8079 0.8435 0.8037 0.8398 0.8561 0.9145`. The newest sits **+0.1532 above the pre-break max — six times the bar (C) was judged against** — and the companion `P(cpcv ≥ 1.0)` per window went from a 2–8 baseline to `12 14 7 18 14 29`. **The 08-03 read was not wrong.** It was correct on its data, taken once, at the registered count; the world changed after it, which is what a single registered read is *for*. **NOT COMPOSITION — checked first, because composition is exactly what voided the original (C) in [[D353]]:** raw pooled and standardised TCM track within ±0.005 across all ten recent windows (window 23: raw 0.9159 vs std 0.9145), and the cell mix moves only trend/swing_mid 61%→56%, MR 11%→18%. Standardisation is not doing the work. **THE LIVE INSTRUMENT CURRENTLY SAYS "FLAT" AND IS WRONG TO:** run today it refits `b` over a series containing the break, inflating `2·b_up` to 0.0965 — the [[D357]]/[[D358]] defect in a new costume, and precisely why the registered-bar flag exists. **The replacement bar is fitted on PRE-BREAK windows 1–17 only, and that fit DEGENERATES** — `b = b_up = 0.0000` exactly, the "cannot resolve drift wearing a decisive number" failure this programme has now hit three times — so it falls back to `2·sd = 0.0264`. **PREREG `74dbbaee89c7`** cannot predict the break (already observed), so it predicts **future** data with two legs that separate the only two actionable outcomes: **A (persistence)** — min over 6 new windows stays above 0.7877; **B (continued rise)** — max exceeds 0.9409. A∧¬B = one-time level shift, re-baseline and reconsider the freeze; A∧B = **the ceiling is still rising and the freeze is the wrong call**; ¬A = transient, the 08-03 reading stands. Required n stated at registration: 7,200 rows at a measured 2,018/day ≈ **3.6 days**. **ATTRIBUTION IS EXPLICITLY NOT CLAIMED:** v55 (08-03 02:27Z) and the D216 ve-floor retirement (08-04 02:27Z, reallocating 3–5% of enumeration out of a 0.34%-converting family into ~22.5% ones) are mutually confounded; the second is larger and more plausible but this prereg establishes persistence, not cause. Note the irony against [[D374]], where the +0.0973 trend-median move was deliberately **not** claimed as a benefit — it now looks like part of a much larger real effect. **SEPARATELY, §4's CAPACITY CAVEAT WAS WRONG AND IS WITHDRAWN.** We wrote — and Crucible endorsed — that (C) was read during a capacity squeeze and that "stopped improving" vs "couldn't measure improvement" were entangled. **(C) reads STAGE-ONE distributions; every pipeline fix is STAGE TWO and cannot touch it.** Measured: honest-arm `P(cpcv|submitted)` runs 63.7/62.9/65.2/65.5/64.1 then 72.6/73.0/71.5 across 07-30→08-06, and the single step is **08-04 (our ve change), not 08-06 (their fixes)**. Two sides agreed a caveat in writing and neither checked it. **Transferable:** a condition that reads "MET" is a statement about a window, not a property of the world — and the instrument that proved it must be re-run before the conclusion is acted on, especially when your own changes landed after the read.

## D381 — 2026-08-06 — the refit-lane skim: "filter to untagged" is a WITHIN-ERA instrument, and our recovery batch hides inside it

**Spec section:** `docs/tasks/investigate-live.md` (query discipline); Crucible methods note, same day. **Their finding, verified on our rows.** From 2026-08-06 17:10 PDT their stage-two scanner runs two lanes, so **the untagged cohort is top-depleted from that moment on, permanently** — the quality lane skims exactly the rows that used to sit at its top. On our stored post-boundary rows the gap is severe: untagged **n=1,887, medCPCV +0.5101, 23 promotes** against `quality_margin` **n=24, medCPCV +1.3374, 4 promotes** — a **2.6× median** on 1.3% of the volume. **THE RULE, adopted:** within-era comparisons (both cohorts post-boundary) filter to untagged and are clean; **cross-boundary comparisons — which includes every v55-vs-vNext read we will ever run — must use the UNION of untagged + `quality_margin` per version**, because the two lanes partition one eligible population and only the union is commensurable with pre-boundary rows. Untagged-only costs the newer version ~0.10 medCPCV **by construction**, the size of a real version delta, **in the direction that would make a freeze look wiser than it is**. `promote_stamp_recovery` is excluded from both read types always — it is a one-shot selected batch, not a lane. **AND ONE ADDITION THAT IS OURS ALONE, relayed back:** their rule assumes the recovery batch is tag-filterable. **In our mirror it is not.** The 23 recovery rows were ingested minutes *before* the `refit_selection` column shipped ([[D375]]) and our writer is `INSERT OR IGNORE`, so they carry **NULL rather than `'promote_stamp_recovery'`** and a naive `refit_selection IS NULL` filter silently *includes* them. Measured: they are **0.7% of our untagged rows (14 of 1,887) but carry 35% of its promotes (8 of 23)** — median barely moves (+0.5101 → +0.5081) while **any promote-rate read inflates by 53%** (23 vs 15). On our side the exclusion must therefore be done **by time, not tag**: `decided_at NOT BETWEEN '2026-08-07 00:32:40' AND '2026-08-07 00:33:15'`. Rows from the next reconcile forward are correctly tagged; this applies to that one batch only. **WHAT THIS DOES AND DOES NOT TOUCH:** prereg `74dbbaee89c7` (the post-break persistence read) is **unaffected** — it reads honest-arm **stage-one** rows, and `refit_selection` is a property of the stage-two refit, so no stage-one row carries or needs it. Affected are per-version **stage-two** reads: the funnel-style comparisons of D363, and any learned-weight or tail-model series trained on stage-two labels. **Transferable:** when a producer adds a selection lane upstream of you, the cohort you were already filtering on silently changes meaning at a dated boundary — and the danger is not the new cohort, it is the *old* one, which is now defined by what was taken out of it.

## D382 — 2026-08-08 — the adx regime-gate association REPLICATES (ρ=−0.1013 at 1.50× its MDE), collider re-check passed, and it authorises nothing

**Spec section:** prereg `6e81bfaa3907`, resolved `confirmed`. **Single read at n=1,727** post-cut qualifying rows against the registered ≥1,500, no earlier peek. **THE COLLIDER CHECK WAS RE-RUN AS PART OF THE READ, not inherited** — that was the load-bearing precondition, because a gate clean at registration and confounded at read time is exactly what this prereg existed to catch, and inheriting registration-time cleanliness would have been assuming the thing under test. It passes: adx observation rate by threshold quintile reads **83.4 / 78.0 / 81.3 / 81.5 / 80.1, spread 5.4pp** against a 10pp VOID threshold. (Contrast `vix_term_slope` at 26.7pp, whose larger apparent rhos of −0.357/−0.321/−0.207 remain **not causally readable**.) **RESULT:** n−3-weighted Fisher-z pooled within-cell Spearman(adx threshold, cpcv_p25) = **−0.1013 against an MDE of 0.0674 — negative as predicted, 1.50× its own detection floor.** All four contributing cells share the sign: `sma_slope` −0.0224 (n=783), `momentum_252` −0.1922 (n=708), `ad_slope` −0.0820 (n=189), `donchian` −0.0954 (n=30). **The individual cells moved substantially in both directions from registration** (sma_slope −0.237→−0.0224, momentum_252 −0.131→−0.1922) **while the pooled estimate held near −0.10** — which is what a real but modest effect looks like under resampling, and a mild argument against the registration reading having been a fluke. Direction: **higher adx threshold ⇒ lower cpcv**, so any implied steer is toward *lower* thresholds. **THE CLOCK WAS WRONG AND THAT IS MINE.** Registration stated ~1.6 days from a measured 922 qualifying rows/day; the read took **4.8 days**. The rate was measured over a window still containing `SAMPLE_N=150` and I reverted it to 40 hours later ([[D359]]) — **I costed the denominator on a rate I then changed myself.** The required *n* was correct and stated in advance, which is what the discipline requires; the calendar estimate attached to it was not, and a prereg whose clock is off by 3× invites exactly the impatience the reading rule exists to prevent. **WHAT IT AUTHORISES: nothing, by design and as registered.** It establishes only that the association survives out of sample on the honest arm. A within-cell cpcv correlation cannot speak to assembly value — [[D361]] is the standing result, and `swing_long` is bad on every solo metric while sitting in 7 of 7 promoted books. A generation steer needs its own operator-gated prereg predicting a **quality** outcome rather than a correlation, and must clear the D361 test first. **AND A CONDITION THAT POST-DATES REGISTRATION:** freeze condition (C) has since been falsified by its own instrument ([[D380]]) and the quality ceiling broke upward by +0.1532 on 08-06, so **the honest-arm distribution this rho was measured over is itself moving.** Any follow-on design must not assume a stationary population.

## D383 — 2026-08-08 — QuantIQ's D491 verdict: FAIL, accepted without appeal; and our −0.043 should never have been their bar

**Spec section:** cross-system; QuantIQ D491/D493; the 2026-08-05 equities close-out. **VERDICT ACCEPTED, no appeal.** The PTS package Forge proposed is **not adopted**, the live config is unchanged, and the event is closed under the one-event-then-stop clause we ourselves supplied. **Criterion iv is the correct kill and it fired on our own disclosure:** the k-grid reads −0.0035 / **+0.3722** / +0.0857 / −0.0498 across k1.5→k3.0, so the improvement exists only at the selected parameter. We had flagged the right-side cliff as "the strongest argument for YOUR walk-forward before adoption"; that sentence is why criterion iv existed, and criterion iv is what killed it. **THE REPLICATION IS THE PART WORTH KEEPING:** independent codebases, **excess 1.2243 vs our 1.1837 and maxDD −3.89% vs our −3.91%** at the same k, with the earnings-rule mechanism transporting cleanly (46 forced exits on their sim vs our 54, majority profitable both). That is about as strong as cross-implementation agreement gets. **THEIR ONE QUESTION — the provenance of our −0.043 tail-decorrelation number, which they imported as criterion iii's bar. ANSWERED AS FAR AS OUR RECORDS ALLOW, and no further.** Pinned from the shipped artifact (`FORGE_ARTIFACT_pts_replica_curve_2011pts_2026-08-05.json`): window **2018-01-03 → 2025-12-31, 2,010 overlap days**, full-sample corr 0.1647, own-base returns `r_opt_t`/`r_pts_t` combined into fixed dollar sleeves (S_OPT 18,000 / S_PTS 7,406.52 / NAV 25,406.52), conditioned on the **options book's own** worst-5% days. **TWO OF THEIR THREE CANDIDATE GAPS ARE ELIMINABLE WITHOUT DATA:** own-base vs NAV-base, and the $18k-vs-$19k sleeve, **both leave a correlation unchanged** — Pearson is invariant under positive linear scaling and the sleeve transform is exactly that. So the gap is not a units mismatch. **Live candidates, ranked:** (a) **a different options book** — the designation flipped `aa31532489613849` → `f52a05c8968bdc7a` on 2026-08-01, four days before we measured, and [[D357]] measured that exact class of substitution moving a book-referenced statistic by **−0.0458, 2.6× that leg's decision bar**, despite +0.9531 rank agreement; a tail-conditional correlation is far more fragile than a level. (b) conditioning on **blended-NAV** worst days rather than the options book's — which, unlike scaling, genuinely depends on the sleeve weights. **WE CANNOT RECOMPUTE IT and said so plainly:** Forge holds no options-book daily equity curves (our exports carry configs, weights and correlations, never curves), so the options series behind that number is an input no longer on disk. Reverse-engineering a plausible match and calling it provenance was the alternative and was declined. **THE MORE USEFUL FINDING IS OURS.** A single number from a close-out relay became a *threshold* in another system's pre-registered criteria, and neither side stated or checked the curve it was measured against. Their result exposes it: the **BASELINE reads +0.1994 and fails the bar too**, while the candidate *improves* the property to +0.1467 — a bar the incumbent cannot clear is not a bar. **This is the second instance in one day.** The first was ours with Crucible in the opposite direction: we wrote and they endorsed a caveat that freeze condition (C) was "read during a capacity squeeze", and neither side checked whether (C)'s basis touched stage two at all — withdrawn the same morning ([[D380]]). **Transferable, and proposed to QuantIQ as a standing row in the interface-model document:** the interface risk is not only "what does this FIELD mean" but **"what was this NUMBER measured against, and is it commensurable with the use you are about to put it to."** Nothing hinges on it for D491 — criterion iv fails independently.

## D384 — Prereg `74dbbaee89c7` READ ONCE at registered n: the ceiling took a **one-time level shift and re-plateaued**. Leg A CONFIRMED, leg B REFUTED. The freeze survives — its evidence base does not.

**Date:** 2026-08-09 · **Class:** measurement (registered read) · **Grammar:** v55, untouched

### The read

Taken at the registered count and only then: **29 complete n=1200 windows, n=34,839** honest-arm
stage-one rows carrying a cpcv (`selection_mode='prefilter_sample'`, `measurement_basis IS
DISTINCT FROM 'fullhist_refit'`). Reference book basis fingerprint `ae47a4749c9d` verified before
reading; corr join 87.6%.

```
windows 24-29 standardised TCM   0.8759  0.8971  0.8889  0.8675  0.8918  0.8751

LEG A  persistence    min 0.8675  vs registered 0.7877  = +0.0798   CONFIRMED
LEG B  continued rise max 0.8971  vs registered 0.9409  = -0.0438   REFUTED
```

Per the registered decision rule, A-confirmed + B-refuted is **ONE-TIME LEVEL SHIFT**: the plateau
moved from ~0.75 to ~0.88 (+0.13) and settled. The floor of the new regime clears the old ceiling
by 3.0× the bar, and not one of the six windows reached even the pre-read peak of 0.9145 — so
window 23 was the top of the excursion, not a waypoint on a climb.

### Why the thresholds were literals

Both comparison values were fixed at registration and used verbatim. Running the exploratory
instrument today would still report "flat within the drift floor", because it refits `b` over a
series that now contains the break and inflates `2·b_up` to 0.0965 — the D357/D358 defect in a new
costume. The registered read computes none of its own constants; that is the entire reason it is a
separate script from `freeze_tail_reading.py`.

### What the two legs each buy

- **Leg B refuting is what keeps a freeze coherent.** A still-climbing ceiling would have meant
  demonstrable headroom and the freeze would be wrong on the merits. It is not climbing.
- **Leg A confirming is what invalidates the declaration's evidence.** (C) certified flatness at a
  level the stream has since left. The declaration is not wrong about *flatness*; it is stale about
  *where*. Signing it now would freeze against a plateau that no longer exists.

### Consequences

1. `docs/proposals/grammar-freeze-declaration.md` header updated: **DO NOT SIGN AS WRITTEN**,
   re-baseline required. The (C) block in §2 is now explicitly a record of the old level.
2. **Re-baselining is the next measurement**, not a decision: a fresh (C) registered against the
   post-break level with its drift floor refit on **post-break windows only**. We have six. The
   prior fit degenerated to `b=0.0000` on 17 windows, which is "cannot resolve drift", so the
   window budget for a non-degenerate refit is the open design question — not something to settle
   by reusing the old 2·sd fallback without saying so.
3. **Attribution is NOT decided by this read** and must not be inferred from it. **(SUPERSEDED
   BY D385: the attribution guess below is REFUTED — the break is a global measurement-basis
   step, not either of our changes.)** v55 (08-03 02:27Z)
   and the D216 ve-floor retirement (08-04 02:27Z) are one day apart and mutually confounded; the
   ve-floor change is larger and more plausible but that is an argument, not a measurement.

### Instrument change (TDD, red first)

`scripts/freeze_registered_read.py` gained `PersistenceLeg` / `_read_persistence` rather than
reusing `RegisteredLeg`. Three structural differences made sharing unsafe: both legs read the
**same** six windows; leg A aggregates with **min** because it tests a floor; and **CONFIRMED here
means the prediction held**, the opposite polarity from the (C) legs where clearing the bar means
falsified. Reusing `_read` would have silently inverted leg A. Added `--read {c,persistence}` plus
a registry-status guard that **aborts on any prereg not marked `registered`**, so the single-read
rule is enforced against the record rather than against memory. 16 tests, ruff + format clean.

### A note on the record

The registry's outcome token is one of three and cannot express a two-leg split. It reads
`confirmed` because leg A held; **leg B is REFUTED** and the evidence string says so in its first
line. `confirmed` is the less dangerous of the two available tokens: a bare `refuted` would read as
"the break was transient and the 08-03 reading stands", which is the registered meaning of a leg-A
refutation and the precise opposite of what happened.

## D385 — **The 08-03 break is NOT ours and is not generation.** A global cpcv step at 2026-08-03 13:27Z survives holding grammar version, cell and composition fixed. D384's attribution is REFUTED by our own data; freeze condition (C) has been comparing across two measurement bases.

**Date:** 2026-08-09 · **Class:** measurement (diagnostic, registers nothing) · **Corrects:** D384 §3

### What was measured

Boundary `2026-08-03 13:27:42Z` in submission order (decision batch `13:50:30Z`), sharp — one
window to the next.

```
                     n pre / post      median cpcv          p95
selected stream    54,306 / 84,905   0.2613 -> 0.4749  +0.2136   +0.1829
honest arm         20,353 / 14,486   0.1527 -> 0.2705  +0.1178   +0.1295

v54 ONLY, within cell, shares flat to +/-1pp:
  trend_continuation/swing_long   0.7780 -> 0.8464   +0.0684
  trend_continuation/swing_mid    0.6363 -> 0.7452   +0.1089
  mean_reversion/swing_mid        0.7608 -> 0.8530   +0.0923
```

Identical generation policy, identical composition, materially better scores. The step is larger
on Crucible's selected stream than on our unselected sample, so it is not about our sampling.

### Every candidate eliminated

- **v55** — head-to-head against v54 *inside the same windows*: +0.0343 pooled, and **−0.0020 in
  `mean_reversion/swing_mid`**, a cell v55 does not touch, which rose +0.13 anyway.
- **The D216 ve-floor retirement** — lands 08-04, a day AFTER the break. It is also a
  between-hypothesis share change, and `hypothesis` is a post-stratification dimension, so the
  statistic is blind to it by construction; `_tcm` takes a **weighted** quantile and a **weighted**
  mean, so the whole statistic is evaluated under a fixed reference mix. Confirmed empirically:
  ve's own within-cell quality moved **+0.0066**.
- **A re-gate wave** — 16,430 config_hashes carry two distinct stage-one cpcv values, which looked
  decisive for about four minutes. The honest arm has **34,839 rows / 34,839 distinct configs**,
  zero duplicates, and every re-measured pair is entirely pre-boundary (mean delta −0.0529 —
  re-measurement made scores *worse*).
- **More data** — `trade_count` fell 522.2 → 501.9.
- **Our own `FORGE_PREFILTER_SAMPLE_N` change** — TCM is flat at ~0.75 across both the normal-rate
  and elevated-rate stretches and steps after; rate and level do not track.

### What we cannot test

Whether the step keys on submission time or scoring time. Median queue lag is 0.37h and, excluding
`fullhist_refit`, **no stage-one row submitted pre-boundary was decided post-boundary** — the
discriminating cell is empty. Relayed to Crucible with the evidence and four ranked candidates; a
rolling evaluation window is the most likely and needs no fix, only a name.

### Why this matters more than the attribution

**(C) has been read across a basis boundary.** Windows 1–17 sit in one measurement basis and
18–29 in another. That is the defect class of D357/D358 in a third costume, and worse, it is the
skim rule we adopted from Crucible in D381 — *do not pool across a re-measurement boundary* —
violated by our own instrument within a week of adopting it.

Consequences, none of which retract D384's arithmetic:

1. **The pre-break (C) reading may still be the correct answer about the grammar.** Windows 1–17
   are within one basis and were never contradicted by grammar evidence.
2. **Re-baselining against ~0.88 is now the wrong move** — it would bake an environment level into
   a grammar criterion and read as a decline when the environment moves back.
3. **`74dbbaee89c7` measured what it said it measured.** Leg A's "durable level shift" is durable
   *within the new basis*, six windows deep. It is not evidence the grammar improved, and D384
   should not be cited as if it were.
4. **The freeze criterion needs a basis-era guard** — (C) must read within a measurement era and
   the instrument must REFUSE across a detected boundary, exactly as leg 2 already refuses on a
   reference-book fingerprint mismatch. Asked Crucible for a machine-readable basis marker to key
   it on. Design, not yet built.

### On D384's attribution paragraph

D384 §3 recorded the ve-floor retirement as "the larger and more plausible driver", hedged as "an
argument, not a measurement". The hedge was correct and the argument was wrong. It took one
weighted-quantile read of our own instrument's source to see that the mechanism could not work —
which was available before the paragraph was written, not after.

## D386 — **The 08-03 boundary is Crucible's monthly tier-3 universe re-rank (13:00:07Z).** Cause ACCEPTED; their stated route REFUTED on our data — the step lives entirely in the cross-sectional arm, which draws no underlying. First-trading-day-of-month adopted as a standing basis boundary.

**Date:** 2026-08-09 · **Class:** measurement + interface · **Follows:** D385 (the ask), D381 (the skim rule)

### What they answered

`crucible-universe-publisher` runs the §3.3.1 tier-3 re-rank **only on the first trading day of
each month**. August's fired 2026-08-03: `tier3_refresh.start` 13:00:00Z, `tier3.floor_excluded
n=86`, `tier3.refresh_written n=74` at 13:00:07Z — **27 minutes before our submission boundary**.
They cleared every scoring-side input across it: rolling window moved Saturday not Monday, zero
`src/` commits 08-02/08-03, CPCV folds/purge/embargo/p25 untouched, earnings-store rewrite 32h
earlier with no step at its own timestamp. The 07-01 firing is the same job — our "July universe
shrink", which retro-explains the v35→v36 boundary note.

**Cause accepted.** Their diagnosis is right and we could not have found it from our side.

### Their route does not reproduce

They predicted post-boundary configs would draw from the new 74-name pool. Measured:

```
arm                                  n pre   n post   pre TCM   post TCM     delta
XSECT  (ranks over the universe)     19,101  14,098    0.7494    0.8732    +0.1238
NAMED  (one underlying)               1,252     388    0.4661    0.4521    -0.0140
```

**The step is entirely in the arm that draws no underlying.** Our named arm is ~100%
`volatility_event` on index/ETF underlyings — static tier-1/2, which they correctly said tier-3
churn does not touch; that is not a corollary, it is substantially our whole named population.

Composition is dead at every level we can hold:

- **Tier** (the one real sub-cell shift, pointing the wrong way): share 4.5% → 1.9%, tier-3's own
  quality flat at +0.0026, and re-weighting pre-quality to the post mix buys **−0.0031**.
- **Cell AND tier together:** +0.1251 / +0.1293 / +0.1062.
- **Underlyings present in both eras only:** +0.1245.
- `selector.universe` is absent from all 52,952 configs — the universe is not baked in at birth.

### What our data forces

The affected population is the one with **no underlying**, so the route cannot be which name a
config drew. The remaining construction is **the universe a cross-sectional config is ranked
over**, read at run time, independent of the price window. That would make their sentence *"the
August snapshot sits outside every backtest window, so a config's SCORE cannot see it"* true of
the price data and false of the ranking universe. **Asked as a question about their runner, not
asserted as a claim about it.** It also explains why selection amplified the step (+0.2136 vs our
+0.1178): the selected stream is more cross-sectional than the honest arm.

### Consequence for the marker — layer 1 is not enough

They offered two layers: (1) fingerprint the snapshot our generator read, at config birth, no
contract change; (2) a data-basis fingerprint stamped on stage-one verdicts, needing the 1.4x
dance. **If the basis attaches at ranking time, birth is the wrong stamp** — a config generated
pre-boundary and scored post-boundary would carry a fingerprint asserting a basis it was never
measured under, i.e. confidently wrong, which is worse than absent. We escaped this month only
because median queue lag is 0.37h and no stage-one row straddled 13:00Z; a 09-01 backlog does not
repeat that luck. **Layer 2 requested.** Layer 1 will be built anyway — free, and it catches
generation-side changes layer 2 would not — but it does not stand in for layer 2.

### Adopted regardless of their answer

**First trading day of the month is a standing basis boundary** — 2026-09-01, 10-01, monthly. The
freeze instrument must refuse to pool across it, as leg 2 already refuses on a reference-book
fingerprint mismatch. Design; not yet built.

### Standing position on the freeze

Unchanged and now confirmed by both sides: **(C) pooled two bases.** The pre-break reading, wholly
inside one basis, is the one that speaks about the grammar. Re-baselining at ~0.88 would bake
Crucible's liquidity floor into our grammar criterion and read as a decline when the pool churns
back. Re-baseline stays HELD. `74dbbaee89c7`'s arithmetic is untouched; its level shift is durable
*within the new basis* and is not evidence the grammar improved.

## D387 — **RETRACTION + the basis guard.** The 13:27Z boundary was a window-grid artifact; the true cut is 2026-08-03T17:15:54Z, our own cache lag. Crucible's generation-basis mechanism is CONFIRMED and our ranking-time correction is WITHDRAWN. Layer 1 already existed — we were not consuming it. Guard now built. Leg B of `74dbbaee89c7` is basis-clean; leg A is not.

**Date:** 2026-08-10 · **Class:** measurement + instrument · **Retracts:** D386 §"what our data forces"

### What we got wrong, and how

We reported the boundary as `2026-08-03 13:27:42Z` and called it sharp. **That is where our
1200-row window grid broke** — an index, not a changepoint. Crucible's publish at 13:00:07Z landed
27 minutes earlier and we read the proximity as corroboration. At hourly resolution across
08-02→08-04 there is no discontinuity there at all: medians run 0.11–0.35 on n=50–500/hour.

Every elimination in D386 was computed against that wrong cut.

### The true boundary, from a marker we already had

```
universe component of enumeration_inputs_hash    n       median     TCM     window
877b1eddde9864eb                             12,153     0.1419   0.7384    07-23 -> 08-02 08:29
877b1eddde9864eb                              9,472     0.1772   0.7634    08-02 08:54 -> 08-03 16:50
e1adced727678c8f                             13,214     0.2745   0.8745    08-03 17:15 -> 08-09
```

`2026-08-03T17:15:54Z` — our `_load_universe_tiers_cached` lru_cache picking up their 13:00:07Z
publish **4h15m late**. The clock disagreement was ours.

### The test that decides the mechanism, and it decides for Crucible

Within the OLD fingerprint, by day: 07-29 0.8117, 07-30 0.7178, 07-31 0.7155, 08-01 0.7409,
08-02 0.7575, **08-03 0.7674**. Median queue lag is 0.37h, so 08-03 configs submitted up to 16:50
were **scored after their publish, under their new universe** — and read at the OLD level. Had the
route been the ranking universe at scoring time, as we argued, those would have risen.

**Generation-basis confirmed. Our proposed amendment to their sentence is withdrawn.** What we no
longer claim is *why* a cross-sectional config with no drawn underlying moves with a universe
change; the timing is unambiguous, the mechanism is not ours to assert, and the instrument only
needs the boundary.

### Layer 1 already existed

`universe_fingerprint()` (D078) — 16-hex digest of the resolved pool plus the tier-3 split, folded
into `enumeration_inputs_hash` on every batch. It recorded the boundary faithfully on the day.
**The gap was never instrumentation; the freeze instrument did not consume it.** Layer 2 relayed
back as de-prioritised: generation-basis is covered by what we have, and only a scoring-basis
change (the 07-19 cache-repair class) remains uncovered.

### The guard (TDD, red first)

`freeze_tail_reading.window_bases()` returns the distinct bases per window, with two deliberate
behaviours: a **straddling** window reports BOTH (it belongs to neither era and must never be
assigned to one by picking a side — that is exactly how a grid boundary became a changepoint), and
an **untagged** window reports the empty set, which the guard refuses on. A guard that passes on
absent data is worse than no guard: it certifies. `freeze_registered_read._basis_guard()` refuses
any registered slice spanning more than one basis, before reading. The query LEFT JOINs
`batch_summaries` so untagged rows arrive as NULL rather than being dropped — dropping them would
shorten the series and move the grid. 37 tests, ruff clean.

Live map: windows 1–18 `877b`, window 19 STRADDLES, windows 20–29 `e1ad`.

### Consequence for `74dbbaee89c7`, which is the useful part

- **Leg B is BASIS-CLEAN and STANDS.** Its threshold derives from window 23 (`e1ad`) and its six
  windows 24–29 are all `e1ad`. Within a single generation basis, `max 0.8971 vs 0.9409` →
  **the ceiling is not rising.** That reading survives everything in this entry.
- **Leg A is CROSS-BASIS and must be discounted.** Its threshold 0.7877 derives from the old-basis
  windows 1–17 while its six windows are new-basis. The +0.0798 margin measures the universe
  change, not persistence. It should not be cited as evidence of a durable *grammar* level shift —
  D384's arithmetic is correct and its interpretation narrows to "the new basis is internally
  stable".

So the coherent picture across D384–D387: **within a fixed generation basis the ceiling is flat,
and the apparent break was a basis change.** That is the pre-break (C) reading, re-derived on the
other side of the boundary — which is the strongest form of agreement available here.

## D388 — Within-basis (C) REGISTERED as `3b0cbca7ae17`. A replication, not a re-baseline: both original (C) legs were basis-clean and STAND. First non-degenerate drift fit in the programme.

**Date:** 2026-08-10 · **Class:** measurement (prereg) · **Follows:** D387

### Why replication, not re-baseline

The basis map settles it: **global windows 1–18 are all `877b1eddde9864eb`.** Leg 1 read 11–16 and
leg 2 read 12–17, so **neither original (C) read crossed the boundary.** They stand as measured.
What was contaminated was the follow-on narrative and leg A of `74dbbaee89c7`. The open question
is therefore whether (C) *still holds* now the generator draws a different universe — and a
replication in a changed environment is stronger evidence than the original.

### The registered numbers

Basis `e1adced727678c8f`, from 2026-08-03T17:15:54Z to the 09-01 re-rank. Rows are filtered to the
basis **first** and gridded **second**, so there is no straddling window to reason about. 11 prior
windows, zero straddles, reference-mass coverage 0.996–1.000, corr join 100%.

```
leg 1 TCM       0.8467 0.8063 0.8471 0.8631 0.9193 0.8720 0.9018 0.8935 0.8701 0.8909 0.8857
                max 0.9193   bar 0.0536 (2*b_up)              falsified above 0.9729
leg 2 TCM-corr  0.4456 0.4358 0.4253 0.4414 0.4411 0.4427 0.4321 0.4484 0.4375 0.4474 0.4335
                max 0.4484   bar 0.0135 (max(2*b_up, 2*sd))   falsified above 0.4619
```

**The drift fit does not degenerate — the first time in this programme.** `b=0.0235`,
`b_up=0.0268` on the basis-local windows. Every prior attempt returned `b=0.0000` exactly and
forced a `2*sd` fallback three separate times. Within a single basis the drift term is real.

### The concession that is in the prereg because it cuts against us

Leg 1's bar is **0.0536, which is 2.2× the original's 0.0242** — wider precisely *because* the fit
now resolves drift instead of collapsing to zero. **A wider bar makes "flat" easier to confirm**,
so a confirmation here is weaker per-unit than the original's and must not be reported as equally
stringent. The RULE was held fixed rather than the number, which is the only defensible choice;
the consequence belongs in the record rather than in a footnote found later.

### Void condition, enforced by the instrument

If the generation basis changes before 6 new windows accrue, the prereg is **VOID** and must be
re-registered inside the new basis — `_basis_guard` refuses rather than reading across. Two things
would do it: an early Crucible re-rank, and **a grammar bump, which is also a generation-basis
change.** No grammar change ships during the measurement window.

### Instrument

`--read within-basis` reuses `RegisteredLeg`/`_read` deliberately: the point of a replication is
that the rule does not move. What differs is upstream — `filter_to_basis` before gridding.
`--basis` added to the exploratory instrument.

Two bugs found and fixed while wiring it, both in the guards rather than the statistic:

- **`ref` shares were divided by the pre-filter `n`.** A uniform scale on every weight CANCELS
  inside `_tcm`'s ratio, so the statistic still read correctly while `coverage` and `max weight` —
  the two guards that exist to make a thin window declare itself — silently reported the filter
  fraction (0.391 instead of ~1.0). A bug that only breaks the alarms is the expensive kind.
- **`_basis_guard` reported "UNTAGGED" for a slice past the end of the series.** "Wait three days"
  and "investigate the marker" were wearing the same message. Now separated.

42 tests, ruff clean.

## D389 — **Within-basis (C) READ and CONFIRMED on both legs.** `3b0cbca7ae17` resolved; the freeze programme has zero open preregistrations. Quality and redundancy both moved DOWN inside a single generation basis, not merely flat.

**Date:** 2026-08-14 · **Class:** measurement (registered read) · **Follows:** D388

### The read

Taken once, at the registered trigger, against a real-disk snapshot. Basis-scoped to
`e1adced727678c8f`: n=22,273, 18 basis-local windows, grid built **after** filtering so no
window straddles the seam. Basis guard reported windows 12–17 basis-clean. Corr join 84.2%;
reference book fingerprint `ae47a4749c9d` verified before leg 2 read.

| leg | new-6 best | registered baseline | delta | bar | falsify above | verdict |
|---|--:|--:|--:|--:|--:|---|
| 1 — quality (std TCM) | 0.8971 | 0.9193 | **−0.0222** | 0.0536 | 0.9729 | **CONFIRMED** |
| 2 — redundancy (std TCM-corr) | 0.4392 | 0.4484 | **−0.0092** | 0.0135 | 0.4619 | **CONFIRMED** |

New-6 quality: 0.8971 0.8887 0.8440 0.8478 0.8881 0.8501.
New-6 redundancy: 0.4372 0.4354 0.4349 0.4231 0.4282 0.4392.

**Both deltas are negative.** The prereg only required "not up by more than the bar"; the
measurement came in below baseline on both legs, so neither confirmation leans on its bar.

### Three things recorded against ourselves

1. **The literals did their job, and the drift was real.** Recomputed prior maxima came out at
   0.9204 / 0.4485 against the registered literals 0.9193 / 0.4484 — post-stratification
   re-weighted history as the sample grew, exactly the float the prereg fixed literals to
   prevent. The read used the literals. That choice made the test marginally **harder**, not
   easier, which is the only direction in which such a choice is defensible.
2. **This confirmation is weaker per-unit than the original (C).** Leg 1's bar is 0.0536,
   2.2× the original's 0.0242, because the drift fit resolved (`b_up=0.0268`) instead of
   degenerating to zero. A wider bar makes "flat" easier to confirm. Carried from D388's
   registration rather than discovered afterwards — and the observed −0.0222 would also have
   cleared the original's narrower bar, which is the fact that makes the caveat survivable.
3. **The read was overdue and nothing fired it.** STATUS.md described a watcher as armed;
   there is no systemd unit and no cron entry for `freeze_registered_read.py`. The clock
   (7,490 in-basis rows vs the 7,200 required) had already been reached when an operator
   check surfaced it. The prereg forbids extension, so a silently-drifting read is a real
   failure mode. **Action: either install the watcher or delete the claim from STATUS.md —
   an unarmed watcher described as armed is worse than no watcher.**

### What this authorises, and what it does not

(C) **replicates inside a single generation basis** — the strongest form of the claim available,
since the generator now draws from a different universe than when (C) was first measured. Per
D388's `action_if_confirmed`, the freeze **declaration** may now be re-founded on within-basis
evidence. That is a document change and **requires the operator's signature; it is not taken here.**

It does **not** re-open the original (C), which stands on its own basis-clean windows. It does
not settle whether a cross-sectional config with no drawn underlying should move with a universe
re-rank at all — still open with Crucible. The void condition never fired: zero rows on any other
basis since the cohort cut, and no grammar bump shipped during the window.

## D390 — **GRAMMAR FREEZE SIGNED.** Operator signature 2026-08-14; grammar frozen at v55; §6 governance in force. Signed on the narrow claim (bulk supply has stopped improving) with the expansion objection explicitly unanswered and carried by the §5 reopeners.

**Date:** 2026-08-14 · **Class:** operator decision (freeze declaration) · **Follows:** D389

### The decision

`docs/proposals/grammar-freeze-declaration.md` moves from RE-FOUNDED/awaiting-signature to
**SIGNED**. Programme D328 → D390. All three conditions were met on registered reads:

| condition | evidence | status |
|---|---|---|
| (A) coverage | census `dead_unprotected` empty — 0 dead cells, 0 dead flow of 148,322 | MET 2026-08-06 |
| (B) multiplicity efficiency | metric B 0.00%, **18** consecutive runs ≤1.00% against a bar of 7 | MET |
| (C) supply ceiling | `3b0cbca7ae17` within-basis, both legs **below** baseline (−0.0222 / −0.0092) | MET, re-founded 2026-08-14 (D389) |

### What the signature asserts — deliberately the narrower claim

**Asserted:** the bulk of the supply distribution has stopped improving, and the search/throughput
budget is better spent on the converting core than on further generation-side search.

**NOT asserted:** that no better strategy exists, that the grammar cannot be improved, or that a
ceiling has been proven. Both counter-measurements were read before signing and are named in the
signed header: the ranked lane is still setting running-maximum records at exactly the
unbounded-search rate (z=+0.13; trail 1.4738 → +1.7397), and the joint frontier is still advancing
(z=+3.60, p=0.003).

### The strongest objection, unanswered on purpose

§4: **"the window spans mostly prunes, not expansion — absence of movement is weak evidence about
what expansion could do."** This is not answered by the evidence and the declaration does not claim
it is. It is why §5's reopeners are first-class: reopener (2) (new registry family with a
net-long-vega mechanism argument) and reopener (3) (Path-C structural decision) are exactly the
untested expansion cases, each reopening a version bump on the operator's signature alone.
Related unanswered limits, all retained in §4: (C) is arithmetically blind to a top-1%-only lift
(rank ~120-from-top vs promotion-grade rank ~0.4–5), and the honest arm does not exist before v49,
so v43 and v47 — the programme's two headline prunes — cannot be validated on that basis at all.

### Why sign now rather than measure more

§8 Step 1 is the load-bearing practical finding: **14 of 23 configs clearing both binding gates were
never refit**, stage-one profile identical to the 9 that were, refit latency p99 = 2h proving they
were passed over rather than queued. The binding constraint on component production is **Crucible-side
refit triage, not Forge-side generation.** Additional grammar search cannot address it. That makes
committing the budget a measured decision rather than an admission of exhaustion.

### In force from this date (§6)

Any post-freeze grammar change is a full increment: **prereg before the edit with required n stated
at registration** (D363/D364), version bump + archive + Decision Log (hard rule #10), goldens
re-pinned, emission proof, funnel attribution, STATUS block. Standing Crucible obligations carry
forward (`INDEX_forge_answered.md`): report eligible-vs-drain drift in either direction —
**under-supply is now the failure mode that costs components** — flag honest-arm rate changes that
move a registered basis, and never tune generation against `IC(cpcv, corr_to_book)`.

### Not done here

The freeze is **procedural, not code-enforced** — no script, config or service reads the
declaration, and the pre-commit grammar version-bump scanner would still pass a post-freeze bump.
A structural guard (hook-level refusal absent a prereg, in the spirit of hard rule #4) is the
obvious follow-up and is **not built**; it is an operator call, logged here so the gap is a known
one rather than an assumed enforcement. The **watcher gap from D389 also remains open**.

## D391 — **D386's standing basis boundary is WRONG and is CORRECTED: the re-rank fires on the 3rd (`OnCalendar=*-*-03`), not the first trading day.** August hid it — Aug 1 was a Saturday, so the two coincided. September diverges by two days. Crucible's export also went DAILY on 08-11; our fingerprint is unaffected, verified in code.

**Date:** 2026-08-14 · **Class:** correction (measurement basis) · **Follows:** D386, D389, D390

### The correction

D386 adopted "first trading day of the month" as a standing basis boundary — 09-01, 10-01,
monthly. **That rule is falsified.** Crucible's answer to our §4 schedule ask:

```
  timer          OnCalendar=*-*-03 06:00:00, Persistent=true
  next run       2026-09-03 (Thu)          <- the FACT: when the basis can change
  snapshot asof  2026-09-01 (Tue)          <- the LABEL: what the file says
  August         Aug-01 Sat -> first trading day WAS Aug-03 -> label == fact, by accident
```

The snapshot is *labelled* with the first trading day because their ranker picks it inside the
month window, but **it does not exist until the run.** We adopted the label as the boundary after
observing a month in which the two happened to coincide — a single-observation generalisation that
looked confirmed because the calendar cooperated.

**Two consequences, both ours to carry:**

1. **The boundary is the RUN, not the label.** Configs our generator emits on 09-01 and 09-02 still
   draw the AUGUST universe, because the September snapshot does not yet exist. Any window cut on
   "first trading day" puts those two days on the wrong side — the same class of error as D387's
   window-grid artifact, and it would have been invisible again in a month where the dates aligned.
2. **`Persistent=true` means the boundary can move LATER, never earlier.** A missed run fires on
   next boot. The honest statement is **"on or after the 3rd"**, never "on the 3rd". Crucible will
   treat a late catch-up as notifiable, since it has the same effect on a window as an off-cycle
   re-rank.

### The rule that replaces it

**The resolved `enumeration_inputs_hash` universe component is the cut. Full stop.** The calendar is
demoted from a rule to a rough expectation — useful for *planning* a read, never for *cutting* one.
This is what D387's basis guard already enforces in code; D386's calendar heuristic was a parallel,
weaker instrument that would have disagreed with it in September. **Nothing that cuts a window may
key on a date.**

### The daily-publish change, and why we are clean

Crucible began publishing `universe_tickers_*.json` **daily at 06:05 from 2026-08-11** (a heartbeat
so QuantIQ's chain producer can distinguish "unchanged" from "publisher stopped"; their staleness
budget went 45d → 5d on it). They flagged the risk that a consumer keying on **file identity or
mtime** would read a daily basis change that is not one.

**Verified in code: we do not.** `_load_underlyings()` resolves the pool through
`_load_universe_tiers_cached()` and returns a **sorted ticker union**; `universe_fingerprint()`
(D078) hashes that *content* plus the tier-3 split. Byte-identical daily republishes therefore
produce an identical fingerprint. The two mtime-ordered globs in the tree read **different files** —
`registry_snapshot_*.json` (`registry_loader`) and `chain_inception_floors_*.json`
(`chain_inception`) — neither is the universe export. **No change required.**

Worth stating rather than assuming: this is the *content-fingerprint-over-calendar* principle
paying off twice in one relay — it is why the daily cadence is a non-event for us, and it is the
same reason the calendar boundary above had to go.

### Effect on the signed freeze (D390): none, and the window it validated is unchanged

`3b0cbca7ae17` read inside basis `e1adced727678c8f` on windows 12–17, all basis-clean, with zero
rows on any other basis since the cohort cut. The correction moves the *end* of that basis from
09-01 to on-or-after 09-03 — **later, i.e. more headroom, not less** — so the read sat even further
inside its era than recorded. The prereg's own text says the basis "ends at their next re-rank,
scheduled for the first trading day of September, 2026-09-01"; that clause is **factually wrong and
is corrected here**. The registry entry is left as written, because a resolved preregistration is an
immutable record and correcting it in place would be exactly the kind of after-the-fact edit the
whole instrument exists to prevent. The correction lives here and in `STATUS.md`.

## D392 — **Both D389/D390 gaps CLOSED: the signed freeze is now structurally enforced, and a registered read can no longer come due silently or be taken and lost.** Guard + watcher + `--resolve`, TDD, 16 new tests.

**Date:** 2026-08-14 · **Class:** instrument (governance enforcement) · **Follows:** D389, D390, D391

Both gaps were logged in D390's "not done here" rather than assumed away, and both are the same
class: **a control that exists as a sentence rather than as a mechanism.** D389 found a watcher
described as armed with no unit behind it; D390 signed a freeze that nothing read. Crucible hit the
same class twice in one week and the agreed disposition — **arm it or delete the claim** — is what
this implements.

### Gap 1 — `scripts/check_freeze_governance.py` (pre-commit hook `freeze-governance`)

Once the declaration's status line reads SIGNED, a **content** change to `config/grammar.yaml` is
refused unless an **open preregistration with a stated required n** exists. That is the sequencing
half of declaration §6 — prereg *before* the edit — and it is the half a machine can check.

**Deliberately not enforced:** goldens re-pinned, emission proof, funnel attribution, STATUS block.
Those are judgements about whether work was done *well*, not facts about whether it was *sequenced*
correctly. A hook pretending to check them would give false assurance — the exact failure it exists
to fix.

**The reopener escape is shaped so it cannot be used silently.** §5 reopeners are first-class, so
`FORGE_FREEZE_REOPENER=D###` overrides — but only when the same commit stages a `## D###` header in
the Decision Log. An override that leaves no permanent record is a hole; one that must leave a
D-entry is an escape hatch. Verified live against the real repo: refused a grammar edit with no
prereg, and refused an override with no staged entry; `config/grammar.yaml` restored byte-clean.

**Inertness properties, both tested:** the guard is inert before signature (a freeze must not be
retroactive) and inert when no declaration file exists (a guard that crashes in a fresh checkout
blocks every commit). A test asserts the *live* declaration still parses as signed, so the guard
cannot go quietly inert if the document is retitled.

### Gap 2 — `scripts/freeze_read_watcher.py` + timer, and `--resolve` on the read tool

**The watcher** reports, per open prereg: DUE (exit 1), waiting with the remaining count (exit 0),
or **UNWATCHABLE** (exit 2) when the registration carries no machine-readable clock
(`watch: {n, basis_fp}`). That third case *is* the D389 defect — the failure was never a broken
watcher, it was a claim no watcher could have checked. The unit deliberately carries **no
`SuccessExitStatus`**, unlike `forge-healthcheck`, so both conditions mark it failed and surface in
`systemctl --user --state=failed`: a watcher whose warning is swallowed is indistinguishable from
no watcher.

**It never computes the metric** — it counts rows and compares fingerprints. Deciding whether to
page by peeking at the answer would BE the read. Counts are basis-scoped in SQL, so a foreign-basis
backlog can never make a read look due (the D387/D391 failure shape), and that is asserted by test.

`forge-prereg-watch.timer`: daily 06:30, `Persistent=true`, reusing a ≤12h snapshot so the 7.5 GB
copy costs at most once a day. **Installed, enabled and smoke-run: `Result=success`,
"no open preregistrations — nothing to watch."**

**`--resolve`** on `freeze_registered_read.py` writes the outcome through the repo's own
`resolve_preregistration`, so a read that is taken is a read that is recorded — `3b0cbca7ae17`'s
resolution had to be entered by hand (D389). Without the flag the tool now prints
`[not recorded] ... the registry is UNCHANGED`, so the silent case is at least a loud one. A leg
that could not be read resolves `insufficient`, never `refuted`: "not enough data" must be a
different outcome from a verdict, or an early read that happens to pass is indistinguishable from
peeking-to-threshold.

### Verification

16 new tests (10 guard, 6 watcher), TDD red→green; 58 script tests and 184 unit+invariant tests
pass; `ruff` clean; `mypy --strict` clean on 107 files. The single-read guard was re-confirmed live:
re-running the within-basis read now aborts with `status is 'confirmed', not 'registered'`.

## D393 — **Crucible's §8 Step 2 close-out: neither generation nor refit triage binds component production.** Their §5 `rank_k=20` residue is a re-derivation of their own 2026-07-22 root-cause, which we shipped as v48 the same day. One open question returned; one pushback registered.

**Date:** 2026-08-14 · **Class:** cross-system finding (no code change) · **Follows:** D328/v48, D390, D392

### What they answered

Our 08-06 §8 Step 2 ask — *is newest-first refit ordering deliberate under the doubled capacity?*
— was already answered by action. They shipped a quality sub-lane on 2026-08-06, the day after the
relay: a reserved sub-budget goes to the best margin over both binding bars, floor-gated at −0.3.
Measured over 44h: **quality lane 2.5% of volume → 6.30% promote rate; newest-first 97.5% → 0.03%.
206×. 2.5% of the budget produced 84% of the promotes.** Our hypothesis was right and the effect
is larger than we argued.

**And more of that lane buys nothing.** They raised its share 20% → 80%, measured no effect, and
reverted the same day: the lane finds 0–3 eligible candidates per pass, so the 8-slot budget was
never binding. **"Refit our best 2,000" turned out to be already executed** — 1,736 of 3,256
above-floor candidates ARE components, 1,460 more have children in flight, and the un-consumed
above-floor supply is **three rows**.

**Both candidate answers to "what binds component production" are now closed: not generation
(our finding), not refit triage (theirs).**

### Their §5 residue is our v48, three weeks late

They report the un-convertible residue as 17 configs of one shape — tier-2 `rank_k=20`, at 100%
chain coverage, refused by a `_rank_chain_floor` demanding `2 × rank_k` tier members (40) on a
20-name tier. **That is verbatim the mechanism they root-caused for us on 2026-07-22**
(`FORGE_coverage_gate_rootcause_reply`), and which we shipped the same day as grammar **v48**
(`2160149`, under the D328 freeze programme): `_RANK_K_CHOICES (5,10,20) → (5,10)`.

Verified against a live snapshot rather than asserted from the constant:

| rank_k | tier | n | last submitted |
|--:|--:|--:|---|
| 20 | 2 (long_only) | 31,640 | **2026-07-22** |
| 20 | 2 (long_short) | 31,527 | **2026-07-22** |
| 20 | 3 | 4 | 2026-07-20 |
| 10 / 5 | 2 | 493,408 | 2026-08-14 (current) |

**63,171 `rank_k=20` configs ever; zero since 2026-07-22.** Their 17 are a closed cohort drawn
from a frozen pool — it cannot grow, and no ordering or budget change on their side could ever
have reached it. **No action required on our side.**

*The recurrence itself is worth recording:* the same mechanism was derived twice, three weeks
apart, from opposite ends — a coverage-label starve on ours, a refit residue on theirs — and the
second derivation did not connect to the first. Same shape as our own D386 (a rule generalised
from one cooperative observation, re-derived later without noticing it was settled). Neither side
has a searchable shared record; naming mechanisms rather than symptoms is what made the two
recognisable as one thing.

### One pushback, registered rather than silently accepted

They recommend `rank_k ≤ 5` two-sided for "genuinely selective" tier-2 configs, because
`10 long + 10 short` covers the whole 20-name tier. **We think that conflates inclusion with
selection, and only for the two-sided case.** `long_only` `rank_k=20` is genuinely degenerate —
buy all 20 of 20, the ranker cannot affect the portfolio. But `long_short` `rank_k=10` includes
every name while the **ranking still decides which side each is on**: that is standard
dollar-neutral cross-sectional construction, where full-tier coverage is a feature and the alpha
is the spread.

**Returned as a question, not an assertion:** is the `2 × rank_k` floor protecting against
*inclusion breadth* (two-sided full-tier is then fine) or against *cross-sectional dispersion
being unmeasurable at n=20* (then `≤ 5` is right)? We decline to tune generation against a floor
whose purpose we have inferred — that is precisely the D361 failure. If they confirm the
dispersion reading, the bound is cheap.

### The freeze's first live test

Their finding landed hours after D390's signature, making it the first external ask to hit a
frozen grammar. If the dispersion reading is confirmed, a `rank_k ≤ 5` two-sided bound is a
prereg + version bump + D-entry, and it is a **tightening** — hard rule #4 permits it without the
loosening path, and D392's hook will require the prereg first. **The honest test of the freeze is
whether it processes a real change correctly, not whether it prevents one.**

### Their two withdrawals

The 3,252 backlog and the ~190 expected promotes are withdrawn by them and were never load-bearing
here. Recorded because the correction shipped in the same message as the finding it undermined,
unprompted — the same discipline as their cadence disclosure.

## D394 — **The floor is INCLUSION BREADTH, cited not inferred; Crucible withdraws the `rank_k ≤ 5` two-sided recommendation. We do NOT act on their new `k=5` evidence either — the v51 tombstone documents this exact collider on this exact axis. Margin-stratified read requested.**

**Date:** 2026-08-14 · **Class:** cross-system finding (no code change) · **Follows:** D393

### The answer

Our returned question — inclusion breadth or cross-sectional dispersion? — has a documented answer:
**inclusion breadth.** Quoted from their DESIGN.md §20 `regime-coverage-rank-parity` (operator
decision 2026-06-09): `n_min = 2 × rank_k`, *"per-config, so a top-20 config needs 40 rankable
names before ranking is a selection rather than an enumeration"* — and the rejected-alternatives
column rejects a fixed global N=40 as *"over-strict for rank_k=5 configs"*. It is a **data floor**
whose output is a window start; nothing in it estimates dispersion.

**Our D393 §2 reading was correct** and the `≤ 5` two-sided recommendation is **withdrawn by
them**, unprompted: *"do NOT spend the freeze's first increment on it."* Asking rather than
inferring cost us nothing and saved a version bump — the D361 discipline paying for itself.

### The new evidence, and why we are NOT acting on it

They measured stage-two outcome by shape after sending the earlier relay:

| tier | rank_k | mode | children | promotes | rate | component rate |
|--:|--:|---|--:|--:|--:|--:|
| 2 | 10 | long_only | 24,363 | 39 | 0.16% | 92.0% |
| 2 | 10 | long_short | 21,318 | 37 | 0.17% | 84.9% |
| 2 | 5 | long_only | 14,848 | 6 | 0.04% | 94.0% |
| 2 | 5 | **long_short** | **9,899** | **0** | **0.00%** | 72.2% |

`P(0 | ~17 expected) ≈ 4e-8`. Their own caveat, volunteered: stage two is a collider, so *"take
the retraction as solid and the ranking as suggestive."*

**We agree, and our own record makes it sharper.** The `_RANK_K_CHOICES` tombstone records that
**v50 shipped a rank_k=5 bias and v51 reverted it the same night**, because Crucible's honest-arm
evidence was collider-biased and they retracted it in full
(`CRUCIBLE_URGENT_rank_k_finding_was_COLLIDER_BIASED_2026-07-25`). The mechanism we reproduced on
our own ledger then is the mechanism operating now: *"stage-two admission is the refit TRIGGER, a
function of config quality, so conditioning on it is a collider."* **Same axis, same source, same
conditioning structure, and we have already shipped-and-reverted once on it.** A second grammar
change on stage-two rates without stratification would be repeating v50 with the sign flipped.

**Direction, in fairness:** their finding *agrees* with v51's post-retraction understanding that
k=5 is the worse value, so this is corroboration rather than a new claim. And 0 of 9,899 is a far
starker fact than the median comparison v50 rested on. It is the **attribution to shape**, not the
count, that the collider threatens.

**Requested instead of acting:** the promote rate for `rank_k=5 long_short` **stratified within
their existing parent-margin buckets** (they already publish 31.5% / 13.9% / 5.6% / 3.1% / 0.6% /
0.01%). Zero within every bucket is shape; concentration in the low-margin buckets is selection.
That read breaks the collider and would make the tightening registrable.

**Our exposure if it is confirmed:** `rank_k=5 long_short` is **17.9% of post-v48 xsect flow**
(48,596 configs since v48), so this is worth resolving properly rather than quickly.

### Two notes back

- **Their mechanism claim cuts further than they drew it.** They report the cross-sectional edge
  *"behaves like an equity factor rather than a name-selection edge, which is exactly why
  narrowing toward real selection removes the mechanism."* If that is right, maximum inclusion is
  the productive direction — which is what their own floor refuses for `long_only rank_k=20`.
  Raised as a question, not a claim: is the floor protecting a **data** requirement that happens
  to bind hardest on the shape their promote data likes best?
- **Our D393 §1 numbers held on re-check:** 63,171 `rank_k=20` ever, last at 2026-07-22 15:45:10Z,
  **zero on or after 07-23**. The 964 dated "after 07-22" in a coarse query are same-day
  pre-deploy submissions, not a leak.

### Adopted from their §3

They commit unilaterally to citing the §20 entry when a finding touches a mechanism, or stating
explicitly that they looked and found none — converting silent inference into a checkable claim.
**We adopt the mirror**: a Forge relay asserting anything about *their* internals cites the source
or says it is an inference. Their framing is the durable one: **"a mechanism you can re-derive is
not evidence that it is unrecorded."**

## D395 — **`second_gate_contrast.py` no longer pools across `measurement_basis`** (the D360 defect, the last item open in the freeze declaration §7). Conclusion unchanged; numbers sharpened.

**Date:** 2026-08-14 · **Class:** instrument fix · **Follows:** D392, D394

**The defect.** The tool's query filtered `selection_mode` and `hypothesis` and never
`measurement_basis`, so a config carrying both a stage-one verdict and a later `fullhist_refit`
verdict landed **twice, on two different bases, in the same cell**. That is not double-counting
noise: stage-one and full-history `decision` answer different questions, and the refit population
is *selected* — it is what a scanner chose to refit. The denominator became a mixture whose
composition varies per cell, which silently breaks the tool's own stated premise that its three
arms "share the SAME base and differ only in what occupies the optional second slot."

**The fix.** Query extracted to a module constant with
`AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'`, plus a testable `fetch_rows()`.
`IS DISTINCT FROM` rather than `!=` so a **NULL basis is KEPT** — NULL is stage one, and `!=`
would drop it, shrinking the honest arm just as quietly as the pooling inflated it. Same
convention as `freeze_tail_reading._QUERY`, deliberately: two instruments disagreeing about what
the honest population is would be worse than either being wrong alone. The output header now
states the basis, so a pasted table cannot be misread later.

**Three tests** (TDD red→green): `fullhist_refit` rows excluded, NULL-basis rows kept, and the
query still carries the clause — the last one so a future edit cannot silently drop it.

**⚠️ THE CONCLUSION DOES NOT CHANGE, and that is worth stating rather than implying otherwise.**
Re-run on the live snapshot, stage-one only:

```
  hurst ALONE (slot unused)   n=8622   13.7%   (baseline)
  hurst + days_since_jump     n=4768   29.8%   z +22.59
  hurst + vix_term_slope      n= 884    8.1%   z  -4.63
```

D339's finding stands in full: **double-gating is not generically harmful** (the veto arm is
+22.59), and the problem is **specific to `vix_term_slope`** (8.1% against a 13.7% baseline, and
3.7× worse than the veto arm — against 3.2× on the pooled numbers). The defect moved the
magnitudes slightly and inverted nothing.

Closes the last open item in the freeze declaration §7.

## D396 — **QuantIQ's DTE-lattice ask, answered: our grid is unbiased (240/240 pairs, uniform) and the trade-count channel their thesis needs is ABSENT (corr +0.006). But there is unexplained cpcv structure across `dte_max` that we report rather than explain away.** Diagnostic only; no change proposed against the frozen grammar.

**Date:** 2026-08-16 · **Class:** cross-system diagnostic (no code change) · **Follows:** D390, D395

**The ask** (`FORGE_DTE_LATTICE_RELAY.md`, QuantIQ D504): book `7f2a697ec6c1b119`'s weekly trend
leg selects 72–84 trading-day DTE; for the 2026-08-17 rebalance only 1 of 184 underlyings lists a
contract in that window, because it falls between the Nov-20 and Dec-18 monthlies. Verified by
them against IBKR — a real lattice wall, not a data gap. Their question: **is 72–84 an edge or an
expiry-lattice alias?** Their §4 sub-question is the one that is ours: *is the search grid itself
lattice-aligned?*

### §4 answered: no grid-side bias

`swing_long`'s §3.5 P2 window is **(60, 90) trading days**; the sampler draws
`dte_min = randint(60, 75)`, `dte_max = randint(76, 90)` — **uniform over integers**, no coarse
grid. On 155,136 emitted `swing_long` trend configs: **240 of 240 pairs emitted**, per-pair counts
mean 646 / min 527 / max 787 against 646 expected, and the pinned **(72,84) drew 603 = 0.39%,
below the mean.** Whatever selected that pair selected it downstream of generation.

**Unit check run and clean:** we suspected a calendar-vs-trading-day mismatch (the symptom fits
one). `crucible_contracts.SelectorSpec` states it outright — trading-day DTEs, converted at the
Crucible boundary. Their reading is correct.

### The mechanism their thesis needs is measurably absent

Fillability would reach outcomes via **trade count → the min-trade gate**. On the honest arm,
stage one, n=38,661: mean trades rise **smoothly and monotonically** with `dte_max` (492.8 at 76 →
745.7 at 90 — mechanical, since `dte_max=76` forces a narrow window), the min-trade gate passes
**98.4–99.3% at every value**, and **corr(mean trades, component rate) = +0.006**. A 33.9% serve
rate still yields 500–750 trades over 8 years, so unfillable name-days thin the sample without
starving the gate.

### ⚠️ What we could NOT explain, recorded rather than dropped

Component rate and mean cpcv show the same shape across `dte_max`, unexplained by trade count:

```
  dte_max   76    77    78    79    80    81    82    83    84    85    86    87    88    89    90
  comp%   25.3  27.9  30.1  31.6  30.1  32.8  31.2  30.1  31.1  29.4  26.1  27.6  26.9  27.4  28.2
  z      -4.24 -1.31 +1.23 +2.86 +1.11 +4.13 +2.39 +1.24 +2.33 +0.39 -3.32 -1.66 -2.37 -1.86 -0.93
```

A plateau at 78–85 with depressed edges; `76` (−4.24) and `81` (+4.13) clear Bonferroni at 15.
**The pinned `dte_max=84` sits inside the elevated plateau (+2.33)** — exactly the configuration
their question was built to detect. **Not attributed**: the trade-count channel is ruled out, and
the shape could be economic, a different artifact, or the narrow-window edge effect at 76
contaminating the low end. **Their instinct was right even though the mechanism they proposed is
not the one operating**, and a negative result on the proposed mechanism is not a licence to drop
the residual.

### Routed, not taken

The walk-forward (`dte_max ∈ {80,84,88,92}`, D493-style retention) is a **stage-two instrument and
therefore Crucible's**. Two notes passed on: **`dte_max=92` is outside our grammar** (P2 caps
`swing_long` at 90, so it has never been emitted and cannot be without a §6 increment against the
frozen grammar); `{80,84,88}` and `dte_min ∈ {68,72,76}` are all in-grid.

### Incidental: D493 closes our equity-package open item

Their cross-ref records **the k=2.0 chandelier failing its knife-edge criterion (neighbours
retained <50%)**. We disclosed that sensitivity when we sent the package (k=3.0 scored 0.7459
against k=2.0's 1.1837) precisely because we could not test it; **their added acceptance criterion
is what caught it**, and it never reached production. Criterion adopted into our standards (D391).

**↳ 2026-08-16 — CORRECTION to the D396 relay, caught by QuantIQ.** Our §4 note said
`dte_min ∈ {68, 72, 76}` was "all in-grid" for the neighbourhood probe. **76 is OUT of grid:**
the sampler is `dte_min = randint(60, mid)` with `mid = (60+90)//2 = 75`, so 60..75 inclusive, and
**0 of 158,459 emitted `swing_long` configs carry `dte_min=76`.** It fails for exactly the reason
their `dte_max=92` does, one bound up instead of one bound down.

**The aggravating detail, recorded because it is the useful part:** the query output quoted in that
same relay printed `dte_min range emitted: 60..75` two lines above the claim. The sampler was read
correctly and measured correctly, and then their three candidate values were passed through without
being checked against the range just printed. Correct probe values: **`dte_min ∈ {68, 72, 75}`**;
`dte_max ∈ {80, 84, 88}` stands.

Three bounds errors in one fortnight across the three repos — our `76`, their `92`, and Crucible
re-deriving a `2 × rank_k` rationale written in the comment above the constant — **all found by
re-reading a record already in the room.** The corollary to Crucible's 08-14 line: *a mechanism you
can re-derive is not evidence that it is unrecorded*, and **a bound you can restate is not evidence
that you checked it.**

QuantIQ's reply otherwise accepts D396 in full: grid uniform (240/240, pinned pair below mean),
their fillability→trade-count mechanism **dead** (corr +0.006), `dte_max=92` withdrawn, and the
walk-forward routed to Crucible with in-grid values and our residual table as motivating evidence.
The residual is **narrowed, not answered** — not the grid, not trade count, `84` at z=+2.33 inside
the 78–85 plateau.

## D397 — **The `dte_max` plateau SURVIVES stratification (mix channel excluded); Crucible's `rank_k=5 long_short` zero does NOT survive theirs. We register nothing.** Two findings tested against the same lesson in one afternoon; one died, one lived.

**Date:** 2026-08-16 · **Class:** cross-system diagnostic (no code change) · **Follows:** D394, D396

### The challenge, and it was a fair one

QuantIQ, cc'd on Crucible's stratified read, held the walk-forward and asked: D396's plateau is a
**pooled** component-rate readout, and Crucible had just shown component rate tracks the parent
population rather than the thing it names. Was the `dte_max` sweep stratified, or pooled? It was
pooled.

### The test: the plateau survives

The stage-one analogue of parent-margin is the honest arm's own composition — `holdout` (prefilter
survivors) vs `prefilter_sample` (prefilter rejects) — since a mix varying with `dte_max` would
move pooled component rate mechanically.

```
  holdout share by dte_max        : 1.6% .. 3.0%  (spread 1.4pp, no trend)
  WITHIN prefilter_sample  n=37,751  rate 29.5%  max|z| 4.47
     mean z: edges 76-77 -2.81 | plateau 78-85 +2.00 | edges 86-90 -2.07
  WITHIN holdout           n=910     rate 11.5%  max|z| 1.59   (no power: ~7 comps/bucket)
```

**Intact inside the dominant arm on its own. The mix channel is excluded.**

**Structural note, offered as a limit on our own claim rather than a rebuttal:** their collider was
**stage-two admission** — the refit trigger, an explicit function of quality, with the outcome
measured downstream. Ours is a stage-one outcome on an arm drawn **at random from prefilter
rejects**; there is no admission step between sampling and measurement, which is what the honest
arm exists to guarantee. That makes their specific collider structurally unlikely here — but it
does not make the residual real.

**Three channels now excluded — grid, trade count, arm mix — and the shape is still unexplained.**
Stronger than D396 could say; weaker than "the residual is a finding". The low edge at `dte_max=76`
remains partly mechanical (it forces a narrow window), but **width does not explain the high edge**:
86–90 are the widest available and are also depressed, so a monotone width story does not fit.

### Crucible's k=5 zero does NOT survive — tightening NOT registered

Their stratified read, run at our request, killed their own finding:

```
  expected on 10_LS within-bucket rates : 2.06
  observed                              : 0
  P(0 | 2.06)                           : 0.127    NOT SIGNIFICANT
```

Zero children in the `>= 0.0` bucket where every other shape promotes at 18–33%, and **99.2% in
`< -0.5`** where nothing promotes. **Not a worse shape — a differently-sampled one.** `rank_k=5
long_short` keeps its 17.9% of post-v48 xsect flow, and **D394's decision to decline was the v51
tombstone doing its job, not foresight** — the pooled 0-of-9,899 (P ≈ 4e-8) was the starker-looking
number and the wrong one.

### Net

Two findings, same lesson, same afternoon: theirs died under stratification, ours lived. **Neither
side knew which in advance, which is the only reason the test was worth running.** Walk-forward
unblocked from our side at `dte_max ∈ {80,84,88}`, `dte_min ∈ {68,72,75}`. Nothing registered,
grammar frozen, zero open preregistrations.

## D398 — **DTE walk-forward verdict: PLATEAU — the pin is robust, 33.9% is a capacity fact. Two corrections back: our table is stage ONE (settled by construction), and `dte_max=88` is NOT our grid edge. Our population independently argues against `(72,88)`.**

**Date:** 2026-08-16 · **Class:** cross-system finding (no code change) · **Follows:** D396, D397

### Their verdict

All 9 cells ran. **Neighbour median 0.8875× certified, 8 of 8 above 0.25×, zero unmeasurable, zero
zero-trade folds → PLATEAU** on the rule fixed before any result. QuantIQ's question answered in
the form asked: **the `swing_long` leg's 33.9% served-name-day fraction is a capacity fact, not a
defect**, and a low forward trade count on that leg is the shape working as certified.

**They honoured both registered clauses at real cost.** `(72,88)` scored **1.7943 against the pin's
1.4057 — 1.28×** — and NO-PROMOTION plus NO-WIDENING bound for the first time with something behind
them. No adoption, no proposal, no increment sought. Geometry: `dte_min` is the live axis and the
pin's 72 is best of three; `dte_max` is flat-to-rising.

**Their §5 independently reproduces our `corr = +0.006` at component level** — trades rise
monotonically as the window widens (2,540 → 5,781) while Sharpe peaks at `dte_min=72` in every
`dte_max` column. Same conclusion, different instrument, different level. They also self-corrected
an interim read (that widening buys trades while Sharpe falls) that six of nine cells supported and
the full grid refuted, before anyone could quote it.

### Correction 1 — our table is stage ONE, settled by construction

Their §4 caveat characterised D396's plateau as a **stage-two** component rate whose admission step
is the refit trigger. It is not. QuantIQ adjudicated by arithmetic; we settled it at query level:

```
  WHERE s.selection_mode IN ('holdout','prefilter_sample')
    AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
  n = 38,661   prefilter_sample 37,751   holdout 910   fullhist_refit rows: 0
```

**The basis filter is in the WHERE clause**, so stage-two rows cannot be present — the count is 0
because it is excluded, not by luck. `prefilter_sample` is random-from-prefilter-rejects, so there
is no admission step between sampling and outcome. **Their registered clause is untouched** (it
never depended on the claim), and the stratification they asked for was run anyway (D397) and the
plateau survived.

### Correction 2 — `dte_max=88` is not our grid edge, and it is ours to correct

Their §4: *"88 is the grid edge (P2 caps at 90), so we cannot see whether it is a peak or a slope."*
The two clauses disagree. **P2 caps at 90; 88 was the edge of their PROBE, not of our grammar:**

```
  dte_max=88: 10,089 emitted   dte_max=89: 10,265   dte_max=90: 11,530
```

The peak-or-slope question is answerable inside the frozen grammar with no widening and no
increment — which changes the epistemic situation but not their decision, and the decision is
theirs. **Fourth bounds slip this fortnight across three repos** — our `dte_min=76`, QuantIQ's
`dte_max=92`, their `2 × rank_k` rationale, this — every one found by re-reading a record already
in the room.

### What we added: our population argues against `(72,88)`

They declined `(72,88)` on registered principle at a 28% cost. **Our sweep independently supports
the call.** Across the whole `swing_long` trend population (honest arm, stage one), `dte_max`
**86–90 is the depressed region** (z −3.32 / −1.66 / −2.37 / −1.86 / −0.93) while 78–85 is
elevated. `(72,88)` sits inside the depressed band. Different objects — one certified window versus
a population — so not a refutation of their cell, but the opposite of corroboration, and it should
ride alongside the 1.28× if anyone ever revisits it through the normal gates.

**Nothing asked, nothing proposed, no increment sought. Grammar frozen, zero open preregistrations.**

**↳ 2026-08-16 (later) — QuantIQ finds a metric disagreement in Crucible's own table; we supply a
third measurement on the same axis.** Their reading: `(72,88)` beats the pin by 28% on
walk-forward and is **17.3% WORSE on cpcv** (0.8732 vs 1.0559), and across the grid the two metrics
**disagree in direction** on `dte_max` — cpcv declines monotonically (0.9492 → 0.7926 → 0.6420)
while wf rises to a peak at 88. Both agree `dte_min=72` is the peak. Their conclusion: the
no-widening clause forwent a **metric-selection artifact**, not a 28% improvement, so §3's cost
estimate overstates it.

**Our contribution — mean cpcv at their exact three probe points**, `swing_long` trend, honest arm,
stage one, ~2,500 configs each:

```
  dte_max                   80        84        88
  Crucible grid  cpcv       0.9492    0.7926    0.6420    monotone decline
  Forge population cpcv     0.3089    0.3268    0.2865    peak at the PIN
```

Levels are not comparable (different stage, population, normalisation) — only orderings are.
**AGREEMENT on the comparison that bears on the clause: 88 is the worst of the three on cpcv in
both.** **DISAGREEMENT: ours puts 84 > 80, theirs 80 > 84** — so the monotone decline is not
reproduced at population level; our shape is a peak at the pin, not a slope through it.

**QuantIQ's §5 caution accepted without qualification:** a three-point axis cannot resolve our
78–85 plateau against depressed 76–77 / 86–90 edges, and the two are different stages on different
populations — *"they neither confirm nor contradict each other."* Reported as a third measurement,
not as corroboration. **Second time in two days one of them has correctly warned against
over-reading our residual** (the first was the stratification challenge, which the plateau
survived). Three channels excluded, residual unexplained, unchanged by the verdict.

The `seed=0` provenance ask is Crucible's; nothing owed by us. Noted for reuse: QuantIQ's line that
amending a **basis** toward verifiable ground truth is defensible where amending a **decision rule**
toward a desired result is not — the cleanest statement of that boundary written in this exchange.

**↳ 2026-08-16 (close-out) — Crucible accepts all three corrections; NOTHING ASKED OF US, no reply
sent.** (1) **Stage one CONFIRMED, their §4 withdrawn** — not narrowed, not re-stratified:
*"My concern was not merely unproven, it was misdirected — it described an instrument you were not
using."* They record the mechanism against themselves: D396 stated *"stage one only, n=38,661"*
three lines above the table they quoted, and the pull was the `comp%` header — **"component" is a
stage-two verdict in their vocabulary, so they resolved our label against their own glossary.**
Same shape as their `2 × rank_k` and XLRE errors: a label read through the wrong dictionary with
the right one two lines up. (2) **`dte_max=88` was their probe's edge, confirmed from our counts**
(10,089 / 10,265 / 11,530 at 88 / 89 / 90); the peak-or-slope question is answerable inside the
frozen grammar with no increment — *"changes the epistemic situation and not the decision"*, and
§3's metric disagreement is now their reason instead of the grid-edge claim, which is a better one.
(3) **cpcv reading confirmed and reproduced; their §3 "28% cost" framing withdrawn** — the clause
forwent a metric-selection artifact. One correction back to QuantIQ: `(72,88)` is the worst cpcv
cell in its row, not second worst.

**Seed provenance (QuantIQ's ask, not ours), answered with a volunteered weakening:** read from the
certified artifact with no schema default, **but 0 is the fleet-wide value, so it does not evidence
a per-run choice** — stated rather than implied.

**Verdict UNCHANGED: PLATEAU. Pin stands at (72,84).** Our two corrections are absorbed, the
residual is untouched, and no reply is owed. Grammar frozen, zero open preregistrations.

## D399 — **ALERT RELAYED: Crucible's stage-two refit scan is OOM-failing since 2026-08-22; we measure −18% to −30% throughput from our own ledger.** Found during a routine sweep; unalerted by either side's monitors. No change made — their service.

**Date:** 2026-08-24 · **Class:** cross-system alert (no code change) · **Follows:** D393, D398

### The failure

`crucible-fullhist-refit.service` (stage-two refit scan) exits 1 with:

```
  RuntimeError: DB writer rejected request:
  Out of Memory Error: failed to pin block of size 256.0 KiB (27.9 GiB/27.9 GiB used)
```

**Intermittent, not stopped** — 2026-08-24: 65 runs finished, 28 failed; a success at 13:51 sat
nine minutes before a failure at 14:00. Degrading rather than down, which is the shape least
likely to be noticed. Onset sharp: **zero systemd failures 08-19/20/21, then 11 / 31 / 28 on
08-22 / 23 / 24.**

### The measured impact, from our ledger

Stage-two verdicts (`measurement_basis='fullhist_refit'`) per UTC day, live snapshot 08-24T22:2xZ:

```
  08-14..08-21   flat baseline ~5,760 refits/day, ~4,950 components
  08-22          5,560 / 4,857     <- failures begin
  08-23          4,720 / 4,088     <- FULL day: -18% refits, -17% components
  08-24          3,800 / 3,336     <- 94% of the UTC day, ~-30% run-rate
```

**08-23 is the clean full-day comparison at −18%; the trend is worsening, not settling.**

### Why it was relayed rather than filed

- **Believed unalerted.** Our standing note on their fleet: the health monitor checks runner
  shards; writers, watchers and publishers are not covered. This is a writer-side OOM.
- **It bears on a conclusion both sides signed off ten days ago.** Their §8 Step 2 close-out
  (D393) — *"refit triage is not the lever; un-consumed above-floor supply is three rows"* — was
  measured ~08-14 with the scan completing 5,760/day. **Not a claim that the finding was wrong:
  a claim that it was measured on a rig that has since lost a fifth to a third of its
  throughput**, and "we have consumed your best supply" is exactly the kind of statement that
  stops being true quietly when the consumer slows down. Whether it needs re-reading is theirs.
- **Their service; untouched.** No config changed, nothing restarted, no fix proposed — the
  DuckDB guidance in their own log is better informed by their workload than by us.

Offered: the per-day series at any granularity as an independent check on their counters, and a
daily re-read reported only if the trend changes. **No ask, nothing blocking on us.**

**Recorded about the discovery itself:** this surfaced during a routine "anything left to do"
sweep of `systemctl --state=failed`, not from any monitor. Both sides have now been bitten by the
same class twice in a fortnight — D389's unarmed watcher, and this. **The health-monitor coverage
gap (runner shards only) is worth treating as a standing hazard rather than a footnote.**

## D400 — **Q62 CLOSED: the six-stream triage.** Five of six are PARK-with-a-reason; the sixth (`selector_spread_bind`) is structurally unavailable as a verdict feature **but its hazard class is live and larger on a different axis — our training frame pools four measurement bases with a 17× base-rate gap, and the remedy (`honest_scope`, D331 Part B) has been built and never flipped.** Operator decision surfaced; no code change made.

**Date:** 2026-08-24 · **Class:** ranker design triage · **Follows:** D331, D132/F1 · **Closes:** Q62 (open since 2026-08-06)

### The triage

QuantIQ's ask (2026-08-03): which of six live streams earn features / labels / era splits in the
two rankers. Our answer, against `ranking/features.py` + `ranking/dataset.py`:

| # | stream | verdict | reason |
|---|---|---|---|
| 1 | `live_arrival_spread_pct` | **PARK** | our estimand is `P(component)` — a *backtest gate* outcome. Live fill data cannot predict a backtest gate. Their own framing agrees ("if your rankers ever grow fillability/cost features"). |
| 2 | `selector_spread_bind` | **see below** | structurally unavailable as a verdict feature; hazard class live elsewhere |
| 3 | `deployment_sizer_modes` | **NO CHANGE** | we do carry `feats["sizer=<mode>"]`, but it describes the **certified config at gate time**, which is the correct object for `P(component)`. The overlay is what *trades*, not what *gates* — it would matter only if we trained on deployment outcomes, i.e. stream 4. |
| 4 | designation WIN/LOSS | **PARK on N** | 147 `promote` rows in the entire clean-era frame; designations are a handful. Cannot support supervision. Retained as a monitoring signal. |
| 5 | live fill/abandon | **PARK on N** | first negative fill labels, small N by their own account. Same gate as 4. |
| 6 | wings-quote staleness | **ADOPTED as a constraint** | recorded as a precondition on any future spread feature: supplement-provenance quotes older than one session are unusable; `cboe_forward/eod` is the fresh source. |

### Stream 2, and what looking for it found

**`selector_spread_bind` cannot be a per-row verdict feature.** At our pinned contracts
**1.44.0** it lives on `PromotedPortfolio` (alongside `deployment_sizer_modes`), not on
`GatedRun`/`RunResult`, so it never reaches the `verdicts` rows `build_dataset` trains on. That is
a structural fact about where the field sits, not a judgement about its value.

**But the hazard they named is live, on a bigger axis.** Measured on the clean-era frame:

```
  measurement_basis    rows       positive-decision rate
  standard_window      386,246     5.0%
  (null)               333,742     9.6%
  fullhist_refit       148,333    86.2%      <- 17.1% of the frame, 17x the screen rate
  selection_pbo             18     0.0%
```

`build_dataset`'s SQL selects no `measurement_basis` and applies no filter on it. **Stage-one
screen verdicts and stage-two refit verdicts are pooled with no basis feature and no era split**,
and the two answer different questions — which is precisely the "different measurement bases …
the gate-pass label means something different on each side" hazard QuantIQ raised for spread-bind.

**This is already known and already solved — and the solution has never been turned on.** D331
Part B added `build_dataset(honest_scope=...)`, whose docstring states the problem in more detail
than we could reconstruct: the screen lane *structurally cannot* produce an honest-coverage
component, so **91.0% of the frame is labelled NEGATIVE regardless of quality**, and the same
`config_hash` appears in both lanes with **opposite labels** (26 of 363 paired configs). Scoping
keeps the same 19,759 positives on 35,674 rows — prevalence 4.988% → 55.4%, an **11× lift**.

**Verified OFF in production:** not in `forge.service`'s `Environment`, not in
`scripts/daily_ranker_eval.sh` or `forge-ranker-eval.service`, and absent from the live daemon's
`/proc/<pid>/environ`. The flag has never been flipped.

### Why this is an operator decision and not a fix we shipped

Two reasons, both in the code's own words. The docstring specifies the flip ritual — *"Flipped
later by editing the service unit, never by a code default — the D108 pattern"* — and it declares
an **estimand shift**: `honest_scope=True` estimates `P(component | honestly evaluated)` rather
than `P(component | emitted)`. That is a different quantity, argued for on the grounds that it
excludes our own prefilter and lane plumbing from the target. **Changing what the production
ranker is estimating is not a defect fix.**

**And there is no fire.** Today's checkpoint: **58/3 consecutive PASS streak**, fresh
n=5,379 delta **+1.150**, cumulative +0.843. The model works despite the pooling; this is an
improvement opportunity with a measured 11× prevalence lift available, not an outage.

**Surfaced for the operator: flip `FORGE_HONEST_SCOPE` in the trainer unit, or leave it.** Not
taken here.

### Closes Q62

Answer relayed to QuantIQ. Nothing they sent blocks on us, and nothing we found blocks on them.

## D401 — **Second OOM alert: the Crucible DB-writer exhaustion has doubled in seven days, spread to three services, and cost ~15,242 refits. Plus a second finding: F3 has been scoring with a 15-day-old model.** No code change; both are surfaced, not fixed.

**Date:** 2026-08-31 · **Class:** cross-system alert + live observation · **Follows:** D399

### The degradation, measured

D399 (08-24) reported the stage-two refit scan OOM-failing at ~30% with −18% to −30% throughput.
Seven days on, unanswered:

```
  failure rate   08-22   7%  ->  08-24  22%  ->  08-28  45%  ->  08-30  54%
  throughput     08-22  -3%  ->  08-24 -29%  ->  08-28 -42%  ->  08-30 -53%
```

**Monotone, not a spike.** On 08-30 the scan failed more often than it succeeded (79 vs 65).
**Cumulative 08-22 → 08-30 against the 5,760/day baseline: ~15,242 refits and ~12,420 components
not produced.**

**No longer refit-specific.** On 2026-08-31 two further units began failing with the *same* DuckDB
memory guidance: `crucible-generation-census` (06:01) and `crucible-dashboard-feed-publisher`
(07:00). The latter is the structural yield-map / WF-percentile / corr-to-book / refutations feed
**that both QuantIQ and Forge consume** — if it stays down, both sides read a stale dashboard
without being told. Three consumers now hit the writer's 27.9 GiB ceiling; the cause is inside
Crucible's wall and we propose nothing.

**Bearing on D393:** their Step 2 close-out (*"refit triage is not the lever; un-consumed
above-floor supply is three rows"*) was measured ~08-14 on a healthy rig. Nine days averaging −29%
and ending at −53% is enough that it is worth re-reading before anyone leans on it. Not a claim it
was wrong.

### The second finding: F3 is running a stale model

`forge.service` has been up since **2026-08-16**. `load_latest_model` is called **once at loop
start** (`main.py:2377`), and there are now **82 `verdict_model_v1_*.json` artifacts on disk**, the
newest written today at 05:02. **The live scorer has therefore been using the 08-16 artifact for
fifteen days** while the trainer wrote fifteen newer ones.

**This refines D400's correction.** The trainer header's claim that it *"cannot change what Forge
submits"* is true **in practice — but by inertia, not by design.** There is no gate; the artifact
would be picked up on the next restart. Two consequences:

1. **The live model drifts stale with nothing watching it.** Whether load-once-at-start is the
   intended operator gate (a defensible reading of the D108 pattern) or an oversight is an open
   question, and it is not documented either way.
2. **The `honest_scope` A/B (prereg draft, `docs/proposals/prereg-honest-scope-ab.md`) is less
   urgent than framed** — a flip's effect is deferred to the next restart. The separate-directory
   design stays correct regardless.

### Recorded about the discovery

Both the OOM escalation and the stale-F3 observation surfaced from a routine *"everything running
smoothly?"* sweep, not from any monitor. **Third instance this month of a real condition found by
a human asking rather than by instrumentation** (after D389's unarmed watcher and D399's original
OOM). The relay asks Crucible the one question we actually want answered: whether the 08-24 alert
reached them — because if it did not, the durable defect is the monitoring gap on both sides, not
the memory limit.

## D402 — **RETRACTION of D400's `honest_scope` claim. It was NOT "built and never flipped": it went live 2026-07-22 and was reverted 2026-07-25 (`6b662ac`, Q59) because the scoping is measured HARMFUL out of sample — robustness OOS rank-IC 0.0321 vs 0.3962 (12×), F3 OOS AUC 0.5910 vs 0.6936. The prereg draft is WITHDRAWN. Correction relay owed to QuantIQ.**

**Date:** 2026-08-31 · **Class:** retraction · **Follows:** D400, D401

### What D400 claimed, and what is true

D400 stated `honest_scope` was *"built, documented, never flipped"* and framed an **11× prevalence
lift** as an available improvement, surfacing a flip decision to the operator. **All of that is
wrong.** The actual history:

```
  2026-07-22 23:26 PDT   FORGE_HONEST_LABEL_SCOPE=on   -> live (D331 Part B; created the v49 boundary)
  2026-07-25             FORGE_HONEST_LABEL_SCOPE=off  -> reverted (6b662ac, Q59 fix)
```

The revert was **measured and out-of-sample validated**, temporal split, fit-past/judge-future,
judged on the *unconditioned* population — the rule both repos adopted after the rank_k retraction:

```
  robustness  OOS rank-IC   0.0321 (drop) -> 0.3962 (no-drop)     12x
  F3          OOS AUC       0.5910 (drop) -> 0.6936 (no-drop + one-hot)
```

Mechanism, in the commit's own words: **the drop is quality-correlated, so it biases every
correlated coefficient (9 of 81 sign-flip), and it deletes whole strata** — `rank_k=20` is 55,820
rows unconditioned and **zero** under the drop, so the model could not learn the k=20 cliff at any
encoding. Both live models were near coin-flip OOS under the scoping, found two independent ways
on two different targets.

### How the error was made

The environ was grepped for `HONEST_SCOPE`. **The variable is `FORGE_HONEST_LABEL_SCOPE`** — the
substring does not match, so a flag that is *explicitly* set (`=off`, line 33 of
`forge-ranker-eval.service`, committed and installed identically) read as absent. From "absent" it
was inferred "never flipped", and the whole D400 finding was built on that inference. The revert's
reasoning was in `IMPLEMENTATION_DECISIONS.md` and in the commit message the entire time.

**This is the failure class we relayed to Crucible on 2026-08-14 and it is now ours:** *a mechanism
you can re-derive is not evidence that it is unrecorded* — and its corollary, *a bound you can
restate is not evidence that you checked it.* Fifth instance across the three repos this month,
first one of ours in this class.

**Compounding it: the 11× prevalence lift is precisely the trap Q59 names.** Prevalence rose while
OOS performance fell 12×. D400's own prereg draft warned against substituting a frame statistic for
ranking quality — citing v50's rank_k bias, the k=5 zero and the champion-improvement wall — and
then did exactly that.

### Actions

- **`docs/proposals/prereg-honest-scope-ab.md` WITHDRAWN.** Its premise (untried remedy) is false
  and its predicted direction is the one already refuted OOS. Retained on disk with a withdrawal
  header rather than deleted, because a withdrawn proposal and an absent one carry different
  information.
- **Correction relay owed to QuantIQ** — the Q62 triage relay carried the same false claim.
- **D400's triage of the six streams is UNAFFECTED.** Five parks and the `selector_spread_bind`
  location finding stand on their own evidence; only the honest_scope section is retracted.
- **D401's stale-F3 observation stands and is unrelated** — F3 loads once at daemon start
  (up since 08-16, 82 artifacts on disk). That the 08-16 artifact postdates the Q59 fix means the
  live model *has* the correct conditioning; whether a 15-day pin is intended remains open.

## D403 — **Crucible's `corr_to_book` basis notice (2026-09-05): pin INTACT, NO registered read in the frozen window, nothing adopted. But their "the guard covers it" holds only because the POPULATION floor is now structurally tripped — leg 2 has been dark on any basis older than 14 days all along — and the newest-window gap it does NOT cover is closed. Plus the finding the relay omits: their 09-03 re-rank published an EMPTY tier 3 for 13.5h and we drew 17,013 submissions from a 24-name universe.**

**Date:** 2026-09-06 · **Class:** relay processed + instrument tightening · **Follows:** D357 (pin), D389 (last leg-2 read), D391 (basis boundary), D392 (watcher)

### What they flagged (three changes, none re-basing `frozen_b36f49a4`)

1. New label `7f2a697ec6c1b119` (their designated champion since 08-06) on rows decided from
   2026-09-06T05:24:15Z, forward-only, no backfill.
2. The export was **frozen 08-31 07:02Z → 09-06 05:25Z**: the 14-day scan crossed their writer's
   result-row cap and a `-`-prefixed ExecStart kept the unit green. Nothing paged.
3. From 09-06 the export is cut from their **nightly snapshot** (~11:00Z), so the newest file trails
   decisions by 7–31 hours. Additive `data_basis` block.

They asked three checks. Answered below, each verified on our own data.

### Verified, not assumed

- **The gap is real.** Daily files through `corr_to_book_2026-08-30T140305Z.json`, then nothing
  until `corr_to_book_2026-09-06T052533Z.json` (mtime 2026-09-06T05:25:38Z, 88.6 MB).
- **The pin is intact by OUR function.** `_basis_fp` over `frozen_b36f49a4` = `ae47a4749c9d` on both
  files. `_load_corr()` on the new file: 204,915 hashes, fp OK. The additive changes are inert to
  the loader (it reads one book by name): fifth `books` entry (fp `09cfe2ad7e55`, minted
  2026-09-06T05:24:11Z from the stored manifest, 6 legs, tail leg on, vt 0.15, 2,122 sessions),
  `data_basis` = `{snapshot: runs-20260905T110045Z.duckdb, snapshot_age_hours: 18.32,
  window_cut_utc: 2026-08-23 05:25:33}`. **Zero of 262,336 rows carry the new key yet** — the
  snapshot predates the mint, exactly as their lag note predicts.
- **Check 1 — NO registered read in the window.** `config/preregistrations.jsonl`: 31 entries, all
  resolved (20 confirmed / 5 insufficient / 6 refuted), newest `resolved_at`
  2026-08-14T06:14:10Z (`3b0cbca7ae17`, D389); no `created_at`/`cohort_cut`/`resolved_at` falls in
  08-31T07:02Z → 09-06T05:25Z. `forge-prereg-watch.service` logged **"no open preregistrations —
  nothing to watch"** on every day 08-31 through 09-05. Nothing to mark.
- **Check 2 — quantified on the 09-06 snapshot** (honest arm with cpcv n=76,914; 64 windows @1200):

  | export read by mtime | population join | newest 8 windows | leg 2 |
  |---|---|---|---|
  | `2026-08-30T140305Z` (the frozen one) | **26.4%** | all 0% (NaN) | UNAVAILABLE |
  | `2026-09-06T052533Z` (first snapshot cut) | **31.2%** | 57–63 at 100%, **window 64 at 30.3%** | UNAVAILABLE |
  | within basis `e1ad` only | 38.1% → 41.3% | — | UNAVAILABLE |

  So any read in the window WOULD have been refused — by the population floor, on a cause the
  relay does not name: **their export is a 14-day rolling window** (`window_days: 14`, cut
  08-23) while the honest arm dates from 07-23 (D335); 43 of 64 windows are NaN under the NEW
  file too. **Leg 2 is readable only on a generation basis younger than ~14 days.** D389's 84.2%
  join was that case (basis born 08-03, read 08-14). Not new today; newly stated.
- **The case the population floor does NOT cover — closed.** Window 64 is 30.3% joined and the
  old `_leg2` read it as a full window (0.4337). Worse, a 0%-joined newest window returns NaN,
  which the code dropped, so "newest" silently became the prior window and the verdict was about
  a window nobody asked about. `_leg2` now **refuses when the newest window is under 50% joined**
  (TDD: 4 tests in `tests/unit/test_scripts/test_freeze_newest_window_join.py`, red → green;
  65 script tests pass; ruff clean). `docs/proposals/grammar-freeze-criterion.md` updated. A
  tightening of a freeze instrument; no grammar, no restart, no version.
- **Check 3 — NOT adopted.** D357 stands: the pin does not chase the designation. The champion
  book's basis fp `09cfe2ad7e55` is recorded here so that any future adoption is a deliberate
  re-pin at a stated boundary, never a drift.

### The finding the relay omits: the 09-03 monthly re-rank published an EMPTY tier 3

- `crucible-universe-publisher` 2026-09-03 13:01Z: `tier3.floor_excluded n=160`,
  **`tier3.refresh_written n=0`** → `universe_tickers_2026-09-03T130107Z.json` and
  `...T130559Z.json` with `"tier_3": []` (406 bytes against the usual 1,231). August's run had
  excluded 86 and written 74 (D386).
- An **off-cycle republish at 2026-09-04T02:30:35Z** restored 74 tier-3 names — by content the
  August list (fingerprint back to `e1adced727678c8f`). The 09-04 and 09-05 06:05Z dailies match.
- **Our side:** the daemon came up fresh after the 09-03 11:08 PDT boot, read the newest file, and
  drew generation basis **`d5da4c3c1469e330` from 09-03 18:35Z to 09-04 23:38Z: 17,013
  submissions from a 24-name universe** (tier 1 + tier 2 only), then back to `e1ad`. The fix was
  on disk ~21h before we drew from it — D387's cache-lag class. The basis guard isolates the
  excursion correctly (windows 62–63 report `d5da,e1ad`; no straddle is attributed to a side).
- **Not relayed by Crucible** — nothing in their 09-03/09-04 handoffs mentions it, and D391's
  undertaking explicitly covers off-cycle re-ranks. Asked in the reply: was the 02:30Z file the
  re-rank's true output (September = August by content) or a rollback of August's list pending a
  re-run? The answer decides whether `e1ad`-after-09-04 is the same basis as `e1ad`-before.
- **Effect:** freeze — none (zero open preregs, nothing registered on `d5da`). Generation — no
  tier-3 single-name emission for ~29h; xsect ranks the tier-2 pool regardless (D296). Context:
  the box rebooted 09-02, 09-03 and 09-04 (operator activity, incl. the 09-02 OOM), which is why
  the 09-03 pickup was a fresh-process read rather than the cache lag.

### Disposition

Reply relay sent (check 1 negative, check 2 numbers, the guard change, the tier-3 question).
No grammar change, no restart, no bump. **Grammar frozen at v55, zero open preregistrations.**
Standing note for the next leg-2 registration: **register only on a basis under 14 days old, and
read before the basis ages past the export window — or ask Crucible to widen `window_days`.**

## D404 — **Crucible's answer to D403's question: (b), tighter. The September tier-3 snapshot was WITHDRAWN (moved aside, never re-ranked), so `e1ad` after 09-04 is August's basis by PROVENANCE. Cause verified on the canonical store: `open_interest` is NULL on every chain row since 08-12, so their tier-3 floor cannot admit any name until it reads OI from where it exists. No calendar boundary exists any more — the basis moves only when they relay it first. We named the corr-export window: 60 days.**

**Date:** 2026-09-06 · **Class:** relay processed + basis-rule supersession · **Follows:** D403, D391 (calendar demoted), D387 (basis guard)

### Their answer, verified here

- **§1 withdrawn, not rolled back.** `~/optbt_data/universe/asof_date=2026-09-01/` holds only
  `all_eligible_tickers.parquet` and `tier3_tickers.parquet.EMPTY-refused-2026-09-03.bak`
  (240 B, mtime 09-03 06:01 PDT); no live tier-3 file for 09-01. `asof_date=2026-08-03/tier3_tickers.parquet`
  (796 B, 08-03 06:00 PDT) is untouched. Their resolver takes the newest snapshot *carrying the
  tier*, so tier 3 resolves to 08-03. **The basis before 09-03 and after 09-04 is the same object,
  not merely the same content — D403's open question is closed.** The 17,013 `d5da` submissions
  were drawn from a snapshot that never existed as a basis.
- **Fix `2b04ff3` exists** (Crucible, 2026-09-03 19:30 PDT: `ingest_universe.py` refuses an empty
  refresh before the write, `check_pipeline_health.py` pages on it, 65 lines of tests). Heartbeat
  verified: `universe_tickers_2026-09-04T130506Z` and `…09-05T130545Z` are 1,231 B, the held list.
- **§2 the cause — VERIFIED on the canonical chain store**, `~/optbt_data/chain_snapshots/underlying=*/asof_date=<session>/data.parquet`:

  | session | files | rows | `open_interest` non-null |
  |---|---|---|---|
  | 2026-08-11 | 184 | 47,332 | 596 (1.3%) |
  | 2026-08-12 | 31 | 9,448 | **0** |
  | 2026-08-13 | 99 | 30,557 | **0** |
  | 2026-09-02 | 98 | 30,513 | **0** |

  Their floor (`open_interest >= 100` on the canonical partitions) has been unsatisfiable on
  every session since 08-12 — the `ibkr_tick101` real-or-NULL producer change they asked
  QuantIQ for. Their own 09-03 record blamed the session denominator; that mechanism exists but
  did not fire. The 10-03 timer will **refuse** (post-`2b04ff3`) unless the floor's input changes
  first, which is a §20 decision on their side, proposed not shipped.
- **§2 commitment, adopted as our rule:** the tier-3 basis moves only by (i) a guarded refresh that
  admits ≥1 name or (ii) a relayed manual re-run, **relayed with asof + timestamp BEFORE it
  lands.** Consequence for us: **D391's "on or after the 3rd" is no longer even a planning
  expectation.** There is no calendar. The `enumeration_inputs_hash` universe component remains
  the cut (D391 rule unchanged); the *expectation* of when it moves is now "when the relay says".
- **§3 a measurement-basis fact, dated 08-12:** their selector skips rows with OI None, so every
  IBKR-captured near-ATM contract has been unselectable since 08-12 and every entry on a
  post-08-12 bar comes from a CBOE supplement row with a real bid/ask — the spread gate binds
  (`spread_too_wide` 4–8% → 32–44% of signals by week; traded 91% → 55–63%). 295,804 forge runs
  decided since 08-12 have windows crossing it, ~3 weeks of an 8.7-year window today, growing a
  session per session. **Not visible on our ledger yet, as expected at ~1% window exposure:**
  weekly median `min_oos_trade_count.value` on stage-one verdicts 521 / 532 / 538 / 535 / 518
  (weeks of 08-03 → 08-31), cpcv_p25 0.43 / 0.42 / 0.48 / 0.44 / 0.40. **Standing watch, no
  instrument:** re-check these monthly; a downtrend from here is this basis change before it is
  supply. Both freeze reads (D384 08-09, D389 08-14) had ≤2 sessions of exposure — unaffected.
  No Forge mechanism reads spreads or OI; prefilters key on activations, not fills.
- **§5 `tier_3_asof` export field:** additive contracts field, operator-gated on their side; we
  adopt through the usual both-directions restart (D244/D245) when it ships. Until then §2's
  commitment is the provenance. Acknowledged, nothing to do.

### §4 — we named the window: **60 days**

Their measured cost: 14 d = 262,336 runs / 88 MB (today); 30 d = 547,750 / ~185 MB; 45 d =
758,820 / ~255 MB; 60 d = 776,445 / ~260 MB. Ours, measured: `_load_corr()` peaks at **376 MB
RSS in 0.7 s on the 88 MB file** → ~1.1 GB on a 60-day file, in a one-shot script on a 123 GB
box. **60 because it is the smallest offered size that keeps a within-basis leg-2 read available
for a basis's whole life:** a basis lives at least a month, a read must reach back to the basis
start, and `Persistent=true` (and now a held basis) only makes it longer. 45 d covers the arm
start today and stops covering it tomorrow. The residual — a basis older than 60 d — is ours to
plan around: register inside the window and read before it ages out, or ask again.

### Disposition

Reply relay sent (window named, §1–§3 verified with our numbers, calendar expectation retired).
No code change, no grammar change, no restart. Grammar frozen at v55, zero open preregs.

## D405 — **Crucible's basis-change notice, relayed BEFORE landing under D404's rule: CBOE panel open interest now folds onto every canonical chain row by OCC symbol at the runner restart. LANDED 2026-09-06T07:32:41Z — read from systemd here before their timestamp relay arrived. Their AAPL/MU numbers replicate EXACTLY on our own join of the two parquet trees. Three chain-basis dates now stand: 07-17 (volume alias), 08-12 (canonical OI NULL), 09-06T07:32:41Z (panel fold).**

**Date:** 2026-09-06 · **Class:** relay processed, measurement-basis date recorded · **Follows:** D404 (08-12 date + watch), D386 (Layer-2 request)

### What they shipped (§20 `panel-oi-fold-into-canonical`, operator decision 2026-09-06)

- A parallel tree `cboe_forward/oi_fold/underlying=*/asof_date=*/oi.parquet` (`occ_symbol`,
  `open_interest`) built nightly from the CBOE EOD panel; both chain loaders left-join it by
  `occ_symbol` and take the panel's value where it has the contract. Never adds rows, never
  creates coverage, no-op where the partition is absent; canonical files untouched; rollback is
  a code revert.
- **Bars 08-12 → today:** NULL → real OI; every IBKR-captured near-ATM strike selectable again;
  IBKR rows carry NBBO mids so the spread gate passes them. Their expectation: traded share back
  toward the pre-08-12 89–93% from 55–63% — to be measured after landing, not asserted.
- **Bars 07-17 → 08-11:** the volume alias is replaced by real OI where the panel carries the
  contract (OI ≥ 100 / volume < 100 becomes eligible; the converse stops being eligible).
- **Bars before 07-17:** no panel, no change; the designated book's certified window (ends
  06-12) untouched. No contracts change, no export shape change, no grammar input. Tier 3 still
  reads the raw partitions (a separate, relayed decision if it moves).

### Verified here, on the shared disk

- **Fold tree:** 6,796 partitions (exact match), 11,675,278 rows (their 11.7M), asof
  **2026-07-17 → 2026-09-04** (they wrote "→ 09-05"; no 09-05 partition exists yet), **39 MB on
  disk** (they wrote 77 MB — likely the uncompressed figure). Backfill mtimes 07:16:35–07:16:50Z,
  consistent with their token roll at 07:16:51Z; the token itself was not located from our side.
- **Mechanism replicated on our own join** (canonical `chain_snapshots` LEFT JOIN `oi_fold` on
  `occ_symbol`, panel value first, then their fill floor `volume ≥ 10 AND OI ≥ 100` on the
  |delta| 0.25–0.60 band):

  | 2026-09-02 | rows | matched | NULL after fold | in-band | pass | theirs |
  |---|---|---|---|---|---|---|
  | AAPL | 255 | 255 | 0 | 86 | **78** | 78 of 86 |
  | MU | 566 | 566 | 0 | 340 | **169** | 169 of 340 |

- **Volume alias confirmed:** 2026-07-20 (34,281 rows) and 2026-08-05 (45,804 rows) —
  `open_interest == volume` on 100% of rows, zero NULL.
- **Landing instant:** `crucible-runner@1.service` Stopped/Started at **2026-09-06 00:32:41 PDT =
  07:32:41Z**; the new process (pid 1449463) bound contracts 1.47.0 at 07:32:42.311Z. **One
  instant for both lanes:** stage-two refits execute inside the same shard (`runner_start …
  source: fullhist_refit` in its journal) and `crucible-refit-watcher` only queues rows from
  QuantIQ's refit inbox — no asymmetric split of the D245 class. Their one-line timestamp relay
  had not arrived when this was written; the instant above is the systemd record, offered to
  them for confirmation.

### Our exposed cohorts (snapshot 2026-09-06T05:40Z, pre-landing)

| era | stage one | stage two | other |
|---|---|---|---|
| volume alias 07-17 → 08-11 | 250,092 | 77,329 | 50,223 untagged |
| canonical OI NULL 08-12 → 09-06T07:32Z | 320,790 | 125,158 | 25 `selection_pbo` |

Every verdict in both eras was priced with an affected forward edge; the affected span inside a
run window is ≤36 sessions today (~2.9% of a 5-yr stage-one window, ~1.6% of fullhist), which is
why D404's weekly `min_oos_trade_count` medians (521 → 518) show nothing. Direction from here:
post-landing verdicts should carry MORE trades than the NULL-OI era at the forward edge, so a
rise at the 09-06 boundary is basis, not supply. **D404's watch now brackets three dates.**

### Consequence, and the gap this makes visible for the third time

- **Nothing to act on.** No prefilter, ranker feature or grammar input reads OI, spreads or fills;
  labels stay comparable within an era. The 05:00 F3/tail retrain pools eras by construction —
  a slowly growing basis drift at the forward edge, recorded, not corrected.
- **Recoverable only by timestamp, again.** A verdict's chain basis is `decided_at` against a
  relayed instant; nothing on the row stamps it. That is D386's Layer-2 request (data-basis
  fingerprint on stage-one verdicts), still open, now with three eras to key on. Restated in
  the reply as a reminder, not a blocking ask.
- Docs: the three eras added to `docs/tasks/investigate-live.md` (eras section).

### Disposition

Ack relay sent: the landing instant as read here, the exact replication, the two small
discrepancies (partition range, on-disk size). No code, no grammar, no restart. **v55 frozen,
zero open preregistrations.**

## D406 — 2026-09-13 — Batch 0 of the 2026-09 simplification plan: contracts pin 1.44.0 → **1.47.0** (pin-only adopt), **D401's stale-model claim RETRACTED**, and the final state decided — Route C, automated

**Context.** The operator asked for an extensive cleanup and simplification plan (2026-09-13); it is
`docs/proposals/repo-simplification-2026-09.md` (a five-track read-only audit at HEAD `db1172f`; suite
2,156 passed / 1 failed (this pin) / 1 skipped in 232 s). The operator then decided the FINAL STATE
(plan §12): **Route C, automated** — no daemon; one weekly, zero-input `forge campaign` run that reads
the designated champion + promoted books + component contributions, evaluates five triggers, rejection-
samples the UNCHANGED v55 population to the chosen cells, applies a structural challenger gate, and
submits ≤ 400/week (from ~80,000). Batches 0–2 were approved ("complete batches 0 to 2"); a relay to
Crucible goes out in the same session.

**Decision 1 — pin-only adopt 1.47.0.** `core/contracts_check.py` pins `1.47.0` (was `1.44.0`);
`uv.lock` (already at 1.47.0, the operator's uncommitted change since 09-06) is committed. 1.45.0 =
`PromotedPortfolio.position_key` (engine/QuantIQ-facing), 1.46.0 was reverted the same day, 1.47.0 =
`DTE_BUCKET_WINDOWS` constant — additive, nothing Forge parses narrows (D267/D374 precedent).
**No restart, and none is owed:** both directions already ran 1.47.0 before the pin moved (Crucible
runner bound it 2026-09-06T07:32:42Z, D405; `forge.service` since the 2026-09-12 12:05 PDT boot,
NRestarts=0), so the D244/D245 asymmetry cannot arise. Verified: `test_contracts_integration.py`
5 passed; `forge check` → `crucible_contracts: 1.47.0 OK`. The hourly healthcheck's `contracts_pin`
WARN (264 of 354 runs since 08-30) clears at the next hour. The tree is deployable again
(`deploy_preflight.sh` dirty-surface NO-GO on `uv.lock` is gone).

**Decision 2 — D401 retraction.** D401 recorded "F3 has been scoring with a 15-day-old model … the
artifact would be picked up on the next restart." **False at HEAD and at the time it was written.**
`load_latest_model` is called inside `_run_one_iteration` (`cli/main.py:1968` def, `:2377` call —
in place since `20ef7ad`, 2026-06-14), as are `load_latest_robustness_model` (`:2411`) and
`load_latest_tail_model` (`:2510`). Journal 2026-09-12 12:05 → 09-13: 59 iterations, `model_id`
rolled `c0c3a234…` → `3046dc2b…` (verdict) and `9bbf621b…` → `01445f6c…` (quality) with zero
restarts. The daily trainer changes what Forge submits the same day; D401's consequence 2 (the
honest_scope A/B "less urgent because deferred to restart") is void with it — moot anyway, that prereg
was withdrawn (D402). Recorded here rather than edited in place: a ledger entry is immutable.

**Also recorded (found by the audit, acted on in Batches 1–2):** `forge-ranker-eval` peaks at
20–34 GB RSS on every run since 08-25 (five sequential fits each re-reading the 8.9 GB snapshot) on
the box whose Crucible services OOM'd twice (D399/D401); "~10 test files monkeypatch `forge.cli.main`"
is 24, of which 22 only import `app`; Forge contains no equities code (the operator's template item
was QuantIQ's PTS arm); `feedback/preregistration.py` is load-bearing for the `freeze-governance` hook,
so the July retirement plan's "retire prereg machinery" row is wrong.

**Alternatives.** Reverting `uv.lock` to 1.44.0 — rejected: the installed editable contracts and both
running processes are 1.47.0; the lock would lie. Restarting `forge.service` for the pin — rejected:
no behaviour depends on the constant beyond the startup check, and the daemon is retired at the
Route C cutover (plan §12.6 Batch 4).

**Action.** Batch 1 (records/docs/unit comments/hygiene) and Batch 2 (coverage-first tests) follow in
this session, each with its own D-entry; the Crucible relay is filed to `freeze/relays/`.

## D407 — 2026-09-13 — Batch 1 of the 2026-09 simplification plan: records rotated, terminal records archived, the relay pile removed, 40 stale doc statements fixed, the unit file stopped being a ledger, runtime cruft archived — zero production change

**Scope.** `docs/proposals/repo-simplification-2026-09.md` §10 Batch 1 (operator: "complete batches
0 to 2"). Docs/records/untracked hygiene only: no `src/` semantics, no config, no restart. The one
`src/` diff is comment-only path repoints (`fable-audit/` → `_archive/fable-audit-2026-07/`,
`docs/INDICATOR_THRESHOLDS.md` → `_archive/`, one proposal path in `contracts_check.py`); the goldens
and the full suite prove no behaviour moved.

**Rotations (D242/D295 precedent, 400 KB bar).** `STATUS.md` 110 KB / 37 blocks → 9 KB / 4 blocks
(34 August blocks → `_archive/STATUS_2026-08.md`). `IMPLEMENTATION_DECISIONS.md` 472 KB → 202 KB
(D301–D350 → `_archive/IMPLEMENTATION_DECISIONS_D301-D350.md`, 50 entries; the four out-of-order runs
D302/D303, D315/D316, D329–D338, D375/D377 are sorted by D-number in both files — content untouched).
`OPEN_QUESTIONS.md` 51 KB → 36 KB: Q23/Q34/Q40/Q49/Q62 (resolved in place, never rotated) →
`_archive/OPEN_QUESTIONS_RESOLVED.md`; Q9/Q14/Q29/Q41/Q45/Q47 bannered "MOOT under D390 unless a §5
reopener fires" (Q9 stays live — `test_phase6_invariants.py:124-127` reads the live file).

**Archived (`git mv`, D202 mechanic).** Eight terminal proposals → `_archive/PROPOSAL_*`:
`grammar-freeze-criterion` (superseded by the signed declaration), `ceiling-saturation-experiment`,
`v50-winner-neighborhood-priors` (D372), `generation-model-levers`, `regime-orthogonal-arms`,
`prereg-honest-scope-ab` (withdrawn D402), `ops-debt-roundup-2026-07` (its open item 5a = DuckDB write
batching is moot under the Route C final state — no daemon), `repo-simplification-2026-08` (superseded
banner appended). `fable-audit/` (7 July audits) → `_archive/fable-audit-2026-07/`; its still-live
reliability items REL-1/2/4/5/8/12 are carried in the 2026-09 plan §6. The two root expansion reviews
(`GRAMMAR_REVIEW_AND_EXPANSION.md`, `LEARNED_SYSTEMS_AND_GENERATION_REVIEW.md`) → `_archive/` — the
"re-verdict at the freeze declaration" architecture.md promised is: archive (expansion roadmaps vs a
frozen grammar). `docs/INDICATOR_THRESHOLDS.md` (pre-D031 snapshot, the D153 trap) → `_archive/`; every
citer now points at `enumeration/indicator_thresholds.py`. Every cross-reference to a moved file was
repointed (grep clean).

**Removed (`git rm`, recoverable via `git show fd9cba4:_archive/<name>`).** The 150 `_archive/PROMPT_*`
+ `CRUCIBLE_*` relay files (1.2 MB) — the retired root channel's record; `freeze/relays/` is the
channel and holds every live exchange. `_archive/` 201 → 63 files. Note added atop the ledger.

**Docs truth fixes (40 statements, 16 files, +74/−77 lines).** CLAUDE.md now shorter and states the
one load-bearing missing fact — grammar FROZEN at v55, prereg first — plus: the /tmp pitfall
replaced by `live_db_snapshot.sh`; "~10 monkeypatch files" → two dozen (22 import only `app`); the
worktree rule scoped to grammar bumps; INDICATOR_THRESHOLDS row repointed at the code. architecture.md,
MANPAGE, HOW-TO, quality-gates, grammar-change, feedback-change, deploy, config/README, README,
DESIGN (one-liners: §11.5 dangling ref, §5.5/§8.4 bannered retired/superseded, dashboard/Slack bullets
deleted, §9.3 JSON, "25 rules" → 21), v39/v41 proposals marked DEPLOYED, NEW_BOX/setup_new_box/
stage_transfer → four timers and version-agnostic. Doc-needle tests: 27 passed. Flagged for Batch 6:
DESIGN §14 history row still says "25 rules".

**Unit file (August Step D).** `deploy/systemd/forge.service` 249 → 49 lines; the 27 directives are
byte-identical (diff-verified); each `Environment=` keeps one ⚠️ line with its D-pointer; the five
`SAMPLE_N` ramp narratives, the retired ve-floor essay, and the arm-B history live in their D-entries.
`forge-prereg-watch.{service,timer}` were file COPIES in `~/.config/systemd/user/`; now symlinks like
the other seven. `daemon-reload` run (no restart; comment-only). Four timers armed, service active.

**Hygiene.** 182 orphan `.pyc` (deleted modules/tests) + 5 stray cpython-314 pyc removed; root
`scratchpad/` (empty) removed; `.mypy_cache` left (regenerates; deleting only slows the next mypy).
`~/forge_data`: `alpha_budget/`, `shadow_null/`, `eod_checks/`, `winning_cohort/`, the two dead
clocks `ranker_eval/robustness_streak*.jsonl` → `~/forge_data/archive/retired_2026-09/`; empty `logs/`
removed. **Not done (operator-gated, §8.11):** the 6.3 GB `forge.db.pre_arm_cleanup_20260731_230544`
copy stays until the operator confirms the D342 repair is closed.

**Verification.** `test_phase6_invariants` + `test_phase0_invariants` + `test_cli_help` +
`test_v1_grammar` green during the work; full suite run at the end of Batch 2 (D408).

## D408 — 2026-09-13 — Batch 2 of the 2026-09 simplification plan: coverage first — three known bugs pinned as strict xfails, model-reload cadence and the snapshot script pinned, perf tests marked slow, the v44 conditioner tests and the Q51 flake removed

**Scope.** Plan §10 Batch 2 as narrowed by §12.6 (final state = Route C): tests only, no `src/`,
no scripts, no config. Suite after: **2,148 passed / 1 skipped / 3 xfailed in 214 s** (before Batch 0:
2,156 passed / 1 failed / 1 skipped in 232 s). `ruff check tests` clean.

**Known-bug gap tests — `@pytest.mark.xfail(strict=True)`, each verified with `--runxfail` to fail at
the intended assertion, each flips LOUD when its fix lands (Batch 5):**
- `tests/unit/test_cli/test_sigterm_handler.py` — REL-4: `forge run` installs no SIGTERM handler
  (`signal.getsignal(SIGTERM)` is `SIG_DFL`); systemd stops the daemon with SIGTERM, and
  `submitter.py` writes the inbox file inside the DB transaction, so a stop between the inbox write
  and the commit leaves an inbox file with no row.
- `tests/unit/test_cli/test_export_outage_signal.py` — REL-1: `_reconcile_pending_silently` on a
  missing export + DB prints nothing at all (the `main.py` `except QueryError: return ()` swallow);
  the test expects an explicit line naming `QueryError`/`export_unreadable`, mirroring the existing
  promoted-configs warn-once memo.
- `tests/unit/test_submission/test_rate_limiter_export_outage.py` — REL-2: the limiter neither logs
  nor flags an unreadable export; accepts either a WARNING record or a `crucible_unreachable` status
  attribute so the fix can pick the shape.

**Behaviour pinned (pass today):** `test_model_reload_cadence.py` — `--loop --max-iterations 2`
calls `load_latest_model` exactly twice on `<forge_db>/models` (the corrected D401 fact, D406);
`tests/unit/test_scripts/test_live_db_snapshot.py` (3) — refuses a RAM-backed dir, fails cleanly on
a missing live DB, refresh → reuse → `--force` → `--clean` on real disk with the copy opened
read-only.

**Suite shape.** The three perf tests carry `@pytest.mark.slow` (`-m slow` collects exactly them;
`-m "not slow"` is now a real fast lane). `test_v44_vix_conditioner.py` (358 lines, 12 tests, ~12 s)
DELETED — the v44/v45 conditioner is retired at v55 (D366); its `_v44_registry` fixture moved into
`test_v55_vix_conditioner_retired.py`, whose silent-re-admission guard still passes. Q51's flaky
`test_held_out_platt_reduces_ece_vs_raw` DELETED (DuckDB scan-order split; `evaluation.py` is retired
under the final state, so no ORDER BY fix) — **Q51 CLOSED by deletion**, swept to the archive.
`tests/README.md` corrected (two dozen files import `forge.cli.main`, 22 only `app`; the phase0
clock scan covers `src/` only; the strict-xfail convention).

**Not done, with reasons.** `deploy_preflight.sh` NO-GO-path test: the script hard-codes the repo
path and always runs the full suite after the tree check, so its dirty-tree branch cannot be exercised
in isolation — needs a `--check-only` flag (script change, Batch 5). Healthcheck level tests for
`check_hypothesis_weights_fallback` / `check_registry_unknown_family`: already exist
(`test_healthcheck.py:56-97`) — the audit's "parse-only" claim was wrong. Shared DB-row-builder
fixture: Batch 6 (many of its 16 client files are slated for deletion). Hot-grammar-reread and
daily-eval-script tests: moot under the final state.

**Verification.** Full suite green (above); `scripts/deploy_preflight.sh` GO on a clean tree after
the Batch 2 commit (run at the end of this session; result in STATUS).

## D409 — 2026-09-14 — Crucible's six answers on campaign mode processed: T1 becomes designation-flip-only, cutover is BLOCKED on a forge-scoped 14-day gated stream (option 2, operator-confirmed), weekday Sunday 03:00 UTC, `promoted_strategies` retirement ACKed, the champion re-based to `7f2a697ec6c1b119`

**Inbound.** `freeze/relays/CRUCIBLE_weekly_campaign_six_answers_…_2026-09-13.md` (their `5b3aa42`),
answering our `FORGE_final_state_is_weekly_CAMPAIGN_mode…_2026-09-13` (D406/D408 session). Every
premise re-read on our disk before replying (crucible-handoff rule); reply delivered as
`FORGE_weekly_campaign_answers_ACCEPTED_option_2…_2026-09-14.md` (freeze `5ab347a`).

**Verified, and what each changes in plan §12:**
1. `component_contributions` is FROZEN at assembly (recomputed from stored ledgers only; a config in
   several books carries the last-iterated book's score). Verified: 18 rows, 6 filed under the
   designated book, values match their table exactly. **T1 = designation flips only**; `marginal_sharpe`
   decay struck from the trigger table; the campaign filters on `portfolio_id == designated`.
2. No live/paper per-leg performance is published, none planned (paper P&L is QuantIQ's). On record;
   Route D stays a QuantIQ ask.
3. `selection_arm` stays `ranked`; the relayed cutover instant is the `ranked`-arm boundary — no
   contracts change (the 1.39.0 precedent).
4. No Crucible timer assumes a daily stream. **§4.1 BLOCKING:** `gated_runs_*.json` is the newest
   decisions across ALL sources — **measured here 2026-09-14T03:11Z: 10,000 rows spanning ~14 h; 60
   retained files reach ~24 h** (their relay said 1,000 rows / 84 min / ~10 h — off by 10× on rows,
   conclusion unchanged: an order of magnitude short of a week). **Operator picked option 2** — Crucible
   adds a forge-scoped, 14-day gated stream, loader-first in contracts; Forge adopts pin-only and wires
   the campaign reconcile to it in Batch 3; **cutover waits on it**. Rejected option 1 (a Forge poller):
   a second moving part whose failure mode is a silent label gap. `failed_runs` now looks back 14 days
   (their `5b3aa42`; verified `lookback_days: 14`, 339 rows).
5. `promoted_strategies` is RETIRING on their side: our prior-promotion-proximity read
   (`cli/main.py:1549`) has received `[]` since C1 (07-06) — verified 0 rows in 90 days across 60
   snapshots. **ACKed**; the read + `ranking/prior_promotion.py` leave in Batch 5 (the F3-off fallback
   was already a zero prior). `designation_history` had NEVER been published: the 08-02 file naming
   `f52a05c8` was a hand-run one-off; the champion has been **`7f2a697ec6c1b119` since 2026-08-06**
   (6 legs: 4 trend, 2 MR). Republished 09-14T02:51Z, now daily 07:00 PT with a 30 h health check.
   Nothing in Forge code read the old file (grep: zero readers); only plan §12.1 text was wrong —
   corrected. `refutations` publishes on content change only (five files, all 07-31): T2 keys on a new
   file with different content, never on file age.
6. Their morning digest goes silent at cutover without erroring; it will read
   `~/forge_data/campaigns/<run_id>.json` once we publish the schema. `forge_funnel.json` must keep
   its aggregate `per_grammar_version` shape (a different shape raises `ForgeFunnelError`; an absent
   file degrades) — the weekly run updates the same aggregate; per-run detail lives in the run record.

**Weekday (operator-confirmed): Sunday 03:00 UTC** (Saturday 20:00 PT). Their Monday 06:00 PT census
reads cohorts ≥ 14 days old, so a Sunday cohort is 15 days old at the first census that can include it
and its stage-one verdicts are long done. Proposed to Crucible for confirmation.

**Open, both sides.** Theirs: the 14-day forge-scoped stream; weekday confirmation. Ours: publish the
run-record schema before the first live run; relay the cutover instant ≥ 24 h ahead; drop the
`promoted_strategies` read (Batch 5). **Nothing changes on the wire yet** — the daemon runs unchanged.
Next: Batch 3 (build `forge campaign` beside the daemon, plan §12.6).

## D410 — 2026-09-14 — Batch 3 BUILT: `forge campaign` exists beside the daemon — the weekly, zero-input challenger run; first two live dry-runs are clean and quiet; the dry-run weeks start

**What shipped (8 commits `96b8ab5` → `2211d47`, TDD, every commit green under ruff / mypy --strict /
scoped pytest; full suite after the build 2,228 passed / 1 skipped / 3 xfailed in 211 s).**
`src/forge/campaign/`: `types.py` (the contract: `CellKey` = the census 5-tuple, `Book`, `CampaignSpec`,
`TriggerInputs/Outcome`, `GateDecision`, `RunRecord`, `CampaignConfig` with the plan §12.7 defaults),
`cells.py` (cell keys, the promoted book via contracts loaders + `designation_history`, verdict-ledger
cell stats under the clean-era + ve-ghost cuts, dead-cell rule from `yield_audit`), `triggers.py`
(T1–T5 as pure functions + weekly-cap allocation), `gate.py` (structural challenger gate:
protected cell / duplicate of a leg by signal-key Jaccard ≥ 0.85 / dead cell), `report.py` (lossless
`campaign_run/v1` codec, `status`), `run.py` (boot checks → reconcile → book + stats → identity →
unstratified enumeration → triggers → rejection-sample to cells → battery → gate → in-cell F3 ×
tail_norm rank → submit → funnel aggregate → record). `cli/campaign_cmd.py` registered as
`forge campaign` (`--dry-run`, `--budget`, path flags; exit 0 ok/no_trigger, 2 boot_failed, 1 error)
and `forge campaign status`. `config/forge_config.py` gains a `campaign:` section resolved onto the
dataclass (unknown keys fail loud). `submitter.py`: one additive map — any `campaign:*` lane stamps
`selection_arm="ranked"` (Crucible 09-13 §3; never an unadmitted Literal, D342). Units
`deploy/systemd/forge-campaign.{service,timer}` (Sunday 03:00 UTC) written, **NOT installed**.
Docs: MANPAGE `### forge campaign` (record schema, exit codes), architecture map row, HOW-TO "Weekly
campaign run". Tests: 56 (part A) + 17 (part B) + 12 invariants incl. the population-unchanged
subsequence proof (hard rule #6) and "no `selection_arm` but `ranked`".

**Design facts fixed by this build.** The run enumerates the UNCHANGED v55 population with no learned
weight maps (the cold-start sequence the goldens pin) and selects by cell afterwards; the seed is
`blake2b(grammar_version|registry_hash|ISO week)` so the same week on the same inputs reproduces the
plan. `min_hypothesis_fraction` is **0.0** for the campaign (`2211d47`): the D037 floor is a
submission-mix guarantee for the daemon's batches and under a cold-start draw it capped the first live
dry-run at 800 of 20,000 configs after 2M attempts. Ranking never falls back to the Jaccard prior
(`promoted_strategies` is retiring, D409): no artifact → score 0.0, recorded. `refutation_ids` = the
BOUND-and-active entry ids (an unbound entry routes nothing, so its retraction is not a generation
event); the refutations baseline is a content hash. Reconcile reuses `reconcile_all_pending` against
today's export — the forge-scoped 14-day stream (D409 §4.1) slots in there when Crucible ships it.

**First two live dry-runs (snapshot DB, `--budget 40`, records in `~/forge_data/campaigns/`).**
`2026-W38-20260914T042757Z`: boot 8/8 ok (contracts 1.47.0, v55, registry 72 ids 0 d old, universe 24,
gated/failed exports, inbox backlog 0, 0 open preregs); designated `7f2a697ec6c1b119`; first run → T1–T3
recorded baselines (book cells 4, refutation ids 3, registry ids 72); T4 none; T5 none; 800 enumerated
(the cap above). `2026-W38-20260914T043217Z` (after the fix): 20,000 enumerated in 44 s; T1–T3 "unchanged"
against the first record; T4 "no stale near-floor cell outside the book"; T5 "no dark cell in this run's
sample" — **the daemon's sweep already covers every cell a 20k sample reaches, so the weekly run does
nothing until a trigger fires. That is the design, observed.** Exit 0 both times; nothing submitted.

**Not done, on purpose.** No end-to-end T1–T4 run test (their pure logic has 23 tests; a two-run
designation-flip fixture is the dry-run weeks' first addition). The units stay uninstalled; cutover
waits on Crucible's stream and the relayed instant (D409). `run.py::_run_battery` duplicates
`_run_battery_for_seed`'s context build — Batch 6 consolidation. `enumerated_by_hypothesis` is counted
over the whole sample.

**Next.** Dry-run weekly by hand (`forge campaign --dry-run --forge-db "$(scripts/live_db_snapshot.sh)"`)
for two weeks, comparing the plan against what the daemon submits; relay the record schema (done in this
session); then Batch 4 cutover per plan §12.6 once the stream is live.

## D411 — 2026-09-14 — the dry-run weeks are AUTOMATED: `forge-campaign.timer` installed and enabled (Sunday 03:00 UTC) in a mode-guarded unit — `dry-run` now, `live` at the cutover by one operator edit

**Operator:** "we should have a timer that runs, we need this automated." The hand-run ritual D410
described lasted one day.

**What shipped.** `scripts/campaign_run.sh` (8 tests) is the unit's `ExecStart`; the unit carries the ONE
operator decision as `Environment=FORGE_CAMPAIGN_MODE=dry-run|live`. `dry-run`: `live_db_snapshot.sh`
(reuses the prereg-watch snapshot when < 12 h old) then `forge campaign --dry-run --forge-db <snap>` —
a plan and a `campaign_run/v1` record every Sunday, nothing submitted, the daemon untouched. `live`:
refused with exit 2 while `forge.service` is active (the daemon owns the live DB and the run's
reconcile writes; an accidental daemon stop must not turn a Sunday into a live submitting run before
Crucible's 14-day stream exists, D409 §4.1); otherwise `forge campaign` on the live DB. Any other value
is refused. No `SuccessExitStatus`; `MemoryHigh=16G` / `MemoryMax=24G` (the first timer run peaked at
**13.8 GB** — cell stats over the 9 GB snapshot plus a 20k enumeration — on the box whose Crucible
services OOM'd twice; fail the unit rather than starve them; the query is a Batch 6 optimisation
target). Installed as symlinks like the other units; `daemon-reload`; `enable --now`. Next fire:
2026-09-19 20:00 PDT = Sunday 03:00 UTC.

**Smoke start through the unit (`systemctl --user start forge-campaign.service`):** `Result=success`,
45 s wall, record `2026-W38-20260914T044046Z` — boot 8/8, designated `7f2a697ec6c1b119`, all five
triggers quiet against the D410 baselines, 20,000 enumerated, submitted 0. Three records now exist for
W38; next Sunday's is the first unattended one.

**The cutover (plan §12.6 Batch 4) becomes:** stop the daemon and its three retiring timers → edit the
unit's mode line to `live` → `daemon-reload` → relay the instant. Docs: MANPAGE (`forge campaign`,
SCRIPTS row, timers), HOW-TO (Monday check + the situation entry), architecture timers list,
NEW_BOX/setup_new_box (five timers, the fifth script). Nothing else changed; suite green; daemon
unchanged.
