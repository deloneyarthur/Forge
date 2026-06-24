"""`forge status` — is the stream getting better at promoting? (ops-sprint item 4)

The pipeline's whole purpose is for Forge's submission stream to become *more likely to
promote over time*. The daily ranker-eval timer already distils that into two curated
"clocks" under `~/forge_data/ranker_eval/`:

  * **F3 verdict ranker** (`streak.jsonl`) — how much better the learned P(component)
    model ranks than the incumbent §6.2 composite (AUC margin), and the trailing
    consecutive-PASS streak toward the F3 criterion.
  * **§8.6 wf_p25 tail** (`robustness_streak_wfp25.jsonl`) — Spearman of the quality
    lane's predicted WF-floor against the realized worst-quartile gate.

Until now reading them meant `tail -1 … | json` spelunking. This command pretty-prints
both — the trend at a glance — with zero DB access (the JSONL files carry no lock, unlike
`forge.db`). It is deliberately distinct from `forge healthcheck` (is the daemon *alive
and producing?*); this answers *is the learning improving?*. For the authoritative
recompute from the DB, use `forge ranker-model eval` / `eval-robustness`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer

_TREND_K = 8  # how many trailing checkpoints to show in the sparkline


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
    f3 = summarize_streak(
        _read_jsonl(eval_dir / "streak.jsonl"),
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
    typer.echo(f"forge status — learning-signal clocks ({eval_dir}; no DB)")
    typer.echo(_format_summary(f3))
    typer.echo(_format_summary(tail))
    typer.echo("(authoritative recompute: `forge ranker-model eval` / `eval-robustness`)")


__all__ = ["StreakSummary", "cmd_status", "summarize_streak"]
