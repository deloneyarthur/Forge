"""`prefilters.runner` is the one battery builder (Batch 6 A1): the campaign and the offline
`forge prefilter` preview used to assemble a `FilterContext` by hand, so a change to what the
battery reads had to land twice. These tests pin the contract both callers now share."""

from __future__ import annotations

from types import MappingProxyType

from forge.core.seed import SeedHierarchy
from forge.prefilters import SyntheticFeatureCache, default_filters, load_calibration
from forge.prefilters.runner import build_filter_context, run_battery_over
from tests.fixtures.strategy_configs import minimal_registry_snapshot, minimal_strategy_config

_REPO_PREFILTER_YAML = (
    __import__("pathlib").Path(__file__).resolve().parents[3] / "config" / "prefilter.yaml"
)


def _cache(registry: object, seed: int) -> SyntheticFeatureCache:
    reg = registry  # type: ignore[assignment]
    return SyntheticFeatureCache(
        root_seed=seed,
        data_history_days=reg.data_history_days,  # type: ignore[attr-defined]
        start_date=reg.data_start_date,  # type: ignore[attr-defined]
    )


def test_context_without_a_db_has_empty_priors_and_the_seeded_rng() -> None:
    registry = minimal_registry_snapshot()
    calibration = load_calibration(_REPO_PREFILTER_YAML)
    ctx = build_filter_context(
        registry=registry, seed=7, calibration=calibration, feature_cache=_cache(registry, 7)
    )
    assert ctx.prior_structural_fingerprints == frozenset()
    assert dict(ctx.trade_rate_priors) == {}
    assert isinstance(ctx.trade_rate_priors, MappingProxyType)
    # the rng factory is the seed hierarchy's: same name -> same stream as any other caller
    assert (
        ctx.rng_factory("permutation_test").random()
        == SeedHierarchy(7).rng("permutation_test").random()
    )


def test_two_callers_get_equal_contexts_for_equal_inputs() -> None:
    registry = minimal_registry_snapshot()
    calibration = load_calibration(_REPO_PREFILTER_YAML)
    a = build_filter_context(
        registry=registry, seed=3, calibration=calibration, feature_cache=_cache(registry, 3)
    )
    b = build_filter_context(
        registry=registry, seed=3, calibration=calibration, feature_cache=_cache(registry, 3)
    )
    assert a.calibration == b.calibration
    assert a.prior_structural_fingerprints == b.prior_structural_fingerprints
    assert dict(a.trade_rate_priors) == dict(b.trade_rate_priors)
    assert a.rng_factory("x").random() == b.rng_factory("x").random()


def test_run_battery_over_returns_one_report_per_config_in_order() -> None:
    registry = minimal_registry_snapshot()
    calibration = load_calibration(_REPO_PREFILTER_YAML)
    ctx = build_filter_context(
        registry=registry, seed=1, calibration=calibration, feature_cache=_cache(registry, 1)
    )
    configs = [minimal_strategy_config(), minimal_strategy_config()]
    reports = run_battery_over(configs, ctx, default_filters())
    assert [r.config.config_hash for r in reports] == [c.config_hash for c in configs]


def test_run_battery_over_prefetches_when_the_cache_can() -> None:
    registry = minimal_registry_snapshot()
    calibration = load_calibration(_REPO_PREFILTER_YAML)
    seen: list[int] = []

    class _Cache(SyntheticFeatureCache):
        def prefetch_for_batch(self, configs: object) -> None:
            seen.append(len(list(configs)))  # type: ignore[arg-type]

    cache = _Cache(
        root_seed=1,
        data_history_days=registry.data_history_days,
        start_date=registry.data_start_date,
    )
    ctx = build_filter_context(
        registry=registry, seed=1, calibration=calibration, feature_cache=cache
    )
    run_battery_over([minimal_strategy_config()], ctx)
    assert seen == [1]
