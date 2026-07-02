"""Unit tests for `forge healthcheck` (ops-sprint item 3, D197).

The journal parser + the five pure check functions are the testable core; the gather
glue (journalctl / systemctl subprocess) is thin and exercised only at runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from forge.cli.healthcheck_cmd import (
    Level,
    check_contracts_pin,
    check_file_freshness,
    check_learning_drift,
    check_loop_liveness,
    check_service_active,
    check_submission_progress,
    parse_forge_journal,
)

_NOW = datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def test_parse_journal_extracts_latest_events() -> None:
    lines = [
        # submitted=0 is a completed cycle that produced no batch -> must NOT count.
        "2026-06-22T05:00:00-07:00 host forge[1]: batch_id=def submitted=0 grammar_version=v22",
        "2026-06-22T06:00:00-07:00 host forge[1]: batch_id=abc submitted=200 grammar_version=v22",
        "2026-06-23T22:10:19-07:00 host forge[1]: --- loop iteration 4061 (effective_seed=9) ---",
        "2026-06-23T22:10:46-07:00 host forge[1]: reconciled: batches=203 newly_gated_total=7283",
        "2026-06-23T22:10:47-07:00 host forge[1]: blocked: crucible stalled — no decisions since X",
        "a non-matching line that must be ignored",
    ]
    state = parse_forge_journal(lines)
    assert state.last_iteration_at == datetime.fromisoformat("2026-06-23T22:10:19-07:00")
    # submitted=200 wins; the earlier submitted=0 must not set the clock.
    assert state.last_submit_at == datetime.fromisoformat("2026-06-22T06:00:00-07:00")
    assert state.last_block_at == datetime.fromisoformat("2026-06-23T22:10:47-07:00")
    assert state.last_block_reason is not None
    assert state.last_block_reason.startswith("crucible stalled")


def test_parse_journal_empty() -> None:
    state = parse_forge_journal([])
    assert state.last_iteration_at is None
    assert state.last_submit_at is None
    assert state.last_block_reason is None
    assert state.hypothesis_weights_degraded_at is None


def test_parse_journal_detects_hypothesis_weights_degrade() -> None:
    from forge.cli.healthcheck_cmd import Level, check_hypothesis_weights_fallback

    lines = [
        "2026-07-02T05:00:00-07:00 host forge[1]: --- loop iteration 10 (effective_seed=9) ---",
        "2026-07-02T05:00:01-07:00 host forge[1]: hypothesis_weights: degraded to uniform "
        "sampling — QueryError loading learned weights",
    ]
    state = parse_forge_journal(lines)
    assert state.hypothesis_weights_degraded_at == datetime.fromisoformat(
        "2026-07-02T05:00:01-07:00"
    )
    # WARN (not CRITICAL) — the daemon still produces, it just stops steering.
    res = check_hypothesis_weights_fallback(state)
    assert res.level == Level.WARN
    assert "UNIFORM-fallback" in res.message
    # Clean journal -> OK.
    ok = check_hypothesis_weights_fallback(parse_forge_journal([]))
    assert ok.level == Level.OK


def test_service_active() -> None:
    assert check_service_active(True).level is Level.OK
    assert check_service_active(False).level is Level.CRITICAL


def test_loop_liveness_levels() -> None:
    kw = {"warn_minutes": 15.0, "critical_minutes": 30.0}
    assert check_loop_liveness(None, _NOW, **kw).level is Level.CRITICAL
    assert check_loop_liveness(_NOW - timedelta(minutes=2), _NOW, **kw).level is Level.OK
    assert check_loop_liveness(_NOW - timedelta(minutes=20), _NOW, **kw).level is Level.WARN
    assert check_loop_liveness(_NOW - timedelta(minutes=45), _NOW, **kw).level is Level.CRITICAL


def test_submission_progress_levels_and_reason() -> None:
    kw = {"warn_hours": 6.0, "critical_hours": 24.0}
    # None -> CRITICAL, carrying the block reason so the alert points upstream.
    none_res = check_submission_progress(
        None, _NOW, last_block_reason="crucible stalled — no decisions", **kw
    )
    assert none_res.level is Level.CRITICAL
    assert "crucible stalled" in none_res.message
    # fresh -> OK
    assert (
        check_submission_progress(
            _NOW - timedelta(hours=1), _NOW, last_block_reason=None, **kw
        ).level
        is Level.OK
    )
    # the ~32h stall -> CRITICAL
    assert (
        check_submission_progress(
            _NOW - timedelta(hours=32), _NOW, last_block_reason="crucible stalled", **kw
        ).level
        is Level.CRITICAL
    )
    # 8h -> WARN
    assert (
        check_submission_progress(
            _NOW - timedelta(hours=8), _NOW, last_block_reason=None, **kw
        ).level
        is Level.WARN
    )


def test_component_contributions_export_soft_check() -> None:
    """D216 follow-up: the component_contributions export is per-promoted-book,
    so absence is EXPECTED until the first promotion — it must be OK, never a
    WARN that pollutes OVERALL. Present → OK with age."""
    from forge.cli.healthcheck_cmd import check_component_contributions_export

    absent = check_component_contributions_export(None, _NOW)
    assert absent.level is Level.OK
    assert "no export yet" in absent.message

    present = check_component_contributions_export(_NOW - timedelta(hours=3), _NOW)
    assert present.level is Level.OK
    assert "3.0h" in present.message


def test_file_freshness_levels() -> None:
    kw = {"label": "backup", "warn_hours": 26.0, "critical_hours": 50.0}
    assert check_file_freshness(None, _NOW, **kw).level is Level.WARN
    assert check_file_freshness(_NOW - timedelta(hours=2), _NOW, **kw).level is Level.OK
    assert check_file_freshness(_NOW - timedelta(hours=30), _NOW, **kw).level is Level.WARN
    assert check_file_freshness(_NOW - timedelta(hours=60), _NOW, **kw).level is Level.CRITICAL


def test_contracts_pin_levels() -> None:
    assert check_contracts_pin("1.19.0", "1.19.0").level is Level.OK
    # Finding A: installed 1.20.0 vs pin 1.19.0 -> un-adopted minor -> WARN.
    assert check_contracts_pin("1.19.0", "1.20.0").level is Level.WARN
    # major drift -> CRITICAL (the daemon would hard-halt at startup).
    assert check_contracts_pin("1.19.0", "2.0.0").level is Level.CRITICAL


def test_learning_drift_levels() -> None:
    kw = {
        "label": "wf_p25",
        "warn_below": 0.0,
        "critical_below": -0.10,
        "regression_delta": 0.25,
    }
    # No eval data yet -> WARN (informational; mirrors "no backup found").
    assert check_learning_drift([], **kw).level is Level.WARN
    # Clearly anti-predictive latest -> CRITICAL (the live lane is mis-ranking).
    assert check_learning_drift([0.3, 0.2, -0.15], **kw).level is Level.CRITICAL
    # Weak (at/below the warn floor) but not anti-predictive -> WARN.
    assert check_learning_drift([0.3, 0.2, -0.02], **kw).level is Level.WARN
    # Healthy and stable -> OK.
    assert check_learning_drift([0.30, 0.32, 0.31, 0.33], **kw).level is Level.OK
    # Healthy latest, but a sharp drop vs its own trailing median -> WARN (drift).
    # median([0.50, 0.52, 0.51]) = 0.51; 0.20 <= 0.51 - 0.25 -> regression WARN.
    assert check_learning_drift([0.50, 0.52, 0.51, 0.20], **kw).level is Level.WARN
    # Short history (< min_history) skips the regression check -> no false alarm.
    assert check_learning_drift([0.9, 0.2], **kw).level is Level.OK
