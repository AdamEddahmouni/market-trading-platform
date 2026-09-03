# Phase 11 — whale options family (design spec)

**Status:** Complete — Phase 11 options slice implemented on BIYA fixture  
**Spec date:** 2026-08-17  
**Scope:** Fixture-first `options` whale family on bounded BIYA options-activity slice  
**Prerequisites:** Phase 10 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-WHALE-002` `ACCEPTED`, `ADR-WHALE-004` `ACCEPTED`

## 1. Purpose

Expand Institutional/Whale Intelligence beyond `regulatory_disclosure` and `order_flow` by admitting a
bounded options-activity fixture and wiring the `options` family through the provider + whale ledger spine.

## 2. In scope

- `ADR-WHALE-004`: options envelope semantics, volume/OI normalization, direction ambiguity policy
- Fixture admission `ADMITTED-OPTIONS-BIYA-001` (bounded BIYA options activity slice)
- `FixtureOptionsProvider` adapter (PORT_ADAPT from options_lane + internship field shapes)
- Generalized whale ledger query for `options` whale_event payloads
- `options` institutional family entitlement on BIYA only
- UI read-only `/workspace/BIYA/options` endpoint and capability projection
- Minimal WORKSPACE Options panel (activity table, quality banner, epistemic badges)

## 3. Out of scope

- Live Tradier/sandbox adapter, full options chain grid UI, Greeks/IV surface charts
- NVDA options claims (order_flow fixture remains NVDA-only)
- Universal whale score, trade recommendations, paper execution

## 4. Completion definition

Phase 11 is complete when the BIYA fixture ingests deterministically, `options` is available
for BIYA at entitled cutoffs, other families remain fail-closed where not entitled, UI exposes
honest capability states, tests pass offline, and `phase11_status` is published.
