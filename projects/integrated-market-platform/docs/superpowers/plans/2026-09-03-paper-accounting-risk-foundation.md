# Paper Accounting and Risk Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Paper a USD, whole-share, long-only cash account with replay-derived multi-instrument positions, reservations, and monetary risk controls shared by internal and broker-paper execution.

**Architecture:** Preserve the append-only event log and derive an immutable account snapshot from fills, order states, and risk decisions. Keep execution paths separate, but pass both through shared portfolio, pricing, reservation, and risk contracts. Persist only per-instrument mark snapshots; positions and reservations remain replay-derived.

**Tech Stack:** Python 3.11 standard library, SQLite event persistence, React/TypeScript, Zod, Vitest.

## Global Constraints

- Paper mutations remain gated by Paper authority; Demo remains immutable and Live remains observational.
- Existing events and response fields remain readable; new current projections expose additive fields.
- USD, integer shares, long-only cash account; no margin, borrow, short selling, or settlement delay.
- Policy version is `phase7.cash-multisymbol/2.0.0`; order/position notional defaults are $10,000/$100,000 and broker MARKET reserve buffer is 500 bps.
- Fixture replay fails closed when bars do not match the requested instrument.

---

### Task 1: Multi-instrument accounting projection

**Files:**
- Modify: `src/market_platform_foundation/portfolio/ledger.py`
- Modify: `src/market_platform_foundation/paper/ledger.py`
- Test: `tests/platform/test_paper_accounting_risk_foundation.py`

**Interfaces:**
- Produces: `build_ledger_state(initial_cash_minor) -> {cash_minor, positions_by_instrument, ...}` and `apply_fill(state, fill, policy) -> state`.
- Produces: deterministic `PaperExecutionLedger.project_positions()` and expanded `project_account()`.

- [ ] Write tests proving two symbols retain independent quantity, weighted basis, cash, realized P&L, and deterministic ordering; prove a fill that would create negative cash or a short position is rejected.
- [ ] Run the new tests and confirm failure against the single-position state.
- [ ] Implement per-instrument accounting while preserving aggregate compatibility fields for existing internal consumers during migration.
- [ ] Add per-instrument marks and incomplete aggregate valuation semantics.
- [ ] Run the focused accounting tests and existing paper ledger suites.

### Task 2: Replay-derived reservations and shared monetary risk

**Files:**
- Modify: `src/market_platform_foundation/risk/policy.py`
- Modify: `src/market_platform_foundation/risk/decision.py`
- Modify: `src/market_platform_foundation/paper/ledger.py`
- Test: `tests/platform/test_paper_accounting_risk_foundation.py`

**Interfaces:**
- Produces: policy fields `max_order_notional_minor`, `max_position_notional_minor`, and `broker_market_reserve_buffer_bps`.
- Produces: `ledger.project_reservations()` and risk decisions containing requested/approved quantity and notional, pricing facts, reservations, projected cash, and reason codes.

- [ ] Write failing tests for cash-constrained BUY resize, inventory-constrained SELL resize, combined caps, partial-fill reservation reduction, terminal release, stale price rejection, and zero-capacity rejection.
- [ ] Implement reservation projection from orders, risk decisions, fills, and order lifecycle events.
- [ ] Refactor `evaluate_risk` to consume target-position, account/reservation, and risk-pricing facts and calculate the minimum whole-share capacity across every limit.
- [ ] Preserve kill-switch, invalid-intent, and max-open-order hard rejects.
- [ ] Run focused risk and paper suites.

### Task 3: Internal and broker execution integration

**Files:**
- Modify: `src/market_platform_foundation/paper/execution.py`
- Modify: `src/market_platform_foundation/paper/broker_paper.py`
- Modify: `src/market_platform_foundation/ui_api/paper_projections.py`
- Test: `tests/platform/test_paper_accounting_risk_foundation.py`

**Interfaces:**
- Internal MARKET pricing fact: next matching eligible bar high.
- Broker LIMIT pricing fact: limit price; broker MARKET pricing fact: required fresh mark plus 500 bps.
- Admission is serialized by a per-ledger re-entrant lock; broker network I/O occurs after the `SUBMITTED` reservation is persisted.

- [ ] Write failing tests for mismatched replay instruments, concurrent cash admission, broker MARKET mark validation/buffering, and resized broker request quantity.
- [ ] Validate/filter bars by `instrument_id` and fail with `PAPER_INSTRUMENT_DATA_UNAVAILABLE` before simulation.
- [ ] Add serialized admission and ensure persistence failure prevents provider calls.
- [ ] Normalize broker provider requests to the approved quantity while preserving requested intent provenance.
- [ ] Run internal execution, broker paper, reconciliation, and authority tests.

### Task 4: Persistence and policy compatibility

**Files:**
- Modify: `src/market_platform_foundation/local_state/startup.py`
- Modify: `src/market_platform_foundation/paper/ledger.py`
- Test: `tests/platform/test_paper_accounting_risk_foundation.py`

**Interfaces:**
- Snapshot projection contains `marks_by_instrument`; legacy singular mark fields remain loadable.
- Session compatibility includes risk-policy identity. An incompatible open session receives an append-only close event with reason `POLICY_INCOMPATIBLE` before a new session starts.

- [ ] Write failing restart tests for multi-mark snapshots, legacy mark restoration, replay-equivalent reservations, and legacy-policy rollover.
- [ ] Persist/restore per-instrument marks and merge missing optional legacy fields safely.
- [ ] Add policy identity compatibility and auditable incompatible-session closure.
- [ ] Run local-state and paper recovery suites.

### Task 5: API and operator surfaces

**Files:**
- Modify: `src/market_platform_foundation/ui_api/paper_projections.py`
- Modify: `ui/src/api/schemas.ts`
- Modify: existing Paper Portfolio, Paper Now preview, and Workspace ticket presentation components/tests.

**Interfaces:**
- Account adds reserved cash, available buying power, market value, equity, gross notional exposure, unrealized P&L, and valuation quality/reasons.
- Positions add cost basis, notional, per-symbol P&L, reserved shares, and available-to-sell.
- Preview adds requested/approved quantity/notional, pricing fact, projected cash/position, reservations, and binding reason codes.

- [ ] Write failing Zod and component tests for complete/incomplete valuation, monetary limits, reservations, and resized-order explanations.
- [ ] Expand backend envelopes without changing endpoints or request fields.
- [ ] Update frontend schemas and compact operator displays; preserve Workspace-only submit and preview revalidation.
- [ ] Run UI tests, typecheck, and build.

### Task 6: Documentation and closure

**Files:**
- Modify: `docs/architecture/PAPER_DECISION_LIFECYCLE.md`
- Modify: `docs/engineering/WORK_LOG.md`

- [ ] Document long-only accounting, pricing facts, reservations, risk caps, incomplete valuation, and session rollover.
- [ ] Complete the Paper execution SOP checklist against the diff.
- [ ] Run `python tools/imp.py format`, `python tools/imp.py lint`, `python tools/imp.py validate fast`, affected tests, domain validation, and `python tools/imp.py validate full`.
- [ ] Run `npm run test:run`, `npm run typecheck`, and `npm run build` from `ui`.
- [ ] Inspect `git diff --check`, complete diff, and final status; do not stage unrelated files.
