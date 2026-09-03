# Phase 12 — whale large_transactions family (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** Fixture-first `large_transactions` whale family on bounded NVDA large-print slice  
**Prerequisites:** Phase 11 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-WHALE-002` `ACCEPTED`, `ADR-WHALE-005` `ACCEPTED`

## 1. Purpose

Expand Institutional/Whale Intelligence beyond `regulatory_disclosure`, `order_flow`, and `options` by admitting a
bounded large-print fixture and wiring the `large_transactions` family through the provider + whale ledger spine.

## 2. In scope

- `ADR-WHALE-005`: large-transaction envelope semantics, size normalization, direction ambiguity policy
- Fixture admission `ADMITTED-LARGE-PRINTS-NVDA-001` (bounded NVDA large-print slice)
- `FixtureLargeTransactionsProvider` adapter (PORT_ADAPT from large_print_lane concepts)
- Generalized whale ledger query for `large_transactions` whale_event payloads
- `large_transactions` institutional family entitlement on NVDA only
- UI read-only `/workspace/NVDA/large-transactions` endpoint and capability projection
- Minimal WORKSPACE Large Transactions panel (print table, quality banner, epistemic badges)

## 3. Out of scope

- Live Moomoo/IBKR tape adapters, `order_book` L2 depth UI, paper execution
- BIYA large-print claims (options fixture remains BIYA-only)
- Universal whale score, trade recommendations, participant identity invention

## 4. Completion definition

Phase 12 is complete when the NVDA fixture ingests deterministically, `large_transactions` is available
for NVDA at entitled cutoffs, other families remain fail-closed where not entitled, UI exposes
honest capability states, tests pass offline, and `phase12_status` is published.
