# Phase 9 — provider interfaces and SEC EDGAR whale ingestion (design spec)

**Status:** Complete — Phase 9 whale disclosure slice implemented on offline fixtures  
**Spec date:** 2026-08-16  
**Scope:** Broker-neutral provider contracts, fixture-first EDGAR disclosure ingestion, whale ledger, institutional feature wiring, UI-001 read-only disclosure API  
**Prerequisites:** Phases 0–8 `PASS`, UI-001 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-PIT-001` `ACCEPTED`

## 1. Purpose

Implement the first Institutional/Whale Intelligence slice authorized after the serial foundation: capability-split provider contracts and offline-first SEC EDGAR disclosure ingestion wired into existing ADR-WHALE-001 fail-closed interfaces.

## 2. In scope

- `ADR-PROV-001`: capability-based provider Protocol contracts (stdlib only).
- `ADR-WHALE-002`: whale ledger identity, amendment ordering, disclosure-lag labeling, PIT cutoff semantics.
- Fixture-first `DisclosureProvider` adapter (PORT_ADAPT from squeeze donor reference; no donor code copy).
- Append-only JSONL whale ledger with deterministic replay hash.
- `regulatory_disclosure` institutional family wired when ledger is entitled; other seven families remain fail-closed.
- UI-001 read-only `/workspace/{symbol}/disclosure` endpoint and capability projection updates.
- Optional live EDGAR fetch gated by `IMP_EDGAR_LIVE=1` and `SEC_USER_AGENT` (excluded from CI).

## 3. Out of scope

- Tradier/Moomoo live adapters, paper execution, CVD/L2, IBKR, composite buy scores.
- Live UI refresh, whale ingestion for non-disclosure families.
- ES futures, crypto, prediction-market expansion tracks.

## 4. Completion definition

Phase 9 whale disclosure slice is complete when provider contracts exist, EDGAR fixtures ingest deterministically into the whale ledger, `regulatory_disclosure` is available on BIYA replay when entitled, all other whale families remain unavailable, UI/API expose honest delayed-disclosure labeling, and the full test suite passes offline.
