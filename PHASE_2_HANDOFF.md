# Phase 2 Handoff: Enumerator

**Status:** complete — **awaiting light review** (§12 phase discipline).
**Started:** 2026-05-13 (session 3 — Phase 2 kickoff + closure plan)
**Finished:** 2026-05-13
**Sessions:** 1 (single sitting; closure plan → contracts side-trip → 6 modules)
**Budget vs actual:** 7-10 days budgeted (§12); ~1 calendar day actual.

---

## Deliverables (against DESIGN.md §12 Phase 2)

| Deliverable | Status | Notes |
|---|---|---|
| CSP-style search over grammar | done | `forge.enumeration.sampler.sample_config` walks §4.2's 9-step CSP with the D7 mode-first amendment. Custom CSP (no networkx/python-constraint) per closure-plan D3. |
| Deterministic enumeration (seed-controlled) | done | `enumerate_candidates(grammar, registry, seed, *, max_candidates)` is byte-deterministic given the §13.1 triple `(grammar_version, registry_hash, seed)`. Verified at 100-config scale in `test_phase2_invariants.py::test_enumeration_byte_identical_for_same_triple`. |
| Integration with `IndicatorMetadata` registry | done | `build_search_space` resolves §3.5 C2 / R1-R3 / X1-X2 against `RegistrySnapshot.indicators` and `IndicatorMetadata.params_schema`. |
| Performance: 100K configs in < 5 min | done | `test_perf_100k_configs_under_five_minutes` — observed ~15s on the v1 demo registry (~20x headroom). |
| `forge enumerate --max=10000` produces 10K configs | done | CLI command shipped. Inline demo registry placeholder; Phase 4 replaces with real Crucible-registry query. |

**Tests passing:** 407 / 407.
**Test files added this phase:** 6 (`test_search_space`, `test_registry_fingerprint`, `test_defaults`, `test_sampler`, `test_iterator`, `test_cli_enumerate`, `test_phase2_invariants`).
**Quality gates:** `ruff check`, `ruff format --check`, `mypy --strict` all clean. Phase 1's 218 tests + Phase 2's 189 tests = 407.

---

## Decisions logged during this phase

`IMPLEMENTATION_DECISIONS.md` entry **D019** (one). Phase 2 also operates under the closure-plan decisions **D1-D8** captured in the conversation (recorded here for traceability — not all needed a Decision Log entry because they were architectural choices the operator green-lit before any code landed):

- **D1** — `crucible_contracts` v1.4.0 adds the `trend_strength` family; adx/hurst reclassified honestly. Logged as **D019**. Closed Q8.
- **D2** — §3.5 P2 exit-DTE strengthening deferred to Phase 5 once feedback data exists.
- **D3** — Custom CSP sampler (no networkx / python-constraint). v1 search space is small enough.
- **D4** — `registry_hash(snapshot)` = 16-char sha256 of canonical JSON dump. Stands in for the missing `RegistrySnapshot.version` field.
- **D5** — `equity_hedge_metadata` is always `None` on Forge-emitted configs (QuantIQ owns equity pairings post-promotion).
- **D6** — `forge.enumeration.defaults` table for fields v1 grammar doesn't constrain (delta_tolerance, kelly_fraction, etc.).
- **D7** — Sampler picks sizer mode **second** (after hypothesis, before bucket) so §3.5 X1/X2 indicator chaining can flow through to bucket+S4 filtering.
- **D8** — Module breakdown: search_space → registry_fingerprint → defaults → sampler → iterator + CLI → invariants/perf/handoff.

---

## Open questions / spec ambiguities surfaced

1. **§3.5 P2 exit-DTE side (carried, see D2 above).** The exit side of the entry/exit DTE rule isn't enforced by the v1 sampler. Phase 5 grammar refinement should revisit once feedback data shows where the right exit-DTE thresholds live.

2. **Demo-registry duplication (low).** `src/forge/enumeration/_demo_registry.py` mirrors `tests/fixtures/strategy_configs.minimal_registry_snapshot` byte-for-byte. Acceptable for Phase 2 — both are placeholders until Phase 4 wires real Crucible-registry queries. If they drift before Phase 4, the sampler's grammar-validity property test catches it (the test fixture's path through enumeration is exercised). Phase 4 should delete `_demo_registry.py` outright and route the CLI through `crucible_contracts` queries.

3. **`forge.grammar.custom_predicates._*` constants are read by Phase 2** (`search_space` and `sampler` both import `_C2_HYPOTHESIS_FAMILIES`, `_P2_ENTRY_DTE`, etc.). The underscore prefix signaled module-private when only the grammar predicates consumed them. They're now effectively shared-internal across `forge.grammar` and `forge.enumeration`. A Phase 6 polish task can promote them to a public `forge.grammar.tables` module without semantic change.

---

## Source inventory — `src/forge/enumeration/`

| File | Lines | Purpose |
|---|---:|---|
| `__init__.py` | 30 | Public API re-exports |
| `search_space.py` | ~245 | §4.2 coordinate-space builder; resolves C2 / R1-R3 / X1-X2 / P2 / P3 / P4 against grammar + registry |
| `registry_fingerprint.py` | 40 | `registry_hash(snapshot)` — 16-char sha256 of canonical JSON dump (D4) |
| `defaults.py` | 20 | Operator-readable table for fields v1 grammar doesn't constrain (D6) |
| `sampler.py` | ~280 | Hypothesis-first stratified sampler with D7 mode-first amendment; valid-by-construction |
| `iterator.py` | ~95 | `enumerate_candidates` lazy generator with safety-net validator + rejection counter |
| `_demo_registry.py` | ~150 | Phase 2 inline demo (Phase 4 deletes) |

Also touched:

- `src/forge/cli/main.py` — added `cmd_enumerate` (`forge enumerate` command).
- `src/forge/core/contracts_check.py` — `FORGE_EXPECTED_CONTRACT_VERSION` bumped to `"1.4.0"`.
- `tests/fixtures/strategy_configs.py` — adx/hurst reclassified to `trend_strength` family.

---

## Test inventory — `tests/unit/test_enumeration/` + `tests/invariants/test_phase2_invariants.py`

| File | Tests | Coverage |
|---|---:|---|
| `test_search_space.py` | 31 | Determinism + C2/R/X rule fan-out + sorted ordering + empty-pool handling |
| `test_registry_fingerprint.py` | 10 | Stability + sensitivity to every snapshot field |
| `test_defaults.py` | 4 | Lock-in for D6 values |
| `test_sampler.py` | 118 | Per-rule §3.5 conformance + path-(a) zero-rejection + edge cases |
| `test_iterator.py` | 10 | Length contract + determinism + ValueError + EnumerationCapped + lazy |
| `test_cli_enumerate.py` | 4 | CLI smoke + determinism + summary flag |
| `test_phase2_invariants.py` | 12 | §13.1 byte-determinism + hard rule #7 + D5 + path-(a) at 1000 + §4.5 perf at 100K |

**Phase 2 total: 189 tests.** Combined suite: 407 / 407.

---

## What's NOT in Phase 2

- **Pre-filter battery** (§5 / Phase 3). Iterator yields raw grammar-valid configs; no signal-density, novelty, permutation-test filtering yet.
- **Ranker / queue** (§6 / Phase 4).
- **Submitter** (§7 / Phase 4) — `crucible_contracts.submit_candidate` not wired.
- **Real Crucible registry path** — Phase 4. Replace `_demo_registry.py`.
- **`submissions` table writes** — Phase 4.
- **Feedback consumer + grammar refiner** (§8 / Phase 5).
- **Tier 2 / 3 strategies.** Sampler always sets `tier=1`. Future work may sample tier from a registry-aware pool.
- **EquityHedgeSpec** — Forge never emits; QuantIQ owns post-promotion (D5).
- **Param sampling for indicators.** Signal `params` are empty by default (passes §3.5 P1 because indicator `params_schema` is empty or the params match). R1 (`iv_rank.threshold`) and E3 (`trailing_atr.activate_after_gain_pct`) are the two exceptions where the sampler sets a param.

---

## Smoke-test commands

```bash
# Verify all gates
uv run ruff check && uv run ruff format --check && uv run mypy --strict src
uv run pytest -q

# Try the CLI
uv run forge enumerate --seed 7 --max 10 --summary
uv run forge enumerate --seed 7 --max 10  # same seed → identical output
uv run forge enumerate --seed 8 --max 10  # different seed → different output

# Quick determinism check from Python
uv run python -c "
from forge.enumeration import enumerate_candidates
from forge.enumeration._demo_registry import demo_registry
from forge.grammar import load_grammar
from pathlib import Path
repo = Path('.').resolve()
g = load_grammar(repo / 'config' / 'grammar.yaml', archive_dir=repo / 'config' / 'grammar_archive')
r = demo_registry()
a = [c.config_hash for c in enumerate_candidates(g, r, seed=99, max_candidates=20)]
b = [c.config_hash for c in enumerate_candidates(g, r, seed=99, max_candidates=20)]
print('determinism:', a == b)
"

# Perf check
uv run python -c "
import time
from forge.enumeration import enumerate_candidates
from forge.enumeration._demo_registry import demo_registry
from forge.grammar import load_grammar
from pathlib import Path
repo = Path('.').resolve()
g = load_grammar(repo / 'config' / 'grammar.yaml', archive_dir=repo / 'config' / 'grammar_archive')
r = demo_registry()
t0 = time.perf_counter()
N = 100_000
for _ in enumerate_candidates(g, r, seed=0, max_candidates=N): pass
print(f'{N} configs in {time.perf_counter() - t0:.2f}s')
"
```

Expected: determinism `True`; perf ~15s for 100K.

---

## Review focus (light)

Per §12 phase discipline, Phase 2 is light-review. Suggested checks:

1. **D1 / contracts v1.4.0.** Confirm the additive change is acceptable and that no downstream consumer trips on `trend_strength`.
2. **Demo-registry duplication (Open Question 2).** Confirm the Phase 4 plan is to delete `_demo_registry.py`.
3. **D7 mode-first ordering.** Skim `sampler.py:sample_config` (~lines 85–172) to verify the order matches §4.2 + D7.
4. **`forge enumerate` output** — eyeball that hypotheses span the 6 v1 set, that DTE buckets vary, and that registry_hash is stable across runs.

If any of these surface follow-ups, log them in `OPEN_QUESTIONS.md` rather than blocking Phase 3.

---

## Awaiting

Operator light-review per §12. Phase 3 (Pre-filter battery) may begin read-only preparation 24h after this handoff if no reply; no code lands until sign-off.
