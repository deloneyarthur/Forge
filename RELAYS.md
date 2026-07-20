# Relay ledger — live cross-system relay files (root `PROMPT_CRUCIBLE_*.md`)

One row per LIVE relay file; answered relays are archived to `_archive/` on
cleanup sweeps (D295 pattern). **Update this table at triage time** — when a
relay is written, carried, answered, or superseded (same-commit rule, like any
doc). States: `held` (drafted, awaiting operator carry), `carried` (sent,
awaiting their reply), `answered` (their reply landed — archive candidate),
`parked` (held indefinitely on an operator decision). Source of truth for
disputes: the cited D-entry, not this table. Created 2026-07-20 (D302,
ops-debt item 5b).

| File | Dir | State | Awaiting / archive condition | Ref |
|---|---|---|---|---|
| `PROMPT_CRUCIBLE_ALPHA_BUDGET_DSR.md` | → | held (since 07-08) | carry; archive after prereg `098ea730d5f2` resolves (≤07-21) | D207/D295 |
| `PROMPT_CRUCIBLE_COMBINED_RELAY_RESPONSE.md` | → | held | carry; archive after the v39→v40 MR read (~07-22/23) | D291/D295 |
| `PROMPT_CRUCIBLE_EV_DEREGISTRATION_RESPONSE.md` | → | held (NEW 07-20) | carry (the ACK takes effect on carry); archive after their deletion publishes + kelly dormancy verified in a batch | D303 |
| `PROMPT_CRUCIBLE_CORR_TO_BOOK_ASK.md` | → | held (NEW 07-20) | **operator go** — new-initiative ask, not a response | D302 |
| `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md` | → | held (since 06-28) | operator relay decision | crucible-handoff |
| `PROMPT_CRUCIBLE_HOUSEKEEPING_ASKS.md` | → | held (NEW 07-20) | carry (meta-king publisher + sma_slope + charged-DSR Qs) | D300 |
| `PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` | → | parked | Path C is parked (operator 06-15); refresh before any resume | D152 |
| `PROMPT_CRUCIBLE_SECTOR_ETF_XSECT_PRECHECK.md` | → | held (since 07-12) | operator relay decision (companion research = D269 DON'T-BUILD) | D269 |
| `PROMPT_CRUCIBLE_SMA_SLOPE_NOT_COMPUTED.md` | → | held | their writer fix unverified — re-probe before archiving | D254/D295 |
| `PROMPT_CRUCIBLE_STALE_VOLUME_METRICS_EXCLUDE.md` | → | held (since 07-12) | archive after prereg `098ea730` resolves | D295 |
| `PROMPT_CRUCIBLE_TIER_UNPIN_RESPONSE.md` | → | answered + superseded | carries the D294 supersession banner (adoption confirmation stands); archive candidate next sweep | D292–D296 |
| `PROMPT_CRUCIBLE_VE_PROGRAM_RESPONSE.md` | → | held | archive after their v38→v39 ve read (~07-21) | D289/D290/D295 |
| `PROMPT_CRUCIBLE_XSECT_CORRECTION_RESPONSE.md` | → | answered | their 07-20 v42 ack closed the loop (D296); archive candidate next sweep | D294/D296 |
