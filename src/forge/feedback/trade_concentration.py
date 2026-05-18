"""T2.5 / D046 — post-batch trade-concentration analyzer.

Pre-T2.5 the draft (`PROMPT_5_FORGE_V1_1_DRAFT.md` Enhancement 1) proposed
a *pre-filter* that rejects configs whose top-3 trades constitute >N% of
total P&L. That implementation required `context.simulated_trades` at
pre-filter time — data Forge's pre-filters don't have (Crucible has it,
inside the runner, behind hard rule #2).

T2.5 ships the same intent as a **post-batch analyzer** instead:
  1. Read gated runs from Crucible's published exports
     (`~/optbt_data/exports/gated_runs_*.json`).
  2. For each *promoted* run, compute a coarse concentration proxy from
     the aggregated metrics that the export carries (no per-trade
     ledger).
  3. Flag promoted runs whose proxy crosses the threshold as
     "concentration suspect" → operator review via OPEN_PROPOSALS.md.

**Concentration proxy** (phase 1):
The export carries `profit_factor`, `win_rate`, `avg_win`, `avg_loss`,
`n_trades`, `total_return`. None of these is "top-K trade share" exactly.
But a strategy whose P&L is dominated by a handful of outsized wins
typically has:
- High profit_factor (>>1.4 gate floor)
- Low win_rate (rare big wins)
- Few trades

So:
  `concentration_proxy = profit_factor / (n_trades * max(win_rate, 0.01))`

High proxy → likely concentrated returns. Calibrated against typical
broad-distribution strategies (profit_factor ~1.5, n_trades ~200,
win_rate ~0.5 → proxy ≈ 0.015). Suspect threshold default = 0.05
(profit_factor ~5, n_trades ~50, win_rate ~0.3 → proxy ≈ 0.33; way
above default).

This is a SCAFFOLD. The exact "top-K trade share" check from the draft
needs trade-ledger access; coordinate with Crucible (separate scope) to
either:
  (a) include `top_3_trade_pnl_share` in the export metrics, or
  (b) add a Crucible-side helper that Forge can query post-promotion.
Either way, the framework here is the consumer site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from crucible_contracts import GatedRun


@dataclass(frozen=True, slots=True)
class ConcentrationFlag:
    """One promoted run flagged as concentration-suspect."""

    run_id: str
    config_hash: str
    proxy_score: float
    profit_factor: float
    n_trades: int
    win_rate: float
    threshold: float


# Default suspect threshold. See module docstring for the calibration
# argument. Operator-overridable via `analyze_promotion_concentration`'s
# `threshold` kwarg; future yaml-config wiring lives alongside the
# other feedback knobs.
_DEFAULT_SUSPECT_THRESHOLD: float = 0.05
# Floor for win_rate in the denominator — prevents divide-by-near-zero
# blowing the proxy up on strategies with 0-1% win rates (which are
# probably broken in a different way and caught by other gates).
_WIN_RATE_FLOOR: float = 0.01


def compute_concentration_proxy(
    *,
    profit_factor: float,
    n_trades: int,
    win_rate: float,
) -> float:
    """T2.5 — coarse concentration proxy from aggregated metrics.

    `concentration_proxy = profit_factor / (n_trades * max(win_rate, FLOOR))`

    Returns 0.0 when n_trades is 0 (can't compute; treat as "not
    concentrated" rather than infinity).
    """
    if n_trades <= 0:
        return 0.0
    denom = n_trades * max(win_rate, _WIN_RATE_FLOOR)
    if denom <= 0:
        return 0.0
    return profit_factor / denom


def analyze_promotion_concentration(
    gated_runs: Iterable[GatedRun],
    *,
    threshold: float = _DEFAULT_SUSPECT_THRESHOLD,
) -> list[ConcentrationFlag]:
    """T2.5 — scan promoted runs for concentration suspects.

    Returns a list of `ConcentrationFlag`s, one per promoted run whose
    proxy exceeds ``threshold``. Empty list when no suspects. Sorted
    descending by ``proxy_score`` (most concentrated first).

    Non-promoted runs are ignored — concentration in rejected configs
    is moot (they're already rejected). The analyzer's job is to
    surface false-positives in the promotion set.
    """
    flags: list[ConcentrationFlag] = []
    for gr in gated_runs:
        if gr.decision.decision != "promote":
            continue
        metrics = gr.run.metrics or {}
        pf = float(metrics.get("profit_factor", 0.0))
        n = int(gr.run.trade_count or 0)
        wr = float(metrics.get("win_rate", 0.0))
        proxy = compute_concentration_proxy(
            profit_factor=pf, n_trades=n, win_rate=wr,
        )
        if proxy > threshold:
            flags.append(
                ConcentrationFlag(
                    run_id=str(gr.run.run_id),
                    config_hash=str(gr.run.config_hash),
                    proxy_score=proxy,
                    profit_factor=pf,
                    n_trades=n,
                    win_rate=wr,
                    threshold=threshold,
                ),
            )
    flags.sort(key=lambda f: f.proxy_score, reverse=True)
    return flags


__all__ = [
    "ConcentrationFlag",
    "analyze_promotion_concentration",
    "compute_concentration_proxy",
]
