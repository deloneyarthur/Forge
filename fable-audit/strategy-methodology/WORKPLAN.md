# Workplan — strategy / indicators / methodology audit (2026-07-01)

Prioritized P0–P4. Each item: action, effort (S ≈ hours, M ≈ 1–3 days, L ≈ week+), gate,
verification. Finding IDs → `FINDINGS.md`. Cross-refs: CQ/LS/PP = the sibling audit
workplans — land shared items once, tick everywhere.

Conventions for every code item: TDD, `ruff format` changed files only,
`mypy --strict src`, scoped pytest, small commits, D-entry + STATUS.md block. Anything
that changes which configs reach Crucible (filters, family retirement, thresholds) is a
population change: prereg (D208) + flag/version + later-cohort confirm (§8.4).

The organizing principle: **P0 makes the imminent D216 activation experiment honest and
disarms the one unattended write path; P1 removes the real throttle on the validated
family; P2 stops paying for dead strategy space; P3 hardens the evidence machinery; P4
is docs/backlog.**

---

## P0 — Before the D216 floor activation (days; mostly S; blocks the flip)

### P0-1. Disarm or leash §5.5 auto-tune before first promotions (MET-H3 + PRE-M4) — S; OPERATOR

The only unattended tracked-file write path in the system, keyed on a dead estimand
(per-config verdict-level promotion rate), reachable for the first time the day real
promotions land — likely at tiny denominators.
- Action: operator picks (a) `auto_tune.enabled: false` (proposal-only; recommended —
  mirrors D206's logic), or (b) keep armed + loud journal line + mandatory D-entry
  follow-up. Either way: move the 30% cumulative-cap bookkeeping off free-text parsing
  (`auto_tune.py:102–122`) to a structured column, and file the estimand re-key
  (component-rate or retire) as the follow-up.
- Verify: with a synthetic 2-batch promotion_rate > 5% fixture, no unattended
  `config/prefilter.yaml` write occurs (mode a) or the journal line + proposal appear
  (mode b).

### P0-2. Instrument vol_event by regime-gate class + per-family funnel telemetry (ENU-H1 + PRE-M5) — S–M; no gate

The activation prereg is unreadable without this: the floor lifts the WHOLE ve family,
but only the earnings-gated subset is the validated orthogonal content, and the battery
kill table was invisible until this audit.
- Action: (a) tag ve submissions/journal lines with gate class (earnings vs macro vs
  none — derivable from the regime signal ids); (b) surface per-family battery survival
  + first-failing-filter in `forge status` and the funnel export
  (`funnel/aggregate.py:38`). Telemetry-only; no behavior change.
- Verify: `forge status` shows the FINDINGS headline table live; ve rows split by gate
  class.

### P0-3. One evidence question to Crucible (ENU-H1) — S; CRUCIBLE (operator carries)

- Ask: did the PC1-load-0.10 / book-PBO-0.107 result hold for macro-calendar-gated
  vol_event comps, or only earnings-gated ones? (n=611 honest ve comps exist
  Crucible-side; zero Forge work.)
- Consequence: if earnings-only, the D216 floor (and P1 below) should target the
  earnings-gated subset, not the family — a different floor key and a different prereg.

### P0-4. Make the activation ritual honest (MET-H1 + MET-M2 + MET-M1a) — S; operator for wording

- Action: (a) fix the "charge the alpha budget" step — either rename to "re-read"
  in deploy/feedback docs or build the minimal charge ledger (M, can trail);
  (b) commit the 06-28 prereg resolution (fold into CQ item 1's tree-cleanup) and adopt
  "register at decision time, commit same day"; (c) the two prereg-tooling one-liners:
  refuse `resolve` on non-`registered` status, atomic tmp+rename on registry rewrite
  (MET-L1).
- Verify: prereg registry committed + append-only in git history; `forge prereg
  resolve` on a resolved id errors.

### P0-5. Read the D216 activation decision against PRE-H1 — S; OPERATOR (framing, not code)

The sampling floor alone delivers ~1.2k ve survivors/week because the battery kills
94.2% downstream. Present the operator both levers together: activate the floor AND
schedule P1-1/P1-2 (battery-side), with the prereg prediction written on the
*post-battery submitted share*, not the sampling share — otherwise the experiment can
"fail" while the floor works exactly as built.

---

## P1 — Un-throttle the validated family (1–2 weeks; the core producer work)

### P1-1. Fix permutation_test's two outright bugs (PRE-H2 a+b) — S code + prereg ritual; OPERATOR flip

The dominant filter for the entire pipeline (51.4% of all enumerated) reads a
single-day return at T+k instead of cumulative T+1..T+k, and shifts by CALENDAR days so
Mon/Tue activations silently lose ~40% of their sample to weekends.
- Action: failing tests first (cumulative forward return; trading-day shift via the
  returns index, not `timedelta`); implement behind a flag or as a versioned change —
  this changes the config population, so: prereg the expected effect (per-family
  survival shift), flip at a deploy window, later-cohort confirm. Coordinate with PP
  P2-3 (memoization) — land the semantics fix FIRST so the memo pins the correct
  computation.
- Verify: per-family survival deltas in the P0-2 telemetry; no weekday-of-activation
  systematic in survivor composition afterward.

### P1-2. Preregistered per-family battery A/B for vol_event (PRE-H1 + PRE-H2c + PRE-H3) — M; OPERATOR

- Action: shadow-count (no live change) what would newly survive under: (a) a
  vol-appropriate permutation null for ve (|move| / straddle-payoff proxy instead of
  signed drift), (b) family-aware signal_correlation threshold or event-pair exemption
  (first: add the S-effort rejected-pair `max_pair` logging), (c) predicted_activations
  as-is (control). Then propose the narrowest change that lifts ve survivors with a
  prereg on post-battery ve share + downstream book-PBO hold.
- Gate: operator + prereg; any live filter change is a population change.
- Verify: shadow counts in a one-off report; then live per-family survival vs the
  prereg prediction.

### P1-3. Activate the 4 idle iv_structure directionals for vol_event (GRM-H1) — M; OPERATOR grammar bump + Crucible data

- Action: re-rate Q41 for the ve slice; D131-style activation audit (live feature-cache
  threshold audit + `signal_horizon` classing) for `iv_vs_index`, `skew_25d`,
  `butterfly_25d`, `vol_of_vol` as single-name ve directionals; grammar bump + archive +
  D-entry per hard rule 10. Sequence AFTER P0-3's answer (if the validated content is
  earnings-gated, scope thresholds to that context).
- Verify: new ids appear in ve enumeration at expected rates; battery survival of the
  new signals tracked via P0-2 telemetry.

### P1-4. Percentile emission for ve's absolute-range directionals (ENU-M4) — M; OPERATOR grammar bump

- Action: migrate dealer-wall distances and `iv_minus_rv`/`iv_term_slope` from
  SPY-calibrated absolute ranges to the D099 percentile pattern (or re-audit ranges per
  underlying class). Can ride the same grammar bump as P1-3.
- Verify: ve gate fire-rates per underlying class before/after; no dead-gate
  underlyings.

### P1-5. Premium-R exits for vol_event (GRM-M2) — M; OPERATOR + cheap Crucible read first

- Action: ask Crucible for a cheap read on exit-shape → tail/PBO from existing gated
  data; if supportive, S5 amendment adding `delta_floor_stop` / `premium_r_target` /
  `premium_r_time_stop` to ve's `optional_additions` (grammar bump; prereg).
- Why here: exits are ve's narrowest variety axis and the identified
  trade-count-neutral tail lever — durability is Crucible's open question.

---

## P2 — Stop paying for dead strategy space (days; mostly S)

### P2-1. Retire event_momentum from enumeration, or justify it (GRM-M3 + PRE-M1 + ENU-M1) — S; OPERATOR

- 12.5% of the enumeration budget, 99.8% battery-killed, structurally never-ranks, v12
  rationale explicitly refuted by v15. Action: operator memo → `DISABLED_HYPOTHESES`
  (D098 precedent) or a recorded justification; drop em from
  `RANK_COMBINER_HYPOTHESES` and fix the D214-stale comment either way (byte-identical
  — verify with the sampler goldens).
- Verify: goldens green; enumeration share redistributes per the floor logic.

### P2-2. Published-vs-table indicator inventory + triage the 3 unreviewed ids (ENU-H2) — S + M; operator for adoption

- Action: (a) healthcheck/`forge status` line "N published ids with no threshold-table
  entry and no ledger mention" (S, no gate); (b) triage `ivol`, `realized_skew`,
  `days_to_cover` via the adoption ritual — `days_to_cover` first (rank-capable,
  mechanism-distinct short-interest content inside the trend book).
- Verify: the inventory line goes to 0-unreviewed after triage decisions are logged.

### P2-3. De-dup probable identical indicators (ENU-M3) — S; Crucible + operator

- Ask Crucible: `rsi` ≡ `rsi_14`? (+ the 4 realized-vol estimators in relval's pool).
  If yes, retire duplicates at the next grammar bump (fold into P1-3/P1-4's bump).

### P2-4. Annotate/null the unreachable threshold ranges (ENU-M2) — S; no gate

- Mark hurst/adx + volatility-family directional ranges "INERT — no C2 family;
  re-audit before any C2 widening"; fixes the false comments.

### P2-5. First-promotion dry-run of the feedback chain (MET-M4) — M; no gate

- Synthetic batch with 2–3 promote verdicts through consume-feedback:
  `record_promoted_patterns`, analyzer dominance at n=2, stuck reset, auto_tune trigger
  (per P0-1's chosen mode). Decide min-n floors now; cheap insurance given the 06-29
  trajectory.

---

## P3 — Harden the evidence machinery (parallelizable; mostly S–M, ungated)

### P3-1. Prereg tooling completion (MET-M1 b+c) — S–M; no gate

- `--substituted-metric` required to resolve on a different metric (stamped,
  queryable); generalize `confirm_promotion_claim` to threshold-on-metric claims and
  wire it into the resolve path so future preregs (D216 activation, P1-1/P1-2 flips)
  resolve on the registered metric by construction. Cross-ref LS P3.4's ritual half.

### P3-2. Out-of-band submission ledger (MET-H2) — S–M; no gate

- Release-style scripts get a required ledger write (one `batch_summaries` row or a
  side JSONL the alpha-budget reader unions in). Do before the next operator-driven
  release experiment.

### P3-3. Alpha-budget charge ledger (MET-H1, the M half) — M; no gate

- Minimal: register-experiment → trial-count increment → healthcheck WARN when a
  pending flip's claimed margin < the current E[max-Sharpe] luck hurdle. Only if the
  operator opted for "make it real" over "rename the ritual step" in P0-4.

### P3-4. Stuck-state alarm fix (MET-M3) — S; no gate

- Transition-based (fires on newly-zero after a non-zero era), or move to healthcheck
  with hysteresis. Do before first promotions make the reset path live.

### P3-5. Wire-or-delete the two inert prefilters (PRE-M2 + PRE-M3) — S + M; operator input

- StructuralRedundancy: wire `prior_config_hashes` (already loaded in main.py;
  coordinate with PP P1-1/P2-4 plumbing) or spec-amend + delete. Novelty temporal
  branch: decide wire-bounded vs delete — bring the D215 selection-side-redundancy
  evidence to the operator for that call.

### P3-6. §7.4 errors-directory watcher (PRE-M6) — S/M; no gate

- Measure actual Crucible-rejection volume first; implement the watcher
  (`status='rejected_by_crucible'`) or spec-amend §7.4 out.

---

## P4 — Docs & backlog (batch into housekeeping)

- **P4-1** (GRM-M1) Rewrite R1's Why in GRAMMAR.md to the long-premium framing; close
  Q34 — S; operator sign-off; doc-only, no version bump.
- **P4-2** (GRM-L1) C2: validate all indicator families, fix the C1-misreading comment
  — S; tightening, rule-#4-legal.
- **P4-3** (GRM-L2) E3 coverage for chandelier/parabolic exits — one Crucible question
  then extend or record — S.
- **P4-4** (GRM-L3) Decide the 2026-05-15 PENDING loosen proposal (reject-as-superseded
  by D206) — S; operator.
- **P4-5** (PRE-L2) Doc rot: battery.py "seven filters" → nine; DESIGN §5.2 ordering
  note; §5.3.4 window figure — S.
- **P4-6** (MET-L2) threshold_proposer `_percentile` nit — only if the retired path is
  ever re-enabled.
- **P4-7** (ENU-L1/L2) vol_event DTE-bracket knob (hold for Crucible durability
  evidence); INDICATOR_THRESHOLDS.md regeneration script — L.
- **P4-8** (PRE-L1) regime_exposure anti-specialist stance — revisit only if
  regime-native vol signals enumerate.

---

## Sequencing picture

```
P0-1 auto-tune disarm ──┐
P0-2 telemetry ─────────┼─→ D216 floor activation (operator) ─→ later-cohort confirm
P0-3 Crucible gate-class Q ┘        │
P0-4 ritual honesty ────────────────┘ (prereg resolvable, budget step real or renamed)
P1-1 permutation fixes ─→ P1-2 ve battery A/B ─→ live filter change (operator)
P1-3 iv_structure activation ─┬─ same grammar bump window ── P1-4 percentile emission
P1-5 premium-R exits (Crucible read first)
P2 / P3 parallel; P2-5 before first promotions land.
```

The through-line: Crucible has already told you *which* supply clears the real gate
(single-name, earnings-vol, PC1 0.10). The grammar can make it, the sampler can be
floored toward it — but the battery currently deletes 94% of it with a mis-specified
directional test, the activation experiment can't see the split that matters, and the
rituals meant to keep the evidence honest are partly decorative. Fix the measurement
and the leash first (P0), then the throttle (P1); everything else is housekeeping
around that arc.
