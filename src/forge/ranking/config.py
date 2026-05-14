"""Loader for ``config/ranker.yaml`` (§10.3).

Round-trips the operator-facing YAML into a `RankerConfig` value with
the same defensive validation pattern as Phase 3's
`forge.prefilters.calibration.load_calibration`: required keys present,
unknown keys rejected, types checked, ranges enforced. The
`RankerWeights.__post_init__` sum-to-1.0 invariant surfaces here
when component values drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forge.ranking.types import DiversificationConfig, RankerConfig, RankerWeights

_REQUIRED_WEIGHT_KEYS = (
    "signal_density",
    "novelty",
    "regime_diversity",
    "permutation_test",
    "prior_promotion_proximity",
)

_REQUIRED_DIVERSIFICATION_KEYS = ("method", "similarity_metric")

_VALID_METHODS = ("greedy",)
_VALID_SIMILARITY_METRICS = ("jaccard",)

_REQUIRED_RANKER_KEYS = ("weights", "diversification")


def _require_mapping(value: Any, section: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        msg = f"ranker.yaml: {section} must be a mapping; got {type(value).__name__}"
        raise ValueError(msg)
    return value


def _validate_float(value: Any, section: str, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        msg = f"ranker.yaml: {section}.{key} must be float; got {value!r}"
        raise ValueError(msg)
    return float(value)


def _parse_weights(raw: dict[str, Any]) -> RankerWeights:
    unknown = set(raw.keys()) - set(_REQUIRED_WEIGHT_KEYS)
    if unknown:
        msg = f"ranker.yaml: unknown weight keys: {sorted(unknown)}"
        raise ValueError(msg)
    missing = set(_REQUIRED_WEIGHT_KEYS) - set(raw.keys())
    if missing:
        msg = f"ranker.yaml: missing weight keys: {sorted(missing)}"
        raise ValueError(msg)
    return RankerWeights(
        signal_density=_validate_float(raw["signal_density"], "weights", "signal_density"),
        novelty=_validate_float(raw["novelty"], "weights", "novelty"),
        regime_diversity=_validate_float(raw["regime_diversity"], "weights", "regime_diversity"),
        permutation_test=_validate_float(raw["permutation_test"], "weights", "permutation_test"),
        prior_promotion_proximity=_validate_float(
            raw["prior_promotion_proximity"],
            "weights",
            "prior_promotion_proximity",
        ),
    )


def _parse_diversification(raw: dict[str, Any]) -> DiversificationConfig:
    unknown = set(raw.keys()) - set(_REQUIRED_DIVERSIFICATION_KEYS)
    if unknown:
        msg = f"ranker.yaml: unknown diversification keys: {sorted(unknown)}"
        raise ValueError(msg)
    missing = set(_REQUIRED_DIVERSIFICATION_KEYS) - set(raw.keys())
    if missing:
        msg = f"ranker.yaml: missing diversification keys: {sorted(missing)}"
        raise ValueError(msg)
    method = raw["method"]
    if method not in _VALID_METHODS:
        msg = (
            f"ranker.yaml: diversification.method must be one of "
            f"{list(_VALID_METHODS)}; got {method!r}"
        )
        raise ValueError(msg)
    similarity = raw["similarity_metric"]
    if similarity not in _VALID_SIMILARITY_METRICS:
        msg = (
            f"ranker.yaml: diversification.similarity_metric must be one of "
            f"{list(_VALID_SIMILARITY_METRICS)}; got {similarity!r}"
        )
        raise ValueError(msg)
    return DiversificationConfig(method=method, similarity_metric=similarity)


def load_ranker_config(path: Path) -> RankerConfig:
    """Load and validate ``config/ranker.yaml`` into a `RankerConfig`.

    Raises:
        FileNotFoundError: if `path` doesn't exist.
        ValueError: on missing required keys, unknown keys, range
            violations, or weights that don't sum to 1.0.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "ranker" not in raw:
        msg = (
            "ranker.yaml: top-level must be a mapping with a 'ranker' "
            f"key; got {type(raw).__name__}"
        )
        raise ValueError(msg)

    ranker = _require_mapping(raw["ranker"], "ranker")
    unknown = set(ranker.keys()) - set(_REQUIRED_RANKER_KEYS)
    if unknown:
        msg = f"ranker.yaml: unknown ranker keys: {sorted(unknown)}"
        raise ValueError(msg)
    missing = set(_REQUIRED_RANKER_KEYS) - set(ranker.keys())
    for key in missing:
        msg = f"ranker.yaml: missing required key 'ranker.{key}'"
        raise ValueError(msg)

    weights = _parse_weights(_require_mapping(ranker["weights"], "ranker.weights"))
    diversification = _parse_diversification(
        _require_mapping(ranker["diversification"], "ranker.diversification"),
    )
    return RankerConfig(weights=weights, diversification=diversification)


__all__ = ["load_ranker_config"]
