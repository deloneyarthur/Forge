"""Steps 5 and 8-11 of the weekly run: population, dark cells, campaign selection, battery,
rank (Batch 6 A4 split from run.py).

WHY a module: this is the part that must stay byte-identical under hard rule #6 -- the
unstratified v55 draw, the rejection-sample to cells, the battery order, the in-cell scorer.
`tests/invariants/test_enumeration_inputs_reach_the_battery.py` reads THIS file (D352)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from forge.campaign.triggers import (
    cells_with_indicators,
    exploration_rotation,
)
from forge.campaign.types import (
    CampaignConfig,
    CampaignSpec,
    CellKey,
    CellStats,
)

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar.models import Grammar
    from forge.prefilters.types import PreFilterReport
    from forge.ranking.types import RankedCandidate


# ---------------------------------------------------------------------------
# steps 5, 8 — population, selection
# ---------------------------------------------------------------------------


def enumerate_population(
    grammar: Grammar,
    registry: RegistrySnapshot,
    *,
    seed: int,
    attempts: int,
    exports_dir: Path,
    now: datetime,
    min_hypothesis_fraction: float,
) -> list[StrategyConfig]:
    """The unchanged cold-start v55 draw, no learned weights (the goldens' population).

    `below_inception` and `refutation_effects` are the loop's structural inputs
    (both fold into `enumeration_inputs_hash`), passed exactly as the loop passes
    them; every weight map stays None. A capped iterator returns what it yielded."""
    from forge.enumeration import (  # noqa: PLC0415
        EnumerationCapped,
        enumerate_candidates,
        resolve_effects,
    )
    from forge.enumeration.chain_inception import underlyings_below_inception  # noqa: PLC0415

    out: list[StrategyConfig] = []
    try:
        for config in enumerate_candidates(
            grammar,
            registry,
            seed=seed,
            max_candidates=attempts,
            below_inception=underlyings_below_inception(now.date(), exports_dir=exports_dir),
            refutation_effects=resolve_effects(exports_dir=exports_dir),
            min_hypothesis_fraction=min_hypothesis_fraction,
        ):
            out.append(config)
    except EnumerationCapped:
        pass
    return out


def dark_cells(
    sample_cells: Iterable[CellKey], stats: Mapping[CellKey, CellStats]
) -> frozenset[CellKey]:
    """Cells the population can produce that Forge has never submitted or judged."""
    dark: set[CellKey] = set()
    for cell in sample_cells:
        st = stats.get(cell)
        if st is None or (st.submitted == 0 and st.decided == 0):
            dark.add(cell)
    return frozenset(dark)


def _claim_rotation(
    sample: Sequence[tuple[StrategyConfig, CellKey]],
    targets: set[CellKey],
    claimed: set[str],
    *,
    cap: int,
    iso_week: str,
) -> list[tuple[StrategyConfig, CellKey]]:
    """T5: walk cells in the weekly rotation so the first-budget cells win deterministically."""
    by_cell: dict[CellKey, list[tuple[StrategyConfig, CellKey]]] = {}
    for config, cell in sample:
        if cell in targets and config.config_hash not in claimed:
            by_cell.setdefault(cell, []).append((config, cell))
    chosen: list[tuple[StrategyConfig, CellKey]] = []
    for cell in exploration_rotation(targets, iso_week):
        for item in by_cell.get(cell, ()):
            if len(chosen) >= cap:
                return chosen
            chosen.append(item)
    return chosen


def _claim_in_order(
    sample: Sequence[tuple[StrategyConfig, CellKey]],
    targets: set[CellKey],
    claimed: set[str],
    *,
    cap: int,
) -> list[tuple[StrategyConfig, CellKey]]:
    chosen: list[tuple[StrategyConfig, CellKey]] = []
    for config, cell in sample:
        if len(chosen) >= cap:
            break
        if cell in targets and config.config_hash not in claimed:
            chosen.append((config, cell))
    return chosen


def select_for_campaigns(
    campaigns: Sequence[CampaignSpec],
    sample: Sequence[tuple[StrategyConfig, CellKey]],
    *,
    cfg: CampaignConfig,
    iso_week: str,
) -> dict[int, list[tuple[StrategyConfig, CellKey]]]:
    """Rejection-sample the population to each campaign's cells, priority order.

    A config belongs to the first campaign that claims it. T5 walks its cells in
    the weekly rotation order so the first-budget cells win deterministically;
    every other campaign keeps enumeration order. Each campaign keeps at most
    ``budget * oversample_factor`` so the battery and gate have headroom."""
    claimed: set[str] = set()
    picked: dict[int, list[tuple[StrategyConfig, CellKey]]] = {}
    for idx, campaign in enumerate(campaigns):
        cap = campaign.budget * cfg.oversample_factor
        targets = set(campaign.cells)
        if campaign.indicator_ids:
            targets |= cells_with_indicators((c for _, c in sample), campaign.indicator_ids)
        if campaign.trigger == "exploration_floor":
            chosen = _claim_rotation(sample, targets, claimed, cap=cap, iso_week=iso_week)
        else:
            chosen = _claim_in_order(sample, targets, claimed, cap=cap)
        claimed.update(c.config_hash for c, _ in chosen)
        picked[idx] = chosen
    return picked


# ---------------------------------------------------------------------------
# steps 9-11 — battery, gate, rank
# ---------------------------------------------------------------------------


def _run_battery(
    configs: Sequence[StrategyConfig],
    *,
    registry: RegistrySnapshot,
    seed: int,
    forge_db_path: Path,
    config_root: Path,
    feature_cache: object,
) -> list[PreFilterReport]:
    """The battery over the kept candidates, built by the one shared runner (Batch 6 A1)."""
    from forge.prefilters.calibration import load_calibration  # noqa: PLC0415
    from forge.prefilters.runner import build_filter_context, run_battery_over  # noqa: PLC0415

    ctx = build_filter_context(
        registry=registry,
        seed=seed,
        calibration=load_calibration(config_root / "prefilter.yaml"),
        feature_cache=feature_cache,
        forge_db_path=forge_db_path,
    )
    return run_battery_over(configs, ctx)


def _scorer(
    models_dir: Path, registry: RegistrySnapshot, notes: list[str]
) -> Callable[[StrategyConfig], tuple[float, float]]:
    """(P(component), composite) per config from the newest artifacts; 0.0 without one.

    Never a Jaccard prior: `promoted_strategies` is retiring and read `[]` since 07-06
    (D409), so the old fallback was a zero prior wearing a name."""
    from forge.ranking.features import extract_features  # noqa: PLC0415
    from forge.ranking.model import (  # noqa: PLC0415
        QUALITY_LANE_TARGET,
        load_latest_model,
        load_latest_robustness_model,
        robustness_tail_norm,
        score_features,
    )

    verdict = load_latest_model(models_dir)
    robust = (
        load_latest_robustness_model(models_dir, target=QUALITY_LANE_TARGET)
        if verdict is not None
        else None
    )
    if verdict is None:
        notes.append("rank: no verdict model artifact; scores are 0.0 (enumeration order)")
    elif robust is None:
        notes.append(f"rank: verdict model {verdict.model_id}, no robustness model")
    else:
        notes.append(f"rank: verdict model {verdict.model_id} x tail_norm {robust.model_id}")

    def _score(config: StrategyConfig) -> tuple[float, float]:
        if verdict is None:
            return (0.0, 0.0)
        feats = extract_features(config, registry).as_dict()
        p = min(1.0, max(0.0, score_features(verdict, feats)))
        if robust is None:
            return (p, p)
        return (p, min(1.0, max(0.0, p * robustness_tail_norm(robust, feats))))

    return _score


def _rank(
    survivors: Sequence[tuple[PreFilterReport, CellKey, int]],
    campaigns: Sequence[CampaignSpec],
    score: Callable[[StrategyConfig], tuple[float, float]],
) -> dict[int, list[RankedCandidate]]:
    """Top `budget` per campaign by score; ties keep enumeration order (stable sort)."""
    from forge.ranking.types import RankedCandidate  # noqa: PLC0415

    scored: dict[int, list[tuple[float, RankedCandidate]]] = {}
    for report, _cell, idx in survivors:
        p, composite = score(report.config)
        cand = RankedCandidate(report=report, prior_promotion_score=p, composite_score=composite)
        scored.setdefault(idx, []).append((composite, cand))
    out: dict[int, list[RankedCandidate]] = {}
    for idx, items in scored.items():
        ordered = sorted(items, key=lambda t: -t[0])
        out[idx] = [cand for _, cand in ordered[: campaigns[idx].budget]]
    return out
