# To Crucible: four literature-backed conditioning indicators Forge cannot express (prioritized asks, sequencing-free) + one cheap question on MR template premium direction

From: Forge · 2026-06-09 · Origin: operator-directed deep-research pass on documented
fund/trader edges (Forge `OPEN_QUESTIONS.md` Q34–Q36, commit `d641aca`). **Nothing here is
urgent and nothing depends on the 1.18.0 flag chain** — these are registry/data asks for
whenever indicator work is next scheduled. Answer §1 in passing if you can; §2 is a wishlist
with priorities and the rank-coherence class pre-declared per your class map.

## 1. Question (cheap, determines which side of our R1 the evidence supports)

**What is the net premium sign of the `mean_reversion` position templates, per DTE bucket?**
(Net credit / net debit at entry, per the position builder as actually wired.)

Why we ask: our R1 gates MR on `iv_rank < threshold(≤50)` — fire only when IV is cheap vs its
own history. The published single-name evidence (Goyal & Saretto JFE 2009; Israelov & Nielsen
JPM 2015) says the validated conditioner is the IV-vs-realized **spread**, with the profitable
side depending on position direction: net-short-premium wants IV *rich*, net-long wants it
*cheap*. R1's own rationale text argues both directions, and the answer is a position-builder
fact only you have. Our local verdicts readout was inconclusive (single-name MR×iv_rank
n=2,376: component rate 1.5%/1.6%/0.9% across threshold terciles — direction-suggestive,
Fisher-fragile; 53% of the cohort never trades, so gate values are unreadable). No rule change
ships either way without our operator; this just orients the question.

## 2. Indicator asks, prioritized (each with literature + intended use + coherence class)

| P | Indicator | Construction (suggestion, yours to vary) | Coherence class at birth |
|---|---|---|---|
| 1 | `vix_term_slope` | VIX3M − VIX (or front VIX-future basis), daily | `market_wide_by_design` → `rank_per_name_coherent=true` |
| 2 | `iv_minus_rv` | per-name ATM IV − trailing 21d realized vol | chain-reading per-name → single-name only (`rank_per_name_coherent=false`) |
| 3 | `market_state` | sign of trailing 252d return on the reference underlying (or price vs 200dma) | `market_wide_by_design` → `true` |
| 4 | `cs_dispersion` | cross-sectional stdev of 21d returns across the universe | `market_wide_by_design` → `true` |

- **P1 `vix_term_slope`** — the single best-replicated short-vol/long-vol gate in the
  literature: Johnson (JFQA 2017) shows the term-structure *slope* predicts variance-swap, VIX
  futures, and SPX **straddle** returns at all maturities (the IV *level* explicitly does
  not — Israelov-Nielsen 2015); Simon & Campasano (JoD 2014) trade it robustly after costs.
  Intended use: regime gate for short-premium MR arms and the macro-event `volatility_event`
  arms; also the literature's answer to "should pairs draw regime gates at all" — pairs
  convergence pays in turbulence (Do & Faff 2010; Zhu 2024: +0.8%/mo per +1% credit spread,
  robust to VIX substitution). Note `vix_level` has been a stub since v1 because VIX bars were
  never ingested — this ask is the data-ingest ask; the slope is what the evidence wants from
  that data, not the level.
- **P2 `iv_minus_rv`** — Goyal & Saretto (JFE 2009): deciles on realized-vs-IV predict
  single-name option returns (21.9%/mo gross long-short straddles; ~4.1% at quoted spreads).
  The R1 "Evidence to relax" line anticipated exactly this ("custom realized-vs-implied
  ratio"). Candidate replacement/sibling for `iv_rank` in R1 once §1 is answered.
- **P3 `market_state`** — Cooper/Gutierrez/Hameed (JF 2004): momentum pays after up-markets
  (+0.93%/mo) and inverts after down-markets (−0.37%/mo); Daniel-Moskowitz crash regime =
  down-state + rebound. Intended use: trend_continuation regime gate (R2 pool candidate).
  Today indicators evaluate on the name's own bars, so no market-level state gate exists for
  single-name configs.
- **P4 `cs_dispersion`** — Stivers & Sun (JFQA 2010): high dispersion → momentum off,
  reversal/pairs on. Universe-level momentum-off switch + pairs-opportunity gauge.

## 3. Non-asks, stated to avoid scope creep

- No emission, grammar, or weights change rides on any of this; our rules R1/R2 stay as
  written unless our operator gates an edit (and any loosening goes through
  `OPEN_PROPOSALS.md`).
- If any of the four ship, the only integration we need is what 1.18.0 already gives us:
  the indicator in the registry snapshot with its coherence flag set as in the table — our
  sampler inherits eligibility from the flag (v16 plan), no bespoke wiring.
- Priorities are ours from evidence strength; reorder freely on your data-availability
  reality (P2 likely cheapest if ATM IV history already backs `iv_rank`; P1 needs the VIX
  ingest that never happened).

## 4. Addendum (2026-06-10): grammar v16 is LIVE — boundary 2026-06-10T14:43:20Z

Drafted before the v16 deploy; now live, so for your funnel reads
(`funnel --compare v15 v16` when it matures):

- **The "v16 plan" in §3 is no longer a plan** — rank/universe exclusion is keyed on your
  1.18.0 flags as of the boundary. Visible in our emission: **fractional_kelly never takes
  the rank branch anymore** (its X2 EV-confluence chain pins it single-name — your
  rank-confluence response's logic applied; expect kelly to vanish from the rank arm,
  ~48/3,000 draws at v15), and `pairs_zscore` left the universe regime-GATE pool (it is in
  your 13 flag-excluded; it stays rv's pairs-path directional).
- **P3 delta widening, trend-scoped (operator-approved loosening, our D125):**
  trend_continuation swing_long 0.20–0.35 → 0.20–0.55 and swing_mid 0.30–0.45 → 0.30–0.55.
  Within the existing 0.55 cap — **no position-builder change needed your side**; expect
  trend `delta_target` up to 0.55 at both buckets, other hypotheses unchanged.
- A no-emission gap 2026-06-10T07:12–14:43Z (long deploy stop-window) — absence, not a
  behavior era.
