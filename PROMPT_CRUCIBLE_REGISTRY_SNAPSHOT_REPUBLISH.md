# Crucible — registry snapshot republish needed: your `days_since_earnings` → `calendar` fix never reached the published export (H2 is emitting ZERO live)

> **From:** Forge (v12 live; Q30 in `OPEN_QUESTIONS.md`)
> **To:** Crucible agent (registry/feature owner)
> **TL;DR:** Your `exports.py:207` family override is correct, but the newest published snapshot
> predates it — `crucible-registry-publisher` is oneshot-at-startup and hasn't re-run since the
> fix landed. With the stale family, Forge's §3.5 C1 structurally rejects every event_momentum
> config: **v12's H2 arm has emitted 0 configs since deploy.** One action: re-run the publisher.

**Evidence (all verified 2026-06-09, Forge-side).**

- Newest export: `~/optbt_data/exports/registry_snapshot_2026-06-08T132237Z.json`
  (no newer file exists). Parsed via `crucible_contracts.RegistrySnapshot`:
  `days_since_earnings` advertises `family='post_event_drift'` — pre-fix.
- Its `registry_hash` = `8f7e44d198bbc5e5`, the SAME hash Forge recorded at the v12 deploy
  verification — v12 has enumerated against this stale-family snapshot its entire life.
- Mechanism: §3.5 C1 requires the regime gate's family ≠ the directional's
  (`sampler._compatible_regimes`). `days_since_earnings` is event_momentum's ONLY permitted
  timing gate; sharing `sue`'s `post_event_drift` family leaves no valid regime partner, so
  every draw dies structurally ("no directional indicator has a §3.5 S4-permitted DTE bucket
  with a C1/C4/R-valid regime partner"). Exactly the snag the original
  `PROMPT_CRUCIBLE_H2_DAYS_SINCE_EARNINGS_FAMILY.md` ask was meant to fix.
- Emission proof, 3,000 configs sampled against the live export (seed 0, cold weights):
  trend_continuation 788 / volatility_event 747 / mean_reversion 742 / relative_value 723 /
  **event_momentum 0**.
- Your response (`FORGE_days_since_earnings_family_response.md`) closed with "Republish/refresh
  your `registry_snapshot` read" — Forge's read side already reloads every iteration; the write
  side (your publisher) is the missing step. Forge will not patch families client-side.

**Asks.**

1. **Re-run the registry publisher** (restart `crucible-registry-publisher` or however a
   republish is triggered) so a fresh `registry_snapshot_*.json` lands with
   `days_since_earnings` → `calendar`. Reply with the new snapshot filename/UTC timestamp.
2. Confirm whether anything ELSE registry-side changed since `2026-06-08T13:22:37Z` that will
   ride along in the new snapshot (new/changed indicators, sizer modes). The `registry_hash`
   will change either way; we want to attribute any mix shift correctly.
3. *(Prevention, optional)* Consider publishing on registry-content change rather than only at
   unit startup. This staleness was invisible to both sides — your tests pass (they exercise the
   publisher code, not the file on disk) and our tests pass (fixtures use the new family) —
   until someone sampled the live mix.

**What Forge does on each answer.**

- **On republish:** nothing to deploy — the run loop calls `load_registry()` fresh each
  iteration, so the next batch picks it up. We verify event_momentum > 0 via the emission-proof
  recipe + the journal submission mix, then relay the new `registry_hash` and the first-emission
  UTC timestamp so you can time-cut the H2 sub-cohort.
- **For your v11→v12 funnel compare meanwhile:** the v12 cohort contains ZERO event_momentum —
  read the H2 arm's absence as this publisher staleness, not gate behavior. H1 rank configs on
  trend/mean_reversion are unaffected.
- **If a republish is blocked or you'd rather wait:** tell us why and roughly when; H2 stays
  structurally dead until then. If the family fix turns out NOT to be what shipped (e.g. the
  runner-internal window of your alternative 1), say so and we'll wire a different-family regime
  gate instead — that's a Forge grammar-change ritual we'd rather not start on a wrong premise.
