# ADR 0009: Cross-Source Evidence Without Scoring

## Context

Candidate snapshots and broker lending data answer different questions and have different provenance, timestamps, freshness, and missing semantics. Combining them into a strategy score would hide coverage and introduce unvalidated judgment.

## Decision

Build immutable point-in-time evidence bundles containing unchanged canonical observations, explicit domain coverage, diagnostics, and deterministic hashes. The policy selects only evidence available for the requested symbol and time.

## Consequences

Consumers can inspect complementary evidence without treating absence as zero or later data as earlier evidence. Phase 1C produces no score, rank, tier, recommendation, or provider winner.

## Rejected alternatives

A mixed provider row would lose provenance and timing. Weighting or renormalizing sources would add strategy behavior. Backfilling missing values from later observations would violate point-in-time integrity.
