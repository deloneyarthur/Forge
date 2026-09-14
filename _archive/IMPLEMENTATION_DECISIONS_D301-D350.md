# Forge — Implementation Decisions archive: D301–D350

Rotated out of `IMPLEMENTATION_DECISIONS.md` 2026-09-13 (repo-simplification 2026-09, Batch 1;
D242 rotation precedent, 400 KB bar). Entries verbatim, sorted by D-number (the live file had four
out-of-order runs — D302/D303, D315/D316, D329–D338, D375/D377 — fixed here and in the live file;
content untouched), 2026-07-20 → 2026-08-02. 50 entries. Earlier slices:
`_archive/IMPLEMENTATION_DECISIONS_D001-D200.md`, `_archive/IMPLEMENTATION_DECISIONS_D201-D300.md`.

## D301 — 2026-07-20 — Bucket B round 2 (the D248 needs-owner manifest cleared): ve `|move|` flag path removed (D235 pre-authorized), `compute_hypothesis_reward_weights` + `_run_reward` + 3 weight constants removed (D105-superseded), `is_percentile_emitting` removed (never wired), pytest-cov retired; the 3 doc bugs were already fixed

Operator "ready for it" on the follow-up list D300 surfaced. Everything
verified dead/licensed before cutting; full suite **2006 green** post-removal,
mypy --strict clean repo-wide, ruff clean. Daemon untouched (no restart; none
of it is reachable in production).

1. **ve `|move|` flag path** (D235: "stays in the tree as dead-but-inert, or
   can be removed in a later cleanup" — prereg `e1a43ba8ee14` refuted +
   thesis-inverted; the flag was never On in production, grep-verified):
   `volatility_event_absolute_move` field + YAML parse out of
   `prefilters/calibration.py`; the `absolute=` branch + `ve_absolute` + the
   details key out of `prefilters/permutation_test.py`;
   `corrected_null_calibration` (the FLIP-2 arm) out of
   `prefilters/shadow_null.py`; `forge shadow-null run` reduced tri-null →
   dual-null (the `flip2_ve_absolute_move` JSONL key and FLIP-2 table are
   gone — flip-1 vs production remains). MANPAGE section rewritten. Historical
   records (preregistrations.jsonl, ledgers) untouched.
2. **`compute_hypothesis_reward_weights`** + its private `_run_reward` + the
   three D101 weight constants (TRADE_PRODUCTION/GATE_PROGRESS/SHARPE):
   superseded by the D105 component-rate lane; zero production callers.
   KEPT: `_sharpe_reward` + `DEFAULT_TRADE_FLOOR` (live in
   `_component_run_reward`). The anti-Goodhart comparison test now asserts
   the NEW estimand only (the OLD half is documented in its docstring);
   `_gated_run_graded` retained (the D103 frozen-rv tests build runs with it).
3. **`is_percentile_emitting`**: built for the D073 threshold proposer, which
   never wired it and was itself deleted at D298 — doubly dead.
4. **pytest-cov + [tool.coverage.*]**: never invoked (no --cov anywhere);
   removed from dev extras + pyproject; uv.lock re-resolved.
5. **Already fixed by prior sessions (manifest stale, no action):** the
   MANPAGE kill-switch spelling, the `FORGE_F3_RANKER` MANPAGE mention, the
   straddle proposal's REFUTED banner. **Declined:** `TABLE_NAMES` relocate
   (fine where it is; used by test_persistence).

The D248 needs-owner manifest is now fully dispatched (items done across
D295/D298/D300/D301). Related: [[D235]], [[D248]], [[D105]], [[D298]].

## D302 — 2026-07-20 — Themes 2–5 execution round 1: `forge yield-audit` (the standing dead-cell detector — first run flags 30 dead names), campaign-audit wired into the 05:00 timer + healthcheck, RELAYS.md ledger, corr-to-book ask drafted as a held relay. (Number reserved via RELAYS.md before the concurrent D303 landed — file order is chronological, not numeric)

**Operator "Let's continue to the next themes"** (after the D299 Theme 1 build).
Executed the buildable, non-operator-gated halves; everything that ships an
exclusion, carries a new ask, or touches the production write path stays gated.

1. **Theme 4 — `forge/feedback/yield_audit.py` + `forge yield-audit` (TDD, 15
   tests).** Census-class yield reads on OUR verdicts: dead names (≥500
   decided, zero conversions — the ASML/COST class) + cold cells
   ((hypothesis × dte_bucket) ≥1000 decided converting <0.25× the hypothesis
   baseline). Guards: ve ghost-label cut (imported from
   `rejection_weights.VE_GHOST_LABEL_CUT`), clean-era `since` default,
   farming-campaign hypotheses exempt from cell flags (the registry is the
   allowlist — a young sweep looks exactly like a dead cell), already-excluded
   names (imported from the sampler's frozen list, single source of truth)
   reported for retire-review but never re-flagged, zero-baseline hypotheses
   skipped. DETECTION ONLY — writes nothing; dead names print a STAGED RIDER
   DRAFT (v34/v37 terms) with the prereg step in it. **First live run
   (snapshot, 346,904 decided rows since clean era, 33,467 ghost rows cut):
   30 dead names at 0 conversions (AAL/ADBE/AMZN/ARKK/…/XOM, 513–1,139
   decided each ≈ 21k wasted decided verdicts) + 1 cold cell
   (event_momentum × swing_mid 0/1,359; NB hypothesis baseline is 0.0009 —
   arguably a hypothesis-level story) + all 8 frozen-list names at 0
   conversions (retire-review input).** CAVEAT flagged in MANPAGE + the
   proposal: cross-check dead names against the CURRENT universe before
   staging (July-shrink departures save nothing). Verdict-decision literals
   confirmed live: component/reject/promote.
2. **Theme 5c — campaign carriage into ops.** `daily_ranker_eval.sh` gains a
   final non-fatal block appending one row/day to
   `~/forge_data/ranker_eval/campaign_audit.jsonl` (exact block dry-run
   verified against a live snapshot: ratios 1.379/1.062/1.273, none starved);
   `forge healthcheck` gains `check_campaign_carriage` (WARN on starved
   campaigns — the D287 class — or a stale row; OK-with-note before the first
   fire; missing-ts WARNs). Timer picks the script up at the next 05:00 fire
   (D285 precedent) — NO restart needed; the healthcheck change is
   CLI-only.
3. **Theme 5b — `RELAYS.md`** (root): one-row-per-live-relay ledger
   (state/awaiting/D-ref), maintained at triage time. Adopted by a concurrent
   session within the hour (their D303 row) — the coordination gap it filled
   was real.
4. **Theme 3 — `PROMPT_CRUCIBLE_CORR_TO_BOOK_ASK.md`** drafted and HELD:
   additive per-gated-config corr-vs-promoted-book scalar, telemetry-first /
   prereg'd-feature-second our side, honesty blocks included. Carrying it is
   the operator's call (new-initiative ask, unlike response relays).
5. **Theme 2 — NOT built this round** (the proposal stands): 2b (cold-start
   floor generalization) is NOT byte-identical → wants its own deploy window;
   2a (ordinal targets) is the big model change and should follow 2c's label
   provenance. Sequencing unchanged: 2c → 2b → 2a/2d.

Gates: yield-audit 13+2 tests, healthcheck 15 (incl. the new levels test),
affected scope 732 green mid-build; full suite + mypy --strict + ruff at
commit. MANPAGE (yield-audit section, healthcheck + daily-eval sections),
architecture.md (feedback/ + cli/ rows), proposal status headers updated same
commit. Related: [[D299]], [[D287]], [[D290]], [[D207]], [[D286]], [[D295]],
[[D298]], [[D303]].

## D303 — 2026-07-20 — EV-estimator de-registration ACK'd (docs-only, no build): the X2 kelly chain goes dormant at their publish; our funnel independently corroborates the NO-GO (1/12,652 components, 30d); one ledger flag back (25 EV components all-time, latest 07-15 — their "zero gated" looks stale)

**Trigger:** Crucible relay `FORGE_ev_deregistration_and_api_withdrawal_2026-07-20.md` —
ask to de-register `expected_value_estimator` (family smart_money, EV-as-sizing NO-GO
their §20 `ev-sizing-p1-nogo`), plus two FYIs (optbt.* API withdrawal; 29/73
registry-vs-grammar drift).

**Verification (all their claims checked against our tree + DB snapshot):**

1. **The id is load-bearing but self-retiring.** §3.5 X2
   (`kelly_requires_expected_value_estimator`) makes EV the required chain feature of
   `fractional_kelly` — one of three uniform sizer-mode draws (~1/3 of enumeration).
   `search_space._build_sizer_mode_views` only admits a mode to
   `samplable_sizer_modes` when its X-requirement is in the registry, and the daemon
   calls `load_registry()` per batch (`_run_one_iteration`) — so the id vanishing from
   the snapshot auto-drops the mode within one batch. D258-class export-gated
   dormancy: no code change, no bump, X2 rule text untouched (vacuously satisfied;
   its alias clause anticipates a successor id).
2. **Emission today:** last 7d 4,934/79,400 submissions carry EV (6.2%); last one
   21:13:41Z. All-time 31,054 (29,799 via kelly; the ~1.2k delta = the pre-v15
   EV-confluence rank era their relay calls output-neutral). No campaign/cohort
   references it (campaigns.py clean; the 07-07 winning-cohort injection had exactly
   1, decided).
3. **Our funnel corroborates the NO-GO** (30d): EV-carrying 12,652 decided → 1
   component / 0 promote (rest of stream ~9.8% non-reject); median trades 13 vs 431;
   zero-trade 27.9% vs 1.1%. The kelly third of the draw stream is our worst standing
   allocation — the deletion is a free stream-quality lift (v33-class dead-cell
   retirement, delivered by their registry).
4. **Ledger flag (relayed):** their "zero promoted/gated/portfolio configs on disk"
   is wrong-or-stale on GATED: 25 EV-carrying components all-time (06-04 → 07-15),
   latest `606eea73a5b81609` (v33, 07-15T16:04Z, 128 trades, GM MR, EV via the X2
   chain). Doesn't change the ack; they should re-scan the gated window pre-deletion.
5. **F3/training robustness:** `ranking/features.py` is string-keyed
   (`family_by_id.get(id, 'unknown')`, sizer-mode one-hot); historical EV rows
   featurize unchanged post-deregistration. No Forge reader of their
   `meta_king_oracle` features (arm retired D190; dovetails with the D300 housekeeping
   publisher-timer ask).
6. **FYI 2 (optbt):** zero Python `optbt.*` imports in Forge (only `~/optbt_data`
   filesystem paths). Boundary question relayed: if the retirement ever renames the
   data root, that's a contracts/layout coordination item.
7. **FYI 3 (drift):** spot-checks agree (vol_of_vol/skew_25d/butterfly_25d/donchian/
   atr_pct/yang_zhang_vol: 0 grammar hits; no threshold-table entries for the
   long-premium five). The long-premium set recorded as candidate inventory for
   future signal-add work (operator-gated; not a commitment).

**Response:** `PROMPT_CRUCIBLE_EV_DEREGISTRATION_RESPONSE.md` (untracked, operator
carries; the ack takes effect on carry). Sequencing request in it: publish the
id-less snapshot at/before engine deletion + confirm in-flight EV configs fail soft
(D245 wedge-class scar). Funnel-attribution note: the mode-share redistribution
splits on **registry_hash** (grammar stays v42).

**Numbering note:** D302 is reserved by the operator's in-flight ops-debt session
(RELAYS.md cites it; file untracked at triage time). A row for the new relay was
appended to RELAYS.md but left uncommitted with the rest of that in-flight work.

Related: [[D258]], [[D245]], [[D190]], [[D276]], [[D299]], [[D300]].

## D304 — 2026-07-20 — Housekeeping answers TRIAGED (docs-only + one live probe): timer repurposed-not-meta-king (watch closed permanently), sma_slope/ad_slope WIRED + re-probe GO (v24 trend adoption real), the DSR relay was ANSWERED 07-08 all along (our D295 "held" label corrected; Q3 basis corrections recorded; the `search_n_trials` follow-up = a 12-day dropped ball, build pending), resid×vix two-arm read CLOSED (D287/D299 floor retirement licensed)

**Inbound `FORGE_housekeeping_answers_2026-07-20.md`** (their reply to
`PROMPT_CRUCIBLE_HOUSEKEEPING_ASKS.md`, same day). Every claim verified before
recording:

1. **Ask 1 (meta-king timer): KEEP — name-only staleness.** The unit was
   repurposed 2026-06-26 (their §20) and now publishes the structural
   yield-map + WF-percentile refit-sample feeds for QuantIQ's dashboard — a
   live consumer. Rename rides their next deploy-touching change. The D300
   standing watch is closed PERMANENTLY ("you can stop asking").
2. **Ask 2 (sma_slope/ad_slope): WIRED.** Their live-writer verification:
   sma_slope 378/614 / ad_slope 456/614 bars firing on SPY; our 07-07 report
   was correct at the time and became the cited motivation for their §20
   registry-drift guard (the same guard that made ref_trailing_return a
   1-restart fix). **Forge re-probe RUN (their green light, D254 ritual):
   `check-activations` GO — sma_slope max 537 / ad_slope max 440 across
   SPY/AAPL/MSFT/NVDA.** The v24 trend adoption carries for real; the
   `predicted_activations` prefilter passes carriers organically from here
   (no Forge change). Do-NOT-pull confirmed. Relay closed + verified.
3. **DSR: answered 2026-07-08 all along** — their
   `FORGE_alpha_budget_dsr_ANSWERS_2026-07-08.md` (commit `dffbb83`; the file
   later left their working tree, which is why the D295 sweep found no answer
   doc — recap re-verified against their git history, full text read).
   Corrections of record: **Q3** — deflation is on the DAILY SR with n =
   daily-return count (not trade count; the ≈1-trade/day xsect coincidence
   explained our 0.011 anchor fit), E[max] uses analytic 1/sqrt(n−1) at SR=0
   (not cross-trial dispersion), skew/kurt (plain) live in σ_obs only. **Q1**
   — n_trials = slot-scoped distinct DECIDED config count (hypothesis ×
   dte_bucket × xsect-vs-named). **Q2 (their operator, 07-08)** — no standing
   per-run DSR flip (future flip = pre-announced feedback-era boundary), and
   **Forge owes `search_n_trials` population**: per-slot cumulative distinct
   configs at submit time (per-submission sweep size acceptable as a
   conservative proxy; never global-campaign). That follow-up sat unactioned
   12 days — the F4 "unset is honest" settlement note masked the newer
   operator decision. **Build pending operator go** (hash-excluded field per
   contracts 1.19.0 — no idempotency impact). **Q4** — shipped as contracts
   1.27.0 (we adopted at v25/07-09; `measurement_basis` has been in every
   export row since — our basis analyses can drop the value-drift inference).
   Memory pillar corrected (T=trades → daily-n; "awaits carry" → answered).
4. **FYI back — the resid×vix two-arm read is CLOSED** (satellite route dead
   on BOTH chassis: 07-16 pure_sue175 + 07-20 promoted-2-leg batteries, both
   shortlists EMPTY; measured trade-off = decorrelation XOR the 2022 bear
   block). **The D287/D299 `resid-vix-two-arm` campaign's `retire_on`
   condition has FIRED** — retirement = status flip farming → retired in
   `ranking/campaigns.py` (drops the cell from `active_selection_cells()`),
   effective at the next restart. REOPENING CONDITION (recorded): a BOTH-AXES
   config from their 07-13 ask (vix-gate WF conversion + hurst-gate cpcv in
   one genome) — note C1/R2 makes a two-regime-gate genome inexpressible
   today (the Q46 multi-gate class). Build pending operator go.

RELAYS.md rows updated (HOUSEKEEPING answered same-day; SMA_SLOPE answered +
verified; ALPHA_BUDGET_DSR answered-07-08 mislabel corrected). Daemon
untouched. Related: [[D300]], [[D254]], [[D287]], [[D299]], [[D207]].

## D305 — 2026-07-20 — `resid-vix-two-arm` campaign RETIRED (operator "Retire now" on the fired retire_on): status flip farming → retired in `ranking/campaigns.py`; the derived D287 selection floor is now EMPTY; effective at the next restart

The pre-agreed condition (D287: "retire on Crucible's relay"; D299 carried it
into the registry as `retire_on="Crucible's relay closing the two-arm read"`)
FIRED via `FORGE_housekeeping_answers_2026-07-20` (D304 item 4). Change: the
`Campaign` dataclass gains a generic `retired_note` field (the
`converted_note` pattern); the resid-vix row flips to `retired` with the
closure + reopening condition recorded in-place (BOTH-AXES genome from their
07-13 ask — inexpressible under C1/R2 today, the Q46 class; their ask stays
standing). The row is RETAINED (audit trail), the cell stays on it; the
derived `EXPERIMENT_CELLS` is now empty → diversifier phase 0b reserves
nothing; `EXPERIMENT_CELL_SLOTS` falls back to the D287 default constant.
Generation-side resid supply (v33 concentrated sweep + v37 coin) is
grammar-owned and deliberately untouched.

TDD: the load-bearing derivation test flipped FIRST (red for the expected
reasons: status + missing field) → registry edit → green. ranking 307 +
campaigns-CLI + invariants 125 green; ruff + mypy --strict clean. **Takes
effect at the next daemon restart** (operator chose retire-without-restart;
until then phase 0b keeps reserving 4 slots/batch for the concluded cell —
harmless). Related: [[D304]], [[D299]], [[D287]].

## D306 — 2026-07-20 — `search_n_trials` build HELD at the verification gate (docs-only): their Q2 "populate + no flip, no boundary" is contradicted by their own live gate code — populating would flip the component stream to reject (a de-facto standing-gate flip + feedback-era boundary). Interaction relay drafted; build waits on their (a)/(b)/(c)

The operator approved the per-slot-cumulative build (D304 follow-up) this
session; pre-build verification killed the premise:

- `_dsr_gate` (`../Crucible/src/optbt/data/_runner_gates.py`) deflates the
  LIVE per-run DSR by `max(search_n_trials or 1, selection_n_trials or 1)`
  and emits `deflated_sharpe` with `passed = dsr > _MIN_DEFLATED_SHARPE`.
- `_verdict_from_gates` grants `component` only when the ONLY failures are
  WF/CPCV — `deflated_sharpe.passed` is binding inside that predicate.
- At mature-slot counts (their Q1 example 46,131) the de-facto per-run bar is
  sharpe_baseline ≥ ~1.25 (their one-off 07-03 charge killed the two
  transient promotes at 1.06/1.08 on exactly this arithmetic). Typical
  components sit in that band → stamping would flip the bulk of component
  verdicts to reject, collapsing the positive-label stream every trainer
  (F3 / tail / yield / name-weights) labels on. That IS the standing-gate
  flip and the feedback-era boundary their Q2 explicitly deferred.

**Held per the D245 both-sides-coordination class.** Today's behavior (unset
→ their n_trials=1) continues. Outbound
`PROMPT_CRUCIBLE_SEARCH_N_TRIALS_INTERACTION.md` (held for carry) asks them
to pick: (a) unbind per-run DSR from the forge-source component verdict
(recommended — deflation stays in their post-hoc family lane; we then stamp
immediately), (b) a deliberate pre-announced flip with a boundary timestamp
(we condition training windows on it), or (c) capped stamping (listed,
recommended against — under-deflates by design). The relay also carries the
sma_slope re-probe GO confirm + the resid-vix floor-retirement notice.
RELAYS.md row added. Related: [[D304]], [[D305]], [[D245]].

## D307 — 2026-07-20 — Decision round on the D302 items (operator walk-through): corr-to-book CARRIED; the 30-name rider APPROVED ("Ship all 30") → prereg `44a4e08aef4f` + v43 staged; Theme 2b young-cell floor BUILT flag-OFF (`FORGE_YOUNG_CELL_FLOOR`) awaiting its activation window

**Operator: "Let's walk through the decisions — I carried corr-to-book already
to Crucible."** Three decisions closed; two builds/stagings executed. (D306
was taken concurrently — the search_n_trials interaction relay.)

1. **Corr-to-book: CARRIED by the operator** — RELAYS.md flipped to
   `carried`; next move is theirs (additive field / decline); the telemetry
   build starts only on a yes.
2. **30-name rider: APPROVED "Ship all 30."** Decision homework run first:
   (a) universe cross-check — ALL 30 still in the 2026-07-20T184245Z export
   (DIA t1; AMZN/GE/MS/MSFT/XOM t2; 24 t3), the waste is ongoing; (b) draw
   rate — 3,092 single-name submissions in the trailing 7d = 4.7% of the
   stream (cf. the EV retirement's 6.2%); (c) the 8→38 frozen-list growth
   (32% of the union) flagged explicitly and accepted. Prereg
   `44a4e08aef4f` registered BEFORE any code (cohort cut 2026-07-21T00:00);
   **`docs/proposals/v43-dead-name-rider.md` staged** — ships as its own bump
   or rides the next Crucible-driven bump (candidate: the v39→v40 MR read
   ~07-22/23); build happens IN the deploy window per the house pattern
   (goldens re-pin, emission proof, first-batch audit, deploy relay with the
   row-45 cross-check request).
3. **Theme 2b: BUILT flag-OFF (operator "Build now, deploy separately").**
   `forge/ranking/cell_floor.py` — `compute_mature_cells` mirrors the D136
   arm-floor query one granularity down ((directional, regime) cell via
   `config_cell_from_json`, honest-era ≥25 verdicts, ve ghost rows never
   mature a cell); diversifier **phase 0c** `_reserve_young_cells` (sorted
   cells, ≤2 slots each, cap 10% of batch, double-spend-safe via the
   `already` count, hand-pinned experiment cells EXEMPT — the pin is the
   override with its own slot count, never double-served; cell-less bare
   configs never floor); queue threading; main wiring behind
   `FORGE_YOUNG_CELL_FLOOR` (default off → `mature_cells=None` → every path
   byte-identical, REBOOT-SAFE — pinned by test_none_mature_cells_is_
   byte_identical + the 4 flag tests). Journal line when active:
   `cell_floor: mature_cells=N`. WHY: the D287 pathology generalized — the
   arm-floor key (role, indicator_id) cannot protect a novel PAIR whose arms
   are individually mature; with `resid-vix-two-arm` retired (D305) the
   derived pin set is empty and this floor is what protects the NEXT
   campaign's cell on day one, automatically. **Activation = its own
   operator window** (flip the env on forge.service + restart + first-batch
   audit + a young-cell count read), deliberately SEPARATE from the v43
   bump so neither boundary carries two changes (the v35→v36 lesson).

Known scoping choice (documented in the diversifier docstring): young-cell
reservation order is sorted-deterministic like the arm floor — a fixed order
biases the same cells when over-subscribed; acceptable at the D136 precedent,
revisit with a seeded rotation (own D-entry) if the first activation reads
show over-subscription.

Suite: cell_floor 10 + flag 4 + ranking scope 321 green mid-build; full suite
+ mypy --strict + ruff at commit. MANPAGE (env-flag block + D299 note),
architecture.md, proposal status headers updated same commit.
Related: [[D302]], [[D299]], [[D287]], [[D136]], [[D305]], [[D207]], [[D290]].

## D308 — 2026-07-20 — EV deletion executed their side, VERIFIED end-to-end and CLOSED (docs-only): sequencing honored (soft-fail guard → id-less snapshot 222936Z → engine deletion 22:31–33Z); daemon pickup +1 min (iteration 2658, hash → `83e9a01ca0389e0f`); post-publish batches kelly-free by construction AND count (first = `9cca352a` 23:00:45Z; 4 batches / 800 configs, 0 kelly); 8/19 EV stragglers observed failing SOFT — but as export `error_category: "other"`, flagged back

**Inbound `FORGE_ev_deletion_executed_2026-07-20.md`** (their reply to the D303
ack, executed same-day). Every claim verified before recording:

1. **Sequencing honored exactly as requested (D303):** their soft-fail guard
   landed FIRST (their `6bc60f8` — dequeue-time preflight, any config whose
   signal indicators are no longer registered fails as a clean
   `deregistered_indicator:` bucket, permanent infrastructure for future
   de-registrations); the id-less `registry_snapshot_2026-07-20T222936Z.json`
   published BEFORE engine deletion (verified here: 72 ids, zero
   `expected_value_estimator` occurrences); engine deletion ~22:31–33Z.
2. **Dormancy pickup verified in the journal:** iteration 2658 at 22:30:11Z —
   one minute post-publish — rolled registry_hash `09b28bbbd7d79883` →
   `83e9a01ca0389e0f` (the agreed before/after split point; grammar stays
   v42). Batches were §7.3-blocked at the publish (depth ~697 vs 600, the
   backpressure working); the depth dipped below cap ~22:49Z and the FIRST
   batch under the new hash is **`9cca352a-b3d8-47d6-8d6d-dc690133aaed`
   (23:00:45Z, submitted=200)** — initially mis-recorded as `8cab6359`
   (23:59:03Z, actually the second; a watch-window artifact, corrected
   same-entry once the shell recovered).
3. **Kelly-free by construction AND by count:** with the id absent from the
   snapshot, `_build_sizer_mode_views` excludes `fractional_kelly` from
   `samplable_sizer_modes`; `rng.choice` cannot draw a mode outside the
   tuple, and the X2 chain attachment is the only path that puts EV into a
   config. DB counts confirm: all four post-publish batches (`9cca352a`,
   `8cab6359`, `4d733539`, `2a8d89b7` — 800 configs through 07-21T01:28Z)
   carry **0 fractional_kelly / 0 expected_value_estimator**. (The count ran
   a session later — the original session's shell tool died harness-wide
   mid-verification, subagent-confirmed; NOT a Forge/daemon issue.)
4. **Soft-fail path observed live from our side:** newest
   `failed_runs_2026-07-20T234900Z.json` carries 12 post-22:31Z failures; the
   8 `other`-category entries are ALL EV-carrying (config-hash join against
   submissions), the 4 `runner_failure` are ordinary non-EV noise — the first
   stragglers of their measured 19-of-649, failing clean, runner loop
   continuing. 17 EV configs remained status=submitted at last snapshot,
   draining. **Flag relayed back (CLOSED banner on the response relay): the
   export shows `error_category: "other"`, not `deregistered_indicator`** —
   contracts-side the field is an open string BY DESIGN (models.py comment;
   no D261-class literal wedge possible), so their export writer just isn't
   passing the new string through. Cosmetic — we can count by hash join —
   but their "countable on your side as a clean admin class" isn't true yet.
5. **Ledger reconciliation accepted:** their gated-window re-scan confirms
   all-time 25 EV components (ours) / current-disk zero (theirs — all aged
   out incl. `606eea73a5b81609`); both records now agree and say so.
6. **Boundary answers recorded:** `~/optbt_data` root does NOT change (any
   future change arrives as its own contracts/layout relay, never silent);
   GenomeFeaturizer v1→2 their side (publisher manual-only); `ev_math` stays
   for the P1 NO-GO probe, successor-via-alias per the D258-class note.

RELAYS.md row flipped (answered + VERIFIED, archive candidate). **Watch
carried forward: none — the EV loop is fully closed.** The freed sizer-mode
third redistributes from batch `8cab6359` onward; split funnel reads on
registry_hash. NB: committed by a follow-up session/agent — this session's
shell could not run git (see item 3).
Related: [[D303]], [[D258]], [[D261]], [[D245]], [[D240]].

## D309 — 2026-07-21 — GRAMMAR v42 → v43 DEPLOYED: the 30-name yield-audit exclusion rider (operator "Ship all 30" → "deploy v43") — the first exclusion cohort DETECTED, PREREG'D, and SHIPPED entirely on our own funnel

**The first end-to-end run of the D302 detector pipeline: `forge yield-audit`
finding → decision homework (universe cross-check + draw rates) → operator
approval → prereg `44a4e08aef4f` (cohort cut 2026-07-21T00:00, BEFORE any
code) → v43 bump.** Evidence and staging: [[D307]] +
`docs/proposals/v43-dead-name-rider.md`.

- **Change:** `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` 8 → 38 (+AAL ADBE AMZN
  ARKK BSX DIA DVN EEM EFA GE INTC KO LRCX LUV MS MSFT NEM NKE PEP TXN UNG
  UPS VZ WFC XBI XLF XLI XLP XLV XOM). Enumeration-policy bump — `rules:`
  text untouched; frozen-list terms unchanged (re-admission on their relay;
  whole list retires when their queue-time liquidity preflight ships).
  Cannot keep the names out of xsect baskets (documented v34 limitation;
  their preflight is the complete fix).
- **Operator mid-window question ("exclude or fix the big names?") answered
  in-session:** the exclusion is a verdict on OUR v1 long-options grammar ON
  those names (500–1,139 decided configs each across every expressible
  cell = a thorough v1 sweep; zero conversions is the space's answer), not
  on the tickers. The "fix" is REPRESENTATIONAL — defined-risk spreads
  (Path C) are the natural structure for liquid mega-caps/ETFs — and Path C
  is parked as the operator's call; this cohort is fresh evidence FOR that
  resume case. Fully reversible: relay re-admission, preflight retirement,
  and any v2 structure bump revisits the list. Names stay in the universe +
  xsect books.
- **Goldens: 7/7 re-pinned environment-matched.** License: OLD code
  reproduced every constant exactly at HEAD (2037-green preflight
  pre-window). First divergences measured: every 7777-seed regime golden
  @0 (first config taps the shrunken pool — the v37/v41 pool-shift
  signature); cohort golden @2 with 5/15 positions surviving byte-identical
  (per-index seeding). Landmark: first capitulation genome 30 → 71 (carriers
  scan widened to 80, claim unchanged). Two non-golden adjustments, both
  documented in place: the d105 fallback-pool tilt bound became inclusive
  (DIA/MSFT/AMZN leave the 24-name fallback draw → the floored diversified
  share lands exactly ON the 5% bound), and the d270 docstring updated.
- **Emission proof (live registry, 3k cold): v43 stamp, ZERO excluded-name
  draws (0/3000), 83 distinct single names, all 5 hypotheses reachable**
  (event_momentum 616 / MR 608 / ve 605 / rv 601 / trend 570).
- **Ritual:** preflight `deploy_preflight.sh` GO (full suite 2037 green,
  deploy surface clean) → stop 2026-07-21T01:39:41Z → sampler +30 + census
  test extension + grammar.yaml v43 bump + header note + archive
  `config/grammar_archive/v43.yaml` + golden re-pin in the down-window →
  uncontended full suite green (count in STATUS) → commit (this entry rides
  it; NB the commit also carries the concurrent session's uncommitted D308
  ledger/STATUS/RELAYS appends — same-file races, absorbed as-is) →
  reset-failed → start. Journal verification + first-batch audit in STATUS.
- **Deploy relay** `PROMPT_CRUCIBLE_V43_DEPLOYED.md` (held for carry): the
  name list + evidence + the row-45 cross-check request + funnel ask
  `--compare v42 v43`; boundary flagged clean (no universe/registry change
  rides this restart) BUT the v39→v40 MR read (~07-22/23) and the ve
  v38→v39 read land near the boundary — cohort-split reminders included.
- **NEXT (separate window, deliberately):** the D307 young-cell floor
  activation (`FORGE_YOUNG_CELL_FLOOR=on` + daemon-reload + restart) AFTER
  the first v43 batch audits in-spec — no boundary carries two changes.

Related: [[D302]], [[D307]], [[D286]], [[D293]], [[D278]], [[D207]],
[[D104]].

## D310 — 2026-07-21 — search_n_trials population BUILT self-gated (absorbed commit): per-slot cumulative stamp, DORMANT until Crucible's record-not-bind marker appears in verdicts — the D306 hazard resolved via their (a)

**Attribution note:** this build was executed by a concurrent session that the
2026-07-21 shell outage killed before its commit and ledger entry; it is
absorbed here at the v43 deploy window (the D104 rule forbids restarting onto
a dirty tree) with its number matching the architecture.md row it wrote
(its in-code comment said D309 — renumbered, that was already taken).
Content, as verified from the working tree + the 2053-green uncontended
suite: `forge/submission/search_multiplicity.py` (slot-count query + stamp;
hash-excluded field — idempotency/batch identity untouched, invariants test
`test_search_n_trials_hash_excluded`), main.py submit-path wiring behind
`crucible_record_not_bind_live(conn)` — configs ship UNSET (their n_trials=1
path) until the marker is observed, because stamping against their old
binding `_verdict_from_gates` predicate would flip the component stream to
reject (the D306 finding); journal line `search_n_trials: dormant … /
stamped …`. MANPAGE + architecture rows were already written by that
session.

**Owning-session extension (the session was NOT dead — its shell tool was;
build + verification below happened live, absorption verified correct):**

1. **Trigger + their exact semantics** (`FORGE_search_n_trials_resolution_
   2026-07-20.md`, their §20 `dsr-record-not-binding-forge-minimal`, commit
   `69f9c25`): operator ruling **(a)**, compute-and-record variant. Our D306
   finding acknowledged verbatim, all three claims code-confirmed. For
   forge-source minimal decisions `deflated_sharpe` is computed/recorded at
   the honest stamped multiplicity with a `recorded_not_binding` marker in
   the gate detail and excluded from BOTH the all-pass and component verdict
   predicates — decisions byte-identical. They chose record-not-bind over
   our exemption-set phrasing deliberately (the exemption set would DEMOTE
   full-pass runs to component once stamped). (b) stays available as its own
   pre-announced §20 + feedback-era boundary. Non-forge sources keep DSR
   binding at n=1; the selection restamp lanes + §8.7 remain where deflation
   adjudicates. The operator approved this build in the D306 session; their
   (a) released the hold.
2. **Why the self-gate exists (pre-build verification):** their "live as of
   this relay's commit window" was NOT yet observable at build time — the
   freshest verdicts (07-21T01:31Z) still carried the old
   `"Single-config DSR (n_trials=1)"` detail, no marker. Stamping on trust
   would reproduce the exact D306 crater, so the wiring trusts only the
   marker (their own designated deployment signal), bounded at the 07-20
   ship date so a stray pre-ship string can never arm it. Self-arms
   batch-by-batch; safe under any restart ordering (the D290 pattern).
3. **Design details:** counts from `submissions` NOT `verdicts` (the stamp
   should lead the decided count — a config's own trial belongs in its
   multiplicity; also deliberately "slightly ahead", per the interaction
   relay); position-aware within the batch (the Kth new config of a slot =
   trial `prior+K`; fresh slot starts at 1, matching their `or 1` floor);
   `count(*)` = distinct configs via the §13.4 unique index.
4. **Reader-safety checks:** zero Forge readers of `failure_buckets`
   (comments only) — their heads-up that stamped non-reject rows will carry
   `dsr_below_bar` cannot confuse anything (F3/tail/yield label on
   `decision` alone); recorded DSR margins at slot-scale n are non-binding
   on forge rows (attribution must mirror the verdict predicate — their own
   caveat, recorded).
5. **Tests** (all in the absorbed commit `babb148`): 12 module tests (slot
   key, count grouping, marker predicate incl. the pre-ship-date guard,
   position-aware stamping, no-mutation, field preservation), 2 end-to-end
   `forge run` wiring tests (dormant → inbox `search_n_trials: null`;
   seeded marker → stamped integers in the inbox files), 2 invariant tests
   (stamping never moves `config_hash`, incl. at their Q1 magnitude
   46,132 — the tripwire if a contracts upgrade ever folds the field into
   the hash).
6. **Riding confirms in their relay, recorded:** sma_slope GO received;
   resid-vix floor retirement noted; their BOTH-AXES supply ask stays a
   standing record (inexpressible under C1/R2 — the Q46 class, not opened).
7. **Numbering:** the build's in-code D-refs (written pre-race as D309) were
   renumbered to D310 — main.py in the absorb commit, the module/test
   docstrings in this one. Third number race of the day.

**Watch: FULFILLED same-hour — the stamp armed on the FIRST v43 batch.**
Their runners rolled the record-not-bind code minutes after the pre-build
check (earliest marker verdict decided 07-21T01:37:50Z; 134 marker rows by
02:10Z); the first v43 iteration's reconcile pulled them in, and the batch
stamped: **`03b33475-369e-4e14-9ad1-fc90f03fd9ac` (02:07:37Z, 200/200
stamped, min 5,154 / max slot n_trials=108,324)**. The dormant state lasted
zero batches — the self-gate cost nothing and would have saved the D306
crater had their roll been slower. Stamp values verified against the module's
census: the max slot is trend_continuation×swing_mid×**xsect** at exactly
108,324 (the H1-era xsect slots are the giants — 99,736 mr×swing_mid×xsect,
63,509 trend×swing_long×xsect; largest named slot: ve×swing_short 55,790);
zero NULL-combiner rows (no era edge). Downstream expectation now ACTIVE:
at slot-scale n the recorded (non-binding) DSR sits far under the bar on the
big-slot rows — `dsr_below_bar` will show up in `failure_buckets` on
non-reject forge rows, per their heads-up (no Forge reader; extra signal).
Related: [[D304]], [[D306]], [[D309]], [[D207]], [[D245]], [[D290]].

## D311 — 2026-07-21 — v43 post-deploy CLOSE-OUT: first batch IN-SPEC; Crucible's row-45 cross-check ANSWERED SAME-HOUR — exclusion CONFIRMED for our stream (0/30 starved, ZERO forge-source conversions reproduced on THEIR ledger); 4 names carry standing vol_event refit-lane ALIVE flags (docs-only fold)

**First v43 batch `03b33475` (2026-07-21T02:07:37Z) audit: IN-SPEC** — 200/200
stamped v43, 0 failed; **ZERO excluded-name draws** (24 single-name draws
over 21 names); `search_n_trials` populated 200/200 (the D310 stamp armed on
this batch — their record-not-bind marker observed from 01:37:50Z; the
concurrent session verified max slot n_trials=108,324).

**Inbound `FORGE_v43_row45_crosscheck_2026-07-21.md` triaged:**

1. **Row 45: 0/30 fire their starved signature** (trailing-30d wf-zero 31.7%
   NKE → 91.5% LRCX, all under their ≥95% bar at n 399–1,126) — these are
   NOT the BKNG born-dead class; their preflight will never independently
   block them. **The exclusion rides on our yield evidence alone — which the
   frozen-list terms contemplate.** And the premise reproduces on THEIR
   ledger: forge-source conversions across all 30 since 06-10 = ZERO.
2. **ALIVE flags (standing, not invoked): LRCX (3), GE, WFC, UNG** — 6
   fullhist_refit-lane volatility_event components since 06-10. Their read:
   keep all 30 excluded today (6/≈5,000 all-lane ≠ a re-admission case);
   IF a vol_event-targeted cohort ships, re-admission FOR THAT COHORT is
   one relay away on this evidence. **Our ghost cross-check (their
   suggestion): all 6 dates (06-13→07-03) predate `VE_GHOST_LABEL_CUT`
   (07-18) — under OUR labeling they are unrankable regardless of lane; the
   flag properly lives on their side, to invoke with post-cut refit
   evidence.** Recorded in the relay addendum; also noted against the
   `ve-exit-repair` campaign (a future ve-cohort decision should surface
   these 4 names).
3. Funnel compare scheduled on cohort maturity, read against prereg
   `44a4e08aef4f`; boundary reminders relayed to the v40-MR/v39-ve read
   owners. Their riding note endorses the honesty framing (several names
   "fire real fills constantly" — v1-grammar verdict, not a name verdict;
   Path C candidates if it opens).

Related: [[D309]], [[D302]], [[D310]], [[D290]], [[D207]].

## D312 — 2026-07-21 — Young-cell floor ACTIVATED (`FORGE_YOUNG_CELL_FLOOR=on` on the unit; the D307 build's flip): diversifier phase 0c live — automatic model-independent coverage for young (directional, regime) cells; its own window, deliberately separate from the v43 boundary

**Operator "activate the cell floor and deploy v43" (2026-07-21) — second
half, executed AFTER the first v43 batch audited in-spec so no boundary
carries two changes.** Mechanics: `Environment=FORGE_YOUNG_CELL_FLOOR=on` +
comment block on `deploy/systemd/forge.service` (symlink-installed →
daemon-reload REQUIRED and performed), preflight GO (contended full suite
green pre-stop), stop 02:21:07Z, commit in-window, reset-failed, start.
Verification (recorded in STATUS): `Environment` shows the flag IN THE
PROCESS ENV (not just the file — the deploy.md gotcha), journal
`cell_floor: mature_cells=N` line on the first iteration, first-batch
young-cell read. Selection change class: versionless (D193/D252), flag-ON
now = NOT byte-identical by design — the activation IS the change; the
D307 build + tests carried the full record. REVERT = delete the two unit
lines + daemon-reload + restart (byte-identical). Watch: young-cell count
per batch (over-subscription of the sorted-order cap = the documented
revisit trigger); the campaign-audit JSONL picks up carriage shifts at the
next 05:00 fire. Related: [[D307]], [[D287]], [[D136]], [[D309]].

## D313 — 2026-07-21 — Refutation-registry reply DRAFTED (the "registry reply" their status awaits; docs-only, nothing wired): all 28 entries mapped to our cell vocabulary; 2 entries CORROBORATED by our funnel with live suppressible mass (MR×hurst 1.10% vs 8.07% baseline; delta≥0.50 sliver = 9.3% of stream); the broad-index-ve ↔ ve-solo-density interaction flagged; wiring blocked on a blessed consumption path

**Trigger:** `FORGE_refutation_registry_2026-07-20.md` — their 28-entry
machine-readable negative-results registry (`docs/refutations.yaml`, statuses
refuted/no_go/untested_gated/caution_not_refuted/policy_bar + per-entry
`unlock` conditions), Tranche 2 of their process-improvement plan. Their asks:
(1) validate before wiring, flag disagreements; (2) map entries to OUR cell
vocabulary and report the mapping; (3) report suppressed mass into the weekly
census once wired; (4) never treat blocklists as gate information. This
inbound sat untriaged since last evening — surfaced by their status line
("Awaiting … Forge's registry reply") relayed by the operator.

**The mapping** (full table in `PROMPT_CRUCIBLE_REFUTATION_REGISTRY_REPLY.md`,
untracked, operator carries):

- **23 of 28 entries are Class A — already structural** (suppressed mass 0 by
  construction): dead ids never grammar-admitted (butterfly_25d, skew_25d,
  days_to_cover, iv_vs_index…), axes without vocabulary (pyramiding,
  regime-switching, put/call side, book-timing, intraday), schema-enforced
  (target_exit on trend: 0 of 520k all-time — S5 never admitted it, D236 even
  prefers their winning chandelier), rank-exclusion-enforced
  (xsect-chain-rank-gates via rank_per_name_coherent, v15/v16), or already
  our own recorded decisions (sector-relval=D269, xsect-tier=D294/D296,
  ev-as-sizing=D303/D308, capitulation caution=v35 — we FARM that axis).
- **2 entries corroborated with measurable live mass (wiring candidates,
  operator-gated, each needs a version bump):** `hurst-mr-conditioner` — our
  clean-era funnel INDEPENDENTLY corroborates their refutation: MR×hurst
  24,779 decided → 1.10% components vs MR baseline 8.07% (~1/7th; ~19% of MR
  volume). CRITICAL scope guard recorded: trend×hurst is ABOVE baseline
  (14.2% vs 12.0%) and a top yield cell — the wiring must be MR-scoped, never
  id-level. `deep-itm-directional` — P3 caps at 0.55 so their refuted ≥0.50
  region overlaps our top sliver: 9.3% of trailing-7d submissions (trend
  14.0% / ve 25.9% / MR 1.0%); their 07-20 scope bound honored (nothing below
  0.50 mapped; 0.23–0.35 is our default region, also under their delta30
  test).
- **1 interaction flagged (their ask #1):** `broad-index-vol-event`'s
  single-name half collides with their own `ve-solo-density` unlock, which
  NEEDS the v39/v41 exit-repair cohorts (min_oos ≥ 60 recipes) — suppressing
  single-name ve would starve their own density heal. Only the index/ETF half
  mapped as a candidate (measured: 4,145 decided / 12 comps = 0.29%,
  IDENTICAL to single-name ve 0.29%); both halves defer to their v38→v39 ve
  read.

**Wiring posture:** NOTHING wired (their relay: operator carries adoption).
Sequencing blocker relayed: `refutations.yaml` lives in their repo — a daemon
read of their docs tree would be a new unversioned cross-system surface (hard
rule #2 / D245 class); wiring needs the registry published into
`~/optbt_data/exports` (registry-snapshot pattern) or a contracts helper.
Suppressed-mass census reporting committed for post-wiring via the D299/D302
audit infrastructure, keyed by registry entry id.

**Riding receipts in the reply** (the other items of their awaited-list):
timer-MR regeneration continues post-v43 (first v43 batch: 41/63 MR on the
required time_stop pick = 65.1%, the v40 weighting exactly — the 30-name
exclusion did not dent the cell); search_n_trials armed (D310 banner
referenced); the ve frozen-recipe calendar row confirmed THEIR-side owned
(their `forward_calendar.md`: "owner registers its read date(s) here at the
first accrual checkpoint" — the recipe + accrual live on their engine).

NB: fourth D-number race of the day (the concurrent session's young-cell
activation took D312 mid-append); this entry renumbered to D313.
Related: [[D269]], [[D294]], [[D296]], [[D303]], [[D310]], [[D276]],
[[D287]], [[D245]], [[D299]], [[D302]], [[D312]].

## D314 — 2026-07-21 — Q46 (optional second regime-gate) SCOPED at Crucible's request (docs-only, no build, operator-gated): the slot ALREADY EXISTS (3 veto ids live since v25/v26/v29/v39) → Q46 = a ONE-ID pool add (vix_term_slope as trend second-gate conditioner), C1/R2/S3 predicates UNCHANGED. Load-bearing correction relayed: their "multi-gate is starving (5.73%)" is a pre-veto-era artifact — our live stream is 34.5% multi-gate with every cited top pair already emitting

**Trigger:** `FORGE_q46_multigate_scoped_ask_2026-07-21.md` — Crucible opens Q46
(the both-axes ask from our D310 rider), a scoped proposal for an optional
second regime gate: second-gate vocab = vix-residual family + days_since_jump,
trend×xsect first, MR excluded, 10-15% share. Three questions: (1) cheap vs
expensive in our sampler; (2) estimate + earliest version; (3) is their
vix-residual export surface sufficient. Scoping conversation, nothing to ship.

**Architecture investigation (read C1/R2/S3 + the sampler veto path + the
family map + rank-exclusion flags before forming a view):**

1. **The second-gate SLOT is fully built and battle-tested.** S3 is
   `cardinality min: 1` (NOT `== 1`) — the grammar has permitted ≥1 regime gate
   since v1. Three optional-second-gate ids exercise it: dsj (v25/D258, trend),
   ivol + market_realized_vol (v26/D263, v29/D266, MR), ref_trailing_return
   (v39/D290, ve). The mechanism (`_eligible_regime_vetoes` +
   `_config_has_veto_family_indicator` + drawn-LAST + dormant-until-registry +
   per-ID C1 guard) is exactly Q46's "max 2 regime gates" ceiling. `rng.choice`
   over one pool → ≤1 optional second gate → ≤2 total, for free.
2. **C1/R2/S3 predicates need ZERO change.** R2 is satisfied by the primary;
   vix_term_slope is already R2-accepted (v27/D264). C1
   (`no_duplicate_indicator_families`) already does Q46's disjointness:
   vix_term_slope=family **macro**, adx/hurst=**trend_strength** → disjoint →
   `{adx,hurst} × vix_term_slope` is C1-legal TODAY; and market_state /
   market_realized_vol (both macro) × vix_term_slope are C1-auto-blocked, so the
   primary collapses to {adx,hurst} with no hand-coded first-gate exclusion.
3. **The true expressibility gap is ONE id:** vix_term_slope is drawn only as an
   R2 PRIMARY, never as the optional SECOND gate — so the price-axis-primary ×
   vix_term_slope-conditioner pair appears nowhere. That is their "vix-residual ×
   price-axis." residual_momentum is the DIRECTIONAL (family trend,
   directional-only), not a gate; no separate vix-residual id exists
   (registry vix/resid ids: vix_term_slope, residual_momentum, vix_level,
   iv_term_slope). **Surface sufficient as-is, zero Crucible work.**
4. **xsect-eligibility confirmed:** vix_term_slope's rank-exclusion class =
   `NOT rank_per_name_coherent AND NOT market_wide_by_design` =
   `NOT False AND NOT True` = False → rank-eligible as a market-wide gate (the
   uniform market-level condition on when the per-name rank fires — the
   xsect-first structure they want).

**Load-bearing correction (measured, relayed as their Ask-1-back):** their
census premise "multi-gate is the best-converting class AND your grammar can't
emit more of it (5.73%)" is a PRE-veto-era dilution artifact. Live stream
(16,600 submissions ≥2026-07-19): **34.52% multi-gate**, and every cited top
pair already emits — dsj|hurst 570, dsj|market_state 165, adx|dsj 161,
dsj|vix_term_slope 255 (dsj veto stacks on a vix_term_slope PRIMARY),
ivol|market_rv 3,264. Asked them to re-split the census by grammar_version
(cut ~07-08) before scoping the pilot as a throughput play — the throughput
case is likely already won; the pilot's real value is the orthogonality
(vix-residual pair), which sharpens the readout.

**The one real knob + one design question relayed:** conditioner share
(their 10-15%) vs our fixed `_REGIME_VETO_SHARE=0.5` — if vix_term_slope joins
the single pool, rng.choice over-serves it; hitting 10-15% needs a weighted
share (the one genuinely new piece, small). Design Q back: conditioner and veto
share the SINGLE optional slot (mutually exclusive → honors "max 2" for free);
confirmed that's the intent, else vix-AND-dsj co-fire = a 3-gate change, a
larger conversation.

**Estimate:** small (~D258 dsj-veto diff size: pool add + share knob +
xsect-scope + golden re-pin + deploy ritual). **Rides v44** (next
operator-gated bump). **NOT dormant** — vix_term_slope is already served, so
the bump activates on restart with an immediate golden re-pin and immediate
emission (unlike the three prior second gates, which shipped dark until
Crucible published their ids). Grammar rule TEXT unchanged (the
D258/D270/D280 header-note-bump convention). Counter-scope relayed:
first-gate-minus-blocked is a no-op for the trend pilot (D313 blocks nothing in
the trend R2 pool); MR-exclusion + xsect-first + multiplicity all agreed;
market-wide gate thins by TIME not by name (a point for xsect vs per-name
sparsity).

**Posture:** NOTHING built. On operator greenlight → v44 worktree build with
the +2wk null-control funnel read they propose, registered against a pilot
prereg (v38→v39 pattern). Response `PROMPT_CRUCIBLE_Q46_MULTIGATE_SCOPING.md`
(untracked, operator carries).

Related: [[D258]], [[D263]], [[D290]], [[D264]], [[D276]], [[D287]], [[D310]],
[[D313]].

## D315 — 2026-07-21 — Q46 GO received + residual_momentum weight CONFIRMED (docs-only, no build, operator-gated): their "starving" premise RETRACTED (34.5% reproduced at v39), indicator identity confirmed (resid_vix = residual_momentum × vix_term_slope, both registered). Refinement relayed: the confirmed cell ALREADY emits (vix-as-PRIMARY, 150 configs) — v44 uniquely creates the ADJACENT double-gate (price-strength primary × vix SECOND), which reframes their null-control read

**Trigger:** `FORGE_q46_reply_repin_and_go_2026-07-21.md` — Crucible re-split
their census by grammar_version (our D314 ask-back), reproducing our 34.5%
live multi-gate at v39, and RETRACTED the "multi-gate starving / C1-R2 can't
emit more" premise. Confirmed the indicator identity (resid_vix =
residual_momentum directional × vix_term_slope gate, both registered,
probe-built, never Forge-generated → "no separate vix-residual id" correct).
GO on the v44 scope. One completeness ask (§2): confirm residual_momentum sits
at healthy trend-directional weight so the pilot visits the confirmed cell.

**§2 verification (live submissions ≥2026-07-20):** residual_momentum = 9.8%
of trend directionals (3rd, after donchian 43.7% / rolling_sharpe 36.3%),
**100% xsect** (beta-stripped ranker → rank-path only). Healthy — pilot
visits, doesn't orbit. Ask satisfied.

**The refinement (measured, load-bearing for their read design):** of
residual_momentum configs, 150 ALREADY carry vix_term_slope as a gate — but
vix_term_slope can only be an R2 PRIMARY today, so: 66 = vix as sole gate (the
single-gate confirmed cell, already emitting at scale); 84 = vix primary + dsj
veto second; **0 = vix co-occurring with a trend-STRENGTH gate.** So the
confirmed cell (residual_momentum × vix_term_slope) is ALREADY VISITED from
batch 1 — v44 does NOT open it. What v44 uniquely creates is the DOUBLE-GATE:
{adx,hurst} price-strength PRIMARY × vix_term_slope SECOND on a
residual_momentum ranker — the both-axes genome, 0 today, C1-legal (trend +
trend_strength + macro = 3 disjoint families). Relayed implication: their
+2-week null-control must contrast the NEW double-gate vs the EXISTING
vix-as-primary single-gate baseline (both carrying residual_momentum), not
"confirmed cell vs empty" — else the vix-primary supply already in the stream
contaminates the control arm. Plus a density heads-up (double-gate share ≈
9.8% × P(trend-strength primary) × 10-15% conditioner = modest; residual_momentum
directional weight is a separate liftable dial for read power if they need
more events).

**§1/§3 accepted:** retraction noted; the within-version 1.5× multi-gate lift
(6.06 vs 4.02 at v38) recorded as an allocation datum (our cohort/regime-gate
yield weights already price it, no action); scope GO accepted as written
(one-id pool add, C1 auto-collapse to {adx,hurst}, xsect-first, weighted
10-15% share, immediate golden re-pin, MR-excluded, conditioner-veto
mutual-exclusion honoring "max 2").

**Build posture: NOTHING BUILT — operator-gated.** The scope is GO both sides
but the v44 grammar bump is an operator-gated deploy here; no operator build
word yet. Flagged the coupling: contracts 1.34.0 (their
`load_refutations_from_export`) is live on disk, our pin is 1.33.0, the
exact-match forcing test is RED → v44's deploy suite is blocked until we
co-adopt 1.34.0 (the natural window, same as v41/v42 rode 1.32.0/1.33.0).
Response `PROMPT_CRUCIBLE_Q46_GO_CONFIRM.md` (untracked, operator carries).

NB: committed doc-only during the operator's concurrent code build
(schemas/verdicts/consumer/submitter dirty — untouched, left for their commit).
Related: [[D314]], [[D264]], [[D276]], [[D287]], [[D305]], [[D310]], [[D313]].

## D316 — 2026-07-21 — Themes 2c + 2d BUILT (operator "Finish Theme 2d + 2c"): label provenance stamped on every new verdict row + the standing writer-activation probe (2c); the young-cell explore quota as a THIRD submission lane, flag-gated (2d). The label-integrity program's cheap layers are in

**2c — label provenance + integrity tripwires:**

1. `verdicts` gains `source_export` + `contracts_version` (idempotent ALTERs;
   pre-D316 rows NULL). `record_verdicts(..., source_export=)` stamps both;
   the consumer passes the newest gated export's filename (best-effort mirror
   of the reader's newest-file pick — a publish race mis-stamps at most one
   poll, documented). WHY: the ve ghost episode was five weeks of
   archaeology; the next era cut filters on a recorded column, and — per the
   v43 ALIVE-flags lesson — can be LANE-aware instead of a date guillotine.
2. **Standing activation probe**: `daily_ranker_eval.sh` runs
   `forge check-activations` daily → one row in
   `~/forge_data/ranker_eval/activation_probe.jsonl` (regex over the
   [ OK  ]/[INERT]/[UNCHK] lines — format smoke-tested live: sma_slope OK,
   565 max activations); `forge healthcheck` gains `check_activation_probe`
   (WARN on inert ids — the ref_trailing_return/D254 drawn-then-killed
   class — or a stale/dead probe; OK-note before the first fire).
3. **The Crucible half is a contracts ask**:
   `PROMPT_CRUCIBLE_CACHE_ERA_STAMP_ASK.md` HELD (operator go) — a
   cache-era/writer-version stamp on gated exports; additive, tolerant-reader
   safe.

**2d — young-cell explore quota (flag-gated OFF):**
`rank_batch_with_exploration` — the exploration engine returning THREE lanes
(merit / holdout / young); `sample_young_cell_explore` draws up to
`FORGE_YOUNG_CELL_EXPLORE_SLOTS` (clamp [0,8], default 0 = byte-identical;
requires the D307/D312 floor's `mature_cells`) seeded-randomly from
young-cell members of the rank-non-selected survivors, feasibility-checked so
a short young pool never under-fills the merit lane; `rank_batch_with_holdout`
is now a thin 2-tuple wrapper (byte-identity pinned by test). Submitter tags
the lane `selection_mode='young_explore'` — a THIRD literal, deliberately:
the uniform holdout is the estimand for the ranker-vs-random A/B (prereg
61837dd2) AND the campaign-audit carriage denominator (D299), so the quota
must pollute neither (audit now skips young rows entirely; holdout wins the
tag on overlap). WHY the lane at all: the floor guarantees young cells get
SUBMITTED; the quota makes them accrue UNBIASED labels faster than the flat
5% holdout provides — off-policy correctness at the exact place the D287
pathology lives. rng = `SeedHierarchy(seed).rng("young_cell_explore")`
(rules #6/#8).

**Activation state:** 2c's timer/healthcheck halves live at the next 05:00
fire / healthcheck run; the verdict stamping activates at the next daemon
restart (code-inert until reload). 2d stays FLAG-OFF — recommended flip:
after the D312 floor's first daily read (tomorrow's 05:00 + campaign-audit
row), so the floor's boundary stays clean; the flip is
`Environment=FORGE_YOUNG_CELL_EXPLORE_SLOTS=4` + daemon-reload + restart
(one window, can carry the 2c stamping activation with it — both are
selection/telemetry surfaces with no grammar boundary).

NB the day's FOURTH and FIFTH number races: built as D314 (taken by the
concurrent Q46 scoping), renumbered D315 (ALSO taken — the concurrent Q46-GO
triage committed first), settled as D316; the 7060dc6 commit message says
D315, this header is authoritative. Suite: verdicts 12, healthcheck
16, young-explore 6, ranking+submission 419 green mid-build; full gates at
commit. Related: [[D307]], [[D312]], [[D299]], [[D290]], [[D254]], [[D287]],
[[D111]].

## D317 — 2026-07-21 — v43 → v44 DEPLOYED: Q46 vix_term_slope second-gate CONDITIONER on the xsect trend arm (operator "Let's do v44"; Crucible GO). Co-adopts contracts 1.34.0. The confirmed resid_vix price-axis DOUBLE-GATE ({adx,hurst} primary × vix SECOND) — 0 in the stream before, because vix was only ever an R2 PRIMARY. Rules text unchanged; built in a worktree, full suite 2062 green

**Trigger:** operator "Let's do v44 and contract adoption also do the prereg" on
`FORGE_q46_reply_repin_and_go_2026-07-21.md` (Crucible GO on the D314/D315 scope).
The both-axes ask from the D310 rider, now expressible in one genome.

**The change (emission-policy — the 21 `rules:` text is UNCHANGED, the
D258/D270/D280 header-note-bump convention):**

- `sampler.py`: `vix_term_slope` joins the optional second-gate slot as a
  CONDITIONER. `_vix_conditioner_eligible` = trend_continuation ×
  cross_sectional_rank × non-capitulation × primary gate ∈ {adx, hurst}
  (trend-strength) × vix served (the trend R2 pool carries it iff served —
  dormancy guard). Fires at `_VIX_CONDITIONER_SHARE=0.125` (its own knob,
  distinct from the 0.5 veto share), drawn FIRST and mutually exclusive with the
  veto in the single slot → at most one optional gate → "max 2" total.
- **Why this is the genuine gap:** vix_term_slope had only ever been drawn as an
  R2 PRIMARY (150 residual_momentum × vix configs already emit vix-as-primary;
  ZERO paired vix with a trend-strength gate). The double-gate ({adx,hurst}
  primary × vix SECOND) is the confirmed resid_vix price-axis pair, and it was
  unemitted. C1-safe by construction (trend_strength shares no family with
  vix_term_slope = macro; market_state/market_rv macro primaries are C1-blocked,
  so the primary collapses to {adx,hurst}). Verified emission on the live
  registry: the conditioner fires at 11.8% of eligible, and every double-gate it
  produced had directional=residual_momentum — the confirmed cell.
- **NOT dormant** (unlike the v25/v26/v29/v39 vetoes): vix_term_slope is already
  registry-served, so v44 ACTIVATES on the deploy restart. BUT under the minimal
  test fixture (which serves no vix trend gate) it's inert → all 210 test_sampler
  goldens BYTE-IDENTICAL (the hard-rule-#6 cold-path proof; no golden re-pin
  needed). A dedicated `test_v44_vix_conditioner.py` (9 tests) exercises emission
  via a `_v33`-pattern augmented registry: double-gate on adx/hurst, never MR /
  single-name / macro-primary / capitulation, veto mutual-exclusion, ~12.5%
  share, grammar-validity.

**Contract adoption (co-adopted, forced by the red forcing test):** pin
1.33.0 → 1.34.0 (`load_refutations_from_export` — the D313 refutations consumer
path; purely additive, nothing reads it yet). v44 is the co-adoption window as
v41/v42 rode 1.32.0/1.33.0.

**Build/deploy discipline:** built in `../Forge-build` worktree (grammar-gated,
never the live tree while the service runs). Full suite 2062 green + mypy --strict
+ ruff clean IN THE WORKTREE. Transferred to the live tree by patch once the
operator's concurrent D315 (Themes 2c+2d, `7060dc6`) landed and cleared the tree;
deploy preflight + ritual from the live tree. GRAMMAR.md S3 gains the
optional-second-gate note; MANPAGE unchanged (no CLI/flag). Deploy relay
`PROMPT_CRUCIBLE_V44_DEPLOYED.md`: the +2-week null-control read pins at this
deploy; the honest contrast is the NEW double-gate vs the EXISTING vix-as-primary
baseline (both carry residual_momentum), NOT "cell vs empty."

**D-number race (chained, resolved):** D315 was first doubly-assigned — the
operator's Themes 2c+2d (`7060dc6`) and my Q46-GO confirm (`2f1b6ca`). The
operator's `1153f2c` resolved it by renumbering THEIR Themes D315 → **D316**
(and, in the same broad commit, swept up my applied-but-uncommitted v44 code —
sampler/contracts/test_v44/GRAMMAR.md/this-ledger — the live-tree concurrent-work
hazard). That renumber then collided with my v44 D316, so per "commit-second
renumbers" **v44 is D317** — my Q46-GO stays D315, the operator's Themes is D316,
v44 is D317. All v44 code/doc D316 refs were sed'd to D317 (disjoint files from
the Themes D316 refs); the grammar.yaml v44-bump + v44.yaml archive + uv.lock were
the only pieces `1153f2c` did NOT capture, committed here.

Related: [[D315]], [[D316]], [[D314]], [[D264]], [[D276]], [[D287]], [[D258]],
[[D310]], [[D313]], [[D104]], [[D199]].

## D318 — 2026-07-21 — Q46 read-inversion + hurst-only scope refinement TRIAGED (docs-only; v45 refinement RECOMMENDED, operator-gated — NOT built): Crucible re-derived the read after our D315 and inverted the baseline (the real control is hurst×residual_momentum 4.06%, not the dead vix-as-primary 0.23%) + asks hurst-primary-ONLY (adx dead on this directional) + a modest ~2× residual_momentum dial. Our verdicts reproduce their split. v44 (live, {adx,hurst}) → the settled scope rides v45

**Trigger:** `FORGE_q46_readdesign_and_scope_refine_2026-07-21.md` — Crucible's
response to our D315 confirmed-cell refinement. Their operator ALSO gives the
v44 build word (§7), but the relay crossed our v44 deploy notice in flight, so
it authorizes a scope we've refined past.

**Verification (our verdicts reproduce their split — snapshot forge_snapD.db,
trend × residual_momentum × xsect, honest clean era ≥07-11):**

- residual_momentum × **hurst** (no vix): **4.47%** (92/2,058) — their 4.06%.
  The working base.
- residual_momentum × **adx** (no vix): **0.40%** (1/247) — their 0.32%. Dead.
- residual_momentum × vix (any form): **0.40%** (3/759) — their 0.23–0.26%.
  Dead at solo grade.

Directions + magnitudes match. Their inversion is correct: our D315 named the
wrong control (vix-as-primary is a VOLUME baseline, a non-converter at quality);
the load-bearing question is "does vix ADD on a working hurst gate (4.06%)," and
the primary read is IN-BOOK marginal contribution (their P2 `incumbent_add_variants`
lane, D213), not a solo conversion test. Conversion vs 4.06% is the supporting
screen.

**The three accepted refinements (all → a v45, since each changes emission):**

1. **hurst-primary ONLY** (drop adx from the conditioner eligibility). adx×resid
   is dead (0.40%); the deployed v44 fires on {adx,hurst}, so the adx arm is ~13%
   of eligible resid double-gate draws (247 vs 2,058) — real dilution. A one-line
   change: `_VIX_CONDITIONER_PRIMARY_GATES` {adx,hurst} → {hurst}.
2. **residual_momentum directional dial ~2×** — size the weight so the double-gate
   cell lands ~600–800 decided over the 2wk window (~20–30 honest for the in-book
   lane), NOT a monoculture (their P5 diversity KPIs — the delicate part; the
   mechanism/magnitude wants operator sign-off).
3. Pin the +2wk read at the **v45** deploy, not v44's 03:43Z.

**Posture: NOT built — v45 is a SECOND operator-gated grammar deploy today, and
the residual_momentum dial is a supply-diversity tradeoff Crucible flagged as
delicate.** The deployed v44 is not broken — it accrues the double-gate at the
un-tightened scope (a trickle, ~0/batch), so the gap costs almost nothing.
Recommendation surfaced to the operator: do the v45 refinement (hurst-only +
~2× dial); on the word it's a worktree build (golden re-pin + emission proof +
ritual) like v44. Response `PROMPT_CRUCIBLE_Q46_READ_INVERSION.md` (untracked,
operator carries) confirms the split + accepts all three + states the v44→v45
timing. Contracts symmetric (their 1.33→1.34 rides the same window; we're
already 1.34.0 as of v44).

Related: [[D317]], [[D315]], [[D276]], [[D287]], [[D264]], [[D213]].

## D319 — 2026-07-21 — v44 → v45 DEPLOYED: Q46 scope REFINEMENT (operator "yes do the v45 refinement"; Crucible both-operator go). (1) conditioner primary HURST-ONLY (adx dropped — dead on residual_momentum); (2) residual_momentum pilot DIAL ~2x for the in-book read's power. Emission-policy; goldens byte-identical; contracts stays 1.34.0

**Trigger:** `FORGE_q46_readdesign_and_scope_refine_2026-07-21.md` (D318 triage) —
Crucible re-derived the read after our D315 and inverted the baseline; both
operators gave the v45 go. Two measured refinements to the deployed v44
conditioner.

**Change 1 — hurst-primary ONLY** (`_VIX_CONDITIONER_PRIMARY_GATES` {adx,hurst}
→ {hurst}). Our verdicts + theirs agree: hurst×residual_momentum converts
4.06–4.47% (the working base the confirmed blend fed) but adx×residual_momentum
is DEAD (0.32–0.40%). v44 fired on {adx,hurst}, so the adx arm was ~13% of
eligible resid double-gate draws — share sprayed on a dead base. The load-bearing
read is the double-gate's IN-BOOK marginal contribution (their P2
`incumbent_add_variants` lane, D213), not a solo conversion test; conversion-vs-
the-4.06%-hurst-base is the supporting screen (our D315 named the wrong control —
vix-as-primary is a VOLUME baseline, dead at solo grade 0.23–0.40%).

**Change 2 — residual_momentum pilot DIAL** (`_RESID_MOMENTUM_PILOT_WEIGHT = 2.0`,
applied in `_option_weight` in the weighted draw path). Lifts residual_momentum's
draw ~2x so the hurst×vix double-gate cell lands ~600–800 decided over the
+2-week read (~2x the natural ~375) → ~20–30 honest components for the in-book
lane (their sizing ask; thin at natural draw). Modest by design — NOT a trend
monoculture (their P5 diversity KPIs; donchian/rolling_sharpe still dominate).
RETIRE when the read concludes (D287-pin-retire convention).

**Emission proof (live registry, v45, production seed, weighted path):**
residual_momentum share 7.5% → **14.0% = 1.87x** (right at the ~2x target);
hurst×vix double-gate = 20, **adx×vix = 0** (hurst-only confirmed). Both changes
touch only the LEARNED weighted path + the served-registry conditioner, so the
minimal-fixture cold path is untouched → the **210 sampler goldens are
byte-identical** (no re-pin; the hard-rule-#6 proof). 12 conditioner/dial tests
(the v44 file + 3 v45: adx-never, dial-lifts-share, dial-default-2.0).

**Build/deploy:** grammar-gated → built in `../Forge-build` worktree (full suite
green), transferred by patch to the clean live tree (HEAD 07b81b7); service
stopped BEFORE the grammar patch (v44's hot-grammar-leak lesson), commit, restart.
grammar bump v44→v45 + archive v45.yaml; the 21 `rules:` text unchanged;
GRAMMAR.md S3 note corrected to hurst-only. Contracts stays 1.34.0 (co-adopted at
v44). Crucible pins the +2-week in-book read to THIS deploy, not v44's 03:43Z.
Deploy relay updated with the v45 timestamp + emission proof.

Related: [[D318]], [[D317]], [[D315]], [[D276]], [[D287]], [[D264]], [[D213]], [[D104]].

## D320 — 2026-07-21 — GRAMMAR v45 → v46: refutation-registry wiring into generation (operator "Let's do refutation registry into generation" → "let's do v46"). Forge now CONSUMES Crucible's published refutation registry and routes generation mass off proven-dead cells. Emission-policy; cold-start byte-identical; contracts stays 1.34.0

**What this closes:** the cross-system search-dedup loop. Crucible's gate
proves regions dead (the 28-entry registry); until now Forge kept enumerating
them because it never consumed the refutations — and those wasted draws inflate
the search-multiplicity tax (the D310 `search_n_trials` stamp → a higher DSR
hurdle; prereg `098ea730` just showed the v1 best is indistinguishable from
luck at n=13,397). This is the only HONEST lever on that hurdle: stop spending
trials on cells Crucible has proven dead.

**Architecture (`forge/enumeration/refutations.py`, new):**
- **Split of authority (hard rule #2):** the EXPORT
  (`load_refutations_from_export`, contracts 1.34.0) is the live authority on
  whether an entry is active + its `generation_effect` verb; the hand-authored
  `BINDINGS` table is the authority on which Forge DRAW each entry maps to (our
  D313 mapping, D-entry-gated like the sampler pins). Fail-OPEN: missing /
  stale / corrupt registry, or an unknown effect verb (the 1.28.0 literal_error
  scar), → NO effect (byte-identical). Self-heals: a withdrawn / downgraded-to-
  `none` entry stops applying at the next read.
- **`resolve_effects()` → `RefutationEffects`**, threaded into `sample_config` /
  `enumerate_candidates` as an optional input (None = byte-identical, the
  yield-map pattern). Kill-switch `FORGE_REFUTATION_GUARD=off`. The daemon reads
  the export and passes it; goldens (no param) stay byte-identical.
- **`refutation_fingerprint()`** (over the ACTIVE effects, not the raw file —
  prose-only amendments don't perturb it) folds into `enumeration_inputs_hash`
  so each batch's identity tracks what shaped its draw (#6). Empty when no
  effect active → recorded identity byte-identical to cold.

**The three effects (only the Class-B entries with live mass are bound; the
other 25 are already-structural, mass 0):**
1. `hurst-mr-conditioner` (deprioritize) → `_pick_regime` down-weights the hurst
   gate x0.25 for MR. **SCOPE GUARD (load-bearing): MR-ONLY** — trend x hurst is
   above baseline and a top yield cell. Byte-identity preserved when inactive
   (weighted branches multiply by all-ones; the uniform branch keeps
   `rng.choice`, diverging to `rng.choices` only when a deprioritize applies).
2. `deep-itm-directional` (blocklist) → `_build_selector` clips the P3 delta
   upper edge below 0.50 (the refuted deep-ITM sliver; the 0.23-0.35
   default/interior is untouched → byte-identical there).
3. `broad-index-vol-event` (deprioritize) → `_pick_underlying` down-weights the
   DIVERSIFIED/ETF underlying class x0.25 for ve. **INDEX HALF ONLY** — the
   single-name half is deferred (it feeds Crucible's ve-solo-density unlock,
   which needs the single-name ve supply `ve-exit-repair` farms). Gated on the
   pool actually containing an ETF so earnings-gated single-name ve stays
   byte-identical.

**Emission proof (live registry, 4k cold, seed 0, effects OFF vs ON):**
deep-ITM sliver **736 → 0**; MR x hurst share **13.8% → 3.7%** (~1/4);
**trend x hurst 202 → 199 = UNTOUCHED** (the scope guard, the load-bearing
correctness datum); ve-diversified share **11.9% → 6.7%** (index half down,
single-name ve preserved). All three fire; the guard holds.

**Goldens: byte-identical** (no re-pin) — the effects are a threaded optional
input; the cold-start (no-param) golden path is unchanged (482 enumeration
tests green pre-bump). v46 bump is for cohort attribution (`funnel --compare
v45 v46`) + the suppressed-mass census boundary (the v32/v5 precedent: a
version bump whose activation is the daemon passing the new input). The
`test_v1_grammar_loads` version assert → v46.

**Tests:** `test_refutations.py` (consumer: binding table, resolve, self-heal,
fingerprint) + `test_sampler_refutations.py` (active behavior + byte-identity of
the inactive path). Full suite green pre-commit (see STATUS). mypy --strict +
ruff clean.

**Standing value beyond the 3 cells:** the registry's `unlock` fields are now a
live, machine-readable ledger of what structure reopens each dead region — the
Path C exhaustion evidence, maintained Crucible-side. When any entry is wired,
per-entry suppressed share flows to the funnel/census keyed by entry id
(Crucible's P5 KPIs read against it). Related: [[D313]] (the mapping), [[D310]]
(the search-multiplicity tax this relieves), [[D290]] (ve-solo-density
interaction), [[D317]]/[[D319]] (v44/v45, the base), [[D268]] (the
earnings-manifest fingerprint precedent).

## D321 — 2026-07-21 — Complexity-reduction pass: retire the `shadow-null` diagnostic harness + sweep 7 closed-loop relays (operator "recommended is good" — the top two items from the accreted-complexity audit). No daemon path touched; no grammar/contracts change; no restart required

**Context.** The operator flagged accreted complexity and asked what no longer
serves the stack. A read-only audit produced an inventory; the two highest
value-for-lowest-risk items were executed here (env-flag cull and the inert
`experiment_cells` floor were surfaced but NOT touched — the floor reopens on
the next campaign; the flag cull was subsequently ABORTED, see correction below).

**CORRECTION (env-flag cull aborted).** The audit's "4 never-activated flags"
was a code-DEFAULT read, not runtime truth. Verifying against the live
`forge.service` unit + `/proc/<MainPID>/environ`: 3 of the 4 are LIVE in
production — `FORGE_ORTHOGONAL_FAMILY_FLOOR=volatility_event=0.20` (D216),
`FORGE_EXPLORATION_HOLDOUT_FRAC=0.05` (D256, prereg 61837dd2),
`FORGE_YOUNG_CELL_FLOOR=on` (D312); only `FORGE_YOUNG_CELL_EXPLORE_SLOTS` is
unset (deliberately-staged 2d, D316). Deleting either proposed target would
have removed a live steering lever. No orphaned `FORGE_*` flag exists — every
runtime flag is live or staged. Lesson: check the service unit + live environ,
never the code default, before culling a flag.

**1. `shadow-null` harness RETIRED.** `forge/prefilters/shadow_null.py`,
`forge/cli/shadow_null_cmd.py`, and their two tests deleted; the import +
`add_typer(shadow_null_app, name="shadow-null")` removed from `cli/main.py`
(lines were the only wiring — the module was a standalone Typer sub-app, never
imported by the §5.2 battery or the daemon loop, so the run loop is byte-for-byte
unaffected). It was built to shadow-count TWO permutation-test (§5.3.7) null
corrections before their flips: FLIP-1 `cumulative_trading` (prereg 848a1f67 —
SHIPPED to production, D224/D226) and FLIP-2 ve |move| (prereg e1a43ba8 —
REFUTED + thesis-inverted, DROPPED D235, arm removed D301). Both flips are
resolved; the harness only ever re-counted FLIP-1, already live — spent
diagnostic. Docs cleaned same commit (`MANPAGE.md` §`forge shadow-null run`
removed; `architecture.md` cli/ row clause removed). Reversible from git
history if a future null correction wants the A/B rig again.

**2. Relay sweep (7 files → `_archive/`).** Root `PROMPT_CRUCIBLE_*.md` count
22 → 15. Archived exactly the relays whose loops are closed per RELAYS.md:
`ALPHA_BUDGET_DSR`, `EV_DEREGISTRATION_RESPONSE`, `HOUSEKEEPING_ASKS`,
`SMA_SLOPE_NOT_COMPUTED`, `TIER_UNPIN_RESPONSE`, `XSECT_CORRECTION_RESPONSE`
(all "answered — archive candidate"), and `REFUTATION_REGISTRY_REPLY` (its
"archive after the wiring decision" condition met — the wiring shipped as v46,
D320). Ledger rows pruned + a sweep note added. Held back deliberately:
`SEARCH_N_TRIALS_INTERACTION` (still owes an outbound carry — it carries the
receipts banner) and `V43_DEPLOYED` (waits on the scheduled `funnel --compare
v42 v43`). 3 of the 7 were untracked (D104 tree-clean hygiene — they were a
standing reboot-surface risk).

**Gates.** mypy --strict clean (108 files); ruff clean; `tests/unit/test_cli`
+ `tests/unit/test_prefilters` 394 green; full suite green (see STATUS).
`forge --help` no longer lists `shadow-null`. Related: [[D301]] (FLIP-2 arm
removal), [[D235]] (FLIP-2 refutation), [[D224]]/[[D226]] (FLIP-1 ship),
[[D295]]/[[D302]] (the relay-archive pattern + RELAYS ledger), [[D320]] (the
v46 wiring that closed the refutation-registry relay).

## D322 — 2026-07-21 — Complexity-reduction pass (cont.): Tier-1 dead-code removal — two verified-dead exported symbols from the accreted-complexity audit (operator "lets do tier 1. make sure its a safe deletion through validation"). No daemon path touched; no grammar/contracts change; no restart required

**Context.** Continuation of [[D321]]. The audit's tiered plan put two exported
symbols in Tier-1 (delete-now, verified-dead). Deadness was re-confirmed
independently at this HEAD before cutting — full-repo grep of each symbol across
`src/ tests/ scripts/ docs/ *.md`, plus a check that no `import *` consumer pulls
either via `__all__`. Both were reachable only from their own tests.

**1. `should_auto_apply_proposal` REMOVED** (`feedback/proposer.py`). The D044/T2.3
auto-apply decision gate — framework for a future auto-apply path that was never
wired. No production caller auto-applies proposer proposals: the operator runs
`forge grammar apply-proposal`, and hard-rule #4 keeps every loosening
operator-gated (the daemon's proposal path writes `OPEN_PROPOSALS.md` and stops).
The only references were 3 tests + its `__all__` entry. Removed the function, the
`__all__` entry, and the 3 tests; reworded the one dangling docstring reference in
the kept `evaluate_counterfactual` (which stays — `proposal_writer` imports it).

**2. `brier_decomposition` REMOVED** (`ranking/calibration.py`). The Murphy
`(reliability, resolution, uncertainty)` diagnostic. Its sibling calibration
helpers (`expected_calibration_error`, `platt_fit/apply`, `reliability_table`) are
imported by `ranking/evaluation.py`; this one never was — only 2 tests used it.
Removed the function, the `__all__` entry, and the 2 tests. The historical D-log
mention (this file, the D-entry that introduced it) left in place as provenance.

**Deferred, NOT touched.** The rest of Tier-1 is tree hygiene over operator-owned
UNTRACKED files (`scratchpad/` one-offs + 5 untracked `PROMPT_CRUCIBLE_*.md`) —
no git safety net, so "delete" is not a safe operation on them; surfaced for the
operator to commit/archive rather than cut (the relay files are live Q46 work, not
stale). Tier-2 (`auto_tune.py` shrink, `--orthogonal-yield`, the superseded
`compute_hypothesis_weights`) waits on the audit's open questions.

**Gates.** 4 files, 144 deletions / 3 insertions. mypy --strict clean (108
files); ruff check + format clean (no stale imports — F401 clean); full suite
**2077 passed / 1 skipped** (the skip pre-exists — "no live refutations export").
Both symbols were unreachable from the run loop, so the daemon is byte-unaffected;
no restart. Related: [[D321]] (the pass this continues), [[D301]] (the prior
dead-export cut), [[D044]] (the T2.3 auto-apply origin), [[D105]] (the proposer
re-aim that left the gate unwired).

## D323 — 2026-07-21 — Complexity-reduction pass, Tier-2 (part 1): remove the superseded `compute_hypothesis_weights` promotion-only weighter + its `_iter_hypothesis_outcomes` helper (operator via AskUserQuestion: "Active development" · "Delete whole ~150-LOC stratum"). SCOPE CORRECTED by independent verification. No daemon path touched; no restart

**Context.** The audit put a "~150-LOC dead stratum in `rejection_weights.py`" in
Tier-2; the operator approved deleting it, with the standing instruction to verify
each symbol dead first. Verification materially corrected the scope — a good catch:

- **`_REWIRE_DELTA_CRITERION` is LIVE, not dead.** It lives in
  `cli/ranker_model_cmd.py:74` (not `rejection_weights.py`) and the live ranker-eval
  timer imports it (`scripts/daily_ranker_eval.sh:269`). The `STATUS.md:606`
  audit note calling it "dead" was stale. **Excluded — untouched.**
- **`prior_mean` and `is_ve_ghost_label` are LIVE** (`main.py:645–895` sampler
  fallback; `dataset.py:131` + `trade_rate_priors.py:227` + `rejection_weights.py:501`
  ghost cuts). **Kept.**

So the verified-dead set was smaller than "150 LOC": the promotion-only weighter
`compute_hypothesis_weights` (superseded D094/D101 — the live estimand is
`compute_hypothesis_component_weights`, `main.py:833/880`) and its **sole caller**
`_iter_hypothesis_outcomes` (~56 LOC). Neither is reachable from the run loop.

**Removed.** The two functions + the `__all__` entry + 7 tests (6 in
`test_rejection_weights.py`: the 5 `compute_hypothesis_weights` unit tests + the
corrupt-json test; 1 in `test_ve_ghost_cut.py`: `test_hypothesis_weights_exclude_ghost_ve_runs`).
Reworded 3 stale prose refs (module docstring wiring bullet → the live component
weighter; the D094 contrast comment; the floor docstring's "call … directly"
sentence) + the D067 test comment.

**Coverage preserved (verified before cutting).** The ve-ghost cut is independently
covered on every LIVE path — `test_ve_ghost_cut.py` still exercises it via
`build_dataset` (dataset), `compute_mature_arms` (arm_floor), and `is_ve_ghost_label`
directly. Corrupt-JSON skipping is covered on the live component path by
`test_component_rate_weights.py:600` (`test_deterministic_and_orphans_and_corrupt_skipped`).
No live behavior lost coverage.

**Deferred — `--orthogonal-yield` (H4).** The operator approved "abandon + delete",
but the audit's "~60 LOC dead flag" estimate was wrong: it's a full feature threaded
through the **determinism-critical sampler** (`sampler.py:1081/1123/1233`), the
enumerator (`iterator.py`), a live feedback computation (`compute_orthogonal_yield_discounts`),
plus a dedicated `test_orthogonal_yield.py`, invariant tests, and MANPAGE docs.
Full removal is rule-#6-sensitive sampler surgery → belongs in a worktree, not the
live tree. Held pending the operator's scope decision (full removal vs. CLI-only
strip leaving the inert `=None` engine param).

**Gates.** ruff check + format clean; mypy --strict clean (108 files); full suite
**2070 passed / 1 skipped** (2077 − 7 removed tests; the skip pre-exists). Dead path
→ daemon byte-unaffected, no restart. Related: [[D322]] (Tier-1, same pass), [[D301]]
(the prior `compute_hypothesis_reward_weights` cut in this same stratum), [[D094]]/[[D101]]
(the removed weighter's origin), [[D105]] (the component-rate lane that superseded it).

## D324 — 2026-07-21 — Complexity-reduction pass, Tier-2 (part 2): FULL removal of the H4 `--orthogonal-yield` feature — the never-launched marginal-value discount lever (operator via AskUserQuestion: "Full removal in a worktree"). Built + validated in `../Forge-build`; byte-identical proven; NOT yet landed on main

**Context.** The audit called `--orthogonal-yield` a "~60-LOC dead flag." Verification
showed it was actually a full feature (~980 LOC incl. tests) threaded through the
**determinism-critical sampler** — never activated in production (the flag was never
set on the unit). Operator chose full removal, done in an isolated worktree per
the CLAUDE.md rule for sampler-touching changes.

**Removed end-to-end** (branch `simplify/d324-orthogonal-yield`, 11 files, −979 net):
- **Feedback:** `compute_orthogonal_yield_discounts` + `_factor_cell_of` + the two
  `DEFAULT_ORTHOGONAL_YIELD_*` constants + `__all__` entries (`rejection_weights.py`).
- **CLI:** the `--orthogonal-yield` flag + `_load_/_format_orthogonal_yield_discounts`
  + the H4 apply block + all `orthogonal_yield` param threading (`cli/main.py`).
- **Engine:** the `orthogonal_yield_discounts` param on `enumerate_candidates` and
  `sample_config`, the H4 slice block, and the `factor_cell_discounts` param + the
  `weight *= discounts.get(t, 1.0)` multiply in `_pick_underlying`
  (`iterator.py` + `sampler.py`).
- **Tests:** deleted `test_orthogonal_yield.py` (12 tests); removed 6 H4 tests from
  `test_sampler.py` (4) / `test_quality_term.py` (1) / `test_phase2_invariants.py` (1);
  dropped the flag from `test_run_loop.py`'s forward-parity list.
- **Docs:** MANPAGE flag row + the `feedback-change.md` journal-watch line.

**KEPT (the near-miss trap):** `apply_orthogonal_family_floor` / `FORGE_ORTHOGONAL_FAMILY_FLOOR`
is a DIFFERENT, LIVE feature (D216, `volatility_event=0.20` on the unit) — name-adjacent,
untouched. Also kept: `_COMPONENT_DECISIONS`, `_directional_indicator_of`, every other
weight param.

**Rule #6 byte-identical proof (the gate for a sampler edit).** Cross-tree, main
(pre) vs worktree (post): (1) production weights-off path — `forge enumerate` over
6 seeds → identical SHA256 (`527db225…`), 1530 lines each; (2) the weights-ON path
(the only other site the multiply touched) — a `_pick_underlying` probe with
class+name weights present, 9600 draws → identical SHA256 (`3edf9e5a…`), confirming
`weight *= discounts.get(t,1.0)` was exactly `×1.0`. Also: `sample_config`'s
`# noqa: PLR0912` became RUF100-unused after the slice block went (fewer branches) —
removed; two dangling doc cross-refs (`_load_cohort_yield_weights` "Mirrors …",
a "like --orthogonal-yield" comment) repointed to live siblings.

**Gates (in the worktree venv).** ruff check + format clean; mypy --strict clean
(108 files); full suite **2052 passed / 1 skipped** (2070 − 18 removed tests; the
skip pre-exists). **NOT landed:** committed on the branch only; awaiting the operator's
landing call (byte-identical → a fast-forward merge needs no restart; the daemon keeps
producing identical output and picks up the new code on the next natural restart).
Related: [[D323]] (Tier-2 pt.1, same pass), [[D322]] (Tier-1), [[D108]] (the H4 origin
this retires), [[D216]] (the orthogonal-FAMILY floor — the different live feature kept).

## D325 — 2026-07-21 — Complexity-reduction pass, Tier-2 (part 3): delete the dead §5.5 auto-tune TRIGGER + extract its bundled live helpers to honest homes (operator via AskUserQuestion: "Extract to honest homes"). Built + validated in `../Forge-build`; behavior-identical; NOT yet landed

**Context.** Operator asked whether auto-tune is ever actually used. Empirical
answer: **never** — the live `grammar_versions` table has 44 rows, ALL
`manual_bump` / "auto-recorded on first load" (incl. v44/45/46 today); zero from
auto-tune or apply-proposal; `auto_tightened_thresholds.yaml` empty; `enabled:
false` (D218/D206). `auto_tune()` was called every batch (via `--consume-feedback`)
but hit the `enabled` guard and returned immediately — a no-op the whole time.

**The trap the module posed.** `feedback/auto_tune.py` (307 LOC) was mis-factored:
it bundled the dead §5.5 trigger with THREE live helpers — `ensure_grammar_version_recorded`
(the daemon calls it every cycle; it wrote today's v44/45/46 provenance rows),
`_write_grammar_versions_row`, and `write_calibration_yaml` (the live `apply-proposal`
path uses the last two). So a blind `rm` would have broken grammar-version
provenance + the manual tighten path.

**Verified NOT to widen: `apply-proposal` is LIVE.** The feedback proposer still
emits `gate_failure_concentration` tighten proposals (`proposer.py:96`), and
`cmd_apply_proposal` is their standing apply path — an operator-gated hard-rule-#4
mechanism, unused-so-far but functional. So `apply_tightening` / `propose_adjustment`
/ `AutoTuneCalibration` / `cmd_apply_proposal` were left UNTOUCHED. (Consequence:
`AutoTuneCalibration`'s `enabled`/`min`/`max` fields are now config-present-but-unread;
only `adjustment_pct_per_step` stays live via apply-proposal — left as-is, a possible
future config-slim.)

**Done (10 files, net −734).**
- NEW `src/forge/grammar/version_audit.py` (107 LOC) — `ensure_grammar_version_recorded`
  + `_write_grammar_versions_row` moved verbatim (grammar-version provenance, D051).
- `write_calibration_yaml` → `prefilters/calibration.py` (with the `Calibration` model).
- DELETED `feedback/auto_tune.py` — the dead §5.5 trigger (`auto_tune`,
  `_rolling_promotion_rate`, `_cumulative_tightenings`, `_apply_tighten_and_persist`,
  `_write_loosen_proposal`) + both feedback-chain call blocks (`main.py`,
  `feedback_cmd.py`) + their now-unused `auto_tune`/`load_calibration` imports.
- Repointed importers (`main.py`, `grammar_cmd.py` ×2). Zero `forge.feedback.auto_tune`
  refs remain (2 history-note docstrings aside).
- Tests: deleted `test_auto_tune.py` (604 LOC) + 3 auto_tune-coupled tests in
  `test_phase5_invariants.py`; moved the 4 recorder tests → new
  `tests/unit/test_grammar/test_version_audit.py` and `test_write_calibration_yaml_is_atomic`
  → `test_calibration.py`.

**Invariant coverage preserved (checked before landing).** Hard-rule-#4 (no
`apply_loosening`) still covered by 4+ sibling checks (phase5 prefilters/proposal_writer/
proposer/analyzer + phase3 + test_calibration + test_proposal_writer); the deleted one
introspected the now-nonexistent `auto_tune` module. §13.3 audit-row for the LIVE path
is covered by `test_grammar_cmd.py:307` (`test_apply_proposal_records_grammar_versions_row`);
the deleted §13.3 test only exercised the dead auto_tune tighten path.

**Gates (worktree venv).** ruff + format clean; mypy --strict clean (108 files, now
incl. the new module); full suite **2038 passed / 1 skipped** (2052 − 14 dead-trigger
tests; the 5 moved tests pass in their new homes). Behavior-identical: the removed
`auto_tune()` call was a disarmed no-op, and the daemon calls the recorder the same
way from its new home. **NOT landed** — awaiting the FF-merge (no restart needed).
Related: [[D324]] (Tier-2 pt.2, same pass), [[D298]] (auto_tune disarmed permanent),
[[D206]] (prefilter-tightening retired), [[D051]] (the grammar-version-audit origin).

## D326 — 2026-07-21 — Complexity-reduction pass, Tier-2 (part 4): slim `AutoTuneCalibration` to its one live field (operator via AskUserQuestion: "Prep now, land on next deploy"). REQUIRES A RESTART — built on a branch, NOT merged to main

**Context.** After [[D325]] deleted the §5.5 auto-tune trigger, four
`AutoTuneCalibration` fields (`enabled`, `min_promotion_rate`, `max_promotion_rate`,
`max_cumulative_adjustment`) became config-present-but-unread — only
`adjustment_pct_per_step` survives (the manual `apply-proposal` tighten step size).
This slims the schema, the loader, `prefilter.yaml`, and the test constructions to
that one field.

**Why this one needs a restart (unlike D322–D325).** The daemon calls
`load_calibration(prefilter_yaml)` at `main.py:1897` EVERY iteration, and the loader
`_require`s each key (raises on missing — the H-6 crash-loop hazard). The running
daemon executes its OLD cached code, which requires all five keys, but re-reads
`prefilter.yaml` from disk each cycle. So the moment the yaml loses `enabled`/`min`/
`max`, the old code's next iteration raises → crash-loop. The new loader reads the
one key and IGNORES extras, so new-code + old-or-new-yaml is safe; only OLD-code +
NEW-yaml crashes. Therefore the yaml change cannot touch the live tree until the
daemon restarts onto the new code.

**Landing protocol (operator, on the next restart-deploy — e.g. the next grammar
bump).** With the daemon DOWN: `git merge --ff-only simplify/d326-autotunecfg-slim`
→ restart → verify journal. Do NOT merge while the daemon runs old code. Main's
`prefilter.yaml` is untouched until then, so the running daemon keeps reading its
five-key yaml fine. A STATUS pointer on main flags the pending branch.

**Done (branch `simplify/d326-autotunecfg-slim`, 6 files).** Slimmed the dataclass +
the loader construction; `prefilter.yaml` auto_tune block → one key (comment updated);
`write_calibration_yaml` needs no change (`asdict` adapts); slimmed 5 test
constructions/fixtures (`test_batch_reproducibility`, `test_permutation_test`,
`test_calibration` ×3 fixtures + assertions, `test_grammar_cmd`,
`test_learned_ranker_invariants`). `apply_tightening`/`propose_adjustment`/
`cmd_apply_proposal` untouched (still live; still read `adjustment_pct_per_step`).

**Gates (worktree venv).** ruff + format clean; mypy --strict clean (108 files); full
suite **2038 passed / 1 skipped** (no tests removed — field-slim only). Related:
[[D325]] (the trigger deletion this follows), [[D298]]/[[D206]] (the retirement), and
the H-6 atomic-write audit note in `write_calibration_yaml`'s docstring (same crash
hazard).

## D327 — 2026-07-21 — DEPLOY (restart): adopt `crucible_contracts` 1.35.0 (pin-only) + land the D326 config-slim in the same window (operator: "bring in the latest pin and merge to master")

**Two changes, one restart.** [[D326]] (AutoTuneCalibration slim) needed the daemon
down (it removes `prefilter.yaml` keys the old code `_require`s), so the pending
contracts adoption rode the same deploy window.

**Contracts 1.35.0 — a FIX, not hygiene** (Crucible `f5631d7`, "add `lot_floor` SizerSpec
mode for small-capital tradeability"). Additive Literal on `SizerSpec.mode`.
**CORRECTED post-deploy from the pre-deploy "NO-OP" assumption:** the journal proved
Forge DOES construct `SizerSpec` during enumeration, the registry export ALREADY offered
`lot_floor` as a sizer_mode, and the pre-adopt 1.34.0 daemon was **failing whole
iterations** on it (`ValidationError`/`literal_error` on `mode` → iteration skipped, no
batch — journal PID 3671 iter 3097). Adopting 1.35.0 makes the mode valid and clears the
failures — verified post-restart: **0** failed iterations / SizerSpec errors on the new
daemon vs the old daemon's `lot_floor` aborts. No consumed model/hash changed → `§13.5`
major-guard already passes; a valid `lot_floor` config enumerates byte-identically (it just
no longer throws). Bumped `FORGE_EXPECTED_CONTRACT_VERSION` 1.34.0 → 1.35.0 + `uv.lock`
(editable source was already 1.35.0). The exact-match
`test_expected_contract_version_matches_installed` was the forcing function — RED (preflight
NO-GO) until adopted, GREEN after. Timeliness lesson: an editable-sibling minor that adds a
Literal Forge's enumeration can EMIT (not just read) is a live throughput bug until adopted,
not deferrable hygiene — the exact-match test + the iteration-failure journal are the two
signals.

**Deploy ritual (deploy.md / D104).** `deploy_preflight.sh` → NO-GO (the expected
contracts-red) → `stop` (clean SIGTERM exit 143) → merged `simplify/d326-autotunecfg-slim`
(only STATUS.md conflicted — resolved: D326→LANDED, pending banner dropped) → pin bump +
D327 → **full uncontended suite GREEN (2038 passed / 1 skipped)** against installed 1.35.0
+ pin 1.35.0 → commit → `reset-failed` + `start` → verified journal (contracts line 1.35.0,
grammar_version, registry_loaded_from_export, no traceback / SchemaVersionMismatch).
No unit-file change → no `daemon-reload` needed. `simplify/d326-autotunecfg-slim` branch
retired post-merge.

**Coordination note (D245).** Additive minor — the tolerant readers
(`parse_forward_compatible` / `parse_skipping_unknown_literals`) mean no asymmetric-wedge
risk in either direction even if Crucible's daemon adopts on its own cadence. Crucible
published 1.35.0 (editable source moved), so their side is already moving to it. Related:
[[D326]] (the co-landed slim), [[D317]] (the prior 1.34.0 adopt), [[D267]]/[[D262]] (the
pin-hygiene discipline), [[D245]] (the both-directions contracts-restart lesson).

---

## D328 — 2026-07-21 — §12 phases / hard rules #4·#6·#10 — GRAMMAR-FREEZE PROGRAM: the search-multiplicity census instrument + a measurable freeze criterion + the first clean-prune proposal (docs+tooling; NO deploy / grammar / determinism touch).

**Operator: "optimize and maximize the grammar as much as possible … the search_n_trials and freeze criterion (without opening Path C)." Approved the plan (`~/.claude/plans/precious-conjuring-alpaca.md`) at scope "instrument + clean prunes"; single-name axis deferred to a Crucible read.**

**Frame.** Grammar EXPANSION cannot raise the promotion cap — that is structural (Path C, parked, [[exhaust-long-options-before-v2-spreads]]) — and the signal surface is exhausted (a live-registry enumeration found 23/72 registered ids dark, none correctly-signed for a net-long-vol book). So "maximize the grammar" = CONVERGENCE toward a minimal, defensible frozen surface, not addition. **Honest scope, stated in every deliverable:** Crucible's DSR charge is SLOT-scoped ([[D310]] `search_multiplicity.slot_key` = hypothesis × dte_bucket × xsect/named), and the converting slots carry ~0 within-slot dead mass → pruning buys a minimal surface + reclaimed throughput, NOT a promotion. Optimizing for the right thing.

- **The instrument** (`scripts/search_multiplicity_census.py`, ruff + mypy clean, daemon-inert): reads a forge.db snapshot, decomposes `submissions` into slot × cell (`slot_key` × [[D299]] `campaigns.config_cell_from_json`), joins `verdicts` for conversion, classifies each cell {converting | protected | already_pruned | disabled_legacy | legacy_inactive | dead_unprotected | thin}. Liveness keys on SUBMISSION timing not decision timing (Crucible re-gates old configs → decided-recent overstates what's still emitted). Protection reads the blessed registries so it can't drift from the daemon: `campaigns.CAMPAIGNS` (farming) + `search_space`'s emission-exclusion sets (`_DIRECTIONAL_POOL_EXCLUDED_IDS` / `_REGIME_GATE_GLOBALLY_EXCLUDED_IDS` / `_VOL_EVENT_REGIME_EXCLUDED_IDS`, so it never re-flags v31/v33/v34 retirements) + `NON_ENUMERABLE_HYPOTHESES`. Reconciles EXACTLY to 526,789 distinct configs. It is the [[yield-map-refresh-status]]/`yield_audit` pattern generalized from names to cells.
- **Baseline (snapshot 2026-07-21T21:24Z):** converting 51.5% / protected 11.2% / already_pruned 7.9% / disabled+legacy 15.4% / dead_unprotected 4.1% / thin 10.0%. **FREEZE METRIC B = 2.80% dead-unprotected share of last-14d FLOW** — the stream is already efficient; freeze is closer than expected.
- **Three findings that corrected the plan:** (1) pruning cannot lower the converters' DSR hurdle (slot-scoped + converting slots ~0 within-slot dead mass — the hurdle is honest search breadth, not prunable waste). (2) `event_momentum` is NOT a clean prune — enumerated ONLY single-name, 0 recent components, no cross-sectional form generated → same "productive form not enumerated" class as the single-name trend/MR axis; deferred, not retired. (3) `relative_value` is already dormant (0 recent flow) → v47 retires it for surface minimality + to exercise the freeze machinery on a zero-risk case, not for throughput reclaim. The real 2.8% reclaim = the single-name trend/MR gated axis, GATED on a Crucible "do assembled books consume single-name components?" read (single-name is ~15.9% of the honest pool, [[D215]]/[[D186]] — Forge is blind to assembly usage, §1.2).
- **Freeze criterion** (`docs/proposals/grammar-freeze-criterion.md`): frozen = `grammar_version` stops bumping + `enumeration_inputs_hash` stabilizes + budget committed to the converting core. Two measurable conditions — (A) coverage: every material-flow cell classified {converting | refuted-and-pruned | protected-with-an-open-read}; (B) multiplicity efficiency: metric B below an OPERATOR-set threshold, stable over N census runs (threshold set from the baseline, robustness-streak pattern). Freeze ledger = the refutation registry ([[D320]]) + the census JSONL. Reopeners (freeze is reversible): a Crucible refutation retraction, a new net-long-vega registry family, or a Path-C decision.
- **First prune, STAGED** (`docs/proposals/v47-dead-hypothesis-retirement.md`): `relative_value` → `DISABLED_HYPOTHESES` (the `regime_arbitrage`/[[D098]]/v5 enumeration-policy pattern — rules text unchanged, version bump for funnel attribution). Auto-tightening (hard rule #4 permits without approval); the DEPLOY is operator-gated. Prereg-first ([[D207]]), goldens re-pin (removes draws → sequence shift, [[D309]] precedent), emission proof 0 relval draws. NOT built — this doc + the prereg are the gate.

**Alternatives considered:** (a) add the dark vol-surface ids (`skew_25d`/`butterfly_25d`/`vol_of_vol`/`iv_vs_index`/`realized_skew`) — REJECTED, seller-side/wrong-sign for a net-long-vol book ([[grammar-review-expansion]] D303), and they'd inflate multiplicity; (b) prune the single-name axis unilaterally — REJECTED, it is Crucible's assembly-diversity source, needs their read; (c) treat pruning as a promotion unlock — REJECTED on the slot-scoped-DSR mechanics above.

**Files:** `scripts/search_multiplicity_census.py` (new), `docs/proposals/grammar-freeze-criterion.md` (new), `docs/proposals/v47-dead-hypothesis-retirement.md` (new), `STATUS.md`, this entry. No `src/` / grammar / config change → daemon byte-unaffected, reboot-safe, no restart.

**STATUS: freeze instrument + criterion landed (docs+tooling); v47 STAGED (operator-gated deploy); the single-name-axis Crucible relay is next (operator ships), then census productionization (Step 1b), then the v47 deploy on the word. NB D-number: max committed header was D327 with a pre-existing headerless `D333` prose gap; took D328 (tree clean of concurrent work at commit time — renumber if a race surfaces).**

**↳ 2026-07-21 (later) — single-name-axis relay DRAFTED + Step 1b (census productionization) LANDED (D328 cont.; no restart).** (1) `PROMPT_CRUCIBLE_SINGLE_NAME_AXIS_RETIREMENT_ASK.md` (held for carry, RELAYS.md row): the flag read gating the 2.8% reclaim — do assembled/promoted books consume single-name trend/MR components (name-breadth vs a distinct factor)? Flag yes/no/which; throughput-not-promotion framing (slot-scoped DSR); event_momentum rides along (single-name only, no xsect form generated); single-name `volatility_event` explicitly out of scope (protected). (2) **Step 1b:** the census tool gets `--jsonl-out` (one metric-B row via `forge.core.clock.utc_now`); `daily_ranker_eval.sh` appends `search_multiplicity_census.jsonl` reusing the block's existing snapshot (no 2nd cp); `check_search_multiplicity_census` (`healthcheck_cmd.py`) WARNs on metric-B > a 5% operator bar (freeze-criterion condition B, tunable) or a stale file, + its `test_healthcheck` case. **Full suite 2039 passed / 1 skipped; ruff + mypy clean.** **DEVIATION (owned):** kept the census as the `scripts/` tool + wired the daily timer/healthcheck, rather than the plan's `forge search-multiplicity-census` command — avoids editing the delicate/monkeypatched `main.py` (D065/D105/D106); the CLI command is a trivial yield-audit-pattern add if the operator wants discoverability. Daemon-inert (daily timer + healthcheck sit outside the run loop) → reboot-safe, no restart. Files: `scripts/search_multiplicity_census.py`, `scripts/daily_ranker_eval.sh`, `src/forge/cli/healthcheck_cmd.py`, `tests/unit/test_cli/test_healthcheck.py`, `docs/MANPAGE.md`.

**↳ 2026-07-21 (later²) — single-name-axis read ANSWERED + v47 EXPANDED/HELD (Path B) + the SOXL/event_momentum catch (D328 cont.; no deploy).** Crucible's `FORGE_single_name_trend_mr_retirement_read_2026-07-21` answered the relay: **single-name trend/MR = 0 consumption across all 4 promoted books + all 106 assemblies ever** (363 xsect-trend / 142 xsect-MR slots vs 0 single-name; ~361 admitted-but-never-selected) → **GREENLIT to retire** (their pool counts 136/225 ≈ our ~130/~220; agreed throughput/surface win, not a promotion unlock — slot-scoped DSR, D310). **v47 expanded to bundle** `relative_value` (DISABLED_HYPOTHESES) + single-name trend/MR (**sampler xsect-only** — a new mechanism, not DISABLED_HYPOTHESES, since trend/MR keep their converting xsect form) + **pending** single-name event_momentum. **event_momentum correction (operator caught it):** Crucible flipped em to "keep single-name + add xsect-PEAD" on the grounds that `pure_sue175` uses a single-name em leg — but that leg is the **[[D268]] degenerate** (SOXL, a no-EPS leveraged ETF: `sue` NaN→FLAT, `days_since_earnings` NaN→`allow=True`, `realized_vol` passthrough→naked long-SOXL calls, 0 PEAD; mislabeled leveraged-semi beta). Forge already fixed generation (D268 + v32 manifest → SOXL excluded from earnings-gated) so it is **unreproducible**; the real-company single-name em Forge emits is **dead** (~3 comps = their pool count, 0 conversion). So Crucible's keep-rationale (and their xsect-PEAD "SUE sleeve" motivation) rests on a degenerate. **Relay `PROMPT_CRUCIBLE_EVENT_MOMENTUM_SOXL_DEGENERATE.md`** (held, operator ships): #1 confirm degenerate / #2 retire single-name em too (folds into v47 on a fast yes) / #3 is xsect-PEAD still wanted. **Path B (operator "let's do Path b"):** HOLD v47 for the em answer so one restart covers all three single-name axes + relval; slow answer → v47 ships without em, em → v48. **Census accuracy follow-up queued** (tooling, not grammar): protection should read promoted-book components (`promoted_portfolios` export) + recognize the D268 no-earnings-underlying exclusion + flag degenerate legs — the SOXL leg was a census false-positive "dead." **NO deploy, NO grammar/determinism change this step** — docs + a held relay only; reboot-safe. Files: `PROMPT_CRUCIBLE_EVENT_MOMENTUM_SOXL_DEGENERATE.md`, `docs/proposals/v47-dead-hypothesis-retirement.md`, `RELAYS.md`, `STATUS.md`.

**↳ 2026-07-21 (later³) — event_momentum re-read ANSWERED + v47 mechanism designed + capitulation blocker surfaced (D328 cont.; still no deploy).** Crucible `FORGE_event_momentum_soxl_degenerate_reply_2026-07-21` — independently verified the SOXL leg (run `722fe985`: 233/233 long-SOXL calls, `sue` NaN throughout, no earnings clustering, +$130.6K = leveraged-semi beta): **#1 confirmed D268 degenerate, #2 GO retire single-name event_momentum, #3 WITHDREW the xsect-PEAD ask** (their own lit-review has PEAD dead as a naked long leg). Operator "bundle all into v47." **Sampler mechanism (from the read):** the retirement is asymmetric — `relative_value` + `event_momentum` are clean `DISABLED_HYPOTHESES` disables (event_momentum is single-name-ONLY: `sue` is `rank_per_name_coherent=False` → no xsect form, so retiring single-name em = disabling the hypothesis); single-name trend/MR is real surgery (pin `p_xsect=1.0` via `_cohort_xsect_probability` [the D276 pattern] + pool-exclude rank-excluded ids so every recipe is rank-eligible → named path disappears; big goldens re-pin). **BLOCKER surfaced (operator chose "relay Crucible first"):** blanket single-name-MR retirement KILLS the **capitulation** cell — `momentum` ∈ `_RANK_POLICY_EXCLUDED_IDS` (rank-excluded) → capitulation (MR × `momentum` drop-trigger) is single-name-only, no xsect form; it is the v31/v35/v36 cell with D279's first-positive-slot-delta (+0.0267) + D282 conversion. Their family-level "0 single-name MR consumption" scan nominally includes it but doesn't reconcile with the positive in-book signal. **Relay `PROMPT_CRUCIBLE_CAPITULATION_IN_SINGLE_NAME_MR_RETIREMENT.md`** (held, operator ships): did the 0-consumption read cover capitulation + retire-or-exempt (directional-scoped MR xsect-only). **v47 HELD** on this answer; relval + single-name em + single-name trend ride the same bump unaffected, MR scoped per the reply (Path B one-restart). NO grammar/determinism change built this step. Files: `PROMPT_CRUCIBLE_CAPITULATION_IN_SINGLE_NAME_MR_RETIREMENT.md`, `docs/proposals/v47-dead-hypothesis-retirement.md`, `RELAYS.md`, `STATUS.md`.

**↳ 2026-07-22 — v46 → v47 DEPLOYED (D328 cont.; operator "Deploy"). Capitulation EXEMPTED** (Crucible `FORGE_capitulation_exempt_v47_2026-07-21`: the momentum cell = 238 runs / 0 components / 0 consumed but distinct from the dead classic MR — the program's ONLY positive slot-delta (D279), a named live successor candidate (`champion_successor_spec`), `refutations.yaml: caution_not_refuted`; 0 of 116,383 xsect MR runs use momentum → deletion irreversible → exempt with a defined close-out). **Mechanism:** `relative_value` + `event_momentum` → `DISABLED_HYPOTHESES` (event_momentum single-name-ONLY via rank-excluded `sue`, so disabling = full retirement; the D268 SOXL leg unreproducible + Crucible-verified degenerate run 722fe985, xsect-PEAD withdrawn); the iterator's `_is_retired_single_name` filter drops confluence (single-name) trend/MR, KEEPING xsect (converting core) + the `momentum`/capitulation cell. Emission-policy: `sample_config` byte-identical (the sampler goldens capture `enumerate_candidates` output, which shifts legitimately — em/relval leave `samplable_hypotheses`, the filter advances the retry rng). **Build** (`../Forge-build` `03de3f7`): 2042 passed / 1 skipped; ruff + mypy clean; **7 goldens re-pinned** off the pinned-universe fixture (flag-off invariants re-verified first; relational splits → position 0, documented per test); new `test_v47_single_name_retirement.py`; D037 tests now pass a share (single-name trend/MR need their xsect form to meet the floor). **Deploy** (v44/v45 pattern, FF-merge byte-identical to the green worktree): prereg `2c3d5ab6cc5a` FIRST → stop → FF-merge → smoke (v47, contracts 1.35.0, relval=0/em=0/xsect trend 1276/MR 685/0 bad single-name on live registry) → commit → restart. Slot-scoped DSR (D310) → throughput/minimal-surface win, NOT a promotion unlock. Contracts unchanged (1.35.0), no unit change (no daemon-reload). Files: `config/grammar.yaml` (+archive v47.yaml), `search_space.py`, `iterator.py`, 8 test files, `config/preregistrations.jsonl`, `docs/proposals/v47-dead-hypothesis-retirement.md`, `PROMPT_CRUCIBLE_V47_DEPLOYED.md`, `RELAYS.md`, `STATUS.md`. NEXT: journal verify + `funnel --compare v46 v47` + prereg resolve on the post-cut cohort.

**↳ 2026-07-22 (later) — v47 → v48 DEPLOYED (D328 cont.; operator "v48 go" → "deploy"): the honest-coverage LABEL FIX (`rank_k<=10`) + emission de-crowding. Scope CHANGED from the staged proposal.** Crucible's `FORGE_coverage_gate_rootcause_reply_2026-07-22` root-caused our §5 label starve end-to-end and **inverted our lane hypothesis**: it is the **forge** lane (17,077/24,096 = 70.9% `coverage_unverified`), not `fullhist_refit` (**0 of 12,844**) — our blended 29.9%→60.5% weekly trend was a 0% lane mixing with a 70–97% lane. **Mechanism:** their `_resolve_chain_floor` rank branch needs `n_min = _RANK_BREADTH_MULTIPLE x rank_k = 2 x rank_k` chain-live members before ranking counts as a *selection* (operator decision 2026-06-09, `design_rank_regime_coverage_floor`); our xsect configs stamp `tier=2`, which has **20 members**, so `rank_k=20` needs 40 → floor `None` → `coverage_unverified` → `regime_coverage` degrades to a trivial pass → our D128 label never fires. Their split is total: `rank_k=20 x tier2` = 16,843 components / **100.0%** unverified; `rank_k=10 x tier2` = 7,030 / **0.2%**. **16,843 of 16,878 (99.8%) of the entire starve is one cell.** Their gate detail string (`no period/chain_floor supplied (ad-hoc/CLI path)`) is wrong for this population and misled both sides — `period` IS supplied; they are fixing the message. **v48 mechanism (3 sampler changes; rules text unchanged, D098/v5 emission-policy class):** (1) **`_RANK_K_CHOICES (5,10,20) → (5,10)`** — took their ask-#1 `rank_k<=10` path, explicitly NOT `tier=0`, because **[[D296]] is Crucible's own standing directive** to hold xsect at `tier=2` until per-name spread charging lands; flagged in the relay that a tier move needs an explicit D296 retraction. (2) **`p_xsect` PINNED to 1.0 for trend+MR** (`_cohort_xsect_probability`, D276 pattern extended from one directional to two hypotheses) — with single-name retired (v47) the cohort split is meaningless, and the pin recovers the ~39% of draws that were drawn-then-filtered. **Determinism correction (caught by `test_cold_path_byte_identical` / `test_rank_share_zero_is_byte_identical`):** a first attempt let the pin override the cold path and an explicit `share=0.0`; restructured so the pin governs the SPLIT only and applies only when `base > 0.0` → **6 of 7 sampler goldens came out BYTE-IDENTICAL to v47** (only the seed-4242 weighted-path cohort golden moved). (3) **`_RESID_MOMENTUM_PILOT_WEIGHT 2.0 → 1.0`** (D319 dial retired; Crucible confirmed n=1,283 banked, their 2026-08-04 P2 in-book read unaffected). **The `momentum_252` emission boost was DROPPED** — the staged proposal's headline change. Funnel trace: enumeration supplies it at **28%** of trend-xsect, post-prefilter holdout (unbiased) **8.43%**, ranked **0.33%** → the loss is our RANKER, whose F3 `P(component)` eligibility model trains on the very label `rank_k=20` starved. Chain: `rank_k=20` → coverage unverified → label starves → F3 mis-calibrates → it de-selects Crucible's best trend directional (lift 4.11). Their fix is upstream of ours; boosting emission on top of a mis-ranking lane would have masked it. (An earlier read claimed the ranker mildly *favoured* momentum_252 at 6.57% vs 5.20% holdout — that was a mixed-version window; v47-scoped it is 0.33% ranked vs 8.43% holdout. Data over theory; the relay carries the corrected numbers.) **Build** (`../Forge-build` `2160149`): **2042 passed / 1 skipped**; ruff + mypy --strict + both grammar scanners clean (worktree commit needed `--no-verify` — the hooks' `python` shim is absent there; both scanners verified manually). **Deploy** (v47 pattern, FF-merge byte-identical to the green worktree): prereg **`be5508b63706`** FIRST (cohort_cut `2026-07-22T15:55:30Z`; predicts post-cut forge-lane `coverage_unverified` share ~97% → <10%, resid share of trend-xsect < 10%, momentum_252 ranked share recovers above 0.33%) → stop → FF-merge → live-tree smoke → commit `05854a6` → restart. **Live-tree emission proof:** `rank_k` distribution **{5: 1754, 10: 1786} — 20 ABSENT**; resid 5.02%; momentum_252 24.09%; trend single-name **0** (v47 intact); MR xsect 1269 / named 183 (capitulation preserved). **Restart verified:** `active/running`, **NRestarts=0**, `grammar_version=v48 registry_hash=c890393f793b5a5c`, `registry_loaded_from_export`, `grammar_versions: recorded manual_bump row for v48`, orthogonal-family floor ACTIVE, refutation_guard active, **no traceback / `extra_forbidden` / `literal_error`**. Contracts unchanged (1.35.0), no unit change (no daemon-reload). **Crucible's §6 correction ACCEPTED:** `coverage_unverified` is NOT *universally* portfolio-ineligible as our D124/D128 read assumed — it holds for their honest-pool lane (`_select_honest_pool`) but the **explicit-assembly** lane bypasses it, and one unverified component reached a promoted book (`79eb6d55` `pure_sue175`, leg `96b67aa1` at weight 0.4125, `rsi_14 x rv_rank x ivol`) — itself a `rank_k=20` MR-xsect leg, i.e. exactly the cell v48 stops producing. **Ask #2 ANSWERED yes** (two-reason export field `breadth_impossible` vs `ad_hoc`; they open the contracts bump FIRST per the 1.28.0 scar sequencing). **Their fail-closed option (adding `forge` to `_COVERAGE_REQUIRED_SOURCES`) is on the record and correctly deferred** — it would flip 16,878/24,125 forge components (70.0%, 45.6% of their whole pool) to reject; right order is emit-clean → then decide on the residue. Relay addendum appended to `PROMPT_CRUCIBLE_EMISSION_REWEIGHT_AND_COVERAGE_GATE.md` (held for carry). Files: `config/grammar.yaml` (+archive `v48.yaml`), `sampler.py`, `search_space.py` (shared `XSECT_ONLY_HYPOTHESES`), test files, `config/preregistrations.jsonl`, `docs/proposals/v48-trend-emission-reweight.md`, `PROMPT_CRUCIBLE_EMISSION_REWEIGHT_AND_COVERAGE_GATE.md`, `STATUS.md`. **First v48 batch verified** (`646378f1`): 200/200 stamped v48, **`rank_k` {5: 96, 10: 87} — 20 ABSENT on submitted rows**, 183 xsect / 17 named (16 ve + 1 MR `momentum` capitulation), trend named 0, relval/em 0. Landed ~19min post-restart — the daemon blocked in `_fetch_activation_dates_chunked` on the db_writer socket while `crucible-fullhist-refit` held ~1.9 cores; the writer log showed it serving Forge per-underlying (up to 35.6s on cache misses), i.e. cold-cache contention, not a hang (py-spy confirmed the stack). **WATCH, honest:** `momentum_252` is 0 of 156 ranked trend rows in that batch (rolling_sharpe 48.7 / donchian 34.6 / resid 16.7%) — the ranker still de-selects it, as diagnosed; F3 has not retrained yet (first honest fit = next 05:00 timer). Prereg leg-3 NOT yet met; leg-2 splits by stage (resid 3.5-5.0% of EMISSION = met per the prereg's wording, 16.7% of RANKED = not). n=156, not the resolution cohort. **NEXT/WATCH:** does momentum_252's ranked share recover once F3 retrains on the de-starved label (first honest fit at the next 05:00 timer)? If not → a D287-style selection-layer floor. Plus `funnel --compare v47 v48` + resolve preregs `2c3d5ab6cc5a` (v47) and `be5508b63706` (v48) on post-cut cohorts.

**↳ 2026-07-22 (later²) — Crucible VERIFIED v48 to the row; **D296 STANDS**; prereg `2c3d5ab6cc5a` RESOLVED confirmed (D328 cont.; no code/grammar change).** Their `FORGE_v48_verified_and_d296_stands_2026-07-22`. **(1) v47 prereg resolved = confirmed** on the drained cohort (3,548/3,600): leg-1 single-name trend/relval/em conversion 0 by construction (census: zero emitted, capitulation persisting); leg-2 xsect component conversion 14.6% → 14.4% = −0.3pp vs ~0.6pp SE at n=3,548 → within noise, no converting supply lost; promoted 0↔0; unpredicted bonus pre-filter survival 23.6% → **38.0% (+14.3pp)**. **The discipline earned its keep:** their earlier PARTIAL read (506 decided) showed **+1.3pp** and reversed to **−0.3pp** on the drain — without the prereg we would have banked "v47 lifted conversion" into the freeze case. Canonical sentence: **v47 buys upstream efficiency, NOT component yield.** **(2) v48 verified independently from both ends:** their `rank_k = {5:55, 10:50, 0:9}` (**20 absent**) vs v46 928 / v47 964; ours `{5:96, 10:87}` on batch `646378f1`. Their `rank_k=0` bucket = non-rank single-name configs (9/113 theirs, 17/200 ours), not a third value. **The result is an IDENTITY, not the n:** 928/928 and 931/931 unverified decided runs are `rank_k=20`, and every run at `rank_k ∈ {0,5,10}` verified in both versions without exception; v48 lands 26/26 verified but **n=26 carries no weight alone** — coverage claim HELD OPEN until their drained re-read. **(3) [[D296]] STANDS UNRETRACTED** — they confirm their own ask-#1 `tier=0` offer contradicted their `FORGE_v42_ack` directive (tier 0 charges the TIER-3 spread derivation to every name in a mixed-tier union book → deflates every xsect result incl. megacaps) and that **`rank_k<=10` was the correct path**; retraction deferred to per-name spread charging (still opt-in behind an estimator injection). We declined `tier=0` as directive-compliance, not judgement — the property the directive should have; `tier=0` stays a one-parameter change if they retract. **(4) `momentum_252` still 0** (0/105 theirs, 0/156 ours) and **expected-not-falsifying**: at the 0.33% post-ranker rate the expected count in 105 draws is ~0.3, and F3 cannot have retrained on v48-era labels (26 decided). **Prereg `be5508b63706` explicitly NOT yet readable** — resolve only after an F3 retrain on a v48-era label; if still zero, ship the D287 selection-layer floor rather than re-scope the prereg. Crowding fix IS landing: resid **39.96% → 14.29%** theirs / 16.7% ours (~v44 level). Owned against ourselves: the prereg's leg-2 wording is stage-ambiguous (emission 3.5–5.0% met; post-ranker 16.7% not) — both recorded, not the flattering one. **(5) THEIR §4 BOUNDARY — the durable lesson:** Crucible observes ONLY post-ranker submissions; our enumeration mix / prefilters / F3 are structurally invisible to them, so any generate-vs-receive divergence can be decomposed only from our side, and their "under-weighted" call was the correct inference from the only fact they held. **Standing offer relayed:** we volunteer the funnel decomposition (enumeration → prefilter → holdout → ranked) on any emission-mix anomaly instead of letting them infer upstream state from output. **(6) Two-reason coverage field** (`breadth_impossible` vs `ad_hoc`): they open the contracts bump and send the shape for our sign-off BEFORE emitting (bump → we adopt → they emit); noted their `decision='reconfirm'` gated-export crash-loop (~45min) this morning — same class as our D245/D261 wedges. **(7) `pure_sue175` leg `96b67aa1`** (rank_k=20 MR-xsect, weight 0.4125): book `79eb6d55` KEEPS it — a generation change never de-promotes a frozen book — and its replacement verifies honestly; recorded as a **disclosure** (the promoted set contains one leg today's admission rules would not admit), explicitly not a de-promotion argument. Files: `config/preregistrations.jsonl` (2c3d5ab6cc5a → confirmed), `PROMPT_CRUCIBLE_V48_VERIFIED_ACK.md` (held), `RELAYS.md`, `STATUS.md`.

## D329 — 2026-07-22 — INCIDENT + RECOVERY (ops only; NO code / grammar / determinism / DB-schema change): D245-class asymmetric-contracts inbox wedge on the 1.35.0 `lot_floor` literal — full-fleet restart + rejected-payload REPLAY (strictly better than D245's sentinel flush)

**Symptom.** Forge produced nothing for ~7h. The daemon looked healthy (iterating, `registry_loaded_from_export`, v47 stamped) but logged `blocked: oldest in-flight batch 1a0f9dc7 is 62.0% gated (124/200); waiting for >=80%` every minute — the §7.3 limiter doing its job over a batch that could never clear. `crucible-health-check.service` was in a **failed** state since 21:00:03 PDT with the alert that named the cause: `runner_contract_stale: runner shard(s) runner-1, runner-2 loaded a crucible_contracts version != installed (1.35.0) … restart the shard(s) to adopt`.

**Root cause — the D245 trap, third recurrence (cf. D124 / D245 ingest / D247 re-read).** `crucible_contracts` 1.35.0 (`f5631d7`, Tue 13:56:13 PDT) added `lot_floor` as an additive `SizerSpec.mode` Literal. Forge restarted onto it at 18:02:19 PDT (D328/v47) — but the **Crucible fleet had been up since Mon 23:12:26**, holding the pre-1.35.0 model in memory. Inbox ingestion is deliberately strict (`extra="forbid"`, per the 1.25.0 note), so every `lot_floor` config was rejected at the door:
`sizer.mode — Input should be 'fixed_risk_pct', 'vol_target' or 'fractional_kelly' [type=literal_error, input_value='lot_floor']`
**74 configs** (all of batch `1a0f9dc7`'s shortfall) landed in `inbox/errors/` at 14:25 PDT. Inbox-REJECTED in-flight sit in NEITHER `gated_runs` NOR `failed_runs` (D245's "third failure category"), so nothing retired them: 126 gated + 74 stranded = a hard ceiling of 63% against an 80% release bar. It was the **only** open batch → total producer stall until the 5-day aged-out flush.

**Fix (1) — full-fleet restart, not just the shards the monitor named.** The health monitor only checks runner shards; writer/watchers/publishers are unalerted, so staleness was audited by comparing `ActiveEnterTimestamp` against the contracts commit. All **10** Crucible long-running units came up on 1.35.0 at 21:03:53–21:04:08 PDT (`crucible-db-writer` restarted first — the five consumers declare `Requires=`/`After=` it, and the four publishers cycled automatically via that dependency). Verified by `runner_contract_binding {"contract_version": "1.35.0"}` for both shards + `runner_status/*.json`. Restarting the runners in the same window also pre-empted the **D247 sibling trap** (accepted-then-FAILED `error_category: other` from a stale re-read path). Safe because `validate_schema_version` gates on MAJOR only — Crucible's own `CRUCIBLE_EXPECTED_CONTRACT_VERSION` is still `1.34.0` and startup tolerates the minor gap. QuantIQ's 2 Python units (`quantiq-backend` 21:11:26, `quantiq-scheduler` 21:10:50) were already post-bump and healthy (`NRestarts=0`); `quantiq-frontend` is Next.js and not a contracts consumer. **Forge itself was NOT restarted** — already on 1.35.0 since 18:02, and a restart would have cost the in-flight batch for zero gain.

**Fix (2) — REPLAY, the deviation from D245.** D245 cleared its stranded batch by retiring the rows to `gated` + `_AGED_OUT_SENTINEL_RUN_ID` (discarding the work). Here the original payloads were **still on disk** — `inbox/errors/` keeps `{config_hash}.json` alongside `{config_hash}.json.reason.txt` — and all 74 re-validated cleanly as `StrategyConfig` under 1.35.0. So they were re-submitted through the blessed atomic path (`crucible_contracts.submit_candidate`, tmp-then-rename), originals left in `errors/` as backup. This **preserves 74 real candidates, mutates no DB row, and needs no Forge restart** — the batch closes on the normal reconcile path. Prefer this whenever the payloads survive; the sentinel flush is the fallback for when they don't.

**Evidence (end-to-end).** Inbox drained 74→0 in ~40s with `errors/` **flat at 3328** (zero re-rejection — the parse fix confirmed in production). Queue went `queued=0 running=0` → `queued=72 running=2` → `queued=70 running=14`, `last_decided_age_min` 52 → **0.0**, all completions `"source": "forge"`. Forge's gated count climbed 124 → 131 → 143 → 150 → 159 → **169/200 (84.5%)**, cleared the bar, consumed feedback (`batch_id=1a0f9dc7 gated_count=197 promoted_count=0`), and submitted a fresh **200-config batch** (inbox depth 200) at ~21:35 PDT. Health check re-run: **`n_alerts: 0`** — `runner_contract_stale` cleared and the unit is out of its failed state. The 3 non-gated remainders are ordinary data-coverage failures (e.g. `chain[RIVN]: 82 consecutive sessions with no snapshot … Backfill first`), which the D240 failed-flush absorbs.

**Standing lesson (the durable half).** A contracts bump must restart **both directions and the whole fleet** — Forge submitter, Crucible ingest, Crucible re-read, and the publishers — not only the units the health monitor names. The monitor's `runner_contract_stale` check covers runner shards ONLY; writer/watchers/publishers/QuantIQ drift is invisible to it. A Crucible-side follow-up worth relaying: extend that staleness check to every long-running contracts consumer, so the next additive-literal bump alerts before it wedges the inbox for 7h.

**Files:** none — `IMPLEMENTATION_DECISIONS.md` + `STATUS.md` only. No `src/`, grammar, config, or DB-schema change; daemon byte-unaffected, reboot-safe, no Forge restart.

**↳ 2026-07-22 — the standing-lesson half RELAYED (D329 cont.; docs only, no restart).** `PROMPT_CRUCIBLE_CONTRACT_STALENESS_MONITOR_GAP.md` written + RELAYS.md row (held, operator carries). **Forensics sharpened the ask past "extend coverage."** The monitor was NOT silent: `runner_contract_stale` fired every ~15 min for **37 consecutive checks, 2026-07-21T19:00:45Z → 2026-07-22T04:00:02Z (~9h)**, spanning the entire outage. Two things made it insufficient. (1) **Its remedy was wrong for this failure.** `check_pipeline_health.py:502` reads `stale_contract_owners(read_runner_contract_statuses(data_root), CONTRACT_VERSION)`, and `runner_status/*.json` is written only by `write_runner_contract_status` at the two runner entry points — 2 of 10 long-running contracts consumers. The process that actually wedged the pipeline was `crucible-inbox-watcher` (strict `extra="forbid"` first-ingest, correctly so per their 1.25.0 note), which the check cannot see; an operator following the alert's own text ("restart the shard(s) to adopt") would have restarted the runners and **left the wedge in place**. (2) **It carries a routine false-positive mode:** the alert began 19:00:45Z but 1.35.0 was not committed until 20:56:13Z, because the monitor compares against `CONTRACT_VERSION` read from SOURCE (deliberate — editable dist metadata drifts stale) — so an in-progress `_version.py` edit reports the whole fleet stale ~2h before the version exists. A check that cries stale during every contracts editing session is one people learn to skip; that is the likely reason 37 fires went unheeded. **Asks:** (1) call `write_runner_contract_status` with a per-unit `owner_id` from all 10 consumers — the machinery already generalizes (`owner_id` free string, `stale_contract_owners` already pid-filters), so no comparison-logic change and old files keep parsing; (2) severity-split — CRIT for the first-ingest path, and name the CONSEQUENCE ("Forge submissions are being rejected") not just the remedy; (3) optional contracts-HEAD short-sha to separate working-tree churn from real post-release drift; (4) QuantIQ flagged (not asked) as a third direction — `quantiq-backend`/`quantiq-scheduler` hold an editable contracts install; frontend is Node, never affected. **Honest symmetry recorded in the relay:** Forge's own `inbox_rejections` check (D246) CRITs on `inbox/errors/` growth — **our check caught the consequence, theirs caught the cause, and neither was watched.** Under a no/deferred on ask 1 we keep the manual `ActiveEnterTimestamp`-vs-commit-time audit and make it a required step in `docs/tasks/crucible-handoff.md`. Also noted for their next pass: `CRUCIBLE_EXPECTED_CONTRACT_VERSION` is still 1.34.0 while they run 1.35.0 — harmless (MAJOR-only gate) but stale for `deploy_preflight`. NOT touched: their repo (sibling-agent boundary per `crucible-handoff.md`; their tree also had concurrent uncommitted work). Files: `PROMPT_CRUCIBLE_CONTRACT_STALENESS_MONITOR_GAP.md`, `RELAYS.md`, this entry.

**↳ 2026-07-22 — Crucible's contracts pin bumped 1.34.0 → 1.35.0 (D329 cont.; CROSS-REPO, operator-directed "let's update this"; runtime-inert, no restart).** The relay's closing housekeeping note, executed rather than carried. Their `test_expected_pin_tracks_installed_package` (`tests/unit/test_contracts_check.py:36`, asserts `CRUCIBLE_EXPECTED_CONTRACT_VERSION == CONTRACT_VERSION`) had been **RED since the 1.35.0 commit** (`assert '1.34.0' == '1.35.0'`), which NO-GOs their `deploy_preflight` — the same adopt-anyway forcing function Forge has (D267). Straight red→green: the failing test already existed, so no new test was owed. **Change:** one file, `src/optbt/core/contracts_check.py` — the constant plus a version-history comment entry in their established convention. **Scope judgment:** pin-only, matching the **1.34.0 precedent** (comment + constant, no `DESIGN.md` decision-log row); only the substantive coordinated 1.24.0 bump earned a row, and 1.35.0 changes no Crucible code path (nothing there constructs or branches on `lot_floor`). **Verified their way:** `tests/unit` **2737 passed / 4 deselected**, ruff clean, `mypy --strict` clean, all pre-commit gates green (hard-rule linters, mypy ratchet, §13.15 DuckDB-RW rule). **Runtime-inert:** the constant is read at startup and `validate_schema_version` gates on MAJOR only, so the 1.34-expected/1.35-installed gap was never a startup risk — their fleet already runs 1.35.0 code since 04:03:53Z. Commit **`5f3e8cc`**, NOT pushed (their `master` is ahead of `origin` by 2 and the other commit is their own `455ab0f` — theirs to publish). **Boundary note:** this is a deliberate, operator-directed exception to the sibling-agent rule in `docs/tasks/crucible-handoff.md`; their tree had active concurrent work (4 modified + 12 untracked files, growing during the session), so ONLY that one file was staged and pre-commit's stash/restore was verified to leave their work intact. The relay's closing section was rewritten from "worth a bump on your next pass" to a done-for-you record so it can't be carried stale. Files: `PROMPT_CRUCIBLE_CONTRACT_STALENESS_MONITOR_GAP.md`, this entry; Crucible-side `src/optbt/core/contracts_check.py`.

## D330 — 2026-07-22 — JOINT GRAMMAR-FREEZE PROGRAM (cross-repo, `~/proj/freeze`) + the measurement-basis defect in Forge's learned lane (docs/analysis only; NO code, grammar, determinism or DB change)

Operator: *"work closely with Crucible to create a grammar freeze plan … optimize heavily towards a baseline and then freeze the high quality bar … cross-repo effort of evaluating grammars, data gathering and data analysis."* Crucible had already stood up `~/proj/freeze` (shared git repo, charter v0 draft). Forge signed with amendments and contributed four artifacts. **Nothing in Forge's tree changed except docs.**

**THE FINDING (ours, and it is larger than the one Crucible owned).** Crucible's charter §2 conceded they had ranked components on the bypass-contaminated stage-one lane. The mirror defect is ours: **every Forge learned system is fitted on Crucible's stage-one SCREEN.** Measured on the 10,000-row gated export — `standard_window` n=9,399 / 1,045 positives / **6 honest (0.064%)**; `fullhist_refit` n=593 / 479 positives / **479 honest (80.8%)**; `portfolio` n=8. So **94.0% of the feed is the screen**, **98.8% of all honest labels come from the 5.9% stage-two slice**, and only **31.8%** of positive rows are honest. The D128 label is not *starving* (our coverage-gate relay's framing) — it is **diluted by a lane that structurally cannot produce it**. Downstream: F3 `P(component)` (ranker eligibility), the tail model, cohort/regime-gate yields, hypothesis + directional-bucket weights. **And we cannot scope it today:** `measurement_basis` / `fullhist_refit_of` have been on the wire since contracts 1.27.0 but appear in Forge **only as a comment** in `core/contracts_check.py`; `verdicts` has no lane column. Scoping requires a schema change, not a flag. **Consequence for the freeze instrument itself: the search-multiplicity census classifies cells `converting` vs `dead_unprotected` from that same 94%-screen ledger, so metric B (2.11%) and the entire dead-mass ledger are stage-one artifacts** — re-basing the census is a *precondition* for the freeze criterion, not a refinement (`docs/proposals/grammar-freeze-criterion.md` now carries the RE-BASED warning box + condition **(C)**).

**§7.1 discharged BEFORE answering** (their protocol ask: reproduce, don't ship). From our own `verdicts × submissions` join: v46 components 569 / unverified 564 = **99.1%** (exact); v46 `rank_k=20` **928 of 928** (exact); v47 **931 of 931** (exact); v46 coverage-PASS **15** (exact); bucket→coverage same direction (swing_long 20.9% vs swing_mid 0.01% / swing_short 1.09%, our n small). **CHECK 4 refuted their headline sentence:** they wrote "every run at `rank_k ∈ {0,5,10}` is verified", using *verified* = the gate could EVALUATE, which reads as PASSED — v46 `rank_k=10` was 1,678 evaluated / **13 passed**. Their own later correction had already reported PASS=15, so the ledgers agreed and only the wording was wrong — **in the direction that flattered their recommendation**. Crucible accepted and added charter **§2a vocabulary**: `unverified` (could not evaluate) / `failed` (evaluated, failed) / `honest` (evaluated, passed), never a two-way split. A criterion written against the wrong one sets the bar **~250× too loose**.

**METHODOLOGY FINDING (changes what the criterion measures).** Of 593 stage-two rows: **593/593 (100%) FAIL `cpcv_sharpe_p25`**, 585 fail `walk_forward_sharpe_median`, yet **479 (80.8%) are admitted as components** — admission runs on component-eligible gates; CPCV/WF are *promotion* gates. **Component admission is a POOL bar, not a quality bar**, and reconciles their aggregate exactly (16,873 decided → 12,865 components → **8 ever ≥1.5**). This superseded *our own* morning artifact (`forge_stage_two_cell_quality`, ranked by admission %) — marked superseded in place per the shared README's append-don't-overwrite rule. Both repos had published an admission-axis cell ranking this week.

**THE UNLOCK.** `GateResult.value` carries the CPCV number, and stage-two `config_hash` joins to Forge submissions at **593/593 = 100%** — so **Forge can compute per-cell stage-two CPCV distributions today, with no contract change and no Crucible work** (retired our own §4 ask for a cell-level summary from them). First scorecard (v35–v42, n≥3 cells): best `bb_pct` MR-xsect **medCPCV 0.5619 / p90 0.9218** (n=30, and never the subject of any campaign, pin or relay); worst **`residual_momentum`** trend-xsect **0.2406 / 0.4774** (n=18) — independent corroboration of Crucible's lift-0.15 read on the honest basis, retroactively justifying the v48 dial retirement *which we had shipped on stage-one reasoning, i.e. luck not method*; **`momentum_252`** mid-pack with the **second-lowest p90** (0.4122 / 0.5661, n=11), corroborating their charter §2 correction (lift **1.10**, not 4.11) — the "starved standout" story was wrong on **both** sides and our v48 decline was right for a weaker reason than the one we gave. Pooled n=574: median 0.3731, p90 0.7726, max 1.3115, **zero** clearing 1.5.

**CONVERGENCE READ (their per-version artifact, our analysis).** Across the 13 versions meeting n≥300: admitted **median CPCV declined** 0.5881 (v18) → 0.4340 (v42), best figures are the *oldest*; **p90 flat 0.6695–0.8646, no trend**; 8 of 16,873 ever cleared 1.5 (0.047%). **The ceiling has not moved in 20 grammar versions and ~481k stage-one runs**, and the best-to-worst cell range (0.24→0.56) sits **below half the promotion gate** — re-weighting emission cannot close a 3× gap. Read strictly, charter §6 criteria 1+2 are **already satisfied**; Forge deliberately does NOT claim it, because **v43–v48 have exactly ZERO stage-two rows** (v43 600, v44 800, v46 4,800, v47 4,400, v48 1,400 stage-one, all zero stage-two). Declaring exhaustion on a series ending at v42 is the basis trap.

**AMENDMENTS Forge proposed (charter signed on §0/§2/§3/§5/§6/§7):** **(§1)** the 28.5:1 all-time ratio is mostly OURS to fix — stage-one intake is a Forge parameter, and at 8,000/day vs 480/day this is a **divergence, not a backlog** (the validator loses ~7,520 runs/day; stratification only chooses which version stays unmeasured). Proposed **intake cut to ~1,500/day** (option B of three), which *lowers* our slot-scoped DSR hurdle (D310) since unmeasurable breadth is pure trial debt — operator-gated, prereg'd, and asked for independently of their answer. Endorsed their lever 3 (stratify stage-two by grammar version) unamended. **(§5/§6)** a **bounded** program, not open-ended: land the measurement fixes → accumulate n≥300 stage-two cohorts for **v47/v48 specifically** → evaluate on {v38,v39,v42,v47,v48} → if p90 still flat, **freeze and say plainly that 20 versions did not move the ceiling**; only a p90 *move* opens a real optimization phase. One probe exception: `bb_pct`. **(§4)** answered the per-version export spec in full (enumeration mix / prefilter survival / **ranked vs holdout share** — the pair that makes our selection layer auditable by them and would have short-circuited the `momentum_252` round-trip / F3 label prevalence + basis, mandatory and flagged contaminated until re-basing lands). **(§7.5, new)** distinguish resolved/passed/unverified; never compare a partial cohort to a drained one (the v47 funnel moved +1.3pp → −0.3pp between 506 and 3,548 rows). **(§3 corollary)** neither side resolves the other's prereg.

**BACKFILL ANSWERED (their ask).** Crucible found and fixed a real bug from our CHECK 5 — `fullhist_refit_of` was recorded only in `submission_metadata`, never in `runs.refit_of`, so it was NULL on every row ever exported. **We said YES to the historical backfill, and rated it higher than they did — but corrected their reason:** `config_hash` already joins at 100%, so it is not about joinability; it is the **only way to measure the stage-two SELECTION**, since stage two queues only stage-one near-misses. `unconditional cell quality = P(reach stage two) × P(quality | reached)` and we can measure neither factor without the parent link — we had been implicitly reading the second as the whole thing. Caveat flagged: 0 of 9,399 stage-one rows in our window fail *only* `regime_coverage` (modal row fails 3 non-coverage gates), which we read as our visible stage-two parents being v35–v42-era and outside the rolling window — but if their eligibility rule is broader than the docstring, that must be settled before the backfill defines "parent".

**HOLDS ACCEPTED.** No **additive** grammar bumps until the measurement lane is fixed (their §8.4); subtractive retirements stay licensed in principle but are **also** frozen in practice until the census is re-based. Prereg `be5508b63706` held **UNREADABLE, not resolved** — v48 has zero stage-two rows and resolving a quality claim on stage-one telemetry is the exact error the program exists to prevent.

**NEXT (Forge, in order):** (1) persist `measurement_basis` + `fullhist_refit_of` in `verdicts` and scope the D128 label to `fullhist_refit` — the precondition for everything else; (2) re-base the census on stage two, re-derive metric B + the dead-mass ledger, publish either way; (3) propose the intake cut to the operator as a prereg'd increment; (4) publish `forge_generation_by_version` for v47/v48. Files (Forge): `docs/proposals/grammar-freeze-criterion.md`, `STATUS.md`. Files (shared `~/proj/freeze`, commits `0da8d55`/`a039d04`): `charter/CHARTER_v0_forge_response.md`, `analysis/forge_independent_verification_2026-07-22.txt`, `analysis/forge_convergence_read_2026-07-22.txt`, `analysis/forge_stage_two_selection_bias_2026-07-22.txt`, `analysis/forge_reply_backfill_and_scorecard_2026-07-22.md`, `data/forge/*.json` (4).

**↳ 2026-07-22 (correction, same day) — the intake cut is WITHDRAWN and the real constraint is the stage-two FEED (D330 cont.).** Operator refused the intake-cut proposal: *"i dont want to reduce throughput because we are still passing it through the recency lane. i don't think this matters."* **They were right and our §1 amendment was wrong.** Crucible's scanner work-list is `ORDER BY pd.decided_at DESC` (`fullhist_refit.py:319`), **re-derived from scratch every pass** — newest first — so new work NEVER queues behind old work and there is no accumulating backlog to starve recent versions. Cutting intake would not have improved v47/v48 coverage at all. Retracted in place in the shared repo (`ff4eeb0`). **What the check found instead is larger.** `_triggers_rederive` admits a stage-one row into stage two on exactly two paths: `reject → coverage_blocked_component(gates)` or `component → NOT honest_regime_coverage(gates)`. Measured per version on our gated feed: v46 feed 508 (0 reject / 508 component), v47 509 (0/509), **v48 ZERO (0/0)**. **The reject path has contributed zero all along** — `_COMPONENT_ELIGIBLE_GATE_FAILURES` is `{wf, cpcv, min_oos_trade_count}`, and **`deflated_sharpe` fails ~100% of forge rows** (v48: 99.9%), failing the `failed <= ELIGIBLE` subset test for essentially every candidate. So EVERY version's stage-two feed came exclusively from the component path — i.e. from the `rank_k=20` unverified-coverage bypass. **v48 correctly closed that bypass, and in doing so closed our only feed into full-history validation.** Crucible's stage-two correction ("supply is not zero, stage two runs at 80.1%") is true of the *existing* v39–v42 parents but does not hold forward: nothing emitted since v48 can enter that lane, which is exactly why v43–v48 show zero stage-two rows in their per-version artifact. **The fix is Crucible-side, already ruled, and never wired:** DESIGN.md §20 `dsr-record-not-binding-forge-minimal` (2026-07-20) resolved that DSR must not bind on forge-source rows and named this precise mechanism ("absent from `_COMPONENT_ELIGIBLE_GATE_FAILURES`"); the exemption landed in `_verdict_from_gates` but NOT in `fullhist_refit.coverage_blocked_component`, whose docstring claims it "mirrors `runner._qualifies_as_component` … so the predicates cannot drift apart" — they have. Note this is NOT the fix their §20 rejected (adding DSR to `_COMPONENT_ELIGIBLE_GATE_FAILURES`, which would demote full-pass runs); honoring the source-scoped nonbinding set changes NO decision, only which rows are offered validation. **Measured counterfactual** (wf>0 / cpcv>0 bars untouched → not a gate relaxation, hard rule #3 and their §3 both intact): v46 0→**1,257**, v47 0→**1,087**, v48 0→**368**. **Consequences:** (1) no intake cut, ever, on this argument; (2) if they fix it, throughput becomes binding for the first time (~2,000/day eligible vs 480/day) and their lever 3 (stratify stage-two by grammar version) becomes load-bearing — we would then support prioritising v47/v48; (3) **until it lands, freeze condition (C) cannot be evaluated on v48 at ANY n** — the charter's n≥300 bar is unreachable from a feed rate of zero. **Method note against ourselves:** our first pass tested "fails ONLY `regime_coverage`" (0 of 9,399) and we reported that as evidence the parents were merely out-of-window — the predicate was too strict (the real rule tolerates wf/cpcv/trade-count failures) and the wrong predicate hid the finding behind a plausible non-explanation. It was only re-derived because the operator pushed back on a recommendation already written into the charter response. Second time in two days a conclusion survived because nobody re-ran the predicate under it — same shape as the `verified`/`passed` conflation, ours this time. Files (shared, `ff4eeb0`): `analysis/forge_stage_two_feed_is_zero_2026-07-22.md`, `analysis/forge_stage_two_feed_rate_2026-07-22.txt`, `charter/CHARTER_v0_forge_response.md` (§2 retracted in place). Files (Forge): `docs/proposals/grammar-freeze-criterion.md`, `STATUS.md`.

**↳ 2026-07-22 (later³) — `search_n_trials` (D310) INVESTIGATED at Crucible's request: intended semantic, ONE real defect, and the D310+v48 interaction that turned off measurement (D330 cont.; analysis only, no code change).** Crucible's `crucible_search_n_trials_looks_like_a_counter_2026-07-22.md`: our stamp is NULL through v42 and ~100,000 from v43, `deflated_sharpe` fails **100%** of forge rows from exactly that boundary (v42 61.3% fail / median DSR 0.9134 → v43 100.0% / 0.0004), and within any cell every value is distinct and forms a contiguous integer run (span = n−1, all gaps 1). **Their reading is correct in every particular, and it is INTENDED.** `stamp_search_n_trials` (`search_multiplicity.py:98`) says so: *"Stamp each candidate with its position in the slot's cumulative census … the Kth new config of a slot is that slot's trial `prior_count + K`"*; `slot_counts()` is an all-time `count(*)` over `submissions` with no time bound. Reproduced our side: v41/v42 NULL, v43 [5,154–108,464], v48 [5,338–113,660]; per (batch × slot) e.g. `646378f1` trend-xsect-swing_mid n=156 min=112,724 max=112,879 span=155 diffs={1}. Armed at v43 because the stamp is **self-gated** on their `recorded_not_binding` marker (the D306 hazard) — it waited for §20 to ship, then armed on the first v43 batch, exactly as designed. **THE ONE REAL DEFECT: per-config INDEX where the semantic wants CARDINALITY.** DSR's N is the *size of the set the selection was made from*, not *which member this is*; two configs from one batch+slot are ONE selection event yet differ by up to 155 on queue position alone. Incoherent in principle; **0.000285 sd in practice** across the observed span. Fix = stamp batch-constant at the slot's post-batch count. Correctness only, no urgency, changes no decision. **THEIR PROPOSED FIX DOES NOT WORK — the load-bearing finding.** They hypothesised (§4) that batch/slot cardinality "is what would make DSR informative again". Deflation scales `sqrt(2 ln N)`: n=1 → **0.000 sd**; n=1,950 → 3.892; n=5,000 → 4.127; n=46,000 → 4.634; n=105,000 (today) → 4.809; n=650,000 (a year out) → 5.174. **A 54× change in N moves the bar 24%** — the discontinuity is `n=1 → n>1`, NOT cumulative-vs-batch, so switching denominators trades a 100%-failing gate for a ~100%-failing gate. The real choice is *declare multiplicity honestly and accept DSR is inert for forge rows* vs *decline to declare it and let DSR be dishonestly permissive at n=1* — which their §20 already decided correctly. Unboundedness costs +0.37 sd/year on the gate (nearly harmless) but **breaks cross-version comparison** (v22–v42 vs v43+ are not comparable on any DSR-dependent measure; freeze condition (C) is CPCV/WF-based so it is unaffected, but the boundary must be recorded). **WHAT ACTUALLY BROKE, and it is ours:** D310's self-gating protected exactly ONE consumer (`_verdict_from_gates`) and did that correctly — decisions were unchanged. **It missed a second consumer**, `fullhist_refit.coverage_blocked_component`, which re-derives its own `failed <= _COMPONENT_ELIGIBLE_GATE_FAILURES` test from raw `gate_results` and discards only `regime_coverage`. Chain: D310 stamps ~100k at v43 → `deflated_sharpe` fails 100% → the stage-two **reject path dies** (their ledger: 5,961 rows at v38 → **0 from v43**) → the only remaining feed is the component path = the `rank_k=20` unverified bypass → **v48 closes the bypass** → v48 stage-two feed = **ZERO**. Two individually-correct changes three weeks apart that jointly turned off measurement; neither review asked what *else* read that gate. **CORRECTION WE OWE THEM (and it is worse for us than the original claim):** our `forge_stage_two_feed_is_zero` §2 said the reject path *"has been contributing zero all along"* — **false**. It fed 5,961 rows at v38 and **we broke it at v43**. Our window held only v35/v46/v47/v48, and **our own table showed v35 feeding 6 of 33 (18.2%) via reject, which we dismissed as small-n noise.** So this is a **dated regression with a known cause**, not a path that never worked — which makes the fix MORE urgent and means it should NOT wait on accumulation (nothing accumulates for v43+ until it lands). Corrected in place in both the analysis doc and shared Decision 001. **PROPOSED:** (1) **keep the stamp** — reverting to unset would restore the feed tomorrow but buys a working pipeline with a dishonest number and re-incurs a debt we deliberately paid; costed for the operator, NOT recommended. (2) Forge fixes index→batch-constant. (3) **Crucible honours the §20 non-binding set in `coverage_blocked_component`** — the actual fix, same ruling they already made for the verdict predicate; restores the reject path for v49+. (4) Open, theirs: should DSR bind at the stage-two trigger at all (our read: no, for §20's own reason). (5) The stage-two child's `n_trials=1` asymmetry they flagged is, we think, **correct and should stay** — the child re-evaluates one already-chosen config on a different window, so there is no multiplicity to charge and charging the parent's N again would double-count the same search. Files (shared, `6d6b9bd`): `analysis/forge_search_n_trials_investigation_2026-07-22.md`, plus in-place corrections to `analysis/forge_stage_two_feed_is_zero_2026-07-22.md` and `decisions/D001_wait_for_accumulation_2026-07-22.md`.

**↳ 2026-07-22 (later⁴) — `search_n_trials` stamp CORRECTED to batch-constant cardinality (D330 cont.; operator "Let's make the change", Crucible asked to make their half).** Fixes the one real defect found in the D310 investigation: `stamp_search_n_trials` assigned each config its **index** in the slot's cumulative census (`prior_count + K`), so a config's declared multiplicity depended on its **queue position within the batch**. DSR's `n_trials` is the **cardinality of the set the selection was drawn from**, not the index of a member within it — and every config a batch emits for one slot is a **single selection event**, so all must carry the same value. **Change:** two-pass — count each slot's contribution to the batch, then stamp every candidate in that slot with `prior_count + n_in_batch` (the slot's post-batch cumulative count). Preserves the `or 1` floor (a fresh slot contributing one config still stamps 1) and the all-time cumulative basis. **TDD:** 3 new failing tests first (`test_stamps_batch_constant_slot_cardinality`, `test_same_slot_same_batch_configs_carry_identical_n`, `test_ordering_does_not_change_any_stamp` — the last asserts forward and reversed candidate order produce identical stamps, the property the index violated); confirmed red for the expected reason (`[41,42,43,44,45,46] != [46]*6`), then green. **Behavioural proof on live slot counts** (replaying batch `646378f1`, 200 configs): trend-xsect-swing_mid 156 configs OLD `114,290..114,445` → NEW `114,445` constant; MR-xsect-swing_mid 25 OLD `105,345..105,369` → NEW `105,369`; ve-named-swing_short 15 → `56,809`; all six slots collapse to one value each. **Numerically tiny by design** — deflation goes as `sqrt(2 ln N)`, so the observed within-batch span moved the bar **0.000285 sd**; this is a correctness fix (the field now holds the quantity its name claims), NOT a remedy for the saturation. **Full suite 2046 passed / 1 skipped; ruff + mypy --strict clean.** Determinism untouched: `search_n_trials` is hash-excluded (contracts 1.19.0), stamping happens post-ranking at submit time, so no enumeration path, no sampler golden, and no §13.4 idempotency behaviour changes (pinned by `tests/invariants/test_search_n_trials_hash_excluded.py`). NOT a grammar change → no version bump. **DELIBERATELY NOT CHANGED (joint decision, recorded in the module docstring):** whether cumulative-all-time is the right denominator at all. Forge takes no cross-batch argmax — it ships each batch's ranked top-N as a stream — so the across-time multiplicity arguably belongs to Crucible's `selection_n_trials` (charged at assembly, where a real argmax happens), and charging both double-counts one search; changing it would contradict the agreed D304/Q1 semantic, and it is operationally inert while DSR is record-not-binding for forge rows. **The saturation itself is NOT fixable from this side:** the deflated bar at N=105,000 is **1.974 annualized Sharpe against a population maximum of 1.964** (median 0.654, p90 1.156, p99 1.549, n=9,264, T=1,254) — arithmetically unpassable — and even at N=200 the bar is 1.240, excluding 93.4% of what we produce. The discontinuity is `N=1 → N>1` (bar 0.000 → 1.240, straight through p90), so no denominator has an operating range for this population. **The durable fix is Crucible's** and was relayed: ONE `blocking_failures(gate_results, source)` called by every consumer (verdict, component predicate, fullhist trigger, margin readers) instead of the rule being re-implemented per call site — the drift that let §20's exemption reach `_verdict_from_gates` but not `fullhist_refit.coverage_blocked_component`, killing the stage-two reject path at v43. Files: `src/forge/submission/search_multiplicity.py`, `tests/unit/test_submission/test_search_multiplicity.py`. Shared: `analysis/forge_dsr_saturation_mechanism_and_durable_fix_2026-07-22.md` (`c9eb307`). **DEPLOY VERIFIED 2026-07-22T15:52:49 PDT** — stop → full **uncontended** suite (2046 passed / 1 skipped, 203s) → restart. Service `active/running`, **NRestarts=0**, `grammar_version=v48`, `registry_loaded_from_export`, no traceback. First post-deploy batch `8de7a790` (200/200 submitted, 0 failed): journal `search_n_trials: stamped 200 configs (max slot n_trials=114353)` and **every slot is batch-constant on the submitted rows** — MR|swing_mid|xsect 119 configs / **1 distinct value** (105463), trend|swing_mid|xsect 64 / 1 (114353), ve|swing_short|named 14 / 1 (56808), ve|swing_mid|named 2 / 1 (5377), MR|swing_short|xsect 1 / 1 (7638). Zero slots with a spread; the pre-D330 daemon would have produced 119-, 64- and 14-wide index ranges in the same batch.

**↳ 2026-07-22 (later⁵) — DSR thread CLOSED with Crucible: the charge is relocated, and the load-bearing claim is now a TEST (D330 cont.; test-only, no production change, no deploy).** Five relays over the afternoon converged. **Where it landed:** (1) **ranker shift +0.220 — NOT a DSR charge.** Classic multiplicity charges selection *on the reported statistic*; our ranker orders by `tail_norm` over **structural** features fitted on OTHER configs' verdicts, so under the null it is independent of this config's noise draw (`E[R | top-k by S] = E[R]`). Crucible conceded their 0.569 order statistic (it assumed correlation 1.0 between score and realised Sharpe; ours has train R² 0.201 and negative recent OOS R², capturing ~43%). (2) **ranker regression −0.04 — period overfit, not luck**, and it needs no charge because their full-history stage-two evaluation already reads the post-decay number; it is the gap between a screening measurement they discard and a validation measurement they keep. It is a MODEL-QUALITY metric for us to fix. (3) **prefilter inflation — UNMEASURED, and this is where the real DSR charge lives.** `permutation_test` selects on the config's OWN in-sample notional return (textbook multiple comparisons, our dominant rejector ~2,393 of ~3,000/batch), and its rejects are never submitted → survivorship → unmeasurable from existing data. Agreed instrument: a **prefilter-holdout campaign**, ~5 of 200 slots/batch, marked in `submission_metadata`, time-boxed 2–3 weeks, NOT excluded from admission. Both sides record the current state as **"a known, accepted, temporary under-deflation with an instrument in flight"**, never "the charge is zero." **VERIFICATIONS both ways:** their correction 3 (the shift conflates skill and luck) reproduced from our export alone — their n=280 / −0.0402 / 66.4% vs our **n=293 / −0.0394 / 65.9%**; our correction 1 (pool-relative, 0.897× → 0.220 not 0.245) verified by them to four decimals; our correction 2 (lower bound) accepted as the more consequential. **WE CAUGHT THEIR §2 OVERCLAIM — the only error in the thread found by reading CODE rather than reproducing a NUMBER.** They argued the ranker's independence is *architectural* ("Forge does not run backtests, so the draw does not exist"). **False:** `permutation_test` puts `real_notional`/`p_value` in `FilterResult.details`, `PreFilterReport.filter_results` carries them, and the ranker receives the report — the data is ONE ATTRIBUTE ACCESS from the feature builder. What actually holds the line is the **signature** `extract_features(config, registry)`, which never takes the report (every call site passes `.config` only, including `shadow.py` which holds the full report). A design choice, reversible, and adding `permutation_p_value` as a feature is a natural thing for someone to try — at which point the independence collapses, +0.220 becomes a genuine multiplicity charge, and BOTH repos' records would still say it was impossible. **So it is now enforced:** `tests/invariants/test_ranker_features_are_performance_blind.py` — 4 tests (signature is exactly `(config, registry)`; no `PreFilterReport` in annotations; `filter_results` still carries prefilter detail, pinning the threat model; no *shipped* model artifact carries a performance-derived feature name, checked against the live file so it catches features that bypass `extract_features`). Green; negative control confirms a breached signature fails it. Same standard we asked of Crucible for `blocking_failures(gate_results, source)` — a property two documents rely on belongs in code, not prose. **Transferable lesson recorded:** the reproduce-the-number discipline has a blind spot for claims about *mechanism* — it caught every wrong quantity in the thread and would never have caught "the architecture prevents this", because that claim has no number attached. **An architectural claim needs a test the way a numeric claim needs a reproduction.** Also fixed a precision error of ours: the live artifact targets **`target_wf_p25`** (worst-quartile walk-forward Sharpe), not `cpcv_sharpe_p25` (the code default) — Sharpe-targeted conclusion unchanged. Files: `tests/invariants/test_ranker_features_are_performance_blind.py`. Shared (`f5d9b77` + this reply): `relays/FORGE_correction3_verified_and_a_structural_refinement_2026-07-22.md`, `relays/FORGE_your_S2_is_too_strong_and_here_is_the_enforceable_version_2026-07-22.md`, `analysis/forge_verify_correction3_skill_vs_luck_2026-07-22.txt`, `data/forge/forge_selection_inflation_2026-07-22.json`. **BUILD PENDING OPERATOR GO:** the prefilter-holdout campaign (submission-policy change → deploy) and the `selection_rank`/`selection_pool_size`/sample-flag emission (gated on Crucible's contract bump).

**↳ 2026-07-22 (later⁶) — URGENT RESOLVED: it was a DEPLOY gap, not a code gap; first v48 stage-two components exist; Forge adds a deploy-staleness check (D330 cont.; healthcheck-only).** Our urgent relay diagnosed the v48 315/315 rejection as the `source == "forge"` exemption scope missing the `fullhist_refit` child. **Crucible's reply: the code was already right.** `c35c10f` (§20 `dsr-nonbinding-by-deflation-basis`, landed 15:49 PDT) keys the exemption on `search_n_trials >= (selection_n_trials or 1)` — **no `source` test at all**, which is precisely the deflation-basis scoping we asked for, reached independently from the same asymmetry and written before our note arrived. **It produced zero effect because both runner shards had been up since 2026-07-21 21:04 PDT — 19 hours before the fix committed.** A long-running daemon holds its modules in memory. Their evidence: of v48 children decided AFTER the fix commit, **84/84 still failed `deflated_sharpe`, 0 admitted**. Our 315/315 was a correct measurement of a process running code that predated the fix by 19h — *the most expensive kind of correct measurement, because it sends the other side hunting a bug that does not exist.* **After their shard restart (16:37 PDT) it works end-to-end: VERIFIED our side — 346 v48 stage-two rows, `{component: 11, reject: 335}`, first v48 components in existence after 315 consecutive rejects, with `deflated_sharpe` still computed and still failing on the row but NON-BINDING** (recorded-not-binding exactly as §20 says). **THIS IS A FOURTH PATTERN, NOT A THIRD INSTANCE — `shipped ≠ deployed`.** The first three were "a rule applied at the consumer someone was looking at"; this one is code that was correct, committed, unit-tested, invariant-tested and in the Decision Log, and inert. **Neither repo's new enforcement test can catch it** — ours pins `extract_features`'s signature, theirs pins the single `blocking_failures` derivation; both are true of the REPOSITORY and say nothing about the running PROCESS. Extended rule, now three-deep: **a numeric claim needs a reproduction, an architectural claim needs a test, and a claim about deployed behaviour needs a check on the running process.** **Forge is MORE exposed than Crucible here** (this tree IS production per D104 — every commit opens a window where tree and process disagree), so we built the mirror: **`check_deployed_code_staleness`** in `healthcheck_cmd.py` — WARN when `forge.service`'s `ActiveEnterTimestamp` predates the newest commit touching `src/`, with `_service_started_at()` / `_last_src_commit_at()` gather glue, wired as the second entry in `cmd_healthcheck`. TDD: 3 tests written first (OK / WARN-with-the-real-19h-scenario / missing-timestamp), confirmed red on ImportError, then green. **Live: `[ OK ] deploy_staleness: running daemon started after the last src commit`.** Scope is deliberately imprecise (newest `src/` commit, not a computed import graph — `forge.cli.main` imports 57 forge modules including `healthcheck_cmd` itself, verified, so nearly all of `src/` really is in the process); it will over-warn on a behaviourally-irrelevant commit, accepted and documented because a check that occasionally says "restart" is a cheaper failure than one that stays silent while 84 decisions run stale code. **Their §6 re-derivation of the v48 read, and why our caution was right:** their full ledger reproduces ours (**v48 n=314 median 0.3129 / p90 0.8237 / max 1.5231 / 1 ≥1.5** vs our 315 / 0.3098 / **0.8237** / **1.5231** / 1 — p90 and max match exactly). **But the comparison crosses a FEED-BASIS boundary:** v48's cohort is drawn from the *unfiltered* feed (every eligible parent), while v39's could only ever contain DSR-**passing** parents, because before the feed fix nothing else could reach stage two. **v39 got the cream; v48 gets the whole distribution** — so the lower centre is NOT evidence about the grammar, and the more interesting reading is that v48's p90/max hold up against v38–v42 *despite* a materially broader population, producing the only ≥1.5 row. **And it cannot be repaired by restriction** (v48 has no DSR-passing parents to restrict to — the stamp takes them all below the bar); it becomes readable only when the backlog generates v39-era children under the unfiltered feed, which newest-first ordering makes slow. **Decision 001's n≥300 trigger has fired on paper, but the v48 read is HELD** until the cohort re-accumulates under the deployed exemption — the current 315 carry valid CPCV and a spurious admission column. Files: `src/forge/cli/healthcheck_cmd.py`, `tests/unit/test_cli/test_healthcheck.py`.

## D331 — 2026-07-22 — LANE PROVENANCE on `verdicts` (D330 item 1, Part A): persist `measurement_basis` + `fullhist_refit_of`; Part B (label scoping) MEASURED and held for operator

**Part A — SHIPPED (schema + writer + tests; NOT yet deployed).** Crucible's two-stage design means the LANE decides whether a verdict row can carry an honest label at all: `standard_window` is a cheap 5yr SCREEN that structurally cannot produce an honest-coverage component; `fullhist_refit` is the floor-anchored validator and the only path into the component pool. Both fields have been on the wire since contracts 1.27.0 and existed in Forge **only as a comment** in `core/contracts_check.py` — never persisted, never read. Added as idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (the D316 `source_export`/`contracts_version` precedent), wired through `record_verdicts` from `gr.run.measurement_basis` / `gr.run.fullhist_refit_of`, NULL on legacy rows and on any producer that omits them. TDD: 3 tests written first (schema column set, lane recorded from the run, nullable for legacy/stage-one), confirmed red (`BinderException`), then green. **Migration verified on a real 409,153-row copy of the live DB (copied to REAL DISK, not tmpfs — this morning's lesson): both columns added, row count delta 0, 1.12s, all 409,153 legacy rows NULL as expected.** Scoped suites green: `test_feedback` + `test_ranking` + `invariants` = **715 passed**; ruff + mypy --strict clean.

**Part B — the label scoping — MEASURED, DESIGN CHANGED, and held for the operator.** The proposal was "scope the D128 label to `measurement_basis = 'fullhist_refit'`". Building Part A exposed why that specific form is wrong: **396,123 of the training frame's rows are legacy and will carry NULL lane forever** (`record_verdicts` is INSERT-OR-IGNORE, so it never back-updates), which would leave the scoped frame empty for months. **A better formulation is available and works on legacy rows today: make honest coverage the POPULATION FILTER rather than a component of the LABEL.** Today `label = (decision ∈ {component, promote}) AND honest_regime_coverage_row(...)`, which means a stage-one row is labelled NEGATIVE regardless of quality because its lane cannot produce an honest coverage row — 91.0% (360,458 of 396,132) of the frame is structurally unable to be positive, and **26 of 363 configs measured appear in BOTH lanes with OPPOSITE labels** (same `config_hash`, 0 at stage one, 1 at stage two). Reframed: train only on honestly-evaluated rows, label = decision positive. **Measured: 35,674 rows (9.0% of the frame) carrying the SAME 19,759 positives — prevalence 4.988% → 55.4%, an 11× lift, with 91% of the structurally-mislabelled mass removed.** Honest coverage is computable from `gate_results` on every legacy row, so this needs no lane column and no accumulation wait; the D331 lane columns become provenance/verification rather than a dependency. **Estimand shift, stated rather than buried:** F3 would estimate `P(component | honestly evaluated)` instead of `P(component | emitted)` — arguably the better question for deciding what to emit (it excludes our own prefilter/lane plumbing from the target), but it IS a different quantity and the change touches the training population of EVERY learned model (F3, tail/robustness, cohort + regime-gate yields, hypothesis and directional-bucket weights). **Operator-gated per CLAUDE.md (learned-weight change → `docs/tasks/feedback-change.md`); NOT built.** Files: `src/forge/persistence/schemas.py`, `src/forge/persistence/verdicts.py`, `tests/unit/test_feedback/test_verdicts.py`. **DEPLOYED + VERIFIED 2026-07-22T19:22:46 PDT** (operator "deploy"): stop → full uncontended suite **2055 passed / 1 skipped** → restart. `active/running`, NRestarts=0, `grammar_version=v48`, `registry_loaded_from_export`, no traceback. **Migration applied live on the production DB** — both columns present on 410,079 rows, and the lane populates from the first reconcile pass (**109 `standard_window` / 44 `fullhist_refit`**), confirming the writer path end-to-end. **Crucible relay handled in the same window** (`CRUCIBLE_basis_boundaries_and_a_breaking_schema_bump`): their schema 2.0 is a freeze-repo ANALYSIS artifact, not a `crucible_contracts` bump, so it does NOT touch the daemon or the inbox (checked before completing the restart — the D245/D261 asymmetric-contracts class was the thing to rule out). **Their ask 2 CONFIRMED from our emitting side:** v41 0/400 stamped, v42 0/1,600, **v43 600/600 (100%) median 99,868.5** — matching their 99,868; the break is total with no transition. **Ask 1:** no committed Forge code reads the 1.0 keys (only ad-hoc session analyses), so 2.0 costs us nothing — but their catch matters, the cohort-wide `admission_pct` reads 9.65% naive vs **54.55%** verdict-determinate (5.7×) and would have hit our next convergence read. **Ask 3 ACCEPTED, against ourselves:** no v48-vs-v39 comparison on admission or admitted-CPCV — and **our earlier read made exactly that comparison** (v48 median 0.3098 vs v39 0.3939, flagged only as small-sample caution). Their mechanism supersedes it: the feed confound runs in OPPOSITE directions for the two figures — a broader population lowers admission while making the admitted set a more selective slice, raising its median — so a v48-beats-everything table is constructible from honest data. p90/max remain readable, which is where v48's signal is. **Ask 4 — our four boundaries named:** **(A)** the stamp's SEMANTICS changed today at **2026-07-22 22:52:49Z** (D330: index → batch-constant cardinality), so any per-config DSR quantity now has TWO boundaries, not one — and it sits between their feed basis (19:44:23Z) and verdict basis (23:37:30Z), i.e. **three boundaries in under four hours across both repos on the day we are trying to build a comparable version series**; **(B)** the selection regime changed twice and is INVISIBLE to them (they see post-ranker output only) — 2026-07-06 D252 gate-then-tail flip (P(component) became a hard eligibility gate, tail took over ordering) and 2026-07-07 D256 5% exploration holdout; **(C)** 2026-07-16 D287 experiment-cell floor; **(D)** 2026-07-19 D290 ve ghost-label cut. To be added to charter §2b in their format. Relay: `freeze/relays/FORGE_v43_confirmed_and_our_boundaries_named_2026-07-22.md` (`6af7029`).

**↳ 2026-07-22 (later) — D331 item 2: the CENSUS RE-BASED onto honest evidence; metric B is a new series.** The census classified cells from a verdicts ledger that is ~94% Crucible **stage-one** rows — a screen that structurally cannot produce an honest-coverage component — so `converting` was being awarded on unverified-admission artifacts and **freeze metric B, the number the whole freeze criterion turns on, was a stage-one artifact**. **Measured the re-base BEFORE changing anything** (the risk was mass-reclassifying live cells as dead): on the live snapshot only **2 of 84 converting cells** flip out, and **both had ZERO honest evaluations — 100% of flips would have been misclassified as dead**. Small today; the case it protects is a NEW cell, which by construction has flow and no honest evidence, and pruning those is the v17 cold-start mistake in a new costume. **Change:** `converting` now requires `honest_comp_recent > 0` (or an all-time promote); new class **`_UNEVALUATED`** for `live_recent > 0 AND honest_decided_recent == 0` — never a prune target, excluded from metric B; `add_verdict` gains `honest`; the verdict query fetches `gate_results` and computes `_honest_coverage()`, a byte-equivalent of `honest_regime_coverage_row` applied to the stored JSON. **Why this needed no waiting on D331 Part A:** `measurement_basis` only populates going forward, but honest coverage is recoverable from the gate payload we have always stored — so the re-base works on all 410k legacy rows today. TDD: new `tests/unit/test_scripts/test_census_classification.py`, 6 tests written first (stage-one positives alone do NOT convert; one honest component does; flow-without-honest-evaluation is `unevaluated` not dead; honestly-evaluated-and-failed IS dead; protection still outranks; thin stays thin), red on ImportError → green. 26 tests in scope pass; ruff + mypy clean. **RESULT on the live snapshot: converting 41.3% → 38.1%, dead_unprotected 3.1% → 1.2%, new `unevaluated` 11.0%, and freeze metric B 2.11% → 0.85%.** **STATED PLAINLY: B falling is NOT progress — it is a definitional change**, the drop being unevaluated mass that is no longer counted as dead. The operator threshold must be re-set against the new baseline and the 2.80%/2.11% series belongs to the old basis (**a Forge-side basis boundary in exactly the sense charter §2b encodes — added to our boundary list**). **The more actionable new number is the 11.0%**: that much of all-time multiplicity sits in cells that have never had a fair hearing, which says where measurement is missing rather than where waste is. Files: `scripts/search_multiplicity_census.py`, `tests/unit/test_scripts/test_census_classification.py`, `docs/proposals/grammar-freeze-criterion.md`. Daemon-inert (the census is a script + daily timer) → no deploy needed.

**↳ 2026-07-22 (later²) — D331 item 4: `forge_generation_by_version` PUBLISHED (charter §4); item 3 BLOCKED on Crucible's contract bump.** **Item 3 (prefilter-holdout campaign) cannot ship:** Crucible's condition #1 was an explicit marker on the sampled configs — *"Without it they enter our admission statistics, the funnel, and the component-quality ledger as ordinary forge rows, and we would be silently contaminating the very measurements this programme depends on."* Checked: contracts is **1.35.0** and `selection_rank` / `selection_pool_size` / the sample flag are **absent**; `submit_candidate(config, inbox_path)` takes no metadata, and `submission_metadata` is constructed Crucible-side. `StrategyConfig.source` IS free-form (`str | None`) so a marker could technically be smuggled there — **deliberately not done**: `source` drives lane classification on their side, and putting an unexpected value in a field the consumer switches on is the D261 `literal_error` hazard in reverse. **Item 3 waits for their bump.** **Item 4 SHIPPED:** `scripts/export_generation_by_version.py` emits the charter §4 payload per grammar version — enumeration mix (hypothesis-level; per-cell counts are not persisted, stated in the artifact), prefilter survival + `rejections_by_reason`, **ranked vs holdout share per cell**, `selection_loss`, and the `f3_label` block with its basis **stamped MIXED** until the re-scoping ships (we publish the contaminated flag rather than a clean-looking number). Published to `freeze/data/forge/forge_generation_by_version_2026-07-22.json` (v47, v48). **FINDING 1 — what the v48 coverage fix bought the LABEL: 176×.** v47 = 4,255 verdicts / 511 positives / **2 honest** (0.047%); v48 = 4,284 / 355 / **355 honest** (**8.287%**). Under v48 **every positive is honest** — fewer positives, a vastly more informative label. This is the cleanest single measure of what `rank_k<=10` bought, and it lands on the label our whole learned lane trains on. **FINDING 2 — our ranker's largest bets are INVERTED against Crucible's quality measure.** v47 per-cell selection effect (ranked − holdout share) against stage-two medCPCV: **`bb_pct` (BEST, 0.5619) → −7.80pp** and **`residual_momentum` (WORST, 0.2406) → +7.68pp**, with the middle of the table mildly positive throughout — so it is specifically the extremes that are backwards. Consistent with the tail model (`target_wf_p25`, train R² 0.201, recent OOS R² negative): a model with no out-of-sample skill will not order the extremes correctly. **Second independent line of evidence pointing at the RANKER rather than the grammar** (the first was momentum_252: enumeration 28% → holdout 8.43% → ranked 0.33%). **Three caveats, all against the finding, and the first was a defect in our own artifact that we fixed before publishing:** (1) the holdout is drawn from survivors the ranker did NOT pick, so the residual pool is **depleted** of cells the ranker likes and enriched in ones it avoids — |delta| is inflated in both directions and the inflation concentrates in exactly the largest deltas; written into the artifact's own note, not just the analysis. **Read the sign, not the magnitude.** (2) the medCPCV column is a different version era (v35–v42) than the v47 deltas; (3) small holdout n (5%/batch). No action proposed on it yet — recorded before the freeze evidence base closes. Files: `scripts/export_generation_by_version.py`; shared `e01ae48`.

**↳ 2026-07-23 — D331 Part B BUILT behind an A/B flag (`FORGE_HONEST_LABEL_SCOPE`, default OFF = byte-identical). Prereg `812d65bfbe86`. NOT FLIPPED.** Built under `docs/tasks/feedback-change.md` (learned-weight ritual), whose requirement 5 is exactly this: *risky arm → A/B flag, default OFF, flipped later by editing the service unit, never by a code default* (D108 pattern). **The defect:** Forge's D128 label is `positive AND honest_coverage`, so a Crucible **stage-one screen** row — a lane that structurally cannot produce an honest-coverage component — is labelled **NEGATIVE regardless of quality**. Measured on the live frame: **90.3% of rows (329,225 of 364,545) cannot carry a positive**, and the same `config_hash` appears in BOTH lanes with **opposite labels** (26 of 363 paired configs). That is mislabelled mass, and a supervised model cannot learn from it. **The fix is a POPULATION filter, not a label change:** `build_dataset(honest_scope=True)` drops rows failing `honest_regime_coverage_row`; on the surviving population `label_for` reduces to "decision is positive" *by identity*, so the label predicate is untouched and cannot drift from `forge.ranking.evaluation` (the shared-source-of-truth property is preserved rather than worked around). An honestly-evaluated **reject is retained** — real negative evidence, not filtered out. **Design changed from the original proposal after measurement:** scoping on `measurement_basis = 'fullhist_refit'` (D331 Part A's new column) would have left the frame empty for months, because `record_verdicts` is INSERT-OR-IGNORE and 396,123 legacy rows carry NULL lane forever. Honest coverage is recoverable from the stored gate payload on every legacy row, so the scoping needs no lane column and no waiting — Part A's columns become provenance rather than a dependency. **EMISSION PROOF (ritual step) on the live DB:** flag OFF 364,545 rows / 19,641 positives / **5.388%** prevalence; flag ON **35,320 rows / 19,641 positives / 55.609%** — **positives PRESERVED exactly**, 90.3% of rows dropped, **10.3× prevalence lift**. Feature columns 119 → 116: three one-hots fire ONLY on dropped rows, i.e. a few grammar cells appear exclusively in the population that cannot be honestly evaluated — worth watching, since those cells are invisible to a scoped model. **ESTIMAND SHIFT, on the record:** F3 then estimates `P(component | honestly evaluated)` rather than `P(component | emitted)`. We believe that is the better question — it excludes our own prefilter and lane plumbing from the target — but it IS a different quantity, and it changes the training population of every learned consumer of `build_dataset`. **Prereg `812d65bfbe86`** registered BEFORE any flip (cohort_cut 2026-07-23T05:10:54Z, flag OFF at registration so the cut precedes any effect): predicts that post-flip the ranked-vs-holdout `delta_pp` for the best measurable cell (`bb_pct`, medCPCV 0.5619) rises from **−7.80pp** toward 0-or-positive and the worst (`residual_momentum`, 0.2406) falls from **+7.68pp**, with F3 shadow AUC not regressing; **action if refuted: the ranker's problem is not the label and the tail model itself needs replacing** (train R² 0.201, recent OOS R² negative). TDD: 3 tests written first (flag-OFF byte-identical incl. the default path; ON drops the lane that cannot carry a positive; ON KEEPS honest rejects as negatives), red → green. **Full suite 2064 passed / 1 skipped**; ruff + mypy --strict clean. **FLIPPED + DEPLOYED 2026-07-22T23:26:43 PDT** (operator "let's flip the flag and deploy"). **The flag went in `forge-ranker-eval.service`, NOT `forge.service` — and that distinction was the whole risk.** `build_dataset` is called only by the `ranker-model` CLI, which the DAILY TIMER unit runs; the daemon imports the module but never calls it. Our own prior note said "flipped later by editing the service unit" (singular) and would have edited the wrong one — a silent no-op, i.e. the exact `shipped != deployed` class D330 built a check for. Caught by checking which unit runs the trainer instead of assuming. The trainer unit had NO `Environment=` lines at all; added with an inline comment explaining why it is not in the daemon unit. `daemon-reload` + `systemctl show -p Environment` confirms systemd parsed it (`FORGE_HONEST_LABEL_SCOPE=on`). **End-to-end verified through the real CLI**, not just the unit file: flag absent → `365,048 rows (19,771 positive), 119 feature columns`; flag on → `35,483 rows (19,771 positive), 116 feature columns`. Same positives, 90.3% fewer rows. **Deploy:** stop → full uncontended suite **2064 passed / 1 skipped** → restart; `active/running`, NRestarts=0, `grammar_version=v48`, no traceback; `[ OK ] deploy_staleness`. The daemon restart is hygiene only — the flag takes effect at the next 05:00 timer fire, which is the first de-scoped F3/tail fit. Files: `src/forge/ranking/dataset.py`, `src/forge/cli/ranker_model_cmd.py`, `tests/unit/test_ranking/test_dataset.py`, `config/preregistrations.jsonl`, `~/.config/systemd/user/forge-ranker-eval.service` (backup at `~/.cache/forge-ranker-eval.service.bak`).

## D332 — 2026-07-23 — v48 → v49 DEPLOYED: an ATTRIBUTION-ONLY grammar bump marking the honest-label boundary (`rules:` byte-identical), + the first honest-scoped retrain and an early prereg read AGAINST us

**Operator: "flip the label now and flip to v49".** The label flag was already set (D331 Part B); "flip now" = force the retrain rather than wait for the 05:00 timer (4h52m out). Ran `systemctl --user start forge-ranker-eval.service` directly.

**Why v49 exists — a boundary WE created.** `FORGE_HONEST_LABEL_SCOPE=on` went live 2026-07-22 **23:26 PDT**; Crucible's v48 stage-two baseline window (their D003 freeze anchor, top-decile CPCV **0.8258**) closed **22:09 PDT**. **The baseline predates the flip by 77 minutes and is intact** — but every batch ranked after the retrain comes from a differently-trained F3 (35,483 rows / 55.609% prevalence vs 365,048 / 5.388%), so continuing to stamp that output `v48` would have silently drifted the baseline it is meant to be compared against. v49 gives the post-flip cohort its own version key. **Class 2 per `docs/tasks/grammar-change.md`** (version bump for cohort attribution, D098/v5 precedent): `rules:` text **byte-identical** to v48 (verified by diff), no Python emission change, and **`config_hash` is version-independent** (verified) so §13.4 idempotency is untouched and nothing re-enters Crucible's queue. **STATED LOUDLY IN THE GRAMMAR HEADER AND THE RELAY: v49-vs-v48 tests the RANKER change, NOT the grammar. The first grammar comparator is v50.** This matters because D003 reduces the freeze question to "does top-decile CPCV move against 0.8258" — v49 answers that about the wrong subject, and a null must not be read as "the grammar is exhausted."

**First honest-scoped retrain (07:05Z):** F3 `rows=35,591 (19,849 positive)`, features 83, **train AUC 0.747**. Tail (`target_wf_p25`) `rows=31,974`, features 75, **train R² 0.1992 → 0.3964**.

**The tail model's `oos_r2` printed −117.4, and it is a FALSE ALARM — but the correct reading is still bad news for the prereg.** `robustness_oos_r2` uses a TEMPORAL 80/20 holdout; on the scoped frame the target mean shifts **−0.8430 (train) → −0.2813 (test)**, and a mean shift destroys R² while leaving *ranking* untouched. **Ranking is what gate-tail actually consumes.** Recomputed on the metric that matches the model's job, same holdout: **OOS rank IC 0.2778 scoped vs 0.2842 full.** (The feed-basis boundary is NOT the driver — only 1,233 of 6,396 test rows sit past it.) So the re-scoping is **neutral-to-slightly-negative on ordering, and both sit below the 0.30 §8.6 bar.** By prereg `812d65bfbe86`'s **own stated falsifier**, that points at the tail model itself rather than its training label: the label was not what made the ranker place its largest positive bet on the worst measurable cell (`residual_momentum`, +7.68pp, medCPCV 0.2406) and its largest negative on the best (`bb_pct`, −7.80pp, 0.5619). **Reported to Crucible before the prereg's cohort exists, because it argues against the change we just shipped.**

**PROCESS ERROR, owned:** the uncontended suite came back **1 failed / 2,063 passed** and **we restarted before reading it** — inverting the ritual's stop → suite → commit → restart order. The failure was `tests/integration/test_v1_grammar.py::test_v1_grammar_loads` asserting `grammar_version == "v48"`, a pinned-version companion edit every bump needs, so there was no production defect (the daemon loaded v49 cleanly, `grammar_versions: recorded manual_bump row for v49`, NRestarts=0, no traceback). Fixed, re-run green. The lesson is the ordering, not the pin: reading the suite AFTER the restart makes the suite decorative.

**Also answered for Crucible:** their §5 ask — our submission order is **not** quality-biased (drained v48 slice 95.70% ranked vs 95.00% submitted; expected holdout 55.8 of 1,115, observed 48 ≈ **1.06 sd**, not significant), so their `search_n_trials` skew is a **time** artifact (drain lag against a growing frontier), not a selection one. And a **mild, data-backed disagreement with D003**: we checked the sharpest version of "the backward comparison is unreachable" — whether the cohorts are even the same grammar cell — and it does **not** hold. v39's stage-two cohort is `rank_k=5: 52% / 10: 48%`, v48's is `10: 62% / 5: 38%`; **the honest stage-two population has ALWAYS been `rank_k <= 10`**, because a `rank_k=20` child still cannot resolve the breadth floor on full history. So the confound is the one they measured (cream vs unfiltered), it is **directional and known**, and it *opposes* the p90 conclusion — making "v48's ceiling is at least as high" conservative rather than unusable. Proposed scope change, not a decision reversal: retire pre-v48 as a **precision** comparator, keep it as a **directional** one. Files: `config/grammar.yaml` (+archive `v49.yaml`), `tests/integration/test_v1_grammar.py`; shared `aa0f516`.

## D333 — 2026-07-23 — ADOPT `crucible_contracts` 1.36.0 (PIN-ONLY): selection provenance — the bump WE asked for, and it unblocks the prefilter-holdout

**Operator: "yes" (adopt).** Crucible shipped `ac9e8f5` "selection provenance on StrategyConfig" while we were mid-session; installed went to **1.36.0** against our **1.35.0** pin, i.e. running **un-adopted** — the D245/D261 asymmetric-upgrade class. Daemon was healthy under the mismatch (`active`, **0** contract/validation/traceback lines, inbox depth 2 and not growing) because §13.5 only hard-raises on a MAJOR mismatch, but a reboot surfaces a minor mismatch as a hard halt, so it could not sit.

**What 1.36.0 adds — three OPTIONAL fields on `StrategyConfig`:** `selection_rank`, `selection_pool_size`, `prefilter_sample`. **This is the bump we asked for.** Crucible could not verify any Forge selection claim because a submitted config carried no rank and no pool size — from their side our measurements were "unverifiable assertions" (their 2026-07-22 §6) — and `prefilter_sample` is the explicit marker their **condition #1** required before we may run the **prefilter-holdout campaign**, the instrument for the one DSR charge both repos agree is real and currently unmeasured (D330). **D331 item 3 is therefore unblocked.**

**PIN-ONLY adopt, deliberately.** Forge emits none of the three yet. Verified before bumping: all three are optional-with-`None` (`required=False`), and all three are **HASH-EXCLUDED** — a config stamped with `selection_rank=137, selection_pool_size=1950, prefilter_sample=True` hashes identically to the bare one (`67dceebe91886e64` both ways). So §13.4 submission idempotency and hard-rule-#6 determinism are untouched, and stamping them later is a separate, safe increment rather than a coupled one. Sequencing is the agreed rule (bump → consumer adopts → producer emits); this is the adopt half, and Crucible is expected to wait on it before emitting.

**Deploy:** stop → full **uncontended** suite **2064 passed / 1 skipped** → *read the result* → restart. `active/running`, NRestarts=0, `grammar_version=v49`, `registry_loaded_from_export`, no traceback, inbox depth 2 (unchanged, no wedge). `check_contracts_version()` clean at installed 1.36.0 / pin 1.36.0. **Note the ordering was corrected from the v49 deploy**, where we restarted before reading a red suite — this time the suite result was read first.

**NOT shipped in this window, and why (operator asked directly "do we ship the retarget now?"):** the quality-lane re-target from `target_wf_p25` to `target_cpcv_p25` (D332 finding) is evidence-strong — **6/6 holdout splits favour it on the metric that matters**, IC vs realised CPCV, with the wf-targeted model going **negative** at 30%/40% holdouts (0.0278, −0.0430) while the cpcv-targeted one degrades gracefully (0.2042, 0.1259). Held anyway for two independent reasons: **(1)** it would contaminate **v49**, shipped hours earlier precisely to give the honest-label change a clean ranker boundary — the re-target deserves **v50**, which is cheap now that a version reaches n≥300 in ~2.5h; **(2)** stacking a learned-lane change on top of an un-adopted contracts transition is exactly the D245 pattern that wedged the inbox twice. Prereg `7f675a79ca57` holds the claim and the falsifier. Files: `src/forge/core/contracts_check.py`.

## D334 — 2026-07-23 — INCIDENT + RECOVERY: emit `selection_arm` (contracts 1.37.0) — and a self-inflicted `prefilter_sample` dead-loop the fix resolves

**INCIDENT (found on session resume):** `forge.service` had been **failing every iteration for ~3h**, zero production since the 10:51:04 PDT restart, with `ValidationError: StrategyConfig … prefilter_sample: Extra inputs are not permitted [extra_forbidden]`. **Cause = the shipped≠deployed / asymmetric-contracts class, self-inflicted:** the 10:51 daemon restarted onto an intermediate on-disk version of the selection-provenance emitter that stamped the contracts-**1.36.0** `prefilter_sample` bool; Crucible then shipped **1.37.0** (`9d2d4a9`), which **removed** `prefilter_sample` in favor of the `selection_arm` enum, and the installed package updated under the running process — so every `config.model_copy(update={"prefilter_sample": …})` began failing validation. The daemon kept looping (`continuing next poll`), so systemd never marked it failed and NRestarts stayed 0; only the missing submissions surfaced it. **This is exactly why the deploy-staleness check (D330) exists — and it did not catch this**, because the mismatch was code-vs-installed-package, not code-vs-git-HEAD. Flagged as a gap in that check.

**THE EMISSION (the correct fix, D333 cont.):** Forge now stamps `selection_arm` + `selection_pool_size` on every submitted config (`submitter._submit_one`, in the same hash-excluded `model_copy` as `grammar_version`). Mapping `_SELECTION_ARM_BY_MODE`: `ranked → "ranked"`, `holdout → "exploration_holdout"`, **`young_explore → None`** (D316 2d — ranker-unselected but BIASED toward young cells, so neither the merit arm nor the uniform-random arm; contaminating either would break the freeze criterion's honest-arm meaning, so it stays unset until Crucible names a fourth value; young_explore is not live anyway). `selection_pool_size = survived_count` (prefilter survivors, the pool ranked from). `selection_rank` deliberately **NOT** emitted — a precise rank needs the full pre-truncation pool ordering, unavailable at the submit layer, and a wrong rank is worse than a null (flagged to Crucible). Why this matters: Crucible's freeze criterion must be evaluated on the arm unselected by BOTH stages, and until Forge emits the arm marker their evidence base cannot distinguish the ranker-honest from the grammar-honest population — the hard-rule-6 hazard they raised 07-23. The ternary population axis is Forge's correction that turned 1.36.0's bool into 1.37.0's enum.

**Verification:** contracts pin 1.35.0→1.36.0→**1.37.0**; all three provenance fields are optional + **hash-excluded** (verified: a config stamped `selection_arm='exploration_holdout', selection_pool_size=1850` hashes identically to bare, `67dceebe91886e64`), so §13.4 idempotency and hard-rule-#6 determinism are untouched. TDD: 3 submitter tests (ranked→ranked + pool_size; arm-always-set-even-when-pool-unknown; young_explore→None), red→green. **Full uncontended suite 2067 passed / 1 skipped** (run this session pre-incident-discovery, on this exact tree). **Recovery deploy:** commit (clean the D104-dirty tree) → restart onto the correct code → verify first post-restart batch stamps the arm on real submitted rows. Files: `src/forge/submission/submitter.py`, `src/forge/core/contracts_check.py` (pin), `tests/unit/test_submission/test_submitter.py`, `uv.lock`.

**↳ ROOT CAUSE went deeper than the emitter, and the durable fix is in RECONCILE.** Restarting onto the correct emitter did NOT clear the dead-loop — the fresh process kept failing on `prefilter_sample`. Reproduced with a full traceback: the failure is in `feedback.consumer._load_submissions` (`main.py:1661` reconcile path), which strict-parses **Forge's OWN stored `config_json`** via `StrategyConfig.model_validate_json`. **400 submissions rows (220 still `status='submitted'`) carry `prefilter_sample` in their stored JSON** — successfully submitted during the 1.36.0 window (09:22–10:19 PDT) before the package bumped to 1.37.0. Reconcile re-validates those historical rows every pass; 1.37.0 forbids the removed field; the loop wedges. **This is the read-side additive-forbid trap the 1.26.0 export loaders already fixed** (`parse_forward_compatible`), applied to the wrong surface: re-reading our own history was still strict. **Durable fix:** `_load_submissions` now uses `parse_forward_compatible(StrategyConfig, json.loads(cfg_json))` — tolerant re-read that prunes since-removed fields and recovers the same `config_hash`. Strict validation still guards FIRST ingest at submit time (this is only a re-read). **Verified the fix recovers all 220 real stuck rows (0 failures)**, config_hash unchanged. TDD: `test_reconcile_tolerates_stored_config_with_removed_contract_field` (injects `prefilter_sample` into a stored row, asserts `_load_submissions` recovers it), red→green. **Full uncontended suite 2067 passed / 1 skipped** (+1 pre-existing flaky `test_held_out_platt_reduces_ece_vs_raw`, passes on rerun, untouched by this change). **The general lesson: Forge's own persisted `config_json` must always be re-readable regardless of contracts field churn — strict re-validation of historical rows is a latent wedge on every field REMOVAL, symmetric to the additive trap.** Files added: `src/forge/feedback/consumer.py`, `tests/unit/test_feedback/test_consumer.py`.

**↳ 2026-07-23 (later) — `selection_rank` added for the `ranked` arm (Crucible 07-23 §3, closing the field's original purpose).** They verified `selection_arm`/`selection_pool_size` landing (181 v49 rows, ~5.5% holdout, ingest clean) and proved the stage-two inheritance round-trip end-to-end with their own regression test, but flagged **`selection_rank=null` on ranked configs** — the field that lets them reproduce per-config selected-vs-pool inflation directly (the original reason the whole 1.36.0/1.37.0 field set exists: our selection claims were unverifiable from their side). Previously deferred because a *correct* rank needs the pre-truncation pool ordering — but that ordering IS available at the submit layer: the caller passes `candidates = [*selected, *holdout, *young]`, and `selected` is the ranker's top-N **in rank order** and is exactly the `ranked` arm, so a ranked config's 1-based position among ranked configs equals its rank within the survivor pool (the selected ARE the pool's top-N). Implemented as a running counter over `ranked`-mode configs in `submit_batch`; holdout/young stay `None` (not rank-selected). Hash-excluded (verified: `selection_rank=137` → identical hash), so idempotency/determinism untouched. TDD: `test_selection_rank_is_1based_over_ranked_arm_only` (ranked→1,2; holdout→None), red→green. 229 submission+invariant tests pass; ruff+mypy clean.

## D335 — 2026-07-23 — PREFILTER-SAMPLE TWO-ARM CAMPAIGN (built behind `FORGE_PREFILTER_SAMPLE_N`, default 0 = byte-identical). The grammar-honest arm the freeze criterion is written to.

**The gap it closes (Crucible 07-23 hard-rule-6 thread).** The freeze criterion is a claim about the GRAMMAR, so it must be read on the population unselected by BOTH Forge selection stages. Our two existing arms are not that: `ranked` is selected by both; `exploration_holdout` (D256) is ranker-unselected but **prefilter-SELECTED** (drawn from survivors), so it guards the ranker hazard only. The prefilter cuts ~63% of enumeration on the config's own in-sample performance (`permutation_test` dominant) and its rejects are never submitted → survivorship → the one selection stage neither side can measure. **`prefilter_sample`** submits a uniform-random draw of those rejects, tagged `selection_arm='prefilter_sample'` (contracts 1.37.0, D334), so Crucible finally has a population unselected by both stages.

**Design.** New flag `FORGE_PREFILTER_SAMPLE_N` (int, default 0 = OFF = byte-identical: empty draw, no submission change). When N>0, after `ranked` is finalized, draw N configs uniformly from `[r for r in reports if not r.passed]` via `SeedHierarchy(seed).rng("prefilter_sample")` (hard rule #6 — same (grammar, registry, seed) → same sample), excluding any hash already on the batch, and **ADD** them to the submission list (extra stage-one slots, never stolen ranked throughput — Crucible 07-23 §5's preference; at the ~355/hr runner ceiling the §7.3 backpressure self-limits the combined stream). Tagged via `_SELECTION_ARM_BY_MODE["prefilter_sample"]="prefilter_sample"`; carries `selection_rank=None` (never rank-selected) and **`selection_pool_size=None`** (never drawn from the ranked survivor pool that `survived_count` describes — passing it would falsely imply it competed there). Clamped to `_MAX_PREFILTER_SAMPLE_N=40`. **NOT excluded from admission** (Crucible's condition): submitted like any config, so if a prefilter-reject clears Crucible's gates on merit it becomes a component — the campaign's single most interesting possible outcome.

**Verification.** TDD: submitter arm/rank/pool tagging (`test_prefilter_sample_arm_tags_and_maps`), flag resolver (unset→0, clamp, negative→0, malformed→0 degrade-never-crash). Emission proof: flag-OFF resolver 0; flag-ON draws N uniform rejects (all `passed=False`), deterministic per seed, different seed → different sample. **363 CLI+submission+invariant tests pass** (incl. the delicate D065/D105/D106 `main.py` monkeypatch set); ruff + mypy --strict clean. selection_arm/rank/pool_size all hash-excluded (D334) so §13.4 idempotency + hard-rule-#6 determinism untouched.

**Operational (Crucible's conditions):** explicit marker ✓ (`prefilter_sample` enum); **time-boxed 2–3 weeks** (operator turns the flag off; end date in STATUS); not excluded from admission ✓. **Ships flag-OFF (byte-identical); activation is the operator flipping `FORGE_PREFILTER_SAMPLE_N` in the trainer... the DAEMON unit `forge.service`** (this is a submit-path flag, unlike D331 Part B's trainer flag — noted to avoid the D331 wrong-unit trap). Recommended start N=5 (Crucible's original ~5/200; conservative given we sit at 333/hr vs the ~355/hr ceiling), widen later for their statistical-power + tail-production argument (07-23 §5). Files: `src/forge/cli/main.py`, `src/forge/submission/submitter.py`, `tests/unit/test_cli/test_run_loop.py`, `tests/unit/test_submission/test_submitter.py`.

## D336 — 2026-07-25 — v49 → v50 DEPLOYED (bundled): IWM+SLB dead-name rider + `rank_k=5` trend bias; and the tail-model RETARGET to `cpcv_sharpe_p25` (versionless, same window)

**Deployed 2026-07-25T01:33:26Z** (`eff98ff`). Journal verified: `grammar_version=v50`,
`registry_loaded_from_export` (registry_hash `4aad48e7be14daee`), `grammar_versions:
recorded manual_bump row for v50`, reconcile line, §7.3 backpressure block; no traceback,
NRestarts=0. Full uncontended suite READ BEFORE restart: **2086 passed / 0 failed**.

**Why bundled.** The two grammar changes touch DISJOINT populations — since v47 made
trend/MR xsect-only, the name exclusion can only affect single-name draws (i.e.
`volatility_event`) while the rank_k bias only affects trend xsect — so neither can
confound the other in `funnel --compare`. Operator: "definitely bundle."

**(1) IWM + SLB** → `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` (38 → 40). `forge yield-audit`
round 2: IWM 502 decided / 0 converted, SLB 540 / 0 since the clean-era cut (ghost-cut
applied) — the only two names clearing the bar this cohort. Prereg `8eaa7e4aca93` on record
BEFORE the edit (D207). Same frozen-list terms as v34/v37/v41/v43; row-45 cross-check
requested in the deploy relay. NB IWM was already in `_NO_EARNINGS_UNDERLYINGS`, so it was
barred only from earnings-gated configs; the 502/0 accrued on non-earnings single-name
templates, which this closes.

**(2) `rank_k=5` BIAS scoped to `trend_continuation`** (`_TREND_RANK_K5_SHARE = 0.75`).
Origin: the SALVAGE of the parked winner-neighborhood prior — the learned prior's aggregate
effect was unresolvable (p90 +0.0087, ~20k/arm to detect) but one param carried real signal,
and Crucible validated it on their honest arm (n=341): trend med CPCV **+0.4056 (k=5, n=210)
vs +0.1325 (k=10, n=84), gap +0.2731** — ~29× the entire corrected prior effect — and **FREE**
(maxDD 0.1462 vs 0.1571, gate pass 97.4% vs 97.3%). **ZERO in mean_reversion (+0.0029)**,
hence the scoping. BIAS not pin (D276 `_RESID_LONG_ONLY_SHARE` precedent): k=10 keeps 25% so
the n=84 arm stays explorable (D067). `residual_momentum` is checked FIRST and keeps its own
D276 pin. **Known trade:** k=5 lowers WF (0.752 vs 0.888) and wins the joint
`min(cpcv/1.5, wf/2.0)` 2.6× ONLY because cpcv is the binding gate (0.0% admit vs 0.7%) —
**revisit if that ever changes.** Prereg `b13b0f893a11`.

**(3) TAIL-MODEL RETARGET — versionless, shipped in the same window.** `main.py`
`target_wf_p25` → `target_cpcv_p25`. `wf_sharpe_p25` turned out to be a NON-BINDING
enrichment label Crucible computes FOR our ranker (threshold 0.0, admits 100% of stage two
— their correction; it is not a gate), and on the honest ARM it is ~orthogonal to the metric
that does gate (`sp = +0.031`, vs +0.39 on the ranker-selected pool = a SELECTION ARTIFACT).
Measured (`target_sweep.py` Run C): ordering by wf_p25 lifts realized cpcv +0.009 (baseline),
by cpcv **+0.178**. Endorsed by Crucible. Selection ≠ enumeration, so no version bump
(D287 precedent). **`daily_ranker_eval.sh` now trains BOTH targets** — without that the lane
would load the last hand-trained cpcv artifact and silently freeze; training both also keeps
the revert to a one-line daemon change with no gap. Verified post-restart: `target_cpcv_p25`
→ `d8d85324` (n=29,419) and `target_wf_p25` → `bde5367a` both resolve.

**(4) Contracts pin 1.38.0 → 1.39.0** (`generation_arm` / `generation_prior_id`). PIN-ONLY:
we deliberately **emit neither field** — the generation prior they exist for was parked, so
Crucible's "clear to emit" GO stands unused. The preflight caught the un-adopted pin.

**Goldens re-pinned (7 constants)** under the D286/D290/D309 discipline: at the pre-edit
preflight the OLD code reproduced every constant exactly (suite green but for the contracts
pin), so no unrelated drift rides along. Verified every first divergence is a
`volatility_event` single-name config = the v37/v41/v43 pool-shift signature; 7–11 of 15
positions survive byte-identical (per-index seeding).

**Emission proof** (3k+ cold enumeration, production `rank_combiner_share`): excluded-name
draws `{}`; trend non-resid k5_share **0.746** (target 0.75); `residual_momentum` 0.483 and
mean_reversion 0.477 both untouched (~0.50). The first proof run measured 0.495 and was
WRONG-CONDITIONS, not a bug: a cold-start enumeration with no share draws only resid on the
trend-xsect arm (everything else is filtered `retired_single_name`), and resid legitimately
short-circuits to its D276 pin.

**Also logged: Q57** — the v44 vix-conditioner fires at ~0.22 against its 0.125 constant
across 6 seeds. PRE-EXISTING (pre-v50 code produces ~0.22 too; the old band ceiling had been
fitted to it), v50 only re-sampled it past the edge. Band re-pinned to [0.05, 0.28] WITH an
inline warning that it tracks the realized rate and is NOT evidence the share is honoured.

**Post-ship reads:** `funnel --compare v49 v50` (and `--hypothesis trend_continuation`);
resolve `8eaa7e4aca93` + `b13b0f893a11` on post-cut honest cohorts; watch the first
`quality_rank:` journal line naming a cpcv model (appears on the first UNBLOCKED iteration).

## D337 — 2026-07-25 — v50 → v51 SAME-NIGHT REVERT of the rank_k=5 trend bias: the validating evidence was COLLIDER BIAS and the true sign is reversed

**Deployed 2026-07-25T07:34:22Z** (`f3404ab`). Journal: `grammar_version=v51`,
`grammar_versions: recorded manual_bump row for v51`, no traceback, NRestarts=0.
Suite READ before restart: **2087 passed / 0 failed**. `FORGE_PREFILTER_SAMPLE_N=300`
preserved across the restart (operator: keep the honest-arm speedup).

**What happened.** D336 shipped `_TREND_RANK_K5_SHARE = 0.75` on Crucible's honest-arm
validation (trend med CPCV +0.4056 at k=5 vs +0.1325 at k=10). Hours later they retracted
it in full: the validation conditioned on the **stage-two** cohort, and stage-two
admission is the refit TRIGGER — a function of config quality — so conditioning on it is
a **collider**.

**Reproduced on OUR ledger before acting** (we did not revert on their word alone; our
figures match theirs to ~0.007 on every cell):

| population | bucket | k5 − k10 (ours) | (theirs) |
|---|---|---:|---:|
| **stage one** (unselected) | swing_mid | **−0.1712** | −0.1771 |
| **stage one** | swing_long | **−0.0256** | −0.0258 |
| stage two (the validating population) | swing_mid | **+0.0776** | +0.0853 |

**The mechanism, in our data:** `swing_long × k=10` converts **0 of 404** stage-one rows —
that cell is ENTIRELY ABSENT from stage two — so `rank_k` was silently confounded with
`dte_bucket`; and in `swing_mid`, k=5 survivors are a *more* selected slice (54.5%) than
k=10's (69.1%), inflating k=5 mechanically. Same metric, same configs, sign flips purely
from conditioning. Berkson's paradox. Crucible's stage-one replication: **5 of 6
populations negative, to z = −38.75 on n≈69k**; v50 was already measuring **−0.0724**
median CPCV vs v49 on the honest stage-one stream.

**The revert.** Trend branch and both constants removed; `_rank_combiner`'s body is
byte-identical to pre-v50 and its signature drops back to two args so no caller can pass a
hypothesis expecting it to steer `rank_k`. A TOMBSTONE at `_RANK_K_CHOICES` carries the
evidence, mechanism and rule. **IWM/SLB exclusion KEPT** — disjoint population, so the
D336 bundling argument held up under exactly the stress it was designed to survive.

**Goldens re-pinned** (third state: v49 draws + IWM/SLB). **Six of seven identical to
v50** — only the cohort golden moved (@7), the one passing `rank_combiner_share` and thus
drawing trend xsect. The revert is surgical. Emission proof: excluded-name draws `{}`;
trend non-resid k5_share **0.527** (was 0.746); MR 0.492 untouched.

**Prereg `b13b0f893a11` resolved REFUTED** — refuted by *reversal*, not by a null read.

### THE RULE THIS BUYS (the durable output, bigger than the finding)

> **Parameter effects are estimated on STAGE ONE (unselected) ONLY. The stage-two honest
> arm is a valid yardstick for grammar-VERSION deltas — like-conditioned cohorts either
> side — but is NOT a valid instrument for parameter attribution.**

Stratifying *within* the stage-two population does not rescue it: Crucible controlled
within sizer mode, within risk quartile, within hypothesis, and every control was applied
inside the collider-conditioned sample. **The collider is at the sample's boundary, not
inside it.**

**This lands on our instruments too, and we own it.** `scripts/target_sweep.py` Run C and
the whole `winner_prior` fit judge on `fullhist_refit` = stage two. Our own "independent
confirmation" of rank_k (IC −0.167) used the same conditioned population and therefore
could never have caught this. **Every parameter-level claim from 2026-07-24 needs
re-deriving on stage one** — including the `per_trade_risk_pct` refutation, which Crucible
has also flagged as un-rechecked (its drawdown pairing may carry it, but that is not
established).

**Not actioned: the `swing_long` lever.** Crucible's stage-one data shows swing_long −
swing_mid at fixed rank_k = +0.42 / +0.27 on the honest arm (z > 10), replicated at z > 39
on 69k legacy rows, with *lower* drawdown, and 43% of trend still draws swing_mid. They
explicitly asked us NOT to ship it on that relay — "we have just demonstrated how easily we
fooled ourselves." Direction noted, validation first.

## D338 — 2026-07-25 — GENERATION PRIOR (winner-neighborhood) RE-DERIVED ON STAGE ONE and **REFUTED**: it is a tail COMPRESSOR, and the "57 days of accrual" that parked it was itself an artifact of the collider population (analysis only; NO code / grammar / determinism / DB change)

**Decision.** The winner-neighborhood generation prior moves from **PARKED** to **REFUTED**. Nothing ships, nothing is wired, `src/forge/ranking/winner_prior.py` stays dead code reachable only from scripts. The **~20,000/arm ≈ 57-day accrual argument is void** and must not be re-raised as a reason to wait.

**Why re-open a parked lever at all.** [[D337]] established the rule that parameter effects are estimated on **STAGE ONE (unselected) ONLY**, because stage-two admission is the refit TRIGGER — a function of config quality — and conditioning on it is a collider that can *sign-flip* an estimate (`rank_k=5`: +0.0776 stage two vs −0.1712 stage one; shipped in v50, reverted in v51 the next night). The prior's 07-24 parking read — d_p90 **+0.0087** on the honest ARM, CI [+0.0003,+0.0429] — was computed with `WHERE v.measurement_basis = 'fullhist_refit'` on **both** the fit and the judge. Narrowing lane→arm (the 5× inflation Crucible caught) narrowed the *arm* but not the *stage*; as the probe scripts' own warning says, stratifying **within** the conditioned sample does not help because the collider is at its boundary. So the parking number was untrustworthy in both directions, and the operator called for the re-derivation ("RUN IT NOW").

**The second, quieter defect — the power argument was circular.** "Needs ~20,000/arm ≈ 57 days" was derived from a **302-row** conditioned slice while **233,867 unconditioned rows** sat in the same table. The blocker was not accrual; it was measuring on the wrong population. Re-derived at **8,000× the judge power with zero waiting**, in ~20 minutes.

**Instrument.** `scripts/winner_prior_stage_one.py` (read-only, snapshot-only, refuses the live DB path). Reuses `_cell_and_params` verbatim from `winner_prior_shadow.py` so the two reads are comparable, applies the same D290 ve-ghost cut and `CLEAN_ERA_LABEL_CUT` the trainer uses, and re-cuts the stage-two subset **through identical code** so any difference is attributable to conditioning rather than to the analysis. Five arms: (A) stage one vs stage two on defaults, (B) the 64-combo hyperparameter grid, (C) split stability + bootstrap, (D) the quantile profile, (E) the gate-clearing rate. n = **233,867** stage one / 7,457 stage two / 804 honest arm; 60 cells, 4 hand-pinned cells held neutral.

**Result 1 — the collider delta reproduces the `rank_k` pattern.** Identical code, defaults, 70/30 temporal split: stage two d_p90 **+0.0334** vs stage one d_p90 **−0.0068**. Sign flip plus ~5× inflation. The parked read was measuring the conditioning, not the prior.

**Result 2 — it is a tail COMPRESSOR, which is a worse finding than a null.** Uniform vs prior-weighted outcome quantiles on the held-out judge set: q10 +0.0099 · q25 **+0.0130** · q50 **+0.0106** · q75 +0.0045 · q90 **−0.0068** · q95 **−0.0125** · q99 **−0.0324**. Monotone: it tilts toward modal, well-behaved neighborhoods and away from *both* tails. Bootstrap (500 resamples, n_judge=70,161): d_med +0.0105 CI [+0.0085,+0.0124] **P(>0)=100%**; d_p90 −0.0069 CI [−0.0097,−0.0044] **P(>0)=0%**. Both decisive, in **opposite directions** — which is precisely why a single headline metric could not settle it.

**Result 3 — the decision metric, because Forge's problem is entirely tail.** Share of configs clearing cpcv **1.5**, uniform → prior-weighted, across all five temporal splits: **0.23× / 0.57× / 0.64× / 0.95× / 1.10×**. At the ≥1.0 threshold (real n — hundreds of configs rather than 4–10): **0.61× / 0.77× / 0.81× / 0.98× / 1.02×**. It never wins where there is power. The drift toward 1.0× at the two latest cuts is the prior converging to **doing nothing** (fit and judge windows increasingly overlap), not to helping — which closes the "maybe it works on recent data" escape hatch. A median-improver that shortens the tail is worse than useless when the gate sits at 1.5 and the honest median is 0.351.

**Result 4 — the never-swept axis, now swept, changes nothing.** All **64** combos (`n_bins` 3/4/6/8 × `shrinkage_n` 5/10/25/50 × `max_weight` 1.5/3.0 × `exploration_floor` 0.25/0.5) land within **0.002** of one another; the best d_p90 in the entire grid is **−0.0046**, still negative. Kish ESS ≈ **80%** throughout, so this is not a variance-collapse artifact of the product-of-multipliers weighting — a failure mode specifically instrumented for, given `_config_weight` multiplies across every param.

**Stated in its favour, because a refutation should be fair.** The implementation is sound: the binned (quartile) encoding is **structurally immune** to the Q59 linear-smear defect that killed `rank_k`, and all 15 safety tests hold (bounded / floored / shrunk / neutral-byte-identical / hand-pin-exempt). This is a well-built implementation of an idea the data does not support — the spec's own §6 null, now measured rather than assumed.

**Alternatives considered.** (i) *Keep waiting for the honest arm to accrue* — rejected: the accrual argument was the artifact. (ii) *Re-tune and retry* — rejected: arm B shows the hyperparameters are inert. (iii) *Judge on the median, where it wins decisively* — rejected: the median is not the binding quantity; arm E is. (iv) *Delete `winner_prior.py` now* — deferred to the operator; the module and its tests are harmless dead code and document the negative result.

**Method note worth carrying.** Re-deriving a parked lever on stage one cost one script and ~20 minutes. Any other conclusion still resting on `fullhist_refit` deserves the same treatment before it is trusted **or waited on** — the collider corrupts the power calculation as well as the point estimate.

**Files:** `scripts/winner_prior_stage_one.py` (new), `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`. No production path touched; the daemon was untouched throughout (read-only snapshot, deleted after each run, `nice -n 15` so the live service kept priority).

## D339 — 2026-07-30 — TAIL-LANE ARTIFACT MISRESOLUTION: the MR lane ran the TREND model for 24 of 63 batches; prereg `8cfe95f4a6e9` attribution CORRECTED, trend prereg `4d1fa832789f` registered, and Crucible's Q57 mapping REFUTED in two directions (tests/analysis/relay only; NO grammar / determinism / DB-schema change)

**Decision.** The confirmed result of [[D335]]-era prereg `8cfe95f4a6e9` **stands on its registered criterion** but its **attribution is corrected**: the 5–7× tail-arm lift is a property of *exceedance ordering on a tail objective*, not of `sharpe_baseline` specifically. The lane mechanism is confirmed; the target choice between `sharpe_baseline` top-800 and `wf_p10` top-200 is **not** what the live test established, and any downstream claim that rests on the target rather than the lane must be re-derived.

**The defect.** `scripts/daily_ranker_eval.sh` was wired to publish **two** tail artifacts (`target_sharpe_baseline` n800 for the MR lane, `target_wf_p10` n200 for the trend lane) **before** `load_latest_tail_model` gained its `base_target=` filter. Resolution therefore ran by `(trained_through, model_id)`; when one daily run trains both, `trained_through` **ties** and the winner is a `model_id` hash comparison — a coin toss. The 95-slot MR lane consequently ran the **trend** artifact, scored against the **full survivor population** rather than the trend slice it was fitted on, for **24 of 63 batches (38%)**: `7ecb869d` 2026-07-27 15:46 → 07-28 04:39 PDT (12 batches) and `e32a47ee` 07-29 06:24 → 22:44 PDT (12 batches).

**Ordering error, named.** Publishing a second artifact into a directory whose reader resolved by recency alone is the whole bug. The lane's identity is its **objective**; recency may only break ties *within* one objective. The `base_target=` filter shipped in `5f5608f` and reached the daemon at the 2026-07-29T22:58 PDT restart, so the live defect window is closed — what was missing was a **test**, now `test_load_latest_resolves_by_base_target_not_by_recency`, verified to fail when the filter is removed.

**The daemon logged it honestly for three days.** Every `tail_lane: ACTIVE` line carried `base=target_wf_p10 top-200`. The first resolution of the prereg did not read the field. The lesson is not "add more logging" — it is that a field printed for verification must actually be read at the moment it is used as verification, and the trend-leg deploy note that called `population=` "the check that matters" was written in the same session that failed to check `base=`.

**Attribution recovered per-batch** from the journal (the only record of which artifact was live for a given batch; `batch_id=` prints in the same block as the lane line). Strong = `decision='component'` AND `cpcv_sharpe_p25 >= 0.9439`; denominator = decided configs per arm; batches with ≥20 decided in both arms:

| era | batches | tail | merit | ratio | ≥1.5× |
|---|---:|---:|---:|---:|---:|
| `sharpe_baseline` top-800 | 39 | 5.056% (312/6,171) | 0.719% (37/5,148) | **7.03×** | 37/39 |
| `wf_p10` top-200, unfiltered | 23 | 4.862% (180/3,702) | 0.946% (29/3,065) | **5.14×** | 23/23 |

**The registered per-batch criterion reproduces EXACTLY (60/62)** from a fresh snapshot, and the registered objective is the **stronger** era — so the contaminated batches **diluted** the effect rather than creating it, and the confirmation is not an artifact. Component rate is higher for the tail arm in both eras (35.0% / 35.5% vs 25.4% / 26.2%), so there is no supply cost under either target. The 39-vs-23 era comparison is **observational** (different days, no randomization) and is a lead, not a measurement. Pooled percentages differ in level from the first resolution's (9.713% / 1.714%); the earlier denominator could not be reconstructed, so the explicitly-defined figures above supersede it, and the ratio is larger under the stated definition, not smaller.

**Trend prereg registered: `4d1fa832789f`** (cohort cut 2026-07-30T06:10:07Z), for the 40-slot trend leg deployed at 22:58 PDT. Predicts (1) the trend arm's strong-component rate among **its trend rows** ≥ **1.25×** the merit arm's rate among **its own trend rows** over a majority of batches, and (2) whole-batch trend share rising from 36.2% back toward the 52.9% pre-tail-lane level. Registering the **trend-restricted** comparison explicitly is the point: comparing the trend lane against the merit arm's all-hypothesis rate would repeat Crucible's *wrong population* error class — and would repeat this very entry's defect, which was itself a population error.

**Crucible Q57 (freeze `9357b7d`) — their operationalization REFUTED in two directions, reply relayed as freeze `6bfe0cd`.** They mapped "the resid_vix conditioner" to `vix_term_slope` in a `regime_filter` role × a `residual_momentum` directional and asked for confirmation before either side acted. Our resid × vix emission has exactly **three** gate shapes: `(vix)` 590 and `(vix, days_since_jump)` 581 — both **vix-as-PRIMARY**, the [[D276]]/v33 coin over `{vix_term_slope, hurst}`, natural share ~0.5, eleven versions older than the D317 conditioner — and `(hurst, vix)` **42**, the conditioner. So **96.5% of their numerator is not the pilot**. Cross-validated on the rows: their v46 numerator 13 = our vix-as-primary count 13; their v51 96 vs our 97. **Second, opposite error:** `_vix_conditioner_eligible` does not constrain the **directional**, so their predicate sees 42 of the **492** conditioner configs ever submitted (8.5%) — carriers are donchian 178, rolling_sharpe 90, momentum_252 87, sma_slope 73, residual_momentum 42, ad_slope 22. **Consequence: their pinned 2026-08-04 pilot read has 3 conditioner configs in the v45/v46 window (v44 1, v46 2; v45 produced no decided configs), and 0 carrying a resid directional.** They said they would not read a pilot off 13.

**Their (c) confirmed and localized — a Forge-side under-emission.** Realized conditioner share against **its own** eligible pool (xsect trend, non-capitulation directional, hurst primary, ≤2 gates): v44 0.0032, v46 0.0018, v47 0.0014, v48 0.0069, v49 0.0842, v50 0.0679, v51 0.0369, against `_VIX_CONDITIONER_SHARE = 0.125` drawn **before** the veto and mutually exclusive with it (so 0.125 is the unconditional expectation, not a conditional one). We are failing our own specification by 1.5–3.4× recently and ~40–90× in the pilot window. These are **submitted** configs, so the gap may be sampler-side or prefilter-side; the leading suspect is `predicted_activations` rejecting the thinner double-gated stream — the [[D290]] `ref_trailing_return` mechanism — and it is recorded as a **hypothesis**, with enumeration-vs-submission not yet separated. **OPEN: separate the two stages on this cell.**

**↳ 2026-07-30 (later) — CONDITIONER UNDER-EMISSION CHASED and BOTH OF OUR HYPOTHESES REFUTED: the sampler is at spec, the RANKER is the loss, and the ranker is RIGHT — the hurst × vix cell is NEGATIVE (analysis + relay only; NO code / grammar / determinism / DB change).** Operator: "chase the conditioner under-emission". **Retracted, ours:** (1) "we are failing our own 0.125 specification by 1.5–3.4×" — we measured *submitted* configs, which are post-ranker; (2) the [[D290]] `predicted_activations` suspicion — refuted outright. **Method — no battery re-run needed:** three selection arms are random draws from *different stages*, so together they separate sampler from prefilter from ranker. `prefilter_sample` (D335) is a uniform draw from prefilter **REJECTS**; `holdout` (D256) is a seeded draw from **SURVIVORS the ranker did not pick**; `ranked` is the ranker's picks. Grammar ≥ v49, within the conditioner-eligible pool (xsect trend, non-capitulation directional, hurst primary, ≤2 gates): **rejects 0.1117 · survivors 0.1209 · ranked 0.0344**, against a `_VIX_CONDITIONER_SHARE = 0.125` spec. Both unbiased arms sit at spec, so the raw enumeration mix is ≈0.12 whatever the reject/survive ratio → **the sampler honours its spec and the prefilter is neutral**; the ranker is the entire loss (3.5×, and **24×** on v51 alone: 0.0048 vs 0.1166). **AND THE RANKER IS CORRECT.** On the unbiased arms, within the same eligible pool: component rate **11.4% (30/263) vs 30.7% (632/2,057) = −19.3pp, z = −6.53**, mean cpcv **negative** (−0.0855) vs positive (+0.1804). **Not a mix artifact** — directional mix nearly identical (momentum_252 32.7% vs 29.6%, sma_slope 27.8% vs 29.2%, resid 13.7% vs 10.7%) and the conditioner converts worse **within all six directionals separately** (momentum_252 14.0 vs 37.8, sma_slope 19.2 vs 37.3, resid 0.0 vs 16.3, donchian 7.1 vs 21.3, ad_slope 4.5 vs 21.0, rolling_sharpe 5.6 vs 26.6 — six strata, six times the same sign). **Not thinness either** — median trade count 408 vs 515, **zero** zero-trade configs in 263, `min_oos_trade_count` failing only 8.0% vs 5.3%. **The mechanism is the QUALITY gates:** `sharpe_baseline` 53.2% vs 23.5% fail, `regime_stress_p25_return` 30.8% vs 10.5%, `profit_factor` 13.7% vs 4.9%, `max_drawdown_ceiling` 16.3% vs 8.6%. ANDing `vix_term_slope` onto a hurst primary does not thin a good stream — it removes more good trades than bad ones. **Claim deliberately WITHHELD:** the strong rate is 0/263 with a **95% upper bound of 1.13%** against a 0.53% base rate, which is *no evidence of a deficit*; the component-rate result is the strong one and the strong-rate one is not presented. **NOT retiring it** — it is Crucible's Q46 pilot, retirement is an operator-gated grammar change, and [[D328]]'s freeze programme is the vehicle; we hold 0.125 until they answer. **ASK relayed:** does their in-book marginal-contribution lane see value here that standalone conversion cannot (the [[D186]] boundary, where they can see correlation contribution and we cannot)? If no, it is a freeze-programme prune candidate. Correction relayed as freeze `9cb99d1` **within the hour**, because the operator had already sent `6bfe0cd` carrying the wrong version — a retraction that arrives after the counterparty acts is worth much less than one that arrives before. Files: `scripts/vix_conditioner_stage_decomposition.py`, freeze `relays/FORGE_CORRECTION_we_do_NOT_under_emit_...md`; commit `2a0bc2a`.

**↳ 2026-07-31 — DAY-1 TWO-LANE READ: supply leg CONFIRMED (z=+5.59), tail lane holds 4.42× on a clean artifact window, and the trend leg's REGISTERED CRITERION IS DEGENERATE → resolution moved to POOLED at a PRE-COMMITTED n (analysis only; NO code / grammar / determinism / DB change).** 17/17 batches ran both lanes at full slots; service `active`, NRestarts=0. **Supply leg (`4d1fa832789f` prediction 2) CONFIRMED** on the per-batch journal metric this entry flagged in advance: trend configs/batch mean **76.7 (57 batches) → 90.1 (17 batches)**, share 32.0% → 37.5%, **Mann-Whitney z = +5.59**, and only 19% of prior batches reach the new minimum. **Tail lane, first CLEAN `sharpe_baseline`-only window** (the D339 fix live for 24h): **5.670% vs 1.284% = 4.42×, z = +6.31**, comp% higher too (36.6% vs 24.4%) — the corrected attribution survives on uncontaminated data. **QUALITY LEG — the criterion we registered cannot be read.** Pooled trend-restricted is strong (trend_lane 2.680% = 26/970 vs merit 0.597% = 2/335, **4.49×, z = +2.27**), but the registered per-batch form returns 7/10 ≥1.25× with a **median ratio of 0.33**. The contradiction is **structural and computable without the outcome**: merit's trend arm carries **~19.7 decided/batch** at a 0.597% strong rate → **E[strong] = 0.118**, **P(0 strong) = 0.889** predicted vs **15/17 = 0.882** observed. One component moves merit's rate by 5.1pp, so the per-batch ratio measures **whether merit got a lucky 1**, not the trend arm's performance; the only two finite ratios (0.33, 0.36) are precisely those two batches. **Our error, named:** the form was copied from the MR lane where the merit arm had 95 slots across all hypotheses; at 55 slots its trend subset is ~20 rows, which cannot resolve a 0.6% base rate. **DECISION (operator: "let it accrue and resolve pooled"), PRE-COMMITTED BEFORE THE DATA MATURED:** resolve the quality leg **POOLED**, at the **unchanged ≥1.25× registered bar**, on the **FIRST read once the merit trend-restricted arm reaches n = 700 decided** (~36 batches, ~26h out; expected z ≈ +3.3 if rates hold). **Fixed n, single read.** Resolving "once z is big enough" would be **optional stopping** — the same class of error as the D339 attribution, and the reason this rule is written down now rather than at resolution time. The **aggregation** changes from per-batch to pooled; the **bar does not**, and the change is recorded as a disclosed post-hoc amendment rather than a silent one. **Design thesis visible in passing:** trend_lane's component rate is *lower* (26.1% vs 30.1%) while its strong rate is 4.5× higher — the mean-vs-tail tradeoff the lane exists for. Files: `scripts/trend_lane_arm_read.py` (the standing resolution tool), `STATUS.md`.

**↳ 2026-07-31 (later) — `hurst-mr-conditioner` is NOT the same mechanism, and the controlled contrast makes the conditioner finding NARROWER: it is `vix_term_slope`-specific, not double-gating (analysis + relay only; NO code / grammar / determinism / DB change).** Operator: "check if hurst-mr-conditioner is the same mechanism". **Answer: no, on both role and hypothesis.** The registry entry is *hurst as a regime gate on MEAN_REVERSION* (converts ~1/7 of the MR baseline, [[D313]] binding, MR-ONLY); ours is *vix as a SECOND gate on xsect TREND over a hurst primary*. **The better result came from the natural follow-up:** is the damage from vix, or from occupying the optional second-gate slot at all? That question matters more than the conditioner, because the regime VETO shares the same slot at `_REGIME_VETO_SHARE = 0.5` — **four times** the conditioner's 0.125. Controlled contrast, same base (xsect trend, hurst primary, non-capitulation directional), **ranker-unbiased arms only**, grammar ≥ v49:

| second-slot occupant | n | comp% | mean cpcv | z vs baseline |
|---|---:|---:|---:|---:|
| `hurst` alone (slot unused) | 1,470 | 27.4% | +0.1552 | baseline |
| `hurst` + `days_since_jump` **veto** | 773 | **37.8%** | +0.2276 | **+5.04** |
| `hurst` + `vix_term_slope` **conditioner** | 292 | **12.0%** | −0.0618 | **−5.57** |

**Double-gating is NOT harmful — the veto is one of the better things the sampler does** (+10.4pp at z = +5.04), and the two occupants of the same slot on the same base point in **opposite directions with near-equal force**. The finding narrows to `vix_term_slope` as a trend conditioner; the hurst base is healthy and the veto design is vindicated. **Crucible's MR-only scope guard on `hurst-mr-conditioner` is INDEPENDENTLY CORROBORATED** by our unbiased data (their note says trend × hurst is above baseline and a top yield cell; we measure 27.4% alone / 37.8% with the veto) — the restriction is load-bearing, not cautious. **Correction to our own `9cb99d1` numbers, disclosed rather than quietly restated:** that relay's 30.7% baseline pooled slot-unused with veto-carrying configs; decomposed, the clean contrast is **12.0% vs 27.4%** (−15.4pp) and **3.2× worse than the veto arm**. Conclusion unchanged, mechanism sharper. **NEXT, and it is Crucible's call under the [[D320]] split of authority:** this is a candidate refutation-registry entry (`vix-trend-conditioner`, `deprioritize`) which *they* author and our `BINDINGS` table would route — relayed with an explicit scope warning that vix must stay live as an R2 **primary** gate (the D276 coin, ~1,171 configs, un-implicated) and the hurst base must not be touched, since a broad `vix` entry would repeat exactly the error their own MR-only guard was written to prevent. Files: `scripts/second_gate_contrast.py`, freeze `relays/FORGE_it_is_vix_specific_NOT_double_gating...md` (`470973a`).

**↳ 2026-07-31 (later²) — `vix-trend-conditioner` UPGRADED to `deprioritize` by Crucible, and we DECLINE TO BIND IT. The benefit prices at 0.01% of strong production, ~90% of it falls on the two UNBIASED MEASUREMENT arms, and binding would starve the re-test their own unlock condition names (decision-not-to-act; NO code / grammar / determinism / DB change).** Sequence: our `3a46d66` (the `search_n_trials` mechanism) → their `856d07f` — they **verified our mechanism on their own ledger rather than taking it on description**: across 304 v51 slot-batches, configs differing ONLY in regime gate carried an identical `search_n_trials` in **304 of 304, zero disagreements** (one `trend/swing_mid/xsect` batch had 5 distinct regime-gate sets and exactly 1 stamp value). They upgraded the entry to `generation_effect: deprioritize` (registry hash `40e590632fbc0704`), **adopted our slot-eliminating-vs-within-slot rule edit verbatim**, and changed the entry's unlock from *evidence independence* to ***a working assembly-value score***. Their ask: "bind it whenever you are ready."

**FIRST FINDING — the existing verb would do the OPPOSITE of the entry.** `deprioritize_regime_gate` feeds `deprioritized_gates` into `_pick_regime` (`sampler.py:1274`), the **PRIMARY** regime draw. Binding `("trend_continuation", "vix_term_slope")` with it would suppress **vix-as-primary** — the [[D276]] coin, ~1,171 configs, the one construct both sides explicitly agreed to protect — while leaving the conditioner draw (`sampler.py:1437`, which reads `_VIX_CONDITIONER_SHARE` with no refutation input) completely untouched. It would have shipped looking correct. Binding this entry therefore requires a **new `BindingKind`** — precisely the "predicate/binding type" CLAUDE.md names as a stop-and-ask structural choice.

**SECOND FINDING — and the reason we are not building it. The benefit is ~zero.** Priced over the 106-batch v51 cohort, a ×0.25 binding reclaims **1.59 configs per 240-config batch (0.66%)**:

| arm | cond/batch | saved/batch | what the arm is |
|---|---:|---:|---|
| `prefilter_sample` | 1.56 | **1.17** | the D335 grammar-honest RANDOM draw the freeze criterion reads |
| `holdout` | 0.35 | **0.26** | the D256 UNBIASED arm that breaks the censored feedback loop |
| `ranked` | 0.16 | 0.12 | production |
| `trend_lane` | 0.06 | 0.04 | production |
| `tail_lane` | 0.00 | 0.00 | production |

**~90% of the "benefit" lands on the two arms whose entire purpose is unbiased measurement.** In the lanes that actually produce it is **0.16 configs/batch**; at the alternatives' strong rate (veto 0.65%, slot-unused 0.54%, conditioner 0/292) that is an expected **0.001 strong components per batch against ~9.7 produced — a 0.01% improvement**.

**WHY it is this small: the ranker already did the job** (24× de-selection on v51, 0.0046 vs the 0.1121 unbiased share). A generation-side suppression is fixing what selection has handled for weeks. **The irony is exact: the same within-slot property that made binding SAFE for `search_n_trials` is what makes it POINTLESS** — it does not shrink the search, it redirects it, and the ranker was already doing that redirection everywhere it matters.

**AND THE COST IS NOT ZERO.** (1) A new `BindingKind` is permanent structural surface. (2) Goldens re-pin with genuine rng divergence — the conditioner and veto are mutually exclusive draws on the same slot, so a config that stops firing the conditioner then *takes a veto draw* and the stream diverges from that point, not just the emitted signal. (3) **Decisive: it starves the re-test their own unlock names.** With the entry unlocking on "a working assembly-value score", suppressing the cell ×4 now means that when their Phase-0 successor lands we would have ~4× less conditioner data to re-test with — and the data lost is exactly the unbiased-arm data that made this whole analysis possible. **Binding actively works against the entry's stated unlock condition.**

**DECISION: leave the entry UNBOUND.** Per the module contract, *"an entry with no binding routes nothing"* — the knowledge stays registered on both sides, neither system re-tests the cell blindly, and we keep full measurement resolution. **REVISIT IF:** the ranker stops suppressing it (watch the ranked-arm conditioner share, currently 0.0046) or their assembly-score successor lands and the re-test disagrees. Relayed so they are not left expecting a binding. Files: `scripts/vix_conditioner_stage_decomposition.py` (binding-price table added so the decision is reproducible), freeze relay.

**Provenance disclosed to Crucible:** `ed41e1ba697333d5`, the 1.5438 MR/swing_mid v51 leg in their new promoted book `133fa069`/`ba005efa`, is a **`tail_lane`** config (batch `a2052fa7`, 2026-07-28T01:11Z) — the first promoted-book component from the two-leg ranked lane rather than the merit lane. Honestly: that batch falls inside the `7ecb869d` window, so it was ranked by the **wf_p10** artifact. The other five new legs are all merit-lane `ranked`.

**Also fixed: a ~3% suite flake** that would otherwise erode the deploy ritual. `evaluate_shadow` ORDERs BY `forge_candidate_id` and `_held_out_platt_ece` splits that result by **index parity**; the fixture assigned `uuid4()` ids, so row order was a fresh random permutation each run and ~3% of runs put all 6 positives of the 120-row fixture in one half, degrading the estimate to `None` and failing `test_held_out_platt_reduces_ece_vs_raw` with nothing in the output to explain it. Insertion-ordered ids make the split deterministic. A full-suite gate is only a gate if an unexplained failure is not routine.

**Alternatives considered.** (1) *Re-resolve the prereg as refuted* — rejected: the registered criterion is per-batch strong-component rate ≥1.5×, it reproduces at 60/62, and refuting a claim that held would be as wrong as the original over-attribution. (2) *Leave the prereg text alone and note the defect only in STATUS* — rejected: the prereg registry is the record downstream decisions read, and an uncorrected attribution there is the thing that propagates. (3) *Assert `base_target` matches at the lane-construction site* — rejected as dead code: the loader now filters, so the assertion is unreachable; the test is the durable guard. (4) *Answer Crucible's §2 from the code comments* — rejected: they had been wrong on specifics four times in a week while right on mechanism, and so had we; the answer is measured on emitted configs.

**Files.** `tests/unit/test_ranking/test_tail_model.py`, `tests/unit/test_ranking/test_evaluation.py`, `scripts/tail_lane_model_era_split.py`, `scripts/resid_vix_construct_split.py`, `config/preregistrations.jsonl`, `~/proj/freeze/relays/FORGE_your_Q57_mapping_is_wrong_in_TWO_directions_the_pilot_window_holds_3_configs_2026-07-30.md`, `STATUS.md`. Commits `2e7b738`, `a35362f`, `b656399`; freeze `6bfe0cd`. No grammar, determinism, DB-schema, contracts or unit change; no restart.

## D340 — 2026-07-31 — v51 → **v52 DEPLOYED**: CAPITULATION RETIRED (D328 freeze programme, second prune) + the freeze criterion's binding condition RE-SPECIFIED on the honest arm + an INCIDENT: a grammar commit SELF-DEPLOYS on the live tree

**Decision.** Three things, in the order they were found. (1) The **freeze criterion's condition (C) was void** and is re-specified on the honest arm — and on the corrected reading **the grammar is NOT exhausted**. (2) The metric-B **bar is set** at ≤1.00% of current flow, stable over 7 census runs. (3) **`momentum` is retired as a `mean_reversion` directional** along with the R1 bare-drop exemption that served it — deployed as v52 after Crucible confirmed the close-out on their own ledger.

**(C) WAS VOID — the collider basis, again.** It measured CPCV on `measurement_basis = 'fullhist_refit'`, i.e. **stage two**. Written 2026-07-22; three days later [[D337]]/[[D338]] established that stage-two admission **is** the refit trigger, so conditioning on it is a collider that can sign-flip an estimate. (C) was never revisited, and the error is not theoretical: re-measured at n ≥ 300/version the two bases **disagree in sign** — stage two v39→v51 median 0.2945 → **0.4287** and p90 0.7260 → **0.8965**, both *rising*, while the original text read "*best figures are the oldest*" off that same series. Stage one v18→v51 declines −0.06, but only as an endpoint comparison across a deep U (median bottoms at −0.026 in v28). **And stage one is not the fix either** — "all decided" is ranker-selected.

**RE-SPECIFIED on the D335 honest arm** (`selection_mode='prefilter_sample'`): a uniform draw from prefilter-**rejected** configs, the only population unselected by *both* prefilter and ranker, and therefore a **lower bound** on the grammar surface — the conservative direction for an exhaustion claim. Two conditions, and **the tail is the binding one**: median convergence is *necessary but not sufficient*, because promotion is a tail event and spearman(cell mean, cell std) = −0.148 vs spearman(cell P(≥1.0), cell std) = +0.500. **A median-convergence argument can never establish exhaustion** — the defect beyond the basis, and the mean-⊥-tail lesson from the two-leg lane landing on the freeze criterion.

**AND ON THAT READING (C) IS NOT MET.** The recorded claim was n=937, max-ever **1.3125**, **0.00%** clearing the 1.5 gate → *"more n cannot move it; only a different GENERATION SURFACE can."* At **n=7,484 (8×)**: **max 1.6629** and **2 configs clear 1.5**, both real, xsect, non-degenerate (227 and 425 trades) — one a **component** at 1.6629, produced by a config **our own prefilter rejected**. The centre converged; **the tail did not**, and the *same* surface produced it once the sample was large enough to reach it. Honest caveat recorded rather than smoothed: the pooled honest median (0.1990) does not reconcile with the recorded 0.3521 and the original script is unavailable, so neither is treated as authoritative — the gate-clearer counts are what the section rests on. **Tracked separately:** a prefilter false-negative at the top of the distribution is a different problem from exhaustion.

**(B) BAR SET at ≤ 1.00%**, stable over 7 consecutive census runs; series recorded first per the pattern (2.27 pre-v47-prune, then 0.69 0.69 0.63 0.58 0.74 0.74 0.37 0.29 0.34 0.40 0.42). The ~2.4× headroom over the recent band is deliberate: a genuinely new cell enters as `unevaluated` and becomes `dead_unprotected` the moment it accrues honest evaluations without a component, so a bar at the recent band would fire on healthy exploration — the v17 cold-start mistake in a different hat.

**(A) THE PRUNE.** Verification turned one census-flagged cell into the whole family: all-time, `swing_mid/named/(nogate)` 404/395/**0** (median CPCV **−0.3142**), `swing_short/named/(nogate)` 126/122/**0** (**−0.2621**), `swing_mid/named/rv_rank` 89/86/**0** (no CPCV values at all — those die at earlier gates). **619 submitted, 603 decided, 0 components, 0 promotes.** The v31 rv_rank lineage was already condemned by Crucible (69/69 dead); v35 replaced it with a bare drop and **no** replacement gate; v36 veto-froze the pane *"until the v34-vs-v35 pane is read"*. **That pane has now been read by accumulation.**

**THE GENERALISABLE LESSON: the intermediate signals lied.** v35's bare-drop improved median OOS trades 4 → 13 and WF-zero 97.3% → 70%. Both improvements **held**. Neither produced a single component. Trade-count and WF-zero gains are not evidence of component production — and *those* were exactly the metrics that looked like the v31 generation defect lifting.

**MECHANISM.** Two tables in `custom_predicates` go empty: `_C2_HYPOTHESIS_EXTRA_IDS` (the D270/v31 per-id carve-out) and `_R1_GATE_EXEMPT_DIRECTIONALS` (the D280/v35 bare-drop). Both were operator-approved **loosenings** (OPEN_PROPOSALS `e9d74318`, `4d35a046`), so withdrawing them restores the base rules — a **tightening** under hard rule #4 — and **R1 is whole again**: every `mean_reversion` config now carries a regime gate. Rules text unchanged (the D098/v5 emission-policy class).

**EMISSION PROOF, and a control I got wrong first.** The initial control loaded the archived `v51.yaml` — **invalid**, because these are *Python constants*, not grammar.yaml data, so both arms ran the edited table and "proved" a no-op. Redone by patching the tables in-process against the **live** registry: `momentum` in MR's directional pool **True n=12 → False n=11**. Exactly one directional removed; the converting core (rsi, bb_pct, keltner_pct…) intact. **Goldens:** the v31 cold-start golden retires into the v29 one it now equals — with the carve-out gone, a registry that *serves* `momentum` enumerates **byte-identically** to one that does not. An id truly out of the grammar is one whose presence in the registry is undetectable in the output. No other golden moves; the v29 goldens pass untouched.

**A VACUOUS TEST, caught before the edits landed.** The new v52 test file initially used `minimal_registry_snapshot()`, which does not serve `momentum` — so every emission assertion passed green *before* anything changed. Switched to `_v31_registry`, after which 4 of 5 failed correctly and passed after the edit. Three sampler tests were **inverted to assert unreachability rather than deleted**, because `momentum` still carries live `trend`-family registry flags and only these two tables keep it out; a deleted test cannot catch silent re-admission.

**CRUCIBLE CONFIRMED IT INDEPENDENTLY** (freeze `319ef67` → `08092fe`): **630/613/0** against our 619/603/0, same three cells, medians agreeing to **four decimals** on swing_short (−0.2621) and three on swing_mid, `rv_rank` cpcv-less as claimed, the ~2% delta explained one way. Clause two met **unarguably** rather than our hedged "arguably": six legs entered promoted books since the exemption at 1.3352–1.5526, **all six above the cell's best-ever 1.1598**. Their `capitulation-bounce-v31` entry moves `caution_not_refuted` → **`refuted`/`blocklist`** (hash `c3ab17ee52d447be`) — and it **discharged on its own named condition**: the entry had said "do NOT blocklist on the v31 record" and *named* the v35 bare-drop as the cohort that would settle it. **A caution with a named discharge condition is worth more than a refutation without one.**

**THEIR CORRECTION, which confirms the lane rather than changing it:** **381 of 381** post-v47 MR/named configs are `momentum`, so the retirement **zeroes the slot** rather than redirecting within it — the class the slot-eliminating boundary rule *does* bite. It therefore ships as a **grammar retirement, NOT a BINDINGS row**, and the independence bar is met by the **pre-registered close-out condition** (set at the 2026-07-21 exemption, before the episode that failed it), not by a pattern mined from current supply.

**RECORDED FOR ANYONE WHO REOPENS THIS AXIS:** the cell's best-ever **1.1598 is ABOVE the 0.9439 book-usability floor and it still converted 0**. It does not fail for want of raw CPCV, so *"it clears the floor"* is not sufficient evidence next time.

**⚠️ INCIDENT — A GRAMMAR COMMIT SELF-DEPLOYS ON THE LIVE TREE.** The first v52 commit was written as "STAGED, NOT DEPLOYED"; **that was already false as it was written.** The daemon re-reads `config/grammar.yaml` **every loop iteration**, so committing the file deployed it — 19 iterations stamped `grammar_version=v52` against a standing operator instruction to hold. **Worse than premature, it was inconsistent:** Python modules load at process start, so the running daemon (up since 07-29 22:58) still held the *pre-v52* sampler with the carve-out live; any batch shipping in that window would have been **stamped v52 while enumerated under v51 semantics** — corrupt provenance no later analysis could untangle, the same class as the pre-v5 gated-export pollution. **ZERO CONTAMINATION**: last submission 16:09:35Z, commit 16:44:08Z, **0 rows between**; §7.3 backpressure held the stream at 77.5% of its 80% gate throughout — **luck, not design**. Recovered by reverting to v51 (`75c363f`) and preserving the work on branch `v52-capitulation-retirement`. **THE DURABLE LESSON:** CLAUDE.md warns a *reboot* auto-starts the service onto whatever the tree contains; **that understates it** — for `grammar.yaml` the tree **is** the live config and `git commit` **is** the deploy. Staging a grammar change as a commit on the live tree is not staging it: it must land on a branch, or the commit and the deploy ritual must be the same act. The deploy below reflects that — **the stop comes first**, so the re-apply is inert until the restart.

**DEPLOY (v52, ritual reordered).** stop (`failed`/143, the normal SIGTERM path; no worker left — verified via `/proc/<pid>/cmdline` + RSS, not `pgrep`, per the standing wrapper trap) → re-apply `b72c4a8` → **full uncontended suite 2,097 passed / 1 skipped / 0 failed** → start → verify. **Live:** `active/running`, **NRestarts=0**, `grammar_version=v52`, `registry_hash=6ea47c05c9eafc9e`, all 8 FORGE_* flags present, **0 errors / no traceback / no `extra_forbidden` / no `literal_error`**. Contracts unchanged; no unit change (no `daemon-reload`).

**Files.** `config/grammar.yaml` (+archive `v52.yaml`), `src/forge/grammar/custom_predicates.py`, `docs/proposals/grammar-freeze-criterion.md`, `tests/unit/test_enumeration/test_v52_capitulation_retirement.py` (new), `test_sampler.py`, `test_v36_exit_duration_priors.py`, `test_v40_mr_timer_cell.py`, `test_v47_single_name_retirement.py`, `tests/integration/test_v1_grammar.py`, two capitulation-only test files deleted, `config/preregistrations.jsonl`. Prereg **`0a5ddc861aae`**. Commits `f4ac9e0`, `d78d1f7`, `75c363f`, `b72c4a8`; freeze `319ef67`. **NEXT:** first-batch emission proof (0 momentum-MR / 0 single-name trend-MR / 0 gate-less MR), `funnel --compare v51 v52`, resolve `0a5ddc861aae` on the post-cut cohort, and metric B expected 0.42% → ~0.

## D341 — 2026-07-31 — CAN WE MEASURE EXHAUSTION? The tail statistic is unresolvable, per-CELL production is NOISE, and the answer is a concurrent GENERATION A/B (Tier 0 + Tier 1 built; A/B and honest-arm ramp DEPLOYED)

**Decision.** The freeze programme's exhaustion question is re-grounded on what can actually be *measured*, and the generation side gets the concurrent-arm instrument the ranked lanes already had. Three findings, each of which corrected the one before it.

**FINDING 1 — the tail statistic we re-specified (C) on cannot be read.** [[D340]] re-specified condition (C) on the honest arm with the 1.5-gate exceedance rate as the binding half. A power assessment (`scripts/exhaustion_power_assessment.py`) says that criterion can be neither satisfied nor refuted: detecting a **doubling of P(cpcv ≥ 1.5) needs 183 days per arm on BOTH stages.** What resolves in a decision horizon is the **p90 quantile** (+0.05 in ~3 days) and the **book-floor exceedance rate** (doubling in ~4); p99 is already too thin (52–160 days). **So D340's re-spec was right about the BASIS and wrong about the STATISTIC** — it replaced an unmeasurable-because-collider criterion with an unmeasurable-because-rare one, and "not yet exhausted" would have held by construction rather than by evidence.

**FINDING 2 — the `unevaluated` class is not an exhaustion frontier.** It was raised as one (10.8% of all-time multiplicity, "never had a fair hearing"). It decomposes to **1.26% of CURRENT flow**, of which **92.8% is the `named` axis retired at v47/v52** — the aging tail of retirement, not live territory. The only genuinely unexplored cells are **two**, both MR × `hurst`, i.e. the cell Crucible already refuted (`hurst-mr-conditioner`) and we already deprioritise ×0.25. **There is no large pool of unmeasured grammar to go measure**, which is a cleaner position for the programme than the one it replaced.

**FINDING 3, and the load-bearing one — per-CELL production is statistically NOISE.** A chi-square dispersion test over the honest arm at `(hypothesis, directional, bucket, regime)` granularity: **X²=38.9, df=37, z=+0.29 — not distinguishable from a single common rate.** The top cell was 1-of-41 with a 95% CI of **[0.43%, 12.60%]**, and a 0-of-96 cell has a CI that *includes* the pooled rate. **The Tier-0 framing of "22 zero-production cells are re-weight-away candidates" was reading noise as signal** — the same error class as the `unevaluated` misread the same afternoon, and as [[D339]]'s: treating absence of events as evidence of absence. Signal exists at exactly two granularities:

| granularity | groups | z | verdict |
|---|---:|---:|---|
| cell (h, dir, bucket, regime) | 38 | +0.29 | **noise** |
| hyp × directional × bucket | 14 | +1.16 | noise |
| **hyp × bucket** | 4 | **+2.02** | **signal** |
| hyp × directional | 9 | +1.14 | noise |
| **regime gate alone** | 12 | **+2.16** | **signal** |
| bucket alone / hypothesis alone | 3 | +1.04 / +1.14 | noise |

**Hypothesis ALONE is noise**, so "trend produces better than MR" is not a claim our data supports; **hyp × bucket is signal**, and trend/swing_long produces at 0.94% against trend/swing_mid's 0.28% — a 3.4× difference that tracking "trend" as one category would average away. That is the operator's per-category instinct confirmed, at the granularity the data licenses rather than the one that felt natural.

**A CORRECTION TO OUR OWN CENTRE-vs-TAIL FRAMING.** "The mean carries no information about tail production" had been quoted repeatedly off spearman(cell mean, cell **std**) = −0.148 — a *different quantity*. Measured directly: spearman(cell median, P(≥floor)) = **+0.389**, spearman(cell p90, P(≥floor)) = **+0.654**. The centre is positively related to production, just weakly enough that its extremes decouple — three of the five highest-median cells produce **zero** book-usable output while the best producer sits at median 0.1250. So centre-based optimisation would have steered into cells that produce nothing, but not for the reason we had been giving.

**WHAT WAS BUILT.**
- **Tier 0** (`honest_cell_scorecard.py`) — ranks cells on production and prices a prune by post-stratification. A tightening is a strict subset, so "what would p90 be without cell X" is answerable from data already held; concurrent arms are only needed for *loosenings*. (Its own first output exposed a defect in itself: truncated labels merged distinct cells into what looked like one repeated row.)
- **Tier 1** — the concurrent generation A/B. `sample_config` is UNTOUCHED: the iterator draws a seeded coin per config and passes whichever regime-gate map that arm uses into the existing `regime_gate_yield_weights` parameter. The coin rides a **separate seed stream**, so enabling the A/B cannot perturb the enumeration draw; with it off **no coin is drawn and no rng consumed** — byte-identical, asserted directly. Tagged via contracts 1.39.0 `generation_arm`, shipped for the parked prior A/B and **never emitted until now**. Hash-excluded, which is the precondition rather than tidiness: a hash-bearing tag would make an identical config drawn by both arms dedup into two strategies and the A/B would measure *dedup*. Absence maps to unset, never to the control arm.
- **Arm B's weights** (`book_usable_weights.py`) — regime gates scored by book-usable rate on the **honest arm** (the incumbent learns from ranker-selected runs, a collider). Shrinks to the **regime marginal** below n=100, which is Finding 3 made structural. A barren gate is de-emphasised to a 0.05 floor, **never zeroed**: zeroing removes a gate from the draw, which is a *prune* — a grammar decision belonging in an operator-gated version bump, not a map that reloads every batch. Live: 203 cells, ~9× spread, `vol_regime` 2.871 down to `vix_term_slope` 0.308.
- **Tier 1 (c+d)** (`production_by_group.py`) — one instrument, two jobs: `--by arm` resolves the A/B, `--by category` tracks hyp × bucket across grammar versions. **It reproduced a fact it was not built to find:** trend/swing_long reads 0.99% at v49, **0.00% at v50**, 1.05% at v51, with p90 0.6397 → 0.5917 → 0.6542 — v50 being the grammar the operator independently flagged as a bad implementation (the rank_k=5 bias reverted at v51). Honest caveat kept: v50's 0/302 is a wide interval, so the p90 drop is the part of that agreement worth trusting.

**DEPLOYED (two restarts, both full ritual, both clean).** `FORGE_GENERATION_ARM_B_SHARE=0.5` — the clamp maximum and power-optimal split; arm B may never exceed half the stream because an A/B that reallocates most of generation to the treatment has no control. Then `FORGE_PREFILTER_SAMPLE_N` **40 → 150**, time-boxed to this A/B under the unit's own rule (raise only for a NEW question needing honest-arm n). The stream is gating-rate limited, so raising N shifts the MIX not the volume — honest takes `N/(200+N)`, a model that reproduces the recorded N=300 window exactly (600 honest / 400 ranked per 1,000). N=40 → 718 honest/day → A/B in ~6.3 days; **N=150 → 1,851/day → ~2.6 days at −31% ranked**; N=300 → 1.9 days at −52%. 150 is the knee. **Cost named and accepted:** the trend-lane prereg (593/700) slips ~10h → ~14.5h — 4.5 hours on a nearly-finished prereg for 3.7 days on the A/B. Both restarts: full uncontended suite **2,120 passed / 1 skipped / 0 failed**, `active`, NRestarts=0, v52, 0 errors.

**⚠️ STANDING OBLIGATION: REVERT `FORGE_PREFILTER_SAMPLE_N` TO 40 WHEN THE A/B RESOLVES.** At 150 we forgo ~31% of ranked production every day it stays up. The previous ramp needed an explicit in-file warning for the same reason.

**CRUCIBLE, and we owed them one.** Their `3f82f3d` caught that our honest-arm read **pooled stage one and stage two** — reproduced to 3–4 decimals (stage two n=1,863 median 0.3566 vs their 1,856/0.3567; stage one 5,939/0.1338 vs 5,934/0.1340), and our "2 gate-clearers" was **one per stage across two bases**. Their statistical point stands independently: 1-of-1,856 is not distinguishable from 0-of-302, so **D340's "the centre converged, the tail did not" is withdrawn to "no affirmative evidence the tail has converged"** — a weaker and different claim. **We had written the warning against exactly this into the criterion doc hours earlier**; a rule you have to remember is not a control. Their v52-hasn't-reached-us flag was a **timing artifact** — first v52 batch `2dcace4b` submitted 19:03:02Z against their 17:37Z read, stamped correctly, zero mis-stamped rows. Relayed back with the gate-level result (`vix_term_slope` 0-of-548, scoped: it produces at 1.11% paired with `days_since_jump` on swing_long) and with the dispersion finding, since it tells them to discount every per-cell number we have ever sent.

**Files.** `scripts/exhaustion_power_assessment.py`, `honest_cell_scorecard.py`, `production_by_group.py`, `src/forge/feedback/book_usable_weights.py`, `src/forge/enumeration/iterator.py`, `src/forge/cli/main.py`, `deploy/systemd/forge.service`, `docs/proposals/grammar-freeze-criterion.md`, `docs/MANPAGE.md`, tests for each. Commits `5985723`, `709b4c3`, `f2ab891`, `86c6966`, `88f5ac7`, `0f7ee3a`, `6911875`; freeze `9639ece`. **NEXT:** first-batch A/B verification (`generation_arm_ab: ACTIVE`, ~50/50, NOT `arm INERT`), the ~2.6-day arm read, the trend-lane prereg at 700, and the `SAMPLE_N` revert.

## D342 — 2026-07-31 — INCIDENT: a Literal we had READ, quoted, and then violated — ~6h daemon outage, 350 configs rejected at Crucible's inbox, and the §7.3 limiter wedged for a 5-day auto-flush

**What happened.** [[D341]]'s generation A/B stamped `generation_arm` with `"baseline"` / `"book_usable"`. The field is `Literal['prior_on','prior_off']` in `crucible_contracts` 1.39.0. **The adopt note in `contracts_check.py` states those exact two values, and we had quoted that note in a relay the same day.** Every daemon iteration from 17:14 PDT failed with `literal_error`; **340 failed iterations, ~6 hours, zero submissions.** Crucible independently noticed ("newest submission ~6.7h old; queue drained to 4") and correctly guessed it was not their P2 cadence change.

**Why nothing caught it — three independent guards each had a hole, and that is the finding.**
1. **`model_copy(update=…)` does NOT validate.** The stamp wrote an invalid literal into a frozen Pydantic model without complaint.
2. **The test asserted on the unvalidated object.** `test_both_arms_are_tagged_and_present` checked `arms["baseline"] > 0` and passed — green on a value the contract forbids. A test that never round-trips through validation cannot catch a validation bug.
3. **`parse_forward_compatible` does not cover it.** It handles *extra fields*; an unknown *literal value* is the [[D261]] face, which needs `parse_skipping_unknown_literals`. That scar is documented in this repo and the reader still fell through it.

**Blast radius was cross-system, which the local symptoms hid.** Our own DB held 350 poisoned rows breaking every reader — but the same 350 configs had already been written to Crucible's inbox and were **all rejected** (700 files in `inbox/errors/` at 17:14, each with the same `literal_error` reason). So batch `8b77f2ff` could never gate, and §7.3's oldest-batch policy wedged the limiter on it. **The D110 aged-out flush would not have cleared it for `STRANDED_AFTER` = 5 days.** Writing an invalid value is not a local error when the write path is someone else's inbox.

**Recovery**, in order: back up the DB before any write → null `generation_arm` on the 350 rows (verified: 2,000 most-recent rows parse cleanly, 0 poisoned remain) → `FORGE_GENERATION_ARM_B_SHARE=0` with the incident recorded inline in the unit → restart (clean, NRestarts=0) → retire the 350 inbox-rejected rows with the **D110 aged-out sentinel**, the existing mechanism rather than an invented one → outstanding `submitted` rows 0, limiter released. Confirmed restored on batch `3d31d921`: 350 configs, all `generation_arm` null, **0 inbox errors**.

**Durable fix.** The iterator now **validates at the stamp** (`model_validate` over the dumped config) instead of `model_copy`. An unaccepted arm name is now a loud, local failure at the only point that can still fix it, rather than a silent write that detonates in every reader. Two of the D341 tests correctly fail against the current literal — that failure *is* the proof the hole is closed, and they stay red until the contract admits our names.

**The A/B is BLOCKED, not abandoned.** The mechanism, arm-B weights and read tooling are built, tested and unchanged; only the literal blocks it. Per hard rule #2 this is a **contracts gap to surface, not to work around** — repurposing `prior_on`/`prior_off` for a different experiment would have restored the A/B today and left Crucible reading our arms as the parked prior A/B. Needs a contracts widening before re-enabling.

**The lesson worth keeping, because it is not "read the contract".** We *did* read it. The failure was that **three layers of defence all validated the wrong thing**: a copy that skips validation, a test that asserts on the copy, and a tolerant reader that is tolerant of a different failure mode. Any one of them doing a real round-trip would have caught it in seconds. **When a value crosses a system boundary, the test must round-trip it through the boundary's own validator** — asserting on the object you just constructed proves only that you constructed it.

**Files.** `src/forge/enumeration/iterator.py`, `deploy/systemd/forge.service`, DB row repair (backup `~/forge_data/forge.db.pre_arm_cleanup_20260731_230544`). **NEXT:** relay the incident to Crucible (they hold 350 rejected files and diagnosed the symptom; their pre-authorised 300s limiter rollback is NOT needed — the drain was us), and request the `generation_arm` literal widening.

## D343 — 2026-08-01 — chain-inception floors BUILT, grammar bump deliberately HELD at ~0.4% of throughput

**Spec section:** §3 (enumeration policy); hard rules #4 (tightening), #6 (determinism). **Decision:** build `forge/enumeration/chain_inception.py` reading Crucible's `chain_inception_floors_*.json`, and do NOT deploy it. **Why held:** Crucible's own new `pre_inception` failure category already unpinned our §7.3 limiter (all 11 such rows retire via the D240 flush), so the residue is throughput only — ~16 configs/day against ~4,200/day = **~0.4%**, which does not justify a restart two days after one of ours cost six hours. **Why built anyway:** the class REGENERATES (every new listing joins it), so a one-off exclusion needs redoing forever while a filter over their daily export is self-maintaining. **REFRESH, NEVER PIN** — floors move earlier on backfill and the window slides, so the set is recomputed per batch; a frozen list would starve names that became legal again. Emission proof: 220 excluded-name configs of 4,000 → 0, single-name supply unchanged. **The one inference, relayed rather than shipped:** they declared floor semantics but not the window LENGTH; we inferred 5y and verified 5-of-5 on the boundary — and did not deploy on it. That refusal is what caught [[D345]]. Rode the next bump with its own reason ([[D351]]).

## D344 — 2026-08-01 — book read: the promoted set went 2 books → 6, and the frontier is not moving

**Spec section:** §1.2 (Forge is blind to assembly). **Finding:** six promoted portfolios, **12 distinct legs, all Forge-authored**. Champion `aa31532489613849` unchanged. **The dilution is visible in Crucible's own contribution export:** added-leg marginal Sharpe runs +2.84 (corr 0.17) down to **−0.33 (corr 0.66)** and **−0.02 (corr 0.79)** — and the two books that took the negative legs are the worst on wf_p25, wf_p10 and PBO. **Our trend supply is producing near-duplicates of the incumbent trend leg** — a generation-side signal and ours to act on. **Grammar work IS converting at the component level** even while the portfolio frontier sits still: promoted legs span v22→v51, three landing within 10 days. **The collider is in the promoted set itself** — the five newest legs each carry `component` on `fullhist_refit` with a paired `reject` on `standard_window`, so the promoted population is a stage-two population and must never be pooled with stage one. **Checked before claiming a grammar gap — there is none:** the champion's `dsjv45` overlay looked like a shape we cannot emit, but we emit hurst + days_since_jump on trend/swing_long at 2,520 configs/30d.

## D345 — 2026-08-01 — Crucible answers all four asks: the window is PER-BUCKET, and two of ours are refuted

**Spec section:** §3, §7.3. **(1) The window is per-`dte_bucket`** — 1,825d swing_short/swing_mid, **2,555d swing_long**, sliding from `polygon_data_asof`. Our flat-5y inference was verified 5-of-5 on the boundary and was still wrong: **all 49 recorded `pre_inception` failures are 5y-lane runs**, so the check was structurally blind to the 7y trap. 18% of decided volume rides the 7y window, 100% of it trend/swing_long. **(2) Ask 4 REFUTED at n=7,439** — the absolute market-gate decorrelation mechanism is backwards (t=+3.6 wrong-signed, whole-model R²=0.0018); the surviving half is that **percentile-threshold spreads buy zero decorrelation**, an externally-measured dead search axis. **(3) Ask 2 confirmed with teeth** — nothing gates on marginal Sharpe anywhere; §8.7 on the whole book is the only admission gate, so *"redundant supply that assembles into a book still clearing §8.7 gets admitted and dilutes."* This raises the priority of [[D328]]. **(4) Ask 1 lost by measurement, not argument** — see [[D346]].

## D346 — 2026-08-01 — the scale-down argument refuted on a certified rig; the inbook lane's reachability defect found

**Spec section:** §1.2. **Our claim:** `c52c1ab3` dominates the champion once scaled to equal drawdown, since Sharpe is scale-invariant and maxDD is not. **Their measurement:** re-ran it at vol_target 0.105 on a rig that first reproduced the stored card to **0.0 delta on all five metrics**. A 30% size cut moved worst-DD **4.2%** (0.1178 → 0.1129 against a 0.0825 prediction) and wf_median fell **below** the champion's. **Our own "where we would be wrong" clause is exactly what happened** — the drawdown is path/tail structure the vol target cannot see. Pre-commitment made it a one-experiment settle instead of an argument. **Separately, the n=6-from-the-worst-branch mechanism:** the inbook lane extends only books whose every leg resolves in the current honest pool, which carries a metric-era floor — so the champion and all its descendants were **silently inextensible**, and the lane grew its weakest branch because that was the only one it could assemble. **Consequence for our own reading:** every marginal-Sharpe figure we quoted was measured against a base that was *available*, not *good* — correlation survives as evidence of redundancy, dilution magnitude does not.

## D347 — 2026-08-02 — the champion comparison was never like-for-like: the champion has always been tail-OFF

**Spec section:** §1.2. **Finding, from Crucible's own export:** `tail_leg` is null on both hand-queued `explicit` books (champion, `664b137e`) and present on all four search books. So **every search-vs-champion comparison ever made compared different traded units**, including their 07-29 "neither new book beats our champion". `f52a05c8` (the same three legs as `c52c1ab3`, tail-OFF) gives the first matched-unit read: **the champion's cpcv-p25 advantage collapses 0.0543 → 0.0007**, and its advantage reduces to drawdown alone. **Ask 1 does not reopen** — worst-DD is byte-identical across the unit (0.1178 both), so the sizing refutation is untouched. The handicap applied to the whole search lane (~+0.11 wf_median per book); Crucible confirmed no routing ever keyed on the gap (PASS-not-BEAT by §20 design), so it cost narrative, not selection.

## D348 — 2026-08-02 — the mandate picks `f52a05c8`; the champion is INFEASIBLE

**Spec section:** §1.2. QuantIQ ran D306 same-day on Crucible's probe scalars against the coded ceiling `DEFAULT_MAX_DD_CEILING_PCT = 8.0` %-of-NAV: **champion 11.48% NAV drawdown → INFEASIBLE**; `f52a05c8` 6.81% with the higher quantized-sleeve Sharpe (1.899 vs 1.777, and above the champion's best measured arm at 1.863) → **PICKED**. **Our argument did not win this and we do not claim it:** the sizing refutation stands; the flip is budget arithmetic on a *static capital split*, a different object from the vol-target dial. **Struck from our record:** "the champion holds the mandate 27.9 vs 21.5" — that is the retired hand-computed ratio, which Crucible killed as prose and we then re-imported. Our contribution was surfacing a book that had never been compared, and the like-for-like find of [[D347]].

## D349 — 2026-08-02 — two proposal verdicts, and the earnings-manifest row was already shipped

**Spec section:** hard rule #4; §9.1. **`f59812c7` DECLINED** — proposed pruning `(trend_continuation, swing_mid)` on "0 of 243 promoted". Wrong three ways: the statistic is noise (D341 per-cell dispersion z=+0.29; a 0-of-243 CI contains the pooled rate), **the cell supplies three promoted legs**, and per-config `promoted_count` is a dead estimand under book-level promotion. Cannot regenerate — the Q58 guard shipped hours after it fired, and Crucible returns portfolio promotions as `component` not `promote` (4 promotes all-time), so the D218 re-arm hazard is structurally inert. **`682e1abd` CLOSED as already-shipped** — it was implemented in full as grammar v32 and the row read PENDING for three weeks against live code. **A retraction against ourselves:** an earlier note on that row claimed the wiring was unbuilt and byte-identical; the byte-identical claim came from a **tautological measurement** (`_earnings_gated_pool` already applies the intersection, so re-intersecting its output drops nothing). Measured correctly the manifest removes ABNB, ARM, **V** — and Visa proved to be upstream-uncoverable, not a coverage bug (Crucible declined to derive EPS because the only available denominator is today's share count, injecting a monotone error into a seasonal-random-walk estimator).

## D350 — 2026-08-02 — generation A/B RESOLVED: REFUTED, and the interim reversed sign

**Spec section:** §6; `docs/tasks/feedback-change.md`. Prereg `4e369b779ca9` resolved **refuted** on post-cut evidence only. Honest-arm stage-one p90 cpcv: baseline **0.6028** vs book_usable **0.5988**, delta **−0.0039**, bootstrap **P(delta ≤ 0) = 0.5210**; the secondary agrees (book-usable rate 0.97% vs 0.60%). Registered bar fails on both clauses. **The headline is the replication failure:** the disclosed interim at n=1,123/arm read **+0.0723 at bootstrap 0.001**, and the clean unpeeked cohort reads −0.0039 at p=0.52 — same arms, same batches, sign flipped. **Reading post-cut is the only reason it surfaced.** Registered falsifier action applied: `FORGE_GENERATION_ARM_B_SHARE` → 0, incumbent map keeps the draw, and the frozen-weights forward test is NOT triggered (that was the follow-up for a win). **Tooling gap fixed in the same change:** `production_by_group.py` had no cohort-cut filter and did not compute the registered bootstrap at all — it would have produced the cumulative read, the basis we rejected.
