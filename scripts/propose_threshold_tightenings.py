"""D073 / Phase 3 — operator-driven threshold-tightening proposer.

Walks the most-recent `gated_runs_*.json` export, cross-references
config_hashes against Forge's `submissions` table, and computes
per-(indicator, role) tightened threshold ranges from the configs
that produced >= 10 trades.

Writes:
  - `config/auto_tightened_thresholds.yaml` (overwrites; tighten-only)
  - `OPEN_PROPOSALS.md` appended with any loosening proposals (operator
    review required per hard rule #4).

After running:
  systemctl --user restart forge.service

to pick up the new ranges in the next iteration.

Usage:
    .venv/bin/python scripts/propose_threshold_tightenings.py

    .venv/bin/python scripts/propose_threshold_tightenings.py \\
        --gated-runs-export /home/aj/optbt_data/exports/gated_runs_LATEST.json \\
        --forge-db /home/aj/forge_data/forge.db \\
        --high-trade-floor 10 \\
        --min-samples 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root so `forge` imports work when run as a script
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def _baseline_table_from_d031() -> dict[
    str, tuple[float | None, float | None, float | None, float | None]
]:
    """Flatten the D031 _INDICATOR_THRESHOLD_TABLE into the shape the
    proposer expects: indicator_id → (d_low, d_high, r_low, r_high).
    None for skip indicators or roles without a range."""
    from forge.enumeration.indicator_thresholds import _INDICATOR_THRESHOLD_TABLE
    out: dict[str, tuple[float | None, float | None, float | None, float | None]] = {}
    for ind_id, spec in _INDICATOR_THRESHOLD_TABLE.items():
        if spec.is_skip:
            out[ind_id] = (None, None, None, None)
            continue
        d = spec.directional_range or (None, None)
        r = spec.regime_range or (None, None)
        out[ind_id] = (d[0], d[1], r[0], r[1])
    return out


def _resolve_latest_export(exports_dir: Path) -> Path | None:
    candidates = sorted(exports_dir.glob("gated_runs_*.json"))
    return candidates[-1] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gated-runs-export", type=Path, default=None,
        help="Path to a gated_runs JSON export. Default: latest in "
        "~/optbt_data/exports/.",
    )
    parser.add_argument(
        "--exports-dir", type=Path,
        default=Path.home() / "optbt_data" / "exports",
        help="Directory to scan for the latest gated_runs export.",
    )
    parser.add_argument(
        "--forge-db", type=Path,
        default=Path.home() / "forge_data" / "forge.db",
        help="Path to Forge's submissions DB.",
    )
    parser.add_argument(
        "--out-yaml", type=Path,
        default=_REPO_ROOT / "config" / "auto_tightened_thresholds.yaml",
        help="Where to write the tightenings YAML.",
    )
    parser.add_argument(
        "--open-proposals", type=Path,
        default=_REPO_ROOT / "OPEN_PROPOSALS.md",
        help="Where to append loosening proposals.",
    )
    parser.add_argument("--high-trade-floor", type=int, default=10)
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print proposals but don't write files.",
    )
    args = parser.parse_args()

    # Resolve export path
    export_path = args.gated_runs_export or _resolve_latest_export(args.exports_dir)
    if export_path is None or not export_path.exists():
        print(
            f"error: no gated_runs export found "
            f"(looked at {args.exports_dir}); pass --gated-runs-export",
            file=sys.stderr,
        )
        return 1

    # Load gated_runs (using the contracts helper for schema-version validation)
    from crucible_contracts import load_recent_gated_runs_from_export
    gated_runs = load_recent_gated_runs_from_export(args.exports_dir, limit=10000)
    print(f"Loaded {len(gated_runs)} gated_runs from {export_path.name}")

    # Open Forge DB
    from forge.persistence.db import db_connection
    with db_connection(args.forge_db) as conn:
        from forge.feedback.threshold_proposer import (
            propose_threshold_tightenings,
            write_loosening_proposals_to_open_proposals,
            write_tightenings_to_yaml,
        )
        baseline = _baseline_table_from_d031()
        proposals = propose_threshold_tightenings(
            conn,
            gated_runs,
            baseline_table=baseline,
            high_trade_floor=args.high_trade_floor,
            min_high_trade_samples=args.min_samples,
        )

    print(f"\n=== {len(proposals)} proposals across (indicator, role) pairs ===")
    print(
        f"  {'indicator':<25} {'role':<14} "
        f"{'baseline':<22} {'proposed':<22} {'n':>4} dir",
    )
    for p in sorted(proposals, key=lambda x: (x.indicator_id, x.role)):
        print(
            f"  {p.indicator_id:<25} {p.role:<14} "
            f"[{p.baseline_low:>7.3f}, {p.baseline_high:>7.3f}]   "
            f"[{p.proposed_low:>7.3f}, {p.proposed_high:>7.3f}] "
            f"{p.n_high_trade_samples:>4} {p.direction}",
        )

    if args.dry_run:
        print("\n(--dry-run: not writing files)")
        return 0

    n_tightened = write_tightenings_to_yaml(
        proposals, args.out_yaml, cohort_size=len(gated_runs),
    )
    print(f"\nWrote {n_tightened} tightenings → {args.out_yaml}")

    n_loosened = write_loosening_proposals_to_open_proposals(
        proposals, args.open_proposals, cohort_size=len(gated_runs),
    )
    print(f"Appended {n_loosened} loosening proposals → {args.open_proposals}")

    print(
        "\nNext step: `systemctl --user restart forge.service` "
        "to pick up the new ranges on next iter.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
