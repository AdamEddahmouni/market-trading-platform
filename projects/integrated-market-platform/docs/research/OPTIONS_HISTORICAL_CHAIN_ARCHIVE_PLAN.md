# Options Historical Chain Archive Plan (O1 — design only)

**Status:** Design document — implementation NOT STARTED  
**Date:** 2026-08-18  
**Authority:** Supplements O1 in `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`

---

## Purpose

Define how expired and point-in-time historical option chains will be stored, replayed, and entitled — without implementing ingestion or synthetic backfill in this phase.

## Scope

| In scope (this document) | Out of scope |
|---|---|
| Storage format contract | Live vendor ingest (Tradier-class) |
| PIT replay selection rules | Synthetic chain reconstruction |
| Entitlement / admission boundaries | UI chain archive browser |
| Dependencies on O1 spec registry + corp actions | Backtest execution harness |

## Storage format (proposed)

Each archived chain slice is an immutable record:

```text
OptionChainArchiveRecord
├── archive_id            # stable content hash
├── underlying_id
├── as_of_time            # ISO-8601 event_time of chain snapshot
├── available_time        # when chain was knowable (envelope semantics)
├── provider_id
├── entitlement
├── contracts[]           # canonical OptionContract dicts (O1 schema)
├── chain_quality         # GOOD | DEGRADED | UNAVAILABLE
├── spec_registry_version # options spec_registry symbology at ingest
└── provenance_ref        # source file / vendor revision
```

Expired chains remain addressable by `(underlying_id, as_of_time)` — never by "current" chain lookup.

## Replay contract

1. `as_of_time_ns` (prediction cutoff) selects records where `available_time <= cutoff`.
2. Chain provider returns the **latest** eligible slice per underlying at cutoff (not future leaks).
3. Corporate-action-adjusted contracts retain `CORPORATE_ACTION_ADJUSTED` and explicit `deliverable`; `ADJUSTED_DELIVERABLE_UNKNOWN` excludes from surface fit (O2).
4. Chain path filters on `event_time`; activity whale path filters on envelope `available_time` — both must be documented per slice at admission.

## Entitlement boundaries

- Archive bytes are admitted only via `tests/fixtures/providers/options/admission_manifest.json` (or successor manifest) with explicit capability claims.
- No archive record is synthesized from partial activity feeds.
- Live archive extension requires provider authorization (deferred).

## No fake backtests guard

Per `OPTIONS_CAPABILITY_GAP_ANALYSIS.md`:

- Do not interpolate missing strikes or expirations across archive gaps.
- Do not backfill OI or volume from adjacent days without explicit vendor fields.
- Research harnesses must declare `chain_archive_available: false` when archive slice is missing.

## Dependencies

| Dependency | Status |
|---|---|
| O1 `OptionContract` schema | Done |
| O1 quality taxonomy + corp action flags | Done (fixture scope) |
| O1 `options/spec_registry.py` | Done |
| O1 `OptionChainSnapshot` workspace wiring | Done |
| Provider authorization for historical vendor | Not started |

## Implementation milestones (future)

1. `OptionChainArchiveProvider` protocol extending `OptionChainProvider`
2. Fixture archive slices for BIYA/NVDA (expired expiries)
3. PIT integration tests mirroring `test_chain_pit_envelope.py`
4. Admission manifest + phase gate

---

**Next action when authorized:** implement fixture archive slices for one expired expiry before any live vendor work.
