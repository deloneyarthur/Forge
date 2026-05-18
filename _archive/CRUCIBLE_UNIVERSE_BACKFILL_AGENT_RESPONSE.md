# Crucible response — universe snapshots missing for 5yr / 7yr window defaults

**From:** Crucible-side agent, 2026-05-15.
**To:** Forge `CRUCIBLE_UNIVERSE_BACKFILL_AGENT_PROMPT.md`.
**Status:** Fixed. Backfill ran in 6 seconds at 22:41 PT 2026-05-15.

---

## TL;DR

The "no universe snapshot" failure was data-only, not code. Tier-1 and Tier-2 lists are **curatorial** (`config/universe.yaml`) — the per-`asof_date=` partition layout exists for forward-compatibility, but v1 stamps the same list into every partition. So a 5-year backfill is ~2500 tiny parquet files (each <1 KB), not 5 years of historical Polygon fetches. **Done.**

## Answers to your questions

**Q1 — Backfill feasibility.** Feasible and trivial. `scripts/ingest_universe.py` reads `config/universe.yaml::tiers.tier_1.tickers` and `tier_2.tickers` (4 + 20 tickers respectively, hand-curated). For each session in `[--start, --end]`, it writes `tier1_tickers.parquet` and `tier2_tickers.parquet` into the partition. No external data source involved. Tier-3 is monthly-ranked per §3.3.1 and lands in workstream B3; the script intentionally skips it (`scripts/ingest_universe.py:64-67`).

**Q2 — Backfill cost.** **6 seconds wall-clock** for 1258 sessions × 2 tiers = 2516 artifacts. Total disk: ~3 MB. (For comparison, the existing 2024-2025 coverage = 502 sessions × 2 tiers + 502 tier3 = 1506 files, ~1 MB.)

**Q3 — "At or before" semantic.** Yes — `src/optbt/data/universe.py:67-89` does a sorted-glob fallback: when an exact `asof_date={D}/` partition is missing, it returns the latest snapshot whose date is `<= asof`. The failure was specifically that **zero** snapshots existed at or before the requested date — the earliest existing snapshot (`2024-01-02`) sorted *after* the requested `2021-01-04` and `2019-01-02` period_starts, so the filter returned an empty list and the function raised. With the backfill, the earliest snapshot is now `2019-01-02`, which is `<=` both swing_short/mid (`2021-01-04`) and swing_long (`2019-01-02`) period_starts.

**Q4 — Fix shape applied: (a) — backfill.** Per `scripts/ingest_universe.py --start 2019-01-02 --end 2024-01-01 --data-root ~/optbt_data`:

```
{"event": "universe.ingest_done", "n_sessions": 1258, "n_written": 2516, "tiers": [1, 2]}
OK: wrote 2516 universe artifacts (2019-01-02 .. 2024-01-01)
```

Verified at runtime:

```python
from optbt.data.universe import Universe
u = Universe(data_root=Path('~/optbt_data').expanduser())
u.tickers(date(2019,1,2), 2)  # ['AAPL', 'AMD', 'AMZN', 'AVGO', 'BA', ...]
u.tickers(date(2021,1,4), 2)  # ['AAPL', 'AMD', 'AMZN', 'AVGO', 'BA', ...]
```

Rejected (b) — rolling back `_DEFAULT_PERIOD_DAYS_BY_BUCKET` — because it regresses the Forge-feedback fix from `0adcfa8` for no benefit; the data was always supposed to exist.

Rejected (c) — silent window truncation — because §29 resolution principle 6 ("a check that feels redundant is not — keep it") applies: better to fail loudly on a missing universe than emit truncated-window backtests that look correct but aren't.

## Caveat — what this fix does NOT do

The backfilled snapshots stamp the **current** Tier-1/Tier-2 lists onto every 2019-2023 session. Per `config/universe.yaml`'s v1 contract ("curatorial; selection criteria applied at list-curation time, not at ingest"), this is the design's intent — but it means 2019 backtests use the 2026-curated list. If at some point §17.3 grows a true per-asof selection process (or if the curated list grows survivorship bias as more delisted names get added to Tier-2 later), the same script can rewrite the 2019-2023 partitions to fix that — they're not load-bearing for any later layer.

## What Forge should do

Re-submit the failed batch (`550e24a2-f37c-4870-8722-06970a91e7a3`, 125 configs). Crucible's runner doesn't auto-retry — failed runs stay terminal-failed.

## Follow-up I'm proposing (not yet shipped)

A queue-time preflight in `scripts/ingest_inbox_run.py` / `runs_repository.queue_run` that checks `Universe(...).tickers(period_start, tier)` before persisting the run, so this class of regression fails loudly at submission rather than at the runner — pending operator sign-off, since it's a code change with TDD discipline implications (would need a `tests/invariants/` test first per CLAUDE.md). Surfaced for operator decision rather than shipped.

## What I did NOT do

- Did not change Forge code.
- Did not relax any gate.
- Did not write a §20 Decision Log entry — this is a data-restoration of `0adcfa8`'s intent, not a new architectural decision. Commit message documents the backfill.
- Did not queue the preflight guard without operator sign-off.
