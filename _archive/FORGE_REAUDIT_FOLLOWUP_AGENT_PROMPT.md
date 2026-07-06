# Forge re-audit follow-up — agent brief

> **Status:** READY TO DISPATCH. Self-contained brief for a fresh agent picking up where the 2026-05-18 re-audit left off.
>
> **You are working in:** `/home/aj/proj/Forge` (a git repo, currently on `main`).
> **Pipeline context:** Forge → Crucible → QuantIQ. Forge is the *producer*; Crucible is the *validator*. See `CLAUDE.md` for hard rules, `docs/DESIGN.md` for spec.

---

## What's already been done (don't redo)

A full two-pass audit landed in this session. State as of 2026-05-18 11:45 PDT:

- **Test suite:** 1055/1055 pass; 82/82 invariants pass.
- **Quality gates:** `uv run ruff check src/ tests/` clean; `uv run mypy --strict src/forge` clean.
- **In-flight work:** all committed across D033–D051 (decision log: `IMPLEMENTATION_DECISIONS.md`).
- **`forge.service`:** restarted 2026-05-18 11:36; running D046+D051 code; first iteration reconciled 1000 rows across 29 batches. v2 audit row landed in `grammar_versions` table via D051 self-heal.
- **Audit-fix work landed:**
  - D036 back-fill in `IMPLEMENTATION_DECISIONS.md` (rate-limiter threshold drop 0.80→0.50 from 2026-05-17 — was missing the formal log entry).
  - D046 multi-batch reconciler + oldest-unfinished rate-limit semantics + pre-rate-limit reconcile call. `reconcile_all_pending` in `src/forge/feedback/consumer.py`; `_reconcile_pending_silently` in `cli/main.py`.
  - D051 grammar_versions audit-row self-healing — `ensure_grammar_version_recorded` in `src/forge/feedback/auto_tune.py`; `_ensure_grammar_version_recorded_silently` in `cli/main.py`.
  - Structural invariants for hard rules #2 (no Crucible internals) and #5 (no LLM SDK) in `tests/invariants/test_phase0_invariants.py`.
  - Warn-once logging on silent `QueryError` swallows in `cli/main.py:_load_hypothesis_weights` and `_fetch_promoted_configs`.
- **Parallel-agent commits worth knowing about:**
  - `e5ee53c` — D033–D048: silent-failure fixes, grammar v1→v2, 9-filter battery (added T1.3 `predicted_activations` + T2.6 `signal_correlation`).
  - `6db2be5` — D049 (theirs): T2.3 counterfactual + T2.4 persistent + T2.5 concentration + T2.7 structural-fingerprint wiring + 3047-config re-queue execution.
  - `e85f0d4` — Archived 14 paired CRUCIBLE prompts to `_archive/`; deleted 7 unpaired prompts (work shipped).
  - `27f7af9` — D050: T2.5 swap to real `top_3_trade_pnl_share` metric (Crucible commit `6a57ee5` shipped the metric in the export).
- **Stale, ignore:** `CONTRACTS_V1_2_AGENT_PROMPT.md`, `PHASE_*_HANDOFF.md` files at root (historical).

---

## Findings backlog — fix these, ordered by priority

### P0 — Operational blocker (do FIRST)

**[P0-1] Reconciler blind-spot: decisions older than Crucible's export window are unreachable.**

Forge is pinned on batch `716677d6-7fee-401e-8ff7-59f6e050a20d` (2 rows from 2026-05-13 20:40 — config_hashes `d3132dd21b68e897` and `74f70cc89e449fba`). Crucible rejected both at 2026-05-13 23:44 — verifiable in historical exports `gated_runs_2026-05-14T07:02Z.json` through `2026-05-15T07:03Z.json`. Crucible's gated-runs export is a rolling top-1000 window (`Crucible/scripts/export_gated_runs.py:44` `_DEFAULT_LIMIT = 1000`); those decisions rolled off ~2.5 days ago. D046's `reconcile_all_pending` reads only what's currently published.

**Effect:** 26 batches stay in-flight forever. The oldest-batch rate-limit logic loops on `716677d6` every iteration; loop is alive but starved. No T2.x scaffold has fired since restart (reachable but not triggered).

**Recommended fix (structural):** add an "export-window low-watermark" fallback to `reconcile_all_pending` in `src/forge/feedback/consumer.py:287-340`. When a `submitted` row's `submitted_at` predates `MIN(decided_at)` in the current export, mark it `status='gated'` with a sentinel `crucible_run_id` (e.g., `"unreachable-aged-out"`). Idempotent. Test: `test_reconcile_all_pending_flushes_predates_export_window` + invariant.

**Quick unblock (operator-decision, if you want):** one-time `UPDATE submissions SET status='gated', crucible_run_id='6195bb6b...'` for the 2 known rows. Decision artifacts are documented in this brief; alternatives: stop the service, run the UPDATE, restart.

---

### P1 — Correctness / wiring honesty

**[P1-1] T2.3 counterfactual is functionally a stub at the call site.**

`cli/main.py:592` passes every proposal to `evaluate_counterfactual(proposal, recent_promoted_count=feedback.promoted_count)`. Read `src/forge/feedback/proposer.py:300-334` — it's phase-1 framework: `del proposal` on line ~321; returns `rejection_rate=1.0` whenever `recent_promoted_count > 0`. So in any batch with ≥1 promotion, every proposal gets `counterfactual_rejection_rate=1.0` stamped in `evidence_json`. Operator-facing noise.

**Note:** hard rule #4 is INTACT — `should_auto_apply_proposal` has zero production callers (only tests). This is documentation/honesty, not safety. D049-theirs overclaimed "wired against recently promoted strategies."

**Fix options (pick one):**
- (a) Label phase explicitly — add `evidence_json["counterfactual_phase"] = "1_binary"` so operators can filter the noise.
- (b) Implement the real per-strategy re-validation. The `proposer.evaluate_counterfactual` signature needs `forge_db_path` + the `promoted_configs` list, then re-run the pre-filter battery on each promoted strategy with the proposed tightening and count actual rejections.

**[P1-2] Manual `forge feedback` bypasses T2.3 + T2.5 enrichment.**

`src/forge/cli/feedback_cmd.py:125-126` directly does `for proposal in proposals: append_proposal(...)`. No counterfactual annotation, no concentration analyzer. Same batch processed via the autonomous loop (`_consume_feedback_after_submit` in `cli/main.py:591-650`) vs manual `forge feedback` produces **different** OPEN_PROPOSALS.md entries.

**Fix:** port the T2.3+T2.5 enrichment block from `_consume_feedback_after_submit` into `cmd_feedback`. Both call sites should produce identical OPEN_PROPOSALS.md output for the same input batch.

**[P1-3] Re-queue script doesn't check grammar_version.**

`scripts/requeue_high_value_configs.py` re-queues configs preserving their original `grammar_version` (often v1). Crucible's inbox-watcher validates against the active grammar; v1-only signals reject silently on Crucible's side, invisible to Forge.

**Fix:** in the re-queue script, parse each config's `grammar_version` field and either (a) skip configs with `grammar_version != current`, or (b) re-write the field to current after validating signal compatibility, or (c) at minimum log a per-version count so the operator sees how many v1-era configs are being shipped to v2's Crucible.

---

### P2 — Hardening / known limits

**[P2-1] T2.7 structural fingerprint O(N) per iteration.**

`cli/main.py:380` (`_load_prior_structural_fingerprints`) re-parses every `submissions.config_json` on every iteration. At 4k rows it's milliseconds; at 50k+ it's measurable. Future: LRU cache or incremental computation (only parse new rows since last call).

**[P2-2] T2.3 `recent_promoted_count` is single-batch despite the parameter name.**

The current binding is `feedback.promoted_count` — that's the just-finished batch's count only, not a multi-batch rolling window. Wire a `recent_promoted_count_query(forge_db, since=now-7d)` if you want true "recent."

**[P2-3] T2.5 emits `target="grammar"` proposals that `apply-proposal` can't apply.**

Operator must hand-edit `config/grammar.yaml`. Documented limit per `grammar_cmd.py:246-251`. Worth a CLI hint: when `list-proposals` shows a `target="grammar"` row, suggest the manual yaml-edit + version-bump + `forge grammar revert`-if-wrong flow.

**[P2-4] `Ranker.score` raises on short-circuited reports.**

`src/forge/ranking/scorer.py:27-32` `_REQUIRED_FILTER_KEYS` lists 4 filters; missing any → `ValueError`. Currently safe (ranker only fires on `passed=True`), but the precondition isn't documented. Add a one-line docstring contract: `"requires report.passed == True"`.

**[P2-5] `_run_battery_for_seed` with `forge_db_path=None`** silently disables structural-fingerprint dedup. Add a logged warning when NoveltyFilter is in the battery but `prior_structural_fingerprints` is empty by default.

**[P2-6] Concurrent manual `forge feedback` + running loop collides on DuckDB exclusive lock.** No race per se (one process exits), but operationally relevant. Either:
- (a) Document the constraint in README's "Operations" section.
- (b) Add a `--read-only` flag to `forge feedback` for diagnostic queries.

---

### P3 — Test / invariant gaps

**[P3-1] Hard rule #3 has no dedicated `tests/invariants/` test.**

Hard rule #3: "Never propose grammar relaxations that lower Crucible's promotion gate." Currently leaning indirectly on rule #4 (`apply_loosening` ban). Add a direct check that Forge cannot emit a `StrategyConfig` violating `ABSOLUTE_MAX_PER_TRADE_RISK_PCT` / `ABSOLUTE_MAX_CONCURRENT_RISK_PCT` from `crucible_contracts`.

**[P3-2] Hard rule #1's "21 v1 rules" invariant lives in `tests/integration/`** rather than `tests/invariants/`. Convention drift. Move `tests/integration/test_v1_grammar.py::test_v1_grammar_rule_count_per_category` to `tests/invariants/test_phase1_invariants.py` (or add a sibling invariant test there).

**[P3-3] D051 self-heal lacks an idempotency-under-race test.**

Concurrent `_ensure_grammar_version_recorded_silently` (loop) + `cmd_apply_proposal` / `cmd_revert` (operator-driven) could race in principle. Both serialize via DuckDB but no test proves the audit ordering stays correct. Add a test that simulates two writers attempting to insert for the same `grammar_version` and verifies exactly one row lands.

---

### P3 — Documentation hygiene

**[P3-4] Stale references to DELETED prompt files.**

`e85f0d4` deleted 7 unpaired prompts: `CRUCIBLE_FEATURE_CACHE_AGENT_PROMPT.md`, `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`, `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md`, `CRUCIBLE_EV_DEADLOCK_AGENT_PROMPT.md`, `CRUCIBLE_EMPTY_THRESHOLD_AGENT_PROMPT.md`, `CRUCIBLE_DB_CHECKPOINT_ON_BATCH_AGENT_PROMPT.md`, `CRUCIBLE_TRADE_CONCENTRATION_METRIC_AGENT_PROMPT.md`.

`STATUS.md`, `IMPLEMENTATION_DECISIONS.md`, `OPEN_QUESTIONS.md` carry bare textual references to several of these (e.g., `IMPLEMENTATION_DECISIONS.md:397` cites `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`). A new contributor reading those D-entries will hit dead references.

**Fix:** sweep the three state docs; for each reference to a deleted prompt, append `(see git log <e85f0d4>)` or move the content into an inline appendix.

---

## Still pending operator decisions

**[OD-1] Bulk-reject 19 stale PENDING proposals in `OPEN_PROPOSALS.md`.**

These are pre-D034 auto-tune flood artifacts: 9 tighten-proposals on 2026-05-14, 10 on 2026-05-15, all `trigger=gate_failure_concentration` with `failure_rate=1.00` against Crucible gate metrics (ablation_arm, cpcv_sharpe_p25, deflated_sharpe, etc.). D034's zero-promotion guard suppresses the trigger now; these are stale.

**Suggested action:** one batch operation marking all 19 `REJECTED` with a single rationale line (e.g., "Pre-D034 zero-promotion-regime artifacts; trigger now correctly suppressed. Bulk-rejected 2026-05-18 by AJ."). Touches `OPEN_PROPOSALS.md` (write the rejection markers) and `grammar_proposals` table (`UPDATE status='rejected', decided_at=now(), decided_by='aj-bulk-2026-05-18'`).

**[OD-2] T1.1 / T1.2 from PROMPT_5 — schedule the contracts schema work.**

Both gated on `crucible_contracts` schema changes:
- T1.1: `SignalSpec.direction` field for bidirectional inference.
- T1.2: `SignalSpec.entry_cadence` field for edge-vs-continuous semantics.

Once they land, T1.3 `PredictedActivationsFilter` can tighten (it currently uses conservative phase-1 semantics per `D038`).

Suggested workflow: write a `CRUCIBLE_SIGNAL_SCHEMA_AGENT_PROMPT.md` brief spec-ing both fields + their migration path. Then a follow-up Forge agent wires the new fields into the grammar + samplers + T1.3 filter.

---

## Constraints / hard rules to respect

All work below must honor `CLAUDE.md`'s 10 hard rules. Specifically watch:

- **Hard rule #2:** No imports from Crucible internals. Use `crucible_contracts` only.
- **Hard rule #4:** Auto-tightening can ship without operator approval; auto-loosening cannot. Don't introduce a code path that loosens a calibration or grammar threshold without writing to `OPEN_PROPOSALS.md` for operator review.
- **Hard rule #6:** Deterministic enumeration. The `(grammar_version, registry_version, seed)` triple still produces byte-identical output.
- **Hard rule #8:** No `datetime.now()`, no `random.seed()`, no `np.random.default_rng()` outside `forge.core.clock` / `forge.core.seed`.
- **Hard rule #10:** Grammar yaml changes require version bump + archive copy + Decision Log entry + (now) `grammar_versions` audit row (D051 self-heals this).

Add a **Decision Log entry (next: D052)** at the bottom of `IMPLEMENTATION_DECISIONS.md` for any code change. Use the format of D046 / D051 — Spec section, Context, Decision, Hard-rules check, Alternatives, Verification, Action.

---

## Operating instructions

1. **Read first:** `CLAUDE.md`, this brief, `STATUS.md`, the relevant section of `docs/DESIGN.md`.
2. **Test loop:** `cd /home/aj/proj/Forge && uv run pytest -q && uv run ruff check src/ tests/ && uv run mypy --strict src/forge`. All three must stay green on the changed scope.
3. **For each fix:** TDD — write the failing test first, then the production code. Append a D-entry. Reference file:line citations.
4. **Don't commit unless the operator asks.** Don't push. Don't restart `forge.service` unless you've made a code change that requires it AND the operator has approved.
5. **Surface decisions to the operator** when:
   - A hard-to-reverse action is needed (DB UPDATE, force-push, dependency change).
   - The fix requires a `crucible_contracts` change.
   - The spec is silent or contradictory on the right behavior.
   - Implementation risk:reward isn't obvious.

---

## Recommended order

Tackle the items in roughly this order. Each box is a self-contained PR-sized unit:

1. **P0-1** — reconciler export-window low-watermark fallback. Unblocks the loop.
2. **P1-1** — T2.3 counterfactual: pick (a) phase-label or (b) real re-validation; one D-entry either way.
3. **P1-2** — port T2.3+T2.5 enrichment into `cmd_feedback` for symmetry with the loop.
4. **P1-3** — re-queue script grammar_version check.
5. **OD-1** — bulk-reject the 19 stale proposals (operator confirms first).
6. **P3-1 + P3-2 + P3-3** — small invariants batch.
7. **P3-4** — doc sweep for deleted-prompt references.
8. **P2-1 .. P2-6** — opportunistically, as you touch the relevant modules.

---

## Quick-reference: key file paths

- `src/forge/feedback/consumer.py` — `reconcile_all_pending`, `consume_batch_results` (D046).
- `src/forge/submission/rate_limiter.py` — `check_rate_limit` (D036 threshold; D046 oldest-batch).
- `src/forge/cli/main.py` — `_reconcile_pending_silently`, `_ensure_grammar_version_recorded_silently`, `_consume_feedback_after_submit`, `_load_prior_structural_fingerprints` (T2.7 wiring).
- `src/forge/cli/feedback_cmd.py` — manual `forge feedback` (P1-2 fix target).
- `src/forge/feedback/proposer.py` — `evaluate_counterfactual`, `should_auto_apply_proposal`, `detect_persistent_proposals` (T2.3 + T2.4 frameworks).
- `src/forge/feedback/trade_concentration.py` — T2.5 + D050 dual-path.
- `src/forge/feedback/auto_tune.py` — `ensure_grammar_version_recorded`, `_write_grammar_versions_row` (D051).
- `scripts/requeue_high_value_configs.py` — re-queue script (P1-3 fix target).
- `tests/invariants/test_phase0_invariants.py` — hard rules #2, #5, #8 source-text scans.
- `tests/invariants/test_phase5_invariants.py` — hard rule #4 ban + D051 audit-row land.
- `IMPLEMENTATION_DECISIONS.md` — append next D-entry at line ~1160 (after D051).
- `STATUS.md` — keep the operational state header current.

---

Good luck. The system is healthier than yesterday but the loop is still pinned. P0-1 is the unblocking move; everything else is cleanup or honesty improvements.
