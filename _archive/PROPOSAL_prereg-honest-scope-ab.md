# PREREGISTRATION — **WITHDRAWN 2026-08-31, NEVER REGISTERED** (see D402)

> **⚠️ WITHDRAWN. Do not register.** Its premise is false. `honest_scope` was **not** an untried
> remedy: it went live 2026-07-22 and was reverted 2026-07-25 (`6b662ac`, Q59) because the scoping
> is **measured harmful out of sample** — robustness OOS rank-IC **0.0321 (drop) vs 0.3962
> (no-drop), 12×**; F3 OOS AUC **0.5910 vs 0.6936**. The drop is quality-correlated (9 of 81
> coefficients sign-flip) and deletes whole strata (`rank_k=20`: 55,820 rows → zero), so the model
> could not learn the k=20 cliff at any encoding.
>
> This document predicted the direction that was already refuted, on the strength of an **11×
> prevalence lift** — which is exactly the frame-statistic-for-ranking-quality substitution its own
> §1 warns against. Kept rather than deleted: a withdrawn proposal and an absent one carry
> different information.

# (WITHDRAWN) preregistration: `honest_scope` A/B for the verdict model

**Status: ⚠️ NOT REGISTERED.** Draft for operator review. Nothing has been flipped, trained or
evaluated under this. Registering it means running `forge prereg register` with the claim below,
which is what makes it binding.

## 0. The correction that shaped this design

An earlier read of `scripts/daily_ranker_eval.sh`'s header — *"the trained artifact rolls the
**shadow** model forward; F3 (live wiring) remains its own operator gate, so this cannot change
what Forge submits"* — was taken at face value. **It does not hold as written.** Traced:

```
  FORGE_F3_RANKER   unset -> defaults "on"          -> F3 is LIVE
  trainer           mv verdict_model_v1_*.json -> ~/forge_data/models/   (daily 05:02)
  production loop   load_latest_model(forge_db_path.parent / "models")   (main.py:2377)
```

**Same directory, newest-wins glob.** The daily artifact IS the model F3 loads (at daemon start).
So flipping `honest_scope` in the trainer would change the live submission path on the next
restart — it is not a shadow-only change, and this preregistration is designed around that.

**Consequence for the design: the experimental arm is trained into a SEPARATE directory and never
enters the live glob.** `forge ranker-model train` already takes `--models-dir`; no code change is
required to keep the arm off the live path.

## 1. The claim

`honest_scope=True` (D331 Part B) restricts the training POPULATION to honestly-evaluated rows.
Under the default, Crucible's `standard_window` screen lane structurally cannot produce an
honest-coverage component, so **91.0% of the frame is labelled NEGATIVE regardless of quality**
and the same `config_hash` appears in both lanes with **opposite labels** (26 of 363 paired
configs, measured 2026-07-22). Independently re-measured 2026-08-24 on the clean-era frame:

```
  measurement_basis    rows        positive-decision rate
  standard_window      386,246      5.0%
  (null)               333,742      9.6%
  fullhist_refit       148,333     86.2%     <- 17.1% of the frame, 17x the screen rate
```

Scoping keeps the same positives on ~35,674 rows: prevalence **4.988% -> 55.4%**.

**THE CLAIM UNDER TEST IS NOT THE PREVALENCE LIFT.** Prevalence is a property of the frame, not
evidence the model ranks better, and substituting one for the other is the exact error this
programme has made three times (v50's rank_k bias, the k=5 zero, the champion-improvement wall).
The claim is about RANKING QUALITY on held-out fresh verdicts.

## 2. What is measured, and against what

Two arms, both trained by the existing `forge ranker-model train`, differing in **one flag**:

```
  ARM A (incumbent)      honest_scope=False   -> ~/forge_data/models/            (LIVE, unchanged)
  ARM B (experimental)   honest_scope=True    -> ~/forge_data/models_honest_ab/  (NEVER live)
```

**Arm B never enters the live glob**, so this preregistration cannot change what Forge submits
while it runs. That property is the reason the design is shaped this way and is not negotiable
within this registration.

**Metric:** the same one the daily checkpoint already judges the live lane on — realized
`wf_sharpe_p25` of the top decile the model orders, on the **fresh** verdict window (decided since
the previous checkpoint), reported as delta vs the `P-base` baseline exactly as
`daily_ranker_eval.sh` computes it today. Using the incumbent harness rather than a new one is
deliberate: a new metric invented alongside a new arm cannot be compared to the 58-checkpoint
history that exists.

## 3. REQUIRED n, STATED AT REGISTRATION (D363/D364)

**5 consecutive daily checkpoints, each carrying >= 150 fresh verdicts** — the same threshold the
standing F3 criterion uses (">=150 fresh verdicts on >=3 consecutive checkpoints"), raised from 3
to 5 because this is an A/B between two arms rather than one arm against a floor. At the observed
fresh-window rate (~5,400 verdicts/checkpoint) that is **5 days**, so the read lands on or after
**2026-08-29** if registered 2026-08-24.

**⚠️ WATCHABILITY, stated honestly:** the D392 watcher keys on `watch: {n, basis_fp}` — a row
count in a generation basis. This clock is checkpoint-based, not row-based, so **the watcher will
report this preregistration UNWATCHABLE unless a checkpoint-count observable is added.** That is
the correct behaviour and the honest disclosure: either add the observable at registration, or
accept a manually-diarised read and know that D389 is the failure mode being courted.

**VOID CONDITION:** Crucible's universe re-rank (on or after **2026-09-03**, D391) changes the
generation basis mid-window. If the read has not completed by then, this preregistration is VOID
and re-registers inside the new basis. At a 5-day clock from 08-24 there are ~5 days of margin;
a later registration date eats it.

## 4. PREDICTED

**Arm B's fresh-window delta vs `P-base` exceeds Arm A's on at least 4 of the 5 checkpoints, and
Arm B's mean delta over the 5 exceeds Arm A's mean by more than 0.0.** One-sided: the claim is
that scoping HELPS. Anything else — worse, or indistinguishable — is a failure to confirm, and the
flag stays off.

**Stated because it cuts against the expected result:** Arm A is currently on a **58/3 consecutive
PASS streak** with fresh delta **+1.150** (2026-08-24). The incumbent is not struggling. A frame
carrying 91% structurally-mislabelled mass is nonetheless producing a model that beats its
baseline by more than a full unit of `wf_sharpe_p25`, five checkpoints out of five, for 58
consecutive checkpoints. **Any story about why scoping must help has to explain that first**, and
the honest prior is that this reads INSUFFICIENT or REFUTED rather than CONFIRMED.

## 5. ACTION IF CONFIRMED / REFUTED

**CONFIRMED** => the operator may flip `FORGE_HONEST_SCOPE` in the trainer unit (the D108 ritual:
service-unit edit, never a code default), accepting the declared **estimand shift** from
`P(component | emitted)` to `P(component | honestly evaluated)`. Confirmation authorises the flip;
it does not perform it, and the estimand shift is a separate operator judgement about what the
ranker should be estimating — not a statistical result.

**REFUTED or INSUFFICIENT** => the flag stays off, `honest_scope` is recorded as measured-and-declined
rather than untried, and the 11x prevalence lift is recorded as **not sufficient on its own** —
which is the most useful outcome for the next person tempted by a frame statistic.

## 6. WHAT THIS DOES NOT CLAIM

- It does not claim the pooling is harmless. Four measurement bases with a 17x base-rate gap and
  opposite labels on the same `config_hash` is a real defect in the frame; this tests only whether
  the built remedy improves ranking.
- It does not test `P(component | honestly evaluated)` as the better ESTIMAND. That is a question
  about what we should want, and no A/B answers it.
- It touches no grammar, so the freeze (D390) is not engaged and no §6 increment is implied.
