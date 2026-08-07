"""Region-carriage audit over the campaign registry (D299).

The D287 failure class made standing: a confirmed region can be protected at
GENERATION (sampler pins/weights) and still be starved at SELECTION — the
learned lane's hard P-gate scores the young cell below eligibility and the
ranked lane submits none of it. It took a hand audit to catch (post-v37
ranked resid ran 14 hurst / 0 vix; p ~ 0.006% under the uniform coin, and the
lone vix arrival came via the HOLDOUT lane).

The detector uses exactly that tell, formalized: the exploration holdout
(P3.3) bypasses ranking, so a campaign's share among holdout rows is an
unbiased estimate of its share of the passed pool. Ranked share far below
holdout share == the selection layer is eating the campaign. Small-n guarded:
below ``MIN_HOLDOUT_MEMBERS`` holdout arrivals the ratio is noise and never
flags.

Read-side only — this module NEVER touches ranking. Run it against a /tmp
snapshot of the live DB (the RW-lock pitfall, docs/tasks/investigate-live.md)
via ``forge campaigns audit``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from forge.ranking.campaigns import CAMPAIGNS, Campaign, campaign_member_fn

if TYPE_CHECKING:
    import duckdb

# A campaign's holdout arrivals below this count give a ratio too noisy to
# flag on (the 5% holdout is ~10 rows/batch; 3 members implies real
# generation-side supply across the window).
MIN_HOLDOUT_MEMBERS: int = 3

# Flag when ranked share falls below this fraction of holdout share. 0.25 is
# deliberately loose — the D287 incident measured ~0.0; a healthy cell sits
# near 1.0. Strict `<`: exactly-at-threshold does not flag.
STARVATION_RATIO: float = 0.25


@dataclass(frozen=True, slots=True)
class CampaignCarriage:
    """One campaign's carriage picture over the audit window."""

    name: str
    status: str
    window_days: int
    ranked_total: int
    holdout_total: int
    ranked_members: int
    holdout_members: int
    ranked_share: float | None
    holdout_share: float | None
    carriage_ratio: float | None
    starved: bool
    decisions: Mapping[str, int]


def _watermark(now: datetime, days: int) -> datetime:
    """Naive-UTC window cut, matching the on-disk TIMESTAMP convention
    (D061: the DB session is pinned to UTC; stored values are naive UTC)."""
    return (now - timedelta(days=days)).astimezone(UTC).replace(tzinfo=None)


def _member_decisions(
    conn: duckdb.DuckDBPyConnection, member_hashes: Sequence[str]
) -> dict[str, int]:
    """Verdict-decision counts for the member hashes (any decided_at — verdict
    latency means window members decide later; the join is on identity)."""
    if not member_hashes:
        return {}
    conn.execute("CREATE OR REPLACE TEMP TABLE _campaign_audit_members(config_hash VARCHAR)")
    conn.executemany("INSERT INTO _campaign_audit_members VALUES (?)", [[h] for h in member_hashes])
    rows = conn.execute(
        """
        SELECT v.decision, COUNT(*)
        FROM verdicts v
        JOIN _campaign_audit_members m USING (config_hash)
        GROUP BY v.decision
        """
    ).fetchall()
    conn.execute("DROP TABLE _campaign_audit_members")
    return {str(decision): int(count) for decision, count in rows}


def _tally_lanes(
    rows: Sequence[tuple[str, str, str]],
    auditable: Sequence[tuple[Campaign, Callable[[Mapping[str, Any]], bool]]],
) -> tuple[int, int, dict[str, dict[str, int]], dict[str, list[str]]]:
    """One pass over window rows: lane totals + per-campaign member counts."""
    ranked_total = 0
    holdout_total = 0
    member_hashes: dict[str, list[str]] = {c.name: [] for c, _ in auditable}
    member_counts: dict[str, dict[str, int]] = {
        c.name: {"ranked": 0, "holdout": 0} for c, _ in auditable
    }
    for config_json, mode, config_hash in rows:
        lane = "holdout" if mode == "holdout" else "ranked"
        if lane == "holdout":
            holdout_total += 1
        else:
            ranked_total += 1
        config = json.loads(config_json)
        for campaign, fn in auditable:
            if fn(config):
                member_counts[campaign.name][lane] += 1
                member_hashes[campaign.name].append(str(config_hash))
    return ranked_total, holdout_total, member_counts, member_hashes


def audit_carriage(
    conn: duckdb.DuckDBPyConnection,
    *,
    now: datetime,
    days: int = 7,
    campaigns: Sequence[Campaign] | None = None,
) -> tuple[list[CampaignCarriage], list[str]]:
    """Audit every FARMING campaign's ranked-vs-holdout carriage.

    Returns ``(results, unauditable)`` — the second element names farming
    campaigns with no resolvable membership signature (listed, never
    guessed at). ``selection_mode`` NULL counts as 'ranked' (pre-P3.3 rows,
    per the schema comment). ``now`` must be tz-aware (callers pass
    ``forge.core.clock.utc_now()``); this function takes it as a parameter so
    the module itself stays clock-free (hard rule #8).
    """
    source = CAMPAIGNS if campaigns is None else campaigns
    farming = [c for c in source if c.status == "farming"]
    auditable: list[tuple[Campaign, Callable[[Mapping[str, Any]], bool]]] = []
    unauditable: list[str] = []
    for campaign in farming:
        fn = campaign_member_fn(campaign)
        if fn is None:
            unauditable.append(campaign.name)
        else:
            auditable.append((campaign, fn))
    if not auditable:
        return [], unauditable

    rows = conn.execute(
        """
        SELECT config_json, COALESCE(selection_mode, 'ranked'), config_hash
        FROM submissions
        WHERE submitted_at >= ?
        """,
        [_watermark(now, days)],
    ).fetchall()

    ranked_total, holdout_total, member_counts, member_hashes = _tally_lanes(rows, auditable)

    results: list[CampaignCarriage] = []
    for campaign, _fn in auditable:
        counts = member_counts[campaign.name]
        ranked_members = counts["ranked"]
        holdout_members = counts["holdout"]
        ranked_share = ranked_members / ranked_total if ranked_total else None
        holdout_share = holdout_members / holdout_total if holdout_total else None
        if ranked_share is not None and holdout_share:
            carriage_ratio: float | None = ranked_share / holdout_share
        else:
            carriage_ratio = None
        starved = (
            holdout_members >= MIN_HOLDOUT_MEMBERS
            and carriage_ratio is not None
            and carriage_ratio < STARVATION_RATIO
        )
        results.append(
            CampaignCarriage(
                name=campaign.name,
                status=campaign.status,
                window_days=days,
                ranked_total=ranked_total,
                holdout_total=holdout_total,
                ranked_members=ranked_members,
                holdout_members=holdout_members,
                ranked_share=ranked_share,
                holdout_share=holdout_share,
                carriage_ratio=carriage_ratio,
                starved=starved,
                decisions=_member_decisions(conn, member_hashes[campaign.name]),
            )
        )
    return results, unauditable


__all__ = [
    "MIN_HOLDOUT_MEMBERS",
    "STARVATION_RATIO",
    "CampaignCarriage",
    "audit_carriage",
]
