# MC2–MC3 — Entity Resolution + Event Clustering (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** MC2 entity resolution and MC3 deduplication/event clustering on admitted BOXL raw-document fixtures  
**Prerequisites:** MC1 IMPLEMENTED, Platform P0 identity

## 1. Purpose

Resolve raw information documents to canonical entities and cluster duplicate/syndicated coverage into `InformationEvent` objects. Prevent article count from equaling catalyst count. Never default missing entity semantics to neutral.

## 2. MC2 — Entity resolution

| Input | Output |
|---|---|
| `EntityClaim` rows (symbol, issuer, exchange, security_type) | `EntityResolution` with deterministic `entity_id` |
| `RawDocument` + symbol registry | `RawDocument` with `associated_entity_ids` / `associated_symbols` |

**Temporal rules:**

- Entity resolution does not alter `event_time` or `available_time`
- Missing symbol → `ENTITY_RESOLUTION_FAILED`; no directional cluster
- Conflicting claims → `ambiguous=True` + `ENTITY_AMBIGUOUS`

**Identity policy:**

- `entity_id_from_symbol(symbol, exchange="US")` via UUID5 `NAMESPACE` (same as participant IDs)
- Fixture scope: 1:1 `SymbolMapping` (`instrument_id = symbol`)

## 3. MC3 — Event clustering

**Cluster key:** `(canonical_event_type, primary_entity_id, event_time_calendar_day)`

**Dedup:** normalized headline hash or `revision_of_document_id` lineage merges into same cluster.

**Syndication:** `independent_source_count` = distinct `source_origin_id` roots (fallback `source_id` when origin absent).

**PIT:**

- Include document only when `available_time <= prediction_cutoff`
- Cluster `available_time` = max(document `available_time`)
- Cluster `event_time` = min(document `event_time`)

**Corroboration:**

| Independent sources | State |
|---|---|
| 1 | `UNVERIFIED` |
| 2 | `PARTIALLY_CORROBORATED` |
| 3+ | `CORROBORATED` |

**Quality flags:** `EVENT_DUPLICATE` on absorbed duplicates; `EVENT_CLUSTER_UNCERTAIN` when entity ambiguous or event type missing.

## 4. Fixture outcome

`boxl_raw_documents_slice.json` (8 documents) → **5** `InformationEvent` clusters matching BOXL catalyst types.

## 5. Out of scope

- Live news ingest
- FinBERT bridge (MC4)
- Catalyst provider refactor
- Full CUSIP / corporate entity graph

## 6. Completion definition

MC2–MC3 complete when fixture pipeline produces deterministic entity IDs and 5-cluster `InformationEvent` output, syndication independent counts validate, PIT adversarial tests pass, MC-D02/MC-D13 resolved (fixture scope), and full test suite remains green.
