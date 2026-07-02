# 02 — Prioritized work plan (P0 → P5)

Each item: **what / why / how / acceptance / gate / effort** (S ≈ hours, M ≈ 1–3 days,
L ≈ week+). Items are ordered by leverage-per-risk given the business context (README §context:
the binding gate is PBO/dimensionality; vol_event supply is the promotable-book fuel).
Evidence citations refer to `01-scorecard.md` (§n) and `03-evidence.md` (E-n).

Conventions for every code item: TDD (failing test first), flag-OFF → byte-identical,
`ruff format` changed files only, D-entry + STATUS.md block per increment, scoped pytest +
`mypy --strict src` before commit. Flag FLIPS and service restarts are operator-gated.

---

## P0 — Hygiene & crash-safety (S total; no operator gate except the commit itself; do first)

**P0.1 — Land the dirty tree (D212–D216) including the untracked invariants test.**
- *Why:* this tree IS production; a reboot deploys uncommitted state (D104). The D216 flag-OFF
  code is inert, but `tests/invariants/test_orthogonal_family_floor_invariants.py` is
  **untracked** — one `git clean` from gone — and D212–D216 D-entries exist only in the
  working tree. The parent audit's WORKPLAN item 1 covers the same ground — coordinate, land once.
- *How:* per `live-tree-concurrent-work-during-deploy` memory: re-`git status`, separate the
  operator's untracked relay/proposal docs from code, commit code+tests+D-entries in small
  commits. No restart needed (flag-OFF, editable-install-inert until import).
- *Acceptance:* `git status` clean of everything you own; invariants file tracked.

**P0.2 — Write the missing gate-then-tail D-entry + STATUS block.**
- *Why:* a 4-commit change to the production scorer (06-26: `edb03e6`,`fdeed29`,`92e9061`,
  `ceeefa4`) is invisible to the decision log ("D-entry deferred", never written). Session
  discipline (CLAUDE.md) and future-agent navigation both depend on it.
- *How:* one D-entry (D21x) summarizing: motivation (the 06-26 A/B, §2), the two-part form,
  flag names/defaults, the floor change in `ceeefa4`, current shadow evidence, and the flip
  gate. Backfill a dated STATUS block or annotate the 07-01 block.
- *Acceptance:* `grep gate-then-tail IMPLEMENTATION_DECISIONS.md` hits; STATUS mentions it.

**P0.3 — Guard the `FORGE_REWIRE_P_FLOOR` env parse (crash risk in the production loop).**
- *Why:* `float(os.environ.get(...))` at `main.py:2000` raises on a malformed value → daemon
  crash-loop on the next restart with a typo'd unit file. §3 defect 3.
- *How:* failing test first (malformed value → default + one warn log, never raise), then match
  the `_orthogonal_family_floors` degrade-never-crash idiom in the same file.
- *Acceptance:* test green; behavior identical for valid values.

**P0.4 — Add the two missing wiring tests.**
- (a) `FORGE_QUALITY_RANK_MODE` dispatch branch in `main.py` (blend default / gate-tail /
  invalid value → default+warn). (b) D216 call-site integration: env set → lifted weights
  reach the sampler AND the `orthogonal-family floor ACTIVE` journal line prints (the D185
  failure mode was an inert call site that passed unit tests; §4 gap 1).
- *Acceptance:* both fail before / pass after; note them in the D-entries.

**P0.5 — Two one-line fixes:** the `eval-robustness` realized-label string ("cpcv_p25" printed
under `--gate wf_sharpe_p25`; §6 nit), and document the D216 floor unit (relative-to-max, NOT
sampling share; 0.20 ⇒ delivered share floats with the oscillating max — §4 gap 2) in the
docstring + `docs/MANPAGE.md` env-var entry.

---

## P1 — The live ranking path (M; highest leverage; builds are ungated, the flip is operator-gated)

**P1.1 — Close the gate-then-tail shadow-vs-production fidelity gap BEFORE any flip decision.**
- *Why:* the shadow streak ranks with a hard gate (1e9 demotion); the flag ships a soft gate
  inside the 0.10 composite slot — the evidence validates an intervention the flip does not
  deliver (§3 defect 1). Flipping now = shipping something never measured.
- *How (pick one, A recommended):*
  - **(A)** Make production match the shadow: under `gate-tail` mode, apply the hard gate at
    queue level (below-floor configs demoted/dropped before the composite), not just via the
    prior slot. Keep flag-OFF default; byte-identical when unset.
  - **(B)** Make the shadow match production: re-run shadow/streak scoring through the full
    composite with `gate_tail_prior` in the 0.10 slot, and let THAT accumulate a streak.
  - A is preferred because B most likely just re-discovers §5 (the 0.10 slot mutes everything).
- *Acceptance:* the ranking the streak measures is bit-for-bit the ranking the flag produces
  (add a parity test: same inputs → shadow ranking == production-mode ranking).

**P1.2 — Restart the rewire streak clean and define the flip gate numerically.**
- *Why:* the streak's first record is a contaminated full-pool window counted as a look (§6);
  and "3 consecutive" has 12.5% null false-promotion (B5).
- *How:* fresh-window-only records post-P1.1; flip gate = k≥3 fresh-window PASSes on the
  *fidelity-corrected* form AND pooled Δ CI excluding 0 (the offline A/B already cleared
  Δ +0.180 CI [+0.060,+0.309] for the hard-gate form — E-3). Pre-register the flip prediction
  via `forge prereg` (what Δ on which metric over which cohort) and resolve it honestly.
- *Gate:* the flip itself (service Environment change + restart) is operator-gated, follows
  `docs/tasks/deploy.md`.

**P1.3 — B3: calibrate P(component) and monitor the floor's eligible fraction.**
- *Why:* load-bearing twice — the live blend multiplies P; gate-tail floors on absolute P —
  and live models are 3–5× over-predicted above p≈0.3 with drift across models (§1).
- *How:* held-out Platt scaling (pure-Python friendly; isotonic only if >~1000 held-out
  positives) applied at train time, stored in the artifact; track Brier(decomposed) +
  reliability + ECE per checkpoint in the eval JSONL; add ECE/reliability to the F3 PASS
  criterion (co-primary with AUC); add an eligible-fraction-under-floor metric to
  `eval-rewire`/healthcheck so calibration drift can't silently change the keep-rate.
- *Acceptance:* reliability table ~diagonal on held-out; F3 streak unaffected (AUC is
  calibration-invariant); eligible-fraction visible in `forge status` or healthcheck.
- *Note:* rescaling P changes the meaning of `FORGE_REWIRE_P_FLOOR=0.02` — re-derive the floor
  from the calibrated distribution as part of P1.1's parity test.

**P1.4 — B2: shadow-A/B the 0.10 prior weight (0.10 → 0.3 / 0.5 / 0.7).**
- *Why:* 90% of the sort measures AUC 0.45–0.53 vs realized components; even a perfect learned
  prior moves the composite by 0.10 (§5). This caps every other item and interacts with P1.1's
  soft-vs-hard choice.
- *How:* offline first (the existing shadow rows + realized outcomes support re-scoring under
  alternate weights with no live change — same method as `ab_rewire.py`); then a shadow-lane
  streak for the winner. Keep the diversifier as the diversity mechanism (D103/D136 floors)
  so a higher prior weight can't collapse variety — check post-diversifier family mix in the
  A/B readout.
- *Acceptance:* realized component/promotion yield of top-N under each weight, with CIs;
  a recommendation with a number, pre-registered before any flip.
- *Gate:* weight change in `config/ranker.yaml` = ranking-policy change → operator sign-off +
  deploy ritual.

---

## P2 — Family-mix / orthogonal supply (S build-side; activation operator-gated; PBO-aligned)

**P2.1 — Activate the D216 vol_event floor per its own protocol.**
- *Why:* the only live lever pointed at the binding gate. vol_event is floor-pinned at ~6.5%
  share while the estimand oscillates the trend/mr monoculture (§4). The 06-29 promotable book
  was 0→67% vol_event — supply is the fuel.
- *How (already scoped in D216 / `docs/proposals/orthogonal-family-supply-for-pbo.md`):*
  after P0.4's integration test: `forge prereg` the prediction (e.g. "vol_event share ≥ X% over
  N days AND Crucible book-PBO on the later cohort improves/holds vs baseline"), charge the
  alpha budget, set `FORGE_ORTHOGONAL_FAMILY_FLOOR=volatility_event=0.20` on the unit, deploy
  per ritual, verify the journal line, later-cohort confirm. Revert = drop the env.
- *Watch-out:* the floor unit is relative-to-max (§4 gap 2) — with trend saturated at 1.000,
  0.20 delivered ~10.7% share in the D216 experiment, but if the max family's weight drops the
  delivered share rises. Log the *delivered share* in the journal line so drift is visible.
- *Gate:* operator (feedback-change + service env edit + restart).

**P2.2 — Track A (estimand re-aim to marginal contribution): keep sequenced, do NOT build yet.**
- Blocked correctly on (a) the `crucible_contracts` loader for `component_contributions`
  (relay `PROMPT_CRUCIBLE_CONTRIB_LOADER_IN_CONTRACTS.md`, held) and (b) the export having
  real data (n=0 until a book promotes). Building against a null signal validates nothing.
  When unblocked: build flag-OFF, shadow the re-aimed weights against the component-rate
  weights for ≥2 weeks of family-mix + downstream-PBO telemetry before proposing a flip.

---

## P3 — Promotion & feedback discipline (M; parallelizable with P1/P2)

**P3.1 — B5: replace both streak gates with a paired, significance-based rule.**
- *How:* per-checkpoint paired statistic (challenger − incumbent on the SAME rows), fresh
  windows only, no pooling across daily artifacts; promote on a confidence-sequence/e-value or
  simple SPRT with explicit α and a minimum effect size; k≥5 if staying with a streak
  heuristic. Log any operator override as a reviewed exception in the D-entry.
- *Acceptance:* the §8.6 and rewire criteria in `ranker_model_cmd.py` (currently `:44`, `:52`)
  documented, tested, and no longer "PROVISIONAL".

**P3.2 — B6 completion: feature drift + adoption gating.**
- *How:* PSI or Jensen-Shannon on the feature vector per checkpoint (flag >0.1 / >0.25);
  label/prior-shift check; and stop blind newest-wins — at minimum, refuse to rotate to an
  artifact whose fresh-window paired IC is negative (keep training daily; gate *adoption*).
  Also surface the `_load_hypothesis_weights` warn-once silent-degrade (§6) as a healthcheck
  WARN ("hypothesis weights: uniform-fallback active").

**P3.3 — B7: a small randomized exploration holdout.**
- *Why:* every learned component trains on Forge-selected submissions (doubly-selected for the
  tail eval) — a textbook direct feedback loop; floors mitigate, don't correct.
- *How:* a deterministic (seeded, rule #8) ~2–5% of each batch bypasses ranking (random-among-
  grammar-valid-prefiltered), tagged in `submissions` so evals can split selected vs holdout.
  Gives unbiased labels to F3, the lane, AND the estimand. Charge it to the alpha budget.
- *Gate:* changes the submission mix → operator sign-off; flag-OFF build first.

**P3.4 — B8: the effective-N / trial-charging handoff to Crucible.**
- The D207 ledger already brackets the honest count (submitted-floor vs enumerated-ceiling) and
  prints "deflation 0.00". Draft the relay: should `search_n_trials` be set (and to what —
  raw counts over-deflate; effective-N via correlation clustering is the principled middle),
  and where is the accounting boundary (per-batch vs cumulative campaign)? Pure coordination;
  unblocks B11 someday. Also: adopt `confirm_promotion_claim` (D208) in the ritual docs so
  post-cut confirmation actually runs on future preregs — and stop resolving preregs on
  substituted metrics except as a disclosed, operator-approved exception.

---

## P4 — Decide the wf_p25 lane's fate on a clock (S decision + S/M execution)

**P4.1 — Set the retire-or-keep rule NOW, before more sunk cost.**
- *Why:* the lane has been live 11 days with zero proven skill: §8.6 0/3 forever, per-model IC
  decay-at-n has now recurred twice (`c66e56af` then `6b89fa04` — E-2), and the live blend
  form is a measured no-op (§2). The honest current defense is only "not harmful".
- *Proposed rule (tune with operator):* after P1.1 lands, give the fidelity-corrected
  gate-then-tail form N=3 fresh-window checkpoints (~2–3 weeks at the current cadence, given
  rotation holes). If it can't sustain the paired gate of P3.1 — or the newest models'
  per-model IC decays below ~+0.1 at n>500 again — demote the ridge head to telemetry-only
  (`FORGE_QUALITY_RANKER=off` on the blend; keep daily training + streak for the record) and
  stop carrying a second overfitting surface in the prior.
- *Also:* run the cheap wf_p25-IC-on-vol_event-subset probe (Crucible's 06-29 durability open
  question; STATUS 06-29). If the lane shows skill *specifically on vol_event*, that changes
  its value proposition even if pooled skill stays marginal — vol_event durability is what the
  promotable book needs.

---

## P5 — Deferred / opportunistic (L or blocked; revisit after P1–P3)

- **P5.1 — B9 Thompson/UCB allocation:** the Beta posteriors already exist; a seeded Thompson
  draw (rule #8 compliant) replaces mean+floors with principled exploration. Best done AFTER
  P2 settles so two family-mix interventions aren't confounded. Effort S–M, flag-OFF-able.
- **P5.2 — B11 elite archive (keep+mutate per-cell champions):** still gated on P3.4/B8
  (mutation inflates effective N). B10 (diversity as objective) and B12 (ceiling-vs-coverage
  telemetry) queue behind it.
- **P5.3 — Dead code sweep in `rejection_weights.py`** (`compute_hypothesis_weights`,
  `compute_hypothesis_reward_weights`, `_sharpe_reward`, `_run_reward`, legacy Beta(1,10)) —
  coordinate with the parent audit's duplication items; pure chore.
- **P5.4 — Model-rotation holes** (06-16, 06-27→29): check `forge-ranker-eval.timer` journal
  for skipped firings vs box downtime; a silent-skip should become a healthcheck WARN.
- **P5.5 — Report OOS R²/IC instead of train-R²** at ridge train time
  (`ranker_model_cmd.py:466`), and add precision@N/NDCG@N at the submission cutoff to evals
  (June review §5) — cheap, fold into any P1 touch of that file.

---

## Sequencing picture

```
P0.1–P0.5 (hours, now)
   ├─ P1.1 fidelity fix ─ P1.2 clean streak ──┐
   ├─ P1.3 calibration ───────────────────────┼─→ operator flip decision (gate-tail, weight)
   ├─ P1.4 weight A/B ────────────────────────┘
   ├─ P2.1 vol_event floor activation (operator) → later-cohort confirm
   ├─ P3.1–P3.3 discipline (parallel)
   └─ P4.1 lane clock starts when P1.1 lands
P2.2 / P3.4 wait on Crucible; P5 waits on the above.
```

The through-line: the stack's *measurement* machinery already told you the live blend is a
no-op, the hygiene weight is promotion-blind, and the estimand fights the PBO gate. The work
is to *act* on those measurements in the right order — fix what the flip would ship (P1)
before flipping, and un-pin the family that clears the actual gate (P2).
