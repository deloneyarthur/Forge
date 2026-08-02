"""Verified-coverage alignment monitor for the tail-aware (T1) ranker model (D155).

Re-runnable reproduction of the D155 static audit, for tracking as the §8.6
streak grows. Answers two questions on each run:

  1. On the VERIFIED-coverage slice the tail model is built for, does `tail_score`
     track REALIZED `cpcv_sharpe_p25` better than the incumbent P(component)
     score? (D155 baseline: Spearman +0.350 vs +0.119.)
  2. Is the verified-coverage population — where all of the tail model's value
     sits (~24% of decided-with-cpcv at D155) — growing over time?

The live ``~/forge_data/forge.db`` holds an intermittent RW lock, so snapshot
first (``docs/tasks/investigate-live.md``) and point this at the copy:

    SNAP=$(scripts/live_db_snapshot.sh)   # real disk; /tmp is tmpfs and the DB is 6.7G
    uv run python scripts/tail_verified_alignment.py "$SNAP"

Read-only. ``verified`` mirrors ``honest_regime_coverage_row``
(``forge.feedback.rejection_weights``): the ``regime_coverage`` gate passed AND
its detail carries no ``coverage_unverified`` marker. SQL is written as literals
(no interpolation) so the only external input is the snapshot path.
"""

from __future__ import annotations

import sys

import duckdb

# --- queries (literal; the honest-coverage predicate is inlined in each) ------

_POPULATION = """
  select case when json_extract_string(v.gate_results,'$.regime_coverage.passed')='true'
                   and coalesce(json_extract_string(v.gate_results,'$.regime_coverage.detail'),'')
                       not like '%coverage_unverified%'
              then 'verified' else 'unverified' end cov,
         count(*) n
  from verdicts v
  where v.decided_at >= timestamp '2026-06-10 17:17:13'
    and try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) is not null
  group by 1 order by 1
"""

_VERIFIED_BY_DAY = """
  select date_trunc('day', v.decided_at) d, count(*) n
  from verdicts v
  where v.decided_at >= timestamp '2026-06-10 17:17:13'
    and try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) is not null
    and json_extract_string(v.gate_results,'$.regime_coverage.passed')='true'
    and coalesce(json_extract_string(v.gate_results,'$.regime_coverage.detail'),'')
        not like '%coverage_unverified%'
  group by 1 order by 1
"""

_GROUND_TRUTH = """
  select json_extract_string(s.config_json,'$.hypothesis') hyp,
         case when json_extract_string(v.gate_results,'$.regime_coverage.passed')='true'
                   and coalesce(json_extract_string(v.gate_results,'$.regime_coverage.detail'),'')
                       not like '%coverage_unverified%'
              then 'verified' else 'unverified' end cov,
         count(*) n,
         median(try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double)) med
  from verdicts v join submissions s on v.config_hash = s.config_hash
  where v.decided_at >= timestamp '2026-06-10 17:17:13'
    and try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) is not null
  group by 1, 2 having count(*) >= 5 order by cov, med desc
"""

_ALIGN_VERIFIED = """
  with j as (
    select ss.tail_score, ss.model_score,
           try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) cpcv
    from shadow_scores ss
    join submissions s on ss.forge_candidate_id = s.forge_candidate_id
    join verdicts v on s.config_hash = v.config_hash
    where ss.tail_score is not null
      and try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) is not null
      and json_extract_string(v.gate_results,'$.regime_coverage.passed')='true'
      and coalesce(json_extract_string(v.gate_results,'$.regime_coverage.detail'),'')
          not like '%coverage_unverified%'
  ),
  r as (select rank() over (order by tail_score) rt, rank() over (order by model_score) rm,
               rank() over (order by cpcv) rc from j)
  select (select count(*) from j), (select corr(rt,rc) from r), (select corr(rm,rc) from r)
"""

_ALIGN_UNVERIFIED = """
  with j as (
    select ss.tail_score, ss.model_score,
           try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) cpcv
    from shadow_scores ss
    join submissions s on ss.forge_candidate_id = s.forge_candidate_id
    join verdicts v on s.config_hash = v.config_hash
    where ss.tail_score is not null
      and try_cast(json_extract(v.gate_results,'$.cpcv_sharpe_p25.value') as double) is not null
      and not (json_extract_string(v.gate_results,'$.regime_coverage.passed')='true'
               and coalesce(json_extract_string(v.gate_results,'$.regime_coverage.detail'),'')
                   not like '%coverage_unverified%')
  ),
  r as (select rank() over (order by tail_score) rt, rank() over (order by model_score) rm,
               rank() over (order by cpcv) rc from j)
  select (select count(*) from j), (select corr(rt,rc) from r), (select corr(rm,rc) from r)
"""


def _fmt(value: float | None) -> str:
    return f"{value:+.3f}" if value is not None else "n/a"


def report_population(con: duckdb.DuckDBPyConnection) -> None:
    print("== verified vs unverified (decided, honest-era, carrying cpcv_p25) ==")
    for cov, n in con.execute(_POPULATION).fetchall():
        print(f"  {cov:<11} {n}")
    print("== verified-coverage count by day (is the value-bearing slice growing?) ==")
    for day, n in con.execute(_VERIFIED_BY_DAY).fetchall():
        print(f"  {str(day)[:10]}  {n}")


def report_ground_truth(con: duckdb.DuckDBPyConnection) -> None:
    print("== realized cpcv_p25 (median) by hypothesis, split by coverage ==")
    print(f"  {'coverage':<11}{'hypothesis':<20}{'n':>6}{'median':>9}")
    for hyp, cov, n, med in con.execute(_GROUND_TRUTH).fetchall():
        print(f"  {cov:<11}{hyp:<20}{n:>6}{med:>9.3f}")


def report_alignment(con: duckdb.DuckDBPyConnection) -> None:
    print("== Spearman to realized cpcv_p25: tail_score vs P(component) ==")
    print("   (D155 baseline: verified +0.350 vs +0.119; unverified tie ~+0.219)")
    for label, query in (("verified", _ALIGN_VERIFIED), ("unverified", _ALIGN_UNVERIFIED)):
        n, tail_corr, pcomp_corr = con.execute(query).fetchall()[0]
        print(f"  {label:<11} n={n:<6} tail={_fmt(tail_corr)}  P(component)={_fmt(pcomp_corr)}")


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    con = duckdb.connect(args[0], read_only=True)
    try:
        report_population(con)
        report_ground_truth(con)
        report_alignment(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
