"""Featurize a ``StrategyConfig`` genome to the meta-king oracle's vector.

WHY this lives in Forge: Crucible *publishes* the durable-score oracle as a
plain-JSON ridge (see :mod:`forge.king.oracle`), but the featurization — the map
from a ``StrategyConfig`` to the oracle's ``feature_columns`` — must be
reproduced bit-for-bit on the Forge side so the generator can score candidate
genomes without a Crucible round-trip. This module is the exact mirror of
Crucible's ``DurableOracle`` featurizer (FORGE meta-king A3 relay §2a); it is
pinned against Crucible's published reference vectors in
``tests/unit/test_king/test_scorer.py``.

Only ``num:`` columns can be NaN (absent / non-numeric); every one-hot and
multi-hot column resolves to ``0.0`` or ``1.0``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def _as_float(value: Any) -> float:
    """Coerce ``value`` to float, or NaN when missing / non-numeric.

    Mirrors the oracle's ``num`` impute sentinel: a column that cannot be read
    as a float becomes NaN here and is median-imputed downstream by the ridge.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def featurize(genome: Mapping[str, Any], columns: Sequence[str]) -> list[float]:
    """Return the feature vector for ``genome`` over ``columns``.

    ``genome`` is a ``StrategyConfig`` rendered as a plain dict (the shape of
    ``StrategyConfig.model_dump(mode="json")`` / ``runs.strategy_json``). The
    column-name prefix encodes the rule (A3 relay §2a):

    - ``cat:<field>=<val>`` -> ``1.0`` if ``str(<field>) == val`` else ``0.0``
      (a novel category leaves every one of that field's columns at ``0.0``)
    - ``has_ind:<tok>`` -> ``1.0`` if ``tok`` in the union of every
      ``signals[].indicators``
    - ``has_exit:<tok>`` -> ``1.0`` if ``tok`` in ``{exits[].id}``
    - ``has_sigt:<tok>`` -> ``1.0`` if ``tok`` in ``{signals[].type}``
    - ``num:<name>`` -> the numeric below, or NaN if absent / non-numeric
    """
    signals = genome.get("signals") or []
    exits = genome.get("exits") or genome.get("exit_rules") or []
    combiner = genome.get("combiner") or {}
    selector = genome.get("selector") or {}
    sizer = genome.get("sizer") or {}

    indicators = {str(ind) for sig in signals for ind in (sig.get("indicators") or [])}
    roles = {str(sig["role"]) for sig in signals if sig.get("role")}
    signal_types = {str(sig["type"]) for sig in signals if sig.get("type")}
    exit_ids = {str(ex.get("id")) if isinstance(ex, dict) else str(ex) for ex in exits}

    categorical: dict[str, str] = {
        "cat:hypothesis": str(genome.get("hypothesis")),
        "cat:dte_bucket": str(genome.get("dte_bucket")),
        "cat:hyp_x_dte": f"{genome.get('hypothesis')}|{genome.get('dte_bucket')}",
        "cat:combiner_type": str(combiner.get("type")),
        "cat:direction_strategy": str(combiner.get("direction_strategy")),
        "cat:rebalance": str(combiner.get("rebalance_frequency")),
        "cat:sizer_type": str(sizer.get("type") or sizer.get("kind")),
        "cat:tier": str(genome.get("tier")),
    }
    numeric: dict[str, float] = {
        "num:underlying_is_null": 1.0 if genome.get("underlying") in (None, "null") else 0.0,
        "num:has_regime_filter": 1.0 if "regime_filter" in roles else 0.0,
        "num:has_directional": 1.0 if "directional" in roles else 0.0,
        "num:n_signals": float(len(signals)),
        "num:n_exits": float(len(exits)),
        "num:n_indicators": float(len(indicators)),
        "num:delta_target": _as_float(selector.get("delta_target")),
        "num:dte_min": _as_float(selector.get("dte_min")),
        "num:dte_max": _as_float(selector.get("dte_max")),
        "num:min_oi": _as_float(selector.get("min_open_interest")),
        "num:min_vol": _as_float(selector.get("min_volume")),
        "num:k": _as_float(combiner.get("k")),
        "num:rank_k": _as_float(combiner.get("rank_k")),
        "num:risk_frac": _as_float(sizer.get("risk_per_trade") or sizer.get("fraction")),
    }

    vector: list[float] = []
    for column in columns:
        if column.startswith("num:"):
            vector.append(numeric.get(column, math.nan))
        elif column.startswith("has_ind:"):
            vector.append(1.0 if column[len("has_ind:") :] in indicators else 0.0)
        elif column.startswith("has_exit:"):
            vector.append(1.0 if column[len("has_exit:") :] in exit_ids else 0.0)
        elif column.startswith("has_sigt:"):
            vector.append(1.0 if column[len("has_sigt:") :] in signal_types else 0.0)
        elif "=" in column:
            key, val = column.split("=", 1)
            vector.append(1.0 if categorical.get(key) == val else 0.0)
        else:
            vector.append(0.0)
    return vector
