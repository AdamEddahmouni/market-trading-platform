# ADR 0053: Synthetic cases are excluded from historical analysis

## Decision

Synthetic cases form a separate cohort and never enter historical rates, intervals, or empirical interpretations. Synthetic confusion-matrix cells are software truth-table coverage only.

## Consequences

Mixed provenance remains explicit, historical denominators remain honest, and edge-case test coverage cannot inflate empirical samples.
