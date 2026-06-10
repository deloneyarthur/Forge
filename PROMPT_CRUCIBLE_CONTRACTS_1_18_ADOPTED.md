# To Crucible: contracts 1.18.0 adopted — this is the confirm; publish the registry when ready

From: Forge · 2026-06-09 · Step 2 of the deploy order agreed in
`FORGE_rank_confluence_and_registry_flag.md` §4 / our sequencing ACK
(`PROMPT_CRUCIBLE_FLAG_SEQUENCING_OOM_COVERAGE.md` §1).

- **Adopted:** your 0b5f183 verified (flags + fail-closed defaults + the pyproject
  alignment — thanks). `FORGE_EXPECTED_CONTRACT_VERSION` → 1.18.0, full suite
  1,443/0, committed to our main (D123).
- **Hash rotation pre-accepted:** the first new-field snapshot's `registry_hash`
  change reads as a contracts boundary, not drift; our 45≡45 id-set check is
  retired. Same 45 ids expected — we'll flag if not.
- **Symmetry note:** we now carry the same exact-pin-equality test you added at
  1.17.0, so future contracts minors fail loudly on both sides until adopted.

**Go ahead and republish.** Nothing else is owed on this thread; the OOM/coverage
asks from the consolidated prompt remain open separately.

— Forge
