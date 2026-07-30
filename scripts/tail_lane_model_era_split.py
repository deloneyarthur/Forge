"""Split the live tail-arm read by WHICH tail artifact actually ranked each batch.

Why this exists: the daily trainer was wired to publish two tail artifacts
(`target_sharpe_baseline` top-800 for the MR lane, `target_wf_p10` top-200 for the trend
lane) BEFORE `load_latest_tail_model` gained its `base_target=` filter, so for two of four
days the newest-by-(trained_through, model_id) resolution handed the 95-slot tail lane the
wf_p10 artifact -- scored on the FULL survivor population rather than the trend slice it was
fitted on. The journal recorded it honestly (`base=` on every ACTIVE line); the first
resolution of prereg 8cfe95f4a6e9 did not read that field.

The accident is an informative natural experiment: two targets, same 95 slots, same merit
control, interleaved in time so drift cancels within each era. This script recovers the
per-era attribution so the confirmed lift is assigned to the right objective.

Input is a (batch_id, model_id, base_target, n_pos) TSV extracted from the journal, since the
journal is the only record of which artifact was live for a given batch:

    journalctl --user -u forge.service --since 2026-07-26 --no-pager \\
      | sed -E 's/.*forge\\[[0-9]+\\]: //' \\
      | grep -oE "tail_lane: ACTIVE .*model=[a-f0-9]+ base=[a-z_0-9]+ top-[0-9]+|^batch_id=..."

Usage: tail_lane_model_era_split.py SNAPSHOT.db BATCH_MODEL_MAP.tsv
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

# The weakest component ever used in a promoted book, measured at ADMISSION time (Crucible's
# later 0.9115 refit was retracted). Anything below this has never been book-usable.
BOOK_FLOOR = 0.9439

# Both arms need enough decided configs for a per-batch ratio to mean anything; this is the
# same threshold the prereg was resolved on.
MIN_DECIDED_PER_ARM = 20

_ARMS = ("tail_lane", "ranked")


def _load_era_map(path: Path) -> dict[str, tuple[str, str]]:
    """batch_id -> (base_target, n_pos) for every batch a tail lane ranked."""
    era: dict[str, tuple[str, str]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        batch_id, _model_id, base, n_pos = line.split("\t")
        era[batch_id] = (base, n_pos)
    return era


def _fetch_arm_counts(snap: Path, batch_ids: list[str]) -> dict[tuple[str, str], list[int]]:
    """(batch_id, arm) -> [decided, components, strong]."""
    agg: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    with db_connection(snap) as conn:
        conn.execute("CREATE TEMP TABLE era_batches (batch_id VARCHAR)")
        conn.executemany("INSERT INTO era_batches VALUES (?)", [(b,) for b in batch_ids])
        rows = conn.execute(
            """
            SELECT CAST(s.forge_batch_id AS VARCHAR),
                   s.selection_mode,
                   v.decision,
                   TRY_CAST(
                       json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
                   )
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            JOIN era_batches e ON e.batch_id = CAST(s.forge_batch_id AS VARCHAR)
            WHERE s.selection_mode IN ('tail_lane', 'ranked')
            """
        ).fetchall()
    for batch_id, arm, decision, cpcv in rows:
        cell = agg[(batch_id, arm)]
        cell[0] += 1
        if decision == "component":
            cell[1] += 1
            if cpcv is not None and cpcv >= BOOK_FLOOR:
                cell[2] += 1
    return agg


def _era_read(
    batches: list[str], agg: dict[tuple[str, str], list[int]]
) -> tuple[list[int], list[float], int]:
    """Pooled [t_dec, t_comp, t_strong, m_dec, m_comp, m_strong], per-batch ratios, wins."""
    pooled = [0] * 6
    ratios: list[float] = []
    wins = 0
    for b in batches:
        t = agg.get((b, "tail_lane"), [0, 0, 0])
        m = agg.get((b, "ranked"), [0, 0, 0])
        for i in range(3):
            pooled[i] += t[i]
            pooled[3 + i] += m[i]
        if t[0] < MIN_DECIDED_PER_ARM or m[0] < MIN_DECIDED_PER_ARM:
            continue
        t_rate, m_rate = t[2] / t[0], m[2] / m[0]
        if m_rate == 0:
            # A shut-out counts as a win but carries no finite ratio to average.
            if t_rate > 0:
                wins += 1
                ratios.append(float("inf"))
            continue
        ratios.append(t_rate / m_rate)
        if t_rate / m_rate >= 1.5:
            wins += 1
    return pooled, ratios, wins


def main() -> int:
    snap, mapping_path = Path(sys.argv[1]), Path(sys.argv[2])
    era = _load_era_map(mapping_path)
    agg = _fetch_arm_counts(snap, list(era))

    by_era: dict[tuple[str, str], list[str]] = defaultdict(list)
    for batch_id, key in era.items():
        by_era[key].append(batch_id)

    print(f"{'era':<40} {'batches':>7} {'tail%':>8} {'merit%':>8} {'ratio':>7} {'>=1.5x':>9}")
    print("-" * 84)
    detail: list[str] = []
    for key in sorted(by_era, key=lambda k: -len(by_era[k])):
        base, n_pos = key
        pooled, ratios, wins = _era_read(by_era[key], agg)
        t_dec, t_comp, t_str, m_dec, m_comp, m_str = pooled
        t_rate = t_str / max(t_dec, 1)
        m_rate = m_str / max(m_dec, 1)
        usable = len(ratios)
        label = f"{base} top-{n_pos}"
        print(
            f"{label:<40} {usable:>7} {100 * t_rate:>7.3f}% {100 * m_rate:>7.3f}% "
            f"{t_rate / max(m_rate, 1e-12):>7.2f} {f'{wins}/{usable}':>9}"
        )
        finite = [r for r in ratios if r != float("inf")]
        med = statistics.median(finite) if finite else float("nan")
        detail.append(
            f"  {label}: tail {t_str}/{t_dec} strong ({100 * t_rate:.3f}%), "
            f"comp {t_comp}/{t_dec} ({100 * t_comp / max(t_dec, 1):.1f}%) | "
            f"merit {m_str}/{m_dec} ({100 * m_rate:.3f}%), "
            f"comp {m_comp}/{m_dec} ({100 * m_comp / max(m_dec, 1):.1f}%) | "
            f"median per-batch ratio {med:.2f}"
        )

    print("\nPOOLED DETAIL")
    for line in detail:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
