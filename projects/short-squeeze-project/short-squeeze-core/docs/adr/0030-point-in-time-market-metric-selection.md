# ADR 0030: Point-in-Time Market-Metric Selection Reuses `evidence.bars`

## Context

`evidence.bars.build_bar_series` already enforces point-in-time eligibility
(`source_timestamp`/`received_timestamp`/`effective_timestamp` all `<= as_of`), symbol/interval/
session filtering, and deterministic ordering for `MARKET_BARS` (ADR 0023, 0024, 0025). Every
Phase 2A metric needs exactly this same filtering before any calculation runs.

## Decision

`metrics.selection` never filters raw observations by `as_of` itself. Every selector
(`resolve_bar_at_boundary`, `resolve_trailing_window`) takes the observation set and a
`MetricSelectionRequest`, and its first step is always `build_bar_series(...)`. Lifecycle
resolution (choosing the latest eligible `COMPLETED`/`CORRECTED` revision per boundary, excluding
`PARTIAL`/`CANCELLED`/unresolved `CONFLICTED` groups) and provider-ambiguity detection are added
as a layer on top of the already-eligible series, not interleaved with the point-in-time check.

## Consequences

There is exactly one point-in-time gate in the codebase for bar evidence. A future fix to that
gate (e.g. a new availability edge case) automatically applies to both `evidence` and `metrics`
without a second change. `metrics.selection` does duplicate `evidence.bars`'s private
`_metadata_time` helper (reading `bar_start`/`bar_end` from `provenance.provider_metadata`) as a
small local function, since that helper is not exported — a two-call-site duplication accepted
deliberately rather than changing `evidence.bars`'s public surface for Phase 2A's benefit.

## Rejected alternatives

Reimplementing point-in-time filtering directly in `metrics/` (a fourth copy, after
`evidence.builder`'s per-domain checks and `evidence.bars`'s own copy) was rejected: Phase 1's own
audit already flagged this pattern as duplication risk (`phase-1-known-limitations.md`), and a
fourth divergent copy specifically for the metrics layer would make "does this respect
no-look-ahead" a per-file question again instead of a single, already-tested answer.
