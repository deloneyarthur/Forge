"""Pinned experiment-cell selection floor — data side (D287).

WHY: a grammar EXPERIMENT can be protected at generation and still starved at
SELECTION. v37/D286 fixed the resid two-arm draw (uniform coin on the pinned
vix_term_slope/hurst pool), but the learned lane then gated the vix arm out at
eligibility — the F3 P(component) model, trained on history where hurst carried
every resid config, scores vix-resid below the hard P floor (16% eligible vs
hurst's 87%), so the ranked lane submitted 14 hurst / 0 vix. Same principle as
D119 (learned weights must not bias an experimental draw) and D136 (young arms
get model-independent coverage), applied one layer up: a pinned
``(directional_indicator, regime_indicator)`` cell gets reserved batch slots
regardless of what the learned P/tail models score it.

The D136 arm floor cannot cover this: its arm key is ``(role, indicator_id)``,
``("regime_filter", "vix_term_slope")`` matured within days of v27 (≥25
verdicts), and even a young arm's reservation is not scoped to the resid pair.

PINNED BY HAND, like the sampler's D276/D286 pins: cells retire on Crucible's
relay (when the two-arm read concludes), never from learned feedback. The
selection mechanics live in ``forge.ranking.diversifier`` (the reservation
phase); this module owns the pin and cell extraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

ExperimentCell = tuple[str, str]

# The resid_vix two-arm sweep (D276/v33): vix_term_slope is the WF-conversion
# carrier and must stay populated for Crucible's arm read. Retire on their relay.
EXPERIMENT_CELLS: frozenset[ExperimentCell] = frozenset({("residual_momentum", "vix_term_slope")})

# Reserved slots per cell per batch. ~2% of a 200-config batch; sized so the
# vix arm's submitted supply is the same order as hurst's organic ~7/batch
# (~50/50-ish mix) without displacing meaningful merit-ranked volume.
EXPERIMENT_CELL_SLOTS: int = 4


def config_cell(config: StrategyConfig) -> ExperimentCell | None:
    """The (directional indicator, regime indicator) cell a config occupies.

    None when either role is absent (bare-drop configs carry no regime gate;
    relative_value carries no directional in the cell sense)."""
    directional = next((s for s in config.signals if s.role == "directional"), None)
    regime = next((s for s in config.signals if s.role == "regime_filter"), None)
    if directional is None or regime is None:
        return None
    if not directional.indicators or not regime.indicators:
        return None
    return (directional.indicators[0], regime.indicators[0])


__all__ = ["EXPERIMENT_CELLS", "EXPERIMENT_CELL_SLOTS", "ExperimentCell", "config_cell"]
