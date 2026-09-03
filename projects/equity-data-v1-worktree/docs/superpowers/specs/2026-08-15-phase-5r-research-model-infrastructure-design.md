# Phase 5R — research/model infrastructure (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-15  
**Scope:** Phase 5R only — research datasets, targets, model interfaces, naive baseline, walk-forward evaluation, artifact identity  
**Prerequisites:** Phase 0 `PASS` through Phase 5 `PASS`

## 1. Purpose

Prove research/model infrastructure on the admitted equity intraday fixture: immutable
research dataset publication, point-in-time walk-forward evaluation, typed forecast
interfaces with explicit fallbacks, and reproducible model artifact identity per
accepted ADRs — without strategy, risk, execution, provider, or neural-network work.

## 2. In scope

- Research dataset manifest and fingerprint from bar-derived feature rows per `ADR-RDATA-001`.
- Forward-return target rows with label availability after the declared horizon per `ADR-PIT-001`.
- Typed forecast interface per `ADR-FCAST-001` with null probability until calibrated.
- Naive last-value baseline model per `ADR-MODEL-001` tuple-rooted identity.
- Walk-forward folds with cutoff boundaries recorded in the run manifest.
- Canonical JSON artifact serialization and reload equality checks.
- Adversarial fixtures for label-leakage and fold-boundary violations.
- Assertion registry for `DATASET-001`, `MODEL-001`, `PIT-WF-001`, `FCAST-001`, `DET-001`, and `SAFE-003`.

## 3. Out of scope

- Neural networks, sklearn, or third-party ML runtimes.
- Strategy, risk, execution, broker, or provider integration.
- Whale ingestion or institutional evidence beyond Phase 5 interfaces.
- Phase 6 preregistration or live/paper orders.
- ES futures or unsupported capability upgrades.

## 4. Completion definition

Phase 5R is complete when the research dataset and naive baseline walk-forward
evaluation pass on the admitted fixture, all six assertions pass, evaluation
determinism is proven under network denial, and `phase5r.pass_publication` is
published without beginning Phase 6.
