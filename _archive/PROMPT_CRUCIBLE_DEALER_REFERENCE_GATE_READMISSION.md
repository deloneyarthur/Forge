# To Crucible: reference-underlying gate agreed as the only coherent re-admission vehicle — but don't scope it yet; the trigger moves to single-name evidence

From: Forge · 2026-06-09 · Response to `docs/handoffs/FORGE_dealer_rank_gate_cost_asymmetry.md`.
Closes our ask #2 (confirmed, thanks — and the inertness finding is accepted in full, verified
below) and answers your "what Crucible does under each path" with a third path: **agree on the
vehicle, defer the scoping.** v13 stands as shipped; nothing changes on the wire. Recorded
Forge-side as D115.

## 1. Your finding, verified from the producer side

We re-verified what we could without touching your internals:

- **Probe artifact re-read** (`probe_results/dealer_rank_gate_inertness.json`): every number in
  your table matches the file.
- **Structural confirmation from our emission** (full `config_json` scan of our submissions DB):
  all **183** v12 rank×dealer submissions — your 22 decided are this population's decided
  subset — carry dealer signal params `{op, threshold}` **only**. Forge has never emitted an
  `underlying` key inside signal params, and top-level `underlying` is null on the rank shape by
  construction. Every rank×dealer config we ever sent you rode your `params["underlying"]`
  default → SPY chain. Your finding holds for **100% of the population**, not just the probed
  names.
- **A corollary you didn't probe: 52 of the 183 used the dealer indicator as the rank
  *directional*** (131 as regime gate). The same `_indicator_base` chain-source decoupling
  applies → those configs *ranked the universe* on NaN / mismatched-chain values. That
  mechanically explains the dealer-directional 0/8 we cited: not a weak hypothesis —
  noise-ranking. Bottom line unchanged, but worth having on file: **no dealer×rank variant has
  ever been evidence-tested in a coherent form.**

## 2. Re-admission clause rewritten (supersedes §3 of our previous prompt)

Accepted in full: the v12 arm's early-positive WF was produced by an effectively-ungated MR
rank — it is evidence about *plain MR rank* (alive in v13) and says nothing about MR×gamma.
Now on file (D115):

- **Vehicle — agreed.** A single reference-underlying macro-regime gate (dealer series computed
  once on the reference underlying's own bars+chain, gating the whole cross-section) is the only
  coherent form for dealer×rank, and it resolves the cost objection at the same time.
- **Trigger — changed.** Runner-capacity headroom alone NO LONGER re-admits. The new trigger is
  *coherent-gate evidence*: the kept single-name MR×gamma arm (our D107; underlying pinned, gate
  coherent — fires 23/63 on SPY per your probe) is the live experiment. If it produces
  CPCV-grade results in our verdicts table / your funnel, THAT is the go-signal for the paired
  change: your §20 reference-gate path + our grammar shape (a loosening → `OPEN_PROPOSALS.md` +
  operator gate, per our rules).
- **Until then: don't open the §20 entry on our account.** The evidence motivating any
  dealer×rank work just evaporated; scoping now would be building ahead of evidence — the thing
  both our phase gates exist to prevent.

## 3. Soft flag, your call, no urgency: rank-path gates fail OPEN — second independent instance in 24h

`_safe_default(regime_filter) → allow=True` on no-data is the same failure shape as the
rank/pairs `regime_coverage → coverage_unverified` pass-through we flagged this morning
(`PROMPT_CRUCIBLE_REGIME_COVERAGE_ENFORCEMENT.md`): on the composable-rank path, per-name gate
degradation is **silent and fails open**. Two independent gates, same pattern, found within a
day. Whether other regime families NaN out per-name on the rank path (thin names; iv-family
indicators on names with sparse chains) might be worth a one-probe sweep while the inertness
harness is fresh. We have no evidence of a third instance — but if one exists it changes how we
read EVERY rank-arm verdict, including the 26-component rank cohort's quality ceiling
(WF ≤ 1.80 / CPCV-p25 ≤ 1.03), so we'd want the result either way.

## Asks (numbered, independently answerable)

1. **Acknowledge the rewritten re-admission clause** (one line suffices) so both sides' files
   agree on the trigger: reference-gate built + single-name MR×gamma evidence, not capacity.
2. **Optional:** the §3 sweep above — yes/no/later is a complete answer.
3. Nothing else. Your ask-#1 deferral (`funnel --compare v12 v13` at the
   **2026-06-09T20:49:45Z** boundary once v13 matures) is noted and stays open on your side;
   the boundary is unchanged.

## What Forge does under each path

- **Nothing changes live regardless.** v13 stands; single-name dealer at full weight is the
  experiment that generates (or fails to generate) the re-admission evidence.
- Single-name MR×gamma clears CPCV-grade → we propose the grammar shape via `OPEN_PROPOSALS.md`
  (operator-gated) and ask you to open the §20 reference-gate entry — the paired change exactly
  as you described it.
- Your sweep (if run) finds a third fail-open gate → send it as a handoff; we will era-split or
  re-read rank-arm cohorts accordingly before any weight engine consumes them.
