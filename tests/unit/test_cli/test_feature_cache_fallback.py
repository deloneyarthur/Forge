"""Resilience: production runs must not silently degrade to the synthetic cache.

RCA (2026-05-28): after a reboot Crucible's writer socket was not yet up and the feature-cache
builder *silently* fell back to `SyntheticFeatureCache`, whose noise-only returns make the whole
prefilter battery meaningless (0 survivors) — and could equally pass garbage. Two halves:

  1. `prefilters.factory.build_feature_cache(require_real=True)` RAISES instead of degrading.
  2. The weekly run builds its cache with `require_real=True` (no override injected): an
     unavailable writer must end the run as an ERROR record (the unit goes FAILED = the page)
     with nothing submitted, never a batch filtered against noise.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crucible_contracts import FeatureCacheUnavailableError

from forge.campaign.report import load_records
from forge.campaign.run import run_campaign
from forge.prefilters.factory import build_feature_cache
from forge.prefilters.feature_cache import SyntheticFeatureCache
from tests.fixtures.strategy_configs import minimal_registry_snapshot
from tests.unit.test_campaign.test_run import _CFG, _env


def test_falls_back_to_synthetic_when_not_required(tmp_path: Path) -> None:
    """No writer socket under `data_root` + require_real=False -> synthetic (dev/test flows)."""
    cache = build_feature_cache(
        minimal_registry_snapshot(), seed=0, require_real=False, data_root=tmp_path
    )
    assert isinstance(cache, SyntheticFeatureCache)


def test_raises_when_required_and_socket_absent(tmp_path: Path) -> None:
    """No writer socket + require_real=True -> raise, never degrade silently."""
    with pytest.raises(FeatureCacheUnavailableError):
        build_feature_cache(
            minimal_registry_snapshot(), seed=0, require_real=True, data_root=tmp_path
        )


def test_campaign_ends_as_error_and_submits_nothing_when_real_cache_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run's own factory call is `require_real=True`; when it raises, the record says
    `error`, the exception propagates (exit 1 for the unit), and the inbox stays empty."""

    def _raise(*_a: object, **_k: object) -> object:
        raise FeatureCacheUnavailableError("writer socket absent (test)")

    monkeypatch.setattr("forge.prefilters.factory.build_feature_cache", _raise)
    env = _env(tmp_path)
    with pytest.raises(FeatureCacheUnavailableError):
        run_campaign(
            forge_db_path=env["forge_db"],
            exports_dir=env["exports"],
            inbox_root=env["inbox"],
            models_dir=env["models"],
            records_dir=env["records"],
            config_root=env["config_root"],
            crucible_db=env["crucible_db"],
            cfg=_CFG,
            dry_run=False,
            skip_train=True,
            echo=lambda _line: None,
        )
    records = load_records(env["records"])
    assert records
    assert records[-1].status == "error"
    assert records[-1].submitted == 0
    assert not env["inbox"].exists() or not list(env["inbox"].glob("*.json"))
