"""Tests for `forge run --loop` and `--consume-feedback` (Phase 5 module 11).

D024/D6 + D7:
- `--loop` runs the cycle repeatedly, sleeping `--poll-interval-seconds`
  between iterations. For testing, `--max-iterations N` caps to N.
- `--consume-feedback` triggers the feedback chain after submit (or
  before, on subsequent iterations, since the previous batch's results
  may have arrived by now).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli.main import _effective_seed, _next_iteration_number, app
from forge.persistence.db import db_connection
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

runner = CliRunner()


# ---------------------------------------------------------------------------
# --loop runs N iterations and exits cleanly
# ---------------------------------------------------------------------------


def test_effective_seed_is_deterministic() -> None:
    """Same (root, iteration) returns the same effective seed."""
    assert _effective_seed(42, 1) == _effective_seed(42, 1)
    assert _effective_seed(42, 7) == _effective_seed(42, 7)


def test_effective_seed_differs_across_iterations() -> None:
    """Different iterations yield different effective seeds.

    This is the load-bearing property of plan C: without it, batch N+1
    enumerates the same configs as batch N and submitter dedup rejects
    them all as duplicates.
    """
    assert _effective_seed(42, 1) != _effective_seed(42, 2)
    assert _effective_seed(42, 1) != _effective_seed(42, 100)


def test_effective_seed_differs_across_roots() -> None:
    """Different root seeds for the same iteration yield different effective seeds."""
    assert _effective_seed(42, 1) != _effective_seed(43, 1)


def test_next_iteration_number_fresh_db_returns_1(tmp_path: Path) -> None:
    """Empty Forge DB → next iteration is 1."""
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db):
        pass  # schema-ensure
    assert _next_iteration_number(forge_db) == 1


def test_next_iteration_number_memory_db_returns_1() -> None:
    """In-memory DB always returns 1 — no persistence, no resume."""
    assert _next_iteration_number(Path(":memory:")) == 1


def test_next_iteration_number_counts_distinct_batch_ids(tmp_path: Path) -> None:
    """Persisted counter equals distinct batch_ids in submissions + 1.

    Restart resilience: a service restart should resume from where it
    left off rather than replaying batch_1 (which would re-enumerate
    the same configs).
    """
    import uuid
    from datetime import UTC, datetime

    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        now = datetime.now(UTC)
        for batch_idx in range(3):
            batch_id = uuid.uuid4()
            # Each batch has at least one submission row
            conn.execute(
                """
                INSERT INTO submissions
                    (forge_candidate_id, forge_batch_id, config_hash,
                     config_json, submitted_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    str(batch_id),
                    f"hash_{batch_idx:016d}",
                    "{}",
                    now,
                    "submitted",
                ],
            )
    assert _next_iteration_number(forge_db) == 4


def test_run_loop_with_max_iterations_exits_cleanly(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
            "--loop",
            "--max-iterations",
            "2",
            "--poll-interval-seconds",
            "0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Loop runs at least once (after first iter the rate limiter may block;
    # the loop should exit cleanly either way after max-iterations)
    assert (
        "submitted=" in result.stdout
        or "blocked" in result.stdout
        or "stopped" in result.stdout.lower()
    )


# ---------------------------------------------------------------------------
# --consume-feedback triggers the feedback chain
# ---------------------------------------------------------------------------


def test_run_with_consume_feedback_runs_chain(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
            "--consume-feedback",
            "--open-proposals",
            str(tmp_path / "OPEN_PROPOSALS.md"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Feedback chain emits its own summary line
    assert "feedback:" in result.stdout.lower() or "gated_count" in result.stdout


# ---------------------------------------------------------------------------
# --loop without rate-limiter-clear still respects max-iterations
# ---------------------------------------------------------------------------


def test_loop_exits_on_max_iterations_even_when_blocked(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    # Pre-populate forge_db with a "pending" batch so the rate limiter blocks
    import uuid
    from datetime import UTC, datetime

    from forge.persistence.db import db_connection

    bid = uuid.uuid4()
    cid = uuid.uuid4()
    # Minimal valid StrategyConfig JSON — the CLI run-loop may parse it
    # downstream (feedback consumer reconstructs StrategyConfigs). The
    # config's hypothesis/structure doesn't matter for rate-limiter blocking;
    # it just needs to deserialize cleanly.
    from tests.fixtures.strategy_configs import minimal_strategy_config

    valid_cfg_json = minimal_strategy_config().model_dump_json()
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
            "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
            [str(bid), 1, datetime(2026, 5, 13, tzinfo=UTC), "v1", "abc"],
        )
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                str(cid),
                str(bid),
                "blocking_hash_xx",
                valid_cfg_json,
                datetime(2026, 5, 13, tzinfo=UTC),
                "submitted",
            ],
        )
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
            "--loop",
            "--max-iterations",
            "3",
            "--poll-interval-seconds",
            "0",
        ],
    )
    assert result.exit_code == 0
    # Should be blocked all 3 iterations
    assert result.stdout.count("blocked") >= 1


# ---------------------------------------------------------------------------
# D060 / P2-5 — warn-once when NoveltyFilter dedup is disabled (no DB path)
# ---------------------------------------------------------------------------


def test_d060_novelty_dedup_disabled_warning_fires_when_db_is_none(
    capsys: object,
) -> None:
    """D060 / P2-5: the autonomous loop populates `prior_structural_fingerprints`
    from `submissions` via `_load_prior_structural_fingerprints`. Calling
    `_run_battery_for_seed` with `forge_db_path=None` (the demo path)
    structurally disables T2.7 dedup. Surface a stderr warning so a future
    caller that legitimately runs the autonomous loop without a DB sees
    that NoveltyFilter is degraded."""
    from forge.cli import main as _main

    # Reset the module-level warn-once flag so this test is independent
    # of any prior test that may have triggered the warning.
    _main._NOVELTY_DEDUP_WARNED = False
    _main._warn_once_novelty_dedup_disabled()
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "NoveltyFilter structural-fingerprint dedup" in captured.err
    # Second call is a silent no-op (warn-once contract).
    _main._warn_once_novelty_dedup_disabled()
    second = capsys.readouterr()  # type: ignore[attr-defined]
    assert second.err == ""
    # Reset for downstream tests.
    _main._NOVELTY_DEDUP_WARNED = False


def test_d063_hypothesis_weights_line_fills_prior_for_missing_keys() -> None:
    """D063: the journal `hypothesis_weights:` line now renders the
    *effective* sampler weights — observed values for hypotheses present
    in the dict, `prior_mean(*)` for those absent. The pre-D063 line just
    dumped `dict.items()` and silently omitted no-data hypotheses, making
    them look pruned when they actually get the prior (often higher than
    observed failures)."""
    from forge.cli.main import _format_hypothesis_weights_line
    from forge.feedback.rejection_weights import prior_mean

    weights = {
        "volatility_event": 0.050,
        "regime_arbitrage": 0.004,
    }
    line = _format_hypothesis_weights_line(weights)
    assert "volatility_event=0.050" in line
    assert "regime_arbitrage=0.004" in line
    # Missing hypotheses get prior_mean with `*` marker, NOT dropped.
    pm_str = f"{prior_mean():.3f}"
    assert f"mean_reversion={pm_str}*" in line
    assert f"trend_continuation={pm_str}*" in line
    assert "(*=prior, no data)" in line


def test_d063_hypothesis_weights_line_uses_canonical_order() -> None:
    """D063: hypotheses render in the canonical `_HYPOTHESES` order
    (trend_continuation, mean_reversion, regime_arbitrage, relative_value,
    volatility_event, tail_hedge), not alphabetical or dict-insertion
    order. Stable ordering keeps the line greppable and diff-friendly."""
    from forge.cli.main import _format_hypothesis_weights_line

    weights = {
        h: 0.1
        for h in (
            "trend_continuation",
            "mean_reversion",
            "regime_arbitrage",
            "relative_value",
            "volatility_event",
            "tail_hedge",
        )
    }
    line = _format_hypothesis_weights_line(weights)
    # Strip the prefix so we can check raw order.
    body = line.removeprefix("hypothesis_weights: ").split(" (")[0]
    names = [seg.split("=")[0] for seg in body.split(", ")]
    assert names == [
        "trend_continuation",
        "mean_reversion",
        "regime_arbitrage",
        "relative_value",
        "volatility_event",
        "tail_hedge",
        "event_momentum",  # v12 / D109
    ]


def test_d065_phase_timings_line_renders_in_pipeline_order() -> None:
    """D065: timings render in canonical pipeline order (reconcile →
    enumeration → prefetch → battery → rank → submit), not insertion
    order. Missing keys are skipped so an iteration that short-circuits
    (e.g., rate-limit blocked) still produces a coherent prefix line."""
    from forge.cli.main import _format_phase_timings_line

    out_of_order = {
        "submit": 0.05,
        "battery": 8.0,
        "reconcile": 3.0,
        "prefetch": 12345.0,
        "rank": 0.20,
        "enumeration": 8.0,
    }
    line = _format_phase_timings_line(out_of_order)
    assert line.startswith("phase_timings: ")
    body = line.removeprefix("phase_timings: ")
    names = [seg.split("=")[0] for seg in body.split(", ")]
    assert names == [
        "reconcile",
        "enumeration",
        "prefetch",
        "battery",
        "rank",
        "submit",
    ]
    # Sanity: prefetch is rendered with two-decimal seconds.
    assert "prefetch=12345.00s" in line


def test_h1_rank_combiner_share_default_and_line() -> None:
    """H1 (v12 / D109): the modest ~1/3 exploration share covers exactly the
    breadth-starved directional archetypes, and journals greppably."""
    from forge.cli.main import (
        _DEFAULT_RANK_COMBINER_SHARE,
        _format_rank_combiner_share_line,
    )
    from forge.enumeration.search_space import RANK_COMBINER_HYPOTHESES

    assert 0.0 < _DEFAULT_RANK_COMBINER_SHARE < 1.0
    share = {h: _DEFAULT_RANK_COMBINER_SHARE for h in RANK_COMBINER_HYPOTHESES}
    line = _format_rank_combiner_share_line(share)
    assert line.startswith("rank_combiner_share: ")
    # Only the eligible directional archetypes — never vol_event / relative_value.
    assert "event_momentum" in line
    assert "trend_continuation" in line
    assert "mean_reversion" in line
    assert "volatility_event" not in line
    assert "relative_value" not in line


def test_h1_rank_on_by_default_kill_switch_off(tmp_path: Path) -> None:
    """H1 (v12 / D109): rank emission is ON by default — `forge run` with no flag
    journals the share line; `--no-cross-sectional-rank` is the kill switch."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    base = [
        "run",
        "--no-config",
        "--seed",
        "0",
        "--batch-size",
        "2",
        "--max",
        "200",
        "--forge-db",
        str(forge_db),
        "--inbox",
        str(inbox),
        "--crucible-db",
        str(crucible_db),
    ]
    on = runner.invoke(app, base)
    assert on.exit_code == 0, on.stdout
    assert "rank_combiner_share:" in on.stdout  # default ON

    off = runner.invoke(app, [*base, "--no-cross-sectional-rank"])
    assert off.exit_code == 0, off.stdout
    assert "rank_combiner_share:" not in off.stdout  # kill switch


def test_d065_phase_timings_line_skips_missing_phases() -> None:
    """D065: an iteration that hits rate-limit `blocked` only populates
    `reconcile`. The line should render just that phase, not pad with
    zeros or `None`s — partial views are honest about what ran."""
    from forge.cli.main import _format_phase_timings_line

    line = _format_phase_timings_line({"reconcile": 2.5})
    assert line == "phase_timings: reconcile=2.50s"


def test_d065_hypothesis_distribution_line_uses_canonical_order() -> None:
    """D065: hypothesis-keyed distribution lines render in the canonical
    `_HYPOTHESES` order with `=0` for absent hypotheses (no silent
    omission — that was D063's lesson)."""
    from forge.cli.main import _format_hypothesis_distribution_line

    line = _format_hypothesis_distribution_line(
        "sampler_attempts",
        {"volatility_event": 100, "tail_hedge": 50},
    )
    assert line.startswith("sampler_attempts: ")
    body = line.removeprefix("sampler_attempts: ")
    pairs = [seg.split("=") for seg in body.split(", ")]
    names = [p[0] for p in pairs]
    counts = {p[0]: int(p[1]) for p in pairs}
    assert names == [
        "trend_continuation",
        "mean_reversion",
        "regime_arbitrage",
        "relative_value",
        "volatility_event",
        "tail_hedge",
        "event_momentum",  # v12 / D109
    ]
    assert counts == {
        "trend_continuation": 0,
        "mean_reversion": 0,
        "regime_arbitrage": 0,
        "relative_value": 0,
        "volatility_event": 100,
        "tail_hedge": 50,
        "event_momentum": 0,
    }


def test_d065_run_battery_for_seed_populates_timings(tmp_path: Path) -> None:
    """D065: `_run_battery_for_seed` populates the caller-owned timings
    dict with `enumeration`, `prefetch`, `battery` keys. The caller is
    responsible for the outer phases (reconcile, rank, submit)."""
    from pathlib import Path as _P

    from forge.cli.main import _run_battery_for_seed
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters.calibration import load_calibration

    config_root = _P(__file__).resolve().parents[3] / "config"
    grammar = load_grammar(
        config_root / "grammar.yaml",
        archive_dir=config_root / "grammar_archive",
    )
    calibration = load_calibration(config_root / "prefilter.yaml")
    registry = load_registry()

    timings: dict[str, float] = {}
    # Tiny max_candidates keeps the test fast; the cache will be
    # synthetic (no socket present in test env) so prefetch is cheap.
    _run_battery_for_seed(
        grammar,
        registry,
        seed=42,
        max_candidates=2,
        calibration=calibration,
        timings=timings,
    )
    assert set(timings) == {"enumeration", "prefetch", "battery"}
    for k, v in timings.items():
        assert v >= 0.0, f"{k} should be non-negative"


# ---------------------------------------------------------------------------
# H-2 (audit 2026-05-29) — the feedback chain must analyze a COMPLETED batch
# (most real gated outcomes from reconcile), never the just-submitted 0-gated
# batch. `_select_feedback_target_batch` is the pure selector that decides it.
# ---------------------------------------------------------------------------


def test_select_feedback_target_picks_most_gated_batch() -> None:
    import uuid as _uuid

    from forge.cli.main import _select_feedback_target_batch

    a, b, c = _uuid.uuid4(), _uuid.uuid4(), _uuid.uuid4()
    # b has the most real gated outcomes -> richest signal -> target.
    assert _select_feedback_target_batch([(a, 5), (b, 40), (c, 12)]) == b


def test_select_feedback_target_none_when_nothing_gated() -> None:
    import uuid as _uuid

    from forge.cli.main import _select_feedback_target_batch

    a, b = _uuid.uuid4(), _uuid.uuid4()
    # No reconciled batch has gated outcomes -> nothing newly completed to learn
    # from -> None (caller skips the chain rather than analyzing 0-gated data).
    assert _select_feedback_target_batch([(a, 0), (b, 0)]) is None
    assert _select_feedback_target_batch([]) is None


# ---------------------------------------------------------------------------
# M-1 (audit 2026-05-29) — a single failing iteration must not crash the daemon
# into a systemd restart loop; SchemaVersionMismatch (§13.5) still hard-halts.
# ---------------------------------------------------------------------------


def test_loop_continues_after_failing_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time as _time

    from forge.cli import main as m

    calls: list[int] = []

    def _flaky(**_kwargs: object) -> str:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient boom")
        return "submitted"

    monkeypatch.setattr(m, "_run_one_iteration", _flaky)
    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--loop",
            "--max-iterations",
            "2",
            "--dry-run",
            "--inbox",
            str(tmp_path / "ib"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    # The first iteration raised; the loop logged it and ran the second anyway.
    assert len(calls) == 2


def test_loop_forwards_yield_map_flags_to_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (D185 deploy catch): the --loop path MUST forward the
    --cohort-yield / --regime-gate-yield A/B flags to ``_run_one_iteration``.
    They were initially wired only into the single-iteration call site (which sits
    at a shallower indent), so a replace_all missed the deeper loop-path call and
    the daemon ran both axes INERT despite the flags being set on the unit. A
    missing kwarg silently defaults to False, so only an explicit forward check
    catches it."""
    import time as _time

    from forge.cli import main as m

    captured: list[dict[str, object]] = []

    def _capture(**kwargs: object) -> str:
        captured.append(kwargs)
        return "submitted"

    monkeypatch.setattr(m, "_run_one_iteration", _capture)
    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)

    on = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--loop",
            "--max-iterations",
            "1",
            "--dry-run",
            "--cohort-yield",
            "--regime-gate-yield",
            "--quality-rank",
            "--inbox",
            str(tmp_path / "ib"),
        ],
    )
    assert on.exit_code == 0, on.stdout
    assert captured, "iteration never ran"
    assert captured[0]["cohort_yield"] is True
    assert captured[0]["regime_gate_yield"] is True
    assert captured[0]["quality_rank"] is True  # D185 lesson: forwarded through --loop
    # D196: the §7.3 throttle params must reach the loop call site too — a missing
    # kwarg silently takes _run_one_iteration's default (the exact D185 trap), so
    # the key's presence is what proves the deeper loop call wires it.
    assert "max_inflight" in captured[0]
    assert "stall_after_seconds" in captured[0]

    # and OFF (default) must forward False — the byte-identical contract in --loop
    captured.clear()
    off = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--loop",
            "--max-iterations",
            "1",
            "--dry-run",
            "--inbox",
            str(tmp_path / "ib2"),
        ],
    )
    assert off.exit_code == 0, off.stdout
    assert captured[0]["cohort_yield"] is False
    assert captured[0]["regime_gate_yield"] is False
    assert captured[0]["quality_rank"] is False


def test_loop_does_not_swallow_schema_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time as _time

    from crucible_contracts import SchemaVersionMismatch

    from forge.cli import main as m

    def _halt(**_kwargs: object) -> str:
        raise SchemaVersionMismatch("contracts drift")

    monkeypatch.setattr(m, "_run_one_iteration", _halt)
    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--loop",
            "--max-iterations",
            "2",
            "--dry-run",
            "--inbox",
            str(tmp_path / "ib"),
        ],
    )
    # §13.5: a contracts mismatch is a hard halt — it must propagate, not be
    # caught-and-continued like a transient error.
    assert result.exit_code != 0


def test_l9_loop_requires_crucible_db(tmp_path: Path) -> None:
    """L-9 (audit 2026-05-29): --loop without a Crucible DB must error (exit 2).

    The §7.3 rate limiter is the only backpressure against unbounded submission,
    and it's silently skipped when crucible_db is None — a loop would then submit
    a full batch every poll interval with zero throttle. Mirrors the --inbox guard.
    """
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--inbox",
            str(tmp_path / "inbox"),
            "--forge-db",
            str(tmp_path / "forge.db"),
            "--loop",
            "--max-iterations",
            "1",
            # deliberately NO --crucible-db
        ],
    )
    # exit 2 with --inbox supplied uniquely identifies the L-9 crucible-db guard
    # (the only remaining code-2 path on this invocation). The message goes to
    # stderr; its exact capture varies by Click version, so the exit code is the
    # contract we assert.
    assert result.exit_code == 2, result.output
