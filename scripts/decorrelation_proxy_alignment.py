"""Test whether cheap pure-config structural distance predicts realized PnL correlation.

WHY: Forge has no return data and can never compute PnL correlation itself, yet
decorrelation-aware generation needs a decorrelation signal. The cheapest possible source is
a structural proxy Forge already computes from the config alone (which indicators a strategy
uses, its hypothesis / regime / cohort / dte). This script measures whether that proxy predicts
the realized daily-PnL correlation Crucible measures (supplied as a one-off sample). The answer
decides whether the decorrelation axis can ship with the FREE proxy or must wait on Crucible's
per-recipe map. See PROMPT_CRUCIBLE_DECORRELATION_PROXY_SAMPLE.md.

Distance is Jaccard over signal INDICATOR-ID sets (params dropped). The finer content_key
fingerprint is intentionally NOT used: it encodes full parameterisation, so almost no two
configs share one and the distance saturates at 1.0 with no discriminating power (verified
empirically on the live stream).

Two modes:
  --sample FILE     VALIDATE (needs Crucible's sample): join (hash_a, hash_b, pnl_corr_full),
                    compute structural distance per pair, report Spearman(distance, |corr|)
                    SEGMENTED BY COHORT (pooling inverts structure here), plus the decision
                    check "are low-distance pairs reliably low-|corr|?".
  (no --sample)     PREFLIGHT (runs today): draw random config pairs from the submissions DB and
                    report the distribution/variance of each structural feature per cohort
                    stratum -- e.g. whether xsect-vs-xsect pairs vary enough for the proxy to
                    have any signal in the regime that matters.

Firing-date / activation overlap is NOT computed: activation_dates() needs the live
Crucible-backed feature cache and is unavailable offline. Pure-config features only.

Offline + read-only. Copy the live DB to /tmp first (it holds an intermittent RW lock); pass
that copy via --db. Output is plain text (house convention for analysis scripts).
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
from crucible_contracts import StrategyConfig

from forge.core.seed import SeedHierarchy

if TYPE_CHECKING:
    from collections.abc import Sequence

# --------------------------------------------------------------------------- features


@dataclass(frozen=True, slots=True)
class ConfigFeatures:
    """Pure-config structural fingerprint of one strategy (no market data)."""

    config_hash: str
    hypothesis: str
    dte_bucket: str
    cohort: str  # "xsect" | "single"
    underlying: str | None
    all_indicators: frozenset[str]
    directional_indicators: frozenset[str]
    regime_indicators: frozenset[str]


@dataclass(frozen=True, slots=True)
class PairFeatures:
    """Symmetric structural distance between two configs (1 = fully disjoint indicators)."""

    cohort_pair: str  # e.g. "single-vs-xsect", "xsect-vs-xsect"
    same_hypothesis: bool
    same_dte: bool
    all_indicator_distance: float  # headline: 1 - Jaccard(all indicator ids)
    directional_distance: float
    regime_distance: float


def _label(value: object) -> str:
    """Render an enum-or-str grammar field as its plain string label."""
    return str(getattr(value, "value", value))


def _indicator_ids(config: StrategyConfig, role: str | None = None) -> frozenset[str]:
    """Collect indicator ids across a config's signals, optionally filtered to one role."""
    ids: set[str] = set()
    for s in config.signals:
        if role is not None and _label(s.role) != role:
            continue
        ids.update(s.indicators)
    return frozenset(ids)


def extract_features(config: StrategyConfig) -> ConfigFeatures:
    """Build the pure-config fingerprint from indicator-id sets (params dropped)."""
    cohort = "xsect" if _label(config.combiner.type) == "cross_sectional_rank" else "single"
    return ConfigFeatures(
        config_hash=config.config_hash,
        hypothesis=_label(config.hypothesis),
        dte_bucket=_label(config.dte_bucket),
        cohort=cohort,
        underlying=config.underlying,
        all_indicators=_indicator_ids(config),
        directional_indicators=_indicator_ids(config, "directional"),
        regime_indicators=_indicator_ids(config, "regime_filter"),
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity of two key sets; two empty sets count as identical (1.0)."""
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def cohort_pair_label(a: str, b: str) -> str:
    """Order-independent label for a pair of cohorts, so x-vs-y == y-vs-x."""
    lo, hi = sorted((a, b))
    return f"{lo}-vs-{hi}"


def pair_features(a: ConfigFeatures, b: ConfigFeatures) -> PairFeatures:
    """Compute the symmetric structural distances between two configs."""
    return PairFeatures(
        cohort_pair=cohort_pair_label(a.cohort, b.cohort),
        same_hypothesis=a.hypothesis == b.hypothesis,
        same_dte=a.dte_bucket == b.dte_bucket,
        all_indicator_distance=1.0 - jaccard(a.all_indicators, b.all_indicators),
        directional_distance=1.0 - jaccard(a.directional_indicators, b.directional_indicators),
        regime_distance=1.0 - jaccard(a.regime_indicators, b.regime_indicators),
    )


# --------------------------------------------------------------------------- statistics


def _rankdata(values: Sequence[float]) -> list[float]:
    """Average-tie ranks (1-based), matching scipy.stats.rankdata semantics."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation; None if either series is constant."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0.0 or vy == 0.0:
        return None
    return cov / ((vx**0.5) * (vy**0.5))


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank correlation; None if < 3 points or a series is constant."""
    if len(xs) < 3:
        return None
    return _pearson(_rankdata(xs), _rankdata(ys))


def _quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile of an unsorted sequence."""
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


# --------------------------------------------------------------------------- DB access


def load_configs(
    db_path: str, hashes: set[str] | None = None, limit: int | None = None
) -> tuple[dict[str, StrategyConfig], int]:
    """Read configs from a (snapshot) Forge DB read-only. Returns (by-hash, n_unparseable)."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        if hashes is not None:
            placeholders = ",".join("?" * len(hashes))
            rows = con.execute(
                f"SELECT config_hash, config_json FROM submissions "  # noqa: S608 -- placeholders only
                f"WHERE config_hash IN ({placeholders})",
                list(hashes),
            ).fetchall()
        else:
            query = "SELECT config_hash, config_json FROM submissions ORDER BY submitted_at DESC"
            if limit is not None:
                query += f" LIMIT {int(limit)}"
            rows = con.execute(query).fetchall()
    finally:
        con.close()

    out: dict[str, StrategyConfig] = {}
    skipped = 0
    for config_hash, config_json in rows:
        try:
            out[config_hash] = StrategyConfig.model_validate_json(config_json)
        except Exception:  # legacy / cross-version rows are skipped and counted
            skipped += 1
    return out, skipped


# --------------------------------------------------------------------------- sample I/O


def load_sample(path: str) -> list[dict[str, object]]:
    """Load Crucible's pairwise-correlation sample.

    Accepts a .csv, a .json list-of-records, or a .json object that wraps the records under a
    key (e.g. {"meta": {...}, "pairs": [...]}) -- the first list-valued entry is taken.
    """
    p = Path(path)
    if p.suffix == ".json":
        data = json.loads(p.read_text())
        records = (
            next((v for v in data.values() if isinstance(v, list)), [])
            if isinstance(data, dict)
            else data
        )
        return [dict(r) for r in records]
    with p.open(newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- reporting


def _summary(name: str, values: list[float]) -> str:
    if not values:
        return f"    {name:<20} (none)"
    return (
        f"    {name:<20} n={len(values):<5} "
        f"mean={sum(values) / len(values):.3f}  "
        f"p10={_quantile(values, 0.10):.3f}  "
        f"med={_quantile(values, 0.50):.3f}  "
        f"p90={_quantile(values, 0.90):.3f}"
    )


def run_preflight(db_path: str, n_pairs: int, limit: int, seed: int) -> int:
    """Report structural-feature distributions over random config pairs (no Crucible data)."""
    configs, skipped = load_configs(db_path, limit=limit)
    feats = [extract_features(c) for c in configs.values()]
    print("=" * 78)
    print("PREFLIGHT  (structural features only -- no PnL correlation yet)")
    print("=" * 78)
    print(f"configs loaded: {len(feats)}   unparseable rows skipped: {skipped}")
    if len(feats) < 2:
        print("not enough configs to form pairs.")
        return 1

    by_cohort: dict[str, int] = {}
    by_hyp: dict[str, int] = {}
    for f in feats:
        by_cohort[f.cohort] = by_cohort.get(f.cohort, 0) + 1
        by_hyp[f.hypothesis] = by_hyp.get(f.hypothesis, 0) + 1
    print(f"\ncohort mix:    {dict(sorted(by_cohort.items()))}")
    print(f"hypothesis mix:{dict(sorted(by_hyp.items()))}")

    rng = SeedHierarchy(seed).rng("decorr_proxy_preflight")
    groups: dict[str, list[PairFeatures]] = {}
    for _ in range(n_pairs):
        a, b = rng.sample(feats, 2)
        pf = pair_features(a, b)
        groups.setdefault(pf.cohort_pair, []).append(pf)

    print(f"\nsampled {n_pairs} pairs. Per-cohort structural distance (1 = disjoint indicators):")
    print("  KEY QUESTION: does distance VARY within xsect-vs-xsect? flat -> proxy blind there.\n")
    for cohort_pair in sorted(groups):
        pfs = groups[cohort_pair]
        share_same_hyp = sum(p.same_hypothesis for p in pfs) / len(pfs)
        share_same_dte = sum(p.same_dte for p in pfs) / len(pfs)
        print(
            f"  [{cohort_pair}]  pairs={len(pfs)}  "
            f"same_hypothesis={share_same_hyp:.0%}  same_dte={share_same_dte:.0%}"
        )
        print(_summary("all_indicator_dist", [p.all_indicator_distance for p in pfs]))
        print(_summary("directional_dist", [p.directional_distance for p in pfs]))
        print(_summary("regime_dist", [p.regime_distance for p in pfs]))
        print()
    return 0


def _report_segment(cohort_pair: str, items: list[tuple[PairFeatures, float]]) -> None:
    """Print proxy alignment for one cohort segment: Spearman per distance + decision check."""
    n = len(items)
    print(f"\n  [{cohort_pair}]  pairs={n}   (Spearman neg => structure predicts decorrelation)")
    abs_corrs = [abs(c) for _, c in items]
    all_d = [p.all_indicator_distance for p, _ in items]
    dir_d = [p.directional_distance for p, _ in items]
    reg_d = [p.regime_distance for p, _ in items]
    for label, dists in (("all-indicator", all_d), ("directional", dir_d), ("regime", reg_d)):
        rho = spearman(dists, abs_corrs)
        rho_txt = "n/a" if rho is None else f"{rho:+.3f}"
        print(f"    Spearman({label:<13} dist, |corr|) = {rho_txt}")

    if n >= 10:
        med = _quantile(all_d, 0.50)
        low = [abs(c) for p, c in items if p.all_indicator_distance <= med]
        high = [abs(c) for p, c in items if p.all_indicator_distance > med]
        if low and high:
            lo_m, hi_m = sum(low) / len(low), sum(high) / len(high)
            print(f"    |corr| low-dist  mean={lo_m:.3f} p90={_quantile(low, 0.90):.3f}")
            print(f"    |corr| high-dist mean={hi_m:.3f} p90={_quantile(high, 0.90):.3f}")


def run_validate(db_path: str, sample_path: str, min_days: int) -> int:
    """Join Crucible's correlation sample and report proxy alignment, segmented by cohort."""
    rows = load_sample(sample_path)
    wanted: set[str] = set()
    for r in rows:
        wanted.add(r["config_hash_a"])
        wanted.add(r["config_hash_b"])
    configs, skipped = load_configs(db_path, hashes=wanted)
    feats = {h: extract_features(c) for h, c in configs.items()}

    print("=" * 78)
    print("VALIDATE  (proxy vs Crucible's realized PnL correlation)")
    print("=" * 78)
    print(f"sample rows: {len(rows)}   configs resolved: {len(feats)}   unparseable: {skipped}")

    segments: dict[str, list[tuple[PairFeatures, float]]] = {}
    dropped_missing = 0
    dropped_thin = 0
    dropped_bad = 0
    for r in rows:
        a = feats.get(r["config_hash_a"])
        b = feats.get(r["config_hash_b"])
        if a is None or b is None:
            dropped_missing += 1
            continue
        corr = _to_float(r.get("pnl_corr_full"))
        if corr is None:
            dropped_bad += 1
            continue
        n_days = _to_float(r.get("n_days_union", "0")) or 0.0
        if n_days < min_days:
            dropped_thin += 1
            continue
        pf = pair_features(a, b)
        # Prefer the sample's authoritative cohort tags (Crucible defines cohort by execution
        # breadth, which diverges from Forge's combiner.type for confluence-on-universe configs).
        ca, cb = r.get("cohort_a"), r.get("cohort_b")
        cohort_key = (
            cohort_pair_label(ca, cb)
            if isinstance(ca, str) and isinstance(cb, str)
            else pf.cohort_pair
        )
        segments.setdefault(cohort_key, []).append((pf, corr))

    print(
        f"usable pairs: {sum(len(v) for v in segments.values())}   "
        f"dropped: no-config={dropped_missing} thin={dropped_thin} bad-corr={dropped_bad}"
    )
    if not segments:
        print("no usable pairs after joins/filters -- check hashes line up and the sample format.")
        return 1
    for cohort_pair in sorted(segments):
        _report_segment(cohort_pair, segments[cohort_pair])
    print("\nRead: a strongly NEGATIVE Spearman in xsect-vs-xsect = the free proxy works.")
    print("Near-zero there -> structure can't see broad decorrelation; need Crucible's map.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="(snapshot) Forge DB path; copy live to /tmp")
    parser.add_argument("--sample", help="Crucible corr sample (.json/.csv); enables VALIDATE")
    parser.add_argument("--self-sample", type=int, default=800, help="PREFLIGHT pair count")
    parser.add_argument("--limit", type=int, default=3000, help="max configs to load in PREFLIGHT")
    parser.add_argument("--min-days", type=int, default=60, help="drop pairs below N union days")
    parser.add_argument("--seed", type=int, default=0, help="seed for PREFLIGHT pair sampling")
    args = parser.parse_args(argv)

    if args.sample:
        return run_validate(args.db, args.sample, args.min_days)
    return run_preflight(args.db, args.self_sample, args.limit, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
