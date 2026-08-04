"""v55 (D366) — the Q46 `vix_term_slope` conditioner is RETIRED, and must stay unreachable.

Crucible closed Q46 on 2026-08-03: the double-gate was proposed as a DECORRELATION mechanism and
measures MORE correlated to the champion book, not less — median |corr| 0.3782 vs 0.3564 at
n=1,335 against 118,189 controls. Reproduced independently on our ledger before accepting:
0.3682 (n=1,172) vs 0.3520 (n=109,384). Their pinned pool-entry metric was separately shown
structurally unmeasurable (~1,768 components for ONE expected entry = 1,506 days), so the
decorrelation axis was the only one that could ever have decided it, and it decided against.

THE RETIREMENT IS A ZEROED SHARE, NOT A DELETED PATH, and both halves of that matter:

  * `_VIX_CONDITIONER_SHARE = 0.0` keeps `rng.random()` being CALLED — the draw site reads
    `_vix_conditioner_eligible(...) and rng.random() < SHARE`, and Python short-circuits, so
    removing the predicate instead would delete the rng consumption and churn the enumeration
    sequence far more than zeroing the comparison does.
  * Crucible's own caveat is that their reading is correlation to ONE reference (the retired
    champion, pinned for coverage). They wrote that the door is not nailed shut and the
    measurement is cheap to repeat against `f52a05c8`. A constant at 0.0 is a one-line revert;
    a deleted code path is not.

These tests are therefore SILENT-RE-ADMISSION guards, not documentation. The v52 precedent is
explicit: a deleted test cannot catch a cell coming back. The paired v44 file keeps its "never"
assertions for the same reason — they still hold, now vacuously, and would fire if the share
were ever restored without a decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crucible_contracts import RegistrySnapshot

from forge.enumeration import enumerate_candidates
from forge.enumeration.sampler import _VIX_CONDITIONER_ID, _VIX_CONDITIONER_SHARE
from forge.grammar import Grammar, load_grammar
from tests.fixtures.strategy_configs import minimal_registry_snapshot
from tests.unit.test_enumeration.test_v44_vix_conditioner import _v44_registry

_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "config"


def _grammar() -> Grammar:
    return load_grammar(_CONFIG_ROOT / "grammar.yaml", archive_dir=_CONFIG_ROOT / "grammar_archive")


@pytest.fixture(scope="module")
def serving_registry() -> RegistrySnapshot:
    """The registry that DOES serve vix_term_slope as a trend gate.

    Using the serving fixture is the whole point: under the minimal registry the conditioner is
    dormant anyway, so a test there would pass before the change and prove nothing. This is the
    same vacuous-fixture trap D340 caught in the v52 work.
    """
    return _v44_registry(minimal_registry_snapshot())


@pytest.fixture(scope="module")
def configs(serving_registry: RegistrySnapshot) -> list:
    return list(
        enumerate_candidates(
            grammar=_grammar(), registry=serving_registry, seed=11, max_candidates=20000
        )
    )


def _gates(config: object) -> list[str]:
    return [s.indicators[0] for s in config.signals if s.role == "regime_filter"]  # type: ignore[attr-defined]


def test_the_share_constant_is_zero() -> None:
    """The retirement itself. Pinned so restoring it cannot be a silent one-character edit."""
    assert _VIX_CONDITIONER_SHARE == 0.0


def test_no_config_carries_the_conditioner_on_a_serving_registry(configs: list) -> None:
    """The emission proof, keyed on the CONDITIONER'S SIGNAL ID.

    Keying on the indicator id instead would be wrong and this test was written that way first:
    `vix_term_slope` is legitimately drawable as an R2 PRIMARY gate, so banning the indicator
    outright contradicts the scope guard below and would have made the retirement look like it
    over-reached. The draw site appends `id="sig_vix_conditioner"`, and that is the only thing
    v55 removes.
    """
    carriers = [
        c
        for c in configs
        if any(s.id == "sig_vix_conditioner" for s in c.signals)  # type: ignore[attr-defined]
    ]
    assert not carriers, (
        f"{len(carriers)} configs still carry a sig_vix_conditioner signal "
        "— the retirement did not take"
    )


def test_no_hurst_vix_double_gate_survives(configs: list) -> None:
    """The specific pair Crucible refuted, asserted directly rather than via the id alone."""
    doubles = [c for c in configs if "hurst" in _gates(c) and _VIX_CONDITIONER_ID in _gates(c)]
    assert not doubles, f"{len(doubles)} hurst x vix double-gates survived the v55 retirement"


def test_vix_is_still_reachable_as_a_PRIMARY_regime_gate(configs: list) -> None:
    """The retirement is scoped to the CONDITIONER, not to the indicator.

    `vix_term_slope` has always been drawable as an R2 PRIMARY gate, and that path is untouched
    — Crucible refuted the double-gate as a decorrelation mechanism, not the id. A retirement
    that quietly took the primary with it would be a scope error this test exists to catch.
    """
    primaries = [
        c
        for c in configs
        if any(
            s.id == "sig_regime" and s.indicators[0] == _VIX_CONDITIONER_ID
            for s in c.signals  # type: ignore[attr-defined]
        )
    ]
    assert primaries, "vix_term_slope disappeared as a PRIMARY gate — the retirement over-reached"
