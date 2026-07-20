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
    check_inbox_rejections,
    check_learning_drift,
    check_loop_liveness,
    check_service_active,
    check_submission_progress,
    check_tmp_headroom,
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
    assert state.registry_unknown_family_at is None


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


def test_parse_journal_detects_registry_unknown_family_skip() -> None:
    """D261: the registry loader logs `registry_unknown_family_skipped` when it drops an
    indicator whose `family` Literal is unknown to Forge's installed contracts (a Crucible
    family added ahead of the pin). WARN so the un-adopted contracts skew is visible."""
    from forge.cli.healthcheck_cmd import Level, check_registry_unknown_family

    lines = [
        "2026-07-09T17:00:00-07:00 host forge[1]: --- loop iteration 42 (effective_seed=9) ---",
        "2026-07-09T17:00:01-07:00 host forge[1]: registry_unknown_family_skipped "
        "dropped=[{'id': 'ivol', 'family': 'idiosyncratic_vol'}] count=1",
    ]
    state = parse_forge_journal(lines)
    assert state.registry_unknown_family_at == datetime.fromisoformat("2026-07-09T17:00:01-07:00")
    res = check_registry_unknown_family(state)
    assert res.level == Level.WARN
    assert "unknown `family`" in res.message
    # Clean journal -> OK.
    ok = check_registry_unknown_family(parse_forge_journal([]))
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


def test_earnings_coverage_export_soft_check() -> None:
    """v32 (D268): the earnings-coverage manifest ships dormant until Crucible starts the
    publisher, so ABSENCE must be OK (never pollute OVERALL — the component_contributions
    precedent). The sampler reads it with max_age_days=None (a stale coverage set never
    HALTS generation — coverage changes slowly, stale beats the frozen list), so the
    staleness teeth live here: present & fresh → OK; older than 45d → WARN (publisher may
    be dead; the covered set is ossifying and a new no-earnings universe add re-opens the
    SOXL blind spot)."""
    from forge.cli.healthcheck_cmd import check_earnings_coverage_export

    absent = check_earnings_coverage_export(None, _NOW)
    assert absent.level is Level.OK
    assert "no export yet" in absent.message

    fresh = check_earnings_coverage_export(_NOW - timedelta(days=3), _NOW)
    assert fresh.level is Level.OK

    stale = check_earnings_coverage_export(_NOW - timedelta(days=46), _NOW)
    assert stale.level is Level.WARN


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


def test_inbox_rejections_levels() -> None:
    kw = {"warn": 25, "critical": 100}
    # Steady state: Forge's output always validates -> ~0 rejections -> OK.
    assert check_inbox_rejections(0, **kw).level is Level.OK
    assert check_inbox_rejections(24, **kw).level is Level.OK
    # A chunk of recent rejections -> WARN (something is emitting invalid configs).
    assert check_inbox_rejections(25, **kw).level is Level.WARN
    assert check_inbox_rejections(99, **kw).level is Level.WARN
    # A batch-sized burst -> CRITICAL (systematic skew, e.g. an asymmetric contracts bump).
    assert check_inbox_rejections(100, **kw).level is Level.CRITICAL
    assert check_inbox_rejections(200, **kw).level is Level.CRITICAL
    # The CRITICAL message must point at the D245 diagnosis (reason files + both-directions).
    crit = check_inbox_rejections(200, **kw)
    assert "errors" in crit.message.lower()


def test_tmp_headroom_levels() -> None:
    kw = {"warn_ratio": 5.0, "critical_ratio": 3.5}
    gb = 10**9
    # Plenty of headroom -> OK (boundary: exactly 5x is not < 5 -> OK).
    assert check_tmp_headroom(10 * gb, gb, **kw).level is Level.OK
    assert check_tmp_headroom(5 * gb, gb, **kw).level is Level.OK
    # Getting tight -> WARN.
    assert check_tmp_headroom(4 * gb, gb, **kw).level is Level.WARN
    # About to fail the ranker-eval cp -> CRITICAL (the 2026-07-09 incident was ~3.3x).
    assert check_tmp_headroom(3 * gb, gb, **kw).level is Level.CRITICAL
    assert check_tmp_headroom(int(3.3 * gb), gb, **kw).level is Level.CRITICAL
    # Scales with DB size: 20G free but a 10G DB is only 2x -> CRITICAL.
    assert check_tmp_headroom(20 * gb, 10 * gb, **kw).level is Level.CRITICAL
    # Unmeasurable -> OK (never a false CRIT).
    assert check_tmp_headroom(None, gb, **kw).level is Level.OK
    assert check_tmp_headroom(5 * gb, 0, **kw).level is Level.OK
    # CRITICAL message points at the /tmp fix.
    assert "tmp" in check_tmp_headroom(3 * gb, gb, **kw).message.lower()


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


def test_campaign_carriage_levels() -> None:
    """D302 (Theme 5c): the daily campaign-audit JSONL row -> healthcheck.

    Missing file/rows is OK-with-note (the wiring is new; the freshness WARN
    covers a timer that stops writing AFTER the first row). Starved campaigns
    and stale rows WARN."""
    from forge.cli.healthcheck_cmd import check_campaign_carriage

    fresh_ts = (_NOW - timedelta(hours=5)).isoformat()
    stale_ts = (_NOW - timedelta(hours=40)).isoformat()

    # No rows yet -> OK (informational note, not a nag).
    result = check_campaign_carriage(None, _NOW)
    assert result.level is Level.OK
    assert "no campaign-audit rows" in result.message

    # Fresh row, nothing starved -> OK.
    healthy = {"ts": fresh_ts, "starved": [], "results": [{"name": "a", "starved": False}]}
    assert check_campaign_carriage(healthy, _NOW).level is Level.OK

    # Fresh row with a starved campaign -> WARN, names in the message.
    starved = {"ts": fresh_ts, "starved": ["resid-vix-two-arm"], "results": []}
    result = check_campaign_carriage(starved, _NOW)
    assert result.level is Level.WARN
    assert "resid-vix-two-arm" in result.message

    # Stale row -> WARN even when nothing is starved.
    old = {"ts": stale_ts, "starved": [], "results": []}
    result = check_campaign_carriage(old, _NOW)
    assert result.level is Level.WARN
    assert "stale" in result.message

    # Unparseable/missing ts -> WARN (cannot trust freshness).
    assert check_campaign_carriage({"starved": []}, _NOW).level is Level.WARN
