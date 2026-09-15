# tests/ — layout and conventions

Scope: where a test goes and the local patterns. Run commands: `docs/tasks/quality-gates.md`.

| Dir | Holds | Rule |
|---|---|---|
| `unit/` | Pure-logic single-module tests, mirroring `src/forge/` (`test_grammar/`, `test_enumeration/`, …) | Default home for new tests |
| `integration/` | Multi-module workflows, contracts integration, resilience (`test_resilience_*`), reproducibility, hook scripts | Anything crossing module boundaries or touching real file layouts |
| `invariants/` | Structural enforcement of the CLAUDE.md hard rules + §13, one file per phase (`test_phase{0..6}_invariants.py`, `test_phase6_properties.py` is Hypothesis-driven) | Every hard rule gets its failure-mode test HERE, written before the production code |
| `fixtures/` | Shared synthetic data: `synthetic_crucible_db.py`, `strategy_configs.py`, `grammar_property_helpers.py` | Extend rather than duplicate |

Markers (pyproject): `unit`, `integration`, `invariants`, `slow`.

## Local patterns

- **Golden sampler-sequence tests** pin cold-start byte-identical enumeration (hard rule #6).
  A deliberate population change re-pins them — note it in the D-entry; never adjust casually.
- **Eight test files import `forge.cli.main`; six only import `app`** and drive it through
  `CliRunner` (behaviour tests). The daemon loop and its monkeypatch seams left in Batch 5 G1;
  `main.py` is a thin Typer entry point (version / check / enumerate / prefilter + the
  `campaign` and `prereg` sub-apps).
- **Time/RNG**: only `forge.core.clock` / `forge.core.seed`, even in tests that build fixtures.
  Note the `tests/invariants/test_phase0_invariants.py` scan covers `src/` only — tests are
  held to the rule by review, not by the scanner.
- **Known-bug gap tests** use `@pytest.mark.xfail(strict=True, reason="REL-n … fixed in Batch N")`
  so the suite stays green while the defect is documented, and the test flips LOUD (strict
  XPASS) the moment the fix lands — remove the marker in the fixing commit.
- Contracts exceptions may be caught only inside test fixtures.
- Resilience tests model the §7.3 limiter/flush against the rolling export window; they are
  timezone-sensitive by design (see the 2026-06-07 migration fix in `STATUS.md`) — use blessed
  naive-UTC stamps and now-relative dates.
