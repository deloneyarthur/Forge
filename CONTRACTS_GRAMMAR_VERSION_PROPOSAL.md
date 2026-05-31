# Contracts proposal — carry `grammar_version` in the submission payload (config_hash-stable)

> **From:** Forge (D096) · **To:** a `crucible_contracts` agent · **Type:** additive, minor version bump
> **Status:** PROPOSAL (operator chose "ship the interim join-map now + propose this durable change").
> **Depends with:** `FUNNEL_INSTRUMENTATION.md` (Crucible funnel, Stage 0), `CRUCIBLE_FUNNEL_FORGE_HANDOFF.md`.

## Problem

Crucible's funnel must slice every run by the grammar version that produced it (`FUNNEL_INSTRUMENTATION.md` Req 1 / Stage 0). Its spec assumes the version arrives in the submission metadata. It cannot today:

- `submit_candidate` writes the **bare** `StrategyConfig` JSON to the inbox (`queries.py`: `tmp.write_text(config.model_dump_json(indent=2))`) — no envelope, no metadata.
- `StrategyConfig` is `model_config = ConfigDict(frozen=True, extra="forbid")` with **no `grammar_version` field** (`models.py`).

So there is nowhere for the version to ride. Forge ships an interim `config_hash → grammar_version` join-map (D096 Part A) to unblock the funnel now; this proposal is the durable fix that matches Crucible's Stage 0 as written.

## Hard constraint: `config_hash` must not change

`config_hash` is the cross-system identity key — Crucible's `runs` PK, Forge's `submissions` unique index (hard rule #9), QuantIQ's reference, and the join-map's key. It is `_short_sha256(self.model_dump(mode="json"))`. **Adding a field that enters the hash would re-key every config**, breaking dedup continuity, idempotency, and all historical joins. The change must leave `config_hash` byte-identical for every existing config.

## Proposed change (recommended)

Add an **optional** field excluded from the hash:

```python
class StrategyConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    ...
    grammar_version: str | None = None   # NEW — the Forge grammar version that produced this config

    @property
    def config_hash(self) -> str:
        # Exclude grammar_version so the identity hash is unchanged for all
        # existing configs (it describes provenance, not strategy semantics).
        return _short_sha256(self.model_dump(mode="json", exclude={"grammar_version"}))
```

- **Optional + `None` default** → back-compat: existing constructors and in-flight inbox files (which lack the field) still validate and deserialize. `extra="forbid"` is satisfied because the field is now declared.
- **Excluded from `config_hash`** → every historical hash, the `submissions` unique index, Crucible's `runs` PK, and the join-map all stay valid. (Property test below pins this.)
- Single-object inbox file is unchanged in shape (still one `StrategyConfig` JSON), so Crucible's existing parser keeps working; it gains one optional field to read.

### Alternative considered — envelope in `submit_candidate` (rejected)
Wrapping the inbox file as `{"config": {...}, "grammar_version": "v4"}` also avoids touching `config_hash`, but it changes the inbox **file format**, forcing a more invasive change to Crucible's inbox watcher (parse an envelope, not a bare config) and to anything else reading the inbox. The optional hash-excluded field is the smaller blast radius and keeps the file a single `StrategyConfig`.

## Tests contracts should add
- **`config_hash` invariance:** for any config, `cfg.config_hash == cfg.model_copy(update={"grammar_version": "v4"}).config_hash` (the load-bearing property).
- Round-trip: `StrategyConfig.model_validate_json(cfg.model_dump_json())` preserves `grammar_version` (set and unset).
- `extra="forbid"` still rejects genuinely-unknown fields.

## Versioning
Additive optional field → **minor** version bump. No breaking change.

## Adoption after it lands
- **Forge:** set `grammar_version` when constructing the submitted config (the value is already in hand per batch — `BatchContext.grammar_version`); bump the contracts pin; keep emitting the join-map as a transition-period cross-check, then retire it.
- **Crucible:** inbox watcher reads `config.grammar_version` into `runs.grammar_version` directly — Stage 0 as originally specified. No join needed once backfilled.

Until this lands, the D096 join-map (`forge_submission_versions.json`) already makes Crucible's funnel fully version-sliceable, so this is not on the critical path — but it is the clean long-term contract.
