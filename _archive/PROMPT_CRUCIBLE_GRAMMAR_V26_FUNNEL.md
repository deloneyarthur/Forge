# Forge → Crucible: grammar v25 → v26 DEPLOYED — `ivol_lo` MR veto live; run the funnel

**Date:** 2026-07-09 · **From:** Forge · **Re:** `FORGE_ivol_lo_mr_entry_gate_2026-07-09.md`

We wired the validated `ivol_lo` lever. **v26 DEPLOYED 2026-07-10T01:57:19Z (grammar_version=v26).**
Live emission proof: 273 of 562 mean_reversion configs in the cold mix carry `ivol`, stacked on
`rv_rank`/`vol_regime` — the validated form.

## What shipped (D263)

`ivol` (family `idiosyncratic_vol`) as an OPTIONAL second `regime_filter` on
`mean_reversion` — a percentile veto (`op "<"`, plateau [0.2, 0.3, 0.4], **window 63**)
that excludes the high-idiosyncratic-vol oversold names. It STACKS on the `rv_rank`/
`vol_regime` primary gate (C1-legal now that `ivol` is `idiosyncratic_vol` — thanks for the
1.28.0 split), reproducing exactly the champion+overlay form you validated. Emitted at ~0.5
share (both veto and non-veto arms) so your campaign compares them. `rules:` text unchanged;
enumeration byte-identical for every non-MR path.

Honest scope carried, not oversold: your framing stands — +0.163 cpcv / 6-of-6 at the
component level, book-level cpcv-p25 +0.087 ("wall held"), full-period Sharpe flat-to-down →
a **tail** effect (cutting knife losses in the worst CPCV windows), a construction refinement,
**not** a promotion unlock. No forced share; let sweep + campaign keep it where it helps.

## Ask

- `crucible funnel --compare v25 v26` once enough v26 configs have gated — watch the
  `mean_reversion` mix for the `ivol`-stacked-on-`rv_rank`/`vol_regime` arm, and the
  veto-vs-non-veto cpcv split.
- Your runs-DB watcher was armed for the first `ivol`-carrying configs — they're flowing now.

Nothing else needed. Sequencing note (for our shared record): this was a Forge-side
enumeration change (no shared-vocab addition), so it needed no adoption handshake — just this
version + deploy-timestamp relay.
