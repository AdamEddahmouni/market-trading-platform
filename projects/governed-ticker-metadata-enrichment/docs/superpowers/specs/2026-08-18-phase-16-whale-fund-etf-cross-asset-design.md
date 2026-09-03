# Phase 16 — whale fund_etf_cross_asset family (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** Fixture-first `fund_etf_cross_asset` whale family on bounded NVDA flow-proxy slice  
**Prerequisites:** Phase 15 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-WHALE-008` `ACCEPTED`

## 1. Purpose

Complete the eight-family whale vocabulary by admitting a bounded fund/ETF cross-asset synthetic fixture and wiring `fund_etf_cross_asset` through the provider + whale ledger spine.

## 2. In scope

- `ADR-WHALE-008`: fund/ETF flow proxy and cross-asset envelope semantics
- Fixture admission `ADMITTED-ETF-CROSSASSET-NVDA-001`
- `FixtureFundEtfProvider` adapter and `fund_etf_lane` formulas
- Whale ledger query for `fund_etf_cross_asset` payloads
- Entitlement on NVDA only
- UI read-only `/workspace/NVDA/fund-etf` endpoint and capability projection

## 3. Out of scope

- Live ETF flow APIs, 13F rows (those remain `regulatory_disclosure`)
- Universal whale score or trade recommendations

## 4. Completion definition

Phase 16 is complete when the NVDA fixture ingests deterministically, all eight whale families have fixture-first entitlement where admitted, tests pass offline, and `phase16_status` is published.
