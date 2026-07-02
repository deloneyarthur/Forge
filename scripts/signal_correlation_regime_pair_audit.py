"""Regime-gate co-firing audit for the §5.3.6 signal_correlation filter (PRE-H3 / D227).

Re-runnable reproduction of the strategy-audit P1-2b measurement: the filter kills a
disproportionate share of multi-signal `volatility_event` configs, and the audit showed
those kills are dominated by the `regime_filter` CONTEXT GATE co-firing with the alpha
signals it gates — structural, not the content redundancy the filter exists to catch.

Answers, per family, over a deterministic enumeration against the LIVE feature cache:

  1. Of multi-signal configs, how many exceed the Jaccard threshold (would be rejected)?
  2. Of those, how many have the max-overlap pair INVOLVING a `regime_filter`-role signal
     (recoverable by `signal_correlation.exclude_regime_filter`, D227) vs a genuine
     content↔content pair (still legitimately rejected)?
  3. Which regime indicators drive the co-firing, and how extreme are the Jaccards?

Baseline (N=1500, seed 0, 2026-07-02): volatility_event 65/320 rejected (20%), 61 (94%)
regime-pairs, median Jaccard 0.949, top gates days_to_nfp/cpi/fomc/opex; content-pair
redundancy rare (9) + marginal (median 0.869). Requires the live Crucible writer socket
(activation dates aren't in forge.db). Read-only; submits nothing.

    uv run python scripts/signal_correlation_regime_pair_audit.py [N]
"""

from __future__ import annotations

import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from forge.cli.main import _build_feature_cache
from forge.enumeration import enumerate_candidates
from forge.grammar import load_grammar
from forge.persistence.registry_loader import load_registry
from forge.prefilters import load_calibration
from forge.prefilters._similarity import jaccard

_REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    grammar = load_grammar(
        _REPO / "config" / "grammar.yaml", archive_dir=_REPO / "config" / "grammar_archive"
    )
    registry = load_registry(allow_demo_fallback=False)
    threshold = load_calibration(
        _REPO / "config" / "prefilter.yaml"
    ).signal_correlation.max_jaccard_overlap
    cache = _build_feature_cache(registry, 0, require_real=True)

    configs = list(enumerate_candidates(grammar, registry, seed=0, max_candidates=n))
    batch_prefetch = getattr(cache, "prefetch_for_batch", None)
    if callable(batch_prefetch):
        batch_prefetch(configs)

    # family -> [n_multisig, n_reject, n_reject_regime_pair, n_reject_content_pair]
    per_fam: dict[str, list[int]] = {}
    regime_inds: Counter[str] = Counter()
    regime_pair_j: list[float] = []
    content_pair_j: list[float] = []
    prefetch_cfg = getattr(cache, "prefetch_for_config", None)

    for cfg in configs:
        sigs = cfg.signals
        if len(sigs) < 2:
            continue
        if callable(prefetch_cfg):
            prefetch_cfg(cfg)
        roles = {s.id: s.role for s in sigs}
        acts = {s.id: cache.activation_dates(s.id) for s in sigs}
        mx, mpair = 0.0, None
        for a, b in combinations(sigs, 2):
            j = jaccard(acts[a.id], acts[b.id])
            if j > mx:
                mx, mpair = j, (a.id, b.id)
        d = per_fam.setdefault(cfg.hypothesis, [0, 0, 0, 0])
        d[0] += 1
        if mx >= threshold and mpair is not None:
            d[1] += 1
            if any(roles.get(sid) == "regime_filter" for sid in mpair):
                d[2] += 1
                regime_pair_j.append(mx)
                for sid in mpair:
                    if roles.get(sid) == "regime_filter":
                        regime_inds[next(s.indicators[0] for s in sigs if s.id == sid)] += 1
            else:
                d[3] += 1
                content_pair_j.append(mx)

    print(f"threshold={threshold}  N={n}")
    print(
        f"{'family':20s} {'multisig':>9s} {'reject':>7s} "
        f"{'reg_pair':>9s} {'content':>8s} {'reg%kill':>9s}"
    )
    for fam, d in sorted(per_fam.items()):
        reg_pct = (100 * d[2] / d[1]) if d[1] else 0.0
        print(f"{fam:20s} {d[0]:9d} {d[1]:7d} {d[2]:9d} {d[3]:8d} {reg_pct:8.0f}%")

    def _median(xs: list[float]) -> float:
        return sorted(xs)[len(xs) // 2] if xs else 0.0

    ge95 = sum(1 for j in regime_pair_j if j >= 0.95)
    print(
        f"\nregime-pair reject Jaccards: n={len(regime_pair_j)} "
        f"median={_median(regime_pair_j):.3f} >=0.95: {ge95}"
    )
    print(
        f"content-pair reject Jaccards: n={len(content_pair_j)} "
        f"median={_median(content_pair_j):.3f}"
    )
    print("regime_filter indicators in killing pairs:", regime_inds.most_common(10))


if __name__ == "__main__":
    main()
