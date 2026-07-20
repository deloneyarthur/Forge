# Sunday review — 2026-06-14 (snapshot 16:07Z, `/tmp/forge_sunday_prep.db`)

> **STATUS (2026-06-24):** HISTORICAL — point-in-time review snapshot (16:07Z, 2026-06-14). All numbers/cohorts are as-of that date; the resulting attack-list items were dispositioned across the D146–D200 arc (throughput cut → §7.3 backpressure D196/D200; ranging supply → v20–v22; bear closed; quality lane flipped D193). For live state see `STATUS.md` + `IMPLEMENTATION_DECISIONS.md`. Snapshot below.

The operator-requested checkpoint (3+ days of honest-era verdicts past the 06-11 baseline).
Cohort cuts: honest era = `decided_at ≥ 2026-06-10 17:17:13Z`; clean = v17+v18+v19; join
`verdicts → submissions` on `config_hash`. Baseline = 2026-06-11T21:00:20Z (bottom).

## TL;DR — the supply finding reframes the whole attack list

**The binding constraint to promotion is bear/ranging worst-quartile robustness — and that is a
GRAMMAR / SUPPLY gap, not a ranking gap.** T3a measured the assembled book's worst CPCV quartile
as **BEAR 2.39× / RANGING 1.33×** (regime_lift). The live D144 `regime_supply:` line shows the
reservable pool ceiling is **0% bear / ~1.8% ranging** every iteration, and the existing D103/D136
floors *already over-select* what little exists (submitted ranging 7.5% > pool 1.8%). **No
bear-paying config is even enumerable** — options-only, long-premium, no shorting/spreads (hard
rule 7). So a perfect T1 ranker + T2 floor cannot assemble a complement the grammar can't supply.

This subsumes three agenda levers: the **dead families** (em) and **rv** *are* the missing
bear/ranging complement, and the **T2 enforcement floor** is now shown near-redundant with the
existing diversifier floors. Meanwhile Forge floods Crucible with a **124k-deep pending queue** of
mostly-trend configs that cannot help (more correlated trend → worse portfolio CPCV-p25).

**→ The two top, complementary, operator-gated levers: (A) bear/ranging grammar expressivity
(the real #1); (B) a throughput cut (stop the trend flood). T2 enforcement drops down the list.**

## Funnel (honest-era, 16:07Z)

| cohort | decided | component | rate |
|---|---|---|---|
| **overall honest-era** | 20,706 | 1,042 | **5.03%** |
| v18 | 8,932 | 498 | 5.58% |
| v19 | 7,315 | 365 | 4.99% |
| v17 | 4,143 | 124 | 2.99% |

Per hypothesis: **trend 9.37%** (692/7,389) · **ve 4.97%** (260/5,236) · **mr 2.09%** (90/4,309)
· **rv 0%** (0/3,654) · **em 0%** (0/117) · ra 0% (0/1, retired). Promotions **0** all-time.

**Rate rose 3.28% → 5.03% since cp#2 — but that's COMPOSITION, not quality.** The ~74%-trend
submission cohort now dominates decisions; trend gate-passes at 9.37%, so the blend rises toward
it. More correlated trend is *worse* for the portfolio worst-quartile — the rising rate argues FOR
the diversity/throughput levers, not against them.

## The crux — worst-quartile is a grammar/supply gap (levers #4 + the new #1)

- **T3a (measured):** worst CPCV quartile = BEAR 2.39× / RANGING 1.33× regime_lift (not the
  base-rate-artifact low_vol). The tail is a directional-drawdown (bear) problem.
- **D144 `regime_supply:` (live since 07:19:16Z):** first/representative line —
  `selected 15/200 (7.5%) pool 20/1105 (1.8%); bear 0/0; cells [trending=137/980 ranging=15/20 bear=0/0 other=48/105]`.
  The reservable ceiling is **88.7% trend / 1.8% ranging / 0% bear**; D103/D136 already pull ~15 of
  the 20 available ranging configs in (selected > pool). T2-enforcement headroom: ~5 configs
  ranging, **nil bear**.
- **T1 tail shadow (corroborating, not the crux):** model `5174039c` strongly positive and
  strengthening (06-14 readout: spearman ≈ +0.45, top-K realized cpcv_p25 tail ≈ 0.73 vs incumbent
  ≈ 0.47). The ranker *can* find the tail-robust configs — there just aren't bear/ranging ones to
  find. **The bottleneck is upstream of ranking.**
- **Conclusion:** the producer-side answer to the binding constraint is **growing bear/ranging
  grammar expressivity** — a config class that pays in directional drawdowns / chop. This is
  operator-gated (grammar) and is the real lever #1. Full design context:
  `docs/proposals/tail-aware-ranker.md` §4 T2 / §7, [[promotion-gate-tiers-and-constraint]].

## Lever verdicts

1. **Throughput cut — ESCALATED.** Pending queue **124,515** (submitted 156,989 / decided 33,746),
   ~6× the 06-11 baseline (19,882) and growing ~+11k/day (Forge ~16k/day vs Crucible ~4–5k/day).
   ~74% of the flood is trend — redundant for the portfolio. §7.3 brakes on quality, not queue
   depth. **Action candidate:** match submission volume to Crucible capacity (top-N batches or
   slower cadence; a queue-depth term in §7.3 as companion to the D137 stall guard). Operator-gated.
2. **Dead families — DIAGNOSED, no defect.** ra + th are intentionally disabled
   (`DISABLED_HYPOTHESES`, D066/D098 — 0 emitted). em IS enumerated (D136 floor) but fails on `sue`
   sparsity → genuinely weak. Reduces to: em weak (decide alongside rv); ra/th retired-by-design.
3. **rv — 0/3,654, decision ripe.** ~7% of the stream / ~18% of decided, **structurally** 0%
   (Q40: options-only can't express the market-neutral RV edge; fails 5–6 gates deeply). Not a
   defect to fix — a capacity question: keep emitting a known-0% family, or **prefilter
   auto-tighten** (allowed without approval) to reclaim its slot for the worst-quartile goal.
4. **Promotion endgame — track BUILT & LIVE (shadow).** T1/T2 (D140–D144) retarget ranking toward
   worst-quartile cpcv_p25 + measure complement supply. Now **blocked on grammar supply, not
   ranking** (see crux). Live wiring + enforcement gated on the §8.6 margin (accruing).
5. **ve×swing_mid — CLOSED.** Faded to 5.56% (21/378) from the 12.2% (n=41 noise) baseline; no
   special follow-through warranted.
6. **Stall guard — DONE.** D137 live since the v19 restart; upstream wedges bounded to ~3h.

## Operator decision menu (the output)

The review converges on **one prioritized, complementary set** — no code/grammar/config changed here:

- **(A) Bear/ranging grammar expressivity work-up [top lever, operator-gated].** Scope a config
  class that pays in directional drawdowns (bear 2.39×) / chop (ranging 1.33×) within hard-rule-7
  constraints (long-premium, options-only). This is the only lever that can lift the worst-quartile
  pool — everything downstream (T1/T2) is ready and waiting on supply.
- **(B) Throughput cut [high leverage, operator-gated].** Stop the 124k trend flood; match Crucible
  capacity. Complements (A): cut the redundant majority, grow the scarce complement.
- **(C) rv prefilter de-emphasis [reclaims ~7% capacity, auto-tighten allowed].** De-weight a
  structurally-0% family; pairs with (B).
- **Down-prioritized:** the T2 enforcement floor — D144 live numbers show it has ~nil headroom over
  D103/D136; re-justify against (A) before building.

## Still accruing / gated

- **§8.6 T1-wiring margin** — `tail_score` accruing since 07:19:16Z; set the margin once ≥3
  checkpoints × ≥150 fresh verified-coverage tail-scored verdicts (days). Then T1 live wiring is its
  own operator go.
- **F3 logistic criterion = 3/3 PASS** (`streak.jsonl`) — still needs operator go + a ritual restart
  to wire (does not auto-wire).
- **T3b `portfolio_contribution`** — deferred until T1 has shadowed (the per-component marginal
  worst-quartile signal; rides the `PromotedPortfolio` contract).

## vs baseline (2026-06-11T21:00:20Z)

| metric | baseline | now (16:07Z) |
|---|---|---|
| honest-era component rate | 3.76% | 5.03% (composition-driven) |
| pending queue | 19,882 | **124,515** |
| trend honest-era rate | 8.9% | 9.37% |
| rv | 0/818 | 0/3,654 (structural, Q40) |
| ve×swing_mid | 5/41 (12.2%) | 21/378 (5.56%, closed) |
| promotions | 0 | 0 |
| worst-quartile response | none | T1/T2 built & live (shadow); blocked on supply |
