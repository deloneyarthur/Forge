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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer

from forge.ranking.drift import adoption_verdict
from forge.ranking.sequential_test import sequential_mean_test

_TREND_K = 8  # how many trailing checkpoints to show in the sparkline
# P3.1 (B5) — the gate-tail flip gate is a Wald SPRT on the fresh-window paired deltas.
# H0: mean Δ = 0 (gate-tail no better than the P(component) baseline); H1: mean Δ =
# _FLIP_MIN_EFFECT. The SPRT controls the false-promote rate at ~alpha under the daily
# peeking the streak does — which the D223 fixed-sample CI ("k PASSes AND CI>0") did NOT
# (a 3-consecutive coin-flip is a 12.5% false-promote). `_FLIP_GATE_K` is reused as the
# SPRT's min_observations (never flip on fewer than k fresh checkpoints).
_FLIP_GATE_K = 3
_FLIP_ALPHA = 0.05  # target false-promote rate
_FLIP_BETA = 0.20  # target false-reject rate
_FLIP_MIN_EFFECT = 0.05  # the mean WF-floor Δ worth flipping for (matches the old margin)
# §8.6 tail lane (P3.1 follow-up): the paired Spearman-delta (tail minus incumbent) worth
# crediting as marginal skill. Modest — the tail model beat the incumbent ~+0.23 on verified
# rows historically, but ties on the unverified majority, so the honest mean delta is small.
_TAIL_FLIP_MIN_EFFECT = 0.05


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
    """Whether the gate-tail flip gate is met. P3.1 (B5): the gate is a Wald SPRT on the
    fresh-window paired deltas — `met` == the SPRT decided ``"promote"`` (log-LR crossed the
    upper Wald boundary), which controls the false-promote rate at ~alpha under daily peeking.
    Full-pool "look" records are excluded; `fresh_pass_streak` is a display-only diagnostic
    (the SPRT weighs delta magnitudes, not the binary PASS)."""

    label: str
    fresh_pass_streak: int
    k: int
    n_fresh_qualifying: int
    mean_delta: float | None
    sprt_decision: str
    sprt_log_lr: float
    sprt_upper: float
    met: bool


def _is_full_pool_look(rec: dict[str, object], clean_era_iso: str) -> bool:
    """P1.2 contamination guard: the first-ever run's window is the whole clean-era pool, not a
    fresh per-checkpoint window. New records carry ``is_first_look``; older ones are identified
    by ``window_since`` == the clean-era cut."""
    if rec.get("is_first_look"):
        return True
    return rec.get("window_since") == clean_era_iso


def _sprt_flip_gate(
    records: Sequence[dict[str, object]],
    *,
    clean_era_iso: str,
    delta_key: str,
    min_effect: float,
    label: str,
    k: int = _FLIP_GATE_K,
) -> FlipGateStatus:
    """Shared SPRT flip gate (P3.1). Excludes full-pool looks (P1.2), then runs a Wald SPRT
    on every data-sufficient (`qualifies`) fresh-window paired Δ read from `delta_key`:
    `met` == the SPRT decided ``"promote"``. `k` is the SPRT's min_observations (never flip on
    <k fresh checkpoints). Pure/testable — the daily verdict is recorded, not re-derived."""
    fresh = [r for r in records if not _is_full_pool_look(r, clean_era_iso)]
    streak = _consecutive_pass(fresh)
    # Only data-sufficient checkpoints feed the SPRT: `qualifies` is the timer's
    # (fresh_decided >= min_fresh) gate — an under-powered window's Δ is noise. Rows that
    # predate `delta_key` (older streak schema) lack it and are skipped by the isinstance check.
    deltas = [
        float(d)
        for r in fresh
        if r.get("qualifies") and isinstance((d := r.get(delta_key)), (int, float))
    ]
    mean = sum(deltas) / len(deltas) if deltas else None
    sprt = sequential_mean_test(
        deltas,
        alpha=_FLIP_ALPHA,
        beta=_FLIP_BETA,
        min_effect=min_effect,
        min_observations=k,
    )
    return FlipGateStatus(
        label=label,
        fresh_pass_streak=streak,
        k=k,
        n_fresh_qualifying=len(deltas),
        mean_delta=mean,
        sprt_decision=sprt.decision,
        sprt_log_lr=sprt.log_lr,
        sprt_upper=sprt.upper,
        met=sprt.decision == "promote",
    )


def rewire_flip_gate(
    records: Sequence[dict[str, object]], *, clean_era_iso: str, k: int = _FLIP_GATE_K
) -> FlipGateStatus:
    """The gate-tail flip gate: SPRT over the rewire streak's per-checkpoint `delta` (top-K
    WF floor of the gate-then-tail lane minus the P(component) baseline)."""
    return _sprt_flip_gate(
        records,
        clean_era_iso=clean_era_iso,
        delta_key="delta",
        min_effect=_FLIP_MIN_EFFECT,
        label="gate-tail flip gate",
        k=k,
    )


def tail_flip_gate(
    records: Sequence[dict[str, object]], *, clean_era_iso: str, k: int = _FLIP_GATE_K
) -> FlipGateStatus:
    """The §8.6 tail-lane skill gate (P3.1 follow-up): SPRT over the streak's per-checkpoint
    `spearman_delta` (tail-model Spearman minus the incumbent P(component) Spearman, same rows).
    Replaces the absolute Spearman ≥ 0.30 bar with a paired significance test — the input P4.1
    (retire-or-keep) should read instead of the streak count."""
    return _sprt_flip_gate(
        records,
        clean_era_iso=clean_era_iso,
        delta_key="spearman_delta",
        min_effect=_TAIL_FLIP_MIN_EFFECT,
        label="§8.6 tail flip gate",
        k=k,
    )


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


def _format_adoption(f3: StreakSummary, tail: StreakSummary) -> str:
    """P3.2 (B6) adoption guard: should the daemon rotate to the newest artifact? Reads each
    lane's latest fresh signal — F3 AUC margin, wf_p25 paired Δ Spearman — and BLOCKs adoption
    when it isn't strictly positive (a model no better than the incumbent isn't worth the
    rotation). Telemetry; the healthcheck raises the matching WARN/CRITICAL."""

    def _m(v: float | None) -> str:
        return f"{v:+.3f}" if v is not None else "n/a"

    f3_v = adoption_verdict(f3.latest_metric)
    tail_v = adoption_verdict(tail.latest_metric)
    return (
        f"{'adoption guard':<22} F3={f3_v} ({_m(f3.latest_metric)})  "
        f"wf_p25={tail_v} ({_m(tail.latest_metric)})"
    )


def _format_flip_gate(g: FlipGateStatus) -> str:
    """P3.1 gate-tail flip gate line: SPRT verdict + log-LR vs boundary + mean Δ + MET/NOT-MET."""
    verdict = "MET" if g.met else "NOT MET"
    md = f"mean Δ {g.mean_delta:+.3f}" if g.mean_delta is not None else "mean Δ n/a"
    sprt = f"SPRT {g.sprt_decision} (logLR {g.sprt_log_lr:+.2f} / {g.sprt_upper:.2f})"
    return (
        f"{g.label:<22} {verdict:<7} {sprt}  {md}  "
        f"fresh-PASS {g.fresh_pass_streak}/{g.k} n={g.n_fresh_qualifying}"
    )


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
    tail_records = _read_jsonl(eval_dir / "robustness_streak_wfp25.jsonl")
    f3 = summarize_streak(
        f3_records,
        label="F3 verdict ranker",
        metric_key="auc_margin",
        metric_name="AUC margin",
    )
    tail = summarize_streak(
        tail_records,
        label="§8.6 wf_p25 tail",
        metric_key="spearman_delta",
        metric_name="Δ Spearman vs P",
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
    typer.echo(_format_adoption(f3, tail))
    from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT

    clean_era_iso = CLEAN_ERA_LABEL_CUT.isoformat()
    typer.echo(_format_flip_gate(rewire_flip_gate(rewire_records, clean_era_iso=clean_era_iso)))
    typer.echo(_format_flip_gate(tail_flip_gate(tail_records, clean_era_iso=clean_era_iso)))
    typer.echo("(authoritative recompute: `forge ranker-model eval` / `eval-robustness`)")


__all__ = [
    "FlipGateStatus",
    "StreakSummary",
    "cmd_status",
    "rewire_flip_gate",
    "summarize_streak",
    "tail_flip_gate",
]
