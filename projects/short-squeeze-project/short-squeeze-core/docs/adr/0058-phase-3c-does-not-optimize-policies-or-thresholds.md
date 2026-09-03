# ADR 0058: Phase 3C does not optimize policies or thresholds

## Decision

Every analysis consumes explicit versioned Phase 3B and Phase 3C policies. It performs no threshold search, grid search, hyperparameter optimization, backtest, or rule weighting.

## Consequences

Analysis identities are reproducible policy statements, and future policy research cannot silently mutate historical results.
