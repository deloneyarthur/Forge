# Phase 5 Handoff: Feedback and grammar refinement

**Status:** complete — **awaiting CLOSE review** (§12 phase discipline; Phase 5 is one of phases 1/3/5).
**Started:** 2026-05-13 (session 5 — Phase 5 kickoff + closure plan)
**Finished:** 2026-05-13
**Sessions:** 1 (single sitting; closure plan → 12 modules + invariants + handoff)
**Budget vs actual:** 10–14 days budgeted (§12); ~1 calendar day actual.

---

## Deliverables (against DESIGN.md §12 Phase 5)

| Deliverable | Status | Notes |
|---|---|---|
| Consumer reads Crucible's gated runs | done | `forge.feedback.consumer.consume_batch_results(forge_db, crucible_db, *, batch_id=None, since=None)` joins `crucible_contracts.get_recent_gated_runs` to `submissions` by `config_hash`. Updates `submissions.status` `submitted → gated`, sets `crucible_run_id`; updates `batch_summaries.promotion_rate / common_failures / completed_at`. Idempotent. |
| Analyzer extracts patterns | done | `forge.feedback.analyzer.analyze_batch(feedback, registry) -> AnalysisReport`. Pure function: gate-failure breakdown, hypothesis metrics, promoted-pattern candidates (hypothesis_dominance + signal_family_dominance ≥ 80% threshold). |
| Proposer generates grammar refinement proposals | done | `forge.feedback.proposer.propose(report, feedback, *, at) -> list[GrammarProposal]`. Three §8.4 triggers: (a) gate-failure concentration (95%+), (b) family/hypothesis dominance, (c) param no-promotion (current-batch-only in Phase 5). |
| Auto-tightening pipeline | done | `forge.feedback.auto_tune.auto_tune(...)` reads rolling 2-batch promotion rate; tighten path applies + writes back `prefilter.yaml` + inserts `grammar_versions` row (`change_type='auto_tighten_calibration'`); cumulative cap 30% enforced structurally. |
| Supervised loosening workflow → `OPEN_PROPOSALS.md` | done | `forge.feedback.proposal_writer.append_proposal` writes `---`-delimited markdown block AND inserts pending row in `grammar_proposals`. Structurally NO `apply_loosening` in any feedback module (invariants enforce). `forge grammar list-proposals / approve-proposal / reject-proposal` cover operator workflow. |

**Tests passing:** 882 / 882.

**Test files added this phase:** 11 (1 per feedback module + 1 ranking + 1 config + 2 CLI + 1 invariants):

```
tests/unit/test_feedback/
├── test_types.py             (29)
├── test_consumer.py          (14)
├── test_analyzer.py          (13)
├── test_promoted_patterns.py ( 6)
├── test_proposer.py          (12)
├── test_proposal_writer.py   ( 8)
└── test_auto_tune.py         ( 9)
tests/unit/test_ranking/
└── test_signal_key.py        ( 9)
tests/unit/test_config/
└── test_forge_config.py      (12)
tests/unit/test_cli/
├── test_feedback_cmd.py      ( 5)
├── test_run_loop.py          ( 3)
└── test_grammar_cmd.py       ( 7)
tests/invariants/
└── test_phase5_invariants.py (15)
```

**Phase 5 total: 142 new tests.** Combined suite: 882 / 882.
**Quality gates:** `ruff check`, `ruff format --check`, `mypy --strict` all clean.

---

## Decisions logged during this phase

`IMPLEMENTATION_DECISIONS.md` entry **D024**.

- **D024 — Phase 5 pre-code closure plan (D1–D11).** Operator approved `1.a..11.a` for all recommended options:
  - **D1** — Consumer signature: `(forge_db, crucible_db, *, batch_id=None, since=None) -> BatchFeedback`. Auto-discovers latest batch when `batch_id` is omitted.
  - **D2** — Analyzer is pure; returns `AnalysisReport`. DB writes to `promoted_patterns` happen in the separate `feedback.promoted_patterns` module.
  - **D3** — Proposer ships all three §8.4 trigger types; (c) operates on the current batch for Phase 5 (Phase 6 will extend to multi-batch).
  - **D4** — Auto-tune writes back to `config/prefilter.yaml` and inserts a `grammar_versions` row with `change_type='auto_tighten_calibration'`. Cumulative cap 30% per direction, enforced by summing prior rows.
  - **D5** — `OPEN_PROPOSALS.md` uses `---`-delimited markdown blocks; every proposal also inserts a `grammar_proposals` row with `status='pending'`.
  - **D6** — `forge feedback [--batch-id | --since]` standalone command + `forge run --consume-feedback` inline hook.
  - **D7** — `forge run --loop` ships in Phase 5: single process, sleeps `--poll-interval-seconds` between iterations, exits cleanly on SIGINT.
  - **D8** — Full `forge.config.forge_config.load_forge_config()` covers §10.1; CLI flags become overrides via `with_overrides()`. Closes Phase 4 OQ-3 and OQ-5.
  - **D9** — Real Crucible-backed FeatureCache **deferred** to Phase 6+ (Crucible hasn't shipped one). `SyntheticFeatureCache` stays.
  - **D10** — `signal.id` → content-hash similarity key (Phase 3 OQ-4 closed). `forge.ranking.signal_key.content_key(signal)` returns a 16-char hex prefix of `sha256(type, role, sorted(indicators), canonical(params))`. Threaded through `jaccard_signal_ids` + `compute_prior_promotion_proximity`. Three test helpers updated to vary `params.key` so their id-based test intent stays valid.
  - **D11** — 12 modules + 1 invariants + 1 handoff build order.

**Contracts version:** No gap. Phase 5 stays pinned to `crucible_contracts == 1.6.0`.

---

## Open questions / spec ambiguities surfaced

1. **§8.4 trigger (c) cross-batch history.** Phase 5 ships current-batch-only for the "param no-promotion" trigger. The spec example ("0 promotions in 200+ submissions") requires rolling-window aggregation. Phase 6 polish: extend `propose()` with a `forge_db` argument that queries the last N batches' submissions and joins by `(hypothesis, dte_bucket)`.

2. **`SyntheticFeatureCache` still in production loop.** D9 deferred the real Crucible-backed cache. Once Crucible ships its registry/feature-cache surface, swap `forge.prefilters.feature_cache` to the real adapter — the Protocol interface is already in place from Phase 3.

3. **`forge feedback` registry source.** The CLI currently uses `forge.enumeration._demo_registry()` for the analyzer's family-lookup. When the real Crucible registry is reachable, swap to `crucible_contracts.get_registry_snapshot(...)` (TBD — contracts doesn't expose that helper today).

4. **`forge grammar apply-proposal` does NOT mutate `grammar.yaml` automatically.** Phase 5 only marks the proposal as `approved` + records operator initials. The actual yaml merge stays a manual operator step so the version-bump + archive + Decision Log entry get human review per §13.2 + hard rule #10. Phase 6 polish may add a yaml-merge convenience under a `--apply` flag with extra guardrails.

5. **`config/forge.yaml` end-to-end wire-up partial.** `load_forge_config` is shipped but the CLI commands (`forge run`, `forge feedback`) don't yet read the yaml's `enumeration.seed`, `submission.batch_size`, etc. as their defaults. Phase 6 will thread `ForgeConfig.with_overrides(...)` into each CLI's argparse layer. For Phase 5, CLI flags carry baked defaults that match yaml values where reasonable.

6. **§6.2 vs §5.3.6 naming carry-forward.** Phase 4 OQ-1 still open: "regime_diversity" weight maps to "regime_exposure" filter. Spec rename is one-line markdown — Phase 6 polish.

7. **`pyproject.toml` networkx mypy override** still unused (carried since Phase 3). Phase 6 polish.

---

## Source inventory — `src/forge/feedback/`

| File | Lines | Purpose |
|---|---:|---|
| `__init__.py` | 33 | Public API re-exports |
| `types.py` | 290 | Frozen dataclasses: BatchFeedback, AnalysisReport, GrammarProposal, Trigger, CandidateOutcome, GateFailureRow, HypothesisMetrics, PromotedPattern |
| `consumer.py` | 230 | `consume_batch_results` (§8.2 + D024/D1) |
| `analyzer.py` | 180 | `analyze_batch` (§8.3 + D024/D2) |
| `promoted_patterns.py` | 60 | §9.1 writer for `promoted_patterns` rows |
| `proposer.py` | 230 | Three §8.4 triggers (D024/D3) |
| `proposal_writer.py` | 90 | `append_proposal` writes OPEN_PROPOSALS.md + grammar_proposals (D024/D5) |
| `auto_tune.py` | 220 | §5.5 auto-tune trigger (D024/D4) |

## Source inventory — `src/forge/ranking/`

| File | Lines | Purpose |
|---|---:|---|
| `signal_key.py` | 30 | content-hash similarity key (D024/D10) |
| `diversifier.py` | (modified) | switched to `content_key` |
| `prior_promotion.py` | (modified) | switched to `content_key` |

## Source inventory — `src/forge/config/`

| File | Lines | Purpose |
|---|---:|---|
| `__init__.py` | 22 | Public API re-exports |
| `forge_config.py` | 130 | `load_forge_config` + Pydantic models for §10.1 |

## Source inventory — `src/forge/cli/`

| File | Lines | Purpose |
|---|---:|---|
| `feedback_cmd.py` | 130 | `forge feedback` (D024/D6) |
| `grammar_cmd.py` | 120 | `forge grammar list-proposals / approve-proposal / reject-proposal` (D024/D11) |
| `main.py` | (modified) | `forge run --loop --consume-feedback`, registers feedback + grammar sub-apps |

Also touched:

- `tests/fixtures/strategy_configs.py` — none (existing fixtures still valid).
- 3 test helpers in `tests/unit/test_ranking/` adjusted to vary `params.key` for content_key compatibility.

---

## What's NOT in Phase 5

- **Real Crucible-backed FeatureCache** (D9 deferred). `SyntheticFeatureCache` stays through Phase 6+.
- **Cross-batch param-cluster trigger** (§8.4 third example needs rolling history; current-batch-only in Phase 5).
- **Auto-merging of approved proposals into `grammar.yaml`** — operator workflow shipped through `forge grammar approve-proposal`; the yaml mutation itself stays manual to preserve the §13.2 review boundary.
- **CLI defaults loaded from `config/forge.yaml`** — loader shipped but `forge run` / `forge feedback` still carry their own defaults; Phase 6 will thread `ForgeConfig` through each command.
- **`pre_filter_logs` retention policy** (carried from Phase 4).
- **DPP diversification** (deferred per §14 decision log, carried from Phase 4).
- **§6.2 "regime_diversity" / §5.3.6 "regime_exposure" naming rename** (carried from Phase 4).
- **networkx mypy section pruning** (carried from Phase 3).

---

## Smoke-test commands

```bash
# Verify all gates
uv run ruff check && uv run ruff format --check && uv run mypy --strict src
uv run pytest -q

# List CLI surface
uv run forge --help

# Single-batch run with feedback chain
uv run forge run --seed 0 --batch-size 2 --max 200 \
    --forge-db /tmp/forge_smoke.db \
    --inbox /tmp/forge_smoke_inbox \
    --crucible-db /tmp/crucible.db \
    --consume-feedback \
    --open-proposals /tmp/OPEN_PROPOSALS.md

# Daemon-loop with --max-iterations cap
uv run forge run --seed 0 --batch-size 2 --max 200 \
    --forge-db /tmp/forge_smoke.db \
    --inbox /tmp/forge_smoke_inbox \
    --crucible-db /tmp/crucible.db \
    --loop --max-iterations 3 --poll-interval-seconds 5

# Standalone feedback
uv run forge feedback --no-config \
    --forge-db /tmp/forge_smoke.db \
    --crucible-db /tmp/crucible.db \
    --open-proposals /tmp/OPEN_PROPOSALS.md

# Operator workflow
uv run forge grammar list-proposals --forge-db /tmp/forge_smoke.db
uv run forge grammar approve-proposal --id <UUID> --initials AJ \
    --forge-db /tmp/forge_smoke.db
```

---

## Review focus (close)

Phase 5 is **close-review** per §12. Suggested focal points:

1. **D024 closure plan accuracy.** Confirm the 11 items match the operator's intent for Phase 5 scope. Items D9 (defer real FeatureCache) and trigger-(c) current-batch-only are explicit narrowings.

2. **§8.4 trigger (c) "param no-promotion" scope.** Spec says "0 promotions in 200+ submissions"; Phase 5 ships current-batch-only with default threshold 200 (so the trigger fires only on large batches). Is this the right Phase 5 boundary, or should the multi-batch rolling window land here?

3. **Hard rule #4 structural enforcement.** `tests/invariants/test_phase5_invariants.py` has 5 tests that grep for `apply_loosening` in calibration / proposal_writer / auto_tune / proposer / analyzer. Confirm no obvious hole.

4. **§5.5 cumulative cap.** The auto_tune module sums step sizes from prior `grammar_versions` rows with `change_type='auto_tighten_calibration'`. If an operator manually edits prefilter.yaml outside this loop, the cap won't see it. Acceptable for v1?

5. **Content-hash key swap (D10).** `jaccard_signal_ids` and `compute_prior_promotion_proximity` now compare on `content_key(signal)` rather than `signal.id`. Three test helpers were updated to vary `params.key` so their id-based test intent stays valid. Confirm the migration is complete (any Phase 6 surfaces that still key on raw id?).

6. **`forge grammar approve-proposal` does NOT auto-mutate yaml.** Phase 5 records `approved` + operator initials but doesn't apply the change to `grammar.yaml` / `prefilter.yaml`. Confirm the intentional manual-edit step is the right human-in-loop boundary.

7. **Daemon-loop ergonomics.** `forge run --loop --max-iterations N --poll-interval-seconds S` is the test-friendly shape. Production usage: `forge run --loop --poll-interval-seconds 600`. SIGINT handling has been tested in `--max-iterations` mode but not in the long-running case; operator may want to validate.

8. **Phase 4 OQ-3 / OQ-5 close-out.** `forge.config.forge_config` is shipped and loads §10.1; but `forge run` / `forge feedback` don't yet read yaml defaults end-to-end (CLI flags still carry baked defaults). Confirm whether this Phase 5/6 split is acceptable or should be fully threaded now.

If any of these surface follow-ups, log them in `OPEN_QUESTIONS.md` rather than blocking Phase 6.

---

## Awaiting

Operator close-review per §12. Phase 6 (Polish + operational discipline) is the next phase; per §12 phase discipline, may begin read-only Phase 6 preparation after 24h with no reply, but no code until explicit "proceed."
