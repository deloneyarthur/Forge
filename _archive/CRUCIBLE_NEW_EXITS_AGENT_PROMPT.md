# Crucible: implement 4 new ExitRule classes for Forge grammar v3 (multi-exit)

**Authored:** 2026-05-19 (Forge-side; for hand-off to a Crucible agent in `/home/aj/proj/Crucible/`)
**Audience:** Crucible maintainer / agent + `crucible_contracts` maintainer
**Severity:** MEDIUM-HIGH — blocks Forge grammar v3 (Phase 4 multi-exit, D071); without it, Forge can only ship grammar v3 with the existing 13 `KNOWN_EXIT_IDS` and the diversity gain is much smaller

---

## Context

Forge's `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` Phase 4 (multi-exit grammar v3, D071) ships a §3.5 S5 rewrite from "exactly one required exit per hypothesis" to "required-from-set + optional-additions". Crucible's 3,829-cohort analysis identified single-exit-per-hypothesis as the **#1 cause of the 89.1% zero-trade rate** — different exit logics produce different trade-count and edge profiles for the same entry signal, but every config in a hypothesis currently gets the same exit.

Operator approved **Option A** of the Phase 4 draft (`/home/aj/proj/Forge/PHASE_4_MULTI_EXIT_DRAFT.md`): ship 4 new ExitRule implementations Crucible-side, along with the grammar rewrite Forge-side. This prompt covers the Crucible half.

## Required deliverables

Implement **4 new ExitRule classes** in Crucible, register them in the existing `ExitRule` framework, and add their IDs to `crucible_contracts.KNOWN_EXIT_IDS`:

### 1. `chandelier_exit`

**Semantics.** Trailing stop at `N × ATR(period)` below the highest high since position entry (long) or above the lowest low (short). Closes the position when price crosses that trail.

**Params (defaults shown):**
- `atr_period: int` — lookback for the ATR calculation, default 22 (standard chandelier).
- `atr_multiplier: float` — distance from extreme, default 3.0.
- `use_close: bool` — whether to trail off the close or the high-low extreme, default False (extreme).

**Use case.** Trend-following exit that stays loose enough to ride trends but exits when momentum reverses. Less aggressive than parabolic_sar, gives more room than trailing_atr.

### 2. `parabolic_sar_exit`

**Semantics.** Closes the position when price crosses the Parabolic SAR indicator's stop level (Wilder 1978). SAR accelerates toward price as the trend ages, so positions get tighter stops the longer they're open.

**Params:**
- `step: float` — initial acceleration factor, default 0.02.
- `max_step: float` — cap on acceleration, default 0.20.

**Use case.** Tightening trend exit — captures the bulk of a move while exiting before the inevitable mean-reversion. Tighter than chandelier_exit; more aggressive trend exit.

### 3. `target_exit`

**Semantics.** Closes the position at a fixed profit target relative to entry. Either ATR-multiplied or fixed-percentage.

**Params:**
- `target_atr_multiplier: float | None` — if set, close at entry + N × ATR(period). Default None.
- `target_pct: float | None` — if set, close at entry × (1 + N) for long, (1 − N) for short. Default 0.05.
- `atr_period: int` — used only when `target_atr_multiplier` is set, default 14.
- (Exactly one of `target_atr_multiplier` / `target_pct` should be non-None.)

**Use case.** Mean-reversion exit. Currently MR strategies only have `time_stop` — many would close at a known good profit if there were a target_exit available.

### 4. `zscore_reversion_exit`

**Semantics.** For pairs / spread-based strategies: closes the position when the spread z-score crosses back through a configurable threshold (typically near 0 — i.e., when the spread has reverted toward its mean).

**Params:**
- `exit_zscore: float` — close when `|spread_zscore| <= exit_zscore`. Default 0.5.
- `lookback: int` — z-score computation window. Default 60.

**Use case.** Replaces `convergence_exit` for `relative_value` configs. The existing `convergence_exit` uses internal logic; `zscore_reversion_exit` lets Forge tune the convergence threshold.

## Contracts changes

In `crucible_contracts.models` (Crucible's sibling repo `crucible_contracts/`):

**Update `KNOWN_EXIT_IDS`:**

```python
KNOWN_EXIT_IDS = frozenset(
    {
        # ... existing 13 entries ...
        # New for Forge grammar v3 (D071, 2026-05-19):
        "chandelier_exit",
        "parabolic_sar_exit",
        "target_exit",
        "zscore_reversion_exit",
    }
)
```

(Total 17 known exit IDs.)

**Bump `crucible_contracts` version:** minor-version bump (additive change), e.g., 1.X.0 → 1.(X+1).0. Update `crucible_contracts/__init__.py::__version__`.

`STOP_LOSS_EXIT_IDS` does NOT need to change. None of the new exits are stop-losses per §3.5 E2 — they're trend/profit/reversion exits. (operator can revisit later if they want to add stop-loss variants like `dynamic_stop_loss` etc.)

## ExitRule framework integration

Each new class should follow the existing `ExitRule` pattern in `src/optbt/strategy/exits/`. Typical structure:

```python
# src/optbt/strategy/exits/chandelier_exit.py
from optbt.strategy.exits.base import ExitRule

class ChandelierExit(ExitRule):
    id = "chandelier_exit"

    def __init__(self, params: dict, calendar: Calendar) -> None:
        self.atr_period = int(params.get("atr_period", 22))
        self.atr_multiplier = float(params.get("atr_multiplier", 3.0))
        self.use_close = bool(params.get("use_close", False))
        ...

    def should_exit(self, position: Position, snap: MarketSnapshot, portfolio: PortfolioState) -> bool:
        # Compute trail from position-entry extreme + ATR, compare to current
        ...
```

Register each in the ExitRule registry (`src/optbt/strategy/exits/registry.py` or wherever `build_exit()` dispatches) so `build_exit(spec.id, spec.params, calendar)` returns the appropriate instance.

## Verification

1. **Unit tests** for each ExitRule class:
   - Chandelier: trail follows the highest high; closes when price drops below `high - N×ATR`.
   - Parabolic SAR: accelerates per step until max_step; closes on the standard SAR cross.
   - Target: closes exactly when entry-relative target is hit.
   - Zscore reversion: closes when spread z reverts to within `exit_zscore` of zero.
2. **Integration:** a representative `StrategyConfig` carrying each new exit (one at a time, then in combinations) backtests cleanly without runner errors.
3. **`KNOWN_EXIT_IDS`** contains all 4 new IDs; `crucible_contracts` version bumped.
4. **No regressions** on existing exit tests.

## Out of scope

- Forge grammar v3 (Forge-side; this prompt only blocks it).
- Sampling distributions for the new params (Forge's sampler.py choice).
- Stop-loss variants (separate proposal if desired).
- Existing ExitRule classes (`trailing_atr`, `time_stop`, etc.) — unchanged.

## Coordinate

Forge-side companions:
- `PHASE_4_MULTI_EXIT_DRAFT.md` — full Phase 4 design doc (Option A approved).
- `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` — Phase 4 row pending D071.

Forge will:
1. Wait for this Crucible ship.
2. Bump `FORGE_EXPECTED_CONTRACT_VERSION` to match the new `crucible_contracts` version.
3. Land grammar v3 (D071) referencing the new exit_ids in `_S5_HYPOTHESIS_EXITS`.
4. Restart forge.service.

Operator-observable check after Forge v3 ships: next iter's submissions should carry varied `exits` lists across configs of the same hypothesis (e.g., trend_continuation configs sampling between `trailing_atr` / `chandelier_exit` / `parabolic_sar_exit` for their required exit, with `theta_cliff_exit` / `time_stop` added optionally).

Delete this prompt file after both the contracts package + the ExitRule implementations ship and Forge confirms v3 grammar enumerates the new exits without runner errors.
