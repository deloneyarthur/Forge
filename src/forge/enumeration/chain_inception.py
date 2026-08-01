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

THE WINDOW IS PER-BUCKET, AND WE GOT THIS WRONG BY INFERENCE FIRST. Crucible queues each
`dte_bucket` at the history its §8.7 `min_oos_trade_count` floor needs at that bucket's trade
cadence, so swing_long runs **seven** years where swing_short/swing_mid run five. We had
inferred a flat 5 years and verified it 5-of-5 on the boundary names — a check that could
never have failed, because all 49 recorded pre-inception failures are 5y-lane runs and the 7y
trap has simply never fired. Under it, COIN and LCID plus six names we had filed as dormant
(UVXY/RTX/SQQQ/PLTR/DASH/ABNB) are pre-inception for swing_long today. Refusing to ship on the
inference was what bought the correction; the lesson is the D342 one again, and it holds.

Fail-open: no export, unreadable, or malformed -> empty set -> emission is byte-identical
(hard rule #6). A missing floors file must never block generation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# Crucible's `runs_repository.py` queue-time table, declared in their 2026-08-01 relay. Each
# length is the history that bucket needs to reach its §8.7 min-trade floor at its natural
# cadence (~25/yr short, ~12/yr mid, ~5/yr long), NOT a per-hypothesis or operator-set choice.
_WINDOW_DAYS_BY_BUCKET = {
    "swing_short": 365 * 5,
    "swing_mid": 365 * 5,
    "swing_long": 365 * 7,
}
# Their queue's own fallback for a bucket it has no entry for. Mirrored deliberately: guessing
# the LONGER window on an unknown bucket would over-exclude against a rule we do not know.
_DEFAULT_WINDOW_DAYS = 365 * 5

# The anchor is Crucible's `polygon_data_asof` (the data-snapshot date at queue time), not the
# calendar day. It trails today by 0-2 sessions, which this margin absorbs many times over.
#
# The margin makes the filter fail SAFE: assuming a LONGER history excludes a superset, so a
# name is dropped shortly before it would start failing rather than shortly after. LCID is the
# live case in the 5y lane — six days inside the true boundary, and it would begin failing
# within a week without this. The cost is real and bounded: names whose floor lands inside the
# margin band are excluded ~6 months early (LYFT and UBER are today's swing_long instances).
#
# What the margin CANNOT absorb is a wrong window LENGTH — 183 days does not cover a two-year
# bucket error, which is why the bucket has to be carried by the rule rather than papered over.
_SAFETY_MARGIN = timedelta(days=183)

_EXPORT_GLOB = "chain_inception_floors_*.json"


@dataclass(frozen=True, slots=True)
class ChainInceptionExclusions:
    """Per-bucket excluded underlyings, carrying its own bucket-resolution rule.

    A bare mapping would let a call site index it with a bucket key that isn't there and get
    an empty set — silently re-introducing the flat-window bug this type exists to end. The
    only way to read it is `for_bucket`, which falls back the way Crucible's queue does.
    """

    by_bucket: Mapping[str, frozenset[str]]
    default: frozenset[str]

    @classmethod
    def none(cls) -> ChainInceptionExclusions:
        """The fail-open value: nothing excluded in any bucket."""
        return cls(by_bucket={}, default=frozenset())

    def for_bucket(self, bucket: str) -> frozenset[str]:
        return self.by_bucket.get(bucket, self.default)

    def all_names(self) -> frozenset[str]:
        """Union across buckets — for the operator-facing batch line, never for filtering."""
        return frozenset(self.default).union(*self.by_bucket.values())

    def __bool__(self) -> bool:
        return bool(self.all_names())


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


def _below(floors: Mapping[str, date], asof: date, window_days: int) -> frozenset[str]:
    cutoff = asof - timedelta(days=window_days) - _SAFETY_MARGIN
    return frozenset(symbol for symbol, floor in floors.items() if floor > cutoff)


def underlyings_below_inception(
    asof: date,
    *,
    exports_dir: Path | None = None,
    floors: Mapping[str, date] | None = None,
) -> ChainInceptionExclusions:
    """Names whose chain history is too short for each bucket's window — drop from emission.

    `asof` is a parameter rather than a clock read so this module stays clock-free (hard
    rule #8); callers pass `forge.core.clock.utc_now().date()`.
    """
    resolved = floors if floors is not None else load_chain_inception_floors(exports_dir)
    if not resolved:
        return ChainInceptionExclusions.none()
    return ChainInceptionExclusions(
        by_bucket={
            bucket: _below(resolved, asof, days) for bucket, days in _WINDOW_DAYS_BY_BUCKET.items()
        },
        default=_below(resolved, asof, _DEFAULT_WINDOW_DAYS),
    )


__all__ = [
    "ChainInceptionExclusions",
    "load_chain_inception_floors",
    "underlyings_below_inception",
]
