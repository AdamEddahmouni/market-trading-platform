# Phase 2 — canonical contracts and replay (design spec)

**Status:** Complete — Phase 2 `PASS` published on synthetic fixtures  
**Spec date:** 2026-08-15  
**Scope:** Phase 2 only — contract definitions, synthetic replay, no adapters or models  
**Prerequisites:** Phase 0 `PASS`, Phase 0A `PASS`, Phase 1 `PASS`

## 1. Purpose

Establish provider-neutral canonical contracts and minimal availability-aware replay
on synthetic fixtures before any real adapter or model work begins.

## 2. In scope

- Event envelope, quality, reference-data, and decision-chain contracts per Revision 3.
- Exact numeric types per `ADR-NUM-001`.
- Timestamp semantics per `ADR-TSP-001` and `ADR-TIME-001`.
- Deterministic ordering per `ADR-ORD-001`.
- Schema compatibility machinery per `ADR-SCH-001`.
- Synthetic adversarial fixtures proving `available_time` visibility.
- Assertion registry extension for `TC-001`, `TC-002`, `TC-003`, `DET-001` on synthetics.

## 3. Out of scope

- Real historical adapter (Phase 3).
- Provider or broker connections.
- Model, strategy, risk, or execution code.
- DuckDB/SQLite physical storage implementation (`ADR-STORE-001` decision only; implementation separately authorized).
- ES futures claims while admitted fixture remains equity OHLCV only.

## 4. Completion definition

Phase 2 is complete when contract round-trip and compatibility assertions pass on
synthetic fixtures, replay lifecycle is deterministic, and a qualifying postreview
gate publishes `phase2.pass_publication` without beginning Phase 3.

## 5. Governing ADRs

All accepted Phase 1 contract ADRs bind, especially: `ADR-NUM-001`, `ADR-TSP-001`,
`ADR-ID-001`, `ADR-ID-002`, `ADR-SEQ-001`, `ADR-SRC-001`, `ADR-ORD-001`,
`ADR-SCH-001`, `ADR-REF-001`, `ADR-RUN-001`, `ADR-DET-001`, `ADR-OFF-001`.
