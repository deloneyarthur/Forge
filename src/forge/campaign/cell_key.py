"""The (directional, regime) selection-cell key — a leaf module on purpose.

WHY a leaf: `ranking/campaigns.py` (the registry, imported by the diversifier at
`forge.ranking` package init) and `campaign/cells.py` (the weekly run, which
imports `forge.ranking.signal_key`) both need these extractors. Housing them in
either side makes a circular import through `forge.ranking.__init__`; a module
that imports nothing from Forge cannot. Moved from `ranking/campaigns.py`
(Batch 5 prep); the registry re-exports them so every old import path holds.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

ExperimentCell = tuple[str, str]
"""(directional indicator, regime indicator) — the D287 selection-cell key."""


def config_cell(config: StrategyConfig) -> ExperimentCell | None:
    """The (directional indicator, regime indicator) cell a config occupies (the D287
    selection-cell key; moved here from `ranking/campaigns.py`, Batch 5 prep).

    None when either role is absent (bare-drop configs carry no regime gate;
    relative_value carries no directional in the cell sense). Model-based
    twin of ``config_cell_from_json`` below; keep them in lockstep."""
    directional = next((s for s in config.signals if s.role == "directional"), None)
    regime = next((s for s in config.signals if s.role == "regime_filter"), None)
    if directional is None or regime is None:
        return None
    if not directional.indicators or not regime.indicators:
        return None
    return (directional.indicators[0], regime.indicators[0])


def config_cell_from_json(config: Mapping[str, Any]) -> ExperimentCell | None:
    """Dict-shaped mirror of ``config_cell`` (reads a submissions-row
    ``config_json`` payload); the equality of the pair is pinned by test
    (test_campaigns)."""
    directional: Mapping[str, Any] | None = None
    regime: Mapping[str, Any] | None = None
    for signal in config.get("signals", ()):
        role = signal.get("role")
        if role == "directional" and directional is None:
            directional = signal
        elif role == "regime_filter" and regime is None:
            regime = signal
    if directional is None or regime is None:
        return None
    d_indicators = directional.get("indicators") or ()
    r_indicators = regime.get("indicators") or ()
    if not d_indicators or not r_indicators:
        return None
    return (d_indicators[0], r_indicators[0])


__all__ = ["ExperimentCell", "config_cell", "config_cell_from_json"]
