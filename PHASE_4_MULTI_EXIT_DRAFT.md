# Phase 4 — Multi-exit per hypothesis (grammar v3) — DRAFT

**Authored:** 2026-05-19 (post-D069 + post-Crucible-vectorization + D070 rate-limit restore)
**Status:** DRAFT — awaiting operator review before any code lands
**Source:** Crucible's `../Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md` Fix #1; Forge's `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 4

---

## Problem

Forge's §3.5 S5 currently pins **exactly one** required exit per hypothesis:

| Hypothesis | Current required exit |
|---|---|
| `trend_continuation` | `trailing_atr` |
| `mean_reversion` | `time_stop` |
| `regime_arbitrage` | `regime_flip_exit` |
| `relative_value` | `convergence_exit` |
| `volatility_event` | `iv_crush_exit` + `event_passed_exit` |
| `tail_hedge` | `roll_on_schedule_exit` |

Every config in a hypothesis gets the same exit logic. Crucible's 3,829-config gauntlet analysis identified this as the **#1 cause of the 89.1% zero-trade rate**: exits fire too late or too early *uniformly*, with no variation. Different exit philosophies (trailing-stop vs target-take vs z-score-reversion vs chandelier-stop) produce different trade-count and edge profiles for the same entry signal.

D069 widened the structural-fingerprint space (param-aware), unlocking three hypotheses past the novelty filter. But the new diversity ships configs that **still all use the same exit per hypothesis**. The exit-monoculture survives Phase 1.

### Expected impact per hypothesis (from the 2026-05-19 cohort analysis)

Cross-referenced 1,000 gated_runs against Forge's submissions table:

| Hypothesis | 0 trades | 1-9 | 10-99 | 100+ | % zero | Phase 4 leverage |
|---|---:|---:|---:|---:|---:|---|
| `volatility_event` | 93 | 4 | 22 | 8 | 73.2% | **High** — varied exits could lift 1-9 → 10+ and 10-99 → 100+ |
| `regime_arbitrage` | 121 | 60 | 19 | 1 | 60.2% | **High** — 80 configs already trade; exits to convert them to evaluable |
| `tail_hedge` (pre-D066) | 175 | 169 | 11 | 0 | 49.3% | N/A — D066 already filters tail_hedge from new submissions |
| `relative_value` | 309 | 8 | 0 | 0 | **97.5%** | **None** — exits can't help configs that never open positions |
| `trend_continuation` | — | — | — | — | (no historical submissions; just unlocked by registry fix) | N/A until permutation_test gate cleared (Phase 3) |
| `mean_reversion` | — | — | — | — | (1 historical submission; same permutation_test blocker) | N/A until Phase 3 |

**Phase 4 directly helps `volatility_event` and `regime_arbitrage`** — the two hypotheses with non-trivial trade counts. It does NOT help:

- `relative_value` (97.5% zero-trade) — entry-side problem; needs **Phase 3.5** (template params widening + Crucible pair-universe expansion).
- `trend_continuation` and `mean_reversion` (0 ranked survivors due to `permutation_test` kills) — signal-quality problem; needs **Phase 3** (threshold auto-tightening).

So Phase 4 unlocks 2 of 5 hypotheses' trade-count ceiling; Phases 3 and 3.5 handle the other three.

---

## Design

**Grammar v3 §3.5 S5 — required-from-set + optional-additions per hypothesis:**

```yaml
# §3.5 S5 (grammar v3): exit composition per hypothesis.
# Sampler picks EXACTLY ONE from `required_from_set`, then OPTIONALLY adds
# zero or more from `optional_additions`. `forbidden` enforces exclusions.
hypothesis_exits:
  trend_continuation:
    required_from_set: [trailing_atr, chandelier_exit, parabolic_sar_exit]
    optional_additions: [theta_cliff_exit, time_stop]
    forbidden: [hard_profit_target]
  mean_reversion:
    required_from_set: [time_stop, target_exit, zscore_reversion_exit]
    optional_additions: [iv_crush_exit]
    forbidden: []
  regime_arbitrage:
    required_from_set: [regime_flip_exit]   # single option for now — see Open Q
    optional_additions: [time_stop, theta_cliff_exit]
    forbidden: []
  relative_value:
    required_from_set: [convergence_exit]   # single option for now — see Open Q
    optional_additions: [time_stop, theta_cliff_exit]
    forbidden: []
  volatility_event:
    required_from_set: [iv_crush_exit, event_passed_exit]   # both required
    optional_additions: [theta_cliff_exit]
    forbidden: []
  tail_hedge:
    required_from_set: [roll_on_schedule_exit]   # tail_hedge filtered at sampler (D066)
    optional_additions: []
    forbidden: [hard_profit_target]
```

**Cardinality grammar (S5 rewrite):**
- Each config carries the §3.5 E1 mandatory exits (`expiry_exit`, `theta_cliff_exit`, `earnings_exit`, `liquidity_exit`) — unchanged.
- Sampler picks **exactly one** id from the hypothesis's `required_from_set` (or, for `volatility_event`, picks the entire required pair — handled as a special case OR by widening "exactly one" to "exactly one OR the whole set if it's a 2-member 'AND' bundle").
- Sampler then picks **0 to K** ids from `optional_additions` (where K is e.g. 2) — adds variation.
- Validator rejects any config whose exits contain a `forbidden` id, or whose exits don't include the required-from-set selection.

---

## Open questions (operator decision points)

**Q1 — Which new exits to ship?** Crucible's proposed `chandelier_exit`, `parabolic_sar_exit`, `target_exit`, `zscore_reversion_exit` don't exist in `crucible_contracts.KNOWN_EXIT_IDS` today. Two paths:

- **Option A (full).** Crucible ships new `ExitRule` implementations for all four, adds them to `KNOWN_EXIT_IDS` in `crucible_contracts.models`, bumps the contracts package version. Forge's grammar v3 references them. Bigger Crucible-side change.
- **Option B (minimal).** Use only EXISTING `KNOWN_EXIT_IDS` for the required-from-set. Limits diversity to what we already have:
  - trend_continuation: `{trailing_atr, time_stop}` (both existing)
  - mean_reversion: `{time_stop, regime_flip_exit}` (both existing; regime_flip_exit on MR is unconventional but mechanically valid)
  - Other hypotheses: single-option required_from_set + optional_additions still gives variation via the optional layer.

  Smaller blast radius, no contracts coordination required, but less diversity per hypothesis.

**Recommendation:** start with **Option B** for v3.0, ship the structural grammar change, then add new exits in v3.1 (Option A) once Crucible has implemented them. That sequences the dependencies cleanly.

**Q2 — How many optional exits maximum?** Bigger optional pool = more strategy-shape variation but harder to interpret. Suggest K=2 max optional additions for v3 (so total exits per strategy: 4 mandatory + 1 from required_from_set + 0-2 optional = 5-7 exits). The §3.5 E2 "at-most-2 stop-loss exits" rule remains the upper bound.

**Q3 — Should `optional_additions` be uniformly weighted or biased?** For v3 simplicity, propose **uniform random selection** of optional exits (each one picked independently with p=0.5, capped at K). Future versions could bias based on observed gauntlet outcomes (Phase 3 threshold-feedback territory).

**Q4 — How does `volatility_event` work?** It currently REQUIRES both `iv_crush_exit` AND `event_passed_exit`. Two-element required-AND vs one-from-set — make sure the grammar handles "required as a bundle" cleanly. Probably easiest: `required_from_set` lists ONE entry that's a tuple `("iv_crush_exit", "event_passed_exit")` for the volatility case. Or special-case it.

---

## Sampler changes (`src/forge/enumeration/sampler.py`)

Current `_build_exits`:

```python
def _build_exits(space, hypothesis, rng):
    ids = list(space.e1_mandatory)
    ids.extend(space.s5_required_by_hypothesis[hypothesis])
    deduped = list(dict.fromkeys(ids))
    return tuple(ExitSpec(id=eid, params=_exit_params(eid, rng)) for eid in deduped)
```

Becomes:

```python
def _build_exits(space, hypothesis, rng):
    ids = list(space.e1_mandatory)
    # v3 S5: required-from-set
    required_options = space.s5_required_set_by_hypothesis[hypothesis]
    chosen_required = rng.choice(required_options)
    if isinstance(chosen_required, tuple):  # bundle case (volatility_event)
        ids.extend(chosen_required)
    else:
        ids.append(chosen_required)
    # v3 S5: optional additions (0-2 per config; uniform p=0.5 each, capped at K)
    K_MAX_OPTIONAL = 2
    optional_pool = space.s5_optional_additions_by_hypothesis[hypothesis]
    optional_picks = [opt for opt in optional_pool if rng.random() < 0.5]
    ids.extend(optional_picks[:K_MAX_OPTIONAL])
    # Dedup (E1 + chosen required + optional may overlap)
    deduped = list(dict.fromkeys(ids))
    return tuple(ExitSpec(id=eid, params=_exit_params(eid, rng)) for eid in deduped)
```

**SearchSpace additions:** new `s5_required_set_by_hypothesis: Mapping[str, tuple[str | tuple[str, ...], ...]]` and `s5_optional_additions_by_hypothesis: Mapping[str, tuple[str, ...]]`. Both derived from `_S5_HYPOTHESIS_EXITS` (which gets restructured in grammar v3).

---

## Validator changes (`src/forge/grammar/custom_predicates.py`)

Current S5 predicate is just "required is subset of exits + no forbidden". The new predicate must additionally verify:

1. Exactly one element of `required_from_set` is present in `exits` (or the entire bundle for the 2-element AND case).
2. All `optional_additions` actually present are from the allowed pool.
3. Total optional-additions count ≤ K_MAX_OPTIONAL.
4. No `forbidden` exits present.

Add as a `custom_python` predicate in v3.

---

## Contracts dependency (Crucible-side)

**v3.0 with Option B (existing exits only):** zero Crucible-side changes. Pure Forge-side grammar bump.

**v3.1 with Option A (new exit_ids):** Crucible ships new `ExitRule` classes + `KNOWN_EXIT_IDS` update + contracts package version bump. Forge bumps `FORGE_EXPECTED_CONTRACT_VERSION` accordingly.

---

## Test plan

1. **Grammar archival check** (hard rule #10): `config/grammar.yaml` v2 → v3, archive v2 to `config/grammar_archive/v2.yaml`, append D-entry. Pre-commit hook enforces.

2. **Validator tests** (`tests/unit/test_grammar/test_custom_predicates.py`):
   - Required-from-set: exactly-one selection passes; zero or two-or-more from the set fails.
   - Optional additions: 0-K passes; K+1 fails.
   - Forbidden: any forbidden exit fails.

3. **Sampler tests** (`tests/unit/test_enumeration/test_sampler.py`):
   - Across 100 seeds: every hypothesis's required-from-set element appears at least once.
   - Optional additions distribute roughly uniformly.
   - No config exceeds K_MAX_OPTIONAL.

4. **Determinism** (§13.1 / hard rule #6): same `(grammar_version, registry_hash, seed)` produces byte-identical config sequence including exit composition.

5. **Property test:** 1,000 sampled configs all pass the updated validator (path (a) closure preserved).

---

## Rollout sequence

1. **Operator approves this design doc** (or requests changes).
2. **Land v3 grammar.yaml** + `_S5_HYPOTHESIS_EXITS` restructure (Forge-side, Option B).
3. **Bump grammar_version v2 → v3**, archive v2, append Decision Log entry (D071 placeholder).
4. **Update sampler + validator + tests** in the same commit.
5. **Restart forge.service** to pick up v3.
6. **Observe iter N+1+ telemetry** — `ranked_top_n_by_hypothesis` distribution should remain healthy; new diversity manifests as varied exit compositions in submissions.
7. **After 5-10 iters of v3 data,** decide whether to ship Option A (new exit_ids via Crucible-side `ExitRule` implementations).

---

## Risks + alternatives

- **Risk: S5 grammar change ripples through validator + sampler + ~5 tests.** Manageable; same scope as D068.
- **Risk: Optional-additions pool may include exits that conflict (e.g., two stop-loss exits + `trailing_atr` triggers §3.5 E2 'at-most-2 stop-loss').** Mitigation: the optional pool only includes non-stop-loss exits per hypothesis; if a hypothesis's `required_from_set` already contains a stop-loss (`trailing_atr` for trend), the pool excludes other stop-losses.
- **Risk: New exit IDs (Option A) require Crucible coordination — not on the critical path for the immediate v3.** Punt to v3.1.

**Alternatives considered:**

- **Sample params on the SINGLE existing exit per hypothesis** (e.g., `trailing_atr.activate_after_gain_pct` sweep). Considered. Rejected: doesn't address the structural exit-philosophy diversity Crucible identified; params can be tuned downstream.
- **Add new exit_ids as the FIRST move** (Option A first, Option B second). Considered. Rejected: requires Crucible coordination on the critical path; v3.0 with existing exits is a smaller, faster win that the operator can review and approve in isolation.
- **Defer Phase 4 until Phase 2/3 land.** Considered. Rejected: the n_trades=0 problem (Crucible-side dominant failure) doesn't improve from feedback-loop work; Phase 4 attacks it directly.

---

## Decision points for the operator

Before any code lands:

1. **Approve the required-from-set + optional-additions structure?** (Yes / requires changes)
2. **Pick Option B (existing exits only) for v3.0 vs Option A (new Crucible exits) immediately?** Recommendation: B for v3.0, A for v3.1.
3. **K_MAX_OPTIONAL = 2 reasonable?** (Or different cap)
4. **Approve grammar version bump v2 → v3?** (Required by hard rule #10 — grammar.yaml change demands archive + version bump + Decision Log entry)
5. **Any concerns about the `volatility_event` 2-element required-AND case?** The bundle-tuple-in-required_from_set approach is one option; an explicit `required_always` field is another (clearer but adds surface).

Once decided, this draft converts to a D071 Decision Log entry and the implementation follows the rollout sequence above. Expected scope: ~1 day of Forge-side work for v3.0 (Option B); +1 day if Option A ships Crucible-side new exits at the same time.
