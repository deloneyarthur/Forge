"""Shadow-count of the permutation-test null correction. Strategy-audit P1-2.

Two flag-OFF null corrections are teed up for the §5.3.7 permutation_test
(prereg 848a1f67 `cumulative_trading`, prereg e1a43ba8 `volatility_event`
|move|). Before flipping either, the operator wants a *shadow-count*: run the
filter over the same live feature-cache data under BOTH the production null and
the corrected null, and see — per signal family — how survival actually moves.
The correction can only change the verdict AT permutation_test (the last, most
expensive filter); the set of configs that *reach* it is identical either way
(filters 1..8 don't read the null), so this is a clean within-population A/B.

This module is the pure aggregator: it takes one `ShadowNullRecord` per config
that reached the filter (its pass/fail under each null) and rolls them up into a
per-family `FamilyShadowDelta`. No feature cache, no RNG, no I/O — the CLI
(`forge shadow-null run`) does the live-cache pass and hands the records here,
so the arithmetic that drives a flip decision is unit-tested on its own.

`gained` = prod FAIL -> corr PASS (the correction rescues a real signal the
buggy single-day null wrongly killed); `lost` = prod PASS -> corr FAIL. By
construction `net_delta == pass_corr - pass_prod == gained - lost`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from forge.prefilters.calibration import Calibration

if TYPE_CHECKING:
    from collections.abc import Iterable


def cumulative_only_calibration(production: Calibration) -> Calibration:
    """The FLIP-1 arm (prereg 848a1f67): `forward_return_mode="cumulative_trading"`
    with `volatility_event_absolute_move` still OFF.

    This is the intermediate the operator lands on after flipping cumulative_trading
    but BEFORE the ve |move| flip. Keeping ve on signed returns here lets the
    shadow-count attribute the two sequenced flips apart: flip-1 = this arm vs
    production (all families); flip-2 = the fully-corrected arm vs this one (ve only,
    since |move| is family-scoped). Non-null sections are identity."""
    cumulative_pt = replace(
        production.permutation_test,
        forward_return_mode="cumulative_trading",
    )
    return replace(production, permutation_test=cumulative_pt)


def corrected_null_calibration(production: Calibration) -> Calibration:
    """The FULLY-CORRECTED arm: BOTH teed-up permutation_test null knobs ON —
    `forward_return_mode="cumulative_trading"` (prereg 848a1f67) and
    `volatility_event_absolute_move=True` (prereg e1a43ba8).

    Every other section is left identical, which is what makes the shadow-count a
    clean A/B: filters 1..8 read only the untouched sections, so the set of configs
    reaching permutation_test is the same under every calibration, and none of these
    are ever persisted — the daemon keeps loading the single_day default from
    `prefilter.yaml`.
    """
    corrected_pt = replace(
        production.permutation_test,
        forward_return_mode="cumulative_trading",
        volatility_event_absolute_move=True,
    )
    return replace(production, permutation_test=corrected_pt)


@dataclass(frozen=True, slots=True)
class ShadowNullRecord:
    """One config that REACHED permutation_test, with its verdict under each null.

    Only configs that survived filters 1..8 are recorded — a config rejected
    earlier can't have its outcome changed by the null correction, so it carries
    no signal about the flip.
    """

    hypothesis: str
    prod_passed: bool
    corr_passed: bool


@dataclass(frozen=True, slots=True)
class FamilyShadowDelta:
    """Per-family roll-up of the null-correction's effect at permutation_test."""

    hypothesis: str
    reached: int
    pass_prod: int
    pass_corr: int
    gained: int  # prod FAIL -> corr PASS
    lost: int  # prod PASS -> corr FAIL

    def __post_init__(self) -> None:
        if self.reached < 0 or self.gained < 0 or self.lost < 0:
            msg = f"FamilyShadowDelta counts must be non-negative; got {self!r}"
            raise ValueError(msg)
        if not (0 <= self.pass_prod <= self.reached) or not (0 <= self.pass_corr <= self.reached):
            msg = (
                f"FamilyShadowDelta pass counts must lie in [0, reached={self.reached}]; "
                f"got pass_prod={self.pass_prod} pass_corr={self.pass_corr}"
            )
            raise ValueError(msg)
        # PP + FP - (PP + PF) collapses to FP - PF, so pass_corr - pass_prod must
        # equal gained - lost. A mismatch means the record tally is corrupt.
        if self.pass_corr - self.pass_prod != self.gained - self.lost:
            msg = (
                "FamilyShadowDelta violates the net-delta identity "
                "(pass_corr - pass_prod == gained - lost): "
                f"{self.pass_corr} - {self.pass_prod} != {self.gained} - {self.lost}"
            )
            raise ValueError(msg)

    @property
    def net_delta(self) -> int:
        """Signed change in survivors under the corrected null (gained - lost)."""
        return self.pass_corr - self.pass_prod

    @property
    def prod_rate(self) -> float:
        return self.pass_prod / self.reached if self.reached else 0.0

    @property
    def corr_rate(self) -> float:
        return self.pass_corr / self.reached if self.reached else 0.0


@dataclass(frozen=True, slots=True)
class ShadowNullSummary:
    """All families' deltas, ordered by hypothesis for a stable, greppable report."""

    per_family: tuple[FamilyShadowDelta, ...]

    @property
    def total_reached(self) -> int:
        return sum(f.reached for f in self.per_family)

    @property
    def total_pass_prod(self) -> int:
        return sum(f.pass_prod for f in self.per_family)

    @property
    def total_pass_corr(self) -> int:
        return sum(f.pass_corr for f in self.per_family)

    @property
    def total_gained(self) -> int:
        return sum(f.gained for f in self.per_family)

    @property
    def total_lost(self) -> int:
        return sum(f.lost for f in self.per_family)

    @property
    def total_net_delta(self) -> int:
        return self.total_pass_corr - self.total_pass_prod


def summary_payload(summary: ShadowNullSummary) -> dict[str, object]:
    """Serialize a summary to JSON-ready `per_family` + `totals` dicts.

    Kept beside the dataclass (not in the CLI) so the telemetry schema is tested
    with the aggregator; the CLI wraps this with run metadata (grammar version,
    null params, timestamp)."""
    return {
        "per_family": [
            {
                "hypothesis": f.hypothesis,
                "reached": f.reached,
                "pass_prod": f.pass_prod,
                "pass_corr": f.pass_corr,
                "gained": f.gained,
                "lost": f.lost,
                "net_delta": f.net_delta,
                "prod_rate": f.prod_rate,
                "corr_rate": f.corr_rate,
            }
            for f in summary.per_family
        ],
        "totals": {
            "reached": summary.total_reached,
            "pass_prod": summary.total_pass_prod,
            "pass_corr": summary.total_pass_corr,
            "gained": summary.total_gained,
            "lost": summary.total_lost,
            "net_delta": summary.total_net_delta,
        },
    }


@dataclass(slots=True)
class _Tally:
    reached: int = 0
    pass_prod: int = 0
    pass_corr: int = 0
    gained: int = 0
    lost: int = 0


def summarize_shadow_null(records: Iterable[ShadowNullRecord]) -> ShadowNullSummary:
    """Roll per-config dual-null verdicts up into a per-family summary.

    Families are emitted in sorted `hypothesis` order so the report is
    deterministic regardless of the order configs streamed through the filter.
    """
    tallies: dict[str, _Tally] = defaultdict(_Tally)
    for rec in records:
        t = tallies[rec.hypothesis]
        t.reached += 1
        t.pass_prod += rec.prod_passed
        t.pass_corr += rec.corr_passed
        if rec.corr_passed and not rec.prod_passed:
            t.gained += 1
        elif rec.prod_passed and not rec.corr_passed:
            t.lost += 1
    per_family = tuple(
        FamilyShadowDelta(
            hypothesis=hypothesis,
            reached=t.reached,
            pass_prod=t.pass_prod,
            pass_corr=t.pass_corr,
            gained=t.gained,
            lost=t.lost,
        )
        for hypothesis, t in sorted(tallies.items())
    )
    return ShadowNullSummary(per_family=per_family)


__all__ = [
    "FamilyShadowDelta",
    "ShadowNullRecord",
    "ShadowNullSummary",
    "corrected_null_calibration",
    "cumulative_only_calibration",
    "summarize_shadow_null",
    "summary_payload",
]
