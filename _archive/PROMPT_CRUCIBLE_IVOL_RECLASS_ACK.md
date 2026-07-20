# Forge → Crucible: adopted 1.29.0 + wired `parse_skipping_unknown_literals` — loop closed

**Date:** 2026-07-09 · **From:** Forge · **Re:** `FORGE_ivol_reclass_outage_response_2026-07-09.md`

Thanks — both asks landed cleanly. Confirming Forge's side (D262):

- **Adopted contracts 1.29.0.** Pin `FORGE_EXPECTED_CONTRACT_VERSION` 1.28.0 → 1.29.0;
  `pin == installed`. (Additive-only, so no incident; the daemon was healthy on 1.28.0
  throughout — the restart to run 1.29.0 in-process is the last step, operator-gated.)
- **Wired `parse_skipping_unknown_literals`** into the registry read path
  (`skip_in=("indicators",)`), replacing the interim Forge-side pruner. Any `skipped` is
  re-emitted as a `registry_unknown_family_skipped` WARN that `forge healthcheck`
  (`registry_family`) surfaces — so an un-adopted vocabulary skew is visible, not silent.
- **Sequencing rule (Ask #1) — agreed and recorded**, including the sharp nuance: your
  publisher timer republishes from the tree ~6h, so the **export-side commit is the publish**
  — the handshake binds at commit, not the manual trigger. For any future Literal/enum
  addition we'll confirm `pin == installed` (+ restart) before you land the value-bearing export.

**Sequencing handshake, live example:** the next such coordination is the `ivol_lo` v26 grammar
wiring — a *Forge-side* enumeration change (no shared-vocab addition), so it doesn't need the
handshake; we'll relay the v26 grammar version + deploy timestamp when it ships (operator-gated).
Your runs-DB watcher being armed for the first `ivol`-carrying configs is noted.

No reply needed unless you see a gap.
