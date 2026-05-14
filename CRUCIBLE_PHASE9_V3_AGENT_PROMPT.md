# Crucible Phase 9 v3 — Indicator parity + EXPORT_LAYOUT registry publication

**Audience:** Crucible-side agent. Read this top-to-bottom; the brief is self-contained.

**Repository:** `/home/aj/proj/Crucible/` (your working directory).
**Sibling repos referenced (read-only for context):** `/home/aj/proj/Forge/`, `/home/aj/proj/crucible_contracts/`.
**Operator approval status:** Path A decided 2026-05-13 by operator after Phase 9 v2 closed. This prompt scopes the v3 follow-on.

---

## 1. Why this work exists

Forge's v1 go-live attempt on 2026-05-13 surfaced gaps in three layers — exits (v2 Gap 1), from-config dispatch (v2 Gap 2), forge-source gate evaluator (v2 Gap 3). Phase 9 v2 closed those.

The next layer surfaced as soon as v2 re-processed Forge's two re-queued runs:

```
runner_failed: Unknown indicator: 'iv_rank'              (forge_mean_reversion_*)
runner_failed: Unknown indicator: 'expected_value_estimator'  (forge_regime_arbitrage_*)
```

Forge's enumerator builds candidates from a `RegistrySnapshot` it currently sources from an in-Forge stub (`forge.enumeration._demo_registry`, "Phase 2 ships ahead of the Phase 4 Crucible-registry wiring"). That stub advertises **14 indicators**; Crucible's runtime implements **23 indicators**; the **intersection is 4**:

```
adx, hurst, realized_vol, rsi_2
```

Forge generates configs Crucible can't backtest because Crucible never published a real `RegistrySnapshot` for Forge to consume. The operator chose **Path A** (over Path B "shrink Forge grammar" and Path C "implement only load-bearing indicators"): **Crucible implements all 10 Forge-required indicators not currently in its runtime, then publishes `RegistrySnapshot` via `EXPORT_LAYOUT.registry_snapshot_*.json` so Forge can consume the canonical list.**

Forge-side `registry_loader.py` is being staged in parallel (this kickoff is written from the Forge side) — it falls back to the demo registry until a real snapshot appears in `~/optbt_data/exports/`, then picks up automatically.

---

## 2. Scope — what to ship

### 2a. Ten new registered indicators

Each indicator is one file in `src/optbt/features/<family>/<name>.py`, following the existing pattern (subclass `IndicatorBase`, `@register`, `ClassVar id/version/lookback`, `compute(bars: pl.LazyFrame) -> pl.Series`, one unit test under `tests/unit/features/`). Most have existing math or scaffolding to wrap.

| # | Indicator id | Family / file | Existing scaffolding | Notes |
|--:|---|---|---|---|
| 1 | `iv_rank` | `features/iv/iv_rank.py` | `features/iv/iv_history.py::iv_rank()` math already exists | Wrap as `IndicatorBase` subclass; param `window` (default 252); upstream dep `atm_iv` per `iv_history.py` docstring; ClassVar `version=1`, `lookback=252` |
| 2 | `expected_value_estimator` | `features/multi_factor/expected_value.py` (new) | none | **See §3 below for math spec.** Operator-recommended definition |
| 3 | `vix_level` | `features/macro/vix_level.py` | `features/macro/vix.py` exists | Wrap or extend `vix.py` to expose `vix_level` as a registered scalar series. May already exist under a different id — check first |
| 4 | `days_to_earnings` | `features/macro/days_to_earnings.py` (new) | `src/optbt/data/earnings.py` already exists | Per-ticker earnings calendar lookup → integer days; param `default_far_value` (default 999 for "no upcoming earnings") |
| 5 | `days_to_fomc` | `features/macro/days_to_fomc.py` (new) | none | Hardcoded FOMC schedule (8 meetings/year, publicly known); param table or yaml-loaded; integer days to next scheduled meeting |
| 6 | `pairs_zscore` | `features/pairs/pairs_zscore.py` (new) | `features/pairs/cointegration.py` exists | Spread = y - β·x where (y, x) is a configured pair; rolling z-score over `window` (default 60). Pair definitions live in `config/pair_candidates.yaml` already (per cointegration.py reference); reuse |
| 7 | `put_call_flow` | `features/dealer/put_call_flow.py` (new) | `chain_snapshots/` data + `features/dealer/aggregate.py` | Daily call_volume − put_volume aggregate, signed, normalized by total. **If chain_snapshots lack volume fields, defer to v1.1 with explicit deferral note.** |
| 8 | `momentum_252` | alias (no new file) | `features/price_trend/returns_12m_skip1` | Register `momentum_252` as an alias of `returns_12m_skip1` (or re-export with that id). Naming alias |
| 9 | `rsi_14` | alias / parameterized | `features/mean_revert/rsi` (existing) | Register `rsi_14` as `rsi(period=14)` — likely register a new class with id `rsi_14` that inherits from RSI with default period |
| 10 | `ema_50` | alias / parameterized | `features/price_trend/ema` (existing) | Same pattern as `rsi_14`: register `ema_50` as `ema(period=50)` |

Each indicator gets one test under `tests/unit/features/<family>/test_<name>.py` exercising the standard surface (id, version, lookback constants; compute output shape and sample values).

### 2b. EXPORT_LAYOUT registry publication

Per `crucible_contracts.formats.EXPORT_LAYOUT`:

```python
EXPORT_LAYOUT = DirectoryLayout(
    root_glob="~/optbt_data/exports/",
    files=("registry_snapshot_*.json", "promoted_strategies_*.json"),
)
```

Build a publisher that writes `~/optbt_data/exports/registry_snapshot_<UTC-isoformat>.json` containing the canonical `crucible_contracts.RegistrySnapshot` Pydantic JSON. Required fields (per contracts v1.6.0):

- `registry_version: str` (semver; bump when indicator set changes)
- `data_history_days: int` (≥1)
- `data_start_date: date`
- `indicators: tuple[IndicatorMetadata, ...]` — each `(id, version, family, lookback, params_schema)`
- `exits: tuple[ExitMetadata, ...]` — match Crucible's exit registry
- `(any other RegistrySnapshot fields per contracts 1.6.0)`

**Publication strategy (operator-approved default):** new CLI command `crucible registry publish` that writes one snapshot. Wire into:

1. A separate systemd unit `crucible-registry-publisher.service` running once per startup (Type=oneshot), OR
2. A new line in `crucible-runner` start hook that triggers a publish on first launch.

Pick whichever matches Crucible's existing service-orchestration norms.

### 2c. Per CLAUDE.md TDD discipline (Crucible's own)

Each indicator: red → green → refactor. Quality gates clean on changed scope (`ruff check`, `ruff format --check`, `mypy --strict`, full pytest). Crucible has 1552 tests as of 2026-05-13; the bar is "no regression."

---

## 3. Operator-recommended spec for items needing decision

The Forge-side scoping flagged 4 spec items. Operator chose Path A but didn't pre-resolve each one. Recommended defaults below — Crucible agent may push back on any of these by flagging in `IMPLEMENTATION_DECISIONS.md` (Crucible-side), but otherwise proceed with these:

### 3.1 `expected_value_estimator` math

§3.5 X2 of Forge's grammar names the indicator but doesn't define it. Crucible's fractional Kelly sizer consumes the output. Recommended definition:

```
EV(t) = win_rate(N) × avg_win(N) − loss_rate(N) × avg_loss(N)
```

where `N` is `window` parameter (default 60 most-recent signal firings), `win_rate = wins / (wins + losses)`, `avg_win` and `avg_loss` are in absolute return units (decimal, e.g., 0.025 = 2.5%). Output: one scalar series (per-bar) where each value is the EV computed over the trailing `window` resolved signals up to that bar. Used by Kelly fraction `f* = (b·p − q) / b` downstream.

Sources for "signal firings": the strategy's own historical signal firings within Crucible's `signals_fired` table for the same `config_hash`. If insufficient firings (< 30), output `NaN` so the sizer falls back to its default fraction.

### 3.2 `days_to_earnings` data source

Crucible has `src/optbt/data/earnings.py`. Use whatever that module already exposes (most likely a `get_next_earnings(ticker, asof) -> date | None`). If the module doesn't exist or doesn't return calendar data, surface the gap in `IMPLEMENTATION_DECISIONS.md` and defer this indicator with an explicit `OPEN_PROPOSALS.md` entry — but operator's strong preference is "find a way to wire something even if it's a placeholder Polygon call."

### 3.3 `put_call_flow` data source

Check `chain_snapshots/` for daily call/put volume columns. If present, compute as `(call_volume_sum − put_volume_sum) / (call_volume_sum + put_volume_sum)` daily aggregate per ticker, output as scalar series. If volume columns are absent: defer to v1.1, write `OPEN_PROPOSALS.md` entry tagged `data-dependency`, drop the indicator from this v3 ship. Forge will then refuse to enumerate configs that reference it (registry export won't advertise it).

### 3.4 `vix_level` data source

Crucible already has `features/macro/vix.py`. Inspect what it exposes; if it returns a scalar VIX series, just register it. If VIX bars aren't ingested yet, add a Polygon ingest for ticker `I:VIX` to the existing bars pipeline. Operator-side note: VIX is core to volatility regime gating; do not skip.

---

## 4. Acceptance criteria

This v3 work is done when **all** of:

1. `optbt.features.base.all_indicator_ids()` (or equivalent) returns a list that is a **superset of Forge's 14-indicator demo registry** (`adx, days_to_earnings, days_to_fomc, ema_50, expected_value_estimator, hurst, iv_rank, momentum_252, pairs_zscore, put_call_flow, realized_vol, rsi_2, rsi_14, vix_level`). Any deferred indicator (e.g., `put_call_flow` if chain_snapshots lacks volume) is documented in `OPEN_PROPOSALS.md` and listed under "deferred to v1.1" in the handoff.
2. One unit test per new indicator passes; full Crucible suite green.
3. `crucible registry publish` (or equivalent trigger) writes a `~/optbt_data/exports/registry_snapshot_<isotime>.json` that **parses cleanly as `crucible_contracts.RegistrySnapshot`** (no ValidationError).
4. The published JSON's `indicators` field includes every newly-registered indicator with truthful `family`, `lookback`, `params_schema`.
5. Re-queueing the two stranded forge-source runs (`682a54b6...` and `6195bb6b...`) and waiting one runner cycle results in both completing (no `Unknown indicator` errors); `promotion_decisions` rows are written (rejected verdict is fine — Forge just needs the rows).
6. Crucible's `CRUCIBLE_CHANGES.md` (if it tracks per-phase changes) gets a v3 entry; otherwise a Decision-log entry in `docs/DESIGN.md` §20.

---

## 5. Out of scope

- **Forge-side changes** — happening in parallel in `/home/aj/proj/Forge/` (see `forge.persistence.registry_loader`); your work doesn't touch Forge.
- **Contracts changes** — `crucible_contracts.RegistrySnapshot` already supports all needed fields (v1.6.0). No bump expected. If you find one needed, flag and pause — that's a contracts side-trip.
- **Calendar/options-flow data INGESTION pipelines** — if e.g. earnings calendar data isn't in `optbt/data/earnings.py`, defer-and-document rather than building the ingest. Crucible's data ingestion is its own workstream.
- **Real promotion gate evaluator** — Phase 9 v2 shipped the minimal subset gate (sharpe>0.5, n_trades≥30, max_dd≤30%, profit_factor≥1.0). Path A doesn't ask for the full campaign-level gate (CPCV, PBO, deflated_sharpe). That's separate.

---

## 6. Hand-off back to Forge

When done:

1. Comment in the operator's Forge-side session (or write a brief note in `~/optbt_data/exports/HANDOFF.md` if working asynchronously) confirming registry export landed + listing any deferred indicators.
2. Forge's `forge.persistence.registry_loader` will pick up the new snapshot automatically on next `forge.service` start. No Forge code changes needed unless you defer an indicator that's structurally required by §3.5 (e.g., R1 needs `iv_rank`, X2 needs `expected_value_estimator` — those CANNOT be deferred or Forge's grammar becomes unsatisfiable for mean_reversion or Kelly-sized configs).
3. Once registry export exists, operator restarts `forge.service`; the loop closes end-to-end for the first time.

---

## 7. References

- Forge `OPEN_QUESTIONS.md` Q11 (v1 go-live original 3-gap discovery) + Q12 (this 4th gap discovery, indicator vocab + Path A choice).
- Forge `IMPLEMENTATION_DECISIONS.md` D027 (v2 prerequisite acknowledgement) + D028 (this Path A scope decision).
- Crucible v2 commits as anchor of pattern: `5623d85` (Gap 1 exits), `d1322f5` (Gap 2 dispatcher), `7c7cd5d` (Gap 3 stub), `e45a90e` (Gap 3 minimal evaluator). Apply the same TDD + per-commit-cost discipline.
- `crucible_contracts.formats.EXPORT_LAYOUT` — the contract for the registry-snapshot file pattern.
- `crucible_contracts.models.RegistrySnapshot` — the file's shape.

Build slowly. Test ruthlessly. Trust the contract.
