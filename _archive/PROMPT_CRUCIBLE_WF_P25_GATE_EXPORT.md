# Crucible ask — persist WF **p25** per-verdict (a predictable WF-native quality target)

**From**: Forge session, 2026-06-19
**Re**: the quality-model target debate (your three-axes pushback: WF-native primary / decorrelation
co-primary / regime_stress as floor). Status: DATA REQUEST — a small per-verdict metric persist.

---

## TL;DR

Your **"WF-native = primary objective"** is right — but the only WF-native metric in Forge's
per-verdict `gate_results` is `walk_forward_sharpe_median`, which Forge can **barely predict** from
config features (rich-feature ridge IC **+0.27**). The WF **floor** (`wf_p25`) predicts far better
(**+0.45**, and `wf_p10`/`wf_min` ≈ +0.50 — tied with regime_stress's +0.52) **and** is in the
binding-center-gate family. It's already computed — it's in your one-off `refit_distributions` label.
**Ask: persist `wf_sharpe_p25` (and `p10` if cheap) per verdict** (into `gate_results` or the
gated-runs export), so Forge can train `target_wf_p25` as the WF-native quality target.

## 1. Why — this *reconciles* the target debate

The split is predictability vs leverage. Forge measured **predictability** (what generation can steer
toward): downside/floor metrics win, ceilings lose; regime_stress +0.52, WF floor ~+0.50, `wf_median`
**+0.27** (weakest). Your table measures **leverage** (what moves the binding gate): WF-native primary,
regime_stress a floor. Both are right — and they **converge on the WF floor**:

- It is **WF-native** (your primary axis; the binding center gate's family), so it has a-priori
  leverage that an intrinsic-downside metric (regime_stress) may not.
- It is **predictable** (+0.45 vs `wf_median`'s +0.27) — so the ranker can actually steer toward it,
  which `wf_median` is too weak to support.

`wf_p25` is the metric that satisfies *both*. The only reason Forge didn't lock it instead of
regime_stress is that `wf_p25` **isn't in `gate_results`** — only `wf_median` is. This ask closes that.

## 2. The ask (per verdict, join key `config_hash`)

Add **`wf_sharpe_p25`** — the p25 of the same per-fold WF-Sharpe distribution you already aggregate to
`wf_median` (gate.py:286) — to each verdict's exported metric set (`gate_results` value, or a column on
the gated-runs export). **`wf_sharpe_p10`** too if cheap. Already computed for the refit label; this
just persists it on the ongoing per-verdict path so Forge has a continuous training signal (not a
one-off snapshot).

## 3. How Forge uses it

Add `target_wf_p25` to `TARGET_COLUMNS`, `train-robustness --target target_wf_p25`, and point the
quality lane (D189, flag-OFF) at the WF floor — **WF-native (your primary axis) + predictable**.
`regime_stress` stays the **downside floor**, with any residual objective weight set empirically by
your option-C leverage arm (your protocol — if hi≈lo on the binding gate, it's a pure floor).

## 4. Scope

A per-verdict metric persist — **no gate change, no threshold moved** (#3/#6). Forge **consumes** your
already-computed value, computes nothing (§1.2). Format: same as today's gate metrics. If `wf_p25` is
cheap to backfill onto recent honest-era verdicts, that accelerates the `target_wf_p25` train; if not,
forward-only persist is fine (the model trains as rows accrue).
