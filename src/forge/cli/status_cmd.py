"""`forge status` — is the stream getting better at promoting? (ops-sprint item 4)

The pipeline's whole purpose is for Forge's submission stream to become *more likely to
promote over time*. The daily ranker-eval timer already distils that into two curated
"clocks" under `~/forge_data/ranker_eval/`:

  * **F3 verdict ranker** (`streak.jsonl`) — how much better the learned P(component)
    model ranks than the incumbent §6.2 composite (AUC margin), and the trailing
    consecutive-PASS streak toward the F3 criterion.
  * **§8.6 wf_p25 tail** (`robustness_streak_wfp25.jsonl`) — Spearman of the quality
    lane's predicted WF-floor against the realized worst-quartile gate.
  * **re-wire gate→tail** (`rewire_streak_wfp25.jsonl`) — the shadow clock for the
    gate-then-tail re-wire candidate (docs/proposals/quality-lane-rewire.md): Δ of its
    top-K realized WF floor vs ranking by P(component) alone (≈ the deployed lane).

Until now reading them meant `tail -1 … | json` spelunking. This command pretty-prints
both — the trend at a glance — with zero DB access (the JSONL files carry no lock, unlike
`forge.db`). It is deliberately distinct from `forge healthcheck` (is the daemon *alive
and producing?*); this answers *is the learning improving?*. For the authoritative
recompute from the DB, use `forge ranker-model eval` / `eval-robustness`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer

_TREND_K = 8  # how many trailing checkpoints to show in the sparkline
# P1.2 — the gate-tail flip gate: k fresh-window PASSes AND the pooled fresh-window Δ's 95%
# CI excluding 0. Both must hold before FORGE_QUALITY_RANK_MODE=gate-tail is flipped on.
_FLIP_GATE_K = 3


@dataclass(frozen=True, slots=True)
class StreakSummary:
    label: str
    metric_name: str
    n_records: int
    latest_verdict: str | None
    latest_metric: float | None
    consecutive_pass: int
    target: int
    latest_ts: str | None
    trend: tuple[float, ...]  # oldest -> newest, the last _TREND_K metric values


def _consecutive_pass(records: Sequence[dict[str, object]]) -> int:
    """Trailing consecutive qualifying-PASS count (mirrors daily_ranker_eval.sh).

    Newest -> oldest: skip non-qualifying rows (stall day / single-class window),
    count PASS, stop at the first qualifying FAIL. Non-qualifying rows neither
    advance nor break the streak.
    """
    streak = 0
    for rec in reversed(records):
        if not rec.get("qualifies"):
            continue
        if rec.get("verdict") == "PASS":
            streak += 1
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# P1.2 — gate-tail flip gate (numeric, contamination-guarded)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FlipGateStatus:
    """Whether the gate-tail flip gate is met. `met` = `fresh_pass_streak >= k` AND the pooled
    fresh-window Δ's 95% CI excludes 0 (both, per P1.2). Full-pool "look" records are excluded."""

    fresh_pass_streak: int
    k: int
    n_fresh_qualifying: int
    pooled_delta: float | None
    ci_low: float | None
    ci_high: float | None
    met: bool


def _is_full_pool_look(rec: dict[str, object], clean_era_iso: str) -> bool:
    """P1.2 contamination guard: the first-ever run's window is the whole clean-era pool, not a
    fresh per-checkpoint window. New records carry ``is_first_look``; older ones are identified
    by ``window_since`` == the clean-era cut."""
    if rec.get("is_first_look"):
        return True
    return rec.get("window_since") == clean_era_iso


def _mean_ci95(values: Sequence[float]) -> tuple[float | None, float | None, float | None]:
    """Sample mean + 95% normal-approx CI. (None, None, None) on empty; a point with no CI on
    a single value (CI undefined). Deterministic — no RNG (hard rules #5/#6)."""
    n = len(values)
    if n == 0:
        return None, None, None
    mean = sum(values) / n
    if n < 2:
        return mean, None, None
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    se = math.sqrt(variance / n)
    return mean, mean - 1.96 * se, mean + 1.96 * se


def rewire_flip_gate(
    records: Sequence[dict[str, object]], *, clean_era_iso: str, k: int = _FLIP_GATE_K
) -> FlipGateStatus:
    """The numeric gate-tail flip gate over the rewire streak records. Excludes full-pool looks
    (P1.2), counts the trailing fresh-window PASS streak, and requires the pooled fresh-window
    Δ's 95% CI to exclude 0. Pure/testable — the daily verdict is recorded, not re-derived."""
    fresh = [r for r in records if not _is_full_pool_look(r, clean_era_iso)]
    streak = _consecutive_pass(fresh)
    deltas: list[float] = []
    for r in fresh:
        delta = r.get("delta")
        if r.get("qualifies") and isinstance(delta, (int, float)):
            deltas.append(float(delta))
    pooled, lo, hi = _mean_ci95(deltas)
    met = streak >= k and lo is not None and lo > 0.0
    return FlipGateStatus(streak, k, len(deltas), pooled, lo, hi, met)


def summarize_streak(
    records: Sequence[dict[str, object]],
    *,
    label: str,
    metric_key: str,
    metric_name: str,
    target: int = 3,
) -> StreakSummary:
    """Reduce raw streak-JSONL records to a glanceable summary. Pure/testable."""
    if not records:
        return StreakSummary(
            label=label,
            metric_name=metric_name,
            n_records=0,
            latest_verdict=None,
            latest_metric=None,
            consecutive_pass=0,
            target=target,
            latest_ts=None,
            trend=(),
        )
    latest = records[-1]
    metric_val = latest.get(metric_key)
    verdict_raw = latest.get("verdict")
    ts_raw = latest.get("ts")
    trend_vals: list[float] = []
    for r in records[-_TREND_K:]:
        v = r.get(metric_key)
        if isinstance(v, (int, float)):
            trend_vals.append(float(v))
    return StreakSummary(
        label=label,
        metric_name=metric_name,
        n_records=len(records),
        latest_verdict=verdict_raw if isinstance(verdict_raw, str) else None,
        latest_metric=float(metric_val) if isinstance(metric_val, (int, float)) else None,
        consecutive_pass=_consecutive_pass(records),
        target=target,
        latest_ts=ts_raw if isinstance(ts_raw, str) else None,
        trend=tuple(trend_vals),
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """Best-effort JSONL read; missing file or bad lines -> what's parseable."""
    if not path.is_file():
        return []
    out: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _latest_field(records: list[dict[str, object]], key: str) -> object | None:
    """Most recent non-null value of ``key`` across ``records`` (older rows may predate
    the field — P1.3 added the calibration/keep-rate columns mid-stream)."""
    for rec in reversed(records):
        value = rec.get(key)
        if value is not None:
            return value
    return None


def _format_calibration(
    f3_records: list[dict[str, object]], rewire_records: list[dict[str, object]]
) -> str:
    """P1.3 drift guard: the latest floor-relevant calibration verdict (does the P the
    absolute gate-then-tail floor reads stay calibrated?) + the floor keep-rate."""
    max_ce = _latest_field(f3_records, "model_max_ce")
    verdict = _latest_field(f3_records, "calibration_verdict")
    keep_rate = _latest_field(rewire_records, "eligible_fraction")
    mce = "n/a" if not isinstance(max_ce, (int, float)) else f"{float(max_ce):.3f}"
    kr = "n/a" if not isinstance(keep_rate, (int, float)) else f"{float(keep_rate):.4f}"
    cv = str(verdict) if verdict is not None else "?"
    return f"{'P calibration/floor':<22} {cv:<4} max_ce {mce}   keep-rate(P>=floor) {kr}"


def _format_flip_gate(g: FlipGateStatus) -> str:
    """P1.2 gate-tail flip gate line: fresh-PASS streak + pooled Δ CI + MET/NOT-MET."""
    verdict = "MET" if g.met else "NOT MET"
    if g.pooled_delta is None:
        ci = "pooled Δ n/a"
    elif g.ci_low is None:
        ci = f"pooled Δ {g.pooled_delta:+.3f} (n={g.n_fresh_qualifying}, CI needs ≥2)"
    else:
        ci = f"pooled Δ {g.pooled_delta:+.3f} CI [{g.ci_low:+.3f},{g.ci_high:+.3f}]"
    return f"{'gate-tail flip gate':<22} {verdict:<7} fresh-PASS {g.fresh_pass_streak}/{g.k}   {ci}"


def _format_summary(s: StreakSummary) -> str:
    if s.n_records == 0:
        return f"{s.label:<22} (no checkpoints recorded yet)"
    verdict = s.latest_verdict or "?"
    metric = "n/a" if s.latest_metric is None else f"{s.latest_metric:+.3f}"
    trend = " ".join(f"{v:+.2f}" for v in s.trend) if s.trend else "—"
    ts = (s.latest_ts or "")[:16]
    return (
        f"{s.label:<22} {verdict:<4} streak {s.consecutive_pass}/{s.target}   "
        f"{s.metric_name} {metric}   last{len(s.trend)}: {trend}   @ {ts}"
    )


def cmd_status(
    data_root: Path = typer.Option(
        Path("~/forge_data").expanduser(), "--data-root", help="Forge data root"
    ),
) -> None:
    """Show the learning-signal clocks (is the stream improving?) — no DB access."""
    eval_dir = data_root / "ranker_eval"
    f3_records = _read_jsonl(eval_dir / "streak.jsonl")
    rewire_records = _read_jsonl(eval_dir / "rewire_streak_wfp25.jsonl")
    f3 = summarize_streak(
        f3_records,
        label="F3 verdict ranker",
        metric_key="auc_margin",
        metric_name="AUC margin",
    )
    tail = summarize_streak(
        _read_jsonl(eval_dir / "robustness_streak_wfp25.jsonl"),
        label="§8.6 wf_p25 tail",
        metric_key="spearman",
        metric_name="Spearman",
    )
    rewire = summarize_streak(
        rewire_records,
        label="re-wire gate-tail",
        metric_key="delta",
        metric_name="Δ vs P",
    )
    typer.echo(f"forge status — learning-signal clocks ({eval_dir}; no DB)")
    typer.echo(_format_summary(f3))
    typer.echo(_format_summary(tail))
    typer.echo(_format_summary(rewire))
    typer.echo(_format_calibration(f3_records, rewire_records))
    from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT

    flip_gate = rewire_flip_gate(rewire_records, clean_era_iso=CLEAN_ERA_LABEL_CUT.isoformat())
    typer.echo(_format_flip_gate(flip_gate))
    typer.echo("(authoritative recompute: `forge ranker-model eval` / `eval-robustness`)")


__all__ = [
    "FlipGateStatus",
    "StreakSummary",
    "cmd_status",
    "rewire_flip_gate",
    "summarize_streak",
]
