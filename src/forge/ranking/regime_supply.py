"""§T2 regime-complement supply metric — SHADOW / telemetry-only (daemon-inert).

WHY: the assembled book's worst CPCV quartile over-populates BEAR markets only —
2.08x regime_lift on Crucible's 2026-07-15 per-block re-derivation
(`FORGE_worst_quartile_regime_label_correction_2026-07-15.md`). The original
06-13 T3a label also named RANGING (1.33x), but that half was a convex-hull CPCV
measurement artifact: corrected ranging lift is 0.90, at/below base rate, so the
complement a T2 floor would reserve is BEAR-ONLY (see
`docs/proposals/tail-aware-ranker.md` §4 T2; DESIGN.md §8.3 sanctions metric
distributions weighting the ranker). Bear remains structurally unsuppliable from
Forge (D148: no bearish stance in the grammar; bear = Crucible's `tail_leg`
overlay), so this metric's load-bearing output is the bear 0/0 line — evidence,
per batch, that a bear reservation has nothing to reserve over. Enforcing a
reservation over an empty complement just under-fills the batch (the §7
coupling risk). The ranging tally stays visible as a CELL (mean_reversion's R1
ranging thesis is label-independent) but is no longer counted as complement.

This module makes that supply VISIBLE before any enforcement: per batch it
classifies each ranked survivor's regime-bet and counts how much bear
complement the floor *could* reserve, in both the submitted batch and the
pre-filter-passed pool it was drawn from. It NEVER reshapes a batch — it is read
only over configs that were already ranked/selected, exactly like the post-submit
shadow scorer. Pure and deterministic (config-only; no feature cache, no DB).

The bear/ranging roll-up keys on the HYPOTHESIS axis, which the grammar binds to a
regime-bet via C2 (hypothesis -> directional family) + R1/R2/R3 (the regime gate):
mean_reversion is the R1/D107 long-gamma / low-vol / ranging payer; trend_continuation
the R2 short-gamma / trending payer (the dominant 76% sleeve); tail_hedge the C2
`macro` crash/bear payer. The grammar has no general bearish/short directional stance
(only the `long_short` rank mode), so bear supply is structurally scarce — which this
metric is built to surface. The finer (hypothesis x regime_gate x op) cell is carried
on each `RegimeBet` and echoed in the cell breakdown so the roll-up stays auditable
and re-bucketable from the journal without a re-run.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from crucible_contracts import StrategyConfig

# The roll-up classes, ordered for stable journal output. Class NAMES are frozen
# at their D144 spellings so journal lines stay greppable/re-bucketable across
# the 2026-07-15 label correction; semantics moved under them: `bear_complement`
# is the sole measured failure-regime complement, `ranging_complement` is a
# visible regime-bet cell that no longer counts toward the complement headline
# (corrected ranging lift 0.90 ~ base rate). `other` is everything the grammar
# does not bind to a bear/ranging payoff (honestly un-classified, not force-fit).
RegimeBetClass = Literal[
    "trending_dominant",
    "ranging_complement",
    "bear_complement",
    "other",
]

REGIME_BET_CLASSES: tuple[RegimeBetClass, ...] = (
    "trending_dominant",
    "ranging_complement",
    "bear_complement",
    "other",
)

# Hypothesis -> regime-bet roll-up. Grounded in C2 (hypothesis -> directional
# family) + R1/R2/R3 + D107 (dealer-gamma regime switch). bear_complement is the
# sole corrected failure-regime complement (2026-07-15); ranging_complement is a
# tracked cell only; the rest are not a bear/ranging bet.
_BET_CLASS_BY_HYPOTHESIS: dict[str, RegimeBetClass] = {
    "trend_continuation": "trending_dominant",  # R2: short-gamma / trending payer
    "mean_reversion": "ranging_complement",  # R1/D107: long-gamma / low-vol / ranging
    "tail_hedge": "bear_complement",  # C2 `macro`: the crash/bear payer
    "volatility_event": "other",  # R3 event-conditional vol expansion — not regime-directional
    "relative_value": "other",  # market-neutral pairs — not a directional bear/ranging bet
    "regime_arbitrage": "other",  # any-family regime switch — ambiguous
    "event_momentum": "other",  # PEAD drift — event-driven, not regime-directional
}


@dataclass(frozen=True, slots=True)
class RegimeBet:
    """One config's regime-bet: the (hypothesis x regime_gate x op) cell plus its
    bear/ranging roll-up. `regime_gate_id` / `op` are the finer axis the future T2
    enforcement floor will reserve on; `bet_class` is the supply-metric roll-up."""

    hypothesis: str
    regime_gate_id: str | None
    op: str | None
    bet_class: RegimeBetClass


def classify_regime_bet(config: StrategyConfig) -> RegimeBet:
    """Classify a config's regime-bet from its grammar structure (config-only;
    no feature cache). The roll-up keys on hypothesis; the (gate, op) cell is
    captured for the finer telemetry axis."""
    gate = next((s for s in config.signals if s.role == "regime_filter"), None)
    regime_gate_id = gate.indicators[0] if gate is not None and gate.indicators else None
    op_raw = gate.params.get("op") if gate is not None else None
    op = op_raw if isinstance(op_raw, str) else None
    bet_class = _BET_CLASS_BY_HYPOTHESIS.get(config.hypothesis, "other")
    return RegimeBet(
        hypothesis=config.hypothesis,
        regime_gate_id=regime_gate_id,
        op=op,
        bet_class=bet_class,
    )


def _tally(configs: Iterable[StrategyConfig]) -> dict[RegimeBetClass, int]:
    """Zero-filled per-class counts over a config population."""
    counts: Counter[RegimeBetClass] = Counter(classify_regime_bet(c).bet_class for c in configs)
    return {cls: counts.get(cls, 0) for cls in REGIME_BET_CLASSES}


def _pct(num: int, denom: int) -> float:
    """Percentage, 0.0 on an empty denominator (an empty batch under-fills to 0)."""
    return 100.0 * num / denom if denom else 0.0


@dataclass(frozen=True, slots=True)
class RegimeComplementSupply:
    """Per-batch regime-complement supply: per-class counts over the submitted
    batch (`selected`) and the pre-filter-passed pool it was drawn from (`pool`).
    `pool` is the reservable ceiling; `selected` is what the current ranker lets
    through. The gap between them is what a T2 floor would (try to) close."""

    selected: dict[RegimeBetClass, int]
    pool: dict[RegimeBetClass, int]

    @property
    def selected_total(self) -> int:
        return sum(self.selected.values())

    @property
    def pool_total(self) -> int:
        return sum(self.pool.values())

    @property
    def complement_selected(self) -> int:
        """Bear complement in the submitted batch (bear-only since the
        2026-07-15 label correction; ranging is a cell, not complement)."""
        return self.selected["bear_complement"]

    @property
    def complement_pool(self) -> int:
        """Bear complement available in the passed pool (the ceiling)."""
        return self.pool["bear_complement"]

    def summary_line(self) -> str:
        """The one-line journal record (greppable `regime_supply:`), leading with
        the bear-only complement supply (the load-bearing 0 — bear is the sole
        corrected crater regime), then the full per-cell selected/pool breakdown
        (ranging stays a visible cell for re-bucketing from the journal)."""
        cs, ps = self.complement_selected, self.complement_pool
        s, p = self.selected, self.pool
        cells = " ".join(
            f"{cls.split('_')[0] if cls != 'trending_dominant' else 'trending'}={s[cls]}/{p[cls]}"
            for cls in REGIME_BET_CLASSES
        )
        return (
            "regime_supply: complement(bear) "
            f"selected {cs}/{self.selected_total} ({_pct(cs, self.selected_total):.1f}%) "
            f"pool {ps}/{self.pool_total} ({_pct(ps, self.pool_total):.1f}%); "
            f"cells [{cells}]"
        )


def compute_regime_complement_supply(
    selected_configs: Iterable[StrategyConfig],
    pool_configs: Iterable[StrategyConfig],
) -> RegimeComplementSupply:
    """Tally the regime-complement supply over the submitted batch and the passed
    pool. Purely observational — the caller logs the result and threads it nowhere
    near submission, so it cannot change any submitted set."""
    return RegimeComplementSupply(
        selected=_tally(selected_configs),
        pool=_tally(pool_configs),
    )


__all__ = [
    "REGIME_BET_CLASSES",
    "RegimeBet",
    "RegimeBetClass",
    "RegimeComplementSupply",
    "classify_regime_bet",
    "compute_regime_complement_supply",
]
