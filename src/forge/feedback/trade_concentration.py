"""T2.5 / D047 — post-batch trade-concentration analyzer.

Pre-T2.5 the draft (`PROMPT_5_FORGE_V1_1_DRAFT.md` Enhancement 1) proposed
a *pre-filter* that rejects configs whose top-3 trades constitute >N% of
total P&L. That implementation required `context.simulated_trades` at
pre-filter time — data Forge's pre-filters don't have (Crucible has it,
inside the runner, behind hard rule #2).

T2.5 ships the same intent as a **post-batch analyzer** instead:
  1. Read gated runs from Crucible's published exports
     (`~/optbt_data/exports/gated_runs_*.json`).
  2. For each *promoted* run, read the `top_3_trade_pnl_share` metric
     directly from the export (D050: Crucible commit `6a57ee5` shipped
     this metric on 2026-05-18).
  3. For runs predating that Crucible commit (export still carries the
     key as None / absent), fall back to a coarse concentration proxy
     computed from `profit_factor`, `n_trades`, `win_rate` — same shape
     the framework shipped with originally.
  4. Flag promoted runs whose share / proxy crosses the threshold as
     "concentration suspect" → operator review via OPEN_PROPOSALS.md.

**The real metric** (Crucible-side, per `migrations/001_initial.sql:40`):
  `top_3_trade_pnl_share = sum(|pnl| of top-3 trades) / sum(|pnl| of all)`
Range [0.0, 1.0]; ~0.05 = broad-distribution; ~0.6 = concentrated.

**Fallback proxy** (for pre-Crucible-commit-6a57ee5 runs):
  `proxy = profit_factor / (n_trades * max(win_rate, 0.01))`
Different scale; calibrated against typical broad-distribution strategies
(PF=1.5, n=200, wr=0.5 → proxy=0.015) vs concentrated (PF=8, n=40,
wr=0.2 → proxy=1.0).

Threshold semantics: ConcentrationFlag stores whichever metric was used
(`metric_type="top_3_share"` vs `metric_type="fallback_proxy"`) so
operator can sort by the trustworthy one when reviewing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import Any

    from crucible_contracts import GatedRun


@dataclass(frozen=True, slots=True)
class ConcentrationFlag:
    """One promoted run flagged as concentration-suspect.

    `metric_type` distinguishes the trustworthy direct metric from the
    fallback proxy. Operator reviewing the OPEN_PROPOSALS surfaces should
    prioritize `metric_type="top_3_share"` flags — those are real
    measurements, not proxies.
    """

    run_id: str
    config_hash: str
    score: float
    metric_type: Literal["top_3_share", "fallback_proxy"]
    profit_factor: float
    n_trades: int
    win_rate: float
    threshold: float


# Default thresholds. The two metrics live on different scales:
# `top_3_share` (range [0,1]; 0.4 = top 3 trades carry 40%+ of P&L; the
# draft's headline threshold). `fallback_proxy` (range ~[0, many]; 0.05
# calibrated empirically — see module docstring).
_DEFAULT_TOP3_SHARE_THRESHOLD: float = 0.40
_DEFAULT_FALLBACK_PROXY_THRESHOLD: float = 0.05
_WIN_RATE_FLOOR: float = 0.01


def compute_concentration_proxy(
    *,
    profit_factor: float,
    n_trades: int,
    win_rate: float,
) -> float:
    """Fallback proxy from aggregated metrics (when `top_3_trade_pnl_share`
    isn't present in the export — pre-Crucible-commit-6a57ee5 runs).

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


def _extract_metric(
    metrics: Mapping[str, Any],
) -> tuple[float | None, Literal["top_3_share", "fallback_proxy"], float]:
    """Pick the trustworthy metric if present, else compute the proxy.

    Returns ``(score, metric_type, threshold)``. ``score`` is None only
    when both paths produce no signal (n_trades == 0 and the direct
    metric is absent/None) — caller treats as not-flagged.
    """
    top3 = metrics.get("top_3_trade_pnl_share")
    if top3 is not None:
        return (float(top3), "top_3_share", _DEFAULT_TOP3_SHARE_THRESHOLD)
    pf = float(metrics.get("profit_factor", 0.0) or 0.0)
    n = int(metrics.get("n_trades", 0) or 0)
    wr = float(metrics.get("win_rate", 0.0) or 0.0)
    proxy = compute_concentration_proxy(
        profit_factor=pf, n_trades=n, win_rate=wr,
    )
    return (proxy, "fallback_proxy", _DEFAULT_FALLBACK_PROXY_THRESHOLD)


def analyze_promotion_concentration(
    gated_runs: Iterable[GatedRun],
    *,
    top_3_share_threshold: float = _DEFAULT_TOP3_SHARE_THRESHOLD,
    fallback_proxy_threshold: float = _DEFAULT_FALLBACK_PROXY_THRESHOLD,
) -> list[ConcentrationFlag]:
    """T2.5 — scan promoted runs for concentration suspects.

    Returns a list of `ConcentrationFlag`s, sorted by score descending
    (most concentrated first). Promoted runs whose direct metric
    `top_3_trade_pnl_share` is available use the true-metric threshold;
    runs predating Crucible's 6a57ee5 commit fall back to the proxy
    threshold. The flag's `metric_type` distinguishes the two so
    downstream consumers can prioritize the trustworthy ones.

    Non-promoted runs are ignored — concentration in rejected configs is
    moot (they're already rejected). The analyzer's job is to surface
    false-positives in the promotion set.
    """
    flags: list[ConcentrationFlag] = []
    for gr in gated_runs:
        if gr.decision.decision != "promote":
            continue
        metrics = gr.run.metrics or {}
        score, metric_type, default_threshold = _extract_metric(metrics)
        if score is None:
            continue
        threshold = (
            top_3_share_threshold
            if metric_type == "top_3_share"
            else fallback_proxy_threshold
        )
        del default_threshold  # only used as a parameter-default sanity check
        if score > threshold:
            flags.append(
                ConcentrationFlag(
                    run_id=str(gr.run.run_id),
                    config_hash=str(gr.run.config_hash),
                    score=score,
                    metric_type=metric_type,
                    profit_factor=float(metrics.get("profit_factor", 0.0) or 0.0),
                    n_trades=int(metrics.get("n_trades", 0) or 0),
                    win_rate=float(metrics.get("win_rate", 0.0) or 0.0),
                    threshold=threshold,
                ),
            )
    flags.sort(key=lambda f: f.score, reverse=True)
    return flags


__all__ = [
    "ConcentrationFlag",
    "analyze_promotion_concentration",
    "compute_concentration_proxy",
]
