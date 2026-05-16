# Crucible — universe snapshots missing for new 5yr / 7yr window defaults

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-15 — Forge operator flagged during post-`0adcfa8` verification.

---

## 1. The pattern

Forge submitted batch `550e24a2-f37c-4870-8722-06970a91e7a3` (125 configs) at 22:15 PT 2026-05-15. 21 minutes later, **0/125 are gated**. Every single run is failing in the runner *before backtest begins* with one of two errors:

```
runner_failed: "No universe snapshot at or before 2019-01-02.
                Run scripts/ingest_universe.py to populate."
runner_failed: "No universe snapshot at or before 2021-01-04.
                Run scripts/ingest_universe.py to populate."
```

Failure distribution from `journalctl --user -u crucible-runner.service --since=-30min`:

```
112  at or before 2021-01-04   (swing_short + swing_mid, 5yr lookback)
 13  at or before 2019-01-02   (swing_long, 7yr lookback)
  0  successful runs
```

Origin source: `src/optbt/data/universe.py` raises when no `asof_date <= period_start` is found.

## 2. Root cause

Crucible commit `0adcfa8` ("runner: bucket-conditional floor + window + regime_stress + ablation") set per-bucket default windows in `src/optbt/persistence/runs_repository.py:41-45`:

```python
_DEFAULT_PERIOD_DAYS_BY_BUCKET = {
    "swing_short": 365 * 5,   # 5 yr — need ~100 trades at ~25/yr
    "swing_mid":   365 * 5,   # 5 yr — need ~60 trades at ~12/yr
    "swing_long":  365 * 7,   # 7 yr — need ~30 trades at ~5/yr
}
```

For runs queued after 12:57 PT 2026-05-15, `period_start` is now:
- swing_short / swing_mid: `today - 5yr` ≈ **2021-01-04**
- swing_long: `today - 7yr` ≈ **2019-01-02**

But Crucible's `/home/aj/optbt_data/universe/` directory only contains **502 snapshots covering 2024-01-02 → 2025-12-31** — about 2 years of coverage. There are no snapshots for 2019, 2020, 2021, 2022, or 2023.

Result: the gate-floor + window fix from `0adcfa8` is structurally unrunnable on the current universe data. The Forge pipeline is producing valid configs that Crucible cannot evaluate.

## 3. What's already known / done (don't redo)

- Forge side: D031 threshold widening + registry re-publish (committed yesterday). No Forge code change needed for this issue.
- Crucible side: per-DTE floor + window map shipped in `0adcfa8`, verified live in 22:14 PT batch.
- Forge inbox.py passes `period_start=None` so the new defaults apply (confirmed by Crucible agent's prior response).

## 4. Questions to answer

Please investigate and report back:

1. **Backfill feasibility**: Can `scripts/ingest_universe.py` produce snapshots back to 2019-01-02 from data Crucible already has access to (Polygon? local CSVs?), or is the historical universe data source not available? Cite the script's data source.

2. **Backfill cost**: If feasible, what's the rough wall-clock time to ingest ~5 additional years of daily snapshots (~1260 trading days)?

3. **Correctness check**: Is a snapshot strictly required *at* `period_start`, or is the latest-available snapshot before `period_start` acceptable for a backtest? (The error string says "at or before", suggesting "before" already works — so the real question is whether there's *any* snapshot from before 2024, not whether it's exactly on the start date.)

4. **Fix shape**: Which is right?
   - (a) Backfill universe to 2019 via `ingest_universe.py` (preferred — restores intent of `0adcfa8`).
   - (b) Roll `_DEFAULT_PERIOD_DAYS_BY_BUCKET` back to a window the existing data supports (e.g. swing_short = 365*2, swing_mid = 365*2, swing_long = 365*2). This regresses the gate-feasibility fix.
   - (c) Cap `period_start` at the earliest available universe snapshot date and emit a warning rather than failing. (Compromise — keeps batches flowing but shrinks effective window unevenly.)
   - (d) Something else suggested by what you find.

## 5. What you should NOT do

- **Do not change Forge code**. Forge has no role in window selection or universe ingestion.
- **Do not relax the gate** (`min_oos_trade_count`). The per-DTE floors from `0adcfa8` are correct; they just need data underneath them.
- **Do not silently swallow** the "no universe snapshot" error in the runner — better to fail loudly (as it does) than emit phantom backtest results.

## 6. Background data sources

- Forge submissions DB: `~/forge_data/forge.db` (3700+ rows)
- Crucible runs DB: `~/optbt_data/runs.duckdb` (writer holds lock; use proxy)
- Universe snapshots: `~/optbt_data/universe/asof_date=YYYY-MM-DD/...` (502 dirs, 2024-2025 only)
- Failing runs window: `journalctl --user -u crucible-runner.service --since=-30min | grep "No universe snapshot"`
- Window map: `src/optbt/persistence/runs_repository.py:41-45`
- Error source: `src/optbt/data/universe.py` (the `No universe snapshot at or before` raise site)
- Ingest script: `scripts/ingest_universe.py`

## 7. Output expected

Report back with:
1. Definitive answers to Q1-Q3 (cite file:line, list data sources used)
2. A recommended fix (a/b/c/d from §4, or a different shape)
3. If the fix is your work: ship it + a Decision Log entry in the canonical Crucible-side log citing this prompt. If the fix is a long-running ingest, kick it off and report ETA.
4. If the fix needs operator approval (e.g. backfill data costs money, or window rollback is a §13 invariant change): surface the trade-off and stop.

Brief is OK. Aim for under 500 words of report unless the investigation reveals something material.
