# Exit-parameter sweeping as a CPCV-p25 TAIL lever (in-scope) — scoped, probe-gated

Status: **✅ FAIR TEST BUILT INTO v22 + DEPLOYED 2026-06-15 ([[D170]]) — the [[D168]] time-cut suspect is now under live OOS
test.** Crucible answered the range (`FORGE_v22_exit_timecut_fairtest_response.md`): `event_passed_exit.n_bars_after_entry`
samples the loosening ladder **{3,5,8,13,21}** (was inert → default 3) on a fresh vol_event cohort. **Decisive masking
caveat:** widening past 5 is inert for any genome composing `time_stop@≤5` (SOXL-vol capped; AMD-vol runs to theta_cliff,
flips +$31k) → the vol-slice lift will be **diluted** (read a muted result as partial masking, not a dead lever);
`time_stop` deferred. Fresh-cohort = fair OOS test confirmed (4 leaks flagged). Awaiting Crucible's hypothesis-sliced
`funnel --compare v21 v22` (post-drain ≥1500). **Origin verdict (D168):** the D165 "confirmed non-tail" was PREMATURE for
the 2 `event_passed`-composing wall-setters — stripping that over-tight early time-cut turns their worst-quartile crater net
−$2.9k → +$31.9k and drops never-peaked loss 76%→44% (a "structural"-looking slice was cut-too-early-to-peak); the lever is
LOOSENING early time-exits, hard-caveated (in-sample optimism, not trade-count-neutral). Operator asked, of the long-options program, "what would help the CPCV-p25 tail — different regime
filters or different exit criteria?" This doc answers: **regime filters are the entry-side lever the
[[D158]]/[[D159]]/[[D161]] program already pulled and [[D161]] empirically showed is a *center* knob; exit
*parameters* are the genuinely-unswept, tail-shaped lever.** Sibling to `conditioning-levers.md` ([[D159]]) and
`momentum-cheap-iv-conditioning.md` ([[D158]]) — those condition *entry*; this shapes the *exit*. Relates:
[[D161]] (center-vs-tail distinction), [[D156]] (the trade-count headwind this lever SIDESTEPS), [[D152]] (the
exhaustion verdict and its M2 vol-target tail finding), Q42 (`OPEN_QUESTIONS.md`).

> **⚑ ADDENDUM — D165 PARTIALLY REOPENED: the productive lever is LOOSENING early time-exits, and it may touch the wall ([[D168]], `../Crucible/docs/handoffs/FORGE_exit_tail_attribution_addendum.md`; `probe_exit_tail_attribution.py --strip-exit event_passed_exit` → `exit_tail_no_eventpassed.json`, commit 81a4e15).** Crucible followed up on its own design-note #1 (`event_passed_exit` = the #1 wall-setter exit, 55%, off the original sweep list). `event_passed_exit` is **per-genome** (only 2 of the 6 wall-setters compose it: AMD-vol, SOXL-vol; others use chandelier/trailing/`time_stop`); all keep the mandatory backstops (`expiry`/`theta_cliff`/`earnings`/`liquidity`). **Stripping it changes those two a lot, on their worst-quartile blocks:**
>
> | genome | trades | crater net | never-peaked %loss |
> |---|---:|---:|---:|
> | AMD-vol baseline | 137 | −$137 | 76% |
> | AMD-vol without it | 40 | **+$31,259** | 44% |
> | SOXL-vol baseline | 86 | −$2,727 | 75% |
> | SOXL-vol without it | 60 | **+$677** | 63% |
> | **2-genome sum** | | **−$2.9k → +$31.9k** | |
>
> **Mechanism — it CORRECTS D165's "~60% structural" read.** `event_passed_exit` chops positions a few bars after entry (~tripling trade count with short cuts). Remove it → positions hold to `theta_cliff`/`expiry` → losers' total loss shrinks AND winners grow, because positions live long enough to develop favorable excursions. **Never-peaked loss share falls 76%→44%** — i.e. a real slice of what read as "structural, negative entry-to-any-exit" was actually **cut-too-early-to-peak**, and that slice **is exit-shapeable.** So the D165 "confirmed non-tail / ~60% irreducible" was **premature for the `event_passed`-composing genomes.**
> - **Direction FLIPS (correcting §2 and the D165 swept-knob note):** the headroom is in **LOOSENING early time-exit thresholds** (`event_passed_exit.n_bars_after_entry`, `time_stop.n_bars` — firing too tight, suppressing the convex upside), **NOT** tightening stops or adding profit-targets (still bounded by the structural floor + the winner-capping convexity tension). This fits the convex long-options payoff — for this book the enemy is cutting early, not holding. **`event_passed_exit.n_bars_after_entry` is added to the swept set** (it honors `params`); it is the single most impactful knob found.
> - **Hard caveats (bound it — a SUSPECT, not a win):** (i) **in-sample optimism** — a post-hoc strip on the *same data the genome was Optuna-selected on* (entry/sizing were tuned *with* this exit's churn), so the +$32k carries selection bias; (ii) **single-config**, not the joint book; (iii) for `event_passed` it is **explicitly NOT trade-count-neutral** (137→40 trades) — which **breaks this doc's §2 trade-count-neutral premise** for the time-exit-loosening form. ⇒ treat as a **flagged suspect for a fair test**, not a confirmed "loosen it."
> - **Disposition ([[D168]] → TIED INTO v22, [[D169]]):** the exit thread is **no longer cleanly closed** — there is a directionally-corrected, caveated, possibly-tail-relevant suspect on 2 wall-setter genomes. **The fair test** (strips the in-sample optimism by construction): emit configs with **wider** `event_passed_exit.n_bars_after_entry`, let Crucible re-select/validate them **fresh** (OOS), read the worst-quartile / CPCV-p25 delta via `funnel --compare`. **Operator elected to TIE this into v22 ([[D169]])** as change **(B)** alongside Lever B **(A)** — clean because (A) is an **mr entry** gate and (B) is a **vol exit** param (DISJOINT hypothesis slices → a hypothesis-sliced funnel preserves attribution), and (B) is sampler-only so it rides (A)'s bump. **(B) is gated on the relay `PROMPT_CRUCIBLE_V22_EXIT_TIMECUT_FAIRTEST.md`** (drafted/held — Crucible's recommended `n_bars_after_entry` range, Ask 1); widen **only** `event_passed_exit` (NOT `time_stop`, cross-hypothesis); fallback = (B)→v23. Full plan: `lever-b-rv-rank-v22-build.md` §6. The three-axis "magnitude wall" close ([[D165]]) is **softened on the exit axis**: entry ([[D161]]) and construction ([[D164]]) stand; the exit axis has a live-but-caveated suspect now under fair test in v22.

> **✅ PROBE ANSWERED — thesis [SUPERSEDED → see the addendum above] CONFIRMED NON-TAIL; buildable only as hygiene ([[D165]], `../Crucible/docs/handoffs/FORGE_exit_tail_attribution_response.md`; `probe_exit_tail_attribution.py` → `exit_tail_attribution.json`, commit 483386f).** Both asks answered on the 6 lowest-p25 long-options wall-setters (248 crater losers). **Verdict: build it if cheap — a clean trade-count-neutral hygiene/dispersion lever — but it CANNOT move the binding wall.**
> - **~60% of the tail is structurally irreducible.** 56% of crater losers **never peaked positive** (58% of loss); **median loser MFE-peak = 0.0** — underwater from the first mark. No profit-take/trailing exit recovers it. The losers are **early time-cuts** (event_passed 55% · time_stop 32% · theta_cliff 12%, low hold-fraction), **NOT slow theta-decay** — which corrects this doc's §2 "theta-bleed-to-zero" mechanism premise: the structural loss is *underwater-from-entry then time-cut*, an **entry/edge** problem, not an exit-timing one.
> - **Give-back headroom exists but is OFF the wall.** Clean give-back (peaked ≥25%) = only **14% of loss**, and it lives in **higher-p25 MR components (p25 0.29–0.36) that don't set the wall** (MR losers round-trip — matches the MR-edge-is-entry finding). The actual wall-setters (trend/vol, p25 0.029–0.097) are **59–76% never-peaked, 1–8% give-back.** So exits help where it doesn't matter and can't help where it does.
> - **The convexity tension (the deep reason).** Oracle peak-exit recovers 1.31× the loss but is a perfect-foresight ceiling dominated by convex round-trips; crater **winners give back only 23% (they run)**, so a target tight enough to catch loser round-trips **also caps the winners carrying the book.** Net-EV is exactly what a sweep would have to resolve — and on the wall-setters there's almost no give-back to win in the first place. (This is the same convexity that makes S5 forbid `hard_profit_target` on trend.)
> - **Ask-2 correction to §3's swept-knob spec (params honored 7/8 — NO D068/D138 hazard):** Crucible's `build_exit()` reads `ExitSpec.params` (`params.get(key,default)`) for 7 of 8. **DROP `hard_profit_target`** (no-op `DeferredExit`, `registry.py:219`, §6.5.3-forbidden; `target_exit` is the real profit-target lever). **ADD `event_passed_exit.n_bars_after_entry`** — the #1 wall-setter loser exit (55%), honored but off the original list. Swept knobs: `premium_stop_loss.stop_pct` · `atr_underlying_stop_loss.{n_atr,atr_period}` · `time_stop.n_bars` · `theta_cliff_exit.dte_threshold` · `target_exit.{target_pct|target_atr_multiplier}` · `convergence_exit.target_zscore` · `zscore_reversion_exit.{exit_zscore,lookback}` · `event_passed_exit.n_bars_after_entry`. **But:** wall-setter genomes don't compose `premium_stop`/`target_exit`/`trailing_atr` at all — for them the only live knobs are `time_stop`/`theta_cliff`/`event_passed`, and the probe says even those can't reach the structural ~60%.
> - **Disposition ([[D165]]):** thesis CONFIRMED NON-TAIL — this is the (b) "structural bleed → no help; firms [[D152]]" branch of §5, decisively. The lever is **viable hygiene** (Crucible: "build it if cheap"), **not** a wall-mover. **Deprioritized below Lever B** (which is also a quality knob but has a cleaner measured story); **don't spend a standalone deploy** on a confirmed-non-tail lever. If built at all, **batch the corrected `_exit_params` sweep onto the Lever B v22 deploy** (both re-pin the golden sequence anyway — near-free) or revisit as pool-hygiene later. The worst-quartile *regime* fix stays sell-side / Path C; the wall is **edge magnitude — a generation problem** (World-A), now confirmed on a **third** independent axis (entry [[D161]] · construction [[D164]] · exit [[D165]]).

> **⚑ ADJACENT REFUTATION FOLDED IN ([[D164]], `../Crucible/docs/design_regime_conditioned_construction.md` §4–§6).** Crucible built and tested the **closest prior art to this thesis** and it landed NEGATIVE. Their **L2 = a book-level *selective* regime de-gross** that, on transition into an adverse regime, **trims held exposure via a partial-liquidation action** (an *exit-side* risk-shaping capability, §4 property 2 / §7.5). The §6 cap-interaction backtest (era-C 342-comp book) **REFUTED L2: uniform vol-target DOMINATES it** on BOTH maxDD (−23.6% vs −40.1%) and Sharpe (1.75 vs 1.42). **The mechanism is the load-bearing update for THIS doc:** *"the book's drawdowns are NOT regime-confined — **theta bleed in calm + vol spikes** — which continuous book-vol-targeting catches and a targeted lever misses."* Theta-bleed-in-calm is the **exact** left-tail my §2 exit thesis targets, and Crucible's evidence says the **existing uniform vol-target already harvests it.** Plus the settled framing: *"cap bounds the tail, selection never moves maxDD"*; the CPCV-p25 wall is **edge magnitude — a Forge generation problem** (World-A), not a construction/exit gap.
>
> **Net effect:** EV downgraded from "calibrated-low" to **"likely dominated by the existing uniform vol-target."** This is NOT a full refutation — the exit-param sweep is *per-trade, per-config* exit timing, a finer granularity than L2's *sleeve-level, regime-conditioned* book de-gross, and it operates **inside** the vol-target rather than replacing it. The open question narrows to: **does per-trade exit-timing variation add CPCV-p25 BEYOND what uniform vol-target already captures?** The exit-attribution probe (already SENT) answers it — but reframed as **confirmatory**, with the prior now "expect vol-target already caught it." If the probe shows worst-fold give-back the book-vol-target did *not* catch → a thin residual; if it shows vol-target already harvested it (the L2-consistent expectation) → **fold D163 closed**, reinforcing the magnitude wall on a third independent axis (entry [[D161]] · construction [[D164]] · exit). **Do not build ahead of the probe; the prior is now adverse.**

> **⚑ EV CALIBRATION — read first. This is a robustness/hygiene lever, NOT a promotion unlock.** The structural
> sign claim ([[D152]]/[[D154]]) still binds: no exit policy turns long premium into the seller's edge. In the
> worst *regime* folds (bear worst-quartile ~2.39×, ranging ~1.33×) you pay the VRP on every trade — exits can
> **truncate losers** but cannot manufacture positive worst-fold Sharpe. So the realistic prize is the same
> thin **1.40 → 1.5 pocket via dispersion-tightening**, plausibly a fraction of Crucible's measured M2
> vol-target lift (**+0.07 to p25**, [[D152]]). What makes it worth scoping anyway: of the in-scope levers it
> is the **only one that is (a) genuinely unswept, (b) mechanistically aligned with the tail metric, and (c)
> trade-count-NEUTRAL** — it sidesteps the [[D156]] headwind that sinks every entry gate. A better profile than
> the entry gates, on a thinner prize. **Probe before build** (§4) — same discipline as [[D158]] step-0 and the
> [[D161]] hurst-overlap gate.

## 0. What this is, and is NOT

- **IS:** a scoped, gated plan to make `forge.enumeration.sampler._exit_params` **sweep the exit thresholds it
  currently leaves at Crucible defaults** (stop tightness, profit-target level, time-stop horizon, theta-cliff
  timing), within the S5-permitted exit set per hypothesis, so the produced cohort spans the part of the
  trade-return distribution that CPCV-p25 keys on. Sampler-only enumeration policy, hard-rule-6 framed.
- **IS NOT:** a build. No `sampler.py`, `grammar.yaml`, or contracts edit has been made. No version bump, no
  `OPEN_PROPOSALS.md` record, no deploy. The relay is **SENT (2026-06-15) — awaiting Crucible's answer.**
- **IS NOT:** a threshold/gate change to Crucible's §8.7 bar (hard rule #3), and **NOT** a grammar change — it
  varies exit *params* inside the already-permitted exit *vocabulary*; it adds no exit IDs and edits no E1–E3 /
  S5 rule.
- **IS NOT:** a promotion path or a reopening of the exhaustion verdict. A clean "exits can't lift the tail"
  result *firms* [[D152]]; a lift is a cheap in-scope hygiene gain, not a 1.5 unlock.

## 1. The gap (grounded, line-cited): exits are enumerated at the ID level, parametrically inert

Forge's grammar expresses exits richly — the `StrategyConfig.exits` field, 4 `MANDATORY_EXIT_IDS`
(`earnings_exit, expiry_exit, theta_cliff_exit, liquidity_exit`), 18 `KNOWN_EXIT_IDS` (incl. the discretionary
risk shapers `premium_stop_loss`, `atr_underlying_stop_loss`, `hard_profit_target`, `time_stop`, `target_exit`,
`zscore_reversion_exit`, `convergence_exit`, `iv_crush_exit`), E1–E3 grammar rules (`grammar.yaml:549-586`), and
S5 hypothesis-exit matching (`exits_match_hypothesis` / `_S5_HYPOTHESIS_EXITS`).

But the sampler varies only **which** exits compose, never **how** they fire:

- `_build_exits` (`sampler.py:943-983`) composes the exit *set*: E1 mandatory + S5 `required_always` + exactly
  one from `required_from_set` (rng) + 0..2 `optional_additions` (each Bernoulli p=0.5). So the **ID set**
  varies across configs.
- `_exit_params` (`sampler.py:1179-1183`) supplies the **parameters**, and it returns **`{}` for every exit
  except `trailing_atr`** — and `trailing_atr` only gets `activate_after_gain_pct ∈ [0.30, 0.50]` because
  grammar rule **E3 forces** a non-trivial activation. Every other exit ships with **empty params → Crucible's
  default threshold.**

**Consequence:** every `premium_stop_loss` runs at the same stop, every `hard_profit_target` at the same
target, every `time_stop` at the same horizon, every `theta_cliff_exit` at the same cliff — across the entire
enumerated population. The stop/target/horizon knobs — the ones that reshape the realized trade-return
distribution — are a **dark axis.** No proposal doc or open question has touched exit *parameters* (Q41 is the
entry/breadth coverage gap; this is its exit-side, tail-shaped sibling — Q42).

Contrast the **sizer**, where the same class of knob *is* already swept: D074 samples `vol_target_annual ∈
[0.10, 0.30]` and `kelly_fraction ∈ [0.10, 0.50]` (`sampler.py:905-940`), "the grammar doesn't constrain these
knobs; they're sampler-side variation." Exit-param sweeping is the **direct precedent-following extension** of
D074 to the exit half of the risk-shape family.

## 2. Why this is the TAIL-shaped lever (the mechanism)

CPCV-p25 is the 25th-percentile OOS Sharpe across the purged folds — a **worst-quartile robustness** number.
Two ways to lift it: cut the left tail of trade returns, or tighten cross-fold dispersion. The two lever
families act on different parts of the distribution:

- **Entry conditioning (regime / vol-cheapness gates)** picks *which* trades to take → concentrates entries
  toward higher-mean setups → lifts the **median/center**. [[D161]] measured exactly this on the live ledger:
  `rv_rank` cheap−rich gives mr a ~2.5× per-trade-Sharpe gradient (+0.095) but is explicitly *"a lift to the
  book center, NOT the CPCV-p25 tail."* And each added gate **cuts trade count** → §8.7 DSR deflates harder
  ([[D156]], the binding constraint) → fights the tail two ways.
- **Exit shaping (stop / target / time-stop params)** reshapes the realized payoff of the trades you *do* take
  — specifically the **left tail.** A long option's worst single-trade outcome is theta-bleeding toward zero on
  a thesis that didn't play out; an earlier time-stop / premium-stop / theta-cliff truncates that. Truncating
  the left tail is what lifts a *worst-quartile* metric — and, decisively, it is **trade-count-NEUTRAL** (you
  still ENTER the same trades; you exit losers earlier), so it **sidesteps the [[D156]] headwind** that kills
  every entry gate.

This is not speculation — it has empirical corroboration in the exhaustion record itself: **the one lever
Crucible measured as tail-positive is M2 vol-targeting (+0.07 to p25, with the real effect on drawdown,
DD-p75 +0.27-0.33; [[D152]]) — a risk-*shape* lever, the same family as exits.** The tail moves on shape, not
on entry selection.

**Hypothesis-specificity (S5 already encodes it — a feature, not a complication):** the legitimate exit knob
differs by hypothesis, and the grammar already forbids the wrong ones. `trend_continuation` **forbids**
`hard_profit_target` (S5) because it wants the convex *right* tail (`OPEN_QUESTIONS.md:657` — "trend's
convex-payoff design deliberately wants tail payoff"); for trend the only legitimate knob is **left-tail
truncation** (time-stop / premium-stop / theta-cliff *timing*), never an upside cap. For `mean_reversion`,
`target_exit` / `zscore_reversion_exit` / `convergence_exit` *are* the natural knobs. The sweep stays inside
the S5-permitted set per hypothesis — so it respects, rather than overrides, the existing payoff-design intent.

## 3. The change surface (verified, line-cited)

| edit | file:line | bump? |
|---|---|---|
| extend `_exit_params` to sample per-exit thresholds from audited ranges (hypothesis-aware) | `sampler.py:1179-1183` | **NO** — sampler-side variation (the D074 sizer precedent) |
| audited per-exit param ranges (stop %, target %, time-stop horizon, theta-cliff DTE) | new constants, sampler/`indicator_thresholds.py`-adjacent | no |
| re-pin the golden sampler sequence (hard rule #6 deliberate change) | `tests/unit/test_enumeration/test_sampler.py`, `tests/integration/test_batch_reproducibility.py`, `tests/invariants/test_phase2_invariants.py` | no (rule #6 preserved — same `(grammar_version, registry_hash, seed)` → same sequence *after* re-pin) |
| `grammar.yaml` | — | **NO CHANGE** — exits stay inside the permitted vocabulary; no exit ID added, no E1–E3 / S5 edit |

**Constraints to honor in the param ranges (so configs stay valid by construction):**
- **E2** (`at_most_two_stop_loss_exits`) — the *set* already satisfies this; param sweeping doesn't change it.
- **E3** (`trailing_atr_has_activation_threshold`) — keep `activate_after_gain_pct ≥ 0.30` (already enforced).
- **S5** per-hypothesis permitted set — sweep only params of exits already permitted for that hypothesis
  (e.g. no `hard_profit_target` param for trend — it's forbidden, never emitted).
- **The audited ranges must produce executable, non-degenerate exits** (a stop so tight it fires intrabar on
  noise, or a target so wide it never fires, both collapse the variation) — calibrate against the live feature
  cache, the [[D131]]/[[D135]] threshold-audit discipline, not hardcoded blind.

**The decisive open risk — Crucible-side param honoring (§4 confirms it before any build).** Exit params are
*emitted* by Forge but *executed* by Crucible's backtester. There is direct precedent that not every param
dict is read: `pairs_convergence` ignored Forge's entry knobs until D068 populated `signals[0].params` the
template actually reads, and `option_momentum`'s `min_months` had to be probe-confirmed as per-config (not a
global constant) at D138. So **some `ExitSpec.params` may be honored per-config and some may use Crucible's
template default regardless.** Sweeping a param Crucible ignores is inert. This must be confirmed *first* — it
is the cheap gate that decides whether the build does anything (§4).

## 4. The Crucible probe that GATES the build (the "analyze" step)

Don't build until we know (a) the worst folds are *fixable* by exits at all, and (b) which exit params Crucible
honors. Both are cheap reads, and Crucible has already demonstrated the exact machinery: the [[D161]] and
[[D159]] results were **causal trade-attribution on the live ledger** (era-C, §13.16 causal entry values). The
same tool answers the tail question. Relay (**SENT 2026-06-15**): `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md`.

**Ask 1 — worst-fold exit attribution (does the headroom exist?).** Decompose the **CPCV-p25 worst-fold
trades** by exit reason / holding period / give-back-from-peak. Of the trades sinking the worst quartile, what
fraction are **theta-bled-to-near-zero longs** that an earlier time-stop / premium-stop / theta-cliff would
have truncated, vs. **adverse-regime structural bleed** (every trade in a bear/ranging fold loses regardless of
exit)?

**Ask 2 — which exit IDs honor per-config `ExitSpec.params`?** The D068/D138 risk: enumerate which of the
discretionary exits (`premium_stop_loss`, `atr_underlying_stop_loss`, `time_stop`, `theta_cliff_exit`,
`hard_profit_target`, `target_exit`, `convergence_exit`, …) read their threshold from per-config
`ExitSpec.params` vs. use a backtester template default — so we sweep only the params that actually bite.

## 5. Expected value and the two clean outcomes

The EV is low and bounded by the sign ceiling (§EV banner). The value is in the *decision the result enables*:

- **Worst folds dominated by truncatable left-tail trades →** the exit-param lever has real headroom; the build
  (a sampler-only `_exit_params` sweep, no bump) is the cheapest positive-EV in-scope increment left, and it is
  trade-count-neutral so it doesn't pay the [[D156]] tax. Plausible prize: a fraction of M2's +0.07, pushing a
  near-miss cohort's p25 up within the 1.40→1.5 pocket.
- **Worst folds dominated by adverse-regime structural bleed →** exits can't help; the result **reinforces**
  the [[D152]]/[[D154]] structural ceiling (you can't out-exit a regime where you're paying VRP on entry) — a
  *stronger* exhaustion verdict, vindicating Path-C's parking. The real worst-quartile fix (a bear/ranging-
  *paying* complement) is sell-side = Path C.

Either way the probe is decisive, cheap, and production-grounded — no offline `enumerate`/`prefilter` demo-
registry ambiguity ([[D156]] caveat), because it reads the live ledger Crucible already attributes.

## 6. Gated sequencing

0. **(In flight) the §4 Crucible probe** — relay `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md` **SENT 2026-06-15,
   awaiting answer.** Answers both "is there headroom" and "which params bite" before any code.
1. **Operator decision** on the result: build the sweep, or accept the reinforced ceiling and re-park.
2. **(If headroom) build per the enumeration-change discipline** — TDD red-first (new `test_sampler` cases for
   the per-exit param emission; re-pin the golden/determinism sequence deliberately, §3) → extend `_exit_params`
   with audited, S5-aware ranges → emission proof (`enumerate_candidates` exit-param mix + `forge enumerate
   --summary`) → deploy ritual (`deploy.md`) → D-entry + STATUS. No version bump.
3. **Measure by funnel-compare** — the deliverable is not the deploy: the compare must report prefilter
   pass-rate AND survivor **CPCV-p25** vs the fixed-exit baseline — the explicit test of whether exit-shape
   beats the fixed-default book on the tail.

## 7. Artifacts / cross-references

- This scope: `docs/proposals/exit-tail-shaping.md` ([[D163]]).
- Gating probe: `PROMPT_CRUCIBLE_EXIT_TAIL_ATTRIBUTION.md` (**SENT 2026-06-15, awaiting answer**).
- Open question: Q42 (`OPEN_QUESTIONS.md`) — the exit-parameter generation-coverage gap (Q41's tail-shaped
  sibling).
- Entry-side siblings: `conditioning-levers.md` ([[D159]]), `momentum-cheap-iv-conditioning.md` ([[D158]]).
- The verdict this respects: `long-options-exhaustion-assessment.md` / [[D152]] (M2 vol-target = the measured
  tail lever); `path-c-scope-expansion.md` (the parked sell-side worst-quartile fix).
- The center-vs-tail distinction this builds on: [[D161]] (`rv_rank` = center knob), [[D146]] (CPCV-p25 = the
  binding worst-quartile wall).
