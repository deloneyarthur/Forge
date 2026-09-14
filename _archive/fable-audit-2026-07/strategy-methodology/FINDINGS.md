# Findings — trading strategy, indicators & methodology (2026-07-01)

Snapshot: HEAD `ceeefa4` + dirty D216 tree; live registry `2026-07-02T010003Z` (59 ids);
funnel data = last 7 days of `batch_summaries` on a `/tmp` DB copy. Severity: H = would
change what the operator works on this week; M = should be scheduled; L = backlog.
Cross-refs: CQ = `../codebase-quality/`, LS = `../learned-systems/`,
PP = `../pipeline-performance/`.

Four areas: GRM (grammar & strategy space), ENU (enumeration & indicators),
PRE (prefilters & submission), MET (methodology & feedback discipline).

---

## Headline empirical table (last 7d, first-failing-filter attribution)

| family | enumerated | battery survival | top killers |
|---|---|---|---|
| trend_continuation | 521k | 32.5% | permutation_test 56% |
| mean_reversion | 350k | 48.3% | permutation_test 43%, signal_correlation 6% |
| relative_value | 268k | 7.2% | permutation_test 82% |
| event_momentum | 172k | **0.2%** | expected_trades 63%, signal_density 31% |
| **volatility_event** | 68.6k | **5.8%** | permutation_test 56%, signal_correlation 21%, predicted_activations 12% |

Survivor-pool mix: trend 46.7% / mr 46.6% / **ve 1.1%**. Submitted mix: mr 70.2% /
trend 22.7% / ve 6.5% (diversifier floors re-lift ve from a tiny survivor pool).

---

## GRM — Grammar & strategy space

### GRM-H1 — The validated family's variety lever sits idle: 4 published iv_structure indicators have no enumeration path; the tracking item (Q41) is priced at a stale LOW

- Evidence: vol_event's live directional pool is 7 ids — iv_rank / iv_minus_rv /
  iv_term_slope (`src/forge/enumeration/indicator_thresholds.py:236,288,307`),
  put_call_flow (:246), 3 dealer-distance ids (:372–396). The other 4 published
  iv_structure ids (`iv_vs_index`, `skew_25d`, `butterfly_25d`, `vol_of_vol`) have NO
  threshold-table or `grammar/signal_horizon.py` entries (grep: zero hits), so
  `_INDICATOR_THRESHOLD_TABLE.get()→None` silently keeps them out of every
  directional/regime pool. `OPEN_QUESTIONS.md:864` (Q41) logs exactly this
  under-coverage but rates it LOW on a "long-premium is IC-bound, EV low" rationale
  dated 2026-06-15 — before the 06-29 inversion made single-name vol_event
  supply + durability the producer job.
- Why it matters: durability (Crucible's open transfer-fragility question) is served by
  variety *within* the validated family; all 7 candidate ids are
  `rank_per_name_coherent=False` → auto-excluded from rank
  (`enumeration/search_space.py:142`), i.e. they can only ever be the single-name form
  that won. Activation is the proven D131/D135 pattern (live-feature-cache threshold
  audit + horizon classing + version bump).
- Action: re-rate Q41 for the vol_event slice; scope a D131-style activation audit of
  the 4 ids as single-name vol_event directionals, prereg'd. **M; operator + Crucible.**

### GRM-M1 — R1's rationale of record is backwards (short-premium logic justifying a long-premium gate); Q34 open since 06-09

- Evidence: `docs/GRAMMAR.md` #R1 (~line 269): "Mean-reversion strategies make money by
  *selling rich premium*… Selling premium when IV is already low is selling lottery
  tickets" — followed by the rule enforcing `iv_rank ≤ 50` (cheap IV;
  `grammar/custom_predicates.py:289,853–861`) in a net-debit, long-options-only system.
  `OPEN_QUESTIONS.md:637` (Q34) flags this exact both-sides "Why"; still open while R1's
  gate set widened three times on top of it.
- Why it matters: GRAMMAR.md is the sync-enforced narrative for operator-owned rules; a
  backwards Why is the stale-doc trap class that caused the D153 mis-derivation. The
  *behavior* is correct for long premium; only the text argues the seller's side.
- Action: operator-approved doc-only rewrite of the R1 Why; fold/close Q34. No yaml byte
  change → no version bump. **S; operator.**

### GRM-M2 — The premium-R exit family (contracts 1.21.0) is adopted but unreachable — no S5 composition path — while exits are vol_event's narrowest variety axis and the identified tail-shaped lever

- Evidence: contracts `models.py:98–125` ships `delta_floor_stop` /
  `premium_r_target` / `premium_r_time_stop`; none appear in `_S5_HYPOTHESIS_EXITS`
  (`grammar/custom_predicates.py:83–152`) → rejected as "foreign exits" for every
  hypothesis (:499–502). Tracked as deliberate ("grammar-gated, unbuilt",
  STATUS.md:125–126) but unscheduled. vol_event's exit surface is a fixed 2-AND +
  optional `time_stop` only (:123–128); the exit/tail open question
  (`OPEN_QUESTIONS.md:885`, D163, `docs/proposals/exit-tail-shaping.md`) names exit
  shape the trade-count-neutral left-tail lever.
- Why it matters: with durability the ask, a thesis-failure delta stop and
  premium-R-unit target/time-stop are the in-paradigm exit-variety additions for the
  validated family — an S5 table edit (operator-gated grammar bump), not new data.
- Action: scope an S5 amendment adding the 3 exits to selected hypotheses'
  `optional_additions` (vol_event first), sequenced behind a cheap Crucible read on
  exit-shape → tail/PBO. **M; operator + prereg.**

### GRM-M3 — event_momentum survives on a refuted rationale; structurally never-ranks; ~0.4% of flow

- Evidence: `config/grammar.yaml:172–179` (v12: "productive form is cross-sectional…
  also rank-eligible") vs `:234–236` (v15: "EVENT_MOMENTUM STRUCTURALLY NEVER RANKS");
  em still in `RANK_COMBINER_HYPOTHESES` (`enumeration/search_space.py:111–114`) though
  the branch can never fire for it; live share 0.4% (06-29 snapshot). See PRE-M1 for the
  enumeration-budget cost (172k/week, 99.8% battery-killed) and ENU-M1 for the vacuous
  frozenset membership.
- Why it matters: a maintained hypothesis surface (S5 row, C2 row, regime pool, sampler
  params) whose designed edge form is unreachable; the D098 precedent exists for
  policy-disabling without touching the 21 rules. Verify whether the D067 exploration
  floor spends anything on it before deciding.
- Action: operator memo — DISABLE (add to `DISABLED_HYPOTHESES`) or record why
  single-name em stays; drop em from `RANK_COMBINER_HYPOTHESES` either way (dead
  branch, byte-identical — verify with goldens). **S; operator.**

### GRM-L1 — C2 validates only `indicators[0]`'s family, on a comment that misreads C1

- Evidence: `grammar/custom_predicates.py:580–590` — "signals are restricted to one
  indicator-per-family by C1, so any indicator works"; C1 guarantees *distinct*
  families, so a hand-authored multi-indicator directional signal passes C2 when only
  its first indicator's family matches. No live exposure (sampler emits 1-indicator
  directionals), but the validator is explicitly the hand-authored safety net
  (GRAMMAR.md #S1).
- Action: check all indicator families; fix the comment. Tightening → rule-#4-legal.
  **S; none (D-entry).**

### GRM-L2 — E3's zero-gain-trailing protection covers only `trailing_atr`; its D071 siblings (`chandelier_exit`, `parabolic_sar_exit`) carry no activation-threshold requirement

- Evidence: `grammar/custom_predicates.py:786–816` (id == "trailing_atr" only);
  contracts `models.py:95–101` keeps chandelier/parabolic out of `STOP_LOSS_EXIT_IDS`,
  so neither E2 nor E3 sees them — yet either is selectable as trend's *only* required
  exit.
- Action: one Crucible question (do these exits have sane activation defaults?), then
  extend E3 or record the default. **S; Crucible → operator.**

### GRM-L3 — Grammar-lane ledger hygiene

- `OPEN_PROPOSALS.md:199` holds a PENDING auto-tune loosen proposal from **2026-05-15**
  (context retired by D206; cross-ref CQ). Q34/Q41 staleness per GRM-M1/GRM-H1.
- Action: decide the 05-15 PENDING (likely reject-as-superseded). **S; operator.**

### GRM — Confirmed sound

- **§3.5 fidelity:** all 21 rules present in v22, one predicate each, matching DESIGN
  text plus documented, operator-approved amendments only (S5/D071 schema, S4/D102
  horizon input, R1/R2/R3 pool widenings — each with version bump + D-entry). Known
  divergences recorded, not silent: §3.6 "25"=21 (D001), E1 3-vs-4 mandatory exits
  (contracts wins, noted), P2 entry-side-only (logged).
- **Version-bump machinery:** archive complete v1–v22; loader byte-compares on-disk vs
  archive at the same version (`grammar/loader.py:122–142`) → silent edits fail at load.
  (Hook bypass via `--no-verify` is owned by CQ item 3.)
- **Equity ban (§13.6 / rule #7):** enforced at contracts parse time (family Literal
  excludes `equity`), pinned by `tests/invariants/test_phase1_invariants.py:21–60`; no
  C2 table admits it.
- **No refuted-region enumeration mass of consequence:** no multi-leg structures exist
  (straddle wall moot at generation); tail_hedge/regime_arbitrage policy-disabled
  (D066/D098); refuted cross-sectional relval/GICS/iv_minus_rv forms were Crucible-side
  constructions, not Forge paths.
- **vol_event structural coherence:** R3's 6-gate pool with the ETF-sentinel guard
  (`custom_predicates.py:906–957`), event-bracket DTE {17,22,32} → swing_short/mid
  (`sampler.py:160–167,800–801`), S4 horizon table with a coverage invariant.
- **Determinism affordances:** frozen canonically-ordered `SearchSpace`, deterministic
  bucket tie-breaking, rank exclusion fail-closed off published registry flags.

---

## ENU — Enumeration & indicators

### ENU-H1 — The D216 vol_event floor lifts the whole family, but only its earnings-gated subset is the validated orthogonal content

- Evidence: `volatility_event`'s regime pool is the R3 event-proximity set
  (`grammar/custom_predicates.py:264–276`, wired at
  `enumeration/search_space.py:357–358`): 6 gates of which 4 are market-wide macro
  calendar (`days_to_fomc/cpi/nfp/opex`) and only 2 are idiosyncratic-earnings
  (`days_to_earnings`, `pre_earnings_setup`). The regime draw is
  uniform-or-yield-modulated (`enumeration/sampler.py:923–986`) and nothing in the D216
  floor (hypothesis-level) or the journal telemetry splits ve supply by gate class.
  Macro gates don't trigger the single-name-only constraint (`sampler.py:289–291`), so
  macro-gated ve on a name or ETF is market-event vol — Crucible's 06-29 lesson was
  that *idiosyncratic name vol* is what loads 0.10 on PC1; orthogonality of the
  macro-gated subset is unproven.
- Why it matters: activating `FORGE_ORTHOGONAL_FAMILY_FLOOR` may spend the lifted share
  on the un-validated sub-family, and the activation prereg couldn't detect it.
- Action: before activation, split ve telemetry (journal + funnel) by regime-gate class
  and ask Crucible whether the PC1-0.10 / PBO-0.107 result held for macro-gated ve
  comps or only earnings-gated. **S–M; operator (activation protocol) + Crucible (one
  evidence question).**

### ENU-H2 — Three published indicators have zero ledger presence: an unreviewed shelf, one mechanism-distinct

- Evidence: registry publishes `ivol`, `realized_skew` (family volatility,
  `rank_per_name_coherent=True`) and `days_to_cover` (family **trend**, rank-coherent);
  none appear in `_INDICATOR_THRESHOLD_TABLE`
  (`enumeration/indicator_thresholds.py:79–407`) → dead via the defensive skip, and
  none is mentioned anywhere in IMPLEMENTATION_DECISIONS.md / OPEN_QUESTIONS.md /
  STATUS.md (grep-verified — unlike vix_term_slope/cs_dispersion/iv_vs_index/skew_25d/
  butterfly_25d/vol_of_vol, which are all deliberate, ledger-tracked non-adoptions).
  `days_to_cover` is notable: short-interest is a different *mechanism* than price
  trend, it is rank-capable, and it would enter trend's C2 pool the moment a threshold
  entry exists — relevant to the dimensionality hunt even inside the trend book.
- Why it matters: no standing published-vs-table inventory exists, so Crucible shelf
  drops go unreviewed silently.
- Action: add a cheap inventory diff (healthcheck WARN or `forge status` line:
  "N published ids unreviewed") + triage the three via the D131/D135/D138 adoption
  ritual. **S inventory (none); M adoption (operator grammar bump).**

### ENU-M1 — `RANK_COMBINER_HYPOTHESES` carries a D214-stale rationale and a vacuous member

- Evidence: `enumeration/search_space.py:101–113` — the comment "vol_event … already
  clears breadth via recurring events" is exactly the enumeration-policy rationale D214
  declared stale under PBO; and `event_momentum`'s membership is vacuous: its only
  directional (`sue`) and only regime (`days_since_earnings`) are both
  `rank_per_name_coherent=False`, so `_uses_single_name_only_indicator`
  (`sampler.py:368–385`) always blocks the rank branch before any rng is consumed
  (`sampler.py:694–698` short-circuits) — removing em would be byte-identical.
- Action: correct the comment (the actual gate is Crucible rank-coherence
  certification, not D109 policy); drop or annotate em (goldens verify). **S; none.**

### ENU-M2 — Inert threshold-table entries with false comments are a latent wrong-activation trap

- Evidence: `hurst` `directional_range=(0.40,0.50)` commented "mean_reversion
  directional" (`indicator_thresholds.py:117–122`) — false: family `trend_strength` is
  in no hypothesis's C2 list (`custom_predicates.py:156–187`), so hurst/adx can never
  be directionals. Same for the whole volatility family's directional ranges
  (`realized_vol`, `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol`, `atr_pct`)
  and `amihud` — reachable in no directional pool; their regime ranges reachable only
  via relative_value's open pool.
- Risk: a future C2 widening silently activates never-audited, possibly wrong-signed
  ranges.
- Action: null or annotate the unreachable ranges ("INERT — no C2 family; re-audit
  before any C2 widening"). **S; none.**

### ENU-M3 — Probable duplicate-content pairs double-weight sampling mass

- Evidence: `rsi` and `rsi_14` carry identical specs
  (`indicator_thresholds.py:81–90`) and both sit in mean_reversion's directional pool;
  if Crucible's `rsi` defaults to period 14 they are the same signal → MR mints
  near-duplicate configs under distinct config_hashes (structural-redundancy keys on
  ids, not content), wasting submissions and inflating effective-N. Same question for
  the 4 realized-vol estimators in relval's gate pool.
- Action: one-line ask to Crucible (is `rsi` ≡ `rsi_14`?); if yes, retire one at the
  next grammar bump. **S; Crucible + operator.**

### ENU-M4 — Absolute threshold ranges are SPY-calibrated but drawn against a high-idio-vol single-name pool

- Evidence: the table's provenance is the 2026-05-14 SPY audit
  (`indicator_thresholds.py:9–11`); dealer wall distances (`call_wall_distance_pct`
  0.5–2.5%, `put_wall…` −3–−0.5%, `:370–394`) and vol-scale gates are explicitly
  SPY-typical, yet underlying draws concentrate on AAPL/NVDA/TSLA/MSTR/COIN where wall
  distances and vol run 2–5× wider — mis-scaled ranges mean quiet gates / thin fire
  rates. D099's percentile emission solved this for MR oscillators but ve's dealer
  directionals and `iv_minus_rv`/`iv_term_slope` (calibrated on 1–6 names, `:276–311`)
  still use absolute ranges.
- Why it matters now: fire-rate and durability of vol_event supply is the current
  producer job.
- Action: re-audit ranges per underlying class or migrate ve directionals to percentile
  emission. **M; operator (grammar bump).**

### ENU-L1 — vol_event's event-bracket DTE shape is a single hardcoded hypothesis

- `_VOL_EVENT_LEAD_DAYS=(5,10,20)` + fixed 12-td post-window (`sampler.py:166–167`);
  D169 widened only the exit ladder. If Crucible's durability probe implicates entry
  timing, this is the knob. **L; hold until evidence.**

### ENU-L2 — INDICATOR_THRESHOLDS.md regeneration

- Properly warning-headed post-D154 (drift contained), but the underlying distributions
  are 2020–2025 SPY; a regeneration script would beat another hand-addendum. **L; none.**

### ENU — Confirmed sound

- Fail-closed rank exclusion keyed on published registry flags
  (`search_space.py:142–150`); new indicators ship rank-excluded until certified.
- No-empty-threshold-leak defense in depth: not-in-table → skippable
  (`indicator_thresholds.py:503–535`), sampler assert (`sampler.py:606–620`), invariant
  test — new registry ids cannot silently emit dead signals.
- Determinism identity honest: universe pool and auto-tightenings fingerprinted into
  batch identity (`sampler.py:263–274`, `indicator_thresholds.py:484–500`);
  threshold-table edits ride grammar bumps (v17/v18/v19 precedent), pinned by
  cold-start goldens.
- Auto-tightening loader enforces tighten-only against D031 baselines (hard rule #4),
  survives the D206 emptied-yaml state.
- ETF/earnings-gate incompatibility enforced at sample time
  (`sampler.py:289–291,348–350`).
- Exploration floors (D067) present on every learned-weight axis in the sampler.

---

## PRE — Prefilters & submission funnel

### PRE-H1 — The battery is the bottleneck on vol_event supply; it kills 94.2% of the validated orthogonal family (vs 51.7% mr)

- Evidence: headline table; killers at `prefilters/permutation_test.py:82`,
  `prefilters/signal_correlation.py:49`, `prefilters/predicted_activations.py:61`.
- Why it matters: the producer job (06-29/D216) is single-name vol_event quantity, and
  the D216 sampling floor sits *upstream* of this wall — lifting sampling 2.9%→10.7%
  yields only ~1.2k ve survivors/week for the diversifier to choose from, and the
  survivors are adversely selected toward directional character (they passed a
  signed-drift test). The Crucible-measured PC1 load 0.10 was measured post-filter, so
  orthogonality of the *surviving* stream is not in question — quantity and
  within-family variety are.
- Action: before/with D216 activation, run a preregistered per-family battery A/B
  (relax the three killers for `volatility_event` only, shadow-count what would newly
  survive). **M; operator (prereg D208 + alpha budget D207).**

### PRE-H2 — permutation_test is the dominant filter (51.4% of ALL enumerated) but its estimator is mis-specified three ways

- (a) It reads the **single-day** return AT T+5, not the cumulative T+1..T+5 forward
  return (`permutation_test.py:97,100` — `returns(target_dates)` at shifted dates), so
  the D075 "T+k forward returns" intent tests one noisy slice of the drift it claims to
  test. (b) The shift is **calendar** days (`timedelta(days=horizon)`, `:97`): Mon/Tue
  activations land on weekends and are silently dropped by `returns()`
  (`prefilters/crucible_feature_cache.py:420–440`) — ~40% weekday-systematic sample
  loss. (c) The null is signed underlying drift; for long-option vol timers the payoff
  is convex (|move|/vega), so the test penalizes exactly the family the pipeline needs
  (part of PRE-H1). Also (d): ~1.38M tests/week at p≤0.10 with no multiple-testing
  accounting — the concrete face of the `search_n_trials` question (overlaps LS
  P3.4/B8; coordinate).
- Action: fix (a)+(b) — S code, but it changes the config population Crucible sees, so
  prereg + flag/version the flip; scope (c) into PRE-H1's A/B. **S–M; operator.**

### PRE-H3 — signal_correlation's 0.85 Jaccard kills 21% of vol_event vs 2–6% elsewhere: event-clock signals co-fire by construction

- Evidence: `signal_correlation.py:68–75`; kill table. Two earnings-anchored signals
  sharing the event calendar are near-Jaccard-1 without being informationally redundant
  in P&L terms — the threshold is calibrated for continuous indicators.
- Action: measure the rejected-pair composition (log `max_pair` for rejects, one
  journal line), then family-aware threshold or event-pair exemption.
  **S measure (none) / M change (operator).**

### PRE-M1 — event_momentum is a zombie family: 99.8% battery-killed, yet burns 172k enumerations/week (12.5% of the budget)

- Evidence: table; `prefilters/expected_trades.py:210` (bucket-level reject regardless
  of individual config; 63% of em kills) + signal_density (31%).
- Why it matters: whether em *should* be dead (PEAD refuted) is a science/policy
  decision — currently a Beta posterior is making it silently while the enumeration
  budget keeps paying. Pairs with GRM-M3.
- Action: explicitly retire em from enumeration (policy, operator-gated) or justify the
  bucket. **S; operator.**

### PRE-M2 — StructuralRedundancyFilter is inert in production

- `prior_config_hashes=frozenset()` at `cli/main.py:296,1318`; zero rejections in 7d.
  Dupes only caught at DB-insert (`submission/submitter.py:203`) after full
  battery+ranking. Low waste post-D069, but §5.3.1 is dead machinery misrepresenting
  the funnel.
- Action: wire it (hashes already loaded elsewhere in main.py — coordinate with PP
  P1-1/P2-4) or spec-amend + delete. **S; none.**

### PRE-M3 — Novelty's temporal-Jaccard branch is inert in production

- `prior_firing_dates={}` at `cli/main.py:297,1319`; only exact structural fingerprints
  fire (184/week). DESIGN §5.3.5's "prevents flooding Crucible with minor variations"
  never runs, while selection-side redundancy (within-MR corr 0.724, D215) is the known
  wall.
- Action: wire a bounded version (last-N submissions' firing sets) or spec-amend +
  delete. **M; operator input on which.**

### PRE-M4 — §5.5 auto-tune targets a dead estimand

- Rolling per-config `promotion_rate` bands 0.5%/5% (`feedback/auto_tune.py:280–299`)
  under a regime where promotion is book-level and per-config promotion is ~0 by design
  → standing deduped loosen-proposal noise; tighten branch unreachable — until first
  promotions make it reachable at small n (see MET-H3, the armed-write half of this
  finding).
- Action: retire (mirrors D206's logic) or re-key to component-rate. **S; operator.**

### PRE-M5 — Telemetry gap: the headline kill table was derivable but invisible

- Per-family×filter data exists (`submission/submitter.py:354`, D064) but `forge
  status`/healthcheck/funnel export surface none of it (`funnel/aggregate.py:38`
  exports only per-version totals; zero hits in `status_cmd.py`/`healthcheck_cmd.py`).
- Action: add per-family battery-survival to `forge status` + the funnel export
  (complements ENU-H1's gate-class split). **S; none.**

### PRE-M6 — DESIGN §7.4 (errors-directory watcher) is not implemented

- Zero hits in src for the `status='rejected_by_crucible'` path. Crucible-rejected
  configs linger as `submitted` until the D052 age-out, mildly depressing the §7.3
  completion fraction; the "grammar drift hint" feedback is lost.
- Action: verify actual error volume, then implement or spec-amend. **S/M; none.**

### PRE-L1 — regime_exposure hard-rejects >80% single-regime concentration

- `prefilters/regime_exposure.py:67`; near-inert today (592/1.38M) but philosophically
  anti-specialist under book-assembly; revisit only if regime-native vol signals
  enumerate. **L.**

### PRE-L2 — Doc rot

- `prefilters/battery.py:4` "seven canonical filters" (nine); DESIGN §5.2 table lists 7
  with pre-T1.3/T2.6 ordering; §5.3.4 "4 years" vs `data_history_days` (~8.4y). **L.**

### PRE — Confirmed sound

- **§7.3 limiter:** three independent guards correct — oldest-batch completion (D046),
  stall guard with deadlock-proof decision-clock predicate
  (`submission/rate_limiter.py:260–306`), depth cap whose watermark exactly mirrors the
  flush (`:309–355`); H-1 sentinel exclusion (`:197`); conservative failure direction
  everywhere. Design margin fine (600 cap ≈ 25h Crucible drain).
- **Idempotency (rule 9):** unique index + M-10 single-transaction crash safety
  (`submitter.py:184–254`) + atomic inbox write + deterministic batch UUID.
- **Battery orchestration:** cost-tier short-circuit; M-5 `data_unavailable` separation
  protecting the D076 priors; M-2 prefetch loads the true permutation null pool.
- **expected_trades:** two-mode design (D076 posterior + cold-start fallback + H1
  structural rank estimate); M-8 tighten semantics; D095 significance-score rescale.

---

## MET — Research methodology & feedback discipline

### MET-H1 — The alpha budget is advisory-only, but activation rituals treat it as chargeable

- Evidence: `feedback/alpha_budget.py:1–38` ("pure read-side telemetry — never read by
  the production loop"); `cli/alpha_budget_cmd.py:87` (read-only report); D207 entry
  (`IMPLEMENTATION_DECISIONS.md:5124`) confirms "NOT wired into the production loop".
  No charge operation, no refusal path, nothing binding anywhere in src/. Yet the D216
  activation protocol and STATUS.md 07-01 both list "charge the alpha budget (D207)" as
  a protocol step — a step with no code referent, so it silently no-ops.
- Why it matters: honest evidence is the product; a budget everyone believes is binding
  but that cannot bind launders search breadth as "accounted for."
- Action: either build a minimal charge ledger (register experiment → increment trial
  count → WARN in `forge status`/healthcheck when a pending flip's claimed margin <
  current luck hurdle), or rename the ritual step to "re-read the alpha budget" in the
  deploy/feedback docs. **S (ritual wording; operator) / M (charge ledger; none).**

### MET-H2 — Out-of-band submission channels are invisible to the trial ledger

- Evidence: `scratchpad/release_relval_sample.py:172` and
  `scratchpad/release_volevent_sample.py:216` submit via `submit_candidate` directly
  with deliberately NO `submissions`/`batch_summaries` rows; the king arm used a
  separate DB. `read_budget_rows` (`alpha_budget_cmd.py:34–48`) reads only
  `batch_summaries` — so exactly the deliberate, operator-driven experiments (the
  highest-selection-pressure trials) are the ones the breadth ledger under-counts.
- Action: give release-style scripts a required `--ledger` write (one `batch_summaries`
  row per release, `enumerated_count=len(pool)`), or a side JSONL the alpha-budget
  reader unions in. **S–M; none.**

### MET-H3 — §5.5 auto-tighten is armed, self-applying, and about to meet its first trigger-able data

- Evidence: `config/prefilter.yaml:49` `auto_tune.enabled: true`; the daemon runs
  `--consume-feedback` (forge.service ExecStart) → `auto_tune()` every iteration
  (`cli/main.py:1517`); the tighten branch **writes git-tracked
  `config/prefilter.yaml` autonomously** (`feedback/auto_tune.py:199–227`) when the
  2-batch rolling `promotion_rate` > 5%. `promoted` keys on the per-config Crucible
  verdict (`feedback/types.py:89`), not the honest book-level publish filter — D215
  already produced a promote verdict the pipeline later disowned. With first real
  promotions imminent (06-29 promotable book), a small-denominator batch pair can trip
  an unattended prefilter tighten: a tracked-file write that dirties the production
  tree (D104), changes filter behavior with no D-entry, and contradicts the operator's
  "prefilter tightening RETIRED (D206)" mental model (D206 retired the *threshold*
  path; this §5.5 calibration path is a different, still-armed mechanism). Secondary:
  the 30% cumulative cap is recovered by string-parsing `step_pct=` out of free-text
  `change_description` (`auto_tune.py:102–122`) — format drift under-counts and the cap
  silently loosens.
- Action: operator decision NOW, before first promotions: set `enabled: false`
  (proposal-only mode), or keep armed but emit a loud journal line + require the
  D-entry follow-up; move the cap to a structured column while touching it.
  **S; operator.** (Pairs with PRE-M4 — same mechanism, estimand half.)

### MET-M1 — Prereg resolution is structurally unenforced; the tested guard has zero production callers and can't express real claims

- Evidence: `confirm_promotion_claim` is called only by its own tests (grep:
  src/ + scripts/ = 0 call sites); its signature handles only promotion-*rate* bounds
  (`feedback/preregistration.py:75–111`), while the one real prereg ever registered was
  a max-percentile-metric claim it cannot express — so resolution was necessarily
  operator free-text, and was metric-substituted (disclosed, operator-accepted). Also
  structurally allowed: re-resolving an already-resolved entry (no status check,
  `preregistration.py:139–161`), backdated `--cohort-cut` at registration
  (`cli/prereg_cmd.py:52–59`), evidence text with no tie to the registered metric.
- Action: (a) refuse `resolve` unless status is `registered`; (b) require
  `--substituted-metric <name>` to resolve on a different metric, stamping the entry so
  substitutions are queryable; (c) generalize the confirm helper to
  threshold-on-metric claims. Cross-ref LS P3.4. **S–M; none.**

### MET-M2 — Prereg practice is thin and its tamper-evidence is currently broken by an uncommitted resolution

- Evidence: `config/preregistrations.jsonl` contains exactly ONE entry in its entire
  history; the registration was committed before its test (good — blob `d023b4b`), but
  the 06-28 resolution has sat uncommitted for 3 days — precisely the failure mode the
  git-based tamper-evidence design (`preregistration.py:12–14`, D208) can't tolerate.
  Multiple prune/retarget-class decisions since D208 (gate-then-tail rewire, D206
  execution) shipped with no prereg.
- Action: commit the resolution (fold into CQ item 1); adopt "register at decision
  time, commit same day" as a standing rule; surface open/uncommitted-registry state as
  a healthcheck WARN. **S; operator (rule).**

### MET-M3 — The stuck-state WARN is saturated and therefore mute

- Evidence: `feedback/stuck_state.py:44` threshold 10 zero-promotion batches; zero
  promotions is the known steady state pre-first-promotion, so the WARN
  (`cli/main.py:1558–1562`) prints every iteration. An always-on alarm can't alert on
  the failure it was built for (sterile grammar / pipeline bug).
- Action: downgrade to a rate-of-change alarm (WARN on *transition* to zero after a
  non-zero era) or move to healthcheck with hysteresis. **S; none.**

### MET-M4 — The feedback stack keys on verdict-level "promote"; its first-promotion behavior is untested at small n

- Evidence: `feedback/types.py:89` read-through; the day real promotions land, one
  batch simultaneously fires `record_promoted_patterns` (`cli/main.py:1503–1504`),
  dominance-pattern proposals at `_MIN_PROMOTED_FOR_PATTERN = 2`
  (`feedback/analyzer.py:37` — 80% dominance from n=2 is near-guaranteed), the
  auto_tune trigger (MET-H3), and the stuck reset. Nothing has ever exercised this path
  with non-zero promotions in production.
- Action: dry-run the feedback chain on a synthetic first-promotion batch (fixture with
  2–3 promotes) and decide the min-n floors BEFORE the event. **M; none.**

### MET-L1 — Prereg registry rewrite is not atomic

- `resolve_preregistration` uses `path.write_text` (`preregistration.py:160`) while
  `proposal_writer`/`auto_tune` both use tmp+rename for exactly this reason. A kill
  mid-rewrite truncates the registry (loader silently skips bad lines,
  `preregistration.py:114–129`). **S; none.**

### MET-L2 — Retired-path nit

- `feedback/threshold_proposer.py:221–230` `_percentile` maps pct→`quantiles` index
  approximately (`int(pct)-1`, clamped) — fine at 5/95, wrong for fractional pcts.
  Path retired (D206), fail-closed at the loader; fix only if re-enabled. **S; none.**

### MET — Confirmed sound

- **Hard rule 4 is genuinely structural, at three independent layers:** proposer emits
  tighten-only (`feedback/proposer.py:16–18`); `apply_tightening` raises on a loosen
  proposal (`prefilters/calibration.py:351+`); the threshold loader re-validates every
  entry against D031 baselines and drops anything wider
  (`indicator_thresholds.py:427–472`). No `apply_loosening` exists anywhere.
- **Hard rule 3:** no proposer output channel targets Crucible's gate — Forge-side
  knobs only.
- `expected_max_sharpe` correctly implements the Bailey–López de Prado E[max] benchmark
  with stdlib `NormalDist`; `n≤1 → 0` is right.
- `confirm_promotion_claim` itself is well-built (structurally excludes
  at-or-before-cut rows; conservative on malformed timestamps) — the problem is zero
  callers (MET-M1).
- OPEN_PROPOSALS flooding structurally prevented (D034 intent-key dedup, verified
  holding); all proposal/calibration writes are atomic tmp+rename.
- auto_tune's cap bookkeeping is crash-safe in the conservative direction (M-11).
- Clock/RNG discipline holds throughout feedback (`forge.core.clock.utc_now`
  everywhere; prereg IDs deterministic sha256).
- Consumer promotion-rate accounting correctly excludes export-rolloff sentinels from
  the denominator (M-7/D110).
- `trade_rate_priors` selection bias noted but adequately covered by LS P3.3
  (exploration holdout); no separate item filed.
