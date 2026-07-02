"""D073 / Phase 3 — Per-(indicator, role) threshold-range proposer.

Crucible's 3,829-cohort analysis identified the D031 threshold table
(`forge.enumeration.indicator_thresholds`) as never re-trained on actual
gated outcomes. Configs that produced zero trades encode "this threshold
range produces nothing on real data"; configs that produced 10+ trades
encode "this threshold range fires usefully." This module turns those
3,829+ outcomes into a learning signal.

Cross-references `gated_runs` (config_hash + trade_count + decision) with
Forge's `submissions` table (config_hash + config_json with thresholds)
to compute, per (indicator_id, role):

  - what threshold range did configs with `n_trades >= high_trade_floor`
    use? (the "fires usefully" sample)
  - what threshold range did `n_trades == 0` configs use? (the "fires
    nothing" sample)

Proposes a TIGHTENING toward the high-trade sample's [5th, 95th]
percentile when there are ≥ `min_high_trade_samples`. Only TIGHTER ranges
get written to `config/auto_tightened_thresholds.yaml`; any proposal
that would WIDEN the D031 baseline goes to `OPEN_PROPOSALS.md` for
operator review (hard rule #4).

Workflow:
  1. Operator runs `scripts/propose_threshold_tightenings.py`.
  2. Module produces a fresh `auto_tightened_thresholds.yaml` (overwrites
     prior).
  3. `forge.enumeration.indicator_thresholds.sample_threshold_params`
     reads the YAML on first call (cached) and prefers the auto-tightened
     range over D031 when one is present + tighter.
  4. Operator restarts forge.service to pick up the new ranges.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from forge.core.clock import utc_now

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import duckdb
    from crucible_contracts import GatedRun


# Default tightening parameters — tunable via function args.
_DEFAULT_HIGH_TRADE_FLOOR: int = 10
_DEFAULT_MIN_HIGH_TRADE_SAMPLES: int = 5
_DEFAULT_TIGHTENING_PERCENTILES: tuple[float, float] = (5.0, 95.0)


@dataclass(frozen=True, slots=True)
class ThresholdProposal:
    """One tightening proposal for an (indicator_id, role) pair.

    `direction` is `"tighten"` when the new range fits inside the
    baseline (auto-applicable) or `"loosen"` when it extends past it
    (requires operator review via `OPEN_PROPOSALS.md`). `baseline_*`
    are the D031-audited values; `proposed_*` are derived from the
    high-trade sample.
    """

    indicator_id: str
    role: str  # "directional" or "regime_filter"
    baseline_low: float
    baseline_high: float
    proposed_low: float
    proposed_high: float
    direction: str
    n_high_trade_samples: int
    high_trade_floor: int
    cohort_size: int

    @property
    def baseline_width(self) -> float:
        return self.baseline_high - self.baseline_low

    @property
    def proposed_width(self) -> float:
        return self.proposed_high - self.proposed_low


def _trades_by_config_hash(gated_runs: Iterable[GatedRun]) -> dict[str, int]:
    out: dict[str, int] = {}
    for gr in gated_runs:
        out[gr.run.config_hash] = int(gr.run.trade_count)
    return out


def _extract_thresholds_per_role(
    config_json: object,
) -> list[tuple[str, str, float]]:
    """Pull (indicator_id, role, threshold) triples from a config_json.

    Skips signals without a numeric `threshold` param. Robust to varying
    config_json shapes (string vs dict, missing keys).
    """
    if isinstance(config_json, str):
        try:
            cfg = json.loads(config_json)
        except (json.JSONDecodeError, ValueError):
            return []
    elif isinstance(config_json, dict):
        cfg = config_json
    else:
        return []

    out: list[tuple[str, str, float]] = []
    for sig in cfg.get("signals", []):
        if not isinstance(sig, dict):
            continue
        role = sig.get("role")
        if role not in ("directional", "regime_filter"):
            continue
        params = sig.get("params") or {}
        threshold = params.get("threshold")
        if not isinstance(threshold, (int, float)):
            continue
        for ind_id in sig.get("indicators", ()):
            if isinstance(ind_id, str):
                out.append((str(ind_id), str(role), float(threshold)))
    return out


def propose_threshold_tightenings(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    baseline_table: dict[str, tuple[float | None, float | None, float | None, float | None]],
    high_trade_floor: int = _DEFAULT_HIGH_TRADE_FLOOR,
    min_high_trade_samples: int = _DEFAULT_MIN_HIGH_TRADE_SAMPLES,
    percentiles: tuple[float, float] = _DEFAULT_TIGHTENING_PERCENTILES,
) -> list[ThresholdProposal]:
    """Compute threshold-range proposals from a gated-run cohort.

    `baseline_table` maps `indicator_id` →
    `(directional_low, directional_high, regime_low, regime_high)`.
    Any `None` means the baseline doesn't define that role's range
    (e.g., `is_skip` indicators) — those (indicator, role) pairs are
    skipped.

    Returns one `ThresholdProposal` per (indicator, role) that had
    ≥ `min_high_trade_samples` configs with `n_trades >= high_trade_floor`.
    Direction "tighten" / "loosen" is determined by comparing the
    proposed [percentile_low, percentile_high] envelope to the baseline.
    """
    trades_by_hash = _trades_by_config_hash(gated_runs)
    if not trades_by_hash:
        return []

    rows = db.execute(
        "SELECT config_hash, config_json FROM submissions WHERE config_hash IN (SELECT UNNEST(?))",
        [list(trades_by_hash.keys())],
    ).fetchall()

    # Bucket: thresholds[(indicator_id, role)] = list of (n_trades, threshold)
    samples: dict[tuple[str, str], list[tuple[int, float]]] = {}
    for config_hash, config_json in rows:
        n_trades = trades_by_hash.get(config_hash, 0)
        for ind_id, role, thr in _extract_thresholds_per_role(config_json):
            samples.setdefault((ind_id, role), []).append((n_trades, thr))

    cohort_size = len(rows)
    proposals: list[ThresholdProposal] = []
    pct_low, pct_high = percentiles
    for (ind_id, role), pairs in samples.items():
        high_trade_thresholds = [thr for n, thr in pairs if n >= high_trade_floor]
        if len(high_trade_thresholds) < min_high_trade_samples:
            continue

        # Find baseline range for this (indicator, role)
        baseline = baseline_table.get(ind_id)
        if baseline is None:
            continue
        d_low, d_high, r_low, r_high = baseline
        if role == "directional":
            b_low, b_high = d_low, d_high
        else:
            b_low, b_high = r_low, r_high
        if b_low is None or b_high is None:
            continue

        # Percentile-based proposed range from the high-trade sample
        sorted_thrs = sorted(high_trade_thresholds)
        p_low = _percentile(sorted_thrs, pct_low)
        p_high = _percentile(sorted_thrs, pct_high)
        if p_low > p_high:  # degenerate; skip
            continue

        # Tighten vs loosen determination: the proposed range fits inside
        # the baseline iff p_low >= b_low AND p_high <= b_high.
        inside_baseline = p_low >= b_low and p_high <= b_high
        direction = "tighten" if inside_baseline else "loosen"

        proposals.append(
            ThresholdProposal(
                indicator_id=ind_id,
                role=role,
                baseline_low=b_low,
                baseline_high=b_high,
                proposed_low=round(p_low, 4),
                proposed_high=round(p_high, 4),
                direction=direction,
                n_high_trade_samples=len(high_trade_thresholds),
                high_trade_floor=high_trade_floor,
                cohort_size=cohort_size,
            ),
        )
    return proposals


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Simple percentile (linear interpolation between order statistics)."""
    if not sorted_values:
        msg = "_percentile called on empty sequence"
        raise ValueError(msg)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    return float(
        statistics.quantiles(sorted_values, n=100, method="inclusive")[
            max(0, min(98, int(pct) - 1))
        ]
    )


def write_tightenings_to_yaml(
    proposals: Sequence[ThresholdProposal],
    path: Path,
    *,
    cohort_size: int,
) -> int:
    """Write `direction == "tighten"` proposals to a YAML shadow file.

    Overwrites the file each time. Includes a frontmatter block with
    cohort_size + timestamp + the high-trade-floor + sample-size
    parameters for operator transparency.

    Returns the number of tightenings written.
    """

    tightenings = [p for p in proposals if p.direction == "tighten"]

    body_lines = [
        "# D073 / Phase 3 — auto-tightened threshold ranges.",
        "# Generated by `scripts/propose_threshold_tightenings.py`.",
        "# Shadows `forge.enumeration.indicator_thresholds._INDICATOR_THRESHOLD_TABLE`",
        "# (D031). The sampler prefers these ranges when present AND tighter",
        "# than D031. Loosening proposals are written to OPEN_PROPOSALS.md",
        "# (hard rule #4 — auto-tightening only).",
        "#",
        f"# cohort_size: {cohort_size}",
        f"# generated_at: {utc_now().isoformat()}",
        f"# n_tightenings: {len(tightenings)}",
        "",
        "tightenings:",
    ]
    for p in sorted(tightenings, key=lambda x: (x.indicator_id, x.role)):
        body_lines.append(
            f"  - indicator_id: {p.indicator_id}",
        )
        body_lines.append(
            f"    role: {p.role}",
        )
        body_lines.append(
            f"    baseline_range: [{p.baseline_low}, {p.baseline_high}]",
        )
        body_lines.append(
            f"    proposed_range: [{p.proposed_low}, {p.proposed_high}]",
        )
        body_lines.append(
            f"    n_high_trade_samples: {p.n_high_trade_samples}",
        )
        body_lines.append(
            f"    high_trade_floor: {p.high_trade_floor}",
        )
        body_lines.append("")
    path.write_text("\n".join(body_lines) + "\n")
    return len(tightenings)


def write_loosening_proposals_to_open_proposals(
    proposals: Sequence[ThresholdProposal],
    path: Path,
    *,
    cohort_size: int,
) -> int:
    """Append `direction == "loosen"` proposals to OPEN_PROPOSALS.md.

    Hard rule #4: auto-loosening is forbidden. These get queued for
    operator review. Returns the number of proposals appended.
    """

    loosenings = [p for p in proposals if p.direction == "loosen"]
    if not loosenings:
        return 0

    lines = [
        "",
        "---",
        "",
        f"## D073 threshold loosening proposals — {utc_now().isoformat()}",
        "",
        f"Cohort size: {cohort_size} gated_runs. Each proposal'd auto-tighten the",
        "D031 range to fit the high-trade-sample percentile band, but the proposed",
        "envelope extends OUTSIDE D031's baseline — per hard rule #4, this requires",
        "operator review before applying.",
        "",
        "| indicator | role | baseline | proposed | high-trade n | floor |",
        "|---|---|---|---|---:|---:|",
    ]
    for p in sorted(loosenings, key=lambda x: (x.indicator_id, x.role)):
        lines.append(
            f"| {p.indicator_id} | {p.role} | "
            f"[{p.baseline_low}, {p.baseline_high}] | "
            f"[{p.proposed_low}, {p.proposed_high}] | "
            f"{p.n_high_trade_samples} | {p.high_trade_floor} |",
        )
    lines.append("")

    with path.open("a") as f:
        f.write("\n".join(lines) + "\n")
    return len(loosenings)


__all__ = [
    "ThresholdProposal",
    "propose_threshold_tightenings",
    "write_loosening_proposals_to_open_proposals",
    "write_tightenings_to_yaml",
]
