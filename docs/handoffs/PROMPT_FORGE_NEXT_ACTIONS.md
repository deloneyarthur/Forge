# Forge: next actions after D077-D079 landing

**Authored:** 2026-05-27
**Audience:** Forge maintainer / agent working in `/home/aj/proj/Forge/`
**Context:** D077 (rv_rank regime gate), D078 (dynamic universe + threshold feedback), D079 (relative_value underlying fix) have all shipped. Service restarted on grammar v4. Rate-limited waiting for Crucible to process batch `1a41005f...`.

---

## Current state

| Metric | Value | Notes |
|---|---|---|
| Tests | 1148 pass, 1 skip | ruff + mypy strict clean |
| Grammar | v4 | R2 expanded with rv_rank |
| Zero-trade rate | ~38% | Latest 1000-run cohort (May 24-26), pre-D077/D079 |
| Threshold tightenings | 14 active | From D073 proposer, in `config/auto_tightened_thresholds.yaml` |
| Service | Running, rate-limited | Waiting for prior batch to gate |

---

## Action 1: Monitor D077/D078/D079 impact (post-unblock)

Once the rate limiter unblocks and the next batch flows through Crucible:

1. **Check relative_value trade rate** — was 99% zero-trade with `underlying=None`. With real tickers assigned (D079), expect significant improvement.
2. **Check rv_rank configs** — do trend_continuation configs with rv_rank regime filters produce trades? Check the gated_runs export for configs containing `rv_rank`.
3. **Re-run the threshold proposer** once the new cohort has 200+ gated runs under the D077-D079 regime. The current 14 tightenings were trained on pre-fix data.

```bash
# After sufficient new gated runs accumulate:
.venv/bin/python scripts/propose_threshold_tightenings.py
systemctl --user restart forge.service
```

---

## Action 2: Hypothesis reweighting (Q20 follow-up)

The May 20 analysis showed `volatility_event` has the best edge density (9 of top 10 traded configs by n_trades) but was only 2.1% of the cohort. Under the round-robin scheduler this should be more balanced, but the D067 stratification weights may still need tuning.

**Steps:**
1. Pull the latest gated_runs export
2. Compute per-hypothesis: trade count distribution, zero-trade rate, best/worst indicators
3. If `volatility_event` or `trend_continuation` (now with rv_rank) consistently outperform, propose a D067 weight update
4. Any reweighting that relaxes a hypothesis's share goes through `OPEN_PROPOSALS.md` (hard rule #4)

---

## Action 3: Contracts gaps to surface upstream

These require `crucible_contracts` changes. Surface to operator for prioritization.

### 3a. `universe_min_asof` on RegistrySnapshot (Q19)

125 runs failed with "No universe snapshot at or before 2021-01-04" when windows widened. `RegistrySnapshot` exposes `data_start_date` (feature-cache anchor) but not `universe_min_asof` (universe table coverage floor). These can drift independently.

**Fix:** Add `universe_min_asof: date | None` to `RegistrySnapshot` (contracts v1.9.0+). Forge clips submissions against `max(data_start_date, universe_min_asof)`.

### 3b. Feature cache surface (Q10)

`SyntheticFeatureCache` is the only implementation. Pre-filter scores are internally consistent for ranking but absolute thresholds can't be validated against real Crucible data. Needs a contracts-level read surface for Crucible's feature cache.

**Status:** Deferred since Phase 3 (2026-05-13). No progress. Not blocking operations but limits pre-filter calibration accuracy.

---

## Action 4: Stub indicator monitoring (Q14/Q17)

Five Crucible-registered indicators historically returned NaN: `iv_rank`, `expected_value_estimator`, `vix_level`, `pairs_zscore`, `put_call_flow`. As of the May 20 analysis, they contributed to high zero-trade rates.

**Crucible may have fixed some of these since May 20.** Check:
1. Query the latest gated_runs for per-indicator zero-trade rates
2. If any of the five now produce trades at >50% rate, the stub has been replaced
3. If still broken, Forge's D076 empirical-prior filter should be suppressing those buckets automatically (reject when posterior P(trades) < 0.10 with ≥20 samples)

**No Forge code change needed** — the empirical-prior filter is adaptive. But if an indicator is genuinely dead, consider surfacing it to the operator for potential exclusion from the grammar.

---

## Action 5: Threshold proposer cadence

The D073 threshold feedback loop is now active. Recommended cadence:

1. **Run proposer weekly** (or after each significant code change that affects config generation)
2. **Review the YAML output** — verify tightenings look reasonable (proposed range strictly inside baseline)
3. **Check for loosening proposals** in `OPEN_PROPOSALS.md` — these require operator approval
4. **Restart service** after each proposer run to pick up new ranges

The proposer reads the latest `gated_runs_*.json` export. As the export limit was raised to 5000, later runs will have more training data.

---

## Not actionable yet (waiting on external)

| Item | Blocked on | Ref |
|---|---|---|
| Real feature cache | contracts v1.9.0+ surface | Q10 |
| Universe min_asof clip | contracts v1.9.0+ field | Q19 |
| Cross-batch no-promotion trigger | Real promotion data (≥2 batches) | Q9 |
| Stuck-state alerting | Operator decision on notification channel | Medium priority |

---

## Files changed in D077-D079 session

For reference, the full list of production files modified:

- `src/forge/grammar/custom_predicates.py` — R2 indicator set expanded, constant renamed
- `src/forge/enumeration/indicator_thresholds.py` — rv_rank threshold entry, role-aware `is_threshold_skippable`
- `src/forge/enumeration/sampler.py` — role-aware skip, chain-family C1 guard, rv_rank params, universe loader, relative_value underlying fix, lookback dedup
- `src/forge/enumeration/search_space.py` — constant rename import
- `src/forge/enumeration/_demo_registry.py` — rv_rank IndicatorMetadata
- `config/grammar.yaml` — v4, R2 version 2
- `config/grammar_archive/v4.yaml` — archive
- `config/auto_tightened_thresholds.yaml` — 14 tightenings from proposer
- `docs/GRAMMAR.md` — R2 section updated

No coordination doc — commits are the record.
