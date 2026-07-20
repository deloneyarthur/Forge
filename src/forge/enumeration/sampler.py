"""Stratified hypothesis-first sampler for grammar-valid ``StrategyConfig``.

§4.2's CSP-style algorithm with the D7 amendment (sizer mode picked second so
§3.5 X1/X2 indicator chaining can complete) and the v8 / D102 reorder
(directional picked BEFORE the DTE bucket, so the bucket can be DERIVED from
the directional signal's horizon instead of sampled blind):

1. Pick hypothesis (only those with non-empty directional + regime pools).
2. Pick sizer mode (only those in ``samplable_sizer_modes``).
3. Pick the directional indicator (§3.5 C2 pool) that has a §3.5-S4-permitted
   DTE bucket (chain-compat aware) AND a C1/C4/R-valid regime partner.
4. Derive the DTE bucket from the directional's signal horizon (v8 / D102):
   ``DTE_target = k * horizon`` for mean_reversion / trend_continuation, an
   event-bracket window for volatility_event, snapped to the nearest
   §3.5-S4-permitted bucket; relative_value picks uniformly (its per-trade DTE
   is a Crucible runtime choice off the live spread half-life).
5. Pick the regime indicator from the §3.5 R-rule pool, C4-disjoint in id,
   C1-disjoint in family from directional. §3.5 S4 gates the directional
   horizon only, so the regime no longer constrains the bucket.
6. Sample selector params: ``delta_target`` in §3.5 P3 band; ``dte_min`` /
   ``dte_max`` from the §3.5 P2 entry window for the bucket.
7. Sample sizer: ``per_trade_risk_pct`` in §3.5 P4 range; mode-specific
   knobs from ``forge.enumeration.defaults``.
8. Compose exits: §3.5 E1 mandatory + §3.5 S5 required for the hypothesis;
   forbidden exits are simply not added.
9. If the sizer mode demands a chained indicator (X1/X2) and it isn't
   already on the strategy, attach as a confluence signal.

Configs are valid-by-construction (closure-plan path (a)). The iterator
runs ``validate()`` as a safety net and logs any residual rejections.
"""

from __future__ import annotations

import functools
import hashlib
import random
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
    UniverseTiers,
    load_earnings_covered_symbols_from_export,
    load_universe_tiers_from_export,
)
from crucible_contracts.exceptions import QueryError

from forge.enumeration import defaults
from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.search_space import (
    NON_ENUMERABLE_HYPOTHESES,
    RANK_COMBINER_HYPOTHESES,
)
from forge.enumeration.underlying_class import underlying_class
from forge.grammar.signal_horizon import (
    buckets_for_horizon_class,
    horizon_class,
    nearest_bucket,
    signal_horizon_days,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from crucible_contracts import IndicatorMetadata, RegistrySnapshot

    from forge.enumeration.search_space import SearchSpace

_logger = structlog.get_logger(__name__)


# Fallback for hypotheses absent from the rejection-weights map. Production
# never hits it: the CLI fills every samplable hypothesis (D105 —
# `compute_hypothesis_component_weights` returns a complete, max-normalized
# map, so a missing key only occurs in direct sampler calls with partial
# maps). On that normalized scale 1/11 reads as ~9% of the best class — the
# same explore share the old Beta(1,10) prior-mean fallback gave. Kept local
# to avoid a circular import between enumeration and feedback.
_HYPOTHESIS_WEIGHT_PRIOR_MEAN: float = 1.0 / 11.0

# D103 (v9) — dynamic relative_value regime-gate weighting. The sampler tilts the
# regime pick toward gates that `forge.feedback.rejection_weights` has learned
# yield accepted relative_value components. Kept local to avoid an
# enumeration→feedback import cycle. Scoped to relative_value (the one
# hypothesis with no §3.5 R-rule, so its regime pool is the whole registry);
# every other hypothesis keeps its uniform `rng.choice` pick.
#
# D105 rescale: the weights are now RAW component-rate posteriors
# (rejection_weights COMPONENT_ALPHA/BETA — Beta(1,50), prior mean 1/51 ≈ 0.02,
# typical learned-good gate ~0.04), so the prior fallback and exploration floor
# sit on that scale: an unseen gate samples at ~half a good gate's weight, and
# a learned-bad gate keeps ~a quarter of a good gate's draw probability
# (~2% per gate across the ~34-gate registry pool — the same per-gate
# exploration share the D067-scale constants produced under the old estimand).
_REGIME_WEIGHT_PRIOR_MEAN: float = 1.0 / 51.0
_REGIME_EXPLORATION_FLOOR: float = 0.01
_REGIME_CURATED_HYPOTHESIS: str = "relative_value"

# D150 (v20) — bias mean_reversion's R1 regime-gate pick toward the RANGING gates
# (gamma_flip long-gamma side, hurst H<0.5) and away from `iv_rank`, which fires
# too sparsely to survive the prefilter (the v6 expected_trades history). iv_rank
# stays explorable (weight 1.0, never zeroed). Grows EFFECTIVE ranging supply from
# the same mean_reversion enumeration share; pairs with the D150 R1 hurst gate.
# D167 (v22) — rv_rank (cheap realized vol) joins the ranging-gate bias set: it is
# the densest, rank-coherent gate and Crucible-validated as dominating hurst, so the
# sampler should prefer it over the prefilter-sparse iv_rank (the "prefer rv_rank"
# economy call — R1 stays an OR, so configs pick one gate; this biases the pick).
# D254 (v24) — vol_regime (the discrete vol tercile, gated <2) joins the boost set
# as the xsect-MR backtest CHAMPION (+0.244 CPCV-p25 vs rv_rank in 6/6 comps;
# FORGE_signal_quality_champions §2b.1). hurst is DROPPED from the boost — it is
# null-to-negative as an MR gate (-0.27 vs rv_rank, 0/6 folds) — but stays R1-
# accepted (weight 1.0, still explorable), i.e. bias AWAY, not remove.
_MR_HYPOTHESIS: str = "mean_reversion"
_MR_RANGING_GATES: frozenset[str] = frozenset(
    # D265 (v28): realized_vol joins the boost — same calm-vol thesis class as
    # rv_rank/vol_regime (the absolute systematic complement), so the new family
    # gets real supply for Crucible's fold-column selection. hurst stays out (D254).
    # D266 (v29): market_realized_vol joins — Crucible's PREFERRED (market-level)
    # variant of the same thesis; at least equal supply to the per-name gates.
    {"gamma_flip_distance_pct", "rv_rank", "vol_regime", "realized_vol", "market_realized_vol"}
)
_MR_RANGING_GATE_WEIGHT: float = 3.0

# D105 — hypothesis x dte_bucket weighting. Same component-rate scale and
# prior/floor rationale as the regime constants above: an unseen cell samples
# at ~half a learned-good cell's weight, a learned-bad cell keeps ~a quarter of
# a good cell's draw probability. Consumed by the joint (directional, bucket)
# draw in `_select_bucket_directional_regime` — the bucket is DERIVED from the
# directional's horizon (D102), and for most indicators every k lands in one
# bucket, so steering the bucket mix necessarily steers the directional pick.
_BUCKET_WEIGHT_PRIOR_MEAN: float = 1.0 / 51.0
_BUCKET_EXPLORATION_FLOOR: float = 0.01

# D105 — underlying-class weighting, same component-rate scale and rationale.
# Per-ticker weight = its class's learned weight, so the high-idio-vol class
# (the minting cohort: AAPL/NVDA/TSLA at 12.8-27.9% yield) outdraws the
# diversified ETF/index class (0 components / ~390 decided), while the floor
# keeps diversified evidence flowing to revise the zero.
_UNDERLYING_CLASS_PRIOR_MEAN: float = 1.0 / 51.0
_UNDERLYING_CLASS_EXPLORATION_FLOOR: float = 0.01


class SamplerError(Exception):
    """Raised when the sampler cannot construct a config from the current
    grammar + registry slice (empty pool at some CSP step)."""


# v8 (D102) — horizon-matched DTE. The directional signal's Forge-owned signal
# horizon (forge.grammar.signal_horizon) drives the DTE bucket: DTE_target =
# k * horizon, snapped to the nearest §3.5-S4-permitted bucket. `k` is the
# exploration knob the grammar now varies instead of raw DTE — it spans "just
# enough time for the thesis" (2x) to "generous" (4x). Per the Crucible
# horizon-matched-DTE handoff (2026-06-04).
_K_MULTIPLIERS: tuple[int, ...] = (2, 3, 4)

# Hypotheses whose DTE is k*horizon off the DIRECTIONAL oscillator/trend period.
# H2 (v12 / D109): event_momentum joins — DTE = k * the sue drift window
# (horizon 10 td) → {20,30,40} td → swing_short/swing_mid, enough DTE to ride the
# 5-20 td post-earnings drift without forcing a blind uniform bucket pick.
_HORIZON_MATCHED_HYPOTHESES: frozenset[str] = frozenset(
    {"mean_reversion", "trend_continuation", "event_momentum"}
)

# volatility_event brackets the event instead: DTE_target = (entry lead before
# the event) + (post-event realization window). Events don't want a k multiple
# of an oscillator period — they want enough DTE to reach the event and capture
# the move. Lead is the exploration knob; the window is fixed at the midpoint of
# the handoff's 10-15 td. Targets {17, 22, 32} -> swing_short / swing_short /
# swing_mid, matching the handoff's "brackets the event -> swing_short/mid".
_VOL_EVENT_LEAD_DAYS: tuple[int, ...] = (5, 10, 20)
_VOL_EVENT_POST_WINDOW_TD: int = 12

# H1 (v12 / D109) — cross_sectional_rank combiner option (the breadth lever).
# rank_k = how many top-ranked names to trade per rebalance; trade count ≈
# rank_k * rebalances (x2 for long_short), deterministic and ≫ the 100-trade
# floor. These are the enumerated knobs; the gate on whether to draw a rank
# combiner at all is the per-hypothesis `rank_combiner_share` (None/empty → never,
# byte-identical cold path, hard rule #6).
_RANK_K_CHOICES: tuple[int, ...] = (5, 10, 20)
_RANK_REBALANCE_CHOICES: tuple[str, ...] = ("weekly", "monthly")
_RANK_DIRECTION_MODES: tuple[str, ...] = ("long_only", "long_short")

# D258 (v25) / D263 (v26) / D266 (v29) — optional regime-VETO share. Fraction of
# ELIGIBLE configs (at least one veto id whose family is absent from the config)
# that carry the optional second regime gate: dsj on trend_continuation (v25),
# ivol + market_realized_vol on mean_reversion (v26/v29 — one drawn per config).
# ~0.5 mints both veto and non-veto arms so the honest campaign compares them;
# feedback-tunable in a later increment. Consumed ONLY when the eligible set is
# non-empty (registry-served AND C1-compatible), so the dormant cold path draws
# no rng and stays byte-identical (hard rule #6). Each veto's C1 family is
# per-ID, read from the registry (SearchSpace.regime_veto_family_by_id) — NOT a
# module constant: dsj is `volatility`, ivol `idiosyncratic_vol`,
# market_realized_vol `macro`.
_REGIME_VETO_SHARE: float = 0.5

# D270 (v31) — the capitulation-bounce family (Crucible
# FORGE_capitulation_bounce_generation_request_2026-07-12): `momentum` as a
# mean_reversion directional (§3.5 C2 per-id carve-out, OPEN_PROPOSALS
# e9d74318). The family's thesis is the PAIR (short-horizon panic drop x
# ELEVATED realized vol), so the gate is pinned — rv_rank op ">" in [50, 80],
# the intended-strength condition the probe's own coding bug left inert
# ("generate gate-on variants so its value gets measured"; gate-OFF fails R1 →
# injection lane). Scoped consequences, all keyed on this directional id:
# regime pool pinned to rv_rank (`_compatible_regimes`); the calm-side
# ivol/market_rv veto slot is SKIPPED (it would strangle co-fire on the very
# prints the trigger selects); time_stop emits `n_bars` in [5, 15] (probe hold
# 10 td — the engine default is 5 and Forge never sampled it; scoping keeps
# the champion MR slice untouched, the D169 concern); computation knobs
# lookback [3, 10] / skip 0 ride the SignalSpec params (D264 pattern).
_CAPITULATION_DIRECTIONAL_ID: str = "momentum"
# D280 (v35): the v31 rv_rank pin is DROPPED — the capitulation arm is
# BARE-DROP (no regime gate; R1 per-directional exemption, operator-approved
# OPEN_PROPOSALS `4d35a046` on Crucible's 2026-07-15 adjudication: the [50,80]
# kernel-unit gate bound harmfully — 69/69 decided dead, median 4 OOS trades —
# and NO replacement gate ships: market_rv x drop co-fires 2x/8.4y). The two
# constants below are retained for the submitted v31 lineage's
# interpretability; the emission path no longer reads them.
_CAPITULATION_REGIME_ID: str = "rv_rank"
_CAPITULATION_RV_RANK_GATE_RANGE: tuple[float, float] = (50.0, 80.0)
_CAPITULATION_LOOKBACK_RANGE: tuple[int, int] = (3, 10)
_CAPITULATION_TIME_STOP_NBARS_RANGE: tuple[int, int] = (5, 15)
# D280 (v35): the swing_short rider — k gains 1 for this directional only
# (1 x horizon 15 td → swing_short; 2/3/4 keep the probe's swing_mid).
_CAPITULATION_K_MULTIPLIERS: tuple[int, ...] = (1, 2, 3, 4)

# D282 (v36) — exit-duration prior concentration (Crucible
# FORGE_exit_duration_priors_2026-07-15, scoping confirmed in
# FORGE_v36_scoping_response_2026-07-15). Crucible's exit registry defaults
# time_stop n_bars to 5; before v36 only the capitulation directional ever
# emitted it. Their probes: (1) trend swing_long — the day-5 timer takes
# 84-88% of exits and CUTS WINNERS (time_stop-bucket win-rate 0.45->0.74 with
# longer holds); n_bars=10 improves cpcv 6/6, wf 5/6 AND maxDD inside their
# declared [3,10] box. Do NOT extend past 10: n=21 buys cpcv by re-opening
# the tail (comp0 maxDD -44%). (2) MR swing_mid — the [5,15] box is right but
# the floor is actively harmful (-0.382 p25-proxy at 5 vs +0.161 at 8;
# plateau 8-20, peak 12); zero floor mass intended ([6,7] is unsampled
# interpolation against a known-bad floor). Scoped to EXACTLY these two
# (hypothesis x bucket) cells — every other time_stop carrier keeps the
# param-less exit ("do not touch other buckets on this evidence"). The
# capitulation directional is VETOED OUT (cohort hygiene: the v35 bare-drop
# pane accumulates at ~50/day and must not split its chassis mid-trial) and
# keeps D270's U[5,15] at BOTH buckets until the v34-vs-v35 pane is read.
_TREND_SWING_LONG_TIME_STOP_NBARS_RANGE: tuple[int, int] = (8, 10)

# D291 (v40) — the MR timer cell goes first-class (Crucible
# FORGE_combined_relay_2026-07-20 §1: the timer-MR family CONVERTED — 1,087
# components/5d, 68 at cpcv>=1.0, head 65316ca4 an 11-bar hold lifting the
# 2-leg book to 1.7236/2.3407 at honest decorrelation 0.347; duration is the
# measured decorrelation axis). Reproduced on OUR verdicts before building
# (decided >= 07-14, MR excl. capitulation): timers n_bars 8-12 convert 15.0%
# vs 13-15 at 11.9% vs param-less default-5 at 5.3% (worst MR cell, n~5,000).
# Two knobs, BOTH scoped to mean_reversion excluding the capitulation
# directional (its v35 bare-drop pane is veto-frozen mid-trial, D282):
#   * the required_from_set pick biases to time_stop at 0.65 (was uniform 0.5)
#     — share moves AWAY from target_exit, the direction D257 already
#     established as safe (share shifting TO target_exit "breaks the book");
#   * n_bars ~ U[8,12] at ALL MR buckets — v36's swing_mid [8,15] narrows to
#     the measured family box and the param-less default-5 emission is retired
#     for MR (supersedes D282's swing_mid-only scoping on the new evidence).
# NB their relay's "15% timer-share" premise mis-attributes v38 (that 0.15 is
# trend/swing_long's OPTIONAL draw; MR's timer is a required pick) — corrected
# in our response relay; the intent (more timer-MR in the converting box) is
# what ships.
_MR_TIME_STOP_NBARS_RANGE: tuple[int, int] = (8, 12)
_MR_TIME_STOP_REQUIRED_PICK_P: float = 0.65

# D292 (v41) / D294 (v42) — the tier stamp. v41 shipped a 15% xsect tier=3
# exploration share on their relay's "never-sampled tier-3 xsect pool"
# framing; their SAME-DAY ledger correction (FORGE_xsect_union_correction_
# 2026-07-20) retracted it: the composable xsect template ranks the ALL-TIER
# union by construction (`_ALL_TIERS = (1,2,3)` + the bulk superset; the
# promoted trend leg trades 89 underlyings incl. tier-1 and 66 outside
# curated 1+2) — the stamp's ONLY engine effect on an xsect config is the
# FillModel SPREAD-TABLE class (tier=3 charges tier_3_base x 1.5). So the
# v41 share bought duplicate books at strictly worse charged costs; v42
# DROPPED it (xsect stamps the calibrated tier=2 constant again; 58 such
# configs were emitted in the ~5h window). The single-name TRUE-tier stamp
# STANDS (their words: a tier-3 single-name charged tier-2 spreads was
# mispriced-cheap — v41 fixed a real cost bug). A future xsect tier=0 stamp
# (explicit union scope, contracts 1.33.0 `ge=0`) waits on their §20 engine
# pin + an explicit ask — relayed as a question, never guessed at.
# (v41's `_XSECT_TIER3_SHARE = 0.15` retired here — tombstone per D169.)

# D288 (v38) — exit-CLASS mix shift for trend swing_long (Crucible
# FORGE_trend_swinglong_exit_mix_2026-07-16; COMPOSES with the v36 duration
# prior above — mix share vs duration-given-carried, two knobs on different
# axes). Their weekly-census read (n=45,850 decided in the cell, 07-02→07-16;
# reproduced on our verdicts to ~1pp before building): exit class orders the
# whole conversion surface — chandelier-only 39.1% component rate >
# other-discretionary 30.7% > timer-carrying 16.9% (monotone; replicates in
# the confluence stratum and at swing_mid) — yet 46% of the cell carried a
# timer via the p=0.5 optional draw. One knob: the time_stop optional
# Bernoulli drops to 0.15 in THIS CELL ONLY; chandelier-only rises
# mechanically (0.5 required-pick x 0.85 no-timer ≈ 42%) and trailing_atr
# (D236: not refuted, kept alongside) keeps its required-pick share. 0.15
# (not 0): their census window mostly PREDATES the v36 U[8,10] prior, so the
# surviving timer draws keep feeding the funnel's read of that prior. Every
# other (hypothesis, bucket) keeps 0.5 — "do not touch other buckets on this
# evidence" (MR's timer is a required_from_set pick, structurally untouched).
_TREND_SWING_LONG_TIME_STOP_PICK_P: float = 0.15
_OPTIONAL_EXIT_PICK_P_DEFAULT: float = 0.5

# D290 (v39) — the ve hold (Crucible's 07-19 ve close-out). time_stop is now the
# REQUIRED ve hold (event_passed_exit is out of the schema — it always ran their
# FALLBACK mode, a hard cut at entry+n_bars, truncating every ve hold; the
# v22/D169 ladder put 60% of ve batches in the cratered region). Their sweep:
# sweet spot around 5; 13/16/21 bars crater (cpcv 0.81/0.42/0.29) -> U[4,7],
# both buckets.
_VE_TIME_STOP_NBARS_RANGE: tuple[int, int] = (4, 7)
_REF_TRAILING_RETURN_ID: str = "ref_trailing_return"
_REF_TRAILING_RETURN_REFERENCES: tuple[str, ...] = ("SPY", "QQQ")
_REF_TRAILING_RETURN_WINDOW_RANGE: tuple[int, int] = (3, 10)

# D276 (v33) — resid_vix CONFIRMED-region concentration (Crucible
# FORGE_resid_vix_region_followup_2026-07-13, first seen 07-15 in the
# late-relay batch): three PIPELINE-NATIVE residual_momentum configs pass the
# WF gate in-book (blend WF 2.119/2.103/2.031 vs probe 2.0611; best cpcv
# carrier 1.4099 — closest-ever to the 1.5 gate); no config carries both axes
# yet, and coverage was ~1 sample per cell over a 5-dim box. Their ask:
# concentrate generation on the converter-anchored region at tens-of-samples-
# per-neighborhood density. All scoped on this directional id (the D270
# pattern): regime pool PINNED to the two confirmed arms (vix_term_slope —
# the WF carriers' gate; hurst — the cpcv carrier's percentile gate); gate
# thresholds narrowed to the converter neighborhoods; structure pinned by
# evidence (every converter is monthly cross_sectional_rank — the closest
# confluence config trades 3 times in 8.5y — so the combiner is forced, with
# rank_k {5,10} and direction_mode long_only-BIASED: 2 of 3 WF passes are
# long_only, and the long_short config nearest the probe params failed, but
# the arm stays explorable). Solo-reject is EXPECTED for this family (all
# three passes are solo §8.7 rejects) — never feed solo verdicts back as kill
# signals.
_RESID_MOMENTUM_DIRECTIONAL_ID: str = "residual_momentum"
_RESID_MOMENTUM_REGIME_IDS: frozenset[str] = frozenset({"vix_term_slope", "hurst"})
_RESID_MOMENTUM_WINDOW_RANGE: tuple[int, int] = (70, 160)
_RESID_MOMENTUM_SKIP_RANGE: tuple[int, int] = (7, 21)
_RESID_VIX_GATE_RANGE: tuple[float, float] = (0.1, 0.7)
_RESID_HURST_GATE_PERCENTILE_RANGE: tuple[float, float] = (0.40, 0.50)
_RESID_RANK_K_CHOICES: tuple[int, ...] = (5, 10)
_RESID_LONG_ONLY_SHARE: float = 0.75

# D276 (v33) — the trend days_since_jump veto never stacks on a
# gamma_flip_distance_pct primary gate: the AND-pair is 93-98% structurally
# dead across every trend directional (~300 configs/wk; Crucible addendum §B),
# while single-gated versions of the same directionals convert at trend's
# healthy rate. Pairings with the OTHER trend gates keep the veto — the
# resid x vix_term_slope x dsj dual-gate arm is explicitly requested supply.
_DSJ_VETO_ID: str = "days_since_jump"
_DSJ_VETO_EXCLUDED_PRIMARY_GATES: frozenset[str] = frozenset({"gamma_flip_distance_pct"})

# Cohort-yield exploration band (§3 of Crucible's 2026-06-17 yield-map refresh).
# When the cohort draw is yield-driven (`cohort_yield_weights` supplied), clamp
# P(cross_sectional_rank) to [floor, 1 - floor] so neither cohort is ever starved
# to zero — the D067 exploration-floor principle on the cohort axis, keeping
# evidence flowing to revise the estimate. Flag-off draws never reach the clamp
# (they use the fixed `rank_combiner_share` unchanged, hard rule #6).
_COHORT_EXPLORATION_FLOOR: float = 0.05

# D151 (v21) — mean_reversion rank ENABLED. D150 held it rank-ineligible pending Q33;
# Crucible answered YES (FORGE_q33_hurst_rank_coherence_response.md): `hurst` is
# per-name-coherent on the rank path (`rank_per_name_coherent = True` — the runner
# reads each name's own price-autocorrelation hurst, not a reference chain). So the
# D150 hypothesis guard is removed; governance reverts to the FLAG-based skip
# (`space.rank_excluded_ids`, keyed on the published `rank_per_name_coherent`): a
# hurst-gated mr config ranks, while the chain-reading iv_rank/gamma_flip gates stay
# single-name confluence (D116 stays correct for them). Honest cap (Crucible, hard
# rule 6): breadth lifts the distribution CENTER, not the worst-quartile p25 — supply,
# not a promotion unlock. Short-history (<~101 sessions) names fail-open on hurst.

# D033 fallback — used when the Crucible universe export is absent.
_FALLBACK_TIER_1_2_UNDERLYINGS: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "AMD",
    "META",
    "AMZN",
    "GOOGL",
    "NFLX",
    "AVGO",
    "BAC",
    "JPM",
    "XOM",
    "CVX",
    "BA",
    "GE",
    "GS",
    "MS",
    "COIN",
    "MSTR",
)

# Exports directory Crucible publishes to. `load_universe_tiers_from_export`
# globs `universe_tickers*.json` within it (contracts 1.13.0 flattened;
# tiered sibling since 1.32.0, D292/v41).
_UNIVERSE_EXPORT_DIR = Path("~/optbt_data/exports").expanduser()


@functools.lru_cache(maxsize=1)
def _load_universe_tiers_cached() -> UniverseTiers | None:
    """D292 (v41): the single cached read of Crucible's tiered universe export
    (`load_universe_tiers_from_export`, contracts 1.32.0). None on an
    unreadable/stale export (`StaleExportError` subclasses `QueryError` — the
    same catch the pre-v41 flattened reader effectively had). Cached for the
    process lifetime — restart to pick up changes."""
    try:
        return load_universe_tiers_from_export(_UNIVERSE_EXPORT_DIR)
    except QueryError as err:
        # M-13: present-but-unparseable export is a DRIFT signal distinct from
        # the expected "absent" offline case. The helper raises loudly; we log
        # and fall back rather than silently narrowing the pool ~152 -> 24.
        _logger.warning(
            "universe_export_unreadable",
            path=str(_UNIVERSE_EXPORT_DIR),
            error=str(err),
            open_question="Q23",
        )
        return None


def _load_underlyings() -> tuple[str, ...]:
    """D078 / Q23: the sampling pool — the tier union from Crucible's universe
    export, blessed-read via contracts (Q23 closed at 1.13.0; the flattened
    reader moved to the tiered sibling at 1.32.0, D292/v41 — IDENTICAL union
    by contract ("two views of one surface"), and required before Crucible
    retires the transition fold (the flattened reader would shrink the pool
    118 -> 24 after retirement). Falls back to the D033 hardcoded list when
    the export is absent/empty or unreadable (logged loudly).
    """
    tiers = _load_universe_tiers_cached()
    if tiers is not None:
        union = tuple(sorted({*tiers.tier_1, *tiers.tier_2, *tiers.tier_3}))
        if union:
            return union
    _logger.info("universe_fallback_hardcoded", n_tickers=len(_FALLBACK_TIER_1_2_UNDERLYINGS))
    return _FALLBACK_TIER_1_2_UNDERLYINGS


def _tier3_symbols() -> frozenset[str]:
    """D292 (v41): TRUE tier-3 membership — feeds the single-name true-tier
    stamp and gates the xsect tier-3 exploration draw. Empty on old-shape
    exports and the D033 fallback (export-gated dormancy: everything stamps
    tier=2 and no rng is consumed, the pre-v41 behavior exactly)."""
    tiers = _load_universe_tiers_cached()
    return frozenset(tiers.tier_3) if tiers is not None else frozenset()


# Pre-v41 the lru_cache lived on `_load_underlyings` itself, and a dozen call
# sites (loader/fingerprint tests, the D274-pattern fixtures) clear the
# universe read via its `cache_clear`. The one true cache is now the shared
# tiers read above — alias its clear so that contract survives the D292
# restructure (both derived views invalidate together; no stale-split hazard).
_load_underlyings.cache_clear = _load_universe_tiers_cached.cache_clear  # type: ignore[attr-defined]


def _stamp_tier(underlying: str | None, combiner: CombinerSpec) -> int:
    """D292 (v41) / D294 (v42): the config's `tier` stamp — the FillModel
    spread-table class (their ledger correction: it is NOT a pool selector;
    xsect ranks the all-tier union regardless).

    Single-name = the underlying's TRUE tier (pure lookup, no rng — a tier-3
    name charged tier-2 spreads was mispriced-cheap; the v41 fix STANDS).
    Xsect = the calibrated tier=2 constant (v42 dropped v41's tier=3 share:
    same union book at 1.5x charged spreads was a strict handicap).
    relative_value (underlying None, confluence combiner) keeps the literal 2
    — pairs legs are Crucible-resolved and the stamp is inert there."""
    if combiner.type == "cross_sectional_rank":
        return 2
    if underlying is not None and underlying in _tier3_symbols():
        return 3
    return 2


def universe_fingerprint() -> str:
    """H-3: stable 16-hex fingerprint of the resolved underlying pool (D078).

    The universe pool shadows `_pick_underlying`'s draws but isn't in
    `registry_hash`/`grammar_version`, so the day Crucible publishes
    `universe_tickers.json` (or changes it) every same-seed reproduction would
    silently diverge (hard rule #6). This folds into `mint_batch_id` +
    `batch_summaries`. `_load_underlyings()` already returns a sorted tuple, so
    the hash is order-stable. D292 (v41): the tier SPLIT is appended when
    tier-3 is served — emission now depends on membership, so same-union/
    different-split must fingerprint differently; the empty-tier-3 payload is
    byte-identical to pre-v41 (continuity for old-shape exports).
    """
    payload = "|".join(_load_underlyings())
    tier3 = _tier3_symbols()
    if tier3:
        payload += "#t3:" + "|".join(sorted(tier3))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@functools.lru_cache(maxsize=1)
def _load_earnings_covered_symbols() -> tuple[str, ...]:
    """D268 durable fix (v32): the earnings-covered symbol set from Crucible's
    coverage export, via the blessed `load_earnings_covered_symbols_from_export`
    (contracts 1.31.0, D271). This is the AUTHORITY on which underlyings may carry
    earnings-gated templates — coverage truth lives where `financials.parquet` is
    authored, so the hardcoded `_NO_EARNINGS_UNDERLYINGS` stopgap is retired from
    maintenance (retained only as free defense-in-depth; see `_earnings_gated_pool`).

    `max_age_days=None` at the read site: a stale coverage set (coverage changes
    slowly) beats HALTING generation, so a silently-dead publisher surfaces in ops
    via the `check_earnings_coverage_export` healthcheck line rather than the loader's
    `StaleExportError`. Absent export → `()` (the contract's cold semantics) → no
    intersection → v31 behaviour exactly. A corrupt export raises `QueryError`
    (`StaleExportError`, its subclass, cannot fire with `max_age_days=None`) → logged
    loudly + `()` fallback (mirrors `_load_underlyings`' `universe_export_unreadable`),
    NOT silently caught, NOT a crash. Cached for the process lifetime — restart to pick
    up a publish, so activation happens at a restart boundary (journal-visible), never
    mid-run.
    """
    try:
        covered = load_earnings_covered_symbols_from_export(_UNIVERSE_EXPORT_DIR, max_age_days=None)
    except QueryError as err:
        # A present-but-unreadable manifest is a drift signal, distinct from the
        # expected "absent" pre-publish case. Log and fall back to no-intersection
        # rather than narrowing (or emptying) the earnings-gated pool on bad data.
        _logger.warning(
            "earnings_coverage_export_unreadable",
            path=str(_UNIVERSE_EXPORT_DIR),
            error=str(err),
        )
        return ()
    return tuple(covered)


def earnings_coverage_fingerprint() -> str:
    """H-3 (v32): stable 16-hex fingerprint of the resolved earnings-coverage set,
    or `""` when no manifest is published.

    Like `universe_fingerprint`, the covered set shadows `_pick_underlying`'s
    earnings-gated draws but lives in neither `registry_hash` nor `grammar_version`;
    once Crucible publishes `earnings_covered_symbols.json` (or changes it), a
    same-seed reproduction would silently diverge unless the covered set is folded
    into the recorded batch identity (hard rule #6). Empty → `""` so the DORMANT
    (pre-publish) `enumeration_inputs_hash` stays byte-identical to v31: an empty
    coverage set applies no intersection, so it shadows no draw and must contribute
    nothing to the identity. `_load_earnings_covered_symbols()` returns a sorted
    tuple, so the hash is order-stable.
    """
    covered = _load_earnings_covered_symbols()
    if not covered:
        return ""
    payload = "|".join(covered)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


_TIER_1_ETF_UNDERLYINGS: frozenset[str] = frozenset({"SPY", "QQQ", "IWM", "DIA"})

# D268 (v30) — no-earnings underlyings excluded from earnings-DEPENDENT generation.
# The T1.4 exclusion above was only the 4 broad-market ETFs, but Crucible's universe
# export has since grown to include ~26 more no-earnings names (leveraged/sector/
# commodity/vol/bond/index products). Crucible's 2026-07-12 relay
# (FORGE_event_momentum_no_earnings_underlying_degenerates): on such a name
# `days_since_earnings` NaN-fills → the engine's no-data fallback returns allow=True
# (never gates) and the `sue` directional NaN → FLAT, so a confluence `realized_vol`
# passthrough backfills a naked long-call — a MISLABELED degenerate leg that trades
# (passes expected_trades) and reached the first promoted book (SOXL). This CONSERVATIVE
# superset (ETFs/leveraged/inverse/commodity/vol/bond/index ONLY — every entry
# unambiguously EPS-less; earnings-covered single names like RTX Corp are deliberately
# ABSENT so honest supply is never starved) closed the ~22.5% degenerate event_momentum
# emission. v32 (D268 durable fix) WIRED the coverage manifest as the authority
# (`_earnings_gated_pool` intersects the pool with `_load_earnings_covered_symbols()`),
# so this list is RETIRED FROM MAINTENANCE — retained only as free defense-in-depth
# (every entry unambiguously EPS-less, so the union can never wrongly exclude a covered
# name, and a manifest-publisher bug can't reintroduce SOXL-class supply). Full deletion
# is a later cleanup bump once the manifest has survived a funnel window (operator's call).
_NO_EARNINGS_UNDERLYINGS: frozenset[str] = _TIER_1_ETF_UNDERLYINGS | frozenset(
    {
        # leveraged / inverse index products
        "TQQQ",
        "SQQQ",
        "SOXL",
        "SOXS",
        "SPXL",
        "SPXS",
        "UPRO",
        "TNA",
        "TZA",
        "UDOW",
        "SDOW",
        "FAS",
        "FAZ",
        "LABU",
        "LABD",
        # sector / industry ETFs (SPDR Select + others)
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLRE",
        "XLU",
        "XLV",
        "XLY",
        "SMH",
        "SOXX",
        "XBI",
        "IBB",
        "KRE",
        "XRT",
        # broad / regional / factor ETFs
        "EEM",
        "EFA",
        "ARKK",
        "FXI",
        "EWZ",
        "KWEB",
        "IWM",
        "VNQ",
        # commodity / currency funds
        "GLD",
        "SLV",
        "USO",
        "UNG",
        "GDX",
        "GDXJ",
        "DBC",
        # volatility products
        "UVXY",
        "VXX",
        "SVXY",
        "VIX",
        # bond / rate ETFs
        "TLT",
        "HYG",
        "IEF",
        "LQD",
        "AGG",
    }
)

# Earnings-calendar regime indicators return a sentinel on ETF underlyings (no
# earnings), so the gate never fires → 0 trades. A config gating on either the
# forward (days_to_earnings; R3 / T1.4) or the backward (days_since_earnings;
# H2 / event_momentum) countdown must therefore be single-name. T1.4 added the
# forward one to the exclusion; v12 adds the backward twin so event_momentum is
# single-name by construction (only event_momentum draws days_since_earnings, so
# this leaves every pre-v12 hypothesis's underlying draw byte-identical — #6).
# D135 (v18) adds pre_earnings_setup — it composes days_to_earnings, so the
# conjunction is a permanent 0.0 on ETFs (never admits); only new v18 draws
# carry it, so every pre-v18 underlying sequence is unchanged (#6).
_EARNINGS_CALENDAR_ETF_INCOMPATIBLE: frozenset[str] = frozenset(
    {"days_to_earnings", "days_since_earnings", "pre_earnings_setup"}
)


# D278 (v34) — structurally untradeable single names (Crucible census #2,
# FORGE_grammar_census_dead_dimensions_2026-07-15 §1): these rank into the
# tier lists on DOLLAR option volume, but zero of their contracts clear the
# v1 selector's min_open_interest/min_volume floor on a sampled day (BKNG
# additionally: a ~$4-5k underlying makes one ATM contract's premium exceed
# the 2%-of-equity per-trade budget) — every config on them is born dead
# (100% WF=0.0 at n=703/431). A FROZEN list by design: the mechanism is
# Crucible-measured per-name against THEIR chain data, not classifiable from
# the ticker; re-admission on their relay ("until we say otherwise"), and the
# whole list retires when their queue-time liquidity preflight ships. NOTE:
# this cannot keep the names out of cross_sectional_rank baskets (underlying
# None; the universe is Crucible's) — their preflight is the complete fix.
# D286 (v37): +SOXX/LLY/GS/MSTR — their row-45 trailing-window guard measures
# 96.1-99.8% WF-zero on ~1,000-run samples each (all clear the ≥25-runs /
# ≥95%-exact-zero bar); the guard eats them at queue time, so our draws on
# them are pure wasted budget (~4.4k draws/wk). Same terms: re-admission on
# their relay; the list retires whole when their liquidity preflight ships.
# D292 (v41): +ASML/COST — the tier-unpin reply named the tier-3 exemplars
# "structurally DEAD single-name underlyings"; our own funnel agrees (ASML
# 641 decided / 0 components, COST 1,544 / 1) — the same dead-cell class,
# measured on OUR verdicts this time. Same re-admission terms; flagged for
# their row-45 cross-check in the response relay.
_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS: frozenset[str] = frozenset(
    {"BKNG", "BRK.B", "SOXX", "LLY", "GS", "MSTR", "ASML", "COST"}
)


def _earnings_gated_pool(underlyings: tuple[str, ...]) -> tuple[str, ...]:
    """The underlying pool for an earnings-gated config — names that actually carry
    earnings data.

    v32 (D268 durable fix): `(universe & covered) - _NO_EARNINGS_UNDERLYINGS` when
    Crucible has published the coverage manifest; the frozen list is retained as free
    defense-in-depth (order is immaterial — it and the covered set are disjoint by
    construction). When the manifest is absent (dormant-until-publish) the covered set
    is empty → exactly the v31 pool (`universe - frozen list`), byte-identical. A
    present-but-DISJOINT covered set (which would empty the pool and crash `rng.choice`)
    falls back to the v31 pool with a loud warn — a bad manifest must NOT halt
    generation. Universe order is preserved (filter, not set ops) so the draw stays
    deterministic (hard rule #6)."""
    v31_pool = tuple(u for u in underlyings if u not in _NO_EARNINGS_UNDERLYINGS)
    covered = _load_earnings_covered_symbols()
    if not covered:
        return v31_pool
    covered_set = frozenset(covered)
    pool = tuple(u for u in v31_pool if u in covered_set)
    if not pool:
        # A valid-but-disjoint manifest would starve the earnings-gated pool entirely.
        # Fall back to the v31 pool rather than crash the loop on `rng.choice(())`.
        _logger.warning(
            "earnings_coverage_empty_intersection",
            n_covered=len(covered),
            n_universe=len(underlyings),
        )
        return v31_pool
    return pool


def _pick_underlying(
    rng: random.Random,
    hypothesis: str,
    regime_indicators: tuple[str, ...] = (),
    underlying_class_weights: Mapping[str, float] | None = None,
    underlying_name_weights: Mapping[str, float] | None = None,
    factor_cell_discounts: Mapping[str, float] | None = None,
) -> str | None:
    """Per-config underlying selection from the Tier 1+2 pool.

    D078: reads from Crucible's universe export when available, falls back
    to the D033 hardcoded list. Determinism preserved via shared rng.

    D098 (v5): `relative_value` returns None — it is a pairs strategy whose
    legs Crucible's PairsConvergence resolves itself (post-commit 4f5271f it
    loads all pair legs regardless of tier, so a single anchor ticker is no
    longer needed). This reverts D079, which had assigned a concrete ticker to
    work around the OLD path's anchor requirement; the tier-loading fix removed
    that requirement, and stamping a single underlying on a pairs config is
    misleading. The rng draw is still consumed below for non-pairs hypotheses,
    keeping the per-hypothesis sampling sequence aligned.

    T1.4 (grammar v2 / D039): when the regime indicators include any
    ETF-incompatible indicator (e.g., `days_to_earnings`), the pool is
    constrained to single-names only — preserves grammar R3's ETF-aware
    compatibility constraint at sample time so the validator doesn't have
    to reject the config downstream.

    D105: ``underlying_class_weights`` tilts the draw by each ticker's learned
    class (`forge.enumeration.underlying_class`) — the pool itself never
    changes, only the draw probability, and the T1.4 exclusion applies before
    weighting. None/empty keeps the uniform `rng.choice` byte-identical.

    D106: ``underlying_name_weights`` (per-name posteriors anchored on the
    class — `compute_underlying_name_weights`) take precedence per ticker;
    names the feedback hasn't observed fall through to their class weight,
    then the prior. The chain keeps every ticker on one coherent
    component-rate scale, so AAPL-grade evidence concentrates draws without
    starving the unobserved remainder of its class.

    H4 (orthogonal-yield): ``factor_cell_discounts`` is the
    (hypothesis, directional)-sliced ``{underlying-name: discount}`` map for
    THIS config's chosen hypothesis+directional (sample_config does the slice).
    Each ticker's weight is multiplied by its own marginal-value discount
    (over-mined names < 1.0; absent → 1.0) BEFORE the exploration floor, so the
    floor still guarantees every ticker a minimum draw and a crowded name stays
    explorable — the discount spreads an over-mined name (AAPL) across its
    minting peers (NVDA/AMD) rather than toward the non-minting diversified
    class. None/empty keeps the D105/D106 (and pre-D105) draw byte-identical
    (hard rule #6 — multiply by exactly 1.0).
    """
    if hypothesis == "relative_value":
        return None
    underlyings = _load_underlyings()
    if any(ind in _EARNINGS_CALENDAR_ETF_INCOMPATIBLE for ind in regime_indicators):
        pool = _earnings_gated_pool(underlyings)
    else:
        pool = underlyings
    # D278 (v34): filter AFTER the branch so it covers both pools; order
    # preserved (filter, not set ops) so the draw stays deterministic (#6).
    pool = tuple(u for u in pool if u not in _STRUCTURALLY_UNTRADEABLE_UNDERLYINGS)
    if underlying_class_weights or underlying_name_weights or factor_cell_discounts:
        names = underlying_name_weights or {}
        classes = underlying_class_weights or {}
        discounts = factor_cell_discounts or {}

        def _ticker_weight(ticker: str) -> float:
            weight = names.get(ticker)
            if weight is None:
                weight = classes.get(underlying_class(ticker), _UNDERLYING_CLASS_PRIOR_MEAN)
            weight *= discounts.get(ticker, 1.0)
            return max(weight, _UNDERLYING_CLASS_EXPLORATION_FLOOR)

        return rng.choices(pool, weights=[_ticker_weight(u) for u in pool], k=1)[0]
    return rng.choice(pool)


def _uses_single_name_only_indicator(
    signals: list[SignalSpec],
    rank_excluded_ids: frozenset[str],
) -> bool:
    """D112 (v13) → D125 (v16): True when a drawn signal makes the config
    single-name-only — it never takes the cross_sectional_rank branch.

    v16 keys the check on the registry's contracts-1.18.0 flags
    (`SearchSpace.rank_excluded_ids` = the dealer family + every
    `NOT rank_per_name_coherent AND NOT market_wide_by_design` id — Crucible's
    fail-closed ClassVar truth about per-name fan-out), retiring the v13-v15
    explicit id sets. ANY role counts, confluence included: D122 corrected the
    v15 premise — EV-as-sizing has no live wiring anywhere, and on the rank
    path a confluence signal is a rank-score factor, where a decoupled
    indicator is output-neutral warm and a cold-cohort FREEZE (uniform NaN →
    empty scores → rebalance no-ops) cold. The X2 kelly EV chain therefore
    pins its config single-name; kelly emission itself is untouched."""
    return any(ind in rank_excluded_ids for sig in signals for ind in sig.indicators)


def _cohort_xsect_probability(
    hypothesis: str,
    directional_id: str,
    bucket: str,
    *,
    cohort_yield_weights: Mapping[tuple[str, str, str, str], float] | None,
    rank_combiner_share: Mapping[str, float] | None,
) -> float:
    """P(emit a ``cross_sectional_rank`` combiner) for the already-chosen recipe.

    Yield-driven (§3 of Crucible's 2026-06-17 yield-map refresh) when
    ``cohort_yield_weights`` carries this recipe's
    ``(hypothesis, directional, bucket)`` triple: ``p = w_xsect / (w_xsect +
    w_single)``, clamped to ``[_COHORT_EXPLORATION_FLOOR, 1 - floor]`` so neither
    cohort is starved (D067). Falls back to the FIXED ``rank_combiner_share`` for
    the hypothesis when the cohort map is absent/empty or has no evidence for the
    triple — so cold-start and flag-off are byte-identical to the H1 draw (hard
    rule #6). Returns 0.0 for hypotheses outside ``RANK_COMBINER_HYPOTHESES``
    (never rank-eligible) and when neither source applies (no cohort rng drawn).

    Within-hypothesis by construction: it only re-weighs single<->xsect for a
    FIXED (hypothesis, directional), never the cross-hypothesis mix — so it cannot
    by itself deepen the trend monoculture (that axis lives in the hypothesis
    weights).
    """
    if hypothesis not in RANK_COMBINER_HYPOTHESES:
        return 0.0
    # D276 (v33): residual_momentum is PINNED to the rank arm — every in-book
    # converter is cross_sectional_rank; the confluence config nearest the
    # probe params trades 3 times in 8.5y (the combiner is load-bearing for
    # the mechanism). Overrides the yield-driven cohort draw for this one
    # directional; the rank-excluded-signal guard at the call site remains
    # the backstop (chained draws host no resid — `_compatible_regimes`).
    if directional_id == _RESID_MOMENTUM_DIRECTIONAL_ID:
        return 1.0
    if cohort_yield_weights:
        w_xsect = cohort_yield_weights.get((hypothesis, directional_id, bucket, "xsect"))
        w_single = cohort_yield_weights.get((hypothesis, directional_id, bucket, "single"))
        if w_xsect is not None and w_single is not None and (w_xsect + w_single) > 0.0:
            p = w_xsect / (w_xsect + w_single)
            return min(max(p, _COHORT_EXPLORATION_FLOOR), 1.0 - _COHORT_EXPLORATION_FLOOR)
    if rank_combiner_share:
        return rank_combiner_share.get(hypothesis, 0.0)
    return 0.0


def _eligible_regime_vetoes(
    signals: list[SignalSpec], space: SearchSpace, hypothesis: str
) -> tuple[str, ...]:
    """The veto ids drawable for this config: the per-ID §3.5 C1 family guard
    (D266) plus the D276 pairing exclusion — dsj never stacks on a gamma_flip
    primary gate (the AND-pair is 93-98% structurally dead; a pure filter, no
    rng consumed, so unaffected paths draw identically)."""
    primary_gate_id = next((s.indicators[0] for s in signals if s.role == "regime_filter"), None)
    veto_pool = space.regime_veto_indicators_by_hypothesis.get(hypothesis, ())
    return tuple(
        v
        for v in veto_pool
        if not _config_has_veto_family_indicator(signals, space, space.regime_veto_family_by_id[v])
        and not (v == _DSJ_VETO_ID and primary_gate_id in _DSJ_VETO_EXCLUDED_PRIMARY_GATES)
    )


def _config_has_veto_family_indicator(
    signals: list[SignalSpec], space: SearchSpace, veto_family: str
) -> bool:
    """§3.5 C1 guard for the D258/D263 optional regime veto: True iff ANY indicator
    already in the config belongs to `veto_family` — the veto's OWN registry family.
    Adding the veto then would put two same-family indicators in one config (C1
    reject), so the sampler skips it — staying valid-by-construction. For dsj
    (`volatility`) this skips when the primary regime gate (rv_rank / vol_regime) or
    the vol_target realized_vol chain is present; for ivol (`idiosyncratic_vol`)
    nothing else in an MR config is that family, so the veto STACKS on the
    volatility gate — the validated `ivol_lo` form."""
    family_ids = set(space.indicators_by_family.get(veto_family, ()))
    return any(ind in family_ids for sig in signals for ind in sig.indicators)


def _sample_veto_params(veto_id: str, rng: random.Random) -> dict[str, object]:
    """Threshold params for the S3 veto slot, plus per-id template knobs.

    D290 (v39): ref_trailing_return carries reference/window template knobs
    beyond the threshold — SAMPLED per Crucible's honesty block (the
    parameterization is knife-edged: variants span cpcv 1.27-1.55; two crossed
    1.5 and were deliberately NOT adopted). Drawn only on this id's path —
    other veto draws consume rng identically (hard rule #6)."""
    params = sample_threshold_params(veto_id, "regime_filter", rng)
    if veto_id == _REF_TRAILING_RETURN_ID:
        params["reference"] = rng.choice(_REF_TRAILING_RETURN_REFERENCES)
        params["window"] = rng.randint(*_REF_TRAILING_RETURN_WINDOW_RANGE)
    return params


def sample_config(
    space: SearchSpace,
    registry: RegistrySnapshot,
    rng: random.Random,
    *,
    hypothesis_weights: Mapping[str, float] | None = None,
    regime_weights: Mapping[str, float] | None = None,
    bucket_weights: Mapping[tuple[str, str], float] | None = None,
    directional_bucket_weights: Mapping[tuple[str, str, str], float] | None = None,
    underlying_class_weights: Mapping[str, float] | None = None,
    underlying_name_weights: Mapping[str, float] | None = None,
    orthogonal_yield_discounts: Mapping[tuple[str, str, str], float] | None = None,
    rank_combiner_share: Mapping[str, float] | None = None,
    cohort_yield_weights: Mapping[tuple[str, str, str, str], float] | None = None,
    regime_gate_yield_weights: Mapping[tuple[str, str, str, str], float] | None = None,
    forced_hypothesis: str | None = None,
) -> StrategyConfig:
    """Construct one grammar-valid ``StrategyConfig`` using ``rng`` for every choice.

    Raises ``SamplerError`` only when the registry is so sparse that no
    grammar-valid config can be built (empty pool at some CSP step).

    ``hypothesis_weights`` biases the hypothesis pick toward those with
    higher posterior promotion rates (long-term #1). When None, falls
    back to uniform `rng.choice`. Hypotheses missing from the map get
    the prior-mean weight so they remain explorable.

    ``regime_weights`` (D103) biases the relative_value regime-gate pick
    toward indicators that feedback has learned yield accepted
    components. Applied ONLY to relative_value (the one hypothesis with no
    §3.5 R-rule); every other hypothesis keeps its uniform pick. When None /
    empty, relative_value also falls back to uniform — so the pre-D103
    sequence is preserved at cold-start and for all other hypotheses.

    ``bucket_weights`` (D105) biases the joint (directional, DTE-bucket) pick
    toward ``(hypothesis, dte_bucket)`` cells that feedback has learned yield
    accepted components. When None / empty, the pre-D105 two-step draw
    (uniform directional → k/lead-derived bucket) is preserved byte-identically
    (hard rule #6: weights are an additional input).

    ``underlying_class_weights`` (D105) biases the underlying pick by each
    ticker's learned class (high-idio-vol vs diversified ETF/index). None /
    empty keeps the uniform pick byte-identical.

    ``directional_bucket_weights`` (D106) refines the joint pick with
    ``(hypothesis, directional, dte_bucket)`` cells, falling back to the
    ``bucket_weights`` pair cell per option (the triple is pair-anchored, so
    the chain is scale-coherent). ``underlying_name_weights`` (D106) refines
    the underlying pick per ticker, falling back to the class weight. Both
    None/empty preserve the respective D105 (and, transitively, pre-D105)
    behaviour byte-identically.

    ``orthogonal_yield_discounts`` (H4) is the
    ``(hypothesis, directional, underlying-name)`` marginal-value discount map.
    It is sliced here by the chosen ``(hypothesis, directional)`` to a
    ``{underlying-name: discount}`` map and forwarded to the underlying pick,
    which multiplies each ticker's weight by its own discount (over-mined names
    < 1.0). None/empty preserves the draw byte-identically (hard rule #6).

    ``rank_combiner_share`` (H1, v12) is the per-hypothesis probability of
    emitting a ``cross_sectional_rank`` combiner (the breadth lever) instead of
    the default confluence — applied ONLY to the breadth-starved directional
    archetypes in ``RANK_COMBINER_HYPOTHESES``. On a rank draw the combiner
    carries ``rank_k`` / ``rebalance_frequency`` / ``direction_mode`` and the
    underlying is set to None (the runner ranks ``universe.tickers``). None/empty
    — and any hypothesis not in the map or mapped to 0.0 — draws NO rng and keeps
    the confluence path byte-identical (hard rule #6); the draw is the LAST
    decision so it never perturbs the signal/selector/sizer/exit/underlying
    sequence of a same-seed config.

    ``cohort_yield_weights`` (§3, 2026-06-17 yield-map refresh) makes that final
    cohort draw YIELD-DRIVEN instead of the fixed ``rank_combiner_share``: the
    ``(hypothesis, directional, dte_bucket, cohort)`` component-rate decides
    P(cross_sectional_rank) for the recipe already chosen (see
    ``_cohort_xsect_probability``). The single largest within-stratum yield axis
    Crucible found — cross-sectional momentum 40.4% vs single-name 0.96% on the
    identical recipe. None/empty (or no evidence for the recipe's triple) →
    fall back to ``rank_combiner_share``, byte-identical to the H1 draw (hard
    rule #6). It re-weighs single↔xsect within a fixed hypothesis only.

    ``regime_gate_yield_weights`` (§2, 2026-06-17 yield-map refresh) makes the
    regime-gate draw yield-driven: the ``(hypothesis, directional, dte_bucket,
    regime_gate)`` component-rate is sliced to the chosen triple and COMPOSED onto
    the D150/uniform base in ``_pick_regime`` (down-weighting sink gates like the
    gamma_flip trend regime, up-weighting minting ones). relative_value is never
    composed (D119 — its pairs runner ignores the gate). None/empty preserves the
    base regime draw byte-identically (hard rule #6).

    ``forced_hypothesis`` (D037) overrides the weighted pick when set —
    use it from the iterator to enforce a per-hypothesis stratified
    floor and prevent the failure-bias sampler from collapsing onto a
    single hypothesis. Raises ``SamplerError`` if the forced hypothesis
    is not in the samplable pool (i.e., has empty directional or regime
    pools under the current registry).
    """
    by_id: dict[str, IndicatorMetadata] = {ind.id: ind for ind in registry.indicators}

    # D066/D098: exclude non-enumerable hypotheses — overlay-only tail_hedge
    # (Crucible's runner RunnerErrors it at dispatch) + disabled-by-policy
    # regime_arbitrage (low-yield by construction). See
    # `NON_ENUMERABLE_HYPOTHESES` in search_space.py for rationale.
    samplable_hypotheses = tuple(
        h
        for h in space.hypotheses
        if h not in NON_ENUMERABLE_HYPOTHESES
        and space.directional_indicators_by_hypothesis[h]
        and space.regime_indicators_by_hypothesis[h]
    )
    if not samplable_hypotheses:
        msg = "no hypothesis has non-empty directional + regime pools"
        raise SamplerError(msg)
    if not space.samplable_sizer_modes:
        msg = "no sizer mode is samplable in the current registry"
        raise SamplerError(msg)

    if forced_hypothesis is not None:
        if forced_hypothesis not in samplable_hypotheses:
            msg = (
                f"forced_hypothesis={forced_hypothesis!r} not in samplable pool "
                f"{list(samplable_hypotheses)} — empty directional or regime pool"
            )
            raise SamplerError(msg)
        hypothesis = forced_hypothesis
    elif hypothesis_weights:
        weights = [
            hypothesis_weights.get(h, _HYPOTHESIS_WEIGHT_PRIOR_MEAN) for h in samplable_hypotheses
        ]
        hypothesis = rng.choices(samplable_hypotheses, weights=weights, k=1)[0]
    else:
        hypothesis = rng.choice(samplable_hypotheses)
    mode = rng.choice(space.samplable_sizer_modes)
    chain_id = space.sizer_required_indicator.get(mode)

    # v8 (D102): horizon-matched DTE. Pick the directional first, derive the
    # DTE target from its signal horizon (k*horizon, or the event-bracket for
    # volatility_event), and snap to the nearest §3.5-S4-permitted bucket. The
    # regime is then chosen by C1/C4/R-rules only — its horizon no longer gates
    # the bucket (that was the degenerate-registry artifact v8 removes; the S4
    # validator only ever checked the directional signal).
    bucket, directional_id, regime_id = _select_bucket_directional_regime(
        space,
        by_id,
        hypothesis,
        chain_id,
        rng,
        regime_weights=regime_weights,
        bucket_weights=bucket_weights,
        directional_bucket_weights=directional_bucket_weights,
        regime_gate_yield_weights=regime_gate_yield_weights,
    )

    # H4: slice the (hypothesis, directional, name) discount map down to this
    # config's chosen (hypothesis, directional) — the factor cell is only fully
    # determined once the underlying (the name) is drawn below, so the discount
    # can only attach to the underlying pick, conditioned on the already-chosen
    # hypothesis + directional. None/empty → no slice → no-op.
    factor_cell_discounts: dict[str, float] | None = None
    if orthogonal_yield_discounts:
        factor_cell_discounts = {
            name: disc
            for (h, d, name), disc in orthogonal_yield_discounts.items()
            if h == hypothesis and d == directional_id
        }

    signals = _base_signals(hypothesis, directional_id, regime_id, rng)
    # Belt-and-suspenders: a `type='threshold'` signal with no `threshold`
    # key in params bypasses Crucible's predicate (`lambda _v: False`) and
    # silently gate-rejects on min_oos_trade_count. The `_directional_candidates`
    # + `_compatible_regimes` filters call `is_threshold_skippable` to exclude
    # indicators without audited threshold ranges; this assert catches any
    # future regression where an indicator slips through.
    for sig in signals:
        if sig.type == "threshold" and "threshold" not in sig.params:
            msg = (
                f"empty-threshold leak: signal id={sig.id} "
                f"indicators={sig.indicators} type=threshold but params "
                f"missing 'threshold' key — add the indicator to "
                "_INDICATOR_THRESHOLD_TABLE or mark it is_skip=True"
            )
            raise SamplerError(msg)
    if chain_id is not None and chain_id not in {directional_id, regime_id}:
        signals.append(
            SignalSpec(
                id=f"sig_chain_{chain_id}",
                type="passthrough",
                role="confluence",
                indicators=(chain_id,),
            )
        )

    selector = _build_selector(space, hypothesis, bucket, rng)
    sizer = _build_sizer(space, mode, rng)
    exits = _build_exits(space, hypothesis, rng, directional_id=directional_id, bucket=bucket)

    config_name = f"forge_{hypothesis}_{bucket}_{rng.getrandbits(32):08x}"

    # D033 — per-config underlying from Tier 1+2 pool.
    # D098 — relative_value returns None (pairs strategy; Crucible loads the legs).
    # T1.4: pass regime indicator IDs so the picker can constrain to single-names
    # when the regime contains an ETF-incompatible indicator (e.g.,
    # days_to_earnings / days_since_earnings — sentinel on ETFs, no earnings).
    underlying = _pick_underlying(
        rng,
        hypothesis,
        regime_indicators=tuple(
            ind for sig in signals if sig.role == "regime_filter" for ind in sig.indicators
        ),
        underlying_class_weights=underlying_class_weights,
        underlying_name_weights=underlying_name_weights,
        factor_cell_discounts=factor_cell_discounts,
    )

    # H1 (v12 / D109) — cross_sectional_rank combiner, the breadth lever. Drawn
    # LAST and gated on `rank_combiner_share` so the confluence cold path is
    # byte-identical (hard rule #6): no share for this hypothesis (or share 0.0,
    # short-circuited before rng) → no rng draw, combiner stays confluence. On a
    # rank draw the runner ranks `universe.tickers(asof, tier)` by the directional
    # score and trades top-rank_k (+ bottom for long_short) each rebalance, so the
    # underlying is None (a single name is meaningless). The directional + regime
    # signals are unchanged — the runner routes role=="regime_filter" to its gates
    # and the directional to the rank score. Routing to Crucible's composable
    # rank runner is by combiner.type on the forge_-prefixed config name.
    #
    # D112 (v13): a config that drew ANY dealer_positioning signal never takes
    # the rank branch — dealer indicators are single-name only (the dealer
    # headline x universe is Crucible's ~100x runner tail; see
    # `DEALER_POSITIONING_FAMILY`). D116 (v14) widened the skip to the
    # chain-reading ids; D118 (v15) re-keyed it on Crucible's indicator→mode
    # map; D125 (v16) keys it on the contracts-1.18.0 registry flags
    # (`space.rank_excluded_ids` — fail-closed, so new indicators auto-inherit
    # exclusion) and drops the v15 confluence exemption (D122: the X2 kelly EV
    # chain is a rank-score factor on this path, not sizing — output-neutral
    # warm, config-freezing cold — so kelly-chain draws stay single-name).
    # Consequences: mean_reversion and event_momentum never rank (their pools/
    # signal sets are flag-excluded) until Crucible flips
    # `rank_per_name_coherent`; trend_continuation (bar-only gates) keeps the
    # rank arm, minus its kelly-chain draws. The skip consumes no rng, so
    # unaffected draw sequences are unchanged; the skipped config keeps its
    # signals and pinned underlying — full single-name sampling weight.
    combiner = CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1)
    # D109 fixed `rank_combiner_share`; the 2026-06-17 yield-map refresh (§3)
    # makes the cohort probability YIELD-DRIVEN via `cohort_yield_weights`,
    # falling back to that share when absent (byte-identical, hard rule #6). The
    # rng.random() is reached under the SAME guard as the D109 inline block
    # (positive probability AND rank-eligible signals), so a None cohort map
    # preserves the H1 draw sequence exactly.
    p_xsect = _cohort_xsect_probability(
        hypothesis,
        directional_id,
        bucket,
        cohort_yield_weights=cohort_yield_weights,
        rank_combiner_share=rank_combiner_share,
    )
    # D276 (v33): residual_momentum arrives here PINNED to the rank arm —
    # `_cohort_xsect_probability` returns 1.0 for it (see the WHY there), so
    # the rng.random() consumption and the rank-excluded-signal guard both
    # stay; resid cannot reach the guard excluded (chained draws host no resid
    # — `_compatible_regimes` — and resid/vix/hurst are rank-eligible on the
    # live registry flags).
    if (
        p_xsect > 0.0
        and not _uses_single_name_only_indicator(signals, space.rank_excluded_ids)
        and rng.random() < p_xsect
    ):
        combiner = _rank_combiner(directional_id, rng)
        underlying = None

    # D258 (v25) / D263 (v26) — optional SECOND regime gate ANDed on top of the
    # mandatory primary regime gate (§3.5 S3 permits >1; R1/R2 satisfied by the
    # primary): dsj event-frequency veto on trend_continuation (v25, vetoes "dead
    # tape"), ivol name-selection veto on mean_reversion (v26, excludes high-idio-
    # vol "falling knives"; Crucible FORGE_ivol_lo_mr_entry_gate_2026-07-09).
    # Per-hypothesis pool + family, both from the registry. DORMANT until the
    # registry serves the veto id — the pool is empty pre-publish, so `if veto_pool`
    # short-circuits BEFORE any rng.random() (byte-identical cold path, hard rule
    # #6), like the H1 rank-combiner guard above. C1-safe by construction: skipped
    # when an existing signal shares the veto's OWN family — for dsj that's
    # volatility (rv_rank/vol_regime or the vol_target realized_vol chain); for ivol
    # (idiosyncratic_vol) nothing else in an MR config is that family, so it STACKS
    # on the volatility gate — the validated form. Drawn LAST so activation shifts
    # only the added signal, not the selector/sizer/exit/underlying/combiner draws.
    # D266 (v29): the C1 guard is per-ID — each veto id is eligible iff no
    # indicator of ITS OWN family is already in the config (MR's pool spans two
    # families: ivol=idiosyncratic_vol, market_realized_vol=macro). For
    # single-id pools (dsj on trend; any partially-served MR registry) the
    # eligible set equals the old per-hypothesis guard, and the share draw +
    # rng.choice consume identically — byte-identical to the D263 path
    # (goldens assert it).
    # D270 (v31): the capitulation directional NEVER draws a veto — both MR
    # veto ids are CALM-side gates (ivol "<" excludes high idio-vol names,
    # market_rv "<" excludes market spikes), the exact prints the elevated-vol
    # drop trigger selects; ANDing one on would strangle co-fire to ~zero.
    # The short-circuit precedes rng.random(), so non-momentum paths consume
    # identically (hard rule #6).
    # D276 (v33): the dsj veto is additionally ineligible when the PRIMARY
    # regime gate is gamma_flip_distance_pct — the AND-pair is 93-98%
    # structurally dead (~300/wk); single-gated versions convert fine. Pure
    # eligibility filter (no rng consumed), so non-gamma_flip paths draw
    # identically; gamma_flip-gated trend paths skip the share draw when the
    # (single-id) eligible set empties — licensed by the v33 bump.
    eligible_vetoes = _eligible_regime_vetoes(signals, space, hypothesis)
    if (
        directional_id != _CAPITULATION_DIRECTIONAL_ID
        and eligible_vetoes
        and rng.random() < _REGIME_VETO_SHARE
    ):
        veto_id = rng.choice(eligible_vetoes)
        signals.append(
            SignalSpec(
                id="sig_regime_veto",
                type="threshold",
                role="regime_filter",
                indicators=(veto_id,),
                params=_sample_veto_params(veto_id, rng),
            )
        )

    return StrategyConfig(
        name=config_name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket=bucket,  # type: ignore[arg-type]
        underlying=underlying,
        tier=_stamp_tier(underlying, combiner),
        signals=tuple(signals),
        combiner=combiner,
        selector=selector,
        sizer=sizer,
        exits=exits,
        equity_hedge_metadata=None,  # D5: Forge submits pure options
    )


def _base_signals(
    hypothesis: str,
    directional_id: str,
    regime_id: str | None,
    rng: random.Random,
) -> list[SignalSpec]:
    """The directional signal plus (usually) the mandatory primary regime gate.

    D280 (v35): ``regime_id`` is None ONLY for the bare-drop capitulation arm
    (R1/S3-exempt) — that config carries no regime gate at all. Every other
    path appends the gate exactly as before.
    """
    signals = [
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=(directional_id,),
            params=_directional_signal_params(directional_id, rng),
        ),
    ]
    if regime_id is not None:
        signals.append(
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=(regime_id,),
                params=_regime_signal_params(
                    hypothesis, regime_id, rng, directional_id=directional_id
                ),
            )
        )
    return signals


def _rank_combiner(directional_id: str, rng: random.Random) -> CombinerSpec:
    """The cross_sectional_rank combiner for a rank-arm draw.

    D276 (v33): residual_momentum's structure is pinned by evidence — monthly
    rebalance (every in-book converter; the weekly config failed hardest and
    breached the book dd gate), rank_k {5, 10} (their 5-10 ask), direction_mode
    long_only-BIASED (2 of 3 WF passes; long_short stays explorable). Every
    other directional keeps the H1 uniform knob draws exactly as before.
    """
    if directional_id == _RESID_MOMENTUM_DIRECTIONAL_ID:
        return CombinerSpec(
            type="cross_sectional_rank",
            rank_k=rng.choice(_RESID_RANK_K_CHOICES),
            rebalance_frequency="monthly",
            direction_mode=("long_only" if rng.random() < _RESID_LONG_ONLY_SHARE else "long_short"),
        )
    return CombinerSpec(
        type="cross_sectional_rank",
        rank_k=rng.choice(_RANK_K_CHOICES),
        rebalance_frequency=rng.choice(_RANK_REBALANCE_CHOICES),  # type: ignore[arg-type]
        direction_mode=rng.choice(_RANK_DIRECTION_MODES),  # type: ignore[arg-type]
    )


def _chain_compatible_buckets(
    space: SearchSpace,
    chain_id: str | None,
) -> tuple[str, ...]:
    """DTE buckets compatible with the X1/X2 chain indicator's §3.5 S4 horizon
    class (all buckets when the sizer mode requires no chained indicator)."""
    if chain_id is None:
        return space.dte_buckets
    return buckets_for_horizon_class(horizon_class(chain_id))


def _compatible_regimes(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    directional_id: str,
    chain_family: str | None,
) -> tuple[str, ...]:
    """Regime indicators that pair with ``directional_id`` under §3.5 C1
    (different family), C4 (different id) and the R-rules, are threshold-able,
    and (D077) don't share the X1/X2 chain indicator's family.

    v8 (D102): NO horizon constraint vs the bucket. §3.5 S4 governs the
    *directional* signal's horizon only (as the validator always has), so the
    regime gate is free to pair with any bucket. Dropping the constraint also
    undoes the degenerate-registry artifact (every lookback 0) that forced
    trend regimes onto rv_rank — adx/hurst can now gate swing_mid/long.

    D270 (v31): the capitulation directional's gate is PINNED to rv_rank —
    the family's thesis IS the (drop trigger x elevated realized vol) pair;
    a calm-side gate (iv_rank/realized_vol '<' ...) ANDed onto a panic-print
    trigger would structurally never co-fire. The pin composes with the
    chain-family filter: under a vol_target chain (realized_vol, family
    volatility) rv_rank is excluded → the pool is EMPTY → momentum is dropped
    from `_directional_candidates` for that draw (C1-correct by construction)."""
    directional_family = by_id[directional_id].family
    compatible = tuple(
        i
        for i in space.regime_indicators_by_hypothesis[hypothesis]
        if i in by_id
        and i != directional_id
        and by_id[i].family != directional_family
        and not is_threshold_skippable(i, "regime_filter")
        and (chain_family is None or by_id[i].family != chain_family)
    )
    if hypothesis == "mean_reversion" and directional_id == _CAPITULATION_DIRECTIONAL_ID:
        # D280 (v35): the capitulation arm is BARE-DROP — no regime gate at
        # all (the v31 rv_rank pin bound harmfully and is dropped on
        # Crucible's adjudication; R1 exempts this directional). The empty
        # pool is the signal to `_select_bucket_directional_regime` to skip
        # the regime draw; admission is handled in `_directional_candidates`.
        return ()
    # D276 (v33): residual_momentum's gate is PINNED to the two CONFIRMED arms
    # (vix_term_slope / hurst) — the density lever of the concentrated sweep.
    # CHAINED draws (X1 vol_target / X2 kelly) host no resid at all: the chain
    # signal is rank-flag-excluded, which would force those draws onto the
    # confluence arm — the structure Crucible measured DEAD for this mechanism
    # (the nearest confluence config trades 3 times in 8.5y). Emptying the
    # pool drops resid from `_directional_candidates` for that draw (the
    # capitulation pin's mechanism), so every emitted resid config is
    # chain-less and rank-eligible by construction.
    if hypothesis == "trend_continuation" and directional_id == _RESID_MOMENTUM_DIRECTIONAL_ID:
        if chain_family is not None:
            return ()
        return tuple(i for i in compatible if i in _RESID_MOMENTUM_REGIME_IDS)
    return compatible


def _directional_candidates(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    chain_compat_buckets: tuple[str, ...],
    chain_family: str | None,
) -> tuple[str, ...]:
    """Directional indicators that can anchor a config for this hypothesis:
    threshold-able, in the registry, with at least one §3.5-S4-permitted DTE
    bucket (after chain-compat) AND at least one compatible regime partner.
    Canonical (sorted) order is preserved from the search space for #6."""
    chain_compat = set(chain_compat_buckets)
    return tuple(
        d
        for d in space.directional_indicators_by_hypothesis[hypothesis]
        if d in by_id
        and not is_threshold_skippable(d, "directional")
        and chain_compat.intersection(buckets_for_horizon_class(horizon_class(d)))
        and (
            _compatible_regimes(space, by_id, hypothesis, d, chain_family)
            # D280 (v35): the bare-drop capitulation arm needs no regime
            # partner (R1-exempt). Chain shape preserved from v31: a
            # vol_target chain (family volatility) never hosted capitulation
            # (previously a C1 side effect of the rv_rank pin; now explicit
            # policy), while the kelly chain (smart_money) still may.
            or (
                hypothesis == "mean_reversion"
                and d == _CAPITULATION_DIRECTIONAL_ID
                and chain_family != "volatility"
            )
        )
    )


def _dte_target(
    hypothesis: str,
    directional_id: str,
    rng: random.Random,
) -> float | None:
    """The v8 (D102) DTE target in trading days, or ``None`` to pick uniformly.

    - mean_reversion / trend_continuation: ``k * signal_horizon(directional)``,
      k ∈ {2, 3, 4} — DTE matches the directional oscillator/trend period.
    - volatility_event: ``entry_lead + post_event_window`` — enough DTE to
      bracket the event and capture the realized move.
    - relative_value: ``None``. Its per-pair DTE is a Crucible *runtime* choice
      (k * the live spread half-life), so Forge can't fix one at generation;
      it samples a bucket uniformly among the S4-permitted set and lets Crucible
      adapt per trade. See the horizon-matched-DTE handoff (2026-06-04)."""
    if hypothesis in _HORIZON_MATCHED_HYPOTHESES:
        # D280 (v35): the capitulation directional adds k=1 — the swing_short
        # rider (Crucible: "still fine, low stakes"). 1 x horizon 15 td snaps
        # swing_short; k∈{2,3,4} keep the probe's swing_mid. Every other
        # directional keeps D102's k∈{2,3,4} exactly.
        ks = (
            _CAPITULATION_K_MULTIPLIERS
            if directional_id == _CAPITULATION_DIRECTIONAL_ID
            else _K_MULTIPLIERS
        )
        return float(rng.choice(ks) * signal_horizon_days(directional_id))
    if hypothesis == "volatility_event":
        return float(rng.choice(_VOL_EVENT_LEAD_DAYS) + _VOL_EVENT_POST_WINDOW_TD)
    return None


def _directional_bucket_options(
    hypothesis: str,
    directional_id: str,
    chain_compat_set: set[str],
) -> tuple[str, ...]:
    """The DTE buckets one directional can induce, WITH multiplicity (D105).

    Mirrors the cold-path derivation exactly: each k (horizon-matched
    hypotheses) or event lead (volatility_event) maps to its
    ``nearest_bucket``; relative_value lists its S4-permitted buckets directly
    (its target is a Crucible runtime concern — see `_dte_target`). Repeats are
    deliberate: a bucket reachable by 2 of 3 knob values carries 2x the
    structural mass, exactly as the cold path's uniform knob draw does, so the
    learned weight composes WITH the structural prior instead of replacing it.
    """
    allowed = tuple(
        b for b in buckets_for_horizon_class(horizon_class(directional_id)) if b in chain_compat_set
    )
    if hypothesis in _HORIZON_MATCHED_HYPOTHESES:
        horizon = signal_horizon_days(directional_id)
        # D280 (v35): mirrors _dte_target's capitulation k=1 rider so the
        # weighted joint draw carries the same structural bucket mass
        # (1x swing_short + 3x swing_mid for the capitulation id).
        ks = (
            _CAPITULATION_K_MULTIPLIERS
            if directional_id == _CAPITULATION_DIRECTIONAL_ID
            else _K_MULTIPLIERS
        )
        return tuple(nearest_bucket(allowed, float(k * horizon)) for k in ks)
    if hypothesis == "volatility_event":
        return tuple(
            nearest_bucket(allowed, float(lead + _VOL_EVENT_POST_WINDOW_TD))
            for lead in _VOL_EVENT_LEAD_DAYS
        )
    return allowed


def _select_bucket_directional_regime(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    chain_id: str | None,
    rng: random.Random,
    *,
    regime_weights: Mapping[str, float] | None = None,
    bucket_weights: Mapping[tuple[str, str], float] | None = None,
    directional_bucket_weights: Mapping[tuple[str, str, str], float] | None = None,
    regime_gate_yield_weights: Mapping[tuple[str, str, str, str], float] | None = None,
) -> tuple[str, str, str | None]:
    """v8 (D102) horizon-matched selection. Returns ``(bucket, directional_id,
    regime_id)``.

    Draw order is fixed for determinism (#6): directional → DTE target →
    bucket → regime. The directional is picked first because the DTE bucket is
    DERIVED from its signal horizon (vs the pre-v8 bucket-first CSP). Valid by
    construction: ``_directional_candidates`` guarantees a non-empty allowed
    bucket set and a non-empty regime set, so no fallback scan is needed.

    With ``bucket_weights`` (D105) the directional + bucket are drawn JOINTLY
    over every (candidate, induced-bucket) pair, weighted by the pair's
    ``(hypothesis, bucket)`` cell. The joint draw is load-bearing: most
    directionals are bucket-locked across k (macd → all swing_mid,
    momentum_252 → all swing_long), so a k-only reweight could not move the
    bucket mix at all — the cell weight must steer WHICH directional anchors
    the config. ``directional_bucket_weights`` (D106) refines each option with
    its (hypothesis, directional, bucket) triple when learned — the triple is
    anchored on the pair cell (`compute_hypothesis_directional_bucket_weights`),
    so the triple → pair → prior fallback chain stays on one scale and a flat
    multiplication's double-counting is avoided. Cold start (None/empty for
    both) keeps the two-step draw above, byte-identical to pre-D105.
    """
    chain_compat = _chain_compatible_buckets(space, chain_id)
    chain_compat_set = set(chain_compat)
    chain_family = by_id[chain_id].family if chain_id is not None else None

    candidates = _directional_candidates(space, by_id, hypothesis, chain_compat, chain_family)
    if not candidates:
        msg = (
            f"no directional indicator has a §3.5 S4-permitted DTE bucket with a "
            f"C1/C4/R-valid regime partner for hypothesis={hypothesis} chain={chain_id}"
        )
        raise SamplerError(msg)

    if bucket_weights or directional_bucket_weights:
        triples = directional_bucket_weights or {}
        pairs = bucket_weights or {}

        def _option_weight(directional: str, bucket_name: str) -> float:
            weight = triples.get((hypothesis, directional, bucket_name))
            if weight is None:
                weight = pairs.get((hypothesis, bucket_name), _BUCKET_WEIGHT_PRIOR_MEAN)
            return max(weight, _BUCKET_EXPLORATION_FLOOR)

        options = tuple(
            (d, b)
            for d in candidates
            for b in _directional_bucket_options(hypothesis, d, chain_compat_set)
        )
        weights = [_option_weight(d, b) for d, b in options]
        directional_id, bucket = rng.choices(options, weights=weights, k=1)[0]
    else:
        directional_id = rng.choice(candidates)
        target = _dte_target(hypothesis, directional_id, rng)
        allowed = tuple(
            b
            for b in buckets_for_horizon_class(horizon_class(directional_id))
            if b in chain_compat_set
        )
        bucket = nearest_bucket(allowed, target) if target is not None else rng.choice(allowed)

    regimes = _compatible_regimes(space, by_id, hypothesis, directional_id, chain_family)
    # D280 (v35): the bare-drop capitulation arm draws NO regime gate — its
    # pool is empty by design (R1-exempt) and no regime rng is consumed, so
    # every other directional's draw sequence is untouched. Keyed on the id
    # (not on pool emptiness) so a genuinely-broken empty pool elsewhere still
    # fails loudly in _pick_regime rather than silently going gate-less.
    if directional_id == _CAPITULATION_DIRECTIONAL_ID and not regimes:
        return bucket, directional_id, None
    # §2 yield-map refresh: slice the (hyp, dir, bucket, regime) yield map down to
    # this config's chosen (hyp, dir, bucket) — the regime cell is determined here
    # (the regime is drawn next), exactly the H4 (hyp, dir)-slice discipline.
    # None/empty → no slice → _pick_regime keeps its D150/uniform draw.
    learned_regime: dict[str, float] | None = None
    # D286 (v37): the resid two-arm sweep is an EXPERIMENT — the learned
    # regime-gate posteriors (minted when hurst carried the cpcv config) compose
    # onto the D276-pinned two-member pool and starve the vix_term_slope arm
    # (~94% hurst emission vs the 07-13 two-arm spec; vix is the WF-conversion
    # carrier). Bypass the composition for this directional — `_pick_regime`
    # then draws the uniform coin on the pinned pair (the D119 relative_value
    # precedent: learned weights must not bias an experimental draw). Learned
    # weighting for every other directional is untouched.
    if regime_gate_yield_weights and directional_id != _RESID_MOMENTUM_DIRECTIONAL_ID:
        learned_regime = {
            r: w
            for (h, d, b, r), w in regime_gate_yield_weights.items()
            if h == hypothesis and d == directional_id and b == bucket
        }
    regime_id = _pick_regime(hypothesis, regimes, rng, regime_weights, learned_regime)
    return bucket, directional_id, regime_id


def _pick_regime(
    hypothesis: str,
    regimes: tuple[str, ...],
    rng: random.Random,
    regime_weights: Mapping[str, float] | None,
    learned_regime_weights: Mapping[str, float] | None = None,
) -> str:
    """Pick the §3.5 S3 regime gate from the compatible pool.

    For the curated hypothesis (relative_value) WITH feedback ``regime_weights``,
    draw weighted toward learned-good gates (D103) — each weight floored (D067
    analogue) so no regime is starved out of exploration, and missing gates get
    the Beta prior so unseen regimes stay explorable. Every other hypothesis —
    and the cold-start (no weights) case — draws uniform via ``rng.choice``,
    byte-identical to the pre-D103 sequence (hard rule #6: weights are an
    additional input, like ``hypothesis_weights``).

    ``learned_regime_weights`` (§2 of the 2026-06-17 yield-map refresh) is the
    sliced ``{regime: component-rate}`` map for the already-chosen
    (hypothesis, directional, bucket). When present (flag on, non-relative_value)
    it COMPOSES with the base draw — ``base[r] * posterior[r]`` — modulating the
    D150 ranging-bias / uniform draw by learned yield: a sink gate (gamma_flip,
    ~0 components) is down-weighted, a minting gate (hurst) up-weighted, while a
    DEAD triple (all regimes ~equal posterior) leaves the base distribution
    intact (so D150 is refined by evidence, never silently discarded).
    relative_value is never composed (D119 — its pairs runner ignores the gate).
    None/empty preserves the base draw byte-identically (hard rule #6)."""
    if hypothesis == _REGIME_CURATED_HYPOTHESIS and regime_weights:
        weights = [
            max(regime_weights.get(r, _REGIME_WEIGHT_PRIOR_MEAN), _REGIME_EXPLORATION_FLOOR)
            for r in regimes
        ]
        return rng.choices(regimes, weights=weights, k=1)[0]
    # D150 (v20): bias mean_reversion toward its ranging R1 gates vs the sparse
    # iv_rank (which stays explorable at weight 1.0). Only engages when >1 gate is
    # present, so a single-gate registry stays byte-identical to rng.choice.
    base: list[float] | None
    if hypothesis == _MR_HYPOTHESIS and len(regimes) > 1:
        base = [_MR_RANGING_GATE_WEIGHT if r in _MR_RANGING_GATES else 1.0 for r in regimes]
    else:
        base = None
    # §2 yield-map refresh: compose the learned regime-yield onto the base, never
    # for relative_value (D119). A dead triple's posteriors are ~equal, so
    # base * posterior stays proportional to base (D150/uniform preserved); a
    # minting triple modulates by component rate (down-weights the sink gates).
    if learned_regime_weights and hypothesis != _REGIME_CURATED_HYPOTHESIS:
        base_w = base if base is not None else [1.0] * len(regimes)
        # Floor the POSTERIOR (component-rate scale, like D103), THEN multiply by
        # the base — so the floor keeps a sink gate explorable without flattening
        # the D150 base ratio (flooring the product would clobber base, since
        # base*rate ~< the floor). A dead triple's equal posteriors then leave
        # base intact; a minting triple modulates it.
        weights = [
            base_w[i]
            * max(
                learned_regime_weights.get(regimes[i], _REGIME_WEIGHT_PRIOR_MEAN),
                _REGIME_EXPLORATION_FLOOR,
            )
            for i in range(len(regimes))
        ]
        return rng.choices(regimes, weights=weights, k=1)[0]
    if base is not None:
        return rng.choices(regimes, weights=base, k=1)[0]
    return rng.choice(regimes)


def _build_selector(
    space: SearchSpace,
    hypothesis: str,
    bucket: str,
    rng: random.Random,
) -> SelectorSpec:
    """§3.5 P2 entry-side DTE + §3.5 P3 delta band (hypothesis-aware, D125).

    D074 (Phase 5): pre-D074 dte_min and dte_max were pinned to the §3.5
    P2 window's exact bounds (e.g., swing_short always emitted dte_min=14
    and dte_max=21). Now `dte_min` is sampled uniformly from the low half
    of the window and `dte_max` from the high half, guaranteeing
    `dte_min < dte_max` by construction (disjoint halves around the
    midpoint). This widens the option-selection space and produces
    distinct fingerprints (D069) for what were previously identical
    selector configs.

    Hard rule check: the §3.5 P2 validator only requires
    `window_low <= dte_min AND dte_max <= window_high`; sampling within
    the window stays valid by construction.
    """
    dte_low, dte_high = space.dte_entry_window_by_bucket[bucket]
    # D125 (v16): hypothesis-scoped P3 override (trend swing_long/mid upper
    # edges → 0.55). One rng.uniform call either way, so non-overridden draw
    # sequences are byte-identical (hard rule #6).
    delta_low, delta_high = space.delta_band_overrides_by_hypothesis.get(hypothesis, {}).get(
        bucket, space.delta_band_by_bucket[bucket]
    )
    mid = (dte_low + dte_high) // 2
    return SelectorSpec(
        delta_target=round(rng.uniform(delta_low, delta_high), 3),
        delta_tolerance=defaults.DELTA_TOLERANCE,
        dte_min=rng.randint(dte_low, mid),
        dte_max=rng.randint(mid + 1, dte_high),
        prefer_monthly_expiry=defaults.PREFER_MONTHLY_EXPIRY,
        min_open_interest=defaults.MIN_OPEN_INTEREST,
        min_volume=defaults.MIN_VOLUME,
        max_bid_ask_spread_pct=defaults.MAX_BID_ASK_SPREAD_PCT,
    )


def _build_sizer(
    space: SearchSpace,
    mode: str,
    rng: random.Random,
) -> SizerSpec:
    """§3.5 P4 ``per_trade_risk_pct`` sampling; D074 (Phase 5) adds
    mode-specific knob sampling for `fractional_kelly` and `vol_target`.

    Pre-D074, `kelly_fraction` and `vol_target_annual` were hardcoded to
    their defaults (0.25 and 0.20 respectively), so every fractional_kelly
    config used identical Kelly sizing and every vol_target config used
    identical vol targeting. D074 samples both within ranges:

      - `fractional_kelly`: kelly_fraction in [0.10, 0.50] (quarter to
        half Kelly typical). Conservative half-Kelly (0.50) at the upper
        end; quarter-Kelly (0.25) is the legacy default; 0.10 captures
        "fractional Kelly with strong conservatism."
      - `vol_target`: vol_target_annual in [0.10, 0.30] (10-30%
        annualized target). 20% is the legacy default; the range covers
        risk-on / risk-off variants without changing the sizer math.

    `fixed_risk_pct` mode keeps both at defaults (the mode doesn't read
    them).

    The grammar doesn't constrain these knobs; they're sampler-side
    variation. Hard rule #6 (determinism) preserved — rng-driven from
    the SeedHierarchy.
    """
    risk_low, risk_high = space.risk_pct_range
    kelly_fraction: float = defaults.KELLY_FRACTION
    vol_target_annual: float = defaults.VOL_TARGET_ANNUAL
    if mode == "fractional_kelly":
        kelly_fraction = round(rng.uniform(0.10, 0.50), 3)
    elif mode == "vol_target":
        vol_target_annual = round(rng.uniform(0.10, 0.30), 3)
    return SizerSpec(
        mode=mode,  # type: ignore[arg-type]
        per_trade_risk_pct=round(rng.uniform(risk_low, risk_high), 4),
        kelly_fraction=kelly_fraction,
        vol_target_annual=vol_target_annual,
    )


def _time_stop_nbars_range(
    hypothesis: str,
    directional_id: str | None,
    bucket: str | None,
) -> tuple[int, int] | None:
    """The scoped time_stop ``n_bars`` sampling box, or None for the
    param-less exit (Crucible's registry default 5).

    Resolution order matters: the capitulation directional resolves FIRST —
    its D270 box survives at BOTH buckets (the v36 scoping response vetoed
    MR-swing_mid inheritance until the v34-vs-v35 pane is read), so it must
    not fall through to the MR cell (bucket-wide since D291/v40)."""
    if directional_id == _CAPITULATION_DIRECTIONAL_ID:
        return _CAPITULATION_TIME_STOP_NBARS_RANGE
    # D291 (v40): every non-capitulation MR bucket samples the measured family
    # box U[8,12] — the param-less default-5 emission is retired for MR.
    if hypothesis == _MR_HYPOTHESIS:
        return _MR_TIME_STOP_NBARS_RANGE
    if hypothesis == "trend_continuation" and bucket == "swing_long":
        return _TREND_SWING_LONG_TIME_STOP_NBARS_RANGE
    # D290 (v39): the required ve hold, both buckets (their sweep's sweet spot).
    if hypothesis == "volatility_event":
        return _VE_TIME_STOP_NBARS_RANGE
    return None


def _pick_required_exit(
    hypothesis: str,
    directional_id: str | None,
    required_set: tuple[str, ...],
    rng: random.Random,
) -> str:
    """The §3.5 S5 required_from_set pick — uniform everywhere except the MR
    timer cell (D291/v40): non-capitulation mean_reversion draws time_stop at
    p=0.65, target_exit otherwise. The membership guard deactivates the bias
    (back to uniform) if the MR required set ever changes shape — the 0.65 is
    calibrated to exactly the {time_stop, target_exit} pair."""
    if (
        hypothesis == _MR_HYPOTHESIS
        and directional_id != _CAPITULATION_DIRECTIONAL_ID
        and set(required_set) == {"time_stop", "target_exit"}
    ):
        return "time_stop" if rng.random() < _MR_TIME_STOP_REQUIRED_PICK_P else "target_exit"
    return rng.choice(required_set)


def _optional_exit_pick_p(hypothesis: str, bucket: str | None, exit_id: str) -> float:
    """The Bernoulli p for one §3.5 S5 optional-additions exit draw.

    0.5 everywhere except cells with census evidence (D288/v38): trend
    swing_long carries time_stop at 0.43x the chandelier-only conversion, so
    its mix share drops to 0.15 — the OUTER lever composing with the v36
    U[8,10] duration prior, which the surviving draws keep."""
    if hypothesis == "trend_continuation" and bucket == "swing_long" and exit_id == "time_stop":
        return _TREND_SWING_LONG_TIME_STOP_PICK_P
    return _OPTIONAL_EXIT_PICK_P_DEFAULT


def _build_exits(
    space: SearchSpace,
    hypothesis: str,
    rng: random.Random,
    *,
    directional_id: str | None = None,
    bucket: str | None = None,
) -> tuple[ExitSpec, ...]:
    """§3.5 E1 mandatory + §3.5 S5 multi-exit composition (D071).

    v3 schema:
      - E1 mandatory exits (always included).
      - `required_always` per hypothesis (always included).
      - Exactly one from `required_from_set` (rng pick), if non-empty.
      - 0..K_MAX_OPTIONAL from `optional_additions` (each picked with p=0.5,
        truncated to K).

    Forbidden exits per S5 are simply omitted; no need to materialize the
    forbidden set. §3.5 E3 demands ``activate_after_gain_pct ≥ 0.30`` on
    any ``trailing_atr`` exit; `_exit_params` sets it here so trend
    configs are valid by construction.

    Determinism: every rng-driven decision (required-from-set pick,
    optional-additions Bernoulli) follows the seed hierarchy. Same
    (grammar_version, registry_hash, seed) produces byte-identical exits.
    """
    # D071 / Phase 4 — K_MAX_OPTIONAL is the cap on optional_additions
    # picked per config. Mirrors `K_MAX_OPTIONAL` in
    # `forge.grammar.custom_predicates`. Kept local to avoid an
    # enumeration→grammar import chain.
    _K_MAX_OPTIONAL = 2

    ids: list[str] = list(space.e1_mandatory)
    ids.extend(space.s5_required_always_by_hypothesis[hypothesis])
    required_set = space.s5_required_from_set_by_hypothesis[hypothesis]
    if required_set:
        ids.append(_pick_required_exit(hypothesis, directional_id, required_set, rng))
    optional_pool = space.s5_optional_additions_by_hypothesis[hypothesis]
    # Each optional independently picked (p=0.5 default; D288 scopes the
    # trend swing_long time_stop draw to 0.15), then truncated to K. The rng
    # consumption is identical on every path — one random() per optional —
    # so unscoped cells stay byte-identical (hard rule #6).
    picked_optional = [
        opt
        for opt in optional_pool
        if rng.random() < _optional_exit_pick_p(hypothesis, bucket, opt)
    ]
    ids.extend(picked_optional[:_K_MAX_OPTIONAL])
    # Preserve order, deduplicate (E1 / required_always / optional may overlap).
    deduped = list(dict.fromkeys(ids))
    exits = tuple(ExitSpec(id=eid, params=_exit_params(eid, rng)) for eid in deduped)
    # D270 (v31) / D282 (v36): scoped time_stop `n_bars` emission. Crucible's
    # exit registry defaults n_bars to 5, so an UNSCOPED emission would move
    # EVERY hypothesis's hold (the D169 "cross-hypothesis dirties the mr slice"
    # concern) — the range table in `_time_stop_nbars_range` names exactly the
    # cells with evidence: capitulation U[5,15] (D270, veto-frozen), MR
    # swing_mid U[8,15], trend swing_long U[8,10]. The extra randint is drawn
    # AFTER the standard exit draws and only on scoped paths — every other
    # path consumes rng identically (hard rule #6).
    nbars_range = _time_stop_nbars_range(hypothesis, directional_id, bucket)
    if nbars_range is not None and any(e.id == "time_stop" for e in exits):
        low, high = nbars_range
        n_bars = rng.randint(low, high)
        exits = tuple(
            ExitSpec(id=e.id, params={"n_bars": n_bars}) if e.id == "time_stop" else e
            for e in exits
        )
    return exits


def _directional_signal_params(
    indicator_id: str,
    rng: random.Random,
) -> dict[str, object]:
    """Threshold params for the directional signal.

    Sourced from `forge.enumeration.indicator_thresholds`, which encodes
    audited per-indicator distributions on real SPY bars (see
    `docs/INDICATOR_THRESHOLDS.md`, 2026-05-14). Prior to this audit Forge
    emitted directional threshold signals with empty params; Crucible's
    predicate then returned False on every bar, producing 0 activations
    and 100% signal_density rejection under the real feature cache.

    D068: Crucible's `pairs_convergence` template reads its CSP-style
    entry rule (pvalue / |zscore| / halflife window / lookback) from
    `signals[0].params`, NOT the generic threshold/op that drives
    activation detection. Pre-D068, every `relative_value` config ran
    with template defaults (pval<0.05, |z|>2.0, hl ∈ (5,30)) — diagnostic
    across 62 sessions x 15 pairs showed only 0.3% (3 of 930) entry-
    eligible (1,154 / 4,039 = 28.6% of submissions, all 0 trades).
    Populating these knobs widens entry eligibility to 4-9% in sweeps,
    restoring usable variation. See IMPLEMENTATION_DECISIONS.md D068.
    """
    params = sample_threshold_params(indicator_id, "directional", rng)
    if indicator_id == "pairs_zscore":
        params.update(_sample_pairs_template_params(rng))
    # D138 (v19): option_momentum's monthly-straddle coverage knob rides the
    # same params dict as its (percentile) threshold — the rv_rank / pre_earnings
    # precedent. Constant (no rng draw): min_months is a data-cleanliness floor,
    # not a strategy axis.
    if indicator_id == "option_momentum":
        params.update(_sample_option_momentum_params())
    # D264 (v27): residual_momentum's formation knobs (window/skip) are a real
    # strategy axis in Crucible's sweep bounds — sampled per config, riding the
    # same params dict as the percentile threshold.
    if indicator_id == "residual_momentum":
        params.update(_sample_residual_momentum_params(rng))
    # D270 (v31): the capitulation drop-trigger's formation knobs ride the same
    # params dict as the absolute threshold (the residual_momentum precedent).
    if indicator_id == _CAPITULATION_DIRECTIONAL_ID:
        params.update(_sample_momentum_params(rng))
    return params


def _sample_momentum_params(rng: random.Random) -> dict[str, object]:
    """D270 (v31) — Crucible `momentum` computation params for the
    capitulation trigger.

    `lookback` is the drop-formation window, the handoff's sweep axis
    (3-10 td; probe point 5). `skip` is PINNED 0: the trigger reads the raw
    trailing drop INCLUDING the most recent bar — a reversal-avoidance skip
    would erase the capitulation print the family exists to buy. Crucible's
    writer reads both from the per-config SignalSpec params
    (`Momentum.compute`: params.get("lookback"/"skip"); min_bars =
    max(lookback, skip) + 1 — verified in their code, no engine change)."""
    low, high = _CAPITULATION_LOOKBACK_RANGE
    return {"lookback": rng.randint(low, high), "skip": 0}


def _sample_residual_momentum_params(rng: random.Random) -> dict[str, object]:
    """D264 (v27) — Crucible residual_momentum computation params.

    `window` (formation lookback of the beta-stripped drift) and `skip` (most-
    recent bars excluded, the momentum-standard reversal guard) are the
    handoff's sweep axes (`FORGE_resid_vix_generation_request_2026-07-11`):
    the v27 exploration bounds were window 63-252 td, skip 0-21 td (probe
    126/21). D276 (v33): narrowed to the CONFIRMED-converter region
    (FORGE_resid_vix_region_followup_2026-07-13 — converters at window
    73/126/147, skip 7/15/21; skip < 7 never converted): window [70, 160],
    skip [7, 21]. Crucible's writer reads both from the per-config SignalSpec
    params (probe-confirmed).
    """
    w_lo, w_hi = _RESID_MOMENTUM_WINDOW_RANGE
    s_lo, s_hi = _RESID_MOMENTUM_SKIP_RANGE
    return {"window": rng.randint(w_lo, w_hi), "skip": rng.randint(s_lo, s_hi)}


def _sample_option_momentum_params() -> dict[str, object]:
    """D138 (v19) — Crucible option_momentum computation params.

    `min_months=3` (= ceil(months/2)) is the probe-audited coverage floor:
    Crucible's as-built default `min_months=months=6` requires six CONSECUTIVE
    clean reconstructed-straddle months, which collides with a ~40% honest
    per-month exit-match miss and reads 0 non-NaN bars on the most liquid names.
    At `min_months=3` every probed name clears the §5.3.3 min_activations=30
    floor (`scripts/probe_option_momentum_min_months.py`,
    `probe_results/option_momentum_min_months_sweep.json`). Crucible's writer
    reads these from the per-config SignalSpec params (probe-confirmed:
    `min_months=4/3` diverge from the `=6` default → not a global constant).
    `months=6` is the shipped formation window (Heston et al. persistence).
    """
    return {"min_months": 3, "months": 6}


def _sample_pairs_template_params(rng: random.Random) -> dict[str, object]:
    """D068 + D072 — extra keys for Crucible's pairs_convergence template.

    The template reads these via `signals[0].params.get(key, default)`;
    populating them lets the sampler vary the pairs strategy's entry
    rule across submissions.

    **D068 (2026-05-19)** shipped initial ranges that bridged template
    defaults to the "widened-aggressive" end of the sensitivity sweep
    (pvalue 0.05-0.20, zscore 0.8-2.0). Even at the aggressive end the
    diagnostic showed ~9% (asof, pair) eligibility — but the gauntlet
    cohort revealed `relative_value` configs are still **97.5% zero-
    trade** (309 / 317 in the 1,000-cohort, with ZERO configs in the
    10+ trade bucket). The wider end of D068's range still isn't fully
    sampled because uniform random splits midpoint-centered.

    **D072 (2026-05-19)** shifts the ranges toward the more permissive
    end while preserving the conservative tail:
      - `pvalue_max` 0.05-0.20 → **0.10-0.25** (the diagnostic's
        widened-aggressive setting was pval<0.20; pushing to 0.25
        admits weaker cointegration evidence).
      - `zscore_entry` 0.8-2.0 → **0.5-1.5** (template default 2.0 was
        too strict; median |z| among pvalue-passers in the diagnostic
        was 1.06, so 0.5-1.5 puts most picks BELOW that median).
      - `halflife_min` (2, 3, 5, 8) → **(1, 2, 3, 5)** (allow faster
        mean-reverters; median observed halflife was 3.32).
      - `halflife_max` (15, 30, 45, 60) → **(20, 45, 60, 90)** (allow
        slower mean-reverters; many pairs have longer halflives that
        the prior cap excluded).
      - `lookback` (126, 189, 252, 378, 504) → **(126, 189, 252, 378)**
        (drop the 504 option; longer lookback means fewer recompute
        windows in a 90-day backtest, lower effective signal turnover).

    `halflife_min` (1..5) and `halflife_max` (20..90) remain disjoint
    so `halflife_min < halflife_max` holds by construction.

    **D103 (v9, 2026-06-05)** — quality-bias. D068/D072 chased FIRING
    (zero-trade was the binding constraint then). By v8 firing is solved:
    current-grammar `relative_value` fires ~77% (was 99% zero-trade on the
    pre-v5 pairs-loading-bug cohort), but the gap shifted to per-component
    Sharpe — median traded Sharpe ~-0.085, rejects fail
    `walk_forward_sharpe_median` / `cpcv_sharpe_p25`. So the ranges tighten
    back toward the higher-Sharpe region (now affordable):
      - `pvalue_max` 0.10-0.25 -> **0.02-0.12** (require stronger
        cointegration; weak cointegration = the spread doesn't converge =
        negative Sharpe). Across current gated runs pvalue_max <= 0.14 ->
        median Sharpe +0.023 vs -0.086 above.
      - `zscore_entry` 0.5-1.5 -> **1.0-2.0** (enter on a larger divergence,
        more convergence edge). zscore_entry >= 1.0 -> +0.072 vs -0.177 below.
    `lookback` / `halflife_*` unchanged. This TIGHTENS enumeration scope
    (fewer, higher-quality firings) — the converse trade of D072, made now
    that firing no longer binds.

    **D105 (v10, 2026-06-07)** — drop `lookback` 378. Crucible's yield map:
    post-rv-fix (5fd485a) the lookback > 280 band runs and trades properly
    and is **0-for-155 decided with best WF 0.19**, vs 135/135 traded <= 280
    historically and ALL 7 rv components at lookback <= 252. One choice of
    four = ~25% of rv enumeration provably wasted. Same tightening direction
    as D103 (hard rule #4: tightenings can ship); 504 was dropped by D072 on
    the same one-step-at-a-time basis.

    Hard rule #3 check (never lower Crucible's gate): unaffected.
    Crucible's gauntlet (Sharpe, profit_factor, etc.) is the same;
    we're just biasing WHICH configs Forge submits toward the region the
    gate rewards.
    """
    return {
        "lookback": rng.choice((126, 189, 252)),
        "pvalue_max": round(rng.uniform(0.02, 0.12), 3),
        "zscore_entry": round(rng.uniform(1.0, 2.0), 3),
        "halflife_min": rng.choice((1, 2, 3, 5)),
        "halflife_max": rng.choice((20, 45, 60, 90)),
    }


def _regime_signal_params(
    hypothesis: str,
    regime_id: str,
    rng: random.Random,
    *,
    directional_id: str | None = None,
) -> dict[str, object]:
    """Threshold params for the regime_filter signal.

    Uses `forge.enumeration.indicator_thresholds.sample_threshold_params`
    for the audited per-indicator distributions. §3.5 R1's "threshold <= 50"
    constraint on iv_rank is honored by the table's `regime_range=(10, 50)`
    entry for that indicator; no special-case logic needed here.

    D270 (v31): ``directional_id`` scopes the capitulation override — the ONLY
    directional-keyed switch; every prior switch is (hypothesis, regime)-keyed.
    ``None`` (every pre-v31 call path) is byte-identical to the old signature.
    """
    params = sample_threshold_params(regime_id, "regime_filter", rng)
    if regime_id == "rv_rank":
        params.update(_sample_rv_rank_params(rng))
    # D135 (v18): the composed pre-earnings conditioner's real knobs ride the
    # same params dict as the degenerate `> 0.5` gate (the threshold table's
    # (0.5, 0.5) emission).
    if regime_id == "pre_earnings_setup":
        params.update(_sample_pre_earnings_setup_params(rng))
    # D107 (v11 / H3): mean_reversion uses the LONG-gamma side of the flip
    # (op "<", flip below spot -> dealers long gamma -> dampening -> ranging);
    # the indicator_thresholds default op ">" is the trend / short-gamma side.
    # The regime "switch" lives here -- same gate, opposite side per hypothesis.
    if hypothesis == "mean_reversion" and regime_id == "gamma_flip_distance_pct":
        params["op"] = "<"
    # D150 (v20): mean_reversion's hurst gate fires on the mean-reverting H<0.5
    # side (op "<"); the indicator_thresholds default ">" is R2's trend side.
    if hypothesis == "mean_reversion" and regime_id == "hurst":
        params["op"] = "<"
    # D270 (v31): the capitulation family's gate fires on the ELEVATED-vol
    # side — rv_rank op ">" in [50, 80], the D107 "opposite side" pattern
    # scoped one level tighter (per-DIRECTIONAL, not per-hypothesis: the
    # champion MR's calm "<" side is untouched on every other directional).
    # R1 accepts it as written (op-agnostic by the documented D107 convention).
    # The extra uniform re-draws the table's calm-side threshold into the
    # elevated band — a NEW path (momentum was never emittable pre-v31), so
    # no pre-v31 sequence consumes differently.
    if (
        hypothesis == "mean_reversion"
        and directional_id == _CAPITULATION_DIRECTIONAL_ID
        and regime_id == _CAPITULATION_REGIME_ID
    ):
        low, high = _CAPITULATION_RV_RANK_GATE_RANGE
        params["op"] = ">"
        params["threshold"] = round(rng.uniform(low, high), 4)
    # D276 (v33): the resid_vix confirmed-region gate bands, per-DIRECTIONAL
    # (the D270 pattern — every other pairing keeps the table's ranges). The
    # extra uniform re-draws the table's threshold into the converter
    # neighborhood: vix_term_slope [0.1, 0.7] absolute (converters 0.22/0.66;
    # the table's (0.0, 2.0) wastes mass above the region); hurst [0.40, 0.50]
    # PERCENTILE (the cpcv carrier's p41-p46 — the table keys op/use_percentile/
    # window, only the value moves). Sequence changes on resid paths are
    # licensed by the v33 bump.
    if directional_id == _RESID_MOMENTUM_DIRECTIONAL_ID and regime_id == "vix_term_slope":
        low, high = _RESID_VIX_GATE_RANGE
        params["threshold"] = round(rng.uniform(low, high), 4)
    if directional_id == _RESID_MOMENTUM_DIRECTIONAL_ID and regime_id == "hurst":
        low, high = _RESID_HURST_GATE_PERCENTILE_RANGE
        params["threshold"] = round(rng.uniform(low, high), 4)
    return params


def _sample_rv_rank_params(rng: random.Random) -> dict[str, object]:
    """D077 — Crucible rv_rank indicator params.

    Crucible defaults: rv_window=21, window=252. Sampling range per
    the PTS calibration handoff (PROMPT_FORGE_RV_RANK_WIRING.md).
    """
    return {
        "rv_window": rng.choice((10, 21)),
        "window": rng.choice((126, 252)),
    }


def _sample_pre_earnings_setup_params(rng: random.Random) -> dict[str, object]:
    """D135 (v18) — Crucible pre_earnings_setup composed-indicator params.

    `enter_min`/`enter_max` are CALENDAR days (days_to_earnings-native, their
    Correction note): the literature's 5-10 *trading*-day pre-announcement
    window is ~[7, 14] calendar — both choice sets center there (7 / 14)
    rather than on the shipped defaults (5 / 10, a trading-day reading).
    `rv_q` rides the component-native [0, 100] rv_rank percentile scale
    (their Correction 1: a [0, 1] draw would never fire). The documented
    effect concentrates where recent realized vol is LOW, so the range spans
    stricter-than-default (30) to slightly looser (60) around the shipped
    default 50. Live-probe check (2026-06-11): [7, 14] x q50 fires 114-152
    days/name — comfortably above the §5.3.3 min_activations floor.
    """
    return {
        "enter_min": rng.choice((5, 6, 7, 8, 9)),
        "enter_max": rng.choice((12, 13, 14, 15, 16)),
        "rv_q": round(rng.uniform(30.0, 60.0), 1),
    }


# D169 (v22) — event_passed_exit time-cut loosening ladder (Crucible fair test,
# [[D168]]; FORGE_v22_exit_timecut_fairtest_response.md §1). The exit's
# `n_bars_after_entry` was emitted as nothing → Crucible's runtime default of 3
# trading days (a hard bar-3 cut that suppresses the convex upside). Sampling the
# wider ladder gives fresh config_hashes, selected/CPCV'd from scratch, which strip
# the post-hoc in-sample optimism (Ask 3). Anchored to the exit ladder, not a
# guessed DTE: event_passed 3 < time_stop 5 < theta_cliff (mandatory cap), and 21
# reaches the theta_cliff envelope for these ~swing genomes. Vol_event-scoped →
# DISJOINT from the Lever B mr gate (one v22 bump, two slices). `time_stop` is NOT
# widened here (cross-hypothesis → would dirty the mr slice; and it masks a widened
# event_passed past 5 anyway — Ask 4) — deferred to a follow-on.
# D290 (v39): _EVENT_PASSED_NBARS_LADDER RETIRED — event_passed_exit left the ve
# schema (its only carrier). The ladder always ran Crucible's FALLBACK mode (we
# never emitted `event_indicator`), so it widened a truncation, not a hold —
# the wound behind the v21->v22 ve conversion collapse (D289).


def _exit_params(exit_id: str, rng: random.Random) -> dict[str, object]:
    """E3: ``trailing_atr`` requires ``activate_after_gain_pct ≥ 0.30``.

    D169 (v22): ``event_passed_exit`` samples ``n_bars_after_entry`` from the
    loosening ladder so a fresh cohort tests whether widening the early time-cut
    recovers the tail give-back ([[D168]]). D236 (v23, §2.7):
    ``chandelier_exit`` samples ``atr_multiplier`` ∈ [2.0, 3.0] (tighter trail =
    higher CPCV-p25). Deterministic via the seed hierarchy (the rng is the
    per-config exit rng) — hard rules #6/#8 preserved.
    """
    if exit_id == "trailing_atr":
        return {"activate_after_gain_pct": round(rng.uniform(0.30, 0.50), 2)}
    if exit_id == "chandelier_exit":
        # D236 (v23, §2.7): Crucible's chandelier template reads `atr_multiplier`
        # from the exit params (the D138 option_momentum / D169 event_passed
        # precedent — a template knob on the per-config exit). A TIGHTER trail
        # (≈2.0 vs the 3.0 default) adds +0.155 CPCV-p25 (exit_param_sweep.json);
        # sweep [2.0, 3.0] and let the gates weight tail (2.0) vs center (3.0).
        # Deterministic via the per-config exit rng (hard rules #6/#8).
        return {"atr_multiplier": round(rng.uniform(2.0, 3.0), 2)}
    return {}
