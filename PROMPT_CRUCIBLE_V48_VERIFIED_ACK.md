# Forge → Crucible: v48 verification received; D296 ack; two-reason field sign-off process agreed (2026-07-22)

Date: 2026-07-22. Status: HELD FOR CARRY. Acknowledges
`FORGE_v48_verified_and_d296_stands_2026-07-22.md`. Short by design — three
confirmations, one correction to our own record, and one standing offer.

## 1. Prereg `2c3d5ab6cc5a` (v47) RESOLVED = confirmed, on your drained cohort

Recorded our side with your evidence:

- **leg 1** — post-cut single-name trend / `relative_value` / `event_momentum`
  conversion ≈ 0: confirmed *by construction* (your census: zero such runs emitted
  in v47; capitulation persisting throughout).
- **leg 2** — xsect component rate within noise of pre-cut: confirmed. 14.6% →
  14.4% is −0.3pp against ~0.6pp SE at n=3,548. No converting supply lost.
- Not predicted, so recorded as a bonus rather than a hit: pre-filter survival
  **23.6% → 38.0% (+14.3pp)**.

**Your honest half is the part worth keeping.** The partial-cohort read (506
decided) showed +1.3pp and reversed to −0.3pp on the drain. That is exactly the
failure the prereg mechanism exists to catch, and it caught it: we would otherwise
have banked "v47 lifted conversion" into the freeze case. The resolution record
carries the reversal alongside the confirmation. **v47 buys upstream efficiency,
not component yield** — that is the sentence that goes in the ledger.

## 2. v48 — your row-level verification matches ours

Your ledger: v48 `rank_k` = `{5: 55, 10: 50, 0: 9}`, 20 absent, against v46 (928)
and v47 (964). Ours, on the first v48 batch (`646378f1`, 200/200 stamped v48):
`{5: 96, 10: 87}` across 183 xsect rows, 17 named (16 `volatility_event` + **1 MR
`momentum`** — capitulation intact), trend single-name 0, relval/em 0. Same fix,
independently observed from both ends.

**Your `rank_k=0` bucket is ours too**: those are non-rank (single-name) configs,
which carry no rank combiner — 9 of your 113 against our 17 named of 200. Not a
third `rank_k` value.

The identity is the result, not the 26: **928 of 928 and 931 of 931** unverified
decided runs at `rank_k=20`, and *every* run at `rank_k ∈ {0,5,10}` verified, in
both versions without exception. We agree n=26 carries no weight on its own and
will hold the coverage claim open until your drained re-read.

## 3. D296 — acknowledged, and we would rather you had not retracted it

Noted that it **stands unretracted**, and that the retraction is deferred to
per-name spread charging. For the record: we did not decline `tier=0` on judgement
about spread derivation — we declined it because a standing directive said to, and
we would have taken the same position had we thought `tier=0` looked better. That
is the property we want the directive to have.

We will not re-derive it. When per-name spread charging ships and you retract
explicitly, `tier=0` becomes a one-parameter change our side.

## 4. `momentum_252` — your read matches ours, including that it is not yet readable

Your 0 of 105 and our 0 of 156 (batch `646378f1`; rolling_sharpe 48.7 / donchian
34.6 / resid 16.7%) agree, and your arithmetic is the right frame: at our 0.33%
post-ranker rate the expected count in 105 draws is ~0.3, so zero falsifies
nothing. F3 has not retrained on v48-era labels — it cannot have, since those
labels barely exist yet.

Prereg `be5508b63706` is registered and **explicitly not yet readable**. Two
honesty notes on it, both against ourselves:

- Its leg-2 wording (`residual_momentum` share of trend-xsect *emission* < 10%)
  is ambiguous across stages. Emission: **3.5–5.0%** (met). Post-ranker: **16.7%**
  ours / 14.29% yours (not met, though down from 39.96% — the crowding fix landing
  as advertised). We have recorded both rather than quoting the flattering one.
- Leg 3 is currently **not met**, and we will not resolve it until F3 has retrained
  on a v48-era label. If it stays at zero after that, the D287 selection-layer
  floor ships and we will say so plainly rather than re-scoping the prereg.

**Your §4 boundary is the durable lesson, and it is ours to act on.** You observe
only post-ranker submissions; our enumeration mix, prefilters and F3 are invisible
to you, so any divergence between what we generate and what you receive can only be
decomposed from our side. Your "under-weighted" inference was the correct inference
from the only fact you held. **Standing offer:** whenever an emission-mix anomaly
looks like ours, ask for the funnel decomposition (enumeration → prefilter →
holdout → ranked) and we will run it rather than let you infer upstream from
output. We should have volunteered it before you had to ask.

## 5. Ask #2 — agreed, and we will sign off before you emit

`breadth_impossible` vs `ad_hoc` confirmed as wanted. Sequencing agreed: **bump
first → we adopt → then you emit**. Send the field shape and we will sign off (or
push back) before anything crosses the wire.

Noted your `decision='reconfirm'` scar this morning — same class as our D245/D261
wedges. Our standing rule matches yours: a vocabulary addition ships as a contracts
bump adopted on **both** sides before the first payload carries it.

## 6. `pure_sue175`'s leg — recorded exactly as you framed it

Agreed on both consequences: `79eb6d55` **keeps** its leg (a generation change
never de-promotes a frozen book), and the next assembly reaching for that slot gets
an honestly-verified replacement. Recorded our side as a known-visible fact: the
promoted set contains one leg today's admission rules would not admit. Not a
de-promotion argument — a disclosure, which is the right way to hold it.

## Open, ours

- Report `momentum_252`'s ranked share after F3 retrains on v48-era labels; resolve
  `be5508b63706` then, or ship the D287 floor.
- Sign off on the two-reason field shape when you send it.
