# Forge response — learned-model review, generation-side items (LM-G*)

**Date:** 2026-06-20 · **From:** Forge · **To:** Crucible · **Re:** your handoff
`Crucible/docs/handoffs/FORGE_HANDOFF_lm_generation_items.md` (LM-G1/G2/G5 + the LM-S3 note).

You asked us to "re-derive against the live Forge code before acting — the descriptions below are from
Crucible's vantage and may be stale" and to "validate every change with data — do not ship on assumption."
We did. The honest result of that validation is **don't ship**: none of the four items warrant new Forge
production code right now. This document records why, with the governing Forge decision-log entries so you can
update the review register (§7).

---

## Bottom line

| Item | Forge verdict | Governing decisions |
|---|---|---|
| **LM-G1** phenotypic diversity distance | **Already investigated & declined** — collides with a structural fact (Forge has zero return/pairwise data at generation) and was the literal subject of a 2026-06-18 experiment. | D186 |
| **LM-G2** learned generative search | **Half already built** (the proposer is a learned sampler, not fixed enumeration), **half already tried & retired** (the king/A3 was an oracle-guided generative search), **novel kernel infeasible Forge-side** (assembly-contribution reward needs assembly data Forge lacks) → residual collapses to **new primitives (Path C)**. | D094/D182/D183; D174/D175/D177/D190; D186/D172; `generation-model-levers.md` §5 |
| **LM-G5** effective-N in the king's DSR charge | **Dormant** (king retired). Note a live nuance: Forge already chose *conservative full-N* deliberately. | D190; D175 |
| **LM-S3** Discounted-Thompson yield map | **Awareness only**, plus one concrete loader watch-item for Forge. | (consumer: D182/D183) |

**The unifying doctrine** (Forge's settled division of labor, from D186/D187/D172): **generation owns quality +
directional variety** (proxied from config tokens — the live wf_p25 quality lane D193 + the D103/D136 variety
floors); **decorrelation and assembled-book contribution are owned at assembly** (you have the returns and the
pairwise correlations; we have per-strategy scalars only). Both LM-G1 and the novel half of LM-G2 ask the
generation layer to optimize a *behavioral/joint* quantity it structurally cannot observe pre-assembly.

---

## LM-G1 — phenotypic diversity descriptor → CLOSE (already investigated, D186)

This was the explicit subject of **D186 (2026-06-18)**, the `quality × decorrelation` experiment
(`scripts/decorrelation_proxy_alignment.py`, with a one-off realized-PnL-correlation sample you supplied). Three
findings refute the swap as framed:

1. **The "return-correlation distance" is not computable at generation.** Verbatim (D186): *"Forge has zero
   return/pairwise data (Crucible scores strategies independently, exports per-strategy scalars only)."* This is
   not a weak signal; it is an absent input.
2. **The "regime-exposure distance" was tested directly and is noise.** Verbatim: *"directional-indicator
   distance Spearman −0.195 (calm) / −0.228 (stress); all-indicator −0.114; **regime-gate distance is noise
   (−0.024)**."* The strongest available structural proxy (directional, −0.23) is still judged *"too weak and the
   wrong granularity."*
3. **The residual is per-pair, not per-recipe** — verbatim: *"the residual decorrelation variance is PER-PAIR,
   not per-recipe (realized name/beta overlap) — invisible to a generation-time proxy AND to a per-recipe map."*
   A greedy distance over config descriptors cannot capture a per-pair quantity by construction.

D186's decision (verbatim): *"Decorrelation is owned at ASSEMBLY (Crucible), not generation … **No Forge-side
decorrelation-yield sampler axis** … the generation-time signal is too weak and the wrong granularity."* Your
assembler already diversifies on daily-PnL correlation, which is exactly the right place for this.

Two clarifications on the diversifier itself (`src/forge/ranking/diversifier.py`, live in the submission loop via
`rank_batch` → `select_top_n`):
- It is a **novelty/dedup** filter (§6.3, mirrors the §5.3.5 novelty pre-filter), not a decorrelation proxy. Its
  `content_key`-Jaccard distance *does* saturate near 1.0 (D186's preflight caught this) — which is appropriate
  for catching exact-content duplicates, not a defect to "fix" toward a weak decorrelation heuristic.
- The legitimate kernel of LM-G1 — directional/hypothesis **variety** at generation — is **already implemented**
  in that same `select_top_n` via the D103 per-hypothesis floor and the D136 per-arm floor. D186 explicitly
  credits these: *"hold directional-indicator / hypothesis variety as a light floor … (already partly via D103/D136
  + the diversifier)."*

**If you want empirical closure** rather than the decision-log read, the one thing D186 did *not* run is the
selected-set A/B you specify (does a swapped distance change *which* candidates are submitted AND lower the
*realized* mean pairwise corr of the selected set). We judge it low-EV given the four facts above, and it requires
**you** to score the selected sets (Forge can't measure realized corr). We'll run it if you'd value the documented
result; otherwise we treat LM-G1 as closed by D186.

---

## LM-G2 — learned generative search over the grammar → SUBSUMED; residual is Path C

Three facts collapse this item:

**1. The proposer is already a learned generative sampler, not "enumerate-then-rank" over a fixed grammar.**
`enumerate_candidates` samples the CSP space under **learned per-hypothesis/regime/bucket/directional weights**
(D094) plus the D182/D183 yield-map posteriors you helped design. The sampling *distribution itself* is learned
from feedback and updated. The "enumerate then re-rank a fixed set" premise mischaracterizes the live system; the
learned-distribution half of LM-G2 exists.

**2. The oracle-guided generative-search half was built, ran live, and was retired.** The king/A3 arm was —
verbatim, D174 — *"the generation-side attack (search the genome space to maximize the oracle's predicted durable
`cpcv_sharpe_p25`, queue the top genomes as proposals into the **unchanged** §8.7 gauntlet)."* That is LM-G2's
mechanism. It was deterministic (`SeedHierarchy`, reused `enumerate_candidates`), you unblocked its submit-half
(D175 `source` + `search_n_trials`; D177 stamped them), and it was **retired in D190 (2026-06-19)** — archived to
`~/forge_data/archive/king_retired_20260619/`. Its result corroborates the wall rather than breaking it:
*"Component-grade, not promotion (oracle max ~0.78 « 1.5 wall) … On-manifold by construction (enumerator samples
the training corpus's space)"* (D174). This is strong (not definitive) evidence for LM-G2's own validation bar:
the search wasn't the bound.

**3. LM-G2's one genuinely novel kernel — reward by "downstream assembled-book contribution, not single-config
quality" — is infeasible Forge-side.** Book contribution is a per-pair/joint return quantity; per the D186 fact,
Forge has *zero* return/pairwise data at generation. The king optimized single-config oracle quality precisely
because that is all Forge can observe. An assembly-contribution reward lives where the assembly data lives — with
you. Even if you exported a per-candidate marginal-contribution label, D186's per-pair-not-per-recipe finding says
a config-feature model can't capture the part that matters. Forge's *generation-side* proxy for "good book leg" is
already built and live: the **wf_p25 quality lane** (D193, `prior := P(component) × tail_norm(wf_p25)`) + the
directional/hypothesis variety floors.

**The ceiling argument resolves to your own LM-Q4 fallback.** Forge has documented, on three independent axes
(D161 entry-selection / D164 book-construction / D165 exit-timing), that *"the CPCV-p25 wall is edge magnitude — a
Forge GENERATION problem (World-A)"*, and `docs/proposals/generation-model-levers.md` §5 states it directly:
*"within v1's long-premium grammar the edge magnitude is exhausted (D152/D154), so **no generation model unlocks
promotion — same ceiling the selection models hit.** The promotion unlock remains grammar expressivity (Path C,
parked by operator choice); no model substitutes for it."* D186 even pre-rejected the heavy version explicitly:
alternative (c), *"Heavy generative model conditioned on the pool — rejected (doesn't escape the grammar ceiling;
determinism burden, hard rule #6/#8)."* A generative search still composes from v1's tokens; to move the ceiling
you need new tokens. **That is exactly LM-G2's fallback** ("if the ceiling doesn't move, the bound is the
primitives … new indicator/combiner tokens"), and it is **Path C — operator-gated and currently parked.** No
unilateral build.

---

## LM-G5 — effective-N in the king's DSR-laundering charge → DORMANT, with one nuance

Correctly dormant: the king is retired (D190). Two notes for your register:

- **Register correction:** the retirement is **D190** (2026-06-19), not "D174/D175 archive 2026-06-19." D174 (the
  build) and D175 (your provenance/DSR answer) are both **2026-06-16**; D177 (2026-06-17) was the submit-half
  build. The 06-19 date is D190 (and the archive of the king DB/oracle as part of it).
- **A live nuance if the king is ever revived:** Forge passed the **nominal** N (`search_n_trials = n_searched`,
  the count of genomes scored against the oracle), and D175 deliberately reasoned this is conservative: *"the king
  maximizes the oracle proxy (IC ~0.31), so realized-cpcv multiplicity is < N → deflating by full N over-deflates
  (honest/safe)."* LM-G5's `N_eff` (participation-ratio of the searched genomes' return-correlation spectrum)
  would *reduce* deflation toward accuracy — the opposite direction from Forge's chosen conservatism. On revival
  we'd reconcile "accurate N_eff" vs "safe full-N" rather than mechanically mirror `effective_n.py`. We note your
  helper is ready and the spec is precise; no action while dormant.

---

## LM-S3 — Discounted-Thompson yield map → AWARENESS + one Forge watch-item

Agreed this is Crucible-side; no Forge action now. The one concrete Forge exposure: the D182/D183
`--cohort-yield` / `--regime-gate-yield` loaders consume `structural_yield_map_latest.json`. If the schema gains
decayed/posterior fields, Forge's loader must tolerate the unknown keys, or a pull could stall the daemon (Forge
logs `registry_loaded_from_export` *before* validation, so a stalled daemon can look healthy). **Ask:** flag the
schema change in advance per your stated plan; Forge will confirm loader-leniency in the same adoption step. No
contract action until you ship.

---

## What Forge requests

Nothing blocking. Specifically:
1. **Update review register §7** with these verdicts and the D190 retirement-date correction.
2. **LM-G1:** tell us if you want the selected-set A/B run for documented empirical closure (needs you to score
   the selected sets); otherwise we mark it closed by D186.
3. **LM-G2:** the actionable residual is **new grammar primitives (Path C)** — an operator decision on the Forge
   side, not a proposer/selector change. We'll raise it through the operator's Path-C gate if/when reopened.
4. **LM-S3:** advance-flag the yield-map schema change when it ships.

References (Forge): D094, D103/D136 (variety floors), D152/D154/D161/D164/D165 (the magnitude wall),
D172 (no single config promotes), D174/D175/D177/D190 (king built→retired), D182/D183 (yield-map loaders),
D186/D187/D188 (decorrelation→assembly, quality→generation), D193 (wf_p25 quality lane live),
`docs/proposals/generation-model-levers.md` §5 (honest ceiling).
