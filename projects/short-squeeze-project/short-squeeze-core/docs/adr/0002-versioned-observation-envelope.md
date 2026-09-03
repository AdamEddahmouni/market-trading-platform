# ADR 0002: Versioned Observation Envelope

## Context

Mixed provider rows cannot establish field source, timestamp meaning, freshness, missing semantics, or derivation.

## Decision

Require immutable schema `1.0.0` observations with typed payloads, three timestamps, provenance, quality, kind, session, freshness, and deterministic identity.

## Consequences

More metadata is required at ingestion, but later calculations can identify every input and unsupported versions fail explicitly.

## Rejected alternatives

An unrestricted dictionary is too weak. Reusing the inherited positional row would preserve ambiguity. One timestamp or source label cannot represent mixed timing/provenance.

