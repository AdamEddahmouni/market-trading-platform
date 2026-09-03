# ADR 0024: Immutable Partial, Completed, and Corrected Bars

## Context

Providers may publish partial, completed, corrected, or cancelled versions of one boundary.

## Decision

Emit immutable observations and connect only explicit provider supersession facts. Preserve unresolved same-boundary disagreements as conflicts; do not mutate, average, or choose a provider winner.

## Consequences

Every as-of reconstruction is reproducible and later corrections are visible without rewriting prior evidence.

## Rejected alternatives

Latest-row mutation destroys history. OHLCV averaging creates a value no provider reported.

