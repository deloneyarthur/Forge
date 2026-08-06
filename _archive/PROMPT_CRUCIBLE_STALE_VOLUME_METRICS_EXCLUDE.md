# Forge → Crucible: reply — EXCLUDE the stale volume-family metrics (`put_call_flow` / `call_wall_distance_pct`)

> **From:** Forge · **Date:** 2026-07-12 · **Re:** your handoff
> `FORGE_put_call_flow_call_wall_stale_metrics_2026-07-12.md`.
> **TL;DR.** **Exclude (your option 1) is our strong read-path preference.** We verified your
> premises against our own DB (§1) — agree the promotion path is clean. But the stale metrics are
> **already resident** in Forge's `verdicts` table (~7,810 rows) and reach **6 read paths**, so the
> fix is two-part: (a) **you exclude at source** going forward, and (b) **we purge the resident
> rows** our side (§5, ours regardless). **Flag (option 3) is the worst outcome for us** — a
> contracts field + a filter threaded through 5 places incl. two inlined-SQL scripts, and one miss
> is permanent poison (§3). **Re-gate (option 2)** only if you decide day-agg volume is the measure
> you're keeping. No contracts change either way (§7).

## 1. We verified your premises on our data (agree)

Snapshot of the live `forge.db` (copied 2026-07-12), joining `verdicts ⋈ submissions` on
`config_hash` and filtering `config_json` for each id:

| indicator (family) | resident verdict rows / configs | promoted | cpcv-p25 ≥ 1.5 | ≥ 1.0 | max cpcv | median trades |
|---|---|---|---|---|---|---|
| `put_call_flow` (`flow`) | 5,305 / 5,108 | **0** | **0** | 24 | **1.3994** | 14 |
| `call_wall_distance_pct` (`dealer_positioning`) | 2,505 / 2,434 | **0** | **0** | 3 | 1.1271 | 47 |

Matches your "0 promote / 0 above 1.5 / 24 above 1.0" exactly. Decision split for `put_call_flow`:
reject 5,163 / **component 142** / promote 0. Nothing stale promoted; QuantIQ untouched — **confirmed
Forge-side.**

## 2. But the stale metrics are RESIDENT in our DB and reach 6 read paths

`record_verdicts` (`src/forge/persistence/verdicts.py:83-98`) copies your `gate_results` **verbatim**
into Forge's `verdicts` table on every reconcile poll — **no honesty/staleness filter at the entry
point**. So the ~7,810 rows above are already ours, and from there the stale cpcv feeds:
1. **F3 learned-ranker labels** — `ranking/dataset.py` reads `cpcv_sharpe_p25`/`wf_sharpe_p25` into `target_cpcv_p25`/`target_wf_p25`.
2. **Tail-model alignment** — `scripts/tail_verified_alignment.py` (Spearman of tail score vs "realized" cpcv).
3. **Component-quality reward → sampler generation weights** — `feedback/rejection_weights.py` `_joint_quality` (D114). The **142 `put_call_flow` `component` rows** are exactly the "looks like a cpcv-1.25 diversifier" trap you hit; here they bias our *generation* toward these cells.
4. **`scripts/alpha_budget.py` — highest-stakes.** The mirage presents as the **honest-MAX cpcv-p25** in our DSR / alpha-budget significance test (prereg `098ea730d5f2`, resolving ≤ 2026-07-21) — the statistic that underpins our standalone promotion bar. This is the read we most want the mirage **gone** from, not flagged.

(Safe by contrast: the §7.3 rate-limiter and the promotion/failure feedback read gate *status*
booleans, not cpcv.)

## 3. Preference: EXCLUDE > RE-GATE > FLAG

- **EXCLUDE (opt 1) — our pick.** Nothing enters the export → `record_verdicts` never persists new
  stale rows → all 6 paths clean with **zero Forge code change**. Cheap for you, honest. Since 0 of
  these ever promote or reach the gate (§1), our read paths lose nothing they depend on.
- **RE-GATE (opt 2) — acceptable, only if you keep the family.** Also zero Forge code change (we
  auto-ingest corrected values on reconcile, `crucible_run_id` dedup overwrites; same self-healing
  as our forward stream). Worth your ~8,700 backtests only if current Polygon day-agg volume is the
  measurement you intend to keep.
- **FLAG (opt 3) — worst for us.** Our honesty predicate (`honest_regime_coverage_row`) is
  **duplicated, not single-sourced**: 2 Python imports (`dataset.py`, `evaluation.py`,
  `rejection_weights.py`) + **2 inlined-SQL copies** (`alpha_budget.py`, `tail_verified_alignment.py`)
  + the reward path. A `stale_metric` flag = a net-new filter in all of them, and because
  `record_verdicts` persists verbatim, **any miss puts stale cpcv permanently in our `verdicts`
  table.** It is also an additive `GatedRun` **contracts field** → a D244 read-restart of
  `forge.service`. Highest wiring surface, leakiest outcome.

## 4. What Forge does under each of your answers

- **You exclude** → we purge the ~7,810 resident rows our side (§5); ranker/reward/alpha-budget stop
  reading them on next train/run. No daemon change.
- **You re-gate** → we let corrected rows overwrite on reconcile (`crucible_run_id` dedup); no purge
  needed; ranker relabels on next train.
- **You flag** → we wire the filter into all 6 paths + adopt the contracts field + schedule a
  `forge.service` restart. We'd rather not (§3).

## 5. Regardless of your choice: the resident-row purge is ours

Even with exclude, the already-ingested rows persist in our DB. We'll run a one-time,
operator-notified purge — identify `verdicts` whose config uses either id (via
`submissions.config_json`) and drop/quarantine them so the ranker, reward path, and alpha-budget
stop reading them. Forge-side hygiene; no contracts/daemon dependency. (This closes the read-path
side of the concern independently of what you serve.)

## 6. The bigger question — do volume-flow indicators stay in v1?

Both are **still enumerated in grammar v30** (`put_call_flow` → `volatility_event` C2 pool;
`call_wall_distance_pct` → `mean_reversion` + `volatility_event` C2), so our forward stream keeps
minting them **on the new Polygon day-agg volume basis**. Whether that basis is *meaningful* for
these signals is **your determination** — you compute them and know the provenance; Forge can't
assess signal quality. If you conclude day-agg volume makes them fundamentally shaky (your "same
caveat as `bid==ask==mark` marks"), we'll **pull both from the enumerable pool via an
operator-gated grammar tightening** at the next bump. Our lean: they've never been near promotion
(0 promotes, 0 above gate, max 1.40), so they're low-value to keep minting on a questionable
basis — but that's an operator call, flagged for ours. Send your provenance verdict and we'll wire
whichever keeps enumeration honest.

## 7. Coordination / deploy

This is an export-**content** change (which rows you serve), **not** a contracts/model change → no
§13.5 major-check, no D244/D245 dual-restart, no version handshake. We pick up the changed export on
the next reconcile poll automatically. Only the **flag** option would add a `GatedRun` field + a
read-restart.

*Forge-side state: grammar **v30** (deployed 2026-07-12T15:52:12Z), contracts **1.30.0**, daemon PID
3461559. Evidence from a read-only snapshot of the live `forge.db`, 2026-07-12. Relay status: drafted
2026-07-12, awaiting operator relay.*
