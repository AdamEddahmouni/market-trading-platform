# ADR 0001: Clean Parallel Core

## Context

Phase 0 found that inherited runtime, provenance, timestamps, persistence, formulas, and GUI concerns are intertwined and lack a safe offline path.

## Decision

Build an independent `short-squeeze-core` repository. Archived repositories remain evidence-only and unchanged.

## Consequences

The foundation is offline and testable without credentials, while later adapters must be migrated deliberately. Temporary duplication is accepted.

## Rejected alternatives

Repairing the inherited application first risks behavior changes before replay evidence exists. Hybrid extraction risks leaking positional rows, global state, and ambiguous freshness into the new contract.

