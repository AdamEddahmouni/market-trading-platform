# Lane H — Market Trackers SEC 3/4/5 insider adapter preparation spec

## Scope

- Dataset: `insider-transactions` only (not all 18 Market Trackers datasets).
- Deliverables: upstream pin, schema characterization, receipt contract, PIT doctrine,
  EventV1 map prep, public-record evidence prep, candidate feature catalog, golden fixtures.
- Explicit non-goals: live sync, Observation Ingress Router implementation (Lane F), execution
  hooks, trade recommendations, Form 4 sentiment classifiers.

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
│ EventMapPrep                │  INSIDER_OWNERSHIP_ROW / REGULATORY_OWNERSHIP
└──────────────┬──────────────┘
               │ derive_pit_clocks
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
| `source_bundle` | `market_trackers.insider_transactions` |
| `upstream_row_id` | Market Trackers `id` |
| `raw_payload_hash` | Canonical hash of full row |
| `primary_source_url` | `provenance.sourceUrl` (EDGAR deep link) |
| `upstream_pin` | Frozen upstream commits + licenses |
| `quality_flags` | Includes `REPLACEABLE_AGGREGATOR`, `NOT_TRADE_RECOMMENDATION` |

## EventV1 map prep

| Attribute | Value |
|-----------|-------|
| `provider_id` | `market_trackers.sec_insider` |
| `publisher_id` | `sec.edgar` |
| `event_family` | `REGULATORY_OWNERSHIP` |
| `event_type` | `INSIDER_OWNERSHIP_ROW` |
| `channel_id` | `sec.form.{form}` |

Payload core preserves raw codes and explicit `interpretation: regulatory_fact_not_trade_signal`.

## Public-record detector prep

| Attribute | Value |
|-----------|-------|
| `detector_id` | `imp.public_record.sec_form_345_row` |
| `semantic_class` | `SEC_REGULATORY_OWNERSHIP_FACT` |
| `reason_codes` | `SEC_FORM_345_ROW`, `PRIMARY_SOURCE_LINKED`, `AGGREGATOR_ROW_REPLACEABLE` |
| `uncertainty_flags` | Always includes `FORM4_NOT_AUTO_DIRECTIONAL` |

## Observation Ingress Router handoff (Lane F — read only)

When Lane F lands, ingress should:

1. Accept raw bytes + content type `application/json` for a single row or array chunk.
2. Emit `ExternalSourceReceipt` per row with injected `platform_received_time_ns`.
3. Pass `AdapterPrepBundle` to normalization without re-deriving PIT from `transactedAt`.
4. Fail closed on validation errors (no partial admit).

This spec does **not** import Lane F modules; golden tests call `build_adapter_prep_bundle` directly.

## Acceptance

| Check | Status |
|-------|--------|
| Upstream pin documented + coded | MET |
| Schema characterized | MET |
| PIT doctrine encoded | MET |
| XA-01 fail-closed on null ticker | MET |
| Golden fixtures + unit tests | MET |
| Live Market Trackers fetch | NOT_EXECUTED |
