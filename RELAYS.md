# Relay ledger — live cross-system relay files (root `PROMPT_CRUCIBLE_*.md`)

One row per LIVE relay file; answered relays are archived to `_archive/` on
cleanup sweeps (D295 pattern). **Update this table at triage time** — when a
relay is written, carried, answered, or superseded (same-commit rule, like any
doc). States: `held` (drafted, awaiting operator carry), `carried` (sent,
awaiting their reply), `answered` (their reply landed — archive candidate),
`parked` (held indefinitely on an operator decision). Source of truth for
disputes: the cited D-entry, not this table. Created 2026-07-20 (D302,
ops-debt item 5b). Last sweep 2026-07-21 (D321): 7 closed-loop relays archived
(ALPHA_BUDGET_DSR, EV_DEREGISTRATION_RESPONSE, HOUSEKEEPING_ASKS,
SMA_SLOPE_NOT_COMPUTED, TIER_UNPIN_RESPONSE, XSECT_CORRECTION_RESPONSE,
REFUTATION_REGISTRY_REPLY — the last on the v46 wiring decision shipping).
Follow-through 2026-07-21 (D322): the 4 live untracked relays (Q46_GO_CONFIRM,
Q46_MULTIGATE_SCOPING, Q46_READ_INVERSION, SEARCH_N_TRIALS_INTERACTION) committed
to close the D104 tree-clean gap; V44_DEPLOYED archived (superseded by v45 — the
read-pin lives in Q46_READ_INVERSION's v45 banner; boundary record preserved in
`_archive/`).

| File | Dir | State | Awaiting / archive condition | Ref |
|---|---|---|---|---|
| `PROMPT_CRUCIBLE_COMBINED_RELAY_RESPONSE.md` | → | held | carry; archive after the v39→v40 MR read (~07-22/23) | D291/D295 |
| `PROMPT_CRUCIBLE_CORR_TO_BOOK_ASK.md` | → | carried (07-20, operator) | their answer (additive field / decline); telemetry build follows only on a yes | D302 |
| `PROMPT_CRUCIBLE_SINGLE_NAME_AXIS_RETIREMENT_ASK.md` | → | held (NEW 07-21) | **operator go** — freeze-program read: do assembled books consume single-name trend/MR components? gates the single-name-axis prune (the 2.8% dead-flow); flag answer → stage a prune or hold | D328 |
| `PROMPT_CRUCIBLE_V46_DEPLOYED.md` | → | held (NEW 07-21) | carry; asks `funnel --compare v45 v46` + suppressed-mass census key shape; archive after the funnel read | D320 |
| `PROMPT_CRUCIBLE_CACHE_ERA_STAMP_ASK.md` | → | held (NEW 07-21) | **operator go** — new-initiative contracts ask (cache-era/writer-version stamp on gated exports; the ghost-episode fix Crucible-side half; would make era cuts lane-aware) | D316 |
| `PROMPT_CRUCIBLE_V43_DEPLOYED.md` | → | answered (their same-hour `FORGE_v43_row45_crosscheck_2026-07-21.md`: 0/30 starved, premise reproduced their ledger, ALIVE flags LRCX/GE/WFC/UNG noted-not-invoked; addenda 1+2 carry deploy evidence + our ghost cross-check) | archive after the scheduled `funnel --compare v42 v43` (reads against prereg `44a4e08aef4f`) | D309/D311 |
| `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md` | → | held (since 06-28) | operator relay decision | crucible-handoff |
| `PROMPT_CRUCIBLE_SEARCH_N_TRIALS_INTERACTION.md` | → | answered + CLOSED; **carries a RESOLVED+receipts banner for the next carry** (stamp ARMED on the first v43 batch `03b33475` 02:07:37Z; slot spans 5,154–108,324; expect `dsr_below_bar` at volume immediately; stamp boundary = the v43 boundary) | carry the banner (bundles w/ `PROMPT_CRUCIBLE_V43_DEPLOYED.md`); archive after | D306/D310 |
| `PROMPT_CRUCIBLE_Q46_GO_CONFIRM.md` | → | held (NEW 07-21) | carry (GO received: residual_momentum confirmed healthy + the double-gate refinement for their null-control read); supersedes the scoping relay's open questions | D315 |
| `PROMPT_CRUCIBLE_Q46_READ_INVERSION.md` | → | held (carries the ✔ v45 DEPLOYED banner) | carry (v45 live 05:23:22Z; pin the +2wk in-book read here; emission proof resid 7.5→14.0%/1.87×, hurst-vix 20/adx-vix 0); supersedes the v44 03:43Z pin | D318/D319 |
| `PROMPT_CRUCIBLE_Q46_MULTIGATE_SCOPING.md` | → | held (NEW 07-21) | carry (Q46 scoping reply: slot already built → 1-id add; census-starving premise corrected to 34.5% live; asks their grammar_version re-split + the co-fire design Q); operator greenlight → v44 build | D315 |
| `PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` | → | parked | Path C is parked (operator 06-15); refresh before any resume | D152 |
| `PROMPT_CRUCIBLE_SECTOR_ETF_XSECT_PRECHECK.md` | → | held (since 07-12) | operator relay decision (companion research = D269 DON'T-BUILD) | D269 |
| `PROMPT_CRUCIBLE_STALE_VOLUME_METRICS_EXCLUDE.md` | → | held (since 07-12) | archive after prereg `098ea730` resolves | D295 |
| `PROMPT_CRUCIBLE_VE_PROGRAM_RESPONSE.md` | → | held | archive after their v38→v39 ve read (~07-21) | D289/D290/D295 |
