# Strike-Forecasting Research — Decision-Grade Synthesis

**Question under study (operator hypothesis):** *"Long options are ~90% directional, so Forge needs a forecasting system that predicts the strike price the underlying will REACH within the strategy's time window, well before expiration."*

**Audience:** Forge operator (quant). **Author:** consolidating analyst, synthesizing 11 specialist threads against `docs/DESIGN.md`, `STATUS.md`, `CLAUDE.md`. **Date:** 2026-06-28.

Confidence tags throughout: **[H]** robustly established (multiple independent high-quality sources agree), **[M]** moderately supported, **[L]** fragile / single-source / contested.

---

## 1. Executive verdict & recommendation

**Verdict on the premise:** Half-true, and true in the half that does not help. A held-to-expiry long single-leg option's *terminal* payoff is ~100% a deterministic function of where the underlying ends relative to the strike — so "directional" is trivially correct as a terminal statement. But that is exactly the framing in which the market has already priced the risk-neutral distribution of the terminal price into the premium (delta = N(d₁); N(d₂) = risk-neutral P(ITM)). You profit only if your **real-world** terminal distribution beats the **risk-neutral** one by more than the variance risk premium (VRP). On a *daily / path* basis the same option is closer to 50/50 directional-vs-(vega+theta) for the moderate-OTM, 14–45 DTE contracts Forge actually enumerates. So the premise is simultaneously true (direction sets terminal payoff) and misleading (direction is already priced, and the marginal real-world directional edge available is tiny). **[H]**

**Verdict on building a horizon strike-forecaster:** **Do not build it.** Four independent walls, any one of which is disqualifying:

1. **Predictability ceiling.** The best documented out-of-sample equity return prediction is cross-sectional, monthly, R²ₒₒₛ ≈ **0.33–0.40%** (IC ≈ 0.06) after 60 years of data and 900+ features (Gu-Kelly-Xiu 2020). Index-level (time-series) direction is *worse* — most predictors have **negative** OOS R² (Goyal-Welch). Daily/weekly direction sits at **51–53%** hit rate. Predicting a *price level* ("reach strike K") is strictly harder than predicting sign. Merton (1980): drift cannot be consistently estimated over a bounded interval — you'd need ~600 years to pin the equity mean to ±1%/yr. The 5–20-day option window is the *worst* horizon: too short for predictor persistence, too long for microstructure. **[H]**
2. **VRP headwind.** Long options structurally pay the VRP: IV exceeds subsequent RV ~**73–85%** of rolling windows, by ~**2–4 vol points** on SPX (less, and more idiosyncratic, on single names — Carr-Wu 2009). Zero-beta ATM straddles lose ~**3%/week** (Coval-Shumway 2001). A 52–55% directional model covers only **one-fifth to one-half** of a typical 40-delta/45-DTE premium's breakeven hurdle. Direction is *necessary but provably not sufficient.* **[H]**
3. **PBO — the actual binding gate.** Forge's promotion constraint is **PBO 0.578 > 0.4** at effective dimensionality ~1.5 (D212), *not* per-config edge magnitude (that wall is cleared at assembly: books WF-med 2.88). A new learned strike-forecaster adds model parameters / search dimensionality, which **raises PBO** — it pushes the binding metric the wrong way. **[H]**
4. **Wrong target for the gate.** A directional forecaster improves *within-family* candidate ranking. The stream is already ~85% mean_reversion; mr is half the 0.78-correlated directional core PBO punishes. Better-ranked-but-correlated supply adds **zero dimensionality**. The lever that moves the gate is **orthogonal family supply**, which two in-flight experiments already target (relval D213, cross-sectional vol_event D214). **[H, grounded in STATUS]**

**What the operator is actually sensing — and where to aim instead.** The intuition that "long options need a forecast" is right; the *object* of the forecast is wrong. What is forecastable at the option's horizon, in descending reliability: **volatility** (HAR-RV R² 0.40–0.65), **scheduled-event structure** (PEAD / pre-earnings IV expansion), **cross-sectional rank** (IC ≈ 0.06), and **touch-probability** (closed-form, but mostly already priced into delta). Most of these Forge already exploits — `iv_rank`/`rv_rank` (cheap-vol entry), the F3 + wf_p25 learned ranker (cross-sectional rank), the `volatility_event` hypothesis with `days_to_earnings`/`days_to_fomc` gates (events). The "system" the operator wants largely *exists* as the ranker; a new directional-level module is not the missing piece.

**Recommendation (one line):** **Do not build a strike/price-target forecaster.** If a falsifiable test is wanted, run the *minimal, parsimony-preserving* version: add **one** deterministic directional-conditioning feature (historical breakeven-hit-rate per `(signal-family, DTE-bucket, delta-band)`) into the existing §6.2 verdict_scorer slot — the same A/B-gated, byte-identical-revert slot the wf_p25 lane (D193) uses — pre-registered via `forge prereg` (D208), charged to `forge alpha-budget` (D207), evaluated under CPCV with purge ≥ max(DTE) and a DSR/Harvey t ≥ 3 bar. **But sequence it AFTER** the relval (D213) and vol_event (D214) experiments resolve, because those target the binding PBO gate and this does not. Prior on it clearing the bar: **low.** Full protocol in §10.

---

## 2. The premise audited — is long-options P&L ~90% directional, and when

**The clean decomposition.** Daily long-option P&L is the Greek Taylor expansion:

```
ΔC ≈ Δ·ΔS  +  ½·Γ·(ΔS)²  +  ν·Δσ  +  Θ·Δt
     └── directional ──┘     └ vega ┘   └ decay ┘
```

Θ·Δt is always a drag for long options; ν·Δσ helps only if IV rises. Direction (Δ·ΔS + ½Γ(ΔS)²) dominates **only on large-move days, deep-ITM (δ≥0.8), or short DTE (≤7d) where vega has collapsed**. **[H]**

**Reconciling the two threads that appear to disagree.** The *premise* thread says moderate-OTM, 14–45 DTE options are "closer to 50/50 directional vs vol/time"; the *forge-fit* thread calls long single-leg "~85–90% sensitive to where the underlying ends up." These are not in conflict — they measure different things:

- **Terminal (held-to-expiry) sensitivity:** ~100% directional. At expiry, vega→0, theta is spent, and payoff = max(S_T − K, 0). The forge-fit "85–90%" is essentially this statement and it is correct.
- **Daily / path attribution:** ~50/50 for Forge's typical contracts under normal RV. The premise thread's number is correct for this.

**The adjudication that matters:** the premise is *true and unhelpful.* Yes, terminal P&L is set by direction — but the market prices the **risk-neutral** terminal distribution into the premium, so the directional bet is already paid for. Delta is the market's risk-neutral reach probability; N(d₂) is its risk-neutral P(ITM). To make money you must beat that priced distribution in the **real world** by enough to clear the VRP. The operator's inference — "it's directional, therefore a directional forecast is the binding lever" — is the error. The binding question is not "which way?" but "is my real-world distribution displaced from the priced one by more than the premium?" **[H]**

**The structural headwind, quantified (carry these numbers):** **[H]**
- IV > RV ~73–85% of rolling 30-day SPX windows; mean gap ~2–4 vol pts (premise, classical-ts, iv-vs-rv threads); practitioner compilation: VIX 19.3% vs RV 15.1%, 1990–2018, ≈4.2 pp (practitioner thread).
- Zero-beta ATM straddle: **−3.15%/week** (Coval-Shumway 2001).
- Index call returns ≈ **−30%/mo ATM, −60%/mo at 6% OTM** beta-adjusted (Broadie-Chernov-Johannes 2009); ATM puts ≈ **−39%/mo**, deep-OTM puts ≈ **−95%/mo** (Bondarenko 2014).
- **Forge-relevant nuance:** index VRP > single-name VRP because index options carry a *correlation-risk* premium individual names lack (Carr-Wu 2009). Forge is single-name scope → a **structurally smaller** headwind than the SPX figures imply. This is the one place the premise gets *easier* for Forge. **[M]**

**The single most important conditional finding:** entry-vol timing rivals or exceeds directional sorting for long-option returns. Goyal-Saretto (2009): sorting on RV > IV (cheap implied vol, **zero directional content**) returns **+2.87%/mo (t = 24.5)**. Implication: if Forge had to optimize one dimension, *cheap-vol entry* may beat *better direction* — and Forge already encodes it via `iv_rank` (R1) and `rv_rank`. **[H]**

---

## 3. The predictability ceiling — how good can any forecaster get (SNR reality)

This is the section that should end the debate. The evidence is convergent across four independent threads (ceiling, ml-dl, classical-ts, practitioner). **[H]**

| Target | Best documented OOS performance | Source |
|---|---|---|
| Cross-sectional monthly return (ML, 30k stocks, 900+ feats) | R²ₒₒₛ **0.33–0.40%**, IC ≈ 0.06, VW Sharpe 1.35 / EW ~2.1–2.5 | Gu-Kelly-Xiu 2020 |
| Index equity premium (time-series) | **Negative** OOS R² for most predictors (−1.78% to −0.05%); historical mean wins | Goyal-Welch 2008; Goyal-Welch-Zafirov 2024 |
| Index premium with sign/positivity constraints | +0.5–2% OOS R² (monthly) | Campbell-Thompson 2008 |
| Daily single-stock direction | **51–53%** hit rate | Hannover WP; ml-dl thread |
| Realized **volatility** (HAR-RV, monthly) | R² **0.40–0.65**; HAR beats GARCH MSE by 31–40% | Corsi 2009; path-dependent HAR 2025 |
| Drift over a 20-day window | Std error ≈ σ/√T → **statistically indistinguishable from noise**; ~600 yrs to pin the mean | Merton 1980 |

**Three corroborating facts that cap the ceiling further:**
- **Post-publication decay:** 97 published predictors lose **26% OOS** and **58% post-publication** (McLean-Pontiff 2016). Any signal worth training on is likely already in the literature and partly arbitraged.
- **Deep learning does not raise the ceiling.** Simple linear models (NLinear/DLinear) beat all Transformers on 9/9 benchmarks (Zeng 2023); zero-shot time-series foundation models score **negative R² vs a random walk** on daily returns (TimesFM −2.80%, Chronos −1.37% vs CatBoost −0.10%); apparent foundation-model wins come from the *factor inputs*, not the architecture. Vanilla LSTM > Transformer on financial RMSE. **[H]**
- **Horizon scaling is adverse.** Predictability concentrates at monthly-to-annual horizons (driven by persistent macro predictors); the option's 5–20-day window is the dead zone. **[H]**

**The IC→IR mirage, defused.** Grinold-Kahn IR ≈ IC·√Breadth makes IC 0.06 look like IR ≈ 2.9 at 200 stocks × 12 months. This is irrelevant to Forge: (a) it assumes mean-variance equity positions, not VRP-paying asymmetric option payoffs; (b) options-book breadth ≪ a long-short equity fund's; (c) a naive IC of 0.05 inflates to an *apparent* 0.15–0.30 under label leakage from overlapping windows (evaluation thread). The honest, leakage-corrected, VRP-net edge available to a horizon directional forecaster is **near zero**. **[H]**

---

## 4. What IS forecastable vs what is not

**NOT forecastable at the option's horizon (abandon):** the *level* the underlying will reach; the *sign* of the return at daily-to-weekly horizons beyond ~51–53%; the index's direction (negative OOS R²); the event-move magnitude (see below). **[H]**

**Forecastable, in descending reliability and Forge-usefulness:**

1. **Volatility (most reliable).** HAR-RV / EGARCH / HAR-IV deliver R² 0.40–0.65 over multi-day-to-monthly windows; vol-state classification hits ~67.5% vs ~50% for price direction. **But the actionable transform is "is IV cheap vs forecast RV?"** — a long option profits via the gamma term ½Γ(RV²−IV²) when RV > IV, *regardless of direction*. Forge already proxies this with `iv_rank`/`rv_rank`. A vol forecast tells you when entry is *less bad*, not generically positive (IV>RV is still the modal outcome). **[H]**

2. **Scheduled events / PEAD (reliable but phase-dependent).** Three empirically distinct phases (event-driven thread): **[H/M]**
   - *Phase 1 — pre-event IV expansion:* buy straddle T-3→T-7, **exit before the announcement** → +3.34% per window (Gao-Xing-Zhang 2018). A vol play, not a direction play.
   - *Phase 2 — the event move itself:* **unfavorable.** ~70–75% of stocks move *less* than the implied move; long straddle into earnings loses ~54.7% of the time; avg IV crush 38.2% overnight. *This is precisely the operator's "reach the strike at the event" target, and it is the losing phase.*
   - *Phase 3 — post-crush directional drift (PEAD):* buy directional option *after* the event when IV has crushed and SUE direction is known → captures ~2%/60d drift (Bernard-Thomas) at the cheapest premium. **Caveat:** PEAD has decayed to ~0 factor-adjusted in large-caps post-2010; survives mainly in costly-to-arbitrage small/illiquid names.
   - Forge maps these to `volatility_event` + `days_to_earnings`/`days_to_fomc`. The gap (per iv-vs-rv & event threads): a scalar `days_to_*` does **not** distinguish phase 1 (pre-event, vol-crush risk) from phase 3 (post-crush, drift). Distinguishing them is the real event lever — and it folds into the already-scoped vol_event work (D214), not a new forecaster.

3. **Cross-sectional ranking (this is what ML is for).** IC ≈ 0.06 used to *rank candidates*, not to predict levels. This is **Forge's existing ranker paradigm** (F3 P(component) + wf_p25 lane). The literature's verdict: translate small IC into selection-in-the-tails, never into a price target. **[H]**

4. **VRP width / term structure as a regime signal.** VRP (IV²−RV²) predicts *aggregate* returns R² ≈ 7% at 1mo, 14–18% at 3–6mo (Bollerslev-Tauchen-Zhou 2009). VIX term slope is a regime *exclusion* filter (avoid initiating longs in deep backwardation — maximally expensive insurance), not a direction signal. Note `vix_term_slope` was deliberately rejected for Forge (D131); term-structure gates belong with Path-C calendars (v2). **[M]**

5. **Touch-probability (right reframing of the operator's intuition, little new signal).** See §6.

---

## 5. Methodology landscape

**Classical time-series.** GARCH(1,1)/EGARCH for daily vol (1-day horizon only; converges to unconditional mean beyond ~1 week); **HAR-RV** (Corsi 2009) is the default for multi-day RV and the hard baseline to beat (needs intraday data); ARFIMA belongs on *log-vol* (d≈0.4), never on log-price (d≈1 → trend extrapolation that fails). Markov regime-switching (Hamilton 1989) identifies regimes *ex post* but forecasts the *next* regime poorly. **Merton (1980) is the keystone negative result:** drift SE = σ/√T independent of sampling frequency → directional forecasting over 20 days is noise. **[H]**

**ML / DL.** Gradient boosting (XGB/LightGBM/CatBoost) is the gold standard for tabular cross-sectional ranking and is fully deterministic with a fixed seed (Forge-compatible). Deep sequence models (LSTM/TFT/PatchTST) show **no reliable advantage** for return direction and are beaten by one-layer linear models; their wins are in vol/regime, not barrier-crossing. Learning-to-rank (LambdaMART) needs a >500-name cross-section — *incompatible with single-underlying options* where the "cross-section" is strikes/expiries. **[H]**

**First-passage / barrier math.** The rigorous version of "reach the strike." For GBM with log-drift ν = μ − σ²/2, barrier b = ln(H/S₀):

```
P_touch = Φ((νT − b)/(σ√T)) + e^(2νb/σ²)·Φ((−νT − b)/(σ√T))
```

At ν = 0 this collapses (reflection principle) to **P_touch = 2·Φ(−b/(σ√T)) = 2·N(d₂)** — exactly twice the terminal ITM probability. Bullish ν pushes the touch/terminal ratio *below* 2; bearish *above* 2. Stochastic vol (Heston, ρ<0) inflates *down*-barrier touches 10–25%; jumps inflate both. **[H]** Key consequence for Forge in §6.

**IV/RV & term structure.** IV is the single best RV forecast (subsumes history; Christensen-Prabhala 1998) **and** the breakeven hurdle (the VRP). HAR-IV beats HAR and GARCH at monthly horizons. `iv_rank` low ⇒ lower premium + vega tailwind from mean-reversion; `iv_rank` high ⇒ structural trap for buyers. Vasquez (2017): IV-term-structure slope sorts cross-sectional straddle returns (+29%/mo long-short, in-sample). VRP may have thinned post-2010 (Lochstoer et al. 2025, working paper [M]) — modern headwind smaller than historical. **[H except where tagged]**

**Event-driven / PEAD.** SUE and analyst-revision drift give directional ranking (top-decile SUE ~4.31%/60d) but near-zero factor-adjusted alpha in large-caps post-2010; NLP-augmented PEAD roughly doubles Sharpe [M]. Daniel-Moskowitz (2016) momentum-crash conditioning (momentum is call-like in bear markets) ≈ doubles momentum Sharpe — but "bear + high-vol" is also when options are most expensive, compounding the long-option cost. Pre-FOMC drift (Lucca-Moench) is **largely arbitraged away** post-2016 (44bps → 9bps). **[H]**

---

## 6. From forecast to trade — touch-probability, strike & DTE selection, sizing

**Touch-probability is the correct, rigorous reframing of "reach the strike" — and it shows why the idea adds little new signal.** The closed form needs (μ̂, σ̂). At the unforecastable drift (ν=0), P_touch = 2·N(d₂), a deterministic function of delta + vol that Forge **already encodes** via P3 delta bands and registry IV. Any *added* value requires a real μ̂ — the very quantity §3 says is near-unforecastable. Worse, P_touch optimizes the wrong objective: it rewards *early-exit management*, but **Crucible scores terminal walk-forward P&L**, not touches; and touching the strike ≠ profiting (you paid the premium). **Net:** the math is a clean conceptual bridge but not a new edge. Its one defensible use is as a *cheap, deterministic, PBO-neutral* prefilter feature — replacing coarse OTM-distance with P_touch(δ, σ, DTE) that integrates DTE and vol correctly — a minor refinement, **not** a priority. **[H]**

**Strike selection requires a distribution, not a point.** EV-optimal strike maximizes ∫_K^∞ (S_T−K)·f_forecast(S_T)dS_T − C_market(K,τ). Profit needs the *forecast* P(S_T>K) to exceed the *risk-neutral* N(d₂) by enough to clear the VRP — typically a **10–25 pp** wedge. Use **N(d₂), not delta**, for EV (the gap reaches ~9 delta-points at 90 DTE / 30% IV). Faias-Santa-Clara (2017): distribution-aware strike selection achieves OOS Sharpe 0.82 — confirming the operand is a *distribution shift*, not a price target. **[H]**

**DTE matching.** Theta ∝ 1/√τ (doubles as DTE halves); ~50% of extrinsic value decays in the last 30 days. Rule: DTE ≈ 1.5–2× the signal's alpha half-life, and for events buy DTE *beyond* the event date. The seller-optimal 30–45 DTE is the *worst* buyer entry. Forge's P2 buckets (swing_short 14–21, mid 30–45, long 60–90) are reasonable but the mid bucket sits in the theta-acceleration zone. **[M]**

**Sizing.** Full Kelly is wrong for options (binary formula ignores continuous payoff; p-error of 0.05 flips the sign). Fractional (¼–½) Kelly → typically <5%/position, often <1% for long premium. *This is QuantIQ's job, not Forge's* (§1.2). **[M]**

**The architectural trap.** EV-optimal selection tempts *joint* optimization over (signal × K × τ). That is precisely the within-sample tuning that inflates PBO. Forge's grammar deliberately *pre-fixes* delta and DTE bands (P2/P3) and lets the ranker pick *which signals* to submit — the PBO-safe design. Do not move strike/DTE selection from grammar-fixed to forecast-derived. **[H]**

---

## 7. Practitioner reality — what systematic options/vol money actually does

The professional consensus directly contradicts the hypothesis's framing. **No systematic desk forecasts a price level.** **[H]**

- **CTAs / trend-followers** predict the *sign* over 1–12 months, never a level, and derive **~two-thirds of realized Sharpe from volatility-scaled position sizing**, not the signal (TS-momentum alpha drops 1.27%→0.41%/mo without vol-scaling; Moskowitz-Ooi-Pedersen 2012). The signal is direction; the edge is *packaging*.
- **Long-vol / tail funds** (Universa, LongTail Alpha) **explicitly disclaim directional forecasting** — they harvest convexity, sized as insurance, absorbing the bleed at portfolio level (Spitznagel: the hedge is optimal "no matter our ability to predict a crash").
- **Vol relative-value desks** are "agnostic on the direction of the underlying"; their edge is *relative value across the surface*, treating direction as already priced.

**Translation to Forge:** the genuine, persistent edge sources the literature names — direction *sign* (Forge's signal grammar), regime conditioning / cheap-vs-expensive IV (`iv_rank`/`rv_rank`/regime gates), and diversification-through-variety (grammar diversity feeding Crucible assembly), plus survival-filtering "packaging" (the wf_p25 quality lane = the CTA's vol-scaling analogue) — are **exactly what Forge already builds.** A horizon price-forecast is the thing these desks rejected. **[H]**

---

## 8. Forge fit — generation-lever vs paradigm-shift; determinism / no-LLM; the PBO/VRP tension

**As a grammar parameter → REFUTED (paradigm shift, hurts the binding gate).** The literal hypothesis — a `predicted_target_pct` field on `StrategyConfig` — would (a) require an operator-gated grammar bump (hard rule #10), (b) **multiply Crucible's effective search N** (each quantile = a new backtest dimension) → directly worsens PBO 0.578, (c) be *stale at backtest time* (a prediction for today's underlying applied to historical bars is meaningless). The grammar already proxies the strike via the time-invariant delta band (P3). **[H, grounded in §3.5 + D212]**

**As a ranker feature → in-scope but low-priority.** The only rule-compliant home is the §6.2 verdict_scorer slot — the same deterministic, non-LLM, A/B-kill-switched, byte-identical-revert slot the wf_p25 lane uses (D193). A directional-conditioning *feature* added to the F3 model:
- satisfies **rule #5** (deterministic ML, not an LLM — explicitly permitted; the ranker is already one) and **rule #6/#8** (uses pinned historical features + seeded training);
- does **not** add to Crucible's PBO (the submitted configs still span the same grammar space) — it adds only to *Forge's own* selection breadth, which `forge alpha-budget` (D207) is built to track;
- **but** it improves only *within-family* ranking. Per D212 the binding gate is *portfolio dimensionality*, which a within-family directional feature leaves unchanged. The stream is ~85% mr; better-ranked correlated mr supply adds no dimensionality. **It does not move the gate.** **[H, grounded in STATUS D212–D214]**

**The honest reframing of the gap.** The right question is not "can we forecast direction well enough to make a long option profitable in isolation?" (no — VRP + ceiling) but "can we identify *when/where* the directional edge is large enough to clear the VRP?" — which is what the existing regime gates (R1 iv_rank, R2 adx/hurst, R3 event-proximity) and the cheap-vol signals already do *structurally*. The marginal value of an ML directional layer is whatever it adds *above* F3's current regime-conditioned prior — an empirical quantity that must be *measured*, and whose prior is low. **[H]**

**Determinism / no-LLM:** no obstacle. Gradient boosting and ridge/logistic are deterministic under fixed seeds and already in the loop. The constraint is **not** "no learning" (MEMORY: ML is allowed; LLMs are not) — it is parsimony under PBO.

---

## 9. Evaluation protocol the overlay MUST pass

Any forecasting overlay is presumed overfit until it survives this stack. Forge already has the tooling (D207 `alpha-budget`, D208 `prereg`); Crucible owns CPCV/PBO/DSR. **[H]**

1. **Purged + embargoed CPCV**, purge width = **max(DTE)** of the corpus, embargo = max(signal lookback). For 30 DTE + 63-day HV this is ~93 days of boundary exclusion per fold (~22% of a 5-yr set). Skipping this inflates IC by **3–5×** via label leakage from overlapping windows. Non-negotiable. Forge's existing `cpcv_p25`/`target_wf_p25` pipeline is the right harness.
2. **PBO via CSCV** — the overlay must not push measured PBO up from 0.578. PBO→0.5 means selection is a coin flip OOS; the current gate is already near that ceiling.
3. **Deflated Sharpe Ratio** — deflate the reported Sharpe by E[max Sharpe] over the number of model variants tried (grows as √(2 log N)). After ~1,000 trials the *spurious* IS t-stat under the null is ~3.48 while the walk-forward t of the same winner is ~0.80.
4. **Multiple-testing budget, pre-registered.** Every architecture/feature/hyperparameter tried is one trial. Harvey-Liu-Zhu (2016): the credibility bar is **t ≥ 3.0** (not 2.0). Fix the architecture before touching Forge data; evaluate once; log the trial count via `forge alpha-budget`; deflate.
5. **VRP-net gate first.** Compute the VRP/theta drag for the target DTE *before* model selection: the forecaster's IC must clear that drag, not zero. A 0.05 IC on the underlying does not survive a 1–3%/contract premium decay.
6. **Regime stratification.** Validate across bull/sideways/bear (≈32/37/31% of history); a signal alive only in one vol regime is covariate-shift waiting to fail live.
7. **Pre-registration (D208)** against same-cohort post-selection bias: predict-then-confirm, structurally dropping pre-cut rows.

---

## 10. Minimal falsifiable first experiment (or the honest negative)

**Primary recommendation: do NOT build a strike/price-target forecaster.** It fails all four walls (§1). The "forecasting" the operator senses is volatility + event-phase + cross-sectional rank, which Forge already exploits; the binding gate is dimensionality, which a directional forecaster does not move.

**If a falsifiable test is required to settle it conclusively**, run exactly this — the smallest experiment that can *kill* the hypothesis cheaply:

- **Object:** ONE deterministic feature, not a model or a grammar change. Define per submitted config:
  `hit_rate(signal_family, DTE_bucket, delta_band) = P(signal fired ∩ underlying moved ≥ breakeven within the DTE window)`, computed over Crucible's pinned historical feature cache. Deterministic, no new feed, no grammar bump, PBO-neutral to Crucible.
- **Where:** add it as a **single** input to the F3 verdict model in the §6.2 verdict_scorer slot (`src/forge/ranking/scorer.py`), retrained via `train-robustness`. A/B-gated by an env kill-switch exactly like D193 → disabling restores the prior byte-for-byte.
- **Hypothesis (pre-register via `forge prereg`, D208):** the feature lifts F3's OOS AUC margin **and** the wf_p25 Spearman **and** realized within-family worst-quartile WF, by a pre-stated margin, on a forward cohort cut now.
- **Evaluation (the §9 stack):** CPCV with purge = max(DTE); DSR-deflated; trial count logged to `forge alpha-budget` (D207); must clear Harvey t ≥ 3. VRP-net IC gate checked first.
- **Kill rule:** if it does not beat the existing P(component) × wf_p25 blend OOS at the pre-registered margin, drop the flag (byte-identical revert) and record the negative. **Prior on passing: low** — forge-fit judges it "partially overlaps with the existing regime gate + signal-density filters."
- **Sequencing (critical):** run this **after** the relval experiment (D213, prereg `9b88966c446a`, target cpcv_sharpe_p25 ≥ 1.3) and the cross-sectional vol_event question (D214) resolve. Those target the *binding* PBO gate; this does not. Opening a third selection-side change while two gate-relevant ones are in flight burns alpha budget against the wrong constraint.

**The higher-EV alternative if the goal is "more promotions," not "test the hypothesis":** the single in-paradigm, not-yet-exploited, *forecastable* lever across all 11 threads is the **earnings event-phase distinction** — separating phase-1 (pre-event IV expansion, exit before crush; Gao +3.34%) from phase-3 (post-crush directional drift) within `volatility_event`. This rides on the **already-scoped** cross-sectional vol_event work (D214), so **fold it there** rather than building anew. It is in-paradigm (long-vol, event-gated), has positive empirical support, and — being a new orthogonal-ish family contribution — has at least a *chance* of moving dimensionality, which a directional ranker feature does not.

---

## 11. Appendix

### Key formulas
- **Greek P&L:** ΔC ≈ Δ·ΔS + ½Γ(ΔS)² + ν·Δσ + Θ·Δt
- **Gamma/theta breakeven (daily move to offset decay):** ΔS_be = √(2|Θ|/Γ) = σ·S·√Δt (= the 1-σ implied daily move)
- **Delta-hedged gain (sign = sign(RV²−IV²)):** ½Γ·S²·(RV²−IV²)·Δt → negative in expectation = the VRP
- **First-passage (touch) under GBM:** P_touch = Φ((νT−b)/(σ√T)) + e^(2νb/σ²)·Φ((−νT−b)/(σ√T)); at ν=0 → 2·N(d₂)
- **Risk-neutral ITM vs delta:** P(ITM) = N(d₂) = N(d₁ − σ√τ); delta = N(d₁) overstates P(ITM)
- **EV-optimal strike:** argmax_K [∫_K^∞ (S_T−K)f_forecast(S_T)dS_T − C_market(K,τ)]
- **Merton drift bound:** SE(μ̂) = σ/√T, independent of sampling frequency
- **HAR-RV:** log RV_{t+h} = c + β_d·RV_d + β_w·RV_w + β_m·RV_m + ε
- **OOS R² (Campbell-Thompson):** 1 − MSPE(model)/MSPE(mean)
- **Fundamental law:** IR ≈ IC·√Breadth (caveat: equity MV, not options)
- **PBO (CSCV):** ω = (rank of IS-best on OOS − 0.5)/N_configs; λ = logit(ω); PBO = P(λ<0)
- **DSR:** Φ[(SR − E[max SR_N])·√(T−1) / √(1 − γ₃SR + (γ₄−1)/4·SR²)]

### Consolidated citations (confidence-tagged)
**Predictability ceiling [H]:** Gu-Kelly-Xiu 2020 (RFS) — 0.33–0.40% R², IC≈0.06, Sharpe 1.35 VW; Goyal-Welch 2008 & Goyal-Welch-Zafirov 2024 (RFS) — negative OOS R²; Campbell-Thompson 2008 (RFS); Rapach-Strauss-Zhou 2010 (RFS); Merton 1980 (JFE); McLean-Pontiff 2016 (JF) — 26%/58% decay; Kelly-Malamud-Zhou 2024 (JF); Harvey-Liu-Zhu 2016 (RFS) — t≥3.0.
**VRP / option returns [H]:** Coval-Shumway 2001 (JF) — −3.15%/wk; Bakshi-Kapadia 2003 (RFS); Broadie-Chernov-Johannes 2009 (RFS); Bondarenko 2014 (QJF); Goyal-Saretto 2009 (JFE) — +2.87%/mo cheap-vol; Carr-Wu 2009 (RFS) — index>single-name VRP; Christensen-Prabhala 1998 (JFE); Muravyev-Ni 2020 (JFE); Lochstoer et al. 2025 (Chicago Fed WP) **[M, pre-pub]**.
**Vol forecasting [H]:** Corsi 2009 (J.Fin.Econometrics); Andersen-Bollerslev-Diebold-Labys 2003 (Econometrica); Nelson 1991 (Econometrica); Gatheral-Jaisson-Rosenbaum 2018 (Quant.Fin.); Bollerslev-Tauchen-Zhou 2009 (RFS); Vasquez 2017 (JFQA) **[H in-sample; OOS unconfirmed]**.
**Barrier math [H]:** Reflection principle (Lévy/Doob; Karatzas-Shreve 1991); Reiner-Rubinstein 1991; Kunitomo-Ikeda 1992 (Math.Fin.); Kou-Wang 2003; Broadie-Glasserman-Kou 1997; Moontower (practitioner) — 2×delta rule.
**Strike/DTE/sizing [H/M]:** Faias-Santa-Clara 2017 (JFQA) — OOS Sharpe 0.82; Garleanu-Pedersen-Poteshman 2009 (RFS); theta/Kelly practitioner sources **[L/M]**.
**ML/DL [H]:** Zeng 2023 (AAAI) — linear>Transformer; Nie 2023 (ICLR, PatchTST); Lim 2021 (TFT); TSFM evals arXiv 2606.27100 & 2511.18578 **[M, preprints]**; López de Prado 2018 (AFML); Bailey-Borwein-LdP-Zhu 2015 (J.Comp.Fin.); Bailey-LdP 2014 (DSR).
**Events [H/M]:** Bernard-Thomas 1989 (JAR); Gao-Xing-Zhang 2018 (JFQA) — +3.34%; Chung-Louis 2017 (JEF); Fink 2020 review; Griffin-McInnis-Zhao 2026 (JAR); Lucca-Moench 2015 (JF); Daniel-Moskowitz 2016 (JFE); iPresage 2025 (practitioner, IV-crush 38.2%) **[M]**.
**Practitioner [H/M]:** Moskowitz-Ooi-Pedersen 2012 (JFE); Hurst-Ooi-Pedersen 2017 (AQR); Spitznagel 2021 *Safe Haven*; Pedersen 2015 *Efficiently Inefficient*; Abdelmessih/Moontower **[M]**.

### Open / contested questions
1. **Has VRP genuinely thinned post-2010?** Lochstoer et al. 2025 says short-vol alphas ≈ 0 post-2010 [M, working paper]. If true, Forge's single-name long-vol headwind is materially smaller than the SPX historical figures — would raise the prior on long-option viability. **Worth confirming once published.**
2. **Is post-crush PEAD (phase 3) net-profitable for single-leg long options after VRP+theta, in Forge's universe?** Underlying drift is ~0 factor-adjusted in large-caps; open whether post-crush premium is low enough for modest drift to clear. **Empirically untested for the single-leg form.**
3. **Does cross-sectional `volatility_event` reach the strong band (cpcv-p25 ≳ 1.3)?** Single-name hits 1.514 (directional, iv_minus_rv-driven); cross-sectional never measured (0/757) (D214). This, not a directional forecaster, is the live question for the binding gate.
4. **Will the relval experiment (D213, prereg `9b88966c446a`) clear ≥1.3?** Decides whether *any* in-v1 orthogonal supply moves PBO, or whether portfolio promotion is v2/Path-C. **This dominates the strike-forecasting question in priority.**
5. **Marginal value of a directional ranker feature above F3's regime-conditioned prior** — unknown; the §10 experiment is the only way to measure it; prior is low.

---

*Bottom line: the premise is true where it doesn't help and false where it would. Direction sets terminal payoff but is already priced; the real-world directional edge available at the option's horizon is near the noise floor; the VRP makes direction necessary-not-sufficient; and a strike-forecaster worsens the actual binding constraint (PBO). Forge already forecasts the forecastable things (vol via iv_rank/rv_rank, events via vol_event, cross-sectional rank via the F3/wf_p25 ranker). Do not build the strike-forecaster. If you must test it, test one parsimonious feature in the existing ranker slot, pre-registered and DSR-disciplined — after the gate-relevant relval/vol_event experiments resolve.*
