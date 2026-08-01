"""Chain-inception floors — don't emit windows a name's option chain cannot cover.

Crucible's continuity guard refuses any config whose backtest window starts before the name's
first chain snapshot, and those refusals are **permanent for the window**: pre-IPO chains
cannot be backfilled, so the config consumes a submission slot and a runner cycle for a
verdict that can only ever be a refusal. Measured ~22 configs/day.

THE EXPORT IS THE AUTHORITY, NOT A PROXY WE COULD COMPUTE. Our own prefetch log carries a
per-name coverage shortfall (`below_full`), and flooring on it was the obvious shortcut. It is
wrong: bar count conflates a late LISTING with an INGEST-START floor on an old name, and those
want opposite handling — the first is permanent, the second is backfillable and its floor will
move earlier. Crucible's export distinguishes them (`floors` vs `context.first_underlying_bar`)
and we read theirs rather than infer ours. That distinction is exactly what a bar-count proxy
would have silently encoded wrong.

REFRESH, NEVER PIN. Floors move EARLIER when history is backfilled (never later), and the
sliding window un-hits names as it advances — Crucible's example: PLTR stopped mattering in
2025, ARM stops in 2028. So the exclusion set is recomputed from the newest export on every
read, not frozen into a constant like the D278/D286 untradeable list. A pinned list would
starve names that became legal again and miss names that just became illegal.

Fail-open: no export, unreadable, or malformed -> empty set -> emission is byte-identical
(hard rule #6). A missing floors file must never block generation.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

# The backtest history Crucible's window implies, INFERRED from their refusals and verified
# against the boundary, not documented by them:
#
#   today - 5y = 2021-08-01
#   LCID floor 2021-07-26  -> 6 days INSIDE  -> has never failed
#   RIVN floor 2021-11-16  -> outside        -> 6 pre_inception failures
#   CEG  2022-02-09, ARM 2023-09-18 -> outside -> failing
#   COIN 2021-04-20        -> inside         -> has never failed
#
# Five of five names on the right side of that line. The margin below then makes the filter
# fail SAFE: assuming a LONGER history excludes a superset, so a name is dropped shortly
# before it would start failing rather than shortly after. LCID is the live case — it sits 6
# days inside the true boundary and would begin failing within a week without the margin.
#
# This is an inference about someone else's semantics, which is the class of mistake that cost
# ~6h in D342. It is therefore (a) fail-safe by construction, (b) relayed to Crucible for
# confirmation, and (c) a single named constant rather than a number buried in a predicate.
_IMPLIED_HISTORY = timedelta(days=365 * 5)
_SAFETY_MARGIN = timedelta(days=183)

_EXPORT_GLOB = "chain_inception_floors_*.json"


def _newest_export(exports_dir: Path) -> Path | None:
    try:
        files = sorted(exports_dir.glob(_EXPORT_GLOB), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    return files[-1] if files else None


def load_chain_inception_floors(exports_dir: Path | None = None) -> dict[str, date]:
    """`{symbol: first-chain-snapshot date}` from Crucible's newest export, or {}."""
    root = exports_dir or (Path.home() / "optbt_data" / "exports")
    path = _newest_export(root)
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    floors = payload.get("floors")
    if not isinstance(floors, dict):
        return {}
    out: dict[str, date] = {}
    for symbol, raw in floors.items():
        try:
            out[str(symbol)] = date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            continue  # one bad row must not void the whole map
    return out


def underlyings_below_inception(
    today: date,
    *,
    exports_dir: Path | None = None,
    floors: dict[str, date] | None = None,
) -> frozenset[str]:
    """Names whose chain history is too short for the implied window — exclude from emission.

    `today` is a parameter rather than a clock read so this module stays clock-free (hard
    rule #8); callers pass `forge.core.clock.utc_now().date()`.
    """
    resolved = floors if floors is not None else load_chain_inception_floors(exports_dir)
    if not resolved:
        return frozenset()
    cutoff = today - _IMPLIED_HISTORY - _SAFETY_MARGIN
    return frozenset(symbol for symbol, floor in resolved.items() if floor > cutoff)


__all__ = ["load_chain_inception_floors", "underlyings_below_inception"]
