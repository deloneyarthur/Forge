# Phase 6 Handoff: Polish and operational discipline

**Status:** complete — **awaiting LIGHT review** (§12 phase discipline; Phase 6 is one of phases 0/2/4/6).
**Started:** 2026-05-13 (session 6 — Phase 6 kickoff + closure plan)
**Finished:** 2026-05-13
**Sessions:** 1 (single sitting; closure plan → 13 modules + handoff)
**Budget vs actual:** 5–7 days budgeted (§12); ~1 calendar day actual.

---

## Deliverables (against DESIGN.md §12 Phase 6)

| Deliverable | Status | Notes |
|---|---|---|
| Property-based invariant tests | done | `tests/invariants/test_phase6_properties.py` — Hypothesis-driven coverage for submission idempotency, ranker composite score range, diversifier exact-N invariant. |
| Reproducibility tests | done | `tests/integration/test_batch_reproducibility.py` — full pipeline (enumerate → prefilter → rank → submit) byte-identical across two runs with same (grammar, registry, seed). |
| Resilience tests | done | Three integration scenarios: Crucible-offline (`test_resilience_crucible_offline.py`), corrupt-feedback orphaned-run (`test_resilience_corrupt_feedback.py`), partial-batch retry (`test_resilience_partial_batch.py`). |
| CLI completion + help text | done | `tests/integration/test_cli_help.py` — every Typer subcommand has non-empty docstring + every option has non-empty `help=` + each command name is referenced in README.md. |
| Operational runbook in README | done | New `## Commands` + `## Operations` sections in `README.md`: normal commands, monitoring SQL, recovery procedures, config inventory, §13 invariant bookmarks. |

**Tests passing:** 923 / 923.

**Test files added this phase:** 7

```
tests/invariants/
├── test_phase6_properties.py   ( 3)
└── test_phase6_invariants.py   (13)
tests/integration/
├── test_batch_reproducibility.py            ( 2)
├── test_resilience_crucible_offline.py      ( 4)
├── test_resilience_corrupt_feedback.py      ( 3)
├── test_resilience_partial_batch.py         ( 4)
└── test_cli_help.py                         ( 5)
tests/unit/test_cli/
└── test_config_threading.py    ( 7)
```

**Phase 6 total: 41 new tests.** Combined suite: 923 / 923.
**Quality gates:** `ruff check`, `ruff format --check`, `mypy --strict` all clean.

---

## Decisions logged during this phase

`IMPLEMENTATION_DECISIONS.md` entry **D025**.

- **D025 — Phase 6 pre-code closure plan (D1–D10).** Operator approved `1.a..10.a` for all recommended options:
  - **D1** — Hypothesis property tests for submission idempotency, ranker score range, diversifier exact-N.
  - **D2** — Full-pipeline byte-determinism integration test (extends Phase 2's enumerator-only test).
  - **D3** — Three resilience scenarios as integration tests (Crucible offline, orphaned Crucible row, partial batch).
  - **D4** — Mechanical CLI help-text audit test + README sync.
  - **D5** — `## Operations` section in `README.md` (commands, monitoring, recovery, configs, invariant bookmarks).
  - **D6** — Thread `load_forge_config()` through `forge run` and `forge feedback`: yaml provides defaults, CLI flags override; `--config PATH` (default `config/forge.yaml`) + `--no-config` escape hatch.
  - **D7** — Doc rename in DESIGN.md §6.2: `regime_diversity_score` → `regime_exposure_score` (matches the §5.3.6 filter name). Doc-only; yaml weight key `regime_diversity` retained for back-compat.
  - **D8** — §8.4 trigger (c) cross-batch param-no-promotion: **deferred** to Phase 7+. Logged as Q9 in `OPEN_QUESTIONS.md`.
  - **D9** — Crucible-backed FeatureCache: **deferred** further. Logged as Q10 in `OPEN_QUESTIONS.md` (contracts-dependency tag).
  - **D10** — Micro-polish: prune unused `networkx` dep + mypy override (i); decline `--apply` convenience for `forge grammar approve-proposal` + add §13.2 docstring note (ii).

**Contracts version:** No gap. Phase 6 stays pinned to `crucible_contracts == 1.6.0`.

---

## Small production code changes (sub-second)

- `src/forge/cli/feedback_cmd.py`: catch `QueryError` from `consume_batch_results`, emit clean error via `typer.echo(... err=True)`, exit code 1. Closes the Crucible-offline resilience scenario (D025/D3.i).
- `src/forge/cli/main.py`: new `_resolve_run_defaults()` helper merges yaml + CLI flag overrides; `cmd_run` gains `--config` and `--no-config` flags; CLI option defaults shift to None so the resolver can distinguish "operator passed nothing" from "operator passed 0". Closes D025/D6.
- `src/forge/cli/grammar_cmd.py`: extended docstring on `cmd_approve_proposal` to spell out the §13.2 manual-yaml-edit boundary (D025/D10.ii).
- `src/forge/ranking/scorer.py`: docstring updated to reflect the §6.2 rename (D025/D7); no functional change.
- `docs/DESIGN.md` §6.2: `regime_diversity_score` → `regime_exposure_score` in the formula + a back-compat note about the yaml key.
- `pyproject.toml`: dropped `networkx>=3.2` dep + the `[[tool.mypy.overrides]] module = ["networkx.*"]` section (D025/D10.i).
- `README.md`: `## Commands` table + comprehensive `## Operations` section (D025/D5).

Test-only updates:

- 3 pre-existing CLI test files (`test_cli_run.py`, `test_run_loop.py`, `test_resilience_partial_batch.py`) updated to pass `--no-config` so they stay hermetic under the new yaml-by-default behavior.

---

## Open questions / spec ambiguities surfaced

1. **`SyntheticFeatureCache` still in the production loop** (carried since Phase 3 D1). Q10 logged. Contracts gap — `crucible_contracts` v1.6.0 doesn't yet expose a feature-cache surface. Swap when contracts ships one.

2. **§8.4 trigger (c) cross-batch param-no-promotion** (carried since Phase 5 OQ-1). Q9 logged. Current-batch-only suffices for v1; multi-batch rolling window is a Phase 7+ candidate.

3. **`forge grammar approve-proposal --apply` convenience.** Declined per D025/D10.ii — Phase 5 OQ-4's intentional human-in-loop boundary stays. If/when an operational pain point emerges, revisit with extra guardrails (auto-archive + version bump + initials + Decision Log entry).

4. **Daemon-loop SIGINT in a real long-running session.** Tested only in `--max-iterations` mode (Phase 5 OQ-7). Real production validation happens when Forge runs autonomously for the first time; operator-side smoke before that go-live recommended.

5. **Phase 7 / "operational discipline" follow-ups** (none currently a blocker for v1 go-live):
   - Cross-batch trigger (c) wiring (Q9).
   - Crucible-backed FeatureCache adapter (Q10) — depends on contracts surfacing.
   - Auto-merge of approved proposals into grammar.yaml (Phase 5 OQ-4 + D025/D10.ii — explicit decision NOT to ship this).
   - §7.3 daemon-loop hardening (signal handling, structured logging of iteration outcomes).

---

## Source inventory — touched in Phase 6

| File | Lines (added) | Purpose |
|---|---:|---|
| `tests/invariants/test_phase6_properties.py` | 214 | Hypothesis property tests |
| `tests/invariants/test_phase6_invariants.py` | 157 | Phase 6 audit guardrails |
| `tests/integration/test_batch_reproducibility.py` | 229 | Full-pipeline §13.1 determinism |
| `tests/integration/test_resilience_crucible_offline.py` | 159 | Crucible-offline resilience |
| `tests/integration/test_resilience_corrupt_feedback.py` | 248 | Corrupt/orphan feedback resilience |
| `tests/integration/test_resilience_partial_batch.py` | 257 | Partial-batch rate-limit resilience |
| `tests/integration/test_cli_help.py` | 115 | CLI help-text audit |
| `tests/unit/test_cli/test_config_threading.py` | 200 | ForgeConfig CLI threading |
| `README.md` | +154 | Commands + Operations sections |
| `src/forge/cli/main.py` | +85 | `_resolve_run_defaults` + `--config` / `--no-config` |
| `src/forge/cli/feedback_cmd.py` | +12 | QueryError → clean exit |
| `src/forge/cli/grammar_cmd.py` | +7 | §13.2 docstring note |
| `src/forge/ranking/scorer.py` | +/-5 | docstring updated |
| `docs/DESIGN.md` | +/-3 | §6.2 rename |
| `pyproject.toml` | -6 | networkx prune |

---

## What's NOT in Phase 6

- **Cross-batch trigger (c)** (Q9, deferred). Current-batch-only stays.
- **Crucible-backed FeatureCache** (Q10, deferred). Synthetic cache stays.
- **`forge grammar approve-proposal --apply`** (declined per D025/D10.ii).
- **Daemon-loop long-running SIGINT test** (carry-forward from Phase 5 OQ-7).
- **§7.3 daemon hardening** (structured logging of per-iteration outcomes, retries on transient errors). Phase 7+.

---

## Smoke-test commands

```bash
# Verify all gates
uv run ruff check && uv run ruff format --check && uv run mypy --strict src
uv run pytest -q

# CLI surface
uv run forge --help
uv run forge run --help    # confirm --config + --no-config flags exist

# Full single-batch with yaml-defaults (production-shape)
uv run forge run --max 200 --batch-size 5 --dry-run     # uses config/forge.yaml

# Same but hermetic (test-shape)
uv run forge run --no-config --seed 0 --batch-size 5 --max 200 --dry-run

# Crucible-offline path (manually crafted)
uv run forge feedback --no-config \
    --forge-db /tmp/forge_smoke.db \
    --crucible-db /tmp/does_not_exist.db \
    --batch-id 00000000-0000-0000-0000-000000000001
# Expected: exit 1, "error: Crucible DB unreachable: ..."
```

---

## Review focus (light)

Phase 6 is **light-review** per §12. Suggested focal points:

1. **D025 closure plan accuracy.** Confirm the 10 items match operator intent. D8 (cross-batch trigger) and D9 (FeatureCache) are explicit deferrals; D10.ii is an explicit decline of the `--apply` convenience.

2. **README Operations section completeness.** Recovery procedures cover: Crucible offline, rate-limited (partial batch), corrupt/orphaned Crucible row, approved-proposal yaml merge, stuck submission. Missing any?

3. **Yaml-by-default behavior change.** `forge run` and `forge feedback` now load `config/forge.yaml` by default. Existing tests opted out via `--no-config`. Operator-facing impact: production `forge run` now reads yaml without `--config` needed. Acceptable?

4. **D025/D10.i networkx prune.** Verified by grep that `networkx` isn't imported anywhere in `src/`, `tests/`, or `scripts/`. The dep + mypy override are dropped. The lockfile (`uv.lock`) may still reference networkx as a transitive — operator may want to refresh.

5. **D025/D7 doc rename consistency.** `regime_exposure_score` is now the §6.2 formula factor name; yaml key `regime_diversity` retained for back-compat (code side untouched). Acceptable transitional state?

6. **Phase 6 invariants coverage.** 13 structural tests in `test_phase6_invariants.py` cover each D025 commitment. Confirm no obvious hole.

If any of these surface follow-ups, log them in `OPEN_QUESTIONS.md` rather than blocking Phase 7 / go-live.

---

## Awaiting

Operator light-review per §12. Phase 7 (operational discipline + cross-batch wiring, if scoped) or v1 go-live is the next phase boundary. Per §12 phase discipline, this is light-review — operator may explicitly approve, or 24h with no reply permits read-only preparation for whatever comes next.
