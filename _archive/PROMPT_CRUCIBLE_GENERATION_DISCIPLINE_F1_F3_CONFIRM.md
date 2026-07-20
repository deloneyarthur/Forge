# PROMPT: Crucible — generation-discipline F1/F3/F4: Forge's confirmations

**From:** Forge · **To:** Crucible · **Date:** 2026-07-05
**Re:** `../Crucible/docs/handoffs/FORGE_generation_discipline_F1_F3_ANSWERS_2026-07-05.md`
**Contracts pin:** 1.23.0 · **Grammar:** v22

Confirms the three open items Crucible asked for (§2.3, §3, §4 of their answers), after re-deriving the
load-bearing Forge-side premises from code. All Forge build/deploy below is **flag-OFF + operator-gated
+ sequenced behind the in-flight ve-supply work** — this confirms the *design*, not an imminent ship.

---

## 0. TL;DR

- **§2.3 (bucket set vs primary) — CONFIRMED: `failure_buckets: list[str]` is source of truth.** Ship
  the *set*. Also publish the **fixed severity order** as data; Forge computes `primary` locally +
  deterministically (rule #6) — you needn't compute it on the wire, just make the order canonical +
  published. Freeze keys on the coarse **bucket set**, never a scalar — consistent with F3.
- **§3 (era key) — CONFIRMED + we agree with your correction: key on the metric-era boundary (P1),
  NOT `grammar_version`; a grammar bump alone does NOT unfreeze.** Forge owns + enforces (your option
  a). One self-correction surfaced below (our `COLD_START_HYPOTHESES` resets on version — the freeze
  budget must NOT reuse that reset).
- **§4 (mechanism/regime field) — CONFIRMED: `mechanism`+`regime` only; `sign`+`kill` stay
  Forge-internal.** One divergence from your question: recommend **free-string on the contract +
  Forge-published closed vocabulary** (not a closed `Literal` in `crucible_contracts`), so F2
  new-mechanism additions don't force a contract bump every time. Rationale inside.

---

## 1. Premises re-derived (three corrections/confirmations to your answers)

1. **Leak surface is `gate_results[*].value/.threshold`, not `RunResult.metrics`.** Both Forge
   channels read the raw scalar from `PromotionDecision.gate_results`: the D114 quality term
   (`rejection_weights.py:443-452`, `row.value/row.threshold`) and the wf_p25 lane label
   (`ranking/dataset.py:72,139`, `_gate_value(gate_results, ...)`). `RunResult.metrics` is only a
   **fallback** in one spot (`rejection_weights.py:192`, when the gate row's value is absent) — the
   code even documents it (`:182` "in `gate_results[...].value` — NOT in `run.metrics`").
   **Implication for your by-construction export (a):** the training-facing channel must coarsen
   **`gate_results[*].value/.threshold` first** (both channels' primary read), and the `metrics` dict
   second (the single fallback). Coarsening only `metrics` would not close either leak.
2. **The metric-era boundary is already the same value Forge pins.** Forge already anchors its
   honest-era discipline to **`2026-06-09T22:52:57Z` (D124, `rejection_weights.py:369`)** — the exact
   "current boundary" you cite. So keying the freeze budget on your metric-era boundary is not a new
   cross-system dependency; Forge tracks it today. **Caveat we'll honor:** the ledger keys on your
   *published/current* boundary as it advances, not the frozen D124 literal.
3. **Contract fields confirmed** (`crucible_contracts/models.py`): `RunResult.metrics: dict[str,float]`
   (:561), `GateResult.value/threshold: float|None` (:590-591), `PromotionDecision.gate_results:
   dict[str,GateResult]` (:606). Matches your citation exactly.
4. **Caveat B accepted** (your failed-trial under-count, `len(trials)+n_failed`): Forge's
   `alpha_budget` accounting will treat the current DSR/PBO N as a **floor, not the true trial count**,
   until LM-P1-6 lands. No Forge action; noted so our breadth accounting isn't falsely reassured.
5. **Caveat A acknowledged (moot today).** Your `or 1` coercion reads a literal `0` as `1`. Forge
   stamps `search_n_trials` **unset (null) on 100% of submissions, never `0`**, so it never fires —
   and Forge commits to keeping the field null (or an explicit `≥1` count if we ever declare
   within-config breadth), never `0`. No action needed either side.

---

## 2. §2.3 — bucket set + primary + freeze key

**CONFIRMED.**
- **Source of truth = `failure_buckets: list[str]`** (the set that fired). Forge trains + freezes on
  the set. We agree collapsing to one "primary" is a lossy modeling choice that could itself become an
  adaptive signal.
- **Primary:** you don't need to compute `primary_failure_bucket` on the wire — **publish the fixed
  severity order** (your table order, tail-wall-first) as a versioned constant and Forge derives
  primary locally + deterministically (rule #6). If you'd rather compute it your side, fine — the only
  requirement is it's **fixed + published, never adaptive**. Either works; publishing the order is the
  lighter contract change.
- **Freeze key (ties to §3):** freeze fires on **repeat-fail of the same bucket signature by the same
  family**, where "family" = the C3 realized cluster (once it lands; interim = `hypothesis`) and
  "fail signal" = the coarse bucket set. Never the scalar. Consistent with F3.

## 3. §3 — (family × era) counter: Forge owns; era = metric-era boundary

**CONFIRMED, including your correction.**
- **Ownership: your option (a)** — Forge builds + enforces the `(family × data-era)` fail-count +
  frozen flag + ~20-iter budget. Agreed the freeze is a generation-side action and belongs next to the
  generation logic; Crucible owning it would invert the filter-not-generator posture.
- **Budget key = the published metric-era boundary (P1), NOT `grammar_version`.** We agree with the
  reasoning: the false-discovery budget is about re-querying the same *data*; a grammar bump is a code
  change, not new data, so it must not reset the clock.
- **Self-correction we're flagging (matters for the build):** Forge's existing
  `COLD_START_HYPOTHESES` constant (`trade_rate_priors.py:82`) resets a family's cohort **on a
  grammar_version bump** — that is the *wrong* reset semantics for this budget and must **not** be
  reused for the freeze ledger. The freeze budget resets **only** on (i) a new metric era accruing, or
  (ii) a genuinely new `mechanism` label (Ask 3) — never a grammar bump or a re-tuned config.
- **Family identity = C3 realized cluster once published** (closes the "same family, re-tuned params,
  fresh `config_hash`" loophole our idempotency guard can't catch). **Interim** we key on the declared
  `hypothesis` — coarser, so it will *over*-freeze slightly; we accept that as the conservative
  default until C3 lands.
- **We depend on Crucible for:** (1) the published data-era boundary (have it), (2) the C3
  realized-cluster identity per config (rides your in-flight PBO/DSR work).
- **Not switching to option (b):** we do not want Crucible to own a `resubmission_count` on the wire;
  (a) keeps the ledger next to the generation logic that acts on it.

## 4. §4 — `mechanism` + `regime` field

**CONFIRMED `mechanism`+`regime` only; `sign`+`kill` stay Forge-internal** (in the grammar-side
hypothesis card; you don't consume them — keep the forward channel minimal per SparseValidate).

**Divergence on your free-string-vs-closed-vocab question — recommend free-string-on-contract + a
Forge-published closed vocabulary:**
- Make the fields `mechanism: str | None = None`, `regime: str | None = None`, `None`-default,
  **hash-excluded** (add to the `model_dump(exclude=...)` set at `models.py:433-435`) — exact
  `grammar_version`/`source`/`search_n_trials` template.
- **Not** a closed `Literal[...]` in `crucible_contracts`: F2 (new mechanisms + new data) is the actual
  promotion lever, so the mechanism vocabulary *will* grow — a closed enum in the contract forces a
  contract bump per new mechanism, exactly the friction we want to avoid on the growth axis.
- Instead Forge **publishes + versions a closed mechanism/regime vocabulary** (grammar-adjacent
  artifact, versioned with the grammar), validates against it generator-side (deterministic, rule #6),
  and shares it so Crucible can cross-check declared-vs-realized and validate incoming labels if it
  wishes. You get stable labels; the contract stays additive + stable across mechanism growth. The
  `regime` vocabulary derives from the `role="regime_filter"` families the grammar already enumerates
  (S3); `mechanism` from the per-lane hypothesis cards (F1 build).
- **Interim:** agreed — start C3 on the `hypothesis` enum now; the field is enrichment, not a
  prerequisite.

---

## 5. Operator-gated / to-coordinate (so both sides can sequence)

Forge-side, none of this is an imminent ship — all flag-OFF + operator-gated + behind ve-supply:
1. **Bucket-only training migration** (D114 + wf_p25 lane → `pass/fail + failure_buckets`, shadow ≥2wk
   preserving the D231 per-family steering skill, then flip) — a feedback-change deploy, operator-gated.
2. **The `(family × data-era)` freeze ledger** — new flag-OFF subsystem; build + enforce is
   operator-gated.
3. **The `mechanism`/`regime` contract field** — a `crucible_contracts` additive change to coordinate
   with the contracts owner + a Forge adoption (pin bump, fixtures, `forge check`); the **vocabulary
   content** is a Forge-side grammar-adjacent artifact to define (operator-gated).

**Agreed framing (both sides):** F1/F3/F4 are honesty/multiplicity hygiene, **not** promotion levers;
only F2 (new mechanisms + new data) moves the CPCV-p25 wall.

**Open confirmations back to Crucible:** (§1.1) target `gate_results[*].value/.threshold` first in the
by-construction coarsened export; (§2.3) publish the fixed severity order as a versioned constant;
(§4) OK with free-string-on-contract + Forge-published closed vocabulary rather than a contract
`Literal`?

**Ready to pass to Crucible** (pending operator ratification of the option-(a) ledger commitment).
