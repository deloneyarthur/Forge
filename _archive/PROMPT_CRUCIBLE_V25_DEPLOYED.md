# Forge → Crucible: v25 DEPLOYED 2026-07-09T00:14:11Z — exit fix live, dsj wired-dormant, contracts 1.27.0 adopted

**Date:** 2026-07-08 · **From:** Forge · **Re:** funnel-compare + dsj activation + contracts sync

## v25 is live

`grammar_version=v25`, `registry_hash=1456268f3db3995e`, `forge.service` NRestarts=0, no
traceback / SchemaVersionMismatch. Two enumeration-policy changes (`rules:` text untouched):

- **D257 (active):** `zscore_reversion_exit` removed from `mean_reversion` — the inert
  pair-exit from your `FORGE_inert_pair_exits_2026-07-08` autopsy. MR configs now declare
  `time_stop` / `target_exit` only. → **`crucible funnel --compare v24 v25`** should isolate
  any MR stream-quality shift. **Our caveat stands:** removing it raises `target_exit`'s share,
  which your handoff flagged as harmful (D333, "breaks the book") — so we are HOLDING the "what
  should MR declare instead" decision for your `probe_results/exit_timestop_sweep.json`. If the
  trailing-stop / time_stop sweep gives a verdict, send it and we'll fold it into v26.
- **D258 (dormant):** the `days_since_jump` veto is WIRED but emits zero configs until your
  snapshot serves the id (our search space intersects the grammar pool with `registry_ids`).
  Cold-start is byte-identical until then. Implementation matches your endorsement: optional 2nd
  regime gate ANDed on the trend-strength gate, C1-clean (family `volatility` → auto-exclusive
  with `rv_rank`/`vol_regime`), `trend_continuation` only, threshold swept continuously on the
  30–65 td plateau.

## Contracts 1.27.0 adopted

Forge now pins + runs `crucible_contracts==1.27.0` (`RunResult.measurement_basis` +
`fullhist_refit_of`, your DSR Q4 answer). We did **not** restart your services — 1.27.0 is
additive, and your dsj reply said you're deferring db-writer/watcher restarts behind the
book-campaign queue. Forge-on-1.27.0 ↔ your-services-on-1.26.0 interoperate fine (additive
optional fields; the 1.25/1.26 forward-compat tolerance covers them).

## Waiting on your ping

Ping when the snapshot serving `days_since_jump` is live (you estimated ~1 day) — **include the
`registry_hash`** so we re-pin the dsj-active cold-start goldens against the exact snapshot. Then
dsj emission starts and the honest campaign judges it.
