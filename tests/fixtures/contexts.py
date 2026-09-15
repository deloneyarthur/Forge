"""Builders for the value objects most unit tests need in hand: a ``FilterContext``,
a ``BatchContext``, a ``RankedCandidate``, and the two-signal ``StrategyConfig`` the
submission tests name by directional id.

WHY one home: eleven prefilter tests each rebuilt the same ``FilterContext`` with a
different fake cache, three submission/invariant tests rebuilt the same
``BatchContext``, five rebuilt a passing ``RankedCandidate``. The builders take the
one thing each test varies as a keyword and default the rest to the values the copies
shared. RNG defaults to ``SeedHierarchy(seed).rng`` (hard rule #8); the copies that used
``random.Random(hash(name))`` could not have pinned a draw, since ``hash`` is salted per
process.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from crucible_contracts import SignalSpec, StrategyConfig

from forge.core.seed import SeedHierarchy
from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import SyntheticFeatureCache
from forge.prefilters.types import FilterContext, FilterResult, PreFilterReport
from forge.ranking.types import RankedCandidate
from forge.submission.batch import BatchContext, mint_batch_id
from tests.fixtures.strategy_configs import minimal_registry_snapshot, minimal_strategy_config

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import date
    from random import Random

    from crucible_contracts import RegistrySnapshot

    from forge.prefilters.calibration import Calibration

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
PREFILTER_YAML: Path = REPO_ROOT / "config" / "prefilter.yaml"

PASSING_FILTER_RESULTS: Mapping[str, FilterResult] = MappingProxyType(
    {
        "structural_redundancy": FilterResult(passed=True, score=1.0),
        "resource_feasibility": FilterResult(passed=True, score=0.95),
        "signal_density": FilterResult(passed=True, score=0.80),
        "expected_trades": FilterResult(passed=True, score=0.70),
        "novelty": FilterResult(passed=True, score=0.90),
        "regime_exposure": FilterResult(passed=True, score=0.60),
        "permutation_test": FilterResult(passed=True, score=0.85),
    }
)


def repo_calibration() -> Calibration:
    """The committed ``config/prefilter.yaml`` — the tree is the deploy."""
    return load_calibration(PREFILTER_YAML)


def make_filter_context(
    *,
    registry: RegistrySnapshot | None = None,
    feature_cache: object | None = None,
    prior_config_hashes: frozenset[str] = frozenset(),
    prior_firing_dates: Mapping[str, frozenset[date]] | None = None,
    calibration: Calibration | None = None,
    rng_factory: Callable[[str], Random] | None = None,
    seed: int = 0,
    trade_rate_priors: Mapping[Any, Any] | None = None,
) -> FilterContext:
    """A ``FilterContext`` over the minimal registry + synthetic cache unless told otherwise."""
    return FilterContext(
        registry=registry if registry is not None else minimal_registry_snapshot(),
        feature_cache=(  # type: ignore[arg-type]
            feature_cache if feature_cache is not None else SyntheticFeatureCache(root_seed=seed)
        ),
        prior_config_hashes=prior_config_hashes,
        prior_firing_dates=dict(prior_firing_dates) if prior_firing_dates is not None else {},
        calibration=calibration if calibration is not None else repo_calibration(),
        rng_factory=rng_factory if rng_factory is not None else SeedHierarchy(seed).rng,
        trade_rate_priors=MappingProxyType(
            dict(trade_rate_priors) if trade_rate_priors is not None else {}
        ),
    )


def make_batch_context(
    *,
    seed: int = 0,
    grammar_version: str = "v1",
    registry_hash: str = "abc",
    submitted_at: datetime | None = None,
) -> BatchContext:
    """A ``BatchContext`` whose id is minted from the §13.1 triple, as production mints it."""
    return BatchContext(
        batch_id=mint_batch_id(
            seed=seed, grammar_version=grammar_version, registry_hash=registry_hash
        ),
        grammar_version=grammar_version,
        registry_hash=registry_hash,
        submitted_at=submitted_at or datetime(2026, 5, 13, 12, tzinfo=UTC),
        seed=seed,
    )


def named_config(
    name: str, directional_id: str, *, indicators: tuple[str, ...] = ("rsi_2",)
) -> StrategyConfig:
    """The minimal config with a named directional and an ``iv_rank`` regime gate."""
    return minimal_strategy_config().model_copy(
        update={
            "name": name,
            "signals": (
                SignalSpec(
                    id=directional_id,
                    type="threshold",
                    role="directional",
                    indicators=indicators,
                    params={"threshold": 30.0},
                ),
                SignalSpec(
                    id=f"iv_rg_{name}",
                    type="threshold",
                    role="regime_filter",
                    indicators=("iv_rank",),
                    params={"threshold": 50.0},
                ),
            ),
        },
    )


def passing_report(
    config: StrategyConfig,
    *,
    filter_results: Mapping[str, FilterResult] | None = None,
    composite_score: float | None = None,
) -> PreFilterReport:
    """A report that passed every filter — the seven-filter scores the copies shared."""
    kwargs: dict[str, Any] = {}
    if composite_score is not None:
        kwargs["composite_score"] = composite_score
    return PreFilterReport(
        config=config,
        passed=True,
        filter_results=(filter_results if filter_results is not None else PASSING_FILTER_RESULTS),
        diagnostic_notes=(),
        **kwargs,
    )


def make_candidate(
    config: StrategyConfig | None = None,
    *,
    composite: float = 0.7,
    prior: float = 0.0,
    filter_results: Mapping[str, FilterResult] | None = None,
    report_composite: float | None = None,
) -> RankedCandidate:
    """A ``RankedCandidate`` around a passing report of ``config`` (minimal config by default)."""
    return RankedCandidate(
        report=passing_report(
            config if config is not None else minimal_strategy_config(),
            filter_results=filter_results,
            composite_score=report_composite,
        ),
        prior_promotion_score=prior,
        composite_score=composite,
    )


__all__ = [
    "PASSING_FILTER_RESULTS",
    "PREFILTER_YAML",
    "REPO_ROOT",
    "make_batch_context",
    "make_candidate",
    "make_filter_context",
    "named_config",
    "passing_report",
    "repo_calibration",
]
