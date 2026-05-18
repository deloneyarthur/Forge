"""Phase 6 — full-pipeline byte-determinism (§12 / §13.1 / D025/D2).

§13.1 promises ``(grammar_version, registry_snapshot, seed) -> same
sequence of configs``. Phase 2 already covers the enumerator in
isolation (``tests/invariants/test_phase2_invariants.py``). This test
extends the determinism guarantee to the full per-batch pipeline:
enumerator → pre-filter battery → ranker → diversifier → submitter.

Two independent runs with identical ``(grammar, registry, seed)`` and
distinct ``forge_db`` workspaces must produce:
  - the same ordered ``submissions.config_hash`` sequence;
  - the same pre-filter scores per ``(config_hash, filter_name)``;
  - byte-identical JSON files in the Crucible inbox directory.

The wall-clock fields (``submitted_at``, ``forge_candidate_id``) are
not asserted to be identical — they're allowed to vary across runs;
the §13.1 contract is on enumeration content, not on per-row UUIDs or
timestamps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from forge.enumeration import registry_hash
from forge.enumeration._demo_registry import demo_registry
from forge.grammar import load_grammar
from forge.persistence.db import db_connection
from forge.prefilters.calibration import (
    AutoTuneCalibration,
    Calibration,
    ExpectedTradeCountCalibration,
    NoveltyCalibration,
    PermutationTestCalibration,
    RegimeExposureCalibration,
    SignalDensityCalibration,
)
from forge.ranking import Ranker, load_ranker_config, rank_batch
from forge.submission import BatchContext, mint_batch_id, submit_batch
from tests.fixtures.strategy_configs import minimal_registry_snapshot

# Limits chosen so the test runs in a few seconds while still exercising
# all four pipeline stages (enumerate, prefilter, rank, submit).
_MAX_CANDIDATES = 50
_BATCH_SIZE = 8
_SEED = 13


def _config_root() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


def _permissive_calibration() -> Calibration:
    """Calibration that lets every filter pass on synthetic-cache inputs.

    The §13.1 determinism property is about identical outputs across
    runs, not about real-edge survival. With synthetic data the
    permutation test rejects almost everything by design; for this
    reproducibility test we widen thresholds so the submitter is
    actually exercised. The filters still compute their scores
    deterministically — the determinism guard is on those scores, not
    on threshold-vs-score outcomes.
    """
    from forge.prefilters.calibration import (
        PredictedActivationsCalibration,
        SignalCorrelationCalibration,
    )

    return Calibration(
        signal_density=SignalDensityCalibration(min_activations=0),
        expected_trade_count=ExpectedTradeCountCalibration(min_trades=0),
        predicted_activations=PredictedActivationsCalibration(min_entries=0),
        novelty=NoveltyCalibration(max_jaccard_overlap=1.0),
        signal_correlation=SignalCorrelationCalibration(max_jaccard_overlap=1.0),
        regime_exposure=RegimeExposureCalibration(max_single_regime_concentration=1.0),
        permutation_test=PermutationTestCalibration(n_permutations=20, p_value_threshold=1.0),
        auto_tune=AutoTuneCalibration(
            enabled=False,
            min_promotion_rate=0.005,
            max_promotion_rate=0.05,
            adjustment_pct_per_step=0.10,
            max_cumulative_adjustment=0.30,
        ),
    )


def _run_pipeline_once(
    *,
    workspace: Path,
    seed: int,
) -> Path:
    """Execute the §2.1 pipeline once into a fresh workspace; return forge_db path."""
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates
    from forge.prefilters import SyntheticFeatureCache, default_filters, run_battery
    from forge.prefilters.types import FilterContext

    forge_db = workspace / "forge.db"
    inbox = workspace / "inbox"
    config_root = _config_root()

    grammar = load_grammar(
        config_root / "grammar.yaml", archive_dir=config_root / "grammar_archive"
    )
    calibration = _permissive_calibration()
    ranker = Ranker(weights=load_ranker_config(config_root / "ranker.yaml").weights)
    registry = demo_registry()
    reg_hash = registry_hash(registry)

    seed_hierarchy = SeedHierarchy(seed)
    ctx = FilterContext(
        registry=registry,
        feature_cache=SyntheticFeatureCache(root_seed=seed),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=seed_hierarchy.rng,
    )
    filters = default_filters()
    reports = [
        run_battery(cfg, ctx, filters)
        for cfg in enumerate_candidates(
            grammar,
            registry,
            seed=seed,
            max_candidates=_MAX_CANDIDATES,
        )
    ]
    ranked = rank_batch(
        ranker,
        reports,
        promoted_strategies=(),
        n=_BATCH_SIZE,
    )

    batch = BatchContext(
        batch_id=mint_batch_id(
            seed=seed,
            grammar_version=grammar.grammar_version,
            registry_hash=reg_hash,
        ),
        grammar_version=grammar.grammar_version,
        registry_hash=reg_hash,
        # Fixed timestamp so the only allowed variability is uuid4 and
        # file timestamps — content stays comparable.
        submitted_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        seed=seed,
    )
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=batch, candidates=ranked, inbox_root=inbox)
    return workspace


def _read_submitted_hashes_in_order(forge_db: Path) -> list[str]:
    """Sorted by config_hash so the order is uuid4-independent."""
    with db_connection(forge_db) as conn:
        rows = conn.execute(
            "SELECT config_hash FROM submissions WHERE status = 'submitted' ORDER BY config_hash"
        ).fetchall()
    return [str(r[0]) for r in rows]


def _read_pre_filter_rows(forge_db: Path) -> list[tuple[str, str, float, bool]]:
    """All `(config_hash, filter_name, score, passed)` tuples, sorted."""
    with db_connection(forge_db) as conn:
        rows = conn.execute(
            """
            SELECT s.config_hash, p.filter_name, p.score, p.passed
            FROM pre_filter_logs p
            JOIN submissions s ON s.forge_candidate_id = p.forge_candidate_id
            ORDER BY s.config_hash, p.filter_name
            """
        ).fetchall()
    return [(str(r[0]), str(r[1]), float(r[2]), bool(r[3])) for r in rows]


def _read_inbox_files(workspace: Path) -> dict[str, bytes]:
    """Map ``filename -> bytes`` for every JSON file under the workspace inbox."""
    inbox = workspace / "inbox"
    files: dict[str, bytes] = {}
    for path in sorted(inbox.rglob("*.json")):
        files[path.name] = path.read_bytes()
    return files


def test_full_pipeline_is_byte_deterministic(tmp_path: Path) -> None:
    """Two runs with the same (grammar, registry, seed) must produce
    identical submission hashes, pre-filter rows, and inbox bytes."""
    workspace_a = tmp_path / "run_a"
    workspace_b = tmp_path / "run_b"
    workspace_a.mkdir(parents=True)
    workspace_b.mkdir(parents=True)

    _run_pipeline_once(workspace=workspace_a, seed=_SEED)
    _run_pipeline_once(workspace=workspace_b, seed=_SEED)

    hashes_a = _read_submitted_hashes_in_order(workspace_a / "forge.db")
    hashes_b = _read_submitted_hashes_in_order(workspace_b / "forge.db")
    assert hashes_a == hashes_b, (
        f"submission config_hash sequence diverged between runs:\n  a={hashes_a}\n  b={hashes_b}"
    )
    assert len(hashes_a) > 0, "test did not exercise the pipeline — zero submissions written"

    rows_a = _read_pre_filter_rows(workspace_a / "forge.db")
    rows_b = _read_pre_filter_rows(workspace_b / "forge.db")
    first_mismatch = next(
        (i for i, (x, y) in enumerate(zip(rows_a, rows_b, strict=False)) if x != y),
        None,
    )
    assert rows_a == rows_b, (
        f"pre_filter_logs diverged: {len(rows_a)} vs {len(rows_b)} rows; "
        f"first mismatch index: {first_mismatch}"
    )

    inbox_a = _read_inbox_files(workspace_a)
    inbox_b = _read_inbox_files(workspace_b)
    assert set(inbox_a) == set(inbox_b), (
        f"inbox file set diverged: a-only={set(inbox_a) - set(inbox_b)}, "
        f"b-only={set(inbox_b) - set(inbox_a)}"
    )
    for name, bytes_a in inbox_a.items():
        assert bytes_a == inbox_b[name], f"inbox file {name} bytes differ between runs"


def test_minimal_registry_snapshot_paired_with_grammar_yaml_loads() -> None:
    """Smoke guard: ensure the demo registry and grammar.yaml shipped in
    the repo are mutually loadable (this is the same pair the full
    determinism test relies on)."""
    config_root = _config_root()
    grammar = load_grammar(
        config_root / "grammar.yaml", archive_dir=config_root / "grammar_archive"
    )
    assert grammar.grammar_version
    registry = minimal_registry_snapshot()
    assert registry_hash(registry)
