"""Config → feature vector for the learned verdict model (D132 / F1).

One extraction codepath serves training (configs rehydrated from
``submissions.config_json``) and scoring (in-memory candidates), so
train/serve skew is impossible by construction — pinned by the round-trip
invariant test. Features are config-structural only: no market data and
nothing verdict-derived (leakage), per the design
(`docs/proposals/learned-ranker.md` §4 F1).

Extraction is featurization, not validation: it must never raise on a
grammar-invalid config — the model's job includes learning what Crucible
does to configs the grammar should not have admitted.

Normalized-within-band features (delta, DTE, risk pct) read the same
source-of-truth tables the grammar predicates use, so a band change (e.g.
the v16 trend delta override) flows into the features automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from crucible_contracts import MANDATORY_EXIT_IDS

from forge.enumeration.indicator_thresholds import _INDICATOR_THRESHOLD_TABLE
from forge.enumeration.underlying_class import underlying_class
from forge.grammar.custom_predicates import _P2_ENTRY_DTE, effective_delta_band

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, SignalSpec, StrategyConfig

# Bump on ANY change to the emitted feature names or their semantics; a model
# artifact records the schema version it was trained against and the scorer
# refuses a mismatch (F3 guard).
FEATURE_SCHEMA_VERSION: int = 1

# §3.5 P4 band — the grammar predicate owns enforcement; this is only the
# normalization range for the feature.
_RISK_PCT_BAND: tuple[float, float] = (0.005, 0.02)


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """Sorted ``(name, value)`` pairs plus the schema version they obey."""

    schema_version: int
    features: tuple[tuple[str, float], ...]

    def as_dict(self) -> dict[str, float]:
        return dict(self.features)


def _normalize(value: float, lo: float, hi: float) -> float:
    """Position of ``value`` within ``[lo, hi]``, clipped to [0, 1]."""
    if hi <= lo:
        return 0.5
    return min(1.0, max(0.0, (value - lo) / (hi - lo)))


def _directional_threshold_quantile(signal: SignalSpec) -> float | None:
    """Threshold position within the sampler's directional range, if knowable.

    Percentile-emitting params (D099) carry the threshold already in [0, 1];
    native-unit thresholds project into the base table range (auto-tightening
    overrides deliberately ignored — the feature is a stable semantic, not the
    sampler's current draw window).
    """
    threshold = signal.params.get("threshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        return None
    if signal.params.get("use_percentile"):
        return min(1.0, max(0.0, float(threshold)))
    spec = _INDICATOR_THRESHOLD_TABLE.get(signal.indicators[0])
    if spec is None or spec.directional_range is None:
        return None
    lo, hi = spec.directional_range
    return _normalize(float(threshold), lo, hi)


def extract_features(config: StrategyConfig, registry: RegistrySnapshot) -> FeatureVector:
    """Featurize one config against the registry's family map."""
    family_by_id = {meta.id: meta.family for meta in registry.indicators}
    feats: dict[str, float] = {}

    feats[f"hypothesis={config.hypothesis}"] = 1.0
    feats[f"dte_bucket={config.dte_bucket}"] = 1.0
    if config.underlying:
        feats[f"underlying_class={underlying_class(config.underlying)}"] = 1.0

    combiner = config.combiner
    feats[f"combiner={combiner.type}"] = 1.0
    is_rank = combiner.type == "cross_sectional_rank"
    feats["is_rank_arm"] = 1.0 if is_rank else 0.0
    if is_rank:
        feats["rank_k"] = float(combiner.rank_k)

    regime_gates = [s for s in config.signals if s.role == "regime_filter"]
    feats["n_signals"] = float(len(config.signals))
    feats["n_regime_gates"] = float(len(regime_gates))
    feats["has_filter"] = 1.0 if any(s.role == "filter" for s in config.signals) else 0.0
    feats["has_confluence"] = 1.0 if any(s.role == "confluence" for s in config.signals) else 0.0

    directional = next((s for s in config.signals if s.role == "directional"), None)
    if directional is not None:
        dir_id = directional.indicators[0]
        feats[f"dir_id={dir_id}"] = 1.0
        feats[f"dir_family={family_by_id.get(dir_id, 'unknown')}"] = 1.0
        quantile = _directional_threshold_quantile(directional)
        if quantile is not None:
            feats["dir_threshold_q"] = quantile

    for gate in regime_gates:
        feats[f"regime_id={gate.indicators[0]}"] = 1.0

    band = effective_delta_band(config.hypothesis, config.dte_bucket)
    if band is not None:
        feats["delta_in_band"] = _normalize(config.selector.delta_target, *band)
    window = _P2_ENTRY_DTE.get(config.dte_bucket)
    if window is not None:
        lo, hi = float(window[0]), float(window[1])
        feats["dte_min_in_window"] = _normalize(float(config.selector.dte_min), lo, hi)
        feats["dte_max_in_window"] = _normalize(float(config.selector.dte_max), lo, hi)

    feats[f"sizer={config.sizer.mode}"] = 1.0
    feats["risk_pct_in_band"] = _normalize(config.sizer.per_trade_risk_pct, *_RISK_PCT_BAND)

    optional_exits = [e for e in config.exits if e.id not in MANDATORY_EXIT_IDS]
    feats["n_optional_exits"] = float(len(optional_exits))
    for exit_spec in optional_exits:
        feats[f"exit={exit_spec.id}"] = 1.0

    return FeatureVector(
        schema_version=FEATURE_SCHEMA_VERSION,
        features=tuple(sorted(feats.items())),
    )
