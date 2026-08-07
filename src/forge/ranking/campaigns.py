"""Campaign registry — the discover -> concentrate -> farm loop as an object (D299).

WHY: both promotions ever came through the same loop — Crucible-side discovery,
Forge verification on our own verdicts, grammar concentration, guaranteed
carriage, funnel read — and each instance was bespoke (a hand-pinned cell, a
D-entry, a watch line in STATUS.md). This module names that loop's state so:

  * the selection floor DERIVES from the registry instead of a one-off pin
    (the diversifier's hand-pin reservation phase was REMOVED 2026-08-06 with
    the pin set empty since D305 — ``active_selection_cells`` remains the
    interface a future farming campaign would wire a new floor from),
  * ``forge campaigns list`` shows what is farming and which decision read
    each campaign waits on, and
  * ``forge campaigns audit`` knows which membership signature to check for
    the D287 failure class — generation feeds a region while the learned
    lane starves it at selection (holdout share >> ranked share).

The registry is CODE, not config: campaigns change only with a D-entry plus
tests, exactly like the sampler's scoped pins (D276/D286/D291). Learned
feedback never edits it — the D119/D136/D287 principle. Membership predicates
work on the submissions table's ``config_json`` as plain dicts (never
re-validated through ``StrategyConfig``) so the audit stays readable across
contract-version drift in old rows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

CampaignStatus = Literal["candidate", "confirmed", "farming", "converted", "retired"]

ExperimentCell = tuple[str, str]
"""(directional indicator, regime indicator) — the D287 selection-cell key."""

# D287 — reserved slots per selection cell per batch (~2% of a 200-config
# batch). The registry may override per campaign, but all ACTIVE selection
# campaigns must agree (the diversifier takes one global slot count); a
# per-cell slot table is the upgrade moment if a future campaign needs it.
DEFAULT_SELECTION_SLOTS: int = 4

_ACTIVE_STATUSES: frozenset[str] = frozenset({"farming"})


@dataclass(frozen=True, slots=True)
class Campaign:
    """One confirmed-region farming effort and the decision it waits on.

    ``selection_cell`` + ``selection_slots`` describe a selection-layer floor
    (diversifier phase 0b); ``None`` means the campaign is generation-owned
    (the sampler's scoped weighting carries it, e.g. the v40 MR timer cell).
    ``member`` is an explicit membership predicate over a submissions-row
    ``config_json`` dict; when absent, membership falls back to the selection
    cell, then to the hypothesis. ``opened`` is a static ISO date recorded at
    edit time — never clock-derived (hard rule #8 keeps this module inert).
    """

    name: str
    status: CampaignStatus
    origin: str
    decision_refs: tuple[str, ...]
    opened: str
    funnel_read: str
    retire_on: str
    hypothesis: str | None = None
    selection_cell: ExperimentCell | None = None
    selection_slots: int = 0
    member: Callable[[Mapping[str, Any]], bool] | None = field(default=None)
    converted_note: str | None = None
    # Set when status flips to "retired": what closed it + what would reopen it.
    retired_note: str | None = None


def config_cell(config: StrategyConfig) -> ExperimentCell | None:
    """The (directional indicator, regime indicator) cell a config occupies.

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


def campaign_member_fn(
    campaign: Campaign,
) -> Callable[[Mapping[str, Any]], bool] | None:
    """Resolve a campaign's membership predicate over ``config_json`` dicts.

    Resolution order: explicit ``member`` > ``selection_cell`` match >
    ``hypothesis`` match > None (the campaign is not auditable from the DB;
    the audit lists it as such rather than guessing).
    """
    if campaign.member is not None:
        return campaign.member
    if campaign.selection_cell is not None:
        cell = campaign.selection_cell
        return lambda config: config_cell_from_json(config) == cell
    if campaign.hypothesis is not None:
        hypothesis = campaign.hypothesis
        return lambda config: bool(config.get("hypothesis") == hypothesis)
    return None


def validate_registry(campaigns: Sequence[Campaign]) -> None:
    """Registry hygiene — malformed records fail at import, not at ranking.

    Unique names; a selection cell requires slots >= 1; slots without a cell
    are dead weight (the diversifier would never read them) and rejected.
    """
    seen: set[str] = set()
    for campaign in campaigns:
        if campaign.name in seen:
            msg = f"duplicate campaign name: {campaign.name!r}"
            raise ValueError(msg)
        seen.add(campaign.name)
        if campaign.selection_cell is not None and campaign.selection_slots < 1:
            msg = (
                f"campaign {campaign.name!r} pins a selection_cell but "
                f"selection_slots={campaign.selection_slots}; a floor needs >= 1"
            )
            raise ValueError(msg)
        if campaign.selection_cell is None and campaign.selection_slots != 0:
            msg = (
                f"campaign {campaign.name!r} sets selection_slots without a "
                "selection_cell — slots only mean anything on a cell floor"
            )
            raise ValueError(msg)


def active_selection_cells(
    campaigns: Sequence[Campaign] | None = None,
) -> frozenset[ExperimentCell]:
    """Cells the diversifier must floor: farming campaigns with a cell."""
    source = CAMPAIGNS if campaigns is None else campaigns
    return frozenset(
        c.selection_cell
        for c in source
        if c.status in _ACTIVE_STATUSES and c.selection_cell is not None
    )


def active_selection_slots(campaigns: Sequence[Campaign] | None = None) -> int:
    """The uniform per-cell slot count for active selection campaigns.

    The diversifier takes ONE global ``experiment_cell_slots`` int; mixed
    per-campaign values would silently misallocate, so they hard-fail here.
    No active selection campaigns -> the D287 default (value unused while the
    derived cell set is empty — phase 0b is skipped on an empty set).
    """
    source = CAMPAIGNS if campaigns is None else campaigns
    slot_values = {
        c.selection_slots
        for c in source
        if c.status in _ACTIVE_STATUSES and c.selection_cell is not None
    }
    if not slot_values:
        return DEFAULT_SELECTION_SLOTS
    if len(slot_values) > 1:
        msg = (
            f"active selection campaigns disagree on slots {sorted(slot_values)}; "
            "the diversifier takes one uniform count — split deployment needs a "
            "per-cell slot table (diversifier change, own D-entry)"
        )
        raise ValueError(msg)
    return slot_values.pop()


# ---------------------------------------------------------------------------
# Seed membership predicates
# ---------------------------------------------------------------------------

# Mirrors the sampler's own v40 scoping (_pick_required_exit /
# _time_stop_nbars_range): mean_reversion excluding the capitulation
# directional, carrying a time_stop exit with n_bars in the measured box.
_MR_TIMER_NBARS_BOX: tuple[int, int] = (8, 12)
_CAPITULATION_DIRECTIONAL_ID: str = "momentum"


def _is_mr_timer_member(config: Mapping[str, Any]) -> bool:
    if config.get("hypothesis") != "mean_reversion":
        return False
    for signal in config.get("signals", ()):
        if signal.get("role") == "directional":
            indicators = signal.get("indicators") or ()
            if indicators and indicators[0] == _CAPITULATION_DIRECTIONAL_ID:
                return False
            break
    low, high = _MR_TIMER_NBARS_BOX
    for exit_spec in config.get("exits", ()):
        if exit_spec.get("id") == "time_stop":
            n_bars = exit_spec.get("params", {}).get("n_bars")
            return n_bars is not None and low <= n_bars <= high
    return False


# ---------------------------------------------------------------------------
# THE REGISTRY — edit only with a D-entry (D276/D286 pin convention)
# ---------------------------------------------------------------------------

CAMPAIGNS: tuple[Campaign, ...] = (
    Campaign(
        name="resid-vix-two-arm",
        status="retired",
        origin=(
            "Crucible probe residual_momentum x vix_term_slope (first WF-gate "
            "pass ever, 07-11) + their two-arm supply ask"
        ),
        decision_refs=("v27/D264", "v33/D276", "v37/D286", "D287", "D305"),
        opened="2026-07-11",
        funnel_read="Crucible's two-arm read (vix_term_slope vs hurst resid arms)",
        retire_on="Crucible's relay closing the two-arm read",
        selection_cell=("residual_momentum", "vix_term_slope"),
        selection_slots=4,
        retired_note=(
            "RETIRED 2026-07-20 (D305): the retire_on condition fired — "
            "FORGE_housekeeping_answers_2026-07-20 closed the two-arm read "
            "(satellite route dead on BOTH chassis: 07-16 pure_sue175 + 07-20 "
            "promoted-2-leg batteries, shortlists EMPTY; measured trade-off = "
            "decorrelation XOR the 2022 bear block). REOPENING CONDITION: a "
            "BOTH-AXES config from their 07-13 ask (vix-gate WF conversion + "
            "hurst-gate cpcv in one genome) — inexpressible under C1/R2 today "
            "(the Q46 multi-gate class); their ask remains standing. "
            "Generation-side resid supply (v33 concentrated sweep, v37 coin) "
            "is grammar-owned and untouched by this selection-floor retire."
        ),
    ),
    Campaign(
        name="mr-timer-duration",
        status="farming",
        origin=(
            "Crucible exit-duration priors relay 07-15 + combined relay 07-20 "
            "(timer-MR family CONVERTED; head 65316ca4)"
        ),
        decision_refs=("v36/D282", "v40/D291"),
        opened="2026-07-15",
        funnel_read="funnel --compare v39 v40 --hypothesis mean_reversion (~07-22/23)",
        retire_on=(
            "the v40 read attributing (or refuting) the D291 concentration; "
            "the frozen promoted spec accrues forward evidence regardless"
        ),
        hypothesis="mean_reversion",
        member=_is_mr_timer_member,
        converted_note=(
            "timer-MR leg 65316ca4 PROMOTED 2026-07-20 in the 2-leg book "
            "b36f49a4fe230f96 — second portfolio ever, first via auto-campaign"
        ),
    ),
    Campaign(
        name="ve-exit-repair",
        status="farming",
        origin="FORGE_ve_program_relay_2026-07-19 (ghost close-out + exit-schema bug)",
        decision_refs=("v39/D290",),
        opened="2026-07-19",
        funnel_read="funnel --compare v38 v39 --hypothesis volatility_event (repair cohort)",
        retire_on=(
            "the v38-vs-v39 ve read on the repair cohort; the ve >= 0.20 "
            "orthogonal floor decision re-anchors on it"
        ),
        hypothesis="volatility_event",
    ),
)

validate_registry(CAMPAIGNS)

__all__ = [
    "CAMPAIGNS",
    "DEFAULT_SELECTION_SLOTS",
    "Campaign",
    "CampaignStatus",
    "ExperimentCell",
    "active_selection_cells",
    "active_selection_slots",
    "campaign_member_fn",
    "config_cell",
    "config_cell_from_json",
    "validate_registry",
]
