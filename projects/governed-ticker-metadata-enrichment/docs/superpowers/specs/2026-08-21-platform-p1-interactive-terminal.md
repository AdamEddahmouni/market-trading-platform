# Platformization P1 — Interactive Paper Terminal

**Status:** Implemented  
**Date:** 2026-08-21  
**Builds on:** [PLATFORM-PAPER-001 P0 design](../superpowers/specs/2026-08-21-platform-paper-001-design.md)

## Discovered current state (pre-P1)

- P0 delivered orthogonal operating context, event-sourced ledger, read-only `/paper/*` observability.
- P1 backend preview/submit/session APIs existed but UI order ticket was deferred.
- Strategy and interactive paths shared `evaluate_risk` + `BarConservativeSimulator` but not a single executor function.
- No trace API, no cancel path, no adversarial P1 test suite.

## Architecture changes

| Area | Change |
|---|---|
| Execution | `execute_order_intent()` canonical path in `paper/execution.py` |
| Parity | `execute_normalized_intent_for_parity()` + `INTERACTIVE_EXECUTION_PARITY` test |
| Preview | Rich operator envelope (exposure, risk utilization, quality state) |
| Trace | `PaperExecutionLedger.project_execution_trace()` + `GET /paper/trace` |
| Cancel | `POST /paper/orders/cancel` — deterministic; filled orders return `NOT_SUPPORTED` |
| Sessions | `POST /paper/sessions/close` emits `PaperSessionClosed` |
| UI | `OrderTicket`, `ExecutionTracePanel`, expanded `PortfolioPage` |

## Files affected

### Backend
- `src/market_platform_foundation/paper/contracts.py`
- `src/market_platform_foundation/paper/execution.py`
- `src/market_platform_foundation/paper/ledger.py`
- `src/market_platform_foundation/ui_api/paper_projections.py`
- `src/market_platform_foundation/ui_api/server.py`

### Frontend
- `ui/src/api/fetchJson.ts`, `endpoints.ts`, `hooks.ts`, `schemas.ts`
- `ui/src/components/PortfolioPage.tsx`
- `ui/src/components/paper/OrderTicket.tsx`
- `ui/src/components/paper/ExecutionTracePanel.tsx`
- `ui/src/styles/layout.css`

### Tests
- `tests/platform/test_paper_p1.py`
- `ui/src/components/PortfolioPage.test.tsx`

### Docs
- `docs/superpowers/specs/2026-08-21-platform-p1-interactive-terminal.md`
- `docs/superpowers/specs/2026-08-21-platform-p1-order-lifecycle.md`
- `docs/research/PLATFORMIZATION_ROADMAP.md`

## Migration concerns

- Opening a new paper session replaces in-memory ledger (preserves append-only semantics within session).
- `IMP_PAPER_EXECUTION=1` still required locally for submit; CI remains read-only for gated tests.

## Test strategy

- `tests/platform/test_paper_p0.py` — P0 regression
- `tests/platform/test_paper_p1.py` — parity, adversarial, vertical slices (gated)
- `ui` vitest — order ticket gating smoke test
