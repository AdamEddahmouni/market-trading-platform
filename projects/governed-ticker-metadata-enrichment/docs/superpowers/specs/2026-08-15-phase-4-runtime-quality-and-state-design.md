# Phase 4 — runtime quality and state (design spec)

**Status:** Complete — Phase 4 `PASS` published on admitted equity intraday fixture  
**Spec date:** 2026-08-15  
**Scope:** Phase 4 only — bar book state, scoped quality observations, deterministic dataset cache on admitted fixture  
**Prerequisites:** Phase 0 `PASS`, Phase 0A `PASS`, Phase 1 `PASS`, Phase 2 `PASS`, Phase 3 `PASS`

## 1. Purpose

Prove runtime quality and supported bar book state on the admitted equity intraday
fixture without expanding verified capabilities or weakening replay determinism.

## 2. In scope

- Bar book state for `BAR_OHLCV_1M` only; no BBO/MBP/MBO reconstruction.
- Scoped `QualityObservation` records for sequencing, validity, and timeliness on bars.
- Content-addressed byte-bounded dataset cache per `ADR-DCACHE-001`.
- Availability-aware replay with quality on the pinned admitted fixture (two network-denied runs).
- Corruption fixtures proving fail-closed consumer eligibility.
- Assertion registry for `TC-001`, `TC-003`, `DET-001`, and `SAFE-003`.

## 3. Out of scope

- Order-book or depth state.
- Model, strategy, risk, or execution work.
- Provider or broker connections.
- ES futures claims.

## 4. Completion definition

Phase 4 is complete when bar quality replay passes on the admitted fixture,
`TC-001`/`TC-003`/`DET-001`/`SAFE-003` pass, cache determinism is proven, and
`phase4.pass_publication` is published without beginning Phase 5.
