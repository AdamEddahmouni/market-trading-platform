# Phase 13 — whale order_book family (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-19  
**Scope:** Fixture-first `order_book` whale family on bounded NVDA depth slice  
**Prerequisites:** Phase 12 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-WHALE-002` `ACCEPTED`, `ADR-WHALE-006` `ACCEPTED`

## 1. Purpose

Expand Institutional/Whale Intelligence beyond `regulatory_disclosure`, `order_flow`, `options`, and
`large_transactions` by admitting a bounded order-book snapshot fixture and wiring the `order_book`
family through the provider + whale ledger spine.

## 2. In scope

- `ADR-WHALE-006`: order-book envelope semantics, snapshot policy, imbalance/OFI derivation, PIT cutoff rules
- Fixture admission `ADMITTED-L2-NVDA-001` (bounded NVDA depth snapshot slice)
- `FixtureOrderBookProvider` adapter (PORT_ADAPT from Eric_futuresX ladder concepts)
- Generalized whale ledger query for `order_book` whale_event payloads
- `order_book` institutional family entitlement on NVDA only
- `depth.L2` capability projection when entitled
- UI read-only `/workspace/NVDA/order-book` endpoint and capability projection
- Minimal WORKSPACE Order Book panel (snapshot ladder, imbalance/OFI summary, quality banner, epistemic badges)

## 3. Out of scope

- Live Moomoo/IBKR L2 adapters, L2 heatmap UI, paper execution
- ES futures session (deferred per ADR-DATA-001)
- BIYA order-book claims (bars fixture remains BIYA-only)
- Universal whale score, trade recommendations, participant identity invention

## 4. Completion definition

Phase 13 is complete when the NVDA fixture ingests deterministically, `order_book` is available
for NVDA at entitled cutoffs, other families remain fail-closed where not entitled, UI exposes
honest capability states, tests pass offline, and `phase13_status` is published.
