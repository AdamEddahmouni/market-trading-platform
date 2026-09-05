# ADR-UX-002 — Chart Framework and Delivery Scope

**Status:** `ACCEPTED`  
**Created:** 2026-08-18  
**ADR ID:** `ADR-UX-002`  
**Logical ID:** `product.adr_ux_002`

## Context

ADR-UX-001 acceptance (2026-08-16) deferred UX-015 (chart framework) and UX-016
(PWA/offline scope). UI-001 implementation authorization requires binding toolchain
decisions before production frontend work begins.

## Decision

### UX-015 — Chart framework

Adopt **Lightweight Charts** (TradingView open-source) for primary OHLCV price
charts in Research UI V1. Use CSS/SVG sparklines for micro charts (attention cards,
compact summaries). Specialized visualizations (order-flow heatmaps, depth ladders)
remain deferred until their modules are separately authorized.

### UX-016 — PWA/offline scope

Adopt **responsive web only** for V1. No service worker, offline cache, or installable
PWA in the initial implementation authorization track. Mobile delivers an intentional
subset per UX-004; offline replay is a later milestone.

## Consequences

- Frontend subject (`ui/`) may declare npm dependencies including `lightweight-charts`
- Foundation subject (`src/market_platform_foundation/`) remains stdlib-only
- PWA scope revisiting requires a separate ADR amendment

## Authority bindings

| Logical ID | Document |
|---|---|
| `product.adr_ux_001` | [ADR-UX-001](ADR-UX-001-navigation-context-explainability.md) |
| `ui1.design_specification` | [UI-001 design spec](../../../superpowers/specs/2026-08-18-ui-001-research-ui-v1-design.md) |
