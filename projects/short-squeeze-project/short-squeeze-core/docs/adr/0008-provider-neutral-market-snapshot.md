# ADR 0008: Provider-Neutral Market Snapshot

## Context

A Finviz-shaped screener row is a descriptive point-in-time snapshot. It is not a trade, consolidated quote, defined market bar, published short-interest report, borrow record, catalyst, or strategy decision.

## Decision

Add `MARKET_SNAPSHOT` and an immutable nullable `MarketSnapshotPayload` to schema `1.0.0`. The payload uses provider-neutral descriptive names, including `short_float_percent`, and keeps the row as one coherent observation.

## Consequences

Existing observations and fixture bytes remain valid and unchanged. Future adapters can emit compatible snapshots without embedding provider or strategy terminology. Observation-level provenance and diagnostics must retain uncertainty and partial-field limitations.

## Rejected alternatives

Encoding the row only in provider metadata would make canonical consumers depend on opaque keys. Emitting one event per field would manufacture artificial events. Reusing trade, quote, bar, or published short interest would mislabel the evidence.
