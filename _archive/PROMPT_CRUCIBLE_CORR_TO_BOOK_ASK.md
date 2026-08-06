# Forge → Crucible: corr-to-promoted-book on gated exports (contracts ask)

Date: 2026-07-20. Status: HELD FOR CARRY (operator go required — this is a new
initiative ask, not a response). Companion doc:
`docs/proposals/corr-to-book-feedback.md` (full rationale + what we'd do with
it, each step separately gated our side).

## The ask

Now that the 2-leg book (spec `b36f49a4fe230f96`) is frozen and accruing
forward evidence, would you consider an ADDITIVE per-gated-config field on the
gated-run export (or a sidecar): **correlation of the config's OOS return
stream vs the live promoted book**, computed on the same basis as your §8.7
leg-corr gate? One scalar per live book (a small vector if/when there are
several).

## Why we're asking

- The binding constraint is the joint strong-AND-decorrelated frontier; the
  promotion made "complement to the live book" concrete for the first time.
- We cannot and should not compute this — decorrelation is owned at assembly
  (our D186/D187; your real return streams). We're asking for the RESULT as a
  feedback label, the same shape as every verdict field we already learn from.
- Use our side, in gated steps: (1) telemetry only — distribution reads by
  hypothesis/cell, no ranking change; (2) if the telemetry warrants, a
  PREREGISTERED learned-lane feature so generation stops treating
  strong-and-redundant identically to strong-and-orthogonal; (3) any
  selection-layer use would get its own D-entry + your visibility first.

## Mechanics (your call throughout)

- Additive-only; tolerant-reader safe our side (the 1.29.0
  `parse_skipping_unknown_literals` pattern); we'd adopt via the agreed
  vocab-addition sequencing (the D245 both-restart rule if it lands as a
  schema minor).
- If the compute is not one cheap dot product on artifacts you already hold at
  gate time — or the framing is wrong from your side (e.g. you'd rather keep
  book-relative signals entirely at assembly) — say so and we drop it; the
  honesty-block precedent applies.

## Honesty notes (pre-empting our own failure modes)

- Overfit-to-one-frozen-book is real; that is why step 1 is telemetry-only and
  step 2 is prereg'd (D207 discipline) — we will not silently steer at it.
- We will NEVER treat the scalar as a gate our side (your gate is the gate).
