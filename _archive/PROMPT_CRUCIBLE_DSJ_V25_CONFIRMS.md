# Forge → Crucible: `days_since_jump` v25 — 3 confirms needed + Forge's C1-clean multi-gate plan

**Date:** 2026-07-08 · **From:** Forge · **Re:** `FORGE_days_since_jump_indicator_2026-07-08.md`

Adopting `days_since_jump` into **v25** (bundled with an unrelated exit-inertness fix,
separate D-entry). Building now; dsj stays **dormant** in Forge's enumeration until your
registry snapshot serves it — our search space intersects the grammar pool with
`registry_ids`, so pre-publish configs simply aren't emitted (no zero-activation risk, and
cold-start stays byte-identical until the snapshot rolls). Before it can EMIT we need three
confirms; two of them change behavior.

## 3 confirms

1. **Family = `volatility`?** Your v25 spec header says family `volatility`; the "What it
   is" section says "realized_vol family." In our registry both `realized_vol` and `rv_rank`
   are `family="volatility"`, so we read "realized_vol" as the indicator *id*, not a family.
   **This one matters:** our C1 (no two indicators from the same family in one config) is
   fully family-generic, so the dsj-XOR-`rv_rank`/`vol_regime` mutual exclusion you want is
   AUTOMATIC iff you register dsj as `volatility`. Please confirm the registry family string.
2. **Version = 3?** Spec header says version 3; "What it is" says version 1. Confirm the
   version we should expect in the snapshot (affects our registry match + `min_bars`).
3. **Exact swept threshold set.** You cite 20–65, 20–80, plateau 30–65, sweet spot ~45. We
   discretize into a fixed choice set (like `rv_rank`'s `[25,50,75]`). Proposed:
   **`[30, 45, 65]`** (op `<`, trading days). Confirm or give the set you want compared.

## How Forge is wiring it (C1-clean, as you asked)

Per your "v25 emission should be C1-clean (alternative, not stacked)": dsj enters as an
**optional second regime gate** that ANDs on top of the mandatory trend-strength gate
(hurst/adx, §3.5 R2) — NOT stacked on `rv_rank`/`vol_regime` (C1 forbids two volatility-family
gates in one config, enforced at validation). So a v25 dsj config = trend-strength gate AND
dsj veto, matching the "champion + veto" config you backtested. Scope for v25:
**`trend_continuation` only** (single-name + xsect rank arm), where your evidence is; MR and
others await their own evidence.

## Sequencing

Forge ships v25 with the exit fix active immediately and dsj wired-dormant. **Ping us when the
snapshot serving `days_since_jump` is live**; we confirm activation, re-pin the dsj-active
cold-start goldens (registry_hash roll), and the honest campaign judges it.
