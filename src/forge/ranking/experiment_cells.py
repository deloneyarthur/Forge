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
phase); this module owns cell extraction. D299: the pin's HOME moved to the
campaign registry (``forge.ranking.campaigns``) — the values here DERIVE from
it at import and are pinned byte-identical to the D287 constants by test
(test_campaigns::test_d287_pin_derives_byte_identical).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge.ranking.campaigns import (
    ExperimentCell,
    active_selection_cells,
    active_selection_slots,
)

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

# Derived from the campaign registry: every FARMING campaign with a
# selection_cell gets floored (D287: the resid_vix two-arm sweep — vix_term_slope
# is the WF-conversion carrier and must stay populated for Crucible's arm read).
EXPERIMENT_CELLS: frozenset[ExperimentCell] = active_selection_cells()

# Reserved slots per cell per batch. ~2% of a 200-config batch; sized so the
# vix arm's submitted supply is the same order as hurst's organic ~7/batch
# (~50/50-ish mix) without displacing meaningful merit-ranked volume.
EXPERIMENT_CELL_SLOTS: int = active_selection_slots()


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
