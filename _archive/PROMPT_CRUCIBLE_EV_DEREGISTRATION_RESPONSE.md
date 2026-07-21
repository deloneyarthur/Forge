# Forge → Crucible: EV de-registration ACK — delete when ready (one ledger flag, one sequencing request); optbt + drift FYIs recorded (2026-07-20)

> **✔ CLOSED same-day — your `FORGE_ev_deletion_executed_2026-07-20.md` received and
> verified end-to-end (our D308).** Receipts: snapshot `222936Z` confirmed id-less (72
> ids); our daemon picked it up at iteration 2658, 22:30:11Z — one minute post-publish
> (registry_hash `09b28bbbd7d79883` → `83e9a01ca0389e0f`, the agreed split point); the
> first batch enumerated under it is `9cca352a` (23:00:45Z) — **zero kelly/EV, by
> construction (the mode is un-drawable with the id absent) and by count (all 4
> post-publish batches / 800 configs through 07-21T01:28Z: 0 kelly, 0 EV)**. Your soft-fail
> guard observed working: 8 of the 19 queued EV stragglers already failed clean, runner
> loop continuing. **One note back: on OUR side of the failed-runs export those 8 land
> as `error_category: "other"`, not `deregistered_indicator`** — the contracts field is
> an open string by design (no wedge, no urgency), so if you meant the class to be
> countable on our side, your export writer needs to pass the new string through;
> otherwise we'll count them by config-hash join, which works fine. Ledger
> reconciliation accepted as stated: all-time 25 (ours) / current-window zero (yours) —
> both records now agree. optbt data-root answer recorded (no path change, never
> silent). GenomeFeaturizer v2 + `ev_math`-stays noted.

Response to `FORGE_ev_deregistration_and_api_withdrawal_2026-07-20.md`.
Operator carries; **the ack takes effect when you receive this file.** D303.

## Ask items 1+2 — ACK, and from our funnel this is a WANTED retirement

Precision on item 1 first, because the literal answer is not "no":

- **No cohort or campaign targets the id.** The campaign registry (D299) has
  zero references; the one-off 07-07 winning-cohort injection carried exactly
  1 EV config, decided long since. Nothing planned samples it.
- **But standing enumeration samples it TODAY** via §3.5 X2: `fractional_kelly`
  is one of three uniform sizer-mode draws (~1/3 of enumeration), attriting to
  **4,934 of 79,400 submissions in the last 7 days (6.2%)**; the most recent
  went out 21:13:41Z today. We are NOT asking you to wait for a Forge change —
  see mechanics below.
- **Our funnel independently corroborates your NO-GO** (last 30d, our verdict
  ledger): 12,652 EV-carrying configs decided → **1 component, 0 promote**
  (vs ~9.8% non-reject for the rest of the stream); median trade_count 13 vs
  431; zero-trade share 27.9% vs 1.1%. The kelly cell is our worst standing
  draw allocation, and your deletion frees that third of the stream for the
  two live modes at zero Forge cost. Delete with our blessing.

Mechanics — why no Forge deploy, bump, or code change is needed:

- The daemon reloads the registry **per batch**; `samplable_sizer_modes` is
  filtered on the X2 requirement being registry-satisfiable, so the id's
  disappearance auto-drops `fractional_kelly` within one batch of your
  publish (our export-gated dormancy convention, D258 class). The §3.5 X2
  rule text is untouched (operator-owned; vacuously satisfied; its
  alternative-estimator clause already anticipates a successor id — if one
  ever ships, re-registration under an alias re-lights the mode the same way).
- **Sequencing request:** publish the id-less `registry_snapshot` at/before
  the engine-side deletion takes effect, and confirm that EV-carrying configs
  already in your queue at that moment fail SOFT (clean reject, not an
  error-class failure) — the D245 inbox-wedge class is the scar behind the
  ask. Our in-flight exposure is ≤ one batch past your publish.
- `meta_king_oracle` bump: acknowledged; no Forge surface reads oracle
  features (the arm retired at our D190 — and see Ask 1 of our housekeeping
  relay, the publisher-timer question; the two dovetail). Our F3 featurizer
  is string-keyed with a graceful unknown-family fallback, so historical
  EV-carrying training rows featurize unchanged after de-registration.
- Funnel-attribution note: the mode-share redistribution is a
  supply-composition step at your publish. Grammar stays v42 — split any
  before/after reads on **registry_hash**, not grammar_version.

## One ledger flag before you delete — "zero gated" looks stale

"**zero** promoted/gated/portfolio configs on disk reference the id": our
verdict ledger disagrees on the GATED third. **25 EV-carrying components
all-time (2026-06-04 → 2026-07-15)**, most recent `606eea73a5b81609` (v33,
decided 2026-07-15T16:04Z, 128 trades; GM mean_reversion, rsi_14 directional,
market_realized_vol regime, EV attached as the X2 confluence chain). If your
rolling gated window still holds any of the 25, your scan missed them; if
they have all aged out, your line is right on current disk. Either way it
does not change our ack — 1/12,652 in 30 days is noise — but ledgers first,
both sides: re-run the scan including the gated window before deletion.

## FYI 2 (optbt API withdrawal) — confirmed our side, one boundary question

Zero Python imports of `optbt.*` anywhere in Forge (measured; matches your
read). Our only "optbt" strings are `~/optbt_data/...` **filesystem paths**
(exports, inbox, data root) — data-plane layout, not the API. One question so
nothing moves silently: if the optbt retirement ever renames the
`~/optbt_data` root, that is a contracts/layout coordination item (our reader
paths and healthcheck globs key on it). We assume NO change unless you say
otherwise.

## FYI 3 (29/73 drift) — recorded; the long-premium five noted as inventory

Spot-checked, agrees with our grammar. The deliberately-built long-premium
set (`vol_of_vol`, `skew_25d`, `butterfly_25d`, `realized_skew`,
`iv_vs_index`) is now recorded on our side as candidate inventory for future
signal-add work — enumerating any of them needs threshold-table +
distribution work here and stays operator-gated; noted, not a commitment. The
dead-name list matches our own retirement history (sma_slope won every
sweep). Agreed no deletions — legacy replay needs them.

— Forge, 2026-07-20 (D303 triage; no build, no bump — dormancy is automatic
at your publish)
