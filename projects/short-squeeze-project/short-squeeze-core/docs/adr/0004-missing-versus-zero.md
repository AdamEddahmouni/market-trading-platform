# ADR 0004: Missing Versus Zero

## Context

The inherited system sometimes converted unavailable indicators to neutral or zero values, making evidence coverage ambiguous.

## Decision

Keep nullable values and a required quality object. Numeric zero is a value; missing, unavailable, not applicable, stale, delayed, invalid, conflicted, and estimated are explicit states with reasons.

## Consequences

Consumers must handle quality deliberately and cannot assume `null == 0`. Conflict resolution is deferred.

## Rejected alternatives

Sentinel numbers contaminate formulas. A single validity boolean cannot express delay, staleness, conflict, or applicability. Silently selecting one conflicting source is outside Phase 1A.

