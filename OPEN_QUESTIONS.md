# Forge — Open Questions

Append-only. Each entry: date, question, what I did instead, severity (low / medium / high).
Operator reviews at every phase boundary.

---

## 2026-05-13 — Q7 — Grammar fields missing from `crucible_contracts.StrategyConfig` — **HIGH SEVERITY, BLOCKING PHASE 1**

**Question:** The §3.5 grammar rules reference fields that do not exist on `crucible_contracts.StrategyConfig` / `SignalSpec`. How should these be carried?

**What's missing (cross-referenced spec rule → contracts field):**

| Spec rule cites | Spec field name | Contracts has? |
|---|---|---|
| S1 ("one hypothesis per strategy") | `hypothesis` ∈ {trend_continuation, mean_reversion, regime_arbitrage, relative_value, volatility_event, tail_hedge} | **NO** — no `hypothesis` field on `StrategyConfig` |
| S2 ("one directional signal") | `signals[*].role` ∈ {directional, regime_filter, filter, confluence} | **NO** — `SignalSpec` has only `id`, `type`, `indicators`, `params` |
| S3 ("at least one regime gate") | `signals[*].role == regime_filter` | **NO** (same as S2) |
| C1, C2 (family rules) | `signals[*].family` ∈ {trend, mean_reversion, volatility, iv_structure, dealer_positioning, flow, macro, calendar, fundamental, smart_money, pairs} | **PARTIAL** — `IndicatorMetadata.family` exists but uses a different 9-value enum: `mean_revert, price_trend, realized_vol, iv, macro, pairs, smart_money, multi_factor, dealer`. Spec lists 11 families; 3 don't exist in contracts (`flow, calendar, fundamental`); 1 contracts-only (`multi_factor`). Renaming conventions also differ (`mean_revert` vs `mean_reversion`, `price_trend` vs `trend`, etc.). |
| E1 (mandatory exits) | "Every strategy includes `expiry_exit`, `theta_cliff_exit`, `earnings_exit`" — **3 exits** | Contracts `MANDATORY_EXIT_IDS` has **4**: `expiry_exit, theta_cliff_exit, earnings_exit, **liquidity_exit**`. |

**What I did instead:** halted before any code lands. Phase 1 cannot proceed because:
- I can't write a `cardinality` predicate for `field: hypothesis` if `hypothesis` doesn't exist on the model.
- I can't write a `cardinality` predicate for `field: signals.role.directional` if `role` doesn't exist on `SignalSpec`.
- I can't write a `forbids` predicate referencing `signals.family` without a lookup convention.

**Severity:** **high** — structural blocker for Phase 1. Picking silently means either (a) inventing fields on a model the contracts package owns (violates hard rule #2), (b) shimming with `signals[*].params["role"]` strings (loose typing, will break refactors), or (c) deriving fields via lookups that the spec doesn't define.

**Options for the operator (numbered for reference in reply):**

1. **Extend `crucible_contracts`** (cleanest; treats this as the gap the kickoff anticipated):
   - Add `hypothesis: Literal[...]` to `StrategyConfig`.
   - Add `role: Literal["directional","regime_filter","filter","confluence"]` to `SignalSpec`.
   - Reconcile `IndicatorMetadata.family` enum with the §3.5 C1 family list (decide: 9, 11, or some merged set; pick canonical spellings).
   - Resolve E1 mandatory-exit count (3 vs 4; recommend accepting contracts' 4 since the contracts validator enforces it).
   - Bump `crucible_contracts` to **1.2.0** (additive: minor). Forge's `FORGE_EXPECTED_CONTRACT_VERSION` follows.

2. **Encode in `SignalSpec.params`** (no contracts change):
   - `hypothesis` lives on `StrategyConfig.signals[0].params["hypothesis"]` (or a separate top-level convention).
   - `role` lives on `signal.params["role"]`.
   - `family` is derived: `signal.indicators[0]` → `RegistrySnapshot.indicators` lookup → `IndicatorMetadata.family`.
   - Forge encodes/decodes via helpers; the grammar predicates use dotted paths into `params`.
   - Stringly-typed; refactors brittle; no validation that the params dict carries the expected keys.

3. **Forge-side annotation field** (least clean):
   - Forge submits configs with an extra `forge_metadata: dict` field that Crucible ignores. Hypothesis/role live there.
   - Violates the "no extra fields" extra="forbid" pydantic config on `StrategyConfig` — would require a contracts change too. So this collapses into option 1.

4. **Defer Phase 1 grammar to v1.1; ship a simpler grammar for v1.0** that only validates fields actually present on contracts (`dte_bucket`, `sizer.mode`, `signals[*].type`, `exits[*].id`, etc.). Loses S1, S2, S3, parts of C1, C2 — about 1/3 of the spec rules. The grammar becomes structurally weaker but immediately implementable.

**Recommendation:** option 1. The contracts package is explicitly named in PIPELINE.md §7 as "the integration boundary" and the kickoff anticipates "missing model or field — surface as a contracts gap." This is precisely that case. Minor version bump (1.1 → 1.2) is additive and won't break Crucible / QuantIQ.

**Note on family-list mismatch (sub-question if option 1 chosen):** the spec's `flow`, `calendar`, `fundamental` families aren't in contracts; contracts' `multi_factor` isn't in the spec. Pick the canonical list and align both sides. My read: spec list (11) is more domain-faithful; contracts is missing common categories. But this is a domain question.

**Surfaced 2026-05-13 by agent.** Awaiting operator decision before any Phase 1 code.

**Resolution 2026-05-13:** Operator chose **option 1** (extend `crucible_contracts` to v1.2.0) and **11-family canonical list** (spec's). See `IMPLEMENTATION_DECISIONS.md` D007 for the full resolution. Forge remains paused at Phase 1 kickoff until contracts v1.2.0 ships. Owner of the contracts change still TBD.
