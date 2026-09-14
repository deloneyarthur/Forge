# Fable audit — trading strategy, indicators & methodology (2026-07-01)

Domain audit of Forge's quant content, performed 2026-07-01 by Claude Fable 5 (session
"strategy/methodology audit"). This is the fourth folder in `fable-audit/`, complementary
to the three same-day audits: it covers the **strategy space itself** (grammar/§3.5,
hypothesis surfaces), **indicators & thresholds** (enumeration reachability, calibration),
**prefilter/submission methodology** (statistical soundness of the battery), and
**research-hygiene machinery** (alpha budget, preregistration, feedback rituals). It does
NOT re-audit code quality, the learned-model systems (F3 / wf_p25 / gate-then-tail /
estimand), or runtime performance — those are owned by the sibling folders; overlaps are
cross-referenced, not duplicated.

## Contents

| File | Purpose |
|---|---|
| `README.md` | This file: verdict, method, snapshot, rules of engagement. |
| `FINDINGS.md` | Complete findings with file:line evidence, in four areas (grammar, enumeration/indicators, prefilters/submission, methodology/feedback), each with a confirmed-sound list. |
| `WORKPLAN.md` | Prioritized items P0–P4, each with action, effort, gating, and verification. |

## Snapshot the audit was taken against

- Date: 2026-07-01. HEAD = `ceeefa4`, working tree DIRTY with the in-flight D216 flag-OFF
  work (same snapshot as the three sibling audits).
- Live registry snapshot consulted: `2026-07-02T010003Z` (59 published ids).
- Live funnel data: last 7 days of `batch_summaries` (276 batches, 1.38M enumerated,
  26.2% battery survival), queried on a `/tmp` copy of `forge.db`.
- Business context at audit time (from STATUS/D212–D216): the binding promotion gate is
  **PBO/dimensionality**; the one Crucible-validated orthogonal family is **single-name
  `volatility_event`** (PC1 load 0.10; mixed book CSCV PBO 0.107); the producer job is
  vol_event **quantity + durability**; the D216 `FORGE_ORTHOGONAL_FAMILY_FLOOR` is built
  flag-OFF with activation operator-gated.

## Method

Four parallel deep-dive subagent audits (grammar & strategy space; enumeration policy &
indicators; prefilter battery & submission funnel; research methodology & feedback
discipline), each seeded with the full session context including the three sibling
workplans for dedup. Read-only: the audit modified nothing outside this folder. The
prefilter agent's DB snapshot copy was left at `scratchpad/forge_snap.db` (disposable).

## Overall verdict

**No hard-rule violations. The 21 §3.5 rules are implemented as written**, version-bump
machinery is sound, determinism affordances hold, the §7.3 limiter and idempotency path
are correct, and hard rule #4 (no auto-loosening) is genuinely structural at three
independent layers. The domain debt clusters in four places:

1. **The battery, not sampling, throttles the validated family.** The prefilter battery
   kills 94.2% of `volatility_event` (vs 51.7% mr) — the D216 sampling floor sits
   *upstream* of this wall. The dominant killer (`permutation_test`, 51.4% of ALL
   enumerated configs) is mis-specified three ways, including a signed-drift null that
   structurally penalizes convex vol payoffs.
2. **The D216 activation experiment is under-instrumented and its ritual is partly
   hollow.** The floor lifts the *whole* ve family but only the earnings-gated subset is
   the validated orthogonal content (4 of 6 regime gates are macro-calendar); no telemetry
   splits them. The "charge the alpha budget" protocol step has no code referent
   (advisory-only ledger), and prereg resolution is structurally unenforced.
3. **Armed-but-wrong feedback automation ahead of first promotions.** §5.5 auto-tune is
   enabled, self-applying (writes tracked `config/prefilter.yaml`), keyed on verdict-level
   per-config "promote" — a dead estimand under book-level promotion — and its trigger
   becomes reachable the day the first real promotions land.
4. **Idle variety levers + zombie strategy space.** Four published iv_structure
   indicators and the contracts premium-R exit family have no enumeration path (both are
   vol_event variety/durability levers); `event_momentum` burns 12.5% of the enumeration
   budget at 99.8% battery kill on a refuted rationale; three published indicators sit
   on an unreviewed shelf.

## Rules of engagement

Identical to `../codebase-quality/README.md` §"Rules of engagement" — this tree IS
production (D104), operator gates on grammar bumps / loosenings / deploys / §3.5 edits,
TDD non-negotiable, determinism goldens for anything near enumeration, coordinate with
the dirty D216 files, don't "fix" known-benign signals. Additional domain-specific
cautions for this plan:

- **Any change that alters which configs survive to submission** (permutation_test fixes,
  battery threshold changes, family retirement) changes the config population Crucible
  sees — treat as a feedback/enumeration-policy change: prereg the prediction (D208),
  note it in the alpha-budget ledger, land behind a flag or version bump, and confirm on
  a later cohort (§8.4).
- **Never trade the promotion gate for supply.** Relaxing a Forge prefilter for
  `volatility_event` is rule-legal (Forge-side knob); anything touching Crucible's gate
  is not (hard rule #3).
- Several items ask Crucible one question before Forge builds anything — keep that order;
  the 06-29 lesson (measure Crucible-side first) saved a wasted grammar bump.

## Suggested pickup order

P0 first — it gates the imminent D216 activation decision and disarms the one unattended
write path (auto-tune) before first promotions can trip it. Then P1 (un-throttle the
validated family), P2 (retire zombie space), P3 (harden the evidence machinery), P4
(docs/minor). Re-verify each finding against the tree at pickup time.
