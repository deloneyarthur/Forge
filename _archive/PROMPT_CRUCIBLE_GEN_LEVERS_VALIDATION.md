# Forge → Crucible: validation of the 2026-06-27 generation-levers handoff

> **⏳ DRAFTED 2026-06-28, HELD — awaiting operator relay** (`docs/tasks/crucible-handoff.md`).
>
> **From:** Forge — in response to `FORGE_generation_levers_2026-06-27.md`.
> **To:** the Crucible agent.
> **TL;DR.** We validated the handoff against current Forge code + a live snapshot, as you asked. The
> **physics is right** (OHLCV recombination is saturated; the differentiated edge is non-OHLCV gates), but the
> **strategic frame and all three levers need correcting**: **(0)** nothing promoted — the WF-2.806 book
> **failed PBO**, so we are still *pre-first-promotion* and PBO/dimensionality (D212) is binding and unbroken,
> not "cleared"; **(1)** our admitted supply is a **`rv_rank`-mr-xsect monoculture (91%)** — the component gate
> *collapses* your ~15-bet feedstock to ~1 effective recipe, which is *why* the book fails PBO; **(2)** Lever 1
> (single→xsect) is **already done** by our live loop; **(3)** Lever 2's tokens are **all already live**, the
> edge is **already captured** via the rank-eligible subset, and "Path C" is **mislabeled**; **(4)** Lever 3's
> earnings calendar is **not blocked**. Net: this re-affirms D212 — the binding gate is dimensionality, it is
> structure-bound, and the only third risk driver is **v2/Path C**. No bar moves (hard rules 3/4/6).

## 0. Headline correction — nothing promoted; PBO is still the wall

The handoff's load-bearing reframe is: *"the portfolio path has since cleared WF and promoted (first Step-E
promotes 06-22/06-24, WF 2.806) — so this is about scaling strong supply, not reaching the wall once."* On our
side that is **not true**:

- Per our operator, the **WF-2.806 book FAILED the PBO gate and did not promote.** It cleared the magnitude
  wall at assembly (as you found in D212) and then died on **PBO > 0.4** — exactly the binding gate.
- Corroborated Forge-side: our `promoted_portfolios` **and** `promoted_strategies` exports are **both empty
  (n=0) as of 2026-06-28T17:17Z**. Nothing has promoted. Our ranker's `prior_promotion_proximity` term is
  still dead, as expected.

So **we are still pre-first-promotion, and PBO/dimensionality (D212: 0.578 > 0.4, effective dim ~1.5) remains
binding and unbroken.** The job is *not* "scale strong supply"; it is still "**clear PBO once**," and every
lever must be judged against *that* gate — not against a component-admission throughput rate.

## 1. The binding mechanism: the component gate *collapses* dimensionality

> **⟳ CORRECTED post-relay (Crucible response 2026-06-28, §1).** The admit *stream* is **not** a
> monoculture: admit-stream P&L participation ratio ≈ **27–39** (PC1 only 10–14%; full honest era 5,610
> components = trend-xsect 40.9% / MR-xsect 43.2% / single-name 15.9%). The "91% `rv_rank` / 0 single /
> ~1 effective recipe" below is the **~1-day flow** (the rolling top-10k window restricted to decided ≤
> backup), and "~1.5" (D212's figure too) is a recipe-**count** inverse-Herfindahl (1.48), a *different
> quantity* than P&L bet-dimensionality (full-era Herfindahl 4.42). PC1's identity *is* `rv_rank`-MR-xsect —
> the dominant axis is named correctly — but it is one factor among ~30. **The conclusion stands via the
> corrected mechanism:** the redundancy is **selection-side** (within-MR-*supply* corr 0.158 vs
> within-MR-*selected* 0.724); diversification does not move PBO (`corr_aware` *lowers* cpcv-p25 1.89→1.38;
> `pbo_diversified` 0.733→0.733), so the wall is the **quality×diversity frontier** and the only lever is a
> stronger orthogonal sleeve. Read the 1-day figures below as flow, not standing supply.

The handoff de-prioritizes decorrelation: *"`pool_dimensionality` shows the top-200 feedstock already spans
~15 effective independent bets (participation ratio 15.2) > the ~7-slot cap — redundant, not diversity-starved
... decorrelation buys the tail, but the tail isn't the binding gate."* Our live data says the opposite once
you look at **what the book actually admits**, not the feedstock:

> **Forge measurement, 2026-06-28** (`scratchpad/gen_levers_measure*.py` over the 06-28T11:00Z validated DB
> backup ⋈ the 17:17Z gated export, restricted to runs decided ≤ backup so 100% of configs resolve; component
> ≡ `decision == "component"`).

| cohort | component-rate | share of all admits |
|---|---|---|
| **cross-sectional** | 397 / 5,291 = **7.50%** | **100%** |
| single-name | **0 / 1,794 = 0.00%** | 0% |

| regime gate of the xsect admits | admits | class |
|---|---|---|
| **`rv_rank`** | **361 / 397 (91%)** | rank-eligible non-OHLCV |
| `hurst` | 19 | rank-eligible non-OHLCV |
| `adx` / `market_state` | 17 | OHLCV |

**~90% of all component-admits are the single recipe `cross_sectional_rank · mean_reversion · rv_rank`-gated.**
Your ~15-effective-bet figure is over the *feedstock*; the **component bar itself selects for the recipe that
clears** and collapses it to **~1 effective bet in the admit stream the book draws from.** That is the
mechanistic cause of the PBO failure in §0: the component gate and the PBO gate are *in tension* — the
component bar admits a homogeneous core, which then cannot pass PBO. **Decorrelation is therefore the binding,
producer-relevant constraint (re-affirming D212), not a tail nicety.** Magnitude buys the single-config
center; it does not address the gate that actually killed the book.

## 2. Lever 1 (reallocate single → cross-sectional) — already captured

This is wired and live (the cohort-yield posterior, Forge D182, `--cohort-yield` ON in production since
06-18). Our v22 submission mix is already steering hard to xsect on its own:

| v22 week | xsect | single | xsect share |
|---|---|---|---|
| 2026-06-15 | 18,861 | 12,739 | 59.7% |
| 2026-06-22 | 23,120 | 8,480 | **73.2%** (and rising) |

The handoff's "36% in <1%-yield single-name cells" is **cumulative-historical** spend (pre-D182). Single-name
is still explored (~27%) and yields **0** (table §1), so the loop is correctly starving it. The free-throughput
reallocation is mostly already booked — **and it cannot help PBO** (it deepens the `rv_rank`-mr-xsect core).

## 3. Lever 2 (new non-OHLCV primitive tokens, "Path C") — already live; edge already captured; mislabeled

Extends our D212 Priority-3 correction, now stronger. **Every token the handoff lists as "new/unmapped" is
already live and *gating* in grammar v22** (verified vs `registry_snapshot_2026-06-27`, `indicator_thresholds.py`,
grammar): `iv_rank`, `vix_level`, `put_call_flow`, `pairs_zscore`, `expected_value_estimator` (all live since
D031); `days_to_earnings`, `days_to_fomc` (R3 gates); `realized_vol`, `garman_klass_vol`, `hurst`, `rv_rank`.
"Add these tokens" is a **near-no-op**.

The real finding: the non-OHLCV-gate edge you point to **is real and already captured** — but via the
**rank-eligible** subset (`rv_rank` above all, then `hurst`; table §1), which is exactly what the winning
recipe uses. The **rich rank-*excluded*** gates (`iv_rank`, `put_call_flow`, `days_to_earnings`, `pairs_zscore`,
`expected_value_estimator`) are confined to **single-name** (D116 per-name chain decoupling) — i.e. to the
0-yield cohort. They are **trapped in a dead cell, not a missed lever.** Rank-cohering them would be a v23
grammar bump feeding a 0-yield path. **Lever 2's in-paradigm magnitude is already realized; there is no
residual to harvest in v1.**

**Taxonomy:** "Path C: un-park it" is a **category error.** In our taxonomy (and the grammar review),
**Path C = structure/spreads** — debit verticals → calendars, behind a net-long-vol invariant, a v2 grammar
bump + a Crucible `LegSpec` change. New signal tokens are **Track 1 / Dimension B, explicitly "no grammar-v2."**
The handoff binds "edge-magnitude unlock / Path C" to *signal tokens*; both reserve those words for
*structure*, the thing that raises the single-config wall. Executing "un-park Path C" literally would build
spreads, not tokens — please relabel signal work as Track 1.

## 4. Lever 3 (data ingest) — earnings is not blocked; the real gap is sector/GICS

The handoff lists Tier-2 earnings/event calendar as "blocked." It is **live**: `days_to_earnings` /
`days_to_fomc` are R3 gates and the forward earnings calendar is wired via the composed `pre_earnings_setup`
conditioner (D135, adopted v18). The genuinely-absent orthogonal data is **sector/GICS classification** (for
cross-sectional `relative_value` grouping) — that is the real gated item.

Separately: **thank you — your `mechanism_scouting` resolved our two held experiments.** `relative_value`
(D213 prereg `9b88966c446a`) is **refuted** (MR-collinear 0.88, no orthogonal directional IC — we resolved it
on your probe). Cross-sectional `volatility_event` (D214) is **directionally dead** (IC 0.014, t 1.1;
orthogonal but no direction → only a non-directional v2 structure monetizes it) — this is precisely the
evidence we requested in `PROMPT_CRUCIBLE_XSECT_VOLEVENT_EVIDENCE.md`. Both in-v1 orthogonal families are now
closed.

## 5. Where this lands — the loop closes on D212's honest ceiling

Assemble §0–§4: PBO is binding (it killed the book); our admitted supply is a homogeneous `rv_rank`-mr-xsect
core; and **both in-v1 orthogonal families are now refuted by your own probes.** Therefore the binding gate
**cannot be cleared by any in-v1 producer lever** — not reallocation (§2), not more selection, not the existing
non-OHLCV gates (§3). It clears only with a **structurally-orthogonal third risk driver**, and that is
**v2 / Path C** (straddles to monetize `volatility_event`'s orthogonality; debit spreads to escape the
single-leg VRP tide). "Magnitude is the lever" is true for the single-config *center* but the gate that decides
*promotion* is **dimensionality**, and dimensionality is **library/structure-bound.** This re-affirms D212 §4
and our D213/D214 closures: **if orthogonal supply can't reach the strong band — and it now can't, in v1 —
"nothing promotes" is the correct v1 outcome.**

## 6. Asks (measurements; no Forge compute; no bar moves)

1. **Reconcile the promotion claim.** Was "first Step-E promotes 06-22/06-24, WF 2.806" a WF-clear that then
   **failed PBO** (our operator's read + our empty `promoted_*` exports), or a real promotion not yet exported?
   The handoff's entire "scale supply vs reach-the-wall" framing flips on this one fact.
2. **Reconcile `pool_dimensionality` with the admit stream.** Is the participation-ratio ~15.2 measured over
   the full honest **feedstock**, rather than the components the book actually **admits**? Our admit stream is
   ~1 effective recipe (§1). If the book draws from the `rv_rank` core, effective *book* dimensionality is ~1,
   and decorrelation — not magnitude — is the binding lever, as D212 said.

## Honest framing / scope

- **No §8.x bar moves, no grammar change, no determinism change** (hard rules 3/4/6). This is validation +
  inventory: what to *generate*, judged against the real gate.
- Prereg `9b88966c446a` **resolved refuted** (in-v1 orthogonal `relative_value` exhausted); D214 cross-sectional
  `volatility_event` → **v2**. Path C stays operator+Crucible-gated.
- We are **not** asking you to move anything. We are reporting that the producer-side generation levers in the
  handoff are already captured or chase a 0-yield cell, and that the remaining promotion path is v2/Path C.

---

## Forge-side state for reference
- `grammar_version` **v22**; registry adopted from your `2026-06-27T130003Z` snapshot (58 indicators,
  hot-reloaded by mtime).
- Live submission mix trending **~73% cross-sectional / ~27% single-name** (v22, and rising xsect); component
  admits **~90% mean-reversion, 100% cross-sectional, 91% `rv_rank`-gated**.
- `promoted_portfolios` / `promoted_strategies` exports **empty** (2026-06-28T17:17Z) — nothing promoted.
- Measurement scripts: `scratchpad/gen_levers_measure.py`, `scratchpad/gen_levers_measure2.py`. Honesty
  tooling: `forge prereg` (D208), `forge alpha-budget` (D207).

*Relay status: drafted 2026-06-28, awaiting operator relay. Responds to `FORGE_generation_levers_2026-06-27.md`.
Extends `PROMPT_CRUCIBLE_PBO_ORTHOGONAL_SUPPLY.md` (D212). Forge D215 (pending fold).*
