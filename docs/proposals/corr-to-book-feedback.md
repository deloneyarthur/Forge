# Proposal: corr-to-promoted-book feedback signal (contracts ask) (Theme 3)

Status: **BRAINSTORM DRAFT — operator-gated; the ASK ITSELF needs operator go
before any relay is carried.** No Forge build until Crucible answers.
Date: 2026-07-20. Source: post-promotion process-improvement review.
Relates to: [[D186]]/[[D187]] (decorrelation owned at ASSEMBLY; Forge =
quality + directional variety), [[D292]] (the 2-leg promotion: leg corr
0.065 was a gate), hard rule #2 (contracts gap = surface, never work around).

## The change in the world this responds to

Until 2026-07-20 there was no live book; "decorrelated" had no concrete
referent at generation time, and D186/D187 correctly parked correlation at
assembly. There is now a FROZEN promoted spec (`b36f49a4fe230f96`) accruing
forward evidence. "Complement to the live book" is, for the first time, a
well-defined per-candidate scalar — and only Crucible can compute it (they
hold real return streams; we never will, and should not).

## The ask (contracts gap, their side)

One additive field on the gated-run export (or a sidecar): a
`corr_to_promoted_book` scalar (or small vector, one per live book) per gated
config — the correlation of the config's OOS return stream against the frozen
book's, on whatever basis they already use for the leg-corr gate (their
§8.7). Additive-only, tolerant-reader safe (the D262 pattern); versioned via
the agreed vocab-addition sequencing (D261/D262 lessons; D245 both-restart
sequencing applies if it lands as a schema minor).

## What Forge would do with it (each step separately gated)

1. **Telemetry first** (versionless, inert): record it alongside verdicts;
   distribution reads by hypothesis/cell. No ranking change.
2. **F3/tail feature** (model change, prereg'd): the frontier's second axis
   becomes visible to the learned lane — candidates that are strong AND
   book-orthogonal stop looking identical to strong-and-redundant ones.
3. **Diversifier axis** (selection change, own D-entry): a complement-aware
   reservation analogous to the D103 hypothesis floor — only if the telemetry
   shows the ranked lane systematically under-carries low-corr supply.

## Why this does NOT violate decorrelation-at-assembly

D186/D187's point was that Forge cannot COMPUTE correlation honestly (no
return streams) and must not fake it with signal-overlap proxies. This ask
keeps the computation at assembly (Crucible's), and feeds the RESULT back as
a label — exactly the shape of every other feedback signal we already learn
from (verdicts, gate_results). Steering stays quality + variety; the variety
axis just gains a real measurement.

## Risks / honesty notes

- **Overfit-to-book**: optimizing complement-to-one-frozen-book narrows the
  stream if the book changes. Mitigation: telemetry-first; any ranking use
  prereg'd; the signal is a FEATURE, never a hard gate our side.
- **Their cost**: per-gated-config corr against the book is one dot product
  on artifacts they already hold at gate time — but that is THEIR call; the
  relay should ask, not assume.
- **Latency**: contracts asks have run days-to-weeks (tier_3 key: proposed
  07-20, shipped same day; ref_trailing_return writer: probe-to-heal ~1 day).
  Raise early precisely because the lead time is the long pole.

## Relay draft (to become a PROMPT_CRUCIBLE_* file only on operator go)

> §N — Ask: corr-to-promoted-book on gated exports. Now that
> `b36f49a4fe230f96` is frozen and accruing, would you consider an additive
> per-gated-config scalar: correlation of the config's OOS returns vs the
> live book, same basis as your §8.7 leg-corr gate? Purpose our side:
> telemetry first (distribution reads), then a prereg'd learned-lane feature
> so generation can see the frontier's second axis. Additive/tolerant-reader
> safe; happy to adopt via the agreed vocab sequencing. If the compute or
> the framing is wrong from your side, say so and we drop it.
