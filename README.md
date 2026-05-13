# Forge

Candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

Forge enumerates grammar-valid options strategy configurations, pre-filters them through cheap statistical checks, and submits survivors to Crucible for full backtest validation. It learns from Crucible's promotion decisions and refines its hypothesis grammar over time.

See `docs/DESIGN.md` for the authoritative spec (§1 overview, §12 phase plan, §13 invariants).
See `../PIPELINE.md` for the system-of-systems context.
See `CLAUDE.md` for implementation discipline (TDD, hard rules, blessed APIs, phase boundaries).

## Quick start

```bash
uv venv
uv pip install -e ".[dev]"
forge --help
forge check    # validates crucible_contracts compat + DB schema
pytest         # full test suite
```

## Architecture (§2.1)

Five components, in order of execution per batch:

1. **Enumerator** — yields grammar-valid `StrategyConfig`s (CSP-style, deterministic).
2. **Pre-filter battery** — 7 filters in cost-ascending order; rejects ~90%.
3. **Ranker & queue** — composite score + greedy diversification.
4. **Submitter** — writes to Crucible's inbox via `crucible_contracts`.
5. **Feedback & grammar refiner** — reads Crucible's gated runs; auto-tightens grammar; surfaces loosening proposals.

The grammar (`config/grammar.yaml` + `docs/GRAMMAR.md`) is the conceptual heart. See §3.

## Project status

Currently in **Phase 0 (Bootstrap)**. See `STATUS.md` for live state.

Phase plan (§12): 0 Bootstrap → 1 Grammar engine → 2 Enumerator → 3 Pre-filter battery → 4 Ranking and submission → 5 Feedback and refinement → 6 Polish. Phases 1, 3, 5 receive close operator review.

## Honest expectations (§1.3)

Promotion rates start near zero. Target 1-3% by month 3-6, 3-5% by month 6-12. Significantly above 5% is suspicious — likely grammar over-tuned to Crucible's gate. Forge succeeds slowly.

## Repository layout

```
forge/
├── docs/DESIGN.md             # spec (source of truth)
├── docs/GRAMMAR.md            # narrative grammar doc (Phase 1)
├── config/
│   ├── forge.yaml             # main config
│   ├── prefilter.yaml         # filter thresholds
│   ├── ranker.yaml            # composite scorer weights
│   ├── grammar.yaml           # machine-readable grammar (Phase 1)
│   └── grammar_archive/       # prior versions
├── src/forge/                 # Python source
├── tests/{unit,integration,invariants,fixtures}/
├── CLAUDE.md                  # implementation discipline
├── STATUS.md                  # live phase/task state
├── IMPLEMENTATION_DECISIONS.md
└── OPEN_QUESTIONS.md
```
