# 14m — G15 Current-State Matrix (Product Acceptance, Browser E2E, Validation Performance, Archive-First Deprecation)

**Status:** CLOSED (2026-09-09 G15 implementation + closure validation pass)  
**Starting FULL baseline:** 4391 / 48 / 0 / 0  
**G15 closure FULL:** **4392 / 48 / 0 / 0** (2026-09-09)  
**G15 closure E2E:** **6 / 0 / 0 / 0** (`validate e2e`, Playwright 10 browser scenarios)  
**UI:** 454 Vitest · typecheck PASS · bundle **202.94 KiB gzip** (budget ≤ 203.00 KiB)

## G15 delivered components

| Component | Path | Role |
|---|---|---|
| E2E harness | `tools/e2e/harness.py` | Deterministic API + Vite startup, fixture Paper session, Playwright runner |
| Playwright specs | `e2e/tests/*.spec.ts` | Equity Paper, derivative surfaces, isolation, routing, live safety, product status |
| Validation tier | `tools/validation_manifest.json` (`product_acceptance`, tier `e2e` only) | E2E gate via `imp.py validate e2e` |
| Route ref resolver | `ui_api/instrument_selector.py` (`resolve_instrument_route_ref`) | UI symbol routes → canonical XA-01 ids for product projections |
| Dead-route census | `tools/e2e/dead_route_census.py` | BL-0803 evidence artifact |
| Performance artifact | `artifacts/g15-validation-performance.json` | BL-0801 measured timings |
| E2E SOP | `docs/engineering/sops/PRODUCT_ACCEPTANCE_E2E.md` | Operator/developer startup path |

## Product acceptance evidence

| Scenario | Browser-proven | Notes |
|---|---|---|
| Equity Paper preview/submit | YES | Real API boundary; `preview_id` on submit |
| Options contract surface | YES | `NVDA20260815C00130000` route + multiplier semantics |
| Futures contract surface | YES | `ES202512` margin-aware surface |
| Demo ↔ Paper isolation | YES | Paper positions not shown as Demo truth |
| Canonical route round-trip | YES | Equity, option, futures headings |
| Live execution blocked | YES | No submit in Live mode |
| Structured product status | YES | Options surface shows AVAILABLE (not generic no-data) |

## Backlog movement

| Item | Pre-G15 | Post-G15 |
|---|---|---|
| BL-0802 Paper workflow E2E | OPEN | **CLOSED** — Playwright + harness green |
| BL-0801 Validation performance | OPEN | **MEASURED** — artifact; FULL 539s vs ~588s preflight reference |
| BL-0803 Dead-route cleanup | OPEN | **ARCHIVE_FIRST** — deprecation headers on legacy GET paper routes; census complete |
| BL-0701 Query-key migration | DEFERRED (G14) | **STILL OPEN** — evidence in `artifacts/g15-query-key-debt.json` |

## Explicit non-goals preserved

- No BL-0701 broad lane query-key migration (bundle budget)
- No Wave 7 IA redesign
- No live broker execution
- Legacy workspace lane query keys retained
