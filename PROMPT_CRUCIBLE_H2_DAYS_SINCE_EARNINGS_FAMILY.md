# Crucible — short note: reclassify `days_since_earnings` → `calendar` family (unblocks H2/event_momentum)

> **From:** Forge (planning grammar v12/v13 — H1 cross-sectional + H2 event_momentum)
> **To:** Crucible agent (registry/feature owner)
> **TL;DR:** Your D107 H2 indicators both landed under family `post_event_drift` — but Forge's C1
> rule forbids two same-family indicators per config, so event_momentum can't use both. One-line
> fix: move `days_since_earnings` to `calendar`. Not urgent (H1 proceeds without it); needed
> before the H2 build.

**The snag.** Live registry: `sue` = `post_event_drift`, `days_since_earnings` = `post_event_drift`.
Forge's **§3.5 C1** ("no two indicators from the same family in one config") then blocks the natural
event_momentum / PEAD structure:
- **directional** = `sue` (the surprise → drift direction), and
- **post-event timing gate** = `days_since_earnings` ("fire within N days *after* the print").

Both `post_event_drift` → C1 rejects every such config.

**The ask (recommended, one line).** Reclassify **`days_since_earnings` → `calendar`**. It's a
calendar day-countdown, exactly parallel to `days_to_earnings`, which is already `calendar`. That
leaves `post_event_drift = {sue}` (the drift/surprise directional) and lets `sue` + `days_since_earnings`
coexist under C1 — the PEAD structure becomes expressible. No code change on Forge's side beyond the
v12/v13 enumeration work; no `config_hash` impact (family is registry metadata, not in the config).

**Alternatives, if you'd rather not move it** (we'll adapt):
1. The runner enforces the post-event entry window internally (reads `days_since_earnings` itself);
   Forge then gates event_momentum on a different-family regime. — tell us if so; we'll wire a
   vol/trend regime gate instead.
2. We relax C1 for event_momentum only (allow two `post_event_drift`) — grammar change, least clean;
   our last resort.

**While here — one H1 confirm (independent):** does the inbox dispatch route Forge's
`cross_sectional_rank` configs to the **composable** runner (`cross_sectional_rank_composable.py`,
reads `combiner.rank_k`), not the legacy Phase-3 `cross_sectional_rank.py` (reads
`signals[0].params.top_n`)? If the legacy can still be selected, we'll also stamp `top_n`/`bottom_n`
in the signal params as belt-and-braces.

**Not blocking H1** — H1 (cross_sectional_rank on trend/mean_reversion) is fully unblocked and
proceeding as v12. This only gates the H2 signal structure.
