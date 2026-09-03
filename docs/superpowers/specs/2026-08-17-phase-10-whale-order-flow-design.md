# Phase 10 — whale order_flow family (design spec)

**Status:** Complete — Phase 10 order_flow slice implemented on NVDA fixture  
**Spec date:** 2026-08-17  
**Scope:** Fixture-first `order_flow` whale family on bounded NVDA CVD demo slice  
**Prerequisites:** Phase 9 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-WHALE-002` `ACCEPTED`, `ADR-WHALE-003` `ACCEPTED`

## 1. Purpose

Expand Institutional/Whale Intelligence beyond `regulatory_disclosure` by admitting a bounded
order-flow fixture and wiring the `order_flow` family through the provider + whale ledger spine.

## 2. In scope

- `ADR-WHALE-003`: order-flow envelope semantics, aggressor provenance, PIT cutoff rules
- Fixture admission `ADMITTED-CVD-NVDA-ORDERFLOW-001` (bounded NVDA 1sec slice)
- `OrderFlowProvider` Protocol + fixture adapter (PORT_ADAPT from CVD Bubble candle shape)
- Generalized whale ledger query for `whale_event` payloads
- `order_flow` institutional family entitlement on NVDA only
- UI read-only `/workspace/NVDA/order-flow` endpoint and capability projection
- Minimal WORKSPACE Order Flow panel (CVD series, quality banner, epistemic badges)

## 3. Out of scope

- Live Moomoo/IBKR adapters, `order_book` L2 heatmap UI, paper execution
- BIYA order-flow claims (bars fixture remains BIYA-only)
- Options, catalyst, and other whale families

## 4. Completion definition

Phase 10 is complete when the NVDA fixture ingests deterministically, `order_flow` is available
for NVDA at entitled cutoffs, other families remain fail-closed where not entitled, UI exposes
honest capability states, tests pass offline, and `phase10_status` is published.
