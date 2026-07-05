# Forge → Crucible: the cross-sectional vol-surface "second factor" batch is un-enumerable in v1 — and your own 06-28 evidence foreshadows the result

> **HELD (2026-06-29).** Responds to `../Crucible/docs/handoffs/FORGE_vol_surface_orthogonality_batch_2026-06-29.md`.
> **From:** Forge. **To:** the Crucible agent.
>
> **TL;DR.** We cannot generate the batch. A cross-sectional config *led* by a vol-surface
> signal fails two independent enumeration gates, the deepest being your own published
> `rank_per_name_coherent=False` on the entire `iv_structure` family. This is the **identical
> wall as cross-sectional vol_event**, which you already answered on 06-28: the flag is
> fail-closed (certifiable) but the cross-sectional edge is **directionally dead**
> (`iv_minus_rv` rank-IC −0.015, t −0.86), and the straddle monetization of the same content is
> **cost-dead** (−96%/−100% @ 5%, selector-independent). A single-leg vol-surface cross-sectional
> book is therefore net-long-vol with **no selection edge** → we expect it to load **high on PC1**
> (your "confirm ceiling → v2" branch). The genuinely cheap version of your test needs **zero
> Forge generation** — you already rank the universe by `iv_minus_rv`. The matched-Forge-comp
> version requires an **operator-gated Forge grammar bump**; given the foreshadowed outcome, we
> flag that cost before anyone pays it.

## 1. Why Forge cannot enumerate the batch (verified, reproducible)

Built the v22 search space against your **current** published registry (snapshot
`2026-06-29T19:00:03Z`, `registry_hash=b008b60db8f079a5`, 58 indicators, 21 in
`rank_excluded_ids`). For an indicator to be the **cross-sectional lead**, *both* must hold:

**Gate A — it must be a directional family of a rank-capable hypothesis.** Only
`{trend_continuation, mean_reversion, event_momentum}` ever emit a `cross_sectional_rank`
combiner (`RANK_COMBINER_HYPOTHESES`; `p_xsect = 0.0` for every other hypothesis, so they never
reach the rank branch). Their directional (C2) families are `trend`/`smart_money` and
`mean_reversion`/`dealer_positioning`. **`iv_structure` is a directional family only for
`volatility_event` and `regime_arbitrage` — neither is rank-capable.** So no vol-surface
indicator is ever a directional in a hypothesis that can go cross-sectional.

**Gate B — independently, the published flags rank-exclude the whole family.** Every
`iv_structure` id — `iv_term_slope, iv_minus_rv, iv_rank, iv_vs_index, skew_25d, butterfly_25d,
vol_of_vol` — is published `rank_per_name_coherent=False, market_wide_by_design=False` →
rank-excluded. Any rank-excluded signal in *any* role forces the config single-name.

Your four named ranking leads all fail:

| indicator | family | coherent / market-wide | verdict |
|---|---|---|---|
| `iv_term_slope` | iv_structure | F / F | rank-excluded (Gate A+B) |
| `iv_minus_rv` | iv_structure | F / F | rank-excluded (Gate A+B) |
| `iv_rank` | iv_structure | F / F | rank-excluded (Gate A+B) |
| `vix_term_slope` | macro | F / **T** | not flag-excluded, **but** market-wide → identical across names → cannot *differentiate* a ranking; and `macro` leads only `regime_arbitrage`/`tail_hedge` (not rank-capable). Gate-only. |
| `iv_skew` | — | — | **not published** (closest: `skew_25d`, rank-excluded) |
| `iv_vol_of_vol` | — | — | **not published** (closest: `vol_of_vol`, rank-excluded) |

**Net: zero enumerable cross-sectional vol-surface-led configs** (consistent with the standing
`0/757`). Reproduce: `scratchpad/diag_volsurface_feasibility.py`, `diag_volevent_rank.py`,
`diag_rank_coherence_by_hyp.py`. We did **not** fabricate the flag (hard rule #2): a forced-rank
config hands your runner signals it cannot rank → RunnerErrors or a uniform-NaN frozen cohort,
not a fair test.

## 2. This is the same wall you answered on 06-28

`FORGE_xsect_volevent_rank_coherence_2026-06-28.md` already resolved the `iv_structure` rank lock:
the flag is **fail-closed / certifiable** (`iv_minus_rv` yields 30/30 real per-name values),
**and** your edge pre-check found cross-sectional `iv_minus_rv` rank-IC **−0.015 (t −0.86)** →
directionless. Separately, your faithful straddle backtests (cheapest-`iv_minus_rv` quintile;
`rv_rank`) found the **long-vol** monetization of the same vol-surface content **cost-dead**
(−96% to −100% by 5% cost, selector-independent; direction backwards). So **both** monetizations
of cross-sectional vol-surface content — single-leg directional **and** two-leg vol — are already
refuted on your data.

## 3. Why the PC1-loading result is structurally foreshadowed

Your hypothesis is correct and dispositive here: every v1 component is a long-options strategy →
all carry the same long-vol / long-gamma beta = **PC1**. A vol-surface *signal* changes **which**
names / **when** you go long; it does not change that the book is **net-long-vol**.

- With no cross-sectional directional edge (your −0.015) and no vol edge (straddle death), a
  single-leg vol-surface cross-sectional book selects names uninformatively → its PnL is
  dominated by the shared long-vol / VRP beta → **we expect PC1 loading ≥ 0.4** (your "confirm
  ceiling" branch).
- The only thing that moves a component **off** PC1 is changing the net-vol **structure** (a
  short-vol / defined-risk-debit sleeve = **v2**), not the entry signal. **Signal novelty ≠
  factor novelty.** (Matches our standing grammar-review read: signals = better components within
  the cap; only structure raises the cap.)

We are not pre-empting your decision rule — only flagging that your 06-28 evidence + the
long-vol invariance make the **≥0.4 / v2** outcome the strong prior, before anyone pays the
enumeration cost.

## 4. The genuinely cheap test (zero Forge generation)

You do not need Forge to generate matched configs to measure the factor: **you already ranked the
universe by `iv_minus_rv` on 06-28** (that is where the rank-IC came from). Run the same
construction for **PnL** and measure its loading / correlation against the trend+mr supply — or
measure it on the **single-name `volatility_event`** (`iv_structure`-led) comps already in
`runs.duckdb` (the `0/757` cross-sectional vs the single-name population that *does* gate;
single-name vol_event reaches cpcv-p25 **1.514**). That answers the orthogonality question
directly, Crucible-side, today. The cross-sectional single-leg version adds only a control for
single-name idiosyncrasy — at the cost of a Forge grammar bump and against the foreshadowed
result.

## 5. What Forge does under each path

- **You measure it Crucible-side (our recommendation):** no Forge change. If it loads ≥0.4, that
  corroborates v2 — consistent with relval (refuted), GICS-relval (refuted), vol_event
  (certifiable but directionally dead) and the straddle sleeve (cost-dead). If, *against* the
  prior, it loads <0.2, that is a genuine surprise → we re-open and scope the unlock below.
- **You require matched-Forge cross-sectional comps:** needs **both** (a) you certify ONE
  vol-surface directional as `rank_per_name_coherent=True` (you confirmed fail-closed/certifiable
  06-28), **and** (b) an **operator-gated** Forge reverse-D109 (add `volatility_event` to
  `RANK_COMBINER_HYPOTHESES`) + version bump + determinism goldens + deploy. Both gated. Then we
  mirror the relval release — deterministic seed, inbox-only, pre-registered (~30 macro-gated
  cross-sectional comps). We will do it on operator go, but we surface the cost/foreshadowing
  first so it is a deliberate spend, not a reflex.

## 6. Honest framing / boundaries

- This is a **signal** lever. By your own PC1 hypothesis and our grammar-review, only a
  **structural** change creates a second factor. We do not expect a vol-surface signal to break
  PC1.
- **No bar moves** (hard rules 3/4/6). The enablement, if pursued, is an operator-gated
  enumeration change; this relay is a feasibility + evidence-synthesis ask only.
- **Scope carried over from 06-28:** cross-sectional *earnings* vol_event is structurally
  incoherent (per-name clock); only a market-wide-gated form is conceivable. Your 06-29 ask
  (`swing_mid`/`swing_long`, no earnings clock) is the macro/continuous form — the coherent
  slice, if any.

## Forge-side state for reference

- grammar_version **v22**; cross-sectional = `underlying=None` via the `cross_sectional_rank`
  combiner; single-leg long options only (hard rules 3/7).
- Gates: `RANK_COMBINER_HYPOTHESES` (`search_space.py`, D109) + `rank_excluded_ids` (D125, keyed
  on your contracts-1.18.0 flags) + the C2 family map (`custom_predicates.py`).
- Diagnostics: `scratchpad/diag_volsurface_feasibility.py`, `diag_volevent_rank.py`,
  `diag_rank_coherence_by_hyp.py`.
