# Phase 4 Handoff: Ranking and submission

**Status:** complete — **awaiting LIGHT review** (§12 phase discipline; Phase 4 is one of phases 0/2/4/6).
**Started:** 2026-05-13 (session 3 — Phase 4 kickoff + closure plan)
**Finished:** 2026-05-13
**Sessions:** 1 (single sitting; closure plan -> contracts v1.6.0 side-trip -> 12 modules + invariants)
**Budget vs actual:** 5-7 days budgeted (§12); ~1 calendar day actual.

---

## Deliverables (against DESIGN.md §12 Phase 4)

| Deliverable | Status | Notes |
|---|---|---|
| Composite scorer | done | `forge.ranking.scorer.Ranker` frozen dataclass; `.score(report, prior_promotion) -> float` applies §6.2 weights with float-drift clamp to [0,1]. |
| Diversification (greedy in v1; DPP optional) | done | `forge.ranking.diversifier.select_top_n` greedy per §6.3 pseudocode; similarity = `jaccard_signal_ids` matching §5.3.5 novelty filter. DPP deferred. |
| Batch queue management | done | `forge.ranking.queue.rank_batch` composes scorer + prior_promotion + diversifier; skips short-circuited reports. |
| Submitter writes YAML to Crucible's inbox | done (JSON per D006) | `forge.submission.submitter.submit_batch` wraps `crucible_contracts.submit_candidate` with D023/D7 idempotency: insert pending → contracts write → update submitted; ConstraintException on duplicate config_hash → skipped_duplicate. |
| Rate limiter watches Crucible's status | done | `forge.submission.rate_limiter.check_rate_limit` cross-references the latest Forge batch's config_hashes against `crucible_contracts.get_recent_gated_runs`. >=80% gated → clear; missing Crucible DB → blocked (conservative). |
| `forge run` performs full cycle (enumerate → pre-filter → rank → submit) | done | `forge run [--seed S] [--batch-size N] [--max N] [--dry-run] [--inbox PATH] [--crucible-db PATH] [--forge-db PATH]`. Single-batch (D023/D6.a); the 10-min poll daemon (§7.3) is Phase 5/6 work. |
| Stops when previous batch is 80% complete in Crucible | done | When `--crucible-db` is provided, `forge run` calls the rate limiter; if blocked, exits with a "waiting" message and exit code 0. |

**Tests passing:** 740 / 740.
**Test files added this phase:** 11 (1 per module + 1 invariants):

```
tests/unit/test_ranking/
├── test_types.py              (19)
├── test_config.py             (16)
├── test_prior_promotion.py    ( 9)
├── test_scorer.py             (14)
├── test_diversifier.py        (16)
└── test_queue.py              ( 9)
tests/unit/test_submission/
├── test_batch.py              (10)
├── test_rate_limiter.py       (10)
├── test_pre_filter_logger.py  ( 8)
├── test_submitter.py          (12)
└── test_cli_run.py            ( 7)
tests/invariants/
└── test_phase4_invariants.py  (11)
```

**Phase 4 total: 141 new tests.** Combined suite: 740 / 740.
**Quality gates:** `ruff check`, `ruff format --check`, `mypy --strict` all clean.

---

## Decisions logged during this phase

`IMPLEMENTATION_DECISIONS.md` entries **D022** + **D023**.

- **D022** — `crucible_contracts` v1.6.0 adds `RegistrySnapshot.data_start_date: date` (required, no default). Forge pin bumped to `"1.6.0"`; 9 RegistrySnapshot constructor sites threaded with `data_start_date=date(2022, 1, 1)`; `permutation_test.py` reads `ctx.registry.data_start_date` instead of the Phase 3 hardcoded anchor. Closes `PHASE_3_HANDOFF.md` open-question item 2.
- **D023** — Phase 4 pre-code closure plan, capturing D1–D8 architectural decisions:
  - **D1** — `compute_prior_promotion_proximity(config, promoted_configs) -> float` = max Jaccard overlap of signal IDs. Empty list → 0.0.
  - **D2** — `Ranker` frozen dataclass loading §6.2 weights once; `score(report, prior) -> float`.
  - **D3** — Greedy diversifier; similarity = Jaccard of signal IDs (matches §5.3.5 novelty).
  - **D4** — Batch size from `config/forge.yaml`; CLI `--batch-size` overrides (defaults baked in; full YAML wire-up is Phase 5/6).
  - **D5** — contracts v1.6.0 side-trip (D022).
  - **D6** — single-batch `forge run`; daemon-loop deferred to Phase 5/6.
  - **D7** — Submitter idempotency: insert pending → contracts write → update submitted; duplicate config_hash → skipped_duplicate (logged, not fatal).
  - **D8** — 12 modules + 1 prep + 1 invariants build order.

---

## Open questions / spec ambiguities surfaced

1. **§6.2 "regime_diversity" weight maps to §5.3.6 "regime_exposure" filter.** Naming inconsistency between spec sections. Ranker reads the filter score under the §6.2 weight; documented inline. Spec-side rename is a Phase 5/6 polish target.

2. **`signal.id` as the prior-promotion / diversifier similarity key.** Same as Phase 3 open-question item 4: real Crucible cache will need a content-hash key for cross-batch comparisons. The function signatures don't change; only the input space does.

3. **`forge run` defaults vs `config/forge.yaml`.** §10.1 says `submission.batch_size: 200` and §6.4 says default 200; Phase 4 CLI defaults to `--batch-size 10` for quick local exercise and `--max 1000` for enumeration. Full `config/forge.yaml` wire-up (so the CLI flags become overrides on top of the YAML) is a Phase 5/6 polish task. Surfaced because the operator-facing defaults differ between code and spec until that wire-up lands.

4. **`promoted_strategies` lookup path.** `_fetch_promoted_configs` in `cli.main` queries Crucible's gated runs and joins to Forge's `submissions.config_json`. The join key is `config_hash`; works for self-submitted configs but not for any externally-injected promoted strategies. For Phase 4 this is correct (Forge only submits its own configs); Phase 5's full feedback consumer can decide whether to widen the source.

5. **Forge DB default location.** CLI defaults `--forge-db` to `:memory:` for safety in dev/test. Operator usage will pass `~/forge_data/forge.db` explicitly. Phase 5/6 may default to the path from `config/forge.yaml` once the YAML wire-up lands.

6. **`pyproject.toml` networkx mypy override still unused.** Phase 3 surfaced this; carries forward as a Phase 6 polish item.

---

## Source inventory — `src/forge/ranking/`

| File | Lines | Purpose |
|---|---:|---|
| `__init__.py` | 28 | Public API re-exports |
| `types.py` | 105 | `RankerWeights` (sum-to-1.0), `DiversificationConfig`, `RankerConfig`, `RankedCandidate` |
| `config.py` | 131 | `load_ranker_config(path)` from `config/ranker.yaml` |
| `prior_promotion.py` | 54 | §6.2 proximity score (D023/D1.a) |
| `scorer.py` | 77 | `Ranker.score(report, prior)` (D023/D2) |
| `diversifier.py` | 100 | `select_top_n` greedy + `jaccard_signal_ids` (D023/D3) |
| `queue.py` | 67 | `rank_batch(ranker, reports, promoted, n)` orchestrator |

## Source inventory — `src/forge/submission/`

| File | Lines | Purpose |
|---|---:|---|
| `__init__.py` | 25 | Public API re-exports |
| `batch.py` | 66 | `mint_batch_id` (deterministic UUID4), `BatchContext` |
| `rate_limiter.py` | 122 | `check_rate_limit` (§7.3, D023/D6.a) |
| `pre_filter_logger.py` | 77 | `record_pre_filter_logs` (§9.1 row-per-filter writer; D021/D8) |
| `submitter.py` | 224 | `submit_batch` wrapping contracts (D023/D7) |

Also touched:

- `src/forge/cli/main.py` — added `cmd_run` (§12 deliverable).
- `src/forge/core/contracts_check.py` — `FORGE_EXPECTED_CONTRACT_VERSION` bumped to `"1.6.0"`.
- `src/forge/prefilters/permutation_test.py` — reads `ctx.registry.data_start_date` (closes Phase 3 OQ-2).
- 9 RegistrySnapshot constructor sites — `data_start_date=date(2022, 1, 1)` threaded.
- `tests/unit/test_enumeration/test_registry_fingerprint.py` — sensitivity row added for `data_start_date`.

---

## What's NOT in Phase 4

- **10-minute poll daemon** (§7.3 / D023/D6.a). `forge run` is single-batch; multi-batch loop is Phase 5/6 work.
- **Real Crucible-backed FeatureCache** (Phase 5 open question, kept from Phase 3). `SyntheticFeatureCache` still in use.
- **`config/forge.yaml` end-to-end wire-up** (Phase 5/6). CLI flags carry defaults baked in code today.
- **Feedback consumer that updates `submissions.status` from `pending` to `gated`** (Phase 5 §8). Today, `submissions.status` only changes on the same row via `submit_batch`: `pending` → `submitted` (success) or `submission_failed`.
- **`batch_summaries.promotion_rate` + `common_failures` backfill** (Phase 5 §8.3).
- **`pre_filter_logs` retention policy / pruning** (Phase 5/6). The table grows monotonically today.
- **Indicator-content-aware feature-cache + similarity keys** (Phase 5; same as Phase 3 OQ-4).
- **DPP diversification** (deferred per §14 decision log; `select_top_n` accepts only `method="greedy"` today).
- **Auto-tune trigger that consumes feedback to call `propose_adjustment`** (§5.5; Phase 5).

---

## Smoke-test commands

```bash
# Verify all gates
uv run ruff check && uv run ruff format --check && uv run mypy --strict src
uv run pytest -q

# Try the CLI (dry-run, no inbox required)
uv run forge run --seed 0 --batch-size 2 --max 200 --dry-run

# Full submit to a tmp inbox + tmp DB
uv run forge run --seed 0 --batch-size 2 --max 200 \
    --forge-db /tmp/forge_smoke.db \
    --inbox /tmp/forge_smoke_inbox

# Re-run the exact same batch — every candidate should be skipped_duplicate
uv run forge run --seed 0 --batch-size 2 --max 200 \
    --forge-db /tmp/forge_smoke.db \
    --inbox /tmp/forge_smoke_inbox
```

Expected: first invocation reports `submitted=N` for some `N>=1`; second invocation reports `submitted=0 skipped_duplicate=N`.

---

## Review focus (light)

Per §12, Phase 4 is **light review**. Suggested checks:

1. **D022 / contracts v1.6.0** — required `data_start_date: date` additive bump. Confirm no downstream consumer trips on the new required field.
2. **D023 / D6.a — single-batch `forge run`.** Confirm the "exit cleanly when blocked" UX is what the operator expects (current behavior: prints "blocked: prev batch ..." and exits with code 0; 10-min daemon polling is later).
3. **§6.2 vs §5.3.6 naming mismatch.** Surfaced as Open Question 1. Scorer maps `regime_diversity` weight to `regime_exposure` filter score. If the spec-side rename should land now (one-line text edit), call it out; otherwise it's Phase 5/6 polish.
4. **D023/D7 idempotency mechanics.** `submissions.config_hash` unique-index + ConstraintException catch → `skipped_duplicate`. Confirm the operator agrees this is the right surface (vs raising; vs INSERT OR REPLACE).
5. **`forge run` default `--forge-db=:memory:`.** Open Question 5 — should the default be `~/forge_data/forge.db` instead? Trade-off: persistence vs accidental writes in tests.
6. **`_fetch_promoted_configs` lookup approach.** Pulls promoted hashes from Crucible's `get_promoted_strategies`, joins to Forge's `submissions.config_json`. Phase 5 feedback consumer will revisit; confirm the join-on-config_hash approach is correct.

If any of these surface follow-ups, log them in `OPEN_QUESTIONS.md` rather than blocking Phase 5.

---

## Awaiting

Operator light-review per §12. Phase 5 (Feedback + grammar refinement) is the next phase; per §12 phase discipline, may begin read-only Phase 5 preparation after 24h with no reply, but no code until explicit "proceed."
