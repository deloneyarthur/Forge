# Crucible handoff — publish + widen the universe (Forge generator-diversity lever)

**Authored:** 2026-05-29 (Forge generator-quality session; operator-approved "widen to ~152")
**Owner:** a fresh agent in `../Crucible` (+ a small `../crucible_contracts` decision, see §3)
**Forge side:** NO code change required. Forge already reads the universe via the blessed
`crucible_contracts.load_universe_tickers_from_export` helper (D093); it just needs a
`forge.service` restart after the export first appears (its `_load_underlyings` is `lru_cache`d).
**Related:** Forge `OPEN_QUESTIONS.md` Q25, `IMPLEMENTATION_DECISIONS.md` D093/D087/D085,
`Crucible/docs/handoffs/PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md` (read-side, already shipped),
`PROMPT_FORGE_TICKER_EXPANSION.md` (the ~152 bar-data set).

---

## Why

Forge picks every candidate's `underlying` from the universe Crucible publishes. Today Crucible
**publishes nothing** — there is `build_universe_tickers()` / `write_universe_tickers()` in
`src/optbt/data/exports.py` but **no `publish_universe_tickers()` and no publisher
script/service** — so the file `~/optbt_data/exports/universe_tickers*.json` never gets written,
and Forge correctly falls back to a hardcoded 24-ticker list (logs `universe_fallback_hardcoded
n_tickers=24` every iteration).

Two facts make this worth doing now:
1. **24 is also the canonical Tier 1+2** (`config/universe.yaml`: tier_1=4 + tier_2=20;
   `build_universe_tickers()` deliberately excludes tier_3). So even fixing the publisher alone
   leaves the pool at 24 — identical to the fallback. The log is cosmetic until the universe is
   actually widened.
2. Forge's binding problem is **zero-trade rate** (~60% of real-decision gated runs trade 0 times;
   `min_oos_trade_count` is the dominant gate failure). More tradable underlyings is one of the few
   structural levers that increases trade opportunities — the operator has approved widening to the
   **~152** names Crucible already has bar data for (`~/optbt_data/bars_underlying/`, ~153 dirs;
   Tier 3 ≈ ranks 25-100 by volume).

## What to build (two parts)

### Part A — wire a universe publisher (closes the Q25/D093 gap)
Mirror the three working exports, each of which has a `publish_*` fn + a script + an enabled
systemd unit:
- `publish_registry_snapshot` (`exports.py:~318`) ↔ `scripts/export_registry.py` ↔
  `crucible-registry-publisher.service`
- `publish_gated_runs_snapshot` (`exports.py:~563`) ↔ `scripts/export_gated_runs.py` ↔
  `crucible-gated-runs-publisher.service`
- `publish_promoted_strategies_snapshot` (`exports.py:~727`) ↔ `scripts/export_promoted_strategies.py`
  ↔ `crucible-promoted-strategies-publisher.service`

Add the missing fourth:
1. `publish_universe_tickers(exports_root: Path | None = None) -> Path` in `exports.py` —
   timestamped atomic write of `universe_tickers_<ts>.json` (reuse `_timestamped_snapshot_path` +
   the same tmp-then-rename atomic write the others use).
2. Either a new `scripts/export_universe.py` + `crucible-universe-publisher.service` (copy the
   registry unit verbatim, swap the ExecStart), **or** — simpler, since the universe and registry
   both derive from static config — fold a `publish_universe_tickers()` call into the already-running
   `crucible-registry-publisher` loop so they co-publish. Operator's call; co-publishing is less
   surface area.

A one-shot `uv run python -c "from optbt.data.exports import publish_universe_tickers;
publish_universe_tickers()"` should immediately produce the file so Forge can be unblocked on its
next restart without waiting for the timer.

### Part B — widen the published set to ~152
`build_universe_tickers()` currently reads tier_1 + tier_2 from `config/universe.yaml` and excludes
tier_3. To reach ~152, choose one (operator preference: the larger, liquidity-screened set):
- **B1:** expand `config/universe.yaml` tier_2 to the target names, OR
- **B2:** change `build_universe_tickers()` to include tier_3 (ranks 25-100). Note tier_3 is
  described as dynamic/monthly — decide whether the published universe should be a point-in-time
  snapshot (re-published monthly by the timer) or a frozen list. A point-in-time snapshot is fine
  for Forge (the universe is folded into Forge's batch-identity fingerprint, D085, so enumeration
  determinism tracks each change).

## §3 — contracts consideration (decide before B2)

`crucible_contracts.load_universe_tickers_from_export` (D093, contracts 1.13.0) currently
**unions/sorts/dedupes the `tier_1` + `tier_2` keys** of the export payload. So:
- If you widen via **B1** (everything lands in `tier_1`/`tier_2`), **no contracts change** — the
  helper already reads it. Simplest path; recommend this.
- If you widen via **B2** and emit a separate `tier_3` key, the helper must be extended to read it
  (a `crucible_contracts` minor bump + Forge re-pin). To avoid that, have `build_universe_tickers()`
  fold tier_3 into the `tier_2` key of the *export payload* even if it's a distinct tier in
  `universe.yaml`. Then no contracts change is needed. **Recommend folding into tier_2 in the export
  to keep the read-side contract stable.**

## Cautions (please confirm before shipping)

1. **Feature-cache / prefetch cost scales with universe size.** Forge's throughput is *already*
   prefetch-bound (~1800-2540s/iteration, Q22) and that's on 24 underlyings. Going to ~152 will
   multiply the per-batch feature-cache prefetch / bar-data load. **Confirm Crucible's
   `prefetch_for_batch` + feature cache can handle ~152 underlyings without blowing the iteration
   budget** (and that bulk-activation `PROMPT_CRUCIBLE_FEATURE_CACHE_PERF` #2 lands first if needed).
   If prefetch can't scale, stage the widening (e.g., 24 → 60 → 152) and watch `phase_timings`.
2. **Indicator + bar-data coverage** must exist for all ~152, or those underlyings just produce
   zero-trade configs (self-limiting waste, not a correctness bug).
3. **Liquidity.** Tier 3 names are less liquid; Forge's `SelectorSpec` liquidity defaults
   (`min_open_interest=100`, `min_volume=10`, `max_bid_ask_spread_pct=0.10`) still apply, so thin
   names may simply not fill — acceptable, but expect some of the widening to be absorbed by these
   filters rather than producing trades.

## Acceptance

- `~/optbt_data/exports/universe_tickers_*.json` exists, parses, contains the target ~152 tickers,
  and is refreshed by a timer/loop (not a one-shot).
- `crucible_contracts.load_universe_tickers_from_export(Path("~/optbt_data/exports").expanduser())`
  returns the ~152-ticker tuple (run from either repo's venv).
- After a `forge.service` restart: the journal no longer logs `universe_fallback_hardcoded`;
  `_load_underlyings` returns the ~152 set; new submissions span the widened underlying pool.
- A `phase_timings` check on the first 1-2 post-widening Forge iterations confirms prefetch stayed
  within an acceptable budget (caution #1).

## Forge-side follow-up (Forge owns, after the file lands)
- Restart `forge.service` (clears the `lru_cache` on `_load_underlyings`).
- Confirm the new underlying spread in `submissions` and watch the zero-trade rate over the next
  cohort — this is the metric the widening is meant to move.
