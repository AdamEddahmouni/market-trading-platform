# Phase 15 — whale public_catalyst family (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** Fixture-first `public_catalyst` whale family on bounded BOXL catalyst slice  
**Prerequisites:** Phase 14 `PASS`, `ADR-WHALE-001` `ACCEPTED`, `ADR-WHALE-007` `ACCEPTED`

## 1. Purpose

Expand Institutional/Whale Intelligence by admitting a bounded public-catalyst fixture and wiring the `public_catalyst` family through the provider + whale ledger spine.

## 2. In scope

- `ADR-WHALE-007`: catalyst envelope semantics, confidence/lean gates, PIT cutoff rules
- Fixture admission `ADMITTED-CATALYST-BOXL-001`
- `FixtureCatalystProvider` adapter (PORT_ADAPT from `catalyst_lane` + internship field shapes)
- Whale ledger query for `public_catalyst` whale_event payloads
- `public_catalyst` institutional family entitlement on BOXL only
- UI read-only `/workspace/BOXL/catalyst` endpoint and capability projection
- Minimal WORKSPACE Catalyst panel

## 3. Out of scope

- Live news/Finviz/social API adapters
- Internship scheduler / paper execution wiring into canonical replay
- Universal whale score or trade recommendations

## 4. Completion definition

Phase 15 is complete when the BOXL fixture ingests deterministically, `public_catalyst` is available for BOXL at entitled cutoffs, other symbols remain fail-closed, UI exposes honest capability states, tests pass offline, and `phase15_status` is published.
