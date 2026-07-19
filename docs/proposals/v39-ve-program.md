# Proposal: v39 — ve program repairs: exit-schema fix, ref_trailing_return veto sampling, iv_term_slope loosening (+ the ve ghost-label training cut)

Status: **SCOPING — operator-gated; nothing ships off this doc.**
Date: 2026-07-19. Source: `FORGE_ve_program_relay_2026-07-19.md` (their 3-day ve
program close-out). Response relay: `PROMPT_CRUCIBLE_VE_PROGRAM_RESPONSE.md` (held
for carry; §5.1/§5.4/§6 answered with data, no build needed there).
Relates to: [[D169]] (the v22 ladder this repairs), [[D168]], [[D071]] (S5 schema),
[[D257]]/[[D236]] (S5 set-edit precedents), [[D128]] (clean-era label cut precedent).

## Verified facts driving the build

- Every ve config carries `event_passed_exit` (ve `required_always`) with NO
  `event_indicator` param → **always their fallback mode** = a hard cut at
  entry+n_bars. The v22/D169 ladder {3,5,8,13,21} put 60% of every ve batch in their
  sweep's cratered region; ve conversion: v21 5.9% → v22 0.7% → ~0 (our DB,
  archive-verified that nothing else changed in the cell).
- `ref_trailing_return` is in our live registry read (macro family, market-wide) — no
  contracts gap.
- 34,273 ve verdicts / 657 "components" inside [2026-06-10, 2026-07-18) are
  ghost-tainted (~10% of all positive training labels).

## Build items (one v38→v39 bump, if approved)

1. **ve exit schema** (`custom_predicates._S5_HYPOTHESIS_EXITS` + sampler — an S5
   set edit, the D236/D257 precedent, flagged explicitly because S5 is a §3.5 rule
   surface): ve `required_always` becomes `("iv_crush_exit", "time_stop")`;
   `event_passed_exit` is REMOVED from the schema for ve (their "either true-event
   mode or omit" — with a timer present it fires 0/68, decoration); `optional_additions`
   drops `time_stop` (now required). `_time_stop_nbars_range` gains
   `(volatility_event, *) → U[4,7]` (their sweet spot; 13/16/21 crater at cpcv
   0.81/0.42/0.29). The `_EVENT_PASSED_NBARS_LADDER` retires with a tombstone comment.
2. **ref_trailing_return veto sampling in ve cells**: threshold U[-0.03, -0.02],
   window randint[3,10], reference choice{SPY, QQQ} — SAMPLED never pinned (their
   honesty block: variants span cpcv 1.27–1.55; two crossed 1.5 and were not adopted).
   Mechanism: the ve veto slot (the D263/D266 veto machinery generalized to ve, or a
   dedicated ve veto draw — decide at build time against the existing veto plumbing).
3. **iv_term_slope threshold loosening ×1.3** on the ve directional sampled range
   (`indicator_thresholds.py`; +0.21 cpcv on their honest chassis).
4. **ve ghost-label cut** (versionless companion, can ride the same deploy): exclude
   `hypothesis == volatility_event AND decided_at < 2026-07-18` rows from every
   learned trainer (ranker dataset, yield maps, name/class weights, trade-rate
   priors) — the CLEAN_ERA_LABEL_CUT precedent scoped to one hypothesis.

## Explicitly NOT built (their honesty block)

- No genome porting (transfer 0/3 — name-specific; thresholds stay sampled per-name).
- No "stabilization" filters (the 7 calm-tape losses are the edge's price).
- No pinning of the veto params (knife-edged; sample only).
- The ve≥0.20 floor and the D287 experiment protections stay untouched (their #5).

## Ritual

Classification #2 (enumeration-policy bump) PLUS an S5 set edit (D236/D257 precedent
— operator approval explicit). Goldens re-pin licensed (ve exit draws shift; the
environment-matched harness from D286/D288 applies). Full deploy ritual per
`docs/tasks/deploy.md`; relay version string to Crucible; ask
`funnel --compare v38 v39 --hypothesis volatility_event`.
