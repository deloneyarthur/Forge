# Crucible relay — the options arm is the PRIMARY, STANDALONE vehicle (NOT the WORLD_A §6.1 overlay)

> **🗄️ ARCHIVED 2026-07-05 (D242): NEVER SENT — operator-confirmed outdated.** The
> exhaustion/standalone-vs-overlay thread moved on empirically (D216 single-name vol_event supply
> strategy; D235 book-PBO 0.178 baseline); the framing here predates both.

**Status: DRAFT for operator review — not sent.** Informational/coordination only: no gate change (hard rule 3), no grammar change in this relay (Path C = grammar v2 = operator+grammar-gated, rule 1), no build commitment.

## 0. The operator's position (explicit — this corrects a framing)

Crucible's `WORLD_A_EVIDENCE_PACKAGE.md` §6.1 (2026-06-08) recommends repurposing Forge's long-vol edge as a **diversifying overlay to the PTS equity alpha**, valuable "even at standalone ~1.0." **The operator declines that route.** The intended frame:

- **The options arm (Forge → Crucible) is the PRIMARY vehicle, judged as STANDALONE as possible** — its success is its own options P&L against the §8.7 gate, **not** marginal contribution to a PTS-anchored book.
- **PTS / QuantIQ equities are a REFERENCE for data and info.** The *only* channel by which the equity arm may inform the options arm is **a variation of ENTRY** (an entry/regime/momentum *signal*) — and only if a probe shows it aids (Q3). Never a portfolio/sizing dependency.

## 1. Frame: exhaust in-scope long-options FIRST; Path C is becoming realistic but HELD

You have CONFIRMED standalone **long-options** exhaustion (D152/D154; 4-check + 22-source sweep): honest-era max **gross CPCV-p25 = 1.40 < 1.5**, **IC-bound**, edge is the **seller's**. Under a standalone-primary mandate that points *eventually* at defined-risk/short-premium (**Path C**). **But the operator's discipline holds:** exhaust the remaining **in-scope** long-options levers first ([[exhaust-long-options-before-v2-spreads]]) — the read is "close, but a few untried levers remain." **Path C is becoming realistic but stays HELD; this relay does NOT request it as the path, nor its sizing.**

## 2. Questions for Crucible

**Q1 — Remaining in-scope standalone headroom (prioritize the last levers).** Given options-standalone-primary, which of these genuinely-untried in-scope levers (you rated them low-EV) are worth running STANDALONE before long-options is declared fully exhausted, and how would you prioritize?
- (i) **joint / bounded-conjunction conditioning** (path-a Thread 2 — §3.5 C3 already permits ≤4 AND-composed signals; the sampler emits 2);
- (ii) a **learned, deterministic non-LLM conditioner** (Thread 3);
- (iii) a **realized-vol *cheapness* entry gate** (Q41 — the orphaned `volatility` family / `vol_regime`, currently unenumerated; would give mean_reversion a denser "buy-cheap-vol" gate than the sparse `iv_rank`);
- (iv) an **equity-derived entry signal** (Q3).

Are any of these a credible route to lift gross CPCV-p25 toward 1.5, or is the verdict firm enough that they're confirmatory only? (We defer to your read; we are NOT re-litigating the verdict, only sequencing the residual in-scope work before Path C.)

**Q2 — Standalone success criterion (confirmed our side).** We will judge the options arm by the full **§8.7 battery at portfolio scope, STANDALONE** — not the §6.1 overlay / marginal-contribution credit, and **not** a relaxed bar; **CPCV-p25 ≥ 1.5** stands. Flag if "primary standalone vehicle" should change how you'd define success (e.g. a *portfolio* of options components vs single-config).

**Q3 — Entry-signal channel (PROBE-GATED).** The operator will adopt an equity-derived entry signal **only if a probe shows it aids.** Would the PTS regime gate, a cross-sectional / risk-adjusted momentum construction, or QuantIQ's HMM regime state plausibly improve the standalone options arm's ENTRY (directional or regime)? **Propose the cheapest probe to test it on our book**; we publish/adopt only on a demonstrated lift. (Hard rule 7: no `equity` as a traded family; an equity-price-derived directional/regime indicator on the underlying is in-bounds — Forge already uses momentum_252 etc.)

**Q4 — Path-C sizing: NOT requested (deferred).** Path C stays HELD; `PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md` remains drafted-but-held. We will request it only once Q1's in-scope levers are run/declined and the operator un-holds Path C.

## 3. What this is / isn't

- **Is:** a strategic-frame clarification (options = primary/standalone, not overlay) + a request to prioritize the residual in-scope levers + a probe-gated entry-signal question. Forge consumes Crucible's verdict; computes nothing (§1.2).
- **Isn't:** a gate change (rule 3), a grammar change (rule 1 — Path C operator+grammar-gated and HELD), a Path-C sizing request, or a build commitment.
- **Standing items unaffected:** the M1/M2 long-options monitor; the §8.6 tail-shadow streak.
