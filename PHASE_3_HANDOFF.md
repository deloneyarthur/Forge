# Phase 3 Handoff: Pre-filter battery

**Status:** complete — **awaiting CLOSE review** (§12 phase discipline; Phase 3 is one of the three close-review phases).
**Started:** 2026-05-13 (session 3 — Phase 3 kickoff + closure plan)
**Finished:** 2026-05-13
**Sessions:** 1 (single sitting; closure plan -> contracts v1.5.0 side-trip -> 13 modules)
**Budget vs actual:** 10-14 days budgeted (§12); ~1 calendar day actual.

---

## Deliverables (against DESIGN.md §12 Phase 3)

| Deliverable | Status | Notes |
|---|---|---|
| Filter protocol and registry | done | `forge.prefilters.types.Filter` (Protocol, @runtime_checkable); `forge.prefilters.battery.default_filters()` is the §5 7-filter registry in cost order. |
| All 7 filters implemented | done | `structural_redundancy` (1), `resource_feasibility` (2), `signal_density` (3), `expected_trades` (4), `novelty` (5), `regime_exposure` (6), `permutation_test` (7). One module each, cost-ascending. |
| Each filter has unit tests with known-pass and known-fail cases | done | 12–18 tests per filter; per-filter test files cover protocol membership, threshold edge cases, score formula, details payload, and purity. |
| Auto-tune mechanism (with manual override) | done (mechanism only) | `forge.prefilters.calibration` ships `propose_adjustment`, `apply_tightening` (pure), and `write_loosening_proposal` (writes to `OPEN_PROPOSALS.md`). **No auto-fire trigger in Phase 3** (D021/D3) — Phase 5 wires the feedback-driven trigger. Structural enforcement of CLAUDE.md hard rule #4 analogue: no `apply_loosening` function exposed. |
| Performance: full battery on 10K candidates in < 30 min | done | `test_perf_1000_candidates_well_under_phase3_budget` runs 1K through the full battery in ~10s. Linear extrapolation: ~100s for 10K vs 1800s budget (18x headroom). |
| `forge prefilter --batch-id=test` runs the full battery | done (interface variant) | Ship `forge prefilter --seed N --max K [--summary]`. The `--batch-id` framing belongs to Phase 4 (the submitter mints the batch id); Phase 3 ships the synthetic-cache CLI demo. |

**Tests passing:** 598 / 598.
**Test files added this phase:** 11 (1 per module + 1 invariants):

```
tests/unit/test_prefilters/
├── test_types.py                  (26)
├── test_feature_cache.py          (17)
├── test_calibration.py            (18)
├── test_structural_redundancy.py  (12)
├── test_resource_feasibility.py   (13)
├── test_signal_density.py         (16)
├── test_expected_trades.py        (15)
├── test_novelty.py                (16)
├── test_regime_exposure.py        (16)
├── test_permutation_test.py       (14)
├── test_battery.py                (15)
└── test_cli_prefilter.py          (4)
tests/invariants/
└── test_phase3_invariants.py      (8)
```

**Phase 3 total: 190 new tests.** Combined suite: 598 / 598.
**Quality gates:** `ruff check`, `ruff format --check`, `mypy --strict` all clean.

---

## Decisions logged during this phase

`IMPLEMENTATION_DECISIONS.md` entries **D020** + **D021**.

- **D020** — `crucible_contracts` v1.5.0 adds `RegistrySnapshot.data_history_days: int = Field(ge=1)`. Forge pin bumped to `"1.5.0"`; 9 RegistrySnapshot constructor sites threaded. Resolves D6.
- **D021** — Phase 3 pre-code closure plan, capturing D1–D9 architectural decisions:
  - **D1** — Internal `FeatureCache` Protocol + `SyntheticFeatureCache` (seeded by `forge.core.seed`). Phase 4/5 wires a Crucible-backed implementation against the same Protocol.
  - **D2** — `PreFilterReport.composite_score` stays `None` in Phase 3; Phase 4 ranker fills it via §6.2 weights.
  - **D3** — Calibration mechanism (loader + propose/apply API) ships at Phase 3. **No auto-fire** — Phase 5 wires the feedback-driven trigger. Loosenings always write to `OPEN_PROPOSALS.md` (no `apply_loosening` function in the module).
  - **D4** — Regime labels live on `FeatureCache.regime_label(date) -> Regime` over the six §5.3.6 labels.
  - **D5** — `Filter` Protocol: `name: str, cost_tier: int, apply(config, ctx) -> FilterResult`. Battery iterates in `cost_tier` order with short-circuit.
  - **D6** — Contracts side-trip (D020).
  - **D7** — Permutation test K=100 confirmed.
  - **D8** — Phase 3 returns `PreFilterReport` in-memory only. Phase 4 wires `pre_filter_logs` DB writes when batch IDs exist.
  - **D9** — 13-module breakdown (types -> feature_cache -> calibration -> 7 filters -> battery -> CLI -> invariants).

---

## Open questions / spec ambiguities surfaced

1. **§5.5 auto-loosen vs CLAUDE.md hard rule #4** (carried, D021/D3). The spec text allows pre-filter auto-loosening when promotion rate < 0.5% for 2 consecutive batches. CLAUDE.md hard rule #4 ("auto-loosening cannot ship without approval") is grammar-focused, but the conservative reading extends to pre-filter thresholds. Resolution: Phase 3 writes loosenings to `OPEN_PROPOSALS.md` and waits; Phase 5 wires the trigger. If the operator wants pre-filter auto-loosen for v1, surface at Phase 5 close.

2. **Permutation-test window assumption (low).** `permutation_test.py` builds the full-window date list with `_full_window(date(2022, 1, 1), n)`. The synthetic feature cache happens to anchor at the same date. When Phase 4 wires Crucible's real cache, the cache must expose its actual start date — likely via a `data_start_date` field on `RegistrySnapshot` (another small contracts bump). Defer to Phase 4 architecture.

3. **`expected_trades` hold-day table (low).** `_HOLD_DAYS_BY_BUCKET` and `_MAX_CONCURRENT_POSITIONS = 5` are coarse estimates. Phase 5 grammar refinement can revisit once actual trade-rate distributions are visible from Crucible feedback.

4. **`signal.id` as feature-cache key (low).** Filters call `feature_cache.activation_dates(signal.id)`. Two configs with identically-shaped signals but different `signal.id` labels would get different synthetic activation sets. Real Crucible cache will need a content-hash key. Phase 4 changes the contract surface; the filter logic stays as-is.

5. **`pyproject.toml` networkx mypy section unused (housekeeping).** Phase 2 D3 chose custom CSP over `networkx`; the `[[tool.mypy.overrides]]` section for `networkx.*` is dead config. Remove during Phase 6 polish.

---

## Source inventory — `src/forge/prefilters/`

| File | Lines | Purpose |
|---|---:|---|
| `__init__.py` | 40 | Public API re-exports |
| `types.py` | 100 | `Filter` Protocol, `FilterResult`, `PreFilterReport`, `FilterContext` |
| `feature_cache.py` | 100 | `FeatureCache` Protocol + `SyntheticFeatureCache` (D021/D1, D021/D4) |
| `calibration.py` | 290 | Nested `Calibration` dataclass + loader + `propose/apply/write_loosening_proposal` (D021/D3) |
| `structural_redundancy.py` | 45 | Filter 1, O(1), cost_tier=1 (§5.3.1) |
| `resource_feasibility.py` | 55 | Filter 2, O(1), cost_tier=2 (§5.3.2) |
| `signal_density.py` | 65 | Filter 3, O(N), cost_tier=3 (§5.3.3) |
| `expected_trades.py` | 80 | Filter 4, O(N), cost_tier=4 (§5.3.4) |
| `novelty.py` | 75 | Filter 5, O(M), cost_tier=5 (§5.3.5) |
| `regime_exposure.py` | 85 | Filter 6, O(N), cost_tier=6 (§5.3.6) |
| `permutation_test.py` | 95 | Filter 7, O(K=100), cost_tier=7 (§5.3.7) |
| `battery.py` | 80 | `run_battery` orchestrator + `default_filters()` registry |

Also touched:

- `src/forge/cli/main.py` — added `cmd_prefilter` (`forge prefilter` command).
- `src/forge/core/contracts_check.py` — `FORGE_EXPECTED_CONTRACT_VERSION` bumped to `"1.5.0"`.
- `tests/fixtures/strategy_configs.py` + 8 other RegistrySnapshot constructor sites — `data_history_days=1008` threaded.
- `tests/unit/test_enumeration/test_registry_fingerprint.py` — sensitivity test for `data_history_days` added (16-char hash now varies on this field too).

---

## What's NOT in Phase 3

- **Ranker** (§6 / Phase 4) — `PreFilterReport.composite_score` stays `None`. The Phase 4 ranker computes §6.2's weighted sum.
- **Diversification** (§6.3 / Phase 4) — DPP / greedy diversifier.
- **Submitter** (§7 / Phase 4) — `crucible_contracts.submit_candidate` not wired.
- **`pre_filter_logs` DB writes** (Phase 4). Reports are in-memory only; Phase 4 batches them and writes to the table when batch IDs exist.
- **Feedback consumer + auto-tune trigger** (§8 / Phase 5). The `propose_adjustment` API ships; the trigger that calls it does not.
- **Real Crucible feature cache wiring** (Phase 4/5). The Protocol exists; the `SyntheticFeatureCache` placeholder is what every Phase 3 test uses.
- **Indicator-content-aware feature cache keys** (Phase 4). Filters use `signal.id` for the synthetic cache lookup; real cache will need a canonical signal-content hash.

---

## Smoke-test commands

```bash
# Verify all gates
uv run ruff check && uv run ruff format --check && uv run mypy --strict src
uv run pytest -q

# Try the CLI
uv run forge prefilter --seed 7 --max 5 --summary
uv run forge prefilter --seed 7 --max 5            # same seed -> identical output
uv run forge prefilter --seed 8 --max 5            # different seed -> different output

# Quick determinism check from Python
uv run python -c "
from forge.core.seed import SeedHierarchy
from forge.enumeration import enumerate_candidates
from forge.enumeration._demo_registry import demo_registry
from forge.grammar import load_grammar
from forge.prefilters import (
    SyntheticFeatureCache, default_filters, load_calibration, run_battery,
)
from forge.prefilters.types import FilterContext
from pathlib import Path
repo = Path('.').resolve()
g = load_grammar(repo / 'config' / 'grammar.yaml', archive_dir=repo / 'config' / 'grammar_archive')
r = demo_registry()
cal = load_calibration(repo / 'config' / 'prefilter.yaml')
h = SeedHierarchy(99)
ctx = FilterContext(registry=r, feature_cache=SyntheticFeatureCache(root_seed=99),
                    prior_config_hashes=frozenset(), prior_firing_dates={},
                    calibration=cal, rng_factory=h.rng)
filters = default_filters()
a = [(c.config_hash, run_battery(c, ctx, filters).passed)
     for c in enumerate_candidates(g, r, seed=99, max_candidates=10)]
b = [(c.config_hash, run_battery(c, ctx, filters).passed)
     for c in enumerate_candidates(g, r, seed=99, max_candidates=10)]
print('determinism:', a == b)
"
```

Expected: smoke prints 5 candidate verdicts + summary; determinism prints `True`.

---

## Review focus (close)

Per §12, Phase 3 is **close review**. Suggested checks:

1. **D020 / contracts v1.5.0** — `data_history_days` required-int additive bump. Confirm no downstream consumer (esp. Crucible registry-generation code, when it lands) trips on the new required field.
2. **D021 / D3 — auto-tune scope.** Phase 3 ships *mechanism* only. Verify the structural enforcement (no `apply_loosening`) reads as intended; if the operator wants pre-filter auto-loosen at Phase 5, name that explicitly.
3. **Filter-by-filter score formulas.** Most filters use `log1p(n) / log1p(10 * threshold)` or entropy-based scoring. These are reasonable defaults but the §6.2 ranker weights them — Phase 4 may want different shapes (e.g., linear), in which case revisit the per-filter score functions.
4. **`expected_trades` hold-day table + 5-slot cap.** Coarse Phase 3 estimates. Confirm the assumption is documented as a Phase 5 revisit target.
5. **Permutation-test window anchor.** Hardcoded `date(2022, 1, 1)` in `permutation_test.py`. Phase 4 must replace with `registry.data_start_date` (likely a v1.6.0 contracts addition). Surfaced in Open Questions item 2.
6. **`signal.id` as feature-cache key.** Synthetic stub; real Crucible cache needs content-hash keys. Phase 4 must address.

If any surface follow-ups, log them in `OPEN_QUESTIONS.md` rather than blocking Phase 4.

---

## Awaiting

Operator close-review per §12. Phase 4 (Ranking + submission) requires explicit "proceed" sign-off; close-review phases do NOT auto-advance after 24h.
