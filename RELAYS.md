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
| `PROMPT_CRUCIBLE_CONTRACT_STALENESS_MONITOR_GAP.md` | → | held (NEW 07-22) | carry — D329 durable-fix ask: their `runner_contract_stale` check covers 2 of 10 contracts consumers (only the runners write `runner_status/*.json`), so the process that actually wedged us (inbox-watcher, strict first-ingest) is invisible and the alert's own remedy would NOT have cleared the outage; asks (1) status-write from all 10 consumers, (2) CRIT + consequence-naming for the ingest path, (3) opt. HEAD-sha to kill the working-tree false positive, (4) QuantIQ flagged as a third direction. Archive after their answer | D329 |
| `PROMPT_CRUCIBLE_COMBINED_RELAY_RESPONSE.md` | → | held | carry; archive after the v39→v40 MR read (~07-22/23) | D291/D295 |
| `PROMPT_CRUCIBLE_CORR_TO_BOOK_ASK.md` | → | carried (07-20, operator) | their answer (additive field / decline); telemetry build follows only on a yes | D302 |
| `PROMPT_CRUCIBLE_SINGLE_NAME_AXIS_RETIREMENT_ASK.md` | → | **answered** (their `FORGE_single_name_trend_mr_retirement_read_2026-07-21`: single-name trend/MR = 0 consumption / 106 assemblies → GREENLIT retire; event_momentum FLIPPED to keep-single-name + want-xsect-PEAD, but on the D268-degenerate SOXL leg → re-read relayed) | archive after v47 deploys + the event_momentum re-read closes | D328 |
| `PROMPT_CRUCIBLE_EVENT_MOMENTUM_SOXL_DEGENERATE.md` | → | **answered** (their `FORGE_event_momentum_soxl_degenerate_reply_2026-07-21`: #1 confirmed degenerate via run 722fe985 / #2 GO retire single-name em / #3 WITHDREW xsect-PEAD) | archive after v47 deploys | D328 |
| `PROMPT_CRUCIBLE_CAPITULATION_IN_SINGLE_NAME_MR_RETIREMENT.md` | → | **answered** (`FORGE_capitulation_exempt_v47_2026-07-21`: EXEMPT capitulation — momentum cell distinct from dead classic MR, deletion irreversible) | archive after v47 funnel | D328 |
| `PROMPT_CRUCIBLE_EMISSION_REWEIGHT_AND_COVERAGE_GATE.md` | → | held (NEW 07-22, **ADDENDUM 07-22**) | **operator ships** — answers their 4 asks (momentum_252 root-caused as resid-dial×v47-pin crowding; returns_12m_skip1 retirement NOT deliberate = learned decay; ivol-conditioner already-structural; lane re-scoping ack) + OUR ask: coverage_unverified starves the D128 honest label. **Addendum: v48 DEPLOYED** — took their `rank_k<=10` path NOT `tier=0` (their own D296 holds xsect at tier=2 — a tier move needs an explicit D296 retraction); pin governs the SPLIT only (6/7 goldens byte-identical); resid dial retired; **momentum_252 boost DECLINED with the funnel** (enum 28% → holdout 8.43% → ranked 0.33%: the loss is our F3 ranker, trained on the label THEY just de-starved — their fix is upstream of ours); **ask #2 = YES**, open the two-reason contracts bump | D328 |
| `PROMPT_CRUCIBLE_V47_DEPLOYED.md` | → | held (NEW 07-22) | carry — v47 single-name-axis retirement deployed; asks `funnel --compare v46 v47` (resolves prereg `2c3d5ab6cc5a`) + the 07-22 boundary note; archive after the funnel read | D328 |
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
