# H1 + H2 → grammar v12 — implementation spec (fresh-pass handoff)

**Status:** Implementation spec for a fresh focused session. Builds on the committed base
(`HEAD = 9db01a1` D108 H4 orthogonal-yield, on `14864d5` D107 v11 H3). Tree clean; service
live on v11 (rate-limiter-blocked → 0 v11 cohort).
**Version:** grammar v11 → **v12** (the next increment — v11 is committed/immutable). See §3.
**Upstream: LANDED + VERIFIED 2026-06-08** (Crucible commits): contracts **1.16.0**
(`cross_sectional_rank` / `event_momentum` / `post_event_drift` literals); the
`cross_sectional_rank_composable` runner (reads `combiner.rank_k`); `event_momentum` dispatch;
registry `days_since_earnings` + `sue`; Polygon EPS ingest. **Both Forge asks resolved** by
`../Crucible/docs/handoffs/FORGE_days_since_earnings_family_response.md`: (1) `days_since_earnings`
→ family **`calendar`** shipped (per-id override, the D019 `adx`/`hurst`→`trend_strength` precedent;
no `config_hash` / version impact) → the H2 C1 conflict is gone; (2) dispatch route **CONFIRMED**
composable (no `top_n` stamp needed). So this is pure **Forge-side enumeration work** — no
contracts/runner blockers left. **One caveat (§2.1): the registry EXPORT Forge reads must refresh**
— as of snapshot `2026-06-08T132237Z` it still advertises `days_since_earnings=post_event_drift`
(stale); H2 needs the republished export advertising `calendar`. H1 is unaffected.

Program context: the binding constraint is **breadth** (`min_oos_trade_count ≥ 100` kills 98%;
0 promotions ever; components are the currency at 1.83%). H1 manufactures breadth; H2 is a new
directional thesis that rides the event calendar. Full rationale: `NEW_HYPOTHESES_V11_PLAN.md`.

---

## 1. H1 — `cross_sectional_rank` combiner (the breadth lever)

### 1.1 Emission contract (VERIFIED against `../Crucible/src/optbt/strategy/templates/cross_sectional_rank_composable.py`)
Forge emits a config where:
- `combiner.type = "cross_sectional_rank"`, `combiner.rank_k = K`,
  `combiner.rebalance_frequency ∈ {"weekly","monthly"}`, `combiner.direction_mode ∈ {"long_only","long_short"}`.
  (Contracts renamed our requested `k` → `rank_k` to avoid colliding with the confluence `k`;
  it's identity-bearing only for rank configs, dropped from `config_hash` otherwise.)
- Signals: a **directional** signal (drives the rank score) + ≥1 **regime_filter** (S3). The
  runner routes `role == "regime_filter"` → gates, everything else → the rank score.
- **`underlying = None`** — the runner ranks over `universe.tickers(asof, tier)`; its
  `required_underlyings` is the all-tier union. A single underlying is meaningless here (mirror
  `relative_value`, which already sets `underlying=None`).
- `tier` selects the ranking universe pool. Selector/sizer/exits: normal.
- Runner behavior: each rebalance, rank the universe by the directional score, take top `rank_k`
  LONG (+ bottom `rank_k` for `long_short`), hold, rebalance. **Trade count ≈ rank_k ×
  rebalances — deterministic**, which is the whole point (defeats the 100-trade floor).

### 1.2 Scope: which hypotheses
A combiner OPTION for the breadth-starved **directional** archetypes: **`trend_continuation` +
`mean_reversion`**. (vol_event is event-single-name; relative_value is pairs — leave both on
`confluence`.) **The directional family + C2 + R1/R2 are UNCHANGED** — H1 reuses the existing
trend/mean-rev signal machinery; it only swaps the combiner + sets `underlying=None`. This makes
H1 much smaller than a wholesale restructure.

### 1.3 Forge changes
1. **`grammar.yaml`** v11→v12 + version note (combiner type isn't in the 21 rules' text →
   enumeration policy, the v5–v11 pattern; the note documents v12). Archive `v12.yaml`.
2. **`sampler.py`** (`sample_config` / the combiner-construction path): for hypothesis ∈
   {trend, mean_rev}, sample `combiner.type ∈ {confluence, cross_sectional_rank}` — start
   cross_sectional at a modest **exploration share** (e.g. ~⅓), feedback can rebalance later.
   For a rank draw: sample `rank_k ∈ {5,10,20}`, `rebalance ∈ {weekly,monthly}`,
   `direction_mode ∈ {long_only,long_short}`; set `underlying=None`; keep the directional +
   regime signal draw as-is. (No `DISABLED_COMBINERS` scaffold exists — H1 was never scaffolded;
   this is net-new. Determinism: hard rule #6 — gate the new draws so cold/`{}` paths stay
   byte-identical, like every prior weight addition.)
3. **`search_space.py`**: expose `cross_sectional_rank` as a combiner option for trend/mean_rev.
4. **Pre-filters — the load-bearing gotcha.** The `expected_trades` prefilter
   (`forge.feedback.trade_rate_priors`) keys on historical *single-name* trade rates; a
   cross_sectional config has none → it must NOT be killed on stale single-name priors (that
   would defeat the breadth win). Either compute expected trades **structurally** for rank
   configs (`≈ rank_k × n_rebalances` over the OOS window → always ≫ 100) or COLD_START them.
   This is the single most important correctness point for H1.
5. **`config_hash` / dedup**: confirm rank configs hash distinctly (the rank_k/rebalance/
   direction_mode fields are identity-bearing for rank type — contracts handles this).
6. **Tests**: sampler emits valid rank configs (combiner fields set, `underlying=None`);
   `validate()` passes; determinism (cold path byte-identical); expected_trades **passes** rank
   configs; the dedup/idempotency invariant holds.

### 1.4 Integration — CONFIRMED (Crucible response, no action)
Dispatch routes Forge's `cross_sectional_rank` configs to the **composable** runner by
construction: `_detect_strategy_name` (`../Crucible/src/optbt/data/runner.py:602-607`) — a
`forge_*`-named config with `combiner.type == "cross_sectional_rank"` returns
`cross_sectional_rank_composable` **before** the hypothesis map, so it wins regardless of
hypothesis. The legacy `top_n` template is reachable only by the bare name `"cross_sectional_rank"`,
which Forge's `forge_<hypothesis>_<bucket>_<hash>` scheme precludes. Pinned by
`test_composable_dispatch.py::test_forge_cross_sectional_rank_combiner_routes_to_rank_template`.
**No `top_n`/`bottom_n` stamp needed** — the composable runner ignores signal `top_n` (reads
`combiner.rank_k`). Just emit `combiner.type="cross_sectional_rank"` + `rank_k`.

---

## 2. H2 — `event_momentum` / PEAD (a new directional hypothesis)

### 2.1 The C1 item — RESOLVED (option (a) shipped); ONE export-refresh check
Crucible shipped the recommended fix: **`days_since_earnings` → family `calendar`** (per-id
override in `exports.py`, the D019 precedent; export-only metadata, no `config_hash`/version
impact). So `sue` (post_event_drift, directional) + `days_since_earnings` (calendar, post-event
timing gate) now sit in different families → **C1 allows both → the PEAD structure is expressible.**
- **CHECK BEFORE BUILDING H2:** the registry EXPORT Forge reads must advertise the new family.
  As of `registry_snapshot_2026-06-08T132237Z` it is **stale** (`days_since_earnings=post_event_drift`).
  Confirm `load_registry()` returns `family=="calendar"` for `days_since_earnings` (republished
  export) before relying on the two-signal structure; the test fixture
  (`minimal_registry_snapshot`) must also reflect `calendar` for the H2 C1/C2 tests. If the export
  hasn't refreshed when H2 starts, ping Crucible to republish (or it lands on their next cycle).

### 2.2 Structure
event_momentum is a directional long-options thesis on the post-earnings drift → routes to the
existing `composable_long_options` template (like trend/mean_rev/vol_event), with:
- **directional** = `sue` (post_event_drift) — surprise sign/magnitude → drift direction.
- **regime/timing gate** = `days_since_earnings` (calendar, post-(a)) — "fire within N days
  *after* the print" (op `"<"`, e.g. `days_since_earnings < {3,5,10}`). This is the PEAD edge:
  enter AFTER the print → sidesteps the IV crush the vol_event sleeves ride → structurally
  ORTHOGONAL to our existing components.

### 2.3 Forge changes (assuming (a))
1. **`custom_predicates.py`**:
   - `_C2_HYPOTHESIS_FAMILIES`: add `"event_momentum": ("post_event_drift",)`.
   - Regime requirement: event_momentum needs a **post-event** gate (`days_since_earnings`).
     Mirror R3's pattern (a `_R*_EVENT_MOMENTUM_REGIME = ("days_since_earnings",)` constant + the
     regime-pool wiring) — Python-side, no new grammar.yaml rule (like R3's `_R3` list). Decide
     whether it's a distinct predicate or folded into the regime-pool builder for the new hypothesis.
   - `_S5_HYPOTHESIS_EXITS["event_momentum"]`: drift-decay `time_stop` in `required_from_set`;
     momentum trailing (`trailing_atr`/`chandelier_exit`) as `optional_additions`; **no
     `hard_profit_target`** (convex payoff, like the winners) → `forbidden`. Plus E1 mandatory.
2. **`search_space.py`**: add `event_momentum` to the enumerable hypotheses; directional pool =
   post_event_drift = `{sue}`; regime pool = `{days_since_earnings}`.
3. **`sampler.py`**: add to samplable hypotheses; **horizon/DTE** — event_momentum is a 5–20-day
   post-event drift → swing_short/mid. Add a horizon handling branch (like vol_event's
   event-bracket, or a fixed drift window) so the bucket is derived sensibly.
4. **`indicator_thresholds.py`**: add `sue` (directional: fire when `|sue| >` threshold — strong
   surprise) and `days_since_earnings` (regime: `< {3,5,10}` td, op `"<"`).
5. **`signal_horizon.py`**: `sue` ≈ 10 td (drift window); `days_since_earnings` timing.
6. **Tests**: event_momentum samples valid configs; C1 (post-(a)) / C2 / regime / S5 pass;
   drift exits; determinism.

### 2.4 Breadth note — H2 needs H1
PEAD on a SINGLE name ≈ 20 earnings/5y — **below the 100-trade floor**. So single-name
event_momentum will mostly die at `expected_trades` (correct). The productive form is
**cross-sectional event_momentum**: rank the universe by post-earnings drift, trade top-K — which
is how quant PEAD is actually run AND clears breadth via H1. **So: implement H1 first, then let
event_momentum ALSO use `cross_sectional_rank`** (§1.2 scope extends to event_momentum). Single-name
event_momentum is fine as exploration but expect thin trade counts.

---

## 3. Versioning + sequencing

- **The next grammar version is `v12`** (v11 is committed/immutable; every enumeration change
  v5→v11 bumped for Crucible `--compare`). H1 + H2 both introduce new enumerable structures
  (combiner type; hypothesis) that are **self-identifying in `config_json`**, so the by-feature
  join (forge.db ⋈ gated export, keyed on `combiner.type` / `hypothesis`) attributes each arm
  even if bundled.
- **Bundle vs split:** H1 is fully unblocked; H2 has the §2.1 coordination item. **Recommended:
  ship H1 as v12 when ready; H2 as v13 once §2.1 resolves** (each ships when unblocked, the
  H3=v11 / H1H2=v12 precedent). Bundle both into v12 only if §2.1 resolves before H1 ships.
- **Per-arm sequence:** (1) H1 single-arm (breadth, fully unblocked) → (2) resolve §2.1 with
  Crucible → (3) H2, ideally cross-sectional from day one (§2.4).
- TDD throughout (red→green; the expected_trades-passes-rank test is the key H1 invariant); full
  suite; ruff + mypy; the D104 deploy ritual (stop → uncontended suite → commit → restart); A/B
  via `crucible funnel --compare v11 v12` + the by-feature join. New Decision Log entries
  (D109 H1, D110 H2 or as bundled); GRAMMAR.md sync; archive `v12.yaml` byte-identical.

## 4. Crucible coordination — RESOLVED
1. ✅ Dispatch → composable runner (combiner.rank_k), no `top_n` stamp. Confirmed + test-pinned (§1.4).
2. ✅ H2 C1 — `days_since_earnings` → `calendar` shipped (§2.1). `sue` + `days_since_earnings` coexist.
3. ✅ event_momentum timing-gate is a Forge signal (`days_since_earnings`, op `"<"`, post-event window) — option (a), not runner-internal.

**Only residual:** confirm the registry export Forge reads has refreshed to advertise
`days_since_earnings=calendar` before the H2 build (§2.1) — Crucible-side republish, not a design item.
Source: `../Crucible/docs/handoffs/FORGE_days_since_earnings_family_response.md`.

## 5. Quick map (files this touches)
`config/grammar.yaml` (+ `grammar_archive/v12.yaml`), `src/forge/grammar/custom_predicates.py`,
`src/forge/enumeration/{sampler,search_space,indicator_thresholds}.py`,
`src/forge/grammar/signal_horizon.py`, `src/forge/feedback/trade_rate_priors.py` (the rank
expected-trades fix), `docs/GRAMMAR.md`, `IMPLEMENTATION_DECISIONS.md`, `STATUS.md`, and tests
under `tests/unit/test_enumeration/`, `tests/unit/test_grammar/`, `tests/invariants/`.
Verified Crucible refs: `cross_sectional_rank_composable.py` (H1 contract), registry
`days_since_earnings`/`sue` (H2), contracts `models.py` `CombinerSpec` (rank fields).
