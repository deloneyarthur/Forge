# Crucible: expand `config/pair_candidates.yaml` (relative_value zero-trade crisis)

**Authored:** 2026-05-19 (Forge-side; for hand-off to a Crucible agent in `/home/aj/proj/Crucible/`)
**Audience:** Crucible maintainer / agent
**Severity:** HIGH — `relative_value` is **97.5% zero-trade** in the latest 1,000-cohort (309/317), bottlenecked by the narrow pair-candidate list

---

## Problem

Forge's `relative_value` hypothesis submits ~91 configs per iteration (post-D069 / D072) — they all route to Crucible's `pairs_convergence` template. Cross-tabulating the latest 1,000 gated_runs against Forge's submissions table:

| Hypothesis | 0 trades | 1-9 | 10-99 | 100+ | Total | % zero |
|---|---:|---:|---:|---:|---:|---:|
| `relative_value` | **309** | 8 | **0** | **0** | 317 | **97.5%** |

**Zero configs reach the 10-trade bucket. Zero ever reach 100 trades.** The other hypotheses have varying trade-rate distributions; relative_value is the worst by an order of magnitude.

## Root cause (Forge-side diagnostic, 2026-05-18)

Forge's funnel walk on a representative `relative_value` config across 62 sessions × 15 pairs in 2025-Q1/Q2:

```
asof_total: 930
pvalue_fail (cointegration p>=0.05): 818  (88.0%)
zscore_fail (|z|<2.0): 96 of 112 pvalue-passers  (85.7%)
halflife_fail (hl outside 5-30): 13 of 16 zscore-passers  (81.3%)
entry_eligible: 3  (0.32%)
```

Per-pair breakdown showed that **only 2 of 15 pairs (PG-CL and GOOG-GOOGL) ever produce viable cointegration** in this window. Every other pair fails the `pvalue<0.05` test 100% of the time. Even at Forge's most aggressive sampler ranges (D072 shipped 2026-05-19 — `pvalue_max` widened to 0.10-0.25, `zscore_entry` to 0.5-1.5, halflife window 1-90 days), the underlying pair list is the gating constraint: **most pairs simply don't cointegrate in the 2025-Q1/Q2 period.**

## Current pair list (`config/pair_candidates.yaml`)

```yaml
within_sector_pairs:
  energy:           [XOM,CVX], [COP,EOG]
  financials:       [JPM,BAC], [GS,MS], [WFC,USB]
  consumer_staples: [KO,PEP], [PG,CL]
  tech:             [GOOG,GOOGL], [AMD,NVDA], [MSFT,ORCL]

cross_sector_pairs:
  cyclicals:        [XLF,XLI], [XLE,XLI]
  growth_vs_value:  [XLK,XLF], [XLY,XLP]
  size:             [SPY,IWM]
```

**Total: 15 pairs** (10 within-sector, 5 cross-sector). Only 2 produced viable signals in the Forge diagnostic. Effective pair universe is ~2.

## Fix scope

**Expand `config/pair_candidates.yaml` to 40-60 pairs** spanning:

1. **More within-sector pairs** across underrepresented sectors:
   - Healthcare: JNJ-PFE, MRK-LLY, UNH-CVS
   - Industrials: CAT-DE, BA-LMT, UPS-FDX
   - Utilities: NEE-DUK, SO-D
   - REITs: AMT-CCI, PLD-EQIX
   - Materials: FCX-NEM, DOW-LIN
   - Communications: T-VZ, DIS-CMCSA
   - Consumer discretionary: AMZN-TGT, LOW-HD, NKE-LULU

2. **More cross-sector ETF pairs**:
   - Style: SPYG-SPYV (growth vs value)
   - Region: SPY-EFA (US vs developed-ex-US), SPY-EEM (US vs EM)
   - Risk: SPY-TLT (equity vs treasury), QQQ-IEF (tech vs intermediate bond)
   - Volatility: SPY-VIX-related (if available)

3. **Single-name vs index proxies**:
   - AAPL-QQQ, MSFT-QQQ, JPM-XLF, XOM-XLE, JNJ-XLV
   - (Captures idiosyncratic drift of large constituents vs their sector ETF)

The exact pair selection is a judgment call — pairs should be plausibly cointegrated (e.g., same industry, share-class arb, large-cap-vs-sector). The above is illustrative; the operator likely has their own preferred list.

## Constraints

- **Both legs must exist in `bars_underlying`** — D068's diagnostic loaded bars for all 28 tickers in the current 15-pair list cleanly, so the bars table is permissive. Verify by `DataStore.load_underlying_bars` for any new ticker before adding to the YAML.
- **Both legs must exist in `options_data`** — the pairs_convergence template'll fail at the option-selection step (`ContractSelector.pick`) if either leg lacks an option chain. This is the harder constraint — check via `chain_snapshot_exists` for a representative recent date.
- **Pair stability** — `refresh.cointegration_check_freq: monthly` already in the YAML re-tests pairs monthly and prunes stale ones. The expanded list is self-pruning; over-inclusion is safer than under-inclusion.

## Validation harness (recommended)

Before committing the new YAML, run a one-time cointegration sweep over the expanded pair list against 2024-2025 SPY data:

```python
# Pseudo: for each candidate pair, count sessions where:
#   cointegration_test(y, x).pvalue < 0.10 AND |spread_zscore| > 1.0
# Pairs with viable_sessions / total < 1% are obvious duds (or
# fundamentally non-stationary in this period) — flag for operator
# decision rather than ship.
```

Forge's existing diagnostic at `/tmp/diag_relative_value.py` is one harness pattern; a similar Crucible-side script would let you sanity-check the expanded list before it ships.

## Verification

1. **Pair count target:** at least 40 total (vs current 15), with at least 25 within-sector and 15 cross-sector / index-vs-name.
2. **No regressions:** existing 15 pairs stay (PG-CL, GOOG-GOOGL produce signal — keep them; the others may be marginal but the monthly cointegration refresh self-prunes).
3. **Bars + options coverage:** every ticker in the new list has both `bars_underlying` and `options_data` partitions populated.
4. **Forge-side smoke test:** after the new YAML ships, the next Forge `relative_value` cohort should show a meaningful drop in zero-trade rate (target: ≤80% zero-trade vs current 97.5%).

## Out of scope

- The `pairs_convergence` template logic itself — its entry rule (pvalue / zscore / halflife) is fine; the issue is candidate pair scarcity.
- Forge-side sampler ranges — D068 + D072 already pushed the param space; further widening at this end is a separate Forge-side discussion.
- Adding new strategy templates (e.g., dispersion, vol-arb) — out of scope for this prompt.

## Coordinate doc

Forge-side companions:
- `IMPLEMENTATION_DECISIONS.md` D068 (initial pairs-template params, 2026-05-18).
- `IMPLEMENTATION_DECISIONS.md` D072 (range widening, 2026-05-19).
- `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 3.5 — this prompt is the Crucible-side half of that phase.

Live evidence: the latest 1,000-cohort gated_runs export at `/home/aj/optbt_data/exports/gated_runs_*.json` — filter by `config_hash` joined against Forge's submissions table for the per-hypothesis n_trades distribution above.

Delete this prompt file after the expanded YAML ships and a Forge iter confirms a measurable reduction in `relative_value` zero-trade rate (target: ≤80%).
