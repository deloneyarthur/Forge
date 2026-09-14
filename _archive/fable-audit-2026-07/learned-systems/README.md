# Learned-systems audit — Forge learning models & their performance (2026-07-01)

**Written by:** Claude Fable 5, learned-systems audit session, 2026-07-01 (~15:00 UTC).
**Audience:** a future agent (e.g. Opus) or the operator picking this up cold. Everything
load-bearing is in these three files; no conversation context is required.
**Scope:** the learned-model systems — F3 verdict ranker, wf_p25 quality lane, the
gate-then-tail rewire, and the yield-map / hypothesis-weight estimand — their implementation
AND their measured live performance, plus the promotion/MLOps discipline around them
(streak gates, drift monitor, alpha-budget/prereg, trial counting).

**Companion audit:** `fable-audit/codebase-quality/` (README, FINDINGS.md, WORKPLAN.md) is a
*separate, concurrent* Fable session's codebase quality/structure audit (src architecture,
tests, tooling, hygiene). The two are complementary and were written the same day; a few items
overlap (committing the dirty tree, the missing gate-then-tail D-entry, `rejection_weights.py`
dead code, `main.py` loader duplication) — if executing both, land each shared hygiene item
once and tick it in both plans. Its README also records suite/lint state at the snapshot
(1,744 passed / 1 failed — the MANPAGE-mentions test missing `forge ranker-model eval-rewire`,
which is the same undocumented 06-26 work this audit's P0.2 covers).

## Files

| File | Contents |
|---|---|
| `01-scorecard.md` | Per-system state: what it is, where it lives (file:line), what the live evidence says, defects — plus the status of every item from the June review (B1–B13) and the verified-healthy list |
| `02-plan.md` | Prioritized work plan P0–P5, each item with what/why/how/acceptance criteria/gates/effort |
| `03-evidence.md` | Raw numbers with provenance and the exact commands to reproduce each measurement |

## Relationship to prior work

- `LEARNED_SYSTEMS_AND_GENERATION_REVIEW.md` (repo root, 2026-06) — the prior deep-research
  audit; its items are cited as **B1–B13** throughout. This audit is the "what happened since,
  and what does the live data say now" follow-up.
- Decision log (`IMPLEMENTATION_DECISIONS.md`): D149 (F3 wired), D193 (quality-lane flip),
  D207 (alpha-budget), D208 (prereg), D209 (drift monitor), D212–D216 (PBO worldview shift →
  D216 orthogonal-family floor). **D212–D216 were UNCOMMITTED in the working tree at audit
  time.** The 06-26 gate-then-tail work (commits `edb03e6`, `fdeed29`, `92e9061`, `ceeefa4`)
  has **no D-entry** ("D-entry deferred" in `edb03e6`'s message — never written) and no
  STATUS.md block; its design record is `docs/proposals/quality-lane-rewire.md`.
- Business context that sets the priorities (see `STATUS.md` 06-25→07-01 blocks + D212–D216):
  the binding promotion gate is **PBO/dimensionality (0.4)**, not edge magnitude. Crucible
  measured single-name `volatility_event` as the in-v1 second factor (PC1 load 0.10; the mixed
  trend/MR + vol_event book clears real CSCV PBO **0.107** « 0.40 — first promotable book
  reachable in v1). So the learned systems' jobs, in order of business value: (a) don't
  degrade the stream, (b) rebalance family mix toward orthogonal (vol_event) supply,
  (c) surface robust/promotable configs first.

## Snapshot caveat — READ FIRST

All numbers and line references are a **2026-07-01 snapshot**: HEAD `ceeefa4` (last commit
06-26) **plus uncommitted D216 changes** in `src/forge/feedback/rejection_weights.py`,
`src/forge/cli/main.py`, `src/forge/cli/healthcheck_cmd.py` and their tests. Before acting:

1. Re-verify line numbers by grep — the tree moves daily.
2. Re-pull live evidence via `03-evidence.md` commands — streaks, per-model ICs, and the
   family mix all drift daily (the mix *oscillates*; a one-day read misleads).
3. Read `STATUS.md` top block + any D-entry newer than D216 — a later session may have
   executed part of `02-plan.md`. Update these files rather than duplicating work.

## Rules of engagement (from CLAUDE.md / docs/tasks/ — non-negotiable)

The parent `fable-audit/README.md` §"Rules of engagement" is the fuller list; the ones that
bind THIS plan specifically:

1. **This tree IS production** (editable install; reboot silently deploys the tree — D104).
   Deploys follow `docs/tasks/deploy.md`; never restart `forge.service` casually.
2. **Every learned-lane change ships flag-OFF → byte-identical**, following the existing
   pattern (`--quality-rank`, `FORGE_QUALITY_RANK_MODE`, `FORGE_ORTHOGONAL_FAMILY_FLOOR`).
   Flag *flips* on the live service are **operator-gated**; building + shadow-measuring is not.
3. **Rules #6/#8 (determinism/seeded RNG)** bind everything near `enumeration/sampler.py` and
   the weight pipeline; golden-sequence pins must stay green. Rule #5 bans LLMs, **not** ML —
   deterministic learned models in-loop are fine (operator correction 06-15).
4. **Rule #2**: `crucible_contracts` is the only inter-system path; a missing export
   (e.g. `component_contributions` loader) is a gap to surface via a relay doc, never a
   workaround.
5. **Feedback/learned-weight changes** follow `docs/tasks/feedback-change.md`, and since
   D207/D208 an activation should pre-register its prediction (`forge prereg`) and be
   read against the alpha budget (`forge alpha-budget`).
6. **Never open `~/forge_data/forge.db` directly** (intermittent RW lock, even read-only
   opens fail) — `cp` to /tmp and query the copy (`docs/tasks/investigate-live.md`).
7. TDD: failing test first; §13/hard-rule behavior gets its invariant test in
   `tests/invariants/` before production code. `ruff format` only on changed files.

## TL;DR verdict

Infrastructure sound (deterministic, content-addressed artifacts, genuine shadow eval,
byte-identical reverts). F3 is decisively earning its keep (17-PASS streak, AUC ~0.86 vs
incumbent ~0.45). But:

1. **Production ranks with a configuration its own 06-26 A/B measured as a no-op** — the live
   D193 blend `P × sigmoid(ridge)` is 0.97-Spearman-identical to P alone, and P is pooled
   *anti-correlated* (−0.10) with realized wf_p25; the P-baseline top-K has a *worse* realized
   WF floor than the population mean. The built fix (gate-then-tail) is flag-OFF, and its
   shadow streak measures a **harder gate than the flag would ship** (fidelity gap).
2. **90% of the composite sort weight is promotion-blind** — the incumbent hygiene composite
   measures AUC 0.45–0.53 vs realized components (coin flip); the only outcome-trained term
   sits at weight 0.10 (B2, never revisited).
3. **The family-mix estimand fights the actual (PBO) gate** — component-rate rewards more of
   the 0.78-correlated trend/mr core; the monoculture oscillates (trend weight saturated at
   1.000 on 07-01; mix swung 81% mr → 33% trend within days) while `volatility_event`, the
   validated orthogonal family, stays pinned at the 5% exploration floor (~6.5% share).
   The D216 Layer-2 floor fix is built flag-OFF with three known gaps.
4. Most June-review Tier-1/2 items are still open: calibration (B3 — now load-bearing; P is
   3–5× over-predicted above p≈0.3), prior weight (B2), significance-based streak gates (B5),
   feature-drift + adoption gating (B6), censored feedback (B7), trial-count reporting
   (B8 — Crucible still charges n_trials=1, deflation 0.00).

Start at `02-plan.md` P0 (hours, no gates), then P1 (the live ranking path — highest leverage).
