# Platformization roadmap (P0–P6)

**Status:** Active — supersedes informal "Phase 1–5" platform sequencing  
**Authority:** [PLATFORM-PAPER-001](../superpowers/specs/2026-08-21-platform-paper-001-design.md), [PLATFORM-STATE-001](../superpowers/specs/2026-08-21-platform-state-001-design.md)  
**Date:** 2026-08-21

This document tracks the transition from replay-only research UI to a provider-agnostic
market operating platform. It uses **Platformization P0–P6** naming to avoid collision
with governed Phases 0–16.

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| **P0** | Orthogonal modes, event ledger, `/paper/*` API, portfolio observability, CI | **COMPLETE** |
| **P1** | Interactive internal simulation (preview + submit → BarConservativeSimulator) | **COMPLETE_WITH_LIMITATIONS** |
| **P2** | Live observational market data (Moomoo), runtime admission, capability-aware Explore | **COMPLETE_WITH_LIMITATIONS** |
| **P2.1** | Live L1/trades/L2 admission, CVD, internal paper on live marks | **COMPLETE_WITH_LIMITATIONS** |
| **P3** | Durable local SQLite state, operator workflow, restart recovery | **COMPLETE_WITH_LIMITATIONS** |
| **P3.1** | Live internal paper on admitted L1, operator instrument, restart marks | **COMPLETE_WITH_LIMITATIONS** — [P3.1 closure](../superpowers/specs/2026-08-21-platform-p31-live-execution-closure.md) |
| **P3.2** | Unified live decision workstation (`/workspace/{symbol}/evidence`, What Matters Now, evidence drawer) | **COMPLETE** — [P3.2](../superpowers/specs/2026-08-21-platform-p32-unified-live-workstation.md) |
| **P3.3** | Finviz Elite discovery, prospective PIT capture, decision-research foundation | **COMPLETE** — [P3.3](../superpowers/specs/2026-08-21-platform-p33-finviz-discovery-research.md) · [DECISION-RESEARCH-001 milestone A](../superpowers/specs/2026-08-22-decision-research-001-design.md) (OOS gate PASS) |
| **P4** | Tradier/Moomoo paper adapters, idempotency, reconciliation | **SPEC DRAFTED — pending principal review** ([PLATFORM-P4-001](../superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md)); sub-milestones: 4A Tradier sandbox adapter + idempotency, 4B reconciliation, 4C Moomoo execution |
| **P5** | Hosted platform, security, PROVIDER-COMMERCIAL-001 | Not started |
| **P6** | Shadow/forward validation | Not started |
| **LIVE-001** | Production execution (separate authorization) | Blocked |

### P4 design status (2026-08-22)

[PLATFORM-P4-001](../superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md)
drafts the broker-neutral paper execution contract, the Tradier sandbox adapter,
idempotent submission, and the reconciliation engine. Status: **design —
pending principal review**; no implementation has begun. A code-grounded audit
is filed at `.planning/2026-08-22-platform-p4-broker-paper-code-audit.md`
(12/12 code-facing claims verified; one blocking design question on fill
authority plus follow-ups F2–F9 pending review).

## Architecture decisions (locked)

1. **Two-dimensional modes:** `data_mode` × `execution_mode` × `execution_authority` (see `operating_modes.py`).
2. **Event-sourced paper ledger:** append-only events; portfolio is projected (`paper/ledger.py`).
3. **Single execution truth:** user orders use `BarConservativeSimulator`, not cursor-price shortcuts.
4. **Execution bar window:** `bars_for_execution()` from replay cursor forward (no chart look-ahead, valid fill path).
5. **Dual data admission:** research fixture pipeline vs runtime quality pipeline (documented in PLATFORM-PAPER-001).
6. **Local durable state (P3):** SQLite event-sourced paper ledger + operator state. No custom JWT, no hosted auth.
7. **CI in P0:** `.github/workflows/imp-validate.yml` (FAST + CHANGED offline on push/PR; landed 2026-08-22).

## Broker priority (P4)

| Provider | Role |
|---|---|
| **Tradier sandbox** | First execution-contract adapter (order lifecycle; no sandbox Greeks/L2) |
| **Moomoo** | Strategic L2/observational data; separate execution adapter even if same vendor |
| **IBKR** | Multi-asset target when funded ($500 min for many data subscriptions) |
| **Alpaca** | Secondary reference only |

## Correctness metrics

| Metric | Target |
|---|---:|
| Orders with audit/provenance IDs | 100% |
| Duplicate submission under retries | 0 |
| LIVE execution without `IMP_LIVE_EXECUTION=1` | 0 paths |
| Unexplained ledger/broker mismatches (P4+) | 0 |
