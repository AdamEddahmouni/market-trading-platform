# ADR-0009: Multi-Source Data Integration Foundation

*Status: Accepted — additive foundation*

## Context

IMP has source-specific market-data and disclosure paths, but needs a common
boundary for operational provider capability, identity, provenance, immutable
capture, point-in-time planning, and reconciliation. The boundary must not
turn the governed workstation into an execution router or an unbounded tick
warehouse.

## Decision

Add provider-neutral contracts under
`src/market_platform_foundation/providers/`:

- `registry.py` describes operational capability and provider health/policy;
  it is separate from runtime `ProviderComposition`.
- `identity.py` requires namespaced canonical identities with venue context;
  tickers remain aliases, and conflicting mappings fail closed with an
  auditable resolution record.
- `raw_records.py` stores bounded deeply immutable raw payloads, redacted
  request identity, source-scoped content identity, and idempotent versioned
  normalization lineage.
- `observations.py` preserves explicit UTC nanosecond clocks, acquisition mode,
  source provenance, bounded secret-safe provider extensions, and supersedes
  lineage through `build_observation_envelope`.
- `planner.py` performs deterministic eligibility, PIT, licensing, health,
  bounded-window rate, circuit, TTL/stale-cache, retry, fallback, and fan-out
  planning without network calls.
- `reconciliation.py` retains all candidates, derives bounded
  datatype-sensitive quality factors, inspects stale/invalid timestamps, and
  emits deterministic conflicts and selection reasons.
- `storage.py` defines bounded operational/analytical query boundaries.

## Safety consequences

No execution provider, mode authority, account identity, paper ledger, risk
gate, preview/submit flow, or Live block is changed. Source data remains
observational and research-governed. Credential values are never part of
registry, raw metadata, diagnostics, or envelopes.

## Deferred

OpenBB, MCP, paid feeds, object storage, DuckDB, worker/event-bus deployment,
and production execution remain deferred. Existing provider-specific clients
must be migrated deliberately through descriptors and deterministic tests.

## References

- [Multi-source foundation](../../providers/MULTI_SOURCE_DATA_FOUNDATION.md)
- [Mode authority](../MODE_AUTHORITY.md)
- [Data contracts](../DATA_CONTRACTS.md)
