"""§5.5 auto-tune trigger — calibration adjustments from rolling promotion rate.

D024/D4: the §5.5 rule fires when the rolling 2-batch promotion rate
crosses a threshold:
  - Below `auto_tune.min_promotion_rate` (default 0.5%):
    propose a loosen (NOT applied — hard rule #4); writes to
    `OPEN_PROPOSALS.md` via `feedback.proposal_writer.append_proposal`.
  - Above `auto_tune.max_promotion_rate` (default 5%):
    apply tightening, write yaml back, write a `grammar_versions` row
    with `change_type='auto_tighten_calibration'` per §13.3.
  - In-band: no action.

Cumulative cap (`auto_tune.max_cumulative_adjustment`, default 30%) is
enforced by reading prior `grammar_versions` rows of the same change_type
and summing step sizes; if the next step would exceed the cap, the
auto-tune is a no-op for this invocation.

Structurally there is NO `apply_loosening` function (hard rule #4):
loosening always routes through `feedback.proposal_writer.append_proposal`.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING

import yaml

from forge.feedback.proposal_writer import append_proposal
from forge.feedback.types import GrammarProposal
from forge.prefilters.calibration import (
    AutoTuneCalibration,
    Calibration,
    apply_tightening,
    propose_adjustment,
)

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import duckdb

    from forge.grammar.models import Grammar


def write_calibration_yaml(calibration: Calibration, path: Path) -> None:
    """Serialize `Calibration` back to the §10.2 YAML shape, atomically.

    H-6 (audit 2026-05-29): the daemon re-reads this file via
    `load_calibration` at the top of EVERY iteration, and that loader raises on
    a missing-key/truncated file. A non-atomic `write_text` killed mid-flight
    (OOM, SIGTERM, power loss) would leave `prefilter.yaml` partial and brick
    the daemon into a 30s systemd crash-loop on the file the auto-tuner itself
    tunes. Write to a sibling tmp then `os.replace` (POSIX-atomic on the same
    filesystem) — mirrors `proposal_writer._atomic_write`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "prefilter": {
            "signal_density": asdict(calibration.signal_density),
            "expected_trade_count": asdict(calibration.expected_trade_count),
            "predicted_activations": asdict(calibration.predicted_activations),
            "novelty": asdict(calibration.novelty),
            "signal_correlation": asdict(calibration.signal_correlation),
            "regime_exposure": asdict(calibration.regime_exposure),
            "permutation_test": asdict(calibration.permutation_test),
            "auto_tune": asdict(calibration.auto_tune),
        }
    }
    content = yaml.safe_dump(data, sort_keys=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _rolling_promotion_rate(
    db: duckdb.DuckDBPyConnection,
    window: int,
) -> float | None:
    """Average of the last `window` batches' promotion_rate. None if
    insufficient batches with non-null promotion_rate."""
    rows = db.execute(
        """
        SELECT promotion_rate
        FROM batch_summaries
        WHERE promotion_rate IS NOT NULL
        ORDER BY submitted_at DESC
        LIMIT ?
        """,
        [window],
    ).fetchall()
    if len(rows) < window:
        return None
    rates = [float(r[0]) for r in rows]
    return sum(rates) / len(rates)


def _cumulative_tightenings(db: duckdb.DuckDBPyConnection) -> float:
    """Sum of prior auto-tighten step sizes from grammar_versions rows."""
    rows = db.execute(
        """
        SELECT change_description
        FROM grammar_versions
        WHERE change_type = 'auto_tighten_calibration'
        """,
    ).fetchall()
    total = 0.0
    for (descr,) in rows:
        if descr is None:
            continue
        for part in str(descr).split(","):
            kv = part.strip().split("=")
            if len(kv) == 2 and kv[0].strip() == "step_pct":
                try:
                    total += float(kv[1])
                except ValueError:
                    continue
    return total


def _write_grammar_versions_row(
    db: duckdb.DuckDBPyConnection,
    *,
    change_type: str,
    description: str,
    at: datetime,
) -> None:
    db.execute(
        """
        INSERT INTO grammar_versions
            (version, rule_count, yaml_sha256, changed_at, change_type,
             change_description, operator_initials)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"calib_{uuid.uuid4().hex[:8]}",
            0,
            "0" * 64,  # calibration changes don't touch grammar.yaml
            at,
            change_type,
            description,
            None,
        ],
    )


def ensure_grammar_version_recorded(
    db: duckdb.DuckDBPyConnection,
    *,
    grammar: Grammar,
    yaml_path: Path,
    at: datetime,
) -> bool:
    """Write a `grammar_versions` audit row for `grammar.grammar_version` if missing.

    D051 (2026-05-18): bridges the hard-rule-#10 audit trail for MANUAL operator
    yaml bumps, which don't pass through `apply-proposal` / `revert` / auto-tune
    (the three pre-D051 write paths). The D035 stuck-state grammar-change floor
    reads `MAX(grammar_versions.changed_at)`; without this self-healing helper,
    a manual grammar bump (like D039's R3 v1→v2) never wrote a row, so the
    stuck counter never reset on the bump.

    Idempotent: if a row for `grammar.grammar_version` already exists, this is
    a SELECT-only no-op. Returns True if a row was written, False if one was
    already present.
    """
    rows = db.execute(
        "SELECT 1 FROM grammar_versions WHERE version = ?",
        [grammar.grammar_version],
    ).fetchall()
    if rows:
        return False
    yaml_bytes = yaml_path.read_bytes()
    sha = hashlib.sha256(yaml_bytes).hexdigest()
    db.execute(
        """
        INSERT INTO grammar_versions
            (version, rule_count, yaml_sha256, changed_at, change_type,
             change_description, operator_initials)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            grammar.grammar_version,
            len(grammar.rules),
            sha,
            at,
            "manual_bump",
            f"auto-recorded on first load post-bump for {grammar.grammar_version}",
            None,
        ],
    )
    return True


def _apply_tighten_and_persist(
    *,
    db: duckdb.DuckDBPyConnection,
    calibration: Calibration,
    yaml_path: Path,
    auto_tune_cfg: AutoTuneCalibration,
    at: datetime,
) -> Calibration:
    proposal = propose_adjustment(
        calibration,
        direction="tighten",
        reason="auto_tighten: rolling promotion rate above max threshold",
    )
    new_cal = apply_tightening(calibration, proposal)
    # M-11 (audit 2026-05-29): write the grammar_versions audit row BEFORE the
    # YAML mutation. The §5.5 cumulative-tightening cap sums recorded step_pcts;
    # if the process dies between the two writes, the safe failure is
    # recorded-but-not-applied (next run's cap over-counts -> conservative). The
    # old order (yaml first) failed the other way: applied-but-not-recorded ->
    # the cap under-counts and silently permits tightening past 30%. The YAML
    # write is atomic (D086) so it cannot leave a half-written file.
    _write_grammar_versions_row(
        db,
        change_type="auto_tighten_calibration",
        description=f"step_pct={auto_tune_cfg.adjustment_pct_per_step:.4f}",
        at=at,
    )
    write_calibration_yaml(new_cal, yaml_path)
    return new_cal


def _write_loosen_proposal(
    *,
    db: duckdb.DuckDBPyConnection,
    auto_tune_cfg: AutoTuneCalibration,
    open_proposals_path: Path,
    at: datetime,
) -> None:
    proposal = GrammarProposal(
        proposal_id=uuid.uuid4(),
        proposed_at=at,
        proposal_type="loosen",
        target="prefilter_calibration",
        proposal_yaml=(
            "# Proposed pre-filter loosening — rolling promotion rate "
            "below min threshold\n"
            f"# step_pct: {auto_tune_cfg.adjustment_pct_per_step:.4f}\n"
        ),
        rationale=(
            "Rolling 2-batch promotion rate is below "
            f"{auto_tune_cfg.min_promotion_rate:.4f}; propose loosening "
            f"pre-filter thresholds by "
            f"{auto_tune_cfg.adjustment_pct_per_step:.0%}."
        ),
        evidence_json={"trigger": "auto_tune_loosen"},
    )
    append_proposal(proposal, open_proposals_path=open_proposals_path, db=db)


def auto_tune(
    *,
    db: duckdb.DuckDBPyConnection,
    calibration: Calibration,
    prefilter_yaml_path: Path,
    open_proposals_path: Path,
    at: datetime,
    rolling_window_batches: int = 2,
) -> Calibration:
    """Run the §5.5 auto-tune step; return possibly-updated Calibration."""
    if at.tzinfo is None:
        msg = "auto_tune: at must be timezone-aware"
        raise ValueError(msg)
    if not calibration.auto_tune.enabled:
        return calibration

    rolling = _rolling_promotion_rate(db, rolling_window_batches)
    if rolling is None:
        return calibration

    cfg = calibration.auto_tune

    if rolling > cfg.max_promotion_rate:
        cumulative = _cumulative_tightenings(db)
        if cumulative + cfg.adjustment_pct_per_step > cfg.max_cumulative_adjustment:
            return calibration
        return _apply_tighten_and_persist(
            db=db,
            calibration=calibration,
            yaml_path=prefilter_yaml_path,
            auto_tune_cfg=cfg,
            at=at,
        )

    if rolling < cfg.min_promotion_rate:
        _write_loosen_proposal(
            db=db,
            auto_tune_cfg=cfg,
            open_proposals_path=open_proposals_path,
            at=at,
        )
        return calibration

    return calibration


__all__ = [
    "auto_tune",
    "write_calibration_yaml",
]
