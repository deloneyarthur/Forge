# Crucible FeatureCache — Q10 closure / real feature cache for Forge

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/` (working directory).
**Sibling repos (read-only context):** `/home/aj/proj/Forge/`, `/home/aj/proj/crucible_contracts/`.
**Operator authorization:** 2026-05-14 (this brief is the Path A closure for Q10).
**Prerequisite:** Crucible Phase 9 v3 has already shipped (commit `phase9v3`); `crucible-db-writer.service` + `crucible-gated-runs-publisher.service` are running.

---

## 1. Why this work exists

Forge's pre-filter battery (DESIGN.md §5) consumes historical feature data via the `forge.prefilters.feature_cache.FeatureCache` Protocol:

```python
class FeatureCache(Protocol):
    data_history_days: int
    def activation_dates(self, signal_id: str) -> frozenset[date]:    # when did signal fire?
    def returns(self, dates: Iterable[date]) -> Mapping[date, float]: # daily returns at those dates
    def regime_label(self, d: date) -> Regime:                        # which regime is in effect
```

Forge currently ships `SyntheticFeatureCache` (Phase 3 D1, Q10 stopgap) which **deterministically stubs every value** from a SHA hash. Under Crucible's real 33-indicator registry the stub produces uniformly low signal-strength values → `permutation_test` rejects 100% of candidates per batch (logged 2026-05-14 as Q13 in Forge's `OPEN_QUESTIONS.md`).

Q10 closure ships the real Crucible-backed implementation. Forge swaps `SyntheticFeatureCache` for `CrucibleFeatureCache` behind the same Protocol; pre-filter survival rate becomes data-grounded.

Forge has been waiting on this since Phase 3 (D021 D1 noted: "Crucible's feature cache doesn't exist yet, so Forge defines a Protocol + SyntheticFeatureCache; real cache lands in Phase 4/5").

---

## 2. Scope — what to ship

### 2a. Three computed features, keyed by signal_id

Forge constructs `signal_id` as a content hash of `(SignalSpec.type, SignalSpec.role, sorted(SignalSpec.indicators), canonical(SignalSpec.params))`. The function is `forge.ranking.signal_key.content_key(signal)` — **move it to contracts** so both sides compute the same id (see §3 below).

For each `signal_id`, Crucible computes:

#### `activation_dates(signal_id) -> frozenset[date]`

Dates on which the signal would have fired over the cached window (default 1008 trading days = ~4 years per RegistrySnapshot.data_history_days).

Algorithm:
1. Decode `signal_id` → original `SignalSpec`. Either by reverse-lookup from a signal_id→spec table (Crucible records every spec it's asked about) OR by accepting both `signal_id` AND the `SignalSpec` in the query (cleaner — no reverse lookup needed; Forge has the spec already).
2. For each indicator in `signal.indicators`: instantiate via `optbt.features.base.build(indicator_id, params)`; call `.compute(bars_lazy)` → series.
3. Apply the signal's predicate over the series (e.g., `threshold` → `series < params['threshold']`).
4. Collect dates where the predicate evaluates True.
5. Cache result keyed by `signal_id` in a new `feature_cache` DuckDB table.

Recommended: accept `SignalSpec` directly in the query so no reverse-lookup table is needed. The signal_id is computed Crucible-side as a sanity check + cache key.

#### `returns(dates) -> Mapping[date, float]`

Daily total returns for the requested dates. Pure lookup from `bars_underlying/` data (already there). No per-signal computation. Default underlying: SPY for v1 (or whatever the operator's primary universe is — see Crucible DESIGN.md §6).

#### `regime_label(date) -> Regime` where `Regime = Literal["bull", "bear", "low_vol", "high_vol", "trending", "ranging"]`

Classify each date into one of 6 macro regimes. **Crucible already has `vol_regime` indicator** at `src/optbt/features/realized_vol/vol_regime.py` — its output is a {low_vol, high_vol} classifier. The 6-regime classifier likely needs to be built composing `vol_regime` + a trend/range classifier (e.g., from EMA cross + ADX) + a bull/bear classifier (e.g., from SPY 200-day moving average).

If the 6-regime classifier isn't reasonable to compose from existing indicators, defer to a simpler subset (`low_vol`/`high_vol` only) and document the partial coverage. Forge's pre-filter `regime_exposure` will still work — it just sees fewer regime variations.

### 2b. Batch query API via `db_writer` socket

The publisher pattern (registry, gated_runs) doesn't fit feature_cache: `signal_id` space is enormous, materializing JSON per-signal is wasteful. Instead, **extend `db_writer.py`'s existing socket protocol** (Crucible already supports read queries over the socket per the `_is_read_only_sql` dispatch added pre-v3):

Add a new request kind (or piggyback on `request_kind="execute"` with a special SQL routing convention):

```python
@dataclass
class FeatureBatchRequest:
    request_kind: Literal["feature_batch"]
    signals: list[SignalSpec]          # full specs, Crucible computes id + caches
    feature_names: list[Literal["activation_dates", "returns", "regime_label"]]
    dates: list[date] | None = None    # for returns / regime_label
    data_history_days: int = 1008      # caching window
```

Response: `dict[signal_id, dict[feature_name, value]]`.

Cache hit on (signal_id, feature_name, window_hash) → return cached value. Cache miss → compute + insert into `feature_cache` table + return.

### 2c. `feature_cache` DuckDB table

New table in `runs.duckdb` (managed by `db_writer`):

```sql
CREATE TABLE feature_cache (
    signal_id       VARCHAR(16) NOT NULL,
    feature_name    VARCHAR(32) NOT NULL,
    window_hash     VARCHAR(16) NOT NULL,    -- hash of data window for cache invalidation
    value_json      JSON NOT NULL,           -- serialized activation_dates / returns / regime_label
    computed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (signal_id, feature_name, window_hash)
);
```

`window_hash` lets us invalidate cache when the underlying data window changes (e.g., new bars ingested). Per §13.2 version-bump pattern from existing indicator caching.

---

## 3. Contracts changes — `crucible_contracts` v1.9.0

### 3a. Move `signal_content_key` from Forge to contracts

Currently `forge.ranking.signal_key.content_key(signal)`. Move to `crucible_contracts.signal_content_key`. Both Forge and Crucible import from contracts.

Forge changes:
- `src/forge/ranking/signal_key.py` becomes a thin re-export wrapper for backward-compat (or simply removed and call sites updated)

Crucible changes:
- import from `crucible_contracts.signal_content_key`

Reason: this is a cross-system identity function. Hard rule #2 — owns by contracts.

### 3b. New `FeatureCacheClient`

```python
class FeatureCacheClient:
    """Client to Crucible's feature cache via the writer socket.

    Forge constructs one per process; reuses connection across batches.
    """
    def __init__(self, socket_path: Path, authkey_path: Path, db_path: Path): ...
    def get_features(
        self,
        signals: Sequence[SignalSpec],
        feature_names: Sequence[Literal["activation_dates", "returns", "regime_label"]],
        *,
        dates: Sequence[date] | None = None,
        data_history_days: int = 1008,
    ) -> dict[str, dict[str, Any]]: ...  # signal_id → feature_name → value
    def close(self) -> None: ...
```

Returns a nested dict; Forge's CrucibleFeatureCache adapter unpacks into Protocol calls.

### 3c. New `FeatureBatchRequest` / `FeatureBatchResponse` Pydantic models

For wire serialization. Both Forge and Crucible import.

### 3d. Bump

`_version.py`: 1.8.0 → 1.9.0. `pyproject.toml` too. ~12 new tests (signal_content_key, FeatureCacheClient, request/response model validation).

---

## 4. Forge-side adapter (companion change, after contracts v1.9.0 lands)

`src/forge/prefilters/crucible_feature_cache.py` — new module implementing the Protocol:

```python
class CrucibleFeatureCache:
    """Real FeatureCache backed by Crucible's writer-socket query API.

    Constructed once per pre-filter battery pass; queries on demand;
    in-memory LRU caches the small per-signal responses so repeated
    queries within a batch don't hit the socket.
    """

    data_history_days: int

    def __init__(self, client: FeatureCacheClient, *, data_history_days: int = 1008): ...

    def activation_dates(self, signal_id: str) -> frozenset[date]: ...
    def returns(self, dates: Iterable[date]) -> Mapping[date, float]: ...
    def regime_label(self, d: date) -> Regime: ...
```

CLI sites in `forge.cli.main` swap `SyntheticFeatureCache(...)` for `CrucibleFeatureCache(client)`. The Protocol contract is unchanged so pre-filter code doesn't move.

Test isolation: existing `SyntheticFeatureCache` stays for unit tests + the synthetic fixtures. Integration tests opt in to the real adapter via fixture.

---

## 5. Acceptance criteria

Done when **all** of:

1. **Crucible side:**
   - `optbt.persistence.db_writer` accepts FeatureBatchRequest via socket; computes features on cache miss; persists to `feature_cache` table; returns response.
   - 3 features implemented: activation_dates (working over real bars + indicator math), returns (lookup from bars_underlying), regime_label (composed from existing indicators or partial coverage with documented gap).
   - Cache invalidation rule documented: window_hash detects underlying-bars updates.
   - `feature_cache` table schema in migrations + applied at startup.
   - Tests: per-feature unit test + integration test that constructs a SignalSpec, calls the publisher, receives valid response.
2. **Contracts v1.9.0:**
   - `signal_content_key` moved from Forge; tests verify it agrees with Forge's prior implementation.
   - `FeatureCacheClient` + `FeatureBatchRequest`/`FeatureBatchResponse` shipped + tested.
   - `CONTRACT_VERSION` = "1.9.0", pyproject too.
3. **Forge:**
   - `forge.prefilters.crucible_feature_cache.CrucibleFeatureCache` implements the Protocol against `FeatureCacheClient`.
   - 4 CLI sites that build `SyntheticFeatureCache(...)` updated.
   - Pin bumped to 1.9.0.
4. **End-to-end validation:**
   - Restart `forge.service`; observe `ranked_top_n > 0` (some candidates survive).
   - Pre-filter survival rate is roughly 1-20% per batch (not 0%, not 100%).
   - Crucible's runner processes the new survivors; gate evaluator writes `promote`/`reject`/`borderline` decisions.
   - At least one batch shows survival end-to-end.

---

## 6. Out of scope

- **Real gate evaluator** — Crucible Phase 9 v2's `e45a90e` minimal evaluator is fine; full §8.7 gate (CPCV, PBO, deflated_sharpe, walk_forward_median, regime_stress, ablation_arm) is a separate workstream.
- **Multi-underlying support** — Crucible's `bars_underlying/` has many tickers but Forge's enumeration currently targets SPY. Multi-underlying is a separate scope.
- **6-regime classifier** if it requires substantial new modelling — defer to a 2-regime (low_vol / high_vol) subset with documented partial coverage. Forge's `regime_exposure` filter still works.
- **Async / parallel feature computation** — the socket pattern is synchronous. If throughput is insufficient for production, add a worker pool inside `db_writer` in a follow-on.

---

## 7. Test data flow (end-to-end smoke after landing)

```
1. Forge: enumerate 200 candidates per batch
2. Forge per-pre-filter: gather all signal_ids in batch; call client.get_features([sigspec, ...], ["activation_dates", "returns"], dates=...)
3. Contracts: serialize request, send via socket
4. Crucible db_writer: dispatch to feature_batch handler
5. Crucible: for each signal_id, check feature_cache table; on hit, return cached value; on miss, compute (run indicator + apply predicate), insert into table, return
6. Crucible: serialize response, send back via socket
7. Forge: unpack response into Protocol calls; pre-filter battery scores honestly
8. Forge: top-N by composite score, submit batch
9. Crucible runner: backtests each submission with real indicator math
10. Gate evaluator: emits promote/reject/borderline based on real metrics
11. Crucible gated-runs publisher: writes gated_runs_*.json
12. Forge rate limiter: clears once 80% gated
13. Forge submits next batch; loop continues
```

---

## 8. References

- Forge `forge/prefilters/feature_cache.py` — the Protocol + `SyntheticFeatureCache` it replaces.
- Forge `forge/ranking/signal_key.py` — `content_key(signal)` to move to contracts.
- Forge OPEN_QUESTIONS.md Q10 (FeatureCache deferral) + Q13 (current 0-survivor symptom).
- Forge IMPLEMENTATION_DECISIONS.md D028 (Path A operator decision), D029 (v1 go-live operational).
- Crucible commit `phase9v3` — pattern for cross-repo work + publisher service.
- Crucible `optbt/persistence/db_writer.py` — existing socket protocol with read support (`_is_read_only_sql` dispatch).
- `crucible_contracts.formats.EXPORT_LAYOUT` — symmetric pattern; FeatureCache uses socket instead of files but the integration discipline is the same.

Build slowly. Test ruthlessly. Trust the contract.
