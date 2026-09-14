# Lane H — Market Trackers congressional PTR adapter preparation spec

## Scope

- Dataset: `congress-trades` only (STOCK Act Periodic Transaction Reports).
- Deliverables: upstream pin, schema characterization, receipt contract, PIT doctrine,
  EventV1 map prep, public-record evidence prep, candidate feature catalog, golden fixtures.
- Explicit non-goals: live sync, Observation Ingress Router implementation, execution hooks,
  trade recommendations, political interpretation, LONG/SHORT mapping from disclosed buy/sell.

## End-to-end contract

```text
┌─────────────────────────────┐
│ Market Trackers row (JSON)  │
└──────────────┬──────────────┘
               │ validate_market_trackers_row
               ▼
┌─────────────────────────────┐
│ ExternalSourceReceipt       │  platform_received_time_ns (caller-injected)
└──────────────┬──────────────┘
               │ map_event_v1_prep + XA-01 ticker resolution
               ▼
┌─────────────────────────────┐
│ EventMapPrep                │  CONGRESSIONAL_PTR_ROW / REGULATORY_DISCLOSURE
└──────────────┬──────────────┘
               │ derive_pit_clocks / reconcile_congressional_clocks
               ▼
┌─────────────────────────────┐
│ PitClocksPrep               │  filedAt day-bound; not transactedAt for availability
└──────────────┬──────────────┘
               │ build_public_record_evidence
               ▼
┌─────────────────────────────┐
│ PublicRecordEvidencePrep    │  OE-facing deterministic descriptor
└─────────────────────────────┘
```

`build_adapter_prep_bundle` returns the full structure for fixture tests and future ingress.

## ExternalSourceReceipt fields

| Field | Purpose |
|-------|---------|
| `receipt_id` | Hash-stable id over bundle + row hash + prep version |
| `source_bundle` | `market_trackers.congress_trades` |
| `upstream_row_id` | Market Trackers `id` (`{chamber}:{docId}:{rowIndex}`) |
| `raw_payload_hash` | Canonical hash of full row |
| `primary_source_url` | `provenance.sourceUrl` (Senate eFD or House Clerk deep link) |
| `upstream_pin` | Frozen upstream commits + licenses |
| `quality_flags` | Includes `REPLACEABLE_AGGREGATOR`, `NOT_TRADE_RECOMMENDATION` |

## EventV1 map prep

| Attribute | Value |
|-----------|-------|
| `provider_id` | `market_trackers.congressional_disclosure` |
| `publisher_id` | `senate.efd` or `house.clerk` (by `chamber`) |
| `event_family` | `REGULATORY_DISCLOSURE` |
| `event_type` | `CONGRESSIONAL_PTR_ROW` |
| `channel_id` | `congress.ptr.{chamber}` |

Payload core preserves raw disclosed side, amount range text/bounds, and
`interpretation: regulatory_fact_not_trade_signal`. **No** `execution_side` or LONG/SHORT fields.

Code: `market_trackers.congressional_disclosure.event_v1_mapping`.

## Public-record detector prep

| Attribute | Value |
|-----------|-------|
| `detector_id` | `imp.public_record.congressional_ptr_row` |
| `semantic_class` | `CONGRESSIONAL_REGULATORY_DISCLOSURE_FACT` |
| `reason_codes` | `CONGRESSIONAL_PTR_ROW`, `PRIMARY_SOURCE_LINKED`, `AGGREGATOR_ROW_REPLACEABLE` |
| `uncertainty_flags` | Always includes `PTR_NOT_AUTO_DIRECTIONAL`, `DISCLOSED_SIDE_NOT_EXECUTION_SIDE` |

## Proposed normalization registry patch (not applied this lane)

When ingress + primary PTR reconcile are mature:

```python
# intelligence/normalization/registry.py (proposed)
from .providers.market_trackers_congressional_disclosure import normalize_congressional_disclosure_row

register_normalizer("market_trackers.congressional_disclosure", normalize_congressional_disclosure_row)
register_normalizer("market_trackers.congressional_disclosure.row", normalize_congressional_disclosure_row)
```

Runtime `normalize_congressional_disclosure_row` is **not** implemented in Phase 3 Lane H to avoid
colliding with SEC production vertical ownership and premature production ingest claims.

## Observation Ingress Router handoff (read only)

Same pattern as SEC insider prep: accept JSON row, emit receipt + bundle, fail closed on validation
errors, never derive availability from `transactedAt` alone.

## Acceptance

| Check | Status |
|-------|--------|
| Upstream pin documented + coded | MET |
| Schema characterized | MET |
| PIT doctrine encoded | MET |
| XA-01 fail-closed on null ticker | MET |
| Golden fixtures + unit tests | MET |
| Live Market Trackers fetch | NOT_EXECUTED |
| Runtime registry normalizer | NOT_IMPLEMENTED (by design) |

**Lane acceptance token:** `CONGRESSIONAL_DISCLOSURE_ADAPTER_PREP_READY`
