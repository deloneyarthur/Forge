# Crucible response — PROMPT_6 + entry-features wire-up + iv-normalization rank mode

**From:** Crucible-side agent, 2026-05-18.
**To:** Forge `PROMPT_6_CRUCIBLE_EXIT_STUBS.md` + the deferred-work follow-up.
**Status:** Wave 1 + Wave 2 + Wave 3 (partial) shipped, plus the architectural follow-up that unblocked Wave 3 IV-rank mode.

---

## What's available now in Crucible's registry

### New calendar/event indicators (family=calendar, version=1)

| Indicator | Source | Notes |
|---|---|---|
| `days_to_cpi` | Hardcoded BLS calendar 2022-2026 | Refresh tuple annually |
| `days_to_nfp` | Hardcoded BLS calendar 2022-2026, first-Friday convention with July-4 shifts baked in | Refresh tuple annually |
| `days_to_opex` | Computed (third-Friday-of-month with NYSE holiday fallback via `Calendar.expiry_for`) | Maintenance-free |

All three support `default_far_value` param (default 999) for the sentinel. Use them as `regime_filter` signals in `volatility_event` configs on **ETF underlyings** (SPY/QQQ/IWM/DIA) where the existing `days_to_earnings` returns the 999 sentinel every bar.

### New / upgraded exit rules

| Exit id | Status | Params |
|---|---|---|
| `event_passed_exit` | Graduated from no-op stub to functional | `n_bars_after_entry: int = 3`, `event_indicator: str = ""` (set to `"days_to_earnings"` / `"days_to_fomc"` / etc. for true-event-date mode; empty = time-since-entry fallback) |
| `iv_normalization_exit` | New | `normalization_ratio: float = 1.5`, `min_holding_days: int = 5`, `use_iv_rank: bool = False`, `rank_threshold: float = 50.0` |
| `flow_reversal_exit` | **Still a no-op stub** | Blocked on GEX/VEX/CEX indicators graduating from NaN-stubs + BarContext extension. Forge configs referencing it validate but produce no trades. |

### Queue-time preflight extension

`runs_repository.queue_run` now rejects configs at submission time when:
- `hypothesis == "volatility_event"` AND
- underlying ∈ {SPY, QQQ, IWM, DIA} AND
- a regime/directional signal references `days_to_earnings`

Error message names the ETF-applicable substitutes: `days_to_fomc`, `days_to_cpi`, `days_to_nfp`, `days_to_opex`. Raised as `HypothesisUniverseIncompatibleError(RunsRepositoryError)` so the inbox-watcher catches it cleanly via the existing `except RunsRepositoryError` block.

### Position.entry_features now populated end-to-end

`Action` gained an `entry_features: dict[str, float]` field; `ComposableLongOptions` populates from each signal's `SignalVote.value`; `Backtester._action_to_position` threads it through to `Position.entry_features`. This is the structural unblock that made `event_passed_exit` true-event-date mode and `iv_normalization_exit` IV-rank mode possible.

For Forge: this means a `volatility_event` config whose signals reference `days_to_earnings` will have `position.entry_features["days_to_earnings"]` populated automatically at entry. `event_passed_exit` with `event_indicator="days_to_earnings"` reads from there.

## What Forge can do now (no Crucible-side coordination needed)

1. **Enumerate `volatility_event` configs on ETF underlyings** using `days_to_fomc/cpi/nfp/opex` as the regime gate. Previously these failed silently (0 trades) because `days_to_earnings` was the only event indicator and returned 999 on ETFs. Now there are 4 ETF-applicable event regime gates.
2. **Use `event_passed_exit` with `event_indicator` set** for true-event-date holding. Pair with the regime gate above so the position knows which event it was entered for.
3. **Use `iv_normalization_exit` with `use_iv_rank=True`** for carry-harvest hypotheses that buy premium when IV is depressed (entry-time rank low) and exit when IV has normalized (current rank > threshold AND > entry rank). Requires a signal that references `iv_rank` so the entry-time rank lands in `entry_features`.

## What Forge cannot do yet

1. **Use `flow_reversal_exit`** — registered as no-op. Forge configs referencing it pass validation but produce no flow-based exits (positions still close via mandatory exits + any other configured exits). This depends on (a) GEX/VEX/CEX/`put_call_flow` indicators graduating from NaN-stubs and (b) BarContext extension for current flow values. Both are net-new substantial work — not committed yet.

## Coordination action items

- **Re-run `scripts/export_registry.py`** on Crucible's side to refresh the registry export Forge reads at startup. The new indicators (`days_to_cpi/nfp/opex`) are registered but Forge won't see them until the export refreshes. The Crucible systemd publisher (`crucible-registry-publisher.service`) handles this on its schedule; if Forge needs them immediately, run the export manually.
- **No Forge code changes required** for any of the above. The new indicators show up in the registry export; Forge's enumerator can start referencing them in next batch.

## Commit references (Crucible)

- `0151782` — PROMPT_6 Wave 1 (3 calendar indicators + vol_event/ETF preflight)
- `fef8790` — PROMPT_6 Wave 2 + partial Wave 3 (pragmatic event_passed_exit + raw-IV iv_normalization_exit)
- `7ccc5b4` — entry-features wire-up scaffold (Action → Position end-to-end)
- `b0bbbf7` — event_passed_exit true-event-date mode using entry_features
- (this commit) — iv_normalization_exit IV-rank mode using entry_features + BarContext.current_iv_rank lazy cache

§20 Decision Log entries: `prompt6-wave1`, `prompt6-wave2-3`, `entry-features-wireup`, `event-passed-true-date`, `iv-normalization-rank-mode`.
