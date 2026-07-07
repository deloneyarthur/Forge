# PROMPT: Crucible — contracts 1.24.0 coordination closed (Forge ack)

> **🗄️ ARCHIVED 2026-07-06 (D248): the final ack of the CLOSED 1.24.0 coordination (D244).**
> Nothing owed either side.

**From:** Forge · **To:** Crucible · **Date:** 2026-07-05
**Re:** `../Crucible/docs/handoffs/FORGE_contracts_1.24.0_closed_2026-07-05.md`

Closed on Forge's side too. Nothing owed. Two quick acks:

1. **Keep the publisher deferred — agreed, it's the right call.** No consumer until the F3
   bucket-training migration (behind ve-supply, D243), and the DBProxy-client restart risk (wedging the
   db-writer accept loop) isn't worth incurring for zero current benefit.
2. **We do NOT need the `failure_buckets` key in the file sooner.** Your `mode="before"` validator
   auto-computes it from `gate_results` on our read, so Forge already has the buckets available from
   every no-field export. That means the **F3 migration consumes buckets without any publisher
   restart** — there's no plumbing dependency to pre-stage. When/if a coordinated publisher restart is
   ever actually wanted (e.g. we want the key literally present for some downstream reason), Forge will
   flag it explicitly; until then, leave it on old code.

Thread closed. Framing unchanged: hygiene, not a promotion lever.
