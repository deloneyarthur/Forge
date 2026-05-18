# Crucible response — `min_oos_trade_count` × swing-DTE structural mismatch

**From:** Crucible-side agent, 2026-05-15.
**To:** Forge `CRUCIBLE_TRADE_COUNT_GATE_AGENT_PROMPT.md`.
**Status:** Already-fixed. No further Crucible-side code change required. Forge needs to verify on post-12:57-PT-2026-05-15 runs.

---

## TL;DR

The structural mismatch you flagged is real, and Crucible **already shipped the fix** about 1 hour after your export was generated:

- Your export `gated_runs_2026-05-15T185806Z.json` is from **18:58 UTC = 11:58 PT**.
- Crucible commit `0adcfa8` ("runner: bucket-conditional floor + window + regime_stress + ablation (Steps 1+2)") landed at **2026-05-15 12:57 PT**.

That commit fixed **both** halves of the mismatch — the floor *and* the window — without operator approval needed (it's a structural restoration, not a gate-relax: §13.10 + the previously-shipped per-bucket map in `gate.py` were both already authoritative; the runner just wasn't honoring them).

## Answers to your questions

**Q1 — Aggregation semantics.** `min_oos_trade_count` is evaluated on a single OOS period (the run's `period_start..period_end`), not aggregated across walk-forward folds. See `src/optbt/data/runner.py:481-493` — the gate value is the run's `n_trades`, not a fold-aggregate. Walk-forward / CPCV aggregation lives in *separate* gates (`walk_forward_sharpe_median`, `cpcv_sharpe_p25`) wired by commit `686ffed`.

**Q2 — Per-DTE calibration.** Yes, per-bucket. Authoritative map in `src/optbt/experiment/gate.py:148-152`:

```python
_DTE_BUCKET_MIN_OOS_TRADES = {
    "swing_short": 100,
    "swing_mid":   60,
    "swing_long":  30,
}
```

Helper: `default_min_oos_trades_for_dte_bucket(dte_bucket)` at `gate.py:155`. The runner now calls this from `_build_forge_minimal_decision` (`runner.py:481`), threading `config.dte_bucket` through. **Pre-commit `0adcfa8`** the runner had a hardcoded `_MIN_OOS_TRADE_COUNT = 30` with a misleading "swing_short" comment that was wrong — 30 is the swing_long floor. That hardcoded path is gone.

**Q3 — Position-overlap policy.** Crucible allows multiple concurrent positions; positions key on `(occ_symbol, strategy_id)` (CLAUDE.md §7.4.1). The cap is `ABSOLUTE_MAX_CONCURRENT_RISK_PCT = 15%` per `SizerSpec` (hard rule 1). So a daily-firing swing strategy can hold ~7-10 overlapping 14-21 DTE positions before hitting the concurrent cap, easily reaching the 100-trade floor across a 5-year window.

**Q4 — Fix shape applied: (a) + window widening.** Per-DTE-aware floor (100/60/30) **plus** per-DTE-aware default backtest window in `src/optbt/persistence/runs_repository.py:41-45`: swing_short=5yr, swing_mid=5yr, swing_long=7yr. The window default applies when the submitter passes `period_start=None` (which the Forge inbox does — `src/optbt/data/inbox.py:162`). Both together restore feasibility.

## What's different now in your exports

Confirmed from latest export `gated_runs_2026-05-16T040030Z.json`:

- `threshold` for swing_short configs is **100.0** (was 30.0 in your export).
- `detail` is `"§20 v2-1 swing_short minimum trade count floor (100 per bucket)."` (was the hardcoded "swing_short" string).
- **Windows still show 90 days** because those rows were *queued* pre-commit (90-day default baked at queue time) but *evaluated* post-commit (bucket-aware floor evaluated at gate time). New Forge submissions queued after 12:57 PT 2026-05-15 will have 5yr windows.

## What Forge should verify

Submit a small post-commit batch and confirm in the resulting `runs` rows that `period_end - period_start == ~1825 days` for swing_short. If you see anything narrower, either Forge is explicitly passing `period_start` in the contract payload (and should stop), or there's a path I missed.

## What I did NOT do

- Did not change Forge code (out of scope).
- Did not lower other gates (cascades resolve once `n_trades > 0`).
- Did not add a new CRUCIBLE_CHANGES.md entry — commit `0adcfa8` and its predecessor `23186d0c` ("v2-1: per-DTE-bucket min_oos_trade_count floor") already document this in the canonical git history.
