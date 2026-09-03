# Phase 3 — verified historical adapter (design spec)

**Status:** Complete — Phase 3 `PASS` published on admitted equity intraday fixture  
**Spec date:** 2026-08-15  
**Scope:** Phase 3 only — one source-specific offline adapter, no models or strategies  
**Prerequisites:** Phase 0 `PASS`, Phase 0A `PASS`, Phase 1 `PASS`, Phase 2 `PASS`

## 1. Purpose

Normalize the admitted Phase 0A equity intraday JSONL fixture reproducibly with
complete provenance and without expanding verified capabilities.

## 2. In scope

- One offline adapter for `ADMITTED-SHORTSQ-BIYA-BARS-001`.
- Canonical `BAR_OHLCV_1M` envelopes per Phase 2 contracts and `ADR-TIME-001`.
- Provenance, coverage, capability, and normalization reports.
- Assertion registry extension for `ADP-001`, `ADP-002`, `SAFE-001`, `SAFE-002`.

## 3. Out of scope

- ES futures or depth/trade/MBO claims.
- Provider or broker connections.
- Model, strategy, risk, or execution work.
- Copying donor bytes into governed paths.

## 4. Completion definition

Phase 3 is complete when the admitted fixture normalizes reproducibly,
`ADP-001`/`ADP-002`/`SAFE-001`/`SAFE-002` pass, and `phase3.pass_publication`
is published without beginning Phase 4.
