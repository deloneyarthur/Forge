# tests/ — layout and conventions

Scope: where a test goes and the local patterns. Run commands: `docs/tasks/quality-gates.md`.

| Dir | Holds | Rule |
|---|---|---|
| `unit/` | Pure-logic single-module tests, mirroring `src/forge/` (`test_campaign/`, `test_grammar/`, `test_enumeration/`, …) | Default home for new tests |
| `integration/` | Multi-module workflows, contracts integration, resilience (`test_resilience_*`), reproducibility, hook scripts, the CLI↔docs sync guard | Anything crossing module boundaries or touching real file layouts |
| `invariants/` | Structural enforcement of the CLAUDE.md hard rules + §13: `test_phase{0..6}_invariants.py` (by build phase; `test_phase6_properties.py` is Hypothesis-driven), `test_campaign_invariants.py` (a run's kept configs are a subsequence of the cold-start sequence), `test_batch5_prep_seams.py` (the campaign imports nothing daemon-era), and the one-invariant files | Every hard rule gets its failure-mode test HERE, written before the production code |
| `fixtures/` | Shared synthetic data: `synthetic_crucible_db.py`, `strategy_configs.py`, `grammar_property_helpers.py` | Extend rather than duplicate |

Markers (pyproject): `unit`, `integration`, `invariants`, `slow`.

## Local patterns

- **Golden sampler-sequence tests** pin cold-start byte-identical enumeration (hard rule #6).
  A deliberate population change re-pins them — note it in the D-entry; never adjust casually.
- **Exports, not DBs.** Tests that feed the consumer write real export files (the
  `write_gated_runs_export` helpers) — the direct-DuckDB fallback is gone (Batch 5 G5, hard rule #2).
- **Eight test files import `forge.cli.main`; six only import `app`** and drive it through
  `CliRunner` (behaviour tests). `main.py` is a thin Typer entry point (version / check / enumerate /
  prefilter + the `campaign` and `prereg` sub-apps).
- **Time/RNG**: only `forge.core.clock` / `forge.core.seed`, even in tests that build fixtures.
  Note the `tests/invariants/test_phase0_invariants.py` scan covers `src/` only — tests are
  held to the rule by review, not by the scanner.
- **Known-bug gap tests** use `@pytest.mark.xfail(strict=True, reason="REL-n … fixed in Batch N")`
  so the suite stays green while the defect is documented, and the test flips LOUD (strict
  XPASS) the moment the fix lands — remove the marker in the fixing commit. None open since
  Batch 5 G6.
- Contracts exceptions may be caught only inside test fixtures.
- Resilience tests model reconcile + the aged-out flush against the rolling export window; they
  are timezone-sensitive by design (see the 2026-06-07 migration fix in `STATUS.md`) — use blessed
  naive-UTC stamps and now-relative dates.
