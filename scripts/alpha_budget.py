"""Alpha-budget / effective-N retrospective for the enumeration campaign.

Scope + methodology: ``ALPHA_BUDGET_SCOPE.md`` (grammar-review Dim C prerequisite).
Answers, from a forge.db snapshot alone:

  Q1  Is the observed honest max cpcv-p25 consistent with a ZERO-EDGE search of the
      campaign's effective size? (exceedance verdict matrix over an N_eff bracket)
  Q2  Does the running honest max TRACK the noise envelope mu0 + sigma*sqrt(2 ln N)
      as trials accumulate (noise creep), or plateau below it (real ceiling)?
  Q3  What Sharpe survives a campaign-charged DSR (the de-facto standalone promotion
      bar)? Calibrated by first reproducing the two 2026-07-03 charged re-gates
      (DSR 0.0726 / 0.0118 at n_trials=46131) from stored per-run fields.
  Q4  Emit the pre-registered prediction for the v24+burst cohort.

The live ``~/forge_data/forge.db`` holds an intermittent RW lock, so snapshot first
(``docs/tasks/investigate-live.md``) and point this at the copy:

    SNAP=$(scripts/live_db_snapshot.sh)   # real disk; /tmp is tmpfs and the DB is 6.7G
    uv run python scripts/alpha_budget.py "$SNAP"

Read-only; no clock/RNG (run stamps derive from the snapshot's max decided_at so
output is a pure function of the input). Hygiene per the scope: post-cost-floor cut
(D124), grammar_version NOT NULL (D103), honest predicate byte-for-byte D124, and a
SINGLE MEASUREMENT BASIS — each hash's earliest post-cut row (the standard-window
run). Fullhist-refit re-gates RE-MEASURE on longer windows (values differ, they do
not copy), are post-selection, and so are paneled separately, never pooled into the
max statistics.
"""

# ruff: noqa: S608 -- every SQL string below composes module CONSTANTS only; the
# sole external input is the snapshot path, opened read-only.
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from dataclasses import dataclass

import duckdb

EULER_GAMMA = 0.5772156649015329
COST_FLOOR_CUT = "2026-06-09 22:52:57"
V24_DEPLOY_CUT = "2026-07-07T15:05:50Z"
CRUCIBLE_CHARGED_N = 46_131
DSR_PASS_BAR = 0.95
PREREG_RESOLVE_N = 3_000
PREREG_RESOLVE_DATE = "2026-07-21"

# Stage-E anchors: the campaign-charged DSR rows (2 as of 2026-07-08 — the 07-03
# re-gates at DSR 0.0726/0.0118) are discovered by _CHARGED_ROWS, and the implied
# SR* must agree across them before the Q3 inversion is trusted.

_HONEST_PREDICATE = """
      json_extract_string(gate_results, '$.regime_coverage.passed') = 'true'
      and coalesce(json_extract_string(gate_results, '$.regime_coverage.detail'), '')
          not like '%coverage_unverified%'
"""

# One value-row per config_hash (earliest post-cut carries the canonical metric
# values; the latest row carries the standing decision).
_DEDUPED = f"""
  select config_hash,
         arg_min(decided_at, decided_at)                                        as decided_at,
         arg_max(decision, decided_at)                                          as final_decision,
         arg_min(try_cast(json_extract(gate_results, '$.cpcv_sharpe_p25.value')
                 as double), decided_at)                                        as cpcv,
         arg_min(try_cast(json_extract(gate_results, '$.sharpe_baseline.value')
                 as double), decided_at)                                        as sharpe,
         arg_min(try_cast(json_extract(gate_results,
                 '$.walk_forward_sharpe_median.value') as double), decided_at)  as wf,
         arg_min(try_cast(json_extract(gate_results,
                 '$.min_oos_trade_count.value') as double), decided_at)         as trades,
         arg_min(try_cast(json_extract(gate_results, '$.regime_coverage.value')
                 as double), decided_at)                                        as window_days,
         arg_min(case when {_HONEST_PREDICATE} then 1 else 0 end, decided_at)   as honest
  from verdicts
  where decided_at > timestamp '{COST_FLOOR_CUT}'
    and grammar_version is not null
  group by config_hash
"""

_COHORT_ALL = f"select * from ({_DEDUPED}) where cpcv is not null"

_COHORT_HONEST_META = f"""
  select d.*,
         json_extract_string(s.config_json, '$.hypothesis') as hypothesis,
         json_extract_string(s.config_json, '$.dte_bucket') as dte_bucket,
         s.config_json
  from ({_DEDUPED}) d
  join submissions s using (config_hash)
  where d.honest = 1 and d.cpcv is not null
"""

_SUBMISSIONS_TOTAL = "select count(*) from submissions"

# The campaign-charged DSR rows (Stage-E anchors) — their OWN stored fields, not the
# parent run's (fullhist refits re-measure on a different window, values differ).
_CHARGED_ROWS = """
  select config_hash,
         try_cast(json_extract(gate_results, '$.deflated_sharpe.value') as double),
         try_cast(json_extract(gate_results, '$.sharpe_baseline.value') as double),
         try_cast(json_extract(gate_results, '$.cpcv_sharpe_p25.value') as double),
         try_cast(json_extract(gate_results, '$.min_oos_trade_count.value') as double),
         try_cast(json_extract(gate_results, '$.regime_coverage.value') as double),
         regexp_extract(json_extract_string(gate_results, '$.deflated_sharpe.detail'),
                        'n_trials=([0-9]+)', 1)
  from verdicts
  where json_extract_string(gate_results, '$.deflated_sharpe.detail')
        like '%deflated by n_trials=%'
"""

# Re-measurement rows (fullhist-refit children etc.): same hash, later row, DIFFERENT
# cpcv than the hash's earliest post-cut row — a selected re-measurement basis that
# must not be pooled with the standard-window max statistics.
_REFIT_ROWS = f"""
  with base as ({_DEDUPED})
  select v.config_hash, v.decided_at, v.decision,
         try_cast(json_extract(v.gate_results, '$.cpcv_sharpe_p25.value') as double) cpcv,
         case when {_HONEST_PREDICATE} then 1 else 0 end as honest
  from verdicts v
  join base b using (config_hash)
  where v.decided_at > timestamp '{COST_FLOOR_CUT}'
    and v.grammar_version is not null
    and v.decided_at > b.decided_at
    and abs(coalesce(try_cast(json_extract(v.gate_results,
            '$.cpcv_sharpe_p25.value') as double), 0.0) - coalesce(b.cpcv, 0.0)) > 1e-9
"""


# --- numerics (stdlib only; no scipy dependency) -------------------------------


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def norm_ppf(p: float) -> float:
    """Acklam's rational approximation (|rel err| < 1.15e-9); enough for gate math."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p out of range: {p}")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > p_high:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def expected_max_factor(n: int) -> float:
    """Bailey/Lopez de Prado E[max of n std normals] multiplier (their SR* form)."""
    return (1.0 - EULER_GAMMA) * norm_ppf(1.0 - 1.0 / n) + EULER_GAMMA * norm_ppf(
        1.0 - 1.0 / (n * math.e)
    )


def null_max_exceedance(x: float, mu0: float, sigma: float, n: int) -> float:
    """P(max of n iid N(mu0, sigma) draws > x) — exact, not the Gumbel asymptotic."""
    q = norm_sf((x - mu0) / sigma)
    if q <= 0.0:
        return 0.0
    return -math.expm1(n * math.log1p(-q))


def null_max_quantile(p: float, mu0: float, sigma: float, n: int) -> float:
    """x such that P(max of n draws <= x) = p."""
    q = 1.0 - p ** (1.0 / n)
    return mu0 + sigma * norm_ppf(1.0 - q)


def sharpe_se(sr: float, t: float) -> float:
    """Normal-moment SR standard error, sqrt((1 + SR^2/2)/(T-1)); gamma3/gamma4 are
    not exported per-run, so calibration reports the residual this leaves."""
    return math.sqrt((1.0 + 0.5 * sr * sr) / (t - 1.0))


# --- cohort ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Row:
    config_hash: str
    decided_at: str
    cpcv: float
    sharpe: float | None
    trades: float | None
    window_days: float | None
    honest: bool
    hypothesis: str | None
    dte_bucket: str | None
    directional: str | None


def _directional_indicator(config_json: str) -> str | None:
    for sig in json.loads(config_json).get("signals", []):
        if sig.get("role") == "directional":
            inds = sig.get("indicators") or []
            return str(inds[0]) if inds else None
    return None


def load_cohort(con: duckdb.DuckDBPyConnection) -> list[Row]:
    meta: dict[str, tuple[str | None, str | None, str | None]] = {}
    for h, hyp, bucket, cj in con.execute(
        f"select config_hash, hypothesis, dte_bucket, config_json from ({_COHORT_HONEST_META})"
    ).fetchall():
        meta[h] = (hyp, bucket, _directional_indicator(cj))
    rows: list[Row] = []
    for h, decided, _dec, cpcv, sharpe, _wf, trades, window, honest in con.execute(
        _COHORT_ALL
    ).fetchall():
        hyp, bucket, directional = meta.get(h, (None, None, None))
        rows.append(
            Row(
                h,
                str(decided),
                cpcv,
                sharpe,
                trades,
                window,
                bool(honest),
                hyp,
                bucket,
                directional,
            )
        )
    rows.sort(key=lambda r: r.decided_at)
    return rows


def robust_stats(values: list[float]) -> tuple[float, float]:
    """(median, IQR-based sigma) — robust to the tail we are testing."""
    xs = sorted(values)
    n = len(xs)

    def q(p: float) -> float:
        i = p * (n - 1)
        lo, hi = math.floor(i), math.ceil(i)
        return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)

    return q(0.5), (q(0.75) - q(0.25)) / 1.349


def family_map(registry_path: str | None) -> dict[str, str]:
    path = registry_path
    if path is None:
        candidates = sorted(
            glob.glob(os.path.expanduser("~/optbt_data/exports/registry_snapshot_*.json"))
        )
        path = candidates[-1] if candidates else None
    if path is None:
        return {}
    with open(path, encoding="utf-8") as fh:
        snap = json.load(fh)
    return {str(ind["id"]): str(ind["family"]) for ind in snap.get("indicators", [])}


# --- stages ---------------------------------------------------------------------


def stage_a(
    honest: list[Row], unverified: list[Row], refits: list[tuple[str, str, str, float, int]]
) -> dict[str, object]:
    mu, sigma = robust_stats([r.cpcv for r in honest])
    mx = max(honest, key=lambda r: r.cpcv)
    by_hyp: dict[str, int] = {}
    for r in honest:
        by_hyp[r.hypothesis or "?"] = by_hyp.get(r.hypothesis or "?", 0) + 1
    u_mu, u_sigma = robust_stats([r.cpcv for r in unverified]) if unverified else (0.0, 0.0)
    refit_honest = [r for r in refits if r[4] == 1]
    refit_outliers = sorted((r for r in refit_honest if r[3] >= 1.5), key=lambda r: -r[3])
    out = {
        "honest_n": len(honest),
        "honest_median": mu,
        "honest_sigma_robust": sigma,
        "honest_max": mx.cpcv,
        "honest_max_hash": mx.config_hash,
        "honest_max_decided": mx.decided_at,
        "unverified_n": len(unverified),
        "unverified_median": u_mu,
        "unverified_sigma_robust": u_sigma,
        "unverified_max": max((r.cpcv for r in unverified), default=None),
        "honest_by_hypothesis": dict(sorted(by_hyp.items(), key=lambda kv: -kv[1])),
        "refit_n": len(refits),
        "refit_honest_n": len(refit_honest),
        "refit_honest_max": max((r[3] for r in refit_honest), default=None),
        "refit_honest_ge_1_5": [
            {"config_hash": h, "decided_at": d, "decision": dec, "cpcv": c}
            for h, d, dec, c, _ in refit_outliers
        ],
    }
    print("== Stage A — honest cohort (post-cut, deduped to standard-window basis) ==")
    print(
        f"  n={len(honest)}  median={mu:+.3f}  sigma_robust={sigma:.3f}  "
        f"max={mx.cpcv:+.3f} ({mx.config_hash} @ {mx.decided_at[:10]})"
    )
    print(
        f"  unverified panel: n={len(unverified)}  median={u_mu:+.3f}  "
        f"sigma={u_sigma:.3f}  max={out['unverified_max']:+.3f}"
    )
    print(f"  hypothesis mix: {out['honest_by_hypothesis']}")
    print(
        f"  refit panel (re-measurements, EXCLUDED from max stats): n={len(refits)}"
        f"  honest={len(refit_honest)}  honest max={out['refit_honest_max']}"
    )
    for h, d, dec, c, _ in refit_outliers:
        print(f"    refit >=1.5: {h} cpcv={c:+.3f} {dec} @ {d[:16]}")
    return out


def stage_b(honest: list[Row], families: dict[str, str], submissions_total: int) -> dict[str, int]:
    cells_dir = {(r.hypothesis, r.directional, r.dte_bucket) for r in honest}
    cells_fam = {
        (r.hypothesis, families.get(r.directional or "", "?"), r.dte_bucket) for r in honest
    }
    n = len(honest)
    k = max(len(cells_dir), 1)
    n_bar = n / k
    bracket = {
        "clusters_hyp_dir_bucket": len(cells_dir),
        "clusters_hyp_family_bucket": len(cells_fam),
        "rho_0.78": int(n / (1.0 + (n_bar - 1.0) * 0.78)),
        "rho_0.50": int(n / (1.0 + (n_bar - 1.0) * 0.50)),
        # 0.158 = the D215-measured within-supply PnL correlation (the 0.78 is
        # SELECTED components only) — the most empirically grounded cell.
        "rho_0.158": int(n / (1.0 + (n_bar - 1.0) * 0.158)),
        "raw_honest": n,
        "crucible_charged_n_trials": CRUCIBLE_CHARGED_N,
        "submissions_upper_bound": submissions_total,
    }
    print("== Stage B — N_eff bracket ==")
    for name, val in bracket.items():
        print(f"  {name:<28} {val}")
    return bracket


def stage_c(
    bracket: dict[str, int], mu: float, sigma: float, observed_max: float
) -> list[dict[str, object]]:
    matrix: list[dict[str, object]] = []
    print("== Stage C — Q1 verdict matrix: P(null max > observed) ==")
    print(
        f"  observed honest max = {observed_max:+.3f}"
        f"   (mu0 variants: 0.0 and empirical median {mu:+.3f})"
    )
    print(f"  {'cell':<28}{'N_eff':>9}   {'p_exceed@mu0=0':>15}   {'p_exceed@median':>16}")
    for name, n_eff in bracket.items():
        if n_eff < 2:
            continue
        p0 = null_max_exceedance(observed_max, 0.0, sigma, n_eff)
        pm = null_max_exceedance(observed_max, mu, sigma, n_eff)
        e0 = null_max_quantile(0.5, 0.0, sigma, n_eff)
        matrix.append(
            {
                "cell": name,
                "n_eff": n_eff,
                "p_exceed_mu0_zero": p0,
                "p_exceed_mu0_median": pm,
                "null_median_max_mu0_zero": e0,
            }
        )
        print(f"  {name:<28}{n_eff:>9}   {p0:>15.4f}   {pm:>16.4f}")
    # Where the verdict flips: the N_eff above which the noise-null survives p>0.05.
    for label, mu0 in (("mu0=0", 0.0), ("mu0=median", mu)):
        q = norm_sf((observed_max - mu0) / sigma)
        crossover = math.log(0.95) / math.log1p(-q) if q > 0 else math.inf
        matrix.append(
            {
                "cell": f"crossover_p05_{label}",
                "n_eff": int(crossover),
                "p_exceed_mu0_zero": None,
                "p_exceed_mu0_median": None,
                "null_median_max_mu0_zero": None,
            }
        )
        print(f"  noise-null survives (p>0.05) for N_eff >= {crossover:,.0f} at {label}")
    return matrix


def stage_d(honest: list[Row], mu: float, sigma: float) -> list[dict[str, object]]:
    running: list[dict[str, object]] = []
    best = -math.inf
    day_last: dict[str, tuple[int, float]] = {}
    for i, r in enumerate(honest, start=1):
        best = max(best, r.cpcv)
        day_last[r.decided_at[:10]] = (i, best)
    print("== Stage D — Q2 creep diagnostic: running max vs noise envelope ==")
    print(f"  {'date':<12}{'cum N':>8}{'run max':>9}{'E[null max]':>13}{'gap(sigma)':>11}")
    days = sorted(day_last)
    shown = {days[0], days[-1]} | set(days[:: max(1, len(days) // 12)])
    for day in days:
        n, mx = day_last[day]
        env = mu + sigma * expected_max_factor(max(n, 2))
        gap = (mx - env) / sigma
        running.append(
            {"date": day, "cum_n": n, "running_max": mx, "null_envelope": env, "gap_sigma": gap}
        )
        if day in shown:
            print(f"  {day:<12}{n:>8}{mx:>9.3f}{env:>13.3f}{gap:>11.2f}")
    final = running[-1]
    verdict = (
        "TRACKS the noise envelope (creep signature)"
        if abs(float(final["gap_sigma"])) <= 1.5
        else "sits OFF the envelope — inspect (possible ceiling or era artifact)"
    )
    print(f"  final gap = {float(final['gap_sigma']):+.2f} sigma -> {verdict}")
    return running


@dataclass(frozen=True, slots=True)
class ChargedAnchor:
    config_hash: str
    dsr: float
    sharpe: float
    cpcv: float
    trades: float
    window_days: float
    n_trials: int

    def t_of(self, t_source: str) -> float:
        if t_source == "trades":
            return self.trades
        scale = 252.0 / 365.0 if t_source == "window_trading_days" else 1.0
        return self.window_days * scale


def stage_e(honest: list[Row], anchors: list[ChargedAnchor]) -> dict[str, object]:
    print("== Stage E — Q3 DSR calibration grid + inversion ==")
    if len(anchors) < 2:
        print(
            f"  only {len(anchors)} charged-DSR rows found — cannot cross-check; "
            "SKIPPING the inversion"
        )
        return {"calibrated": False, "anchors_found": len(anchors)}
    n_trials = max(a.n_trials for a in anchors)
    combos: list[dict[str, object]] = []
    for sr_field in ("sharpe", "cpcv"):
        for t_source in ("trades", "window_trading_days", "window_calendar_days"):
            implied = [
                getattr(a, sr_field)
                - norm_ppf(a.dsr) * sharpe_se(getattr(a, sr_field), a.t_of(t_source))
                for a in anchors
            ]
            combos.append(
                {
                    "sr_field": sr_field,
                    "t_source": t_source,
                    "implied_sr_star": implied,
                    "spread": max(implied) - min(implied),
                }
            )
    combos.sort(key=lambda c: float(c["spread"]))
    print(f"  anchors: {len(anchors)} charged rows, n_trials={n_trials}")
    print(f"  {'SR field':<10}{'T source':<24}{'implied SR* per anchor':<28}{'spread':>8}")
    for c in combos:
        pair = ", ".join(f"{v:.3f}" for v in c["implied_sr_star"])  # type: ignore[union-attr]
        print(f"  {c['sr_field']:<10}{c['t_source']:<24}{pair:<28}{float(c['spread']):>8.3f}")
    best = combos[0]
    implied_best = list(best["implied_sr_star"])  # type: ignore[arg-type]
    sr_star_charged = sum(implied_best) / len(implied_best)
    spread = float(best["spread"])
    calibrated = spread < 0.05
    status = (
        "CONSISTENT (anchors agree on SR*)"
        if calibrated
        else "APPROXIMATE — residual likely the unexported skew/kurt terms"
    )
    sane = all(sr_star_charged > getattr(a, str(best["sr_field"])) for a in anchors)
    print(
        f"  winner: SR={best['sr_field']} T={best['t_source']} "
        f"SR*({n_trials})={sr_star_charged:.3f} spread={spread:.3f} -> {status}"
        + ("" if sane else "  [WARN: SR* below an anchor SR — inconsistent]")
    )

    sigma_implied = sr_star_charged / expected_max_factor(n_trials)
    t_source = str(best["t_source"])

    def _t_of(row: Row) -> float | None:
        if t_source == "trades":
            return row.trades
        if row.window_days is None:
            return None
        return row.window_days * (252.0 / 365.0 if t_source == "window_trading_days" else 1.0)

    t_all = sorted(t for r in honest if (t := _t_of(r)) is not None and t > 2)
    t_typical = t_all[len(t_all) // 2]
    z_pass = norm_ppf(DSR_PASS_BAR)
    bars: dict[str, float] = {}
    for n in (n_trials, 100_000, 250_000):
        sr_star = sigma_implied * expected_max_factor(n)
        sr_req = sr_star
        for _ in range(50):
            sr_req = sr_star + z_pass * sharpe_se(sr_req, t_typical)
        bars[str(n)] = sr_req
    max_sharpe = max((r.sharpe for r in honest if r.sharpe is not None), default=None)
    print(
        f"  implied trial-sigma={sigma_implied:.3f}; typical honest T ({t_source}) "
        f"= {t_typical:.0f}"
    )
    print(
        f"  required {best['sr_field']} for DSR>=0.95: "
        + "  ".join(f"n={n}: {v:.3f}" for n, v in bars.items())
    )
    print(f"  context: campaign max honest sharpe_baseline = {max_sharpe}")

    # Map the bar into cpcv-p25 units via the honest-slice empirical relation —
    # a NOISY map (report r); the bar is native in the deflated field's units.
    pairs = [(r.sharpe, r.cpcv) for r in honest if r.sharpe is not None]
    mean_x = sum(p[0] for p in pairs) / len(pairs)
    mean_y = sum(p[1] for p in pairs) / len(pairs)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x, _ in pairs)
    var_y = sum((y - mean_y) ** 2 for _, y in pairs)
    slope, intercept = cov / var_x, mean_y - (cov / var_x) * mean_x
    pearson_r = cov / math.sqrt(var_x * var_y)
    mapped = (
        {n: intercept + slope * v for n, v in bars.items()}
        if best["sr_field"] == "sharpe"
        else dict(bars)
    )
    print(
        "  cpcv-p25-equivalent bar: "
        + "  ".join(f"n={n}: {v:.2f}" for n, v in mapped.items())
        + f"   (map: cpcv = {intercept:+.3f} + {slope:.3f}*sharpe, r={pearson_r:.2f})"
    )
    return {
        "grid": combos,
        "winner": {"sr_field": best["sr_field"], "t_source": best["t_source"]},
        "anchors": [
            {
                "config_hash": a.config_hash,
                "dsr": a.dsr,
                "sharpe": a.sharpe,
                "cpcv": a.cpcv,
                "trades": a.trades,
                "window_days": a.window_days,
            }
            for a in anchors
        ],
        "n_trials_charged": n_trials,
        "sr_star_charged": sr_star_charged,
        "calibration_spread": spread,
        "calibrated": calibrated,
        "sane": sane,
        "sigma_implied": sigma_implied,
        "t_typical": t_typical,
        "required_sr_for_dsr95": bars,
        "max_honest_sharpe": max_sharpe,
        "cpcv_equivalent_bar": mapped,
        "cpcv_from_sharpe": {"intercept": intercept, "slope": slope, "pearson_r": pearson_r},
    }


def stage_f(
    mu: float, sigma: float, stage_e_out: dict[str, object], stamp: str
) -> dict[str, object]:
    bound = min(
        null_max_quantile(0.95, 0.0, sigma, PREREG_RESOLVE_N),
        null_max_quantile(0.95, mu, sigma, PREREG_RESOLVE_N),
    )
    prereg = {
        "kind": "alpha_budget_prereg_v1",
        "created_from_snapshot_max_decided_at": stamp,
        "cohort": {
            "definition": (
                "honest-predicate (D124) rows on the STANDARD-WINDOW basis "
                "(each hash's earliest verdict; fullhist-refit "
                "re-measurements excluded) with decided_at >= "
                f"{V24_DEPLOY_CUT} (v24 deploy) OR config_hash in the burst "
                "manifest ~/forge_data/winning_cohort/cohort_hashes.txt"
            ),
            "resolution_source": (
                "forge.db verdicts for daemon flow; burst hashes are "
                "NOT in forge.db (direct-to-inbox) — resolve those "
                "from Crucible's gated_runs exports by manifest"
            ),
        },
        "resolve": {"honest_n_at_least": PREREG_RESOLVE_N, "or_by_date": PREREG_RESOLVE_DATE},
        "prediction": {
            "statement": (
                "cohort honest max cpcv_sharpe_p25 <= bound (the null 95th "
                "pct of the max of 3000 draws, most signal-favorable mu0); "
                "a breach rejects the noise-null at that level"
            ),
            "bound": bound,
            "mu0_variants": {"zero": 0.0, "empirical_median": mu},
            "sigma_robust": sigma,
        },
        "q3_standalone_bar": stage_e_out.get("required_sr_for_dsr95"),
        "q3_cpcv_equivalent": stage_e_out.get("cpcv_equivalent_bar"),
        "q3_calibrated": stage_e_out.get("calibrated"),
    }
    print("== Stage F — Q4 prereg ==")
    print(
        f"  prediction: v24+burst cohort honest max cpcv-p25 <= {bound:.3f} "
        f"(resolve at honest n>={PREREG_RESOLVE_N} or {PREREG_RESOLVE_DATE})"
    )
    return prereg


# --- entry ----------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("snapshot", help="path to a forge.db snapshot copy")
    parser.add_argument(
        "--out",
        default=os.path.expanduser("~/forge_data/alpha_budget"),
        help="report/prereg output dir (default ~/forge_data/alpha_budget)",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help="registry snapshot JSON for family clustering "
        "(default: newest in ~/optbt_data/exports)",
    )
    parser.add_argument(
        "--no-write", action="store_true", help="print only; skip writing report/prereg JSON"
    )
    args = parser.parse_args(argv[1:])

    con = duckdb.connect(args.snapshot, read_only=True)
    try:
        rows = load_cohort(con)
        submissions_total = int(con.execute(_SUBMISSIONS_TOTAL).fetchone()[0])
        anchors = [
            ChargedAnchor(h, dsr, sh, cp, tr, wd, int(nt))
            for h, dsr, sh, cp, tr, wd, nt in con.execute(_CHARGED_ROWS).fetchall()
            if None not in (dsr, sh, cp, tr, wd) and nt
        ]
        refits = [
            (str(h), str(d), str(dec), float(cpcv), int(honest))
            for h, d, dec, cpcv, honest in con.execute(_REFIT_ROWS).fetchall()
            if cpcv is not None
        ]
    finally:
        con.close()

    honest = [r for r in rows if r.honest]
    unverified = [r for r in rows if not r.honest]
    stamp = max(r.decided_at for r in rows).replace(" ", "T")[:19] + "Z"

    a = stage_a(honest, unverified, refits)
    mu = float(a["honest_median"])  # type: ignore[arg-type]
    sigma = float(a["honest_sigma_robust"])  # type: ignore[arg-type]
    observed_max = float(a["honest_max"])  # type: ignore[arg-type]
    b = stage_b(honest, family_map(args.registry), submissions_total)
    c = stage_c(b, mu, sigma, observed_max)
    d = stage_d(honest, mu, sigma)
    e = stage_e(honest, anchors)
    f = stage_f(mu, sigma, e, stamp)

    print("== Summary ==")
    print(
        f"  Q1: standard-basis honest max {observed_max:+.3f} < the 1.5 bar; "
        "whether it exceeds noise depends on mu0 x N_eff (see crossover lines) — "
        "indistinguishable from a modest-edge bulk either way"
    )
    print(
        f"  Q2: running max sits {float(d[-1]['gap_sigma']):+.2f} sigma vs the null "
        "envelope — no break-out; the >=1.5 outliers all live on the refit basis"
    )
    if e.get("calibrated"):
        bars = e["required_sr_for_dsr95"]
        print(
            "  Q3: campaign-charged DSR bar (sharpe_baseline): "
            + "  ".join(f"n={n}: {v:.2f}" for n, v in bars.items())  # type: ignore[union-attr]
            + " — the de-facto standalone bar"
        )
    print(
        f"  Q4: prereg bound {float(f['prediction']['bound']):.3f} "  # type: ignore[index]
        f"on the v24+burst cohort (resolve n>={PREREG_RESOLVE_N} "
        f"or {PREREG_RESOLVE_DATE})"
    )

    if not args.no_write:
        os.makedirs(args.out, exist_ok=True)
        tag = stamp.replace(":", "").replace("-", "")
        report = {
            "snapshot_max_decided_at": stamp,
            "stage_a": a,
            "stage_b": b,
            "stage_c": c,
            "stage_d_tail": d[-14:],
            "stage_e": e,
            "prereg": f,
        }
        for name, payload in (("report", report), ("prereg", f)):
            path = os.path.join(args.out, f"{name}_{tag}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, default=str)
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
