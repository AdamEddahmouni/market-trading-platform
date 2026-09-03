# P0 — Bitemporal Reference Store (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** In-memory append-only reference store with market-valid and knowledge-valid intervals, plus centralized PIT joins for futures specs, symbol mappings, options OI, earnings calendars, and dividend assumptions  
**Prerequisites:** ADR-REF-001 ACCEPTED, Platform P0 event `available_time` replay, F1 spec registry, O7 event-vol, P1 corporate event registry

## 1. Purpose

Event streams already filter on `available_time`. Reference facts (contract specs, OI, earnings dates, dividend yields, symbol maps) were still uni-temporal. A later correction could leak into earlier as-of queries.

This slice adds a **bitemporal reference store** and **centralized PIT joins** so as-of lookup requires both an effective market time and a knowledge time. Resolves O-23 on fixture scope. Does not add a database, DatasetStore, or live earnings ingest.

## 2. Interval semantics

```text
visible(record, market_time, knowledge_time) =
  valid_from <= market_time < valid_to
  AND known_from <= knowledge_time < known_to
```

- `valid_from` / `valid_to`: when the fact applies in the market
- `known_from` / `known_to`: when the platform could know that version
- `valid_to` and `known_to` are exclusive
- Empty `valid_to` or `known_to` means open-ended
- Empty `valid_from` or `known_from` is illegal — append fail-closed
- Times are canonical ISO-8601 UTC strings (nanosecond precision, `Z` suffix)

Corrections append a new `record_version`. Silent overwrite is forbidden. Two records for the same `(kind, entity_key)` may not have overlapping valid intervals **and** overlapping known intervals.

## 3. Record kinds (v1)

| Kind | `entity_key` | Payload |
|---|---|---|
| `FUTURES_SPEC` | family (`ES`) | multiplier, tick_size, tick_value, point_value, spec_version |
| `SYMBOL_MAPPING` | instrument id | venue_id, provider_symbol |
| `EARNINGS_CALENDAR` | underlying (`NVDA`) | earnings_event_time, event_type |
| `DIVIDEND_ASSUMPTION` | underlying | dividend_yield |
| `OPTIONS_OI` | underlying or `UNDERLYING:EXPIRY` | open_interest |

## 4. Output contracts

`join_as_of(kind, entity_key, market_time, knowledge_time)` returns:

- `status` — `AVAILABLE` | `UNAVAILABLE`
- `record` — visible `ReferenceRecord` or `None`
- `payload` — dict or empty
- `record_version` — int or `None`
- `quality_flags` — `REFERENCE_UNAVAILABLE`, `LOOKAHEAD_REJECTED` (later version exists but `known_from` is after knowledge time), `REFERENCE_SUPERSEDED` (returned version has a later `known_from` sibling not visible)

Missing join fail-closes: `UNAVAILABLE`, no invented payload.

## 5. Consumers

- `resolve_futures_spec(family, as_of: date)` — unchanged signature; `as_of` is both market and knowledge time at `00:00:00.000000000Z`. Backed by the store (default ES `es_cme_v1` from 2020-01-01).
- `CorporateEventRegistry.query_events` — thin adapter: visibility uses `known_from=available_time` (open `known_to`), `valid_from=available_time` (open `valid_to`). Announced future `event_time` remains visible once known.
- `build_event_vol_snapshot` — when `reference_store` is passed and no explicit `earnings_event`, resolve `EARNINGS_CALENDAR` via `join_as_of`. `UNAVAILABLE` → existing `EARNINGS_DATE_UNKNOWN` fail-closed path. Explicit `earnings_event` still wins.

## 6. Quality flags

- `REFERENCE_UNAVAILABLE`
- `REFERENCE_SUPERSEDED`
- `LOOKAHEAD_REJECTED`
- Options consumers may also surface `EARNINGS_DATE_UNKNOWN` / `OI_STALE` / `DIVIDEND_UNCERTAIN` when the join is missing

## 7. Fixtures

| Fixture | Admission |
|---|---|
| `p0_bitemporal_slice.json` | `ADMITTED-P0-REF-001` — ES spec correction, NVDA earnings revision, OI restatement, dividend restatement, ES symbol map |
| `p0_bitemporal_expected.json` | Golden as-of query results for P0-S1 |

## 8. Gate milestone P0-S1 (fixture scope)

Aggregate PASS when all of:

- Pre-correction knowledge time sees original ES spec / NVDA earnings / OI / dividend
- Post-correction knowledge time sees restated versions
- Knowledge time before `known_from` never returns the correction (`LOOKAHEAD_REJECTED` when a later version exists)
- Overlapping append is rejected
- Missing entity fail-closes `UNAVAILABLE`

## 9. Out of scope

- Database / DatasetStore / live calendars
- Rewriting every adapter `available_time` filter
- sklearn, vendor feeds, SHARED P4 fusion

## 10. Completion definition

Fixture ingest produces deterministic as-of results, PIT adversarial tests pass, P0-S1 gate reports aggregate PASS, `resolve_futures_spec` and O7 calendar joins use the store, O-23 marked resolved (fixture scope), full test suite remains green.
