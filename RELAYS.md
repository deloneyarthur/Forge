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
| `PROMPT_CRUCIBLE_ALPHA_BUDGET_DSR.md` | → | answered (was answered 2026-07-08 all along — their `dffbb83`; the D295 "held" label was OUR mislabel, corrected D304) | archive candidate; Forge owes the Q2 follow-up (`search_n_trials` population, per-slot semantics) | D304 |
| `PROMPT_CRUCIBLE_COMBINED_RELAY_RESPONSE.md` | → | held | carry; archive after the v39→v40 MR read (~07-22/23) | D291/D295 |
| `PROMPT_CRUCIBLE_EV_DEREGISTRATION_RESPONSE.md` | → | answered + VERIFIED (their `FORGE_ev_deletion_executed_2026-07-20.md`: deletion 22:31–33Z, sequencing honored; dormancy verified by construction + count — 4 post-publish batches / 800 configs, 0 kelly, first `9cca352a` under id-less hash `83e9a01c`; carries the CLOSED banner w/ the export `other`-bucket note) | archive candidate next sweep | D303/D308 |
| `PROMPT_CRUCIBLE_CORR_TO_BOOK_ASK.md` | → | carried (07-20, operator) | their answer (additive field / decline); telemetry build follows only on a yes | D302 |
| `PROMPT_CRUCIBLE_V43_DEPLOYED.md` | → | held (NEW 07-21) | carry; asks: row-45 cross-check on the 30 names + `funnel --compare v42 v43`; archive after both | D309 |
| `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md` | → | held (since 06-28) | operator relay decision | crucible-handoff |
| `PROMPT_CRUCIBLE_SEARCH_N_TRIALS_INTERACTION.md` | → | answered + CLOSED; **carries a RESOLVED+receipts banner for the next carry** (stamp ARMED on the first v43 batch `03b33475` 02:07:37Z; slot spans 5,154–108,324; expect `dsr_below_bar` at volume immediately; stamp boundary = the v43 boundary) | carry the banner (bundles w/ `PROMPT_CRUCIBLE_V43_DEPLOYED.md`); archive after | D306/D310 |
| `PROMPT_CRUCIBLE_HOUSEKEEPING_ASKS.md` | → | answered (same-day: their `FORGE_housekeeping_answers_2026-07-20.md`) | archive candidate next sweep; all three asks closed (timer repurposed-not-meta-king — permanently answered, stop asking; sma_slope wired; DSR was answered 07-08) | D300/D304 |
| `PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` | → | parked | Path C is parked (operator 06-15); refresh before any resume | D152 |
| `PROMPT_CRUCIBLE_SECTOR_ETF_XSECT_PRECHECK.md` | → | held (since 07-12) | operator relay decision (companion research = D269 DON'T-BUILD) | D269 |
| `PROMPT_CRUCIBLE_SMA_SLOPE_NOT_COMPUTED.md` | → | answered + VERIFIED (writer wired via their §20 registry-drift guard; Forge re-probe 07-20: `check-activations` GO — sma_slope max 537 / ad_slope max 440 on 4 names) | archive candidate next sweep; v24 trend adoption carries for real | D254/D304 |
| `PROMPT_CRUCIBLE_STALE_VOLUME_METRICS_EXCLUDE.md` | → | held (since 07-12) | archive after prereg `098ea730` resolves | D295 |
| `PROMPT_CRUCIBLE_TIER_UNPIN_RESPONSE.md` | → | answered + superseded | carries the D294 supersession banner (adoption confirmation stands); archive candidate next sweep | D292–D296 |
| `PROMPT_CRUCIBLE_VE_PROGRAM_RESPONSE.md` | → | held | archive after their v38→v39 ve read (~07-21) | D289/D290/D295 |
| `PROMPT_CRUCIBLE_XSECT_CORRECTION_RESPONSE.md` | → | answered | their 07-20 v42 ack closed the loop (D296); archive candidate next sweep | D294/D296 |
