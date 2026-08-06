# Repo simplification — reduce surface, reduce context, protect production

**Status:** PROPOSAL — next-steps plan, awaiting operator sequencing. Nothing here is executed.
**Trigger:** operator, 2026-08-06: *"AI is making a lot of mistakes, I think our repo is too
expansive. Reduce and simplify as much as possible without affecting production; reduce the
amount of context needed to understand the repo."*
**Basis:** a five-track audit run 2026-08-06 (root files/archives, docs/, src/, scripts/+deploy/,
tests/+config/). Every claim below traces to a file:line found in that pass.
**Relates to:** `fable-audit/code-complete-retirement/REPORT.md` (the pre-written post-freeze
retirement plan — Step F below), `docs/proposals/grammar-freeze-declaration.md` (DRAFT, all
three conditions MET 2026-08-06, awaiting operator).
**Lifecycle:** this file is a `*_PLAN`-shaped record — sweep it to `_archive/` when its tranches
have landed (D202/D241 criterion).

---

## 1. Diagnosis — why "too expansive" is producing AI mistakes

The repo's *production core* is healthy and small: `deploy/` is fully live with zero orphans,
the test suite has no fixture blobs and its invariants were written version-agnostically, ruff
`F401/F811/F841` over `src/` is clean. The expansion is almost entirely **records and stale
prose**, and the recent incident history maps onto it directly:

| Recent mistake | Repo cause |
|---|---|
| D362 — the "unsent relay queue" fiction, reported every turn | Relay convention moved to `freeze/relays/` 08-03, but 21 `PROMPT_CRUCIBLE_*` files stayed at root, `RELAYS.md` was never superseded-marked, and `docs/tasks/crucible-handoff.md` still teaches the old convention |
| D361 — argued from solo cpcv while the deciding export sat on our own disk | Volatile state spread across a 559 KB STATUS.md and 702 KB ledger; the load-bearing fact drowned |
| D154 — indicator mis-derivation | An agent read stale `docs/INDICATOR_THRESHOLDS.md` instead of the code |
| D351-class — hook that could never execute | `docs/tasks/quality-gates.md:27,30,32` **still teaches the pre-D351 broken invocation** |
| Any DESIGN-cited work | `docs/DESIGN.md` is the declared source of truth and ~40% of its body is provably wrong (fictional §11 file tree, 3× obsolete ranker weights, 7-filter table vs live 9, 6-table DDL vs live 8, five wrong §3.5 rule bodies) — every wrong line costs an agent twice: once to read, once to un-learn |

Current read-path inventory: **34 root `.md`** (should be ~10 per the `docs/architecture.md`
taxonomy), **~10,800 lines** under `docs/` (37 proposals not listed in any routing table),
**39 scripts** of which 23 are spent one-off research, **STATUS.md 559 KB / 199 blocks**,
**IMPLEMENTATION_DECISIONS.md 692 KB**. The conventions to fix all of this already exist
(D202/D241 sweep criterion, D242/D295 ledger rotation, MANPAGE script-retirement ledger) —
they have simply not been run for 16 days, the longest gap in the repo's history.

## 2. Constraints — what "without affecting production" means concretely

1. **No daemon behavior change without the deploy ritual.** Steps A–D below are docs/records
   and untracked-artifact hygiene only; no restart, no src semantics.
2. **Determinism is sacred.** `auto_tightenings_fingerprint()` feeds `enumeration_inputs_hash`
   (`enumeration/__init__.py:48`, `submission/batch.py:70`) — the empty
   `config/auto_tightened_thresholds.yaml` and its loader **stay**. Any edit inside
   `sampler.py`/`iterator.py` draw paths churns the RNG sequence and is a grammar-version
   event, not a cleanup (the v55 "zero the constant, keep the branch" convention,
   `sampler.py:292-306`).
3. **Archive, never delete, for records** (`git mv` → `_archive/`, D202 mechanic); scripts may
   be deleted with a MANPAGE retirement-ledger row (D241/D295/D298 precedent) since git holds
   them.
4. **Test-enforced doc strings survive every cut**: GRAMMAR.md rule-id headings (pre-commit
   `grammar-doc-sync`), MANPAGE `## COMMANDS` + every-command-mentioned
   (`test_cli_help.py:88`), HOW-TO `## Common situations` + recovery needles, architecture.md
   `§13.1`–`§13.6` needles (`test_phase6_invariants.py:55-83`).
5. **One tranche = one commit**, suite green after each; behavior- or policy-touching tranches
   get a D-entry; pure record sweeps get one collective D-entry (D202 style).

## 3. The steps

### Step 0 — three strays that are open items, not cleanup (do first, small)

| Item | Why it's first |
|---|---|
| `PROMPT_QUANTIQ_new_training_signals_for_the_rankers_2026-08-03.md` (root, **untracked**) | An **unhandled inbound relay** — zero references anywhere in Forge, no D-entry, no STATUS mention. Triage/answer it, then file to `freeze/relays/`. It is also the only root D104 tree-clean violation. |
| `scripts/joint_frontier.py` (**untracked**, written 08-06) | In-flight freeze-declaration instrument. Commit it (it imports `ceiling_record_test.py`, which the declaration cites) or fold its result into the declaration and drop it — but decide; untracked = lost. |
| 4 untracked ACF relays in `_archive/` (2026-08-04/05) | Authored by the `asset-class-feasibility` sibling; **sent and answered** per that repo's ledger, but headers still read "NOT YET SENT". Commit them with corrected banners (they are the only record of that exchange). |

### Step A — root + record sweep (docs-only, zero production risk, ~1 commit each)

1. **Sweep the answered relay pile**: 18–20 of the 21 root `PROMPT_CRUCIBLE_*` files meet
   their own stated archive conditions (5 explicitly ANSWERED in `RELAYS.md`; 3 Q46 relays dead
   since Crucible closed Q46 on 08-03/D364; 9 "held" drafts whose channel no longer exists —
   D362's finding; `V43_DEPLOYED` obsolete at v55). Check `INDEX_crucible_answered.md` for
   `CORR_TO_BOOK_ASK` before moving it; `PATHC_DEBIT_VERTICAL_SIZING` is operator-parked
   (D152) — move with a park-note or leave, operator's call. `RELAYS.md` archives with the pile
   it indexes (superseded by `freeze/INDEX_forge_answered.md`).
2. **Fix the regenerator**: rewrite `docs/tasks/crucible-handoff.md` to point at
   `freeze/relays/` + the two INDEX ledgers. Until this lands, every future relay recreates
   root clutter. (This doc has zero code refs; it is pure convention.)
3. **Rotate the ledgers** (D242/D295 precedent, pre-commit already exempts `_archive/` from the
   large-file hook):
   - `STATUS.md`: July blocks → `_archive/STATUS_2026-07.md`; keep August (~15 blocks).
   - `IMPLEMENTATION_DECISIONS.md`: D201–D300 → `_archive/IMPLEMENTATION_DECISIONS_D201-D300.md`.
     Slightly ahead of the ~1 MB bar — justified by the operator's context directive.
   - `OPEN_QUESTIONS.md`: sweep RESOLVED Q-entries to `_archive/OPEN_QUESTIONS_RESOLVED.md`,
     keep open ones + a grep pointer (same mechanic as the D242 rotation note).
   - **`OPEN_PROPOSALS.md`: DO NOT TOUCH** — machine-consumed (`contract: forge-proposals/v1`,
     QuantIQ's `list-proposals` parses it); rotation explicitly declined by operator at D298.
4. **Archive the stale root reviews**: `AUDIT.md` (self-bannered stale since 06-09),
   `SECTOR_VOL_MECHANISM_RESEARCH.md` + its companion `SECTOR_ETF_XSECT_PRECHECK` relay (D269
   closed; `IMPLEMENTATION_DECISIONS.md:1177` itself says it matches the archived-research
   pattern), `ALPHA_BUDGET_SCOPE.md` (prereg `098ea730d5f2` confirmed+resolved — first repoint
   its two live citers: `scripts/alpha_budget.py:3`, `docs/proposals/path-c-scope-expansion.md:4,12`).
5. **Operator re-verdict** on `GRAMMAR_REVIEW_AND_EXPANSION.md` +
   `LEARNED_SYSTEMS_AND_GENERATION_REVIEW.md`: protected as "live working documents" by
   `docs/architecture.md:118`, but a grammar freeze undercuts an expansion roadmap. Recommend:
   archive on freeze declaration; keep until then.
6. **Sweep terminal proposals**: ~25 of 37 `docs/proposals/*.md` are LANDED / SUPERSEDED /
   REFUTED / DEAD / DEPLOYED with zero code references → `_archive/`. **Keep the 12 cited from
   `src/`/`tests/`** (they are the design-of-record for `ranking/`) and the open ones
   (`path-c-scope-expansion.md`, freeze criterion/declaration). Discriminator: grep-hit from
   code, nothing else.
7. **Restore the taxonomy invariant**: update `docs/architecture.md:105-125` so every surviving
   root file matches a row again, and add a `docs/proposals/` routing row to `CLAUDE.md` +
   `README.md` (5,695 lines currently undiscoverable).

Net effect of Step A alone: root `.md` 34 → ~10; the two session-entry ledgers drop to
current-era size; the relay convention becomes single-sourced.

### Step B — docs truth repair + shrink (docs-only; the core context reduction)

Target: **~10,800 → ~4,200 lines** in the docs read-path. D201 is the precedent for doc-only
DESIGN reconciliation.

1. **`docs/DESIGN.md` 1067 → ~450** — the highest-value single edit in the plan:
   delete §11 (fictional file tree — `architecture.md` owns the map), §9.1 DDL
   (`persistence/schemas.py` owns it), §10.1–10.3 config pastes (`config/*.yaml` own them;
   §10.3 verbatim-pastes weights obsolete since D220); fix "25 rules" → 21 at L367/L1059; fix
   the `PIPELINE.md` path refs at L14-15/L322. Replace the five stale §3.5 rule *bodies*
   (C1/E1/R1/R2/R3) with pointers to `docs/GRAMMAR.md`. ⚠️ **§3.5 text is operator-owned (hard
   rule #1)** — this tranche ships only as an operator-reviewed diff, and
   `docs/STRATEGY_GENERATION_STATE.md` §11 (its known-drift table) gets folded in as fixes in
   the same commit, after which SGS archives (twice-stale-bannered, 0 code refs).
2. **`docs/GRAMMAR.md` 358 → ~230**: strip the per-version accretion (the R1 heading's
   8-version changelog; the 6,233-char single line at L300) to *current rule + one D-link per
   admission*. The evidence already lives in D-entries **and** duplicated in `grammar.yaml`
   comments — 3 copies today. Keep every rule-id heading (sync hook).
3. **`docs/MANPAGE.md` 888 → ~600**: move the four env-knob rationale essays (L140–200) to
   pointers at their D-entries; drop the config-file table (L830-841) for a pointer. Keep every
   command mention (test-enforced).
4. **Fix-in-place, cheap and urgent**: `docs/tasks/quality-gates.md:27,30,32` (currently
   teaches the exact bug D351 fixed); `docs/glossary.md:44` (hardcoded 0.05 weight → pointer);
   `deploy/NEW_BOX_TRANSFER.md` (hardcodes `v22` three times — make version-agnostic: "matches
   `config/grammar.yaml`").
5. **Delete `docs/DECISIONS.md`** (13 lines, empty since inception, self-describes as unused;
   routing already exists in CLAUDE.md + architecture.md).
6. **`docs/INDICATOR_THRESHOLDS.md` 233 → ~90**: keep the SPY distribution tables (the real
   calibration record) + the stale-banner; delete the struck-through §9, the shipped
   "implementation plan", and the self-admitted moving-target id list.
7. **Merge `docs/glossary.md` → architecture.md §Terms** (keep the ~15 genuinely ambiguous
   terms; the rest duplicate architecture/MANPAGE rows). Split architecture.md's two
   unreadable table cells (L42: 2,136 chars; L44: 1,169) into sub-lists — no content loss.
8. **Anti-drift rule going forward** (add one line to CLAUDE.md's doc-routing section): *a doc
   may state where a value lives, never the value* — the CLAUDE.md:117 volatile-facts rule,
   restated at the point of temptation. We deliberately do **not** propose new sync-check
   machinery; the fix is deleting the copies so there is nothing left to drift.

### Step C — scripts + inert artifacts (tracked-file deletes, no daemon surface)

1. **Retire the 23 one-off research scripts** (246 KB, 59% of scripts source; all conclusions
   shipped and D-cited): the tail-target sweep chain (9), winner-prior trio (3 — see Step E1),
   `collider_fix_sweep.py`, the vix/D339 pair (superseded by inline computation in
   `daily_ranker_eval.sh:533`), the freeze-prep six, `target_sweep.py`. Mechanic: delete +
   MANPAGE retirement-ledger rows (the established format). **Keep in place**:
   `second_gate_contrast.py` (cited by the freeze declaration as needing repair) and
   `ceiling_record_test.py`/`joint_frontier.py` (in-flight). `freeze_registered_read.py` is a
   spent instrument wired only to a test — retire script+test together once the declaration
   lands.
2. **Add a 10-line scripts inventory** to MANPAGE §SCRIPTS (16 keepers, classed
   wired/ritual/in-flight) + the standing rule: *a one-off analysis script is deleted with a
   ledger row when its D-entry lands.* 33 of 39 scripts are currently undocumented.
3. **Cache hygiene** (untracked, zero risk): `rm -r scripts/__pycache__` (279 KB, holds `.pyc`
   for July-deleted scripts), the stale `src/forge/feedback/__pycache__/threshold_proposer*.pyc`
   and cpython-314 strays, the 18+ orphan test `.pyc`. Optional: `.mypy_cache` is 25 MB.
4. **pyproject nits**: drop the ~7 mypy flags already implied by `strict = true` (L91-98);
   bump `pytest>=8.0` floor to match installed 9.x. (numpy demotion to dev is possible only if
   its single src import moves to polars — optional, low value.)
5. **`tests/integration/test_v1_grammar.py`**: delete the ~115-line inline version-changelog
   comment block (L90–207) — triplicated with the ledgers and `grammar_archive/`; keep the two
   assertions. Comment-only; suite proves it.

### Step D — DESIGN.md §5.2 note + `forge.service` narrative (operator-reviewed, docs-only)

`deploy/systemd/forge.service` is 18 K and ~95% comment — it has become a second decision
ledger (five `SAMPLE_N` ramp/revert cycles narrated inline). The ⚠️-next-to-the-variable
pattern has **earned its place twice** (D351, D359 reverts fired because of it) — keep the
per-variable ⚠️ obligations, move the *history* paragraphs to their D-entries. Operator-gated
only because the file is the live unit (edit on a branch; `daemon-reload` at next planned
restart — no dedicated restart for comments).

### Step E — src dead code (operator-gated; deploy ritual; each its own D-entry)

Ordered by value ÷ risk. None of these change enumeration semantics; all still follow
stop → suite → commit → restart → verify, batched into one service window.

1. **`src/forge/ranking/winner_prior.py` (352 LOC) + its test + the 3 `winner_prior_*`
   scripts.** Zero production references; its gating flag was never created; prereg
   `916d79109b4d` refuted ("WITHDRAWN-AS-MISCALIBRATED"); proposal marked parked. The single
   cleanest dead unit in the tree.
2. **Micro-cleanups**: the `meta-king` comment at `core/contracts_check.py:43` (last trace of
   D190); consolidate the twice-hardcoded `_DEFAULT_FORGE_DB`
   (`cli/campaigns_cmd.py:26`, `cli/yield_audit_cmd.py:18`); the RETIRED §8.6 tail-clock
   display plumbing (`ranker_model_cmd.py:55-64` + paired-delta path, D285).
3. **D287 experiment-cell reservation (~90 LOC)** — provably a no-op (pin set empty since
   D305; `_reserve_experiment_cells` unreachable). **Operator call**: `campaigns.py` is the
   intended home for future pins, so removal accepts re-adding the mechanism if a campaign
   ever pins a cell again. Minimum-safe variant: delete only `experiment_cells.py`'s
   duplicated `config_cell` extraction.
4. **Arm-B generation A/B plumbing (~120 LOC)** — flag `0`, prereg REFUTED (D351), registered
   falsifier action was "revert to a single map". **Operator call**: `contracts_check.py:209-215`
   deliberately keeps the `generation_arm` field free for the next experiment.
5. **Explicit non-candidates** (look dead, are not): the D206 tighten machinery
   (determinism identity — constraint 2); `young_explore` (~130 LOC dark, but **parked with a
   recommended flip=4**, not abandoned — D316/D367); `FORGE_HONEST_LABEL_SCOPE` (a live revert
   lever, Q59); the version-retirement guard tests (deliberate silent-re-admission tripwires,
   `test_v55_vix_conditioner_retired.py:20-24`, and v55 *imports from* v44); `SyntheticFeatureCache`
   + `_demo_registry` (preview commands + fixtures); `config/grammar_archive/` (provenance
   chain for every config_hash ever submitted — 2.5 MB is cheap, delta-encoding it would add
   design surface to save disk we don't need).

### Step F — the big structural items (post-freeze, or explicit operator priority)

1. **On freeze declaration → execute `fable-audit/code-complete-retirement/REPORT.md`.**
   The trigger it was written for (2026-07-06, "conditional plan, trigger NOT met") is now a
   DRAFT declaration with all three conditions MET. It needs a refresh pass first — some rows
   already happened (threshold proposer deleted D298; several preregs resolved) — then its P0
   tranche alone retires ~2,600 src + ~2,400 test lines and 12 of 30 CLI commands (the entire
   grammar-*change* machinery, which is dead the day the freeze lands). Its §3 KEEP list is the
   overreach line; honor it verbatim.
2. **`cli/main.py` decomposition — the single highest-leverage readability change, and the
   most dangerous.** 3,215 LOC; `_run_one_iteration` alone is 873 lines orchestrating every
   lane, flag, and echo stanza; 16 test files import its private symbols (the README's "~10"
   undercounts), which is exactly why D065/D105/D106 say don't refactor casually. Recommend:
   **do not do this pre-freeze.** Post-freeze, Step F1 shrinks it substantially for free
   (young_explore/arm-B/experiment-cell threading all leave); re-measure then, and if still
   warranted, sequence test-decoupling (public seams) *before* moving any code.
3. **`sampler._UNIVERSE_EXPORT_DIR` lazy resolution** — would collapse 2 of the 3 autouse
   conftest fixtures and the import-order hack. Touches the sampler module (constraint 2
   applies even though it is not a draw path) — bugfix-class deploy, low urgency.

## 4. Keeping it small — the regrowth rules

The repo had all the right conventions and still regrew; each rule below attaches the
convention to a moment where it is checked, not remembered:

1. **Sweep-on-land** (exists, D241): when a D-entry closes a record, the record moves to
   `_archive/` *in the same commit* — the same-commit rule docs already follow.
2. **Relay hygiene**: relays live in `freeze/relays/` + the INDEX ledgers, never at repo root
   (Step A2 makes the task doc say so).
3. **STATUS block discipline** (propose to operator): a STATUS block is ≤ ~10 lines — the
   what/why/state — and the full narrative lives in the D-entry it cites. Today's blocks run
   50+ lines and duplicate their D-entries nearly verbatim, which is why STATUS.md regrew to
   559 KB in 5 weeks. One place per fact.
4. **Ledger rotation at 400 KB, not 1 MB** (amend D242): rotation exists to protect the
   session read-path; 1 MB was calibrated to the large-file hook, not to context.
5. **Scripts ledger rule** (Step C2): one-off scripts die with their D-entry.
6. **Monthly sweep checkpoint**: add "root/`docs/proposals/` sweep + ledger size check" to the
   operator's standing review agenda. Sixteen days without a sweep is how the current pile
   formed.

## 5. Expected impact

| Surface | Now | After A–C | After F (post-freeze) |
|---|---|---|---|
| Root `.md` files | 34 | ~10 | ~8 |
| Session-entry ledgers (STATUS + ledger + OQ) | 1.42 MB | ~250 KB | same |
| `docs/` read-path | ~10,800 lines | ~4,200 | ~3,500 |
| `scripts/` | 39 files | 16 | ~12 |
| `src/` | 29,405 LOC | −~400 (Step E1–E2) | −~3,000 more |
| CLI commands | 30 | 30 | ~18 |
| Wrong-fact surface (docs that must be mentally discarded) | DESIGN ~40%, SGS, quality-gates, NEW_BOX, INDICATOR §9 | ~0 | ~0 |

Steps 0–C are docs/records/untracked hygiene: no daemon restart, no behavior change, executable
as a short series of small commits under the existing sweep conventions. Step D is a comment
move inside the live unit file. Steps E–F are operator-gated code removals with the deploy
ritual, and F is mostly downstream of the freeze declaration the operator already has on their
desk.

Suggested first bite (one sitting, all reversible): Step 0 + A1 + A2 + A3 + the three
fix-in-place items from B4.
