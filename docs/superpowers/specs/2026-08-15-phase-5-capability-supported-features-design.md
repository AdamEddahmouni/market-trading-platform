# Phase 5 — capability-supported features (design spec)

**Status:** Complete — Phase 5 `PASS` published on admitted equity intraday fixture  
**Spec date:** 2026-08-15  
**Scope:** Phase 5 only — bar-derived feature snapshots, institutional evidence vocabulary interfaces, PIT guards  
**Prerequisites:** Phase 0 `PASS`, Phase 0A `PASS`, Phase 1 `PASS`, Phase 2 `PASS`, Phase 3 `PASS`, Phase 4 `PASS`

## 1. Purpose

Prove capability-supported feature surfaces on the admitted equity intraday fixture
without claiming institutional evidence dimensions that lack entitled sources and
without weakening replay determinism or point-in-time semantics.

## 2. In scope

- Bar-derived `FeatureSnapshot` rows from `BAR_OHLCV_1M` only.
- Eight institutional evidence family interfaces per `ADR-WHALE-001`, fail-closed to
  `unavailable` without entitled sources.
- Prediction-cutoff guards per `ADR-PIT-001`.
- Availability-aware feature replay on the pinned admitted fixture (two network-denied runs).
- Adversarial fixtures for future-input rejection and institutional overclaim attempts.
- Assertion registry for `CAP-001`, `PIT-FEAT-001`, `WHALE-001`, `DET-001`, and `SAFE-003`.

## 3. Out of scope

- Whale ingestion, filings, order book, options flow, or fund-flow data.
- Model, strategy, risk, execution, provider, or broker work.
- Phase 5R research datasets, targets, or model artifacts.
- ES futures or depth/trade/MBO claims.

## 4. Completion definition

Phase 5 is complete when bar-derived feature snapshots pass on the admitted fixture,
`CAP-001`/`PIT-FEAT-001`/`WHALE-001`/`DET-001`/`SAFE-003` pass, feature replay
determinism is proven, and `phase5.pass_publication` is published without beginning
Phase 5R.
