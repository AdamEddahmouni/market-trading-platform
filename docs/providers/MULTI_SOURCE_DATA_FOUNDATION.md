# Multi-Source Data Integration Foundation

This document defines the governed, provider-neutral boundary for source-backed
observations. It is additive to the existing market-data and paper execution
contracts; it does not authorize live execution.

## Adding a provider

1. Implement a provider adapter against an existing provider protocol or a
   narrow testable protocol.
2. Register a `ProviderDescriptor` and one or more `CapabilityDescriptor`
   objects. Declare asset classes, venues, interfaces, history/PIT support,
   license class, rate policy, schema version, and normalizer version.
3. Store only credential references (for example, `ENV:VENDOR_API_KEY`), never
   credential values. Credential references and license classes are validated
   against the foundation formats. Keep provider-specific conditions in the
   adapter and descriptor.
4. Add deterministic fixture tests and an operational-readiness note. Runtime
   `ProviderComposition` remains separate from the operational registry.

## Data flow and time

Provider responses are captured as immutable `RawRecord` values. The
provider/source-instance namespace, raw request identity, and content hash
provide deterministic deduplication; redacted request metadata prevents
recognized secrets from entering lineage. A normalizer creates a new
versioned output and never changes the raw record.

`Observation` carries separate nanosecond UTC clocks for event, source
publication, effective, available, received, ingested, normalized, published,
and validity bounds. `available_time_ns` is the point-in-time knowledge clock:
an as-of query must not see an observation before it is available, regardless
of event time. Revisions identify the source revision and may supersede an
earlier observation without mutating it.

## Identity and provenance

Use `InstrumentIdentity.qualified_id()` with namespace, asset class, venue, and
instrument ID. A ticker is an alias, not a universal identity. Provider
identifiers are retained in `ProviderIdentifierMapping`, including source
instance, mapping version, and conflict state. Invalid and `CONFLICT` states
fail closed; `resolve_mapping_conflict()` returns a deterministic, auditable
unresolved decision with every canonical candidate retained. Observation envelopes retain
provider, source instance, raw reference, license, quality, confidence, and
revision lineage as additive fields compatible with current API envelopes.
Optional structured `extensions` carry provider-specific metadata through the
observation, envelope, and normalization paths. Extensions are deeply frozen,
JSON-shaped, limited to 8 KiB and five nesting levels, and reject
secret-bearing keys. Recognized credential patterns in request metadata and
extension strings are redacted; opaque strings with no credential marker must
not be used for secrets.

## Planning and reconciliation

`QueryPlanner` filters registered capabilities by enabled state, health,
PIT/as-of support, license purpose, circuit state, and bounded rate windows.
`QueryRequest.mode`, source-instance, account, and optional provider scope are
validated and included in cache identity. It returns stable priority ordering,
bounded retry metadata, fallback providers, explicit fan-out selection, and
cache policy. `cache_put()`/`cache_get()` implement TTL and stale serving with
a bounded cache. Network execution belongs to the adapter/application service,
not the planner.

`reconcile_candidates` retains every candidate and applies bounded,
datatype-sensitive quality scoring. Its explicit `ReconciliationPolicy`
inspects stale, future, invalid-clock, as-of, and low-confidence candidates.
Numeric values use a declared tolerance;
strings, enums, and objects require exact agreement. Conflicts and outliers
are represented explicitly, while the selected value and selection reason are
deterministic.

## Storage and execution-plane separation

The initial `InMemoryObservationStore` implements operational and analytical
query protocols for bounded local use. It is intentionally not a SQLite tick
warehouse. Future object or analytical storage can implement the same
interfaces. Existing account-scoped caches, local state, paper ledger, mode
authority, risk/preview/submit boundary, and permanent Live execution block
remain authoritative and unchanged.

OpenBB, MCP, object storage, DuckDB, hosted workers, paid consolidated feeds,
and production execution are deferred integration boundaries. Existing IBKR,
NewsAPI/Finnhub, Finviz, Moomoo, and Tradier work remains independently gated
until an adapter is deliberately registered and tested.
