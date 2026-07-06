# `crucible_contracts` v1.2.0 — Implementation Prompt

> **For the operator:** paste this as the first message of a fresh agent session, with the working directory set to `/home/aj/proj/crucible_contracts/`. The agent should have access to `~/proj/PIPELINE.md`, `~/proj/Forge/IMPLEMENTATION_DECISIONS.md` (specifically entry D007), and `~/proj/Forge/OPEN_QUESTIONS.md` (specifically Q7). No prior conversation history is needed.

---

You are extending `crucible_contracts` from v1.1.0 → v1.2.0. This is an **additive-plus-rename** release that closes a gap identified by Forge during its Phase 1 kickoff. The contracts package is the integration boundary between Forge, Crucible, and QuantIQ (see `~/proj/PIPELINE.md` §7); it is a separate repository owned by neither consumer.

## Why this change

Forge began Phase 1 (grammar engine, see `~/proj/Forge/docs/DESIGN.md` §3) and discovered that the §3.5 grammar rules reference fields that do not exist on `StrategyConfig` / `SignalSpec`. Forge halted at kickoff per the "stop and ask immediately" protocol and the operator chose option 1: extend `crucible_contracts` rather than shim around the gap.

Authoritative resolution: `~/proj/Forge/IMPLEMENTATION_DECISIONS.md` entry **D007** (read this entry; it is the source of truth for what to build).

## Hard rules — cannot be relaxed

1. **Pydantic models only, no business logic.** The contracts package describes inter-system shapes; it never imports from Crucible or Forge internals. If you find yourself adding control flow, you're in the wrong repo.
2. **Only three external deps**: `pydantic`, `polars`, `duckdb`. Do not add a fourth (per `README.md`). `pyyaml` is permitted only as a dev/test dep, never as a runtime dep.
3. **100% test coverage** for every public model and every helper. New fields require tests that exercise both the happy path (valid value) and the failure path (invalid value rejected by Pydantic).
4. **`ruff check` clean** (existing config in `pyproject.toml` is strict).
5. **`mypy --strict` clean** on `src/`.
6. **Frozen `model_config` preserved** on every model (`frozen=True, extra="forbid"`). New fields do not change frozenness.
7. **`CONTRACT_VERSION` bump is a deliberate event.** Bump it exactly once in this release, in `src/crucible_contracts/_version.py`. The bump goes from `"1.1.0"` → `"1.2.0"`.
8. **No silent enum value drift.** When you rename existing `IndicatorMetadata.family` values, replace them — do not add aliases that accept both old and new names. Spec ambiguity is resolved by D007: the 11-family list is canonical.

## What to change

### 1. `src/crucible_contracts/_version.py`

Bump:
```python
CONTRACT_VERSION = "1.2.0"
```

### 2. `src/crucible_contracts/models.py`

**(a)** Add to `StrategyConfig`:

```python
hypothesis: Literal[
    "trend_continuation",
    "mean_reversion",
    "regime_arbitrage",
    "relative_value",
    "volatility_event",
    "tail_hedge",
]
```

Required, no default. Place it near the top of the field list (after `name`, before `dte_bucket`) so the conceptual identity of the strategy reads first. See `~/proj/Forge/docs/DESIGN.md` §3.5 S1 for the rationale.

**(b)** Add to `SignalSpec`:

```python
role: Literal["directional", "regime_filter", "filter", "confluence"]
```

Required, no default. See `~/proj/Forge/docs/DESIGN.md` §3.5 S2/S3/C4 for the rationale.

**(c)** Reconcile `IndicatorMetadata.family` to the 11-family canonical list:

```python
family: Literal[
    "trend",
    "mean_reversion",
    "volatility",
    "iv_structure",
    "dealer_positioning",
    "flow",
    "macro",
    "calendar",
    "fundamental",
    "smart_money",
    "pairs",
]
```

Replace the current 9-family Literal. Also update the module-level constant `_INDICATOR_FAMILIES` (~line 30 of models.py) to match — and notice that this constant currently shadows the same list inline; keep both in sync or eliminate the duplication (recommended: keep the constant; use `_INDICATOR_FAMILIES` in the Literal via `Literal[*_INDICATOR_FAMILIES]` is **not** valid Python typing, so keep the Literal explicit but keep the constant for runtime use).

Renames vs current contracts v1.1.0:
- `mean_revert` → `mean_reversion`
- `price_trend` → `trend`
- `realized_vol` → `volatility`
- `iv` → `iv_structure`
- `dealer` → `dealer_positioning`

Drops: `multi_factor`. Adds: `flow`, `calendar`, `fundamental`. Unchanged: `macro`, `pairs`, `smart_money`.

**(d)** Mandatory exits unchanged. `MANDATORY_EXIT_IDS` retains 4 ids (`expiry_exit, theta_cliff_exit, earnings_exit, liquidity_exit`). Do not touch.

### 3. `src/crucible_contracts/__init__.py`

No new symbols added at top level; `hypothesis` / `role` / `family` are attributes of existing exported models, not new exports. Sanity-check that nothing else in `__init__.py` needs to change. If you've kept the constant `_INDICATOR_FAMILIES` private, it stays private.

### 4. Tests

The repo's quality bar is **100% coverage**. Every new field/value gets explicit tests. Add to existing test modules; do not create new ones unless a clearly new shape demands it.

**`tests/test_models.py`**:
- Test that `StrategyConfig` requires `hypothesis` (missing field → `ValidationError`).
- Test that `StrategyConfig.hypothesis` accepts each of the 6 valid values.
- Test that `StrategyConfig.hypothesis` rejects an unknown value (e.g., `"momentum"`).
- Test that `SignalSpec` requires `role`.
- Test that `SignalSpec.role` accepts each of the 4 valid values.
- Test that `SignalSpec.role` rejects an unknown value (e.g., `"directional_filter"`).
- Test that `IndicatorMetadata.family` accepts each of the 11 valid values.
- Test that `IndicatorMetadata.family` rejects each of the OLD values that were renamed (`"mean_revert"`, `"price_trend"`, `"realized_vol"`, `"iv"`, `"dealer"`, `"multi_factor"`) — this is the breaking-change guard.
- Test that `IndicatorMetadata.family` rejects an obviously-invalid value (e.g., `"options_alpha"`).
- Where existing tests construct sample models, ensure they pass valid `hypothesis` / `role` / `family` arguments. Don't break existing positive-path tests.

**`tests/test_validators.py`**:
- `validate_config_against_registry` — verify it still works against the new shape. The registry's `signal_types` set is what `SignalSpec.type` is validated against; the new `role` field is a Pydantic Literal and validates without registry consultation. No validator-function change is needed, but confirm with a test that exercises a `StrategyConfig` with `hypothesis` and `role` populated.
- Test that `validate_schema_version("2.0.0", "1.2.0")` raises (major mismatch) and that `validate_schema_version("1.1.0", "1.2.0")` does **not** raise (same major; minor differences tolerated).

**`tests/test_queries.py`**:
- Re-run existing tests against the updated models (you may need to add `hypothesis` / `role` to test-fixture `StrategyConfig` / `SignalSpec` instances).
- The query helpers (`get_promoted_strategies`, `get_recent_gated_runs`, `submit_candidate`, `request_refit`) don't read or write `hypothesis` / `role` / `family` directly; they round-trip whole models via JSON. Verify a `StrategyConfig` with the new fields round-trips through `submit_candidate` and the resulting JSON contains the new fields.

**`tests/test_formats.py`**:
- No changes expected; formats are about directory layouts, not model fields.

### 5. README

Update the "Schema versioning" section's example or add a brief release-note line at the bottom under a new "Changelog" heading:

```markdown
## Changelog

### v1.2.0 — 2026-05-13
- **Added** `StrategyConfig.hypothesis` (required Literal): trend_continuation / mean_reversion / regime_arbitrage / relative_value / volatility_event / tail_hedge.
- **Added** `SignalSpec.role` (required Literal): directional / regime_filter / filter / confluence.
- **Renamed and expanded** `IndicatorMetadata.family` enum to the canonical 11-family list. Renames: mean_revert→mean_reversion, price_trend→trend, realized_vol→volatility, iv→iv_structure, dealer→dealer_positioning. Added: flow, calendar, fundamental. Dropped: multi_factor.
- Treated as minor bump despite the enum rename because no production data exists yet (Forge and Crucible are pre-build). Consumers pinned to major version 1 keep working without code change apart from updating field references.

### v1.1.0
- Mandatory-exits validator + py.typed marker.

### v1.0.0
- Bootstrap.
```

### 6. SemVer note in the commit message

This release is *technically* breaking because the family enum renames existing values, which would reject pre-existing data. We treat it as a minor bump (1.1 → 1.2) because no consumer has shipped production data yet (Crucible is unbuilt, Forge is at Phase 0). Be explicit about this in the commit body.

## Quality gates before commit

In order:

1. `uv sync` (if `uv.lock` exists; otherwise `uv pip install -e ".[dev]"`).
2. `.venv/bin/ruff check` — must be clean.
3. `.venv/bin/ruff format --check` — must be clean.
4. `.venv/bin/mypy src` — must be clean (`Success: no issues found`).
5. `.venv/bin/pytest --cov=src/crucible_contracts --cov-report=term-missing --cov-fail-under=100` — must be 100% pass and 100% coverage.

If any gate fails, fix the underlying issue. Do not lower the coverage bar; do not silence the lint with `# noqa` unless the suppression is justified in-line with a one-sentence reason.

## Commit

One commit, on `master`, message:

```
v1.2.0: hypothesis + role + family-list reconciliation

Closes a gap surfaced by Forge during Phase 1 kickoff (see Forge's
IMPLEMENTATION_DECISIONS.md D007). The grammar rules in
FORGE_DESIGN.md §3.5 reference fields that did not exist on
StrategyConfig / SignalSpec. This release adds them.

Additions:
- StrategyConfig.hypothesis: Literal[6 values] (required)
- SignalSpec.role: Literal[4 values] (required)

Reconciliation:
- IndicatorMetadata.family enum now matches the spec's canonical
  11-family list. Renames mean_revert→mean_reversion,
  price_trend→trend, realized_vol→volatility, iv→iv_structure,
  dealer→dealer_positioning. Adds flow, calendar, fundamental.
  Drops multi_factor.

Treated as minor (additive-plus-rename) bump because no production
data exists yet (Crucible unbuilt, Forge at Phase 0). A strict SemVer
read would call the enum rename a 2.0.0 breaking change; we accept
the convention slightly bent given the pre-production state.

CONTRACT_VERSION bumped 1.1.0 → 1.2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## When to stop and ask

Stop and ask the operator if:

- A test reveals a coupling you didn't expect (e.g., a query helper that constructs `StrategyConfig` internally and needs a `hypothesis` default for back-compat).
- The 100% coverage requirement starts forcing you to test trivial property accesses — propose a coverage exemption rather than write noise tests.
- You discover that a downstream consumer (Crucible source tree, QuantIQ source tree) already references the OLD family names; the rename needs to be coordinated.
- Anything else surprises you. The contracts package is small; surprises are signals, not noise.

For everything else, proceed and commit.

## Reporting back

After commit, your final message to the operator should include:

1. The new commit SHA.
2. Confirmation that all five quality gates are green.
3. Coverage percentage (expect 100%).
4. The next-step instruction for the Forge agent: bump `FORGE_EXPECTED_CONTRACT_VERSION` in `~/proj/Forge/src/forge/core/contracts_check.py` to `"1.2.0"`, then resume Phase 1 from the kickoff point (re-read `~/proj/Forge/docs/DESIGN.md` §3 and `~/proj/Forge/STATUS.md`).

The Forge agent will not auto-resume; the operator triggers Forge's next session manually.

---

**End of prompt.**
