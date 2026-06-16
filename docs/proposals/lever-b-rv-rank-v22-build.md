# Lever B build scope — v22: add `rv_rank` (cheap realized vol) as a `mean_reversion` R1 gate

Status: **✅ BUILT + DEPLOYED 2026-06-15 ([[D170]]) — operator approved (A) + relayed/answered (B); built in worktree
`../Forge-v22` (commit `4c4ce84`), full suite 1623 passed, deployed v21→v22.** This scope is now history; the build
record is [[D170]]. (A) `rv_rank` mr R1 gate ([[D167]]) + (B) `event_passed_exit` ladder {3,5,8,13,21} ([[D169]], range
from `FORGE_v22_exit_timecut_fairtest_response.md`). Direct precedent: **[[D107]]** (gamma→R1, v11), **[[D150]]** (hurst→R1,
v20) — same change class, same file surface. Next: Crucible's hypothesis-sliced `funnel --compare v21 v22` (post-drain).

> **⚑ v22 NOW CARRIES TWO CHANGES (operator elected to tie in the [[D168]] exit time-cut fair test, [[D169]]).** v22 =
> **(A) Lever B** — add `rv_rank` as a `mean_reversion` entry R1 gate (this doc) **+ (B) the time-cut fair test** — widen
> `event_passed_exit.n_bars_after_entry` (a `volatility_event` *exit* param) so a fresh cohort tests the [[D168]] "loosen
> early time-exits" suspect OOS. **The tie-in is clean because the two act on DISJOINT hypothesis slices** (A→mr entry, B→vol
> exit), so one v22 bump + a **hypothesis-sliced** `funnel --compare v21 v22` reads both without cross-contamination, and the
> fresh wider-threshold cohort strips the in-sample optimism by construction. **(B) is a sampler-only `_exit_params` change —
> no extra grammar bump beyond (A)'s.** **(B) is GATED on the relay `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md` (Crucible's
> recommended `n_bars_after_entry` range, Ask 1) before `_exit_params` is finalized.** (A) is independently justified and ships
> regardless; if Crucible's range answer or the attribution turns out messy, the fallback is **v22 = (A) alone, (B) → v23**.
> See §6 (revised).

> **⚑ HONEST SCOPE (unchanged, hard rule #6) — a CENTER/quality knob, NOT a tail/promotion unlock.** `rv_rank`-LOW
> concentrates mr into ~2.5× higher-Sharpe entries (cheap−rich +0.095 full-sleeve, +0.142 inside the hurst gate) — a
> per-trade-quality / cap-efficiency lift to the book **center**. Every vol-quintile is net-profitable, so it adds **no
> standalone PnL** and does **not** move the CPCV-p25 tail (the tail is edge-magnitude-bound — [[D165]]'s three-axis close).
> This build is justified as **pool-quality hygiene on the thinnest arm**, not a promotion path. We build it because it is
> the one Crucible-validated, in-scope, positive-EV enumeration increment left — not because it lifts promotions.

## 0. What this is, and the change classification

- **IS:** the v21→v22 grammar bump that adds `rv_rank` (realized-vol percentile, op `<` = cheap) as a **fourth accepted
  `mean_reversion` R1 regime gate**, alongside `iv_rank` / `gamma_flip_distance_pct` / `hurst`, plus a sampler bias toward it
  (the "prefer `rv_rank`" economy call). Mirrors [[D150]] exactly.
- **Classification (`docs/tasks/grammar-change.md`):** an **operator-directed loosening** (widens what passes R1) + an
  **enumeration-policy bump** (the deterministic stream changes → `grammar_version` bumps for cohort attribution). The
  `rules:` YAML block text does not change (the R1 `function:` reference is unchanged; the accepted set lives in the Python
  validator), but R1's **semantics** widen — so it needs **explicit operator approval** (hard rule #1), exactly as D107/D150.
- **NOT routed through `OPEN_PROPOSALS.md`.** That queue is for Forge's **auto-tune** loosenings (the `auto_tune_loosen`
  approval-marker flow). [[D150]] — the direct precedent — was an *"operator-DIRECTED loosening (not auto), grammar-change
  ritual"* recorded as a D-entry; the D-entry + operator approval **is** the audit trail. **This corrects the
  `conditioning-levers.md` §2/§3 note** that said the loosening goes "to `OPEN_PROPOSALS` via the approval flow" — that
  applies to auto-loosenings, not an operator-directed R1 widening.
- **NOT a §8.7 / promotion-gate change** (hard rule #3) — R1's pass/fail *logic* is unchanged; only its accepted-gate set
  widens. **NOT** a build yet — no file edited.

## 1. The R1 edit — ADD, don't replace (recommended); bias the sampler to PREFER `rv_rank`

Crucible's "replace vs stack is your grammar-economy call" resolves cleanly given R1 is an **OR** (any one accepted gate
satisfies it; a config carries exactly one regime gate):

- **ADD `rv_rank` to R1's accepted set** (do NOT remove `hurst`). R1 accepts `{iv_rank, gamma_flip, hurst, rv_rank}`.
  Removing `hurst` would orphan every existing hurst-gated mr config and is a larger, riskier semantic change for no gain —
  Crucible's "hurst earns no marginal quality once `rv_rank` is in" is about *stacking both on one config*, which R1-as-OR
  never does. **Recommended.** (The minimal form Crucible named.)
- **Express "prefer `rv_rank`" via the sampler bias, not the grammar.** Add `rv_rank` to `_MR_RANGING_GATES` (`sampler.py:113`)
  so it inherits the D150 **3.0** weight in `_pick_regime` (`sampler.py:850-854`) — biasing new mr configs to pick `rv_rank`
  (or gamma/hurst) over the prefilter-sparse `iv_rank`. `rv_rank` is the *densest* of the ranging gates (a name-relative
  percentile that fires uniformly — Crucible's "no absolute-threshold fragility"), so it belongs in the high-weight set. A
  later tuning option (not v22): weight `rv_rank` *above* hurst to make it the dominant pick — defer to funnel evidence.

**Direction is free:** `rv_rank`'s spec already has `op_regime="<"` (cheap/LOW = vol cheap; `indicator_thresholds.py:271-275`),
which is exactly mr's calm-vol edge — so, unlike D150's `hurst` (which needed an explicit MR-side op), **`rv_rank` needs no
per-hypothesis op edit.** (Build-verify: confirm the sampler emits op `<` for mr's `rv_rank` gate and that `rv_rank`'s
existing presence in the *trend* R2 pool doesn't force a different op cross-hypothesis — a `test_sampler` assertion.)

## 2. Change surface (file:line — the D150 template, verified current)

| edit | file:line | note |
|---|---|---|
| add `_R1_RV_RANK_REGIME_INDICATOR = "rv_rank"` constant | `custom_predicates.py` (near `:288-301`) | alongside the other 3 R1 constants |
| R1 validator: accept a `rv_rank` regime gate (op-agnostic, like gamma/hurst — no threshold check) | `custom_predicates.py:830-848` | add a branch after the `hurst` branch (`:838-839`); update the failure-detail string (`:851-856`) |
| MR regime pool `+= rv_rank` | `search_space.py:342-351` | add `_R1_RV_RANK_REGIME_INDICATOR` to the set (+ import, `:39-41`) |
| sampler ranging-gate bias `+= rv_rank` | `sampler.py:113` (`_MR_RANGING_GATES`) | inherits the 3.0 weight; the "prefer rv_rank" economy |
| `grammar.yaml`: `grammar_version: v21 → v22` + header version-history note + R1 `evidence_to_relax`/rationale touch-up | `config/grammar.yaml:370`, `:592-602`, header `~:133` | ANY byte change trips the bump hook |
| archive byte-identical copy | `config/grammar_archive/v22.yaml` | `cp config/grammar.yaml config/grammar_archive/v22.yaml` (loader checks at startup) |
| `GRAMMAR.md#R1` narrative sync | `docs/GRAMMAR.md` | doc-sync hook fires on rule-id paths |
| **(B, [[D169]])** emit `event_passed_exit: {n_bars_after_entry: <sampled>}` from a wider range | `sampler.py:1179-1183` (`_exit_params`) | **sampler-only, no extra bump**; range from the relay (Ask 1); gated on `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md` |

The R1 `function:` name (`mean_reversion_requires_iv_rank_gate`) **stays** — it's a registry key; renaming for cosmetics is a
needless larger diff (D150 kept it through the hurst addition too). The (B) `_exit_params` widening is the only change that
also re-pins the exit-emission golden tests; both (A) and (B) re-pin the shared sampler golden sequence (§4).

## 3. The rank-coherence decision (a real fork — recommend LET it rank)

`rv_rank` is **rank-coherent** (`rank_per_name_coherent=True`, bar-only — Crucible-confirmed). MR rank is **enabled** since
[[D151]]. So adding `rv_rank` to MR's pool means `rv_rank`-gated mr configs **can rank** (unlike the chain-reading `iv_rank`,
which stays rank-excluded). Two options:

- **LET it rank (recommended).** Consistent with `rv_rank`'s coherence and Crucible's "works on both confluence and rank."
  Caveat Crucible flagged: **mr's edge is on *confluence*** (mr rank caps at cpcv 0.729, "refuted on its own terms") — so the
  rank configs will be **weak-but-harmless** (the prefilter/ranker down-weights them; they don't threaten anything). Simplest;
  no new rank-exclusion machinery. The emission proof reports the confluence/rank split.
- **RESTRICT to confluence-only** (add `rv_rank` to the mr rank-exclusion, the D150-interim style). More code, contradicts
  `rv_rank`'s coherence, and buys little since weak mr-rank is harmless. **Not recommended** unless the emission proof shows
  an unwanted mr-rank surge.

Unlike [[D150]] (which had to *suppress* mr rank pending the Q33 hurst-coherence answer, then re-enable at [[D151]]), there is
**no coherence question to resolve here** — `rv_rank`'s flag is already published and confirmed. So no suppress/re-enable
dance.

## 4. TDD plan (red-first — `docs/tasks/grammar-change.md` step 3)

Write these failing first, confirm they fail for the right reason, then implement:

1. **`test_custom_predicates`** — an mr config gated *only* on `rv_rank` (op `<`) **passes R1** (today it fails: `rv_rank ∉
   {iv_rank, gamma_flip, hurst}`). Plus: an mr config with *no* accepted gate still fails (regression — the OR didn't go
   permissive).
2. **`test_search_space`** — `_build_regime_pool["mean_reversion"]` includes `rv_rank` (when in the registry).
3. **`test_sampler`** — mr emits `rv_rank` regime gates at op `<`; the `_MR_RANGING_GATES` bias includes `rv_rank`; the
   cross-hypothesis op check (§1 build-verify).
4. **`test_cross_sectional_rank`** — `rv_rank`-gated mr **ranks** (the §3 decision) — asserts the chosen behavior so a later
   regression is caught.
5. **(B, [[D169]]) `test_sampler`** — `_exit_params` emits `event_passed_exit.n_bars_after_entry` sampled from the
   relay-supplied range (deterministic from the seed hierarchy, hard rule #8); the previously-inert exit now carries a param.
6. **Golden / determinism re-pin (deliberate, hard rule #6):** `test_sampler` golden-sequence assertions +
   `test_phase2_invariants` (R1/R2/R3 regime-membership) + `test_batch_reproducibility` re-baselined — the stream changes
   ((A) new gate in the pool + the bias re-weight; (B) the new exit param), so the golden sequence changes *by design*;
   re-pin it, never casually. The **cold path** (single-gate, no >1) stays `rng.choice`-byte-identical for (A) (the bias
   engages only with >1 gate present — the D150 property); (B) changes every config that composes `event_passed_exit`.

## 5. Determinism, version, archive (hard rules #6, #10)

`(grammar_version, registry_hash, seed)` → identical sequence **after** the deliberate re-pin (rule #6 preserved; the
sequence simply changes). `grammar_version` v21→**v22** for cohort attribution; `grammar_archive/v22.yaml` byte-identical;
both grammar pre-commit hooks (`grammar-version-bump`, `grammar-doc-sync`) must pass.

## 6. Batching decision — v22 = (A) Lever B + (B) the `event_passed_exit` time-cut fair test (REVISED, [[D169]])

**Operator elected to tie the [[D168]] exit time-cut fair test into v22.** This REVISES the original "Lever B alone"
recommendation — and on inspection the tie-in is clean, not muddy, because the two changes act on **disjoint hypothesis
slices**:

| change | touches | read on |
|---|---|---|
| **(A) Lever B** — `rv_rank` mr **entry** R1 gate | `mean_reversion` configs | **mr** slice: component-rate, per-trade Sharpe / cap-efficiency, CPCV-p25 (expected center-lift, ~flat tail) |
| **(B) time-cut fair test** — widen `event_passed_exit.n_bars_after_entry` (**exit** param) | `volatility_event` genomes that compose it (AMD-vol, SOXL-vol) | **vol** slice: worst-quartile / CPCV-p25 + never-peaked-loss share |

⇒ a **hypothesis-sliced** `funnel --compare v21 v22` reads each lever on its own slice, so attribution survives the batch
(the [[D151]] clean-cohort concern is met by slicing, not by separating the deploys). Two conditions make this hold, both
honored: **(i)** widen **only** `event_passed_exit` (vol-scoped), **NOT** `time_stop.n_bars` (cross-hypothesis → would
contaminate the mr slice — deferred, relay Ask 4); **(ii)** (B) is GATED on the relay (Crucible's recommended range, Ask 1)
before `_exit_params` is finalized.

**Why batch rather than v22+v23:** (B) is sampler-only → it rides (A)'s bump for free (no second deploy), and the **fresh
wider-threshold cohort IS the fair OOS test** ([[D168]] in-sample optimism stripped by construction — new `config_hash`es,
selected fresh). Tying it in is strictly more efficient *given* the slices are disjoint.

**Fallback (the "try" in the operator's call):** if Crucible's range answer is unworkable, or the sliced attribution looks
contaminated, drop back to **v22 = (A) alone, (B) → v23**. (A) never blocks on (B).

**Still NOT in v22:** the rest of the [[D165]] exit-param sweep (`premium_stop`/`target_exit`/etc. — confirmed non-tail
hygiene, nothing to measure) and the trend high-vol/trending tilt ([[D166]], IC-bound, declined).

## 7. Build → deploy → measure (the ritual, `docs/tasks/{grammar-change,deploy}.md`)

0. **(B-gate)** relay `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md` → Crucible's recommended `event_passed_exit.n_bars_after_entry`
range (Ask 1). (A) can start in parallel; (B)'s `_exit_params` edit waits on this answer. →
1. Operator approves the R1 widening (this scope) → 2. worktree build (service is live; never the live tree) → 3. TDD §4 →
4. implement §2 ((A) R1 edit + (B) `_exit_params` once the range lands) → 5. v22 bump + archive + GRAMMAR.md#R1 sync →
6. emission proof (`uv run forge enumerate --max 50 --summary` + the `_build_regime_pool`/mix recipe — expect mr `rv_rank`-gate
share material + `event_passed_exit` carrying a varied `n_bars_after_entry`) → 7. full uncontended suite + `mypy --strict` +
`ruff` → 8. D-entry + STATUS → 9. deploy (`deploy.md`: stop → suite → commit → restart → journal verify) → 10. relay `v21→v22`
to Crucible for a **hypothesis-sliced** `funnel --compare v21 v22` (mr slice = (A); vol slice = (B)).

## 8. Operator decisions needed (to proceed)

1. **Approve the R1 widening** (the go/no-go for (A); hard rule #1) — empirically justified by [[D164]]; this is the gate.
2. **Confirm ADD-not-replace** (§1) — recommended; keeps existing hurst configs, expresses "prefer" via the sampler bias.
3. **Confirm LET-it-rank** (§3) — recommended; weak-but-harmless mr-rank, no new exclusion machinery.
4. **v22 = (A) Lever B + (B) `event_passed_exit` time-cut fair test** (§6) — **operator-elected** ([[D169]]); disjoint slices →
   sliced funnel preserves attribution; (B) gated on the relay's range answer, fallback = (B)→v23. Relay
   `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md` is **drafted, awaiting operator send** (it gates (B), not (A)).

Decisions 1–3 have clear recommended defaults; #4 is the operator's elected tie-in. On approval + the relay's range answer I
build red-first in a worktree per §7. Nothing is built or bumped until then; **(A) can proceed before (B)'s range lands.**

## 9. Artifacts / cross-references

- This scope: `docs/proposals/lever-b-rv-rank-v22-build.md` ([[D167]]).
- The cleared gate: `../Crucible/docs/handoffs/FORGE_mr_rv_hurst_overlap_response.md` ([[D164]]).
- The lever's origin + change surface: `conditioning-levers.md` (Lever B, [[D159]]/[[D161]]/[[D164]]).
- Precedents: [[D107]] (gamma→R1, v11), [[D150]] (hurst→R1, v20), [[D151]] (mr rank enabled).
- **(B) the tied-in exit time-cut fair test:** `exit-tail-shaping.md` ([[D168]] addendum) + relay `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md` ([[D169]], drafted/held).
- Deferred (NOT in v22): the rest of the [[D165]] exit-param sweep (non-tail hygiene); the trend tilt `momentum-cheap-iv-conditioning.md` ([[D166]], IC-bound); `time_stop.n_bars` widening (cross-hypothesis, relay Ask 4).
- Honest scope authority: [[D165]] (three-axis tail close), [[D152]] (exhaustion verdict).
