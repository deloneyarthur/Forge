"""Q39 follow-up — option_momentum `min_months` x percentile activation sweep.

WHY: At the v18 cut (D135/Q39) we HELD `option_momentum` after an ad-hoc
FeatureCacheClient sweep read it data-starved (0 non-NaN bars on 6/10 names,
max 146 on KO) at "every parameterization incl. percentile". Crucible's reply
(`../Crucible/docs/handoffs/FORGE_option_momentum_coverage_response.md`,
2026-06-12) says that read mistook the *cause*: the zeros are the shipped
default `min_months = months = 6` (six CONSECUTIVE clean months) colliding with
a ~40% honest per-month exit-match miss, NOT a coverage hole. At `min_months=4`
every probed name clears the floor by 5-16x. The percentile observation ("tops
out at 26") was the SAME sparsity ceiling measured at `min_months=6`.

This script (a) closes the reproducibility gap Crucible flagged on our side —
their probe is committed as `scripts/probe_option_momentum_coverage.py`, ours
never was — and (b) answers the one question their reply leaves open for us:

  Does Crucible's option_momentum computation READ `min_months` from the
  per-config SignalSpec params (like `rv_rank` reads `rv_window`), so Forge can
  self-serve the unblock — or is it a global default, so the unblock needs a
  Crucible republish (option_momentum v2)?

The sweep is self-diagnosing because `signal_content_key` hashes the FULL params
dict: `min_months=4` and `min_months=6` are distinct cache keys, so if the
writer's computation reads the param the counts DIVERGE; if it ignores params
they are IDENTICAL. We also bank an audited percentile activation count at a
shippable selectivity (top-20% momentum) so a future activation is a calibrated
table add, and a `rsi_2` control per name to prove the cache is live (the
2026-05-28 synthetic-fallback RCA: never read a dead/synthetic cache as signal).

Read-only: issues `activation_dates` queries over the SAME writer socket the §5
prefilter uses every batch. No submissions, no writes. Note it computes up to
6 option_momentum series-variants x N names on the live writer — a one-time
compute spike (cf. the v18 first-battery ~28 min new-series cost).

Usage:
    uv run python scripts/probe_option_momentum_min_months.py
    uv run python scripts/probe_option_momentum_min_months.py \\
        --data-root /home/aj/optbt_data --data-history-days 2400 \\
        --out probe_results/option_momentum_min_months_sweep.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from crucible_contracts import (
    FeatureCacheClient,
    FeatureCacheUnavailableError,
    SignalSpec,
    signal_content_key,
)

# Crucible's probe window (their reply: "closest match to your data_history_days
# =2400"); keep it so our counts cross-check against their section-2 table.
DEFAULT_DATA_HISTORY_DAYS = 2400
# Mirrors forge.enumeration.indicator_thresholds._PERCENTILE_WINDOW (1 trading yr).
PERCENTILE_WINDOW = 252
# forge.enumeration default months for the monthly-straddle construction.
DEFAULT_MONTHS = 6
# §5.3.3 signal_density floor (calibration.signal_density.min_activations).
MIN_ACTIVATIONS_FLOOR = 30
# Percentile thresholds (op ">" = the option-momentum thesis: buy recent
# winners). 0.0 fires on ~every non-NaN bar -> an AVAILABILITY proxy that
# reproduces Crucible's non-NaN table; 0.80 = top-20%, a shippable SELECTIVITY.
AVAIL_THRESHOLD = 0.0
SELECT_THRESHOLD = 0.80
# Crucible's 10 probed names (their section-1/2 tables), in their order.
PROBE_NAMES: tuple[str, ...] = (
    "MSFT",
    "AMZN",
    "GOOGL",
    "META",
    "NFLX",
    "TSLA",
    "AMD",
    "AAPL",
    "KO",
    "NVDA",
)
# Column order for the printed/JSON table. `default_*` omits min_months entirely
# (== the shipped global default) so we can tell "param ignored" (default==mm6==
# mm4) from "param read" (mm4 >> default==mm6).
_COLUMNS: tuple[str, ...] = (
    "control_rsi_2",
    "default_avail",
    "mm6_avail",
    "mm4_avail",
    "mm3_avail",
    "mm4_select",
    "mm3_select",
)


def _option_momentum_spec(*, min_months: int | None, threshold: float) -> SignalSpec:
    """A directional option_momentum threshold spec in percentile mode.

    `min_months=None` omits both monthly-construction knobs (the global-default
    baseline). The op is ">" — fire when the name's straddle return ranks high
    vs its own trailing window (the momentum direction; percentile normalizes
    the cross-name IV-level offset Crucible's section 3 flags).
    """
    params: dict[str, object] = {
        "threshold": threshold,
        "op": ">",
        "use_percentile": True,
        "percentile_window": PERCENTILE_WINDOW,
    }
    if min_months is not None:
        params["min_months"] = min_months
        params["months"] = DEFAULT_MONTHS
    return SignalSpec(
        id=f"om_mm{min_months}_t{threshold}",
        type="threshold",
        role="directional",
        indicators=("option_momentum",),
        params=params,
    )


def _control_spec() -> SignalSpec:
    """rsi_2 directional in percentile mode — a liveness control.

    rsi_2 is healthy on every name (~2,119 bars in the v18 / Q39 probe), so a
    near-zero count here means the cache is dead/synthetic, not that
    option_momentum is starved — exit loudly in that case.
    """
    return SignalSpec(
        id="ctrl_rsi_2",
        type="threshold",
        role="directional",
        indicators=("rsi_2",),
        params={
            "threshold": 0.20,
            "op": "<",
            "use_percentile": True,
            "percentile_window": PERCENTILE_WINDOW,
        },
    )


def _labeled_specs() -> list[tuple[str, SignalSpec]]:
    """The per-name probe matrix, paired with their `_COLUMNS` labels."""
    return [
        ("control_rsi_2", _control_spec()),
        ("default_avail", _option_momentum_spec(min_months=None, threshold=AVAIL_THRESHOLD)),
        ("mm6_avail", _option_momentum_spec(min_months=6, threshold=AVAIL_THRESHOLD)),
        ("mm4_avail", _option_momentum_spec(min_months=4, threshold=AVAIL_THRESHOLD)),
        ("mm3_avail", _option_momentum_spec(min_months=3, threshold=AVAIL_THRESHOLD)),
        ("mm4_select", _option_momentum_spec(min_months=4, threshold=SELECT_THRESHOLD)),
        ("mm3_select", _option_momentum_spec(min_months=3, threshold=SELECT_THRESHOLD)),
    ]


def _probe_name(
    client: FeatureCacheClient,
    name: str,
    labeled: list[tuple[str, SignalSpec]],
    data_history_days: int,
) -> dict[str, int | None]:
    """One batched `activation_dates` round-trip for `name`; counts per column.

    A column value of None means the writer returned no `activation_dates` entry
    for that spec (distinct from 0 = computed-but-never-fires).
    """
    specs = tuple(spec for _, spec in labeled)
    response = client.get_features(
        signals=specs,
        feature_names=("activation_dates",),
        data_history_days=data_history_days,
        underlying=name,
    )
    counts: dict[str, int | None] = {}
    for label, spec in labeled:
        feature_map = response.features.get(signal_content_key(spec))
        if feature_map is None or "activation_dates" not in feature_map:
            counts[label] = None
        else:
            counts[label] = len(feature_map["activation_dates"])
    return counts


def _fmt(value: int | None) -> str:
    return "  --" if value is None else f"{value:>4}"


def _emit_table(results: dict[str, dict[str, int | None]]) -> None:
    header = f"{'name':<6} " + " ".join(f"{c:>12}" for c in _COLUMNS)
    print(header)
    print("-" * len(header))
    for name, row in results.items():
        cells = " ".join(f"{_fmt(row.get(c)):>12}" for c in _COLUMNS)
        print(f"{name:<6} {cells}")


def _emit_verdict(results: dict[str, dict[str, int | None]]) -> bool:
    """Print the mechanism + viability verdict; return True if the cache looks live."""

    def total(column: str) -> int:
        return sum((results[n].get(column) or 0) for n in results)

    control_live = sum(1 for n in results if (results[n].get("control_rsi_2") or 0) >= 100)
    default_t, mm6_t, mm4_t, mm3_t = (
        total("default_avail"),
        total("mm6_avail"),
        total("mm4_avail"),
        total("mm3_avail"),
    )
    baseline = max(default_t, mm6_t)
    viable_mm4 = sum(
        1 for n in results if (results[n].get("mm4_select") or 0) >= MIN_ACTIVATIONS_FLOOR
    )
    viable_mm3 = sum(
        1 for n in results if (results[n].get("mm3_select") or 0) >= MIN_ACTIVATIONS_FLOOR
    )

    print()
    print(f"control rsi_2 live (>=100 acts) on {control_live}/{len(results)} names")
    print(f"availability totals  default={default_t}  mm6={mm6_t}  mm4={mm4_t}  mm3={mm3_t}")
    # Param read iff dropping min_months to 4 clearly lifts availability over the
    # shipped-default baseline (the section-2 prediction: 0 -> hundreds).
    if mm4_t >= max(2 * baseline, baseline + 100):
        print(
            "MECHANISM: min_months IS read per-config -> Forge can self-serve "
            "(sampler param, no Crucible republish)."
        )
    elif baseline == 0 and mm4_t == 0:
        print(
            "MECHANISM: still 0 at mm4 -> param NOT taking effect; needs a "
            "Crucible republish (option_momentum v2, lower default)."
        )
    else:
        print(
            "MECHANISM: inconclusive — mm4 did not clearly separate from the "
            "default/mm6 baseline; inspect the table by hand."
        )
    print(
        f"VIABILITY (top-20% selectivity, floor={MIN_ACTIVATIONS_FLOOR}): "
        f"mm4 clears on {viable_mm4}/{len(results)} names, mm3 on {viable_mm3}."
    )
    return control_live >= (len(results) + 1) // 2


def _registry_provenance(data_root: Path) -> dict[str, str]:
    """Best-effort: record the newest registry snapshot's name + exported_at.

    Avoids a wall-clock stamp (DTZ / determinism); the snapshot's own
    `exported_at` dates the data we measured against.
    """
    exports = sorted((data_root / "exports").glob("registry_snapshot_*.json"))
    if not exports:
        return {}
    latest = exports[-1]
    try:
        snap = json.loads(latest.read_text())
        # `exported_at` is null in current snapshots; `snapshot_taken_at` carries
        # the real stamp.
        stamp = snap.get("exported_at") or snap.get("snapshot_taken_at") or ""
    except (OSError, ValueError):
        stamp = ""
    return {"registry_snapshot": latest.name, "snapshot_taken_at": str(stamp)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.home() / "optbt_data")
    parser.add_argument("--data-history-days", type=int, default=DEFAULT_DATA_HISTORY_DAYS)
    parser.add_argument("--names", nargs="*", default=list(PROBE_NAMES))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("probe_results/option_momentum_min_months_sweep.json"),
    )
    args = parser.parse_args(argv)

    data_root: Path = args.data_root
    socket_path = data_root / "db_writer.sock"
    authkey_path = data_root / "db_writer.authkey"
    db_path = data_root / "runs.duckdb"
    if not (socket_path.exists() and authkey_path.exists()):
        print(f"ERROR: writer socket/authkey not found under {data_root}", file=sys.stderr)
        return 2

    labeled = _labeled_specs()
    client = FeatureCacheClient(socket_path=socket_path, authkey_path=authkey_path, db_path=db_path)
    print(
        f"probing option_momentum on {len(args.names)} names "
        f"(data_history_days={args.data_history_days}); one batched read each.\n"
    )
    results: dict[str, dict[str, int | None]] = {}
    errors: dict[str, str] = {}
    try:
        for name in args.names:
            try:
                results[name] = _probe_name(client, name, labeled, args.data_history_days)
            except FeatureCacheUnavailableError as exc:
                errors[name] = str(exc)
                print(f"  {name}: writer unavailable: {exc}", file=sys.stderr)
    finally:
        client.close()

    if not results:
        print("ERROR: every name failed — writer unreachable.", file=sys.stderr)
        return 2

    _emit_table(results)
    cache_live = _emit_verdict(results)

    payload = {
        "probe": "option_momentum_min_months_sweep",
        "data_history_days": args.data_history_days,
        "percentile_window": PERCENTILE_WINDOW,
        "months": DEFAULT_MONTHS,
        "min_activations_floor": MIN_ACTIVATIONS_FLOOR,
        "avail_threshold": AVAIL_THRESHOLD,
        "select_threshold": SELECT_THRESHOLD,
        "columns": list(_COLUMNS),
        "results": results,
        "errors": errors,
        **_registry_provenance(data_root),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"\nwrote {args.out}")

    if not cache_live:
        print(
            "ERROR: rsi_2 control unhealthy on most names — cache may be "
            "synthetic/dead; do NOT read these counts as signal.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
