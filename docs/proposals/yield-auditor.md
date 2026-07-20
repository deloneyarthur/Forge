# Proposal: standing yield auditor — self-serve dead-cell detection (Theme 4)

Status: **DETECTOR BUILT (D302, 2026-07-20)** — `forge yield-audit` ships the
read-only detection half (dead names + cold cells, all guards below, prints a
staged rider draft, writes nothing). Still operator-gated: shipping any
exclusion, the weekly-timer wiring, and OPEN_PROPOSALS auto-staging. First
live run flagged 30 dead names (~21k decided verdicts since the clean era at
zero conversions) + 1 cold cell — CAVEAT: cross-check flags against the
CURRENT universe before acting (names no longer drawn save nothing).
Date: 2026-07-20. Source: post-promotion process-improvement review.
Relates to: hard rule #4 (auto-tightening may ship without approval;
loosening may not), [[D207]] (preregistration discipline), [[D286]]/[[D293]]
(v37/v41 frozen-list exclusion riders), [[D292]] (the drawn-but-dead names
found by THEIR census, not us), [[D273]] (worst-Q label correction — why
sample-size guards matter), memory: prefilter-tightening RETIRED (D206 —
this is NOT that; thresholds were a flat axis, name/cell retirement is not).

## The gap

Every structural exclusion so far was relay-driven: Crucible's census found
ASML 641 decided / 0 components, BKNG 1,254/0, COST 1,544/1, LLY 1,372/0,
SOXX 1,367/0 — on OUR verdicts, which we hold locally. We have shipped the
frozen-list mechanism four times (v34, v37, v41 rider) but never the
detector. Dead supply is pure waste under the fewer/stronger directive
(~4.4k wasted draws/wk was the v37 batch's own number).

## Proposed shape

A weekly (systemd timer, alongside the 05:00 eval) read-only audit over our
verdicts DB snapshot:

- **Per-name single-name yield**: decided n, component n, WF-zero rate —
  flag names with n >= 500 decided and 0 components (the census bar), or
  WF-zero >= 95% at n >= 1,000 (the v34 bar).
- **Per-cell yield** (hypothesis x bucket x exit-shape, the funnel's cell
  vocabulary): conversion vs the family baseline, min-n guarded.
- Output: a STAGED exclusion-rider draft (the v34/v37/v41 frozen-list terms)
  appended to `OPEN_PROPOSALS.md` — **flagged as tightening**, with the
  query + counts embedded, and a prereg line auto-drafted (D207: claim +
  cohort cut BEFORE the exclusion ships, so the read is honest).

## Where the gates sit (unchanged)

- Detection + staging: automatic (read-only; writes only to OPEN_PROPOSALS).
- Shipping: exclusions ride grammar bumps as riders → operator-gated deploy
  window, exactly as today. Hard rule #4 licenses the tightening itself;
  the deploy gate is what stays human.
- Un-excluding (the reverse) is a LOOSENING: never automatic, ever.

## Guards (the D273 lesson: bad labels make confident wrong calls)

- Min-n per flag (>=500 decided) and a family-baseline comparison, never an
  absolute conversion bar alone.
- Ghost-era exclusion: the ve pre-07-18 label cut (D290) applies to every
  read this auditor does; label-provenance work (Theme 2c) feeds directly in.
- Cohort splits by grammar_version + the era time-cuts (D104) — the auditor
  reuses the funnel's cohort discipline, not raw pooled counts.
- Names already structurally excluded are reported (for retire-review when
  their row-45 preflight makes our frozen lists redundant) but never re-flagged.

## Interaction with the campaign registry (D297)

Campaign cells are EXEMPT from auto-flagging while status=farming — a young
concentrated sweep looks exactly like a dead cell until its read matures
(the v33 resid sweep would have flagged in week one). The registry is the
allowlist; another reason it exists.

## Not proposed
- Auto-shipping anything into grammar.yaml (rule #10 versioning + operator
  deploy gate stand).
- Touching prefilter thresholds (D206: that axis is retired, flat on the tail).
