# ADR 0005: Offline Adapter Boundary

## Context

Provider acquisition concerns can leak credentials, network state, and unstructured values into canonical observations. Phase 1B must prove normalization independently of acquisition.

## Decision

Define immutable provider-neutral context, diagnostic, rejection, and result models. Provider-specific normalizers consume already-available objects and return typed canonical observations plus structured diagnostics. Acquisition is outside the adapter package.

## Consequences

Normalization is deterministic and testable without provider state. Live acquisition cannot be inferred from this implementation and would require a later, separately reviewed boundary.

## Rejected alternatives

Returning dictionaries would weaken result invariants. Embedding an SDK client would couple contract tests to credentials, entitlement, network, and session state.
