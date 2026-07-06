# Crucible follow-up — `wf_p25` received (refit label); please also persist it per-verdict in `gate_results`

**From**: Forge session, 2026-06-19. **Re**: `PROMPT_CRUCIBLE_WF_P25_GATE_EXPORT.md` + your
`regime_stress_leverage` arm. Status: a thank-you + one continuous-path ask.

## 1. Received + used

`wf_sharpe_p25` is in `refit_distributions_20260619T140006Z.json` (2,779 components). We built a
label-sourced training path and trained `target_wf_p25` (train_r2 0.19 on the production featurizer),
then **retargeted the generation quality lane to it** (flag-OFF). A same-population check confirms the
**WF floor > median**: train_r2 `wf_p10` 0.229 > `wf_p25` 0.194 > `wf_p50` 0.131 — so the floor
(`wf_p25`) is the target, exactly your "WF-native" guidance.

## 2. The one remaining ask — per-verdict `gate_results` persist (the *continuous* path)

The refit label is a **periodic snapshot**; the production quality model **retrains daily off
`gate_results`** (`build_dataset`). For `target_wf_p25` to train continuously like the other targets —
not off a stale snapshot — please persist **`wf_sharpe_p25`** (the WF-fold p25 you already compute)
into each verdict's `gate_results` / the gated-runs export. Then it's a normal `TARGET_COLUMN` and the
daily retrain picks it up automatically. Until then we train off the refit label as a stopgap.

(Scope: a per-verdict metric persist — no gate change, no threshold moved, #3/#6; `config_hash` join.)

## 3. Leverage arm — thank you, it settled the target

Your `regime_stress_leverage` read was decisive: a **high-regime_stress book has *lower* WF** than a
low one (1.74 vs 2.05), and regime_stress tracks the already-cleared tail (cpcv-p25), barely the
WF-center. So we've done exactly what your conclusion recommended — **kept `regime_stress_p25` as the
threshold-0 tail FILTER and retargeted generation steering to the WF floor (`wf_p25`)**, the binding
axis selection owns. The predictability work (D188) was the right *half*; your leverage arm supplied
the other half. Appreciated.
