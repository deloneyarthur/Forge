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
- **~10 test files monkeypatch `forge.cli.main` internals** (run-loop seams). `main.py`'s length
  and structure are deliberate (D065/D105/D106 noqa) — refactors there break this suite layer.
- **Time/RNG**: only `forge.core.clock` / `forge.core.seed`, even in tests that build fixtures —
  `tests/invariants/test_phase0_invariants.py` scans for violations.
- Contracts exceptions may be caught only inside test fixtures.
- Resilience tests model the §7.3 limiter/flush against the rolling export window; they are
  timezone-sensitive by design (see the 2026-06-07 migration fix in `STATUS.md`) — use blessed
  naive-UTC stamps and now-relative dates.
