# Forge — Status

## 2026-09-15 (later) — **Batch 5 G3 DONE (D420): daemon-era feedback GONE — `rejection_weights` (1,171 LOC) + the §8.5 proposal machinery, 8 modules / 12 test files (−3,003 src, −4,772 tests); `feedback/` = consumer · eras · preregistration · trade_rate_priors · types. Hard rule #4 re-cut ("no code writes grammar.yaml at runtime", AST invariant); `OPEN_PROPOSALS.md` static. Suite 1,618 green in 94 s; live dry-run identical.** (D420)

- Next: G4 (rate limiter, write-only prefilter logger + Q44 close, three unused predicate types).

## 2026-09-15 (later) — **Batch 5 G2 DONE (D419): daemon-era ranking GONE — 14 modules + `yield_audit` + `ranker.yaml` (32 files / 7,866 LOC); `ranking/` = dataset · features · model · shadow · signal_key · types. Hard rules #6/#9 keep named tests (`test_batch_reproducibility` re-targeted to two campaign runs in disjoint workspaces). Suite 1,803 green in 99 s; live dry-run identical.** (D419)

- Next: G3 (feedback, daemon era — `rejection_weights` 1,171 LOC + the proposal machinery; hard rule #4 reworded).

## 2026-09-15 (later) — **Batch 5 G1 DONE (D418): the daemon loop + its command family are GONE — `cli/main.py` 2,952 → 254 lines, 29 files / 7,489 LOC deleted; `forge --help` = version · check · enumerate · prefilter · campaign · prereg. Suite 2,052 green in 116 s (was 220 s). Live dry-run reproduces the plan.** (D418)

- REL-4 SIGTERM test re-targeted to the campaign oneshot (xfail until G6); the D352 battery-inputs invariant now reads `campaign/run.py`. Next: G2 (ranking, daemon era).

## 2026-09-15 — **Batch 5 G0 DONE (D417): the weekly run trains its own two models (verdict + cpcv robustness, retention 4/family) and judges preregistrations at boot (DUE/UNWATCHABLE = FAIL); ranker-eval + prereg-watch timers, 7 scripts, 6 unit files GONE (−3,279 LOC). Two Sunday-breaking defects found by live dry-runs and fixed (CUTOVER.json crashed the record loader; failed records wiped the baselines). Timers = campaign (Sun 03:00Z) + backup (Sun 04:30Z). Peak RSS with training 25–27 GB → caps 32/48 GB.** (D417)

- Suite 2,219 green. Next: G1 (the daemon loop + its CLI leave `cli/main.py`).

## 2026-09-14 (later) — **CUTOVER RAN 2026-09-14T23:52:05Z (operator ran the unit; Crucible waived the 24 h notice). `forge.service` DISABLED — the daemon era is over. `forge campaign` LIVE: first live run reconciled 624 verdicts from the forge stream, 20,000 enumerated, no trigger, 0 submitted. Timers now: campaign (Sun 03:00 UTC), backup, ranker-eval, prereg-watch. Batches 0–4 DONE; Batch 5 (remove the daemon era, plan §13) starts.** (D416)

- Expect `truncated: true` on the forge stream until ~09-28T21:20Z; a truncated file after that is ours to relay. 16 GB peak on the live run (cap 24 GB) — Batch 6 target.

## 2026-09-14 (later) — **Crucible recorded the instant; one gap they found is FIXED: the absent-forge-stream fallback no longer runs the aged-out flush (an absent window is as blind as a truncated one). The `ranked` boundary is split by campaign identity — `submitted_hashes` in live run records is now a contract field.** (D415)

- Nothing blocks the 09-15T07:00Z cutover. Watch item: one unreproduced test failure on the first scoped run, three clean re-runs after.
- **Tonight's sequence (operator-confirmed via the Crucible session, 09-14):** 14:20 PT Crucible's maintenance unit STOPS `forge.service` (left enabled, NO restart — our ask: no casual restart of the refactored tree 3 h before its retirement) and runs its measure window (≤ 6 h, latest end ~20:50 PT); 22:45/22:49/22:53 PT their cutover-guard writes `CRUCIBLE_maintenance_window_NOT_healthy*` only if all three checks fail; 00:00 PT our cutover script refuses on that file (`e37cf7d`) or proceeds (disable daemon, flip to `live`, first live run). Hourly healthcheck CRITs from 15:00 PT are EXPECTED. The daemon's last submission is ~21:20Z, widening the gap around the relayed 07:00Z `ranked` boundary.

## 2026-09-14 (later) — **Batch 5 PREP done: nine helpers the campaign borrowed from doomed modules moved to permanent homes (pure refactor `b4803cc`, old names still bound), tripwire invariant added, removal checklist written (plan §13, groups G0–G7). Suite 2,252 green; live dry-run plan identical. Daemon untouched; cutover armed for 09-15T07:00Z.** (D414)

- Batches remaining after the cutover: 5 (remove the daemon era), 6 (consolidate), 7 (regrowth rules).

## 2026-09-14 (later) — **CUTOVER SCHEDULED: 2026-09-15T07:00:00Z (operator: "as soon as possible"; Crucible's 24 h notice honoured). `scripts/cutover_campaign.sh` + `forge-cutover.{service,timer}` written and syntax-checked; NOT armed, NOT committed, relay NOT delivered — the harness refused those as a production deploy, so they are the operator's two commands (D413).** (D413)

- At the instant: daemon stopped + DISABLED, healthcheck timer off, campaign unit flipped to `live`, first live run immediately, then Sundays. ranker-eval / prereg-watch / backup keep running until Batch 5.
- Expect `truncated: true` on the forge stream until ~09-29 (the daemon's 14-day tail); not an anomaly before then.

## 2026-09-14 (later) — **Crucible shipped the forge-scoped 14-day gated stream (contracts 1.48.0, live, verified 10k rows / truncated until cutover); adopted pin-only, campaign reconcile wired to it (truncated window → no aged-out flush); Sunday 03:00 UTC confirmed; `promoted_strategies` publisher stopped. BOTH cutover blockers on their side are CLEARED — Batch 4 waits only on the operator's cutover date (relayed ≥ 24 h ahead).** (D412)

- No restart taken or owed (the daemon never reads the new stream). Timer keeps running dry-run Sundays until the unit is flipped to `live`.

## 2026-09-14 (later) — **The dry-run weeks are automated: `forge-campaign.timer` installed + enabled (Sunday 03:00 UTC), unit in `dry-run` mode (snapshot DB, nothing submitted); smoke start through the unit = success, 45 s, 13.8 GB peak → `MemoryHigh=16G`/`MemoryMax=24G` on the unit. Cutover = flip the unit's `FORGE_CAMPAIGN_MODE` to `live` once the daemon is stopped and Crucible's stream is live; the wrapper refuses `live` while the daemon runs.** (D411)

- Monday check: `journalctl --user -u forge-campaign.service -n 30`; a FAILED unit is the page. Five Forge timers now. Daemon unchanged.
- Plan §8.11 CLOSED (operator, 2026-09-14): the 6.3 GB `forge.db.pre_arm_cleanup_20260731_230544` copy (D342 pre-repair) DELETED; three validated nightly backups (09-11/12/13) supersede it. No operator-gated data item remains.

## 2026-09-14 (later) — **Batch 3 BUILT: `forge campaign` lives beside the daemon (8 commits, suite 2,228 green). Two live dry-runs clean: boot 8/8, designated `7f2a697e`, baselines recorded, then "no trigger" on 20,000 enumerated in 44 s — the sweep already covers every reachable cell, so the weekly run stays quiet until a trigger fires. Nothing submitted, nothing installed, daemon unchanged.** (D410)

- Fix landed mid-build: the campaign enumerates UNSTRATIFIED (`min_hypothesis_fraction=0.0`, `2211d47`) — the daemon's D037 floor capped the first dry-run at 800/20,000.
- Dry-run weeks start now: `forge campaign --dry-run --forge-db "$(scripts/live_db_snapshot.sh)"` weekly; records in `~/forge_data/campaigns/`. Cutover (Batch 4) waits on Crucible's 14-day forge-scoped stream + the relayed instant (D409). Record schema relayed to Crucible.

## 2026-09-14 — **Crucible answered the campaign-mode relay same day: cutover is BLOCKED on a forge-scoped 14-day gated stream (their option 2, operator-confirmed — the existing export reaches ~24 h, measured); T1 = designation flips only (contributions are frozen at assembly); weekday Sunday 03:00 UTC; `promoted_strategies` retirement ACKed (our read has been `[]` since 07-06); champion re-based to `7f2a697ec6c1b119` @ 08-06 (`designation_history` had never been published).** (D409)

- Reply delivered (freeze `5ab347a`). Nothing on the wire changes; daemon unchanged. Waiting on: their stream (loader-first), weekday confirmation. Owed by us: run-record schema before the first live run; cutover instant ≥ 24 h ahead.
- Next: Batch 3 — build `forge campaign` beside the daemon (plan §12.6).

## 2026-09-13 (later) — **Batch 2 DONE: coverage first. Three known bugs pinned as strict xfails (SIGTERM tear REL-4, unlogged export-outage swallows REL-1/REL-2), model-reload-per-iteration and the snapshot script pinned, 3 perf tests marked `slow`, v44 conditioner tests + the Q51 flake deleted (Q51 CLOSED). Suite 2,148 passed / 1 skipped / 3 xfailed in 214 s.** (D408)

- `scripts/deploy_preflight.sh` → **GO** after the commit (tree clean, suite 2,148 passed / 1 skipped / 3 xfailed in 219 s). Batches 0–2 complete; nothing restarted. Next: Batch 3 = build `forge campaign` beside the daemon (plan §12.6), gated on Crucible's six answers (relay `480fe72`).
- Deferred with reasons in D408: `deploy_preflight.sh --check-only` (Batch 5), row-builder fixture (Batch 6).

## 2026-09-13 (later) — **Batch 1 DONE: records rotated (STATUS 110→9 KB, ledger 472→202 KB, OQ 51→36 KB), 12 terminal records + fable-audit archived, 150 relay files removed, 40 stale doc facts fixed, forge.service 249→49 lines (directives byte-identical), prereg-watch units symlinked, runtime cruft archived. Zero production change.** (D407)

- Left for the operator (§8.11): the 6.3 GB `forge.db.pre_arm_cleanup_20260731_230544` copy. Flagged for Batch 6: DESIGN §14 "25 rules" history row.
- Crucible relay DELIVERED (`freeze/relays/FORGE_final_state_is_weekly_CAMPAIGN_mode…2026-09-13.md`, commit `480fe72`): six asks; daemon unchanged until cutover.

## 2026-09-13 — **Batch 0 of the 2026-09 simplification plan: contracts pin 1.47.0 adopted (pin-only), D401's stale-model claim RETRACTED, final state decided = Route C automated `forge campaign`.** (D406)

- Pin `1.44.0` → `1.47.0` + `uv.lock` committed; `forge check` OK; pin test green; tree deployable again. **No restart** — both directions already ran 1.47.0 (Crucible 09-06T07:32:42Z, forge.service 09-12 boot).
- D401 retracted: models reload EVERY iteration (`main.py:1968/2377`); 4 model ids rolled 09-13 with NRestarts=0.
- Plan of record: `docs/proposals/repo-simplification-2026-09.md` (§12 = final state). Batches 1–2 executing this session; Crucible relay filed to `freeze/relays/`.

## 2026-09-06 (latest) — **Crucible basis change, relayed BEFORE landing per D404's rule: CBOE panel open interest folds onto canonical chain rows at the runner restart. LANDED 2026-09-06T07:32:41Z (read from systemd here). Their AAPL/MU numbers replicate EXACTLY on our own join. Three chain-basis dates recorded: 07-17 / 08-12 / 09-06T07:32:41Z. Nothing to act on.** (D405)

- **VERIFIED ON DISK:** `oi_fold` tree 6,796 partitions (exact), 11,675,278 rows, asof 07-17 → **09-04** (they wrote 09-05), 39 MB on disk (they wrote 77 MB); backfill mtimes 07:16:35–50Z. Own join of `chain_snapshots` ⟕ `oi_fold` on `occ_symbol` + their fill floor: **AAPL 09-02 78 of 86 in-band pass, MU 169 of 340 — exact.** Volume alias 07-17→08-11 confirmed (`open_interest == volume` on 100% of rows, 07-20 and 08-05).
- **LANDING INSTANT: `crucible-runner@1` Stopped/Started 07:32:41Z**, new pid bound contracts 1.47.0 at 07:32:42Z. Stage two runs inside the same shard (`source: fullhist_refit` in its journal) and the refit-watcher only queues — **one instant for both lanes, no D245-class split.** Their one-line timestamp relay had not arrived; ours is offered for confirmation.
- **OUR EXPOSED COHORTS (snapshot 05:40Z):** volume-alias era 250,092 stage one / 77,329 stage two / 50,223 untagged; NULL-OI era 320,790 / 125,158 / 25. Affected span ≤36 sessions (~2.9% of a 5-yr window) — invisible on the ledger now; a trade-count RISE at the 09-06 boundary is basis, not supply. **D404's monthly watch now brackets three dates.**
- **NOTHING TO ACT ON:** no prefilter/ranker/grammar input reads OI, spreads or fills. The F3/tail retrain pools eras by construction — recorded drift, not corrected. **Third chain-basis change since 07-17 recoverable only by `decided_at` vs a relayed instant** — D386's Layer-2 stamp still open; restated in the reply as a reminder. Eras added to `docs/tasks/investigate-live.md`.
- **DISPOSITION:** ack relay sent; no code, no grammar, no restart. v55 frozen, zero open preregs.

## 2026-09-06 (later) — **Crucible answers D403: (b), tighter. The September tier-3 snapshot was WITHDRAWN, never re-ranked — `e1ad` after 09-04 is August's basis by PROVENANCE. Cause VERIFIED on the canonical store: `open_interest` NULL on every chain row since 08-12, so no refresh can admit a name until their floor reads OI elsewhere. NO calendar boundary exists any more; the basis moves only when they relay first. Corr-export window named: 60 days.** (D404)

- **§1 VERIFIED:** `asof_date=2026-09-01/` holds only the `.EMPTY-refused-2026-09-03.bak`; the 08-03 tier-3 parquet is untouched; fix `2b04ff3` (refuse-not-publish + health check + tests) exists; the 09-04/09-05 heartbeats republish the held 74-name list. **D403's open question is CLOSED: same basis object, not just same content.** The 17,013 `d5da` submissions came from a snapshot that never was a basis.
- **§2 VERIFIED on `chain_snapshots`:** `open_interest` non-null 1.3% on 08-11 (596 of 47,332 rows), **0.0% on 08-12, 08-13, 09-02** (31/99/98 files). Their floor `open_interest >= 100` on canonical partitions has been unsatisfiable every session since 08-12 — the `ibkr_tick101` real-or-NULL change they asked QuantIQ for. Their own 09-03 record blamed the session denominator; wrong mechanism. The 10-03 timer will REFUSE unless the floor's input changes first (§20 decision, theirs, proposed not shipped).
- **RULE SUPERSEDED:** the tier-3 basis moves only by a guarded refresh admitting ≥1 name or a relayed manual re-run, **relayed with asof + timestamp BEFORE landing**. D391's "on or after the 3rd" is retired even as a planning expectation. The `enumeration_inputs_hash` cut is unchanged.
- **§3 MEASUREMENT-BASIS FACT, dated 08-12:** near-ATM IBKR contracts unselectable (OI None), every post-08-12 entry sourced from a CBOE supplement row with real bid/ask → spread gate binds (`spread_too_wide` 4–8% → 32–44%/week; traded 91% → 55–63%). ~3 weeks of an 8.7-year window today, growing per session. **Not visible on our ledger yet** (weekly median `min_oos_trade_count` 521→518, cpcv_p25 ~0.40–0.48, weeks of 08-03→08-31). Both freeze reads predate meaningful exposure. **STANDING WATCH:** re-check monthly; a downtrend from here is this before it is supply.
- **§4 WINDOW NAMED: 60 days** (their cost 776k runs / ~260 MB; ours measured 376 MB RSS / 0.7 s on the 88 MB file → ~1.1 GB one-shot). Smallest offered size that keeps a within-basis leg-2 read available for a basis's whole life; ships in their next 07:00 PDT file, nothing to restart here. A basis older than 60 d = register inside the window and read before it ages out.
- **§5** `tier_3_asof` additive field: operator-gated theirs; adopt via the both-directions restart when it ships. **DISPOSITION:** reply relay sent; no code, no grammar, no restart. v55 frozen, zero open preregs.

## 2026-09-06 — **Crucible's `corr_to_book` notice processed: pin INTACT (`ae47a4749c9d` on both files, our function), NO registered read fell in the 08-31 → 09-06 frozen window, champion label NOT adopted. Leg 2's newest-window gap closed. And their 09-03 re-rank published an EMPTY tier 3 for 13.5h — we drew 17,013 submissions from 24 names.** (D403)

- **THEIR THREE CHANGES, all verified here:** export frozen 08-31 07:02Z → 09-06 05:25Z (files daily through `2026-08-30T140305Z`, then `2026-09-06T052533Z`); new label `7f2a697ec6c1b119` forward-only from 09-06 05:24:15Z (fifth `books` entry, fp `09cfe2ad7e55`; **zero rows carry it yet**); export now snapshot-cut, trailing decisions 7–31h (`data_basis` block present). Additive shape is inert to `_load_corr` (204,915 hashes, fp OK).
- **CHECK 1 = NONE.** Registry: 31/31 resolved, newest 08-14T06:14Z; nothing timestamped in the window. Watcher: "no open preregistrations" daily 08-31 → 09-05. Nothing to mark.
- **CHECK 2 QUANTIFIED — and their "the guard covers it" is true for the wrong reason.** Honest arm n=76,914 / 64 windows: population join **26.4%** under the frozen file, **31.2%** under the new one, 38.1% → 41.3% within `e1ad` — UNAVAILABLE either way. Cause is not today's lag: **the export is a 14-day rolling window** (cut 08-23) and the honest arm is 45 days old, so 43 of 64 windows are NaN. **Leg 2 is readable only on a basis younger than ~14 days** (D389's 84.2% was that case). Newly stated, not new.
- **THE CASE THE POPULATION FLOOR DOES NOT COVER, closed:** window 64 is 30.3% joined and was read as a full window; a 0%-joined newest window went NaN, got dropped, and the PRIOR window was silently judged as newest. `_leg2` now refuses when the newest window is <50% joined — TDD, 4 new tests (`test_freeze_newest_window_join.py`), 65 script tests green, ruff clean; criterion doc updated. Instrument tightening only.
- **THE FINDING THE RELAY OMITS:** `crucible-universe-publisher` 09-03 13:01Z `tier3.floor_excluded n=160` / **`refresh_written n=0`** → `tier_3: []` on disk (406 B); off-cycle republish 09-04 02:30Z restored August's 74 names (content fp back to `e1ad`). Our daemon (fresh after the 09-03 boot) drew basis **`d5da4c3c1469e330` 09-03 18:35Z → 09-04 23:38Z, 17,013 submissions**, no tier-3 single-name for ~29h; pickup of the fix lagged ~21h (D387 class). Basis guard isolates it (windows 62–63 `d5da,e1ad`). **Not relayed by them; asked in ours:** true re-rank output or a rollback? Decides whether post-09-04 `e1ad` is the same basis as pre-09-03.
- **DISPOSITION:** reply relay sent; no grammar change, no restart, no bump. Grammar frozen at v55, zero open preregs. **Next leg-2 registration: only on a basis <14 days old, read before it ages out — or ask Crucible to widen `window_days`.** Tree note: `uv.lock` was already modified when this session began (operator's); left uncommitted.

> Older blocks: `_archive/STATUS_2026-08.md` (Aug), `_archive/STATUS_2026-07.md` (Jul), earlier slices alongside.
