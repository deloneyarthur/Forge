"""Pre-filter battery calibration: load thresholds, propose adjustments.

`Calibration` mirrors `config/prefilter.yaml` as a nested frozen dataclass.
`load_calibration(path)` round-trips it. Adjustments arrive as
`AdjustmentProposal`s; the API enforces hard rule #4's spirit by exposing
`apply_tightening` (pure) and `write_loosening_proposal` (writes to
`OPEN_PROPOSALS.md`) but NOT `apply_loosening`. Phase 3 ships only the
mechanism; Phase 5 will wire the feedback-driven trigger.

See DESIGN.md §5.5, `IMPLEMENTATION_DECISIONS.md` D021 (closure D3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import yaml

Direction = Literal["tighten", "loosen"]


# ---------------------------------------------------------------------------
# Nested calibration dataclasses (one per filter + auto-tune)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SignalDensityCalibration:
    min_activations: int


@dataclass(frozen=True, slots=True)
class ExpectedTradeCountCalibration:
    min_trades: int
    # D076 / Q16 — empirical-prior knobs. Reject a config when its
    # `(hypothesis, dte_bucket, directional_family)` bucket has seen
    # ≥ `min_bucket_samples` gated runs AND the Beta-smoothed posterior
    # P(n_trades ≥ min_trades) is below `min_pass_probability`. Buckets
    # under the sample floor fall back to the legacy activations heuristic
    # so cold-start exploration is preserved. Defaults: 0.10 / 20.
    min_pass_probability: float = 0.10
    min_bucket_samples: int = 20


@dataclass(frozen=True, slots=True)
class PredictedActivationsCalibration:
    """T1.3 (PROMPT_5_FORGE_V1_1_REVISED) — floor on the directional x
    regime intersection count before submission. Stricter than
    ExpectedTradeCountCalibration because the intersection naturally
    shrinks the firing count, so a lower threshold is correct."""

    min_entries: int


@dataclass(frozen=True, slots=True)
class NoveltyCalibration:
    max_jaccard_overlap: float


@dataclass(frozen=True, slots=True)
class SignalCorrelationCalibration:
    """T2.6 (PROMPT_5_FORGE_V1_1_REVISED) — max pairwise Jaccard overlap
    of activation dates between any two signals in a single config.
    Lower = stricter (more distinct signals required)."""

    max_jaccard_overlap: float
    # P1-2b (strategy-audit PRE-H3): exclude the `regime_filter`-role context gate
    # from the pairwise comparison. A regime gate co-firing with the alpha signals it
    # gates is STRUCTURAL (its job is to restrict firing to a regime), not the
    # "two edges that are really one" redundancy this filter exists to catch —
    # measured, 94% of vol_event kills are regime-gate co-firing (median Jaccard 0.949)
    # on event-calendar gates (days_to_nfp/cpi/fomc/opex), while genuine content-pair
    # redundancy is rare + marginal. When True, only alpha-bearing signals (non-
    # regime_filter) are compared. Changes the config population → operator flip +
    # prereg (docs/tasks/feedback-change.md). False (default) → byte-identical.
    exclude_regime_filter: bool = False


@dataclass(frozen=True, slots=True)
class RegimeExposureCalibration:
    max_single_regime_concentration: float


@dataclass(frozen=True, slots=True)
class PermutationTestCalibration:
    n_permutations: int
    p_value_threshold: float
    # D075: k-day forward horizon for the return comparison. 0 = legacy
    # same-day behavior. Positive values shift activation dates by k days
    # before reading returns — addresses the systemic permutation_test
    # rejection of leading / trend-family directional signals.
    forward_horizon_days: int
    # P1-1 (strategy-audit): how the forward return is read.
    #   "single_day"        — legacy: the return on the single calendar day at T+horizon
    #                         (two bugs: point-in-time not cumulative; CALENDAR-day shift
    #                         drops weekend-adjacent samples).
    #   "cumulative_trading"— the fix: cumulative return over the next `horizon` TRADING
    #                         days (T+1..T+k via the returns index), null built on the same
    #                         statistic. Changes the config population → operator-flip +
    #                         prereg (docs/tasks/feedback-change.md). Absent → legacy.
    forward_return_mode: str = "single_day"
    # (The P1-2a `volatility_event_absolute_move` knob lived here until D301 —
    # prereg e1a43ba8 was refuted + thesis-inverted, DROPPED at D235; the flag
    # was never On in production. Git history has the path.)


@dataclass(frozen=True, slots=True)
class AutoTuneCalibration:
    enabled: bool
    min_promotion_rate: float
    max_promotion_rate: float
    adjustment_pct_per_step: float
    max_cumulative_adjustment: float


@dataclass(frozen=True, slots=True)
class Calibration:
    signal_density: SignalDensityCalibration
    expected_trade_count: ExpectedTradeCountCalibration
    predicted_activations: PredictedActivationsCalibration
    novelty: NoveltyCalibration
    signal_correlation: SignalCorrelationCalibration
    regime_exposure: RegimeExposureCalibration
    permutation_test: PermutationTestCalibration
    auto_tune: AutoTuneCalibration


# ---------------------------------------------------------------------------
# AdjustmentProposal
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdjustmentProposal:
    """A proposed pre-filter calibration change.

    Phase 3 mechanism; Phase 5 wires the feedback-driven trigger that
    actually constructs these. `apply_tightening` consumes a tighten
    proposal; loosening proposals never auto-apply — they are written to
    `OPEN_PROPOSALS.md` for operator review.
    """

    direction: Direction
    magnitude_pct: float
    reason: str

    def __post_init__(self) -> None:
        if self.direction not in ("tighten", "loosen"):
            msg = f"AdjustmentProposal.direction must be tighten|loosen; got {self.direction!r}"
            raise ValueError(msg)
        if (
            math.isnan(self.magnitude_pct)
            or math.isinf(self.magnitude_pct)
            or self.magnitude_pct <= 0.0
        ):
            msg = f"AdjustmentProposal.magnitude_pct must be > 0; got {self.magnitude_pct!r}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


_REQUIRED_TOP_KEYS = (
    "signal_density",
    "expected_trade_count",
    "predicted_activations",
    "novelty",
    "signal_correlation",
    "regime_exposure",
    "permutation_test",
    "auto_tune",
)


def _require(d: dict[str, Any], section: str, key: str) -> Any:
    if key not in d:
        msg = f"prefilter.yaml: missing required key {section}.{key}"
        raise ValueError(msg)
    return d[key]


def _validate_int(value: Any, section: str, key: str, *, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        msg = f"prefilter.yaml: {section}.{key} must be int >= {minimum}; got {value!r}"
        raise ValueError(msg)
    return value


_FORWARD_RETURN_MODES = ("single_day", "cumulative_trading")


def _validate_forward_return_mode(value: Any) -> str:
    if value not in _FORWARD_RETURN_MODES:
        msg = (
            f"prefilter.yaml: permutation_test.forward_return_mode must be one of "
            f"{_FORWARD_RETURN_MODES}; got {value!r}"
        )
        raise ValueError(msg)
    return str(value)


def _validate_unit_float(value: Any, section: str, key: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        msg = f"prefilter.yaml: {section}.{key} must be float; got {value!r}"
        raise ValueError(msg)
    f = float(value)
    if not (0.0 <= f <= 1.0):
        msg = f"prefilter.yaml: {section}.{key} must be in [0, 1]; got {f!r}"
        raise ValueError(msg)
    return f


def load_calibration(path: Path) -> Calibration:
    """Load and validate `config/prefilter.yaml` into a frozen `Calibration`.

    Raises:
        FileNotFoundError: if `path` doesn't exist.
        ValueError: on missing required keys, unknown top-level keys, or
            out-of-range values.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "prefilter" not in raw:
        msg = (
            "prefilter.yaml: top-level must be a mapping with a 'prefilter' "
            f"key; got {type(raw).__name__}"
        )
        raise ValueError(msg)

    pf = raw["prefilter"]
    if not isinstance(pf, dict):
        msg = "prefilter.yaml: 'prefilter' section must be a mapping"
        raise ValueError(msg)

    unknown = set(pf.keys()) - set(_REQUIRED_TOP_KEYS)
    if unknown:
        msg = f"prefilter.yaml: unknown top-level keys: {sorted(unknown)}"
        raise ValueError(msg)
    missing = set(_REQUIRED_TOP_KEYS) - set(pf.keys())
    if missing:
        msg = f"prefilter.yaml: missing required top-level keys: {sorted(missing)}"
        raise ValueError(msg)

    sd = pf["signal_density"]
    etc = pf["expected_trade_count"]
    pa = pf["predicted_activations"]
    no = pf["novelty"]
    sc = pf["signal_correlation"]
    re_ = pf["regime_exposure"]
    pt = pf["permutation_test"]
    at = pf["auto_tune"]

    return Calibration(
        signal_density=SignalDensityCalibration(
            min_activations=_validate_int(
                _require(sd, "signal_density", "min_activations"),
                "signal_density",
                "min_activations",
                minimum=1,
            ),
        ),
        expected_trade_count=ExpectedTradeCountCalibration(
            min_trades=_validate_int(
                _require(etc, "expected_trade_count", "min_trades"),
                "expected_trade_count",
                "min_trades",
                minimum=1,
            ),
            # D076 / Q16 — optional with defaults so existing prefilter.yaml
            # files (pre-D076) keep loading. New deploys can pin explicit
            # values; the daemon picks them up on next reload.
            min_pass_probability=_validate_unit_float(
                etc.get("min_pass_probability", 0.10),
                "expected_trade_count",
                "min_pass_probability",
            ),
            min_bucket_samples=_validate_int(
                etc.get("min_bucket_samples", 20),
                "expected_trade_count",
                "min_bucket_samples",
                minimum=1,
            ),
        ),
        predicted_activations=PredictedActivationsCalibration(
            min_entries=_validate_int(
                _require(pa, "predicted_activations", "min_entries"),
                "predicted_activations",
                "min_entries",
                minimum=1,
            ),
        ),
        novelty=NoveltyCalibration(
            max_jaccard_overlap=_validate_unit_float(
                _require(no, "novelty", "max_jaccard_overlap"),
                "novelty",
                "max_jaccard_overlap",
            ),
        ),
        signal_correlation=SignalCorrelationCalibration(
            max_jaccard_overlap=_validate_unit_float(
                _require(sc, "signal_correlation", "max_jaccard_overlap"),
                "signal_correlation",
                "max_jaccard_overlap",
            ),
            # P1-2b — optional with default so existing prefilter.yaml keeps loading
            # and an un-flipped tree is byte-identical.
            exclude_regime_filter=bool(sc.get("exclude_regime_filter", False)),
        ),
        regime_exposure=RegimeExposureCalibration(
            max_single_regime_concentration=_validate_unit_float(
                _require(re_, "regime_exposure", "max_single_regime_concentration"),
                "regime_exposure",
                "max_single_regime_concentration",
            ),
        ),
        permutation_test=PermutationTestCalibration(
            n_permutations=_validate_int(
                _require(pt, "permutation_test", "n_permutations"),
                "permutation_test",
                "n_permutations",
                minimum=1,
            ),
            p_value_threshold=_validate_unit_float(
                _require(pt, "permutation_test", "p_value_threshold"),
                "permutation_test",
                "p_value_threshold",
            ),
            forward_horizon_days=_validate_int(
                _require(pt, "permutation_test", "forward_horizon_days"),
                "permutation_test",
                "forward_horizon_days",
                minimum=0,
            ),
            forward_return_mode=_validate_forward_return_mode(
                pt.get("forward_return_mode", "single_day")
            ),
        ),
        auto_tune=AutoTuneCalibration(
            enabled=bool(_require(at, "auto_tune", "enabled")),
            min_promotion_rate=_validate_unit_float(
                _require(at, "auto_tune", "min_promotion_rate"),
                "auto_tune",
                "min_promotion_rate",
            ),
            max_promotion_rate=_validate_unit_float(
                _require(at, "auto_tune", "max_promotion_rate"),
                "auto_tune",
                "max_promotion_rate",
            ),
            adjustment_pct_per_step=_validate_unit_float(
                _require(at, "auto_tune", "adjustment_pct_per_step"),
                "auto_tune",
                "adjustment_pct_per_step",
            ),
            max_cumulative_adjustment=_validate_unit_float(
                _require(at, "auto_tune", "max_cumulative_adjustment"),
                "auto_tune",
                "max_cumulative_adjustment",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Adjustment proposal + application
# ---------------------------------------------------------------------------


def propose_adjustment(
    calibration: Calibration,
    *,
    direction: Direction,
    reason: str,
) -> AdjustmentProposal:
    """Build a proposal using the calibration's configured step size.

    The magnitude lives in `auto_tune.adjustment_pct_per_step` so changing
    the step in one place changes every proposal — there's no second
    source of truth.
    """
    return AdjustmentProposal(
        direction=direction,
        magnitude_pct=calibration.auto_tune.adjustment_pct_per_step,
        reason=reason,
    )


def apply_tightening(
    calibration: Calibration,
    proposal: AdjustmentProposal,
) -> Calibration:
    """Return a new `Calibration` with each loosen-able knob shifted in
    the stricter direction by `proposal.magnitude_pct`.

    "Stricter" means: floor thresholds go up; ceiling thresholds (including
    p-value) go down. Pure function — `calibration` is unchanged.
    """
    if proposal.direction != "tighten":
        msg = f"apply_tightening rejected loosen proposal: {proposal.reason!r}"
        raise ValueError(msg)
    step = proposal.magnitude_pct

    new_sd = replace(
        calibration.signal_density,
        min_activations=round(calibration.signal_density.min_activations * (1.0 + step)),
    )
    new_etc = replace(
        calibration.expected_trade_count,
        min_trades=round(calibration.expected_trade_count.min_trades * (1.0 + step)),
        # M-8: `min_pass_probability` is the D076 PRIMARY expected-trades gate for
        # warmed buckets (`min_trades` only governs the cold-start fallback). A
        # tighten must raise it too, else a tighten step is a near-no-op for the
        # filter §5.5 most needs. Cap < 1.0 so a tighten can't reject every bucket.
        min_pass_probability=min(
            0.95, calibration.expected_trade_count.min_pass_probability * (1.0 + step)
        ),
    )
    new_pa = replace(
        calibration.predicted_activations,
        min_entries=round(calibration.predicted_activations.min_entries * (1.0 + step)),
    )
    new_no = replace(
        calibration.novelty,
        max_jaccard_overlap=calibration.novelty.max_jaccard_overlap * (1.0 - step),
    )
    new_sc = replace(
        calibration.signal_correlation,
        max_jaccard_overlap=(calibration.signal_correlation.max_jaccard_overlap * (1.0 - step)),
    )
    new_re = replace(
        calibration.regime_exposure,
        max_single_regime_concentration=(
            calibration.regime_exposure.max_single_regime_concentration * (1.0 - step)
        ),
    )
    new_pt = replace(
        calibration.permutation_test,
        p_value_threshold=calibration.permutation_test.p_value_threshold * (1.0 - step),
    )

    return replace(
        calibration,
        signal_density=new_sd,
        expected_trade_count=new_etc,
        predicted_activations=new_pa,
        novelty=new_no,
        signal_correlation=new_sc,
        regime_exposure=new_re,
        permutation_test=new_pt,
    )


def write_loosening_proposal(proposal: AdjustmentProposal, inbox_path: Path) -> None:
    """Append a loosen proposal to `OPEN_PROPOSALS.md` for operator review.

    Structural enforcement of CLAUDE.md hard rule #4 (and the analogous
    discipline for pre-filter loosening, D021/D3): there is intentionally
    NO `apply_loosening` function on this module. Loosenings must go
    through this path -> operator decides -> human-edited yaml.
    """
    if proposal.direction != "loosen":
        msg = f"write_loosening_proposal rejected tighten proposal: {proposal.reason!r}"
        raise ValueError(msg)
    block = (
        "\n---\n"
        f"- direction: loosen\n"
        f"- magnitude_pct: {proposal.magnitude_pct}\n"
        f"- reason: {proposal.reason}\n"
    )
    with inbox_path.open("a", encoding="utf-8") as fh:
        fh.write(block)


__all__ = [
    "AdjustmentProposal",
    "AutoTuneCalibration",
    "Calibration",
    "ExpectedTradeCountCalibration",
    "NoveltyCalibration",
    "PermutationTestCalibration",
    "PredictedActivationsCalibration",
    "RegimeExposureCalibration",
    "SignalCorrelationCalibration",
    "SignalDensityCalibration",
    "apply_tightening",
    "load_calibration",
    "propose_adjustment",
    "write_loosening_proposal",
]
